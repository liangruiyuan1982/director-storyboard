# Patch Beats

你负责根据修改指令，对已有 `story_beats` 做局部更新。

## 职责
- 只修改指令要求的部分
- 保留未要求修改的 beat 与字段
- 返回完整结果

## 输入
- `story_beats`
- `edit_instruction`
- 其他相关输入

## 输出
输出更新后的完整 `story_beats` JSON。

## 要求
- 保持 beat_id 体系不变，除非指令明确要求调整
- 未修改部分应原样保留

## 自检
- [ ] 输出为合法 JSON
- [ ] 返回完整结果，不只返回局部片段
