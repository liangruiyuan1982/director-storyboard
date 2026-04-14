from datetime import datetime
from pathlib import Path
import json
import time


GATE_STEP_MAP = {
    "Gate 0": "phase2_beats",
    "Gate 1": "phase3_characters",
    "Gate 2": "phase4e_panels",
}

GATE_FILE_MAP = {
    "Gate 0": ".gate_0.json",
    "Gate 1": ".gate_1.json",
    "Gate 2": ".gate_2.json",
    "Gate 3": ".gate_3.json",
}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def gate_file_path(project_dir, gate_name):
    return Path(project_dir) / GATE_FILE_MAP[gate_name]


def build_gate_state(project_dir, gate_name, preview_file=None):
    project_name = Path(project_dir).name
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
    return {
        "project": project_name,
        "gate_name": gate_name,
        "status": "waiting",
        "timestamp": str(datetime.now()),
        "preview_file": str(Path(project_dir) / preview_file) if preview_file else None,
        "summary": info["summary"],
        "needs": info["needs"],
        "options": info["options"],
    }


def init_gate(project_dir, gate_name, preview_file=None):
    state = build_gate_state(project_dir, gate_name, preview_file=preview_file)
    save_json(gate_file_path(project_dir, gate_name), state)
    return state


def wait_gate_response(project_dir, gate_name, timeout_ms=300000):
    gate_file = gate_file_path(project_dir, gate_name)
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        if gate_file.exists():
            state = load_json(gate_file)
            if state.get("status") != "waiting":
                return state.get("choice", "confirm")
        time.sleep(5)
    return "timeout"


def resolve_gate_choice(project_dir, gate_name, choice, update_review_status):
    gate_file = gate_file_path(project_dir, gate_name)
    state = load_json(gate_file) if gate_file.exists() else {}
    step_key = GATE_STEP_MAP.get(gate_name)

    if choice == "confirm":
        state["status"] = "confirmed"
        state["choice"] = "confirm"
        save_json(gate_file, state)
        if step_key:
            update_review_status(project_dir, step_key, "approved")
        return "continue"

    if choice in ("modify", "regen_dna", "regen_beats", "regen", "regen_keyframes"):
        state["status"] = "awaiting_detail"
        state["pending_choice"] = choice
        save_json(gate_file, state)
        if step_key:
            update_review_status(project_dir, step_key, "awaiting_detail")
        return "await_detail"

    if choice == "timeout":
        return "continue"

    return "continue"
