"""Parse kdev-secure-coding rule markdown into UA-compatible concept nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ieidev_ingestor.tags import (
    KIND_SECURITY_RULE,
    make_tag,
)

# Matches `## 3.1.1 标题文本`
_RULE_HEADING_RE = re.compile(
    r"^##\s+(?P<id>\d+(?:\.\d+){1,3})\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)
# Matches `### 规则` (Chinese) or `### Rules` (English)
_RULES_SECTION_RE = re.compile(r"^###\s+(?:规则|Rules)\s*$", re.MULTILINE)
# Slug from filename: `01-input-validation.md` → `input_validation`
_FILENAME_SLUG_RE = re.compile(r"^\d+-(?P<slug>.+?)\.md$")
# Matches `### 适用场景` (Chinese applicability section)
_SCENARIO_SECTION_RE = re.compile(r"^###\s+适用场景\s*$", re.MULTILINE)
# Backtick-quoted spans
_BACKTICK_RE = re.compile(r"`([^`]+)`")
# Valid API pattern token: identifier, optionally dotted (e.g. mod.func)
_PATTERN_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class RuleParseError(Exception):
    """Raised when a rule markdown file cannot be parsed."""


@dataclass
class SecurityRule:
    rule_id: str
    title: str
    summary: str
    category: str
    source_file: Path
    patterns: list[str] = field(default_factory=list)


def _extract_category(filename: str) -> str:
    m = _FILENAME_SLUG_RE.match(filename)
    if not m:
        return filename.replace(".md", "").replace("-", "_")
    return m.group("slug").replace("-", "_")


def _extract_summary(body: str) -> str:
    """Take the first non-empty bullet inside ### 规则 as the summary."""
    rules_match = _RULES_SECTION_RE.search(body)
    if not rules_match:
        return ""
    after = body[rules_match.end():]
    for line in after.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            break
        if stripped.startswith(("-", "*")):
            return stripped.lstrip("-* ").strip()
    return ""


def _extract_patterns(body: str) -> list[str]:
    """Extract backtick-quoted API tokens from the `### 适用场景` section."""
    m = _SCENARIO_SECTION_RE.search(body)
    if not m:
        return []
    after = body[m.end():]
    nxt = re.search(r"^###\s+", after, re.MULTILINE)
    section = after[: nxt.start()] if nxt else after
    seen: dict[str, None] = {}
    for tok in _BACKTICK_RE.findall(section):
        tok = tok.strip()
        if _PATTERN_TOKEN_RE.match(tok) and tok not in seen:
            seen[tok] = None
    return list(seen.keys())


def parse_rule_file(path: Path) -> list[SecurityRule]:
    if not path.exists():
        raise RuleParseError(f"rule file not found: {path}")
    text = path.read_text(encoding="utf-8")
    category = _extract_category(path.name)
    rules: list[SecurityRule] = []
    matches = list(_RULE_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        summary = _extract_summary(body)
        if not summary:
            continue
        rules.append(SecurityRule(
            rule_id=m.group("id"),
            title=m.group("title").strip(),
            summary=summary,
            category=category,
            source_file=path,
            patterns=_extract_patterns(body),
        ))
    return rules


def parse_rules_dir(dir_path: Path) -> list[SecurityRule]:
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    out: list[SecurityRule] = []
    for md in sorted(dir_path.glob("*.md")):
        out.extend(parse_rule_file(md))
    return out


def rule_to_node(rule: SecurityRule) -> dict[str, Any]:
    return {
        "id": f"kdev-sec:rule:{rule.rule_id}",
        "type": "concept",
        "name": rule.title,
        "summary": rule.summary,
        "tags": [
            make_tag(KIND_SECURITY_RULE),
            make_tag("rule_id", rule.rule_id),
            make_tag("category", rule.category),
            make_tag("source", "kdev-secure-coding"),
        ],
        "complexity": "moderate",
    }
