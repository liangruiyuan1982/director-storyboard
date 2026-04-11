#!/usr/bin/env python3
"""快速诊断：单次 LLM 调用看原始返回"""
import sys
import json
import re
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-last-supper"
story_text = open(f"{PROJECT}/story.txt", encoding="utf-8").read()
intent = json.load(open(f"{PROJECT}/director_intent.json"))

# 简单诊断 prompt（只用 story_dna.md 的 SYSTEM_PROMPT 核心内容）
system = "你是一个专业的剧本分析师，负责将故事文本进行结构层面的深度诊断，输出 Story DNA。Story DNA 包含：三幕结构定位、叙事功能分析、情绪曲线、信息流动图。分析以下故事，输出 JSON 格式的 story_dna.json。只返回 JSON，不要其他文字。"

user = f"""分析以下故事文本，输出 story_dna.json。

【故事文本】
{story_text}

【导演意图】
- 故事标题：{intent['story_title']}
- 整体色调：{intent['q4_color_tone']}
- 旁白类型：{intent['q5_voiceover_type']}
- 时长目标：{intent['duration_target']}

请输出 JSON 格式，包含以下字段：
- story_title
- structure_summary（1-2句话描述整体结构）
- three_act_structure（act_1_end_beat, turning_point_1, turning_point_2, act_3_start_beat, total_beats_estimated）
- narrative_functions（每个 beat 的 function 和 description）
- emotion_curve（每个 beat 的 emotion, intensity, note）
- information_flow（每个 beat 的 what_audience_knows, what_character_knows, information_gap）
- key_dramatic_moments（转折点列表）
- emotional_climax（情感高潮 beat_id）

只返回 JSON，不要解释。"""

print(f"Story: {len(story_text)} chars")
print("⏳ 调用 GLM-5.1...")
result = call_api("glm51", system, user, max_tokens=8192)
text = result.content if hasattr(result, 'content') else str(result)
print(f"\n原始返回 ({len(text)} chars):\n{text[:1000]}")
print(f"\n[{'JSON 提取成功' if re.search(r'```json', text) or text.strip().startswith(('{','[')) else 'JSON 提取失败'}]")
