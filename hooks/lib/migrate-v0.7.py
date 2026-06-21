#!/usr/bin/env python3
"""ieidev-memory v0.7 软迁移脚本（v0.8 改写为 Python）

把已经被 git tracked 的 .ieidev/ 转成本地过程目录：
  1) .gitignore append .ieidev/（由 init-gitignore.py 负责）
  2) git rm --cached -r .ieidev/（移出 index，保留历史 commit）
  3) 用户手动 commit 这次改动

最低 Python 版本：3.7。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(args: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, **kwargs)


def main() -> int:
    # 1. 是否在 git 仓库
    r = _run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("[ieidev-memory] 当前不在 git 仓库，无需迁移")
        return 0

    # 2. 是否有 .ieidev/ 目录
    if not Path(".ieidev").is_dir():
        print("[ieidev-memory] 当前无 .ieidev/ 目录，跳过")
        return 0

    # 3. 调 init-gitignore.py append .gitignore
    script_dir = Path(__file__).resolve().parent
    init_script = script_dir / "init-gitignore.py"
    init_r = _run(
        [sys.executable, str(init_script)],
        capture_output=False,
    )
    if init_r.returncode != 0:
        print("[ieidev-memory] WARN: init-gitignore.py 退出非 0，请检查", file=sys.stderr)

    # 4. 查 .ieidev/ 是否被 tracked，是则 rm --cached
    tracked = _run(
        ["git", "ls-files", "--error-unmatch", ".ieidev/"],
        capture_output=True, text=True,
    )
    if tracked.returncode == 0:
        print("[ieidev-memory] .ieidev/ 当前被 git tracked，移出 index（保留历史 commit）...")
        _run(
            ["git", "rm", "-r", "--cached", ".ieidev/"],
            capture_output=True, text=True, check=True,
        )
        print("[ieidev-memory] 完成。请 git diff --cached 核对，再 commit：")
        print("")
        print("  git commit -m 'chore: .ieidev/ 转为本地过程目录（ieidev-memory v0.7 立场反转）'")
        print("")
    else:
        print("[ieidev-memory] .ieidev/ 未被 git tracked，无需迁移")

    print("")
    print("[ieidev-memory] v0.7 软迁移完成。docs/ 下的团队级产物保持不变。")
    print("后续沉淀过程→产物用 /ieidev-team:memory-distill；周总结用 /ieidev-team:memory-weekly。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
