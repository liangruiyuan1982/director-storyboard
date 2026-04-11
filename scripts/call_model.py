#!/usr/bin/env python3
"""
LLM 调用包装器
复用 ai-storyboard-pro 的 api.py
"""
import sys
import json
import argparse

# 添加 ai-storyboard-pro 的 scripts 目录到路径
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")

from api import call_api


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="glm51")
    parser.add_argument("--output", required=True)
    parser.add_argument("--system", default="你是一个专业的AI助手。")
    args = parser.parse_args()

    result = call_api(args.model, args.system, args.prompt, max_tokens=8192)
    
    # api.py returns (text, elapsed, usage) tuple
    text = result[0] if isinstance(result, tuple) else (result.content if hasattr(result, 'content') else str(result))
    
    # 提取 JSON
    import re
    try:
        # 尝试直接解析
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 ```json ... ```
        m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
        if m:
            data = json.loads(m.group(1))
        else:
            # 尝试找第一个 { 或 [
            for start_char in ['{', '[']:
                idx = text.find(start_char)
                if idx >= 0:
                    close = '}' if start_char == '{' else ']'
                    depth = 0
                    end_idx = -1
                    for i, c in enumerate(text[idx:], idx):
                        if c == start_char: depth += 1
                        elif c == close:
                            depth -= 1
                            if depth == 0: end_idx = i+1; break
                    if end_idx > 0:
                        try:
                            data = json.loads(text[idx:end_idx])
                            break
                        except:
                            continue
            else:
                raise ValueError(f"无法解析 JSON，原始内容前200字: {text[:200]}")
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 输出: {args.output}")


if __name__ == "__main__":
    main()
