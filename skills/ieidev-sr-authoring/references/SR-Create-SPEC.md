# SR Pipeline Contract

> **Audience**: 任意 agent（Claude Code / Cursor / Cline / 自研 agent / 纯 LLM 调用 / CI 脚本 / 人）；与 IDE 或 skill 框架无关。
> **Status**: Active
> **Version**: 1.0
> **Date**: 2026-05-23

本契约定义 SR（System-level Requirement，系统级别需求）的：
- 文档结构与字段约定（§3）
- 产出步骤（§4）
- 评审清单（§5）
- 可选机械工具的 I/O（§6）

任意 agent 读完本文档后，无需读其他文件即可产出或评审一份 SR。

## 1. Purpose & Audience

### 1.1 目的

提供一份**自包含、agent-agnostic** 的 SR 操作契约。具体地：
- 定义 SR 文档的固定模板（Part A Brief + Part B SR-Items）；
- 规范 SR 的产出流程（4 阶段：吸收上下文 → 澄清 → 写作 → 自检）；
- 规范 SR 的评审标准（5 条机械规则 MC-1..5 + 7 条 LLM 红线 R1..7）；
- 不绑定特定 IDE、特定 skill 系统、特定语言/框架。

### 1.2 读者

- **任意 agent**：依据本契约产出符合规范的 `spec.md`，或对既有 `spec.md` 执行评审。
- **人类协作者**：在没有任何工具的情况下也能完成 SR 创建与评审。
- **CI / 自动化**：通过 §6 描述的工具 I/O 集成 SR 校验到流水线。

### 1.3 不在范围

- 上游"原始需求"如何收集（依赖各组织的实践）
- 下游制品（无论什么形式）如何从 SR 推导出来（本契约不规定下游契约）
- 任何特定 agent / IDE 的触发约定（这是 agent 集成层的事）

## 2. SR 在需求生命周期中的位置

SR 是"原始需求"经过结构化整理后的中间制品。它具备以下三个核心属性：

1. **可评审**：SR 是评审的对象，必须按 §5 清单可被人或 LLM 系统性扫查。
2. **可被下游消费**：SR 不是终点，会被某种下游制品（设计、测试、计划、文档等）进一步消化；具体下游类型不由本契约规定。
3. **稳定可追溯**：每条 SR-item 有不重号的 ID，是上下游追溯链的稳定主键。

SR 的颗粒度是 **能力 / feature 粒度**（中等）：一条 SR-item 对应一个业务能力或特性包，可能隐含若干页面、操作、字段。比 backlog item 粗，比"产品愿景"细。

## 3. SR Template

### 3.1 文件路径 / Frontmatter / ID 约定

**文件路径**：`specs/<feature-set-slug>/spec.md`

`<feature-set-slug>` 使用 kebab-case，例：`devsec-projver`、`knowledge-fav`。

**文件 Frontmatter 形态**：

```markdown
# Spec: <Feature Set 中文名称>

**Status**: Draft | Review | Approved
**Version**: v0.1
**Owner**: <责任人>
**Date**: YYYY-MM-DD
**Downstream** (可选): <下游制品路径或类型描述；无下游时省略此行>
**References**: <既有上下文文档相对路径列表>
```

**Downstream 字段语义**：
- **可选**：缺席不触发任何评审失败
- **通用**：值是下游制品的路径或类型描述，不预设是任何特定文件类型
- 既有 SR 实例若已写 `**Downstream**: ./testable-requirements.md (TRD)` 之类的具体值，保留原值即合规

**SR-item ID 规范**：

格式：`SR-<FEATURE-SET-SLUG-UPPERCASE>-<NN>`

示例：`SR-DEVSEC-PROJVER-01`、`SR-DEVSEC-PROJVER-02`、…

规则：
- `<NN>` 为 2 位零填充顺序号
- **不重号、不回收**：废弃的 SR-item 标 `Status: Deprecated` 保留在文档内，序号不回收，跨阶段追溯稳定
- **不引入上层 ID**（如 IR-/AR-）：模块分组由 markdown 二级标题 `## Group: <模块名>` 自然表达，不进 ID

### 3.2 Part A — Brief

固定 6 个模块，缺一不可。如某模块"不适用"，必须**显式写出"不适用"**而非省略。

#### A.1 背景与目标 (Background & Goal)

- **目的**：交代为什么做这个 feature set、要解决的业务问题、目标状态。
- **推荐篇幅**：100–250 字，1–3 段叙述。
- **禁止**：技术选型、实现路径、UI 样式。

#### A.2 范围与边界 (Scope & Boundaries)

- **In-scope**：粗粒度特性清单（与 Part B 每条 SR-item 对应）。
- **Out-of-scope**：显式排除项 + 理由。
- **与既有系统 / 未来迭代的边界**：相对现有系统新增/复用了什么；哪些被推迟。

#### A.3 目标用户与场景 (Users & Scenarios)

写 US-level 业务场景叙述，**不是用户故事**——用户故事下沉到 Part B 每条 SR-item。

- **主要用户角色**：角色名 + 主要职责/关心什么；含系统角色和外部系统角色。
- **关键业务场景**：3–6 个，每个 1 段，描述"什么时机 / 谁 / 想完成什么 / 期望结果"。

> 评审纪律：A.3 的每个场景必须能映射到至少一条 SR-item（见 §5.2 R6）。

#### A.4 关键实体提要 (Key Entities)

**只列实体名 + 一句话用途 + 与其他实体的关系**。字段表、约束、权威来源等细节下沉给下游制品。

格式：
```markdown
- **<Entity 1>**: <一句话用途>；关系：<与其他实体的从属/引用关系>
```

如有既有实体定义文档，在此引用其相对路径。

#### A.5 横向约束 / 集成边界 (Cross-cutting Constraints)

不属于单条 SR-item、但每条都必须遵循的规则。**用业务语义描述，不写技术实现**。

**核心模块**（如适用必填；不适用则显式写"不适用（理由：…）"）：

- **权限模型**：是否采用可配置 RBAC；功能权限点命名约定（如 `entity:action`）；数据范围维度有哪些；前后端校验责任分层。**禁止写死角色名**（详见 §5.2 R1）。
- **数据范围**：数据范围维度、多授权语义、与权限点组合判定的语义。
- **外部系统集成**：每个外部系统的同步方向、字段权威粗描、触发方式、开发期是否需要 mock。
- **非功能约束**：性能 / 安全 / 合规 / 可用性 / 可观测性中存在硬性目标的，列出可观察指标。

**可选模块**（按 feature set 实际情况启用，无则整块省略）：

- 审计与可追溯
- 隐私与数据保护
- 国际化与本地化
- 兼容性
- 错误处理与降级
- 升级与数据迁移

#### A.6 总体成功标准 + Open Questions

- **Success Criteria (SC-N)**：用户/业务侧可观察的成功条件。
- **Open Questions (OQ-N)**：对实现/测试有影响的未决问题。**评审通过时本块的 OQ 必须为空（写"无"或整块缺席）**。

### 3.3 Part B — SR-Items（轻 SR 模板）

#### 总体结构

```markdown
## Part B — SR Items

## Group: <模块 1 名称>

### SR-<SLUG>-<NN>  <SR 标题>
…

### SR-<SLUG>-<NN+1>  …

## Group: <模块 2 名称>

### SR-<SLUG>-<NN+m>  …
```

`## Group` 仅作阅读组织，不进入 ID。

#### 单个 SR-item 的固定字段

```markdown
### SR-<SLUG>-<NN>  <SR 标题>

**Priority**: P0 / P1 / P2 / P3
**Status**: Draft / Review / Approved / Deprecated
**Depends on**: SR-XXX-NN, … | 无

**用户故事**
作为 <用户角色>，我想要 <能力>，以便 <业务价值>。

**范围**
- 包含：<操作/能力 1>、<操作/能力 2>…
- 不包含：<显式排除项；写"无"也行，不可省略>

**验收要点**（3–8 条）
- <可观察的成功条件 1>
- <可观察的成功条件 2>
- …

**Open Questions**（可选；该条留空时整块省略）
- OQ-<SR-NN>-1: <具体未决问题；评审解决后删除或转下游>
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| Priority | 是 | P0/P1/P2/P3 |
| Status | 是 | Draft / Review / Approved / Deprecated |
| Depends on | 是 | 单方向引用其他 SR-ID；无依赖写"无"；不维护反向 "Used by" 字段 |
| 用户故事 | 是 | 「作为 X，我想要 Y，以便 Z」单句 |
| 范围 - 包含 | 是 | 粗描该 SR 覆盖的能力/操作集合 |
| 范围 - 不包含 | 是 | 显式排除项；写"无"也算填 |
| 验收要点 | 是 | 3–8 条可观察的成功条件 |
| Open Questions | 否 | 评审通过时必须清空（删除整块） |

#### 验收要点的写作纪律

| 必须 | 禁止 |
|---|---|
| 描述系统应有的可观察行为 | 描述实现细节（组件名 / SQL / 索引 / 具体接口） |
| 表达业务侧约束的"存在性"（唯一、必填、不可删…） | 写出完整字段表或字段级类型/长度规则 |
| 指明关键失败/异常场景如何对用户表现 | 写出完整错误码表 / 接口契约 |
| 用权限点 + 数据范围语义描述授权 | 写死角色名（如"只有 Admin 可删"） |

## 4. Creation Procedure

### 4.1 输入要求

执行本流程前，必须备齐：

- **原始需求材料**：任意形式（用户访谈纪要 / 产品规划摘要 / 客户问题列表 / 上游 PRD 草稿 / 既有 prose 需求等）。
- **既有上下文**：实体定义文档（如有）、外部系统手册、组织既有的权限/数据范围框架说明、相关历史 spec。
- **边界已知项**：哪些不在本迭代、有哪些已确认的硬约束（截止日期 / 合规 / 性能 / 兼容性）。

### 4.2 阶段 1：吸收上下文

按以下顺序读完所有文件，再开始动笔：

1. 本契约（即 `docs/sr-pipeline/CONTRACT.md`）—— 模板规范的唯一权威源
2. 用户提供的原始需求材料
3. 既有的实体定义文档、外部系统手册（如用户引用）
4. 相关历史 spec（如本 feature set 与既有 spec 有重叠或衍生关系）

### 4.3 阶段 2：澄清问题（brainstorm 风格）

按以下顺序、每次一个问题向用户确认，优先用 multiple-choice：

1. **Feature set slug**：建议一个 kebab-case slug（如 `devsec-projver`），询问用户确认。
2. **业务目标一句话**：本 feature set 解决什么问题？
3. **范围边界**：哪些明确不在本迭代？
4. **主要用户角色**：3 个以内主要角色 + 是否涉及系统/外部系统角色。
5. **关键实体**：列实体名 + 一句话用途；如已有实体定义文档，请用户给路径。
6. **横向约束盘点**（A.5 核心 4 类）：权限模型 / 数据范围 / 外部集成 / NFR，逐个确认是否适用；不适用要在 spec 里显式写"不适用（理由：…）"。
7. **可选横向模块**（审计/隐私/i18n/兼容性/降级/迁移）：逐个确认是否启用。
8. **核心特性清单**：用户列出粗粒度特性；为每条预分配 SR-NN 编号。

### 4.4 阶段 3：写 spec.md 主体

按 §3.1 文件头 → §3.2 Part A 6 块 → §3.3 Part B SR-items 顺序写。每写完一块可向用户呈现，确认后继续。

**Part A 写作要点**:
- A.1 100–250 字业务背景，不写技术。
- A.2 In-scope 与 Part B SR-item 1:1 对应；Out-of-scope 给理由。
- A.3 业务场景叙述（非用户故事）；3–6 段。
- A.4 实体名 + 一句话用途 + 关系；**禁止贴字段表**（详见 §5.2 R2）。
- A.5 业务语义描述；**禁止写死角色名 / SQL / 索引**（详见 §5.2 R1、R3）。
- A.6 SC 可观察、不写实现细节；OQ 列已知未决问题，待评审通过时清空。

**Part B 写作要点**:
- ID 格式：`SR-<SLUG-UPPER>-<NN>`，2 位零填充顺序号。
- 6 必填字段 + 1 可选字段（见 §3.3 字段说明表）。
- 用户故事单句格式："作为 X，我想要 Y，以便 Z"。
- 验收要点 3–8 条；只写可观察行为；遵循 §3.3 的"验收要点写作纪律"。

### 4.5 阶段 4：自检

写完后，自检以下清单。所有项通过才进入评审：

- [ ] Part A 6 块齐全；A.5 核心 4 类不适用显式写"不适用"
- [ ] Part B 至少 1 条 SR-item，每条 6 必填字段齐全
- [ ] 所有 OQ 已清空或显式写"无"（若 Status 计划升到 Review/Approved）
- [ ] Depends on 引用的 SR-ID 都在文档内存在
- [ ] 文件头 frontmatter 完整，Status 设为 `Review`（如准备评审）

然后按 §5 进入评审。

### 4.6 红线：以下情况必须停下来询问用户，不得自行决定

- 关键实体不止 5 个时，是否分拆为多个 feature set
- 用户的原始需求里出现明显技术选型（如"用 React"），是否记录为 A.5 非功能约束的硬约束 OR 移除
- 出现跨 feature set 的强耦合时，是否纳入本 spec 范围
- 用户未明示但行业默认存在的非功能要求（如数据加密），是否记入 A.5

## 5. Review Checklist

评审分两层：
- **§5.1 机械规则 MC-1..5**：可被人/LLM/Python 工具机械判定
- **§5.2 LLM 红线 R1..7**：需要人/LLM 语义判断

通过条件：MC-1..5 全过 AND R1..7 全过。

### 5.1 Mechanical Rules

机械规则可由人、LLM 或 `tools/sr_check.py`（见 §6）独立执行。本节用自然语言完整描述每条规则，**不依赖 Python 也能执行**。

#### MC-1: Part A 6 块齐全

**What**: spec.md 中必须包含 Part A 的全部 6 个二级章节标题：A.1 背景与目标 / A.2 范围与边界 / A.3 目标用户与场景 / A.4 关键实体提要 / A.5 横向约束 / 集成边界 / A.6 总体成功标准 + Open Questions。

**Why**: 模板设计上 6 块各自承担独立责任。缺一块意味着该维度信息被遗漏或被混入其他块；即使章节"不适用"也必须显式存在并写"不适用"。

**How to verify manually**: 扫文档目录或用 grep `^### A\.[1-6]`；6 条都在即过。中文标题完整匹配（不含 trailing 空格、不含 emoji）。

**Tool reference**: `check_part_a_blocks` in `tools/sr_check.py`, rule label `A_BLOCKS_PRESENT`.

**PASS 示例**:
```
## Part A — Brief
### A.1 背景与目标
...
### A.6 总体成功标准 + Open Questions
```

**FAIL 示例**:
```
## Part A — Brief
### A.1 背景与目标
...
（A.4 缺失）
### A.5 横向约束 / 集成边界
```

#### MC-2: 无 TBD/TODO/FIXME 占位符

**What**: spec.md 全文（含 Part A、Part B、frontmatter）不允许出现 `TBD`、`TODO`、`FIXME` 单词边界匹配的占位符。

**Why**: 占位符意味着该处需求未定，把含占位符的草稿送评审是浪费评审员时间。

**How to verify manually**: `grep -nE "\b(TBD|TODO|FIXME)\b" spec.md`；任何 hit 即 fail。

**Tool reference**: `check_no_tbd` in `tools/sr_check.py`, rule label `NO_PLACEHOLDER`.

**PASS 示例**: `grep -nE "\b(TBD|TODO|FIXME)\b" spec.md` 返回空。

**FAIL 示例**:
```
### A.5 横向约束 / 集成边界
TBD
```

#### MC-3: 至少 1 条 SR-item 且 6 必填字段齐全

**What**: Part B 必须至少有 1 条 SR-item（以 `### SR-XXX-NN` 起始的 ### 级标题）；每条 SR-item 必须包含 6 个必填字段：`**Priority**`、`**Status**`、`**Depends on**`、`**用户故事**`、`**范围**`、`**验收要点**`。

**Why**: SR 文档的核心载荷是 SR-item；缺字段意味着评审者拿不到完整契约，下游也无法消费。

**How to verify manually**: 用 grep `^### SR-` 找所有 SR-item heading；对每个 SR-item 块体扫这 6 个 `**字段**` 标签是否存在。注意 `Priority` / `Status` / `Depends on` 三个字段是 `**字段**: 值` 同行格式；`用户故事` / `范围` / `验收要点` 是 `**字段**` 单独成行（值在下一行）。

**Tool reference**: `check_sr_item_required_fields` in `tools/sr_check.py`, rule labels `SR_ITEM_PRESENT` (无 SR-item) / `SR_ITEM_FIELD` (字段缺失).

**PASS 示例**:
```
### SR-FOO-01  Demo

**Priority**: P0
**Status**: Draft
**Depends on**: 无

**用户故事**
作为 X，我想要 Y，以便 Z。

**范围**
- 包含：a
- 不包含：b

**验收要点**
- 系统应能 X。
```

**FAIL 示例**: 同上但缺 `**Priority**: P0` 行。

#### MC-4: Depends on 引用合法

**What**: 每个 SR-item 在 `**Depends on**:` 后列出的 SR-ID 必须存在于本 spec.md 内（即必须能在某个 `### SR-XXX-NN` 标题中找到）。`无` 或空字符串豁免。

**Why**: 引用未定义的 SR-ID 意味着追溯链断裂；要么 typo，要么遗漏了该 SR 的定义。

**How to verify manually**: 提取所有 `### SR-XXX-NN` 标题里的 ID 形成"已定义"集合；对每个 `**Depends on**:` 行解析其中的 `SR-XXX-NN` token，逐个核对在已定义集合内。

**Tool reference**: `check_depends_on_references` in `tools/sr_check.py`, rule label `DEPENDS_ON_REF`.

**PASS 示例**:
```
### SR-FOO-01  A
**Depends on**: 无
...

### SR-FOO-02  B
**Depends on**: SR-FOO-01
...
```

**FAIL 示例**:
```
### SR-FOO-02  B
**Depends on**: SR-FOO-99
（文档内不存在 SR-FOO-99）
```

#### MC-5: 文档级 Status 合法

**What**: spec.md frontmatter 中的文档级 `**Status**:` 字段（即文件中第一个 `**Status**:` 出现位置；通常在顶部）必须存在，且取值在 `{Draft, Review, Approved}` 集合内。

**Why**: Status 是评审 Gate 流转的依据；取值非标准会导致评审/晋升流程失效。注意 SR-item 内的 `**Status**:`（per-item 状态）另有取值集 `{Draft, Review, Approved, Deprecated}`，本规则只校验"文件内首个" Status，即文档级。

**How to verify manually**: 从文件顶部找到第一个 `**Status**: <value>` 行，比对 value ∈ {Draft, Review, Approved}。

**Tool reference**: `check_frontmatter_status` in `tools/sr_check.py`, rule label `FRONTMATTER_STATUS`.

**PASS 示例**: `**Status**: Review` 在 frontmatter。

**FAIL 示例**: `**Status**: WhateverFancyValue` 或 frontmatter 缺 Status 字段。

#### MC 总览速查

| ID | 名称 | sr_check.py 函数 | rule label |
|---|---|---|---|
| MC-1 | Part A 6 块齐全 | `check_part_a_blocks` | `A_BLOCKS_PRESENT` |
| MC-2 | 无 TBD/TODO/FIXME 占位符 | `check_no_tbd` | `NO_PLACEHOLDER` |
| MC-3 | ≥1 SR-item 且 6 必填字段齐全 | `check_sr_item_required_fields` | `SR_ITEM_PRESENT` / `SR_ITEM_FIELD` |
| MC-4 | Depends on 引用合法 | `check_depends_on_references` | `DEPENDS_ON_REF` |
| MC-5 | 文档级 Status 合法 | `check_frontmatter_status` | `FRONTMATTER_STATUS` |

### 5.2 LLM Red-Lines R1..7

LLM 红线由人或 LLM 通读判定，无机械工具。每条红线沿用 §5.1 MC-N 五段式，差异为：把 "Tool reference" 替换为 "Look in"（指明扫查范围）。

#### R1: 写死角色名

**What**: SR 中不允许出现"只有 Admin 可…"、"管理员可以…"、"Editor 可以…"等以特定角色名作为授权判据的写法。

**Why**: SR 应基于权限点 + 数据范围表达授权语义，避免与具体 RBAC 角色实现耦合；既有项目改组织/换角色名时 SR 不应回退到此层。

**How to scan**: 通读 A.5 横向约束 + Part B 全部"验收要点"；找以下模式：`只有 <RoleName> 可…`、`<RoleName> 可以/不可以…`、`仅 <RoleName>…`。注意"平台管理员"作为 A.3 用户角色定义或场景叙述是合法的；红线只针对**授权判据**的写法。

**Look in**: Part A.5 + 每条 SR-item 的验收要点。

**PASS 示例**:
```
- 具备产品线删除权限点、且目标位于其授权数据范围的用户，可删除产品线。
```

**FAIL 示例**:
```
- 管理员可以删除产品线。
- 只有 Admin 可以执行删除操作。
```

#### R2: 越界贴字段表

**What**: SR 的 Part A.4（关键实体提要）只列实体名 + 一句话用途 + 关系；不允许出现完整字段表（含字段名/类型/必填/长度/默认值等列）。Part B 验收要点也不允许列举字段级类型/长度/默认值。

**Why**: 字段定义是下游制品（如 TRD 数据字典、ER 图）的责任；SR 越界会导致维护双源、且把可拆设计决策过早冻结。

**How to scan**: 在 A.4 与 Part B 验收要点扫 markdown table 模式（`| 字段 | 类型 | …`）以及任何把字段类型/长度/默认值并列描述的句子。

**Look in**: Part A.4 + 每条 SR-item 的验收要点。

**PASS 示例**:
```
- **产品线 (ProductLine)**：业务归属边界，最多 3 级层级。
```

**FAIL 示例**:
```
- **产品线 (ProductLine)**: 字段定义如下：
| 字段 | 类型 | 必填 |
| name | string | yes |
```

#### R3: 越界写技术实现

**What**: SR 不允许出现具体技术选型、SQL/索引、API 路径、HTTP 方法、错误码表、Given-When-Then 测试句式、具体组件/类/服务名。

**Why**: SR 是 WHAT 不是 HOW；技术实现属下游制品（设计/计划/代码）。

**How to scan**: A.5 与 Part B 验收要点扫以下信号词：`SQL`、`SELECT`、`POST /`、`GET /`、`HTTP 4xx/5xx`、`Given … When … Then`、`React`、`Spring`、`使用 <某 library>`、`在 <某 service> 类中`、表/索引名。

**Look in**: Part A.5 + 每条 SR-item 的验收要点。

**PASS 示例**:
```
- 同一上级下的产品线名称必须唯一，重复时不允许保存并提示。
```

**FAIL 示例**:
```
- 使用唯一索引 idx_productline_name 保证同级名称不重复。
- POST /api/productline 返回 201。
```

#### R4: 验收要点不可观察

**What**: 验收要点必须描述用户或系统可观察的行为/状态；不允许写非可观察的陈述（如"应该用某算法"、"在某 service 类中处理"）。

**Why**: 不可观察的要点不能被测试或评审，进入后续阶段就会成为隐式假设。

**How to scan**: 每条 SR-item 验收要点，问"如果我是测试员，我能不能从外部观察这一条是否满足？"答否则 fail。

**Look in**: 每条 SR-item 的验收要点。

**PASS 示例**:
```
- 取消收藏后该文章不再出现在"我的收藏"列表。
```

**FAIL 示例**:
```
- 应该用 React Context 实现状态共享。
- 使用某种缓存算法提高查询速度。
```

#### R5: A.5 写"不适用"前未论证

**What**: A.5 核心 4 类（权限模型 / 数据范围 / 外部集成 / NFR）若标"不适用"，必须附带理由（如"不适用（理由：本 feature set 不涉及外部系统）"），不允许裸"不适用"。

**Why**: 裸"不适用"让评审员无法判断是真不适用还是漏想；带理由的"不适用"能在评审时被有效挑战。

**How to scan**: 在 A.5 找"不适用"出现位置，看其后是否紧跟括号或冒号包裹的理由短语。

**Look in**: Part A.5 核心 4 模块。

**PASS 示例**:
```
**外部系统集成**：不适用（理由：本 feature set 是纯本地 CRUD，无外部依赖）。
```

**FAIL 示例**:
```
**外部系统集成**：不适用。
```

#### R6: 场景孤儿（A.3 场景无对应 SR-item）

**What**: A.3 中列出的每个"关键业务场景"（场景 S1, S2, …）必须能在 Part B 中找到至少一条 SR-item 覆盖（其范围或验收要点显式承担该场景）。

**Why**: 场景孤儿意味着 A.3 描述的业务需求落不到具体 SR-item，下游消费时该场景被遗漏。

**How to scan**: 列出 A.3 所有场景的核心动作关键词；在 Part B 每条 SR-item 的范围+验收要点中搜索是否覆盖该动作或其等价表述。

**Look in**: A.3 × Part B 交叉。

**PASS 示例**: A.3 列"场景 S2：批量导出"，Part B 有 `SR-XXX-NN 数据批量导出` 覆盖。

**FAIL 示例**: A.3 列"场景 S5：批量导出"，但 Part B 全部 SR-item 都不涉及导出。

#### R7: OQ 未清空

**What**: 当文档 Status 为 Review 或 Approved 时，A.6 的 Open Questions 块和每条 SR-item 内的 Open Questions 块必须都"已清空"——即写"无"或整块缺席。Status=Draft 时 OQ 可以非空。

**Why**: Open Question 代表"未决"；未决项进入 Review/Approved 状态意味着评审/发布建立在不完整契约上。

**How to scan**: 找文件首个 `**Status**:` 取值；若 ∈ {Review, Approved}，扫 A.6 的 OQ 子块 + 每条 SR-item 的 OQ 子块是否为空/写"无"/整块缺席。

**Look in**: A.6 + 每条 SR-item 的 OQ 块。

**PASS 示例**:
```
**Open Questions**: 无。
```

**FAIL 示例**（Status=Approved 时）:
```
**Open Questions**:
- OQ-1: 删除是否级联到下级？
```

#### R 总览速查

| ID | 名称 | Look in |
|---|---|---|
| R1 | 写死角色名 | A.5 + Part B 验收要点 |
| R2 | 越界贴字段表 | A.4 + Part B 验收要点 |
| R3 | 越界写技术实现 | A.5 + Part B 验收要点 |
| R4 | 验收要点不可观察 | Part B 验收要点 |
| R5 | 不适用未论证 | A.5 核心 4 类 |
| R6 | 场景孤儿 | A.3 × Part B 交叉 |
| R7 | OQ 未清空 | A.6 + 每条 SR-item OQ |

### 5.3 评审报告模板

评审者按以下结构产出报告（不必落盘，直接交付给调用者）：

```markdown
## SR Review Report: <spec.md 路径>

### 机械规则 (MC-1..5)
- MC-1 Part A 6 块齐全: PASS / FAIL [+ findings 行]
- MC-2 无占位符:        PASS / FAIL [+ findings]
- MC-3 SR-item 必填字段: PASS / FAIL [+ findings]
- MC-4 Depends on 合法:  PASS / FAIL [+ findings]
- MC-5 文档级 Status:    PASS / FAIL [+ findings]

### LLM 红线 (R1..7)
- R1 写死角色名:           PASS / N findings [+ 位置]
- R2 越界贴字段表:         PASS / N findings
- R3 越界写技术实现:       PASS / N findings
- R4 验收要点不可观察:     PASS / N findings
- R5 不适用未论证:         PASS / N findings
- R6 场景孤儿:             PASS / N findings
- R7 OQ 未清空:            PASS / N findings

### 结论
- 整体：APPROVE / REQUEST CHANGES
- 若 REQUEST CHANGES：列出最关键的 3 项必修
```

### 5.4 决策规则

- **MC-1..5 全过 AND R1..7 全过** → APPROVE；spec 可由 Status=Review 升到 Approved
- **任何一项 FAIL** → REQUEST CHANGES；spec 留在 Draft/Review；评审者列出必修项
- **borderline 判定**（某条红线接近边界但有合理解释）：评审者应在报告中明示 borderline，由作者/产品决策方裁定

## 6. Optional Tooling

机械规则 MC-1..5 可由人/LLM 直接执行（§5.1 已提供完整描述）。本节描述可选的 Python 工具 `tools/sr_check.py`，加速批量/CI 场景的机械校验。

### 6.1 工具角色

`tools/sr_check.py` 是 **可选加速器**，不是评审的必经路径：
- 任意 agent / 人 在 §5.1 框架内独立判定 MC-1..5 也算合规
- 工具的存在不改变 §5.1 的规则定义；规则定义的唯一源是 §5.1 文本
- 工具实现选择 Python 是工程便利；其他语言重写一遍同等接口也合规

### 6.2 工具 I/O 约定

```
调用:    python3 tools/sr_check.py <path/to/spec.md>

退出码:  0 = 全部 MC 通过
         1 = 至少 1 条 ERROR finding
         2 = 工具错误（参数错 / 文件不存在）

输出:    每条 finding 一行，格式：
         [SEVERITY] RULE-LABEL[:line]: message

         SEVERITY ∈ {ERROR, WARN}
         RULE-LABEL 是英文标签（见下面映射表）
         line 是 1-based 行号（部分规则提供，部分规则不提供）
```

### 6.3 工具 rule label → MC-N 映射

| 工具 rule label | 对应 MC | 触发条件 |
|---|---|---|
| `A_BLOCKS_PRESENT` | MC-1 | Part A 某块缺失 |
| `NO_PLACEHOLDER` | MC-2 | 文件含 TBD/TODO/FIXME |
| `SR_ITEM_PRESENT` | MC-3 | Part B 一条 SR-item 都没有 |
| `SR_ITEM_FIELD` | MC-3 | 某 SR-item 缺必填字段 |
| `DEPENDS_ON_REF` | MC-4 | Depends on 引用未定义的 SR-ID |
| `FRONTMATTER_STATUS` | MC-5 | 文档级 Status 缺失或非法 |

### 6.4 自动化集成示例

```bash
# 在 CI 中作为 gate
python3 tools/sr_check.py specs/<slug>/spec.md
if [ $? -ne 0 ]; then
    echo "SR 机械校验失败，请修复后再提评审"
    exit 1
fi
```

```bash
# 批量校验所有 specs
for f in specs/*/spec.md; do
    python3 tools/sr_check.py "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```

工具源码与测试位于 `tools/sr_check.py` 和 `tools/test_sr_check.py`（pytest）。

## 7. Worked Example

完整示例见 `specs/devsec-projver/spec.md`（9 条 SR-item，4 个 Group）。

> 注：该示例的 `**Downstream**:` 字段指向 `./testable-requirements.md (TRD)`，是该 SR 自身的下游记录；本契约**不**要求 SR 必须有 TRD 类下游，仅"如有下游则写在 Downstream 字段"。

下面把 `SR-DEVSEC-PROJVER-01` 完整内联，作为单条 SR-item 的实际形态参考：

```markdown
### SR-DEVSEC-PROJVER-01  产品线手动管理

**Priority**: P0
**Status**: Draft
**Depends on**: 无

**用户故事**
作为平台管理员，我想要手动新增、编辑、删除、查看产品线（最多 3 级层级），以便建立后续项目归属与数据范围授权的基础。

**范围**
- 包含：新增/编辑/删除/查看，名称与详情维护，层级关系维护。
- 不包含：批量导入；与 RDM 的同步（见 SR-DEVSEC-PROJVER-02）。

**验收要点**
- 具备产品线相应权限点、且目标位于其授权数据范围的用户，可执行对应操作。
- 产品线层级深度不超过 3 级。
- 同一上级下的产品线名称必须唯一，重复时不允许保存并提示。
- 存在下级产品线或关联项目的产品线不可删除。
```

## 8. Glossary

- **SR (System-level Requirement)**：系统级别需求；本契约定义的中间制品形态。
- **Feature set**：SR 文档对应的能力集合；一份 spec.md 一个 feature set。
- **Part A / Part B**：SR 文档的两层结构。Part A 是 Brief（背景/范围/场景/实体/横向约束/成功标准），Part B 是 SR-Items 列表。
- **SR-item**：Part B 中的单条规范化需求；最小可追溯单元；有不重号 ID。
- **权限点 (permission point)**：形如 `entity:action` 的功能权限单元（如 `productline:delete`）；SR 用其表达授权，不用具体角色名。
- **数据范围 (data scope)**：数据可访问性的业务维度（如"产品线"、"租户"）；与权限点组合判定授权。
- **横向约束 (cross-cutting constraint)**：不属于单条 SR-item 但适用于全部的规则；记录在 Part A.5。
- **Open Question (OQ)**：对实现/测试有影响的未决问题；Status=Review/Approved 时必须清空。
- **Red-line**：在 SR 中明令禁止的写法（R1..7）；由人/LLM 扫查。
- **Mechanical check**：可由 §5.1 MC-1..5 机械判定的规则；可被工具加速。
