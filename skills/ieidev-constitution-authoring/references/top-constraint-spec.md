# 顶层约束生成规范（Top-Level Constraint Generation Spec）

- **版本**：v0.1（首版，基于 KDevSec 项目实践抽象）
- **作者**：Will + AI 协同推导
- **日期**：2026-05-26
- **落盘位置**：`/home/will/AI_Coding_Lab/tmp/top-constraint-spec.md`
- **前置阅读**（强推荐）：`./constraint-architecture.md`（方法论背景）

---

## §0 元说明

### §0.1 本文是什么

本文是一份**面向任意 LLM Agent 的规范文档**，描述如何为一个具体项目生成其"顶层约束文档"（root constraint document，下文简称"根文档"）。根文档常见的物理形态包括 `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.cursorrules` / `Project.md` 等。

### §0.2 谁来读、谁来用

| 角色 | 行为 |
|---|---|
| **执行 Agent** | 从头到尾按本规范执行 Phase 1（探测+设计）→ 用户评审 → Phase 2（生成）→ 内联自检 |
| **项目负责人 / 开发者** | 在 Phase 1 Step 1 指认前置材料；在 Phase 1 评审 checkpoint 审阅设计报告；在 Phase 2 完成后跑加载验证 |

### §0.3 怎么用

1. 把本规范**全文**提供给目标 Agent（任意 LLM 客户端，不限 Claude Code）
2. 同时把项目根目录可访问性提供给 Agent
3. 用一句话触发：例如"请按本规范为项目 X 生成顶层约束文档"
4. Agent 进入 Phase 1 流程，主动与你对话

### §0.4 设计原则（编码约定）

| 原则 | 含义 |
|---|---|
| **Agent 无关** | 规范不依赖任何 Agent 原生语法（如 Claude Code 的 `@./path` 自动展开）。输出文档是纯 markdown，任何 LLM 读完都能照做 |
| **通用/项目专有 严格区分** | 规范中**每一节**都用两个子块——`### 通用规则`（任何项目都一样）和`### 项目专有变量`（本项目要填空的位置） |
| **最小骨架 + 可选挂载** | 根文档的"必备"段落只有 2 段（preamble + 内联硬约束）；其余段落根据前置材料动态挂载 |
| **占位符语法** | 小模板中所有需要替换的位置都用 `<<PLACEHOLDER_NAME>>` 形式标注 |

### §0.5 术语表

| 术语 | 含义 |
|---|---|
| 根文档 | 项目的最高优先级约束文件，AI Agent 在每次会话启动时（或被显式要求时）加载 |
| 子约束 | 被根文档引用的次级文档，按主题分散在 `references/` 或类似目录 |
| 前置材料（prereq） | 用来填充根文档的源文件——例如团队已有的硬约束清单、SOP 文档、风格规范等 |
| C1-C6 | 6 类标准前置材料的代号（§2 详述） |
| 事实子树 | 收容"做什么、为什么、技术语境是什么"类材料的引用集合 |
| 过程子树 | 收容"怎么做、什么时候停下评审"类材料的引用集合（即 SOP） |
| 触发路由表 | 用来告诉 Agent"在什么任务/SOP 节点下必读哪个子约束"的对照表 |
| 冲突裁决链 | 用来告诉 Agent"多个子约束打架时谁胜"的优先级声明 |

---

## §1 输出文档的通用骨架

### §1.1 最小骨架（任何根文档都必备）

```
§preamble · 角色定位 + 顶层优先级
§hard-constraints · 内联硬约束（绝对不能引用，必须 100% 内联）
```

仅当**只有 C1 一类前置材料**时，输出就是这两段。文件可以短到 30-60 行。

### §1.2 可选挂载段落（按前置材料决定是否挂）

| 段落 | 何时挂 | 落在哪 |
|---|---|---|
| §navigation · 首跳指针 | 一旦挂载任何子树就必备 | 紧贴 §hard-constraints 之后 |
| §factual-subtree · 事实子树（业务/技术语境） | C2 或 C4 或 C5 或 C6 任一存在 | §navigation 之后 |
| §process-subtree · 过程子树（SOP/工作流） | C3 存在 | §factual-subtree 之后 |
| §routing-table · 触发路由表 | 一旦挂载任何子树就必备（**位置依 Q9 适配**） | 见 §4.2.3 |
| §conflict-resolution · 冲突裁决链 | 一旦挂载任何子树就必备 | 见 §4.2.4 |

### §1.3 三种典型形态（按 C1-C6 不同组合）

**形态 A · 极简型**（只有 C1）

```
§preamble
§hard-constraints（内联）
```

**形态 B · 单子树型**（有 C1 + C2/C4/C5/C6 至少一类，但没有 C3）

```
§preamble
§hard-constraints
§navigation（路由表在此 · 任务特征式）
§factual-subtree
  ├─ <<leaf-1>>
  ├─ <<leaf-2>>
  └─ ...
§conflict-resolution
```

**形态 C · 双子树型**（C1 + C3 + 其它任意，KDevSec 即此型）

```
§preamble
§hard-constraints
§navigation（首跳指针 · 极简）
§factual-subtree
  ├─ <<leaf-1>>
  └─ ...
§process-subtree
  ├─ §routing-table（SOP 节点式）
  └─ §conflict-resolution
```

---

## §2 前置材料目录（6 类标准 prereq）

### §2.1 通用规则

| 代号 | 类别 | 必备? | 缺失时 |
|---|---|---|---|
| **C1** | 硬约束 / 红线原则 | **必备** | Agent MUST 基于 C2（若有）为用户起草 6-8 条最小红线，**待用户确认后**才能进入下一步 |
| **C2** | 项目背景与目标 | 推荐 | 不挂事实子树的"背景节"；若 C4-C6 也无，则不挂事实子树 |
| **C3** | 流程 / SOP / 工作流 | 可选 | 不挂过程子树；路由表降级为任务特征式放根级 |
| **C4** | 技术参考资料（风格、UED、框架理解等） | 可选 | 不挂相应 leaf |
| **C5** | 历史 / 遗留代码理解 | 可选 | 不挂相应 leaf |
| **C6** | 原型 / 设计参考 | 可选 | 不挂相应 leaf |

### §2.2 项目专有变量

每个项目在 Phase 1 Step 1 时会填出如下清单：

| 变量 | 含义 | 示例（KDevSec） |
|---|---|---|
| `C1_PATH` | C1 材料的文件路径或"无"标记 | `./references/03-constitution-ref/6.12条大原则.md` |
| `C2_PATH` | C2 材料路径或"无" | `./references/00-项目背景和总体目标/项目背景与整体要求.md` |
| `C3_PATH` | C3 材料路径或"无" | `./references/03-constitution-ref/7.SOP-整体流程说明.md` |
| `C4_PATHS` | C4 材料路径列表（可多个） | `[./references/04-ued6.0/AGENTS.md, ./references/03-constitution-ref/5.新框架Ruoyi代码整体逻辑理解.md]` |
| `C5_PATHS` | C5 材料路径列表 | `[./references/03-constitution-ref/2.读旧版本平台的代码获取代码理解.md] + 源码目录 ./references/01-SecurityManager/` |
| `C6_PATHS` | C6 材料路径列表 | `[./references/03-constitution-ref/3.新KDevSec平台原型风格.md] + 资产目录 ./references/02-prototype/` |

---

## §3 Phase 1 · 探测 + 设计（Discovery + Design）

> 目标：让 Agent 把"将要写出什么"完整设计清楚，**写文件之前**先让用户评审。

### §3.1 Step 0 · 现存根约束检测

#### 通用规则
- Agent **MUST** 在询问 C1-C6 之前，先询问/探测项目根目录是否已存在以下任一文件：
  `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.cursorrules` / `Project.md`
- 若存在 → MUST 把现有文件**全文内容**贴出给用户 → 询问三选一：
  - **[Overwrite]** 备份现有 → 然后由 Phase 2 覆盖
  - **[Merge-manually]** 不动现有 → Phase 2 写到新文件 `<原文件名>.new.md`，由用户手工合并
  - **[Abort]** 中止本次流程
- 用户未做出选择前 **MUST NOT** 进入 Step 1

#### 项目专有变量
| 变量 | 来源 | 示例 |
|---|---|---|
| `EXISTING_FILE_PATH` | Step 0 探测 | `CLAUDE.md`（5 行委托式内容） |
| `EXISTING_FILE_CONTENT` | Step 0 读取 | （5 行 SpecKit 委托内容） |
| `USER_CHOICE` | 用户回答 | Overwrite / Merge-manually / Abort |
| `BACKUP_FILE_PATH` | 若 Overwrite，备份目标 | `CLAUDE.md.bak-2026-05-20` |
| `OUTPUT_FILE_PATH` | Phase 2 写入目标 | `CLAUDE.md`（Overwrite）/`CLAUDE.md.new.md`（Merge-manually） |

---

### §3.2 Step 1 · C1-C6 用户清单探测（用户清单优先）

#### 通用规则
- Agent **MUST** 显式向用户列出 6 类前置材料，请用户**逐一指认**对应文件路径（或答"无"）
- 提问示例话术（Agent 应直接使用或近似改写）：

  > 我需要为本项目生成一份顶层约束文档。请你指认以下 6 类前置材料的存在位置（如不存在请直接答"无"）：
  > - **C1** 硬约束 / 红线原则文档（团队的"绝对不能违反"清单）：
  > - **C2** 项目背景与目标文档（项目做什么、为什么、给谁用）：
  > - **C3** 流程 / SOP / 工作流文档（团队怎么干活、什么时候停下评审）：
  > - **C4** 技术参考资料（前端规范、风格、框架理解等；可多个）：
  > - **C5** 历史 / 遗留代码理解文档（如果是重构/迁移项目）：
  > - **C6** 原型 / 设计参考（视觉设计稿、原型代码目录等）：

- 若 C1 用户答"无" → Agent **MUST NOT** 跳过，**MUST** 进入"起草子流程"：
  1. 基于 C2（若有）或基于用户口述的项目背景，**起草 6-8 条最小红线**
  2. 把草稿贴给用户 → 用户**确认 / 修订**
  3. 修订定稿后才能进入 Step 2

- 用户答出的每个路径，Agent **MUST** 当场验证该文件 / 目录确实存在；不存在的视为"无"
- 多文件类（C4-C6）可以是路径列表

#### 项目专有变量
见 §2.2 表（`C1_PATH` … `C6_PATHS`）。

---

### §3.3 Step 2 · 挂载决策

#### 通用规则
按 §1.3 三形态规则**确定性地**裁定输出文档形态：

```
IF C1 是唯一存在的类 (C2-C6 全无)
THEN 形态 = A (极简型)

ELSE IF C3 存在
THEN 形态 = C (双子树型)
     · 必挂事实子树（即使 C2/C4-C6 只有一类）
     · 必挂过程子树

ELSE  (C3 不存在 但 C2/C4/C5/C6 至少一类存在)
THEN 形态 = B (单子树型)
     · 挂事实子树
     · 不挂过程子树
     · 路由表降级为根级任务特征式
```

事实子树内部 leaf 来源映射：

| 来源 | leaf 节标题（推荐） |
|---|---|
| C2 | 主体引用直接放在事实子树入口段（不单独成 leaf） |
| C4 各项 | "技术参考 · <主题>"（按 C4 文件主题命名）|
| C5 | "历史 / 遗留代码理解" |
| C6 | "原型 / 设计参考" |

#### 项目专有变量
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `OUTPUT_SHAPE` | §3.3 规则 | C（双子树型） |
| `MOUNT_FACTUAL_SUBTREE` | §3.3 规则 | true |
| `MOUNT_PROCESS_SUBTREE` | §3.3 规则 | true |
| `FACTUAL_LEAVES` | C4/C5/C6 主题列表 | [UED规范, 新框架Ruoyi, 旧平台代码, 新平台原型] |

---

### §3.4 Step 3 · 派生段落草稿

#### §3.4.1 触发路由表草稿（按 Q9 适配形状）

**通用规则 · 形状裁定**：
```
IF MOUNT_PROCESS_SUBTREE == true   (即 C3 存在)
THEN 形状 = SOP节点式
     · 位置：放在过程子树内部
     · 列：当前 SOP 节点 / 任务性质 / 必读子约束
     · 行来源：Agent 读 C3 材料，提取关键节点（如"需求分析"、"编码-前端"、"测试设计"等），
               并对每个节点判定"该节点活动可能踩到哪些子约束 → 列为必读"
ELSE                                (无 C3，但有事实子树)
THEN 形状 = 任务特征式
     · 位置：放在根级 §navigation
     · 列：任务特征 / 必读文件
     · 行来源：Agent 基于事实子树 leaves 的主题反推任务特征
               （如"修改 UI 颜色" → UED 规范）
```

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `ROUTING_SHAPE` | 上述规则 | SOP节点式 |
| `ROUTING_ROWS` | Agent 推导 | 8 行映射（详见 §6 走查示例） |

#### §3.4.2 冲突裁决链草稿

**通用规则**：
- 冲突裁决链分**两层**——
  - **层级优先级**（meta-priority）：声明"哪种**类型**的规则胜过哪种"
  - **技术契约层内部优先级**（content-priority within factual subtree）：声明"事实子树内部 leaves 之间打架谁胜"
- 层级优先级默认链（任何形态都用）：
  ```
  用户显式指令 > §hard-constraints > §process-subtree（若有） > §factual-subtree（若有） > 模型默认行为
  ```
- 技术契约内部优先级链由 Agent 按以下默认排序（用户可调）：
  1. C4 中标了 `NON-NEGOTIABLE`、`MUST`、`硬约束` 等强字眼的 leaf（视觉/契约级硬约束）
  2. C4 其它 leaf（一般技术契约：命名/目录/导入路径等）
  3. C6 原型 / 设计参考（视觉实现参考）
  4. C5 遗留代码（**仅业务逻辑参考**，不允许复用代码）
- Agent **MUST** 在生成的冲突裁决链上方加一段"正交说明"：
  > 本节优先级链针对**技术契约层**的内容冲突。它与顶部"层级优先级"正交——顶部区分的是规则的抽象层级，本节区分的是技术语境层内部 leaves 谁胜。

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `META_PRIORITY_CHAIN` | 默认链填值 | 用户显式指令 > §1 12 原则 > §3 SOP 流程子树 > §2 技术语境子树 > 模型默认 |
| `CONTENT_PRIORITY_CHAIN` | Agent 推导 | §1 > §2.4 UED > §2.3 Ruoyi > §2.2 Prototype > §2.1 Old code |

---

### §3.5 Step 4 · 设计报告与评审 checkpoint

#### 通用规则
- Agent **MUST** 在 Phase 1 末尾产出一份**设计报告**给用户评审
- 设计报告**必备 5 个主字段** + **风险作为开放问题的子项**
- 评审未通过前 **MUST NOT** 进入 Phase 2
- 用户的修订意见 Agent **MUST** 复述确认 → 应用 → 再次提交

#### Phase 1 设计报告标准模板
```markdown
# 顶层约束生成 · Phase 1 设计报告

## 1. 前置材料探测结果
| 类别 | 用户指认路径 / 状态 | 备注 |
|---|---|---|
| C1 硬约束 | <<C1_PATH>> / 无（agent 已起草） | <<C1_NOTE>> |
| C2 项目背景 | <<C2_PATH>> / 无 | — |
| C3 流程/SOP | <<C3_PATH>> / 无 | 决定路由形状 |
| C4 技术参考 | <<C4_PATHS>> | leaf 数量：<<C4_LEAF_COUNT>> |
| C5 遗留代码 | <<C5_PATHS>> / 无 | — |
| C6 原型 | <<C6_PATHS>> / 无 | — |

## 2. 输出文档结构决策
- 输出文档形态：<<OUTPUT_SHAPE>>（A 极简 / B 单子树 / C 双子树）
- 是否挂载「事实子树」：<<MOUNT_FACTUAL_SUBTREE>>
- 是否挂载「过程子树」：<<MOUNT_PROCESS_SUBTREE>>
- 路由表形状：<<ROUTING_SHAPE>>
- 输出文档章节预览：
  <<OUTPUT_TOC_PREVIEW>>

## 3. 派生段落草稿
### 3.1 触发路由表（草稿）
<<ROUTING_TABLE_DRAFT>>

### 3.2 冲突裁决链（草稿）
**层级优先级**：<<META_PRIORITY_CHAIN>>

**技术契约层内部优先级**（仅当事实子树存在时）：
<<CONTENT_PRIORITY_CHAIN_NUMBERED>>

## 4. 输出文件去向
- 目标路径：<<OUTPUT_FILE_PATH>>
- 现存文件处理：<<USER_CHOICE>>
- 备份路径（如有）：<<BACKUP_FILE_PATH>>

## 5. 需要用户决断的开放问题
- [ ] <<OPEN_QUESTION_1>>
- [ ] <<OPEN_QUESTION_2>>
- [ ] **风险与缓解**（子项）：
  - 风险 1：<<RISK_1>> · 缓解：<<MITIGATION_1>>
  - 风险 2：<<RISK_2>> · 缓解：<<MITIGATION_2>>

---

**评审请回复：**
- [ ] 通过，可以进入 Phase 2 生成
- [ ] 不通过，请按以下意见修订：<<REVIEW_FEEDBACK>>
```

#### 项目专有变量
（即上方模板中所有 `<<...>>` 占位符 —— 在 Phase 1 各 step 中已经填出，此 step 仅汇总）

---

## §4 Phase 2 · 生成（Generation）

> 前提：Phase 1 设计报告已经被用户评审通过。

### §4.1 装配顺序

Agent 按下列顺序拼装输出文档（缺席的可选段落直接跳过）：

```
1. §preamble （必备）
2. §hard-constraints （必备）
3. §navigation （若挂载任何子树则必备）
4. §factual-subtree （若 MOUNT_FACTUAL_SUBTREE）
5. §process-subtree （若 MOUNT_PROCESS_SUBTREE），其内部按顺序：
   5.1 §process-subtree-anchor （主引用 C3 文件）
   5.2 §routing-table （若 ROUTING_SHAPE == SOP节点式）
   5.3 §conflict-resolution
6. §routing-table （若 ROUTING_SHAPE == 任务特征式，放在 §navigation 内部表格里，不另成节）
7. §conflict-resolution （若形态 B —— 即 C3 不存在但事实子树存在，且未在 §process-subtree 内已写）
```

### §4.2 各节小模板（每节双子块）

> 下述每个小节都遵循 Q6=C 编码：先讲通用规则，再给小模板，最后列项目专有变量。

#### §4.2.1 §preamble 小模板

**通用规则**：
- MUST 在文档最顶部
- MUST 含项目名、本文件角色一句话定位、引用语法约定、顶层优先级（即元 §3.4.2 的 `META_PRIORITY_CHAIN`）
- MUST NOT 引入任何项目专有的实质约束（实质约束放 §hard-constraints）

**小模板**：
````markdown
# <<OUTPUT_FILENAME>> · <<PROJECT_NAME>> 顶层约束

> 本文件是项目最高执行准则。所有 AI Agent MUST 在动手前完整加载本文件。
> 引用语法：本文件中所有 `./<相对路径>` 形式的引用，Agent MUST 在相关任务到来时**主动打开并读完**该路径文件。
> 修订原则：硬约束属内联区，绝对不能动；其余段落按主题引用，变更子约束不必动本文件。

## 优先级（顶层）

<<META_PRIORITY_CHAIN>>
````

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `OUTPUT_FILENAME` | Step 0 | `CLAUDE.md` |
| `PROJECT_NAME` | 用户口述或 C2 | KDevSec |
| `META_PRIORITY_CHAIN` | §3.4.2 | 用户显式指令 > §1 ... > 模型默认行为 |

---

#### §4.2.2 §hard-constraints 小模板

**通用规则**：
- MUST 紧贴 §preamble 之后
- MUST **100% 内联**（绝对不允许 `./xxx` 或任何外部引用）
- 若 C1 来自外部文件且原文有草稿标记（`(?)`、`(待补)`、`(TBD)`、`（？...）` 等中英方括号注释）→ MUST 清理这些标记
- 若 C1 是 Agent 在 Phase 1 起草的 → 直接使用定稿后的版本，不可再加额外免责声明

**小模板**：
````markdown
## §1 <<HARD_CONSTRAINT_SECTION_TITLE>>

<<HARD_CONSTRAINT_PREAMBLE_IF_ANY>>

<<HARD_CONSTRAINTS_FULL_TEXT>>
````

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `HARD_CONSTRAINT_SECTION_TITLE` | C1 文件标题 / Agent 起草标题 | "12 条大原则" |
| `HARD_CONSTRAINT_PREAMBLE_IF_ANY` | C1 文件首段（如有） | "除非显式覆盖，否则本规则适用于本项目中的所有任务..." |
| `HARD_CONSTRAINTS_FULL_TEXT` | C1 文件主体（已清理草稿标记） | 12 条规则全文 |

---

#### §4.2.3 §navigation + §routing-table 小模板

**通用规则**：
- §navigation 段提供"首跳指针"——告诉 Agent **第一步该读哪个主题子文档**
- §routing-table 的具体位置依 ROUTING_SHAPE 而定（见 §4.1 装配顺序）
- 路由表至少 3 行，至多 12 行；超过 12 行建议拆分子约束粒度

**小模板 · ROUTING_SHAPE = SOP节点式**（路由表下沉到过程子树内）：
````markdown
## § 导航 · 首跳指针

任务进来后，根据特征选择子树展开：

| 任务特征 | 第一跳必读 |
|---|---|
| 写代码 / 评审 / SOP 节点推进 / 评分 / 归档 | `<<C3_PATH>>`（含路由表与冲突裁决） |
| 业务理解 / 技术语境 | `<<C2_PATH>>`（其下挂多个技术语境分支） |

> 注意：SOP 子约束内含**节点级路由表**和**冲突裁决规则**。遇到具体 SOP 节点时，必须先到 SOP 子约束里查该节点应展开的下游约束。

[... §factual-subtree 写在这里 ...]

## §3 AI Coding SOP 流程
`<<C3_PATH>>`
（<<C3_BRIEF>>。MUST 全文加载。）

### §3.1 触发路由表（按 SOP 节点 → 必读子约束）

| 当前 SOP 节点 | 任务性质 | 必读子约束 |
|---|---|---|
<<ROUTING_ROWS>>
````

**小模板 · ROUTING_SHAPE = 任务特征式**（路由表在根级 §navigation）：
````markdown
## § 触发路由（任务特征 → 必读文件）

| 任务特征 | 必读文件 |
|---|---|
<<ROUTING_ROWS>>
````

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `ROUTING_SHAPE` | §3.4.1 | SOP节点式 |
| `ROUTING_ROWS` | Agent 推导 | 8 行映射 |
| `C2_PATH` / `C3_PATH` | Step 1 | 见 §2.2 示例 |
| `C3_BRIEF` | Agent 总结 C3 文件 | "公司级 SOP，含 3 阶段流程、评审门、SKILL 映射、横切原则" |

---

#### §4.2.4 §conflict-resolution 小模板

**通用规则**：
- MUST 含"正交说明"段（如 §3.4.2 通用规则所述）
- MUST 含两层：层级优先级 + 技术契约层内部优先级（若事实子树存在）
- 可选含两张细化表：SOP 流程级冲突 / 技术契约级具体冲突

**小模板**：
````markdown
### §<<X>>.<<Y>> 冲突裁决规则

> 说明：本节优先级链针对**技术契约层**的内容冲突。它与本文件顶部的"层级优先级"正交——顶部区分的是规则的抽象层级（硬约束 / 流程规则 / 事实性语境），本节区分的是同属技术语境层的几份子约束在内容冲突时谁胜。

**全局优先级链（高 → 低）**：

<<CONTENT_PRIORITY_CHAIN_NUMBERED>>

**SOP 流程级冲突**（若过程子树存在）：

| 冲突场景 | 裁决 |
|---|---|
<<SOP_LEVEL_CONFLICT_ROWS>>

**技术契约级冲突**：

| 冲突场景 | 裁决 |
|---|---|
<<TECH_CONTRACT_CONFLICT_ROWS>>
````

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `CONTENT_PRIORITY_CHAIN_NUMBERED` | §3.4.2 | 5 行编号列表 |
| `SOP_LEVEL_CONFLICT_ROWS` | Agent 推导（默认 3 行：Spec↔Plan / 评审不通过 / 测试失败↔实现） | 见 §6 走查示例 |
| `TECH_CONTRACT_CONFLICT_ROWS` | Agent 推导 | 4 行 |

---

#### §4.2.5 §factual-subtree 小模板

**通用规则**：
- §factual-subtree 的入口段引用 C2 文件（项目背景）
- 下属每个 leaf 对应 C4 / C5 / C6 的一份材料
- 每个 leaf 节 MUST 含 4 项：主引用 / 源码或资产深挖 / 读取时机 / 优先级注释

**小模板**：
````markdown
## §<<X>> 项目背景与总体目标

`<<C2_PATH>>`
（<<C2_BRIEF>>。MUST 在任何业务相关任务前读全文。）

<<FOR EACH leaf in FACTUAL_LEAVES>>

### §<<X>>.<<I>> 子约束 · <<LEAF_TITLE>>
- 主：`<<LEAF_MAIN_PATH>>`
- 源码/资产深挖：`<<LEAF_DEEP_PATH>>`（如有）
- 读取时机：<<LEAF_READ_WHEN>>
- 优先级注释：<<LEAF_PRIORITY_NOTE>>

<<END FOR>>
````

**项目专有变量**：
| 变量 | 来源 | 示例（KDevSec §2.4 UED leaf） |
|---|---|---|
| `LEAF_TITLE` | C4/5/6 主题 | "新前端 UED 规范（NON-NEGOTIABLE）" |
| `LEAF_MAIN_PATH` | C4_PATHS / C5_PATHS / C6_PATHS 元素 | `./references/04-ued6.0/AGENTS.md` |
| `LEAF_DEEP_PATH` | 源码或资产目录 | `design-tokens.json / tailwind.preset.js / ued-v6.css` |
| `LEAF_READ_WHEN` | Agent 推导 | "任何前端代码、原型、Tailwind 配置修改之前" |
| `LEAF_PRIORITY_NOTE` | Agent 推导 | "该子约束已自带'硬约束'语义，禁止裸 hex/裸 px/未授权字体等" |

---

#### §4.2.6 §process-subtree 小模板

**通用规则**：
- §process-subtree 入口段引用 C3 文件
- 内部依次安排 §routing-table（SOP 节点式） + §conflict-resolution
- 不再下挂 leaf——C3 自身已是完整的 SOP 文档，不应被进一步拆解

**小模板**：见 §4.2.3 的 ROUTING_SHAPE=SOP节点式 模板（已含 §3 入口段）+ §4.2.4 冲突裁决模板。

**项目专有变量**：上述两个模板的占位符并集。

---

### §4.3 写文件

#### 通用规则
- Agent 把装配好的内容写入 `<<OUTPUT_FILE_PATH>>`
- 若 `USER_CHOICE == Overwrite` → 先把现有文件复制为 `<<BACKUP_FILE_PATH>>` 再覆盖
- 若 `USER_CHOICE == Merge-manually` → 直接写新文件 `<<OUTPUT_FILE_PATH>>`（即 `<原文件名>.new.md`）
- 写完 MUST 读回文件首 10 行确认头部结构正确（preamble 标题在）

#### 项目专有变量
| 变量 | 来源 | 示例（KDevSec） |
|---|---|---|
| `OUTPUT_FILE_PATH` | §3.1 | `CLAUDE.md` |
| `BACKUP_FILE_PATH` | §3.1（若 Overwrite） | `CLAUDE.md.bak-2026-05-20` |

---

### §4.4 内联自检清单（Phase 2 末尾，必跑）

Agent 写完输出文档后 **MUST** 逐项自检；任一项 NO → 必须修正，不得宣称完成。

```markdown
- [ ] 必备 §preamble 段在且含顶层优先级链
- [ ] 必备 §hard-constraints 段在且 100% 内联（无任何 ./ 或外部引用，无任何指针式委托如"详见 xxx"）
- [ ] 若挂载了任何子树 → §navigation 段在；否则不应有 §navigation
- [ ] 若挂载了任何子树 → §conflict-resolution 段在；否则不应有
- [ ] 文档内所有 `<<PLACEHOLDER>>` 已被本项目实际内容替换（grep 检索 `<<` 应零结果）
- [ ] 引用条目（如有）都指向用户在 Phase 1 Step 1 指认过的真实路径
- [ ] 若 C1 来自外部文件且原文有草稿标记 → 已清理
- [ ] 文档末尾**无**多余空段或注释残留
```

---

## §5 推荐加载验证（Phase 2 完成后，建议用户做）

> 这一节不是 Agent 自动执行的，是 spec 写给项目负责人的"建议动作"。Agent 在 Phase 2 完成后应向用户主动建议这 3 步。

落地后，请用户在**新会话**中执行以下 3 步加载验证：

1. **首跳测试**：给 Agent 一个**虚拟任务**（最好选与某个 leaf 主题相关的，例如"修改一个前端表单的标签颜色"），观察 Agent 是否能按 §navigation 路由 → §routing-table → 对应 leaf 正确展开链路
2. **冲突裁决测试**：构造一个**伪冲突**（例如"旧平台用 GET 而新原型用 POST，我该用哪个？"），观察 Agent 是否引用了 §conflict-resolution 里的"新平台原型胜（旧码仅业务参考）"类规则
3. **子约束可见性测试**：直接问 Agent "你能列出本项目所有子约束吗，并按 SOP 节点（或任务特征）分组？"，应能完整复述 §routing-table

任一失败 → 回到 spec Phase 1 修订路由 / 优先级链，再走 Phase 2。

---

## §6 走查示例 · KDevSec 项目

> 本节以 KDevSec 项目为完整例子，演示 spec 从 Phase 1 走到 Phase 2 的每一步如何具象化。

### §6.1 Phase 1 Step 0 · 现存根约束检测

- `EXISTING_FILE_PATH` = `sop_test0518/CLAUDE.md`（5 行 SpecKit 委托内容）
- `USER_CHOICE` = Overwrite
- `BACKUP_FILE_PATH` = （用户选择不备份，按 git 历史回滚）
- `OUTPUT_FILE_PATH` = `sop_test0518/CLAUDE.md`

### §6.2 Phase 1 Step 1 · C1-C6 探测结果

| 类别 | 路径 |
|---|---|
| C1 | `./references/03-constitution-ref/6.12条大原则.md` |
| C2 | `./references/00-项目背景和总体目标/项目背景与整体要求.md` |
| C3 | `./references/03-constitution-ref/7.SOP-整体流程说明.md` |
| C4 | `[./references/04-ued6.0/AGENTS.md, ./references/03-constitution-ref/5.新框架Ruoyi代码整体逻辑理解.md]` |
| C5 | `[./references/03-constitution-ref/2.读旧版本平台的代码获取代码理解.md]` + 源码 `./references/01-SecurityManager/` |
| C6 | `[./references/03-constitution-ref/3.新KDevSec平台原型风格.md]` + 资产 `./references/02-prototype/` |

### §6.3 Phase 1 Step 2 · 挂载决策

- `OUTPUT_SHAPE` = C（双子树型）—— 因 C3 存在
- `MOUNT_FACTUAL_SUBTREE` = true
- `MOUNT_PROCESS_SUBTREE` = true
- `ROUTING_SHAPE` = SOP 节点式（路由下沉过程子树）
- `FACTUAL_LEAVES` = [UED 规范（C4，标 NON-NEGOTIABLE）、新框架 Ruoyi（C4）、原型风格（C6）、旧平台代码（C5）]

### §6.4 Phase 1 Step 3 · 派生段落草稿

**路由表草稿**（8 行）：

| 当前 SOP 节点 | 任务性质 | 必读子约束 |
|---|---|---|
| §2.1 子阶段 1A · 初步需求分析 | brainstorming、SR 起草 | §2 项目背景全文；§2.1 旧平台业务逻辑 |
| §2.3 子阶段 1B · 用户故事 + 原型 | AR、原型 | §2.2 新平台原型风格；§2.4 UED 规范 |
| §2.5 子阶段 1C · 实现方案设计 | spec-kit plan | §2.3 新框架 Ruoyi 理解 |
| §3.2 子阶段 2B · 编码（前端） | 写/改前端 | §2.4 UED 规范（硬）；§2.3 Ruoyi |
| §3.2 子阶段 2B · 编码（后端） | 写/改后端 | §2.3 Ruoyi |
| §3.2 数据迁移子任务 | 字段映射、表结构 | §2.1 旧平台代码（数据契约） |
| §4.1 子阶段 3A · 测试设计 | 写 UI/API 测试 | §2.4 UED（UI 行为契约） |
| 任何评审门 ①②③ | 评审/打分 | SOP §1.1 + §1.6 |

**冲突裁决链草稿**：
- 层级优先级：用户显式指令 > §1 12 原则 > §3 SOP > §2 技术语境 > 模型默认
- 技术契约内部：§1 > §2.4 UED > §2.3 Ruoyi > §2.2 Prototype > §2.1 Old code

### §6.5 Phase 2 实际生成（节选）

最终 KDevSec `CLAUDE.md` 共 166 行，章节为：
```
§preamble + 顶层优先级
§1 12 大原则（内联）
§ 导航 · 首跳指针（含 2 行映射 + 1 句"注意"）
§2 项目背景与总体目标
  ├─ §2.1 旧平台代码理解
  ├─ §2.2 新平台原型风格
  ├─ §2.3 新框架 Ruoyi 整体理解
  └─ §2.4 新前端 UED 规范（NON-NEGOTIABLE）
§3 AI Coding SOP 流程
  ├─ §3.1 触发路由表（8 行 SOP 节点）
  └─ §3.2 冲突裁决规则（3 层：层级 / SOP 流程 / 技术契约）
```

完整产物：`sop_test0518/CLAUDE.md`（实际文件）；完整 spec：`sop_test0518/docs/superpowers/specs/2026-05-20-claude-md-top-level-constraint-design.md`。

### §6.6 Phase 2 自检结果（截选）

- ✅ `<<PLACEHOLDER>>` 残留：0（grep 检索 `<<` 零结果）
- ✅ 23 个章节标题顺序符合形态 C 装配规则
- ✅ §1 内联，无任何 ./ 或委托式指针
- ✅ 8 处 ./references/ 引用全部解析到真实文件
- ✅ 草稿标记（C1 原文的 `(?)`、`(？...)` 等）已清理

---

## 附录 A · ADR-0001：Agent 无关型 spec 设计

### 标题
为顶层约束生成规范采用"Agent 无关型纯文档" 设计，放弃 Agent 原生语法

### 状态
Accepted（2026-05-26）

### 上下文
顶层约束生成 spec 有两种设计选择：
- **方案 1**：贴合 Claude Code 原生语法（如 `@./path` 引用自动展开），输出文档充分利用该 Agent 特性
- **方案 2**：完全脱离任何 Agent 的原生语法，输出文档是"纯人类语言 markdown"，任何 LLM 读完都能照做

### 决策
采用方案 2（Agent 无关型）。

### 理由
- spec 的服务目标是"任何项目 + 任何 Agent"。方案 1 把目标受众缩小到 Claude Code 一家，违背规范的最大化普适性目标
- 团队/项目使用的 Agent 不止 Claude Code（同时存在 Cursor / Copilot / Gemini / Codex 等），统一规范能让所有 Agent 受益于相同的结构纪律
- 方案 1 的"自动加载子约束"优点很诱人，但实测中（参考 KDevSec 走查 §6.6）即使没有 `@./path` 自动展开，只要根文档的"导航 + 路由"段写清楚，任何能阅读 markdown 的 LLM 都能正确按指引展开
- 真正的兜底是 §5 推荐加载验证（用户在新会话里跑 3 步测试），它对所有 Agent 一致

### 后果
**正面**：
- spec 一份适配所有 LLM 类 Agent；无需为不同 Agent 维护变体
- 规范本身可作为"方法论文档"独立流通，不绑定特定工具

**负面**：
- 输出文档放弃了 Claude Code 等 Agent 的"自动加载"原生优化（理论上首跳触发率略低）
- 用户需要在 §5 加载验证里发现"某些 Agent 没主动读子约束"的实际情况后，**手工**在该项目的根文档头部追加 Agent-specific 提示语（如"Claude Code 用户：本文件中所有 `./xxx` 路径请用 `@./xxx` 重新粘贴"）。这条留作未来潜在的"adapter 层"伏笔

### 何时考虑反转
若某天发现 90%+ 用户都在用同一种 Agent（如 Claude Code 一家独大），且"无自动加载"已成为实际首跳率的主要瓶颈 → 此时再加 adapter 层（spec 主体不变，新增小附录"各 Agent 适配片段"），而不是推翻 ADR-0001。

---

## 附录 B · 自检清单（spec 自身的元自检，给 spec 维护者用）

每次修订本规范后，维护者 MUST 跑一遍：

- [ ] §1.3 三种形态的章节装配规则与 §4.1 装配顺序一致
- [ ] §2.1 表里 C1-C6 的"缺失时"列与 §3.2 Step 1 中 C1 缺失的起草子流程一致
- [ ] §3.4.1 路由表形状裁定规则与 §4.2.3 的两份小模板互斥地覆盖所有 ROUTING_SHAPE 值
- [ ] §3.4.2 默认两层优先级链与 §4.2.4 占位符一一映射
- [ ] §4.4 自检清单覆盖了所有"易出错"段落（preamble / 内联硬约束 / 占位符 / 引用解析 / 草稿标记）
- [ ] §6 KDevSec 走查的每一个步骤都能找到对应的 §3/§4 规则条目

---

**END OF SPEC v0.1**
