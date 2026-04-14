#!/usr/bin/env python3
"""快速测试 Phase 1-3 的 LLM 调用"""
import sys
import json
import re
sys.path.insert(0, "/Users/liangruiyuan/.openclaw/workspace/skills/ai-storyboard-pro/scripts")
from api import call_api

SKILL_DIR = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard"
PROJECT = "/Users/liangruiyuan/.openclaw/workspace/skills/director-storyboard/projects/test-last-supper"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_json(text):
    """Extract JSON from LLM response text"""
    # Try ```json ... ``` first
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
    if m:
        return m.group(1).strip()
    # Try finding first { or [
    for start_char in ['{', '[']:
        idx = text.find(start_char)
        if idx >= 0:
            # Try to find matching close
            close = '}' if start_char == '{' else ']'
            depth = 0
            end_idx = -1
            for i, c in enumerate(text[idx:], idx):
                if c == start_char:
                    depth += 1
                elif c == close:
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                return text[idx:end_idx]
    return None

def call_model(model_key, system, user_prompt, max_tokens=8192):
    result = call_api(model_key, system, user_prompt, max_tokens=max_tokens)
    # api.py returns (text, elapsed, usage) tuple
    text = result[0] if isinstance(result, tuple) else result
    json_str = extract_json(text)
    if json_str:
        return json.loads(json_str)
    print(f"  [DEBUG] raw response:\n{text[:800]}")
    raise ValueError(f"无法从响应中提取JSON")

def read_ref(name):
    with open(f"{SKILL_DIR}/references/{name}", encoding="utf-8") as f:
        return f.read()

print("=" * 60)
print("🎬 Phase 1: Story DNA 分析")
print("=" * 60)

story_text = open(f"{PROJECT}/story.txt", encoding="utf-8").read()
intent = load_json(f"{PROJECT}/director_intent.json")

system = "你是一个专业的剧本分析师。输出JSON，只返回JSON，不要其他文字。"
user = read_ref("story_dna.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_text': story_text, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print(f"Story length: {len(story_text)} chars")
print(f"Intent: {intent['story_title']}")
print("⏳ 调用 GLM-5.1...")

dna = call_model("glm51", system, user)
save_json(f"{PROJECT}/story_dna.json", dna)
print(f"✅ Phase 1 完成")
if "narrative_functions" in dna:
    for bid, info in list(dna["narrative_functions"].items())[:5]:
        print(f"   {bid}: {info.get('function','')} - {info.get('description','')[:40]}")
print(f"   三幕: Act1到{list(dna.get('narrative_functions',{}).keys())[-1] if dna.get('narrative_functions') else '?'}")
print(f"   情感高潮: {dna.get('emotional_climax', 'N/A')}")

print("\n" + "=" * 60)
print("🎬 Phase 2: Beat 可视化规划")
print("=" * 60)

user2 = read_ref("beat_analysis.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_text': story_text, 'story_dna': dna, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
beats = call_model("glm51", system, user2)
save_json(f"{PROJECT}/story_beats.json", beats)
beat_list = beats.get("beats", [])
print(f"✅ Phase 2 完成: {len(beat_list)} beats")
total_dur = sum(b.get("duration_estimate", 5) for b in beat_list)
print(f"   估算总时长: {total_dur}s (目标: {intent['duration_target']})")
for b in beat_list:
    scene = b.get('scene', 'N/A')
    mood = b.get('mood', b.get('emotion', 'N/A'))
    dur = b.get('duration_estimate', 5)
    vh = b.get('visual_hint', '')[:50]
    vo = b.get('voiceover', '')[:30]
    key_mark = "⭐" if b.get('key_visual_moment') else "  "
    print(f"   {key_mark}{b.get('beat_id','')} [{b.get('narrative_function','')}] {mood}|{dur}s|{scene}")
    print(f"       🎥 {vh}...")
    if vo:
        print(f"       🎤 {vo}...")

print("\n" + "=" * 60)
print("🎬 Phase 3a: 角色档案")
print("=" * 60)

user3 = read_ref("character_card.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'story_text': story_text, 'story_dna': dna, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
chars = call_model("glm51", system, user3)
save_json(f"{PROJECT}/characters.json", chars)
print(f"✅ Phase 3a 完成: {len(chars.get('characters', []))} characters")
for c in chars.get("characters", []):
    vnf = c.get('visual_narrative_function', '')[:80]
    dvp = c.get('director_visual_priority', '')[:60]
    print(f"   {c.get('name','')} [{c.get('role_level','')}] - {c.get('occupation','')}")
    if vnf:
        print(f"     视觉叙事功能: {vnf}...")
    if dvp:
        print(f"     导演优先级: {dvp}...")

print("\n" + "=" * 60)
print("🎬 Phase 3b: 角色视觉描述")
print("=" * 60)

user4 = read_ref("character_visual.md") + f"\n\n## 输入数据\n```json\n{json.dumps({'characters': chars, 'director_intent': intent}, ensure_ascii=False)}\n```\n\n请输出JSON。"

print("⏳ 调用 GLM-5.1...")
visuals = call_model("glm51", system, user4)
save_json(f"{PROJECT}/character_visuals.json", visuals)
print(f"✅ Phase 3b 完成")
for cv in visuals.get("character_visuals", []):
    for app in cv.get("appearances", []):
        desc = app["descriptions"][0][:120] if app["descriptions"] else "N/A"
        print(f"   {cv['name']} [id={app['id']}]: {desc}...")

print("\n" + "=" * 60)
print("✅ Phase 1-3 快速测试完成！")
print("=" * 60)
