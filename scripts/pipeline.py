#!/usr/bin/env python3
"""
Director Storyboard Pipeline — 完整专业版
5 Phase + 4 Gate + Look Development + 批注持久化
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from path_config import SKILL_DIR, PROJECTS_DIR
from gates import init_gate, wait_gate_response, resolve_gate_choice as resolve_gate_choice_core
from panel_assembler import assemble_panels as assemble_panels_core, infer_panel_intents as infer_panel_intents_core
from phase_runners import (
    phase1_story_dna as phase1_story_dna_core,
    phase2_beats as phase2_beats_core,
    phase3_characters as phase3_characters_core,
    step_phase4a_lookdev as step_phase4a_lookdev_core,
    step_phase4b_color_script as step_phase4b_color_script_core,
    step_phase4c_photography as step_phase4c_photography_core,
    step_phase4d_acting as step_phase4d_acting_core,
    step_phase4e_panels as step_phase4e_panels_core,
    phase5_output as phase5_output_core,
)
from cli_runner import build_parser, resolve_project_dir, run_full, run_single_phase
from state_store import (
    STEP_DEFS,
    STEP_INDEX,
    all_outputs_exist,
    bootstrap_run_state_from_outputs,
    fingerprint_diff,
    gather_fingerprint,
    gate_state_file,
    load_json,
    load_run_state,
    mark_step_done,
    mark_step_failed,
    mark_step_running,
    print_run_state_summary,
    reconcile_run_state,
    restart_from_step,
    save_json,
    save_run_state,
    should_skip_step,
    step_output_valid,
    update_review_status,
)

# ─── 工具函数 ────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def read_ref(name):
    with open(SKILL_DIR / "references" / name, encoding="utf-8") as f:
        return f.read()

# ─── Gate 协调 ──────────────────────────────────

def wait_for_gate(gate_name, project_dir, preview_file=None, preview_url=None, model="glm51"):
    """初始化 Gate 状态文件，外部确认链路后续可接入真实消息系统。"""
    return init_gate(project_dir, gate_name, preview_file=preview_file)

def check_gate_response(project_dir, gate_name, timeout_ms=300000):
    return wait_gate_response(project_dir, gate_name, timeout_ms=timeout_ms)

def resolve_gate_choice(project_dir, gate_name, choice, model):
    return resolve_gate_choice_core(project_dir, gate_name, choice, update_review_status)

# ─── Look Development ──────────────────────────────────────

def phase_lookdev(project_dir, model="glm51"):
    """
    Phase 1.5: Look Development（视觉基调确立）
    
    在 Color Script 之前，先确立：
    1. 视觉母题（Visual Motif）— 导演最核心的视觉关注点
    2. 参考图方向（可以是指令式描述，如"参考王家卫的抽帧色调"）
    3. 色调关键词（3-5个描述全片色彩感受的词）
    4. 摄影机哲学（镜头运动的核心风格）
    """
    update_progress(project_dir, "lookdev", "running")
    
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    
    system = "你是一个电影视觉风格设计师。只返回JSON。"
    user = read_ref("lookdev.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_dna': story_dna, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n输出JSON。"
    
    lookdev = run_llm("lookdev.md", {"story_dna": story_dna, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "lookdev.json", lookdev)
    
    update_progress(project_dir, "lookdev", "waiting_gate", "等待 Gate LD 确认")
    return "waiting_gate"

# ─── LLM 调用 ────────────────────────────────────────────

def run_llm(prompt_file, input_data, model="glm51", output_file=None,
              validation=None, max_retries=3):
    """
    调用 LLM via call_model.py，支持验证和重试
    
    validation: dict, 可选，期望的验证规则
      - type: "array" | "object"
      - key: 期望的数组键名 (如 beats, panels)
      - min_items: 数组最小长度
      - expected_count: 期望的精确数组长度
    """
    # 直接使用 call_model.py 的 call_with_retry（避免子进程开销）
    from call_model import call_with_retry
    
    prompt_path = SKILL_DIR / "references" / prompt_file
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()
    
    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    full_prompt = template + f"\n\n## 输入数据\n```json\n{input_json}\n```\n\n请输出 JSON。"
    
    out_file = output_file or "/tmp/llm_output.json"
    
    # 获取模型的最大 token 限制
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent / "ai-storyboard-pro" / "scripts"))
    from config import MODELS
    model_cfg = MODELS.get(model, {})
    model_max_tokens = model_cfg.get("max_tokens")
    if model_max_tokens is None:
        model_max_tokens = model_cfg.get("extra_body", {}).get("max_tokens")
    if model_max_tokens is None:
        model_max_tokens = 16384
    
    try:
        data = call_with_retry(
            model=model,
            system="你是专业AI助手。只返回JSON，不要其他文字。",
            prompt=full_prompt,
            validation=validation,
            max_retries=max_retries,
            max_tokens=model_max_tokens,
            output_file=out_file
        )
        return data
    except Exception as e:
        print(f"❌ run_llm 失败: {e}", file=sys.stderr)
        raise

# ─── 进度追踪 ────────────────────────────────────────────

def update_progress(project_dir, phase, status, message=""):
    progress_file = Path(project_dir) / "pipeline_progress.json"
    if progress_file.exists():
        progress = load_json(progress_file)
    else:
        progress = {"phases": {}, "created": str(datetime.now())}
    
    progress["phases"][phase] = {
        "status": status,
        "message": message,
        "timestamp": str(datetime.now())
    }
    save_json(progress_file, progress)

# ─── 预览生成 ────────────────────────────────────────────

def generate_beats_viewer(project_dir):
    project_dir = Path(project_dir)
    story_beats = load_json(project_dir / "story_beats.json")
    story_dna = load_json(project_dir / "story_dna.json")
    
    beats = story_beats.get("beats", [])
    dna = story_dna.get("narrative_functions", {})
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Beat 审核 — {project_dir.name}</title>
<style>
body{{font-family:system-ui;max-width:900px;margin:0 auto;padding:20px}}
.beat{{border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}}
.beat-header{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.beat_id{{font-weight:bold;color:#7c3aed}}
.act{{padding:2px 8px;border-radius:4px;font-size:12px}}
.act_1{{background:#dbeafe}}
.act_2{{background:#fef9c3}}
.act_3{{background:#fee2e2}}
.duration{{color:#6b7280;font-size:14px;margin-left:auto}}
.content{{background:#f9fafb;padding:10px;border-radius:4px;margin:8px 0;font-size:14px}}
.vh{{color:#374151;font-style:italic;font-size:13px;margin:6px 0}}
.vo{{color:#2563eb;font-size:13px;margin:4px 0}}
.dna-box{{background:#f0f9ff;padding:16px;border-radius:8px;margin-bottom:20px;border:1px solid #bfdbfe}}
.key{{font-weight:bold;color:#1d4ed8}}
</style></head><body>
<h1>🎬 Beat 方案审核 — Gate 0</h1>
<div class="dna-box">
<h2>Story DNA</h2>
<p><span class="key">三幕结构</span>: 
Act1→{story_dna['three_act_structure']['act_1_end_beat']} | 
TP1→{story_dna['three_act_structure']['turning_point_1']} | 
TP2→{story_dna['three_act_structure']['turning_point_2']} | 
Act3←{story_dna['three_act_structure']['act_3_start_beat']}</p>
<p><span class="key">情感高潮</span>: {story_dna.get('emotional_climax', 'N/A')}</p>
<p><span class="key">结构摘要</span>: {story_dna.get('structure_summary', '')}</p>
</div>
<h2>Beats ({len(beats)}个 | 估算 {sum(b.get('duration_estimate',5) for b in beats)}s)</h2>
"""
    for b in beats:
        fn = dna.get(b.get('beat_id',''), {})
        act = b.get('three_act_position', 'act_1')
        html += f"""
<div class="beat">
  <div class="beat-header">
    <span class="beat_id">{b.get('beat_id','')}</span>
    <span class="act act_{act.replace('act_','')}">{b.get('narrative_function','')} | {fn.get('function','')}</span>
    <span class="duration">⏱{b.get('duration_estimate',5)}s</span>
    {"⭐" if b.get('key_visual_moment') else ""}
  </div>
  <div class="content">{b.get('content','')[:100]}...</div>
  <div class="vh">💡 {b.get('scene','')} | {b.get('emotion','')}</div>
  <div class="vh">🎥 {b.get('visual_hint','')[:100]}...</div>
  {f"<div class='vo'>🎤 {b.get('voiceover','')[:80]}... <small>({b.get('voiceover_perspective','')})</small></div>" if b.get('voiceover') else ""}
</div>
"""
    html += "</body></html>"
    
    out = Path(project_dir) / "beats-viewer.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ beats-viewer.html: {out}")
    return out

def generate_character_viewer(project_dir):
    chars = load_json(Path(project_dir) / "characters.json")
    char_vis = load_json(Path(project_dir) / "character_visuals.json")
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>角色审核 — Gate 1</title>
<style>
body{{font-family:system-ui;max-width:900px;margin:0 auto;padding:20px}}
.char{{border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0}}
.char-header{{display:flex;align-items:center;gap:12px}}
.name{{font-size:20px;font-weight:bold}}
.level{{padding:2px 8px;border-radius:4px;font-size:12px}}
.level_S{{background:#fef08a}}
.level_A{{background:#d9f99d}}
.level_B{{background:#bfdbfe}}
.level_C{{background:#e5e7eb}}
.sec{{margin:8px 0}}
.label{{font-weight:bold;color:#6b7280;font-size:12px}}
.intro{{color:#374151}}
.vnf{{color:#7c3aed;font-size:13px}}
.dvp{{color:#2563eb;font-style:italic;font-size:13px}}
.desc{{background:#f9fafb;padding:8px;border-radius:4px;font-size:13px}}
</style></head><body>
<h1>🎭 角色档案审核 — Gate 1</h1>
"""
    for c in chars.get("characters", []):
        lvl = c.get("role_level", "C")
        vnf = c.get("visual_narrative_function", "").replace("\n", "<br>")
        dvp = c.get("director_visual_priority", "")
        html += f"""
<div class="char">
  <div class="char-header">
    <span class="name">{c.get('name','')}</span>
    <span class="level level_{lvl}">{lvl}级</span>
    <span style="color:#6b7280">{c.get('gender','')} | {c.get('age_range','')} | {c.get('occupation','')}</span>
  </div>
  <div class="sec">
    <div class="label">身份介绍</div>
    <div class="intro">{c.get('introduction','')}</div>
  </div>
  <div class="sec">
    <div class="label">视觉叙事功能</div>
    <div class="vnf">{vnf}</div>
  </div>
  <div class="sec">
    <div class="label">导演视觉优先级</div>
    <div class="dvp">{dvp}</div>
  </div>
</div>
"""
    html += "</body></html>"
    out = Path(project_dir) / "character-viewer.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ character-viewer.html: {out}")
    return out

def generate_storyboard_viewer(project_dir):
    """生成带批注系统的导演工作台 HTML（调用 generate_viewer.py）"""
    import subprocess
    project_dir = str(Path(project_dir).resolve())
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "generate_viewer.py"), project_dir],
        capture_output=True, text=True, timeout=30,
        cwd=str(SKILL_DIR)
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"⚠️  viewer 生成失败: {result.stderr[:200]}")
    return Path(project_dir) / "viewer.html"

# ─── Phase 核心 ──────────────────────────────────────────

def phase0_intent_capture(project_dir, story_file):
    """Phase 0: 创建 story.txt，等待意图问卷完成"""
    mark_step_running(project_dir, "phase0_input", [])
    update_progress(project_dir, "phase0", "running")
    with open(story_file, encoding="utf-8") as f:
        story_text = f.read()
    dest = Path(project_dir) / "story.txt"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(story_text)
    
    intent_file = Path(project_dir) / "director_intent.json"
    if not intent_file.exists():
        update_progress(project_dir, "phase0", "waiting_intent")
        mark_step_done(project_dir, "phase0_input")
        return "waiting_intent"
    
    intent = load_json(intent_file)
    update_progress(project_dir, "phase0", "done")
    mark_step_done(project_dir, "phase0_input")
    return "done"

def phase1_story_dna(project_dir, model="glm51"):
    """Phase 1: Story DNA 分析"""
    return phase1_story_dna_core(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, model=model)

def phase2_beats(project_dir, model="glm51"):
    """Phase 2: Beat 结构规划 + Visual Hint 独立生成"""
    return phase2_beats_core(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, generate_beats_viewer, model=model)

def phase3_characters(project_dir, model="glm51"):
    """Phase 3: 角色档案 + 角色视觉"""
    return phase3_characters_core(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, generate_character_viewer, model=model)

def step_phase4a_lookdev(project_dir, model="glm51"):
    return step_phase4a_lookdev_core(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, update_progress, model=model)

def step_phase4b_color_script(project_dir, model="glm51"):
    return step_phase4b_color_script_core(project_dir, run_llm, load_json, save_json, mark_step_running, mark_step_done, model=model)

def step_phase4c_photography(project_dir, beats, intent, model="glm51"):
    return step_phase4c_photography_core(project_dir, beats, intent, run_llm, load_json, save_json, mark_step_running, mark_step_done, model=model)

def step_phase4d_acting(project_dir, beats, intent, model="glm51"):
    return step_phase4d_acting_core(project_dir, beats, intent, run_llm, load_json, save_json, mark_step_running, mark_step_done, model=model)

def step_phase4e_panels(project_dir, model="glm51"):
    return step_phase4e_panels_core(project_dir, assemble_panels, save_json, mark_step_running, mark_step_done, update_progress, generate_storyboard_viewer, model=model)

def phase4_cinematography(project_dir, model="glm51", resume=False):
    """Phase 4: Look Development → Color Script → Photography → Acting → 分镜组装"""
    update_progress(project_dir, "phase4", "running")

    if not should_skip_step(project_dir, "phase4a_lookdev", resume):
        step_phase4a_lookdev(project_dir, model=model)
    else:
        print("  [skip 4a] Look Development")

    if not should_skip_step(project_dir, "phase4b_color_script", resume):
        beats, intent, _ = step_phase4b_color_script(project_dir, model=model)
    else:
        print("  [skip 4b] Color Script")
        beats = load_json(Path(project_dir) / "story_beats.json")
        intent = load_json(Path(project_dir) / "director_intent.json")

    if not should_skip_step(project_dir, "phase4c_photography", resume):
        step_phase4c_photography(project_dir, beats, intent, model=model)
    else:
        print("  [skip 4c] Photography")

    if not should_skip_step(project_dir, "phase4d_acting", resume):
        step_phase4d_acting(project_dir, beats, intent, model=model)
    else:
        print("  [skip 4d] Acting")

    if not should_skip_step(project_dir, "phase4e_panels", resume):
        return step_phase4e_panels(project_dir, model=model)

    print("  [skip 4e] 分镜组装")
    update_progress(project_dir, "phase4", "done")
    return "done"

def infer_panel_intents(project_dir, beats, chars, photo, acting, cs, intent, model="glm51"):
    return infer_panel_intents_core(project_dir, beats, chars, photo, acting, cs, intent, run_llm=run_llm, model=model)


def assemble_panels(project_dir, model="glm51"):
    """Phase 4e: 组装 panels.json"""
    return assemble_panels_core(project_dir, run_llm=run_llm, model=model)

def phase5_output(project_dir):
    """Phase 5: 成片输出（主要是 viewer.html）"""
    return phase5_output_core(project_dir, mark_step_running, mark_step_done, update_progress, generate_storyboard_viewer)

# ─── 局部修改 ────────────────────────────────────────────

def patch_beats(project_dir, instruction, model="glm51"):
    """
    根据导演指令局部修改 beats。
    instruction 格式如：'B05+B06 merged' / 'B03 duration→8s' / 'B07 key_visual=true'
    """
    beats = load_json(Path(project_dir) / "story_beats.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    
    # 验证：beats 数组必须非空
    patch_validation = {"type": "object", "key": "beats", "min_items": 1}
    patched = run_llm("patch_beats.md", {
        "instruction": instruction,
        "story_beats": beats,
        "director_intent": intent
    }, model=model, validation=patch_validation, max_retries=3)
    
    save_json(Path(project_dir) / "story_beats.json", patched)
    
    # 重新组装 panels（因为 beats 可能变了）
    panels = assemble_panels(project_dir)
    save_json(Path(project_dir) / "panels.json", panels)
    
    generate_beats_viewer(project_dir)
    generate_storyboard_viewer(project_dir)
    print(f"✅ patch 完成: {instruction}")
    return patched

# ─── 主入口 ──────────────────────────────────────────────

def run_step(step_key, fn, project_dir, *args, **kwargs):
    try:
        return fn(project_dir, *args, **kwargs)
    except Exception as e:
        if step_key:
            mark_step_failed(project_dir, step_key, e)
        raise

def process_gate(project_dir, gate_name, preview_file, confirm=False):
    wait_for_gate(gate_name, project_dir, preview_file)
    print(f"⏸ {gate_name} 等待确认")
    if confirm:
        print(f"  [skip] {gate_name} 确认跳过（--confirm）")
        gate_map = {"Gate 0": "phase2_beats", "Gate 1": "phase3_characters", "Gate 2": "phase4e_panels"}
        if gate_name in gate_map:
            update_review_status(project_dir, gate_map[gate_name], "approved")
        return "continue"
    choice = check_gate_response(project_dir, gate_name)
    return resolve_gate_choice(project_dir, gate_name, choice, None)

def main():
    parser = build_parser(STEP_DEFS)
    args = parser.parse_args()

    if not args.model and args.phase != "patch":
        parser.error("必须显式传 --model，例如 --model glm51")

    project_dir = resolve_project_dir(args.project, PROJECTS_DIR)
    ensure_dir(project_dir)
    reconcile_run_state(project_dir)
    bootstrap_run_state_from_outputs(project_dir)
    print_run_state_summary(project_dir)
    if args.restart_from:
        restart_from_step(project_dir, args.restart_from)

    if args.phase == "patch" and args.patch:
        print(f"🔧 局部修改: {args.patch}")
        patch_beats(project_dir, args.patch, model=args.model)
        print("✅ 修改完成")
        return

    if args.phase == "full":
        run_full(
            args,
            project_dir,
            should_skip_step,
            run_step,
            process_gate,
            phase0_intent_capture,
            phase1_story_dna,
            phase2_beats,
            phase3_characters,
            phase4_cinematography,
            phase5_output,
            load_run_state,
            save_run_state,
            print_run_state_summary,
        )
        return

    run_single_phase(
        args,
        project_dir,
        should_skip_step,
        run_step,
        phase0_intent_capture,
        phase1_story_dna,
        phase2_beats,
        phase3_characters,
        phase4_cinematography,
        phase5_output,
        phase_lookdev,
    )

if __name__ == "__main__":
    main()
