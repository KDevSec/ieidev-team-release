# Gate 判定逻辑

编排器到 gate 节点时，需要判断 verdict。本文件定义每个 gate 的具体判据。

适用于 `dev-engineer`（开发工程师）员工的 coding-flow。其他员工会有自己的 gate 判定逻辑。

## ⚠️ 先搞清"增量"是什么（最容易踩的坑）

**增量 = 能独立过 e2e 验收的纵向切片**，不是实现分层。这条定义决定了整个 flow 循环几次。

| | 实现切片（不是增量） | 交付增量（是增量） |
|---|---|---|
| 例子 | T0 主题 → T1 登录 → T2 仪表盘（一套视觉系统的横向分层） | "购物车" / "支付" / "订单确认"（各自能独立 e2e 的纵向功能） |
| 单独拿出来 | 没法端到端验收（T0 主题单独没有可验收的东西） | 能独立跑过 e2e |
| 该住哪 | **单个增量内部**，是 n6b 实现节点自己的工序 | **flow 级 g-increment 循环单元** |

**判增量数 N 的红线**：一个切片如果**自己过不了 e2e**，它就不是增量，是某增量的子任务，归进那个增量的 task 列表。

**踩过的坑（G-005）**：UED 考题被错拆成 T0-T4 四个"增量"（其实是一套视觉系统的实现分层，**整体只有 1 个增量**）。编排器每个 T 跑一遍 gate 链、跑完想回去做下一个，但拓扑没给合法回头路，于是劫持 `g-deploy FAIL` 当增量循环——deploy 根本没失败、merge 被空过、还撞了 retry cap。**g-increment gate 就是为根治这个而加的合法回头路。**

## Gate 总览

| Gate | 节点 | Kind | Reviewer | 处理 |
|---|---|---|---|---|
| g-relevance | n1-relevance | decision | self | 自判 |
| g-plan-review | n4-plan-review | review | reviewer-expert | **发函评审专家**（已兑现，见下「Reviewer-Expert Gate」） |
| g-complexity | n5-complexity | decision | self | 自判 |
| g-verify | n8-verify | review | self | 自判 |
| g-code-review | n9a-code-review | review | reviewer-expert | **发函评审专家**（已兑现） |
| g-e2e | n9b-e2e | acceptance | self | 自判 |
| **g-increment** | **n9c-increment** | **decision** | **self** | **自判（more/done）** |
| g-sec-review | n10-sec | review | reviewer-expert | **发函评审专家**（已兑现） |
| g-deploy | n12-deploy | acceptance | self | 自判 |

## Self-Review Gate 判据

### g-relevance（关联度，decision → high/low）

判断任务与当前代码库的关联程度，决定是否需要 worktree 隔离。

- **high**：任务与主分支代码有共享 schema / 共享目录 / 共享鉴权 / 直接在主分支上改就行
- **low**：任务独立性强、可能影响主分支稳定性、需要 worktree 隔离

典型判法：读考题/需求 → 看是否涉及"在已有项目里改"（high）vs "独立新功能/实验性任务"（low）。多数视觉改造 = high（直接在主分支改样式）。

### g-complexity（复杂度，decision → simple/complex）

判断任务复杂度，决定主控直接实现还是派 subagent。

- **simple**：单文件改动、< 5 个文件涉及、无需 TDD、主控 1-2 轮能做完
- **complex**：多文件/多页面改动、涉及全局主题/组件系统、需要 TDD 循环、需要多轮 increment

典型判法：读 PLAN.md 的 task 数 → ≤ 3 个 atomic task 且单模块 → simple；> 3 个 task 或跨模块 → complex。视觉改造几乎都是 complex（T0-T3 四个大任务）。

### g-verify（完成验证，review → PASS/FAIL）

判断当前 increment 的实现是否完成。验证清单：

1. `npm run build` 通过（零错误）
2. Lint 通过（零 error，warning 可接受）
3. UED 硬约束 grep 检查：
   - 无裸 hex/rgb 颜色（`grep -rn '#[0-9a-fA-F]\{3,8\}' src/` 除 CSS 变量文件外）
   - 无"登陆"错别字（`grep -rn '登陆' src/`）
4. 关键页面可访问（手动打开或截图确认不破版）

- **PASS**：以上全部通过
- **FAIL**：任一项不通过，回流到 n6b 修

注意：这是"完成验证"不是"质量评审"。只要功能做完了 + 基本约束满足就 PASS，不需要做到完美。

### g-e2e（Per-Increment E2E，acceptance → PASS/FAIL）

判断当前 increment 的端到端质量是否达标。需要先派 `ieidev-team:dev-engineer-e2e` agent 做检查：

1. 视觉 diff：1366px + 1920px 截图 vs 原型图
2. 功能冒烟：登录页能打开 → 输入账号密码 → 点登录 → 进首页
3. UED §10 自检清单逐项勾选（CHECKLIST.md）

- **PASS**：视觉还原可接受 + 核心功能可用 + CHECKLIST 无硬伤
- **FAIL**：视觉偏差大 / 功能不可用 / CHECKLIST 有硬伤，回流到 n6b 修

> e2e PASS = "**这个增量交付完成**"。过了 e2e 就进 g-increment 判断还有没有下一个切片。

### g-increment（增量循环判断，decision → more/done）

判断"刚过 e2e 的这个增量是不是最后一个"，决定回去做下一切片还是进收尾链。

**判据**（在 n3-plan 时已按"可独立 e2e"切好增量、定死总数 N）：
- 编排器跟踪当前做完的是第 k 个增量（从 PLAN.md 的增量清单数）
- **k < N** → `more`（回 n6b 做第 k+1 个切片）
- **k == N** → `done`（所有切片都过了 e2e，进收尾链 n10-sec → merge → deploy）

**铁律**：
1. **N 在 n3-plan 定死，不能边跑边加**。要加增量 = 回 n3-plan 重新规划，不在循环里临时塞。
2. **每个 more 回去的必须是"能独立过 e2e 的纵向切片"**，不是实现分层。如果你发现自己想 more 回去做的是"T0 主题打底""抽个公共组件"这种——停，那是上一个增量没做完的工序，不该走 g-increment，该是 g-e2e/g-verify FAIL 回流。
3. **单增量任务 N=1**：第一个增量过 e2e 后直接 `done`，循环只跑一遍。纯视觉改造、单页面改造这类通常 N=1（T0-T4/各页面都是一个增量内部的实现工序）。

> g-increment 是 decision gate，不碰 retry cap——可以合法循环 N 次，不会像被劫持的 g-deploy FAIL 那样撞 max_retries。

### g-deploy（部署+金丝雀验收，acceptance → PASS/FAIL）

判断部署是否成功 + 金丝雀冒烟是否通过。需要先派 `ieidev-team:dev-engineer-deploy` agent 部署，然后 e2e 做金丝雀检查：

1. 合并分支成功
2. 部署环境可达
3. 金丝雀冒烟：登录 → 首页 → 核心功能走一遍
4. 交付物齐全（PLAN.md / CHANGES.md / CHECKLIST.md / TEST-REPORT.md / RUN.md / screenshots/ / ued6-restyle.patch）

- **PASS**：部署成功 + 金丝雀通过 + 交付物齐全
- **FAIL**：部署失败 / 金丝雀不通过 / 交付物缺失，回流到 n6b

注意：如果是纯视觉改造无后端环境，金丝雀可能 env-blocked（无 MySQL → 无法起 FastAPI）。这时视觉部分能做到"npm run build 通过 + 截图还原"即可，功能冒烟标为 partial。视情况判 PASS（接受限制）或 FAIL（要求必须全功能）。

## Reviewer-Expert Gate（已兑现，发函评审专家）

评审专家(reviewer) 员工**已建**（spec 2026-06-12 v0.2 / Q-016），以下标 `reviewer: reviewer-expert` 的 gate
**不再 deferred 空过**，统一走 spec §5 的**发函协作 6 步**——`reviewer-expert` 是 callee 员工，由编排发函、它 fan-out 评审能力出 verdict 回函：

| 员工:Gate | 评审对象 | 派给（in-scope cap）|
|---|---|---|
| dev-engineer:g-plan-review | plan.md | design（多触点）|
| dev-engineer:g-code-review | src/+tests/+diff | code |
| dev-engineer:g-sec-review | security.md+diff | security |
| req-architect:g-sr-review | sr.md | sr |
| req-architect:g-ar-proto-review | 用户故事 + prototype/ | story + prototype（一闸两能力）|
| req-architect:g-design-review | design.md | design（多触点）|

**发函 6 步**（caller 编排在 review gate 执行；详见 `node-agent-routing.md`「reviewer 发函 dispatch」段）：

1. 写 review 请求 → `handoffs/reviewer/<gate>.request.json`（`{target_paths[], caps[], standards_refs[], thresholds, request_id:<gate-node>, caller:<员工id>, diff_range?, transcript_ref?}`）。
2. 发函 dispatch `ieidev-team:reviewer-orchestrator`（`run_in_background: true`，B 轨）。
3. reviewer-orchestrator 普通 `Read` request（裸文件，不走 CLI handoff reader）→ 并行 fan-out 对应 `ieidev-team:reviewer-<cap>` → 各出百分制评分表。
4. inline 仲裁冲突 + 双重通过条件聚合 gate verdict。
5. 裸 `Write` 结果 → `handoffs/reviewer/<gate>.handoff.json`（`{verdict:PASS|FAIL, scores, counts, revisions, 仲裁, anomaly?, by:reviewer-expert}`）。
6. caller 收 completion → 普通 `Read` 取 `verdict`（裸文件交接，不走 CLI handoff reader）→ `record-gate --gate <gate> --kind review --verdict <V> --request-id <node> --by reviewer-expert`；回函若含 `anomaly` 字段，caller 自行决定是否在自己的 `events.jsonl` 记一条事件。

**FAIL 回流**：`gate_iters<3` → 编排读修订建议、自主判断修哪些（🔴 必处置 / 🟡⚪ 可 tech-debt 化）→ 重做 action → 增量评（只评修订部分）；`≥3` → `status=blocked` 升 CEO，escalate 不 force-accept。

> **L1 回退逃生门**：L1 flow-config `reviewer: self` 时回退自评（env 受限/省 token），不发函、按本节点 self 判据自评 record-gate。per-gate reviewer 的 engine 级 config-merge 待后续 plan，本期靠 L0 node-table reviewer 字段生效。

## Decision Gate 的 verdict 对应节点

方便编排器调 record-gate 时确认 to_node 是否合理：

| Gate | verdict | → 节点 |
|---|---|---|
| g-relevance | high | n3-plan |
| g-relevance | low | n2-worktree |
| g-complexity | simple | n6a-impl-inline |
| g-complexity | complex | n6b-impl-subagent |
| **g-increment** | **more** | **n6b-impl-subagent（下一切片）** |
| **g-increment** | **done** | **n10-sec（进收尾链）** |

## 逐增量循环 vs 收尾链（once）

| 阶段 | 节点 | 跑几次 | 说明 |
|---|---|---|---|
| 逐增量循环 | n6b → n8-verify → n9a-code-review → n9b-e2e → n9c-increment | **每增量一次** | 每个纵向切片走完整质量链；more 回 n6b 做下一切片 |
| 收尾链 | n10-sec → n11-merge → n12-deploy → n13-done | **整任务只一次** | 所有切片都过 e2e 后（g-increment done）才跑：安全扫全量 diff、单次合并、单次部署 |

**别再用 g-deploy FAIL 当增量循环**（G-005 根因）——增量循环走 g-increment more；g-deploy FAIL 回归本义（部署/金丝雀真挂了才 FAIL）。收尾链每个节点整个任务只经过一次，n11-merge 是真合并（不是空过）。

## 回流规则

- g-verify FAIL → n6b-impl-subagent（重做实现）
- g-e2e FAIL → n6b-impl-subagent（重做实现）
- g-deploy FAIL → n6b-impl-subagent（真部署失败才回流，不是增量切换）
- g-plan-review FAIL → n3-plan（重写计划；发函评审专家给 FAIL 时真回流）

回流最多 2 次（总共 3 次尝试），第 3 次引擎自动 escalate 为 blocked。
g-increment 的 more 循环**不算回流**（decision gate，不碰 cap），可循环 N 次。

---

# req-architect（需求架构师）gate 判据

适用于 `req-architect` 员工的 design-flow。3 评审 gate 复刻 ieidev-design-flow 的 3 闸门，**已翻 `reviewer=reviewer-expert`**（兑现评审专家，spec v0.2 / Q-016）——编排到 gate **发函 `ieidev-team:reviewer-orchestrator`**（in-scope cap：g-sr-review→sr / g-ar-proto-review→story+prototype / g-design-review→design），走上面「Reviewer-Expert Gate（已兑现）」的发函 6 步，verdict 由评审专家百分制评分表 + 双重通过条件聚合得出，caller `record-gate --by reviewer-expert`。

**L1 回退 self 自评**（env 受限/省 token）：L1 flow-config `reviewer: self` 时不发函，主控按 design-flow `skills/ieidev-design-flow/references/review-gate-prompt.md` 的成功标准自评，`config.review_mode` 控档：

- **ai**（默认）：主控自评 → 输出 VERDICT/ISSUES → PASS/FAIL，直接 record-gate。
- **both**：自评后 `AskUserQuestion` 让用户确认/覆盖，再 record-gate。
- **human**：直接 `AskUserQuestion` 让用户判 PASS/FAIL。

> per-gate reviewer 的 engine 级 config-merge 待后续 plan；本期 L0 node-table `reviewer` 字段（已是 reviewer-expert）生效，回退靠手改字段。

| Gate | 节点 | 复刻 design-flow | 评审对象 | 判据来源 |
|---|---|---|---|---|
| g-sr-review | n2-sr-review | Gate1 | sr.md | review-gate-prompt.md Stage1 成功标准 |
| g-ar-proto-review | n5-ar-proto-review | Gate2（AR+原型共评）| ar + prototype/ | review-gate-prompt.md Stage2 成功标准（含 C-2.6 宪法合规）|
| g-design-review | n7-design-review | Gate3 | design.md | review-gate-prompt.md Stage3/4 成功标准 |

## 回流有界（复刻 design-flow「3 次 FAIL → 升人」）

FAIL 时引擎自动 `gate_iters++`；达 `max_retries(3)` → `status=blocked` 留原地升人（不强过、不冒充第三方）。回流目标：

- g-sr-review FAIL → n1-spec（重写 SR）
- g-ar-proto-review FAIL → n4-prototype（重做原型；AR 本身要返工时编排升级回 n3-decompose）
- g-design-review FAIL → n6-design（重做方案）

> 注：这是 review gate 的 R3 escalate（→ blocked），不是 R2 机械 reflow（→ terminal_fail n-fail）。req-architect 全 review gate，正常不触达 n-fail。

---

# test-engineer（测试工程师）gate 判据

适用于 `test-engineer` 双 flow。两 review gate 均**发函评审专家**（reviewer-expert），按「Reviewer-Expert Gate（已兑现）」段 6 步发函，FAIL 有界回流（cap=3 → blocked 升人）。

> 🔴 **黑盒独立**：测试设计 gate 评的是「测试是否独立覆盖需求」，锚点用需求/原型/用户故事，**非源码**；评审专家不以实现代码为准绳。

| Gate | flow / 节点 | Kind | Reviewer | 处理 |
|---|---|---|---|---|
| g-test-design-review | design / n2-design-review | review | reviewer-expert | 发函 cap=test-design（阈值 85）；FAIL→回流 n0-points 重设计 |
| g-test-coverage-review | exec / n1-coverage-review | review | reviewer-expert | 发函 cap=test-coverage（阈值 80）；FAIL→回流 n0-ui-auto 重跑 |

**追加到「Reviewer-Expert Gate（已兑现）」总表**：
| 员工:Gate | 评审对象 | 派给（in-scope cap）|
|---|---|---|
| test-engineer:g-test-design-review | test-points.md + test-cases.md | test-design |
| test-engineer:g-test-coverage-review | ui-results + 覆盖报告 | test-coverage |