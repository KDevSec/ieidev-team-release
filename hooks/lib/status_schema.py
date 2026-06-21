#!/usr/bin/env python3
"""
status 字段枚举与防御
====================

ieidev-memory 六类记录的 `status` 字段 = **评分/销账态**（不是修复态）。
合法值只有 4 种：
    open | scored | voided-faded | voided-r-<NNN>

修复进展（fixed / mitigated / 处置中 / 日期）写进 body 的「解决 / 处置进展」段，
**不重载 status、不新增 fix_status 字段**（Q-决策，见 决策日志）。

本模块给 step_completeness / distill 共享：
- `is_known_status(s)`   —— 是否 4 枚举之一
- `is_voided_status(s)`  —— 是否销账态（voided-faded / voided-r-NNN）
- `warn_unknown_status(s, entry_id, stream)` —— 遇非枚举 status 告警一行
  （别静默当未评分）；返回是否告警。
"""

from __future__ import annotations

import re
import sys

KNOWN_SIMPLE = frozenset({"open", "scored", "voided-faded"})
_RE_VOIDED_R = re.compile(r"^voided-r-\d+$")


def _norm(s: "str | None") -> str:
    return (s or "").strip()


def is_known_status(s: "str | None") -> bool:
    """status 是否 4 合法枚举之一（open|scored|voided-faded|voided-r-<digits>）。"""
    s = _norm(s)
    return s in KNOWN_SIMPLE or bool(_RE_VOIDED_R.match(s))


def is_voided_status(s: "str | None") -> bool:
    """status 是否销账态（voided-faded 或 voided-r-<digits>）。"""
    s = _norm(s)
    return s == "voided-faded" or bool(_RE_VOIDED_R.match(s))


def warn_unknown_status(status: "str | None", entry_id: str = "?", stream=None) -> bool:
    """status 非空且非枚举 → 往 stream（默认 stderr）打一行告警；返回是否告警。

    用途：防止把 `fixed` / `mitigated` / `处置中` 这类**修复态**误写进 status 后
    被下游静默当作「未评分 / 非销账」处理。修复态应写 body「解决」段。
    """
    s = _norm(status)
    if not s or is_known_status(s):
        return False
    stream = stream if stream is not None else sys.stderr
    print(
        f"⚠️ ieidev-team: 条目 {entry_id} 的 status='{s}' 非枚举值"
        f"（合法仅 open|scored|voided-faded|voided-r-NNN）"
        f"——不静默当未评分；修复态请写 body「解决」段，勿重载 status。",
        file=stream,
    )
    return True
