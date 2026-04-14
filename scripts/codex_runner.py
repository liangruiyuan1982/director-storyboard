#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from codex_backend_direct import run_direct
from codex_backend_infer import probe_infer, run_infer
from path_config import resolve_project, SKILL_DIR


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="director-storyboard Codex runner")
    p.add_argument("--phase", required=True, choices=["dna", "beats"])
    p.add_argument("--project-dir", required=True)
    p.add_argument("--backend", default="auto", choices=["auto", "infer", "direct"])
    p.add_argument("--model", default="openai-codex/gpt-5.4")
    p.add_argument("--skip-probe", action="store_true")
    p.add_argument("--dump-debug", action="store_true")
    return p


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_project_story(project_dir: Path) -> str:
    for name in ["story.txt", "script.txt", "content.txt", "source.txt"]:
        p = project_dir / name
        if p.exists():
            return read_text(p)
    raise FileNotFoundError(f"No story/script source found in {project_dir}")


def load_json_text(project_dir: Path, names) -> str:
    for name in names:
        p = project_dir / name
        if p.exists():
            return read_text(p)
    raise FileNotFoundError(f"Missing required file, checked: {names}")


def build_dna_prompt(project_dir: Path) -> Dict[str, str]:
    story_text = load_project_story(project_dir)
    ref = read_text(SKILL_DIR / "references" / "story_dna.md")
    return {
        "system_prompt": "你是专业分镜分析助手。只返回合法 JSON，不要附加解释。",
        "user_prompt": f"以下是 Story DNA 分析规则：\n{ref}\n\n以下是原始文案：\n{story_text}\n\n请严格输出 JSON，不要附加解释。",
    }


def build_beats_prompt(project_dir: Path) -> Dict[str, str]:
    story_text = load_project_story(project_dir)
    dna_text = load_json_text(project_dir, ["story_dna.json", "dna.json"])
    ref = read_text(SKILL_DIR / "references" / "beat_analysis.md")
    return {
        "system_prompt": "你是专业分镜分析助手。只返回合法 JSON，不要附加解释。",
        "user_prompt": f"以下是 Beat 分析规则：\n{ref}\n\n以下是 Story DNA：\n{dna_text}\n\n以下是原始文案：\n{story_text}\n\n请严格输出 JSON，不要附加解释。",
    }


def run_backend(backend: str, model: str, prompt_payload: Dict[str, str]) -> Dict[str, Any]:
    if backend == "infer":
        return run_infer(model, prompt_payload["system_prompt"], prompt_payload["user_prompt"])
    if backend == "direct":
        return run_direct(model, prompt_payload["system_prompt"], prompt_payload["user_prompt"])
    raise ValueError(f"Unsupported backend: {backend}")


def dump_debug(project_dir: Path, phase: str, output: Dict[str, Any], prompt_payload: Dict[str, str], probe: Dict[str, Any] | None = None) -> None:
    debug_dir = project_dir / "debug" / "codex_runner"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / f"{phase}.prompt.txt").write_text(
        f"SYSTEM:\n{prompt_payload['system_prompt']}\n\nUSER:\n{prompt_payload['user_prompt']}\n",
        encoding="utf-8",
    )
    (debug_dir / f"{phase}.raw.txt").write_text(output.get("raw_text") or "", encoding="utf-8")
    (debug_dir / f"{phase}.parsed.json").write_text(
        json.dumps(output.get("parsed"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta = {
        "ok": output["ok"],
        "backend_requested": output["backend_requested"],
        "backend_used": output["backend_used"],
        "error_type": output["error_type"],
        "error_message": output["error_message"],
        "probe": probe,
    }
    (debug_dir / f"{phase}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    project_dir = resolve_project(args.project_dir)
    if args.phase == "dna":
        prompt_payload = build_dna_prompt(project_dir)
    else:
        prompt_payload = build_beats_prompt(project_dir)

    requested_backend = "infer" if args.backend == "auto" else args.backend
    probe = None
    if requested_backend == "infer" and not args.skip_probe:
        probe = probe_infer(args.model)
        if not probe["ok"]:
            output = {
                "ok": False,
                "phase": args.phase,
                "backend_requested": args.backend,
                "backend_used": "infer",
                "model": args.model,
                "probe": probe,
                "text": None,
                "raw_text": probe.get("raw_text"),
                "parsed": probe.get("parsed"),
                "error_type": probe["error_type"],
                "error_message": f"infer probe failed: {probe['error_message']}",
            }
            if args.dump_debug:
                dump_debug(project_dir, args.phase, output, prompt_payload, probe)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return

    result = run_backend(requested_backend, args.model, prompt_payload)
    output = {
        "ok": result["ok"],
        "phase": args.phase,
        "backend_requested": args.backend,
        "backend_used": requested_backend,
        "model": args.model,
        "probe": probe,
        "text": result.get("text"),
        "raw_text": result["raw_text"],
        "parsed": result["parsed"],
        "error_type": result["error_type"],
        "error_message": result["error_message"],
    }
    if args.dump_debug:
        dump_debug(project_dir, args.phase, output, prompt_payload, probe)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
