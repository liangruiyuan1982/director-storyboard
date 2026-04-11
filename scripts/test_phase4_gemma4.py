#!/usr/bin/env python3
"""用 gemma4 测试完整 Phase 4"""
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

system_json = "你是专业AI助手。只返回JSON，不要其他文字。"

beats_full = load_json(f"{PROJECT}/story_beats.json")
intent = load_json(f"{PROJECT}/director_intent.json")

# 精简 beats
BEAT_FIELDS = ("beat_id","emotion","emotion_intensity","narrative_function",
               "scene","key_visual_moment","three_act_position","duration_estimate")
beats_min = {"beats": [{k: v for k, v in b.items() if k in BEAT_FIELDS} for b in beats_full.get("beats", [])]}

# Phase 4a: Color Script
print("4a: Color Script...")
cs = call_m("gemma4", system_json, read_ref("color_script.md") +
    f"\n\n## 输入\n```json\n{json.dumps({'story_beats': beats_min, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n输出JSON。")
save_json(f"{PROJECT}/color_script.json", cs)
print(f"  ✅ 全局={cs.get('global_color_theme','')[:50]}")
print(f"  示例: {[(b['beat_id'], b['dominant_color']) for b in cs.get('beats',[])[:3]]}")

# Phase 4b: Photography
print("4b: Photography...")
cs_beats = {"beats": cs.get("beats", [])}
photo_input = {"story_beats": beats_min, "color_script": cs_beats, "director_intent": intent}
user = read_ref("cinematography.md") + f"\n\n## 输入\n```json\n{json.dumps(photo_input, ensure_ascii=False)}\n```\n\n输出JSON。"
photo = call_m("gemma4", system_json, user)
save_json(f"{PROJECT}/photography.json", photo)
print(f"  ✅ {len(photo.get('shots',[]))} shots")
gs = photo.get("global_style", {})
print(f"  风格={gs.get('imaging_style')} | 叙事距离={gs.get('narrative_distance')}")
for s in photo.get("shots",[])[:2]:
    print(f"  {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:35]}...")

# Phase 4c: Acting
print("4c: Acting...")
chars = load_json(f"{PROJECT}/characters.json")
chars_min = {"characters": [{k: v for k, v in c.items() if k in ("name","aliases","personality_tags","role_level")} for c in chars.get("characters", [])]}
acting_input = {"story_beats": beats_min, "characters": chars_min, "director_intent": intent}
user = read_ref("acting.md") + f"\n\n## 输入\n```json\n{json.dumps(acting_input, ensure_ascii=False)}\n```\n\n输出JSON。"
acting = call_m("gemma4", system_json, user)
save_json(f"{PROJECT}/acting.json", acting)
print(f"  ✅ {len(acting.get('panels',[]))} panels")
for p in acting.get("panels",[])[:2]:
    print(f"  {p.get('beat_id')}: {p.get('performance_notes','')[:40]}...")
    print(f"    潜:{p.get('emotional_subtext','')[:50]} | 导演:{p.get('performance_directive','')[:45]}...")

print("\n✅ Phase 4 (gemma4) 全部完成!")
