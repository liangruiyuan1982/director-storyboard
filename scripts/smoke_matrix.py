#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE = SCRIPT_DIR / "pipeline.py"


def run_case(name, cmd):
    print(f"\n=== {name} ===")
    print("$", " ".join(str(x) for x in cmd), flush=True)
    proc = subprocess.run(cmd, text=True)
    return proc.returncode


def classify_exit(code):
    if code == 0:
        return "ok"
    if code < 0:
        return f"signal:{-code}"
    if code == 137:
        return "sigkill_or_oom"
    return f"exit:{code}"


def build_cases(project, model, level):
    light = [
        ("single_phase5", [sys.executable, str(PIPELINE), "5", "--project", project, "--model", model, "--resume"]),
        ("resume_full", [sys.executable, str(PIPELINE), "full", "--project", project, "--model", model, "--resume", "--confirm"]),
    ]
    heavy = [
        ("restart_from_phase4c", [sys.executable, str(PIPELINE), "full", "--project", project, "--model", model, "--restart-from", "phase4c_photography", "--resume", "--confirm"]),
    ]
    if level == "light":
        return light
    if level == "heavy":
        return heavy
    return light + heavy


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "marathon-original-vo-test"
    model = sys.argv[2] if len(sys.argv) > 2 else "minimax"
    level = sys.argv[3] if len(sys.argv) > 3 else "all"
    if level not in ("light", "heavy", "all"):
        raise SystemExit("usage: smoke_matrix.py [project] [model] [light|heavy|all]")

    cases = build_cases(project, model, level)
    failed = []
    for name, cmd in cases:
        code = run_case(name, cmd)
        if code != 0:
            failed.append((name, code))

    if failed:
        print(f"\n❌ smoke_matrix {level} failed:")
        for name, code in failed:
            print(f"- {name}: {classify_exit(code)}")
        raise SystemExit(1)

    print(f"\n✅ smoke_matrix {level} passed")


if __name__ == "__main__":
    main()
