#!/usr/bin/env python3
"""
generate.py — 分镜图+视频生成工具
支持两种模式：
  --mode prompt   : 只生成并导出 image_prompt（选项B）
  --mode image    : 生成图片（选项A）
  --mode video    : 生成视频（选项A，需要先有图）
  --mode full     : 完整流程：图+视频（选项A）

用法：
  python3 generate.py full --project test-last-supper           # 完整流程
  python3 generate.py prompt --project test-last-supper --export # 只导出prompt
"""
import argparse
import json
import os
import subprocess
import sys
import time
import base64
from datetime import datetime
from pathlib import Path

PROJECT_BASE = Path("/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects")
JIMENG_API = "http://127.0.0.1:8000"

def load_json(path):
    with open(path) as f: return json.load(f)

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f: f.write(text)

# ─── 即梦 API 调用 ──────────────────────────────────────────

def jimeng_generate(prompt, ref_image_b64=None, ratio="16:9", model="jimeng-5.0", save_name=None):
    """调用即梦 API 生成图片"""
    payload = {
        "model": model,
        "prompt": prompt,
        "ratio": ratio,
        "resolution": "2K",
    }
    if ref_image_b64:
        payload["images"] = [f"data:image/jpeg;base64,{ref_image_b64}"]
        payload["sample_strength"] = 0.7
    if save_name:
        payload["save_name"] = save_name

    import urllib.request
    req = urllib.request.Request(
        f"{JIMENG_API}/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_session_id()}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    
    # Extract image URLs
    images = []
    if "data" in result and result["data"]:
        for item in result["data"]:
            if "url" in item:
                images.append(item["url"])
    return images

def jimeng_video(prompt, ref_image_url=None, duration=5, save_name=None):
    """调用即梦视频生成 API"""
    payload = {
        "model": "jimeng-4.0",
        "prompt": prompt,
        "duration": duration,
    }
    if ref_image_url:
        payload["image_url"] = ref_image_url
    if save_name:
        payload["save_name"] = save_name

    import urllib.request
    req = urllib.request.Request(
        f"{JIMENG_API}/v1/videos/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_session_id()}"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    
    task_id = None
    if "data" in result and result["data"]:
        task_id = result["data"].get("task_id")
    return task_id

def get_session_id():
    """从 jimeng-stdio.py 配置文件读取 session_id"""
    cfg_path = Path.home() / ".openclaw/workspace/skills/director-storyboard/scripts/jimeng-stdio.py"
    if not cfg_path.exists():
        cfg_path = Path.home() / ".openclaw/workspace/scripts/jimeng-stdio.py"
    if cfg_path.exists():
        content = open(cfg_path).read()
        import re
        m = re.search(r'SESSION_ID\s*=\s*["\']([^"\']+)["\']', content)
        if m: return m.group(1)
    # Fallback: try env
    return os.environ.get("JIMENG_SESSION_ID", "")

# ─── Prompt 导出（选项B） ─────────────────────────────────

def export_prompts(panels, output_dir):
    """导出所有 image_prompt 和 video_prompt 到文本文件"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # image prompts
    img_lines = ["# Image Prompts — 关键帧描述\n", f"# 项目: {panels[0]['panel_id'][:3] if panels else 'N/A'}\n", f"# 生成时间: {datetime.now()}\n", "#" + "="*60 + "\n\n"]
    vid_lines = ["# Video Prompts — 分镜视频生成提示词\n", f"# 总时长: 估算 {sum(p.get('duration',5) for p in panels)}s\n\n"]

    for p in panels:
        pid = p["panel_id"]
        kfs = p.get("keyframes", [])
        
        img_lines.append(f"## {pid} | {p.get('beat_id','')} | {p.get('shot_type','')} | {p.get('camera_movement','')} | {p.get('duration',5)}s\n")
        img_lines.append(f"角色: {', '.join(p.get('characters', []))}\n")
        img_lines.append(f"色调: {p.get('dominant_color','')}\n")
        img_lines.append(f"光影: {p.get('lighting','')}\n")
        
        for kf in kfs:
            img_lines.append(f"\n  [{kf.get('frame_type','')}]\n")
            img_lines.append(f"  {kf.get('image_prompt','')}\n")
        
        img_lines.append("\n" + "-"*60 + "\n\n")
        
        # video prompt
        vid_lines.append(f"## {pid} | {p.get('duration',5)}s | {p.get('camera_movement','')}\n")
        vid_lines.append(f"  {p.get('video_prompt','')}\n\n")

    save_text(output_dir / "image_prompts.txt", "".join(img_lines))
    save_text(output_dir / "video_prompts.txt", "".join(vid_lines))
    
    # Also save structured JSON
    structured = []
    for p in panels:
        kf_list = []
        for kf in p.get("keyframes", []):
            kf_list.append({
                "frame_type": kf.get("frame_type", ""),
                "image_prompt": kf.get("image_prompt", "")
            })
        structured.append({
            "panel_id": p["panel_id"],
            "beat_id": p.get("beat_id", ""),
            "duration": p.get("duration", 5),
            "shot_type": p.get("shot_type", ""),
            "camera_movement": p.get("camera_movement", ""),
            "transition": p.get("transition", "cut"),
            "characters": p.get("characters", []),
            "character_prompts": p.get("character_prompts", []),
            "lighting": p.get("lighting", ""),
            "dominant_color": p.get("dominant_color", ""),
            "keyframes": kf_list,
            "video_prompt": p.get("video_prompt", "")
        })
    save_json(output_dir / "prompts_structured.json", structured)
    
    return output_dir

# ─── 图片生成（选项A） ─────────────────────────────────────

def download_image(url, save_path):
    """下载图片到本地"""
    import urllib.request
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(save_path, "wb") as f:
            f.write(resp.read())

def generate_images(panels, output_dir, max_retries=2):
    """为每个 panel 生成图片"""
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    for p in panels:
        pid = p["panel_id"]
        kfs = p.get("keyframes", [])
        
        for kf in kfs:
            ftype = kf.get("frame_type", "first_frame")
            prompt = kf.get("image_prompt", "")
            if not prompt:
                print(f"  ⚠️ {pid}/{ftype}: 无 prompt，跳过")
                continue
            
            save_name = f"{pid}_{ftype}.jpg"
            save_path = images_dir / save_name
            
            # 如果已有，跳过
            if save_path.exists():
                print(f"  ⏭️  {pid}/{ftype}: 已存在，跳过")
                results[f"{pid}_{ftype}"] = str(save_path)
                continue
            
            print(f"  🎨 {pid}/{ftype}: 生成中...")
            for attempt in range(max_retries):
                try:
                    imgs = jimeng_generate(prompt, save_name=save_name)
                    if imgs:
                        download_image(imgs[0], save_path)
                        print(f"    ✅ 保存到 {save_path}")
                        results[f"{pid}_{ftype}"] = str(save_path)
                        break
                    else:
                        print(f"    ⚠️  无返回结果，重试 {attempt+1}/{max_retries}")
                except Exception as e:
                    print(f"    ❌ 错误: {e}")
                    if attempt == max_retries - 1:
                        print(f"    ❌ {pid}/{ftype} 生成失败")
                    else:
                        time.sleep(5)
            
            time.sleep(2)  # 避免频率限制
        
        # 也为没有 keyframes 的 panel 生成一张总图
        if not kfs:
            prompt = p.get("video_prompt", p.get("scene_description", ""))
            if prompt:
                save_name = f"{pid}_panel.jpg"
                save_path = images_dir / save_name
                if not save_path.exists():
                    try:
                        imgs = jimeng_generate(prompt, save_name=save_name)
                        if imgs:
                            download_image(imgs[0], save_path)
                            print(f"  ✅ {pid}: 面板图已保存")
                    except Exception as e:
                        print(f"  ❌ {pid}: {e}")
    
    return results, images_dir

# ─── 视频生成（选项A） ─────────────────────────────────────

def generate_videos(panels, images_dir, output_dir, check_interval=30, max_wait=600):
    """为每个 panel 生成视频"""
    output_dir = Path(output_dir)
    videos_dir = output_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    for p in panels:
        pid = p["panel_id"]
        duration = p.get("duration", 5)
        video_prompt = p.get("video_prompt", "")
        
        save_name = f"{pid}_video.mp4"
        save_path = videos_dir / save_name
        
        if save_path.exists():
            print(f"  ⏭️  {pid}: 已存在，跳过")
            results[pid] = str(save_path)
            continue
        
        # 找到对应的图片
        ref_img_path = None
        for kf_type in ["first_frame", "last_frame"]:
            img_path = images_dir / f"{pid}_{kf_type}.jpg"
            if img_path.exists():
                ref_img_path = str(img_path)
                break
        if not ref_img_path:
            img_path = images_dir / f"{pid}_panel.jpg"
            if img_path.exists():
                ref_img_path = str(img_path)
        
        print(f"  🎬 {pid}: 视频生成中（参考图: {ref_img_path}）...")
        
        if ref_img_path:
            # 使用参考图生成视频
            with open(ref_img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            try:
                task_id = jimeng_video(
                    video_prompt,
                    ref_image_b64=img_b64,
                    duration=duration,
                    save_name=save_name
                )
                print(f"    📋 task_id: {task_id}（轮询等待完成...）")
                # 轮询等待
                status = wait_for_video(task_id, max_wait, check_interval)
                if status == "completed":
                    # 下载视频
                    video_url = get_video_url(task_id)
                    if video_url:
                        import urllib.request
                        req = urllib.request.Request(video_url)
                        with urllib.request.urlopen(req, timeout=60) as resp:
                            with open(save_path, "wb") as f:
                                f.write(resp.read())
                        print(f"    ✅ {pid} 视频已保存: {save_path}")
                        results[pid] = str(save_path)
                else:
                    print(f"    ⚠️  {pid} 视频状态: {status}")
            except Exception as e:
                print(f"    ❌ {pid} 错误: {e}")
        else:
            print(f"  ⚠️  {pid}: 无参考图，跳过视频生成")
    
    return results, videos_dir

def wait_for_video(task_id, max_wait, interval):
    """轮询等待视频生成完成"""
    import urllib.request
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            req = urllib.request.Request(
                f"{JIMENG_API}/v1/videos/generations/{task_id}",
                headers={"Authorization": f"Bearer {get_session_id()}"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            status = result.get("data", {}).get("status", "")
            if status == "completed":
                return "completed"
            elif status in ("failed", "error"):
                return status
            else:
                print(f"    ⏳ 状态: {status}，继续等待...")
        except Exception as e:
            print(f"    ⚠️  查询状态失败: {e}")
    return "timeout"

def get_video_url(task_id):
    """获取视频 URL"""
    import urllib.request
    req = urllib.request.Request(
        f"{JIMENG_API}/v1/videos/generations/{task_id}",
        headers={"Authorization": f"Bearer {get_session_id()}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result.get("data", {}).get("video_url", "")

# ─── 主入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="分镜图+视频生成工具")
    parser.add_argument("mode", choices=["prompt", "image", "video", "full"])
    parser.add_argument("--project", required=True, help="项目名（projects/下的目录名）")
    parser.add_argument("--export", action="store_true", help="导出prompt到文件（prompt模式）")
    parser.add_argument("--force", action="store_true", help="强制重新生成，跳过已有文件")
    args = parser.parse_args()

    project_dir = PROJECT_BASE / args.project
    if not project_dir.exists():
        print(f"❌ 项目不存在: {project_dir}")
        sys.exit(1)

    panels_data = load_json(project_dir / "panels.json")
    panels = panels_data.get("panels", [])

    print(f"\n{'='*60}")
    print(f"🎬 generate.py | 模式: {args.mode} | 项目: {args.project} | Panels: {len(panels)}")
    print(f"{'='*60}")

    if args.mode == "prompt":
        out_dir = project_dir / "exports"
        path = export_prompts(panels, out_dir)
        print(f"\n✅ Prompt 已导出到: {path}")
        print(f"   image_prompts.txt   — 关键帧描述（可直接复制到即梦/可灵）")
        print(f"   video_prompts.txt   — 视频生成提示词")
        print(f"   prompts_structured.json — 结构化数据")

    elif args.mode == "image":
        out_dir = project_dir / "output"
        results, images_dir = generate_images(panels, out_dir)
        print(f"\n✅ 图片生成完成: {len(results)} 张")
        print(f"   保存目录: {images_dir}")

    elif args.mode == "video":
        images_dir = project_dir / "output" / "images"
        if not images_dir.exists():
            print("❌ 需要先运行 image 模式生成图片")
            sys.exit(1)
        out_dir = project_dir / "output"
        results, videos_dir = generate_videos(panels, images_dir, out_dir)
        print(f"\n✅ 视频生成完成: {len(results)} 个")
        print(f"   保存目录: {videos_dir}")

    elif args.mode == "full":
        out_dir = project_dir / "output"
        
        # Step 1: Export prompts
        prompt_dir = project_dir / "exports"
        export_prompts(panels, prompt_dir)
        print(f"✅ Prompt 已导出: {prompt_dir}")
        
        # Step 2: Generate images
        print(f"\n🎨 Step 1/2: 生成关键帧图片...")
        img_results, images_dir = generate_images(panels, out_dir)
        print(f"✅ 图片生成完成: {len(img_results)} 张")
        
        # Step 3: Generate videos
        print(f"\n🎬 Step 2/2: 生成视频...")
        vid_results, videos_dir = generate_videos(panels, images_dir, out_dir)
        print(f"✅ 视频生成完成: {len(vid_results)} 个")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"🎉 全部完成!")
        print(f"{'='*60}")
        print(f"📁 项目目录: {project_dir}")
        print(f"📁 图片目录: {images_dir}")
        print(f"📁 视频目录: {videos_dir}")
        print(f"📁 Prompt导出: {prompt_dir}")

if __name__ == "__main__":
    main()
