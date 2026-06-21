#!/usr/bin/env python3
"""ieidev-memory PostToolUse hook（v0.8 转 Python）

Claude 每次 Write/Edit/MultiEdit/NotebookEdit 命中里程碑白名单时注入一条软提醒：
"刚动了里程碑文件 X，请把对应 Step 追加到 .ieidev/memory/执行日志.md"

白名单在 hooks/lib/milestone.py 中维护（覆盖 Spec Kit、ADR、迭代/Sprint、架构/PRD/
设计、根目录关键文档、数据库 migration、OpenAPI/GraphQL/Proto 契约等）。

v0.7 联动：写入 .ieidev/memory/* 时 touch .last-flush（与 SessionEnd mtime 机制配合）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from migrate import ieidev_memory_migrate  # noqa: E402
from milestone import is_milestone_path  # noqa: E402


def main() -> int:
    ieidev_memory_migrate()

    ieidev_dir = Path(".ieidev/memory")
    if not ieidev_dir.is_dir():
        return 0

    if sys.stdin.isatty():
        return 0

    try:
        raw = sys.stdin.read()
    except OSError:
        return 0
    if not raw:
        return 0

    # 解析 hook input JSON
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    # 绝对路径转相对（便于匹配 specs/ 这种相对前缀）
    cwd = os.getcwd()
    rel_path = file_path
    if file_path.startswith(cwd + os.sep) or file_path.startswith(cwd + "/"):
        rel_path = file_path[len(cwd) + 1:]
    rel_path = rel_path.replace(os.sep, "/")

    # 写入 .ieidev/memory/ → 刷新 .last-flush（mtime 联动 SessionEnd WARN）
    if ".ieidev/memory/" in rel_path or ".ieidev/memory/" in file_path.replace(os.sep, "/"):
        try:
            (ieidev_dir / ".last-flush").touch(exist_ok=True)
        except OSError:
            pass

    if is_milestone_path(rel_path):
        print(
            f"[ieidev-memory] 刚动了里程碑文件 {rel_path} —— "
            f"请把对应的 Step 追加到 .ieidev/memory/执行日志.md"
            f"（说明这次变更的目的、产出、模型自评）。"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
