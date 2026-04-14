#!/usr/bin/env python3
"""测试 Phase 1-2 beat_id 格式修复（gemma4）"""
import sys, json, re, os
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-last-supper"
SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
os.chdir(SKILL_DIR)

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_json(text):
    for start_char in ['{', '[']:
        idx = text.find(start_char)
        if idx >= 0:
            close = '}' if start_char == '{' else ']'
            depth = 0; end_idx = -1
            for i, c in enumerate(text[idx:], idx):
                if c == start_char: depth += 1
                elif c == close:
                    depth -= 1
                    if depth == 0: end_idx = i+1; break
            if end_idx > 0:
                try: return json.loads(text[idx:end_idx])
                except: continue
    return None

def call_m(model_key, system, user, max_tokens=8192):
    result = call_api(model_key, system, user, max_tokens=max_tokens)
    text = result[0] if isinstance(result, tuple) else result
    data = extract_json(text)
    if data: return data
    print(f"[DEBUG]\n{text[:500]}")
    raise ValueError("JSON解析失败")

def read_ref(name):
    with open(f"references/{name}", encoding="utf-8") as f:
        return f.read()

story_text = open(f"{PROJECT}/story.txt", encoding="utf-8").read()
intent = load_json(f"{PROJECT}/director_intent.json")
system = "你是专业的剧本分析师。只返回JSON，不要其他文字。"

print("=" * 60)
print("Phase 1: Story DNA (gemma4, beat_id格式检查)")
print("=" * 60)

# 只取 story_dna.md 的 SYSTEM_PROMPT 部分（不包括beat分析prompt）
user = read_ref("story_dna.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_text': story_text, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n输出JSON。只返回JSON。"
dna = call_m("gemma4", system, user)
save_json(f"{PROJECT}/story_dna.json", dna)
beat_ids = list(dna.get("narrative_functions", {}).keys())
print(f"✅ Phase 1 完成: {len(beat_ids)} beats")
print(f"   beat_id格式: {beat_ids[:5]}")

# 验证格式
import re
all_b01 = all(re.match(r"B\d+", bid) for bid in beat_ids)
print(f"   格式正确(B01/B02...): {all_b01}")

print("\n" + "=" * 60)
print("Phase 2: Beat生成 (gemma4)")
print("=" * 60)
user = read_ref("beat_analysis.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_text': story_text, 'story_dna': dna, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n输出JSON。"
beats = call_m("gemma4", system, user)
save_json(f"{PROJECT}/story_beats.json", beats)
beat_list = beats.get("beats", [])
beat_ids2 = [b.get("beat_id") for b in beat_list]
print(f"✅ Phase 2 完成: {len(beat_list)} beats")
print(f"   beat_id格式: {beat_ids2[:5]}")
all_b02 = all(re.match(r"B\d+", bid) for bid in beat_ids2)
print(f"   格式正确: {all_b02}")
total_dur = sum(b.get("duration_estimate", 5) for b in beat_list)
print(f"   总时长: {total_dur}s (目标: {intent['duration_target']})")

print("\n✅ Phase 1-2 格式验证完成!")
