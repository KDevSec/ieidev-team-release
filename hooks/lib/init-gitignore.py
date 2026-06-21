#!/usr/bin/env python3
"""ieidev-memory v0.8 init-gitignore helper

立场反转后（v0.7+）`.ieidev/` 默认本地过程目录；init 时自动 append `.ieidev/` 到
项目 `.gitignore`。环境变量 `IEIDEV_GIT_TRACK=1` → 跳过（单人项目可选托管模式）。

v0.8 起从 init-gitignore.sh 改写为纯 Python，去除 bash + grep + echo 平台分叉。
最低 Python 版本：3.7（用 `from __future__ import annotations` + typing.X 兼容）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List


MARK_LINE = ".ieidev/"
MARK_COMMENT = "# ieidev-memory v0.7: 本地过程目录，不 git 托管（产物请沉淀到 docs/）"


def main() -> int:
    if os.environ.get("IEIDEV_GIT_TRACK", "0") == "1":
        print("[ieidev-memory] IEIDEV_GIT_TRACK=1，跳过 .gitignore 修改（单人托管模式）")
        return 0

    gitignore = Path(".gitignore")

    if not gitignore.exists():
        gitignore.write_text(f"{MARK_COMMENT}\n{MARK_LINE}\n", encoding="utf-8")
        print(f"[ieidev-memory] 新建 .gitignore 并加入 {MARK_LINE}")
        return 0

    # 已有 .gitignore：只在缺 .ieidev/ 行时追加（幂等）
    lines: List[str] = gitignore.read_text(encoding="utf-8").splitlines()
    if MARK_LINE in lines:
        print(f"[ieidev-memory] .gitignore 已有 {MARK_LINE}，跳过")
        return 0

    # 末尾追加（保留原有内容 + 空行 + 注释 + 行）
    existing = gitignore.read_text(encoding="utf-8")
    suffix = "\n" if existing and not existing.endswith("\n") else ""
    with gitignore.open("a", encoding="utf-8") as f:
        f.write(f"{suffix}\n{MARK_COMMENT}\n{MARK_LINE}\n")
    print(f"[ieidev-memory] 追加 {MARK_LINE} 到 .gitignore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
