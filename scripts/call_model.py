#!/usr/bin/env python3
"""
LLM 调用包装器
复用 ai-storyboard-pro 的 api.py
支持验证期望结构和自动重试
"""
import sys
import json
import argparse
import time
import re
import subprocess
from pathlib import Path

# 添加 ai-storyboard-pro 的 scripts 目录到路径
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

SCRIPT_DIR = Path(__file__).resolve().parent
CODEX_RUNNER = SCRIPT_DIR / "call_model_codex.mjs"


def call_codex(model, system, prompt):
    payload = json.dumps({
        "modelRef": model,
        "systemPrompt": system,
        "userPrompt": prompt,
    }, ensure_ascii=False)
    proc = subprocess.run(
        ["node", str(CODEX_RUNNER)],
        input=payload,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Codex 调用失败: {proc.stderr[:500]}")
    return proc.stdout

MAX_RETRIES = 3

def is_truncated(text):
    """检测 LLM 输出是否被截断（token 限制处停止）
    
    只用括号匹配判断截断。quote counting 容易误判（中文内容有特殊字符），
    所以放弃 quote 计数方案。
    """
    text = text.rstrip()
    if not text:
        return False
    
    # 1. 花括号不匹配 → 截断
    if text.count('{') > text.count('}'):
        return True
    if text.count('[') > text.count(']'):
        return True
    
    # 2. 末尾是未闭合的 { 或 [ → 截断
    if text.rstrip().endswith(('{', '[')):
        return True
    
    # 3. 检查末尾是否像是被截断的字段名
    # 触发条件：末尾在引号中间（odd quotes in tail）且不在闭合大结构内
    tail = text[-50:] if len(text) >= 50 else text
    # 简单启发式：如果末尾有未闭合的引号，且括号基本匹配
    # 可能是内容里有未转义字符导致引号奇数
    # 但如果括号匹配且以 } 或 ] 结尾 → 不截断
    if tail.count('"') % 2 == 1:
        # 末尾引号不匹配
        # 检查是否以 } 或 ] 结尾（如果是，说明 JSON 完整，只是内容有引号）
        if text.rstrip().endswith(('}', ']')):
            return False  # 实际上完整，不算截断
        return True  # 真正截断
    
    return False


def robust_parse(text):
    """更强的 JSON 容错解析"""
    c = text
    c = re.sub(r'```\w*', '', c)
    c = re.sub(r'<[^>]+>', '', c)
    c = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', c)
    c = c.replace("\u00ab", '"').replace("\u00bb", '"')
    c = c.replace("\u201c", "\u300c").replace("\u201d", "\u300d")
    c = re.sub(r'\}\n\s*\}', '}', c)
    c = re.sub(r'"\w+_,\s*("(?:panel_id|beat_id|performance_notes|body_language|facial_expression|lighting|depth_of_field|color_temperature|camera_movement|shot_type|duration|voiceover|transition|description|source_text|mood|appearance|scene_type|freeze_action|body_tension|energy_state)")', r'\1', c)
    c = re.sub(r'\n\s*_\w+":\s*"[^"]*"', '', c)
    c = re.sub(r',\s*,', ',', c)
    try:
        return json.loads(c)
    except Exception:
        pass
    c = re.sub(r'"_([^_]+)_"', r'"\1"', c)
    c = re.sub(r',\s*,', ',', c)
    c = re.sub(r',\s*([}\]])', r'\1', c)
    c = re.sub(r'""([,}\]])', r'"\1', c)
    c = re.sub(r'([\{\[,\n]\s*)([a-zA-Z_][a-zA-Z0-9_]*)":', r'\1"\2":', c)
    c = re.sub(r'\s+_([a-zA-Z][a-zA-Z0-9_]*)\s*:', r' "\1":', c)
    c = re.sub(r':\s+(?![\[{"\'\-\d])([A-Za-z_][A-Za-z0-9_]*)\s*([,}\]])', lambda m: f': "{m.group(1)}"{m.group(2)}' if m.group(1) not in ('true','false','null') else f': {m.group(1)}{m.group(2)}', c)
    try:
        return json.loads(c)
    except Exception:
        pass
    def _extract_balanced(src, open_ch, close_ch):
        depth = 0
        start = -1
        for i, ch in enumerate(src):
            if ch == open_ch:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0 and start >= 0:
                    return src[start:i+1]
        return None
    for open_ch, close_ch in [('{','}'), ('[',']')]:
        block = _extract_balanced(c, open_ch, close_ch)
        if block:
            try:
                return json.loads(block)
            except Exception:
                pass
    last = max(c.rfind('}'), c.rfind(']'))
    if last > 0:
        try:
            return json.loads(c[:last+1])
        except Exception:
            pass
    raise ValueError("Cannot parse JSON from output")


def extract_json(text):
    """从 LLM 输出中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
    if m:
        fenced = m.group(1)
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            text = fenced
    for start_char in ['{', '[']:
        idx = text.find(start_char)
        if idx < 0:
            continue
        close = '}' if start_char == '{' else ']'
        depth = 0
        end_idx = -1
        for i, c in enumerate(text[idx:], idx):
            if c == start_char:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        if end_idx > 0:
            try:
                return json.loads(text[idx:end_idx])
            except json.JSONDecodeError:
                continue
    try:
        return robust_parse(text)
    except Exception:
        pass
    if is_truncated(text):
        raise ValueError("JSON被截断，模型在token限制处停止")
    raise ValueError(f"无法解析 JSON，原始内容前200字: {text[:200]}")


def validate_result(data, validation):
    """
    验证 LLM 返回的数据结构是否符合期望
    validation: dict, 期望的验证规则
      - type: "array" | "object" | "dict"
      - key: 期望存在的顶层键名
      - min_items: 数组最小长度（用于 beats/panels 数量验证）
      - expected_count: 期望的精确数组长度
    """
    if not validation:
        return True, None
    
    vtype = validation.get("type", "object")
    
    if vtype == "array":
        if not isinstance(data, list):
            return False, f"期望数组，得到 {type(data).__name__}"
        if "min_items" in validation and len(data) < validation["min_items"]:
            return False, f"数组长度 {len(data)} < 最小要求 {validation['min_items']}"
        return True, None
    
    if vtype in ("object", "dict"):
        if not isinstance(data, dict):
            return False, f"期望对象，得到 {type(data).__name__}"
        if "key" in validation:
            if validation["key"] not in data:
                return False, f"缺少必需的键 '{validation['key']}'"
        if "min_items" in validation:
            key = validation.get("key", "panels")
            arr = data.get(key, [])
            if not isinstance(arr, list):
                return False, f"键 '{key}' 不是数组"
            if len(arr) < validation["min_items"]:
                return False, f"键 '{key}' 数组长度 {len(arr)} < 最小要求 {validation['min_items']}"
        return True, None
    
    return True, None


def call_with_retry(model, system, prompt, validation=None, max_retries=MAX_RETRIES,
                    max_tokens=8192, output_file=None):
    """带验证和重试的 LLM 调用"""
    if output_file is None:
        output_file = "/tmp/llm_output.json"
    
    for attempt in range(max_retries):
        finish_reason = None
        if model in ("gpt5.4", "openai-codex/gpt-5.4"):
            text = call_codex("openai-codex/gpt-5.4", system, prompt)
            result = text
        else:
            result = call_api(model, system, prompt, max_tokens=max_tokens)
            text = result[0] if isinstance(result, tuple) else (result.content if hasattr(result, 'content') else str(result))
        
        try:
            data = extract_json(text)
        except ValueError as e:
            if isinstance(result, tuple) and len(result) >= 3 and isinstance(result[2], dict):
                finish_reason = result[2].get("finish_reason")
            debug_path = f"/tmp/llm_debug_{model}_attempt{attempt+1}.txt"
            try:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass
            print(f"⚠️ 尝试 {attempt+1}/{max_retries}: JSON解析失败 - {e} | finish_reason={finish_reason} | debug={debug_path}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
        
        ok, reason = validate_result(data, validation)
        if not ok:
            print(f"⚠️ 尝试 {attempt+1}/{max_retries}: 验证失败 - {reason}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise ValueError(f"验证失败: {reason}")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 输出: {output_file} (尝试 {attempt+1})")
        return data
    
    raise ValueError("所有重试均失败")


def main():
    parser = argparse.ArgumentParser(description="LLM 调用包装器")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="glm51")
    parser.add_argument("--output", required=True)
    parser.add_argument("--system", default="你是专业AI助手。只返回JSON，不要其他文字。")
    parser.add_argument("--max-tokens", type=int, default=8192)
    # 验证参数
    parser.add_argument("--validate-type", choices=["array", "object"], default=None,
                        help="期望的返回类型")
    parser.add_argument("--validate-key", default=None,
                        help="期望的数组键名 (如 beats, panels)")
    parser.add_argument("--validate-min", type=int, default=None,
                        help="数组最小长度")
    parser.add_argument("--validate-count", type=int, default=None,
                        help="数组精确长度")
    parser.add_argument("--retries", type=int, default=MAX_RETRIES,
                        help="最大重试次数")
    args = parser.parse_args()
    
    validation = None
    if args.validate_type:
        validation = {"type": args.validate_type}
        if args.validate_key:
            validation["key"] = args.validate_key
        if args.validate_min is not None:
            validation["min_items"] = args.validate_min
        if args.validate_count is not None:
            validation["min_items"] = args.validate_count
    
    call_with_retry(
        model=args.model,
        system=args.system,
        prompt=args.prompt,
        validation=validation,
        max_retries=args.retries,
        max_tokens=args.max_tokens,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
