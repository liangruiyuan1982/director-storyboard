#!/usr/bin/env python3
"""完整 pipeline：marathon-essay 项目"""
import sys, json, os, time
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api
from pathlib import Path

PROJECT = Path("/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/marathon-essay")
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
    print(f"[JSON解析失败]\n响应末尾500字:\n{t[-500:]}")
    raise ValueError("JSON解析失败")

system = "你是专业AI助手。只返回JSON，不要其他文字。"
MODEL = "glm51"

story = open(PROJECT/"story.txt").read()
intent = lj(PROJECT/"director_intent.json")
target = int(intent['duration_target'].rstrip('s'))

def ref(name): return open(f"references/{name}").read()
def inp(**kw): return json.dumps(kw, ensure_ascii=False)

def fmt_time(s):
    m, sec = int(s)//60, int(s)%60
    return f"{m}:{sec:02d}" if m else f"{sec}s"

print(f"{'='*70}")
print(f"🎬 跑到最后 — 完整分镜制作")
print(f"{'='*70}")
print(f"字数: {len(story)} | 目标: {target}s | 模型: {MODEL}")
print()

# ── Phase 1: Story DNA ───────────────────────────────────────────────
print(f"{'─'*70}")
print(f"📍 Phase 1: Story DNA")
print(f"{'─'*70}")
dna, et = call_m(MODEL, system, ref("story_dna.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"story_dna.json", dna)
tp1 = dna["three_act_structure"]["turning_point_1"]
tp2 = dna["three_act_structure"]["turning_point_2"]
print(f"✅ {fmt_time(et)} | 三幕: {tp1} | TP1→{tp2}")
ec = dna.get("emotional_climax","?")
print(f"   情感高潮: {ec}")
narr_fn = dna.get("narrative_functions", {})
for bid, info in list(narr_fn.items())[:6]:
    print(f"   {bid}: {info.get('function','?')} — {info.get('description','')[:50]}...")

# ── Phase 1.5: Look Development ────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 1.5: Look Development")
print(f"{'─'*70}")
ld, et = call_m(MODEL, system, ref("lookdev.md") + f"\n\n## 输入\n```json\n{inp(story_dna=dna, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"lookdev.json", ld)
print(f"✅ {fmt_time(et)}")
print(f"   视觉母题: {ld.get('visual_motif','')[:100]}...")
print(f"   色调关键词: {ld.get('color_keywords',[])}")
for m in ld.get("emotion_color_mapping", []):
    print(f"   [{m.get('phase','')}] {m.get('color_keywords',[])} → {m.get('narrative_meaning','')[:60]}")

# ── Phase 2: Beats ─────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 2: Beats")
print(f"{'─'*70}")
beats, et = call_m(MODEL, system, ref("beat_analysis.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, story_dna=dna, director_intent=intent)}\n```\n\nJSON。", max_t=16384)
sj(PROJECT/"story_beats.json", beats)
bl = beats.get("beats", [])
total_dur = sum(b.get("duration_estimate", 5) for b in bl)
dur_pct = int(total_dur/target*100)
ok = "✅" if total_dur >= target*0.9 else "⚠️"
print(f"✅ {fmt_time(et)} | {len(bl)} beats | {total_dur}s ({dur_pct}%) {ok}")
for b in bl:
    kf = "⭐" if b.get("key_visual_moment") else "  "
    vo = b.get("voiceover","")[:50]
    print(f"   {kf}{b.get('beat_id')}[{b.get('narrative_function','?')}|{b.get('duration_estimate')}s] {b.get('emotion','?')}")
    print(f"       🎤 {vo}...")

# ── Phase 3: Characters ─────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 3: Characters")
print(f"{'─'*70}")
chars, et = call_m(MODEL, system, ref("character_card.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, story_dna=dna, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"characters.json", chars)
chars_min = {"characters":[
    {k:v for k,v in c.items()
     if k in ("name","aliases","gender","age_range","role_level","personality_tags",
              "visual_narrative_function","director_visual_priority","expected_appearances")}
    for c in chars.get("characters",[])]}

vis_tpl = open("references/character_visual.md").read()
vis_sys = vis_tpl.split("## 非人类角色")[0] if "## 非人类角色" in vis_tpl else vis_tpl
vis, et2 = call_m(MODEL, system, vis_sys + f"\n\n## 输入\n```json\n{inp(characters=chars_min, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"character_visuals.json", vis)
print(f"✅ Phase 3a {fmt_time(et)} + 3b {fmt_time(et2)}")
for c in chars.get("characters",[]):
    vnf = c.get("visual_narrative_function","")[:100]
    print(f"   {c.get('name')} [{c.get('role_level','')}]")
    print(f"       视觉功能: {vnf}...")
    for ea in c.get("expected_appearances",[]):
        print(f"       id={ea.get('appearance_id',ea.get('id','?'))} {ea.get('change_reason','')[:60]}")

# Check differentiation
cv_root = vis.get("appearance_generation", vis.get("character_visuals", vis.get("characters",[])))
for cv in cv_root:
    cname = cv.get("name","")
    apps = cv.get("appearances",[])
    if len(apps)>=2:
        d0 = (apps[0].get("description","") or (apps[0].get("descriptions",[""])[0] or ""))[:40]
        d1 = (apps[1].get("description","") or (apps[1].get("descriptions",[""])[0] or ""))[:40]
        diff = "✅不同" if d0!=d1 else "⚠️相同"
        print(f"       外观差异: {diff} | id0:{d0[:30]} | id1:{d1[:30]}")

# ── Phase 4: Cinematography ────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 4: Cinematography")
print(f"{'─'*70}")
beats_min = {"beats":[
    {k:v for k,v in b.items()
     if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene",
              "key_visual_moment","three_act_position","duration_estimate","characters")}
    for b in bl
]}

# 4a Color Script
print("⏳ Color Script...", end=" ", flush=True)
t0 = time.time()
cs, _ = call_m(MODEL, system, ref("color_script.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, director_intent=intent, lookdev=ld)}\n```\n\nJSON。")
sj(PROJECT/"color_script.json", cs)
print(f"✅ {fmt_time(time.time()-t0)}")
print(f"   全局: {cs.get('global_color_theme','')[:100]}...")

# 4b Photography
print("⏳ Photography...", end=" ", flush=True)
t0 = time.time()
ph, _ = call_m(MODEL, system, ref("cinematography.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, color_script={'beats':cs.get('beats',[])}, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"photography.json", ph)
gs = ph.get("global_style",{})
print(f"✅ {fmt_time(time.time()-t0)}")
print(f"   风格: {gs.get('imaging_style')} | 叙事距离: {gs.get('narrative_distance')}")
for s in ph.get("shots",[]):
    print(f"   {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:50]}...")

# 4c Acting
print("⏳ Acting...", end=" ", flush=True)
t0 = time.time()
ac, _ = call_m(MODEL, system, ref("acting.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, characters=chars_min, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"acting.json", ac)
print(f"✅ {fmt_time(time.time()-t0)}")
for p in ac.get("panels",[]):
    print(f"   {p.get('beat_id')}: {p.get('performance_notes','')[:70]}...")
    print(f"       潜: {p.get('emotional_subtext','')[:70]}...")
    if p.get('performance_directive'):
        print(f"       导: {p.get('performance_directive','')[:70]}...")

# ── Phase 4d: Assembly ─────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 4d: 分镜组装")
print(f"{'─'*70}")

# Build vis map
vis_map = {}
vis_root = vis.get("appearance_generation", vis.get("character_visuals", vis.get("characters",[])))
for cv in vis_root:
    cname = cv.get("name","")
    for app in cv.get("appearances",[]):
        aid = app.get("id", app.get("appearance_id",0))
        desc = app.get("description","") or (app.get("descriptions",[""])[0] or "")
        vis_map[(cname, aid)] = desc

char_first = {}
for c in chars.get("characters",[]):
    ea = c.get("expected_appearances",[])
    char_first[c["name"]] = ea[0].get("appearance_id",ea[0].get("id",0)) if ea else 0

panels = []
for i, beat in enumerate(bl):
    bid = beat["beat_id"]
    shot = next((s for s in ph.get("shots",[]) if s.get("beat_id")==bid),{})
    act = next((a for a in ac.get("panels",[]) if a.get("beat_id")==bid),{})
    csb = next((c for c in cs.get("beats",[]) if c.get("beat_id")==bid),{})
    q6 = intent.get("q6_transition_philosophy","Mix")
    tr = {"硬切":"cut","Dissolve":"dissolve","Fade":"fade"}.get(q6, csb.get("transition_to_next","cut") or "cut")
    vprompt = " ".join(filter(None,[
        shot.get("camera_movement","Static"),
        beat.get("visual_hint",""),
        act.get("performance_notes",""),
        csb.get("dominant_color","")
    ]))
    beat_chars = beat.get("characters",[])
    pcp, pcn = [], []
    if beat_chars:
        for cname in beat_chars:
            aid = char_first.get(cname,0)
            desc = vis_map.get((cname,aid),"")
            if desc: pcn.append(cname); pcp.append(desc[:200])
    elif char_first:
        for cname, aid in char_first.items():
            desc = vis_map.get((cname,aid),"")
            if desc: pcn.append(cname); pcp.append(desc[:200])
    panels.append({
        "panel_id":f"P{i+1:02d}","beat_id":bid,"duration":beat.get("duration_estimate",5),
        "shot_type":shot.get("shot_type","中景"),"camera_movement":shot.get("camera_movement","Static"),
        "scene_description":beat.get("visual_hint",""),"voiceover":beat.get("voiceover",""),
        "transition":tr,"lighting":shot.get("lighting",""),
        "depth_of_field":shot.get("depth_of_field",""),
        "color_temperature":shot.get("color_temperature",5500),
        "performance_notes":act.get("performance_notes",""),
        "emotional_subtext":act.get("emotional_subtext",""),
        "performance_directive":act.get("performance_directive",""),
        "facial_expression":act.get("facial_expression","N/A"),
        "body_language":act.get("body_language","N/A"),
        "dominant_color":csb.get("dominant_color",""),
        "color_narrative":csb.get("narrative_function",""),
        "characters":pcn,"character_prompts":pcp,"video_prompt":vprompt,
        "key_visual_moment":beat.get("key_visual_moment",False),
        "directors_note":"","keyframes":[],"versions":[]
    })

sj(PROJECT/"panels.json",{"panels":panels})
total = sum(p["duration"] for p in panels)
print(f"✅ {len(panels)} panels | {total}s")
for p in panels:
    kf = "⭐" if p.get("key_visual_moment") else "  "
    print(f"   {kf}{p['panel_id']} | {p['beat_id']} | {p['shot_type']} | {p['camera_movement']} | {p['transition']}")

# ── Phase 5: Viewer ────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 5: 导演工作台")
print(f"{'─'*70}")
import subprocess
r = subprocess.run(
    [sys.executable, str(SKILL_DIR/"scripts/generate_viewer.py"), "marathon-essay"],
    capture_output=True, text=True, timeout=30, cwd=str(SKILL_DIR)
)
print(r.stdout.strip() if r.returncode==0 else f"⚠️ viewer生成: {r.stderr[:200]}")

# ── Final Summary ───────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"📋 完整分镜总结")
print(f"{'='*70}")
print(f"标题: {intent['story_title']}")
print(f"风格: {intent['q1_imaging_style']} | 叙事距离: {intent['q2_narrative_distance']} | 时长: {intent['q3_time_sense']} | 色调: {intent['q4_color_tone']}")
print(f"旁白: {intent['q5_voiceover_type']} | 过渡: {intent['q6_transition_philosophy']}")
print(f"Beats: {len(bl)} | 总时长: {total_dur}s ({dur_pct}%) | 目标: {target}s")
print(f"Panels: {len(panels)} | {total}s")
print(f"时长达成: {'✅' if total_dur >= target*0.9 else '⚠️'} ({total_dur}s / {target}s)")
print(f"\n输出文件:")
for fn in ["story_dna.json","lookdev.json","story_beats.json","characters.json",
           "character_visuals.json","color_script.json","photography.json",
           "acting.json","panels.json","viewer.html"]:
    fp = PROJECT/fn
    status = "✅" if fp.exists() else "❌"
    size = fp.stat().st_size if fp.exists() else 0
    size_str = f"{size}B" if size < 1024 else f"{size//1024}KB ({size}B)"
    print(f"   {status} {fn} ({size_str})")
print(f"\n🎬 分镜制作完成!")
