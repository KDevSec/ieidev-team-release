"""Extract spec intents from markdown documents.

Granularity rules (priority):
1. FR table rows — markdown tables whose first column header contains "ID" OR
   whose first data cell matches an FR-ID pattern (e.g. F1.1 / G2.3 / NF1.1.2):
   each data row becomes one Intent (kind="fr_row"). The enclosing section is
   NOT separately emitted.
2. Section (H2-H4) — any heading not absorbed by an FR table becomes one Intent
   (kind="section"). Body text truncated to 800 chars.
3. Whole-doc fallback — if a doc has no H2/H3/H4, the whole text becomes one
   Intent (kind="doc").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FR_ID_RE = re.compile(r"^[A-Z][A-Za-z]?\d+(?:\.\d+)+$")
_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}.*$")

SECTION_TEXT_MAX = 800


@dataclass
class Intent:
    intent_id: str
    source_doc: str
    intent_kind: str  # "fr_row" | "section" | "doc"
    intent_title: str
    intent_text: str


def _split_table_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _find_fr_tables(body: str) -> list[tuple[int, int, list[list[str]]]]:
    """Find FR-style tables in body. Returns (start_line_idx, end_line_idx_inclusive, rows)."""
    lines = body.splitlines()
    tables: list[tuple[int, int, list[list[str]]]] = []
    i = 0
    while i < len(lines):
        if _TABLE_LINE_RE.match(lines[i]):
            start = i
            rows = [_split_table_row(lines[i])]
            i += 1
            if i < len(lines) and _TABLE_SEP_RE.match(lines[i]):
                i += 1
                while i < len(lines) and _TABLE_LINE_RE.match(lines[i]):
                    rows.append(_split_table_row(lines[i]))
                    i += 1
                header = rows[0]
                first_data = rows[1] if len(rows) >= 2 else None
                is_fr_table = (
                    (header and "ID" in (header[0] or "").upper())
                    or (first_data and _FR_ID_RE.match((first_data[0] or "").strip()))
                )
                if is_fr_table and len(rows) >= 2:
                    tables.append((start, i - 1, rows))
        else:
            i += 1
    return tables


def _truncate(text: str, limit: int = SECTION_TEXT_MAX) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _strip_table_lines(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        if _TABLE_LINE_RE.match(line) or _TABLE_SEP_RE.match(line):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def extract_intents_from_markdown(md_text: str, doc_relpath: str) -> list[Intent]:
    """Top-level entry. Parse md_text and return intents for doc_relpath."""
    intents: list[Intent] = []

    headings = list(_HEADING_RE.finditer(md_text))
    if not headings:
        text = _truncate(md_text)
        if text:
            intents.append(Intent(
                intent_id=doc_relpath,
                source_doc=doc_relpath,
                intent_kind="doc",
                intent_title=doc_relpath.rsplit("/", 1)[-1],
                intent_text=text,
            ))
        return intents

    for idx, h in enumerate(headings):
        title = h.group(2).strip()
        sec_start = h.end()
        sec_end = headings[idx + 1].start() if idx + 1 < len(headings) else len(md_text)
        sec_body = md_text[sec_start:sec_end]

        fr_tables = _find_fr_tables(sec_body)
        if fr_tables:
            for _, _, rows in fr_tables:
                for data_row in rows[1:]:
                    if not data_row:
                        continue
                    first_cell = (data_row[0] or "").strip()
                    if not first_cell:
                        continue
                    second_cell = (data_row[1] or "").strip() if len(data_row) > 1 else ""
                    intent_title = (
                        f"{first_cell} {second_cell}".strip() if second_cell else first_cell
                    )
                    intent_text = " | ".join(c for c in data_row if c)
                    intents.append(Intent(
                        intent_id=f"{doc_relpath}#{first_cell}",
                        source_doc=doc_relpath,
                        intent_kind="fr_row",
                        intent_title=intent_title,
                        intent_text=intent_text,
                    ))
            continue

        section_text = _truncate(_strip_table_lines(sec_body))
        intents.append(Intent(
            intent_id=f"{doc_relpath}#{title}",
            source_doc=doc_relpath,
            intent_kind="section",
            intent_title=title,
            intent_text=section_text,
        ))

    return intents
