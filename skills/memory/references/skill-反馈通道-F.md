# skill-feedback.md（F-NNN）反馈通道

## 什么时候读本文件

- 用户在对话流里对外部 skill / 插件 / 工具 / 方法论 / 协作模式说出 5 类语义之一（RFE / 痛点 / bug / 表扬 / 困惑）
- 用户给 Step 打分时夹带了 skill 反馈，触发评分裂解（详见 `references/subject-推断与评分裂解.md`）
- 第一次写 F-NNN 条目，确认 schema 和铁规
- 准备实现 `/ieidev-team:memory-distill` 的 `dataset-skill-feedback-by-subject/` 切片

## 这个文件存在的原因

`改进建议.md`（R-NNN）的定位是**项目内方法论反思** —— 例如"字段对齐这件事应不应该升铁规"。

但用户随口对**外部 skill / 工具**的吐槽（"ieidev-memory 召回太吵"/"bash 这操作老报错"/"frontend-design 这次没共鸣"）不属于项目方法论——它是：
- **对 skill 维护方的反馈** / RFE backlog 项
- **未来 skill 自主优化的训练信号**（顶级蒸馏原料）

把这两类信号混在 R-NNN 里：
- 改进建议被稀释，跨项目聚类时主题混乱
- 蒸馏管道按 subject 切训练集时，"R-001 字段对齐"和"R-003 ieidev-memory 召回吵"会被错误归类，污染各自的训练集

所以新增 **skill-feedback.md（F-NNN）** 作为物理隔离的反馈通道。

| 通道 | 编号 | 用途 | subject 范围 |
|---|---|---|---|
| 改进建议.md | R-NNN | 项目内方法论反思 | 仅 `methodology:<本项目>` |
| skill-feedback.md | F-NNN | 对外部 skill / plugin / 工具的反馈 | `skill:` / `plugin:` / `tool:` / `methodology:` / `collaboration:` |

## 三铁规

| # | 铁规 | 违反后果 |
|---|---|---|
| 🔴 1 | **subject 必填**（详见 `references/subject-推断与评分裂解.md`） | 蒸馏 dataset 无法按 subject 切片 |
| 🔴 2 | **verbatim（用户原话）必填**，智能体不可改写、不可总结、不可抽象化 | 丢失情绪 / 强度 / 场景细节，蒸馏价值跌一个量级 |
| 🟢 3 | **score 显式可空**（不强制打分） | 强制打分会拉低反馈密度，吐槽采集要低摩擦 |

### 为什么 verbatim 必须保留原话

蒸馏价值排序 = **原话 > 改写 > 打分**：

| 形式 | 信息量 | 蒸馏用途 |
|---|---|---|
| 打分（4/5） | 极低 | 只能学到偏好方向 |
| 改写（"用户认为召回准确性不足"） | 中 | 丢情绪、强度、场景 |
| 原话（"这破召回要是能学着不刷屏就好了"） | **最高** | 直接训 RM / 提 RFE / 做指令微调 |

强制改写就是数据贬值。智能体看到用户吐槽时的本能改写冲动（"嗯，意思是用户希望召回有 demote 机制"）必须抑制——**原话原样落盘**。

## v0.17+ ID 格式

**新编 F 条目用 `mint_record_id("F", state_dir)` 生成时间戳 ID**（如 `F 20260613-150300-ly`），不再手写 `F-NNN` 顺序号。现存 `F-NNN` 冻结、`parse_record_id` 双认。

```python
from step_id import mint_record_id
from pathlib import Path
f_id = mint_record_id("F", Path(".ieidev/memory/state"))  # => "F 20260613-150300-ly"
```

## schema

```yaml
## F-NNN: <简短标题>  <!-- legacy 顺序 ID 示例，冻结；新编用时间戳形 ## F 20260613-150300-ly: 标题 -->
日期: YYYY-MM-DD
subject: <subject>                                    # 铁规 1：必填
subject_inferred_by: L1-显式提及 | L2-上下文 | L3-用户选择
subject_confidence: high | medium | low
type: 痛点 | RFE | bug | 表扬 | 困惑                  # 5 类语义之一
verbatim: "<用户原话>"                                # 铁规 2：必填，不可改写
context: <发生时的简要场景>                            # 智能体补充
diagnosis: <可能的原因，假设语气>                       # 智能体补充，可选
desired: <如可推断，用户希望的形态>                     # 智能体补充，可选
score: null | 1 | 2 | 3 | 4 | 5                       # 铁规 3：显式可空
```

### 完整示例

```yaml
## F-001: ieidev-memory 召回噪声大
日期: 2026-05-12
subject: plugin:ieidev-memory
subject_inferred_by: L1-显式提及（用户直接说出名字）
subject_confidence: high
type: 痛点
verbatim: "这破召回要是能学着不刷屏就好了"
context: 用户在 Step 5 评分时夹带了这句吐槽（评分裂解触发）
diagnosis: triggers 关键词过宽，命中率太高
desired: 增加 demote 机制（同 session 同主题命中多次时降级）
score: null
```

## 5 类语义自动识别

智能体在主对话流里检测以下语义模式自动**起草** F-NNN（**注意：起草不是直接落盘——还要走"落盘前一句话确认"流程**）：

| type | 关键词模式 | 典型例子 |
|---|---|---|
| **RFE** | "如果 X 就好了 / 要是能 X / 希望 X / 想要 X / 加个 Y 多好" | "要是这玩意能记住上次选啥就好了" |
| **痛点** | "这玩意 / 这破 / 不好用 / 烦 / 吵 / 没用 / 太慢 / 太重" | "这破工具老报权限错误" |
| **bug** | "为啥 / 咋回事 / 怎么会这样 / 不应该是这样吧 / 是不是坏了" | "为啥它把无关的也匹配出来了？" |
| **表扬** | "干得对 / 这次准 / 帮大忙 / 牛 / 好用 / 真省事" | "ieidev-memory 这次召回挺准的" |
| **困惑** | "看不懂 / 啥意思 / 为啥要这么干 / 这有啥用" | "这个 frontmatter 为啥要有 status 字段啊？" |

### 边界：哪些不属于 F-NNN

⚠️ **不要过度激进采集**。以下情况**不**起 F-NNN：

- 用户在讨论项目代码本身的问题 → 走 G-NNN / R-NNN
- 用户引用别人的吐槽 / 反讽 / 段子 → 不采集
- 用户对自己写的代码不满意 → 走 R-NNN（项目内反思）
- 用户在 brainstorm 假设 / "如果 X 的话 Y 会..." → 不采集（不是 RFE）

如果智能体识别置信度低（不确定是不是真反馈），**宁可不起 F**——补漏比错记容易。

## 落盘前一句话确认（防误采）

智能体推断完 subject + type + verbatim 后，**落盘前必须用一句话向用户确认**：

> "听到你说 [verbatim 摘要]，记到 skill-feedback.md 给 subject `<subject>` 当 [type] 信号，对吗？"

| 用户回答 | 智能体行为 |
|---|---|
| "对" / "嗯" / "好" / "记吧" / 积极回应 | 实际写入文件 |
| "不是" / "别记" / "错了" / "无所谓" | 丢弃草稿 |
| "是 X 不是 Y" / "subject 错了" | 修正 subject 后落盘 |
| 用户开始改 verbatim | **保留用户原话**，不要按修正版改写——只允许用户调整 subject / type / context，verbatim 一字不改 |

**为什么必须确认**：5 类语义识别会有 false positive。一句话确认是低成本的精度保险，相比"先记错再事后改"摩擦小得多。

## 评分裂解（与 Step 评分的关系）

用户给 Step 打分时常夹带 skill 反馈，这是 **F-NNN 采集的最大流量来源**。例：

> 用户："顺畅度 4 分，主要是 ieidev-memory 召回太吵打断了节奏"

**正确处理**：拆两条独立条目落盘：

| 条目 | 文件 | 内容要点 |
|---|---|---|
| 1 | 执行日志.md Step 评分段 | 顺畅度 4/5（subject 隐含 = project） |
| 2 | skill-feedback.md F-NNN | subject: plugin:ieidev-memory / type: 痛点 / verbatim: "主要是 ieidev-memory 召回太吵打断了节奏" |

详见 `references/subject-推断与评分裂解.md` 的"评分裂解"章节。

## subagent 化建议（决策 4 落地）

F-NNN 的实体写入是 **subagent 异步 fire-and-forget 的最大杠杆点**（详见 `references/subagent-落盘机制.md`）：

```
主会话同步：识别 5 类语义 → 推断 subject → 一句话向用户确认
   ↓ 用户确认后
主会话 fire-and-forget 调 subagent → 写 skill-feedback.md → 返回状态行
主会话继续主线对话，不被"写日志"动作打断
```

`inline` 模式下不开 subagent，直接主会话写入。两档行为一致，差别仅在"是否打扰主会话上下文"。

## 蒸馏价值与导出

F-NNN 是 markdown 切片导出（决策 3）的核心数据源：

- `dataset-full.md` —— F 全量条目
- `dataset-skill-feedback-by-subject/<subject>.md` —— 按 subject 切片，每 subject 一个独立 markdown 文件，用于"这个 subject 自主优化"训练集

详见 `references/markdown-切片导出.md`。

## 未决问题（首批数据出来后再定）

1. 多 skill 并用时同一句话该拆几条 F？（如"这次 brainstorm + ieidev-memory 都很顺"是 1 条还是 2 条）
2. subject 命名空间稳定性（skill 改名后老 F 数据对齐策略）
3. 是否让 Claude 自己也独立打 skill 分（用户视角 vs Claude 视角双轨）
4. 5 类语义识别的误采阈值如何收敛
5. fire-and-forget 失败时如何告警（主会话已不等）
