"""SKILL.md SHA cache + drift detection (R-001 v1 / R-005)。

每个 session 启动时缓存当前 SKILL.md 的 git SHA；之后 SessionStart 再触发时
比对缓存 vs 当前——不等则说明 skill 在会话期间被升级，brief 提醒重启。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_SKILL_RELPATH = "skills/memory/SKILL.md"

# session_id 可能含特殊字符，sanitize 后用作文件名
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize_id(session_id: str) -> str:
    return _SAFE_ID_RE.sub("-", session_id)[:64] or "unknown"


def _cache_path(session_id: str, state_dir: Path) -> Path:
    return state_dir / f"skill-version-cache-{_sanitize_id(session_id)}.json"


def read_cache(session_id: str, state_dir: Path) -> Optional[str]:
    p = _cache_path(session_id, state_dir)
    if not p.is_file():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        sha = data.get("skill_sha")
        return sha if isinstance(sha, str) and sha else None
    except (OSError, ValueError):
        return None


def write_cache(session_id: str, sha: str, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = _cache_path(session_id, state_dir)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"skill_sha": sha}, f)
    os.replace(tmp, p)


def current_skill_sha(
    repo_root: Path,
    skill_relpath: str = DEFAULT_SKILL_RELPATH,
) -> Optional[str]:
    """git log -1 --format=%H -- <skill_relpath>；非 git / 文件无 commit → None。"""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", skill_relpath],
            cwd=str(repo_root), capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return out if out else None


def detect_drift(
    session_id: str,
    repo_root: Path,
    state_dir: Path,
    skill_relpath: str = DEFAULT_SKILL_RELPATH,
) -> Tuple[Optional[str], Optional[str]]:
    """返回 (cached_before_this_call, current)。
    First call: cached=None (no signal) + 写入 current。
    Subsequent: cached=cached_sha, current=current_sha；caller 判 == 决定 drift。
    """
    cached = read_cache(session_id, state_dir)
    current = current_skill_sha(repo_root, skill_relpath)
    if current is not None and cached != current:
        write_cache(session_id, current, state_dir)
    return cached, current
