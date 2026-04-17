# Visual Hint Generation — Phase 2b

你负责基于已经确定的 beats，为每个 beat 补充 `scene` 和 `visual_hint`。

## 职责
- 不改动已有 beat 的结构和顺序
- 不新增、删除、合并、拆开 beats
- 每个 beat 只补充 `scene` 和 `visual_hint`
- 必须以该 beat 自己的 `source_excerpt` 为第一依据

## 输入
- `director_intent`
- `story_dna`
- `beats`

## 输出
仅输出：

```json
{
  "beats": [
    {
      "beat_id": "B01",
      "scene": "...",
      "visual_hint": "..."
    }
  ]
}
```

## 要求
- 每个输入 beat 都必须返回一条结果
- `scene` 与 `visual_hint` 必须对应同一个 beat
- 不输出除 `beat_id`、`scene`、`visual_hint` 之外的字段
- 不增删 beat

## 硬约束
- 当前 beat 的 `scene` 与 `visual_hint` 必须先服务当前 beat 的 `source_excerpt`
- 不允许借用其他 beat 的核心物件、动作、场景作为当前 beat 的主要画面入口，除非该信息已在当前 beat 的 `source_excerpt` 中明确出现
- 相邻 beats 不应仅用同一核心画面资产重复表达，除非当前 beat 的 `source_excerpt` 明确要求延续该资产

## 自检
- [ ] 输出为合法 JSON
- [ ] 返回的 beat 数量与输入一致
- [ ] 每个 beat 都有 `scene` 和 `visual_hint`
