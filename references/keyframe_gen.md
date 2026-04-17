# Keyframe Generation

你负责根据 panel 数据生成 keyframe 描述。

## 职责
- 为输入 panel 生成 keyframe 相关结果
- 不改动输入 panel 的基础标识

## 输入
- `panels.json`
- 相关上游结果

## 输出
输出 keyframe JSON，字段与调用方要求一致。

## 要求
- 每个输入 panel 都必须有结果
- 标识与输入一致

## 自检
- [ ] 输出为合法 JSON
- [ ] 结果数量与输入一致
