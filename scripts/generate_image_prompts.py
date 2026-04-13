#!/usr/bin/env python3
"""Phase 4e: 为所有 panels 生成 image_prompt（gemma4）"""
import sys, json, re, os
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
os.chdir(SKILL_DIR)

# 解析 --project 参数
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--project', default='test-last-supper')
args = parser.parse_args()
PROJECT = f"/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/{args.project}"

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
def extract_core_look(desc: str) -> str:
    if not desc:
        return ""
    text = desc.replace("\n", " ").strip()
    stop_markers = ["站", "坐", "跑", "走", "扶", "停", "目光", "神情", "场景", "背景", "环境", "位于画面", "镜头", "视角", "机位", "光线", "整体画面", "（功能："]
    cut = len(text)
    for marker in stop_markers:
        idx = text.find(marker)
        if idx > 0:
            cut = min(cut, idx)
    core = text[:cut].strip(" ，。；")
    return core


def extract_state_variant(desc: str) -> str:
    if not desc:
        return ""
    text = desc.replace("\n", " ").strip()
    if "（功能：" in text:
        text = text.split("（功能：", 1)[0].strip()
    return text

chars_vis_map = {}
for cv in char_vis.get("character_visuals", []):
    cname = cv.get("name", "")
    chars_vis_map[cname] = {}
    for app in cv.get("appearances", []):
        aid = app.get("id", app.get("appearance_id", 0))
        descs = app.get("descriptions", [])
        full = descs[0] if descs else ""
        core = app.get("core_look", "") or extract_core_look(full)
        state_variant = app.get("state_variant", "") or ""
        chars_vis_map[cname][aid] = {
            "full": full,
            "core": core,
            "state_variant": state_variant,
            "fallback_state": extract_state_variant(full)
        }

# Build per-panel context (minimized)
panel_contexts = []
for p in panels:
    beat_id = p["beat_id"]
    char_prompts_raw = p.get("character_prompts", [])
    char_prompts_str = "\n".join(char_prompts_raw) if char_prompts_raw else "无角色描述"
    appearance_refs = "、".join(p.get("appearance_refs", [])) if p.get("appearance_refs") else "未指定appearance"
    core_looks = []
    state_variants = []
    for item in p.get("character_appearances", []):
        cname = item.get("name", "")
        aid = item.get("appearance_id", 0)
        vis = chars_vis_map.get(cname, {}).get(aid, {})
        core = vis.get("core", "")
        state_variant = vis.get("state_variant", "")
        if core:
            core_looks.append(f"{cname}(appearance_{aid}): {core}")
        if state_variant:
            state_variants.append(f"{cname}(appearance_{aid}): {state_variant}")
    core_looks_str = "\n".join(core_looks) if core_looks else "无稳定外观描述"
    state_variants_str = "\n".join(state_variants) if state_variants else "无版本差异说明"
    
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
        "freeze_action": p.get("freeze_action", ""),
        "body_tension": p.get("body_tension", ""),
        "energy_state": p.get("energy_state", ""),
        "visual_task": p.get("visual_task", ""),
        "frame_priority": p.get("frame_priority", ""),
        "facial_expression": p.get("facial_expression", "N/A"),
        "lighting": p.get("lighting", ""),
        "dominant_color": p.get("dominant_color", ""),
        "color_temperature": p.get("color_temperature", 5500),
        "duration": p.get("duration", 5),
        "key_visual_moment": p.get("key_visual_moment", False),
        "character_prompts": char_prompts_str,
        "character_core_looks": core_looks_str,
        "character_state_variants": state_variants_str,
        "appearance_refs": appearance_refs,
    }
    panel_contexts.append(ctx)

system = "你是专业的AI视频关键帧画面设计师。只返回JSON。"
template = read_ref("keyframe_gen.md")

# Process in batches of 3 panels to avoid token overflow
all_keyframes = {}  # accumulate across batches: {pid: {panel_data_with_keyframes}}
for i in range(0, len(panel_contexts), 3):
    batch = panel_contexts[i:i+3]
    batch_json = json.dumps({"panels": batch}, ensure_ascii=False)
    user = template + f"\n\n## 输入数据\n```json\n{batch_json}\n```\n\n输出JSON。只返回JSON。"
    
    pids_this_batch = [panel_contexts[j]["panel_id"] for j in range(i, min(i+3, len(panel_contexts)))]
    print(f"  处理 {pids_this_batch[0]}~{pids_this_batch[-1]}...")
    
    try:
        result = call_m("gemma4", system, user)
        if isinstance(result, dict):
            # If result has 'keyframes' wrapper key, unwrap it
            if "keyframes" in result and isinstance(result["keyframes"], dict):
                result = result["keyframes"]
            # Accumulate into all_keyframes (MERGE, not overwrite)
            before = len(all_keyframes)
            all_keyframes.update(result)
            after = len(all_keyframes)
            print(f"    batch got {len(result)} panels, total accumulated: {after}")
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if str(k).startswith("P"):
                            all_keyframes[k] = v
        else:
            print(f"    ⚠️ unexpected result type: {type(result)}, retrying one-by-one")
            for ctx in batch:
                single = json.dumps({"panels": [ctx]}, ensure_ascii=False)
                single_user = template + f"\n\n## 输入数据\n```json\n{single}\n```\n\n输出JSON。只返回JSON。"
                try:
                    r = call_m("gemma4", system, single_user)
                    if isinstance(r, dict):
                        all_keyframes.update(r)
                except Exception as ex:
                    print(f"    ⚠️ {ctx['panel_id']} failed: {ex}")
    except Exception as e:
        print(f"    ⚠️ batch failed: {e}, retrying one-by-one")
        for ctx in batch:
            single = json.dumps({"panels": [ctx]}, ensure_ascii=False)
            single_user = template + f"\n\n## 输入数据\n```json\n{single}\n```\n\n输出JSON。只返回JSON。"
            try:
                r = call_m("gemma4", system, single_user)
                if isinstance(r, dict):
                    all_keyframes.update(r)
            except Exception as ex:
                print(f"    ⚠️ {ctx['panel_id']} failed: {ex}")

print(f"\n✅ 生成了 {len(all_keyframes)} 个 panel 的 keyframes")

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
        v = all_keyframes[pid]
        # Handle various return structures
        if isinstance(v, dict):
            if "keyframes" in v:
                p["keyframes"] = v["keyframes"]
            elif "frames" in v:
                p["keyframes"] = v["frames"]
            else:
                # Assume the dict itself is the panel data with keyframes nested
                p["keyframes"] = list(v.values())[0] if v else []
        else:
            p["keyframes"] = []

with open(f"{PROJECT}/panels.json", "w") as f:
    json.dump(panels_full, f, ensure_ascii=False, indent=2)

print(f"✅ panels.json 更新完成（含 keyframes）")

# Print sample
for pid, kf_data in list(all_keyframes.items())[:2]:
    for kf in kf_data.get("keyframes", []):
        print(f"\n{pid} {kf.get('frame_type')}:")
        print(f"  {kf.get('image_prompt','')[:150]}...")
