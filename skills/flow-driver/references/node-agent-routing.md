# Node→Agent 路由表

每个 action 节点需要派哪个业务 agent（subagent_type），以及派单时需要传什么上下文。

本表适用于 `dev-engineer`（开发工程师）员工的 coding-flow。未来其他员工（如 req-architect）会有自己的路由表。

## 🔴 派单标识：一律用插件全名 `ieidev-team:<agent-id>`

CC 的 agent 注册表（主控 `Agent` 工具 / workflow `agent()` 同源）**只认带插件命名空间的全名**，裸 canonical id 会 not-found：

```
Agent({subagent_type: "dev-engineer-env"})            ❌ not found
Agent({subagent_type: "ieidev-team:dev-engineer-env"})  ✅
```

因此：**本路由表 `subagent_type` 列、SKILL/orchestrator 里所有派单示例，统一写成 `ieidev-team:<agent-id>`**。
（注意：agent `.md` frontmatter 的 `name:`、`staff.yml` 的 `agents:` 花名册仍是裸 canonical id —— 那是文件名/身份标识，插件系统负责在派单时加前缀；只有「派单调用值」需要写全名。）

## 🔵 派单方式：后台 + 文件交接（B 轨）

业务派单一律 `run_in_background: true`，agent 收尾把状态写到
`.ieidev/features/<slug>/handoffs/<员工>/<node_id>.handoff.json`（`ieidev_core handoff-write`），
主控靠 completion 通知 + `handoff-read` 拿结果，**不读 subagent 内联返回**。
协议 schema + 派单步骤见 `SKILL.md` §2.4 / §2.4bis / §4。
（本表的产物落位规则——dev-engineer 落 `delivery/`、req-architect 落 `handoffs/`——不变；交接**状态文件**统一落 `handoffs/<员工>/`，内部用 `artifacts` 指向真实产物路径。）

## 路由映射

| 节点 id | 节点名称 | subagent_type | agent 中文名 | 干什么 | 需传的上下文 |
|---|---|---|---|---|---|
| n0-env | 项目背景对齐 | `ieidev-team:dev-engineer-env` | 开发工程师·环境准备 | clone 仓库、栈版本对齐、蒸馏 UED materials → rules.md；**先读同 slug 上游交付**：`ieidev_core handoff-read coding-flow <slug> --employee req-architect --node n8-merge`，存在则取 SR+背景作项目背景对齐输入，缺失则裸任务（SKILL §2.4ter） | repo_url, materials_path（含 AGENTS.md / design-tokens.json / ued-v6.css）, workspace 路径, **上游 req-architect 交付 handoff（若同 slug 存在）** |
| n2-worktree | 新建 worktree | `ieidev-team:dev-engineer-env` | 开发工程师·环境准备 | 在 worktree 里做（关联度低时走此分支） | repo_url, workspace 路径, 分支名 |
| n3-plan | 写 implementation-plan | `ieidev-team:dev-engineer-plan` | 开发工程师·实施计划 | 写 PLAN.md：任务拆解、TDD 序列、验收标准；**上游存在时**以 `handoff-read --employee req-architect --node n8-merge` 的 AR(迭代+用户故事)/方案切增量清单与 PLAN 起点，缺失则裸任务自定增量（SKILL §2.4ter） | 任务描述, gate_a_verdict（high/low）, 考题或 spec 文件路径, workspace 路径, **上游 req-architect AR/方案 handoff（若同 slug 存在）** |
| n6a-impl-inline | 主控直接实现 | **不派 agent** | — | 主控自己写代码（simple 任务时走此分支） | 任务描述, PLAN.md 路径, workspace 路径 |
| n6b-impl-subagent | subagent 派单实现(含TDD) | `ieidev-team:dev-engineer-frontend` | 开发工程师·前端实现 | 改 src：视觉改造（token 对齐 + 页面逐页走查）。**当前增量内部的实现工序（T0→T4 这种分层）在这一个节点里做完，可多次派 frontend 分批建，中间不跑 gate 链** | 任务描述, PLAN.md 路径, rules.md 路径, prototype 图路径, **当前是第几个增量（纵向切片）**, workspace 路径, src 项目路径 |
| n11-merge | 合并主分支 | `ieidev-team:dev-engineer-deploy` | 开发工程师·部署上线 | 合并分支 + 起测试环境 + release notes（**收尾链，整任务只跑一次，真合并不空过**） | 分支名, workspace 路径, 项目路径 |

## Gate 节点不派 agent

Gate 节点由编排器（你）自行判断，不派业务 agent。具体判据见 `gate-decision-logic.md`。

但以下 gate 节点涉及验证/验收工作，需要先派 agent 做检查再判断：

| Gate 节点 | 检查方式 | 说明 |
|---|---|---|---|
| n8-verify (g-verify) | ieidev-team:dev-engineer-frontend 自检 | frontend agent 完成后自跑 build+lint+UED grep，编排器读结果判 PASS/FAIL |
| n9b-e2e (g-e2e) | `ieidev-team:dev-engineer-e2e` 派单 | 派 e2e agent 做视觉 diff + 功能冒烟，等结果后判 PASS/FAIL |
| n12-deploy (g-deploy) | `ieidev-team:dev-engineer-deploy` + e2e 检查 | deploy agent 起环境后，e2e agent 做金丝雀冒烟 |

注意：这些 gate 的"检查"部分确实需要派 agent，但"判断"部分由编排器做。流程是：先派 agent 收证据 → 读证据 → 编排器判 verdict → record-gate。

## 逐增量循环 vs 收尾链（once）

```
逐增量循环（每个纵向切片跑一遍）：
  n6b 实现 → n8-verify → n9a-code-review → n9b-e2e → n9c-increment(more/done)
   ▲                                                      │ more（还有切片）
   └──────────────────────────────────────────────────────┘
                                              │ done（切片全过 e2e）
收尾链（整任务只跑一次）：                      ▼
  n10-sec → n11-merge → n12-deploy → n13-done
```

- **逐增量**：实现 + verify + 代码评审 + e2e，每个增量一遍。more 回 n6b 做下一切片。
- **收尾一次**：安全扫全量 diff、单次真合并、单次部署金丝雀。**只在 g-increment done 后跑。**
- 单增量任务（N=1，如纯视觉改造）：循环只跑一遍，直接 done 进收尾。

## ⚠️ 产物落在任务 workspace 的 delivery/，不是框架仓（G-006 根因）

派 e2e / deploy / frontend agent 时，**必须在上下文里写死"产物根 = `<任务workspace>/delivery/`"**，所有截图、报告、patch 都落这里。

**坑**：数字员工跑外部任务时 cwd 可能串到框架仓，agent 会无脑套用全局"截图放 `<项目>/screenshots/`"规则，把考试截图丢进框架仓 `kdev-agents/screenshots/`——违反考题交付目录要求。**显式注入 delivery/ 绝对路径 + 声明"本次是外部任务、产物一律落 delivery/、不套用全局 screenshots 规则"**，盖过全局默认。

## n6a vs n6b 的选择

- g-complexity 判 `simple` → n6a（主控直接实现，不派 subagent）
- g-complexity 判 `complex` → n6b（派 `ieidev-team:dev-engineer-frontend` subagent）

绝大多数视觉改造任务判 `complex`，走 n6b。

## 单上下文构造要点

派 agent 时 prompt 要包含以下要素（按 agent 需求选取）：

1. **身份声明**："你是 XX·YY（dev-engineer-ZZ），当前在 coding-flow 的 nX 节点"
2. **任务描述**：`--task` 参数的内容，或从文件读取的考题/需求描述
3. **节点目标**：从 node-table 和 agent 人设文档提取的职责描述
4. **前序产物**：env.md / rules.md / PLAN.md 的路径（已经产出的话）
5. **约束材料**：AGENTS.md / design-tokens.json / 原型图 的路径
6. **工作目录**：workspace + 项目路径
7. **当前范围**：特别是 frontend agent，明确"这一轮做哪个 increment"

详见 SKILL.md §4 上下文构造模板。

---

# req-architect（需求架构师）design-flow 路由

适用于 `req-architect` 员工的 design-flow（node-table=`orchestration/req-architect.node-table.yml`）。

## 路由映射

| 节点 id | 节点名称 | subagent_type | agent 中文名 | 干什么 | 需传的上下文 |
|---|---|---|---|---|---|
| n0-clarify | 需求澄清 IR | `ieidev-team:req-architect-clarify` | 需求架构师·需求澄清 | 澄清原始需求 → ir.md | 原始需求文本/路径, **产物根=`<workspace>/.ieidev/features/<slug>/handoffs/req-architect/`** |
| n1-spec | 需求计划 SR | `ieidev-team:req-architect-spec` | 需求架构师·需求计划 | 写 SR（调 `ieidev-team:sr-authoring`）→ sr.md | ir.md 路径, 产物根 |
| n3-decompose | 需求拆解 AR | `ieidev-team:req-architect-decompose` | 需求架构师·需求拆解 | 迭代拆分 + 用户故事（调 `ieidev-team:ar-authoring`）；用户故事回编排 `add-story` 填 stories[] | sr.md 路径, 产物根 |
| n4-prototype | 高保真原型 | `ieidev-team:req-architect-prototype` | 需求架构师·原型设计 | 高保真原型（先抽宪法 UI 约束[`ieidev-team:constitution-authoring` 口径]再调 `ieidev-team:frontend-design`）→ prototype/ | AR 路径, 项目宪法根文档, 产物根 |
| n6-design | 方案设计 | `ieidev-team:req-architect-design` | 需求架构师·方案设计 | 概要+详细方案（调 `ieidev-team:detailed-design-authoring`）→ design.md | AR+prototype 路径, 产物根 |
| n8-merge | 产物聚合+合并交付 | **编排自做（不派）** | 需求架构师·编排 | 阶段聚合报告 + 合并交付（参 design-flow output-merge-rules.md）→ docs/design-flow/<slug>/；**收尾落跨员工交付 handoff**：`ieidev_core handoff-write design-flow <slug> --employee req-architect --node n8-merge --status done --summary ... --artifact sr/ar/prototype/design --gate-input '{"sr":..,"ar":..,"prototype":..,"design":..}'`（供下游 coding-flow 同 slug 读，见 SKILL §2.4ter）| 各阶段终版路径 |

## Gate 节点（n2-sr-review / n5-ar-proto-review / n7-design-review）

由编排器（你）按 design-flow 判据自判，不派业务 agent。判据见 `gate-decision-logic.md` 的 req-architect 段。

## ⚠️ 产物落 handoffs/req-architect/（同 dev-engineer 的 delivery/ 教训，G-006）

派 req-architect 业务 agent 时，**必须在上下文写死「产物根 = `<workspace>/.ieidev/features/<slug>/handoffs/req-architect/`」**，所有 ir/sr/ar/prototype/design 都落这里，不套用全局 `screenshots/` 规则。最终合并交付落 `docs/design-flow/<slug>/`。

---

# test-engineer（测试工程师）test-flow 路由

适用于 `test-engineer` 员工的双 flow（`node_tables`：test-design-flow / test-exec-flow）。

> 🔴 **黑盒独立硬规**：测试设计（n0-points/n1-cases）只读「需求文档 + 原型图 + 用户故事」，**禁读业务源码 `src/`、禁读 dev-engineer handoff/flow**。读代码设计测试 = 代码自测。dev-engineer ⊥ test-engineer 并行独立、流程不延续。UI 自动化脚本期读运行时 DOM 拿选择器(黑盒)允许，不读源码逻辑。

## 路由映射（test-design-flow，无 env）
| 节点 id | subagent_type | 干什么 | 需传上下文 |
|---|---|---|---|
| n0-points | `ieidev-team:test-engineer-points` | 读需求/原型(禁读src)设计测试点 → test-points.md；**先** `handoff-read test-design-flow <slug> --employee req-architect --node n8-merge` 取 SR/用户故事/原型，缺失则裸任务 | 需求文档/原型路径, 产物根=`<ws>/.ieidev/features/<slug>/handoffs/test-engineer/`, 上游 req-architect 交付(若同 slug) |
| n1-cases | `ieidev-team:test-engineer-cases` | 1:1 渲染 → test-cases.md | test-points.md 路径, 产物根 |
| n3-merge | 编排自做（不派）| handoff-write 设计交付(test-points/test-cases) | — |

## 路由映射（test-exec-flow，env-gated）
| 节点 id | subagent_type | 干什么 | 需传上下文 |
|---|---|---|---|
| n0-ui-auto | `ieidev-team:test-engineer-ui` | 读 test-cases + 被测环境 URL → Playwright+pytest → ui-results | test-cases.md(handoff-read n3-merge), **被测环境 URL(运行时输入)**, recon/menu_list.md, 产物根 |
| n0a-api-auto | `ieidev-team:test-engineer-api`（API 自动化）| 读 test-cases(API直通字段) + 被测环境 base URL → ieidev-team:uicase-to-apicase 转换 + ieidev-team:api-autotest 写/跑/三分 → api-results | test-cases.md(handoff-read n3-merge), **API base URL(运行时输入)**, 产物根 |
| n2-report | 编排自做（不派）| handoff-write 测试报告(ui-results/api-results/覆盖) | — |

## Gate 节点（n2-design-review / n1-coverage-review）
均 `reviewer: reviewer-expert`，按「reviewer 发函 dispatch」段发函 `ieidev-team:reviewer-orchestrator`（cap=test-design / test-coverage）。无 env 时 exec-flow 不 start-run，止于 design 交付。

---

# reviewer 发函 dispatch（review gate 发函评审专家）

适用于**三员工**（dev-engineer + req-architect + test-engineer）所有 `reviewer: reviewer-expert` 的 review gate。评审专家(reviewer) 是 **callee 员工**（无自有 flow），不在上面 node→agent 路由表里——它**不是某个 action 节点的业务 agent**，而是 caller 编排**到 review gate 时发函**的协作方。判据逻辑见 `gate-decision-logic.md`「Reviewer-Expert Gate（已兑现）」；本段定义**发函时的上下文构造**。

> **发函硬规（who→whom / 结构化非自由对话 / 建议非拦截·caller 自主判断）见 `SKILL.md` §2.4quater 跨员工直接发函硬规（v1.5 硬规 2/7）。** 本段只管「上下文怎么构造」，硬规边界以 §2.4quater 为准，勿在两处各写一份免漂移。

## 派单标识（全名，G-009）

```
Agent({subagent_type: "reviewer-orchestrator"})            ❌ not found
Agent({subagent_type: "ieidev-team:reviewer-orchestrator"})  ✅
```

发函只 dispatch **`ieidev-team:reviewer-orchestrator`** 一个入口；它内部读 `orchestration/reviewer.dispatch-table.yml` 把 gate 反查成 in-scope 评审能力、再 fan-out `ieidev-team:reviewer-<cap>`（caller 不直接派 cap agent）。

## 派单方式：后台 + 文件交接（B 轨）

`run_in_background: true`。caller 编排在 review gate **先写 request 文件**，再 dispatch，靠 completion 通知 + 普通 `Read` 拿 verdict，**不读 subagent 内联返回**（同业务派单 B 轨）。

## caller→reviewer 上下文构造（request schema）

caller 编排到 review gate 时，写 `<workspace>/.ieidev/features/<slug>/handoffs/reviewer/<gate>.request.json`：

```json
{
  "target_paths": ["待评产物路径（如 src/, tests/, design.md, sr.md, prototype/）"],
  "caps": ["in-scope 评审能力（编排可留空，reviewer-orchestrator 据 dispatch-table 反查 gate→caps）"],
  "standards_refs": ["standards/reviewer/<cap>.md（reviewer 侧自取，caller 可省）"],
  "thresholds": {"<cap>": 85},
  "request_id": "<gate-node，如 n9a-code-review>",
  "caller": "<员工 id：dev-engineer | req-architect | test-engineer>",
  "diff_range": "<代码评审用的 git diff 区间，可选>",
  "transcript_ref": "<可选 transcript 锚点>"
}
```

**产物落位**：reviewer 全部产物落 `handoffs/reviewer/`——request（`<gate>.request.json`）、各 cap 评分表（`<gate>.<cap>.score.md`）、仲裁（`<gate>.arbitration.md`）、回函 verdict（`<gate>.handoff.json`）。与 caller 自己的 `handoffs/<员工>/` 平级，不混。

## 🔴 契约注：`handoffs/reviewer/` 是裸文件交接，不是 CLI flow-state handoff

handoff 机制现"一机三用"，**前两用走 CLI、第三用走裸文件，schema 不同物**：

| 用法 | 生产方 | 机制 | schema |
|---|---|---|---|
| (a) 同流主循环↔业务 agent | flow-owner 节点（持 `node_id`）| CLI `handoff-write/read` | `node_id/employee/status/summary[…]` |
| (b) P-B 跨员工交付 | flow-owner n8-merge（持 `node_id`）| CLI `handoff-write/read` | 同上 |
| (c) reviewer 发函回函 | **无 flow-state 的 callee** | **裸 `Write`/`Read`** | `{verdict, scores, counts, revisions, 仲裁, anomaly?, by, request_id}` |

因此对 reviewer 本族文件（`<gate>.request.json` / `.<cap>.score.md` / `.arbitration.md` / `.handoff.json`）：

- caller 与 reviewer 一律用普通 `Read`（json 解析）取字段；**绝不可用 `ieidev_core handoff-read` 读本族文件**——它缺 `node_id/employee/status/summary`，CLI reader 会 `FlowStateError: missing required key 'node_id'`。
- CLI `handoff-write/read` 只服务 (a)/(b)——生产方是持 `node_id` 的 flow-owner 节点，schema 对得上；reviewer 无 flow-state，故走裸文件，与 CLI 机制**平级而不同物**（不是漏写键，是另一种东西）。
- 这条契约由 `tests/test_reviewer_wiring.py` 钉死（裸回函喂 CLI reader 必失败 + 文档不得指令 CLI 读裸文件）。

## 发函 → 回收 6 步（caller 视角）

1. 写 `handoffs/reviewer/<gate>.request.json`（上面 schema）。
2. `Agent({subagent_type: "ieidev-team:reviewer-orchestrator", run_in_background: true, ...})`，prompt 指向 request 文件 + slug + workspace。
3.（reviewer-orchestrator 普通 `Read` request → fan-out cap → 评分表 → 仲裁 → 聚合 verdict → 裸 `Write` `<gate>.handoff.json`）。
4. caller 收 completion 通知。
5. 普通 `Read` `<gate>.handoff.json` 取 `verdict / counts / revisions / 仲裁 / anomaly?`（裸文件交接，不走 CLI handoff reader——见上「契约注」）。
6. `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core record-gate <flow> <slug> --gate <gate> --kind review --verdict <V> --request-id <node> --by reviewer-expert --table <caller node-table>`。FAIL 时按 caller 回流规则重做 action 节点（见 `gate-decision-logic.md`）；回函若含 `anomaly`，caller 自行决定是否在自己的 `events.jsonl` 记一条事件（callee 不碰）。

> **L1 回退**：L1 flow-config `reviewer: self` 时**不发函**，按本 gate 的 self 判据自评 record-gate（env 受限/省 token 逃生门）。per-gate reviewer 的 engine 级 config-merge 待后续 plan，本期 L0 node-table `reviewer` 字段生效。

## caller→cap 对应（各员工 review gate 反查）

caller 编排到 review gate 时，`caps` 字段据此填：

| caller:gate | 对应 cap（dispatcher 反查 dispatch-table 得出）|
|---|---|
| dev-engineer:g-plan-review | design |
| dev-engineer:g-code-review | code |
| dev-engineer:g-sec-review | security |
| req-architect:g-sr-review | sr |
| req-architect:g-ar-proto-review | story + prototype |
| req-architect:g-design-review | design |
| test-engineer:g-test-design-review | test-design |
| test-engineer:g-test-coverage-review | test-coverage |