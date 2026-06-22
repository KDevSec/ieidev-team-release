"""kdev-core CLI — drive a flow's R1/R2/R3 engine from the shell.

Thin argparse shell over flow_state (R1) / node_machine (R2) / gate (R3): the
orchestration Agent calls these subcommands at each node. The engine + node-table
stay harness-agnostic; the CLI is just a portable seam. node-table (+ its
`gate_specs` section) is data loaded from a YAML file.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from ieidev_core import flow_state, node_machine, gate, cqo_audit


def _load_table(path):
    """Load a node-table YAML -> (validated table, gate_specs dict)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    table = node_machine.load_node_table(data)
    return table, data.get("gate_specs", {})


def _print_state(state, workspace, extra=None):
    """Print enriched state JSON for orchestrator consumption (flat view)."""
    from ieidev_core import events
    slug = state.get("slug")
    data = {
        "slug": slug,
        "flow": state.get("flow"),
        "display_name": state.get("display_name"),
        "feature_status": state.get("feature_status"),
        "status": state.get("status"),            # run 级
        "active": state.get("_has_active", False),
        "run": state.get("run"),
        "current_node": state.get("current_node"),
        "config": state.get("config"),
        "gate_calls": state.get("gate_calls", 0),
        "gate_iters": state.get("gate_iters", {}),
        "blocked_reason": state.get("blocked_reason"),
        "stories": state.get("stories", []),
        "runs": state.get("runs", []),
        "events_len": len(events.read_events(workspace, slug)),
    }
    if extra:
        data.update(extra)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_show(args):
    state = flow_state.read_state(args.workspace, args.flow, args.slug)
    actual_flow = state.get("flow")  # None if no active run
    extra = None
    if actual_flow is not None and actual_flow != args.flow:
        extra = {"_note": (
            f"flow 不符：请求 '{args.flow}' 但实际活跃 flow 为 '{actual_flow}'；"
            "已按 slug 取真实状态（show 忽略 flow 参数，按 slug 定位）"
        )}
    _print_state(state, args.workspace, extra=extra)
    return 0


def cmd_init(args):
    flow_state.init_state(args.workspace, args.flow, args.slug,
                          display_name=args.display_name,
                          review_mode=args.review_mode,
                          auto_mode=args.auto_mode,
                          initial_node=args.initial_node,
                          origin=args.origin, relates_to=args.relates_to)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_resume(args):
    _print_state(flow_state.resume_state(args.workspace, args.flow, args.slug),
                 args.workspace)
    return 0


def cmd_advance(args):
    table, _ = _load_table(args.table)
    state = node_machine.advance_persist(
        args.workspace, args.flow, args.slug, args.to_node,
        table=table, reflow=args.reflow, reason=args.reason)
    _print_state(state, args.workspace)
    return 0


def cmd_record_gate(args):
    table, gate_specs = _load_table(args.table)
    gr = gate.make_gate_result(
        args.gate, args.kind, node=args.node, verdict=args.verdict,
        request_id=args.request_id, by=args.by, iter=args.iter,
        issues=args.issues or [])
    state = gate.record_gate_persist(
        args.workspace, args.flow, args.slug, gr,
        table=table, gate_specs=gate_specs)
    _print_state(state, args.workspace)
    return 0


def cmd_complete(args):
    flow_state.mark_inactive(args.workspace, args.flow, args.slug,
                             status=args.status)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_start_run(args):
    flow_state.start_run(args.workspace, args.flow, args.slug,
                         initial_node=args.initial_node,
                         review_mode=args.review_mode, auto_mode=args.auto_mode)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_add_story(args):
    flow_state.add_story(args.workspace, args.slug, story_id=args.id,
                         title=args.title, status=args.status)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_set_story_status(args):
    flow_state.set_story_status(args.workspace, args.slug, story_id=args.id,
                                status=args.status)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_close_feature(args):
    flow_state.close_feature(args.workspace, args.slug, status=args.status)
    _print_state(flow_state.read_state(args.workspace, slug=args.slug),
                 args.workspace)
    return 0


def cmd_list_features(args):
    print(json.dumps(flow_state.list_features(args.workspace),
                     ensure_ascii=False, indent=2))
    return 0


def cmd_events(args):
    from ieidev_core import events
    print(json.dumps(events.read_events(args.workspace, args.slug),
                     ensure_ascii=False, indent=2))
    return 0


def cmd_cqo_audit(args):
    """CQO 机械聚合层：读 <slug> 全量 events → circuit-breaker 信号 + 过程合规 flag.

    只读消费 events（不写 events.jsonl、不碰状态机；callee 约束）。打印 audit_summary
    JSON 供 cqo-orchestrator agent 在其上做语义去重 + 研判 + 写报告/回函。
    """
    from ieidev_core import events, cqo_audit
    evs = events.read_events(args.workspace, args.slug)
    summary = cqo_audit.audit_summary(evs, threshold=args.threshold)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_dispatch_start(args):
    from ieidev_core import events
    e = events.dispatch_event(
        phase="start", slug=args.slug, flow=args.flow, emp=args.emp,
        dispatch_id=args.dispatch_id, stage_index=args.stage_index,
        handoff_from=args.handoff_from)
    events.append_event(args.workspace, args.slug, e)
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


def cmd_dispatch_done(args):
    from ieidev_core import events
    e = events.dispatch_event(
        phase="done", slug=args.slug, flow=args.flow, emp=args.emp,
        dispatch_id=args.dispatch_id, status=args.status,
        subagent_tokens=args.subagent_tokens, tool_uses=args.tool_uses,
        duration_s=args.duration_s)
    events.append_event(args.workspace, args.slug, e)
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


def cmd_handoff_path(args):
    p = flow_state.handoff_dir(args.workspace, args.slug, args.employee)
    print(str(p))
    return 0


def cmd_handoff_write(args):
    gi = None
    if args.gate_input:
        try:
            gi = json.loads(args.gate_input)
        except json.JSONDecodeError as exc:
            snippet = args.gate_input[:60]
            raise ValueError(
                f"--gate-input 须合法 JSON，解析失败（{exc}）；实收：{snippet!r}"
            ) from exc
    p = flow_state.write_handoff_status(
        args.workspace, args.slug, args.employee, args.node, args.status,
        args.summary, artifacts=args.artifact, gate_input=gi, reason=args.reason)
    print(str(p))
    return 0


def cmd_handoff_read(args):
    data = flow_state.read_handoff_status(
        args.workspace, args.slug, args.employee, args.node)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_migrate(args):
    from ieidev_core import migrate
    report = migrate.migrate_workspace(args.workspace, dry_run=args.dry_run,
                                        remove_old=args.remove_old)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_next_step(args):
    table, gate_specs = _load_table(args.table)
    state = flow_state.read_state(args.workspace, args.flow, args.slug)
    result = node_machine.get_next_actions(state, table, gate_specs)
    # Enrich with display-level info
    nodes = table["nodes"]
    current = result.get("current_node")
    node_info = nodes.get(current) if current else None
    result["node_kind"] = node_info["kind"] if node_info else result.get("node_kind")
    result["node_name"] = node_info["name"] if node_info else result.get("node_name")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_gate_lookup(args):
    table, gate_specs = _load_table(args.table)
    state = flow_state.read_state(args.workspace, args.flow, args.slug)
    current = state.get("current_node")
    nodes = table["nodes"]
    node_info = nodes.get(current) if current else None
    if not node_info:
        print(json.dumps({"error": f"unknown node {current!r}"}, indent=2))
        return 1
    gate_id = node_info.get("gate")
    if not gate_id:
        print(json.dumps({"error": f"node {current!r} is not a gate"}, indent=2))
        return 1
    spec = gate_specs.get(gate_id)
    if not spec:
        print(json.dumps({"error": f"gate {gate_id!r} not found in specs"}, indent=2))
        return 1
    result = dict(spec)
    result["gate"] = gate_id
    result["current_iter"] = state.get("gate_iters", {}).get(gate_id, 0)
    result["max_retries"] = table.get("max_retries", node_machine.DEFAULT_MAX_RETRIES)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_unblock(args):
    to_node = getattr(args, "to_node", None)
    state = flow_state.unblock_state(args.workspace, args.flow, args.slug,
                                    to_node=to_node)
    _print_state(state, args.workspace)
    return 0


def cmd_list_flows(args):
    """[兼容别名] list-flows → list_features."""
    print(json.dumps(flow_state.list_features(args.workspace),
                     ensure_ascii=False, indent=2))
    return 0


def cmd_pause_gate(args):
    from ieidev_core import gate_pause
    gate_pause.write_pause(args.workspace, args.slug, args.gate, reason=args.reason or "")
    print(json.dumps({"paused": args.gate}, ensure_ascii=False))
    return 0


def cmd_confirm_gate(args):
    from ieidev_core import gate_pause
    gate_pause.clear_pause(args.workspace, args.slug, args.gate)
    print(json.dumps({"confirmed": args.gate,
                      "still_paused": gate_pause.active_pauses(args.workspace, args.slug)},
                     ensure_ascii=False))
    return 0


def _common(sub, name):
    """A subparser with the shared --workspace + flow/slug positionals."""
    sp = sub.add_parser(name)
    sp.add_argument("flow")
    sp.add_argument("slug")
    sp.add_argument("--workspace", default=".", help="workspace root (default: cwd)")
    return sp


def build_parser():
    p = argparse.ArgumentParser(prog="ieidev_core",
                                description="Drive a flow's R1/R2/R3 engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = _common(sub, "show")
    ps.set_defaults(func=cmd_show)

    pi = _common(sub, "init")
    pi.add_argument("--display-name", required=True)
    pi.add_argument("--review-mode", default="ai", choices=["ai", "both", "human"])
    pi.add_argument("--auto-mode", action="store_true")
    pi.add_argument("--initial-node", default=None)
    pi.add_argument("--origin", default=None)
    pi.add_argument("--relates-to", default=None)
    pi.set_defaults(func=cmd_init)

    pr = _common(sub, "resume")
    pr.set_defaults(func=cmd_resume)

    pa = _common(sub, "advance")
    pa.add_argument("to_node")
    pa.add_argument("--table", required=True)
    pa.add_argument("--reflow", action="store_true")
    pa.add_argument("--reason", default=None)
    pa.set_defaults(func=cmd_advance)

    pg = _common(sub, "record-gate")
    pg.add_argument("--table", required=True)
    pg.add_argument("--gate", required=True)
    pg.add_argument("--kind", required=True,
                    choices=["review", "decision", "acceptance"])
    pg.add_argument("--verdict", required=True)
    pg.add_argument("--node", default=None)
    pg.add_argument("--request-id", required=True)
    pg.add_argument("--by", default="ai")
    pg.add_argument("--iter", type=int, default=1)
    pg.add_argument("--issues", action="append")
    pg.set_defaults(func=cmd_record_gate)

    pc = _common(sub, "complete")
    pc.add_argument("--status", default="completed",
                    choices=["completed", "aborted"])
    pc.set_defaults(func=cmd_complete)

    pn = _common(sub, "next-step")
    pn.add_argument("--table", required=True)
    pn.set_defaults(func=cmd_next_step)

    pg_lk = _common(sub, "gate-lookup")
    pg_lk.add_argument("--table", required=True)
    pg_lk.set_defaults(func=cmd_gate_lookup)

    pu = _common(sub, "unblock")
    pu.add_argument("--to-node", default=None,
                    help="node to move current_node to after unblocking")
    pu.set_defaults(func=cmd_unblock)

    plf = sub.add_parser("list-flows")
    plf.add_argument("--workspace", default=".", help="workspace root (default: cwd)")
    plf.set_defaults(func=cmd_list_flows)

    psr = _common(sub, "start-run")
    psr.add_argument("--initial-node", default=None)
    psr.add_argument("--review-mode", default="ai", choices=["ai", "both", "human"])
    psr.add_argument("--auto-mode", action="store_true")
    psr.set_defaults(func=cmd_start_run)

    pas = _common(sub, "add-story")
    pas.add_argument("--id", required=True)
    pas.add_argument("--title", required=True)
    pas.add_argument("--status", default="pending",
                     choices=["pending", "in_progress", "done"])
    pas.set_defaults(func=cmd_add_story)

    pss = _common(sub, "set-story-status")
    pss.add_argument("--id", required=True)
    pss.add_argument("--status", required=True,
                     choices=["pending", "in_progress", "done"])
    pss.set_defaults(func=cmd_set_story_status)

    pcf = _common(sub, "close-feature")
    pcf.add_argument("--status", default="completed",
                     choices=["completed", "aborted"])
    pcf.set_defaults(func=cmd_close_feature)

    pev = _common(sub, "events")
    pev.set_defaults(func=cmd_events)

    pca = _common(sub, "cqo-audit")
    pca.add_argument("--threshold", type=int,
                     default=cqo_audit.DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
                     help="circuit-breaker FAIL 触顶阈值（默认 3，来自 cqo_supervision config 骨架）")
    pca.set_defaults(func=cmd_cqo_audit)

    pds = _common(sub, "dispatch-start")
    pds.add_argument("--emp", required=True)
    pds.add_argument("--dispatch-id", required=True, dest="dispatch_id")
    pds.add_argument("--stage-index", type=int, default=None, dest="stage_index")
    pds.add_argument("--handoff-from", default=None, dest="handoff_from")
    pds.set_defaults(func=cmd_dispatch_start)

    pdd = _common(sub, "dispatch-done")
    pdd.add_argument("--emp", required=True)
    pdd.add_argument("--dispatch-id", required=True, dest="dispatch_id")
    pdd.add_argument("--status", default="done", choices=["done", "blocked"])
    pdd.add_argument("--subagent-tokens", type=int, default=None, dest="subagent_tokens")
    pdd.add_argument("--tool-uses", type=int, default=None, dest="tool_uses")
    pdd.add_argument("--duration-s", type=int, default=None, dest="duration_s")
    pdd.set_defaults(func=cmd_dispatch_done)

    php = _common(sub, "handoff-path")
    php.add_argument("--employee", required=True)
    php.set_defaults(func=cmd_handoff_path)

    phw = _common(sub, "handoff-write")
    phw.add_argument("--employee", required=True)
    phw.add_argument("--node", required=True)
    phw.add_argument("--status", required=True,
                     choices=["done", "blocked", "needs_context"])
    phw.add_argument("--summary", required=True)
    phw.add_argument("--artifact", action="append", default=[])
    phw.add_argument("--gate-input", default=None, dest="gate_input")
    phw.add_argument("--reason", default=None)
    phw.set_defaults(func=cmd_handoff_write)

    phr = _common(sub, "handoff-read")
    phr.add_argument("--employee", required=True)
    phr.add_argument("--node", required=True)
    phr.set_defaults(func=cmd_handoff_read)

    plf2 = sub.add_parser("list-features")
    plf2.add_argument("--workspace", default=".",
                      help="workspace root (default: cwd)")
    plf2.set_defaults(func=cmd_list_features)

    pmg = sub.add_parser("migrate")
    pmg.add_argument("--workspace", default=".",
                     help="workspace root (default: cwd)")
    pmg.add_argument("--dry-run", action="store_true")
    pmg.add_argument("--remove-old", action="store_true")
    pmg.set_defaults(func=cmd_migrate)

    ppg = sub.add_parser("pause-gate")
    ppg.add_argument("slug")
    ppg.add_argument("gate")
    ppg.add_argument("--workspace", default=".", help="workspace root")
    ppg.add_argument("--reason", default=None)
    ppg.set_defaults(func=cmd_pause_gate)

    pcg = sub.add_parser("confirm-gate")
    pcg.add_argument("slug")
    pcg.add_argument("gate")
    pcg.add_argument("--workspace", default=".", help="workspace root")
    pcg.set_defaults(func=cmd_confirm_gate)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (flow_state.FlowStateError, node_machine.NodeMachineError,
            gate.GateError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
