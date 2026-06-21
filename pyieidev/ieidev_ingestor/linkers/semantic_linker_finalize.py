"""SemanticLinker finalize phase: read verdicts → upsert edges + extras + report."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ieidev_ingestor.graph_io import (
    GraphIOError,
    KnowledgeGraph,
    upsert_edge,
)

EXTRAS_KEY = "kdev_spec_link"
DOC_DRIFT_DEFAULT_DAYS = 30
DOC_DRIFT_SECURITY_DAYS = 14


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ts_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _git_mtime(path: Path, repo_root: Path | None = None) -> float | None:
    """Return git commit timestamp for path; None if not under git or git unavailable."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return float(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _remove_owned_edges(graph: KnowledgeGraph, owned: list[dict]) -> int:
    """Remove edges matching owned triples from the graph; rebuild index."""
    if not owned:
        return 0
    owned_set = {(t["source"], t["target"], t["type"]) for t in owned}
    new_edges = []
    new_index: dict = {}
    removed = 0
    for e in graph.edges:
        triple = (e["source"], e["target"], e["type"])
        if triple in owned_set:
            removed += 1
            continue
        new_index[triple] = len(new_edges)
        new_edges.append(e)
    graph.edges = new_edges
    graph._edge_triple_to_index = new_index
    return removed


def _intent_counts(verdicts: list[dict]) -> dict[str, int]:
    counts = {"implemented": 0, "partial": 0, "not_found": 0, "error": 0}
    for v in verdicts:
        st = v.get("status")
        if st in counts:
            counts[st] += 1
    return counts


def _is_security_doc(graph: KnowledgeGraph, doc_node_id: str) -> bool:
    idx = graph._node_id_to_index.get(doc_node_id)
    if idx is None:
        return False
    return any(
        isinstance(t, str) and t.startswith("kdev:security_rule")
        for t in graph.nodes[idx].get("tags", [])
    )


def finalize(
    graph: KnowledgeGraph,
    verdicts: list[dict],
    source_root: Path,
) -> tuple[KnowledgeGraph, dict[str, Any]]:
    """Mutate graph: clear old owned edges, write new documents edges, update extras.

    Returns (graph, report_data) where report_data is a structured dict used by
    the report renderer.
    """
    prior_extras = graph.extras.get(EXTRAS_KEY, {}) or {}
    prior_owned = prior_extras.get("owned_edge_triples", [])
    _remove_owned_edges(graph, prior_owned)

    new_owned: list[dict] = []
    edges_written = 0
    skipped_invalid_target = 0
    implemented_intents: list[dict] = []
    partial_intents: list[dict] = []
    not_found_intents: list[dict] = []
    error_intents: list[dict] = []

    for v in verdicts:
        status = v.get("status")
        intent_id = v.get("intent_id", "")
        source_doc = intent_id.split("#", 1)[0] if intent_id else ""
        target_doc_node = f"document:{source_doc}"
        if target_doc_node not in graph._node_id_to_index:
            error_intents.append({"intent_id": intent_id, "reason": "doc node missing"})
            continue

        if status == "not_found":
            not_found_intents.append({"intent_id": intent_id})
            continue
        if status == "error":
            error_intents.append({"intent_id": intent_id, "reason": "subagent error"})
            continue
        if status not in {"implemented", "partial"}:
            continue

        bucket = implemented_intents if status == "implemented" else partial_intents
        linked_entries = []
        for link in v.get("linked", []):
            target = link.get("target_node_id")
            conf = link.get("confidence")
            try:
                conf_f = float(conf)
            except (TypeError, ValueError):
                continue
            if not (0.0 <= conf_f <= 1.0):
                continue
            if target not in graph._node_id_to_index:
                skipped_invalid_target += 1
                continue
            edge = {
                "source": target,
                "target": target_doc_node,
                "type": "documents",
                "direction": "backward",
                "weight": conf_f,
            }
            try:
                upsert_edge(graph, edge)
                edges_written += 1
                new_owned.append({"source": target, "target": target_doc_node,
                                  "type": "documents"})
                linked_entries.append({
                    "target": target, "confidence": conf_f,
                    "reason": link.get("reason", ""),
                })
            except GraphIOError:
                skipped_invalid_target += 1
                continue
        bucket.append({"intent_id": intent_id, "linked": linked_entries})

    counts = _intent_counts(verdicts)
    graph.extras[EXTRAS_KEY] = {
        "schema_version": 1,
        "last_run_at": _iso_now(),
        "intents_processed": len(verdicts),
        "implemented_count": counts["implemented"],
        "partial_count": counts["partial"],
        "not_found_count": counts["not_found"],
        "error_count": counts["error"],
        "edges_written": edges_written,
        "skipped_invalid_target": skipped_invalid_target,
        "owned_edge_triples": new_owned,
    }

    report_data = {
        "counts": counts,
        "edges_written": edges_written,
        "implemented_intents": implemented_intents,
        "partial_intents": partial_intents,
        "not_found_intents": not_found_intents,
        "error_intents": error_intents,
        "skipped_invalid_target": skipped_invalid_target,
    }
    return graph, report_data


def render_report(
    graph: KnowledgeGraph,
    report_data: dict,
    source_root: Path,
) -> str:
    counts = report_data["counts"]
    total = sum(counts.values())
    def pct(n: int) -> str:
        return f"{(100*n/total):.0f}%" if total else "0%"

    # Drift: compare git mtimes for docs and their linked code
    drift_rows: list[tuple[str, str, str, int, bool]] = []
    for grp in (report_data["implemented_intents"], report_data["partial_intents"]):
        for it in grp:
            doc_rel = it["intent_id"].split("#", 1)[0] if it["intent_id"] else None
            if not doc_rel or not it.get("linked"):
                continue
            doc_t = _git_mtime(Path(doc_rel), source_root)
            code_ts = []
            for link in it["linked"]:
                idx = graph._node_id_to_index.get(link["target"])
                if idx is None:
                    continue
                node = graph.nodes[idx]
                if isinstance(node.get("filePath"), str):
                    t = _git_mtime(Path(node["filePath"]), source_root)
                    if t is not None:
                        code_ts.append(t)
            if doc_t is None or not code_ts:
                continue
            code_t = max(code_ts)
            days = int((code_t - doc_t) / 86400)
            is_sec = _is_security_doc(graph, f"document:{doc_rel}")
            threshold = DOC_DRIFT_SECURITY_DAYS if is_sec else DOC_DRIFT_DEFAULT_DAYS
            if days > threshold:
                drift_rows.append((
                    it["intent_id"],
                    datetime.fromtimestamp(doc_t).strftime("%Y-%m-%d"),
                    datetime.fromtimestamp(code_t).strftime("%Y-%m-%d"),
                    days,
                    is_sec,
                ))

    # 缺文档: function nodes that aren't the source of any documents edge
    docs_source_set = {e["source"] for e in graph.edges if e["type"] == "documents"}
    missing_doc_files: dict[str, int] = {}
    for n in graph.nodes:
        if n.get("type") != "function":
            continue
        if n["id"] in docs_source_set:
            continue
        fp = n.get("filePath", "")
        if fp:
            missing_doc_files[fp] = missing_doc_files.get(fp, 0) + 1

    out = []
    out.append("# Spec ↔ Code 对齐审计报告")
    out.append(f"> 生成时间: {_iso_now()}")
    out.append("> 上次 LLM 判定: 本次（新鲜）")
    out.append("")
    out.append("## 📊 摘要")
    out.append("| 实现状态 | 数量 | 占比 |")
    out.append("|---|---|---|")
    out.append(f"| ✅ 有实现 | {counts['implemented']} | {pct(counts['implemented'])} |")
    out.append(f"| ⚠️ 部分/疑似 | {counts['partial']} | {pct(counts['partial'])} |")
    out.append(f"| ❌ 未发现实现 | {counts['not_found']} | {pct(counts['not_found'])} |")
    out.append(f"| 🔥 LLM 判定错误 | {counts['error']} | {pct(counts['error'])} |")
    out.append("")
    out.append("| 同步状态 | 数量 |")
    out.append("|---|---|")
    out.append(f"| ⚠️ 漂移(>阈值) | {len(drift_rows)} |")
    out.append(f"| 🔍 缺文档(代码无 doc 归属) | {len(missing_doc_files)} 文件 |")
    out.append(f"| 🚫 LLM 输出无效 target 被跳过 | {report_data.get('skipped_invalid_target', 0)} |")
    out.append("")

    if report_data["not_found_intents"]:
        out.append("## ❌ 未发现实现")
        out.append("| Intent | 说明 |")
        out.append("|---|---|")
        for it in report_data["not_found_intents"]:
            out.append(f"| {it['intent_id']} | LLM 未在候选中找到匹配 |")
        out.append("")

    if report_data["partial_intents"]:
        out.append("## ⚠️ 部分/疑似实现")
        out.append("| Intent | 候选 | confidence |")
        out.append("|---|---|---|")
        for it in report_data["partial_intents"]:
            for lk in it["linked"]:
                out.append(f"| {it['intent_id']} | {lk['target']} | {lk['confidence']:.2f} |")
        out.append("")

    if drift_rows:
        out.append("## ⚠️ 漂移（代码比文档新 超过阈值）")
        out.append("| Intent | 文档时间 | 代码最新时间 | 漂移天数 | 安全相关 |")
        out.append("|---|---|---|---|---|")
        for iid, dt, ct, days, is_sec in drift_rows:
            out.append(f"| {iid} | {dt} | {ct} | {days} | {'是' if is_sec else '否'} |")
        out.append("")

    if missing_doc_files:
        out.append("## 🔍 缺文档（按文件聚合）")
        out.append("| 文件 | 无文档函数数 |")
        out.append("|---|---|")
        for fp, n in sorted(missing_doc_files.items(), key=lambda x: -x[1])[:20]:
            out.append(f"| {fp} | {n} |")
        out.append("")

    out.append("## ⚠️ 重要注意事项")
    out.append("- **未发现实现 ≠ 未实现**：v1 候选检索为关键词重叠，跨语言（中文 intent ↔ 英文代码摘要）召回不全，请人工核对")
    out.append("- 低 confidence (< 0.5) 项需人工确认")
    out.append("- 涉及 `kdev:security_rule` 的文档漂移阈值为 14 天，其他为 30 天")

    return "\n".join(out) + "\n"


def write_report(report_text: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"spec-link-{_ts_for_filename()}.md"
    path.write_text(report_text, encoding="utf-8")
    return path
