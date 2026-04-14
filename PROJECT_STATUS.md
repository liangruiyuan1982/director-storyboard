# PROJECT_STATUS.md

## 当前状态

- Skill: `director-storyboard`
- 当前分支: `main`
- 最近确认提交: `388e6c0` (`feat: upgrade panel decision schema and fix phase4 pipeline`)
- GitHub 已 push: 是
- 正式 full pipeline 状态: **已跑通，exit code 0**
- 最近完整验证时间: 2026-04-13

---

## 本轮已完成的核心升级

### 1. Panel 从信息汇总层升级为导演决策层
新增字段：
- `visual_task`
- `frame_priority`
- `freeze_action`
- `body_tension`
- `energy_state`

目的：让 keyframe / video 生成不再自己猜“这帧最重要的任务是什么”。

### 2. Acting 层升级
`references/acting.md` 已新增并要求输出：
- `freeze_action`
- `body_tension`
- `energy_state`

同时已将 `energy_state` 从过于僵硬的封闭枚举，升级为更贴近导演判断的开放主类系统，当前允许并鼓励使用：
- 耗尽
- 稳定
- 释然
- 对抗
- 压抑
- 崩塌前
- 试探
- 悬停
- 微动
- 抽离

目标：避免把复杂关系瞬间粗暴压扁为“对抗/压抑”。

### 3. Keyframe 生成逻辑升级
已更新：
- `references/keyframe_gen.md`
- `scripts/generate_image_prompts.py`

现在 keyframe 会显式使用：
- `visual_task`
- `frame_priority`
- `freeze_action`
- `body_tension`
- `energy_state`

同时已移除部分过度模板化的硬构图规则：
- 双人镜头不再固定 60/40
- 跟随镜头不再机械固定前 1/3 留白
- 明确允许关系镜头根据叙事压力采用失衡、错位、非对称构图

### 4. Viewer 升级
已更新：
- `scripts/generate_viewer.py`

viewer 中可直接查看：
- `visual_task`
- `frame_priority`
- `freeze_action`
- `body_tension`
- `energy_state`
- keyframes 提示词（确认已在写回后刷新）

### 5. 解析链路修复
已更新：
- `scripts/call_model.py`
- `scripts/pipeline.py`

关键修复：
- 修正 `glm51` 的 `max_tokens` 读取逻辑，支持从 `extra_body.max_tokens` 正确读取
- `extract_json()` 不再先误判截断，再提取 fenced JSON
- 新增 `robust_parse()` 容错解析
- 失败时记录 `finish_reason` 与 debug 文件

### 6. 正式主链路验证通过
验证结果：
- `pipeline.py 4 --project ... --model glm51 --confirm` 成功
- `scripts/test_full_pipeline.py` 成功，最终 `exit code 0`
- viewer 已确认在 keyframes 写回后自动刷新

### 7. 年龄规则从“硬年龄痕迹”升级为“年龄-状态-生活痕迹”综合判断
已更新：
- `references/character_visual.md`

当前要求模型区分：
- 实际年龄（chronological age）
- 外观年龄感（apparent age）
- 生活痕迹来源（life wear markers）

目标：
- 避免把当前测试项目经验硬写死为模板
- 避免把中年角色机械写成固定脸谱
- 让“显年轻 / 显疲惫 / 显成熟”都必须有来源、有解释

---

## 当前权威验证项目

### 1. 架构验证项目
`projects/test-marathon-schema-v9`

用途：
- 验证新 panel schema
- 验证 viewer 展示新字段
- 验证身体状态镜头是否真的优先服务导演任务

### 2. 完整链路验证项目
`projects/test-emotional-monologue`

用途：
- 验证 full pipeline 是否完整跑通
- 验证新增 schema 是否与正式测试脚本兼容
- 验证年龄一致性、关系镜头、空镜/环境镜头判断是否更稳定

---

## 当前明确已解决的问题

1. `cinematography` 阶段报“JSON被截断”并非 glm5.1 能力不足，主因是本地解析链路误判。
2. fenced JSON 被提前判为截断的问题已修复。
3. `max_tokens` 读取逻辑异常已修复。
4. viewer 先生成、keyframes 后写回导致“有数据但看不到”的流程顺序问题已修复。
5. `test_full_pipeline.py` 与主链路解析器不一致的问题已修复。
6. 年龄漂移（如把 39 岁角色写成 20 岁感角色）已明显缓解。
7. 关系镜头、关系前奏镜头、记忆切片镜头，已开始出现较清晰的区分。

---

## 当前仍存在的核心问题

### 核心问题：`visual_task / frame_priority` 仍主要由 `pipeline.py` 本地硬规则推断

当前 `assemble_panels()` 仍通过关键词 / if-else 逻辑直接推断：
- `visual_task`
- `frame_priority`

这带来一个本质问题：

> 系统现在更像“修得越来越像样的规则分类器”，而不是“真正理解镜头主导权的导演判断器”。

### 已观察到的典型后果

1. **空间主导镜头仍容易误判**
   - 例如 P01 这类“人物在场，但镜头主导权属于空间”的镜头，仍会被误吸到 `body_state` 或 `character_identity`

2. **过渡镜头 / 时间流逝镜头容易落入兜底分类**
   - 例如 P03 这类“人物与环境交界”的镜头，仍可能被误判为 `character_identity`

3. **继续往 `pipeline.py` 里堆判断条件，会重新滑回‘写死提示词/写死规则’的老路**

---

## 已形成的新判断共识（重要）

### 不应继续用更多 if/else 去补洞

用户已明确指出，正确方向不是：
- 遇到站台、灯光、空旷就判 environment
- 遇到眼神、交汇就判 relation

而是应该：

## 教会模型像导演一样判断“这一镜到底是谁在主导观众感受”

换句话说，系统真正缺失的不是更多规则，而是：

# “镜头主导权判断器”

---

## 下一阶段升级计划（当前最重要）

### 目标
把 `visual_task / frame_priority` 的生成逻辑，从：
- 本地硬编码关键词分类器

升级为：
- 由模型完成的“镜头主导权分析”步骤

### 计划方案

#### 1. 新增参考文件
已新增：
- `references/panel_intent.md`

作用：
专门负责分析每个 beat/panel 的“主导叙事压力来源”，不直接写 keyframe，不直接写 acting，不直接写摄影。

当前该文件已明确要求模型先判断：
- 主导叙事压力来源
- 删掉人物后镜头是否仍成立
- 删掉环境后镜头是否仍成立
- 观众最终记住的单一记忆点
- 人物是在定义画面，还是被画面定义

#### 2. 当前已落地的判断维度
`panel_intent.md` 已要求模型先回答：
- 这一镜的主导叙事压力来自哪里？
  - environment
  - body_state
  - emotion_pressure
  - memory_fragment
  - event_interruption
  - movement_shape
- 观众最终会记住什么？
- 人物在这镜里是主动主体，还是被环境定义？
- 如果删掉人物，这镜头还成立吗？
- 如果删掉环境，这镜头还成立吗？

#### 3. 当前已设计的输出字段
`panel_intent.md` 当前要求模型输出：
- `dominant_force`
- `remove_character_still_works`
- `remove_environment_still_works`
- `memory_point`
- `subject_relation`
- `visual_task`
- `frame_priority`
- `reasoning_brief`

再由 `pipeline.py` merge 到 `panels.json`

#### 4. 下一步替换现有逻辑
`pipeline.py` 当前那段本地 if/else 推断逻辑，下一步将替换为：
1. 调用 `panel_intent.md`
2. 读取结构化判断结果
3. merge 进 panel
4. 下游 `generate_image_prompts.py` 继续消费

### 当前进度
- [x] 设计“镜头主导权判断器”的判断框架
- [x] 新建 `references/panel_intent.md`
- [x] 在 `pipeline.py` 中接入该步骤
- [x] 删除/退役当前本地关键词分类逻辑（`visual_task / frame_priority` 已改由 `panel_intents.json` 提供）
- [x] 跑回归验证（重点看环境主导镜头、过渡镜头、关系镜头）

---

## 当前对系统阶段的判断

### 已经进入的阶段
- 不是“链路能不能跑通”阶段
- 不是“viewer 能不能显示”阶段
- 不是“年龄会不会乱漂”阶段

### 当前所处阶段
# 导演判断层的后期精修阶段

当前已完成的验证结论：
- 系统已不再依赖本地关键词 if/else 来生成 `visual_task / frame_priority`
- `panel_intents.json` 已在正式流程中落盘并参与 `panels.json` 生成
- 环境主导镜头（如 B01）已能落到 `environment`
- 过渡镜头（如 B03）已能落到 `environment`
- 记忆切片镜头（如 B04）维持为 `memory_fragment → environment`
- 身体状态镜头（如 B02/B05）维持为 `body_state`

当前真正要继续验证的，不再是“有没有主导权判断器”，而是：
- 它在更多项目中是否稳定
- `event_interruption` / `emotion_pressure` / `movement_shape` 三者之间是否仍会互相污染

### 当前正在进行的下一阶段任务
- 开始第二阶段校准：专门收紧并区分 `event_interruption / emotion_pressure / movement_shape`
- 目标：让“事件打断”“关系张力”“身体已离开但目光未离开”三类镜头不再互相抢语义主导权

### 当前最新进展（第二阶段）
已更新：
- `references/panel_intent.md`

本轮新增的校准重点：
1. `emotion_pressure` 明确界定为“关系压强”，不再默认写成对抗/对峙/敌意
2. `event_interruption` 必须满足“外部事件成为主记忆点 + 原有走势被打断/改写”才成立
3. `movement_shape` 只有在方向关系本身成为核心记忆点时才成立，避免抢走本该属于事件或关系的镜头

### 当前阻塞（更新）
- beat_analysis 的解析失败并未稳定复现，重跑后已通过
- 当前已保留调试能力：`test_full_pipeline.py` 的 `call_m()` 会在解析失败时把完整原始响应保存到 `/tmp/test_full_pipeline_debug_<model>_<timestamp>.txt`
- 该问题仍视为潜在不稳定项，但目前不再阻塞第二阶段验证

### 第二阶段最新验证结论
- `emotion_pressure` 的措辞已明显改善，不再默认滑向“对峙/对抗”
- 示例：B07 已能稳定生成“疏离中的微弱试探/尚未接通的空气压力”这类更准确的关系表达
- `event_interruption` 与 `movement_shape` 的边界开始清晰：
  - B06 → `event_interruption`
  - B08 → `movement_shape`
- 环境主导镜头保持稳定：
  - B01 / B03 / B09 → `environment`

### 当前进入的新阶段：验收式抽检
目标：
- 不再盲目新增规则，而是验证哪些能力已经稳定可用
- 区分“偶发波动”和“结构性缺陷”
- 判断 skill 距离“可长期生产使用”还差最后哪些边界

本阶段将重点抽检：
1. 年龄事实继承是否稳定
2. `memory_fragment / environment / body_state` 是否会偶发串位
3. `emotion_pressure / event_interruption / movement_shape` 的边界是否在不同拆 beat 结果下仍然稳定
4. 关键帧是否继续忠实执行上游 panel 判断，而不是悄悄回退成保守默认画面
5. 用新的、更复杂的真实长文样本做实战抽检，而不是只反复用 `test-emotional-monologue`

### 当前新增抽检任务
- 用户提供了一篇新的马拉松随感长文，要求验证系统在真实作者性文本、复杂议论+回忆混合结构下的表现
- 当前准备以该文本作为新的抽检样本，优先检验：
  - 长文本 beat 拆分稳定性
  - 抽象思辨内容的镜头化能力
  - 物件（奖牌）/身体（35公里后）/哲思（意义追问）三层叙事是否能被清晰拆开
  - 最终脚本是否具备专业短视频表达力，而不是只会生成标准抒情散文分镜

### 用户新增明确需求（重要）
- 本次项目的**旁白必须完整使用用户提供的原文**，不允许改写、压缩成另一版文案再配旁白
- 这暴露出当前 skill 的另一个关键能力要求：
  - 不能默认“拿到内容就改编成新的旁白脚本”
  - 必须能根据用户意图切换工作模式

### 当前新增能力要求
skill 后续需要支持至少两种模式：
1. **改编模式**：允许对原文进行影视化改写，再生成脚本与分镜
2. **原文旁白模式**：严格保留用户原文作为 VO，只做结构拆分、节奏控制、画面设计、镜头调度，不改写旁白文本本身

### 当前判断
- 这不是一次性项目偏好，而是 skill 设计层面的能力缺口
- 后续在意图捕获 / director_intent / script generation 阶段，需要明确识别并保留“VO 是否允许改写”这一用户约束

### 当前正在执行的新任务
- 正式把“原文旁白模式”接入 skill，而不是继续人工绕过 skill 直接产出方案
- 当前这篇马拉松长文将作为该模式的首个真实测试样本

### 当前最新进展（原文旁白模式）
已更新：
- `references/beat_analysis.md`
- `references/intent_questionnaire.md`
- `references/review_checklist.md`

本轮完成内容：
1. `beat_analysis.md` 已支持两种 VO 工作模式：
   - `adapt`
   - `preserve_original`
2. `intent_questionnaire.md` 已将“旁白类型”和“旁白是否允许改写”拆成两个独立问题（Q5 + Q5b）
3. `review_checklist.md` 已改为按模式审核 voiceover，不再默认“不能逐字复制”

### 当前下一步
- 用用户提供的马拉松长文，作为“原文旁白模式”的首个真实测试样本
- 核验 skill 是否能做到：
  - 保留原文旁白
  - 只做结构拆分与画面设计
  - 不再偷偷改写 VO

### 当前最新执行进展
- 已创建测试项目：`projects/marathon-original-vo-test`
- 已写入：
  - `story.txt`（用户原文）
  - `director_intent.json`（含 `q5b_voiceover_rewrite = preserve_original`）
- 已完成 `story_dna + beat_analysis` 定点测试
- 当前结果：`beat_analysis` 已能在 preserve_original 模式下基本保持 `voiceover = content`
- 已抓取原始响应文件：
  - `DNA RAW`: `/tmp/marathon_dna_raw_1776099546.txt`
  - `BEATS RAW`: `/tmp/marathon_beats_raw_1776099631.txt`

### 当前验证结论（原文旁白模式首测）
- B01 / B02 / B04 / B05 / B06 已明确做到 `voiceover` 与原文段落一致
- B03 / B07 / B08 的 `MATCH=False` 主要原因是原文中存在段落换行合并、长段截断或字符裁切，当前肉眼观察仍然属于原文切分，而不是改写成另一版文案
- 进一步判断后确认：在 `preserve_original` 模式里，让模型继续输出 `voiceover` 本身是多余风险

### 当前新的架构决策（重要）
在 `preserve_original` 模式下：
- 模型只负责切 beat / 输出 `content`
- 系统程序直接执行：`voiceover = content`
- 不再要求模型额外生成 `voiceover`

结论：
- 这比继续做“原文溯源校验”更简单、更稳
- `voiceover` 在该模式下应从“模型输出字段”改为“程序派生字段”

### 当前最新落地进展（程序层）
已更新：
- `scripts/pipeline.py`
- `scripts/test_full_pipeline.py`

当前程序行为：
- 若 `q5b_voiceover_rewrite = preserve_original` → 自动执行 `voiceover = content`
- 若 `q5_voiceover_type = 无旁白` → 自动执行 `voiceover = ""`
- 只有在 `adapt` 模式下，才保留模型生成 voiceover 的路径

### 本轮新增修复
- 修复 `generate_beats_viewer(project_dir)` 对 `project_dir` 类型假设过强的问题
- 现在函数入口会统一转为 `Path(project_dir)`，避免在字符串路径下访问 `.name` 时报错

### 当前最新验证结果（关键）
- 已对 `projects/marathon-original-vo-test` 重跑 `phase1_story_dna + phase2_beats`
- 结果：8 个 beats 全部满足 `voiceover == content`
- 验证结论：`preserve_original` 模式已从“提示词约束”升级为“程序保证”，当前已实现 100% 原文旁白保真

### 当前进入的新检查任务
- 开始对 `marathon-original-vo-test` 做内容质量抽检
- 重点不再是 VO 保真，而是：
  1. beat 拆分是否真正抓住物件层 / 身体层 / 思辨层
  2. skill 是否能在不改旁白的前提下，仍然组织出有效画面
  3. 分镜是否滑向励志套路片或空镜堆砌片

### 当前抽检结论（首轮）
- 当前 `preserve_original` 模式已解决“VO 不改写”问题，但还没有解决“是否真正理解作者思维路径”问题
- 具体表现：
  - 过早把哲学答案（如村上春树句子）提前成核心 beat
  - 没有把“石子投入湖面”“从征服到日常”“老朋友的调侃”“证明自己”这些作者性节点拆成足够清晰的结构层
  - visual_hint 开始滑向通用文艺短片模板（如夕阳奔跑、空旷长路、留白剪影）
- 当前下一步已明确：直接强化 `beat_analysis.md` 在 `preserve_original` 模式下的拆分原则，使其优先尊重作者思维推进顺序，而不是套用通用影视化切段逻辑

### 当前最新进展（拆分哲学校准）
已更新：
- `references/beat_analysis.md`

本轮新增的 preserve_original 拆分原则包括：
1. 先尊重作者思维路径，再考虑影视节奏
2. 不得提前抽取后段哲学答案句作为前段核心 beat
3. 物件层 / 身体层 / 思辨层尽量分开
4. visual_hint 禁止偷滑向通用文艺短片模板
5. 先问“原文推进了什么”，再问“适合什么镜头”

### 当前二轮抽检结论
- 结构上已有进步：
  - “石子投入湖面”节点已被保住
  - 村上春树句子不再过早抢到前段
- 但核心问题仍在：
  - “从征服到日常”这一观念转折没有被单独立住
  - “从证明自己到更纯粹”没有被充分拆出
  - visual_hint 在部分 beat 仍滑向史诗感/通用文艺模板
- 当前下一步已明确：继续强化 `beat_analysis.md`，明确要求优先识别三类节点：
  1. 观察节点
  2. 观念转折节点
  3. 哲学锚点节点

### 当前最新进展（三类节点识别）
已更新：
- `references/beat_analysis.md`

本轮新增明确规则：
- preserve_original 模式下，优先识别并单独判断：
  - 观察节点
  - 观念转折节点
  - 哲学锚点节点
- 明确要求：观念转折节点必须优先单独立 beat，不能被吞进大段叙述里
- 额外收紧 visual_hint：禁止用宏大自然景观、夕阳远去、长路剪影等偷换文本逻辑

### 当前三轮验证结论
- beat 结构层已明显进步：
  - “从征服到日常”已被单独立出
  - “从证明自己到更纯粹”已被单独立出
- 当前主要瓶颈已转移到 `visual_hint`
- 具体问题：
  - 仍频繁滑向“远景/逆光/奔向远方/背影/道路延伸”等通用模板
  - 对哲学段落仍倾向用史诗感或广告感镜头偷换抽象概念
- 当前下一步已明确：开始精修 `visual_hint` 在 preserve_original 模式下的生成规则

### 当前最新进展（visual_hint 校准）
已更新：
- `references/beat_analysis.md`

本轮最新做法已从“禁句式黑名单”回调为“判断框架引导”。

当前要求模型在生成 visual_hint 前，先完成三步判断：
1. 现实证据识别
2. 信息损失判断
3. 记忆点判断

当前原则：
- 不再靠列举某些俗套句式来堵漏洞
- 改为要求模型先判断：这段原文的现实画面证据是什么、如果抽象化会丢掉什么、观众最后该记住哪个具体证据
- 继续坚持：用判断框架引导，而不是用黑名单替模型写答案
- 该方法现已提升为通用规则，不再只属于 `preserve_original` 模式；`adapt` 模式同样应先经过这套 visual_hint 判断框架

### 当前下一步
- 对 `projects/marathon-original-vo-test` 再进行一轮完整测试
- 目标：检查在最新规则下，full pipeline 的整体输出是否同步改善，而不只是 Phase 2 局部变好

### 当前最新执行进展
- 已启动针对 `projects/marathon-original-vo-test` 的 full pipeline 完整测试
- 本轮不再借用默认样本，而是直接对当前真实测试项目跑：
  - story_dna
  - lookdev
  - beat_analysis
  - character_card
  - character_visual
  - color_script
  - cinematography
  - acting
  - assemble_panels
  - viewer

### 当前完整测试结论（marathon-original-vo-test）
- full pipeline 已成功跑通
- 当前状态不再是“链路问题”，而是“执行层画面理解问题”
- 前半段现实证据明显变强：
  - 奖牌框 / 书架 / 未拆封奖牌
  - 35 公里路标 / 呼吸 / 步态
- 但后半段仍存在两类问题：
  1. `或者` 式摇摆画面（没有真正锁定画面抓手）
  2. 用看似高级的意象替代理解（如树木/路灯/水珠等哲学替身）
- 当前下一阶段已明确：把“现实证据优先”的约束继续下传到 panel / visual 执行层，而不只停留在 beat_analysis

### 当前最新进展（执行层校准）
已更新：
- `references/panel_intent.md`
- `scripts/pipeline.py`

本轮动作：
1. 在 `panel_intent.md` 增加执行层现实证据判断要求
2. 明确要求 `visual_task` 不能使用“或者A，或者B”这类摇摆表达
3. 明确要求不要用临时意象替代理解文本
4. 在 `pipeline.py` 增加兜底清洗：若 `visual_hint` 出现“或者”，优先保留前面的明确抓手，避免摇摆表达直接漏进 panel 层

### 当前新任务
- 执行方案 A：对 `projects/marathon-original-vo-test` 进行一轮 `gpt5.4` 完整对照测试
- 目标：和现有 `gemma4` 结果做全链路质量对比，重点看 beat / panel / keyframe 三层是否减少伪深刻意象化并提升现实证据执行力

### 当前阻塞与新决策
- 已确认当前 `test_full_pipeline.py -> api.py` 这条测试链路无法直接使用 Codex 订阅模型
- 原因不是 project/model 参数错误，而是该链路依赖 API 配置表与 API 调用，不支持“仅订阅、无 API key”的 Codex 模式
- 用户已明确坚持：必须测试 Codex 订阅模型
- 因此当前任务已升级为：为 `director-storyboard` 建立一条 **Codex 订阅专用测试入口**，而不是继续在 `api.py` 链路上硬套 alias

### 当前进一步确认的阻塞
- 已尝试走 ACP / codex 正式路径
- 结果表明：不是 Codex 订阅不存在，而是 **Feishu 当前会话表面不支持 ACP 所需的 thread binding**
- 系统报错：`Thread bindings are unavailable for feishu.`
- 结论：当前无法在 Feishu 会话里直接拉起可绑定的 Codex ACP 子会话

### 当前执行方向
- 不再继续依赖 Feishu + ACP thread binding
- 改为在当前主会话内，为 `director-storyboard` 设计一条 **非 ACP thread 绑定** 的 Codex 订阅测试方案

### 重要复盘：本轮多次跑偏的教训（后续接手者必看）
本轮出现过几次典型跑偏，必须明确记录，避免后面的人重蹈覆辙。

#### 跑偏 1：绕开 skill，直接人工交付内容
**错误做法**：
- 用户本意是在测试和优化 skill
- 但中途一度直接手工写出导演方案/短视频脚本，绕开了 skill 本身

**为什么错**：
- 这会让“看起来有产出”掩盖“skill 实际还没学会”
- 会破坏当前任务目标：优化 skill，而不是替 skill 交作业

**正确做法**：
- 当用户是在拿真实样本测试 skill 时，必须优先把需求转成 skill 能力
- 先补 skill，再用样本跑 skill，再评估输出
- 不要用人工方案替代 skill 验证

#### 跑偏 2：把用户需求当成一次性偏好，而不是 skill 能力缺口
**错误做法**：
- 一开始把“旁白必须保留原文”理解成当前项目的小要求
- 试图临时记住，而不是立刻改 skill 结构

**为什么错**：
- 这类需求如果不进入 skill 结构，后面一定会再次忘掉或再次违背

**正确做法**：
- 发现用户约束后，先判断：这是项目偏好，还是 skill 能力缺口？
- 如果会重复出现，就必须升格为 skill 能力
- 本轮正确升级方式：拆出 `Q5b`，引入 `preserve_original / adapt` 双模式

#### 跑偏 3：在 preserve_original 模式里仍让模型生成 voiceover
**错误做法**：
- 明知 VO 必须 100% 保留原文，仍让模型输出 voiceover，再去检查像不像原文

**为什么错**：
- 这本身就在制造不必要风险
- 会把一个本可由程序保证的事情，变成不稳定的模型行为

**正确做法**：
- 在 `preserve_original` 模式下，模型只负责切 beat / 输出 `content`
- 程序直接执行：`voiceover = content`
- 让 `voiceover` 从模型输出字段变成程序派生字段

#### 跑偏 4：为了解一个测试样本的问题，回到“写死规则/禁词表”
**错误做法**：
- 遇到某个测试样本里常见的俗套 visual_hint，直接列出禁词或禁句式
- 例如直接点名禁止某些模板化画面表达

**为什么错**：
- 这会重新滑回“针对单一测试样本打补丁”的老路
- 不是教模型判断，而是在替模型背答案

**正确做法**：
- 不要靠黑名单式禁词解决质量问题
- 要把问题上提到“模型生成前的判断步骤”
- 对 visual_hint，正确方向应是先引导模型回答：
  1. 这一段原文最可拍的现实证据是什么？
  2. 如果拍成抽象情绪海报，会丢掉哪条关键信息？
  3. 观众最后该记住的是哪一个具体画面证据？
- 也就是：用判断框架引导，而不是用禁词表堵漏洞

#### 跑偏 5：只说“尊重思维路径”，但没有把“该识别什么节点”写清楚
**错误做法**：
- 前期只是抽象地强调“尊重作者思维路径”
- 但没有告诉模型：哪些节点是必须被优先识别和单独立住的

**为什么错**：
- 抽象原则太空，模型容易继续走通用影视化切段逻辑

**正确做法**：
- 把抽象原则转成可操作的识别框架
- 本轮正确方向：明确要求优先识别三类节点：
  - 观察节点
  - 观念转折节点
  - 哲学锚点节点
- 并明确：观念转折节点必须优先单独立 beat

### 统一方法论（后续一律遵守）
1. **先判断这是样本问题，还是 skill 能力问题**
2. **如果是 skill 能力问题，优先改结构，不要靠临时记忆**
3. **不要用人工方案替 skill 交作业**
4. **不要用黑名单式禁词表解决泛化问题**
5. **优先给模型补“判断框架”，而不是替模型写答案**
6. **让可程序保证的约束，交给程序，不要交给模型碰运气**

### 当前新发现的问题
- 年龄泛化仍未完全锁稳，本轮角色视觉输出又从 39 岁漂到“约35岁 / 35岁女性”
- 这说明年龄-状态-生活痕迹框架方向是对的，但还缺少“不得轻易缩窄/改写原始年龄锚点”的更强约束
- 同时发现 `memory_fragment` 在 B04 中的 `frame_priority` 被输出为 `character_identity`，不够理想；更合理的执行优先级应继续偏向 `environment` 或至少避免落回默认人物优先

### 当前正在继续推进的两项校准
1. **年龄事实锁定**
   - 目标：把年龄从“可被反复转述的描述字段”升级为 `canonical fact`
   - 要求：后续环节只允许引用，不允许自行改写 `39岁 → 35岁`
   - 当前已落实到：
     - `references/character_visual.md`
     - `references/keyframe_gen.md`
   - 最新验证结果：在最近一次 `test-emotional-monologue` 回归中，keyframe 已稳定保持 `39岁女性`，未再漂移为 `35岁`

2. **`memory_fragment -> frame_priority` 映射校准**
   - 目标：避免记忆切片镜头在执行层掉回 `character_identity`
   - 要求：当主导力明确是 `memory_fragment` 时，执行优先级默认更接近 `environment` 或其他合理维度，而不是人物默认优先
   - 当前已落实到：
     - `references/panel_intent.md`
   - 最新验证结果：最近一次回归中，B04 已稳定输出 `memory_fragment -> environment`

这是 skill 从“可用”走向“成熟”的最后一道关键坎。

---

## 已知注意事项

1. `test_full_pipeline.py` 需要显式锁定本 skill 的 `pipeline.py`，不能再依赖模糊 import。
2. `call_model.py` 是当前 JSON 稳定性的关键枢纽，后续修改要谨慎。
3. 如果后面再出现“JSON解析失败”，优先先看：
   - `finish_reason`
   - `/tmp/llm_debug_<model>_attemptN.txt`
4. `visual_task / frame_priority` 这层现在仍是最容易被“局部测试项目牵着走”的模块，修改时必须优先追求泛化，而不是局部修补。

---

## 下一位接手先看什么

按顺序看：
1. `PROJECT_STATUS.md`
2. `SKILL.md`
3. `references/character_visual.md`
4. `references/acting.md`
5. `references/keyframe_gen.md`
6. `scripts/pipeline.py`
7. 验证项目：
   - `projects/test-marathon-schema-v9`
   - `projects/test-emotional-monologue`

---

## 一句话 handoff

`director-storyboard` 已完成链路修复、年龄泛化修正、viewer 刷新闭环和 panel 决策层升级；`director-storyboard` 已完成从本地关键词分类器到“镜头主导权判断器”的第一阶段重构；当前最关键的下一步，是扩大验证样本，并继续校准 `event_interruption / emotion_pressure / movement_shape` 的边界。


## 2026-04-14 回归验证补充

### 已完成验证
- clean-run：使用 `/tmp/openclaw/ds-regression/clean-run-v1` 从空白项目完整跑通至 `phase5_output`
- interrupted resume：已验证 `running` 残留状态可被 reconcile，并在 `--resume` 下正确恢复
- restart-from：已验证 `--restart-from phase4c_photography` 可正确从指定阶段继续执行

### 本轮修复
- `overall_status` 结束态统一为 `completed`，不再混用 `done`
- `pipeline.py` 的 `--model` 白名单加入 `minimax`
- minimax 实跑通过 full clean-run，全链路闭环成立

### 当前结论
- checkpoint / resume / restart-from 已从“功能实现”进入“回归验证通过”状态
- clean-run + 中断恢复 + restart-from 三条主链均已验证通过
