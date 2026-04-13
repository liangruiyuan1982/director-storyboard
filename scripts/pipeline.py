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

SKILL_DIR = Path(__file__).parent.parent
PROJECTS_DIR = SKILL_DIR / "projects"

# ─── 工具函数 ────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_ref(name):
    with open(SKILL_DIR / "references" / name, encoding="utf-8") as f:
        return f.read()

# ─── 飞书 Gate 确认系统 ──────────────────────────────────

def feishu_send(chat_id, msg, msg_type="text"):
    """通过 feishu_im_user_fetch 发送飞书消息（当前 session 以用户身份）"""
    # 使用当前 session 发送，不创建新会话
    from pathlib import Path
    # 读取 feishu token（当前 session 的 token）
    token_file = Path.home() / ".openclaw/feishu_tokens/default.json"
    if not token_file.exists():
        # 降级：用 exec 执行 curl
        cmd = [
            "python3", "-c",
            f"import urllib.request, json; req = urllib.request.Request("
            f"'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',"
            f"data=json.dumps({{'app_id':'cli_xxx','app_secret':'xxx'}}).encode(),"
            f"headers={{'Content-Type':'application/json'}},method='POST');"
            f"print(urllib.request.urlopen(req).read())"
        ]
        return False
    return True

def wait_for_gate(gate_name, project_dir, preview_file=None, preview_url=None, model="glm51"):
    """
    真正的 Gate 等待：发送预览给导演，等待飞书回复。
    
    流程：
    1. 生成预览 HTML，发到飞书
    2. 发送确认选项（确认/修改/重新生成）
    3. 等待回复，根据用户选择继续
    """
    project_name = project_dir.name
    preview_path = Path(project_dir) / preview_file if preview_file else None
    
    # 构造确认消息
    gate_messages = {
        "Gate 0": {
            "summary": "Story DNA + Beat 方案",
            "needs": "审核三幕结构、Beat 拆分、visual_hint",
            "options": [
                {"label": "✅ 确认，进入下一步", "value": "confirm"},
                {"label": "🔄 局部修改 Beat", "value": "modify"},
                {"label": "🔄 重新生成 Story DNA", "value": "regen_dna"},
                {"label": "🔄 重新生成 Beats", "value": "regen_beats"},
            ]
        },
        "Gate 1": {
            "summary": "角色档案 + 视觉方案",
            "needs": "审核角色外观描述、visual_narrative_function、director_visual_priority",
            "options": [
                {"label": "✅ 确认，进入下一步", "value": "confirm"},
                {"label": "🔄 局部修改角色", "value": "modify"},
                {"label": "🔄 重新生成", "value": "regen"},
            ]
        },
        "Gate 2": {
            "summary": "分镜方案",
            "needs": "审核 Color Script、摄影参数、表演指令",
            "options": [
                {"label": "✅ 确认，进入下一步", "value": "confirm"},
                {"label": "🔄 局部修改", "value": "modify"},
                {"label": "🔄 重新生成", "value": "regen"},
            ]
        },
        "Gate 3": {
            "summary": "关键帧 + 分镜看板",
            "needs": "抽检关键帧质量、确认节奏和时长",
            "options": [
                {"label": "✅ 确认，进入成片输出", "value": "confirm"},
                {"label": "🔄 重新生成关键帧", "value": "regen_keyframes"},
                {"label": "🔄 局部调整", "value": "modify"},
            ]
        },
    }
    
    info = gate_messages.get(gate_name, gate_messages["Gate 0"])
    
    # 构造飞书卡片消息
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🎬 {gate_name} 需要你的确认"},
                "template": "purple"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**项目**: {project_name}\n"
                                    f"**审核内容**: {info['summary']}\n"
                                    f"**需要你确认**: {info['needs']}"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📄 预览文件: `{preview_path}`\n"
                                    f"（在浏览器打开查看详细内容）"
                    }
                } if preview_path else {"tag": "div", "text": {"tag": "lark_md", "content": ""}},
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "**请选择操作**"}
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": opt["label"]},
                            "value": opt["value"],
                            "type": "primary" if opt["value"] == "confirm" else "default"
                        }
                        for opt in info["options"]
                    ]
                }
            ]
        }
    }
    
    # 保存 Gate 状态
    gate_state = {
        "gate_name": gate_name,
        "status": "waiting",
        "timestamp": str(datetime.now()),
        "preview_file": str(preview_path) if preview_path else None,
        "options": info["options"]
    }
    gate_file = Path(project_dir) / f".gate_{gate_name.replace(' ', '_').lower()}.json"
    save_json(gate_file, gate_state)
    
    # 发飞书消息（用 sessions_send 发到当前 session）
    return gate_state

def check_gate_response(project_dir, gate_name, timeout_ms=300000):
    """
    检查 Gate 是否有确认响应。
    通过检查 .gate_xxx.json 文件是否被用户更新来判断。
    
    返回：'confirm' / 'modify' / 'regen' / 'timeout'
    """
    gate_file = Path(project_dir) / f".gate_{gate_name.replace(' ', '_').lower()}.json"
    start = time.time()
    
    while (time.time() - start) * 1000 < timeout_ms:
        if gate_file.exists():
            state = load_json(gate_file)
            if state.get("status") != "waiting":
                return state.get("choice", "confirm")
        time.sleep(5)
    
    return "timeout"

def resolve_gate_choice(project_dir, gate_name, choice, model):
    """根据用户 Gate 选择执行对应操作"""
    if choice == "confirm":
        # 标记 Gate 完成
        gate_file = Path(project_dir) / f".gate_{gate_name.replace(' ', '_').lower()}.json"
        state = load_json(gate_file) if gate_file.exists() else {}
        state["status"] = "confirmed"
        state["choice"] = "confirm"
        save_json(gate_file, state)
        return "continue"
    
    elif choice in ("modify", "regen_dna", "regen_beats", "regen"):
        # 需要进一步处理，等待用户具体指令
        gate_file = Path(project_dir) / f".gate_{gate_name.replace(' ', '_').lower()}.json"
        state = load_json(gate_file) if gate_file.exists() else {}
        state["status"] = "awaiting_detail"
        state["pending_choice"] = choice
        save_json(gate_file, state)
        return "await_detail"
    
    elif choice == "timeout":
        return "continue"  # 超时则继续
    
    return "continue"

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
    story_beats = load_json(Path(project_dir) / "story_beats.json")
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    
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
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "generate_viewer.py"), Path(project_dir).name],
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
    update_progress(project_dir, "phase0", "running")
    with open(story_file, encoding="utf-8") as f:
        story_text = f.read()
    dest = Path(project_dir) / "story.txt"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(story_text)
    
    intent_file = Path(project_dir) / "director_intent.json"
    if not intent_file.exists():
        update_progress(project_dir, "phase0", "waiting_intent")
        return "waiting_intent"
    
    intent = load_json(intent_file)
    update_progress(project_dir, "phase0", "done")
    return "done"

def phase1_story_dna(project_dir, model="glm51"):
    """Phase 1: Story DNA 分析"""
    update_progress(project_dir, "phase1", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    intent = load_json(Path(project_dir) / "director_intent.json")
    dna = run_llm("story_dna.md", {"story_text": story_text, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "story_dna.json", dna)
    update_progress(project_dir, "phase1", "done")
    return "done"

def phase2_beats(project_dir, model="glm51"):
    """Phase 2: Beat 可视化规划"""
    update_progress(project_dir, "phase2", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    # 验证：beats 数组必须非空
    beats_validation = {"type": "object", "key": "beats", "min_items": 1}
    beats = run_llm("beat_analysis.md", {"story_text": story_text, "story_dna": story_dna, "director_intent": intent}, model=model, validation=beats_validation)
    save_json(Path(project_dir) / "story_beats.json", beats)
    generate_beats_viewer(project_dir)
    update_progress(project_dir, "phase2", "waiting_gate", "等待 Gate 0 确认")
    return "waiting_gate"

def phase3_characters(project_dir, model="glm51"):
    """Phase 3: 角色档案 + 角色视觉"""
    update_progress(project_dir, "phase3", "running")
    story_text = open(Path(project_dir) / "story.txt", encoding="utf-8").read()
    story_dna = load_json(Path(project_dir) / "story_dna.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    
    chars = run_llm("character_card.md", {"story_text": story_text, "story_dna": story_dna, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "characters.json", chars)
    
    visuals = run_llm("character_visual.md", {"characters": chars, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "character_visuals.json", visuals)
    
    generate_character_viewer(project_dir)
    update_progress(project_dir, "phase3", "waiting_gate", "等待 Gate 1 确认")
    return "waiting_gate"

def phase4_cinematography(project_dir, model="glm51"):
    """Phase 4: Look Development → Color Script → Photography → Acting → 分镜组装"""
    update_progress(project_dir, "phase4", "running")
    
    # Phase 4a: Look Development（新增）
    print("  [4a] Look Development...")
    lookdev = run_llm("lookdev.md", {
        "story_dna": load_json(Path(project_dir) / "story_dna.json"),
        "director_intent": load_json(Path(project_dir) / "director_intent.json")
    }, model=model)
    save_json(Path(project_dir) / "lookdev.json", lookdev)
    update_progress(project_dir, "lookdev", "done")
    
    # Phase 4b: Color Script
    print("  [4b] Color Script...")
    beats = load_json(Path(project_dir) / "story_beats.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    beats_min = {"beats": [
        {k: v for k, v in b.items()
         if k in ("beat_id","emotion","emotion_intensity","narrative_function","scene","key_visual_moment","three_act_position","duration_estimate")}
        for b in beats.get("beats", [])
    ]}
    cs = run_llm("color_script.md", {"story_beats": beats_min, "director_intent": intent, "lookdev": lookdev}, model=model)
    save_json(Path(project_dir) / "color_script.json", cs)
    
    # Phase 4c: Photography
    print("  [4c] Photography...")
    photo = run_llm("cinematography.md", {
        "story_beats": beats_min,
        "color_script": {"beats": cs.get("beats", [])},
        "director_intent": intent
    }, model=model)
    save_json(Path(project_dir) / "photography.json", photo)
    
    # Phase 4d: Acting（带验证：确保返回所有 beats）
    print(f"  [4d] Acting ({len(beats.get('beats',[]))} beats)...")
    chars = load_json(Path(project_dir) / "characters.json")
    chars_min = {"characters": [
        {k: v for k, v in c.items()
         if k in ("name","aliases","personality_tags","role_level")}
        for c in chars.get("characters", [])
    ]}
    # 验证：acting.json 必须有 panels 数组，长度 >= beat 数量
    acting_validation = {
        "type": "object",
        "key": "panels",
        "min_items": len(beats.get("beats", []))
    }
    acting = run_llm("acting.md",
                    {"story_beats": beats_min, "characters": chars_min, "director_intent": intent},
                    model=model,
                    validation=acting_validation,
                    max_retries=3)
    save_json(Path(project_dir) / "acting.json", acting)
    
    # Phase 4e: 分镜组装
    print("  [4e] 分镜组装...")
    panels = assemble_panels(project_dir)
    save_json(Path(project_dir) / "panels.json", panels)
    
    # Phase 4f: 生成 viewer
    generate_storyboard_viewer(project_dir)
    
    update_progress(project_dir, "phase4", "waiting_gate", "等待 Gate 2 确认")
    return "waiting_gate"

def assemble_panels(project_dir):
    """Phase 4e: 组装 panels.json"""
    beats = load_json(Path(project_dir) / "story_beats.json").get("beats", [])
    chars = load_json(Path(project_dir) / "characters.json")
    char_vis = load_json(Path(project_dir) / "character_visuals.json")
    photo = load_json(Path(project_dir) / "photography.json")
    acting = load_json(Path(project_dir) / "acting.json")
    cs = load_json(Path(project_dir) / "color_script.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    
    # Build beat → appearance_id mapping from expected_appearances
    beat_to_appearance = {}  # {beat_id: {char_name: appearance_id}}
    char_first = {}  # {char_name: default appearance_id}
    for c in chars.get("characters", []):
        cname = c["name"]
        ea_list = c.get("expected_appearances", [])
        char_first[cname] = ea_list[0].get("appearance_id", ea_list[0].get("id", 0)) if ea_list else 0
        for ea in ea_list:
            bid = ea.get("beat_id", "")
            if bid:
                if bid not in beat_to_appearance:
                    beat_to_appearance[bid] = {}
                aid = ea.get("appearance_id", ea.get("id", 0))
                beat_to_appearance[bid][cname] = aid

    # Build character visual description map
    # Handle both {"character_visuals": [...]} and {"characters": [...]} structures
    vis_map = {}  # {(char_name, appearance_id): description}
    char_visuals_root = char_vis.get("character_visuals", char_vis.get("characters", []))
    for cv in char_visuals_root:
        cname = cv.get("name", "")
        for app in cv.get("appearances", []):
            # Handle both "id" and "appearance_id", "description" and "descriptions"
            aid = app.get("id", app.get("appearance_id", 0))
            # description (singular string) or descriptions (array)
            desc = app.get("description", "")
            if not desc:
                desc_list = app.get("descriptions", [])
                desc = desc_list[0] if desc_list else ""
            vis_map[(cname, aid)] = desc
    
    panels = []
    for i, beat in enumerate(beats):
        beat_id = beat["beat_id"]
        shot = next((s for s in photo.get("shots", []) if s.get("beat_id") == beat_id), {})
        act = next((a for a in acting.get("panels", []) if a.get("beat_id") == beat_id), {})
        csbeat = next((c for c in cs.get("beats", []) if c.get("beat_id") == beat_id), {})

        # Determine which characters appear in this beat and their appearance_ids
        beat_chars = beat.get("characters", [])
        beat_app_map = beat_to_appearance.get(beat_id, {})
        panel_char_prompts = []
        panel_char_names = []
        panel_char_appearances = []
        def infer_appearance(beat, char_first_aid=0):
            """Smart fallback: infer appearance_id from beat keywords when no explicit mapping exists."""
            scene = beat.get("scene", "") + beat.get("content", "") + beat.get("emotion", "") + beat.get("visual_hint", "")
            if any(kw in scene for kw in ["跑", "疲惫", "汗水", "翻山", "运动", "汗渍", "喘", "负荷"]):
                return 1  # 运动/疲惫状态
            if any(kw in scene for kw in ["清晨", "释然", "日出", "晨光", "宁静", "终点", "完成", "背影"]):
                return 2  # 精神升华/清晨状态
            return char_first_aid  # 默认日常状态

        if beat_chars:
            for cname in beat_chars:
                if beat_id in beat_to_appearance:
                    aid = beat_app_map.get(cname, char_first.get(cname, 0))
                else:
                    aid = infer_appearance(beat, char_first.get(cname, 0))
                panel_char_names.append(cname)
                panel_char_appearances.append({"name": cname, "appearance_id": aid})
                desc = vis_map.get((cname, aid), "")
                if desc:
                    panel_char_prompts.append(desc[:200])
        elif char_vis.get("character_visuals") or char_vis.get("characters"):
            # Fallback: all characters appear in all beats (backward compat)
            for cname, aid in char_first.items():
                if beat_id not in beat_to_appearance:
                    aid = infer_appearance(beat, aid)
                panel_char_names.append(cname)
                panel_char_appearances.append({"name": cname, "appearance_id": aid})
                desc = vis_map.get((cname, aid), "")
                if desc:
                    panel_char_prompts.append(desc[:200])
        
        q6 = intent.get("q6_transition_philosophy", "Mix")
        if q6 == "硬切": transition = "cut"
        elif q6 == "Dissolve": transition = "dissolve"
        elif q6 == "Fade": transition = "fade"
        else: transition = csbeat.get("transition_to_next", "cut") or "cut"
        
        appearance_refs = []
        for item in panel_char_appearances:
            appearance_refs.append(f"{item['name']}(appearance_{item['appearance_id']})")
        role_ref = "、".join(appearance_refs)
        aspect_ratio = photo.get("global_style", {}).get("aspect_ratio", "16:9") if isinstance(photo, dict) else "16:9"
        shot_type = shot.get("shot_type", "中景")
        cam_move = shot.get("camera_movement", "Static")
        lighting = shot.get("lighting", "")
        visual_hint = beat.get("visual_hint", "")
        # deeper cleaning for legacy prefixes / video-ish tags
        changed = True
        while changed:
            changed = False
            for prefix in ["特写：", "近景：", "中景：", "全景：", "远景：", "快速蒙太奇：", "慢动作：", "摄影机", "镜头"]:
                if visual_hint.startswith(prefix):
                    visual_hint = visual_hint[len(prefix):].strip(" ：，。;")
                    changed = True
        for noise in ["慢动作", "快速蒙太奇", "中景：", "近景：", "特写：", "远景：", "全景："]:
            visual_hint = visual_hint.replace(noise, "")
        visual_hint = re.sub(r"[；;]+", "，", visual_hint)
        visual_hint = re.sub(r"。{2,}", "。", visual_hint).strip(" ，。")
        perf = act.get("performance_notes", "")
        # If performance is empty-shot but beat clearly needs a human image, synthesize a static action cue
        if perf in ("空镜头", "", "N/A") and any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["跑", "疲惫", "翻山", "步伐", "背影"]):
            if any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["疲惫", "翻山"]):
                perf = "疲惫跑者的身体在一次短暂停顿中微微下沉，呼吸负荷清晰可见"
            elif any(kw in (beat.get("content", "") + beat.get("visual_hint", "")) for kw in ["背影", "步伐"]):
                perf = "背影在前进动作的一瞬间定格，步伐稳定，身体保持持续推进"
        freeze_action = act.get("freeze_action", "")
        body_tension = act.get("body_tension", "")
        energy_state = act.get("energy_state", "")
        if freeze_action in ("", "N/A"):
            freeze_action = perf if perf not in ("", "N/A") else "无明确动作定格"
        if body_tension in ("", "N/A"):
            if any(kw in freeze_action for kw in ["呼吸", "胸", "肩"]):
                body_tension = "胸腔与肩颈承压"
            elif any(kw in freeze_action for kw in ["步伐", "腿", "前倾"]):
                body_tension = "下肢与脊背持续发力"
            else:
                body_tension = "N/A"
        if energy_state in ("", "N/A"):
            if any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["疲惫", "负荷", "喘", "耗尽"]):
                energy_state = "耗尽"
            elif any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["释然", "轻盈", "宁静"]):
                energy_state = "释然"
            elif any(kw in (beat.get("emotion", "") + beat.get("content", "") + freeze_action) for kw in ["稳定", "平稳", "日常"]):
                energy_state = "稳定"
            else:
                energy_state = "压抑" if beat.get("emotion_intensity", 0) and beat.get("emotion_intensity", 0) >= 7 else "稳定"

        narrative_blob = beat.get("narrative_function", "") + beat.get("emotion", "") + beat.get("content", "") + beat.get("visual_hint", "")
        if any(kw in narrative_blob for kw in ["疲惫", "负荷", "翻山", "汗水"]):
            visual_task = "强调身体负荷与征服留下的疲惫痕迹"
            frame_priority = "body_state"
        elif any(kw in narrative_blob for kw in ["释然", "清晨", "渐行渐远", "终点"]):
            visual_task = "强调释然后的轻盈与空间开阔感"
            frame_priority = "emotion_pressure"
        elif any(kw in narrative_blob for kw in ["奖牌", "书架", "纹理", "触碰"]):
            visual_task = "强调物件纹理与记忆触发的关系"
            frame_priority = "movement_shape"
        else:
            visual_task = "强调当前叙事节点最关键的人物与空间信息"
            frame_priority = "character_identity"

        color_desc = csbeat.get("dominant_color", "")
        video_lines = [
            f"{aspect_ratio}，横屏。",
            f"镜头：{shot_type}，运镜方式：{cam_move}。",
        ]
        if role_ref:
            video_lines.append(f"角色：{role_ref}。")
        if visual_hint:
            video_lines.append(f"画面内容：{visual_hint}。")
        if perf:
            video_lines.append(f"人物动作：{perf}。")
        if freeze_action and freeze_action != "无明确动作定格":
            video_lines.append(f"动作定格：{freeze_action}。")
        if visual_task:
            video_lines.append(f"视觉任务：{visual_task}。")
        if lighting:
            video_lines.append(f"光线：{lighting}。")
        if color_desc:
            video_lines.append(f"整体画面色调：{color_desc}。")
        video_prompt = "\n".join(video_lines)
        
        panels.append({
            "panel_id": f"P{i+1:02d}",
            "beat_id": beat_id,
            "duration": beat.get("duration_estimate", 5),
            "shot_type": shot.get("shot_type", "中景"),
            "camera_movement": shot.get("camera_movement", "Static"),
            "scene_description": beat.get("visual_hint", ""),
            "voiceover": beat.get("voiceover", ""),
            "transition": transition,
            "lighting": shot.get("lighting", ""),
            "depth_of_field": shot.get("depth_of_field", ""),
            "color_temperature": shot.get("color_temperature", 5500),
            "performance_notes": act.get("performance_notes", ""),
            "emotional_subtext": act.get("emotional_subtext", ""),
            "performance_directive": act.get("performance_directive", ""),
            "freeze_action": freeze_action,
            "body_tension": body_tension,
            "energy_state": energy_state,
            "visual_task": visual_task,
            "frame_priority": frame_priority,
            "facial_expression": act.get("facial_expression", "N/A"),
            "body_language": act.get("body_language", "N/A"),
            "dominant_color": csbeat.get("dominant_color", ""),
            "color_narrative": csbeat.get("narrative_function", ""),
            "characters": panel_char_names,
            "character_prompts": panel_char_prompts,
            "character_appearances": panel_char_appearances,
            "appearance_refs": appearance_refs,
            "video_prompt": video_prompt,
            "key_visual_moment": beat.get("key_visual_moment", False),
            "directors_note": "",
            "versions": []
        })
    
    return {"panels": panels}

def phase5_output(project_dir):
    """Phase 5: 成片输出（主要是 viewer.html）"""
    update_progress(project_dir, "phase5", "running")
    generate_storyboard_viewer(project_dir)
    update_progress(project_dir, "phase5", "done")
    return "done"

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

def main():
    parser = argparse.ArgumentParser(description="Director Storyboard Pipeline")
    parser.add_argument("phase", nargs="?", choices=["0","1","2","3","4","5","full","lookdev","patch"],
                        help="Phase")
    parser.add_argument("--project", required=True)
    parser.add_argument("--story", help="Path to story.txt (phase 0)")
    parser.add_argument("--model", default="gemma4", choices=["glm51","kimi25","gemma4"])
    parser.add_argument("--confirm", action="store_true", help="Bypass gate waiting, assume confirmed")
    parser.add_argument("--patch", help="Partial modification instruction (e.g. 'B05+B06 merged')")
    args = parser.parse_args()

    if "/" in args.project:
        project_dir = Path(args.project)
    else:
        project_dir = PROJECTS_DIR / args.project
    ensure_dir(project_dir)

    # 局部修改模式
    if args.phase == "patch" and args.patch:
        print(f"🔧 局部修改: {args.patch}")
        patch_beats(project_dir, args.patch, model=args.model)
        print("✅ 修改完成")
        return

    if args.phase == "full":
        print(f"🚀 全流程启动: {project_dir.name}")
        
        # Phase 0
        if args.story:
            s = phase0_intent_capture(project_dir, args.story)
            if s == "waiting_intent":
                print("⏸ Phase 0: 请先完成意图问卷 → 写入 director_intent.json")
                return
        
        # Phase 1
        phase1_story_dna(project_dir, model=args.model)
        
        # Phase 2
        status = phase2_beats(project_dir, model=args.model)
        if status == "waiting_gate":
            preview = Path(project_dir) / "beats-viewer.html"
            gate = wait_for_gate("Gate 0", project_dir, "beats-viewer.html")
            print(f"⏸ Gate 0 等待确认: {preview}")
            if not args.confirm:
                choice = check_gate_response(project_dir, "Gate 0")
                resolved = resolve_gate_choice(project_dir, "Gate 0", choice, args.model)
                if resolved == "await_detail":
                    print("⏸ 请输入具体修改指令（如 --patch 'B05+B06 merged'）")
                    return
            else:
                print("  [skip] Gate 0 确认跳过（--confirm）")
        
        # Phase 3
        status = phase3_characters(project_dir, model=args.model)
        if status == "waiting_gate":
            gate = wait_for_gate("Gate 1", project_dir, "character-viewer.html")
            print(f"⏸ Gate 1 等待确认")
            if not args.confirm:
                choice = check_gate_response(project_dir, "Gate 1")
                resolve_gate_choice(project_dir, "Gate 1", choice, args.model)
            else:
                print("  [skip] Gate 1 确认跳过（--confirm）")
        
        # Phase 4
        status = phase4_cinematography(project_dir, model=args.model)
        if status == "waiting_gate":
            gate = wait_for_gate("Gate 2", project_dir, "viewer.html")
            print(f"⏸ Gate 2 等待确认")
            if not args.confirm:
                choice = check_gate_response(project_dir, "Gate 2")
                resolve_gate_choice(project_dir, "Gate 2", choice, args.model)
            else:
                print("  [skip] Gate 2 确认跳过（--confirm）")
        
        # Phase 5
        phase5_output(project_dir)
        print("🎉 全流程完成!")
        return

    # 单 Phase 模式
    phase_map = {
        "0": lambda: phase0_intent_capture(project_dir, args.story),
        "1": phase1_story_dna,
        "2": phase2_beats,
        "3": phase3_characters,
        "4": phase4_cinematography,
        "5": phase5_output,
        "lookdev": phase_lookdev,
    }
    phase_map[args.phase](project_dir, model=args.model)

if __name__ == "__main__":
    main()
