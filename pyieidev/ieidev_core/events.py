# ieidev_core/events.py
"""kdev-core R1 — events.jsonl append-only stream (事实流水通道).

控制态小而热（flow-state.json 的 active{}），流水长而冷（这里）。每行一个 JSON
对象、append-only、自带 actor + slug/flow/run（去归一化，HUD 扫 events 不用回查）。

两类事件（P-Core-FF 范围）+ dispatch：
  - transition：R2 流转（来自 phase_history 条目），actor="system"
  - gate：R3 关卡判定（来自 GateResult），actor=GateResult.by
  - dispatch：CEO 总编排派单/回填（start 派单 + done 回填 usage），actor="ceo"
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def _events_path(workspace, slug) -> Path:
    return Path(workspace) / ".ieidev" / "features" / slug / "events.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_event(workspace, slug, event) -> None:
    """Append one event dict as a JSON line. Injects ts if absent. Creates file/dir."""
    path = _events_path(workspace, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(event)
    rec.setdefault("ts", _now_iso())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_events(workspace, slug) -> list:
    """Read all event lines (oldest first). Missing file -> []. Skips blank/corrupt lines."""
    path = _events_path(workspace, slug)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def transition_event(*, slug, flow, run, entry) -> dict:
    """Build a transition event line from an R2 phase_history entry."""
    return {
        "ts": entry.get("entered_at") or _now_iso(),
        "type": "transition",
        "actor": "system",
        "slug": slug,
        "flow": flow,
        "run": run,
        "from": entry.get("from"),
        "to": entry.get("to"),
        "reflow": bool(entry.get("reflow", False)),
        "forced_fail": bool(entry.get("forced_fail", False)),
        "reason": entry.get("reason"),
    }


def gate_event(*, slug, flow, run, gate_result) -> dict:
    """Build a gate event line from an R3 GateResult dict."""
    gr = gate_result
    return {
        "ts": gr.get("ts") or _now_iso(),
        "type": "gate",
        "actor": gr.get("by"),
        "slug": slug,
        "flow": flow,
        "run": run,
        "gate": gr.get("gate"),
        "kind": gr.get("kind"),
        "node": gr.get("node"),
        "verdict": gr.get("verdict"),
        "iter": gr.get("iter"),
        "by": gr.get("by"),
        "request_id": gr.get("request_id"),
        "issues": list(gr.get("issues", [])),
        "revisions": list(gr.get("revisions", [])),
    }


def dispatch_event(*, phase, slug, flow, emp, dispatch_id,
                   stage_index=None, handoff_from=None, status=None,
                   subagent_tokens=None, tool_uses=None, duration_s=None,
                   actor="ceo") -> dict:
    """Build a dispatch event line (CEO 派单/回填).

    phase="start"：派单时写（stage_index / handoff_from）。
    phase="done"：完成时**追加**回填（status + 可空 usage：subagent_tokens/tool_uses/duration_s）。
    events.jsonl append-only —— done 不改写 start，靠 dispatch_id 配对。
    """
    return {
        "ts": _now_iso(),
        "type": "dispatch",
        "phase": phase,
        "actor": actor,
        "slug": slug,
        "flow": flow,
        "emp": emp,
        "dispatch_id": dispatch_id,
        "stage_index": stage_index,
        "handoff_from": handoff_from,
        "status": status,
        "subagent_tokens": subagent_tokens,
        "tool_uses": tool_uses,
        "duration_s": duration_s,
    }
