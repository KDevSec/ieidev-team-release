---
name: memory
description: 为多迭代长周期工程项目建立「持久工程记忆 + 智能召回 + 蒸馏导出」制度——每步完成、每次踩坑、每个决策、每次评分、每次对外部 skill/工具的反馈实时落盘到 `.ieidev/memory/` 规范文件；用户再次提到相关话题时 UserPromptSubmit hook 自动召回指针让 Claude 按需 Read。用作跨会话续航 + 避免重复踩坑 + 未来 skill 自主优化 / 知识蒸馏的原料库。核心机制：实时落盘 + 汇总从文件聚合（不翻会话）+ 命中即召回 + 按期归档切档 + CLAUDE.md 接口契约化 + subject 三级自动推断 + verbatim 原话不可改写 + markdown 主存 + markdown 切片包蒸馏导出（不引入 JSONL）+ 落盘路径 hybrid/inline 两档可选。触发时机：用户说"建立工程记忆 / 加 .ieidev / 搞记忆机制"开始初始化；说"写今天总结 / 生成每日汇总 / 交接给明天 / 总结一下今天"从 `.ieidev/memory/` 当天条目聚合输出；说"切档 / 归档一下 / 整理主文件"按月/季度搬老条目到归档子目录；说"这条以后都要遵守 / 加到项目规则 / 变成硬规矩 / 升级成铁规"按规则升级流程问用户三件事；说"修 CLAUDE.md 漂移 / 接口漂移 / claude.md 对齐 skill / claude.md 升级"按接口契约生成精确 diff patch 对齐 CLAUDE.md；新会话时问"昨天做到哪了 / 之前聊到什么 / 上次进度 / 继续上次的工作 / 恢复上下文"从 `.ieidev/memory/` 回读；或会话即将被压缩、看到 `<ieidev-memory-recall>` / `<ieidev-memory-brief>` 注入（含 ⚠️ CLAUDE.md 接口漂移提示）、看到 `.ieidev/memory/WARN-未记录-*.md` 或 checkpoint 文件、用户抱怨"每次新会话都要重新解释上下文"等场景；**或当用户在对话流里对外部 skill/插件/工具说出 5 类语义之一——RFE（"要是能 X 就好了 / 希望 Y / 如果有 Z 多好"）、痛点（"这破 X / 这玩意 / 不好用 / 太吵 / 太烦"）、bug（"为啥 / 怎么会这样 / 不应该是这样吧"）、表扬（"干得对 / 这次准 / 帮大忙"）、困惑（"看不懂 / 啥意思 / 为啥要这么干"）——按 subject 三级推断（L1 显式提及 / L2 上下文 / L3 候选选一）确定归属、起草 F-NNN 反馈条目、向用户一句话确认后落盘到 skill-feedback.md**；或用户给 Step 打分时夹带 skill 反馈（"4 分但 X 太吵"）按**评分裂解**自动拆两条——Step 评分段记项目分（subject:project）+ F-NNN 记 skill 反馈（subject:plugin:X, verbatim:用户原话）；或用户问"对谁打分 / 这分给谁 / 评分 subject 是什么 / 怎么归类这条反馈"按三级推断回答；或用户说"导出蒸馏数据 / 导出 markdown / export-md / distill / 蒸馏 / 知识蒸馏 / 训练数据 / 把记录弄出来训练"走 `/ieidev-team:memory-distill` 产出三个 markdown 切片包（dataset-full / dataset-misalignment / dataset-skill-feedback-by-subject）；或用户问"记录太占上下文 / subagent 模式 / hybrid / record_mode / 落盘方式怎么切"时介绍 .ieidev/memory/config.yaml 的两档配置（hybrid 默认 / inline 备用）；或用户问"自动蒸馏 / 定时蒸馏 / 什么时候蒸馏 / distill mode / 蒸馏阈值 / 多久蒸馏一次 / 蒸馏频率"时介绍 distill.mode 两档（auto 默认：阈值满足 SessionStart 后台 Popen 跑 distill.py --auto-context、manual 备用：仅 brief 注入"建议蒸馏"），触发条件 = 时间 ≥ 7 天 AND（F 新增 ≥10 OR misalign 新增 ≥3 OR R 新增 ≥5），失败写 WARN-distill-failed-*.md 下次 SessionStart 显眼提醒。不管状态机或流程编排，只管"该记什么、何时记、怎么记、怎么归属（subject）、怎么召回、何时归档、何时导出蒸馏切片、何时自动触发蒸馏"。
---

# ieidev 工程记忆机制

## 这个 skill 解决的问题

核心目的有两件：

**1. 跨会话续航**：长周期项目最大的痛点是失忆——上次为什么选 A 不选 B？上周踩过的坑这周又踩？每次新会话都要重新解释上下文？把关键信号落盘就能缓解。

**2. 经验外溢给未来 skill 作者**：更有价值的定位——项目推进过程中积累下来的**真实感受评分、盲区诊断、踩坑轨迹、用户反馈原话**，是未来产出新 skill / 改进既有方法论的**一手原料**。不是让本项目强制执行这些教训，而是让下游 skill 作者能读到真实发生的故事。

**这个 skill 不管**：
- 流程编排、状态机、做什么阶段、用什么工具
- 项目内是否强制执行这些记录提炼出的规则（记录和执行是两件事）
- 评分的"对错"——只管如实捕获双方的主观感受

**记录 + 打分感受是主角。方法论铁规、R-NNN 改进信号这些是可选的衍生产物，不是核心。**

## 两条蒸馏前提铁规（subject + verbatim）

为了让 `.ieidev/memory/` 的数据能被下游知识蒸馏 / skill 自主优化消费，**所有评分和反馈必须满足两条额外铁规**——这两条不写进 CLAUDE.md（属 skill 实施细节），但是 skill 行为的硬约束：

### 🔴 subject 必明（评的是谁）

每条评分 / 反馈必须显式标记 **subject**——评的到底是 `project`（项目结果） / `skill:<name>`（某 skill） / `plugin:<plugin>/skill:<skill>` / `tool:<name>` / `methodology:<name>` / `collaboration:<pattern>` / `unknown`。

**subject 由智能体自动推断，严禁让用户从空白打字填写**。三级推断策略（L1 显式提及 / L2 上下文 / L3 候选选一）覆盖 ~90% 场景不打扰用户。推不出时归 `unknown`，绝不默认归 `project`（会污染项目评分子集）。

用户给 Step 打分时常夹带 skill 反馈（"4 分但 X 太吵"），智能体必须自动**评分裂解**——拆成 Step 评分（subject:project）+ F-NNN 反馈（subject:plugin:X）两条独立条目，绝不能塞同一条。

> 完整推断策略、置信度字段、评分裂解伪代码见 **`references/subject-推断与评分裂解.md`**。

### 🔴 verbatim（用户原话）不可改写

skill-feedback.md（F-NNN）的 `verbatim` 字段必须保留**用户原句**——智能体不可总结、不可改写、不可抽象化。

蒸馏价值排序 = **原话 > 改写 > 打分**。打分信息量低；改写丢情绪 / 强度 / 场景；原话才是真实自然语言需求，可直接训 RM / 提 RFE / 做指令微调。**强制改写就是数据贬值**。

> F-NNN 完整 schema、5 类语义识别（RFE / 痛点 / bug / 表扬 / 困惑）、落盘前一句话确认流程见 **`references/skill-反馈通道-F.md`**。

## 核心运作原则：实时落盘 + 汇总只读文件（极其重要）

这是本 skill 最关键的机制，任何使用者都必须理解。**这 3 条是"贯穿 session 的铁规"**——需要 Claude 下意识时刻在场遵守，因此它们是唯一会落到项目 `CLAUDE.md` 的内容（其他 skill 细节都留在 SKILL.md / references/，用户召唤时按需读）。

- 🔴 实时落盘
- 🔴 文件聚合不翻会话
- 🔴 优先处理 hook 产出（WARN / brief / recall / checkpoint）

完整模板见 `references/初始化-claude-md-模板.md`。

### 🔴 记录是"实时落盘"，不是"会话末尾回忆"

智能体在项目推进过程中，**每做完一步、踩一次坑、做一次决策、接到一次用户评分，就立刻把当条记录写进 `.ieidev/memory/` 对应文件**。这是持续进行的后台动作——不是攒到会话最后一次写完，更不是等用户提醒才记。

不实时落盘的后果：
- 会话被压缩或崩溃 → 当天信号全失
- 记忆失真 → 靠回忆写的记录比实时写的差一个量级
- 用户评分过夜补录 → 第二天的分数严重失真（感受褪色）

### 🔴 每日汇总是"从 `.ieidev/memory/` 聚合"，不是"翻会话记录"

用户说"写今天的总结"时，智能体的动作路径**必须**是：

```
读 .ieidev/memory/执行日志.md  ──┐
读 .ieidev/memory/决策日志.md  ──┤
读 .ieidev/memory/踩坑日志.md  ──┼── 按今天日期筛选条目 → 拼装 → 写入 每日汇总/YYYY-MM-DD.md
读 .ieidev/memory/改进建议.md  ──┤
读 .ieidev/memory/当前状态.md  ──┘
```

**严禁**：回头翻会话上下文、让用户"重述今天做了什么"、凭印象总结。

为什么这样设计？——这正是这个 skill 存在的意义：
- 实时落盘阶段智能体已经带着**当下准确的细节**写好了每一条
- 汇总阶段只需要按日期筛选 + 拼装 + 写索引，速度快、信息准
- 如果非要翻会话，说明实时落盘没做到位，这是 skill 失效的信号

如果某一步没来得及实时落盘，**宁可在汇总里标 `Step N: 待补（会话中未及时落盘）`**，也不要编造或靠回忆填满。这是数据诚信。

## 🔴 Step 完成硬闸门（四段必填）

**Step 四段必填——缺任一段视为未完成。下一步工作开始前必须补齐。**

- **执行事实段**：任一字段缺（工具调用次数 / 报错次数 / 绕路次数 / token 消耗感 / 使用的 skill）→ 未完成
- **模型自评段**：扣分项为空或占位（`—` / `待补` / `TBD`）→ 未完成
- **用户评分段**：完成时间戳或顺畅度为空 / `—` / 占位 → 未完成
- **评分差异分析段**：两段时分戳都填后才能生成

### 动作链（按 `rating.mode` 三分支）

评分模式由 `.ieidev/memory/config.yaml` 的 **`rating.mode`**（flat dot-key 单层）决定：
`model-only` | `user-opt-in`（插件默认）| `user-required`。**一句话即时切换**——用户说"关掉评分"→ 写 `rating.mode: model-only`；"严格评分"→ `user-required`。

**三档共性（与模式无关）**：执行事实段 + 模型自评段必填，**模型自评扣分项所有模式都必填**（防讨好式满分）。

**`user-required`（现行硬闸门）**
```
模型做完一步 → 写执行事实段 + 模型自评段（含扣分项）
            → 【公布自评分给用户】→【主动追问用户评分】
            → 用户回答后填用户评分段 + 锁定两段时分戳 → 生成评分差异分析段 → Step 完成
```

**`user-opt-in`（插件默认，温和）**
```
模型做完一步 → 写执行事实段 + 模型自评段（含扣分项）→ 公布自评分
            → 轻提一句"如要补用户评分随时说"，不追问、不等待
            → 用户不回应即 Step 完成（用户评分段留空不算半残）
```

**model-only（= 本项目 Q-002 机读化，零追问）**
```
模型做完一步 → 写执行事实段 + 模型自评段（含扣分项）
            → 用户评分段留空 `—` 骨架 + 标 status: voided-faded + 销账注释
            → 直接 Step 完成（不公布、不追问）
```
⚠️ **model-only 绝不把自评分拷进用户评分段**——那是伪造用户评分，污染下游 misalignment 数据。
用户评分段保留 `—` 骨架，用户随时主动给分 → 当场回填 + 改 `status: scored` 恢复闭环。

### 用户临时说"跳过评分直接下一步"（仅 user-required 模式）

若处于 `user-required` 且用户一次性说"先别采集评分，开下一步"——这是**开 R-NNN 销账**的情形：
- Step 末尾追加 `> 半残销账：用户明确要求跳过评分，YYYY-MM-DD`
- 改进建议.md 开 R-NNN 记录这次半残事件

（长期不想评分 → 直接切 `rating.mode: model-only`，无需每次 R-NNN。）

**严禁**：在 user-required 下默默把 Step 当"完成"过了（"模型写完自评就认为 Step 完成"是反模式）。

> iter-7 discriminating eval 验证：加这段让 skill 单次推理 token -21% / tool uses -35%，
> 行为完全一致；22 行文档 trade 掉的是"模型每次触发时省 ~11.5k token"的长期收益。
> 详见 `${CLAUDE_PLUGIN_ROOT}/evals/skill-quality/iterations/20260423-07-p0-1-discriminating/notes.md`

## 初始化

用户说"建立工程记忆 / 加 .ieidev / 搞记忆机制"时触发。在项目根建立 `.ieidev/memory/` 目录和骨架文件（当前状态 / 决策日志 / 踩坑日志 / 执行日志 / 每日汇总 / 改进建议），并在 CLAUDE.md 加触发规则段。

**初始化时必须问用户一个决策（走 Q-001）**：Step 编号用全局递增还是迭代内递增？默认倾向全局递增。

**v0.11+ 升级**：全局递增的基础上**加 scope 前缀**——`Step <scope-slug>-N` 格式（v0.11 起为分支 slug，v0.14 起员工 scope 用 canonical id）。原因：多 worktree symlink 共享 `.ieidev/` 架构下，两个 session 并发独立递增会产生 ID 冲突；多员工 scoped 布局下各员工需独立计数器。新格式让每个 scope 有独立计数器，互不干扰。详见 §「多 worktree / 多 scope 并发」。

**关键授权**：这些文件**不需要向用户请示即可写入**——在 CLAUDE.md 里显式授权一次，后续智能体自动维护。

> 目录结构、CLAUDE.md 模板、接口契约、v0.2.0 升级迁移、.gitignore 配置等完整步骤见 **`references/初始化-claude-md-模板.md`**。

## 七类记录的触发时机总览

| 触发时机 | 写入文件 | 编号 | 详细 schema |
|---------|---------|------|------------|
| 需要人做决策（有歧义、多选项、不可逆） | 决策日志.md | Q（新：时间戳形，见下） | `references/六类记录-schema.md` §1 |
| 踩坑 / 绕路 / 报错 / 命令失败 | 踩坑日志.md | G（新：时间戳形，见下） | §2 |
| 每步/每里程碑完成 | 执行日志.md（双评分） | Step（新：时间戳形） | §3 |
| 用户当场反馈体验/规则 | 执行日志.md 的评估区 | — | §3 |
| 会话结束前 | 每日汇总/YYYY-MM-DD.md | — | §4 |
| 评分差值 ≥ 2 或反复出现的感受信号（项目内方法论） | 改进建议.md | R（新：时间戳形，见下） | §5 |
| **对外部 skill/插件/工具的 5 类语义反馈**（RFE/痛点/bug/表扬/困惑） | **skill-feedback.md**【新】 | **F（新：时间戳形，见下）** | **`references/skill-反馈通道-F.md`** |
| 流程状态变更 | 当前状态.md | — | §7（含 frontmatter 字段语义） |
| （可选）项目自愿立硬规 | 方法论铁规.md | — | §6 |

### 七类记录要点速览

**1. 决策日志.md（Q-NNN）** — "智能体不该替用户拍板"的问题。记选项 + 用户选择 + 理由（不只记结论，便于未来 review 看取舍逻辑）。

**2. 踩坑日志.md（G-NNN）** — 绕弯才发现的事。**必须**在标题下一行标 `triggers: [...]` 3-5 个关键词（中英文都要），否则永远不会被自动召回。

**3. 执行日志.md（双评分，最核心）** — 每个工作单元一条 Step（**粒度 = 自然停顿点**：连续独立执行 ≥ 30min–1h / 需用户决策 / 有可 review 产出 任一触发闸门，详见 `references/六类记录-schema.md` §3），四段：**执行事实**（工具调用/报错/绕路/token/**使用的 skill**，估算即可）+ **模型自评**（顺畅度 1-5，**必填一条扣分项**防讨好式满分）+ **用户评分**（当场采集，1-5 + 一句话）+ **评分差异分析**（差值 ≥ 2 → 追加 R-NNN）。**锁定铁规**：模型自评时分戳必须早于用户评分时分戳（防自评污染）。

**4. 每日汇总/YYYY-MM-DD.md** — 给下次会话的交接班。速览 + 未完成项 + 明日计划 + 当日新增 Q/G/R 索引。**不复述执行日志已有细节**。

**5. 改进建议.md（R-NNN）**【重要】 — **项目内方法论反思的原料库**。评分差值 ≥ 2、负面反馈、方法论反思都在这里留原始信号——**不提炼、不总结、不过滤**。消费者是未来的 skill 作者（跨项目聚类归纳）。**注意：R-NNN 只装"项目内方法论"信号**，对外部 skill / 工具的吐槽走 F-NNN（见 6）。

**6. skill-feedback.md（F-NNN）**【新增 / 重要】 — **对外部 skill / 插件 / 工具 / 方法论 / 协作模式的反馈通道**，与 R-NNN 物理隔离。三铁规：`subject` 必填（评的是谁）、`verbatim`（用户原话）必填（不可改写）、`score` 显式可空（不强制打分）。智能体在主对话流里识别 5 类语义（RFE / 痛点 / bug / 表扬 / 困惑）自动起草，落盘前用一句话向用户确认避免误采。用户给 Step 打分时夹带 skill 反馈，按**评分裂解**自动拆两条（Step 评分段记项目分 + F-NNN 记 skill 反馈）。**这是 markdown 切片导出 `dataset-skill-feedback-by-subject/<subject>.md` 的核心数据源**。详见 **`references/skill-反馈通道-F.md`** 和 **`references/subject-推断与评分裂解.md`**。

**7. 方法论铁规.md（可选）** — 项目**自愿**在本项目内强制执行的硬规则。与改进建议.md 的区别：铁规是本项目执行的规则；改进建议是给下游 skill 作者的信号。

**8. 当前状态.md（含 YAML frontmatter）**【重要】 — 工作状态的单一真相源。frontmatter 字段（`phase` / `iteration` / `current_step` / `last_updated` / `pending_decisions` / `unresolved_gotchas`）给 hook 脚本用，body 给人读。**每次完成 Step 都要顺手改** `current_step` + `last_updated`。

> 每类的完整格式、字段语义、设计意图、锁定铁规细节见 **`references/六类记录-schema.md`**。F-NNN 单独成档，见 **`references/skill-反馈通道-F.md`**。

## 条目状态与沉淀字段（v0.7+）

条目 frontmatter 支持 `status`（**评分/销账态** only：open / scored / voided-faded / voided-r-NNN；**≠修复态**——修复进展写 body「解决」段，不新增 fix_status）和 `promote_*`（沉淀：pending / done / skipped + 目标路径 + 日期）两组字段。Hook 扫描时优先读 `status`，未填等价于 `open`；`voided-*` 跳过欠评扫描；遇非枚举 status 由 `status_schema.warn_unknown_status` 告警。

> 完整取值语义、Hook 行为、沉淀阈值逻辑见 **`references/六类记录-schema.md`** 各 § 的"条目状态与沉淀字段"段。

## triggers 写法要点

`triggers:` 字段是**智能召回的锚点**——UserPromptSubmit hook 扫所有带 triggers 的条目，用字面子串匹配用户 prompt 后注入 `<ieidev-memory-recall>` 指针。

**核心原则**：
- 3-5 个关键词，中英文都要（用户可能用任一种）
- 用**用户会说的口语词**（命令名 / 场景词 / 特征词），不用过泛（"error"）也不用过特殊（错误码）
- 写新 G-NNN / Step / 铁规时**顺手就标**——不标就永远不会被自动召回

**渐进式披露**：注入只给编号+标题+路径（~30 token），Claude 判断相关再 Read 细节。

> 完整规范（三种合法格式、项目级 spec 文件扫描路径、session 去重、常见错位）见 **`references/triggers-写法.md`**。

## 文件切档与归档

长项目主文件膨胀时，采用**人工触发 + Claude 提醒**的切档制度。核心规则：执行日志按月切、踩坑/决策按季切、改进建议不切；搬家不删除，编号保留，切档前征得用户同意。Stop hook 检测跨期时提醒。

> 切档规则一览、操作步骤、召回逻辑变化见 **`references/切档与归档.md`**。

## 规则升级流程

改进建议/方法论铁规积累到一定程度可升级为项目级硬规则。升级**不自动执行**。三个触发信号：R-NNN 同主题 ≥ 2 次、铁规被引用 ≥ 3 次、用户明确要求。升级时**必问三件事**（严禁替用户拍板），源条目原文完整保留。

> 触发信号、必问三件事、默认位置推荐、执行步骤见 **`references/规则升级流程.md`**。

### 原料来源（v0.12+ 显式标注）

R-NNN（项目内方法论反思）→ 累积 ≥ 2 次同主题 或 用户明确"升铁规" → 走升级流程
（必问三件事见 `references/规则升级流程.md`）→ 落到 方法论铁规.md / 项目宪章 / ADR

完整流程见 `references/规则升级流程.md`。

## 落盘路径：subagent 化两档（hybrid / inline）

为了节省主会话上下文 token 并改善用户对话体验，ieidev-memory 提供两档落盘路径配置（`.ieidev/memory/config.yaml`）：

```yaml
record_mode: hybrid   # hybrid（默认） | inline
```

| 档位 | 行为 |
|---|---|
| **`hybrid`（默认）** | 小高频留主会话内联，大单次 + F-NNN 实体写入走 subagent。Claude Code 等支持 Agent / Task tool 的平台默认。 |
| **`inline`** | 全部主会话内联。平台不支持 subagent 或用户偏好极简时用。 |

**两档都做的主会话同步内联**：subject 三级推断 / 评分裂解 / F-NNN 落盘前确认 / 单条 Step 落盘 / Q/G/R 写入 / 当前状态.md 改 frontmatter。

**hybrid 模式额外走 subagent**：
- **同步等返回**（主会话等 subagent 完成才继续）：每日汇总 / weekly 聚合 / markdown 切片导出
- **异步 fire-and-forget**（主会话不等）：**F-NNN 实体写入**（用户确认 subject 之后——这是最大杠杆点，让随口吐槽不打断对话）/ 长文件 lint

**Fallback**：如果 Agent / Task tool 不可用 → 自动降级到 `inline`，无需运行时检测（Claude 看到工具不在列表自然降级）。

**subagent 必须返回审计摘要**：`{written_to, status, lint_warnings, stats}`——无审计 = 数据信任崩塌。

> 完整动作分类表、调用契约、上下文传递最低成本原则、命令模板分支逻辑见 **`references/subagent-落盘机制.md`**。

## 自动蒸馏机制（auto / manual 两档）

`.ieidev/memory/` 积累到一定时间 + 一定数据增长 → 自动跑 distill 或提醒用户。两档配置（`.ieidev/memory/config.yaml`）：

```yaml
distill:
  mode: auto                    # auto（默认） | manual
  reminder_days: 7              # 时间阈值
  reminder_new_f: 10            # F-NNN 新增条数阈值
  reminder_new_misalign: 3      # misalign Step 新增条数阈值
```

**触发条件（AND 语义）**：距上次蒸馏 ≥ 7 天 **AND**（F 新增 ≥10 **OR** misalign 新增 ≥3 **OR** R 新增 ≥5）。从未蒸馏 + 有任何数据 → 首次触发。

**两档行为**：

- `auto`（默认）：SessionStart hook 检测到触发 → 后台 `subprocess.Popen` 跑 `distill.py --auto-context --skip-promote`（detach 子进程，hook 立刻返回）→ brief 注入"已开始后台自动蒸馏"
- `manual`：仅 brief 注入"建议蒸馏：[原因]，跑 `/ieidev-team:memory-distill`"

**关键约束**：
- **promote 阶段永远不自动**——用户挑选 + 写 docs/ 是高风险动作。auto 模式只跑 dataset 阶段。
- **失败显式 WARN**——`distill.py` try/except 包裹，失败写 `WARN-distill-failed-*.md`，下次 SessionStart 显眼提醒
- **成功 touch `.last-distill`**（auto 模式额外 touch `.last-distill-auto`，下次 brief 注入"上次自动蒸馏完成于 X"）
- **兼容老项目**：无 `.last-distill` 时 fallback 到 `.last-promote` mtime

> 完整阈值检测逻辑、Popen detach 流程、WARN 处理、未决问题见 **`references/蒸馏触发机制.md`**。

## 自动化触发（三层）

| 层次 | 机制 | 触发条件 |
|---|---|---|
| **自然触发** | skill description 命中 | 用户自然语言说"建立记忆 / 写总结 / 切档 / 继续上次工作"等 |
| **主动触发** | CLAUDE.md 触发规则段 | 初始化时贴进项目 CLAUDE.md，每个新会话 Claude 读到即按规则维护 |
| **自动触发** | Hook（插件自带） | Stop / SessionStart / SessionEnd / PreCompact / PostToolUse / UserPromptSubmit 各司其职 |

**关键 hook 概要**（细节见 reference）：

- **Stop hook**：软提醒漏汇总 / 漏 Step / 跨期归档
- **Strict 模式**（opt-in，`touch .ieidev/memory/strict`）：漏记时 exit 2 硬阻塞
- **SessionEnd**：关会话前写 `WARN-未记录-YYYY-MM-DD.md` 兜底
- **SessionStart**：注入 `<ieidev-memory-brief>` 摘要（今日进度 + 当前状态字段 + ⚠️ 待处理项，含 CLAUDE.md **接口漂移**检测——基于 `claude_md_contract` 自动发现老项目缺哪些 hook 标签响应）
- **PreCompact**：压缩前快照到 `checkpoints/压缩前-*.md`（7 天自动清理）
- **UserPromptSubmit**：字面匹配 triggers 注入 `<ieidev-memory-recall>` 指针（session 去重）

**边界**：hook 只能戳一下 Claude 注意或硬阻塞罢工，不能做智能判断。真正的决策（该不该写、写什么）由 skill 负责——不要想用 hook 代替 skill。

> 每个 hook 的检测项、阻塞条件、输出格式、扫描路径见 **`references/自动化机制-hooks.md`**。

## 每日汇总的动作路径（必读）

用户说"写今天的总结"/"生成每日汇总"时，智能体的动作路径**严格如下**（重复强调，不要偷懒）：

```
Step 1：读 .ieidev/memory/ 下所有核心文件的当天条目
         - 执行日志.md 筛今天的 Step
         - 决策日志.md 筛今天的 Q-NNN
         - 踩坑日志.md 筛今天的 G-NNN
         - 改进建议.md 筛今天的 R-NNN
         - 当前状态.md 读最新状态

Step 2：按每日汇总 schema 拼装
         - 完成的工作（速览，不复述执行日志细节）
         - 未完成项
         - 明日计划
         - 本日新增 Q/G/R
         - 负面评价观察

Step 3：写入 .ieidev/memory/每日汇总/YYYY-MM-DD.md
         - 文件已存在则追加（一天多次会话累积）
         - 文件不存在则新建

Step 4：更新 .ieidev/memory/当前状态.md
```

**必须遵守**：
- 整个过程应当**快速**（几秒到十几秒），因为只是文件 I/O + 拼装，不是推理
- **不要回头翻会话记录**：会话上下文只是"刚写进文件的内容的副本"，读文件才是准确的
- **不要让用户复述**："你今天做了什么？"——不，用户已经在过程中给过实时评分和反馈了，都在 `.ieidev/memory/` 里
- 如果 `.ieidev/memory/` 里今天条目为空（说明实时落盘没跟上），**坦率报告**"今天 `.ieidev/memory/` 里没有记录，无法聚合——这是 skill 失效的信号，建议下次启用 hook 或加强触发规则段"，**不要**凭印象补写

### 为什么这个设计重要？

- **决定 skill 是否成立**：如果每日汇总靠回忆写、每步记录靠总结阶段回填，这个 skill 就退化成"会话结束前写点总结"——毫无价值。区别不在于"有没有文件"，而在于"文件里的内容是否是实时的、准确的、不偏向的"。
- **让下游 skill 作者能用**：未来的 skill 作者读 `.ieidev/memory/` 时看到的必须是**当时当刻的原始信号**，不是事后美化的总结。美化后的总结失去了"智能体和用户当下的张力"，也就失去了提炼新 skill 的原料价值。

## 何时不用这个 skill

- 一次性脚本、单会话就结束的任务 → 过度设计
- 已有成熟项目管理工具（Jira/Linear）承接决策和缺陷 → 只保留执行日志 + 每日汇总即可
- 用户明确说"别搞那么多文件" → 听用户的，可以退化成只有执行日志.md 一份

## 落地时的务实提醒

- **先立骨架再谈规则**：初始化时把空文件和 CLAUDE.md 段落写好，不要一开始就塞满"约定"。约定应从真实踩坑中生长。
- **编号不回收**：Q-007 一旦废弃，不要把后面的号往前挪，用"已废"标注即可。编号的稳定性 > 紧凑性。
- **超过 500 行的执行日志/踩坑日志考虑分档**：按迭代/季度切分成归档文件，保留索引（详见 `references/切档与归档.md`）。
- **原始胜于提炼**：改进建议.md 是原料库，不是结论库。写入时保留用户原话、事实段、具体数字——未来 skill 作者看原始证据比看你的总结更有价值。
- **项目内不强制执行就是对的**：不要因为 R-NNN 记了 5 条就回头试图"改造本项目的方法论"——这是 skill 滥用。除非用户明确说"加进铁规"，否则记录完就放那儿。

## 下游：知识蒸馏（markdown 切片包）

通过 `/ieidev-team:memory-distill` 命令按蒸馏目标 filter + sanitize 原 markdown 条目，
产出三个独立 markdown 切片包：
- `dataset-full/` — 全量记录（含 Step / G / Q / R / F），适合通用蒸馏
- `dataset-misalignment/` — 评分差值 ≥ 2 的样本，适合 RLHF
- `dataset-skill-feedback-by-subject/` — F-NNN 按 subject 路由

F-NNN 的 `verbatim` 字段（用户原话）是最高价值的 RFE 信号源——保留情绪 / 强度 / 具体场景。

**架构决策**：**markdown 主存 + markdown 切片包导出，不引入 JSONL**——现代蒸馏管道（Axolotl / Unsloth / HuggingFace SFT trainer 等）直接吃 markdown，多一层中间格式徒增维护、丢失叙事（markdown body 里的因果链 reasoning trace 是顶级蒸馏样本）。

> 三个切片包的筛选规则、sanitize 规则、实现路径、subagent 化建议见 **`references/markdown-切片导出.md`**。
> 蒸馏触发机制（auto / manual 两档）见 **`references/蒸馏触发机制.md`**。

### 本 skill 的边界

只负责**把料备好**：写记录、推断 subject、采集 verbatim、产出切片包。**下游训练管道、聚类归纳、产出新 skill 是别的 skill 或人工要做的事。** 本 skill 不管训练、不管 fine-tuning、不管 RM/DPO 实际配置——只管原料的采集、归属和导出。

## 多 worktree / 多 scope 并发：时间戳记录 ID（v0.17 / Q-020）

### 何时触发

任何会让多个 Claude session 共享同一份 `.ieidev/memory/` 的场景：
- secondary worktree（通过 [worktree_link.py](../../hooks/lib/worktree_link.py) 自动 symlink）
- 多终端开同一仓库
- 主仓库 + 镜像/挂载点同时 Claude 会话
- 多员工 scoped 布局下，各员工有独立的 `staff/<canonical-id>/` scope（v0.14+，见§记忆 scope 分离）

### 新 ID 格式（v0.17+，Q-020）

`<Type> <YYYYMMDD-HHMMSS>-<who>[.<n>]`，其中：
- **Type**：`Step` / `Q` / `G` / `R` / `F`
- **YYYYMMDD-HHMMSS**：**本地时间戳**，由 `mint_record_id` 在落盘时自动生成
- **who**：git email 本地部分（`@` 前），无 git 环境时省略整个 `-<who>` 后缀（不写 `-None`）
- **[.<n>]**：同一写手同一秒内第二条起 `.2`、`.3`…（去重兜底）

**协调自由**：时间戳 + who 组合，worktree / 多机同时落盘也不会撞号（G-011 修复）。slug/counter 机制已**退役**（不再用于新记录 minting）。

举例：
- `Step 20260613-142301-ly`（主线，ly 落盘）
- `Step 20260613-142301-ly.2`（同秒第二条）
- `Step 20260613-142301`（无 git 环境，省略 who）
- `Q 20260613-150000-ly`（决策日志条目）
- `G 20260613-150100-ly`（踩坑日志条目）
- `R 20260613-150200-ly`（改进建议条目）
- `F 20260613-150300-ly`（skill 反馈条目）

### 智能体落 Step / Q/G/R/F 时的标准流程

**Step + Q/G/R/F 全部走 `mint_record_id` 时间戳形**（Q-020 决策）。新编条目统一用此接口，**不要**手写 `Q-NNN` / `G-NNN` 等旧顺序 ID。

```python
import sys
sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/hooks/lib")
from step_id import mint_record_id
from pathlib import Path

# Step 条目
record_id = mint_record_id("Step", Path(".ieidev/memory/state"))
# record_id = "Step 20260613-142301-ly"

# Q / G / R / F 同样写法，改 Type 参数即可
q_id = mint_record_id("Q", Path(".ieidev/memory/state"))
# q_id = "Q 20260613-150000-ly"

g_id = mint_record_id("G", Path(".ieidev/memory/state"))
r_id = mint_record_id("R", Path(".ieidev/memory/state"))
f_id = mint_record_id("F", Path(".ieidev/memory/state"))
```

然后用这个 ID 作为条目的标题：

```markdown
## Step 20260613-142301-ly: 实现 mint_record_id
triggers: [...]
日期：2026-06-13
...

## Q 20260613-150000-ly: 是否引入 Docker？
日期：2026-06-13
...

## G 20260613-150100-ly: pnpm install 漏装子包依赖
triggers: [...]
日期：2026-06-13
...
```

智能体可以直接读 [step_id.py](../../hooks/lib/step_id.py) 实现细节；本节只规范"用哪个接口"。

### 历史兼容（旧顺序 ID 冻结 + 双认）

- 现存 `Step main-N` / `Step <slug>-N` / `Q-NNN` / `G-NNN` / `R-NNN` / `F-NNN` 等顺序 ID **冻结**，不再 mint 新顺序 ID，但继续被 `parse_record_id` 解析（向后兼容）。
- `parse_record_id` 同时认时间戳格式（新）和顺序格式（旧），可安全混用于同一日志文件。
- `step_id_prefix_since` HTML 注释保留在 `执行日志.md` 作为历史标识，不再驱动 minting。

## 记忆 scope 分离（v0.14, P-C1）

### Opt-in 布局

ieidev-memory 支持两种物理布局，**flat 为默认，scoped 需手动迁移**：

| 布局 | 目录结构 | 适用场景 |
|---|---|---|
| **flat（默认）** | `.ieidev/memory/{执行日志.md, 决策日志.md, ...}` | 单人 / 主控单轨项目（现状不变） |
| **scoped** | `.ieidev/memory/{shared/<markdown>, staff/<canonical-id>/<markdown>}` | 多员工数字员工 dogfood |

### 检测方式

**`shared/` 目录存在 = scoped 布局**（`scope.is_scoped` 检测）。

**迁移命令**（手动、幂等）：
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/lib/migrate_scope.py --staff dev-engineer,req-architect
```
创建 `shared/`、各 `staff/<canonical-id>/` 目录，并将现有 flat 文件迁移进 `shared/`。

### shared/ — 项目时间线（所有员工共享）

存放项目级公共记录：
- 决策日志.md / 踩坑日志.md / skill-feedback.md / 当前状态.md
- 执行日志.md（主线 / shared scope 的 Step rollup）
- 改进建议.md / 方法论铁规.md / conventions.md / 每日汇总/ / 归档/

### staff/\<canonical-id\>/ — 员工专属执行 rollup

> ⚠️ **STALE（P-C2/Q-019），待 Phase B/C 重构**：staff 叙事 scope 已收窄——叙事仅 CEO/shared，**员工 = events + handoffs（无 per-员工叙事 Step）**，staff 目录稀疏化为仅 `reviewer`（评审经验）/ `cqo`（审计），dev/req 机器侧无 ieidev-memory 足迹。本节仍是旧 P-C1「员工各有执行 rollup」模型；defer 窗口期勿照此为 dev/req 建 scope。详见 P-C2 spec §8.2 / §0.5、记忆底座合稿 §5.3。

每位员工有独立目录（如 `staff/dev-engineer/`、`staff/req-architect/`），存放：
- 执行日志.md（该员工的 Step rollup，ID = `Step <canonical-id>-N`，如 `Step dev-engineer-1`）

### plumbing 留 root（不 scoped）

机器本地管道文件始终保留在 `.ieidev/memory/` 根目录，不跟随 scope 迁移：
- `state/`（计数器、pending-commits）
- `checkpoints/`（PreCompact 快照）
- `dataset/`（蒸馏切片包）
- `config.yaml` / `strict`（严格模式开关）
- `.last-*`（蒸馏时间戳标记）

### 召回 / brief / rollup 聚合

brief、recall、每日汇总等机制**自动跨 shared + 所有 staff scope 聚合**，并在输出中标注来源（`[shared]` / `[staff/dev-engineer]` 等），让主控一眼分辨。

### 框架仓保持 flat

kdev-agents 框架仓（主控单轨）**始终保持 flat 布局**。只有多员工 dogfood 项目才迁移到 scoped。

## 用 step-recorder dispatch 落 step（v0.12+）

### 何时 dispatch

每完成一个 step-worthy 工作单元（任务 / 决策 / 踩坑 / 用户评分），**主会话不要自己写 Step**——
dispatch [step-recorder](../../agents/step-recorder.md) subagent 负责。

判据（满足任一即 step-worthy）：
- 至少 1 个 commit + 完成了一个独立工作单元
- 或：一个 Q-NNN 决策推到拍板态
- 或：一个 G-NNN 踩坑被发现 / 解决
- 或：用户对一个工作单元给评分

**hook 兜底**：若主会话遗忘，commit hook 会累积 pending-commits.json；SessionStart / Stop brief 会显示
`🔔 pending step-recorder dispatch: N commit 累积`——看到提醒立刻 dispatch。

### Dispatch 标准格式

````python
Agent({
  subagent_type: "general-purpose",
  model: "sonnet",
  description: "Record Step <slug>-<N>",
  prompt: """
You are step-recorder. Read ${CLAUDE_PLUGIN_ROOT}/agents/step-recorder.md
for role + 8 hard-gates + action sequence. Work from <repo root>.

## Input (YAML)
```yaml
title: <concrete verb + concrete object>
about: project | feature/<name> | bugfix/<name>
scope: shared                 # shared（缺省）| <canonical-id>（员工 scope，如 dev-engineer）
commit_shas: [...]
files_touched: [...]
key_decisions: [...]
key_facts:
  tools_invoked_count: <int>
  errors_hit: <int>
  detours: <int>
  token_feel: light | medium | heavy
self_eval_score: 1-5
self_eval_deduction: <substantive — empty REJECTED>
triggers: [...]   # ≥ 5
references: [...]
commits_batch_id: <Q-NNN or null>
```
"""
})
````

**`scope` 字段说明**：
- 缺省 / `shared`：主线活动，Step 写入 `shared/执行日志.md`（flat 布局则写根目录执行日志.md）
- `<canonical-id>`（如 `dev-engineer`）：员工活动，Step 写入 `staff/<canonical-id>/执行日志.md`

主控 dispatch 员工 step 时，将 `scope` 设为该员工的 canonical id；主线活动留空或填 `shared`。step-recorder agent 读取该字段决定落盘路径和 slug（详见 [agents/step-recorder.md](../../agents/step-recorder.md)）。

完整 schema、8 hard-gate 规则、反例对照、action sequence 详见
[agents/step-recorder.md](../../agents/step-recorder.md)。

### 为什么 dispatch 而不是主会话自己写

主会话被任务流吸住、自然停顿点被预期下一棒吞没——遗忘是常态（R-001 痛点：5/27 实测 75% under-reporting）。
dispatch fire-and-forget = 主会话只付出 ~30 行 YAML 写作 + 立即继续，subagent 干 Read/算/Write/Edit。
比"自己 Read 执行日志 + mint + Write 4 段 + Edit 当前状态" 轻 5-10x。
