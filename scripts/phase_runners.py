from pathlib import Path


def phase1_story_dna(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, model="glm51"):
    mark_step_running(project_dir, "phase1_story_dna", ["story.txt", "director_intent.json"])
    update_progress(project_dir, "phase1", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    intent = load_json(Path(project_dir) / "director_intent.json")
    dna = run_llm("story_dna.md", {"story_text": story_text, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "story_dna.json", dna)
    update_progress(project_dir, "phase1", "done")
    mark_step_done(project_dir, "phase1_story_dna")
    return "done"


def phase2_beats(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, generate_beats_viewer, model="glm51"):
    mark_step_running(project_dir, "phase2_beats", ["story.txt", "director_intent.json", "story_dna.json"])
    update_progress(project_dir, "phase2", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    beats_validation = {"type": "object", "key": "beats", "min_items": 1}
    beats = run_llm("beat_analysis.md", {"story_text": story_text, "story_dna": story_dna, "director_intent": intent}, model=model, validation=beats_validation)
    if intent.get("q5b_voiceover_rewrite") == "preserve_original":
        for beat in beats.get("beats", []):
            beat["voiceover"] = beat.get("content", "")
    elif intent.get("q5_voiceover_type", "").startswith("C"):
        for beat in beats.get("beats", []):
            beat["voiceover"] = ""

    visual_input = {
        "story_text": story_text,
        "director_intent": intent,
        "story_dna": story_dna,
        "beats": [
            {k: v for k, v in beat.items() if k not in ("scene", "visual_hint")}
            for beat in beats.get("beats", [])
        ]
    }
    visual_validation = {"type": "object", "key": "beats", "min_items": len(beats.get("beats", [])) or 1}
    visual_plan = run_llm("visual_hint_generation.md", visual_input, model=model, validation=visual_validation)
    visual_map = {b.get("beat_id"): b for b in visual_plan.get("beats", [])}
    for beat in beats.get("beats", []):
        vb = visual_map.get(beat.get("beat_id"), {})
        if vb.get("scene"):
            beat["scene"] = vb["scene"]
        if vb.get("visual_hint"):
            beat["visual_hint"] = vb["visual_hint"]

    save_json(Path(project_dir) / "story_beats.json", beats)
    generate_beats_viewer(project_dir)
    update_progress(project_dir, "phase2", "waiting_gate", "等待 Gate 0 确认")
    mark_step_done(project_dir, "phase2_beats", review="pending")
    return "waiting_gate"


def phase3_characters(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, generate_character_viewer, model="glm51"):
    mark_step_running(project_dir, "phase3_characters", ["story.txt", "director_intent.json", "story_dna.json"])
    update_progress(project_dir, "phase3", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    intent = load_json(Path(project_dir) / "director_intent.json")

    chars = run_llm("character_card.md", {"story_text": story_text, "story_dna": story_dna, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "characters.json", chars)

    visuals = run_llm("character_visual.md", {"characters": chars, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "character_visuals.json", visuals)

    generate_character_viewer(project_dir)
    update_progress(project_dir, "phase3", "waiting_gate", "等待 Gate 1 确认")
    mark_step_done(project_dir, "phase3_characters", review="pending")
    return "waiting_gate"


def step_phase4a_lookdev(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, model="glm51"):
    print("  [4a] Look Development...")
    mark_step_running(project_dir, "phase4a_lookdev", ["story_dna.json", "director_intent.json"])
    lookdev = run_llm("lookdev.md", {
        "story_dna": load_json(Path(project_dir) / "story_dna.json"),
        "director_intent": load_json(Path(project_dir) / "director_intent.json")
    }, model=model)
    save_json(Path(project_dir) / "lookdev.json", lookdev)
    update_progress(project_dir, "lookdev", "done")
    mark_step_done(project_dir, "phase4a_lookdev")
    return lookdev


def step_phase4b_color_script(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, model="glm51"):
    print("  [4b] Color Script...")
    mark_step_running(project_dir, "phase4b_color_script", ["story_beats.json", "director_intent.json", "lookdev.json"])
    beats = load_json(Path(project_dir) / "story_beats.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    lookdev = load_json(Path(project_dir) / "lookdev.json")
    beats_min = {"beats": [
        {k: v for k, v in b.items() if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")}
        for b in beats.get("beats", [])
    ]}
    cs = run_llm("color_script.md", {"story_beats": beats_min, "director_intent": intent, "lookdev": lookdev}, model=model)
    save_json(Path(project_dir) / "color_script.json", cs)
    mark_step_done(project_dir, "phase4b_color_script")
    return beats, intent, cs


def step_phase4c_photography(project_dir, beats, intent, run_llm, load_json, save_json, mark_step_running, mark_step_done, model="glm51"):
    print("  [4c] Photography...")
    mark_step_running(project_dir, "phase4c_photography", ["story_beats.json", "color_script.json", "director_intent.json"])
    cs = load_json(Path(project_dir) / "color_script.json")
    beats_min = {"beats": [
        {k: v for k, v in b.items() if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")}
        for b in beats.get("beats", [])
    ]}
    photo = run_llm("cinematography.md", {
        "story_beats": beats_min,
        "color_script": {"beats": cs.get("beats", [])},
        "director_intent": intent
    }, model=model)
    save_json(Path(project_dir) / "photography.json", photo)
    mark_step_done(project_dir, "phase4c_photography")
    return photo


def step_phase4d_acting(project_dir, beats, intent, run_llm, load_json, save_json, mark_step_running, mark_step_done, model="glm51"):
    print(f"  [4d] Acting ({len(beats.get('beats',[]))} beats)...")
    mark_step_running(project_dir, "phase4d_acting", ["story_beats.json", "characters.json", "director_intent.json"])
    chars = load_json(Path(project_dir) / "characters.json")
    chars_min = {"characters": [
        {k: v for k, v in c.items() if k in ("name","aliases","personality_tags","role_level")}
        for c in chars.get("characters", [])
    ]}
    beats_min = {"beats": [
        {k: v for k, v in b.items() if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")}
        for b in beats.get("beats", [])
    ]}
    acting_validation = {"type": "object", "key": "panels", "min_items": len(beats.get("beats", []))}
    acting = run_llm("acting.md", {"story_beats": beats_min, "characters": chars_min, "director_intent": intent}, model=model, validation=acting_validation, max_retries=3)
    save_json(Path(project_dir) / "acting.json", acting)
    mark_step_done(project_dir, "phase4d_acting")
    return acting


def step_phase4e_panels(project_dir, assemble_panels, save_json, mark_step_running, mark_step_done, update_progress, generate_storyboard_viewer, model="glm51"):
    print("  [4e] 分镜组装...")
    mark_step_running(project_dir, "phase4e_panels", ["story_beats.json", "characters.json", "character_visuals.json", "photography.json", "acting.json", "color_script.json", "director_intent.json"])
    panels = assemble_panels(project_dir, model=model)
    save_json(Path(project_dir) / "panels.json", panels)
    generate_storyboard_viewer(project_dir)
    update_progress(project_dir, "phase4", "waiting_gate", "等待 Gate 2 确认")
    mark_step_done(project_dir, "phase4e_panels", review="pending")
    return "waiting_gate"


def phase5_output(project_dir, mark_step_running, mark_step_done, update_progress, generate_storyboard_viewer):
    project_path = Path(project_dir)
    tracked_inputs = ["panels.json"]
    tracked_inputs += [name for name in ("panel_notes.json", "viewer_versions.json") if (project_path / name).exists()]
    mark_step_running(project_dir, "phase5_output", tracked_inputs)
    update_progress(project_dir, "phase5", "running")
    generate_storyboard_viewer(project_dir)
    update_progress(project_dir, "phase5", "done")
    mark_step_done(project_dir, "phase5_output")
    return "done"
