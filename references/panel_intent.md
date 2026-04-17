# Panel Intent — Phase 4e

你负责基于已有阶段结果，为每个 panel 生成结构化 intent 信息。

## 职责
- 汇总上游信息
- 为每个 panel 生成 intent 字段
- 不改动 panel 顺序

## 输入
- `story_beats.json`
- 其他上游阶段输出

## 输出
输出 panel intent JSON，字段应与调用方要求一致。

## 要求
- 每个输入 panel/beat 都必须有对应输出
- 保持标识一致
- 不增删输入项

## 自检
- [ ] 输出为合法 JSON
- [ ] 输入项与输出项一一对应
