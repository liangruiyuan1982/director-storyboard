from pathlib import Path
import json
import re

from state_store import load_json, save_json


def infer_panel_intents(project_dir, beats, chars, photo, acting, cs, intent, run_llm, model="glm51"):
    panel_intents_path = Path(project_dir) / "panel_intents.json"
    validation = {"type": "object", "key": "panel_intents", "expected_count": len(beats)}
    data = run_llm(
        "panel_intent.md",
        {
            "story_beats": {"beats": beats},
            "photography": photo,
            "acting": acting,
            "color_script": cs,
            "characters": chars,
            "director_intent": intent,
        },
        model=model,
        output_file=str(panel_intents_path),
        validation=validation,
        max_retries=3,
    )
    save_json(panel_intents_path, data)
    return {item.get("beat_id"): item for item in data.get("panel_intents", [])}


def assemble_panels(project_dir, run_llm, model="glm51"):
    beats = load_json(Path(project_dir) / "story_beats.json").get("beats", [])
    chars = load_json(Path(project_dir) / "characters.json")
    char_vis = load_json(Path(project_dir) / "character_visuals.json")
    photo = load_json(Path(project_dir) / "photography.json")
    acting = load_json(Path(project_dir) / "acting.json")
    cs = load_json(Path(project_dir) / "color_script.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    panel_intents = infer_panel_intents(project_dir, beats, chars, photo, acting, cs, intent, run_llm=run_llm, model=model)

    beat_to_appearance = {}
    char_first = {}
    for c in chars.get("characters", []):
        cname = c["name"]
        ea_list = c.get("expected_appearances", [])
        char_first[cname] = ea_list[0].get("appearance_id", ea_list[0].get("id", 0)) if ea_list else 0
        for ea in ea_list:
            bid = ea.get("beat_id", "")
            if bid:
                if bid not in beat_to_appearance:
                    beat_to_appearance[bid] = {}
                aid = ea.get("appearance_id", ea.get("id", 0))
                beat_to_appearance[bid][cname] = aid

    vis_map = {}
    char_visuals_root = char_vis.get("character_visuals", char_vis.get("characters", []))
    for cv in char_visuals_root:
        cname = cv.get("name", "")
        for app in cv.get("appearances", []):
            aid = app.get("id", app.get("appearance_id", 0))
            desc = app.get("description", "")
            if not desc:
                desc_list = app.get("descriptions", [])
                desc = desc_list[0] if desc_list else ""
            vis_map[(cname, aid)] = desc

    def infer_appearance(beat, char_first_aid=0):
        scene = beat.get("scene", "") + beat.get("content", "") + beat.get("emotion", "") + beat.get("visual_hint", "")
        if any(kw in scene for kw in ["跑", "疲惫", "汗水", "翻山", "运动", "汗渍", "喘", "负荷"]):
            return 1
        if any(kw in scene for kw in ["清晨", "释然", "日出", "晨光", "宁静", "终点", "完成", "背影"]):
            return 2
        return char_first_aid

    panels = []
    for i, beat in enumerate(beats):
        beat_id = beat["beat_id"]
        shot = next((s for s in photo.get("shots", []) if s.get("beat_id") == beat_id), {})
        act = next((a for a in acting.get("panels", []) if a.get("beat_id") == beat_id), {})
        csbeat = next((c for c in cs.get("beats", []) if c.get("beat_id") == beat_id), {})

        beat_chars = beat.get("characters", [])
        beat_app_map = beat_to_appearance.get(beat_id, {})
        panel_char_prompts = []
        panel_char_names = []
        panel_char_appearances = []

        if beat_chars:
            for cname in beat_chars:
                if beat_id in beat_to_appearance:
                    aid = beat_app_map.get(cname, char_first.get(cname, 0))
                else:
                    aid = infer_appearance(beat, char_first.get(cname, 0))
                panel_char_names.append(cname)
                panel_char_appearances.append({"name": cname, "appearance_id": aid})
                desc = vis_map.get((cname, aid), "")
                if desc:
                    panel_char_prompts.append(desc[:200])
        elif char_vis.get("character_visuals") or char_vis.get("characters"):
            for cname, aid in char_first.items():
                if beat_id not in beat_to_appearance:
                    aid = infer_appearance(beat, aid)
                panel_char_names.append(cname)
                panel_char_appearances.append({"name": cname, "appearance_id": aid})
                desc = vis_map.get((cname, aid), "")
                if desc:
                    panel_char_prompts.append(desc[:200])

        q6 = intent.get("q6_transition_philosophy", "Mix")
        if q6 == "硬切":
            transition = "cut"
        elif q6 == "Dissolve":
            transition = "dissolve"
        elif q6 == "Fade":
            transition = "fade"
        else:
            transition = csbeat.get("transition_to_next", "cut") or "cut"

        appearance_refs = [f"{item['name']}(appearance_{item['appearance_id']})" for item in panel_char_appearances]
        role_ref = "、".join(appearance_refs)
        aspect_ratio = photo.get("global_style", {}).get("aspect_ratio", "16:9") if isinstance(photo, dict) else "16:9"
        shot_type = shot.get("shot_type", "中景")
        cam_move = shot.get("camera_movement", "Static")
        lighting = shot.get("lighting", "")
        visual_hint = beat.get("visual_hint", "")
        if "或者" in visual_hint:
            visual_hint = visual_hint.split("或者")[0].strip(" ，。;；")
        changed = True
        while changed:
            changed = False
            for prefix in ["特写：", "近景：", "中景：", "全景：", "远景：", "快速蒙太奇：", "慢动作：", "摄影机", "镜头"]:
                if visual_hint.startswith(prefix):
                    visual_hint = visual_hint[len(prefix):].strip(" ：，。;")
                    changed = True
        for noise in ["慢动作", "快速蒙太奇", "中景：", "近景：", "特写：", "远景：", "全景："]:
            visual_hint = visual_hint.replace(noise, "")
        visual_hint = re.sub(r"[；;]+", "，", visual_hint)
        visual_hint = re.sub(r"。{2,}", "。", visual_hint).strip(" ，。")
        perf = act.get("performance_notes", "")
        if perf in ("空镜头", "", "N/A") and any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["跑", "疲惫", "翻山", "步伐", "背影"]):
            if any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["疲惫", "翻山"]):
                perf = "疲惫跑者的身体在一次短暂停顿中微微下沉，呼吸负荷清晰可见"
            elif any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["背影", "步伐"]):
                perf = "背影在前进动作的一瞬间定格，步伐稳定，身体保持持续推进"
        freeze_action = act.get("freeze_action", "")
        body_tension = act.get("body_tension", "")
        energy_state = act.get("energy_state", "")
        if freeze_action in ("", "N/A"):
            freeze_action = perf if perf not in ("", "N/A") else "无明确动作定格"
        if body_tension in ("", "N/A"):
            if any(kw in freeze_action for kw in ["呼吸", "胸", "肩"]):
                body_tension = "胸腔与肩颈承压"
            elif any(kw in freeze_action for kw in ["步伐", "腿", "前倾"]):
                body_tension = "下肢与脊背持续发力"
            else:
                body_tension = "N/A"
        if energy_state in ("", "N/A"):
            if any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["疲惫", "负荷", "喘", "耗尽"]):
                energy_state = "耗尽"
            elif any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["释然", "轻盈", "宁静"]):
                energy_state = "释然"
            elif any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["稳定", "平稳", "日常"]):
                energy_state = "稳定"
            else:
                energy_state = "压抑" if beat.get("emotion_intensity", 0) and beat.get("emotion_intensity", 0) >= 7 else "稳定"

        panel_intent = panel_intents.get(beat_id, {})
        visual_task = panel_intent.get("visual_task", "强调当前镜头最需要观众记住的叙事焦点")
        frame_priority = panel_intent.get("frame_priority", "character_identity")
        color_desc = csbeat.get("dominant_color", "")
        video_lines = [
            f"{aspect_ratio}，横屏。",
            f"镜头：{shot_type}，运镜方式：{cam_move}。",
        ]
        if role_ref:
            video_lines.append(f"角色：{role_ref}。")
        if visual_hint:
            video_lines.append(f"画面内容：{visual_hint}。")
        if perf:
            video_lines.append(f"人物动作：{perf}。")
        if freeze_action and freeze_action != "无明确动作定格":
            video_lines.append(f"动作定格：{freeze_action}。")
        if visual_task:
            video_lines.append(f"视觉任务：{visual_task}。")
        if lighting:
            video_lines.append(f"光线：{lighting}。")
        if color_desc:
            video_lines.append(f"整体画面色调：{color_desc}。")
        video_prompt = "\n".join(video_lines)

        panels.append({
            "panel_id": f"P{i+1:02d}",
            "beat_id": beat_id,
            "duration": beat.get("duration_estimate", 5),
            "shot_type": shot.get("shot_type", "中景"),
            "camera_movement": shot.get("camera_movement", "Static"),
            "scene_description": beat.get("visual_hint", ""),
            "voiceover": beat.get("voiceover", ""),
            "transition": transition,
            "lighting": shot.get("lighting", ""),
            "depth_of_field": shot.get("depth_of_field", ""),
            "color_temperature": shot.get("color_temperature", 5500),
            "performance_notes": act.get("performance_notes", ""),
            "emotional_subtext": act.get("emotional_subtext", ""),
            "performance_directive": act.get("performance_directive", ""),
            "freeze_action": freeze_action,
            "body_tension": body_tension,
            "energy_state": energy_state,
            "visual_task": visual_task,
            "frame_priority": frame_priority,
            "facial_expression": act.get("facial_expression", "N/A"),
            "body_language": act.get("body_language", "N/A"),
            "dominant_color": csbeat.get("dominant_color", ""),
            "color_narrative": csbeat.get("narrative_function", ""),
            "characters": panel_char_names,
            "character_prompts": panel_char_prompts,
            "character_appearances": panel_char_appearances,
            "appearance_refs": appearance_refs,
            "video_prompt": video_prompt,
            "key_visual_moment": beat.get("key_visual_moment", False),
            "directors_note": "",
            "versions": []
        })

    return {"panels": panels}
