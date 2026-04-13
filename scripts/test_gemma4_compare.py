#!/usr/bin/env python3
"""gemma4 vs glm51 对比测试：同一个故事"""
import sys, json, os, time
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api
from pathlib import Path

PROJECT = Path(os.environ.get("DIRECTOR_STORYBOARD_PROJECT", "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-gemma4"))
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
    t = r[0] if isinstance(r, tuple) else t
    data = extract_json(t)
    elapsed = time.time() - t0
    if data: return data, elapsed
    print(f"[DEBUG]\n{t[-500:]}")
    raise ValueError("JSON解析失败")

system = "你是专业AI助手。只返回JSON，不要其他文字。"
MODEL = "gemma4"

story = open(PROJECT/"story.txt").read()
intent = lj(PROJECT/"director_intent.json")
target = int(intent['duration_target'].rstrip('s'))

def ref(name): return open(f"references/{name}").read()
def inp(**kw): return json.dumps(kw, ensure_ascii=False)

print("="*70)
print(f"📍 Phase 1 Story DNA (gemma4)")
print("="*70)
t0 = time.time()
dna, et = call_m(MODEL, system, ref("story_dna.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"story_dna.json", dna)
print(f"✅ {et:.0f}s | TP1: {dna['three_act_structure']['turning_point_1']} | TP2: {dna['three_act_structure']['turning_point_2']}")

print(f"\n{'='*70}")
print(f"📍 Phase 1.5 Look Dev (gemma4)")
print("="*70)
t0 = time.time()
ld, et = call_m(MODEL, system, ref("lookdev.md") + f"\n\n## 输入\n```json\n{inp(story_dna=dna, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"lookdev.json", ld)
print(f"✅ {et:.0f}s")
print(f"   视觉母题: {ld.get('visual_motif','')[:80]}...")
print(f"   色调: {ld.get('color_keywords',[])}")

print(f"\n{'='*70}")
print(f"📍 Phase 2 Beats (gemma4)")
print("="*70)
t0 = time.time()
beats, et = call_m(MODEL, system, ref("beat_analysis.md") + f"\n\n## 输入\n```json\n{inp(story_text=story, story_dna=dna, director_intent=intent)}\n```\n\nJSON。", max_t=16384)
sj(PROJECT/"story_beats.json", beats)
bl = beats.get("beats",[])
total_dur = sum(b.get("duration_estimate",5) for b in bl)
dur_pct = int(total_dur/target*100)
ok = "✅" if total_dur >= target*0.9 else "⚠️"
print(f"✅ {et:.0f}s | {len(bl)} beats | {total_dur}s ({dur_pct}%) {ok}")
print(f"   目标: {target}s | 达成: {total_dur}s = {dur_pct}%")
for b in bl:
    kf = "⭐" if b.get("key_visual_moment") else "  "
    print(f"   {kf}{b.get('beat_id')}[{b.get('narrative_function','?')}|{b.get('duration_estimate')}s] {b.get('emotion','?')}")

print(f"\n{'='*70}")
print(f"📍 Phase 3 Characters (gemma4)")
print("="*70)
chars_in = inp(story_text=story, story_dna=dna, director_intent=intent)
chars, et = call_m(MODEL, system, ref("character_card.md") + f"\n\n## 输入\n```json\n{chars_in}\n```\n\nJSON。")
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
print(f"✅ Phase 3a {et:.0f}s + 3b {et2:.0f}s")
for c in chars.get("characters",[]):
    vnf = c.get("visual_narrative_function","")[:80]
    print(f"   {c.get('name')} [{c.get('role_level','')}] — {vnf}...")

# Check differentiation
cv_root = vis.get("appearance_generation", vis.get("character_visuals", vis.get("characters",[])))
for cv in cv_root:
    cname = cv.get("character_name", cv.get("name",""))
    apps = cv.get("appearances",[])
    if len(apps)>=2:
        d0 = (apps[0].get("description","") or (apps[0].get("descriptions",[""])[0] or ""))[:30]
        d1 = (apps[1].get("description","") or (apps[1].get("descriptions",[""])[0] or ""))[:30]
        diff = "✅不同" if d0!=d1 else "⚠️相同"
        print(f"   外观差异: {diff}")

print(f"\n{'='*70}")
print(f"📍 Phase 4 Cinematography (gemma4)")
print("="*70)
beats_min = {"beats":[{k:v for k,v in b.items() if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")} for b in bl]}

t0=time.time()
cs, _ = call_m(MODEL, system, ref("color_script.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, director_intent=intent, lookdev=ld)}\n```\n\nJSON。")
sj(PROJECT/"color_script.json", cs)
print(f"✅ Color Script {time.time()-t0:.0f}s | {cs.get('global_color_theme','')[:60]}...")

t0=time.time()
ph, _ = call_m(MODEL, system, ref("cinematography.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, color_script={'beats':cs.get('beats',[])}, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"photography.json", ph)
gs = ph.get("global_style",{})
print(f"✅ Photography {time.time()-t0:.0f}s | 风格={gs.get('imaging_style')} | 距离={gs.get('narrative_distance')}")
for s in ph.get("shots",[])[:4]:
    print(f"   {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:40]}...")

t0=time.time()
ac, _ = call_m(MODEL, system, ref("acting.md") + f"\n\n## 输入\n```json\n{inp(story_beats=beats_min, characters=chars_min, director_intent=intent)}\n```\n\nJSON。")
sj(PROJECT/"acting.json", ac)
print(f"✅ Acting {time.time()-t0:.0f}s")
for p in ac.get("panels",[])[:3]:
    print(f"   {p.get('beat_id')}: {p.get('performance_notes','')[:50]}...")

print(f"\n{'='*70}")
print(f"📍 Phase 4d 分镜组装")
print("="*70)

vis_map = {}
vis_root = vis.get("appearance_generation", vis.get("character_visuals", vis.get("characters",[])))
for cv in vis_root:
    cname = cv.get("character_name", cv.get("name",""))
    for app in cv.get("appearances",[]):
        aid = app.get("id", app.get("appearance_id",0))
        desc = app.get("description","") or (app.get("descriptions",[""])[0] or "")
        vis_map[(cname, aid)] = desc

beat_to_appearance = {}
char_first = {}
for c in chars.get("characters",[]):
    ea = c.get("expected_appearances",[])
    char_first[c["name"]] = ea[0].get("appearance_id",ea[0].get("id",0)) if ea else 0
    for item in ea:
        bid = item.get('beat_id','')
        if bid:
            beat_to_appearance.setdefault(bid,{})[c['name']] = item.get('appearance_id', item.get('id',0))

panels = []
for i, beat in enumerate(bl):
    bid = beat["beat_id"]
    shot = next((s for s in ph.get("shots",[]) if s.get("beat_id")==bid),{})
    act = next((a for a in ac.get("panels",[]) if a.get("beat_id")==bid),{})
    csb = next((c for c in cs.get("beats",[]) if c.get("beat_id")==bid),{})
    q6 = intent.get("q6_transition_philosophy","Mix")
    tr = {"硬切":"cut","Dissolve":"dissolve","Fade":"fade"}.get(q6, csb.get("transition_to_next","cut") or "cut")
    beat_chars = beat.get("characters",[])
    beat_app_map = beat_to_appearance.get(bid,{})
    pcp = []; pcn = []; appearance_refs = []; character_appearances = []
    if beat_chars:
        for cname in beat_chars:
            aid = beat_app_map.get(cname, char_first.get(cname,0))
            desc = vis_map.get((cname,aid),"")
            if desc:
                pcn.append(cname); pcp.append(desc[:200]); appearance_refs.append(f"{cname}(appearance_{aid})"); character_appearances.append({"name":cname,"appearance_id":aid})
    elif char_first:
        for cname, aid in char_first.items():
            desc = vis_map.get((cname,aid),"")
            if desc: pcn.append(cname); pcp.append(desc[:200]); appearance_refs.append(f"{cname}(appearance_{aid})"); character_appearances.append({"name":cname,"appearance_id":aid})
    aspect_ratio = ph.get("global_style", {}).get("aspect_ratio", "16:9") if isinstance(ph, dict) else "16:9"
    vlines = [
        f"{aspect_ratio}，横屏。",
        f"镜头：{shot.get('shot_type','中景')}，运镜方式：{shot.get('camera_movement','Static')}。",
    ]
    if appearance_refs:
        vlines.append(f"角色：{'、'.join(appearance_refs)}。")
    visual_hint = beat.get('visual_hint','')
    for prefix in ['特写：','近景：','中景：','全景：','远景：','快速蒙太奇：','慢动作：','摄影机','镜头']:
        if visual_hint.startswith(prefix):
            visual_hint = visual_hint[len(prefix):].strip()
    if visual_hint:
        vlines.append(f"画面内容：{visual_hint}。")
    if act.get('performance_notes',''):
        vlines.append(f"人物动作：{act.get('performance_notes','')}。")
    if shot.get('lighting',''):
        vlines.append(f"光线：{shot.get('lighting','')}。")
    if csb.get('dominant_color',''):
        vlines.append(f"整体画面色调：{csb.get('dominant_color','')}。")
    vprompt = "\n".join(vlines)
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
        "characters":pcn,"character_prompts":pcp,"character_appearances":character_appearances,"appearance_refs":appearance_refs,"video_prompt":vprompt,
        "key_visual_moment":beat.get("key_visual_moment",False),
        "directors_note":"","keyframes":[],"versions":[]
    })

sj(PROJECT/"panels.json",{"panels":panels})
total = sum(p["duration"] for p in panels)
print(f"✅ {len(panels)} panels | {total}s")
for p in panels:
    kf = "⭐" if p.get("key_visual_moment") else "  "
    print(f"   {kf}{p['panel_id']} | {p['beat_id']} | {p['shot_type']} | {p['camera_movement']} | {p['transition']} | chars={p.get('characters',[])}")

print(f"\n{'='*70}")
print("📊 gemma4 vs glm51 对比总结")
print("="*70)
print(f"Story: {len(story)}字 | 目标: {target}s")
print(f"Beats: {len(bl)} | 实际: {total_dur}s ({dur_pct}%)")
print(f"Panels: {len(panels)} | {total}s")
dur_ok = "✅" if total_dur >= target*0.9 else "⚠️ 不足"
print(f"时长达成: {dur_ok}")
print(f"\nPhase 质量对比:")
print(f"  Look Dev: glm51=89s | gemma4=?")
print(f"  Beats:    glm51=20 beats/180s(100%) | gemma4={len(bl)} beats/{total_dur}s({dur_pct}%)")

for fn in ["story_dna.json","lookdev.json","story_beats.json","characters.json",
           "character_visuals.json","color_script.json","photography.json","acting.json","panels.json"]:
    fp = PROJECT/fn
    print(f"   {'✅' if fp.exists() else '❌'} {fn}")
