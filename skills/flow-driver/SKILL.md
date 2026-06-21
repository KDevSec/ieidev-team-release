---
name: flow-driver
description: 通用数字员工编排驱动循环——读 staff.yml 路由员工 → 读 node-table 驱动 ieidev-core 引擎走 SOP（next-step → 派 agent / 判 gate → advance → 循环），直到 terminal 或 BLOCKED。Use when 用户说"用开发工程师跑 X"、"用 XX 员工跑这个任务"、"按 SOP 开发"、"自主跑完这个需求"、"用数字员工跑"，或 `/ieidev-team:flow-driver dev-engineer --task "..." --auto`，或任何涉及"员工 × 任务 × 编排流程"的组合请求。也用于断点续跑（session 中断后恢复）和 BLOCKED 解除后重新推进。
---

# flow-driver：通用数字员工编排驱动循环

把"一个数字员工按自己的 SOP 走完一个任务"变成一条可自驱的循环。你（顶层主控）扮演编排角色，读员工的花名册（staff.yml）确定路由，读引擎状态（next-step）确定当前位置，然后逐节点推进——派业务 agent 执行动作、自己判断 gate、调 CLI 落账、循环直到终点。

## 为什么需要这个 skill

ieidev-core 引擎能记账（R1/R2/R3），node-table 能定义节点图，agent .md 能定义人设——但三者之间没有运行时胶水。一个人类主控需要粘贴 ~60 行提示词才能手动描述整个流程。这个 skill 就是那段胶水：把引擎查询、agent 派单、gate 判断串成一个自动循环，让用户只需一句自然语言就能启动。

## 关键约束（贯穿整个循环）

1. **子 agent 不能再开子 agent**：这是 Claude Code 的硬限制。编排角色必须由顶层 session 扮演——你就是编排器，不要试图把编排下放给 dev-engineer-orchestrator agent 自跑。

2. **每个节点/gate 必须调 CLI 落账**：ieidev-core 引擎是状态的唯一权威。跳过 CLI = 状态漂移 = 下次 resume 出错。这在循环中是自动化完成的，但你要确保不跳过。

3. **第三方评审 gate 已兑现发函评审专家**：reviewer-expert 的 gate（dev: g-plan/code/sec-review；req: g-sr/ar-proto/design-review）**不再 deferred 空过**——到 gate 写 `handoffs/reviewer/<gate>.request.json` → dispatch `ieidev-team:reviewer-orchestrator`（run_in_background）→ 普通 `Read` `<gate>.handoff.json` 取 verdict（裸文件交接，不走 CLI handoff reader）→ `record-gate --by reviewer-expert`（6 步见 `references/node-agent-routing.md`「reviewer 发函 dispatch」段 + `references/gate-decision-logic.md`「Reviewer-Expert Gate（已兑现）」）。L1 flow-config `reviewer: self` 时回退自评（逃生门）。

4. **回流有界**：verify / e2e / deploy gate FAIL 后回流到 n6b 重做，最多重试 2 次（总共 3 次尝试），第 3 次引擎自动 escalate 为 blocked。blocked 时输出报告停住，不死循环。

5. **派 agent 时给足上下文**：每个业务 agent 拿到的 prompt 要包含——任务描述、当前节点目标、前序产物路径、UED/materials 等约束。不要只派一个空 prompt。

---

## 1. Bootstrap（从零启动）

用户给你任务描述 + 员工名（或通过 `/ieidev-team:flow-driver` 命令传入参数）。你需要：

### 1.1 解析参数

```
/ieidev-team:flow-driver <employee-id> --task <task-desc-or-path> [--auto] [--slug <slug>]
```

- `<employee-id>`：员工 canonical id（如 `dev-engineer`），从 staff.yml 反查
- `--task`：任务描述文本，或考题/需求文档的路径
- `--auto`：auto_mode=true，所有 gate 自决不停等用户确认
- `--slug`：flow slug（默认从任务描述自动生成一个 filesystem-safe 名称）

如果是自然语言触发（"用开发工程师跑这个考题"），从对话上下文推断 employee-id 和 task。

### 1.2 读 staff.yml 路由

```bash
# 本插件根由 Claude Code 注入 ${CLAUDE_PLUGIN_ROOT}（本 skill 内容会在读取时就地替换成绝对安装路径）。
# 单插件布局：staff.yml 在插件根，python 包统一在 ${CLAUDE_PLUGIN_ROOT}/pyieidev/ 下。
# 不再用 `find ~` 脆启发式猜框架仓位置（FF-2 债已还）。
PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT}
```

读 `$PLUGIN_ROOT/staff.yml`，找到 employee 对应的：
- `node_table`：编排定义路径（相对于插件根）
- `agents`：可用业务 agent 列表
- `runtime_model`：推荐模型
- `flow_skill`：方法论参考（只作知识引用，不调用）
- **多 flow flow-owner**（如 test-engineer）：staff.yml 用 `node_tables`(复数 map：flow→table 路径) + `default_flow`，按要跑的 flow 取对应 table；单 flow 员工仍用 `node_table`(单数)。

确定 **flow 名** 与 **node-table 路径**（下文每条命令把这俩**字面值直接填进去**，不要设 shell 变量——见下方 🔴 自包含规则）：

- **node-table 路径** = `${CLAUDE_PLUGIN_ROOT}/orchestration/<emp>.node-table.yml`（`<emp>` 取员工 canonical id，如 `dev-engineer`；多 flow flow-owner 如 test-engineer 按要跑的 flow 取对应 table，见 staff.yml 的 `node_tables` map）。
- **flow 名** = 对应 node-table 顶部的 `flow:` 字段值（如 `dev-engineer.node-table.yml` 顶部 `flow: coding-flow`；`req-architect` → `design-flow`；`test-engineer.design.node-table.yml` → `test-design-flow`、`.exec.` → `test-exec-flow`）。直接打开 node-table 看顶部 `flow:` 一行即可；若要用单条命令读出来（自包含、读+用合在一个可跑单元里）：
  ```bash
  PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -c "import yaml; print(yaml.safe_load(open('${CLAUDE_PLUGIN_ROOT}/orchestration/<emp>.node-table.yml'))['flow'])"
  ```

> 🔴 **每条命令字面值自包含、不靠 shell 变量跨调用（照抄即可）**：下文循环里**每条** `python3 -m ieidev_core ...` 都把 flow 名（`<flow>`）、node-table 路径（`<node-table 路径>`）、`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev` 前缀**全部行内填实际字面值**，**不靠一次设 `FLOW=`/`NT=`/`export` 给后续命令兜底**——因为 Claude Code 的 Bash 工具每次调用都是全新 shell、环境变量不跨调用持久（官方："Shell state (env vars) does not persist"），靠跨调用变量必然报空 flow 名 / 空 table 路径 / `No module named 'ieidev_core'`。flow-driver 这些 CLI 是 agent 分多次 bash 调用顺序执行的（resume→看输出→next-step→看输出→advance…），所以每条都要单独可跑、每条照抄填字面值即必成功。

### 1.3 探断点或初始化

```bash
# 先探有没有已存在的 flow
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core resume <flow> <slug> --workspace <workspace>
```

- 如果 resume 成功 → 有断点，从 `current_node` 继续
- 如果 resume 报 "not resumable" 或 "no flow-state.json" → 初始化新 flow：
  ```bash
  PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core init <flow> <slug> --display-name "<任务名>" \
    [--auto-mode] --initial-node <第一个节点 id>
  ```
  第一个节点 id 从 node-table 的 nodes 列表找（通常是 `n0-env` 或类似）

- 如果 resume 报 "status=blocked" → 先 `unblock`：
  ```bash
  PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core unblock <flow> <slug> --to-node <想要回到的节点>
  ```

### 1.4 进入 Driving Loop

初始化/恢复完成后，进入下面的主循环。

---

## 2. Driving Loop（主循环）

每轮循环做一件事：**问引擎我在哪 → 判断该做什么 → 做完 → 推进到下一轮**。

```
LOOP:
  ┌─ 查询当前位置 ──────────────────────────────────────────┐
  │  python3 -m ieidev_core next-step <flow> <slug> --table <node-table 路径> │
  └──────────────────────────────────────────────────────────┘
          │
          ▼
  ┌─ 判断 node_kind ─────────────────────────────────────────┐
  │                                                          │
  │  terminal → complete → 输出总结 → STOP                   │
  │                                                          │
  │  blocked → 输出 BLOCKED 报告 → STOP                      │
  │                                                          │
  │  action → 派业务 agent → advance → GOTO LOOP             │
  │                                                          │
  │  gate → 判断 gate → record-gate → GOTO LOOP              │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

### 2.1 查询当前位置

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core next-step <flow> <slug> --table <node-table 路径> --workspace <workspace>
```

返回 JSON 含 `current_node`、`node_kind`、`node_name`、`next_actions`、`gate_spec`、`is_blocked`。这是你每轮唯一的决策依据。

### 2.2 terminal 节点 → 完结

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core complete <flow> <slug> --workspace <workspace>
```

输出总结：列出 phase_history（经过的节点）、gate_calls（判断过的 gate）、最终状态。完结后 STOP——不再循环。

### 2.3 blocked 状态 → 停住报告

输出 BLOCKED 报告给用户：
- 哪个 gate escalate 的
- blocked_reason 内容
- 当前节点 id
- 建议：`ieidev-core unblock <flow> <slug> --to-node <建议节点>` 来恢复

STOP——等用户决定是否 unblock 后重新启动。

### 2.4 action 节点 → 派业务 agent（后台 + 文件交接）

从 `next_actions` 得到下一步节点 id，但当前 action 节点本身需要先完成工作。派单逻辑（B 轨：执行甩后台、决策留主控）：

1. **读 Node→Agent 路由表**（见 `references/node-agent-routing.md`）确定当前节点对应哪个 `subagent_type`
2. **算交接目录**：
   ```bash
   PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core handoff-path <flow> <slug> --employee <canonical-id> --workspace <workspace>
   # → .ieidev/features/<slug>/handoffs/<员工>/
   ```
3. **构造派单上下文**（§4 模板）：prompt 里必含——任务描述、当前节点目标、前序产物路径、工作目录、相关约束（UED/原型图等），**末尾必含「完成后写交接文件」指令**（见 §2.4bis + §4 模板）
4. **后台派 agent**（🔴 `subagent_type` 必须是插件全名 `ieidev-team:<agent-id>`，裸 id not-found——见 `references/node-agent-routing.md` 顶部「派单标识」；🔴 `run_in_background: true` 是 B 轨核心）：
   ```
   Agent({
     subagent_type: "ieidev-team:dev-engineer-env",
     run_in_background: true,
     prompt: "<构造的上下文 + 写交接文件指令>"
   })
   ```
   `run_in_background: true` 让 subagent 的工具调用、内联渲染、大段 result 全在后台 sidechain，**不灌主会话**——这是 B 轨压掉"派单刷屏"的核心。runtime_model 按 staff.yml（当前阶段1统一 opus）。
5. **等完成通知 → 读交接文件**（不读 subagent 内联返回）：
   - 后台 agent 完成时主循环收到 **completion 通知**。
   - 读结构化状态：
     ```bash
     PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core handoff-read <flow> <slug> --employee <id> --node <current_node> --workspace <workspace>
     # → {node_id, employee, status, summary, artifacts, gate_input, reason}
     ```
   - `status=done` → 取 `artifacts` / `gate_input` 作下一步（gate）输入。
   - `status=blocked` / `needs_context` → **不 advance**，按 BLOCKED 处理（§2.3，或带 `reason` 升人）。
   - ⚠️ **可观测**：completion 通知 + 交接文件 `status` 双信号；`handoff-read` 报 `handoff status not found / unreadable`（FlowStateError）= 该节点没干完，**不静默 advance**——按未完成处理（重派或升人）。
6. **推进到下一节点**（仅 `status=done`）：
   ```bash
   PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core advance <flow> <slug> <to_node> --table <node-table 路径> \
     --reason "<node_name> 完成" --workspace <workspace>
   ```
   `to_node` 取 `next_actions[0].to_node`（action 节点通常只有一个 next）

### 2.4bis 文件交接协议（B 轨核心，最小够用）

业务 agent **不把产出大段 result 回灌主会话**，而是写一个结构化状态文件，主循环读它。

- **路径**：`.ieidev/features/<slug>/handoffs/<员工 canonical-id>/<node_id>.handoff.json`（目录由 ieidev-core `handoff_dir` 约定，P-Core-FF 已建；**不自创新目录**）。
- **schema**（ieidev-core `write_handoff_status` 落、`read_handoff_status` 校验）：

  | 字段 | 含义 |
  |---|---|
  | `node_id` | 当前节点 id |
  | `employee` | 员工 canonical id |
  | `status` | `done` / `blocked` / `needs_context` |
  | `summary` | 一句人话（必填） |
  | `artifacts` | 产物路径列表（可空） |
  | `gate_input` | 给下一 gate 的结构化信号，可 `null` |
  | `reason` | `status != done` 时必填 |

- **agent 怎么写**：派单 prompt 末尾注入指令（见 §4 模板），让 agent 收尾调 `ieidev_core handoff-write ...`。
- **主循环怎么读**：`handoff-read`（见 §2.4 step 5）。
- **为什么文件而非 result 回灌**：result 回灌刷屏主会话（连 recorder 的机器块都被反馈嫌吵，见 MQ-1）；文件交接 = 主循环只读它要的几个字段，编排叙述清爽。**gate 判断仍在主循环**（B 轨守界：执行甩后台、决策留主控）。

### 2.4ter 跨员工 handoff（上游交付 → 下游 spec 输入）

§2.4bis 是**同一 flow 内**主循环↔业务 agent 的交接（按 `current_node` 读）。本段是**跨员工跨 flow**的交接：上游员工（如需求架构师 req-architect）design-flow 的交付，喂给下游员工（开发工程师 dev-engineer）coding-flow 的 spec/plan 输入。**机制纯复用 B 轨 `handoff-write`/`handoff-read`，不新增原语。**

**join 键 = 同一 feature slug。** 一个 feature 一个 slug：req-architect 在 slug X 上跑 design-flow、落产物到 `.ieidev/features/X/handoffs/req-architect/`；dev-engineer 在**同一 slug X** 上跑 coding-flow，读这里当输入。

**生产方（上游）落交付 manifest**：在其**聚合/交付节点**收尾时调一次：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core handoff-write design-flow <slug> --workspace <ws> \
  --employee req-architect --node n8-merge --status done \
  --summary "<一句话：交付了什么>" \
  --artifact .ieidev/features/<slug>/handoffs/req-architect/sr.md \
  --artifact .ieidev/features/<slug>/handoffs/req-architect/ar.md \
  --artifact .ieidev/features/<slug>/handoffs/req-architect/prototype/ \
  --artifact .ieidev/features/<slug>/handoffs/req-architect/design.md \
  --gate-input '{"sr":"<sr 路径>","ar":"<ar 路径>","prototype":"<prototype 路径>","design":"<design 路径>"}'
```
- `artifacts` = 产物路径列表（人/机都能顺着取）；`gate_input` = role→path 结构化指针（消费方按角色精确取 sr/ar/prototype/design）。

**生产方 → 交付节点映射**（消费方据此知道读哪个 `--node`）：

| 生产方（员工）| 交付节点 `--node` | 交付内容 |
|---|---|---|
| `req-architect` | `n8-merge` | SR / AR(迭代+用户故事) / 原型 / 方案 |
| `test-engineer` | `n3-merge`（design-flow）| test-points / test-cases（黑盒设计产出）|
| `test-engineer` | `n2-report`（exec-flow）| ui-results / 覆盖报告 |

> 🔴 **test-engineer 黑盒独立**：消费方=`handoff-read req-architect n8-merge` 取需求/原型作设计输入（缺失裸任务）；**显式不建 dev-engineer→test-engineer 边**——test 不读 dev 代码/flow，避免"代码自测"污染。被测环境 URL 是运行时输入（非 handoff 依赖）。

**消费方（下游）读上游交付**：下游员工在其入口节点按上表读**同 slug** 的上游交付：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core handoff-read coding-flow <slug> --workspace <ws> \
  --employee req-architect --node n8-merge
# → {node_id, employee, status, summary, artifacts, gate_input, reason}
```
- `status=done` → 取 `gate_input` 的 role→path 指针 / `artifacts` 作下游 spec/plan 输入（dev-engineer n0-env 读 SR+背景；n3-plan 读 AR+方案切增量）。
- **上游缺失**（`handoff-read` 报 `handoff status not found` = FlowStateError）→ 该 slug 没有上游交付，**回退裸任务**：dev-engineer 按现状（clone+蒸馏 / 自己定增量）走，不阻断、不报错。

**为什么不另起原语**：B 轨 `write/read_handoff_status` 已是「谁产了啥+路径+状态」结构化指针，跨员工只是换 `employee`/`slug` join 维度，零扩展即覆盖（守「复用别重造」）。**gate 判断仍在主循环**（同 §2.4bis 边界：执行甩文件、决策留主控）。

### 2.4quater 跨员工直接发函硬规（v1.5 硬规 2/7）⭐

§2.4ter 给的是「**怎么发函**」（机制：B 轨 handoff write/read）。本段钉死「**谁能给谁发 / 发的是什么 / 对方说了算不算**」——把[概念模型合稿 §10.1 通信硬规](../../../../docs/framework/01-design/2026-06-10-02-KDev数字员工-概念模型与员工能力-合稿-v1.0.md) 的硬规 2/4/5 收口成**编排 runtime 契约**，全集群发函（caller→reviewer 评审、上游→下游交付）共守。canonical 声明在合稿 §10.1，本段是其运行时落地。

**① 谁能给谁发函（who→whom）：**
- 🔴 **员工编排能力之间直接发函、不经 CEO**（硬规 2）：员工 A 编排 → 员工 B 编排（3 跳：A 编排→B 编排→B 能力→回流）。CEO 只在 4 场景介入（阶段聚合 / 异常升级 / 用户问询 / 评审 3 次循环升级），日常协作不掺和。
- 🔴 **业务/评审能力不直接对外**（硬规 4、硬规 5）：能力（`dev-engineer-frontend`、`reviewer-code`…）只跟自家编排对话；跨员工协作**必须走编排能力**，不能能力直连别家能力。发函**只 dispatch 对方的 `<employee>-orchestrator`**（评审专家即 `ieidev-team:reviewer-orchestrator`），由它内部 fan-out 自家 cap——**caller 不直接派对方的 cap agent**。
- 评审专家是 **callee**：被 caller review gate 发函调用，**只回函给请评审的那个 caller 编排**，从不反向命令 caller、不跨员工另联、不 halt caller flow。

**② 发函 = 结构化请求，非自由对话：**
- 发函落**结构化 request 文件**（`handoffs/reviewer/<gate>.request.json` 或交付 manifest），字段 = **谁发给谁**（`caller`）+ **评什么/要什么**（`caps` / `target_paths` / `gate_input`）+ **产物指针**（`standards_refs` / `artifacts` / `thresholds`）。**不是**往主会话糊一段自然语言指令。
- 走 **B 轨**（`run_in_background` + 文件交接），**不读 subagent 内联返回**——执行甩后台、决策留主控（避免结果回灌刷屏，MQ-1）。回函同样落结构化文件，但 **reviewer 回函是裸文件交接**（`<gate>.handoff.json`，自定义 schema、无 CLI 必填键）caller 用普通 `Read` 取，**不同于** intra-flow/P-B 业务 agent 的 handoff status（走 CLI flow reader，schema 含 `node_id` 等必填键）——契约见 `references/node-agent-routing.md`「reviewer 发函 dispatch」段。

**③ 边界：评审给建议、caller 自主判断（非硬拦截）：**
- 评审专家**只产出**评分表 + 🔴/🟡/⚪ 分级**建议** + verdict，**不直接命令** caller 改什么。🟡/⚪ 由 caller 编排 **自主判断**修 or tech-debt 化。
- 🔴 阻断**有牙齿但经 gate**：经**双重通过条件**（`total≥阈值 AND 🔴=0`）强制该能力 FAIL（总分再高也不放行），但兑现路径是 **caller flow 的有界回流 + escalate**（ieidev-core 执行），评审专家**不自己 halt/command** caller。
- **处置权 + 入账都在 caller**：caller 读 verdict → 自主决定回流修哪些 → 自己调 `record-gate --by reviewer-expert` 入账（评审专家不碰 ieidev-core 状态机）。3 次不过 → `status=blocked` 升 CEO → 用户拍板，escalate 不 force-accept。

**守 [G-008]**：编排**仍走通用 `flow-driver`**——caller（flow-owner）用本 skill 驱动自己的 node-table，到 review gate 按 §2.5c 发函；评审专家（callee）**不复用本 driver、不持有自己的 `flow-state`、不写 `features/<slug>/` 流程账**，只产评分表寄生 caller flow 贡献一个 verdict。别给 callee 造假 node-table（spec §2.1）。

### 2.5 gate 节点 → 判断

从 `next-step` 返回的 `gate_spec` 确定判断逻辑。四种情况：

#### a. reviewer=self + auto_mode=true → 自判

你（主控）根据 gate 判定逻辑（见 `references/gate-decision-logic.md`）自行判断 verdict，直接调 CLI：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core record-gate <flow> <slug> \
  --gate <gate_id> --kind <decision|review|acceptance> \
  --verdict <verdict_value> --request-id <current_node> \
  --table <node-table 路径> --workspace <workspace>
```

- decision gate：verdict 取 `gate_spec.branches` 的某个 key
- review/acceptance gate：verdict 取 `PASS` 或 `FAIL`

#### b. reviewer=self + auto_mode=false → 自判 + 问用户确认

先按 a 的逻辑自判，但**停下来问用户确认**："我判断 g-xxx = Y，你确认吗？" 用户确认后才调 record-gate。

#### c. reviewer=reviewer-expert → 发函评审专家（已兑现，非 deferred）

评审专家(reviewer) 已建（spec v0.2 / Q-016）。不再记 deferred PASS——走**发函协作 6 步**（发函的派单/后台/handoff 机制详见 `references/node-agent-routing.md`「reviewer 发函 dispatch」段 + `references/gate-decision-logic.md`「Reviewer-Expert Gate（已兑现）」，与 verify/e2e/deploy gate「先派 agent 收证据再判」同 B 轨）：

1. 写 `<workspace>/.ieidev/features/<slug>/handoffs/reviewer/<gate>.request.json`（`{target_paths, caps, standards_refs, thresholds, request_id:<current_node>, caller:<员工id>, diff_range?}`）。
2. 发函 `ieidev-team:reviewer-orchestrator`（后台 B 轨，派单细节见 node-agent-routing.md），prompt 指向 request + slug + workspace。
3. 收 completion → 普通 `Read` `<gate>.handoff.json` 取 `verdict`（裸文件交接，不走 CLI handoff reader；契约见 `references/node-agent-routing.md`「reviewer 发函 dispatch」段）。
4. 由你（主控）在主循环调 record-gate 入账（verdict 判定不下放，沿用评审专家聚合结论）：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core record-gate <flow> <slug> \
  --gate <gate_id> --kind review \
  --verdict <PASS|FAIL> --request-id <current_node> \
  --by reviewer-expert \
  --table <node-table 路径> --workspace <workspace>
```

FAIL 时按回流规则重做对应 action 节点（gate-decision-logic.md）。

#### d. reviewer=reviewer-expert 但 L1 回退 self → 自评（逃生门）

L1 flow-config 把该 gate 配成 `reviewer: self`（env 受限/省 token）时**不发函**，按 a/b 的 self 自评逻辑判 + record-gate。per-gate reviewer 的 engine 级 config-merge 待后续 plan，本期靠手改 node-table reviewer 字段回退。

### 2.6 回到 LOOP

record-gate 或 advance 完成后，回到 2.1 重新查询 next-step，开始下一轮。

---

## 3. 特殊场景处理

### 3.1 断点续跑（session 中断恢复）

如果 session 中断了，下次新 session 里用户说"继续上次的工作"：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core resume <flow> <slug> --workspace <workspace>
```

从 `current_node` 继续，进入 Driving Loop。不需要重新 init。

### 3.2 BLOCKED 解除

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core unblock <flow> <slug> --to-node <回到哪个节点>
```

然后重新进入 Driving Loop。建议 `--to-node` 设为回流目标节点（如 n6b），而不是停在原来 escalate 的 gate 节点。

### 3.3 增量 vs 实现工序（别踩 G-005 的坑）

**先分清两件事**（详见 `references/gate-decision-logic.md` 顶部）：

- **增量 = 能独立过 e2e 的纵向切片**（如"购物车""支付"各自可独立验收）→ 走 g-increment 循环
- **实现工序 = 一个增量内部的横向分层**（如 T0 主题 → T1 登录 → T2 仪表盘，是一套视觉系统的分层）→ 在**单个 n6b 节点内部**做完，可多次派 frontend 分批建，**中间不跑 gate 链**

**两种循环别混**：

| 想干什么 | 走哪条路 |
|---|---|
| 一个增量内部分批写代码（T0→T4） | n6b 内部多次派 frontend，**不经过 gate** |
| 一个增量没做好要重做 | g-verify/g-e2e **FAIL 回流** → n6b |
| 这个增量过了 e2e，做下一个纵向切片 | g-e2e PASS → **g-increment more** → n6b |
| 所有增量都过了 e2e | g-increment **done** → 收尾链（n10→n11→n12，跑一次） |

**关键**：考题列的 T0/T1/T2/T3/T4 是**实现工序不是增量**——UED 视觉改造整体就是 **1 个增量**（N=1），T0-T4 在 n6b 内部一次做完，e2e PASS 后 g-increment 直接判 `done` 进收尾。**绝不要把 T0-T4 当 4 个增量去 g-increment more 循环，更不要用 g-deploy FAIL 当增量切换**（那是被根治掉的旧 bug）。

### 3.4 n6a vs n6b 选择

g-complexity gate 判断：
- `simple` → n6a-impl-inline（主控直接实现，不派 subagent）
- `complex` → n6b-impl-subagent（派 `ieidev-team:dev-engineer-frontend` subagent）

绝大多数视觉改造考题是 `complex`，走 n6b。

---

## 4. 上下文构造模板

派业务 agent 时，用这个模板构造 prompt：

```
你是 <agent 中文名>（<agent canonical id>），当前在 coding-flow 的 <node_id> 节点（<node_name>）。

## 任务
<--task 参数的内容，或从文件读取的考题/需求描述>

## 当前节点目标
<从 node-table 和 agent 人设文档中提取的该节点职责描述>

## 前序产物（已存在）
- env.md: <路径>
- rules.md: <路径>
- PLAN.md: <路径>
- ...

## 约束
- UED 规范：<materials_path>/AGENTS.md
- 设计 token：<materials_path>/design-tokens.json
- 原型图：<materials_path>/01-pic/login.png 等
- ...

## 工作目录
<workspace 路径>
```

派 agent 时，在上面模板**末尾追加**下面这段「写交接文件」指令（B 轨文件交接，REQUIRED）：

```
## 完成后写交接文件（REQUIRED）

完成本节点工作后，你【必须】把结构化状态写到交接文件（**不要**把大段产出回灌——产出落 artifacts，主控只读交接文件）：

PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core handoff-write <flow> <slug> \
  --employee <你的 canonical id> --node <当前 node_id> \
  --status done \
  --summary "<一句话：这步干完了什么>" \
  --artifact <产物路径> [--artifact <更多产物>] \
  [--gate-input '<给下一 gate 的 JSON，如 {"build":"pass","lint":"clean"}>'] \
  --workspace <workspace>

若未完成 / 被阻塞：把 --status 改成 blocked（或 needs_context）并加 --reason "<为什么>"。

你的 final message 只回一句话确认（如"n3-plan 完成，详见交接文件"）——详情在交接文件 + artifacts 里，**不要长篇回灌**。
```

（主控构造 prompt 时把 `<FRAMEWORK_REPO>` / `<flow>` / `<slug>` / `<node_id>` / `<canonical id>` / `<workspace>` 全部替换成实际值再派单。）

---

## 5. CLI 快查

所有 ieidev-core CLI 子命令（`--workspace` 默认 cwd，可省略）：

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `init` | 初始化新 flow | `--display-name`, `--auto-mode`, `--initial-node` |
| `resume` | 探断点续跑 | 无 |
| `next-step` | 查询当前位置+可选动作 | `--table` |
| `advance` | 推进到下一节点 | `to_node`, `--table`, `--reason` |
| `record-gate` | 记录 gate 判断 | `--gate`, `--kind`, `--verdict`, `--request-id`, `--table`, `--by` |
| `complete` | 终结 flow | `--status completed|aborted` |
| `unblock` | 解除 blocked | `--to-node` |
| `list-flows` | 列出所有 flow | 无 |
| `gate-lookup` | 查当前 gate spec | `--table` |
| `show` | 看当前完整状态 | 无 |

gate verdict 规则：
- decision：取 `branches` 的 key（如 `high`/`low`、`simple`/`complex`）
- review/acceptance：`PASS` 或 `FAIL`

---

## 参考文件

本 skill 有两个 reference 文件，按需读取：

- **`references/node-agent-routing.md`**：Node→Agent 路由表——每个 action 节点对应哪个 subagent_type、需要传什么上下文。派单前读这个文件确定该派谁。
- **`references/gate-decision-logic.md`**：Gate 判定逻辑——每个 self-review gate 的具体判据。到 gate 节点时读这个文件确定怎么判。