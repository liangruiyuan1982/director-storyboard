from datetime import datetime
from pathlib import Path
import json
import hashlib


STEP_DEFS = [
    {"key": "phase0_input", "label": "Phase 0 Input", "outputs": ["story.txt", "director_intent.json"], "review": None},
    {"key": "phase1_story_dna", "label": "Phase 1 Story DNA", "outputs": ["story_dna.json"], "review": None},
    {"key": "phase2_beats", "label": "Phase 2 Beats", "outputs": ["story_beats.json"], "derived_outputs": ["beats-viewer.html"], "review": "gate_0"},
    {"key": "phase3_characters", "label": "Phase 3 Characters", "outputs": ["characters.json", "character_visuals.json"], "derived_outputs": ["character-viewer.html"], "review": "gate_1"},
    {"key": "phase4a_lookdev", "label": "Phase 4a Lookdev", "outputs": ["lookdev.json"], "review": None},
    {"key": "phase4b_color_script", "label": "Phase 4b Color Script", "outputs": ["color_script.json"], "review": None},
    {"key": "phase4c_photography", "label": "Phase 4c Photography", "outputs": ["photography.json"], "review": None},
    {"key": "phase4d_acting", "label": "Phase 4d Acting", "outputs": ["acting.json"], "review": None},
    {"key": "phase4e_panels", "label": "Phase 4e Panels", "outputs": ["panels.json", "viewer.html"], "derived_outputs": ["panel_intents.json"], "review": "gate_2"},
    {"key": "phase5_output", "label": "Phase 5 Output", "outputs": ["viewer.html"], "review": None},
]

STEP_INDEX = {step["key"]: i for i, step in enumerate(STEP_DEFS)}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def state_file(project_dir):
    return Path(project_dir) / "run_state.json"


def gate_state_file(project_dir, review_key):
    review_to_file = {
        "gate_0": ".gate_0.json",
        "gate_1": ".gate_1.json",
        "gate_2": ".gate_2.json",
    }
    return Path(project_dir) / review_to_file.get(review_key, f".{review_key}.json")


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gather_fingerprint(project_dir, rel_paths):
    fp = {}
    for rel in rel_paths or []:
        p = Path(project_dir) / rel
        if p.exists() and p.is_file():
            fp[rel] = file_sha256(p)
    return fp


def all_outputs_exist(project_dir, outputs):
    return all((Path(project_dir) / rel).exists() for rel in outputs)


def load_run_state(project_dir):
    p = state_file(project_dir)
    if p.exists():
        return load_json(p)
    now = str(datetime.now())
    state = {
        "project": Path(project_dir).name,
        "pipeline_version": "resume-v1",
        "created_at": now,
        "updated_at": now,
        "current_step": None,
        "overall_status": "not_started",
        "steps": {}
    }
    for step in STEP_DEFS:
        state["steps"][step["key"]] = {
            "label": step["label"],
            "status": "not_started",
            "review": "not_required" if not step["review"] else "pending",
            "outputs": step["outputs"],
            "input_fingerprint": {},
            "started_at": None,
            "ended_at": None,
            "last_error": None
        }
    save_json(p, state)
    return state


def save_run_state(project_dir, state):
    state["updated_at"] = str(datetime.now())
    save_json(state_file(project_dir), state)


def mark_step_running(project_dir, step_key, input_paths=None):
    state = load_run_state(project_dir)
    step = state["steps"][step_key]
    step["status"] = "running"
    step["started_at"] = str(datetime.now())
    step["ended_at"] = None
    step["last_error"] = None
    step["input_fingerprint"] = gather_fingerprint(project_dir, input_paths)
    state["current_step"] = step_key
    state["overall_status"] = "running"
    save_run_state(project_dir, state)


def mark_step_done(project_dir, step_key, review=None):
    state = load_run_state(project_dir)
    step = state["steps"][step_key]
    step["status"] = "done"
    step["ended_at"] = str(datetime.now())
    if review:
        step["review"] = review
        state["overall_status"] = "waiting_review" if review in ("pending", "awaiting_detail") else "running"
    else:
        state["overall_status"] = "running"
    state["current_step"] = step_key
    save_run_state(project_dir, state)


def mark_step_failed(project_dir, step_key, err):
    state = load_run_state(project_dir)
    step = state["steps"][step_key]
    step["status"] = "failed"
    step["ended_at"] = str(datetime.now())
    step["last_error"] = str(err)
    state["current_step"] = step_key
    state["overall_status"] = "failed"
    save_run_state(project_dir, state)


def update_review_status(project_dir, step_key, review_status):
    state = load_run_state(project_dir)
    step = state["steps"][step_key]
    step["review"] = review_status
    state["overall_status"] = "waiting_review" if review_status in ("pending", "awaiting_detail", "waiting") else "running"
    save_run_state(project_dir, state)


def _recompute_state_pointers(state):
    running_steps = [k for k, v in state["steps"].items() if v.get("status") == "running"]
    failed_steps = [k for k, v in state["steps"].items() if v.get("status") == "failed"]
    done_steps = [step_def["key"] for step_def in STEP_DEFS if state["steps"][step_def["key"]].get("status") == "done"]
    pending_reviews = [
        step_def["key"] for step_def in STEP_DEFS
        if step_def["review"] and state["steps"][step_def["key"]].get("status") == "done" and state["steps"][step_def["key"]].get("review") in ("pending", "waiting", "awaiting_detail")
    ]

    if running_steps:
        current = running_steps[-1]
        overall = "running"
    elif failed_steps:
        current = failed_steps[-1]
        overall = "failed"
    elif pending_reviews:
        current = pending_reviews[-1]
        overall = "waiting_review"
    elif done_steps:
        current = done_steps[-1]
        overall = "completed" if len(done_steps) == len(STEP_DEFS) else "running"
    else:
        current = None
        overall = "not_started"

    changed = False
    if state.get("current_step") != current:
        state["current_step"] = current
        changed = True
    if state.get("overall_status") != overall:
        state["overall_status"] = overall
        changed = True
    return changed


def json_has_keys(path, keys):
    try:
        data = load_json(path)
        if not isinstance(data, dict):
            return False
        return all(k in data for k in keys)
    except Exception:
        return False


def step_output_valid(project_dir, step_key):
    pdir = Path(project_dir)
    validators = {
        "phase1_story_dna": lambda: json_has_keys(pdir / "story_dna.json", ["story_title", "three_act_structure", "narrative_functions"]),
        "phase2_beats": lambda: json_has_keys(pdir / "story_beats.json", ["beats"]) and isinstance(load_json(pdir / "story_beats.json").get("beats", []), list) and len(load_json(pdir / "story_beats.json").get("beats", [])) > 0,
        "phase3_characters": lambda: json_has_keys(pdir / "characters.json", ["characters"]) and json_has_keys(pdir / "character_visuals.json", ["character_visuals"]),
        "phase4a_lookdev": lambda: json_has_keys(pdir / "lookdev.json", ["visual_motif", "camera_philosophy"]),
        "phase4b_color_script": lambda: json_has_keys(pdir / "color_script.json", ["beats"]),
        "phase4c_photography": lambda: json_has_keys(pdir / "photography.json", ["global_style", "shots"]),
        "phase4d_acting": lambda: json_has_keys(pdir / "acting.json", ["panels"]),
        "phase4e_panels": lambda: json_has_keys(pdir / "panels.json", ["panels"]) and (pdir / "viewer.html").exists(),
        "phase5_output": lambda: (pdir / "viewer.html").exists(),
    }
    fn = validators.get(step_key)
    if not fn:
        return all_outputs_exist(project_dir, STEP_DEFS[STEP_INDEX[step_key]]["outputs"])
    try:
        return fn()
    except Exception:
        return False


def infer_review_from_downstream(state, step_key):
    downstream = {
        "phase2_beats": ["phase3_characters", "phase4a_lookdev", "phase4b_color_script", "phase4c_photography", "phase4d_acting", "phase4e_panels", "phase5_output"],
        "phase3_characters": ["phase4d_acting", "phase4e_panels", "phase5_output"],
        "phase4e_panels": ["phase5_output"],
    }
    for child in downstream.get(step_key, []):
        if state["steps"].get(child, {}).get("status") == "done":
            return "approved"
    return None


def reconcile_from_downstream_facts(state):
    changed = False
    for step_key in ("phase2_beats", "phase3_characters", "phase4e_panels"):
        inferred_review = infer_review_from_downstream(state, step_key)
        if not inferred_review:
            continue
        step = state["steps"][step_key]
        if step.get("status") != "done":
            step["status"] = "done"
            changed = True
        if step.get("review") != "approved":
            step["review"] = "approved"
            changed = True
        if step.get("last_error"):
            step["last_error"] = None
            changed = True
        if not step.get("ended_at"):
            step["ended_at"] = str(datetime.now())
            changed = True
    return changed


def reconcile_run_state(project_dir):
    state = load_run_state(project_dir)
    changed = False
    for step_def in STEP_DEFS:
        step = state["steps"][step_def["key"]]
        if step["status"] == "done" and not all_outputs_exist(project_dir, step_def["outputs"]):
            step["status"] = "not_started"
            step["ended_at"] = None
            changed = True
        if step["status"] == "running":
            step["status"] = "failed"
            step["last_error"] = "interrupted_previous_run"
            changed = True
        if step_def["review"]:
            gate_file = gate_state_file(project_dir, step_def["review"])
            if gate_file.exists():
                gate = load_json(gate_file)
                gate_status = gate.get("status")
                mapped = {"confirmed": "approved", "waiting": "waiting", "awaiting_detail": "awaiting_detail"}.get(gate_status)
                if mapped and step.get("review") != mapped:
                    step["review"] = mapped
                    changed = True
    if reconcile_from_downstream_facts(state):
        changed = True
    if _recompute_state_pointers(state):
        changed = True
    if changed:
        save_run_state(project_dir, state)
    return state


def bootstrap_run_state_from_outputs(project_dir):
    state = load_run_state(project_dir)
    changed = False
    for step_def in STEP_DEFS:
        step = state["steps"][step_def["key"]]
        if step["status"] not in ("not_started", "failed"):
            continue
        if all_outputs_exist(project_dir, step_def["outputs"]) and step_output_valid(project_dir, step_def["key"]):
            step["status"] = "done"
            step["ended_at"] = str(datetime.now())
            if step_def["review"]:
                inferred_review = infer_review_from_downstream(state, step_def["key"])
                gate_file = gate_state_file(project_dir, step_def["review"])
                if inferred_review == "approved":
                    step["review"] = "approved"
                elif gate_file.exists():
                    gate = load_json(gate_file)
                    gate_status = gate.get("status")
                    step["review"] = "approved" if gate_status == "confirmed" else "pending"
                else:
                    step["review"] = "approved"
            input_map = {
                "phase1_story_dna": ["story.txt", "director_intent.json"],
                "phase2_beats": ["story.txt", "director_intent.json", "story_dna.json"],
                "phase3_characters": ["story.txt", "director_intent.json", "story_dna.json"],
                "phase4a_lookdev": ["story_dna.json", "director_intent.json"],
                "phase4b_color_script": ["story_beats.json", "director_intent.json", "lookdev.json"],
                "phase4c_photography": ["story_beats.json", "color_script.json", "director_intent.json"],
                "phase4d_acting": ["story_beats.json", "characters.json", "director_intent.json"],
                "phase4e_panels": ["story_beats.json", "characters.json", "character_visuals.json", "photography.json", "acting.json", "color_script.json", "director_intent.json"],
                "phase5_output": [
                    rel for rel in ["panels.json", "panel_notes.json", "viewer_versions.json"]
                    if (Path(project_dir) / rel).exists()
                ],
            }
            step["input_fingerprint"] = gather_fingerprint(project_dir, input_map.get(step_def["key"], []))
            changed = True
    if changed:
        done_steps = [k for k, v in state["steps"].items() if v["status"] == "done"]
        if done_steps:
            state["current_step"] = done_steps[-1]
            state["overall_status"] = "running"
        save_run_state(project_dir, state)
    return state


def fingerprint_diff(project_dir, step_key):
    state = load_run_state(project_dir)
    step = state["steps"].get(step_key, {})
    saved_fp = step.get("input_fingerprint") or {}
    current_fp = gather_fingerprint(project_dir, saved_fp.keys())
    missing = [rel for rel in saved_fp.keys() if rel not in current_fp]
    changed = [rel for rel, old_hash in saved_fp.items() if rel in current_fp and current_fp[rel] != old_hash]
    added = [rel for rel in current_fp.keys() if rel not in saved_fp]
    return {
        "matches": not missing and not changed and not added,
        "missing": missing,
        "changed": changed,
        "added": added,
        "saved": saved_fp,
        "current": current_fp,
    }


def fingerprint_matches(project_dir, step_key):
    return fingerprint_diff(project_dir, step_key)["matches"]


def should_skip_step(project_dir, step_key, resume=False, verbose=False):
    if not resume:
        return False
    state = reconcile_run_state(project_dir)
    step = state["steps"][step_key]
    step_def = STEP_DEFS[STEP_INDEX[step_key]]
    outputs_ok = all_outputs_exist(project_dir, step_def["outputs"])
    valid_ok = step_output_valid(project_dir, step_key)
    fp_info = fingerprint_diff(project_dir, step_key)
    fp_ok = fp_info["matches"]
    review_ok = (not step_def["review"]) or step.get("review") == "approved"
    ok = step["status"] == "done" and outputs_ok and valid_ok and fp_ok and review_ok
    if verbose:
        if ok:
            print(f"⏭ {step_key}: skip (done, outputs ok, structure ok, fingerprint ok{', review ok' if step_def['review'] else ''})")
        else:
            reasons = []
            if step["status"] != "done":
                reasons.append(f"status={step['status']}")
            if not outputs_ok:
                reasons.append("outputs_missing")
            if not valid_ok:
                reasons.append("outputs_invalid")
            if not fp_ok:
                diff_parts = []
                if fp_info["changed"]:
                    diff_parts.append("changed=" + ",".join(fp_info["changed"]))
                if fp_info["missing"]:
                    diff_parts.append("missing=" + ",".join(fp_info["missing"]))
                if fp_info["added"]:
                    diff_parts.append("added=" + ",".join(fp_info["added"]))
                reasons.append("fingerprint_changed" + (f"[{'; '.join(diff_parts)}]" if diff_parts else ""))
            if step_def["review"] and not review_ok:
                reasons.append(f"review={step.get('review')}")
            print(f"▶ {step_key}: run ({', '.join(reasons) if reasons else 'resume disabled'})")
    return ok


def print_run_state_summary(project_dir):
    state = reconcile_run_state(project_dir)
    print("\n🧭 run_state summary")
    print(f"  overall: {state.get('overall_status')} | current: {state.get('current_step')}")
    for step_def in STEP_DEFS:
        step = state["steps"][step_def["key"]]
        extra = f", review={step.get('review')}" if step_def["review"] else ""
        print(f"  - {step_def['key']}: {step.get('status')}{extra}")


def restart_from_step(project_dir, restart_key):
    state = load_run_state(project_dir)
    idx = STEP_INDEX[restart_key]
    for step_def in STEP_DEFS[idx:]:
        step = state["steps"][step_def["key"]]
        step["status"] = "not_started"
        step["review"] = "not_required" if not step_def["review"] else "pending"
        step["started_at"] = None
        step["ended_at"] = None
        step["last_error"] = None
        step["input_fingerprint"] = {}
    state["current_step"] = restart_key
    state["overall_status"] = "not_started"
    save_run_state(project_dir, state)
    print(f"♻️ 将从 {restart_key} 开始重跑")
