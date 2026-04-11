---
name: director-storyboard
description: 专业导演分镜系统。以导演创作意图为核心，5-phase  pipeline 将故事文本转化为可视化分镜看板。核心差异：前置"导演意图问卷"、结构化决策门（Gate）、色彩脚本（Color Script）、批注层。当用户提到"分镜"、"导演分镜"、"视频脚本"、"小说转视频"、需要专业级分镜制作流程、或要求"有导演思维的分镜工具"时触发。
---

# Director Storyboard — 以导演意志为核心的分镜系统

## 核心理念（一句话）

**这个工具的目的不是"把文字变成图"，而是帮助导演在视觉化之前，先把自己的创作意图想清楚。**

所有流程设计都围绕一个原则：每一步 AI 的输出，都是导演意志的延伸，而不是 LLM 的自说自话。

---

## 与 ai-storyboard-pro 的核心区别

| 维度 | ai-storyboard-pro | director-storyboard（这个工具） |
|------|------------------|-------------------------------|
| 起点 | 故事文本 | 导演意图 + 故事文本 |
| 流程 | 6步线性，无决策门 | 5 Phase + 4 个导演决策门 |
| voiceover | 代码复制 content | LLM 基于叙事视角重新生成 |
| 色彩 | 无 | 独立 Color Script 环节 |
| viewer | 分镜展示 | 导演工作台（批注+版本+导出） |
| 角色造型 | 纯外观描述 | 外观 + 角色视觉叙事功能定位 |
| 迭代 | 无 | 支持指定 step 重跑 |

---

## 5 Phase + 4 Gate 流程总览

```
Phase 0 · 导演意图捕获
  用户输入 story.txt → 完成意图问卷 → 两者结合输入后续流程
        ↓ [Gate 0: 意图确认]

Phase 1 · Story DNA 分析
  结构诊断（三幕坐标 + 叙事功能 + 情绪曲线 + 信息流）
        ↓ [Gate 1: 结构确认]

Phase 2 · Beat 可视化规划
  叙事功能标注 + visual_hint 生成（含景别/光影/色调）
        ↓ [Gate 2: Beat 方案确认]

Phase 3 · 角色 + 场景设计
  角色卡（外观+视觉叙事功能）+ 场景视觉基调
        ↓ [Gate 3: 视觉方向确认]

Phase 4 · 摄影 + 表演 + 分镜合成
  Color Script + Photography + Acting + 分镜组装 + 关键帧
        ↓ [Gate 4: 图像确认]

Phase 5 · 成片输出
  分镜看板（HTML）+ 拍摄参数表 + Color Script 文档
```

---

## 项目目录结构

```
projects/{story-name}/
├── story.txt                    # 原始故事文本
├── director_intent.json         # Phase 0 输出（意图问卷答案）
├── story_dna.json               # Phase 1 输出（结构分析）
├── story_beats.json             # Phase 2 输出（Beat 方案）
├── characters.json              # Phase 3a 输出（角色档案）
├── character_visuals.json       # Phase 3b 输出（外貌+视觉功能）
├── color_script.json            # Phase 4a 输出（色彩叙事）
├── photography.json             # Phase 4b 输出（摄影参数）
├── acting.json                  # Phase 4c 输出（表演指令）
├── panels.json                  # Phase 4d 输出（分镜组装+关键帧）
├── viewer.html                  # Phase 5 输出（分镜看板）
└── pipeline_progress.json       # 断点续跑状态
```

---

## Phase 0 · 导演意图捕获

### 输入
- `story.txt`：用户提供的故事文本（200-2000字）
- `意图问卷`：用户回答 6 个结构化问题

### 意图问卷（6 题）

| # | 问题 | 选项 | 影响 |
|---|------|------|------|
| Q1 | 整体影像风格？ | A. 纪实/手持感（现实主义）B. 精致/稳定（古典主义）C. 戏剧化/强对比（表现主义） | camera_movement 基准策略 |
| Q2 | 叙事距离？ | A. 亲密（大量特写）B. 中距（观察式）C. 疏离（全景为主） | shot_type 分布策略 |
| Q3 | 时间感？ | A. 紧迫（短镜头快切）B. 正常（自然节奏）C. 延展（长镜头慢节奏） | duration_estimate 基准 |
| Q4 | 整体色调？ | A. 冷色系 B. 暖色系 C. 低饱和/消色 D. 高对比/强烈 | color_temperature 全局基调 |
| Q5 | 旁白类型？ | A. 第一人称内心独白 B. 第三者叙述 C. 无旁白 | voiceover 生成逻辑 |
| Q6 | 过渡哲学？ | A. 硬切（现代/简洁）B. Dissolve（柔和/记忆感）C. Fade（时间断裂/诗意）D. Mix（混合使用） | transition 默认策略 |

### 输出
`director_intent.json`

```json
{
  "story_title": "（从 story.txt 提取或用户命名）",
  "q1_imaging_style": "精致/稳定",
  "q2_narrative_distance": "亲密",
  "q3_time_sense": "正常",
  "q4_color_tone": "冷色系",
  "q5_voiceover_type": "第一人称内心独白",
  "q6_transition_philosophy": "硬切",
  "additional_notes": "（用户自由补充的导演笔记）",
  "duration_target": "60s",
  "key_visual_moments": ["（用户指定的关键视觉场景，最重要 1-3 个）"]
}
```

### 执行方式
问卷在飞书消息中通过 `ask_user_question` 工具发送，用户完成后答案写入 `director_intent.json`。

---

## Phase 1 · Story DNA 分析

### 输入
- `story.txt`
- `director_intent.json`

### 参考文档
`references/story_dna.md`

### 输出
`story_dna.json`

```json
{
  "three_act_structure": {
    "act_1_beats": ["B01", "B02", "B03"],
    "turning_point_1": "B03",
    "act_2_beats": ["B04", "B05", "B06", "B07"],
    "turning_point_2": "B07",
    "act_3_beats": ["B08", "B09"]
  },
  "narrative_functions": {
    "B01": {"function": "建置", "description": "建立主角日常世界"},
    "B02": {"function": "催化", "description": "打破日常平衡的事件"},
    ...
  },
  "emotion_curve": [
    {"beat": "B01", "emotion": "平静", "intensity": 3, "note": "日常感"},
    {"beat": "B02", "emotion": "紧张", "intensity": 6, "note": "事件介入"},
    ...
  ],
  "information_flow": [
    {"beat": "B01", "what_audience_knows": ["A在日常中"], "what_character_knows": ["A知道自己被困"]},
    ...
  ]
}
```

### LLM 调用
- 模型：glm51 或 kimi25
- Prompt：见 `references/story_dna.md`

---

## Phase 2 · Beat 可视化规划

### 输入
- `story.txt`
- `story_dna.json`
- `director_intent.json`

### 参考文档
`references/beat_analysis.md`

### 输出
`story_beats.json`

每个 beat 的关键字段：

```json
{
  "beat_id": "B01",
  "content": "原文片段（逐字复制）",
  "voiceover": "旁白内容（由LLM基于Q5旁白类型重新生成，不是直接复制）",
  "voiceover_perspective": "第一人称/第三者叙述/无旁白",
  "voiceover_tone": "冷静/温暖/犹豫/紧迫",
  "scene": "具体摄影可到达的场景地点",
  "narrative_function": "建置/催化/发展/高潮/结局",
  "duration_estimate": 4,
  "visual_hint": "景别+主体+光影+色调（40-80字，必须可拍摄）",
  "emotion": "单一情绪词",
  "key_visual_moment": true,
  "mood": "单个情绪词"
}
```

### Gate 2：导演确认 Beat 方案
- 生成 `beats-viewer.html` 供导演预览
- 导演可要求：调整 beat 边界、修改 visual_hint、合并/拆分 beat、调整时长
- 确认后进入 Phase 3

---

## Phase 3 · 角色 + 场景设计

### Phase 3a · 角色档案

### 输入
- `story.txt`
- `story_dna.json`
- `director_intent.json`

### 参考文档
`references/character_card.md`

### 输出
`characters.json`

**每个角色包含两个新字段**：
- `visual_narrative_function`：这个角色在每个场景中的视觉叙事功能（是压迫者还是被压迫者？是观察者还是被观察者？）
- `director_visual_priority`：导演最希望这个角色被观众记住的视觉特征

```json
{
  "characters": [
    {
      "name": "角色名",
      "aliases": [],
      "visual_narrative_function": "（这场戏里，这个角色承担什么视觉叙事功能？）",
      "director_visual_priority": "（如果只能保留一个视觉特征，是什么？）",
      "introduction": "身份+性格底色+角色关系",
      "gender": "男/女",
      "age_range": "约XX岁",
      "role_level": "S/A/B/C/D",
      "personality_tags": [],
      "era_period": "现代都市",
      "occupation": "职业",
      "costume_tier": 2,
      "suggested_colors": ["主色调", "辅色调"],
      "primary_identifier": "S/A级必填-辨识标志",
      "expected_appearances": [
        {"id": 0, "change_reason": "初始形象"}
      ]
    }
  ]
}
```

### Phase 3b · 角色视觉描述

### 参考文档
`references/character_visual.md`

### 输出
`character_visuals.json`

**结构同 ai-storyboard-pro**，但额外增加：
- `visual_function_note`：这个 appearance 在叙事上的功能（如"破败感暗示角色的社会边缘位置"）
- 每条 description 必须包含：面部特征(40%)、发型、体态、服装配饰（鞋子必填）

---

### Gate 3：导演确认角色方向

- 输出角色卡汇总（每角色一张视觉卡，含外观+视觉叙事功能定位）
- 导演确认后才进入 Phase 4

---

## Phase 4 · 摄影 + 表演 + 分镜合成

### Phase 4a · Color Script（新增核心模块）

### 输入
- `story_beats.json`
- `director_intent.json`

### 参考文档
`references/color_script.md`

### 输出
`color_script.json`

```json
{
  "global_emotion_tone": "（从 Q4 映射）",
  "beats": [
    {
      "beat_id": "B01",
      "dominant_color": "冷蓝灰",
      "narrative_function": "建立世界的压抑感和秩序感",
      "visual_metaphor": "角色被困在冷色秩序中",
      "transition_to_next": "微妙的色调渐暖（暗示变化即将到来）"
    }
  ]
}
```

---

### Phase 4b · 摄影参数

### 输入
- `story_beats.json`
- `color_script.json`
- `director_intent.json`

### 参考文档
`references/cinematography.md`

### 输出
`photography.json`

```json
{
  "global_style": {
    "color_grade": "（来自 color_script 全局基调）",
    "aspect_ratio": "16:9",
    "resolution": "2K",
    "imaging_style": "（来自 Q1）",
    "transition_philosophy": "（来自 Q6，硬切/dissolve/fade）"
  },
  "shots": [
    {
      "beat_id": "B01",
      "shot_type": "中景",
      "camera_movement": "固定",
      "lighting": "侧窗自然光，柔和漫射",
      "depth_of_field": "浅景深 f/2.8-f/4.0",
      "color_temperature": "5500K",
      "color_note": "（来自 color_script 的 dominant_color 映射）"
    }
  ]
}
```

---

### Phase 4c · 表演指令

### 输出
`acting.json`

规则基本沿用 ai-storyboard-pro，但增加：
- `emotional_subtext`：这场戏的潜台词（给演员的内部创作依据）
- `performance_directive`：导演给演员的核心表演指示（1句话）

---

### Phase 4d · 分镜组装（代码）

### 输入
全部 Phase 1-4 的输出文件

### 逻辑
沿用并增强 ai-storyboard-pro Step 4 的组装逻辑，主要升级：
- `transition` 不再硬编码为 "cut"，而是根据 `Q6` 和 `color_script` 的 `transition_to_next` 动态生成
- voiceover 直接从 `story_beats.json` 读取（Phase 2 已由 LLM 生成）
- `video_prompt` 格式升级：增加 `emotion_tone` 字段（来自 color_script）

---

### Phase 4e · 关键帧生成

### 参考文档
`references/keyframe_gen.md`

### 输出
`panels.json`（追加 keyframes 数组）

---

## Phase 5 · 成片输出

### viewer.html（导演工作台）

在 ai-storyboard-pro 的 viewer.html 基础上，增加：

| 功能 | 说明 |
|------|------|
| 批注层 | 每帧可输入导演批注（存储到 panels.json） |
| 版本记录 | 保留历史版本快照（供对比） |
| 角色卡悬浮 | 鼠标悬停角色名显示角色卡 |
| Color Script 可视化 | 色彩情绪曲线可折叠展示 |
| 导出 PDF | 含批注的导演版分镜 |

---

## Pipeline 命令

```bash
cd ~/.openclaw/workspace/skills/director-storyboard/scripts

# 全流程（带意图问卷）
python3 pipeline.py full --story /path/to/story.txt

# 指定 Phase 重跑（保留其他 Phase 结果）
python3 pipeline.py 4 --project projects/xxx   # 重跑 Phase 4（Color Script + 摄影 + 分镜）
python3 pipeline.py 4e --project projects/xxx # 仅重跑关键帧生成

# 查看进度
python3 pipeline.py status --project projects/xxx
```

### 模型配置

| 参数 | 模型 | 适用 Phase |
|------|------|-----------|
| `--model glm51` | GLM-5.1 | 所有 LLM 调用（推荐） |
| `--model kimi25` | Kimi K2.5 | 备选 |
| `--model gemma4` | Gemma 4 26B | 本地免费，质量略低 |

---

## 导演决策门操作规范

**每个 Gate 的操作方式**：

1. 当前 Phase 完成后，暂停 pipeline
2. 生成该 Phase 的预览文件（HTML 或结构化摘要）
3. 通过飞书发送给导演
4. 导演确认或提出修改意见
5. 修改完成后，pipeline 继续

**Gate 确认才算完成，否则不得进入下一 Phase**

**修改循环**：每次修改完成后重新发送确认，循环直到导演说"确认"或"可以了"

---

## 质量自检清单

每 Phase 输出后，Agent 必须逐项检查：

- [ ] JSON 格式正确（双引号、JSON.parse 验证通过）
- [ ] 无任何字段为空字符串（除非规范明确允许）
- [ ] beat/panel 数量与输入一致
- [ ] scene 字段全部为具体地点，无抽象词
- [ ] mood 为单一情绪词（无顿号/逗号）
- [ ] 禁止皮肤/眼睛/唇色描写
- [ ] 鞋子描述必填
- [ ] 角色 aliases 完整（覆盖原文所有代词）
- [ ] voiceover 与 content 不是简单复制关系（需 LLM 重新生成判断）

---

## 详细参考文档索引

| 文档 | 内容 | 何时读取 |
|------|------|---------|
| `references/intent_questionnaire.md` | 意图问卷的详细说明和设计依据 | Phase 0 开始前 |
| `references/story_dna.md` | Story DNA 分析的 prompt 和输出规范 | Phase 1 |
| `references/beat_analysis.md` | Beat 生成 prompt 和 visual_hint 规范 | Phase 2 |
| `references/character_card.md` | 角色档案 prompt（含视觉叙事功能） | Phase 3a |
| `references/character_visual.md` | 角色外貌描述 prompt | Phase 3b |
| `references/color_script.md` | Color Script 生成 prompt 和规范 | Phase 4a |
| `references/cinematography.md` | 摄影参数 prompt（参考 Step 4 Comprehensive） | Phase 4b |
| `references/keyframe_gen.md` | 关键帧 image_prompt prompt | Phase 4e |
| `references/review_checklist.md` | 完整的人工审核清单 | 每个 Gate 前 |
