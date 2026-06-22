# pyieidev/ieidev_team/roadmap.py
"""计划说明书纯函数 —— 从 delivery-plan dict + 工作区文件派生路线图结构体。

无 ieidev_core 依赖；读 flow-state.json + events.jsonl 文件直接用 json/pathlib。
"""
import json
from pathlib import Path

_EMP_DISPLAY = {
    "req-architect": "需求架构师",
    "dev-engineer": "开发工程师",
    "test-engineer": "测试工程师",
}


def _read_stories(workspace, slug):
    """读 flow-state.json 里的 stories[]；缺失/损坏 → []。"""
    path = Path(workspace) / ".ieidev" / "features" / slug / "flow-state.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        s = doc.get("stories")
        return s if isinstance(s, list) else []
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def _read_dispatch_events(workspace, slug):
    """读 events.jsonl 里 type==dispatch 的行；缺失/坏行 → 跳过。"""
    path = Path(workspace) / ".ieidev" / "features" / slug / "events.jsonl"
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("type") == "dispatch":
                    out.append(e)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def _stage_status_map(dispatch_events):
    """stage_index（1-based）→ "done"|"active"；无事件 → key 缺失（调用方默认 pending）。

    done 仅在 phase=done AND status=done 时成立；blocked dispatch（phase=done, status=blocked）
    不标 done，降回 pending（常见路径与 datasource._roadmap_stage_status_map 一致；非强约束，
    未跨模块校验）。
    """
    result = {}
    for e in dispatch_events:
        si = e.get("stage_index")
        if si is None:
            continue
        if e.get("phase") == "done":
            if e.get("status") == "done":
                result[si] = "done"
            else:
                # blocked / failed dispatch: 撤销 active，回落 pending（调用方默认）
                result.pop(si, None)
        elif e.get("phase") == "start" and result.get(si) != "done":
            result[si] = "active"
    return result


def build_roadmap(plan, workspace, slug):
    """从 delivery-plan + 工作区文件构建路线图结构体。

    Args:
        plan: delivery-plan dict（可为 None）
        workspace: 工作区根路径（str 或 Path）
        slug: feature slug

    Returns:
        {
            "stages": [{emp, flow, display_name, on, stage_index, status}, ...],
            "story_summary": {done, total, pct, items[{id, title, status}]},
            "worktree": {intent, concrete}
        }
    """
    stories = _read_stories(workspace, slug)
    dispatch_events = _read_dispatch_events(workspace, slug)
    status_map = _stage_status_map(dispatch_events)

    # plan 容错：仅 dict 才取 stages/worktree_intent；非 dict（None/list/str/…）→ 空 stages、intent=None
    is_plan = isinstance(plan, dict)
    stages = []
    if is_plan:
        on_stages = [s for s in (plan.get("stages") or []) if s.get("on")]
        for i, s in enumerate(on_stages, 1):
            emp = s.get("emp") or ""
            stages.append({
                "emp": emp,
                "flow": s.get("flow") or "",
                "display_name": _EMP_DISPLAY.get(emp, emp),
                "on": True,
                "stage_index": i,
                "status": status_map.get(i, "pending"),
            })

    done = sum(1 for s in stories if s.get("status") == "done")
    total = len(stories)
    pct = round(100 * done / total) if total else 0

    return {
        "stages": stages,
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
            "intent": (plan.get("worktree_intent") if is_plan else None),
            # concrete：前向占位——confirm 期落点未定，dev 段未来填实（当前恒 None）
            "concrete": None,
        },
    }
