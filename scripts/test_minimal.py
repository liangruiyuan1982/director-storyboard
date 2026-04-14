#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cli_runner import resolve_project_dir
from state_store import load_run_state, mark_step_running, mark_step_done, update_review_status
from panel_assembler import assemble_panels


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_cli_resolve_project_dir():
    projects_dir = Path("/tmp/projects-root")
    assert resolve_project_dir("demo", projects_dir) == projects_dir / "demo"
    assert resolve_project_dir("/abs/demo", projects_dir) == Path("/abs/demo")
    print("✅ test_cli_resolve_project_dir")


def test_state_store_review_transition(tmpdir):
    state = load_run_state(tmpdir)
    assert state["overall_status"] == "not_started"
    mark_step_running(tmpdir, "phase2_beats", ["story.txt"])
    state = load_run_state(tmpdir)
    assert state["steps"]["phase2_beats"]["status"] == "running"
    assert state["overall_status"] == "running"
    mark_step_done(tmpdir, "phase2_beats", review="pending")
    state = load_run_state(tmpdir)
    assert state["steps"]["phase2_beats"]["status"] == "done"
    assert state["steps"]["phase2_beats"]["review"] == "pending"
    assert state["overall_status"] == "waiting_review"
    update_review_status(tmpdir, "phase2_beats", "approved")
    state = load_run_state(tmpdir)
    assert state["steps"]["phase2_beats"]["review"] == "approved"
    assert state["overall_status"] == "running"
    print("✅ test_state_store_review_transition")


def test_panel_assembler_minimal(tmpdir):
    _write(Path(tmpdir) / "story_beats.json", {"beats": [{"beat_id": "B01", "content": "他继续向前跑", "visual_hint": "中景：跑者在路边喘息", "emotion": "疲惫", "emotion_intensity": 8, "characters": ["主角"], "duration_estimate": 5, "voiceover": "他继续向前跑"}]})
    _write(Path(tmpdir) / "characters.json", {"characters": [{"name": "主角", "expected_appearances": [{"appearance_id": 1, "beat_id": "B01"}]}]})
    _write(Path(tmpdir) / "character_visuals.json", {"character_visuals": [{"name": "主角", "appearances": [{"appearance_id": 1, "description": "中年跑者，汗湿上衣"}]}]})
    _write(Path(tmpdir) / "photography.json", {"global_style": {"aspect_ratio": "16:9"}, "shots": [{"beat_id": "B01", "shot_type": "中景", "camera_movement": "Static", "lighting": "自然光", "depth_of_field": "浅景深", "color_temperature": 5500}]})
    _write(Path(tmpdir) / "acting.json", {"panels": [{"beat_id": "B01", "performance_notes": "", "freeze_action": "", "body_tension": "", "energy_state": "", "emotional_subtext": "坚持", "performance_directive": "稳住呼吸"}]})
    _write(Path(tmpdir) / "color_script.json", {"beats": [{"beat_id": "B01", "dominant_color": "冷蓝灰", "transition_to_next": "cut", "narrative_function": "压迫"}]})
    _write(Path(tmpdir) / "director_intent.json", {"q6_transition_philosophy": "硬切"})

    def fake_run_llm(prompt_name, payload, model="test", output_file=None, validation=None, max_retries=3):
        data = {"panel_intents": [{"beat_id": "B01", "visual_task": "强调身体负荷", "frame_priority": "body_state"}]}
        if output_file:
            Path(output_file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    result = assemble_panels(tmpdir, run_llm=fake_run_llm, model="test")
    panels = result["panels"]
    assert len(panels) == 1
    panel = panels[0]
    assert panel["visual_task"] == "强调身体负荷"
    assert panel["frame_priority"] == "body_state"
    assert panel["transition"] == "cut"
    assert panel["character_appearances"][0]["appearance_id"] == 1
    assert panel["video_prompt"].strip()
    assert "视觉任务" in panel["video_prompt"]
    print("✅ test_panel_assembler_minimal")


def main():
    test_cli_resolve_project_dir()
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "story.txt").write_text("demo", encoding="utf-8")
        test_state_store_review_transition(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_panel_assembler_minimal(tmpdir)
    print("\n✅ test_minimal passed")
    print("ℹ️ deeper restart coverage: run test_restart_state.py")


if __name__ == "__main__":
    main()
