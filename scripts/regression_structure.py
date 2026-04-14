#!/usr/bin/env python3
from pathlib import Path
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from panel_assembler import assemble_panels
from path_config import resolve_project


def fake_run_llm(prompt_name, payload, model="glm51", output_file=None, validation=None, max_retries=3):
    beats = payload.get("story_beats", {}).get("beats", [])
    data = {
        "panel_intents": [
            {
                "beat_id": beat.get("beat_id"),
                "visual_task": "测试视觉任务",
                "frame_priority": "character_identity",
            }
            for beat in beats
        ]
    }
    if output_file:
        Path(output_file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main():
    project_arg = sys.argv[1] if len(sys.argv) > 1 else "marathon-original-vo-test"
    project_dir = resolve_project(project_arg)
    panels = assemble_panels(project_dir, run_llm=fake_run_llm, model="test")
    panel_list = panels.get("panels", [])
    assert panel_list, "panels 为空"
    required = ["panel_id", "beat_id", "video_prompt", "visual_task", "frame_priority"]
    for panel in panel_list:
        for key in required:
            assert key in panel, f"缺少字段: {key}"
    print(f"✅ regression_structure passed: {len(panel_list)} panels")


if __name__ == "__main__":
    main()
