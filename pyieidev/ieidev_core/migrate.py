"""kdev-core 迁移：旧 .ieidev/flows/<flow>/<slug>/ → feature-first .ieidev/features/<slug>/.

幂等（目标已存在则跳过）；同 slug 跨多 flow 合并进一个 feature 的 runs[]+events；
旧 history[]→gate 事件、phase_history[]→transition 事件。非破坏（--remove-old 才删旧）。
"""
import json
import shutil
from pathlib import Path

from ieidev_core import events as _events
from ieidev_core import flow_state as _fs


def _old_flows_root(workspace) -> Path:
    return Path(workspace) / ".ieidev" / "flows"


def _scan_old(workspace):
    """收集旧 flow-state：{slug: [(flow, doc), ...]}，按 created_at 排序。"""
    root = _old_flows_root(workspace)
    by_slug = {}
    if not root.exists():
        return by_slug
    for flow_dir in sorted(root.iterdir()):
        if not flow_dir.is_dir():
            continue
        for slug_dir in sorted(flow_dir.iterdir()):
            sp = slug_dir / "flow-state.json"
            if not sp.exists():
                continue
            try:
                doc = json.loads(sp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            doc.pop("_meta", None)
            by_slug.setdefault(slug_dir.name, []).append((flow_dir.name, doc))
    for slug in by_slug:
        # 主键 created_at；created_at 相等时让 in_progress 排最后（它是进行中的最新一棒，
        # 应落到 active{}）——保证「最后一个若 in_progress 进 active」语义确定。
        by_slug[slug].sort(key=lambda fd: (fd[1].get("created_at", ""),
                                           fd[1].get("status") == "in_progress"))
    return by_slug


def _run_summary(flow, run_no, doc):
    return {
        "flow": flow, "run": run_no, "status": doc.get("status", "completed"),
        "final_node": doc.get("current_node"), "ended_at": doc.get("updated_at"),
    }


def _emit_events(workspace, slug, flow, run_no, doc):
    for entry in doc.get("phase_history", []) or []:
        _events.append_event(workspace, slug,
                             _events.transition_event(slug=slug, flow=flow, run=run_no, entry=entry))
    for gr in doc.get("history", []) or []:
        _events.append_event(workspace, slug,
                             _events.gate_event(slug=slug, flow=flow, run=run_no, gate_result=gr))


def migrate_workspace(workspace, *, dry_run=False, remove_old=False):
    """迁移整个 workspace。返回 {migrated:[slug], skipped:[slug], dry_run:bool}。"""
    by_slug = _scan_old(workspace)
    migrated, skipped = [], []
    for slug, flows in by_slug.items():
        target = _fs._state_path(workspace, slug)
        if target.exists():
            skipped.append(slug)
            continue
        if dry_run:
            migrated.append(slug)
            continue
        first_flow, first_doc = flows[0]
        display_name = first_doc.get("display_name", slug)
        created_at = first_doc.get("created_at") or _fs._now_iso()
        config = first_doc.get("config", {"review_mode": "ai", "auto_mode": False})
        runs, active = [], None
        feature_in_progress = False
        run_no = 0
        for idx, (flow, doc) in enumerate(flows):
            run_no += 1
            is_last = idx == len(flows) - 1
            _emit_events(workspace, slug, flow, run_no, doc)
            if is_last and doc.get("status") == "in_progress":
                active = {
                    "flow": flow, "run": run_no,
                    "current_node": doc.get("current_node"),
                    "status": "in_progress",
                    "gate_iters": {}, "gate_calls": 0, "retries": {},
                    "blocked_reason": None, "config": doc.get("config", config),
                    "started_at": doc.get("created_at") or created_at,
                }
                feature_in_progress = True
            else:
                runs.append(_run_summary(flow, run_no, doc))
        if feature_in_progress:
            feature_status = "in_progress"
        else:
            feature_status = flows[-1][1].get("status", "completed")
        out_doc = {
            "slug": slug, "display_name": display_name,
            "origin": "migrated:.ieidev/flows", "relates_to": None,
            "status": feature_status, "stories": [], "runs": runs, "active": active,
            "created_at": created_at,
        }
        _fs._write_doc(workspace, slug, out_doc)
        if remove_old:
            for flow, _doc in flows:
                shutil.rmtree(_old_flows_root(workspace) / flow / slug, ignore_errors=True)
        migrated.append(slug)
    return {"migrated": sorted(migrated), "skipped": sorted(skipped), "dry_run": dry_run}
