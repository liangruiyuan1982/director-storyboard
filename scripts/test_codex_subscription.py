#!/usr/bin/env python3
"""Codex 订阅专用测试入口。
不依赖 ai-storyboard-pro 的 api.py，直接复用 director-storyboard 的 call_model.py / pipeline.py。
用于验证在仅订阅、无 API key 模式下，director-storyboard 是否能跑通关键阶段。
"""
import json
import sys
import time
import importlib.util
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from path_config import PROJECTS_DIR, SKILL_DIR

pipeline_path = str(SCRIPT_DIR / "pipeline.py")
pipeline_spec = importlib.util.spec_from_file_location("director_storyboard_pipeline_codex", pipeline_path)
pipeline_main = importlib.util.module_from_spec(pipeline_spec)
pipeline_spec.loader.exec_module(pipeline_main)
should_skip_step = pipeline_main.should_skip_step
mark_step_running = pipeline_main.mark_step_running
mark_step_done = pipeline_main.mark_step_done
mark_step_failed = pipeline_main.mark_step_failed
reconcile_run_state = pipeline_main.reconcile_run_state

call_model_path = str(SCRIPT_DIR / "call_model.py")
call_spec = importlib.util.spec_from_file_location("director_storyboard_call_model_codex", call_model_path)
call_model_mod = importlib.util.module_from_spec(call_spec)
call_spec.loader.exec_module(call_model_mod)
run_llm = call_model_mod.run_llm

DEFAULT_PROJECT = str(PROJECTS_DIR / "marathon-original-vo-test")
PROJECT = str(Path(sys.argv[1])) if len(sys.argv) > 1 else DEFAULT_PROJECT
MODEL = "gpt5.4"
PHASE = sys.argv[2] if len(sys.argv) > 2 else "phase2"

os_path = SKILL_DIR


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_ref(name):
    with open(SKILL_DIR / "references" / name, encoding="utf-8") as f:
        return f.read()


def run_test_step(step_key, fn):
    try:
        return fn()
    except Exception as e:
        mark_step_failed(PROJECT, step_key, e)
        raise


def phase1_story_dna():
    story = Path(PROJECT, "story.txt").read_text(encoding="utf-8")
    intent = load_json(Path(PROJECT) / "director_intent.json")
    mark_step_running(PROJECT, "phase1_story_dna", ["story.txt", "director_intent.json"])
    t0 = time.time()
    data = run_llm("story_dna.md", {"story_text": story, "director_intent": intent}, model=MODEL)
    save_json(Path(PROJECT) / "story_dna.json", data)
    mark_step_done(PROJECT, "phase1_story_dna")
    print(f"✅ phase1_story_dna via Codex: {time.time()-t0:.0f}s")
    return data


def phase2_beats():
    story = Path(PROJECT, "story.txt").read_text(encoding="utf-8")
    intent = load_json(Path(PROJECT) / "director_intent.json")
    dna = load_json(Path(PROJECT) / "story_dna.json")
    mark_step_running(PROJECT, "phase2_beats", ["story.txt", "director_intent.json", "story_dna.json"])
    t0 = time.time()
    beats = run_llm("beat_analysis.md", {"story_text": story, "story_dna": dna, "director_intent": intent}, model=MODEL, validation={"type": "object", "key": "beats", "min_items": 1})
    if intent.get("q5b_voiceover_rewrite") == "preserve_original":
        for beat in beats.get("beats", []):
            beat["voiceover"] = beat.get("content", "")
    elif intent.get("q5_voiceover_type", "").startswith("C"):
        for beat in beats.get("beats", []):
            beat["voiceover"] = ""
    save_json(Path(PROJECT) / "story_beats.codex.json", beats)
    mark_step_done(PROJECT, "phase2_beats")
    print(f"✅ phase2_beats via Codex: {time.time()-t0:.0f}s | beats={len(beats.get('beats', []))}")
    return beats


def main():
    reconcile_run_state(PROJECT)
    print(f"🎯 Codex subscription test | project={Path(PROJECT).name} | phase={PHASE}")
    if PHASE in ("phase1", "phase2") and not should_skip_step(PROJECT, "phase1_story_dna", True, True):
        run_test_step("phase1_story_dna", phase1_story_dna)
    if PHASE == "phase1":
        return
    run_test_step("phase2_beats", phase2_beats)


if __name__ == "__main__":
    main()
