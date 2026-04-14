#!/usr/bin/env python3
import tempfile
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from state_store import load_run_state, mark_step_done, restart_from_step


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        load_run_state(project)
        mark_step_done(project, "phase1_story_dna")
        mark_step_done(project, "phase2_beats", review="approved")
        mark_step_done(project, "phase3_characters", review="approved")
        mark_step_done(project, "phase4a_lookdev")
        mark_step_done(project, "phase4b_color_script")

        restart_from_step(project, "phase3_characters")
        state = load_run_state(project)

        assert state["steps"]["phase1_story_dna"]["status"] == "done"
        assert state["steps"]["phase2_beats"]["status"] == "done"
        assert state["steps"]["phase3_characters"]["status"] == "not_started"
        assert state["steps"]["phase4a_lookdev"]["status"] == "not_started"
        assert state["steps"]["phase4b_color_script"]["status"] == "not_started"
        assert state["current_step"] == "phase3_characters"
        print("✅ test_restart_state passed")


if __name__ == "__main__":
    main()
