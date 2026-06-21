"""PatternLinker: deterministic rule->code linking via API token matching."""

from __future__ import annotations

import re
from pathlib import Path

from ieidev_ingestor.graph_io import KnowledgeGraph
from ieidev_ingestor.security_rules import SecurityRule
from ieidev_ingestor.linkers.base import (
    build_path_index,
    make_security_edge,
    resolve_node_id,
)


class PatternLinker:
    def link(
        self,
        rules: list[SecurityRule],
        graph: KnowledgeGraph,
        source_root: Path,
    ) -> list[dict]:
        source_root = Path(source_root)

        compiled: list[tuple[re.Pattern, str]] = []
        for rule in rules:
            rule_node_id = f"kdev-sec:rule:{rule.rule_id}"
            if rule_node_id not in graph._node_id_to_index:
                continue
            for pat in rule.patterns:
                rx = re.compile(r"\b" + re.escape(pat) + r"\b")
                compiled.append((rx, rule_node_id))
        if not compiled:
            return []

        path_index = build_path_index(graph)
        edges: dict[tuple[str, str], dict] = {}
        for rel_path in path_index:
            try:
                text = (source_root / rel_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for rx, rule_node_id in compiled:
                    if rx.search(line):
                        node_id = resolve_node_id(path_index, rel_path, line_no)
                        if node_id is None:
                            continue
                        key = (rule_node_id, node_id)
                        if key not in edges:
                            edges[key] = make_security_edge(rule_node_id, node_id)
        return list(edges.values())
