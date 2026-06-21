# subject 三级推断与评分裂解

## 什么时候读本文件

- 第一次写 Step 评分 / F-NNN 反馈，需要确定 subject 字段时
- 用户给 Step 打分时夹带了对 skill 的吐槽，要决定怎么拆条目
- 推断不出 subject 时要走 L3 候选 disambiguate 流程
- 实现 F-NNN 写入时的 subject_inferred_by / subject_confidence 字段

## 这个机制存在的原因

落盘的评分数据要被**下游知识蒸馏管道**消费——蒸馏需要按 subject 切训练集（对 plugin:ieidev-memory 的反馈 vs 对 project 的评分要分开成训练集）。

如果所有打分混在"对项目"假设里，蒸馏 dataset 就是脏的：
- ieidev-memory 改进信号会混进 frontend-design 训练样本
- 反向训练失败，skill 自主优化无从谈起

**但 subject 不能让用户每条手填**——摩擦太大，反馈密度会暴跌。所以 subject **必须由智能体自动推断**，用户只在推断置信度极低时才被请求 disambiguate。

## subject 类型枚举

| subject 值 | 含义 | 例子 |
|---|---|---|
| `project` | 对项目本身结果的评分（默认） | "代码跑通了，4 分" |
| `skill:<name>` | 对某个 skill 的反馈 | `skill:brainstorming` |
| `plugin:<plugin-name>/skill:<skill-name>` | 对某 plugin 内某 skill 的反馈（更精确） | `plugin:ieidev-memory/skill:ieidev-memory` |
| `tool:<name>` | 对某工具的反馈 | `tool:bash` / `tool:Read` |
| `methodology:<name>` | 对方法论的反馈 | `methodology:TDD` / `methodology:四段必填` |
| `collaboration:<pattern>` | 对协作模式的反馈 | `collaboration:opus-design-sonnet-code` |
| `unknown` | 推断不出（蒸馏时整体过滤掉） | 安全的失败模式 |

## L1 / L2 / L3 三级推断

约 90% 场景不需要打扰用户。

### L1 显式提及（~40%）

用户原话直接说出 skill / plugin / 工具名 → 字符串匹配直接定 subject。

**例**：

| 用户原话 | 推断 subject |
|---|---|
| "ieidev-memory 召回太吵" | `plugin:ieidev-memory` |
| "刚才那个 trigger-match 又不准了" | `plugin:ieidev-memory/skill:ieidev-memory`（指 lib/trigger-match.py 对应的 skill） |
| "TDD 这套对这种任务太重" | `methodology:TDD` |
| "Opus 设计这次 hit" | `collaboration:opus-design-sonnet-code` |
| "bash 这操作老报错" | `tool:bash` |
| "brainstorming skill 引导得很好" | `skill:brainstorming` |

### L2 上下文推断（~50%）

L1 没明确提及时，取以下信号推断：
- 当前 Step 内最近调用的 skill / 工具（执行事实段「使用的 skill」字段是好信号源）
- 紧挨着用户反馈的 hook 注入对应的 plugin

**例**：

| 上下文 | 用户原话 | 推断 |
|---|---|---|
| 智能体刚被注入 `<ieidev-memory-recall>` | "召回太多了" | `plugin:ieidev-memory` |
| 当前 Step 执行事实段「使用的 skill」= `[brainstorming]` | "这次思路打得很开" | `skill:brainstorming` |
| 主会话前一轮调了 `Agent` tool | "subagent 这次没把握重点" | `tool:Agent` |
| 用户刚 Read 了 SKILL.md，下一句吐槽 | "这文档读起来累" | `plugin:<当前 skill 所属 plugin>` |

### L3 候选 disambiguate（~10%）

L1/L2 都推不出时，给用户 **2-3 个候选选一个**（绝不要求用户从零打字）。

**例**：

> 智能体：你说"不准"是指：(a) ieidev-memory 召回 (b) trigger-match 关键词匹配 (c) 别的？请选 a/b/c 或说明。

用户答 (a) → 落 `plugin:ieidev-memory`。

**绝不要这样问**：
- ❌ "subject 是什么？"（让用户从空白打字）
- ❌ "这是对什么的反馈？"（同上）

## 置信度字段（F-NNN frontmatter 必填）

```yaml
subject: plugin:ieidev-memory
subject_inferred_by: L2-上下文（前句有 ieidev-memory-recall 注入）
subject_confidence: high | medium | low
```

| 置信度 | 落盘行为 | 蒸馏导出过滤 |
|---|---|---|
| **high** | 直接落盘，不打扰用户 | 训练集主体 |
| **medium** | 落盘 + 在文末注 "(推断 subject=X，如错请 edit)" | 走人工抽检 |
| **low** | **必须走 L3 询问后落盘**（不允许跳过确认） | 噪音剔除（除非用户已确认） |

### 置信度判断启发式

| 推断方式 | 默认置信度 |
|---|---|
| L1 显式提及（用户原话直接含 subject 名） | **high** |
| L2 上下文推断（hook 注入 / 「使用的 skill」字段命中） | **medium**（可被一句话确认升 high） |
| L2 但有多个候选都沾边 | **low**（必须走 L3） |
| L3 候选选一 | **high**（用户已确认） |

## 评分裂解（关键机制）

用户给 Step 打分时常夹带 skill 反馈。智能体必须**自动拆两条**落盘，绝不能塞同一条。

### 典型例子

用户说："顺畅度 4 分，主要是 ieidev-memory 召回太吵打断了节奏"

#### ❌ 错误做法（污染数据集）

```markdown
## Step N
### 用户评分
- 顺畅度：4/5
- 用户评价："主要是 ieidev-memory 召回太吵打断了节奏"
```

后果：
- "ieidev-memory 召回太吵"这条 skill 反馈被淹没在项目分里
- 蒸馏导出 `dataset-skill-feedback-by-subject/plugin-ieidev-memory.md` 时遗漏这条
- 蒸馏导出 `dataset-misalignment.md` 时这条 Step 算项目差值，但实际差值是 skill 引起的——归因错误

#### ✅ 正确做法（评分裂解）

**条目 1**：执行日志.md Step 评分段

```markdown
### 用户评分
- 完成时间：2026-05-12 14:35
- 顺畅度：4/5
- 用户评价：（用户对项目结果的简要评价；skill 反馈已拆到 F-NNN）
- 🚨 关键 GAP：（如有）
```

**条目 2**：skill-feedback.md F-NNN

```yaml
## F-NNN: ieidev-memory 召回噪声大
日期: 2026-05-12
subject: plugin:ieidev-memory
subject_inferred_by: L1-显式提及
subject_confidence: high
type: 痛点
verbatim: "主要是 ieidev-memory 召回太吵打断了节奏"
context: 在 Step（无前缀/带前缀 `<branch-slug>-N` 或时间戳 `<ts>-<who>`）评分时夹带反馈（评分裂解触发）
diagnosis: triggers 关键词过宽或同主题重复召回
desired: demote 机制 / 同 session 重复命中降权
score: null
```

### 评分裂解的判断启发式

用户的一段评价是否含 skill 反馈？看是否提到：

| 信号 | 是否拆？ |
|---|---|
| 提到 skill / plugin / tool 名字 | **一定要拆** |
| 5 类语义关键词（"X 不好用 / 要是能 Y / 这破 X"等） | **一定要拆** |
| 提到方法论 / 协作模式（"TDD 那套" / "Opus 设计"） | **一定要拆** |
| 中性叙述（"这个任务挺顺" / "功能跑通了" / "代码量比预期多"） | **不需要拆**（属项目分） |
| 对智能体本身工作的吐槽（"你这次没领会"） | **不拆**（这是项目分内的负面信号，进 GAP 段） |

### 评分裂解后的 verbatim 处理

拆出去的 F-NNN 的 verbatim 字段，保留**用户原句中关于 skill 的那部分**：

- 原话："顺畅度 4 分，主要是 ieidev-memory 召回太吵打断了节奏"
- F.verbatim = `"主要是 ieidev-memory 召回太吵打断了节奏"`（去掉评分前缀，保留 skill 吐槽原话）

**不要**改写成`"用户认为 ieidev-memory 召回过于嘈杂"`——这违反 verbatim 不可改写铁规。

## fallback：推不出归 unknown

绝不能默认归 `project`——会污染项目评分子集，蒸馏 dataset 全脏。

`unknown` 在蒸馏时能被整体过滤掉，是安全的失败模式。后期可由用户/抽检人工回填。

```yaml
subject: unknown
subject_inferred_by: L2-上下文（无明确信号 + 多 skill 共用）
subject_confidence: low
```

蒸馏导出脚本看到 `subject:unknown` 自动跳过。

## 用户视角的体验保证

| 场景 | 用户要做的 |
|---|---|
| 顺口吐槽 skill | 啥也不用做（L1/L2 自动） |
| 评分时夹带反馈 | 啥也不用做（评分裂解自动） |
| 推断置信度低 | 在 2-3 个候选里点一下（不打字） |
| 智能体推错了 | 事后改一行 `subject:` 字段（markdown 主存可编辑） |

**用户永远不会被要求从空白填 subject。** 这是降摩擦的硬约束——违反此约束等于 F-NNN 通道失效。

## 与 Step schema 的集成（about 字段）

Step 条目的顶部字段可显式加 `about: <subject>`（缺省 = `project`，可不写）：

```markdown
## Step 7: 实现 token 采集器核心循环
triggers: ["采集器", "核心循环"]
日期：2026-04-15
status: open
about: project           # 缺省可不写，默认 project
```

只有 Step 评分**完全**是关于某个 skill 而不是项目时才显式写 `about: skill:X`（罕见——绝大多数 Step 是项目动作，对 skill 的评价应该走 F-NNN）。

详见 `references/六类记录-schema.md` §3 的"about 字段"段。

## 未决问题（首批数据出来后再定）

1. 多 skill 并用时同一句话该拆几条 F（如"这次 brainstorm + ieidev-memory 都很顺"）
2. subject 命名空间稳定性（skill 改名后老数据对齐策略）
3. 是否让 Claude 自己也独立打 skill 分（用户视角 vs Claude 视角双轨数据）
4. L2 推断的"hook 注入紧挨着"窗口阈值（多少轮对话内的 hook 仍算上下文信号？）
5. L1 字符串匹配的命名空间扩展（用户用昵称"老 km"指 ieidev-memory 怎么处理？）
