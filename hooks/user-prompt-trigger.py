#!/usr/bin/env python3
"""ieidev-memory UserPromptSubmit hook（v0.8 转 Python）

用户每次发 prompt 时，扫 .ieidev/memory/ 里的 triggers 字段，匹配命中就注入
<ieidev-memory-recall> 提示给 Claude。渐进式披露（只给编号+标题+路径）。

本脚本是薄壳，核心逻辑在 hooks/lib/trigger-match.py。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"

# 把 lib 加到 sys.path 让 import 找到 migrate
sys.path.insert(0, str(LIB_DIR))

from migrate import ieidev_memory_migrate  # noqa: E402


SUPPRESS = json.dumps({"continue": True, "suppressOutput": True})


def main() -> int:
    # 防御性迁移
    ieidev_memory_migrate()

    # stdin 必须有内容
    if sys.stdin.isatty():
        print(SUPPRESS)
        return 0

    try:
        raw = sys.stdin.read()
    except OSError:
        print(SUPPRESS)
        return 0

    if not raw:
        print(SUPPRESS)
        return 0

    # 把 input 原样传给 python 核心
    trigger_match = LIB_DIR / "trigger-match.py"
    try:
        r = subprocess.run(
            [sys.executable, str(trigger_match)],
            input=raw, text=True, capture_output=True, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        print(SUPPRESS)
        return 0

    if r.stdout:
        sys.stdout.write(r.stdout)
    else:
        print(SUPPRESS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
