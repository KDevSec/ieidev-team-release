#!/usr/bin/env python3
"""ieidev-memory PreCompact hook（v0.8 转 Python，逻辑沿用 v0.7）

会话即将被压缩时触发。此时 Claude 仍有完整上下文。

行为：
  1. 总是写 .ieidev/memory/checkpoints/压缩前-YYYY-MM-DD-HHMMSS.md
     内容 = 今日核心文件原文复制 + 工作区 porcelain
  2. 执行日志今天空 + 工作区有变更 → checkpoint 加"⚠️ 未落盘"警告区块
  3. 顺手清理 7 天前的旧 checkpoint
  4. stdout 软提醒
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from _utf8 import force_utf8_stdio  # noqa: E402
force_utf8_stdio()  # Windows GBK 兼容：v0.8.1+ 统一处理 emoji 编码（pre-compact 软提醒虽暂无 emoji，预防未来 reminders 含 emoji）

from migrate import ieidev_memory_migrate  # noqa: E402
from checkpoint import prune_old_checkpoints  # noqa: E402
from scope import shared_dir  # noqa: E402


def _read_trigger() -> str:
    if sys.stdin.isatty():
        return "auto"
    try:
        raw = sys.stdin.read()
    except OSError:
        return "auto"
    if not raw:
        return "auto"
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return "auto"
    return data.get("trigger") or "auto"


def _git_porcelain() -> str:
    try:
        in_repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return ""
    if in_repo.returncode != 0:
        return ""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout.rstrip("\n")


def main() -> int:
    ieidev_memory_migrate()

    ieidev_dir = Path(".ieidev/memory")
    if not ieidev_dir.is_dir():
        return 0

    shared = shared_dir(ieidev_dir)
    trigger = _read_trigger()
    today = date.today().isoformat()
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")

    checkpoint_dir = ieidev_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = checkpoint_dir / f"压缩前-{timestamp}.md"

    # 判断"是否未落盘"
    log_file = shared / "执行日志.md"
    log_empty_today = True
    if log_file.is_file():
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        log_empty_today = today not in text

    porcelain = _git_porcelain()

    # 拼 checkpoint 内容
    parts: List[str] = []
    parts.append(f"# 压缩前快照 — {timestamp}")
    parts.append("")
    parts.append(f"**触发方式**：{trigger} （auto=自动压缩 / manual=用户 /compact）")
    parts.append("**生成时机**：PreCompact hook，会话即将被压缩")
    parts.append("**主要用途**：压缩后 Claude 上下文会丢失细节，此文件保留原始信号。")
    parts.append("")

    if log_empty_today and porcelain:
        parts.extend([
            "## ⚠️ 未落盘警告",
            "",
            f"**执行日志今天（{today}）无任何条目**，但工作区存在未提交变更。",
            "说明本会话的工作单元（Step）未实时落盘。请压缩后优先：",
            "",
            '1. 读本文件的"工作区快照"区块',
            f"2. 回忆对应的 Step，追加到 `{log_file}`",
            "3. 补记完成后删除本 checkpoint",
            "",
        ])

    parts.extend([
        "## 工作区快照（git status --porcelain）",
        "",
        "```",
        porcelain if porcelain else "(工作区干净)",
        "```",
        "",
    ])

    for src_name in ("执行日志.md", "决策日志.md", "踩坑日志.md", "改进建议.md", "当前状态.md"):
        src = shared / src_name
        if not src.is_file():
            continue
        parts.extend([
            f"## 📋 {src_name} 原文（压缩前快照）",
            "",
            "```markdown",
        ])
        try:
            parts.append(src.read_text(encoding="utf-8").rstrip("\n"))
        except OSError:
            parts.append("(读取失败)")
        parts.extend(["```", ""])

    today_summary = shared / "每日汇总" / f"{today}.md"
    if today_summary.is_file():
        parts.extend([
            f"## 📅 今日汇总（{today}）原文",
            "",
            "```markdown",
        ])
        try:
            parts.append(today_summary.read_text(encoding="utf-8").rstrip("\n"))
        except OSError:
            parts.append("(读取失败)")
        parts.extend(["```", ""])

    parts.extend([
        "---",
        "",
        "_本文件由 ieidev-memory PreCompact hook 自动生成。_",
        "_retention：7 天后自动清理，如需长期保留请手工 mv 出 checkpoints/ 目录。_",
    ])

    try:
        checkpoint_file.write_text("\n".join(parts) + "\n", encoding="utf-8")
    except OSError:
        return 0

    # 7 天 retention
    prune_old_checkpoints(checkpoint_dir, days=7)

    # 软提醒
    sys.stdout.write(f"[ieidev-memory] 会话即将压缩。已写 checkpoint：{checkpoint_file}\n")
    sys.stdout.write(
        "[ieidev-memory] 压缩后若需回忆细节，可 Read 此文件。"
        "如本会话有 Step/决策/踩坑未落盘，请**现在就**追加到 .ieidev/memory/ 对应文件。\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
