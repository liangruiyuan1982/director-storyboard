# 导演审核清单 — 每个 Gate 前执行

## Gate 1 审核（Beat 方案确认）

审核对象：`story_beats.json`

### 结构审核
- [ ] beat 数量与 story_dna.json 的 total_beats_estimated 匹配（差距 ≤ 2）
- [ ] 三幕分布合理（Act1 约 25%，Act2 约 50%，Act3 约 25%）
- [ ] 转折点位置与 story_dna.json 一致

### 视觉审核
- [ ] 每个 visual_hint 包含景别词
- [ ] scene 字段全部是真实可拍摄地点
- [ ] 无抽象心理词（"感到温暖""内心平静"等）
- [ ] 连续相同 scene 的 beat 没有不当拆分

### 时长审核
- [ ] duration_total_estimate 与 duration_target 差距 < 20%
- [ ] 高潮 beat 的 duration_estimate 高于周围 beat

### 叙事审核
- [ ] voiceover 不是 content 的逐字复制
- [ ] narrative_function 与 story_dna.json 一致
- [ ] key_visual_moments 被正确标记

---

## Gate 2 审核（角色 + 场景设计确认）

审核对象：`characters.json` + `character_visuals.json`

### 角色完整性
- [ ] 所有出场角色（S/A/B/C/D 级）都被提取
- [ ] aliases 覆盖原文所有代词
- [ ] 无群众演员被错误提升为 B/C 级

### 视觉功能
- [ ] S/A 级角色都有 visual_narrative_function
- [ ] S/A 级角色都有 director_visual_priority
- [ ] director_visual_priority 是辨识策略，不是外貌描述

### 外观一致性
- [ ] 鞋子描述存在
- [ ] 无皮肤/眼睛/唇色描写
- [ ] id=1/2 的前30字与 id=0 一致
- [ ] 服装描述与 suggested_colors 匹配

---

## Gate 3 审核（摄影 + 表演确认）

审核对象：`photography.json` + `acting.json`

### 摄影审核
- [ ] shot_type 只使用中文分镜词库
- [ ] 特写镜头不超过总 beat 数的 40%
- [ ] camera_movement 与 Q1 影像风格一致
- [ ] color_temperature 与 color_script.json 一致
- [ ] 每个 shot 有 color_note 引用 color_script

### 表演审核
- [ ] performance_notes 用行为动词，不用状态词
- [ ] emotional_subtext 有"字面/潜台词"格式
- [ ] performance_directive 是行动方向，不是描述
- [ ] facial_expression 描述物理变化
- [ ] 无运镜描述在 performance_notes/body_language 中

---

## Gate 4 审核（图像确认）

审核对象：`panels.json`（含 keyframes）

### prompt 质量
- [ ] 每个 image_prompt 包含七层完整描述
- [ ] 首帧与尾帧前30字不同
- [ ] 人物外貌从 character_visuals 逐字复制
- [ ] 光影描述与 color_script 一致
- [ ] 帧数与 camera_movement 匹配

### 一致性
- [ ] 同一角色在不同 panel 中外观一致
- [ ] color_script 的色调策略被正确执行
- [ ] transition 类型符合 Q6 选择

---

## 审核后的操作

审核完成后，填写审核结论：

```json
{
  "gate": "Gate 2",
  "project": "xxx",
  "timestamp": "2026-04-11T12:00:00+08:00",
  "decision": "confirmed / needs_revision / needs_discussion",
  "issues": [
    {
      "severity": "critical / major / minor",
      "location": "B03/beat/visual_hint",
      "issue": "描述具体问题",
      "suggested_fix": "建议的修改方向"
    }
  ],
  "notes": "（导演自由备注）"
}
```

如果 decision = "needs_revision"，修改完成后重新提交审核。

如果 decision = "needs_discussion"，通过飞书与导演讨论具体问题后再决定。
