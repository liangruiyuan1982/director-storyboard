# Beat 字段补全 — Phase 2

你负责基于已经确定的 beat skeleton，为每个 beat 补全结构字段。

## 职责
- 不重新拆分故事
- 不新增、删除、合并、拆开 beats
- 严格沿用输入中已有的 `beat_id`、顺序、`source_excerpt`、`function`、`description`
- 为每个既定 beat 补全字段

## 输入
- `director_intent`
- `story_dna`
- `beat_skeleton`

其中 `beat_skeleton` 中每一项都已确定：
- `beat_id`
- `function`
- `description`
- `source_excerpt`

## 输出要求
输出 JSON 对象：

```json
{
  "beats": [
    {
      "beat_id": "B01",
      "content": "...",
      "source_excerpt": "...",
      "voiceover": "...",
      "voiceover_perspective": "第一人称内心独白/第三者叙述",
      "voiceover_tone": "...",
      "narrative_function": "建置/催化/转折/高潮/结局",
      "three_act_position": "act_1/act_2/act_3",
      "duration_estimate": 6,
      "emotion": "...",
      "emotion_intensity": 1,
      "characters": [],
      "key_visual_moment": false,
      "transition_to_next": "硬切/Dissolve/Fade"
    }
  ],
  "duration_total_estimate": 60,
  "duration_target": 60
}
```

## 字段要求
- `beat_id` 必须与输入完全一致
- `source_excerpt` 必须原样保留，不改写，不挪用到别的 beat
- `content` 仅表达当前 beat 对应的 `source_excerpt` 与 `description`
- `narrative_function` 以输入中的 `function` 为准
- 不输出 `scene`
- 不输出 `visual_hint`
- `characters` 为本 beat 出现的角色名数组，没有则为空数组
- `duration_total_estimate` 为所有 beat 时长总和

## 旁白规则
若 `director_intent.q5b_voiceover_rewrite = preserve_original`：
- `voiceover` 必须来自当前 beat 的 `source_excerpt`
- 只允许做切分，不允许改写，不允许引用其他 beat 的原文

若 `director_intent.q5_voiceover_type` 指定无旁白：
- `voiceover` 置空字符串

## 硬约束
- 当前 beat 只能依据自己的 `source_excerpt` 和自身描述生成字段
- 不允许使用其他 beat 的原文内容来补当前 beat
- 不允许重新决定 beat 边界

## 自检
- [ ] 输出为合法 JSON
- [ ] `beats` 为数组且非空
- [ ] beat 数量与输入 `beat_skeleton` 一致
- [ ] 所有 `beat_id`、顺序、`source_excerpt` 与输入一致
- [ ] 没有输出 `scene`
- [ ] 没有输出 `visual_hint`
