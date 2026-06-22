---
name: ieidev-goal
description: 目标总编排——把一个高层目标端到端跑通需求到测试的跨数字员工交付流水线。你（主控）做目标总编排：把目标 LLM 对号入座到命名生命周期模板（lifecycle）→ 渲染一屏编排结论让人确认/微调 → 冻结 delivery-plan → 主会话顺序链式调 /ieidev-team:flow-driver 跑各段（需求→开发→测试），段间同 slug 接力、停人闸停人。Use when 用户说"总编排 / 目标总编排 / 一个目标跑通需求到测试 / 把这个需求从头跑到测试 / 端到端交付 X / 编排一条跨员工流水线"，或 `/ieidev-team:goal <高层目标>`，或任何"一个高层目标 × 跨多个数字员工 × 端到端交付"的组合请求。单员工单任务请改用 /ieidev-team:flow-driver。
---

# goal：目标总编排（一个目标跑通需求到测试）

把"一个高层目标"端到端编排成跨数字员工的交付流水线。你（顶层主控）做目标总编排：先把目标路由到一个命名的**生命周期模板**（lifecycle），产出一份**delivery-plan**（封闭 schema 的交付计划）；渲染一屏编排结论给人确认/微调；确认后冻结计划，再在**主会话**里**顺序**调 `/ieidev-team:flow-driver`，让每个数字员工按自己的 SOP 跑完一段，段间同 slug 接力，到停人闸停下向人汇报。

整个编排分三段：**plan → confirm → drive**。本 skill 不引入任何新引擎、新原语——它只是把已建的 lifecycle / lint / delivery_plan / confirm / drive 五个纯函数模块、ieidev-core CLI、`/ieidev-team:flow-driver`、reviewer-orchestrator、HUD 串成一条主会话循环。

---

## §0 硬约束（贯穿整个编排，先读再动）

🔴 **子 agent 不能再开子 agent**（Claude Code 硬限制）。后果链：

1. **总编排只能主会话跑**。目标总编排必须由顶层 session 执行——你就是总编排器，不要把整段编排下放给某个 agent 自跑。
2. **drive 段在主会话里顺序调 `/ieidev-team:flow-driver`**。`/ieidev-team:flow-driver` 本身也跑在主会话（它是另一层主控编排循环），**它内部**才会派 capability agent（如 `dev-engineer-orchestrator` / 各 reviewer-cap）。
3. 🔴 **绝不**把 `/ieidev-team:flow-driver` 当 `Agent()` 子 agent 派出去。一旦把它派成子 agent，它就降为"子 agent"，无法再派 capability agent，整条 flow 当场断掉。正确做法是：主会话**自己**执行 `/ieidev-team:flow-driver <emp> ...`（即把控制权交给那段 flow-driver 循环），它跑完回到主会话，再进下一段。

一句话：目标总编排（本 skill）顺序"接力跑"各段 flow-driver，全程不开任何编排 subagent。

### §0.1 `--auto` 逃生口语义

默认**交互档**：goal 在 plan 后 needs_clarification 为真时先和人澄清需求；confirm 段渲完编排结论后写 `pause-gate` 停下等人确认；drive 段每到 `human_gate_after` 非 null 时写 `pause-gate` 停下。后两个停靠由 PreToolUse hook `block-advance-past-gate`（`hooks/hooks.json` 已注册）实现**硬停**——一旦停靠标记写下，即使 auto 模式也绕不过（hook 返回 `permissionDecision: deny`，确定性）。

显式传 `--auto`（`/ieidev-team:goal <目标> --auto`）时跳过上述所有人闸（不写 pause-gate 标记、不停下），自负风险——适合无人值守、已对齐方案的场景。

---

## §0.5 PYTHONPATH 自包含（照抄即可）

本 skill 的 `from ieidev_team import ...` 与 `python3 -m ieidev_core|ieidev_hud ...` 都需要本插件 python 包根在路径上。4 个包统一在 `${CLAUDE_PLUGIN_ROOT}/pyieidev/` 下（`${CLAUDE_PLUGIN_ROOT}` 在本 skill 内容读取时已就地替换成绝对安装路径）。

🔴 **每条 python 命令都行内自带前缀 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev`，不靠一次 `export` 给后续命令兜底**——因为 Claude Code 的 Bash 工具每次调用都是全新 shell、环境变量不跨调用持久（官方："Shell state (env vars) does not persist"），靠 export 必然每条后续命令报 `No module named 'ieidev_team'`/`'ieidev_core'`。下文 `python3 ...` / `python3 -m ieidev_core ...` 都已照此自包含写好（python 内联代码块同理在前面加 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -c "..."`），照抄整条即可、每条单独必成功。**不再用 `find ~` 猜路径（FF-2 已还）。**

---

## §1 plan 段：目标 → 生命周期模板 → delivery-plan

用户给一个高层目标（如"做用户认证功能"）。你要把它**对号入座**到一个命名生命周期模板，产出 delivery-plan dict。

### 1.1 读模板与花名册

```python
from ieidev_team import lifecycle
templates = lifecycle.list_templates()          # 列 lifecycles/*.yml 的 template_id
tpl = lifecycle.load_template("full-delivery")   # 取某模板 dict（不存在 → TemplateError）
```

每个模板 dict 含：`template_id` / `display` / `when`（命中条件，给 LLM 对号入座用）/ `stages`（每段 `{emp, flow, handoff_from}`）/ `reviews_default` / `human_gates_default`。同时读 `staff.yml` 拿到合法 emp 集合。

> **MVP 范围**：当前只兑现 `full-delivery` 一模板（需求→开发→测试三段）。其余模板（design-only / design+build / test-only / build-only）是后续纯加 YAML 即生效——不要在本 skill 里硬编码它们的逻辑。

### 1.2 LLM 对号入座

你（LLM）读各模板的 `when`，结合目标语义判断命中哪个模板，给出：

- `confidence`（0–1，对路由判断的把握）
- `reasoning`（一句话为什么是这个模板）
- 命中模板的 `stages`（照模板 seed，可逐段 `on: true/false` 增删、可改 `review_overrides` / `human_gates`）
- **当 `confidence < 0.6` 或目标同时贴近两个模板时，必填 `runner_up: {template_id, why_not}`**（次优模板 + 为什么没选它），供确认屏并列展示。

### §1.3 需求澄清门控（非 `--auto`）

plan 产出后，调用：
```python
from ieidev_team.delivery_plan import needs_clarification
if needs_clarification(plan):   # confidence < 0.6
    # 先和人来回澄清 2-3 个问题（意图/边界/验收口径）
    # 据答复重算 plan → 再跑 §1.2 → 再判 needs_clarification
    ...
```
`--auto` 时跳过澄清门控，直接进 §2。

### 1.4 组装 delivery-plan dict

按 `ieidev_team.delivery_plan` 的 schema 组装（字段示例见模块 docstring / 任务简报）：

```yaml
template_id: full-delivery
slug: user-auth
goal: "做用户认证功能"
confidence: 0.86
reasoning: "全新功能+无现成SR+安全敏感+需可测交付 → 全交付三段"
stages:
  - {emp: req-architect, flow: design-flow,      on: true, handoff_from: null}
  - {emp: dev-engineer,  flow: coding-flow,      on: true, handoff_from: req-architect@n8-merge}
  - {emp: test-engineer, flow: test-design-flow, on: true, handoff_from: req-architect@n8-merge}
review_overrides:
  dev-engineer: {g-sec-review: reviewer-expert}
human_gates: [after-req]
runner_up: {template_id: design+build, why_not: "含'功能'隐含可交付→需测试段"}
```

此时 plan 还**只在内存里**（未落盘、未冻结）——进 §2 校验。

---

## §2 confirm 段：lint 校验 → 渲染一屏 → 人确认/微调

### 2.1 校验先行（非空不进确认屏）

```python
from ieidev_team import lint
errors = lint.validate(plan, staff=staff)   # 返回 list[str]；空 = 合法
```

🔴 **`errors` 非空 → 据错修正 plan 重出，绝不带着错误进确认屏**（避免人确认一份非法计划）。修正后重跑 `validate`，直到返回空列表。

### 2.2 渲染一屏编排结论

```python
from ieidev_team import confirm
screen = confirm.render_screen(plan, staff=staff)
print(screen)
```

`render_screen` 打印这一屏：路由到哪个模板 + confidence + reasoning + runner_up（若有）+ 各段 emp/flow/on + per-gate 评审意图（专家/自评）+ 链级停人闸（human_gates）。**per-gate 评审项只是意图展示**（见 §5 诚实债 1）。

#### §2.2-bis 计划说明书骨架随屏展示

`render_screen` 输出里已含「计划说明书（骨架）」段，来自 `confirm.render_plan_skeleton(plan)`：

- **阶段路线**：从模板 stages 派生（模板已知，不需要等 LLM 推理）。
- **worktree 意向**：来自 plan dict 的 `worktree_intent` 字段，值为 `"worktree"` / `"inline"` / 缺失（待 dev 段自动判定）。你（LLM）在 §1 组装 delivery-plan 时，应根据任务规模/风险**显式填写** `worktree_intent`：
  - `"worktree"`：任务改动面大、有专属分支诉求、预计跑 worktree 隔离时
  - `"inline"`：纯小改/热修/文档补丁类，inline 当前分支即可
  - 省略字段 = 不表态（确认屏显示"待 dev 段自动判定"）
- **story 粗估**：来自 plan dict 的 `story_estimate` 字段（字符串，如 `"~5-8 个用户故事（预估）"`）。你在 §1 组装 plan 时同样应按需填写——这是 LLM 毛估、不精确，confirm 屏会标「预估」字样，decompose 跑完后 HUD 自动填实真实数据。

两个字段均为**可选**，不填时确认屏展示占位文字，不影响 lint 校验。

### 2.3 人确认/微调循环

读人输入：

- 人按 **Enter**（无修改）→ 接受当前 plan，进 §3。
- 人给一条编辑命令 → `confirm.apply_edit(plan, command)` 应用（非法命令 → `EditError`）→ 回到 §2.1 重跑 `validate` + 重渲一屏 → 再读人输入。如此循环，直到人 Enter。

🔴 **禁一键 Enter 的两种情形**（强制二次确认，不让人闭眼放行）：

1. `confidence < 0.6`（路由判断本身没把握）；
2. 计划**丢段**（某关键 stage `on: false` 导致交付链不完整，如有"功能"目标却砍掉测试段）。

这两种情形下，明确向人指出风险点，要人**显式输入确认词**（而非空 Enter）才放行。

### §2.3bis confirm 硬停（非 `--auto`）

渲完编排结论 + 人读完屏幕后，非 `--auto` 下：
1. 写停靠标记：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core pause-gate <slug> confirm --reason "待人确认 delivery-plan"`
2. 停下，向人汇报：「计划已渲染，请审阅 confirm 屏并回复（Enter 接受 / 编辑命令 / 澄清）」
3. 人确认后（Enter 或编辑）：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core confirm-gate <slug> confirm`，清标记，进 §3。

hook 保证：若此时 LLM 想绕过停靠直接调 `python3 -m ieidev_core dispatch-start ...`，PreToolUse hook `block-advance-past-gate` 检测到 `<slug>` 有 PAUSED-confirm 标记，返回 deny，Bash 工具调用被拒绝。

---

## §3 drive 段：冻结 → build_sequence → 逐段接力跑 flow-driver

### 3.1 冻结落盘（写一次、之后不变）

```python
from ieidev_team import delivery_plan
delivery_plan.write(workspace, plan)   # 落 features/<slug>/delivery-plan.yml
```

冻结后该 yml 不再改——它是本次链级编排的权威快照，HUD 读它渲链进度（§6）。

### 3.2 取有序步骤

```python
from ieidev_team import drive
steps = drive.build_sequence(plan)   # list[step]
```

每个 step 含：`stage_index` / `emp` / `flow` / `dispatch_id` / `handoff_from` / `driver_cmd` / `dispatch_start_cmd` / `dispatch_done_cmd` / `human_gate_after`。`dispatch_start_cmd` / `dispatch_done_cmd` 是给 `python3 -m ieidev_core` 的参数列表；`driver_cmd` 是要在主会话执行的 `/ieidev-team:flow-driver ...` 命令串。

### 3.3 逐段循环（按 steps 顺序，主会话内）

对每个 step：

1. **写派单 start 事件**：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core <step.dispatch_start_cmd...>`
   （即 `dispatch-start <flow> <slug> --emp <e> --dispatch-id <id> --stage-index N`）→ 向 `features/<slug>/events.jsonl` append `phase=start` 事件。
2. **主会话执行 `driver_cmd`**：在**主会话**里跑 `step.driver_cmd`（`/ieidev-team:flow-driver <emp> --task <slug> --slug <slug>`），让该员工的 flow-driver 循环跑到 terminal（完成）或 BLOCKED。**不要 `Agent()` 派它**（§0 硬约束）。
3. **写派单 done 事件**：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core <step.dispatch_done_cmd...>`
   （即 `dispatch-done <flow> <slug> --emp <e> --dispatch-id <id> --status done`）→ append `phase=done`。
   usage 三字段（`--subagent-tokens` / `--tool-uses` / `--duration-s`）**能观测多少填多少，观测不到就不填（落 null）**——flow-driver 跑主会话、整段 usage 取不到一个 usage 对象（见 §5）。BLOCKED 时 `--status blocked`，停下报告，不进下一段。
4. **停人闸 + CQO 审计**：若 `step.human_gate_after` 非 null（如 `after-req`），跑完本段后**停下**——**先按 §4.5 发函 `ieidev-team:cqo-orchestrator` 审计本段过程健康度**，再把「该段交付产物 + CQO verdict」一并向人汇报，等人确认再进下一 step。（阶段交界 / flow 收尾的 checkpoint 同样按 §4.5 触发。）

   非 `--auto` 下，先写停靠标记：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core pause-gate <slug> <step.human_gate_after>`，再停下汇报。人确认后：`python3 -m ieidev_core confirm-gate <slug> <step.human_gate_after>` 清标记。

   hook 保证：即便 LLM 想在停靠标记存在时调 `dispatch-start`/`advance`/`start-run`，PreToolUse hook `block-advance-past-gate` 返回 deny，Bash 被拒绝（确定性，auto 绕不过）。`--auto` 时不写 pause-gate 标记，不停下。

### 3.4 段间 handoff：零新增

段间衔接**不新增任何机制**：上游 flow-driver 已在自己的交付节点 `handoff-write`（如 req-architect 在 `n8-merge` 写交接包），下游 flow-driver bootstrap 时按**同 slug** `handoff-read` 自动捡起（缺失则回退裸任务）。总编排这层不写、不读 handoff，只负责按 `handoff_from` 顺序接力调 driver。

---

## §4 评审发函：总编排不碰

评审 gate（reviewer-expert）的发函**完全由各 flow-driver 内部**按自己 node-table 的 `gate_specs.reviewer` 触发——到 review gate 时由 flow-driver 写 reviewer 请求 → dispatch `ieidev-team:reviewer-orchestrator`（硬规：只派这一个 orchestrator，由它 fan-out 各 reviewer-cap）→ 读 verdict → `record-gate`。

🔴 **目标总编排这层不直接发任何评审函、不直接派任何 reviewer-cap**。评审是 flow-driver 段内的事，总编排只在停人闸汇报里转述结果。

---

## §4.5 CQO 元监督发函：checkpoint 深审（L-b，建议非拦截）

CQO（监督员）是**治理层**——评审专家管「单个产物在 gate 上的质量」，CQO 管「**整条流水线的过程/行为质量**」：gate 有没有真过、TDD 有没有真刷绿、员工有没有跑偏、**同一个错误反复撞了 3 次该不该断路升人**（circuit-breaker）。它**消费现有事件账**（`events.jsonl` + reviewer 回函 + memory Step），不重造，**建议非拦截**——出 verdict 回 goal，处置权在 goal + 人。

> **当前边界（D-1~D-5 + L-a 增量）**：已做 **L-b**（checkpoint 发函深审，LLM 研判，本节）+ **circuit-breaker** 信号 + 过程合规核查；**已加 L-a 逐事件 hook**（常驻监听廉价规则全检 → WARN 信号，消费口径见 §4.6）。**仍不做** plateau 信号（依赖未落地的 FF-4 数字分）。

### 何时发函 CQO（checkpoint 硬编码，D-3）

在以下 **checkpoint**，goal 总编排（你，主会话）**发函 `ieidev-team:cqo-orchestrator` 做一次审计**：

1. **停人闸（human_gate）**：§3.3 step 4 跑到 `human_gate_after` 非 null 时——**先发函 CQO 审计本段，把 CQO verdict 一并纳入向人的汇报**（让人带着「过程健康度」一起拍）。
2. **阶段交界**：一段 flow-driver 跑完、进下一 step 前（尤其上一段 BLOCKED 或反复回流过）。
3. **flow 收尾**：最后一段跑完、整条链交付前，做一次收尾审计。

### 发函 6 步（主会话执行，不开编排 subagent）

1. **写 request**：裸 `Write` `.ieidev/features/<slug>/handoffs/cqo/<checkpoint>.request.json`：
   ```json
   {"slug": "<slug>", "checkpoint": "<after-req|stage-boundary|final>",
    "flow_scope": ["<被审段的 flow 名>"], "caller": "goal", "request_id": "<checkpoint>"}
   ```
   （`threshold` 可省——CQO 缺省读 `staff.yml` 的 `cqo.cqo_supervision.signals.circuit_breaker.threshold`=3。）
2. **dispatch CQO**：`Agent(subagent_type="ieidev-team:cqo-orchestrator", ...)`（**只派这一个**——CQO 是叶子，自己跑机械层 `ieidev_core cqo-audit` + LLM 语义研判，不再 fan-out 任何子 agent）。
3. **收回函**：CQO 完成 → 普通 `Read` `.ieidev/features/<slug>/handoffs/cqo/<checkpoint>.handoff.json` 取 `{verdict, signal, severity, report_ref, evidence[], by:"cqo"}`（裸文件，不走 CLI flow reader）。
4. **goal 据 verdict 决定**（**CQO 不拦，goal 兑现**）：
   - `verdict:escalate`（🔴 circuit-breaker 同根因反复失败）→ **停下向人汇报**，建议升人 / 换策略 / 降范围，**不自动进下一段**。
   - `verdict:prompt`（🟡 过程合规问题，如 gate 疑似空过）→ 在停人闸汇报里**显式列出 CQO 的疑点**，让人判要不要回流。
   - `verdict:ok`（⚪ 核查无异常）→ 照常继续（停人闸照走 / 进下一 step）。

🔴 **goal 这层只是 CQO 的「发函主 + 兑现者」**：CQO 的告警**回给 goal**，由 goal 兑现（升人/提示/放行）；CQO 自己**不碰状态机、不直接拦流、不命令任何员工**（防套娃叶子，spec §8）。**无 CQO verdict 时不阻塞编排**——发函失败/超时则降级为「本 checkpoint 未审计」，照常汇报，不卡链。

---

## §4.6 CQO L-a 信号消费：棒间读 WARN（L-c，常驻监听的兑现端）

CQO 的**常驻监听**（L-a，spec §4.2 L-a 行）已落地为 **PostToolUse(matcher=Bash) hook**（`hooks/cqo-event-audit.py`）：每次任一员工跑 `ieidev_core record-gate/advance/dispatch-*`（写事件落账）**之后**，hook 自动跑**纯 python、零 LLM** 的确定性规则全检（评审被自评糊弄 / advance 过 TDD 节点无测试 / gate PASS 但产物文件不存在），命中即落 `.ieidev/memory/staff/cqo/WARN-<时间戳>.md` 信号文件。**这是机械触发，不分 goal 在不在场**——你（goal 总编排）是它的**消费端**。

> 🔴 **L-a 是逐条全检不是抽样**：廉价确定性规则查得起**每条**写事件（每条都过一遍规则、不漏），所以是「全检 / 逐条全量」，不是「抽查几条」。真正按 checkpoint 抽样深挖的是 **L-b LLM 深审**（§4.5）——全覆盖在 L-a，按需深度在 L-b。

### 何时消费（L-c，每棒之间）

🔴 **goal for-loop 每棒之间（§3.3 每 step 跑完、进下一 step 前）必须扫一次 `.ieidev/memory/staff/cqo/WARN-*.md`**——这是「优先处理 hook 产出」铁规 3 在 CQO 上的落地（同 kdev-memory `WARN-未记录-*.md` 的「hook 留信号 → 主控优先处理 → rm」范式）：

1. **扫信号**：`ls .ieidev/memory/staff/cqo/WARN-*.md`（或裸 `Read` 目录）。无文件 → 照常进下一棒，零额外动作。
2. **有信号 → 据严重度决定**（信号是确定性烟雾报警，非判决——深判要 L-b）：
   - 🔴 高可疑（如多条命中 / circuit-breaker 类）→ **按 §4.5 当场插一次 L-b 深审**（发函 cqo-orchestrator），把深审 verdict 纳入向人汇报。
   - 🟡 单条可疑（如某 gate by 不符 / 单点产物缺失）→ 至少**在下个停人闸汇报里显式列出该疑点**，让人判要不要回流；视情提前插 L-b。
3. **消费后删**：处理完（已升 L-b / 已纳入汇报）→ `rm` 掉该 WARN 文件（避免重复消费 + 污染下次扫描）。**未处理前不要删。**

🔴 **L-a 不拦流、不自动回流**：hook 只「报」（写信号），处置权恒在 goal 棒间消费决策 + 人——与 CQO「建议非拦截」同范式。**棒间扫 WARN 是下意识动作，不依赖被提醒。**

### §4.6.1 R-009 事件驱动 CQO 升级桥：棒间扫 reviewer 回函 anomaly.escalate=CQO

WARN 信号（§4.6 L-a hook）是 CQO **常驻监听**的兑现端；R-009 桥是 CQO **元评审异常**的事件驱动直达端——两者都在棒间消费，互补不重叠。

reviewer-orchestrator 在 review gate **裁不动 / 元评审冲突**时，会在回函 `handoffs/reviewer/<gate>.handoff.json` 写 `anomaly={type:meta-review-conflict|arbitration-undecided, escalate:"CQO"}`（reviewer-orchestrator §Critical 6 / §Capabilities 仲裁 3 步）。此前 goal 只在自己 checkpoint 派 CQO，这类异常只能**等下一次定时 checkpoint 顺带审**——无事件驱动直达（P-final-review D3「R-009 半闭合」）。本桥闭合它。

🔴 **goal for-loop 每棒之间（§3.3 每 step 跑完、进下一 step 前），除扫 WARN 外，还须扫本段 reviewer 回函有无 `escalate=CQO`**：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -c "
from ieidev_team.cqo_bridge import reviewer_handoffs_escalating_cqo
for p in reviewer_handoffs_escalating_cqo('.ieidev/features/<slug>/handoffs/reviewer'):
    print(p)
"
```

- **有命中** → **即时按 §4.5 发函 `ieidev-team:cqo-orchestrator` 审计本段**（事件驱动 L-b；request 的 `checkpoint` 记 `reviewer-escalate`、`flow_scope`=本段 flow），把 CQO verdict 纳入向人汇报——**不必等下一个定时 checkpoint**。
- **无命中** → 照常进下一棒，零额外动作。

判定抽成纯函数 `ieidev_team.cqo_bridge.reviewer_escalates_cqo(handoff_path)->bool`（顶层 dict + `anomaly` 是 dict + `escalate=="CQO"`；缺文件/坏 JSON/缺字段→False，永不抛），`reviewer_handoffs_escalating_cqo(dir)->[Path]` 扫目录返命中（按名排序），有测试钉死（`tests_team/test_cqo_bridge.py`）。**与 §4 不冲突**：goal 仍不发任何评审函、不派 reviewer-cap——只**读**已落地的 reviewer 回函 `anomaly` 字段决定要不要发 **CQO** 函（CQO 发函本就是 goal 的职责，§4.5）。

---

## §5 诚实债（必须对用户明示，不得越界宣称）

本 MVP 是 **L2→L3 human-in-loop 编排，不是自主 L3**。两笔账要对用户讲明白：

🔻 **诚实债 1：评审开关 per-gate 自动化引擎未建。**
确认屏上的 per-gate 专家/自评只是**意图展示**——没有 per-gate flow-config merge 引擎把"这一 gate 走专家、那一 gate 走自评"自动喂进各 flow-driver。当前评审开关只能：① 用 **flow 初始化**时的 `--review-mode {ai,both,human}` 三档做**段级**粗调——这是 **ieidev_core** CLI 的 flag（`python3 -m ieidev_core init <flow> <slug> --review-mode {ai,both,human}` 或 `start-run` 同名参数），`/ieidev-team:flow-driver` **自身不暴露该 flag**（它只接 `--task/--auto/--slug`）；② per-gate 的细粒度切换靠**手改对应员工的 node-table** 的 `gate_specs.reviewer` 字段。**不要宣称 per-gate 评审自动化已工作。**

🔻 **诚实债 2：链级进度无断点续跑，崩了不可恢复。**
跨员工的链级状态（跑到第几 step、哪些段已完成）**只活在主会话内存里**——没有 `delivery-resume` cursor、没有链级断点续跑。主会话崩溃 / 换 session → 链级进度**不可恢复**（已落盘的 delivery-plan.yml 和 events.jsonl 还在，但要人工判断从哪段重起）。**因此本 MVP 不得宣称达 L3**（L3 要求无人值守可恢复的自主编排，本 MVP 不具备）。

> 注：单段 flow-driver 内部有自己的引擎断点续跑（resume 探断点），那是**段内**能力；这里说的"无断点续跑"指的是**链级**（跨段）层面。两者不要混为一谈、不要据段内能力宣称链级 L3。

🔻 **诚实债 4：human_gate 已由 PreToolUse hook 硬停；`--auto` 是显式逃生口。**
§3.3 step 4 的「停人闸」现已有**确定性硬停**：非 `--auto` 下写 `PAUSED-<gate>` 标记，PreToolUse hook `block-advance-past-gate`（已注册 `hooks/hooks.json`）检测到标记即返回 `permissionDecision: deny`，任何试图推进的 Bash 调用被 Claude Code 拒绝——**auto 模式也绕不过**（hook deny 与 skipAutoPermissionPrompt 无关，是更底层的权限拒绝）。显式 `--auto` 是唯一逃生口：跳过 pause-gate 写标记，不硬停，自负风险。

🔻 **诚实债 3：CQO L-a 是「廉价规则烟雾报警 + 棒间消费」，不是真 daemon；plateau 仍未做。**
CQO 现有 **L-a 逐事件 hook**（§4.6）+ **L-b checkpoint 深审**（§4.5）两层。L-a 是 PostToolUse(matcher=Bash) hook——**写事件 CLI 调用之后**触发，跑**纯 python、零 LLM** 的确定性规则（3 条：评审被自评糊弄 / advance 过 TDD 节点无测试 / gate PASS 但产物缺）→ 落 WARN 信号，由 goal **棒间消费**（不是 push、不是逐毫秒轮询的真 daemon——CC 无常驻进程模型）。所以：① L-a 只覆盖**确定性可机械判**的几条规则，深层「TDD 真假绿 / 员工跑偏」仍要 L-b LLM 研判；② 命中**不实时拦流**，靠 goal 棒间扫 WARN 兑现（建议非拦截）；③ **plateau（停滞）信号仍不做**（依赖未落地的 FF-4 数字分）。**可以说「CQO 已做逐事件廉价规则全检（L-a）+ checkpoint 深审（L-b）」，但不要宣称「真后台 daemon 实时拦截」或「停滞检测」。**

---

## §6 HUD：自动渲染，零额外动作

delivery-plan.yml（§3.1 冻结写）+ dispatch 事件（§3.3 start/done append 进 `features/<slug>/events.jsonl`）落盘后，HUD **自动**多渲染出链级进度 + 派单流——总编排这层不需要为 HUD 做任何额外动作：

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_hud render
```

HUD 只读 `features/<slug>/` 下的文件、零写入、运行时不 import ieidev_core（自包含、坏数据降级）；`delivery-plan.yml` 以 guarded `import yaml` 读，缺 PyYAML / 缺文件 / 坏行则降级。总编排只管把数据按契约落到 `features/<slug>/`，渲染交给 HUD。

---

## 速查：本 skill 引用的真实 API / 命令（勿杜撰）

- `ieidev_team.lifecycle`：`list_templates()` / `load_template(id)` / `TemplateError`
- `ieidev_team.lint`：`validate(plan, staff=None) -> list[str]`（空=合法）
- `ieidev_team.delivery_plan`：`parse(text)` / `structural_errors(plan)` / `write(workspace, plan)` / `read(workspace, slug)` / `path(workspace, slug)`
- `ieidev_team.confirm`：`render_screen(plan, staff=None)` / `review_items(...)` / `apply_edit(plan, command)` / `EditError`
- `ieidev_team.drive`：`build_sequence(plan) -> list[step]`（step 键：`stage_index`/`emp`/`flow`/`dispatch_id`/`handoff_from`/`driver_cmd`/`dispatch_start_cmd`/`dispatch_done_cmd`/`human_gate_after`）
- `ieidev_team.cqo_bridge`（R-009 事件驱动 CQO 升级桥，§4.6.1）：`reviewer_escalates_cqo(handoff_path) -> bool`（单份回函是否 `anomaly.escalate==CQO`，永不抛）/ `reviewer_handoffs_escalating_cqo(reviewer_handoffs_dir) -> list[Path]`（扫目录返命中，按名排序）
- ieidev-core CLI（每条行内自带 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev` 前缀，照抄即可）：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core dispatch-start <flow> <slug> --emp <e> --dispatch-id <id> [--stage-index N] [--handoff-from <e@node>] [--workspace WS]`；`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core dispatch-done <flow> <slug> --emp <e> --dispatch-id <id> --status {done,blocked} [--subagent-tokens N] [--tool-uses N] [--duration-s N] [--workspace WS]`
- 命令：`/ieidev-team:flow-driver <emp> --task <...> [--auto] [--slug <slug>]`（跑主会话）；`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_hud render`
- CQO 元监督（§4.5，L-b checkpoint 发函）：`Agent(subagent_type="ieidev-team:cqo-orchestrator")`（叶子，自跑机械层不 fan-out）；机械层 CLI `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core cqo-audit <flow> <slug> [--threshold N]`（读 events → circuit-breaker 信号 + 过程合规 flag）；回函裸文件 `.ieidev/features/<slug>/handoffs/cqo/<checkpoint>.handoff.json`
- CQO L-a 信号消费（§4.6，棒间）：扫 `.ieidev/memory/staff/cqo/WARN-*.md`（hook `cqo-event-audit.py` 命中确定性规则时落）→ 据严重度决定（🔴 插 L-b 深审 / 🟡 纳入停人闸汇报）→ 消费后 `rm`。hook 是 PostToolUse(matcher=Bash) 机械触发，goal 只读不写信号。
