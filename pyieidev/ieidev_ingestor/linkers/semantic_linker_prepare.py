"""SemanticLinker prepare phase: build intents.json from a graph + source docs."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ieidev_ingestor.candidates import CandidateRetriever, KeywordRetriever
from ieidev_ingestor.graph_io import KnowledgeGraph
from ieidev_ingestor.intents import extract_intents_from_markdown


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _doc_nodes(graph: KnowledgeGraph) -> list[dict]:
    return [
        n for n in graph.nodes
        if n.get("type") == "document"
        and isinstance(n.get("filePath"), str)
        and n["filePath"].endswith(".md")
    ]


def prepare_intents(
    graph: KnowledgeGraph,
    graph_path: str,
    source_root: Path,
    top_k: int = 30,
    retriever: CandidateRetriever | None = None,
) -> dict[str, Any]:
    """Compose the intents.json payload (reads source .md files; no graph writes)."""
    retriever = retriever or KeywordRetriever()
    doc_nodes = _doc_nodes(graph)
    intents_payload: list[dict] = []
    seen_ids: dict[str, int] = {}  # intent_id -> index in intents_payload
    for d in doc_nodes:
        fp = d["filePath"]
        md_path = source_root / fp
        if not md_path.exists():
            continue
        try:
            md_text = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for intent in extract_intents_from_markdown(md_text, fp):
            candidates = retriever.retrieve(
                intent.intent_title, intent.intent_text, graph, top_k=top_k
            )
            entry = {
                "intent_id": intent.intent_id,
                "source_doc": intent.source_doc,
                "intent_kind": intent.intent_kind,
                "intent_title": intent.intent_title,
                "intent_text": intent.intent_text,
                "candidates": candidates,
            }
            if intent.intent_id in seen_ids:
                print(
                    f"warning: duplicate intent_id {intent.intent_id!r}, "
                    f"overriding earlier entry",
                    file=sys.stderr,
                )
                intents_payload[seen_ids[intent.intent_id]] = entry
            else:
                seen_ids[intent.intent_id] = len(intents_payload)
                intents_payload.append(entry)

    return {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "graph_path": graph_path,
        "source_root": str(source_root),
        "doc_count": len(doc_nodes),
        "intent_count": len(intents_payload),
        "intents": intents_payload,
    }


def write_intents_json(payload: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
