#!/usr/bin/env python3
"""完整专业测试：逐 Phase 跑 pipeline，评估每个环节"""
import sys, json, re, os, time, importlib.util
from pathlib import Path

AI_SCRIPTS = "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts"
DS_SCRIPTS = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/scripts"
if AI_SCRIPTS not in sys.path:
    sys.path.insert(0, AI_SCRIPTS)
if DS_SCRIPTS not in sys.path:
    sys.path.insert(0, DS_SCRIPTS)

from api import call_api

# force director-storyboard's pipeline.py, avoid path collision
pipeline_path = f"{DS_SCRIPTS}/pipeline.py"
pipeline_spec = importlib.util.spec_from_file_location("director_storyboard_pipeline_main", pipeline_path)
pipeline_main = importlib.util.module_from_spec(pipeline_spec)
pipeline_spec.loader.exec_module(pipeline_main)
should_skip_step = pipeline_main.should_skip_step
mark_step_running = pipeline_main.mark_step_running
mark_step_done = pipeline_main.mark_step_done
mark_step_failed = pipeline_main.mark_step_failed
reconcile_run_state = pipeline_main.reconcile_run_state
restart_from_step = pipeline_main.restart_from_step
generate_beats_viewer = pipeline_main.generate_beats_viewer
generate_character_viewer = pipeline_main.generate_character_viewer

# force director-storyboard's call_model.py, avoid path collision
call_model_path = f"{DS_SCRIPTS}/call_model.py"
spec = importlib.util.spec_from_file_location("director_storyboard_call_model", call_model_path)
call_model_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(call_model_mod)
extract_json = call_model_mod.extract_json

DEFAULT_PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-emotional-monologue"
DEFAULT_MODEL = "gemma4"
SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
os.chdir(SKILL_DIR)

PROJECT = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT
MODEL = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
PROJECT = str(Path(PROJECT))
PROJECT_NAME = Path(PROJECT).name
reconcile_run_state(PROJECT)

def load_json(path):
    with open(path) as f: return json.load(f)
def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)
def read_ref(name):
    with open(f"references/{name}") as f: return f.read()

def run_test_step(step_key, fn):
    try:
        return fn()
    except Exception as e:
        mark_step_failed(PROJECT, step_key, e)
        raise

def call_m(model, system, user, max_tokens=8192):
    if model in ("gpt5.4", "openai-codex/gpt-5.4"):
        import subprocess
        prompt = f"{system}\n\n{user}"
        cmd = [
            "openclaw", "infer", "model", "run",
            "--prompt", prompt,
            "--model", "openai-codex/gpt-5.4",
            "--json"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"infer 调用失败: {proc.stderr[:500]}")
        infer_raw = proc.stdout
        try:
            infer_obj = json.loads(infer_raw)
            outputs = infer_obj.get("outputs", [])
            text = "\n".join(o.get("text", "") for o in outputs if isinstance(o, dict) and o.get("text"))
        except Exception:
            text = infer_raw
    else:
        result = call_api(model, system, user, max_tokens=max_tokens)
        text = result[0] if isinstance(result, tuple) else result
    try:
        return extract_json(text)
    except Exception as e:
        safe_model = model.replace("/", "_")
        debug_path = f"/tmp/test_full_pipeline_debug_{safe_model}_{int(time.time())}.txt"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[DEBUG] raw response saved: {debug_path}")
        print(f"[DEBUG]\n{text[:800]}")
        raise ValueError(f"JSON解析失败: {e}")

system = "你是专业AI助手。只返回JSON，不要其他文字。"

def phase_label(n):
    labels = {"0":"Phase 0 意图捕获","1":"Phase 1 Story DNA","1.5":"Phase 1.5 Look Dev",
               "2":"Phase 2 Beats","3":"Phase 3 角色","4a":"Phase 4a Color","4b":"Phase 4b Photo",
               "4c":"Phase 4c Acting","4d":"Phase 4d 组装","5":"Phase 5 Viewer"}
    return labels.get(n, n)

print("=" * 70)
print(f"🎬 专业测试开始：{PROJECT_NAME}")
print("=" * 70)

# ── Phase 1: Story DNA ──────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('1')}")
print(f"{'─'*70}")
story = open(f"{PROJECT}/story.txt").read()
intent = load_json(f"{PROJECT}/director_intent.json")
print(f"Story: {len(story)}字 | 时长目标: {intent['duration_target']}")

if should_skip_step(PROJECT, "phase1_story_dna", True, True):
    print("⏭ Phase 1 Story DNA（resume）")
    dna = load_json(f"{PROJECT}/story_dna.json")
else:
    def _phase1():
        mark_step_running(PROJECT, "phase1_story_dna", ["story.txt", "director_intent.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        dna = call_m(MODEL, system, read_ref("story_dna.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/story_dna.json", dna)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase1_story_dna")
        return dna
    dna = run_test_step("phase1_story_dna", _phase1)

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

if should_skip_step(PROJECT, "phase4a_lookdev", True, True):
    print("⏭ Phase 1.5 Look Dev（resume）")
    ld = load_json(f"{PROJECT}/lookdev.json")
else:
    def _phase15():
        mark_step_running(PROJECT, "phase4a_lookdev", ["story_dna.json", "director_intent.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        ld = call_m(MODEL, system, read_ref("lookdev.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/lookdev.json", ld)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase4a_lookdev")
        return ld
    ld = run_test_step("phase4a_lookdev", _phase15)

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

if should_skip_step(PROJECT, "phase2_beats", True, True):
    print("⏭ Phase 2 Beats（resume）")
    beats = load_json(f"{PROJECT}/story_beats.json")
else:
    def _phase2():
        mark_step_running(PROJECT, "phase2_beats", ["story.txt", "director_intent.json", "story_dna.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        beats = call_m(MODEL, system, read_ref("beat_analysis.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        if intent.get("q5b_voiceover_rewrite") == "preserve_original":
            for beat in beats.get("beats", []):
                beat["voiceover"] = beat.get("content", "")
        elif intent.get("q5_voiceover_type", "").startswith("C"):
            for beat in beats.get("beats", []):
                beat["voiceover"] = ""
        visual_input = {
            "story_text": story,
            "director_intent": intent,
            "story_dna": dna,
            "beats": [
                {k: v for k, v in beat.items() if k not in ("scene", "visual_hint")}
                for beat in beats.get("beats", [])
            ]
        }
        visuals = call_m(MODEL, system, read_ref("visual_hint_generation.md") + f"\n\n## 输入\n```json\n{json.dumps(visual_input,ensure_ascii=False)}\n```\n\nJSON。")
        visual_map = {b.get("beat_id"): b for b in visuals.get("beats", [])}
        for beat in beats.get("beats", []):
            vb = visual_map.get(beat.get("beat_id"), {})
            if vb.get("scene"):
                beat["scene"] = vb["scene"]
            if vb.get("visual_hint"):
                beat["visual_hint"] = vb["visual_hint"]
        save_json(f"{PROJECT}/story_beats.json", beats)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase2_beats")
        return beats
    beats = run_test_step("phase2_beats", _phase2)

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

if should_skip_step(PROJECT, "phase3_characters", True, True):
    print("⏭ Phase 3 Characters（resume）")
    chars = load_json(f"{PROJECT}/characters.json")
    vis = load_json(f"{PROJECT}/character_visuals.json")
else:
    def _phase3():
        mark_step_running(PROJECT, "phase3_characters", ["story.txt", "director_intent.json", "story_dna.json"])
        print(f"⏳ Phase 3a ({MODEL})...", end=" ", flush=True)
        t0 = time.time()
        chars = call_m(MODEL, system, read_ref("character_card.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_text':story,'story_dna':dna,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/characters.json", chars)
        print(f"✅ {time.time()-t0:.0f}s")

        print(f"⏳ Phase 3b ({MODEL})...", end=" ", flush=True)
        t0 = time.time()
        vis = call_m(MODEL, system, read_ref("character_visual.md") + f"\n\n## 输入\n```json\n{json.dumps({'characters':chars,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/character_visuals.json", vis)
        generate_character_viewer(PROJECT)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase3_characters")
        return chars, vis
    chars, vis = run_test_step("phase3_characters", _phase3)

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
if should_skip_step(PROJECT, "phase4b_color_script", True, True):
    print("⏭ Phase 4a Color Script（resume）")
    cs = load_json(f"{PROJECT}/color_script.json")
else:
    def _phase4b():
        mark_step_running(PROJECT, "phase4b_color_script", ["story_beats.json", "director_intent.json", "lookdev.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        cs = call_m(MODEL, system, read_ref("color_script.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'director_intent':intent,'lookdev':ld},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/color_script.json", cs)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase4b_color_script")
        return cs
    cs = run_test_step("phase4b_color_script", _phase4b)
print(f"  全局: {cs.get('global_color_theme','')[:80]}...")
for b in cs.get("beats",[])[:3]:
    print(f"  {b.get('beat_id')}: {b.get('dominant_color')} → {b.get('transition_to_next','')[:40]}")

print(f"\n{'─'*70}")
print(f"📍 {phase_label('4b')} Photography")
print(f"{'─'*70}")

if should_skip_step(PROJECT, "phase4c_photography", True, True):
    print("⏭ Phase 4b Photography（resume）")
    photo = load_json(f"{PROJECT}/photography.json")
else:
    def _phase4c():
        mark_step_running(PROJECT, "phase4c_photography", ["story_beats.json", "color_script.json", "director_intent.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        photo = call_m(MODEL, system, read_ref("cinematography.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'color_script':{'beats':cs.get('beats',[])},'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/photography.json", photo)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase4c_photography")
        return photo
    photo = run_test_step("phase4c_photography", _phase4c)
gs = photo.get("global_style",{})
print(f"  风格={gs.get('imaging_style')} | 叙事距离={gs.get('narrative_distance')} | 过渡={gs.get('transition_philosophy')}")
for s in photo.get("shots",[])[:4]:
    print(f"  {s.get('beat_id')}: {s.get('shot_type')} | {s.get('camera_movement')} | {s.get('lighting','')[:40]}...")

print(f"\n{'─'*70}")
print(f"📍 {phase_label('4c')} Acting")
print(f"{'─'*70}")

chars_min = {"characters":[{k:v for k,v in c.items() if k in ("name","aliases","personality_tags","role_level")} for c in chars.get("characters",[])]}
if should_skip_step(PROJECT, "phase4d_acting", True, True):
    print("⏭ Phase 4c Acting（resume）")
    acting = load_json(f"{PROJECT}/acting.json")
else:
    def _phase4d():
        mark_step_running(PROJECT, "phase4d_acting", ["story_beats.json", "characters.json", "director_intent.json"])
        print(f"⏳ {MODEL}...", end=" ", flush=True)
        t0 = time.time()
        acting = call_m(MODEL, system, read_ref("acting.md") + f"\n\n## 输入\n```json\n{json.dumps({'story_beats':beats_min,'characters':chars_min,'director_intent':intent},ensure_ascii=False)}\n```\n\nJSON。")
        save_json(f"{PROJECT}/acting.json", acting)
        print(f"✅ {time.time()-t0:.0f}s")
        mark_step_done(PROJECT, "phase4d_acting")
        return acting
    acting = run_test_step("phase4d_acting", _phase4d)
for p in acting.get("panels",[])[:3]:
    print(f"  {p.get('beat_id')}: {p.get('performance_notes','')[:50]}...")
    print(f"    潜: {p.get('emotional_subtext','')[:60]}...")
    print(f"    导演: {p.get('performance_directive','')[:60]}...")

# ── Phase 4d: Assembly ───────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('4d')} 分镜组装")
print(f"{'─'*70}")

pipeline_path = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/scripts/pipeline.py"
spec = importlib.util.spec_from_file_location("director_storyboard_pipeline", pipeline_path)
pipeline_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline_mod)
if should_skip_step(PROJECT, "phase4e_panels", True, True):
    print("⏭ Phase 4d Assembly（resume）")
    panels = load_json(f"{PROJECT}/panels.json")
else:
    def _phase4e():
        mark_step_running(PROJECT, "phase4e_panels", ["story_beats.json", "character_visuals.json", "color_script.json", "photography.json", "acting.json"])
        panels = pipeline_mod.assemble_panels(PROJECT)
        save_json(f"{PROJECT}/panels.json", panels)
        pipeline_mod.generate_storyboard_viewer(PROJECT)
        mark_step_done(PROJECT, "phase4e_panels")
        return panels
    panels = run_test_step("phase4e_panels", _phase4e)
print(f"  ✅ {len(panels['panels'])} panels | 总时长: {sum(p['duration'] for p in panels['panels'])}s")
for p in panels["panels"][:3]:
    print(f"  {p['panel_id']} | {p['beat_id']} | {p['shot_type']} | {p['camera_movement']} | {p['transition']}")
    print(f"    {p['video_prompt'][:60]}...")

# ── Phase 5: Viewer ─────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 {phase_label('5')} Viewer")
print(f"{'─'*70}")
if should_skip_step(PROJECT, "phase5_output", True, True):
    print("⏭ Phase 5 Viewer（resume）")
else:
    mark_step_running(PROJECT, "phase5_output", ["panels.json"])
    pipeline_mod.generate_storyboard_viewer(PROJECT)
    mark_step_done(PROJECT, "phase5_output")
    print(f"  ✅ viewer.html 生成完成")

# ── Keyframe Generation ──────────────────────────────────────────────────
print(f"\n{'─'*70}")
print(f"📍 Phase 4e: 关键帧 Image Prompt 生成")
print(f"{'─'*70}")
print(f"⏳ {MODEL} (分2批)...", end=" ", flush=True)
t0 = time.time()

def gen_kf(panels_batch):
    user = read_ref("keyframe_gen.md") + f"\n\n## 输入\n```json\n{json.dumps({'panels':panels_batch},ensure_ascii=False)}\n```\n\nJSON。"
    return call_m(MODEL, system, user)

char_vis = load_json(f"{PROJECT}/character_visuals.json")
chars_vis_map = {}
for cv in char_vis.get("character_visuals", []):
    cname = cv.get("name", "")
    chars_vis_map[cname] = {}
    for app in cv.get("appearances", []):
        aid = app.get("id", app.get("appearance_id", 0))
        descs = app.get("descriptions", [])
        full = descs[0] if descs else ""
        chars_vis_map[cname][aid] = {
            "full": full,
            "core": app.get("core_look", "") or full,
            "state_variant": app.get("state_variant", "") or ""
        }

panel_contexts = []
for p in panels["panels"]:
    cam = p.get("camera_movement","Static")
    fc = 1 if cam in ("Static",) or p.get("shot_type","") in ("特写","极端特写") else (3 if cam=="Orbit" else 2)
    core_looks = []
    state_variants = []
    for item in p.get("character_appearances", []):
        cname = item.get("name", "")
        aid = item.get("appearance_id", 0)
        vis = chars_vis_map.get(cname, {}).get(aid, {})
        if vis.get("core"):
            core_looks.append(f"{cname}(appearance_{aid}): {vis['core']}")
        if vis.get("state_variant"):
            state_variants.append(f"{cname}(appearance_{aid}): {vis['state_variant']}")
    panel_contexts.append({
        "panel_id": p["panel_id"], "beat_id": p["beat_id"],
        "shot_type": p.get("shot_type","中景"), "camera_movement": cam,
        "frame_count": fc, "scene_description": p.get("scene_description",""),
        "performance_notes": p.get("performance_notes",""),
        "freeze_action": p.get("freeze_action", ""),
        "body_tension": p.get("body_tension", ""),
        "energy_state": p.get("energy_state", ""),
        "visual_task": p.get("visual_task", ""),
        "frame_priority": p.get("frame_priority", ""),
        "facial_expression": p.get("facial_expression","N/A"),
        "lighting": p.get("lighting",""), "dominant_color": p.get("dominant_color",""),
        "color_temperature": p.get("color_temperature",5500),
        "duration": p.get("duration",5),
        "key_visual_moment": p.get("key_visual_moment",False),
        "character_prompts": "\n".join(p.get("character_prompts",[])) or "无角色",
        "character_core_looks": "\n".join(core_looks) or "无稳定外观描述",
        "character_state_variants": "\n".join(state_variants) or "无版本差异说明",
        "appearance_refs": "、".join(p.get("appearance_refs", [])) if p.get("appearance_refs") else "未指定appearance"
    })

all_kf = {}
for i in range(0, len(panel_contexts), 3):
    batch = panel_contexts[i:i+3]
    r = gen_kf(batch)
    if isinstance(r, dict):
        if "keyframes" in r and isinstance(r["keyframes"], dict):
            r = r["keyframes"]
        for k, v in r.items():
            if str(k).startswith("P"):
                all_kf[k] = v
    elif isinstance(r,list):
        for item in r:
            if isinstance(item,dict):
                for k,v in item.items():
                    if str(k).startswith("P"):
                        all_kf[k]=v

with open(f"{PROJECT}/keyframes.json", "w") as f:
    json.dump({"keyframes": all_kf}, f, ensure_ascii=False, indent=2)

# Update panels.json with keyframes
for p in panels["panels"]:
    pid = p["panel_id"]
    if pid in all_kf:
        v = all_kf[pid]
        if isinstance(v, dict):
            if "keyframes" in v:
                p["keyframes"] = v["keyframes"]
            elif "frames" in v:
                p["keyframes"] = v["frames"]
            else:
                p["keyframes"] = []
        else:
            p["keyframes"] = []
save_json(f"{PROJECT}/panels.json", panels)
print(f"✅ {time.time()-t0:.0f}s | {len(all_kf)} panels keyframes")

# Regenerate viewer after keyframes are written back
pipeline_mod.generate_storyboard_viewer(PROJECT)
print("  ✅ viewer.html 已在 keyframes 写回后刷新")

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
print(f"模型: {MODEL}")
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
