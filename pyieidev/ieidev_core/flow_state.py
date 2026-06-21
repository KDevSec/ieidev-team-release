"""kdev-core R1 — feature-first flow-state store (适配层).

磁盘：.ieidev/features/<slug>/flow-state.json（嵌套：台账 runs[]+stories[]+单棒 active{}）
      + 同目录 events.jsonl（流水，见 ieidev_core.events）。
内存：read_state 返回扁平视图（控制态在顶层），R2/R3 纯函数不变地读写它。

适配层不变量：所有持久化都是 read→单次 op→write。read_state 永远返回
history=[]/phase_history=[]（增量模型）；write_state 把内存里这两个列表当本次新增、
虹吸进 events.jsonl，绝不存进 flow-state.json。

两级 status：磁盘顶层 status=feature 级；active.status=run 级。
内存扁平 status ⟷ active.status（R3 写 blocked 落 run）；内存 feature_status ⟷ 顶层 status。
active 是对象或 null（无在跑棒次时 null）——布尔 stale-guard 已废弃，可续 = active 非 null 且 active.status==in_progress。
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ieidev_core import events as _events

VALID_REVIEW_MODES = {"ai", "both", "human"}

class FlowStateError(Exception):
    """Raised when flow-state.json is missing, corrupt, or in an invalid state."""


def _feature_dir(workspace, slug) -> Path:
    return Path(workspace) / ".ieidev" / "features" / slug


def _state_path(workspace, slug) -> Path:
    return _feature_dir(workspace, slug) / "flow-state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_state(workspace, flow, slug, *, display_name,
               review_mode="ai", auto_mode=False, initial_node=None,
               origin=None, relates_to=None):
    """立项：建 features/<slug>/flow-state.json，run 1 进 active{}。slug 仍调用方直传(v0.1)。"""
    if review_mode not in VALID_REVIEW_MODES:
        raise ValueError(
            f"review_mode must be one of {sorted(VALID_REVIEW_MODES)}, got {review_mode!r}"
        )
    path = _state_path(workspace, slug)
    if path.exists():
        raise FlowStateError(
            f"flow-state.json already exists for feature {slug!r}; resume or pick a different slug"
        )
    now = _now_iso()
    doc = {
        "slug": slug,
        "display_name": display_name,
        "origin": origin,
        "relates_to": relates_to,
        "status": "in_progress",
        "stories": [],
        "runs": [],
        "active": {
            "flow": flow,
            "run": 1,
            "current_node": initial_node,
            "status": "in_progress",
            "gate_iters": {},
            "gate_calls": 0,
            "retries": {},
            "blocked_reason": None,
            "config": {"review_mode": review_mode, "auto_mode": auto_mode},
            "started_at": now,
        },
        "created_at": now,
        "updated_at": now,
    }
    _write_doc(workspace, slug, doc)
    return read_state(workspace, slug=slug)


def _flatten(doc) -> dict:
    """嵌套磁盘 doc -> 扁平内存视图（R2/R3 看到的）。history/phase_history 永远 []。"""
    active = doc.get("active")
    flat = {
        # feature 台账（透传）
        "slug": doc.get("slug"),
        "display_name": doc.get("display_name"),
        "origin": doc.get("origin"),
        "relates_to": doc.get("relates_to"),
        "feature_status": doc.get("status"),
        "stories": doc.get("stories", []),
        "runs": doc.get("runs", []),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        # 增量模型
        "history": [],
        "phase_history": [],
    }
    if active is not None:
        flat.update({
            "flow": active.get("flow"),
            "run": active.get("run"),
            "current_node": active.get("current_node"),
            "status": active.get("status"),
            "gate_iters": dict(active.get("gate_iters", {})),
            "gate_calls": active.get("gate_calls", 0),
            "retries": dict(active.get("retries", {})),
            "blocked_reason": active.get("blocked_reason"),
            "config": active.get("config"),
            "_has_active": True,
            "_active_started_at": active.get("started_at"),
        })
    else:
        flat.update({
            "flow": None, "run": None, "current_node": None, "status": None,
            "gate_iters": {}, "gate_calls": 0, "retries": {}, "blocked_reason": None,
            "config": None, "_has_active": False, "_active_started_at": None,
        })
    return flat


def read_state(workspace, flow=None, slug=None):
    """读 feature 状态，返回扁平视图。flow 形参兼容旧签名(忽略)，slug 必给。"""
    if slug is None:  # 兼容 read_state(ws, flow, slug) 旧位置参数
        slug = flow
    path = _state_path(workspace, slug)
    if not path.exists():
        raise FlowStateError(f"no flow-state.json at {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FlowStateError(f"corrupt flow-state.json at {path}: {exc}") from exc
    doc.pop("_meta", None)
    return _flatten(doc)


def _rebuild_doc(slug, flat) -> dict:
    """扁平内存视图 -> 嵌套磁盘 doc（不含 _meta；事件虹吸由 write_state 负责）。"""
    if flat.get("_has_active"):
        active = {
            "flow": flat.get("flow"),
            "run": flat.get("run"),
            "current_node": flat.get("current_node"),
            "status": flat.get("status"),
            "gate_iters": dict(flat.get("gate_iters", {})),
            "gate_calls": flat.get("gate_calls", 0),
            "retries": dict(flat.get("retries", {})),
            "blocked_reason": flat.get("blocked_reason"),
            "config": flat.get("config"),
            "started_at": flat.get("_active_started_at"),
        }
    else:
        active = None
    return {
        "slug": flat.get("slug") or slug,
        "display_name": flat.get("display_name"),
        "origin": flat.get("origin"),
        "relates_to": flat.get("relates_to"),
        "status": flat.get("feature_status", "in_progress"),
        "stories": flat.get("stories", []),
        "runs": flat.get("runs", []),
        "active": active,
        "created_at": flat.get("created_at") or _now_iso(),
    }


def _write_doc(workspace, slug, doc, *, step_id=None) -> None:
    """原子写一个完整嵌套 doc（注入 updated_at + _meta）。内部用，不做事件虹吸。"""
    path = _state_path(workspace, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    to_write = {k: v for k, v in doc.items() if k != "_meta"}
    to_write["updated_at"] = _now_iso()
    to_write["_meta"] = {"written_at": _now_iso(), "step_id": step_id}
    fd, tmp_path = tempfile.mkstemp(prefix=".flow-state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(to_write, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def write_state(workspace, flow=None, slug=None, state=None, *, step_id=None):
    """写扁平 state：重建嵌套 doc + 虹吸 history/phase_history 增量进 events.jsonl。

    兼容旧位置签名 write_state(ws, flow, slug, state)。新式可 write_state(ws, slug=..., state=...)。
    """
    if state is None:
        raise ValueError("write_state requires a state dict")
    if slug is None:
        slug = state.get("slug") or flow
    flat = state
    flow_id = flat.get("flow")
    run_id = flat.get("run")
    # 1. 虹吸增量 → events.jsonl（先盘后状态文件：事件丢一行可容忍，状态文件是真相源）
    for entry in flat.get("phase_history", []) or []:
        _events.append_event(workspace, slug,
                             _events.transition_event(slug=slug, flow=flow_id, run=run_id, entry=entry))
    for gr in flat.get("history", []) or []:
        _events.append_event(workspace, slug,
                             _events.gate_event(slug=slug, flow=flow_id, run=run_id, gate_result=gr))
    # 2. 重建嵌套 doc 并原子写
    doc = _rebuild_doc(slug, flat)
    _write_doc(workspace, slug, doc, step_id=step_id)


def mark_inactive(workspace, flow, slug=None, *, status="aborted", step_id=None):
    """[兼容旧 API] 终结当前在跑棒次：等价 complete_run。fold active→runs[] + 清空 active。

    旧语义是 active=False + 顶层 status。新语义：run 级终态 + 折叠台账；feature 级 status
    一并置为给定的终态（completed 或 aborted）。
    """
    if slug is None:
        slug = flow
    if status not in {"completed", "aborted"}:
        raise ValueError(
            f"mark_inactive status must be 'completed' or 'aborted', got {status!r}"
        )
    return complete_run(workspace, slug, status=status, close_feature=True, step_id=step_id)


def resume_state(workspace, flow, slug=None):
    """可续 = active 非 null 且 active.status == in_progress（布尔 stale-guard 已废弃）。"""
    if slug is None:
        slug = flow
    state = read_state(workspace, slug=slug)
    if not state["_has_active"] or state["status"] != "in_progress":
        raise FlowStateError(
            f"feature {slug!r} not resumable: no active run in_progress "
            f"(active={state['_has_active']}, run_status={state['status']!r})"
        )
    return state


def unblock_state(workspace, flow, slug=None, *, to_node=None):
    """清 blocked：active.status 回 in_progress，清 blocked_reason，可选移 current_node。"""
    if slug is None:
        slug = flow
    state = read_state(workspace, slug=slug)
    if not state["_has_active"] or state["status"] != "blocked":
        raise FlowStateError(
            f"feature {slug!r} active run is not blocked (status={state['status']!r})"
        )
    state["status"] = "in_progress"
    state["blocked_reason"] = None
    if to_node is not None:
        state["current_node"] = to_node
    write_state(workspace, flow, slug=slug, state=state)
    return read_state(workspace, slug=slug)


def list_flows(workspace):
    """[兼容别名] = list_features。"""
    return list_features(workspace)


def list_features(workspace):
    """扫 .ieidev/features/*/flow-state.json，返回每 feature 概要（HUD 多功能队列用）。"""
    features_dir = Path(workspace) / ".ieidev" / "features"
    if not features_dir.exists():
        return []
    result = []
    for feat_dir in sorted(features_dir.iterdir()):
        state_path = feat_dir / "flow-state.json"
        if not state_path.exists():
            continue
        try:
            doc = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        doc.pop("_meta", None)
        active = doc.get("active")
        stories = doc.get("stories", [])
        done = sum(1 for s in stories if s.get("status") == "done")
        result.append({
            "slug": doc.get("slug"),
            "display_name": doc.get("display_name"),
            "feature_status": doc.get("status"),
            "active_flow": active.get("flow") if active else None,
            "active_node": active.get("current_node") if active else None,
            "active_run": active.get("run") if active else None,
            "runs_count": len(doc.get("runs", [])),
            "stories_done": done,
            "stories_total": len(stories),
        })
    return result


_VALID_STORY_STATUSES = {"pending", "in_progress", "done"}


def add_story(workspace, slug, *, story_id, title, status="pending", step_id=None):
    """追加一个用户故事到 stories[]（feature 级，HUD 完成度分母）。id 不可重复。"""
    if status not in _VALID_STORY_STATUSES:
        raise ValueError(f"story status must be one of {sorted(_VALID_STORY_STATUSES)}, got {status!r}")
    state = read_state(workspace, slug=slug)
    if any(s.get("id") == story_id for s in state.get("stories", [])):
        raise FlowStateError(f"story {story_id!r} already exists in feature {slug!r}")
    state["stories"] = [*state.get("stories", []),
                        {"id": story_id, "title": title, "status": status}]
    write_state(workspace, None, slug=slug, state=state, step_id=step_id)
    return read_state(workspace, slug=slug)


def set_story_status(workspace, slug, *, story_id, status, step_id=None):
    """更新某用户故事状态（HUD 完成度分子）。"""
    if status not in _VALID_STORY_STATUSES:
        raise ValueError(f"story status must be one of {sorted(_VALID_STORY_STATUSES)}, got {status!r}")
    state = read_state(workspace, slug=slug)
    stories = [dict(s) for s in state.get("stories", [])]
    for s in stories:
        if s.get("id") == story_id:
            s["status"] = status
            break
    else:
        raise FlowStateError(f"no story {story_id!r} in feature {slug!r}")
    state["stories"] = stories
    write_state(workspace, None, slug=slug, state=state, step_id=step_id)
    return read_state(workspace, slug=slug)


def complete_run(workspace, slug, *, status="completed", close_feature=False, step_id=None):
    """终结当前在跑棒次：fold active → runs[] 一行摘要 + 清空 active。Q3: 默认不动 feature 级。"""
    if status not in {"completed", "aborted"}:
        raise ValueError(f"complete_run status must be completed|aborted, got {status!r}")
    state = read_state(workspace, slug=slug)
    if not state["_has_active"]:
        raise FlowStateError(f"feature {slug!r} has no active run to complete")
    run_summary = {
        "flow": state["flow"],
        "run": state["run"],
        "status": status,
        "final_node": state["current_node"],
        "ended_at": _now_iso(),
    }
    state["runs"] = [*state.get("runs", []), run_summary]
    state["_has_active"] = False
    if close_feature:
        state["feature_status"] = status
    write_state(workspace, None, slug=slug, state=state, step_id=step_id)
    return read_state(workspace, slug=slug)


def start_run(workspace, flow, slug, *, initial_node=None,
              review_mode="ai", auto_mode=False, step_id=None):
    """补活：feature 已存在且无在跑棒次时，开新 run 填 active（run 号自增）。单棒约束。"""
    if review_mode not in VALID_REVIEW_MODES:
        raise ValueError(f"review_mode must be one of {sorted(VALID_REVIEW_MODES)}, got {review_mode!r}")
    state = read_state(workspace, slug=slug)  # 不存在 → FlowStateError(no flow-state.json)
    if state["_has_active"]:
        raise FlowStateError(
            f"feature {slug!r} already has an active run (run {state['run']}); "
            f"complete it before starting a new one (单棒约束)"
        )
    next_run = max((r.get("run", 0) for r in state.get("runs", [])), default=0) + 1
    state["_has_active"] = True
    state["_active_started_at"] = _now_iso()
    state["flow"] = flow
    state["run"] = next_run
    state["current_node"] = initial_node
    state["status"] = "in_progress"
    state["gate_iters"] = {}
    state["gate_calls"] = 0
    state["retries"] = {}
    state["blocked_reason"] = None
    state["config"] = {"review_mode": review_mode, "auto_mode": auto_mode}
    if state.get("feature_status") in {"completed", "aborted"}:
        state["feature_status"] = "in_progress"  # 补活重开
    write_state(workspace, flow, slug=slug, state=state, step_id=step_id)
    return read_state(workspace, slug=slug)


def close_feature(workspace, slug, *, status="completed", step_id=None):
    """显式收口 feature 级 status（无在跑棒次时才允许）。"""
    if status not in {"completed", "aborted"}:
        raise ValueError(f"close_feature status must be completed|aborted, got {status!r}")
    state = read_state(workspace, slug=slug)
    if state["_has_active"]:
        raise FlowStateError(
            f"feature {slug!r} has an active run; complete it before closing the feature"
        )
    state["feature_status"] = status
    write_state(workspace, None, slug=slug, state=state, step_id=step_id)
    return read_state(workspace, slug=slug)


def handoff_dir(workspace, slug, employee):
    """返回（并 mkdir -p）.ieidev/features/<slug>/handoffs/<employee>/。

    最小约定：只生成目录路径，内容由员工填、handoff 协议留 P-B。
    """
    p = _feature_dir(workspace, slug) / "handoffs" / employee
    p.mkdir(parents=True, exist_ok=True)
    return p


HANDOFF_STATUSES = ("done", "blocked", "needs_context")


def _handoff_status_path(workspace, slug, employee, node_id) -> Path:
    return _feature_dir(workspace, slug) / "handoffs" / employee / f"{node_id}.handoff.json"


def write_handoff_status(workspace, slug, employee, node_id, status, summary,
                         artifacts=None, gate_input=None, reason=None):
    """落一份结构化交接状态到 handoffs/<employee>/<node_id>.handoff.json。

    业务 agent 收尾调它（经 CLI），主循环靠 read_handoff_status 读，
    替代把大段 result 回灌主会话（B 轨压刷屏核心）。返回写入的 Path。
    """
    if status not in HANDOFF_STATUSES:
        raise FlowStateError(
            f"invalid handoff status {status!r}; "
            f"must be one of {', '.join(HANDOFF_STATUSES)}")
    if not node_id:
        raise FlowStateError("node_id required")
    if not summary:
        raise FlowStateError("summary required (one-line human signal)")
    if status != "done" and not reason:
        raise FlowStateError(f"reason required when status={status!r}")
    handoff_dir(workspace, slug, employee)  # mkdir -p（幂等）
    path = _handoff_status_path(workspace, slug, employee, node_id)
    payload = {
        "node_id": node_id,
        "employee": employee,
        "status": status,
        "summary": summary,
        "artifacts": list(artifacts or []),
        "gate_input": gate_input,
        "reason": reason,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def read_handoff_status(workspace, slug, employee, node_id):
    """读 + 校验交接状态文件，返回 dict。

    缺文件/坏 JSON/缺必填键 → FlowStateError，让"后台 agent 没写/写坏"
    显式冒泡（主循环当作该节点未完成），不静默当成功。
    """
    path = _handoff_status_path(workspace, slug, employee, node_id)
    if not path.exists():
        raise FlowStateError(f"handoff status not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise FlowStateError(f"handoff status unreadable: {path}: {exc}") from exc
    for key in ("node_id", "employee", "status", "summary"):
        if key not in data:
            raise FlowStateError(f"handoff status missing required key {key!r}: {path}")
    if data["status"] not in HANDOFF_STATUSES:
        raise FlowStateError(
            f"handoff status invalid status {data['status']!r} "
            f"(must be one of {', '.join(HANDOFF_STATUSES)}): {path}")
    return data
