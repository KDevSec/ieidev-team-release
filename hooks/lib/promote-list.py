#!/usr/bin/env python3
"""ieidev-memory promote-list（v0.8 改写为 Python）

给 /ieidev-team:memory-distill 命令的 promote 阶段调用：列出 .ieidev/memory/ 下所有
promote_status != done 的条目，附推荐沉淀去向。

历史命令名 /ieidev-memory-promote 已合并到 /ieidev-team:memory-distill（2026-05-15）——
promote（人工挑选 → docs/）和 dataset（全量打包 → .ieidev/memory/dataset/）两步
合一个命令，因为 markdown 既给人看也给机器看。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path
from typing import List, Tuple


SOURCES: List[Tuple[str, str]] = [
    ("改进建议.md", "建议"),
    ("conventions.md", "R-NNN 规则"),
    ("决策日志.md", "Q-NNN"),
    ("踩坑日志.md", "G-NNN"),
    ("执行日志.md", "Step"),
]

RECOMMENDATION_TABLE = """| 来源 | 推荐 docs/ 去向 |
|---|---|
| 改进建议.md | docs/05-报告/实战总结-<项目名>.md 反思章节 |
| conventions.md §11 R-NNN | docs/08-开发规范.md |
| 决策日志.md Q-NNN | docs/04-架构/ADR-NNN.md |
| 踩坑日志.md G-NNN 高频类 | docs/04-架构/踩坑索引.md |
| 执行日志.md Step 4.5+ | docs/05-报告/实战项目总结.md |"""


def days_since_promote(ieidev_dir: Path) -> str:
    """返回距上次 .last-promote touch 的天数（字符串），从未 touch 返回 "never"。"""
    flush = ieidev_dir / ".last-promote"
    if not flush.exists():
        return "never"
    try:
        ft = flush.stat().st_mtime
    except OSError:
        return "never"
    if ft <= 0:
        return "never"
    return str(int((time.time() - ft) // 86400))


def list_pending_entries(md_path: Path, max_items: int = 30) -> List[str]:
    """扫 markdown 文件的 ## 二级标题条目；返回 promote_status != done|skipped 的标题列表（最多 max_items）。"""
    if not md_path.is_file():
        return []
    lines = md_path.read_text(encoding="utf-8").splitlines()

    pending: List[str] = []
    title: str = ""
    status: str = ""

    def flush() -> None:
        if title and status not in ("done", "skipped"):
            actual = status if status else "pending"
            pending.append(f"- {title}  [{actual}]")

    for line in lines:
        if line.startswith("## "):
            flush()
            title = line
            status = ""
        else:
            stripped = line.strip()
            if stripped.startswith("promote_status:"):
                value = stripped.split(":", 1)[1].strip()
                if value in ("done", "skipped", "pending"):
                    status = value
    # last item
    flush()
    return pending[:max_items]


def main() -> int:
    ieidev_dir = Path(".ieidev/memory")
    if not ieidev_dir.is_dir():
        print("[ieidev-memory] 当前项目无 .ieidev/memory/，无候选可沉淀。")
        return 0

    today = date.today().isoformat()
    days = days_since_promote(ieidev_dir)

    print("# /ieidev-team:memory-distill promote 阶段：沉淀候选列表")
    print("")
    print(f"- 扫描时间：{today}")
    print(f"- 距上次沉淀：{days} 天")
    print("")

    for filename, label in SOURCES:
        path = ieidev_dir / filename
        if not path.is_file():
            continue
        print(f"## {label}（{ieidev_dir}/{filename}）")
        print("")
        for entry in list_pending_entries(path):
            print(entry)
        print("")

    print("---")
    print("")
    print("## 推荐沉淀去向")
    print("")
    print(RECOMMENDATION_TABLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
