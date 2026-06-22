"""本机 registry —— 把用过数字员工的项目/feature 登记到 ~/.ieidev-team/registry.json。

机器本地、原子读写、并发安全（fcntl 串行化 read-modify-write）。零 ieidev_core 依赖。
团队同步是 phase-2：本期只埋 owner = git email + "@" + hostname。
"""
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path

try:
    import fcntl                     # Linux/mac：串行化并发 read-modify-write
except ImportError:                  # Windows 降级：仅靠原子 replace（单机 MVP 可接受）
    fcntl = None


def registry_home() -> Path:
    env = os.environ.get("IEIDEV_TEAM_HOME")
    return Path(env) if env else Path.home() / ".ieidev-team"


def registry_path() -> Path:
    return registry_home() / "registry.json"


def _git_email():
    try:
        out = subprocess.run(["git", "config", "user.email"],
                             capture_output=True, text=True, timeout=3)
        v = out.stdout.strip()
        return v or None
    except (OSError, subprocess.SubprocessError):
        return None


def owner_id(*, email=None, host=None) -> str:
    e = email or _git_email() or "unknown"
    h = host or socket.gethostname() or "unknown"
    return f"{e}@{h}"


def read_registry() -> dict:
    path = registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": []}
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return {"entries": []}
    return data


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)        # 原子替换
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def register(workspace, slug, *, display_name, employee, owner, status, ts) -> dict:
    ws = str(Path(workspace).resolve())
    entry = {"workspace": ws, "slug": slug, "display_name": display_name,
             "employee": employee, "owner": owner, "status": status, "ts": ts}
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / "registry.lock"
    lock = open(lock_path, "w")
    try:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_registry()
        data["entries"] = [e for e in data["entries"]
                           if not (e.get("workspace") == ws and e.get("slug") == slug)]
        data["entries"].append(entry)
        _atomic_write(path, data)
    finally:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return entry


def _entry_key(entry) -> str:
    return f"{entry.get('workspace')}::{entry.get('slug')}"


def workspace_exists(entry) -> bool:
    ws = entry.get("workspace")
    slug = entry.get("slug")
    if not ws or not slug:
        return False
    return (Path(ws) / ".ieidev" / "features" / slug).exists()


def mark_stale() -> dict:
    data = read_registry()
    stale = [_entry_key(e) for e in data["entries"] if not workspace_exists(e)]
    return {"entries": data["entries"], "stale_keys": stale}


def prune() -> int:
    path = registry_path()
    lock_path = path.parent / "registry.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = open(lock_path, "w")
    try:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        data = read_registry()
        keep = [e for e in data["entries"] if workspace_exists(e)]
        removed = len(data["entries"]) - len(keep)
        if removed:
            _atomic_write(path, {"entries": keep})
        return removed
    finally:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
