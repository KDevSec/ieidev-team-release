"""ieidev-memory checkpoint 公共库（v0.8 转 Python）

提供 PreCompact 写盘的 retention 逻辑，避免 .ieidev/memory/checkpoints/ 无限膨胀。
被 pre-compact-check.py 通过 import 引用。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import time
from pathlib import Path


def prune_old_checkpoints(dir_path: Path, days: int = 7) -> None:
    """清理指定目录下超过 N 天的 checkpoint 文件（仅扫 ``压缩前-*.md``）。

    幂等、只读其他文件；失败静默（不阻断 hook）。
    """
    if not dir_path.is_dir():
        return
    cutoff = time.time() - days * 86400
    for p in dir_path.iterdir():
        if not p.is_file():
            continue
        if not p.name.startswith("压缩前-") or not p.name.endswith(".md"):
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass  # 权限/竞态等失败不阻断
