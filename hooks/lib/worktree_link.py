"""ieidev-memory v0.8 worktree-link helper（从 worktree-link.sh 转 Python）

secondary worktree 启动时自动 symlink/junction `.ieidev` → 主 worktree 的 .ieidev/
让所有 worktree 共享同一份记忆（单一真相源）。

被 session-start-brief.py 通过 import 引用。

平台：用 ``pathlib.Path.symlink_to`` 透明跨 Linux/macOS/Windows——
Windows 在 Python 3.8+ 通过 Developer Mode 或在 Win10 1703+ 装管理员权限创建
symlink；失败时 fallback 到 ``cmd /c mklink /J`` 创建 NTFS junction（无需管理员权限）。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _git_query(*args: str) -> Optional[str]:
    """git 子命令，返回 stdout 第一行或 None。"""
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _is_windows_msys() -> bool:
    """检测当前是否运行在 Git-Bash / MSYS / Cygwin 环境（uname -s 含 MINGW/MSYS/CYGWIN）。"""
    s = sys.platform
    if s == "win32":
        # native Windows（Python 不在 git-bash 里）—— 也走 junction 路径
        return True
    if s.startswith("cygwin"):
        return True
    # 通过 uname 判别 MSYS/MINGW（在 git-bash Python 下 sys.platform 可能是 "win32" 或 "cygwin"）
    try:
        sysname = platform.uname().system  # 'MINGW64_NT-...' on git-bash
    except Exception:
        sysname = ""
    return any(prefix in sysname.upper() for prefix in ("MINGW", "MSYS", "CYGWIN"))


def _create_symlink(target: Path, dest: Path) -> bool:
    """跨平台建 symlink/junction，成功返回 True。

    优先用 os.symlink（Linux/macOS/Windows Developer Mode 都支持）；
    失败 fallback Windows mklink /J。
    """
    if not _is_windows_msys():
        # Linux / macOS：直接 ln -s
        try:
            os.symlink(target, dest, target_is_directory=True)
            return True
        except OSError:
            return False

    # Windows：尝试 os.symlink（Developer Mode 下可用），失败 fallback junction
    try:
        os.symlink(target, dest, target_is_directory=True)
        return True
    except OSError:
        pass

    # Fallback: cmd /c mklink /J（NTFS junction，无需管理员权限）
    target_win = str(target)
    dest_win = str(dest)
    try:
        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", dest_win, target_win],
            capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except (OSError, FileNotFoundError):
        return False


def worktree_link_kdev() -> None:
    """secondary worktree 启动时自动建 .ieidev → 主 worktree/.ieidev/ 的 link。

    跳过条件：
      - 不在 git 仓库
      - 主 worktree（git-common-dir == git-dir）
      - 本地已有 .ieidev/（含 symlink/junction）→ 幂等跳过
      - 主 worktree 也无 .ieidev/ → 不强建
    """
    common_dir = _git_query("rev-parse", "--git-common-dir")
    cur_dir = _git_query("rev-parse", "--git-dir")
    if not common_dir or not cur_dir:
        return  # 不在 git 仓库

    # 路径正规化（容忍相对/绝对差异）
    try:
        common_real = Path(common_dir).resolve(strict=False)
        cur_real = Path(cur_dir).resolve(strict=False)
    except OSError:
        return

    # 主 worktree：common == cur，跳过
    if common_real == cur_real:
        return

    # 已有本地 .ieidev/（含 symlink）→ 幂等跳过
    local_kdev = Path(".ieidev")
    if local_kdev.exists() or local_kdev.is_symlink():
        return

    # 主 worktree 根目录 = 主 .git 的父目录
    main_root = common_real.parent
    main_kdev = main_root / ".ieidev"
    if not main_kdev.is_dir():
        return  # 主 worktree 也无 .ieidev/

    if _create_symlink(main_kdev, local_kdev):
        kind = "junction" if _is_windows_msys() else "symlink"
        print(f"[ieidev-memory] secondary worktree → 已自动 {kind} .ieidev → {main_kdev}")
    else:
        print("[ieidev-memory] WARN: 创建 worktree symlink/junction 失败")
        print(f"  手动方案（Windows）：cmd /c mklink /J \"{local_kdev}\" \"{main_kdev}\"")
        print(f"  手动方案（Linux/macOS）：ln -s \"{main_kdev}\" \"{local_kdev}\"")
