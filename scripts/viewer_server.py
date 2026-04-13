#!/usr/bin/env python3
"""
viewer_server.py — 导演工作台后端服务器
提供 annotation 持久化和 version snapshot 功能。

启动: python3 viewer_server.py [--port 8080]
访问: http://localhost:8080/viewer/<project_name>
"""
import argparse
import json
import os
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import threading

SKILL_DIR = Path(__file__).parent.parent
PROJECTS_DIR = SKILL_DIR / "projects"
PORT = 8080

# ─── Annotation & Version Backend ───────────────────────────────

def save_notes(project_name, notes):
    """保存批注到 panel_notes.json"""
    project = PROJECTS_DIR / project_name
    if not project.exists():
        return {"error": "项目不存在"}, 404
    notes_file = project / "panel_notes.json"
    
    # 合并：保留历史，新批注追加
    existing = {}
    if notes_file.exists():
        existing = json.load(open(notes_file))
    
    for pid, new_notes in notes.items():
        if pid not in existing:
            existing[pid] = []
        # 追加新批注（带时间戳）
        for n in new_notes:
            n["id"] = str(uuid.uuid4())[:8]
            n["timestamp"] = datetime.now().isoformat()
        existing[pid] = existing[pid] + new_notes
    
    with open(notes_file, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return {"saved": True, "panels": list(notes.keys())}

def load_notes(project_name):
    """加载批注"""
    project = PROJECTS_DIR / project_name
    notes_file = project / "panel_notes.json"
    if not notes_file.exists():
        return {}
    return json.load(open(notes_file))

def save_version(project_name, label):
    """保存版本快照"""
    project = PROJECTS_DIR / project_name
    if not project.exists():
        return {"error": "项目不存在"}, 404
    
    vp_file = project / "viewer_versions.json"
    versions = []
    if vp_file.exists():
        versions = json.load(open(vp_file)).get("versions", [])
    
    vid = str(uuid.uuid4())[:8]
    version = {
        "id": vid,
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "files": {}
    }
    
    # 快照关键文件
    for fname in ["story_beats.json", "panels.json", "director_intent.json",
                   "color_script.json", "photography.json", "acting.json"]:
        fpath = project / fname
        if fpath.exists():
            version["files"][fname] = json.load(open(fpath))
    
    versions.append(version)
    with open(vp_file, "w") as f:
        json.dump({"versions": versions}, f, ensure_ascii=False, indent=2)
    
    return {"saved": True, "version_id": vid, "label": label}

def load_versions(project_name):
    """加载版本列表"""
    project = PROJECTS_DIR / project_name
    vp_file = project / "viewer_versions.json"
    if not vp_file.exists():
        return []
    return json.load(open(vp_file)).get("versions", [])

def load_version(project_name, version_id):
    """加载指定版本"""
    versions = load_versions(project_name)
    for v in versions:
        if v["id"] == version_id:
            return v
    return None

def get_project_info(project_name):
    """获取项目信息"""
    project = PROJECTS_DIR / project_name
    if not project.exists():
        return None
    
    info = {"name": project_name, "files": {}}
    for fname in ["story_beats.json", "panels.json", "director_intent.json"]:
        fp = project / fname
        if fp.exists():
            info["files"][fname] = {
                "size": fp.stat().st_size,
                "modified": datetime.fromtimestamp(fp.stat().st_mtime).isoformat()
            }
    return info

# ─── HTTP Server ──────────────────────────────────────────────

class ViewerHandler(SimpleHTTPRequestHandler):
    """处理 viewer 后端 API 请求"""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path.startswith("/api/"):
            # API 路由
            project = query.get("project", [""])[0]
            
            if path == "/api/project" and project:
                result = get_project_info(project)
                if result:
                    self.send_json(result)
                else:
                    self.send_json({"error": "not found"}, 404)
            
            elif path == "/api/versions" and project:
                result = load_versions(project)
                self.send_json(result)
            
            elif path == "/api/notes" and project:
                result = load_notes(project)
                self.send_json(result)
            
            elif path.startswith("/api/version/") and project:
                version_id = path.split("/")[-1]
                result = load_version(project, version_id)
                if result:
                    self.send_json(result)
                else:
                    self.send_json({"error": "not found"}, 404)
            
            elif path == "/api/projects":
                # 列出所有项目
                projects = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]
                self.send_json({"projects": projects})
            
            else:
                self.send_json({"error": "unknown endpoint"}, 404)
        
        elif path.startswith("/viewer/"):
            # 提供 viewer HTML
            project = path.split("/viewer/")[-1].strip("/")
            viewer_path = PROJECTS_DIR / project / "viewer.html"
            if viewer_path.exists():
                self.send_file(viewer_path, "text/html")
            else:
                self.send_json({"error": "viewer not found"}, 404)
        
        elif path == "/":
            # 根目录：列出项目
            projects = [p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()]
            html = self._index_html(projects)
            self.send_html(html)
        
        else:
            # 静态文件
            super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        project = query.get("project", [""])[0]
        
        if not project:
            self.send_json({"error": "project required"}, 400)
            return
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            data = json.loads(body)
        except:
            self.send_json({"error": "invalid JSON"}, 400)
            return
        
        if parsed.path == "/api/notes":
            notes = data.get("notes", {})
            result = save_notes(project, notes)
            self.send_json(result)
        
        elif parsed.path == "/api/version":
            label = data.get("label", f"手动快照 {datetime.now().strftime('%H:%M')}")
            result = save_version(project, label)
            self.send_json(result)
        
        else:
            self.send_json({"error": "unknown endpoint"}, 404)
    
    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def send_file(self, filepath, content_type):
        content = open(filepath, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
    
    def _index_html(self, projects):
        links = "".join(f'<li><a href="/viewer/{p}">{p}</a></li>' for p in sorted(projects))
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>导演工作台</title>
<style>
body{{font-family:system-ui;max-width:700px;margin:60px auto;padding:20px}}
h1{{color:#e63946}}
ul{{list-style:none;padding:0}}
li{{padding:8px 0;border-bottom:1px solid #333}}
a{{color:#7c3aed;text-decoration:none;font-size:16px}}
a:hover{{text-decoration:underline}}
.info{{color:#888;font-size:13px}}
</style></head><body>
<h1>🎬 导演工作台</h1>
<p class="info">选择项目查看导演分镜工作台</p>
<ul>{links}</ul>
</body></html>"""
    
    def log_message(self, fmt, *args):
        # 抑制默认日志，改用时间戳
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}", flush=True)

# ─── 启动 ────────────────────────────────────────────────────

def run_server(port=PORT):
    server = HTTPServer(("localhost", port), ViewerHandler)
    print(f"🎬 导演工作台后端启动: http://localhost:{port}")
    print(f"   项目列表: http://localhost:{port}/")
    print(f"   示例: http://localhost:{port}/viewer/test-emotional-monologue")
    print(f"按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 停止")
        server.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    run_server(args.port)
