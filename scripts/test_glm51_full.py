#!/usr/bin/env python3
"""完整 pipeline 测试：glm51"""
import sys, json, os, time
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api
from pathlib import Path

PROJECT = Path("/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-glm51")
SKILL_DIR = Path("/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard")
os.chdir(SKILL_DIR)

def lj(p): return json.load(open(p))
def sj(p,d): open(p,"w").write(json.dumps(d,ensure_ascii=False,indent=2))
def extract_json(text):
    for sc, cl in [('{','}'),('[',']')]:
        idx = 0
        while idx < len(text):
            ni = text.find(sc, idx)
            if ni < 0: break
            depth = 0; ei = -1
            for i, c in enumerate(text[ni:], ni):
                if c == sc: depth += 1
                elif c == cl:
                    depth -= 1
                    if depth == 0: ei = i+1; break
            if ei > 0:
                try: return json.loads(text[ni:ei])
                except: pass
            idx = ni + 1
    return None

def call_m(m, sys_txt, user, max_t=8192):
    t0 = time.time()
    r = call_api(m, sys_txt, user, max_tokens=max_t)
    t = r[0] if isinstance(r, tuple) else r
    data = extract_json(t)
    elapsed = time.time() - t0
    if data: return data, elapsed
    print(f"[DEBUG tail]\n{t[-500:]}")
    raise ValueError("JSON解析失败")

system = "你是专业AI助手。只返回JSON，不要其他文字。"
MODEL = "glm51"

story = open(PROJECT/"story.txt").read()
intent = lj(PROJECT/"director_intent.json")
target = int(intent['duration_target'].rstrip('s'))

def ref(name): return open(f"references/{name}").read()

def inp(**kwargs): return json.dumps(kwargs, ensure_ascii=False)

# ── Phase 1: Story DNA ────────────────────────────────────────────────
print("="*65)
print(f"📍 Phase 1 Story DNA (glm51)")
print("="*65)
t0 = time.time()
dna, et = call_m(MODEL, system, ref("story_dna.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"story_dna.json", dna)
print(f"✅ {et:.0f}s | 三幕: {dna['three_act_structure']['act_1_end_beat']} | TP1: {dna['three_act_structure']['turning_point_1']} | TP2: {dna['three_act_structure']['turning_point_2']}")
print(f"   情感高潮: {dna.get('emotional_climax','?')}")
narr_fn = dna.get("narrative_functions", {})
for bid, info in list(narr_fn.items())[:3]:
    print(f"   {bid}: {info.get('function','?')} — {info.get('description','')[:50]}...")

# ── Phase 1.5: Look Development ────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 1.5 Look Development (glm51)")
print("="*65)
t0 = time.time()
ld, et = call_m(MODEL, system, ref("lookdev.md") + f"\n\n## 输入\n```json\n{inp(story_dna=dna, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"lookdev.json", ld)
print(f"✅ {et:.0f}s")
print(f"   视觉母题: {ld.get('visual_motif','')[:80]}...")
print(f"   色调关键词: {ld.get('color_keywords',[])}")
print(f"   摄影机哲学: {ld.get('camera_philosophy','')[:70]}...")
for m in ld.get("emotion_color_mapping", []):
    print(f"   [{m.get('phase','')}] {m.get('color_keywords',[])} — {m.get('narrative_meaning','')}")

# ── Phase 2: Beats ──────────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 2 Beats (glm51)")
print("="*65)
t0 = time.time()
beats, et = call_m(MODEL, system, ref("beat_analysis.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, story_dna=dna, director_intent=intent)}\n```\n\nJSON。", max_t=16384)
sj(PROJECT/"story_beats.json", beats)
bl = beats.get("beats", [])
total_dur = sum(b.get("duration_estimate", 5) for b in bl)
dur_pct = int(total_dur/target*100)
ok = "✅" if total_dur >= target*0.9 else "⚠️"
print(f"✅ {et:.0f}s | {len(bl)} beats | {total_dur}s ({dur_pct}%) {ok}")
print(f"   目标: {target}s | 达成: {total_dur}s = {dur_pct}%")
for b in bl:
    kf = "⭐" if b.get("key_visual_moment") else "  "
    vo = b.get("voiceover", "")[:50]
    print(f"   {kf}{b.get('beat_id')}[{b.get('narrative_function','?')}|{b.get('duration_estimate')}s] {b.get('emotion','?')} | {vo}...")

# ── Phase 3: Characters ──────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 3 Characters (glm51)")
print("="*65)
chars_min_input = {
    "story_text": story,
    "story_dna": dna,
    "director_intent": intent
}
chars, et = call_m(MODEL, system, ref("character_card.md") + f"\n\n## 输入\n```json\n{inp(**chars_min_input)}\n```\n\nJSON。")
sj(PROJECT/"characters.json", chars)
chars_min = {"characters": [
    {k:v for k,v in c.items()
     if k in ("name","aliases","gender","age_range","role_level","personality_tags",
              "visual_narrative_function","director_visual_priority","expected_appearances")}
    for c in chars.get("characters",[])
]}
vis_template = open("references/character_visual.md").read()
vis_sys = vis_template.split("## 非人类角色")[0] if "## 非人类角色" in vis_template else vis_template
vis, et2 = call_m(MODEL, system, vis_sys + f"\n\n## 输入\n```json\n{inp(characters=chars_min, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"character_visuals.json", vis)
print(f"✅ Phase 3a {et:.0f}s + 3b {et2:.0f}s")
for c in chars.get("characters", []):
    vnf = c.get("visual_narrative_function","")[:90]
    print(f"   {c.get('name')} [{c.get('role_level','')}] — {vnf}...")
    ea = c.get("expected_appearances", [])
    for a in ea:
        print(f"     id={a.get('appearance_id',0)} {a.get('change_reason','')[:50]}")
# Check differentiation
cv_data = vis.get("appearance_generation", vis.get("character_visuals", []))
for cv in cv_data:
    apps = cv.get("appearances", [])
    if len(apps) >= 2:
        d0 = apps[0].get("description","")[:30] if isinstance(apps[0], dict) else ""
        d1 = apps[1].get("description","")[:30] if isinstance(apps[1], dict) else ""
        if not d0: d0 = apps[0].get("descriptions",[""])[0][:30]
        if not d1: d1 = apps[1].get("descriptions",[""])[0][:30]
        diff = "✅不同" if d0 != d1 else "⚠️相同"
        print(f"     外观差异: {diff}")

# ── Phase 4: Cinematography ─────────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 4 Cinematography (glm51)")
print("="*65)

beats_min = {"beats": [
    {k:v for k,v in b.items()
     if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene",
              "key_visual_moment","three_act_position","duration_estimate")}
    for b in bl
]}

print("⏳ Color Script...", end=" ", flush=True)
t0 = time.time()
cs, _ = call_m(MODEL, system, ref("color_script.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, director_intent=intent, lookdev=ld)}\n```\n\nJSON。")
sj(PROJECT/"color_script.json", cs)
print(f"✅ {time.time()-t0:.0f}s | {cs.get('global_color_theme','')[:60]}...")

print("⏳ Photography...", end=" ", flush=True)
t0 = time.time()
ph, _ = call_m(MODEL, system, ref("cinematography.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, color_script={'beats':cs.get('beats',[])}, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"photography.json", ph)
gs = ph.get("global_style", {})
print(f"✅ {time.time()-t0:.0f}s | 风格={gs.get('imaging_style')} | 距离={gs.get('narrative_distance')}")
for s in ph.get("shots",[])[:4]:
    print(f"   {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:40]}...")

print("⏳ Acting...", end=" ", flush=True)
t0 = time.time()
ac, _ = call_m(MODEL, system, ref("acting.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, characters=chars_min, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"acting.json", ac)
print(f"✅ {time.time()-t0:.0f}s")
for p in ac.get("panels",[])[:3]:
    print(f"   {p.get('beat_id')}: {p.get('performance_notes','')[:50]}...")
    print(f"     潜: {p.get('emotional_subtext','')[:60]}...")

# ── Phase 4d: Assembly ──────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 4d 分镜组装")
print("="*65)

vis_map = {}
for cv in vis.get("appearance_generation", vis.get("character_visuals",[])):
    cname = cv.get("character_name","") or cv.get("name","")
    for app in cv.get("appearances",[]):
        aid = app.get("appearance_id", app.get("id",0))
        desc = (app.get("description","") or app.get("descriptions",[""])[0] or "").split("（功能")[0].split(" (功能")[0]
        vis_map[(cname, aid)] = desc

panels = []
for i, beat in enumerate(bl):
    bid = beat["beat_id"]
    shot = next((s for s in ph.get("shots",[]) if s.get("beat_id")==bid), {})
    act = next((a for a in ac.get("panels",[]) if a.get("beat_id")==bid), {})
    csb = next((c for c in cs.get("beats",[]) if c.get("beat_id")==bid), {})
    q6 = intent.get("q6_transition_philosophy","Mix")
    tr = {"硬切":"cut","Dissolve":"dissolve","Fade":"fade"}.get(q6, csb.get("transition_to_next","cut") or "cut")
    vprompt = " ".join(filter(None,[
        shot.get("camera_movement","Static"),
        beat.get("visual_hint",""),
        act.get("performance_notes",""),
        csb.get("dominant_color","")
    ]))
    panels.append({
        "panel_id": f"P{i+1:02d}","beat_id":bid,
        "duration": beat.get("duration_estimate",5),
        "shot_type": shot.get("shot_type","中景"),
        "camera_movement": shot.get("camera_movement","Static"),
        "scene_description": beat.get("visual_hint",""),
        "voiceover": beat.get("voiceover",""),
        "transition": tr,
        "lighting": shot.get("lighting",""),
        "depth_of_field": shot.get("depth_of_field",""),
        "color_temperature": shot.get("color_temperature",5500),
        "performance_notes": act.get("performance_notes",""),
        "emotional_subtext": act.get("emotional_subtext",""),
        "performance_directive": act.get("performance_directive",""),
        "facial_expression": act.get("facial_expression","N/A"),
        "body_language": act.get("body_language","N/A"),
        "dominant_color": csb.get("dominant_color",""),
        "color_narrative": csb.get("narrative_function",""),
        "characters":[],"character_prompts":[],"video_prompt":vprompt,
        "key_visual_moment": beat.get("key_visual_moment",False),
        "directors_note":"","keyframes":[],"versions":[]
    })

sj(PROJECT/"panels.json", {"panels":panels})
total = sum(p["duration"] for p in panels)
print(f"✅ {len(panels)} panels | {total}s")
for p in panels:
    kf = "⭐" if p.get("key_visual_moment") else "  "
    print(f"   {kf}{p['panel_id']} | {p['beat_id']} | {p['shot_type']} | {p['camera_movement']} | {p['transition']}")

# ── Viewer ─────────────────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"📍 Phase 5: Viewer")
print("="*65)
import subprocess
r = subprocess.run(
    [sys.executable, str(SKILL_DIR/"scripts/generate_viewer.py"), "test-glm51"],
    capture_output=True, text=True, timeout=30, cwd=str(SKILL_DIR)
)
print(r.stdout.strip() if r.returncode == 0 else f"❌ viewer生成失败: {r.stderr[:200]}")

# ── Summary ────────────────────────────────────────────────────────
print(f"\n{'='*65}")
print("📊 测试总结")
print("="*65)
print(f"Story: {len(story)}字 | 目标: {target}s")
print(f"Beats: {len(bl)} | 实际: {total_dur}s ({int(total_dur/target*100)}%)")
print(f"Panels: {len(panels)} | {total}s")
dur_ok = "✅" if total_dur >= target*0.9 else "⚠️ 不足"
print(f"时长达成: {dur_ok}")
print(f"\n输出文件:")
for fn in ["story_dna.json","lookdev.json","story_beats.json","characters.json",
           "character_visuals.json","color_script.json","photography.json","acting.json",
           "panels.json","viewer.html"]:
    fp = PROJECT/fn
    if fp.exists():
        print(f"   ✅ {fn} ({fp.stat().st_size}B)")
    else:
        print(f"   ❌ {fn} MISSING")
