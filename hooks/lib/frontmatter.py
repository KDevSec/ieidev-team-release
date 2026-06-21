"""ieidev-memory frontmatter 解析公共库（v0.8 转 Python）

被 session-start-brief.py 通过 import 引用。

从 .ieidev/memory/当前状态.md 的 YAML frontmatter 提取结构化字段：
  phase / iteration / current_step / last_updated / pending_decisions / unresolved_gotchas

最低 Python 版本：3.7。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import shared_dir  # noqa: E402


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _resolve_state_file() -> Optional[Path]:
    """scoped → shared/当前状态.md；flat → .ieidev/memory/当前状态.md；再 fallback 0.2.0 遗留。"""
    scoped = shared_dir(Path(".ieidev/memory")) / "当前状态.md"
    if scoped.is_file():
        return scoped
    flat = Path(".ieidev/memory/当前状态.md")
    if flat.is_file():
        return flat
    legacy = Path(".ieidev/当前状态.md")
    if legacy.is_file():
        return legacy
    return None


def read_state_field(field: str) -> str:
    """读 frontmatter 里指定字段的值（标量）。

    若文件不存在 / 无 frontmatter / 字段缺失 → 返回空字符串。
    去除两端引号（单/双）。
    """
    state = _resolve_state_file()
    if state is None:
        return ""

    try:
        content = state.read_text(encoding="utf-8")
    except OSError:
        return ""

    m = _FM_RE.match(content)
    if not m:
        return ""

    fm = m.group(1)
    prefix = f"{field}:"
    for line in fm.split("\n"):
        line = line.rstrip()
        if line.startswith(prefix):
            val = line[len(prefix):].strip()
            # 去两端引号
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            return val
    return ""


def has_state_frontmatter() -> bool:
    """判断 .ieidev/memory/当前状态.md 是否带 frontmatter。"""
    state = _resolve_state_file()
    if state is None:
        return False
    try:
        first_line = state.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return False
    return first_line.strip() == "---"
