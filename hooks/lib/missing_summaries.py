"""ieidev-team: 扫描"过去日期有条目但缺对应每日汇总"的共享库（v0.8 转 Python）

被 stop-check.py 和 session-start-brief.py 通过 import 引用。

为什么独立成 lib：Stop hook 的"今天无汇总"规则只看今天，无法覆盖跨天会话场景
（晚上 23:55 干到次日 01:30 不关会话 → SessionEnd 不触发 → 昨天汇总被遗漏）。
这个函数让 Stop 和 SessionStart hook 共用，用纯文件扫描的方式发现被遗漏的过去日期。

数据源：.ieidev/memory/{执行日志,决策日志,踩坑日志,改进建议}.md 里的
"日期：YYYY-MM-DD" 行（skill 定义的标准格式，中文全角冒号）。
判据：日期严格早于今天 且 .ieidev/memory/每日汇总/<date>.md 不存在。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import re
import sys
from datetime import date as _date
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import shared_dir  # noqa: E402


_DATE_RE = re.compile(r"日期：(\d{4}-\d{2}-\d{2})")
_SOURCE_FILES = ["执行日志.md", "决策日志.md", "踩坑日志.md", "改进建议.md"]


def list_missing_past_summaries(
    ieidev_dir: str = ".ieidev/memory",
    today: str = "",
    max_items: int = 5,
) -> str:
    """列出缺失的过去每日汇总（升序，最多 max_items 个最近）。

    返回空格分隔的 YYYY-MM-DD 字符串；无缺失返回空字符串。
    """
    kdev = shared_dir(Path(ieidev_dir))
    if not kdev.is_dir():
        return ""

    if not today:
        today = _date.today().isoformat()

    # 从源文件 grep "日期：YYYY-MM-DD"
    dates: set = set()
    for filename in _SOURCE_FILES:
        path = kdev / filename
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _DATE_RE.finditer(text):
            dates.add(m.group(1))

    if not dates:
        return ""

    daily_dir = kdev / "每日汇总"
    missing: List[str] = []
    for d in dates:
        # YYYY-MM-DD 字典序等价于时间序
        if d < today and not (daily_dir / f"{d}.md").is_file():
            missing.append(d)

    if not missing:
        return ""

    missing_sorted = sorted(set(missing))[-max_items:]
    return " ".join(missing_sorted)
