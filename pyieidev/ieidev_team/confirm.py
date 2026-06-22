"""确认屏渲染 + 结构化编辑（纯函数；副作用/交互留 SKILL.md 主会话）。"""
import copy
from ieidev_team import roster

_DISPLAY = {
    "req-architect": "需求架构师", "dev-engineer": "开发工程师",
    "test-engineer": "测试工程师",
}


_STAGE_ROUTE_DISPLAY = {
    "req-architect": "需求架构师·需求设计",
    "dev-engineer":  "开发工程师·开发实现",
    "test-engineer": "测试工程师·测试验收",
}


def render_plan_skeleton(plan) -> str:
    """渲染计划说明书骨架（confirm 阶段）：阶段路线 + worktree 意向 + story 粗估。

    confirm 时 story 数/worktree 落点可能尚未确定，展示意向/粗估并标注待填实。
    """
    L = []
    L.append("── 计划说明书（骨架） ──")

    # 阶段路线
    on_stages = [s for s in plan.get("stages", []) if s.get("on")]
    if on_stages:
        route = " → ".join(
            _STAGE_ROUTE_DISPLAY.get(s.get("emp", ""), s.get("emp", ""))
            for s in on_stages
        )
        L.append(f"阶段路线：{route}")
    else:
        L.append("阶段路线：（无启用段）")

    # worktree 意向
    wt = plan.get("worktree_intent")
    if wt == "worktree":
        L.append("worktree：将在隔离 worktree 执行（dev 段落点待确认）")
    elif wt == "inline":
        L.append("worktree：inline 当前分支执行")
    else:
        L.append("worktree：待 dev 段自动判定")

    # story 粗估
    est = plan.get("story_estimate")
    if est:
        L.append(f"用户故事（预估）：{est}")
    else:
        L.append("用户故事：待 decompose 阶段填实")

    return "\n".join(L)


def review_items(emp, flow, overrides, staff=None) -> list:
    specs = roster.gate_specs(emp, flow, staff)
    ov = overrides or {}
    out = []
    for gid, spec in specs.items():
        if spec.get("kind") != "review":
            continue
        reviewer = ov.get(gid, spec.get("reviewer"))
        out.append({"gate": gid, "reviewer": reviewer,
                    "overridden": gid in ov})
    return out


def render_screen(plan, staff=None) -> str:
    L = []
    slug = plan.get("slug")
    L.append(f"━━━ ieidev 编排结论 · 待你确认  slug: {slug} ━━━")
    L.append(f"目标：{plan.get('goal')}")
    L.append(f"归类：{plan.get('template_id')}   置信度 {plan.get('confidence')}")
    L.append(f"理由：{plan.get('reasoning')}")
    L.append("⚠️ 按依赖串行驱动，非真并发（各段不同时跑）")
    L.append("")
    L.append("拟派流水线（同 slug 串联）：")
    on_stages = [s for s in plan.get("stages", []) if s.get("on")]
    overrides = plan.get("review_overrides") or {}
    for i, s in enumerate(on_stages, 1):
        emp, flow = s["emp"], s["flow"]
        disp = _DISPLAY.get(emp, emp)
        src = f"  ◄── 读 {s['handoff_from']}" if s.get("handoff_from") else ""
        L.append(f"  [{i}] ✓ {disp}  {emp} · {flow}{src}")
        items = review_items(emp, flow, overrides.get(emp), staff)
        if items:
            parts = []
            for it in items:
                tag = " ⚠(已调整)" if it["overridden"] else ""
                parts.append(f"{it['gate']}={it['reviewer']}{tag}")
            L.append("        评审： " + "   ".join(parts))
    L.append("")
    hg = plan.get("human_gates") or []
    L.append(f"人介入闸（停人）：{' · '.join(hg) if hg else '无'}  + 评审3次不过升你裁决")
    ru = plan.get("runner_up")
    if ru:
        L.append(f"次选：{ru.get('template_id')} —— {ru.get('why_not', '')}")
    L.append("")
    L.append(render_plan_skeleton(plan))
    L.append("")
    low = float(plan.get("confidence", 1)) < 0.6
    if low:
        L.append("🔴 置信度<0.6：禁一键 Enter，请二次确认或换模板/微调后再派。")
    L.append("你可以：[Enter] 照此派发  [d N] 关段  [r <emp> <gate>=<self|reviewer-expert>] 调评审"
             "  [g +after-test] 加停人闸  [t <template>] 换模板  [s <slug>] 改 slug")
    return "\n".join(L)


class EditError(Exception):
    pass


def apply_edit(plan, command) -> dict:
    plan = copy.deepcopy(plan)
    parts = command.strip().split()
    if not parts:
        raise EditError("empty command")
    op = parts[0]
    if op == "d" and len(parts) == 2 and parts[1].isdigit():
        on = [s for s in plan["stages"] if s.get("on")]
        idx = int(parts[1]) - 1
        if not (0 <= idx < len(on)):
            raise EditError(f"no stage #{parts[1]}")
        on[idx]["on"] = False
        return plan
    if op == "r" and len(parts) == 3 and "=" in parts[2]:
        emp = parts[1]
        gate, reviewer = parts[2].split("=", 1)
        plan.setdefault("review_overrides", {}).setdefault(emp, {})[gate] = reviewer
        return plan
    if op == "g" and len(parts) == 2 and parts[1][:1] in "+-":
        sign, gate = parts[1][0], parts[1][1:]
        hg = plan.setdefault("human_gates", [])
        if sign == "+" and gate not in hg:
            hg.append(gate)
        elif sign == "-" and gate in hg:
            hg.remove(gate)
        return plan
    if op == "t" and len(parts) == 2:
        plan["template_id"] = parts[1]
        return plan
    if op == "s" and len(parts) == 2:
        plan["slug"] = parts[1]
        return plan
    raise EditError(f"unknown edit command: {command!r}")
