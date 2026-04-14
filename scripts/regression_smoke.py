#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE = SCRIPT_DIR / "pipeline.py"


def run(cmd):
    print("$", " ".join(str(x) for x in cmd), flush=True)
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else "marathon-original-vo-test"
    model = sys.argv[2] if len(sys.argv) > 2 else "minimax"

    run([sys.executable, str(PIPELINE), "full", "--project", project, "--model", model, "--resume", "--confirm"])
    run([sys.executable, str(PIPELINE), "full", "--project", project, "--model", model, "--restart-from", "phase4c_photography", "--resume", "--confirm"])

    print("✅ regression_smoke passed")


if __name__ == "__main__":
    main()
