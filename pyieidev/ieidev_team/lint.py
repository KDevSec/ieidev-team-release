"""delivery-plan.yml 语义校验器：drive 前硬校验，不过禁进确认屏。

逐字段对 staff.yml / node-table gate_specs / handoff 契约硬校验。
返回空 list = 合法；非空 = 拒进、逐条人读。
"""
from ieidev_team import lifecycle, roster, delivery_plan

_VALID_REVIEWERS = {"reviewer-expert", "self"}
_VALID_HUMAN_GATES = {"after-req", "after-dev", "after-test"}


def validate(plan, staff=None) -> list:
    errs = delivery_plan.structural_errors(plan)
    if errs:
        return errs   # 结构不全，不跑语义（防 KeyError）
    if staff is None:
        staff = roster.load_staff()

    # 1. template
    if plan["template_id"] not in lifecycle.list_templates():
        errs.append(f"unknown template_id: {plan['template_id']!r}")

    on_stages = [s for s in plan["stages"] if s.get("on")]
    seen_emps = []   # 按顺序的 on:true emp，用于 handoff 前向引用校验

    for s in on_stages:
        emp, flow = s.get("emp"), s.get("flow")
        # 2. emp flow-owner + flow 合法
        if not roster.is_flow_owner(emp, staff):
            errs.append(f"stage emp {emp!r} is not a flow-owner")
        elif flow not in roster.flows_for(emp, staff):
            errs.append(f"stage emp {emp!r} has no flow {flow!r}")
        # 3. handoff_from
        hf = s.get("handoff_from")
        if hf:
            if "@" not in hf:
                errs.append(f"handoff_from must be '<emp>@<node>', got {hf!r}")
            else:
                up_emp, up_node = hf.split("@", 1)
                if up_emp not in seen_emps:
                    errs.append(
                        f"handoff_from {hf!r}: {up_emp!r} must be an earlier on stage")
                else:
                    up_flow = next(x["flow"] for x in on_stages if x["emp"] == up_emp)
                    try:
                        dn = roster.delivery_node(up_emp, up_flow, staff)
                    except roster.RosterError:
                        dn = None
                    if up_node != dn:
                        errs.append(
                            f"handoff_from {hf!r}: node must be {up_emp!r} delivery_node "
                            f"{dn!r}, got {up_node!r}")
        seen_emps.append(emp)

    # 4. review_overrides
    on_emp_set = {s["emp"] for s in on_stages}
    for emp, gates in (plan.get("review_overrides") or {}).items():
        if emp not in on_emp_set:
            errs.append(f"review_override emp {emp!r} not in on stages")
            continue
        flow = next(s["flow"] for s in on_stages if s["emp"] == emp)
        try:
            specs = roster.gate_specs(emp, flow, staff)
        except roster.RosterError:
            specs = {}
        for gid, val in (gates or {}).items():
            if gid not in specs:
                errs.append(f"review_override {emp}.{gid}: unknown gate")
            if val not in _VALID_REVIEWERS:
                errs.append(
                    f"review_override {emp}.{gid}={val!r}: must be one of {_VALID_REVIEWERS}")

    # 5. human_gates
    for g in (plan.get("human_gates") or []):
        if g not in _VALID_HUMAN_GATES:
            errs.append(f"unknown human_gate: {g!r}")

    # 6. low confidence → runner_up required
    if float(plan["confidence"]) < 0.6:
        ru = plan.get("runner_up")
        if not (isinstance(ru, dict) and ru.get("template_id")):
            errs.append("confidence<0.6 requires runner_up with template_id")

    return errs
