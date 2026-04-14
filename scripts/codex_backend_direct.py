#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict


PI_AI_PATH = "/Users/liangruiyuan/.openclaw/extensions/lossless-claw/node_modules/@mariozechner/pi-ai/dist/index.js"


def classify_direct_error(text: str) -> str:
    t = (text or "").lower()
    if "no api key for provider: openai-codex" in t:
        return "auth_error"
    if "err_module_not_found" in t or "cannot find module" in t:
        return "runtime_error"
    return "unknown_error"


def run_direct(model: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    provider, model_id = model.split("/", 1)
    script = f"""
import {{ getModel, complete }} from '{PI_AI_PATH}';

async function main() {{
  try {{
    const model = await getModel('{provider}', '{model_id}');
    const result = await complete(model, [
      {{ role: 'system', content: {json.dumps(system_prompt)} }},
      {{ role: 'user', content: {json.dumps(user_prompt)} }}
    ], {{
      temperature: 0,
      maxOutputTokens: 4096
    }});
    console.log(JSON.stringify(result, null, 2));
  }} catch (err) {{
    console.error(String(err?.stack || err));
    process.exit(1);
  }}
}}

await main();
""".strip()
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as f:
        f.write(script)
        temp_path = Path(f.name)
    proc = subprocess.run(["node", str(temp_path)], text=True, capture_output=True)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "backend": "direct",
            "raw_text": stdout or None,
            "raw_stderr": stderr or None,
            "parsed": None,
            "error_type": classify_direct_error(stderr or stdout),
            "error_message": stderr or stdout or f"direct exited with code {proc.returncode}",
        }
    try:
        result = json.loads(stdout)
    except Exception:
        return {
            "ok": False,
            "backend": "direct",
            "raw_text": stdout or None,
            "raw_stderr": stderr or None,
            "parsed": None,
            "error_type": "parse_error",
            "error_message": "direct backend returned non-JSON output",
        }
    error_message = result.get("errorMessage")
    if error_message:
        return {
            "ok": False,
            "backend": "direct",
            "raw_text": stdout,
            "raw_stderr": stderr or None,
            "parsed": result,
            "error_type": classify_direct_error(error_message),
            "error_message": error_message,
        }
    return {
        "ok": True,
        "backend": "direct",
        "raw_text": stdout,
        "raw_stderr": stderr or None,
        "parsed": result,
        "error_type": None,
        "error_message": None,
    }
