"""IO + safe upsert for Understand-Anything knowledge-graph.json files.

We do not re-implement UA's full zod validation. We only guard the slice
we write — that fields exist, types are in the canonical allowlist, and
edges reference existing nodes. UA's loader will perform its own pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Pulled from UA schema.ts (21 + 35) — pinned by contract test.
UA_NODE_TYPES = frozenset({
    "file", "function", "class", "module", "concept",
    "config", "document", "service", "table", "endpoint",
    "pipeline", "schema", "resource",
    "domain", "flow", "step",
    "article", "entity", "topic", "claim", "source",
})

UA_EDGE_TYPES = frozenset({
    "imports", "exports", "contains", "inherits", "implements",
    "calls", "subscribes", "publishes", "middleware",
    "reads_from", "writes_to", "transforms", "validates",
    "depends_on", "tested_by", "configures",
    "related", "similar_to",
    "deploys", "serves", "provisions", "triggers",
    "migrates", "documents", "routes", "defines_schema",
    "contains_flow", "flow_step", "cross_domain",
    "cites", "contradicts", "builds_on", "exemplifies",
    "categorized_under", "authored_by",
})

REQUIRED_NODE_FIELDS = ("id", "type", "name", "summary", "tags", "complexity")
REQUIRED_EDGE_FIELDS = ("source", "target", "type", "direction", "weight")
REQUIRED_TOP_KEYS = ("version", "project", "nodes", "edges", "layers", "tour")


class GraphIOError(Exception):
    """Raised on any malformed graph state we wrote or refuse to write."""


@dataclass
class KnowledgeGraph:
    version: str
    project: dict[str, Any]
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    layers: list[dict[str, Any]] = field(default_factory=list)
    tour: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    # Private indexes — O(1) lookup; never written to JSON.
    _node_id_to_index: dict[str, int] = field(
        default_factory=dict, repr=False
    )
    _edge_triple_to_index: dict[tuple[str, str, str], int] = field(
        default_factory=dict, repr=False
    )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "version": self.version,
            "project": self.project,
            "nodes": self.nodes,
            "edges": self.edges,
            "layers": self.layers,
            "tour": self.tour,
        }
        out.update(self.extras)
        return out


def load_graph(path: Path) -> KnowledgeGraph:
    if not path.exists():
        raise GraphIOError(f"graph not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GraphIOError("top-level must be an object")
    for key in REQUIRED_TOP_KEYS:
        if key not in raw:
            raise GraphIOError(f"required key missing: {key}")
    extras = {k: v for k, v in raw.items() if k not in REQUIRED_TOP_KEYS}
    nodes: list[dict[str, Any]] = list(raw["nodes"])
    edges: list[dict[str, Any]] = list(raw["edges"])
    node_id_to_index: dict[str, int] = {
        n["id"]: i for i, n in enumerate(nodes)
    }
    edge_triple_to_index: dict[tuple[str, str, str], int] = {
        (e["source"], e["target"], e["type"]): i
        for i, e in enumerate(edges)
    }
    return KnowledgeGraph(
        version=raw["version"],
        project=raw["project"],
        nodes=nodes,
        edges=edges,
        layers=list(raw["layers"]),
        tour=list(raw["tour"]),
        extras=extras,
        _node_id_to_index=node_id_to_index,
        _edge_triple_to_index=edge_triple_to_index,
    )


def save_graph(graph: KnowledgeGraph, path: Path) -> None:
    path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _validate_node(node: dict[str, Any]) -> None:
    for f in REQUIRED_NODE_FIELDS:
        if f not in node:
            raise GraphIOError(f"node missing required field: {f}")
    if node["type"] not in UA_NODE_TYPES:
        raise GraphIOError(f"unknown node type: {node['type']!r}")
    if not isinstance(node["tags"], list):
        raise GraphIOError("node.tags must be a list")
    if node["complexity"] not in {"simple", "moderate", "complex"}:
        raise GraphIOError(f"invalid complexity: {node['complexity']!r}")


def _validate_edge(edge: dict[str, Any], node_ids: set[str] | dict[str, Any]) -> None:
    for f in REQUIRED_EDGE_FIELDS:
        if f not in edge:
            raise GraphIOError(f"edge missing required field: {f}")
    if edge["type"] not in UA_EDGE_TYPES:
        raise GraphIOError(f"unknown edge type: {edge['type']!r}")
    if edge["direction"] not in {"forward", "backward", "bidirectional"}:
        raise GraphIOError(f"invalid direction: {edge['direction']!r}")
    weight = edge["weight"]
    if not isinstance(weight, (int, float)) or not 0.0 <= float(weight) <= 1.0:
        raise GraphIOError(f"weight must be in [0, 1]: {weight!r}")
    if edge["source"] not in node_ids:
        raise GraphIOError(f"dangling source: {edge['source']!r}")
    if edge["target"] not in node_ids:
        raise GraphIOError(f"dangling target: {edge['target']!r}")


def upsert_node(graph: KnowledgeGraph, node: dict[str, Any]) -> None:
    _validate_node(node)
    node_id = node["id"]
    if node_id in graph._node_id_to_index:
        i = graph._node_id_to_index[node_id]
        graph.nodes[i] = node
    else:
        graph._node_id_to_index[node_id] = len(graph.nodes)
        graph.nodes.append(node)


def upsert_edge(graph: KnowledgeGraph, edge: dict[str, Any]) -> None:
    # Pass the index dict directly — dict `in` is O(1), no set copy needed.
    _validate_edge(edge, graph._node_id_to_index)
    triple = (edge["source"], edge["target"], edge["type"])
    if triple in graph._edge_triple_to_index:
        i = graph._edge_triple_to_index[triple]
        graph.edges[i] = edge
    else:
        graph._edge_triple_to_index[triple] = len(graph.edges)
        graph.edges.append(edge)


def find_nodes_by_tag(graph: KnowledgeGraph, tag: str) -> list[dict[str, Any]]:
    return [n for n in graph.nodes if tag in n.get("tags", [])]
