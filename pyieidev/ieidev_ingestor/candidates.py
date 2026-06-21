"""Candidate retrieval for the SemanticLinker.

v1 only provides KeywordRetriever (token overlap, stdlib-only). The Protocol is
designed so a future EmbeddingRetriever (when a graph carries embeddings) can
plug in without changing the linker.
"""

from __future__ import annotations

import re
from typing import Protocol

from ieidev_ingestor.graph_io import KnowledgeGraph

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MIN_TOKEN_LEN = 2
_CANDIDATE_TYPES = {"function", "class"}


def _tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) >= _MIN_TOKEN_LEN
    }


class CandidateRetriever(Protocol):
    def retrieve(
        self,
        intent_title: str,
        intent_text: str,
        graph: KnowledgeGraph,
        top_k: int = 30,
    ) -> list[dict]:
        """Return [{"node_id": str, "summary": str}, ...] of length ≤ top_k."""
        ...


class KeywordRetriever:
    """v1 retriever: token overlap on (name + summary) of function/class nodes.

    Fallback: when no candidate has positive overlap, return the first top_k
    function/class nodes (so the subagent always has something to say "not_found"
    on instead of an empty list).
    """

    def retrieve(
        self,
        intent_title: str,
        intent_text: str,
        graph: KnowledgeGraph,
        top_k: int = 30,
    ) -> list[dict]:
        q = _tokens(f"{intent_title} {intent_text}")

        scored: list[tuple[int, dict]] = []
        for n in graph.nodes:
            if n.get("type") not in _CANDIDATE_TYPES:
                continue
            d = _tokens(f"{n.get('name','')} {n.get('summary','')}")
            score = len(q & d)
            scored.append((score, n))

        scored.sort(key=lambda x: x[0], reverse=True)

        positives = [n for s, n in scored if s > 0]
        if positives:
            # Fill remaining slots with zero-score candidates so top_k is honoured
            zeros = [n for s, n in scored if s == 0]
            chosen = (positives + zeros)[:top_k]
        else:
            chosen = [n for _, n in scored][:top_k]

        return [
            {"node_id": n["id"], "summary": n.get("summary", "")}
            for n in chosen
        ]
