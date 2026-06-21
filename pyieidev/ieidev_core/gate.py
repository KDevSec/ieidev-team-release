"""kdev-core R3 — three-kind gate (GateResult + record_gate).

Builds on R1 (flow_state.history) + R2 (node_machine.advance). A GateResult is the
structured verdict a flow feeds back after running a gate; record_gate appends it to
state["history"], bumps the double counters, and applies the resulting transition via
R2 advance.

Three gate kinds:
  - review / acceptance: verdict PASS|FAIL.
        PASS               -> advance(on_pass), reset that gate's iter
        FAIL, iter < max   -> advance(on_reflow)              [redo]
        FAIL, iter >= max  -> escalate: status="blocked", NO advance, NO force-accept
  - decision: verdict is a branch key -> advance(branches[verdict])

Gate semantics ride in a separate `gate_specs` arg (R2's node_machine is untouched):
  gate_specs = {
    "g-code":  {"kind": "review",     "on_pass": "n-next", "on_reflow": "n-tdd"},
    "g-e2e":   {"kind": "acceptance", "on_pass": "n-ship", "on_reflow": "n-fix"},
    "g-route": {"kind": "decision",   "branches": {"go": "n-go", "rework": "n-plan"}},
  }
All transition targets are still validated by R2 adjacency (advance raises on illegal edges).

[OMC] structured verdict (no regex); escalate never force-accepts. request_id is recorded
for traceability; full open/approval LOCK enforcement is deferred.
"""
from datetime import datetime, timezone

from ieidev_core.node_machine import advance

GATE_KINDS = {"review", "decision", "acceptance"}
GATE_VERDICTS = {"PASS", "FAIL"}  # review/acceptance; decision uses branch keys


class GateError(Exception):
    """Malformed GateResult, unknown gate spec, or invalid verdict."""


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_gate_result(gate, kind, *, node, verdict, request_id,
                     by="ai", iter=1, issues=None, revisions=None, ts=None):
    """Build + validate a structured GateResult dict."""
    if not gate:
        raise GateError("GateResult requires a non-empty gate id")
    if kind not in GATE_KINDS:
        raise GateError(f"GateResult kind must be one of {sorted(GATE_KINDS)}, got {kind!r}")
    if not request_id:
        raise GateError("GateResult requires a non-empty request_id")
    if kind in ("review", "acceptance") and verdict not in GATE_VERDICTS:
        raise GateError(f"{kind} verdict must be PASS/FAIL, got {verdict!r}")
    return {
        "gate": gate,
        "kind": kind,
        "node": node,
        "request_id": request_id,
        "iter": iter,
        "verdict": verdict,
        "by": by,
        "issues": list(issues or []),
        "revisions": list(revisions or []),
        "ts": ts or _now_iso(),
    }


def record_gate(state, gate_result, *, table, gate_specs, max_retries=None):
    """Record a GateResult and apply the resulting transition. Pure (state -> new state).

    Appends the GateResult to state["history"] (R1's field), bumps the double counters
    (per-gate gate_iters + flow-total gate_calls), then dispatches by the gate's kind:
      review/acceptance: PASS -> advance(on_pass) + reset iter; FAIL within cap ->
        advance(on_reflow); FAIL at/over cap -> escalate (status="blocked", no advance).
      decision: advance(branches[verdict]).
    advance() is always called with reflow=False — R3 owns the review bound via gate_iters,
    distinct from R2's mechanical reflow->terminal_fail.
    """
    gid = gate_result["gate"]
    spec = gate_specs.get(gid)
    if spec is None:
        raise GateError(f"no gate spec for gate {gid!r}")
    kind = spec["kind"]
    cap = max_retries if max_retries is not None else table["max_retries"]

    new = dict(state)
    new["history"] = [*state.get("history", []), gate_result]
    new["gate_calls"] = state.get("gate_calls", 0) + 1
    gate_iters = dict(state.get("gate_iters", {}))

    verdict = gate_result["verdict"]

    if kind in ("review", "acceptance"):
        if verdict == "PASS":
            gate_iters[gid] = 0
            new["gate_iters"] = gate_iters
            return advance(new, spec["on_pass"], table=table, reason=f"{gid} PASS")
        if verdict == "FAIL":
            gate_iters[gid] = gate_iters.get(gid, 0) + 1
            new["gate_iters"] = gate_iters
            if gate_iters[gid] >= cap:
                new["status"] = "blocked"
                new["blocked_reason"] = (
                    f"{gid} failed {gate_iters[gid]}x (>= {cap}); escalate to human"
                )
                return new
            return advance(new, spec["on_reflow"], table=table,
                           reason=f"{gid} FAIL reflow#{gate_iters[gid]}")
        raise GateError(f"{kind} verdict must be PASS/FAIL, got {verdict!r}")

    if kind == "decision":
        branches = spec.get("branches", {})
        if verdict not in branches:
            raise GateError(f"decision {gid!r} verdict {verdict!r} not in branches {sorted(branches)}")
        new["gate_iters"] = gate_iters
        return advance(new, branches[verdict], table=table, reason=f"{gid} decision={verdict}")

    raise GateError(f"unknown gate kind {kind!r} for gate {gid!r}")


def record_gate_persist(workspace, flow, slug, gate_result, *, table, gate_specs,
                        max_retries=None, step_id=None):
    """record_gate() + persist via R1 flow_state.write_state. Returns the persisted state."""
    from ieidev_core import flow_state

    state = flow_state.read_state(workspace, flow, slug)
    new_state = record_gate(state, gate_result, table=table, gate_specs=gate_specs,
                            max_retries=max_retries)
    flow_state.write_state(workspace, flow, slug, new_state, step_id=step_id)
    return flow_state.read_state(workspace, flow, slug)
