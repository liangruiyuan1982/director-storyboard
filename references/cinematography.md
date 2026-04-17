# 摄影设计 — Phase 4c

你负责为每个 beat 生成摄影相关字段。

## 职责
- 生成全局摄影风格信息
- 为每个 beat 生成对应 shot 信息
- 不改动输入 beat 的结构与顺序

## 输入
- `story_beats`
- `color_script`
- `director_intent`

## 输出
```json
{
  "global_style": {
    "imaging_style": "...",
    "narrative_distance": "..."
  },
  "shots": [
    {
      "beat_id": "B01",
      "shot_type": "...",
      "camera_movement": "...",
      "lighting": "...",
      "depth_of_field": "...",
      "color_temperature": 5600
    }
  ]
}
```

## 要求
- 每个输入 beat 都必须返回一条 `shots` 记录
- `beat_id` 必须与输入一致
- 仅输出 `global_style` 和 `shots`

## 自检
- [ ] 输出为合法 JSON
- [ ] `shots` 数量与输入 beat 数一致
- [ ] 每条 shot 都包含必要字段
