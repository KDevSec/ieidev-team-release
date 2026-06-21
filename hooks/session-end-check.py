#!/usr/bin/env python3
"""ieidev-memory SessionEnd hook（v0.8 转 Python，逻辑沿用 v0.7 mtime 机制）

会话真正结束时的兜底：用 mtime 比对替代 git status。
检测 .ieidev/memory/ 下有无比 .last-flush 更新的文件 → 若有则写 WARN。
v0.7 立场反转后 .ieidev/ 默认 gitignore，git status 拿不到 .ieidev/ 变化，必须换机制。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from migrate import ieidev_memory_migrate  # noqa: E402
from scope import shared_dir  # noqa: E402


def _find_newer(ieidev_dir: Path, flush_file: Path, max_items: int = 20) -> List[str]:
    """跨平台等价 ``find $IEIDEV_DIR -newer $FLUSH_FILE -type f``。

    排除 .last-flush / WARN-未记录-* / checkpoints / state。
    """
    try:
        flush_mtime = flush_file.stat().st_mtime
    except OSError:
        return []

    results: List[str] = []
    for p in ieidev_dir.rglob("*"):
        if not p.is_file():
            continue
        # 排除项
        if p.name == ".last-flush":
            continue
        if p.name.startswith("WARN-未记录-"):
            continue
        # checkpoints / state 子目录
        rel_parts = p.relative_to(ieidev_dir).parts
        if "checkpoints" in rel_parts or "state" in rel_parts:
            continue

        try:
            if p.stat().st_mtime > flush_mtime:
                results.append(str(p))
                if len(results) >= max_items:
                    break
        except OSError:
            continue

    return results


def _git_porcelain_kdev() -> List[str]:
    """v0.6 fallback：git status --porcelain -uall 过滤 .ieidev/memory/ 路径。"""
    try:
        in_repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if in_repo.returncode != 0:
        return []

    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if r.returncode != 0:
        return []

    return [line for line in r.stdout.splitlines() if ".ieidev/memory/" in line]


def main() -> int:
    ieidev_memory_migrate()

    ieidev_dir = Path(".ieidev/memory")
    if not ieidev_dir.is_dir():
        return 0

    shared = shared_dir(ieidev_dir)
    today = date.today().isoformat()
    log_file = shared / "执行日志.md"
    flush_file = ieidev_dir / ".last-flush"
    warn_file = ieidev_dir / f"WARN-未记录-{today}.md"

    # 执行日志今天已有条目 → 无需警告
    if log_file.is_file():
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if today in text:
            return 0

    # 检测变化
    if flush_file.is_file():
        changed = _find_newer(ieidev_dir, flush_file)
    else:
        # fallback v0.6 行为
        changed = _git_porcelain_kdev()

    if not changed:
        return 0

    # 写 WARN（覆盖同日旧警告）
    body_lines: List[str] = [
        f"# ⚠️ 未记录警告：{today}",
        "",
        f"会话结束时检测到：**执行日志 ({log_file}) 今天无任何条目**，但 `.ieidev/memory/` 有未落盘的变更。",
        "",
        "下次进入项目时：",
        f"1. 回忆这些变更对应的工作单元（Step），追加到 {log_file}",
        "2. 如有关键决策/踩坑/改进信号，补记到对应的 Q/G/R 日志",
        f"3. 补记完成后 `touch {flush_file}` 重置并 `rm {warn_file}`",
        "",
        "## 比 .last-flush 更新的文件",
        "",
        "```",
    ]
    body_lines.extend(changed)
    body_lines.extend([
        "```",
        "",
        "_本文件由 ieidev-memory SessionEnd hook (v0.8) 自动生成。_",
    ])

    try:
        warn_file.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
