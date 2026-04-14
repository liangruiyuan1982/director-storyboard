#!/usr/bin/env python3
"""生成带真实后端连接的 viewer.html"""
import json
from pathlib import Path
from datetime import datetime

BACKEND_URL = "http://localhost:8080"

def resolve_project_dir(project_dir):
    path = Path(project_dir)
    if path.exists():
        return path.resolve()
    candidate = Path(__file__).parent.parent / "projects" / str(project_dir)
    if candidate.exists():
        return candidate.resolve()
    return path


def generate_viewer_html(project_dir):
    """生成完整的 viewer.html，包含真实后端调用"""
    project_dir = resolve_project_dir(project_dir)
    project_name = Path(project_dir).name
    
    panels = []
    panels_file = Path(project_dir) / "panels.json"
    if panels_file.exists():
        panels = json.load(open(panels_file)).get("panels", [])
    
    # 加载已有批注和版本
    notes_file = Path(project_dir) / "panel_notes.json"
    notes = {}
    if notes_file.exists():
        notes = json.load(open(notes_file))
    
    versions_file = Path(project_dir) / "viewer_versions.json"
    versions = []
    if versions_file.exists():
        versions = json.load(open(versions_file)).get("versions", [])
    
    total_dur = sum(p.get("duration", 5) for p in panels)
    
    version_options = "\n".join(
        f'<option value="{v["id"]}">{v["label"]} ({v["timestamp"][:16]})</option>'
        for v in reversed(versions)
    )
    
    panels_html = ""
    # 提取所有 keyframes 数据（keyframes.json 已合并到 panels.json）
    all_keyframes = {}
    for p in panels:
        pid = p.get("panel_id","")
        all_keyframes[pid] = p.get("keyframes", [])
    
    for p in panels:
        pid = p.get("panel_id", "")
        pid = p.get("panel_id", "")
        beat_id = p.get("beat_id", "")
        duration = p.get("duration", 5)
        shot_type = p.get("shot_type", "中景")
        cam = p.get("camera_movement", "Static")
        transition = p.get("transition", "cut")
        voiceover = p.get("voiceover", "")
        perf_notes = p.get("performance_notes", "")
        emo_sub = p.get("emotional_subtext", "")
        directive = p.get("performance_directive", "")
        freeze_action = p.get("freeze_action", "")
        body_tension = p.get("body_tension", "")
        energy_state = p.get("energy_state", "")
        visual_task = p.get("visual_task", "")
        frame_priority = p.get("frame_priority", "")
        color = p.get("dominant_color", "")
        scene_desc = p.get("video_prompt", "")  # 用 video_prompt 而非 scene_description（包含完整信息）
        appearance_refs = p.get("appearance_refs", [])
        
        # 已有批注
        pid_notes = notes.get(pid, [])
        notes_html = ""
        for n in pid_notes[-3:]:
            ts = n.get("timestamp", "")[:16]
            txt = n.get("text", "")
            notes_html += f"""<div class="note-entry">
                <div class="note-meta">{ts} | {n.get('author','导演')}</div>
                <div>{txt}</div>
            </div>"""
        
        kf_star = "⭐" if p.get("key_visual_moment") else ""
        
        # 构建 keyframes HTML（image_prompt 列表）
        kf_list = all_keyframes.get(pid, [])
        if kf_list:
            kf_items_html = ""
            for kf in kf_list:
                frame_type = kf.get("frame_type","")
                img_prompt = kf.get("image_prompt","")
                kf_items_html += f"""
      <div class="kf-item">
        <div class="kf-label">🖼️ {frame_type}</div>
        <div class="kf-prompt">{"  " + img_prompt[:200]}{"..." if len(img_prompt)>200 else ""}</div>
        <button class="btn-copy" onclick="copyPrompt(this)">📋 复制</button>
      </div>"""
            keyframes_html = f"""
    <div class="keyframe-section">
      <div class="section-label">🖼️ 关键帧图Prompt <span class="keyframe-count">({len(kf_list)}帧)</span></div>
      {kf_items_html}
    </div>"""
        else:
            keyframes_html = """
    <div class="keyframe-section keyframe-missing">
      <div class="section-label">🖼️ 关键帧图Prompt</div>
      <div class="kf-missing">⚠️ 暂无keyframes（需重新生成）</div>
    </div>"""
        
        panels_html += f"""
<div class="panel" id="panel-{pid}">
  <div class="panel-left">
    <div class="pid">{kf_star}{pid} <span class="beat-id">{beat_id}</span></div>
    <div class="meta">{shot_type} | {duration}s | {cam}</div>
    <div class="meta" style="margin-top:6px">
      <span class="transition-tag">{transition}</span>
      {" | " + color[:25] if color else ""}
    </div>
  </div>
  <div class="panel-right">
    {('<div class="char-ref">🎭 角色引用: ' + '、'.join(appearance_refs) + '</div>') if appearance_refs else ''}
    <div class="scene">🎬 视频Prompt <span class="prompt-label">video_prompt</span></div>
    <div class="video-prompt">{scene_desc[:300]}{"..." if len(scene_desc)>300 else ""}</div>
    {('<div class="voiceover">🎤 ' + voiceover[:80] + '...</div>') if voiceover else ''}
    {keyframes_html}
    <div class="perf-section">
      <div class="section-label">表演笔记</div>
      <div class="perf-notes">{perf_notes[:100]}{"..." if len(perf_notes)>100 else ""}</div>
      {('<div class="schema-line"><span class="schema-key">visual_task</span> ' + visual_task + '</div>') if visual_task else ''}
      {('<div class="schema-line"><span class="schema-key">frame_priority</span> ' + frame_priority + '</div>') if frame_priority else ''}
      {('<div class="schema-line"><span class="schema-key">freeze_action</span> ' + freeze_action + '</div>') if freeze_action and freeze_action != 'N/A' else ''}
      {('<div class="schema-line"><span class="schema-key">body_tension</span> ' + body_tension + '</div>') if body_tension and body_tension != 'N/A' else ''}
      {('<div class="schema-line"><span class="schema-key">energy_state</span> ' + energy_state + '</div>') if energy_state and energy_state != 'N/A' else ''}
      {('<div class="emo-sub">潜: ' + emo_sub[:80] + '...</div>') if emo_sub else ''}
      {('<div class="directive">导演: ' + directive[:80] + '...</div>') if directive else ''}
    </div>
    <div class="annotation-section">
      <div class="section-label">导演批注</div>
      <textarea class="note-input" id="note-{pid}" placeholder="输入批注... (Shift+Enter换行)" rows="2"></textarea>
      <div class="note-actions">
        <button class="btn-save" onclick="saveNote('{pid}')">💾 保存</button>
      </div>
      <div class="notes-list" id="notes-{pid}">{notes_html}</div>
    </div>
  </div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🎬 导演分镜工作台 — {project_name}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0a0a0f;
  color: #e5e5e5;
  min-height: 100vh;
}}
.header {{
  position: sticky;
  top: 0;
  background: #0a0a0f;
  border-bottom: 2px solid #2a2a3a;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  z-index: 100;
}}
.header h1 {{
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}}
.header-right {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}}
.tag {{
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}}
.tag-red {{ background: #e63946; color: #fff; }}
.tag-purple {{ background: #7c3aed; color: #fff; }}
.tag-gray {{ background: #374151; color: #ccc; }}
.version-bar {{
  background: #12121f;
  border-bottom: 1px solid #1e1e2e;
  padding: 10px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}}
.version-bar select {{
  background: #1e1e2e;
  color: #e5e5e5;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 13px;
}}
.btn {{
  background: #7c3aed;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}}
.btn:hover {{ background: #6d28d9; }}
.btn-save {{
  background: #1e3a5f;
  color: #93c5fd;
  border: 1px solid #2563eb;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}}
.btn-save:hover {{ background: #1e40af; }}
.main {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px 20px;
}}
.panel {{
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 12px;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  background: #111118;
  transition: border-color 0.2s;
}}
.panel:hover {{ border-color: #7c3aed; }}
.panel-left {{ }}
.pid {{
  font-size: 17px;
  font-weight: 700;
  color: #e63946;
}}
.pid .beat-id {{ color: #888; font-size: 13px; font-weight: 400; margin-left: 6px; }}
.meta {{ color: #6b7280; font-size: 12px; margin-top: 4px; }}
.transition-tag {{
  display: inline-block;
  background: #e63946;
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}}
.scene {{ color: #d1d5db; font-size: 13px; line-height: 1.5; margin-bottom: 4px; font-weight: 600; }}
.prompt-label {{ font-size: 10px; background: #7c3aed; color: #fff; padding: 1px 5px; border-radius: 3px; font-weight: 400; margin-left: 6px; }}
.video-prompt {{ color: #a5b4fc; font-size: 13px; line-height: 1.5; background: #16162a; border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; font-family: "Courier New", monospace; }}
.voiceover {{ color: #60a5fa; font-size: 12px; margin-top: 6px; }}
.char-ref {{ color: #fca5a5; font-size: 12px; margin-bottom: 6px; }}
.perf-section {{ margin-top: 8px; }}
.section-label {{ color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
.perf-notes {{ color: #9ca3af; font-size: 13px; line-height: 1.4; }}
.schema-line {{ color: #d1d5db; font-size: 12px; margin-top: 4px; }}
.schema-key {{ display: inline-block; min-width: 92px; color: #c084fc; font-family: monospace; font-size: 11px; }}
.emo-sub {{ color: #67e8f9; font-size: 12px; margin-top: 4px; font-style: italic; }}
.directive {{ color: #fbbf24; font-size: 12px; margin-top: 4px; }}
.keyframe-section {{ margin-top: 8px; border-top: 1px dashed #2a2a3a; padding-top: 8px; }}
.keyframe-count {{ color: #6b7280; font-size: 11px; font-weight: 400; }}
.kf-item {{ background: #1a1a2e; border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; }}
.kf-label {{ color: #fbbf24; font-size: 12px; font-weight: 600; margin-bottom: 4px; }}
.kf-prompt {{ color: #e5e5e5; font-size: 12px; line-height: 1.5; white-space: pre-wrap; font-family: "Courier New", monospace; background: #111120; border-radius: 4px; padding: 6px 8px; }}
.btn-copy {{ background: #1e3a5f; color: #93c5fd; border: 1px solid #2563eb; border-radius: 4px; padding: 2px 8px; font-size: 11px; cursor: pointer; margin-top: 4px; }}
.btn-copy:hover {{ background: #1e40af; }}
.keyframe-missing {{ border-top: 1px dashed #2a2a3a; padding-top: 8px; margin-top: 8px; }}
.kf-missing {{ color: #6b7280; font-size: 12px; font-style: italic; }}
.annotation-section {{ margin-top: 10px; }}
.note-input {{
  width: 100%;
  background: #1a1a25;
  color: #e5e5e5;
  border: 1px dashed #4b5563;
  border-radius: 6px;
  padding: 8px;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  min-height: 50px;
  font-family: inherit;
}}
.note-input:focus {{ outline: none; border-color: #7c3aed; }}
.note-actions {{ margin-top: 4px; display: flex; gap: 8px; }}
.notes-list {{ margin-top: 6px; }}
.note-entry {{
  background: #1a1a28;
  border-left: 3px solid #7c3aed;
  padding: 6px 10px;
  border-radius: 0 4px 4px 0;
  margin-top: 4px;
  font-size: 12px;
}}
.note-meta {{ color: #6b7280; font-size: 11px; margin-bottom: 2px; }}
#status-bar {{
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #1e1e2e;
  color: #4ade80;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  opacity: 0;
  transition: opacity 0.3s;
  z-index: 200;
}}
#status-bar.show {{ opacity: 1; }}
</style>
</head>
<body>

<div class="header">
  <h1>🎬 导演分镜工作台</h1>
  <div class="tag tag-red">{total_dur}s</div>
  <div class="tag tag-purple">{len(panels)} panels</div>
  <div class="header-right">
    <button class="btn" onclick="saveAllNotes()">💾 保存全部批注</button>
    <button class="btn" onclick="saveSnapshot()">📸 保存快照</button>
  </div>
</div>

<div class="version-bar">
  <span style="color:#6b7280">版本:</span>
  <select id="version-select" onchange="loadVersion(this.value)">
    <option value="">— 当前版本 —</option>
    {version_options}
  </select>
  <span class="tag tag-gray">{project_name}</span>
  <span id="version-info" style="color:#6b7280;font-size:12px;margin-left:auto">
    后端: {BACKEND_URL}
  </span>
</div>

<div class="main">
{"".join(panels_html)}
</div>

<div id="status-bar"></div>

<script>
const PROJECT = "{project_name}";
const BACKEND = "{BACKEND_URL}";
let currentVersion = null;

// ─── Status Bar ──────────────────────────────────────────────
function showStatus(msg, color="") {{
  const el = document.getElementById("status-bar");
  el.textContent = msg;
  el.style.color = color || "#4ade80";
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}}

// ─── Copy Prompt ─────────────────────────────────────────
async function copyPrompt(btn) {{
  const promptEl = btn.previousElementSibling;
  const text = promptEl.textContent.trim();
  try {{
    await navigator.clipboard.writeText(text);
    const orig = btn.textContent;
    btn.textContent = "✅ 已复制";
    setTimeout(() => btn.textContent = orig, 1500);
  }} catch(e) {{
    showStatus("复制失败: " + e.message, "#ef4444");
  }}
}}

// ─── Note Operations ───────────────────────────────────────
async function saveNote(pid) {{
  const ta = document.getElementById("note-" + pid);
  const text = ta.value.trim();
  if (!text) return;
  
  try {{
    const resp = await fetch(BACKEND + "/api/notes?project=" + PROJECT, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ notes: {{ [pid]: [{{ text, author: "导演" }}] }} }})
    }});
    const result = await resp.json();
    if (result.saved) {{
      ta.value = "";
      showStatus("✅ 批注已保存");
      // 刷新批注列表
      loadNotesForPanel(pid);
    }}
  }} catch (e) {{
    showStatus("❌ 保存失败: " + e.message, "#f87171");
  }}
}}

async function saveAllNotes() {{
  const panels = document.querySelectorAll(".panel");
  const allNotes = {{}};
  for (const p of panels) {{
    const pid = p.id.replace("panel-", "");
    const ta = document.getElementById("note-" + pid);
    if (ta && ta.value.trim()) {{
      allNotes[pid] = [{{ text: ta.value.trim(), author: "导演" }}];
    }}
  }}
  const pids = Object.keys(allNotes);
  if (pids.length === 0) {{ showStatus("没有新批注", "#fbbf24"); return; }}
  
  try {{
    const resp = await fetch(BACKEND + "/api/notes?project=" + PROJECT, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ notes: allNotes }})
    }});
    const result = await resp.json();
    if (result.saved) {{
      for (const pid of pids) {{
        const ta = document.getElementById("note-" + pid);
        if (ta) ta.value = "";
      }}
      showStatus("✅ " + pids.length + " 个面板批注已保存");
    }}
  }} catch (e) {{
    showStatus("❌ 保存失败: " + e.message, "#f87171");
  }}
}}

async function loadNotesForPanel(pid) {{
  try {{
    const resp = await fetch(BACKEND + "/api/notes?project=" + PROJECT);
    const allNotes = await resp.json();
    const pidNotes = allNotes[pid] || [];
    const container = document.getElementById("notes-" + pid);
    if (!container) return;
    container.innerHTML = pidNotes.slice(-3).map(n => `
      <div class="note-entry">
        <div class="note-meta">${{n.timestamp ? n.timestamp.slice(0,16) : ""}} | ${{n.author || "导演"}}</div>
        <div>${{n.text}}</div>
      </div>
    `).join("");
  }} catch (e) {{ /* backend not running */ }}
}}

// ─── Version Operations ────────────────────────────────────
async function saveSnapshot() {{
  const label = prompt("版本标签 (如 '调整B05后', 直接回车使用时间戳):");
  if (label === null) return;
  const finalLabel = label || "快照 " + new Date().toLocaleTimeString("zh-CN", {{hour:"2-digit",minute:"2-digit"}});
  
  try {{
    const resp = await fetch(BACKEND + "/api/version?project=" + PROJECT, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ label: finalLabel }})
    }});
    const result = await resp.json();
    if (result.saved) {{
      // 添加到下拉菜单
      const sel = document.getElementById("version-select");
      const opt = document.createElement("option");
      opt.value = result.version_id;
      opt.textContent = finalLabel + " (刚刚)";
      sel.insertBefore(opt, sel.firstChild);
      sel.value = result.version_id;
      showStatus("✅ 快照已保存: " + finalLabel);
    }}
  }} catch (e) {{
    showStatus("❌ 快照保存失败: " + e.message, "#f87171");
  }}
}}

async function loadVersion(vid) {{
  if (!vid) {{ showStatus("已切换到当前版本"); return; }}
  try {{
    const resp = await fetch(BACKEND + "/api/version/" + vid + "?project=" + PROJECT);
    const version = await resp.json();
    if (version && version.files) {{
      currentVersion = version;
      showStatus("📋 已加载版本: " + version.label);
      // 可以在这里实现版本对比 UI
      alert("版本: " + version.label + "\\n文件: " + Object.keys(version.files).join(", "));
    }}
  }} catch (e) {{
    showStatus("❌ 加载失败: " + e.message, "#f87171");
  }}
}}

// ─── Load existing notes on startup ─────────────────────────
async function init() {{
  try {{
    const resp = await fetch(BACKEND + "/api/notes?project=" + PROJECT);
    if (resp.ok) {{
      const allNotes = await resp.json();
      for (const [pid, pidNotes] of Object.entries(allNotes)) {{
        const container = document.getElementById("notes-" + pid);
        if (container && pidNotes.length > 0) {{
          container.innerHTML = pidNotes.slice(-3).map(n => `
            <div class="note-entry">
              <div class="note-meta">${{n.timestamp ? n.timestamp.slice(0,16) : ""}} | ${{n.author || "导演"}}</div>
              <div>${{n.text}}</div>
            </div>
          `).join("");
        }}
      }}
    }}
  }} catch (e) {{
    document.getElementById("version-info").textContent = 
      "⚠️ 后端未连接: " + e.message + " | 启动命令: python3 scripts/viewer_server.py";
  }}
}}

// ─── Keyboard shortcuts ───────────────────────────────────
document.addEventListener("keydown", (e) => {{
  if (e.key === "s" && (e.metaKey || e.ctrlKey)) {{
    e.preventDefault();
    saveAllNotes();
  }}
  // Ctrl+Enter in textarea saves that note
  if (e.key === "Enter" && e.shiftKey) {{
    const active = document.activeElement;
    if (active && active.classList.contains("note-input")) {{
      const pid = active.id.replace("note-", "");
      saveNote(pid);
    }}
  }}
}});

init();
</script>
</body>
</html>"""
    
    return html

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 generate_viewer.py <project_name|project_dir>")
        sys.exit(1)
    arg = sys.argv[1]
    project_dir = resolve_project_dir(arg)
    if not project_dir.exists():
        print(f"❌ 项目不存在: {project_dir}")
        sys.exit(1)

    html = generate_viewer_html(project_dir)
    out = project_dir / "viewer.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ viewer.html: {out} ({len(html)} bytes)")
