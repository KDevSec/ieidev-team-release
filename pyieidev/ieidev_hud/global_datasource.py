"""全局 HUD 数据层 —— 读 registry → 逐项目复用 build_feature_view → 映射成多项目 goal 模型。

零写入、容错降级（坏/缺项目标 stale，绝不崩）。产出 = Plan-2 前端唯一消费的数据契约。
"""
import os
from datetime import datetime

from ieidev_hud import datasource
from ieidev_team import registry as _registry

_GATE_NAME = {
    "g-sr-review": "SR需求评审", "g-ar-proto-review": "用户故事+原型评审",
    "g-design-review": "方案评审", "g-plan-review": "实施计划评审",
    "g-code-review": "代码评审", "g-sec-review": "安全评审",
    "g-test-design-review": "测试设计评审", "g-test-coverage-review": "测试覆盖评审",
}
_ORPHAN_SECONDS = 1800   # running 派单超此无 done → 孤儿 stale

_ROUTE_ST = {"done": "done", "active": "active"}   # roadmap stage status → mockup st


def _ev_kind(e):
    t = e.get("type")
    if t == "gate":
        return f"评审·{e.get('verdict')}"
    if t == "transition":
        return "流转"
    if t == "dispatch":
        return "派单"
    return t or "事件"


def _ev_detail(e):
    t = e.get("type")
    if t == "gate":
        return f"{e.get('gate') or e.get('node')} 第{e.get('iter')}轮 · {e.get('by')} · {len(e.get('issues', []) or [])} issues"
    if t == "transition":
        return f"{e.get('from')} → {e.get('to')}" + ("（回流）" if e.get("reflow") else "")
    if t == "dispatch":
        return f"{e.get('emp')} · {e.get('flow')} · {e.get('phase')}{(' '+str(e.get('status'))) if e.get('status') else ''}"
    return ""


def _parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _elapsed(started_at, now):
    dt = _parse_ts(started_at)
    if dt is None or now is None:
        return ""
    secs = int((now - dt).total_seconds())
    if secs < 0:
        return ""
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def _orphan(started_at, now):
    dt = _parse_ts(started_at)
    if dt is None or now is None:
        return False
    return (now - dt).total_seconds() > _ORPHAN_SECONDS


def _state(fv):
    """active | done（stale 由调用方按 workspace 失联判，这里不判）。"""
    if fv.get("feature_status") == "done":
        return "done"
    rs = (fv.get("roadmap") or {}).get("story_summary") or {}
    if rs.get("total") and rs.get("done") == rs.get("total"):
        return "done"
    return "active"


def build_goal_view(workspace, slug, *, owner, now):
    fv = datasource.build_feature_view(workspace, slug)
    if fv is None:
        return None
    roadmap = fv.get("roadmap") or {}
    route = [{"emp": s.get("display_name") or s.get("emp"),
              "flow": s.get("flow"),
              "st": _ROUTE_ST.get(s.get("status"), "pending")}
             for s in (roadmap.get("stages") or [])]
    active = fv.get("active") or {}
    node = {"flow": active.get("flow"), "current_node": active.get("current_node"),
            "run": active.get("run"), "status": active.get("status")}
    ss = roadmap.get("story_summary") or {}
    items = [{"id": it.get("id"), "title": it.get("title"),
              "status": it.get("status"), "sr": None}        # sr 预留恒 None
             for it in (ss.get("items") or [])]
    # 在跑派单 → emps（running，喂在跑总览）
    emps = []
    for dv in fv.get("dispatches", []):
        if dv.get("running"):
            emps.append({"emp": datasource._EMP_DISPLAY_HUD.get(dv.get("emp"), dv.get("emp")),
                         "st": "running",
                         "elapsed": _elapsed(dv.get("started_at"), now),
                         "stale": _orphan(dv.get("started_at"), now)})
    gates = [{"name": _GATE_NAME.get(g.get("gate"), g.get("gate") or g.get("node")),
              "id": g.get("gate"), "by": g.get("by"), "ts": g.get("ts"),
              "it": g.get("iter"), "v": g.get("verdict"),
              "issues": []}                                  # issues 文本 Plan-2 再接（gate_views 只有 count）
             for g in fv.get("gates", [])]
    return {
        "key": slug, "title": fv.get("display_name") or slug, "slug": slug,
        "owner": owner, "state": _state(fv), "pct": ss.get("pct", 0),
        "route": route, "node": node,
        "worktree": roadmap.get("worktree") or {"intent": None, "concrete": None},
        "emps": emps,
        "stories": {"done": ss.get("done", 0), "total": ss.get("total", 0),
                    "pct": ss.get("pct", 0), "items": items},
        "alerts": [{"crit": a.get("kind") in ("blocked", "gate_fail"),
                    "text": a.get("detail"),
                    "meta": a.get("ts")}
                   for a in fv.get("alerts", [])],
        "gates": gates,
        "events": [{"ts": e.get("ts"), "kind": _ev_kind(e), "detail": _ev_detail(e)}
                   for e in list(reversed(fv.get("events", [])))[:12]],
    }


_ROSTER = ["需求架构师", "开发工程师", "测试工程师", "评审专家"]


def empty_model(scope, *, now):
    """最小合法降级 model —— HUD 铁律：build_*_model 抛错时 render 仍出合法 shell。
    形状与 build_global_model / build_workspace_model 一致，仅内容空。"""
    return {
        "generated_at": now.isoformat(timespec="seconds") if now else None,
        "scope": scope, "roster": _ROSTER,
        "counts": {"projects": 0, "active": 0, "done": 0, "stale": 0},
        "projects": [], "active_dispatches": [],
    }


def _active_dispatches(goals, proj_name):
    """从一组 goal 派生在跑派单行（active + running）。全局/单工作区共用，行为一致。"""
    out = []
    for gv in goals:
        if gv.get("state") != "active":
            continue
        for emp in gv.get("emps", []):
            if emp.get("st") == "running":
                nd = gv.get("node") or {}
                out.append({
                    "key": gv["key"], "goal": gv["title"], "proj": proj_name,
                    "role": emp.get("emp"),
                    "node": f"{nd.get('flow')}·{nd.get('current_node')} 第{nd.get('run')}轮",
                    "elapsed": emp.get("elapsed", ""), "stale": emp.get("stale", False)})
    return out


def _stale_goal(entry):
    """workspace 失联 → 用 registry 留档造一个 stale 占位 goal。"""
    slug = entry.get("slug")
    return {"key": slug, "title": entry.get("display_name") or slug, "slug": slug,
            "owner": entry.get("owner"), "state": "stale", "pct": 0,
            "route": [], "node": {}, "worktree": {"intent": None, "concrete": None},
            "emps": [], "stories": {"done": 0, "total": 0, "pct": 0, "items": []},
            "alerts": [{"crit": False,
                        "text": "workspace 失联 → 标 stale；详情为 registry 最后已知态", "meta": "stale"}],
            "gates": []}


def build_global_model(*, now):
    entries = _registry.read_registry()["entries"]
    by_ws = {}
    for e in entries:
        by_ws.setdefault(e.get("workspace"), []).append(e)
    projects, active_dispatches = [], []
    counts = {"projects": 0, "active": 0, "done": 0, "stale": 0}
    for ws, ents in sorted(by_ws.items()):
        proj_name = os.path.basename(ws.rstrip("/")) if ws else "?"
        goals = []
        for e in ents:
            slug = e.get("slug")
            if not _registry.workspace_exists(e):
                gv = _stale_goal(e)
            else:
                try:
                    gv = build_goal_view(ws, slug, owner=e.get("owner"), now=now)
                except Exception:
                    gv = None
                if gv is None:
                    gv = _stale_goal(e)        # 坏项目同样降级，不崩
            goals.append(gv)
            counts[gv["state"]] = counts.get(gv["state"], 0) + 1
        active_dispatches.extend(_active_dispatches(goals, proj_name))
        projects.append({"name": proj_name, "path": ws, "goals": goals})
    counts["projects"] = len(projects)
    return {
        "generated_at": now.isoformat(timespec="seconds") if now else None,
        "scope": "global", "roster": _ROSTER, "counts": counts,
        "projects": projects, "active_dispatches": active_dispatches,
    }


def build_workspace_model(workspace, *, now):
    """单工作区 model：直接扫该 workspace 所有 slug（不走 registry），包成与
    build_global_model 同形的模型，但 scope="workspace"、projects 恒一项。
    坏/缺 → 降级（goal None → 跳过该 slug；无 slug → goals=[]）。
    """
    owner = _registry.owner_id()
    proj_name = os.path.basename(str(workspace).rstrip("/")) or "?"
    goals = []
    counts = {"projects": 1, "active": 0, "done": 0, "stale": 0}
    for slug in datasource.list_feature_slugs(workspace):
        try:
            gv = build_goal_view(workspace, slug, owner=owner, now=now)
        except Exception:
            gv = None
        if gv is None:
            continue
        goals.append(gv)
        counts[gv["state"]] = counts.get(gv["state"], 0) + 1
    return {
        "generated_at": now.isoformat(timespec="seconds") if now else None,
        "scope": "workspace", "roster": _ROSTER, "counts": counts,
        "projects": [{"name": proj_name, "path": str(workspace), "goals": goals}],
        "active_dispatches": _active_dispatches(goals, proj_name),
    }
