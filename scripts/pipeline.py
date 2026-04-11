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

def run_llm(prompt_file, input_data, model="glm51", output_file=None):
    """调用 LLM via api.py"""
    prompt_path = SKILL_DIR / "references" / prompt_file
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()
    
    input_json = json.dumps(input_data, ensure_ascii=False, indent=2)
    full_prompt = template + f"\n\n## 输入数据\n```json\n{input_json}\n```\n\n请输出 JSON。"
    
    cmd = [
        sys.executable,
        str(SKILL_DIR / "scripts" / "call_model.py"),
        "--prompt", full_prompt,
        "--model", model,
        "--output", output_file or "/tmp/llm_output.json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"LLM call failed: {result.stderr}")
    
    data = load_json(output_file or "/tmp/llm_output.json")
    # api.py returns (text, elapsed, usage) tuple
    if isinstance(data, tuple):
        return data[0] if len(data) >= 1 else data
    return data

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
    """生成带批注系统的导演工作台 HTML"""
    panels = load_json(Path(project_dir) / "panels.json").get("panels", [])
    versions = []
    vp_file = Path(project_dir) / "viewer_versions.json"
    if vp_file.exists():
        versions = load_json(vp_file).get("versions", [])
    
    total_dur = sum(p.get("duration", 5) for p in panels)
    version_select = "".join(
        f'<option value="{v["id"]}">{v["label"]} ({v["timestamp"][:16]})</option>'
        for v in versions
    ) or '<option value="">当前版本</option>'
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>导演分镜工作台</title>
<style>
body{{font-family:system-ui;max-width:1200px;margin:0 auto;padding:16px;background:#0f0f0f;color:#e5e5e5}}
.header{{display:flex;align-items:center;gap:16px;border-bottom:2px solid #333;padding-bottom:12px;margin-bottom:16px}}
.header h1{{color:#fff;margin:0;font-size:22px}}
.header-meta{{display:flex;gap:12px;font-size:13px;color:#888}}
.tag{{padding:2px 8px;border-radius:4px;font-size:11px}}
.tag-red{{background:#e63946;color:#fff}}
.tag-orange{{background:#f4a261;color:#000}}
.version-bar{{background:#1a1a2e;padding:10px 16px;border-radius:6px;margin-bottom:16px;display:flex;align-items:center;gap:12px;font-size:13px}}
.version-bar select{{background:#252525;color:#e5e5e5;border:1px solid #444;padding:4px 8px;border-radius:4px}}
.btn{{background:#7c3aed;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:13px}}
.panel{{display:grid;grid-template-columns:180px 1fr;gap:12px;border:1px solid #2a2a2a;border-radius:8px;padding:14px;margin:12px 0;background:#1a1a1a}}
.panel:hover{{border-color:#7c3aed}}
.pid{{font-size:18px;font-weight:bold;color:#e63946}}
.meta{{color:#888;font-size:12px;margin-top:4px}}
.scene{{color:#ccc;font-size:13px;margin:8px 0}}
.note-section{{margin-top:10px}}
.note-label{{color:#888;font-size:11px;margin-bottom:4px}}
.note-input{{width:100%;background:#252525;color:#e5e5e5;border:1px dashed #7c3aed;border-radius:4px;padding:8px;font-size:13px;min-height:60px;resize:vertical}}
.save-note{{background:#7c3aed;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;margin-top:4px}}
.notes-list{{margin-top:8px}}
.note-entry{{background:#1e1e2e;padding:6px 10px;border-radius:4px;margin-top:4px;font-size:12px;color:#aaa}}
.note-entry .meta{{color:#666;font-size:11px}}
</style>
</head><body>
<div class="header">
  <h1>🎬 导演分镜工作台</h1>
  <div class="header-meta">
    <span class="tag tag-red">总时长: {total_dur}s</span>
    <span class="tag tag-orange">Panels: {len(panels)}</span>
  </div>
</div>

<div class="version-bar">
  <span style="color:#888">版本:</span>
  <select id="version-select">{version_select}</select>
  <span style="color:#888">|</span>
  <button class="btn" onclick="saveVersion()">📸 保存快照</button>
  <button class="btn" onclick="saveNotes()">💾 保存批注</button>
  <span id="save-status" style="color:#4ade80;font-size:12px;margin-left:auto"></span>
</div>
"""
    for p in panels:
        pid = p.get("panel_id", "")
        beat_id = p.get("beat_id", "")
        duration = p.get("duration", 5)
        shot_type = p.get("shot_type", "中景")
        cam = p.get("camera_movement", "Static")
        transition = p.get("transition", "cut")
        voiceover = p.get("voiceover", "")
        performance_notes = p.get("performance_notes", "")
        emotional_subtext = p.get("emotional_subtext", "")
        directive = p.get("performance_directive", "")
        color = p.get("dominant_color", "")
        
        # Load saved notes for this panel
        notes = []
        notes_file = Path(project_dir) / "panel_notes.json"
        if notes_file.exists():
            all_notes = load_json(notes_file)
            notes = all_notes.get(pid, [])
        
        notes_html = "".join(
            f"<div class='note-entry'><div class='meta'>{n.get('timestamp','')[:16]} | {n.get('author','')}</div><div>{n.get('text','')}</div></div>"
            for n in notes[-3:]  # Show last 3 notes
        )
        
        html += f"""
<div class="panel" id="panel-{pid}">
  <div>
    <div class="pid">{pid} <span style="color:#888;font-size:13px">{beat_id}</span></div>
    <div class="meta">{shot_type} | {duration}s | {cam}</div>
    <div class="meta" style="margin-top:4px">
      <span style="color:#e63946">{transition}</span>
      {" | " + color if color else ""}
    </div>
  </div>
  <div>
    <div class="scene">🎥 {p.get('scene_description','')[:100]}...</div>
    {f"<div style='color:#2563eb;font-size:13px;margin-top:4px'>🎤 {voiceover[:60]}...</div>" if voiceover else ""}
    <div class="note-section">
      <div class="note-label">表演笔记</div>
      <div style="color:#ccc;font-size:13px">{performance_notes[:80]}...</div>
      {f"<div style='color:#a8dadc;font-size:12px;margin-top:4px'>潜: {emotional_subtext[:60]}...</div>" if emotional_subtext else ""}
      {f"<div style='color:#f4a261;font-size:12px;font-style:italic;margin-top:4px'>导演: {directive[:60]}...</div>" if directive else ""}
    </div>
    <div class="note-section">
      <div class="note-label">导演批注</div>
      <textarea class="note-input" id="note-{pid}" placeholder="输入批注..."></textarea>
      <div class="notes-list" id="notes-{pid}">{notes_html}</div>
    </div>
  </div>
</div>
"""
    
    html += """
<script>
const projectDir = location.pathname.split('/projects/')[1].split('/')[0];

async function saveNotes() {
  const panels = document.querySelectorAll('.panel');
  const allNotes = {};
  for (const p of panels) {
    const pid = p.id.replace('panel-', '');
    const ta = document.getElementById('note-' + pid);
    if (ta && ta.value.trim()) {
      allNotes[pid] = allNotes[pid] || [];
      allNotes[pid].push({
        text: ta.value.trim(),
        author: '导演',
        timestamp: new Date().toISOString()
      });
    }
  }
  // Save via fetch to backend
  const resp = await fetch('/save-notes', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: projectDir, notes: allNotes})
  });
  document.getElementById('save-status').textContent = '✅ 已保存';
  setTimeout(() => document.getElementById('save-status').textContent = '', 2000);
}

async function saveVersion() {
  const label = prompt('版本标签（如"调整B05后"）:');
  if (!label) return;
  const resp = await fetch('/save-version', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project: projectDir, label})
  });
  document.getElementById('save-status').textContent = '✅ 快照已保存: ' + label;
  setTimeout(() => document.getElementById('save-status').textContent = '', 3000);
}
</script>
</body></html>"""

    out = Path(project_dir) / "viewer.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ viewer.html: {out}")
    return out

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
    beats = run_llm("beat_analysis.md", {"story_text": story_text, "story_dna": story_dna, "director_intent": intent}, model=model)
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
    
    # Phase 4d: Acting
    print("  [4d] Acting...")
    chars = load_json(Path(project_dir) / "characters.json")
    chars_min = {"characters": [
        {k: v for k, v in c.items()
         if k in ("name","aliases","personality_tags","role_level")}
        for c in chars.get("characters", [])
    ]}
    acting = run_llm("acting.md", {"story_beats": beats_min, "characters": chars_min, "director_intent": intent}, model=model)
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
    
    visual_map = {}
    for cv in char_vis.get("character_visuals", []):
        for app in cv.get("appearances", []):
            visual_map[(cv["name"], app["id"])] = app["descriptions"][0] if app["descriptions"] else ""
    char_first = {c["name"]: (c.get("expected_appearances", [])[0]["id"] if c.get("expected_appearances") else 0) for c in chars.get("characters", [])}
    
    panels = []
    for i, beat in enumerate(beats):
        beat_id = beat["beat_id"]
        shot = next((s for s in photo.get("shots", []) if s.get("beat_id") == beat_id), {})
        act = next((a for a in acting.get("panels", []) if a.get("beat_id") == beat_id), {})
        csbeat = next((c for c in cs.get("beats", []) if c.get("beat_id") == beat_id), {})
        
        q6 = intent.get("q6_transition_philosophy", "Mix")
        if q6 == "硬切": transition = "cut"
        elif q6 == "Dissolve": transition = "dissolve"
        elif q6 == "Fade": transition = "fade"
        else: transition = csbeat.get("transition_to_next", "cut") or "cut"
        
        video_prompt = " ".join(filter(None, [
            shot.get("camera_movement", "Static"),
            beat.get("visual_hint", ""),
            act.get("performance_notes", ""),
            csbeat.get("dominant_color", "")
        ]))
        
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
            "facial_expression": act.get("facial_expression", "N/A"),
            "body_language": act.get("body_language", "N/A"),
            "dominant_color": csbeat.get("dominant_color", ""),
            "color_narrative": csbeat.get("narrative_function", ""),
            "characters": [],
            "character_prompts": [],
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
    instruction 格式如：'B05+B06 merged' / 'B03 duration→8s' / 'B07 add key_visual=true'
    """
    beats = load_json(Path(project_dir) / "story_beats.json")
    intent = load_json(Path(project_dir) / "director_intent.json")
    
    system = "你是专业分镜规划师。用户要求局部修改Beat方案。请直接修改JSON中的相关字段，只返回修改后的story_beats.json完整内容。"
    user = f"""当前 story_beats.json:
{json.dumps(beats, ensure_ascii=False, indent=2)}

导演修改指令: {instruction}

请直接输出修改后的完整JSON（不要解释，只返回JSON）。"""
    
    patched = run_llm("beat_analysis.md", {"instruction": instruction, "story_beats": beats, "director_intent": intent}, model=model)
    save_json(Path(project_dir) / "story_beats.json", patched)
    generate_beats_viewer(project_dir)
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
