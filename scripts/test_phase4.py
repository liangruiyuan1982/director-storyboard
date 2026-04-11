#!/usr/bin/env python3
"""测试 Phase 4: Color Script + Photography + Acting"""
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

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_json(text):
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
    if m:
        return m.group(1).strip()
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
            if end_idx > 0: return text[idx:end_idx]
    return None

def call_model(model_key, system, user_prompt, max_tokens=8192):
    result = call_api(model_key, system, user_prompt, max_tokens=max_tokens)
    text = result[0] if isinstance(result, tuple) else result
    json_str = extract_json(text)
    if json_str:
        return json.loads(json_str)
    print(f"  [DEBUG] raw:\n{text[:600]}")
    raise ValueError(f"无法提取JSON")

def read_ref(name):
    with open(f"references/{name}", encoding="utf-8") as f:
        return f.read()

system = "你是一个专业的AI助手。输出JSON，只返回JSON。"

print("=" * 60)
print("🎬 Phase 4a: Color Script")
print("=" * 60)
story_beats = load_json(f"{PROJECT}/story_beats.json")
intent = load_json(f"{PROJECT}/director_intent.json")

user = read_ref("color_script.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_beats': story_beats, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
cs = call_model("glm51", system, user)
save_json(f"{PROJECT}/color_script.json", cs)
print(f"✅ Color Script 完成")
print(f"   全局色调主题: {cs.get('global_color_theme', 'N/A')}")
for b in cs.get('beats', [])[:5]:
    print(f"   {b.get('beat_id')}: {b.get('dominant_color')} | {b.get('narrative_function','')[:40]}...")
    print(f"     → {b.get('transition_to_next','')[:60]}")

print("\n" + "=" * 60)
print("🎬 Phase 4b: Photography")
print("=" * 60)
story_dna = load_json(f"{PROJECT}/story_dna.json")

user = read_ref("cinematography.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_beats': story_beats, 'color_script': cs, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
photo = call_model("glm51", system, user)
save_json(f"{PROJECT}/photography.json", photo)
print(f"✅ Photography 完成")
gs = photo.get('global_style', {})
print(f"   影像风格: {gs.get('imaging_style')} | 过渡: {gs.get('transition_philosophy')}")
for s in photo.get('shots', [])[:5]:
    print(f"   {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:40]}...")

print("\n" + "=" * 60)
print("🎬 Phase 4c: Acting")
print("=" * 60)
chars = load_json(f"{PROJECT}/characters.json")

user = read_ref("acting.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_beats': story_beats, 'characters': chars, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
acting = call_model("glm51", system, user)
save_json(f"{PROJECT}/acting.json", acting)
print(f"✅ Acting 完成")
for p in acting.get('panels', [])[:4]:
    pn = p.get('performance_notes','')[:50]
    es = p.get('emotional_subtext','')[:50]
    pd = p.get('performance_directive','')[:50]
    print(f"   {p.get('beat_id')}: {pn}...")
    print(f"     潜台词: {es}...")
    print(f"     导演指示: {pd}...")

print("\n✅ Phase 4a-4c 全部完成!")
