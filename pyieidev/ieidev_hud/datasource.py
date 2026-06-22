"""ieidev-hud 只读数据层 —— 直接读 .ieidev/features/<slug>/ 文件，零写入、零 ieidev_core 依赖。

契约 = 文件格式（见 plan「数据契约」）。运行时不 import ieidev_core：HUD 自包含，
底座可 headless 单装。解析容错：缺失/损坏一律降级（None / [] / 跳过坏行）。
"""
import json
from pathlib import Path

try:
    import yaml as _yaml
except ImportError:        # HUD 自包含：缺 PyYAML 不崩，delivery-plan 视为缺失
    _yaml = None


def _features_dir(workspace) -> Path:
    return Path(workspace) / ".ieidev" / "features"


def _feature_dir(workspace, slug) -> Path:
    return _features_dir(workspace) / slug


def read_flow_state(workspace, slug):
    """读 flow-state.json → dict；缺失或损坏 → None。"""
    path = _feature_dir(workspace, slug) / "flow-state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_events(workspace, slug):
    """读 events.jsonl（oldest first）→ list[dict]；缺失 → []；跳过空行/坏行。"""
    path = _feature_dir(workspace, slug) / "events.jsonl"
    if not path.exists():
        return []
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def list_feature_slugs(workspace):
    """扫 .ieidev/features/*/flow-state.json，返回 slug 列表（按目录名排序）。"""
    fdir = _features_dir(workspace)
    if not fdir.exists():
        return []
    out = []
    for sub in sorted(fdir.iterdir()):
        if (sub / "flow-state.json").exists():
            out.append(sub.name)
    return out


# ---------------------------------------------------------------------------
# Task 4.1: delivery-plan 读取 + dispatch 事件派生
# ---------------------------------------------------------------------------

def _normalize_stage_on(stage):
    """YAML 1.1 把裸 `on:` 键解析成布尔 True（kdev-team 写盘会加引号、但手写/兼容旧文件可能裸写）；
    防御性归一：把 True 键搬回字符串 "on"，使 stage.get("on") 稳定可用。"""
    if isinstance(stage, dict) and True in stage and "on" not in stage:
        stage = dict(stage)
        stage["on"] = stage.pop(True)
    return stage


def read_delivery_plan(workspace, slug):
    """读 features/<slug>/delivery-plan.yml → dict；缺 yaml/缺文件/坏 → None。"""
    if _yaml is None:
        return None
    path = _feature_dir(workspace, slug) / "delivery-plan.yml"
    if not path.exists():
        return None
    try:
        plan = _yaml.safe_load(path.read_text(encoding="utf-8"))
    except (_yaml.YAMLError, OSError):
        return None
    if isinstance(plan, dict) and isinstance(plan.get("stages"), list):
        plan["stages"] = [_normalize_stage_on(s) for s in plan["stages"]]
    return plan


def _dispatch_views(events):
    """dispatch 事件按 dispatch_id 配对 start↔done → 渲染用摘要。"""
    by_id = {}
    order = []
    for e in events:
        if e.get("type") != "dispatch":
            continue
        did = e.get("dispatch_id")
        if did not in by_id:
            by_id[did] = {
                "dispatch_id": did, "emp": e.get("emp"), "flow": e.get("flow"),
                "stage_index": e.get("stage_index"), "status": "running",
                "started_at": None, "done_at": None, "running": True,
                "subagent_tokens": None, "tool_uses": None, "duration_s": None,
            }
            order.append(did)
        v = by_id[did]
        if e.get("phase") == "start":
            v["started_at"] = e.get("ts")
            if e.get("stage_index") is not None:
                v["stage_index"] = e.get("stage_index")
        elif e.get("phase") == "done":
            v["done_at"] = e.get("ts")
            v["status"] = e.get("status") or "done"
            v["running"] = False
            for k in ("subagent_tokens", "tool_uses", "duration_s"):
                if e.get(k) is not None:
                    v[k] = e.get(k)
    return [by_id[d] for d in order]


# ---------------------------------------------------------------------------
# Task 3: derivation layer — build_feature_view
# ---------------------------------------------------------------------------

_EMP_DISPLAY_HUD = {
    "req-architect": "需求架构师",
    "dev-engineer": "开发工程师",
    "test-engineer": "测试工程师",
}


def _roadmap_stage_status_map(dispatches):
    """dispatch view 列表 → {stage_index: "done"|"active"}；无 → key 缺失。"""
    result = {}
    for dv in dispatches:
        si = dv.get("stage_index")
        if si is None:
            continue
        if dv.get("status") == "done":
            result[si] = "done"
        elif dv.get("running") and result.get(si) != "done":
            result[si] = "active"
    return result


def _roadmap_stages(plan, dispatches):
    """delivery-plan on 段 + dispatch 状态 → stages list。"""
    if not plan:
        return []
    on_stages = [s for s in (plan.get("stages") or []) if s.get("on")]
    status_map = _roadmap_stage_status_map(dispatches)
    return [
        {
            "emp": s.get("emp") or "",
            "flow": s.get("flow") or "",
            "display_name": _EMP_DISPLAY_HUD.get(s.get("emp") or "", s.get("emp") or ""),
            "on": True,
            "stage_index": i,
            "status": status_map.get(i, "pending"),
        }
        for i, s in enumerate(on_stages, 1)
    ]


def _completion(stories):
    total = len(stories)
    done = sum(1 for s in stories if s.get("status") == "done")
    pct = round(100 * done / total) if total else 0
    return done, total, pct


def _gate_views(events):
    """events 里的 gate 行 → 渲染用摘要（无 score，FF-3）。"""
    out = []
    for e in events:
        if e.get("type") != "gate":
            continue
        out.append({
            "gate": e.get("gate"), "kind": e.get("kind"), "node": e.get("node"),
            "verdict": e.get("verdict"), "iter": e.get("iter"), "by": e.get("by"),
            "issues_count": len(e.get("issues", []) or []),
            "ts": e.get("ts"),
        })
    return out


def _active_view(doc):
    a = doc.get("active")
    if not a:
        return None
    return {
        "flow": a.get("flow"), "run": a.get("run"),
        "current_node": a.get("current_node"), "status": a.get("status"),
        "blocked_reason": a.get("blocked_reason"), "started_at": a.get("started_at"),
    }


def _alerts(active_view, gate_views):
    out = []
    if active_view and active_view.get("status") == "blocked":
        out.append({"kind": "blocked",
                    "detail": active_view.get("blocked_reason") or "在跑棒次阻塞",
                    "ts": active_view.get("started_at")})
    for g in gate_views:
        if g.get("verdict") == "FAIL":
            out.append({"kind": "gate_fail",
                        "detail": f"{g.get('gate') or g.get('node')} 第{g.get('iter')}轮 FAIL"
                                  f"（{g['issues_count']} issues）",
                        "ts": g.get("ts")})
    return out


def build_feature_view(workspace, slug):
    """单 feature → 归一化 view-model；feature 不存在 → None。"""
    doc = read_flow_state(workspace, slug)
    if doc is None:
        return None
    events = read_events(workspace, slug)
    stories = doc.get("stories", []) or []
    done, total, pct = _completion(stories)
    active_view = _active_view(doc)
    gate_views = _gate_views(events)
    alerts = _alerts(active_view, gate_views)
    # —— 派单/链进度派生（dispatch 事件 + delivery-plan）——
    dispatches = _dispatch_views(events)
    plan = read_delivery_plan(workspace, slug)
    if plan:
        on_stages = [s for s in (plan.get("stages") or []) if s.get("on")]
        done_count = sum(1 for dv in dispatches if dv["status"] == "done")
        delivery = {
            "template_id": plan.get("template_id"),
            "slug": plan.get("slug", slug),
            "goal": plan.get("goal"),
            "stages": on_stages,
            "total_on": len(on_stages),
            "done_count": done_count,
            "progress_label": f"链进度 {done_count}/{len(on_stages)}",
        }
    else:
        delivery = None
    employee_activity = [
        {"emp": dv["emp"], "busy": dv["running"], "dispatch_id": dv["dispatch_id"]}
        for dv in dispatches
    ]
    # ── Roadmap（计划说明书结构体）──
    roadmap = {
        "stages": _roadmap_stages(plan, dispatches),
        "story_summary": {
            "done": done,
            "total": total,
            "pct": pct,
            "items": [
                {"id": s.get("id"), "title": s.get("title"),
                 "status": s.get("status", "pending")}
                for s in stories
            ],
        },
        "worktree": {
            "intent": (plan.get("worktree_intent") if plan else None),
            "concrete": None,
        },
    }
    return {
        "slug": doc.get("slug", slug),
        "display_name": doc.get("display_name") or slug,
        "feature_status": doc.get("status"),
        "stories": stories,
        "stories_done": done, "stories_total": total, "completion_pct": pct,
        "active": active_view,
        "runs": doc.get("runs", []) or [],
        "gates": gate_views,
        "alerts": alerts, "alert_count": len(alerts),
        "events": events,             # 原始 tail，渲染层自行截断
        "updated_at": doc.get("updated_at"),
        "delivery": delivery,
        "dispatches": dispatches,
        "employee_activity": employee_activity,
        "roadmap": roadmap,          # ← 新增
    }


# ---------------------------------------------------------------------------
# Task 4: aggregate layer — build_hud_model
# ---------------------------------------------------------------------------

def _pick_primary(features):
    """状态栏主角：优先有在跑棒次的；否则 updated_at 最新；都没有 → None。"""
    if not features:
        return None
    active = [f for f in features if f.get("active")]
    pool = active or features
    return max(pool, key=lambda f: f.get("updated_at") or "")


def build_hud_model(workspace):
    """全景：扫所有 feature → view-model 列表 + 选 primary。"""
    features = []
    for slug in list_feature_slugs(workspace):
        v = build_feature_view(workspace, slug)
        if v is not None:
            features.append(v)
    return {
        "features": features,
        "feature_count": len(features),
        "primary": _pick_primary(features),
    }
