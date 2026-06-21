"""ieidev-memory promote-scan helper（v0.8 转 Python）

扫描 .ieidev/memory/ 的沉淀候选，输出 Brief P1 hint
（或 P0 当距 .last-promote > 30 天）。

被 session-start-brief.py 通过 import 引用。

约束：
  - 幂等、只读（不写任何文件）
  - 返回文本：P1 hint（"📝 建议沉淀：..."）/ P0（"🔴 长期未沉淀..."）/ 空字符串

最低 Python 版本：3.7。
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import shared_dir  # noqa: E402


_PROMOTE_DONE_RE = re.compile(r"^promote_status:\s*done", re.MULTILINE)
_RULE_HEADING_RE = re.compile(r"^### R-[0-9]", re.MULTILINE)


def _count_h2(path: Path) -> int:
    """计算文件里 ``^## `` 二级标题数量。"""
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.startswith("## "))


def _count_h2_prefix(path: Path, prefix: str) -> int:
    """计算文件里 ``^## <prefix>`` 二级标题数量。"""
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(
        1 for line in text.splitlines()
        if line.startswith(f"## {prefix}")
    )


def _count_promote_done(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return len(_PROMOTE_DONE_RE.findall(text))


def _count_rule_headings(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return len(_RULE_HEADING_RE.findall(text))


def _today_eod_ts(today: str) -> float:
    """today 字符串的 23:59:59 epoch（与 v0.7.x bash `date -d "$today 23:59:59"` 一致）。"""
    try:
        d = _date.fromisoformat(today)
    except ValueError:
        return time.time()
    eod = datetime(d.year, d.month, d.day, 23, 59, 59)
    return eod.timestamp()


def scan_promote_candidates(ieidev_dir: str, today: str) -> str:
    """扫描沉淀候选并返回 brief 提醒文本（无信号则空字符串）。"""
    root = Path(ieidev_dir)
    if not root.is_dir():
        return ""

    base = shared_dir(root)
    flush = root / ".last-promote"   # marker 留 root（plumbing）
    days_since_promote: Optional[int] = None  # None 等价于 "never"
    if flush.is_file():
        try:
            flush_ts = flush.stat().st_mtime
        except OSError:
            flush_ts = 0.0
        if flush_ts > 0:
            today_ts = _today_eod_ts(today)
            days_since_promote = int((today_ts - flush_ts) // 86400)

    improvements = base / "改进建议.md"
    rule_md = base / "conventions.md"
    gotchas = base / "踩坑日志.md"

    r_total = _count_h2(improvements)
    r_done = _count_promote_done(improvements)
    r_pending = max(0, r_total - r_done)

    rule_total = _count_rule_headings(rule_md)
    rule_done = _count_promote_done(rule_md)
    rule_pending = max(0, rule_total - rule_done)

    g_total = _count_h2_prefix(gotchas, "G-")
    g_done = _count_promote_done(gotchas)
    g_pending = max(0, g_total - g_done)

    reasons: list = []
    escalate_p0 = False

    # 时间触发
    if days_since_promote is not None and days_since_promote > 7:
        reasons.append(f"距上次沉淀 {days_since_promote} 天")
        if days_since_promote > 30:
            escalate_p0 = True

    # 增量触发
    if r_pending >= 3:
        reasons.append(f"改进建议 {r_pending} 条 pending")
    if rule_pending >= 2:
        reasons.append(f"R-NNN 规则 {rule_pending} 条 pending")
    if g_pending >= 5:
        reasons.append(f"踩坑 {g_pending} 条 pending")

    if not reasons:
        return ""
    if r_pending == 0 and rule_pending == 0 and g_pending == 0:
        return ""

    if escalate_p0:
        return (
            f"  - 🔴 长期未沉淀（{days_since_promote} 天）：团队已长期未获本项目过程结晶\n"
            f"    · 改进建议 pending: {r_pending}；R-NNN: {rule_pending}；G-NNN: {g_pending}\n"
            f"    · 执行 /ieidev-team:memory-distill 查看沉淀候选并更新 .last-promote\n"
        )
    return (
        f"  - 📝 建议沉淀（{'；'.join(reasons)}）：\n"
        f"    · 执行 /ieidev-team:memory-distill 查看沉淀候选并写入 docs/ 产物通道\n"
    )
