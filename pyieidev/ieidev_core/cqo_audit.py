# ieidev_core/cqo_audit.py
"""CQO 监督员（元监督）的机械可验聚合层 — circuit-breaker 信号 + 过程合规规则.

定位（spec 2026-06-18-CQO监督员-design §0/§4.3/§10）：
  CQO 评「整条流水线的过程/行为质量」，不评单个产物（那是 reviewer）。双信号里
  **circuit-breaker（反复失败）这一半是「机械可验」的**——数 FAIL 次数、跨 gate/跨
  flow 聚合、看引擎侧 blocked 事实——把这部分确定性逻辑沉到带测试的纯函数，LLM
  agent（cqo-orchestrator）只在其上做**语义去重**（「同一根因撞了 3 次吗」）+ 研判。

约束（callee + 不造第二本账）：
  - **只读消费** events（kdev-core events.jsonl 的 transition/gate/dispatch 行）。
  - **不写** events.jsonl、**不碰**状态机；判定落 CQO 自己 scope + 回函。
  - 纯函数、零 LLM、零 IO（events 由 caller 用 `ieidev_core events <flow> <slug>`
    或 events.read_events 取好后喂进来）—— 与 hud datasource「自包含、坏数据降级」同纪律。

范围（MVP，照主控 D-2/D-4）：只上 **circuit-breaker** 信号 + 过程合规核查。
  plateau 信号不进 MVP（依赖未落地的 FF-4 数字分），故本模块不实现 plateau。
"""

# 默认阈值取 spec §11.1 D-5 / 架构补遗 §8.3 cqo_supervision config 骨架默认值。
# caller（cqo-orchestrator 读 staff.yml 的 cqo_supervision.signals.circuit_breaker.threshold）
# 可覆盖；这里只是兜底缺省。
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3


def _gate_events(events):
    """只取 gate 行（type=="gate"）。其余事件（transition/dispatch）旁路。"""
    return [e for e in events if e.get("type") == "gate"]


def gate_fail_tally(events):
    """按 gate id 聚合 FAIL verdict 次数（跨 gate / 跨 flow）。

    返回 {gate_id: fail_count}（只含 fail_count>0 的 gate）。PASS 不计。
    这是 circuit-breaker 的原始计数面——「同一个 gate 反复被打回」的机械事实。
    """
    tally = {}
    for e in _gate_events(events):
        if e.get("verdict") == "FAIL":
            gid = e.get("gate")
            tally[gid] = tally.get(gid, 0) + 1
    return tally


def circuit_breaker_signals(events, threshold=DEFAULT_CIRCUIT_BREAKER_THRESHOLD):
    """触顶的 circuit-breaker 信号列表（每个触顶 gate 一条）。

    定义（spec §4.3 信号1）：同一 gate **跨 gate/跨 flow** 累计 FAIL >= threshold。
    这里做 CQO 的两个增量里的「跨 flow 聚合」——引擎 gate.py 只在单 gate 单 flow 内
    数 iter，整条链反复在同名 gate 打转引擎看不出，从全景 events 看得出。

    「语义去重」（同根因？）不在这里做——本层只把每次 FAIL 的 issues 文本作为原料
    （issues_samples）带回，由 cqo-orchestrator LLM agent 在其上判同根因。

    返回 list[dict]，每条：
      {gate, fail_count, threshold, signal:"circuit-breaker",
       flows:[去重的 flow 名], issues_samples:[每次 FAIL 的 issues 列表]}
    """
    gate_rows = {}
    for e in _gate_events(events):
        if e.get("verdict") != "FAIL":
            continue
        gid = e.get("gate")
        gate_rows.setdefault(gid, []).append(e)

    signals = []
    for gid, rows in gate_rows.items():
        if len(rows) < threshold:
            continue
        flows = []
        for r in rows:
            fl = r.get("flow")
            if fl not in flows:
                flows.append(fl)
        signals.append({
            "gate": gid,
            "fail_count": len(rows),
            "threshold": threshold,
            "signal": "circuit-breaker",
            "flows": flows,
            "issues_samples": [list(r.get("issues", [])) for r in rows],
        })
    return signals


def process_compliance_flags(events):
    """确定性过程合规核查 —— 规则命中（零 LLM）.

    盯「过程动作合不合规」而非产物质量。MVP 规则集（确定性、机械可验）：
      - pass-without-advance：某 gate verdict=PASS 但全程**没有任何前进流转**
        （非 reflow transition）。可疑：gate 点头了但流没往前走（gate 被糊弄/空过）。

    返回 list[dict]，每条：{rule, gate, severity, detail}。
    规则是 best-effort 烟雾报警，深判交 LLM agent；不命中即返回 []。
    """
    flags = []

    # 是否存在「真前进」流转（非 reflow）。pass 后该有人往前走。
    has_forward_transition = any(
        e.get("type") == "transition" and not e.get("reflow", False)
        for e in events
    )
    if not has_forward_transition:
        for e in _gate_events(events):
            if e.get("verdict") == "PASS":
                flags.append({
                    "rule": "pass-without-advance",
                    "gate": e.get("gate"),
                    "severity": "🟡",
                    "detail": "gate 判 PASS 但事件流里没有任何前进流转，"
                              "疑似 gate 空过 / 流未真推进，建议人工核对该 gate 的产物是否落账。",
                })

    return flags


def _severity_of(circuit_breaker, compliance_flags):
    """聚合严重度：有 breaker → 🔴（阻断级）；只有合规 flag → 取最高 flag 级；都无 → ⚪。"""
    if circuit_breaker:
        return "🔴"
    if any(f.get("severity") == "🔴" for f in compliance_flags):
        return "🔴"
    if compliance_flags:
        return "🟡"
    return "⚪"


def audit_summary(events, threshold=DEFAULT_CIRCUIT_BREAKER_THRESHOLD):
    """把三层聚合打包成 cqo-orchestrator 回函可直接消费的裸 dict（纯数据，无 IO）.

    返回：
      {by:"cqo", severity, circuit_breaker:[...], compliance_flags:[...],
       gate_fail_tally:{...}}
    这是「机械层」产物；agent 在其上加语义去重结论 + 证据指针 + 给 CEO/goal 的建议，
    再写审计报告 + 回函（schema 见 spec §5.2 / 任务简报）。
    """
    cb = circuit_breaker_signals(events, threshold=threshold)
    flags = process_compliance_flags(events)
    return {
        "by": "cqo",
        "severity": _severity_of(cb, flags),
        "circuit_breaker": cb,
        "compliance_flags": flags,
        "gate_fail_tally": gate_fail_tally(events),
    }
