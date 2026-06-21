"""kdev-core R2 — node machine (node-table + advance: adjacency/guard/bounded-reflow).

Builds on R1 (ieidev_core.flow_state). A node-table is a flow's SOP: nodes + allowed
transitions. `advance` is a PURE function (state dict -> new state dict, or raises);
it does not touch the filesystem. `advance_persist` wraps it with flow_state.write_state.

Borrows OMC Team Pipeline (src/hooks/team-pipeline/transitions.ts): an adjacency map
separated from a guard(state, next)->str|None, plus an immutable update appending a
phase_history entry. Adds bounded reflow (retry++ on a gate->action loop) with a forced
terminal-fail on overflow — the [OMC-avoid] "never loop forever" rule.

R2 adds two state fields: `phase_history` (transition log) and `retries` (per-node reflow
counter). It never touches R1's `history` field (reserved for R3 GateResults).
"""
from datetime import datetime, timezone

NODE_KINDS = {"action", "gate", "terminal"}
DEFAULT_MAX_RETRIES = 3


class NodeMachineError(Exception):
    """Malformed node-table, illegal transition, or guard failure."""


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_node_table(table):
    """Validate + normalize a node-table dict.

    Returns {flow, max_retries, terminal_fail, nodes: {id: node}, adjacency: {id: [next_ids]}}.
    """
    if not isinstance(table, dict) or "nodes" not in table:
        raise NodeMachineError("node-table must be a dict with a 'nodes' list")
    nodes_list = table["nodes"]
    if not isinstance(nodes_list, list) or not nodes_list:
        raise NodeMachineError("node-table 'nodes' must be a non-empty list")

    nodes = {}
    for n in nodes_list:
        nid = n.get("id")
        if not nid:
            raise NodeMachineError(f"node missing 'id': {n!r}")
        if nid in nodes:
            raise NodeMachineError(f"duplicate node id: {nid!r}")
        kind = n.get("kind", "action")
        if kind not in NODE_KINDS:
            raise NodeMachineError(
                f"node {nid!r} has invalid kind {kind!r} (must be one of {sorted(NODE_KINDS)})"
            )
        nxt = n.get("next", [])
        if not isinstance(nxt, list):
            raise NodeMachineError(f"node {nid!r} 'next' must be a list")
        nodes[nid] = {
            "id": nid,
            "name": n.get("name", nid),
            "kind": kind,
            "gate": n.get("gate"),
            "next": list(nxt),
        }

    for nid, n in nodes.items():
        for tgt in n["next"]:
            if tgt not in nodes:
                raise NodeMachineError(f"node {nid!r} points to unknown node {tgt!r}")
        if n["kind"] == "terminal" and n["next"]:
            raise NodeMachineError(
                f"terminal node {nid!r} must have empty 'next', got {n['next']!r}"
            )

    terminal_fail = table.get("terminal_fail")
    if terminal_fail is not None:
        if terminal_fail not in nodes:
            raise NodeMachineError(f"terminal_fail {terminal_fail!r} is not a node")
        if nodes[terminal_fail]["kind"] != "terminal":
            raise NodeMachineError(f"terminal_fail {terminal_fail!r} must be a terminal node")

    max_retries = table.get("max_retries", DEFAULT_MAX_RETRIES)
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
        raise NodeMachineError(f"max_retries must be a non-negative int, got {max_retries!r}")

    return {
        "flow": table.get("flow"),
        "max_retries": max_retries,
        "terminal_fail": terminal_fail,
        "nodes": nodes,
        "adjacency": {nid: list(n["next"]) for nid, n in nodes.items()},
    }


def advance(state, to_node, *, table, guard=None, reflow=False, reason=None):
    """Pure transition: returns a NEW state dict, or raises NodeMachineError.

    Three steps (OMC pattern):
      1. adjacency: to_node must be in adjacency[current_node] (else raise).
      2. guard: if given, guard(state, to_node) -> str|None; non-None -> raise(reason).
      3. immutable update: new current_node + append a phase_history entry.

    Bounded reflow: reflow=True (a gate->action retry) increments retries[to_node];
    if it exceeds table["max_retries"], the transition is forced to table["terminal_fail"]
    (or raises if no terminal_fail is configured). Forward advances (reflow=False) never
    touch the retry counter — the idempotent exemption.
    """
    current = state.get("current_node")
    if current is None:
        raise NodeMachineError("cannot advance: state has no current_node")
    adjacency = table["adjacency"]
    if current not in adjacency:
        raise NodeMachineError(f"current_node {current!r} is not in the node-table")
    if to_node not in adjacency[current]:
        raise NodeMachineError(f"illegal transition: {current!r} -> {to_node!r}")

    if guard is not None:
        greason = guard(state, to_node)
        if greason is not None:
            raise NodeMachineError(f"guard rejected {current!r} -> {to_node!r}: {greason}")

    retries = dict(state.get("retries", {}))
    target = to_node
    forced_fail = False
    if reflow:
        retries[to_node] = retries.get(to_node, 0) + 1
        if retries[to_node] > table["max_retries"]:
            tf = table.get("terminal_fail")
            if tf is None:
                raise NodeMachineError(
                    f"retry overflow at {to_node!r} (> {table['max_retries']}) "
                    f"and no terminal_fail configured"
                )
            target = tf
            forced_fail = True

    new_state = dict(state)
    new_state["current_node"] = target
    new_state["retries"] = retries
    entry = {
        "from": current,
        "to": target,
        "reflow": bool(reflow),
        "forced_fail": forced_fail,
        "reason": reason,
        "entered_at": _now_iso(),
    }
    new_state["phase_history"] = [*state.get("phase_history", []), entry]
    return new_state


def get_next_actions(state, table, gate_specs):
    """Return what the orchestrator should do next at the current node.

    Returns a dict:
      {
        "current_node": str | None,
        "node_kind": str,          # "action"|"gate"|"terminal"|None
        "node_name": str | None,
        "next_actions": [{"to_node": str, "label": str}],
        "gate_spec": dict | None,  # gate_specs entry for the current gate node
        "is_blocked": bool,
        "blocked_reason": str | None,
      }
    """
    current = state.get("current_node")
    nodes = table["nodes"]
    adjacency = table["adjacency"]
    is_blocked = state.get("status") == "blocked"
    blocked_reason = state.get("blocked_reason")

    result = {
        "current_node": current,
        "node_kind": None,
        "node_name": None,
        "next_actions": [],
        "gate_spec": None,
        "is_blocked": is_blocked,
        "blocked_reason": blocked_reason,
    }

    if current is None or current not in nodes:
        # Not yet advanced or unknown node — return bare info
        return result

    node = nodes[current]
    result["node_kind"] = node["kind"]
    result["node_name"] = node["name"]

    # Terminal nodes have no next actions
    if node["kind"] == "terminal":
        return result

    # If blocked, no valid actions until unblocked
    if is_blocked:
        return result

    next_ids = adjacency.get(current, [])
    gate_id = node.get("gate")

    if node["kind"] == "gate" and gate_id and gate_id in gate_specs:
        spec = gate_specs[gate_id]
        # Build gate_spec for orchestrator decision-making
        gs = dict(spec)
        gs["gate"] = gate_id
        gs["current_iter"] = state.get("gate_iters", {}).get(gate_id, 0)
        gs["max_retries"] = table.get("max_retries", DEFAULT_MAX_RETRIES)
        result["gate_spec"] = gs

        # Derive next_actions from gate_spec
        if spec["kind"] == "decision":
            branches = spec.get("branches", {})
            for verdict_key, target in branches.items():
                result["next_actions"].append({"to_node": target, "label": verdict_key})
        elif spec["kind"] in ("review", "acceptance"):
            result["next_actions"].append({"to_node": spec["on_pass"], "label": "PASS"})
            result["next_actions"].append({"to_node": spec["on_reflow"], "label": "FAIL"})
    else:
        # Action node: next_actions from adjacency
        for nid in next_ids:
            target_node = nodes.get(nid)
            label = target_node["name"] if target_node else nid
            result["next_actions"].append({"to_node": nid, "label": label})

    return result


def advance_persist(workspace, flow, slug, to_node, *, table, guard=None,
                    reflow=False, reason=None, step_id=None):
    """advance() + persist via R1 flow_state.write_state. Returns the persisted state."""
    from ieidev_core import flow_state

    state = flow_state.read_state(workspace, flow, slug)
    new_state = advance(state, to_node, table=table, guard=guard, reflow=reflow, reason=reason)
    flow_state.write_state(workspace, flow, slug, new_state, step_id=step_id)
    return flow_state.read_state(workspace, flow, slug)
