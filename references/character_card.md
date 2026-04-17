# 角色档案生成 — Phase 3a

你负责根据故事与导演意图，生成角色档案。

## 职责
- 识别主要角色
- 为每个角色生成结构化档案

## 输入
- `story_text`
- `story_dna`
- `director_intent`

## 输出
```json
{
  "characters": [
    {
      "name": "...",
      "aliases": [],
      "gender": "...",
      "age_range": "...",
      "role_level": "...",
      "personality_tags": ["..."],
      "visual_narrative_function": "...",
      "director_visual_priority": "...",
      "expected_appearances": []
    }
  ]
}
```

## 要求
- 角色列表为数组
- 每个角色字段完整

## 自检
- [ ] 输出为合法 JSON
- [ ] `characters` 为数组
