# pyieidev/ieidev_core/gate_pause.py
"""人闸停靠标记（#7 硬停）：goal 到 human_gate/confirm 时写 PAUSED-<gate>，
PreToolUse hook 见标记即拦推进命令；人确认后 clear。纯文件读写、永不抛。"""
import datetime
from pathlib import Path

_PREFIX = "PAUSED-"


def _feature_dir(workspace, slug) -> Path:
    return Path(workspace) / ".ieidev" / "features" / str(slug)


def pause_path(workspace, slug, gate) -> Path:
    return _feature_dir(workspace, slug) / f"{_PREFIX}{gate}"


def write_pause(workspace, slug, gate, reason="") -> Path:
    p = pause_path(workspace, slug, gate)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    p.write_text(f"gate: {gate}\nreason: {reason}\npaused_at: {ts}\n", encoding="utf-8")
    return p


def active_pauses(workspace, slug) -> list:
    d = _feature_dir(workspace, slug)
    if not d.is_dir():
        return []
    return sorted(f.name[len(_PREFIX):] for f in d.glob(f"{_PREFIX}*") if f.is_file())


def is_paused(workspace, slug) -> bool:
    return bool(active_pauses(workspace, slug))


def clear_pause(workspace, slug, gate) -> bool:
    try:
        pause_path(workspace, slug, gate).unlink(missing_ok=True)
        return True
    except OSError:
        return False
