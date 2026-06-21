"""ieidev-memory 归档提醒逻辑（v0.8 转 Python）

被 stop-check.py 通过 import 引用。

切档规则（见 SKILL.md「文件切档与归档」）：
  执行日志.md   → 按月切     执行日志-YYYY-MM.md
  踩坑日志.md   → 按季度切  踩坑日志-YYYYQN.md
  决策日志.md   → 按季度切  决策日志-YYYYQN.md
  改进建议.md   → 不切档

判据：主文件里最早一条日期 < 当月/当季 → 提醒切档。
不用定行数阈值——用日期自然判断更直观。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import re
import sys
from datetime import date as _date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import shared_dir  # noqa: E402


_DATE_RE = re.compile(r"(?:日期|date)[：:]\s*(\d{4}-\d{2}-\d{2})")


def date_to_quarter(d: str) -> str:
    """从 YYYY-MM-DD 算季度号 YYYYQN。"""
    year = d[0:4]
    month = int(d[5:7])
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def earliest_date_in_file(path: Path) -> Optional[str]:
    """提取文件里最早的 ``日期：YYYY-MM-DD``（按字典序，等价时间序）。"""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    matches = _DATE_RE.findall(text)
    if not matches:
        return None
    return min(matches)


def check_monthly_archive_hint(path: Path, label: str) -> str:
    """检查某文件是否需要按月归档；返回提醒文本（无则空）。"""
    earliest = earliest_date_in_file(path)
    if not earliest:
        return ""
    earliest_month = earliest[:7]  # YYYY-MM
    current_month = _date.today().strftime("%Y-%m")
    if earliest_month != current_month:
        stem = label.rsplit(".md", 1)[0]
        return (
            f"{label}（最早条目 {earliest}，跨月到 {current_month}）"
            f"→ 建议切 {earliest_month} 及更早条目到 归档/{stem}-{earliest_month}.md"
        )
    return ""


def check_quarterly_archive_hint(path: Path, label: str) -> str:
    """检查某文件是否需要按季度归档；返回提醒文本（无则空）。"""
    earliest = earliest_date_in_file(path)
    if not earliest:
        return ""
    earliest_q = date_to_quarter(earliest)
    today = _date.today().isoformat()
    current_q = date_to_quarter(today)
    if earliest_q != current_q:
        stem = label.rsplit(".md", 1)[0]
        return (
            f"{label}（最早条目 {earliest}，跨季到 {current_q}）"
            f"→ 建议切 {earliest_q} 及更早条目到 归档/{stem}-{earliest_q}.md"
        )
    return ""


def collect_archive_hints(ieidev_dir: str) -> str:
    """聚合：扫 .ieidev/memory/ 三个主文件，返回归档提醒（无则空字符串）。

    返回的字符串末尾带换行；调用方按需 strip。
    """
    kdev = shared_dir(Path(ieidev_dir))
    hints: list = []

    line = check_monthly_archive_hint(kdev / "执行日志.md", "执行日志.md")
    if line:
        hints.append(f"  - {line}")

    line = check_quarterly_archive_hint(kdev / "踩坑日志.md", "踩坑日志.md")
    if line:
        hints.append(f"  - {line}")

    line = check_quarterly_archive_hint(kdev / "决策日志.md", "决策日志.md")
    if line:
        hints.append(f"  - {line}")

    return "\n".join(hints) + ("\n" if hints else "")
