"""Linker family: connect kdev rule nodes to code nodes in a UA graph.

The family has more than one shape:
- Member 1 — PatternLinker (deterministic, pattern-based) implements the
  `Linker` Protocol below: `link(rules, graph, source_root) -> [edge]`.
- Member 2 — SemanticLinker (LLM-driven, in `semantic_linker_prepare` +
  `semantic_linker_finalize`) is intentionally a different shape: it splits
  into a `prepare → subagent judge → finalize` pipeline driven by the
  `kdev-codegraph-spec-link` skill. It does NOT implement this Protocol.

The constants and helpers below (`SECURITY_EDGE_TYPE`, `make_security_edge`,
`build_path_index`, `resolve_node_id`) are shared by PatternLinker; future
non-pattern members may reuse them as needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ieidev_ingestor.graph_io import KnowledgeGraph
from ieidev_ingestor.security_rules import SecurityRule

SECURITY_EDGE_TYPE = "related"
SECURITY_EDGE_WEIGHT = 0.6


class Linker(Protocol):
    def link(
        self,
        rules: list[SecurityRule],
        graph: KnowledgeGraph,
        source_root: Path,
    ) -> list[dict]:
        """Return edge dicts (rule node -> code node). Pure; does not persist."""
        ...


def build_path_index(graph: KnowledgeGraph) -> dict[str, dict]:
    """Index graph nodes by filePath for O(1)-ish hit resolution.

    Returns {filePath: {"file": <file_node_id|None>,
                         "funcs": [(start, end, func_node_id), ...]}}
    """
    idx: dict[str, dict] = {}
    for n in graph.nodes:
        fp = n.get("filePath")
        if not fp:
            continue
        entry = idx.setdefault(fp, {"file": None, "funcs": []})
        if n.get("type") == "file":
            entry["file"] = n["id"]
        elif n.get("type") == "function":
            lr = n.get("lineRange")
            if isinstance(lr, (list, tuple)) and len(lr) == 2:
                entry["funcs"].append((lr[0], lr[1], n["id"]))
    return idx


def resolve_node_id(
    path_index: dict[str, dict], rel_path: str, line_no: int
) -> str | None:
    """Map a (file, line) hit to the enclosing function node, else the file node."""
    entry = path_index.get(rel_path)
    if entry is None:
        return None
    for start, end, node_id in entry["funcs"]:
        if start <= line_no <= end:
            return node_id
    return entry["file"]


def make_security_edge(rule_node_id: str, code_node_id: str) -> dict:
    return {
        "source": rule_node_id,
        "target": code_node_id,
        "type": SECURITY_EDGE_TYPE,
        "direction": "forward",
        "weight": SECURITY_EDGE_WEIGHT,
    }
