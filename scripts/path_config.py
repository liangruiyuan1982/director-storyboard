from pathlib import Path
from typing import Optional
import os
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
WORKSPACE_DIR = SKILL_DIR.parent.parent
DEFAULT_PROJECTS_DIR = SKILL_DIR / "projects"
EXTERNAL_PROJECTS_DIR = WORKSPACE_DIR / "skill-data" / "director-storyboard" / "projects"
PROJECTS_DIR = EXTERNAL_PROJECTS_DIR if EXTERNAL_PROJECTS_DIR.exists() else DEFAULT_PROJECTS_DIR
AI_STORYBOARD_SCRIPTS = SKILL_DIR.parent / "ai-storyboard-pro" / "scripts"


def add_ai_storyboard_to_path():
    path = str(AI_STORYBOARD_SCRIPTS)
    if path not in sys.path:
        sys.path.insert(0, path)
    return AI_STORYBOARD_SCRIPTS


def resolve_project(project: Optional[str] = None, default_name: Optional[str] = None) -> Path:
    if project:
        p = Path(project).expanduser()
        if p.is_absolute() or "/" in project:
            return p
        return PROJECTS_DIR / project
    if default_name:
        return PROJECTS_DIR / default_name
    return PROJECTS_DIR
