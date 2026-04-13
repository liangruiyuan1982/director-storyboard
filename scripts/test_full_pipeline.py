#!/usr/bin/env python3
"""完整专业测试：逐 Phase 跑 pipeline，评估每个环节"""
import sys, json, re, os, time
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-emotional-monologue"
SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
os.chdir(SKILL_DIR)

def load_json(path):
    with open(path) as f: return json.load(f)
def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)
def read_ref(name):
    with open(f"references/{name}") as f: return f.read()

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
                except: pass
    return None

def call_m(model, system, user, max_tokens=8192):
    result = call_api(model, system, user, max_tokens=max_tokens)
    text = result[0] if isinstance(result, tuple) else result
    data = extract_json(text)
    if data: return data
    print(f"[DEBUG]\n{text[:400]}")
    raise ValueError("JSON解析失败")

system = "你是专业AI助手。只返回JSON，不要其他文字。"
MODEL = "gemma4"

def phase_label(n):
    labels = {"0":"Phase 0 意图捕获","1":"Phase 1 Story DNA","1.5":"Phase 1.5 Look Dev",
               "2":"Phase 2 Beats","3":"Phase 3 角色","4a":"Phase 4a Color","4b":"Phase 4b Photo",
               "4c":"Phase 4c Acting","4d":"Phase 4d 组装","5":"Phase 5 Viewer"}
    return labels.get(n, n)

print("=" * 70)
print("🎬 专业测试开始：最后一班地铁（421字独白）")
print("=" * 70)

# ── Phase 1: Story DNA ──────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('1')}")
print(f"{'─'*70}")
story = open(f"{PROJECT}/story.txt").read()
intent = load_json(f"{PROJECT}/director_intent.json")
print(f"Story: {len(story)}字 | 时长目标: {intent['duration_target']}")

print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
dna = call_m(MODEL, system, read_ref("story_dna.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/story_dna.json", dna)
print(f"✅ {time.time()-t0:.0f}s")

beats_est = dna.get("three_act_structure",{}).get("total_beats_estimated","?")
ec = dna.get("emotional_climax","?")
narr_fns = dna.get("narrative_functions",{})
print(f"  三幕: Act1→{dna['three_act_structure'].get('act_1_end_beat')} | TP1→{dna['three_act_structure'].get('turning_point_1')} | TP2→{dna['three_act_structure'].get('turning_point_2')}")
print(f"  情感高潮: {ec}")
print(f"  beats: {beats_est}")
for bid, info in list(narr_fns.items())[:3]:
    print(f"  {bid}: {info.get('function','')} — {info.get('description','')[:40]}...")

# ── Phase 1.5: Look Development ─────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('1.5')} [新增]")
print(f"{'─'*70}")

print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
ld = call_m(MODEL, system, read_ref("lookdev.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/lookdev.json", ld)
print(f"✅ {time.time()-t0:.0f}s")

vm = ld.get("visual_motif","?")
kw = ld.get("color_keywords",[])
cp = ld.get("camera_philosophy","")
print(f"  视觉母题: {vm[:80]}...")
print(f"  色调关键词: {kw}")
print(f"  摄影机哲学: {cp[:60]}...")
for m in ld.get("emotion_color_mapping",[]):
    print(f"  [{m.get('phase','')}] {m.get('color_keywords',[])} — {m.get('narrative_meaning','')}")

# ── Phase 2: Beats ─────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('2')}")
print(f"{'─'*70}")

print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
beats = call_m(MODEL, system, read_ref("beat_analysis.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/story_beats.json", beats)
print(f"✅ {time.time()-t0:.0f}s")

bl = beats.get("beats",[])
total_dur = sum(b.get("duration_estimate",5) for b in bl)
print(f"  Beats: {len(bl)}个 | 总时长: {total_dur}s (目标:{intent['duration_target']})")
for b in bl:
    kf = "⭐" if b.get("key_visual_moment") else "  "
    dur = b.get("duration_estimate",5)
    em = b.get("emotion","?")
    nf = b.get("narrative_function","?")
    vh = b.get("visual_hint","")[:55]
    vo = b.get("voiceover","")
    print(f"  {kf}{b.get('beat_id')} [{nf}|{em}|{dur}s]")
    print(f"      🎥 {vh}...")
    if vo: print(f"      🎤 {vo[:60]}...")

# ── Phase 3: Characters ─────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('3')}")
print(f"{'─'*70}")

print("⏳ Phase 3a (gemma4)...", end=" ", flush=True)
t0 = time.time()
chars = call_m(MODEL, system, read_ref("character_card.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/characters.json", chars)
print(f"✅ {time.time()-t0:.0f}s")

print("⏳ Phase 3b (gemma4)...", end=" ", flush=True)
t0 = time.time()
vis = call_m(MODEL, system, read_ref("character_visual.md") + f"\n\n## 输入\n```json\n{json.dumps({'characters':chars,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/character_visuals.json", vis)
print(f"✅ {time.time()-t0:.0f}s")

for c in chars.get("characters",[]):
    print(f"  {c.get('name')} [{c.get('role_level','')}] — {c.get('gender','')} | {c.get('age_range','')}")
    vnf = c.get("visual_narrative_function","")[:90]
    dvp = c.get("director_visual_priority","")[:70]
    print(f"    视觉叙事功能: {vnf}...")
    print(f"    导演优先级: {dvp}...")

# ── Phase 4: Cinematography ─────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('4a')} Color Script")
print(f"{'─'*70}")

beats_min = {"beats":[{k:v for k,v in b.items() if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")} for b in bl]}
print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
cs = call_m(MODEL, system, read_ref("color_script.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'director_intent':intent,'lookdev':ld},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/color_script.json", cs)
print(f"✅ {time.time()-t0:.0f}s")
print(f"  全局: {cs.get('global_color_theme','')[:80]}...")
for b in cs.get("beats",[])[:3]:
    print(f"  {b.get('beat_id')}: {b.get('dominant_color')} → {b.get('transition_to_next','')[:40]}")

print(f"\n{'─'*70}")
print(f"📍 {phase_label('4b')} Photography")
print(f"{'─'*70}")

print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
photo = call_m(MODEL, system, read_ref("cinematography.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'color_script':{'beats':cs.get('beats',[])},'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/photography.json", photo)
print(f"✅ {time.time()-t0:.0f}s")
gs = photo.get("global_style",{})
print(f"  风格={gs.get('imaging_style')} | 叙事距离={gs.get('narrative_distance')} | 过渡={gs.get('transition_philosophy')}")
for s in photo.get("shots",[])[:4]:
    print(f"  {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:40]}...")

print(f"\n{'─'*70}")
print(f"📍 {phase_label('4c')} Acting")
print(f"{'─'*70}")

chars_min = {"characters":[{k:v for k,v in c.items() if k in ("name","aliases","personality_tags","role_level")} for c in chars.get("characters",[])]}
print("⏳ gemma4...", end=" ", flush=True)
t0 = time.time()
acting = call_m(MODEL, system, read_ref("acting.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'characters':chars_min,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
save_json(f"{PROJECT}/acting.json", acting)
print(f"✅ {time.time()-t0:.0f}s")
for p in acting.get("panels",[])[:3]:
    print(f"  {p.get('beat_id')}: {p.get('performance_notes','')[:50]}...")
    print(f"    潜: {p.get('emotional_subtext','')[:60]}...")
    print(f"    导演: {p.get('performance_directive','')[:60]}...")

# ── Phase 4d: Assembly ───────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('4d')} 分镜组装")
print(f"{'─'*70}")

from pipeline import assemble_panels
# We need to import from pipeline, but we can't run the full module
# Let's just assemble manually
panels = assemble_panels(PROJECT)
save_json(f"{PROJECT}/panels.json", panels)
print(f"  ✅ {len(panels['panels'])} panels | 总时长: {sum(p['duration'] for p in panels['panels'])}s")
for p in panels["panels"][:3]:
    print(f"  {p['panel_id']} | {p['beat_id']} | {p['shot_type']} | {p['camera_movement']} | {p['transition']}")
    print(f"    {p['video_prompt'][:60]}...")

# ── Phase 5: Viewer ─────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('5')} Viewer")
print(f"{'─'*70}")
from pipeline import generate_storyboard_viewer
generate_storyboard_viewer(PROJECT)
print(f"  ✅ viewer.html 生成完成")

# ── Keyframe Generation ──────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 4e: 关键帧 Image Prompt 生成")
print(f"{'─'*70}")
print("⏳ gemma4 (分2批)...", end=" ", flush=True)
t0 = time.time()

def gen_kf(panels_batch):
    user = read_ref("keyframe_gen.md") + f"\n\n## 输入\n```json\n{json.dumps({'panels':panels_batch},ensure_ascii=False)}\n```\n\nJSON。"
    return call_m(MODEL, system, user)

panel_contexts = []
for p in panels["panels"]:
    cam = p.get("camera_movement","Static")
    fc = 1 if cam in ("Static",) or p.get("shot_type","") in ("特写","极端特写") else (3 if cam=="Orbit" else 2)
    panel_contexts.append({
        "panel_id": p["panel_id"], "beat_id": p["beat_id"],
        "shot_type": p.get("shot_type","中景"), "camera_movement": cam,
        "frame_count": fc, "scene_description": p.get("scene_description",""),
        "performance_notes": p.get("performance_notes",""),
        "facial_expression": p.get("facial_expression","N/A"),
        "lighting": p.get("lighting",""), "dominant_color": p.get("dominant_color",""),
        "color_temperature": p.get("color_temperature",5500),
        "duration": p.get("duration",5),
        "key_visual_moment": p.get("key_visual_moment",False),
        "character_prompts": "\n".join(p.get("character_prompts",[])) or "无角色"
    })

all_kf = {}
for i in range(0, len(panel_contexts), 3):
    batch = panel_contexts[i:i+3]
    r = gen_kf(batch)
    if isinstance(r,dict):
        all_kf.update(r)
    elif isinstance(r,list):
        for item in r:
            if isinstance(item,dict):
                for k,v in item.items():
                    if k.startswith("P"): all_kf[k]=v

# Update panels.json with keyframes
for p in panels["panels"]:
    pid = p["panel_id"]
    if pid in all_kf:
        p["keyframes"] = all_kf[pid].get("keyframes",[])
save_json(f"{PROJECT}/panels.json", panels)
print(f"✅ {time.time()-t0:.0f}s | {len(all_kf)} panels keyframes")

# Print samples
for pid, kf_data in list(all_kf.items())[:3]:
    for kf in kf_data.get("keyframes",[]):
        ft = kf.get("frame_type","")
        pmt = kf.get("image_prompt","")
        print(f"  {pid} {ft}: {pmt[:100]}...")

# ── Summary ──────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"🎉 专业测试完成!")
print(f"{'='*70}")
print(f"项目: {PROJECT}")
print(f"Story: {len(story)}字 | 目标: {intent['duration_target']}")
print(f"Beats: {len(bl)} | 实际总时长: {total_dur}s")
print(f"Panels: {len(panels['panels'])}")
print(f"Look Dev: ✅ | Color Script: ✅ | Photography: ✅ | Acting: ✅")
print(f"Keyframes: {len(all_kf)} panels")
print(f"\n📁 输出文件:")
for f in ["story_dna.json","lookdev.json","story_beats.json","characters.json",
          "character_visuals.json","color_script.json","photography.json","acting.json",
          "panels.json","viewer.html"]:
    fp = Path(PROJECT)/f
    if fp.exists():
        size = os.path.getsize(fp)
        print(f"  ✅ {f} ({size} bytes)")
    else:
        print(f"  ❌ {f} MISSING")

from pathlib import Path
