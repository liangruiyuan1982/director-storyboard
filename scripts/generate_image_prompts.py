#!/usr/bin/env python3
"""Phase 4e: 为所有 panels 生成 image_prompt（gemma4）"""
import sys, json, re, os
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-last-supper"
SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
os.chdir(SKILL_DIR)

def load_json(path):
    with open(path) as f: return json.load(f)

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

panels = load_json(f"{PROJECT}/panels.json")["panels"]
chars = load_json(f"{PROJECT}/characters.json")
char_vis = load_json(f"{PROJECT}/character_visuals.json")
chars_vis_map = {}
for cv in char_vis.get("character_visuals", []):
    for app in cv.get("appearances", []):
        chars_vis_map[cv["name"]] = app["descriptions"][0] if app["descriptions"] else ""

# Build per-panel context (minimized)
panel_contexts = []
for p in panels:
    beat_id = p["beat_id"]
    char_prompts_raw = p.get("character_prompts", [])
    char_prompts_str = "\n".join(char_prompts_raw) if char_prompts_raw else "无角色描述"
    
    # Determine frame count
    cam = p.get("camera_movement", "Static")
    if cam in ("Static",) or p.get("shot_type", "") in ("特写", "极端特写"):
        frame_count = 1
    elif cam in ("Orbit",):
        frame_count = 3
    else:
        frame_count = 2  # Push/Pull/Pan/Track/Follow/Crane etc.
    
    ctx = {
        "panel_id": p["panel_id"],
        "beat_id": beat_id,
        "shot_type": p.get("shot_type", "中景"),
        "camera_movement": cam,
        "frame_count": frame_count,
        "scene_description": p.get("scene_description", ""),
        "performance_notes": p.get("performance_notes", ""),
        "facial_expression": p.get("facial_expression", "N/A"),
        "lighting": p.get("lighting", ""),
        "dominant_color": p.get("dominant_color", ""),
        "color_temperature": p.get("color_temperature", 5500),
        "duration": p.get("duration", 5),
        "key_visual_moment": p.get("key_visual_moment", False),
        "character_prompts": char_prompts_str,
    }
    panel_contexts.append(ctx)

system = "你是专业的AI视频关键帧画面设计师。只返回JSON。"
template = read_ref("keyframe_gen.md")

# Process in batches of 3 panels to avoid token overflow
all_keyframes = {}
for i in range(0, len(panel_contexts), 3):
    batch = panel_contexts[i:i+3]
    batch_json = json.dumps({"panels": batch}, ensure_ascii=False)
    user = template + f"\n\n## 输入数据\n```json\n{batch_json}\n```\n\n输出JSON。只返回JSON。"
    
    print(f"  处理 P{panel_contexts[i]['panel_id'][1:]}~P{panel_contexts[min(i+2, len(panel_contexts)-1)]['panel_id'][1:]}...")
    result = call_m("gemma4", system, user)
    
    # result should be dict: {"P01": {...}, "P02": {...}, ...}
    if isinstance(result, dict):
        all_keyframes.update(result)
    elif isinstance(result, list):
        # Sometimes LLM returns list
        for item in result:
            if isinstance(item, dict):
                for k, v in item.items():
                    if k.startswith("P"):
                        all_keyframes[k] = v

print(f"\n✅ 生成了 {len(all_keyframes)} 个 panel 的 keyframes")

# Save keyframes separately
keyframes_out = {"keyframes": all_keyframes, "generated_at": str(__import__('datetime').datetime.now())}
with open(f"{PROJECT}/keyframes.json", "w") as f:
    json.dump(keyframes_out, f, ensure_ascii=False, indent=2)

# Update panels.json with keyframes
panels_full = load_json(f"{PROJECT}/panels.json")
for p in panels_full["panels"]:
    pid = p["panel_id"]
    if pid in all_keyframes:
        p["keyframes"] = all_keyframes[pid].get("keyframes", [])

with open(f"{PROJECT}/panels.json", "w") as f:
    json.dump(panels_full, f, ensure_ascii=False, indent=2)

print(f"✅ panels.json 更新完成（含 keyframes）")

# Print sample
for pid, kf_data in list(all_keyframes.items())[:2]:
    for kf in kf_data.get("keyframes", []):
        print(f"\n{pid} {kf.get('frame_type')}:")
        print(f"  {kf.get('image_prompt','')[:150]}...")
