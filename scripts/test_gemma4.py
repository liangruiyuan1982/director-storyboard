#!/usr/bin/env python3
"""用 gemma4 测试 Color Script（精简输入）"""
import sys
import json
import re
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-last-supper"
SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
import os; os.chdir(SKILL_DIR)

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def extract_json(text):
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
                try: return json.loads(text[idx:end_idx])
                except: continue
    return None

def call_model(model_key, system, user_prompt, max_tokens=8192):
    result = call_api(model_key, system, user_prompt, max_tokens=max_tokens)
    text = result[0] if isinstance(result, tuple) else result
    data = extract_json(text)
    if data: return data
    print(f"[DEBUG]\n{text[:800]}")
    raise ValueError("JSON解析失败")

def read_ref(name):
    with open(f"references/{name}", encoding="utf-8") as f:
        return f.read()

# 加载并精简 beats（只取必要字段）
beats_full = load_json(f"{PROJECT}/story_beats.json")
intent = load_json(f"{PROJECT}/director_intent.json")

# 精简 beats：去掉长 content，只保留必要字段
beats_minimal = {
    "beats": [
        {
            "beat_id": b["beat_id"],
            "emotion": b.get("emotion", ""),
            "emotion_intensity": b.get("emotion_intensity", 5),
            "narrative_function": b.get("narrative_function", ""),
            "scene": b.get("scene", ""),
            "key_visual_moment": b.get("key_visual_moment", False)
        }
        for b in beats_full.get("beats", [])
    ]
}

system = "你是专业的色彩叙事设计师。只返回JSON，不要其他文字。"
user = read_ref("color_script.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_beats': beats_minimal, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print(f"Beats: {len(beats_minimal['beats'])} | Input size: {len(user)} chars")
print("⏳ 调用 gemma4...")
cs = call_model("gemma4", system, user, max_tokens=8192)
print(f"✅ Color Script 成功!")
print(f"   全局: {cs.get('global_color_theme', 'N/A')[:80]}")
for b in cs.get('beats', [])[:3]:
    print(f"   {b.get('beat_id')}: {b.get('dominant_color')} → {b.get('transition_to_next','')[:50]}")
