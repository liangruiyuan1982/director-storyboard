#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Optional


def extract_infer_text(parsed: Any) -> Optional[str]:
    if not isinstance(parsed, dict):
        return None
    if isinstance(parsed.get("text"), str) and parsed.get("text"):
        return parsed["text"]
    result = parsed.get("result")
    if isinstance(result, dict):
        if isinstance(result.get("text"), str) and result.get("text"):
            return result["text"]
        message = result.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        texts.append(item["text"])
                if texts:
                    return "\n".join(texts)
    return None


def classify_infer_error(parsed: Any, stderr: str, stdout: str) -> tuple[Optional[str], Optional[str]]:
    if isinstance(parsed, dict):
        for key in ("error", "errorMessage", "message"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return "provider_error", value
        result = parsed.get("result")
        if isinstance(result, dict):
            for key in ("error", "errorMessage", "message"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return "provider_error", value
    if stderr:
        return "transport_error", stderr
    if stdout:
        return "parse_error", "infer returned unparseable output"
    return "empty_output", "infer returned empty output"


def run_infer(model: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
    cmd = [
        "openclaw",
        "infer",
        "model",
        "run",
        "--model",
        model,
        "--prompt",
        prompt,
        "--json",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    parsed = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = None
    if proc.returncode != 0:
        error_type, error_message = classify_infer_error(parsed, stderr, stdout)
        return {
            "ok": False,
            "backend": "infer",
            "raw_text": stdout or None,
            "text": extract_infer_text(parsed),
            "raw_stderr": stderr or None,
            "parsed": parsed,
            "error_type": error_type,
            "error_message": error_message or f"infer exited with code {proc.returncode}",
        }
    text = extract_infer_text(parsed)
    if not text and not parsed:
        return {
            "ok": False,
            "backend": "infer",
            "raw_text": stdout or None,
            "text": None,
            "raw_stderr": stderr or None,
            "parsed": None,
            "error_type": "empty_output",
            "error_message": "infer returned empty output",
        }
    return {
        "ok": True,
        "backend": "infer",
        "raw_text": stdout or None,
        "text": text,
        "raw_stderr": stderr or None,
        "parsed": parsed,
        "error_type": None,
        "error_message": None,
    }


def probe_infer(model: str) -> Dict[str, Any]:
    return run_infer(model, "只返回纯文本。", "回复 ok")
