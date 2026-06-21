"""ieidev_hud/setup.py — statusLine 幂等合并引擎（纯函数、可单测）。

把 Claude Code statusLine 配置写入 settings.json，不破坏已有键。
支持：创建新文件 / 无缝添加 / 幂等刷新自身 / 跳过他者 / --force 覆盖并备份。
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class SetupError(Exception):
    """settings.json 操作失败（格式错误等），原文件未改动。"""


def resolve_plugin_root() -> Path:
    """返回含 ieidev_hud/ 包的插件根目录。

    优先读 CLAUDE_PLUGIN_ROOT 环境变量（集成测试 / 打包场景注入）；
    否则以本文件的父目录的父目录为准（即 ieidev-hud/ 项目根）。
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_val:
        return Path(env_val)
    return Path(__file__).resolve().parent.parent


def build_statusline_command(plugin_root: Path) -> str:
    """构造写入 statusLine.command 的字符串。

    形如：python3 "/abs/ieidev_hud/__main__.py" statusline --workspace ${workspaceFolder}
    脚本路径带双引号（防路径含空格）；${workspaceFolder} 是 CC 模板变量，照原样写入。
    """
    main_py = plugin_root / "ieidev_hud" / "__main__.py"
    return f'python3 "{main_py}" statusline --workspace ${{workspaceFolder}}'


def is_kdev_statusline(statusline) -> bool:
    """判断 statusLine 值是否属于本插件写入的条目。"""
    if not statusline:
        return False
    if isinstance(statusline, str):
        return "ieidev_hud" in statusline
    if isinstance(statusline, dict):
        cmd = statusline.get("command")
        return isinstance(cmd, str) and "ieidev_hud" in cmd
    return False


def resolve_settings_path(scope: str, workspace=None) -> Path:
    """把 scope（'user'|'project'）解析成 settings.json 的绝对路径。"""
    if scope == "user":
        return Path.home() / ".claude" / "settings.json"
    return Path(workspace) / ".claude" / "settings.json"


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


DEFAULT_REFRESH_INTERVAL = 10  # 秒；后台 subagent 跑 flow 时主会话空闲也按 timer 刷 HUD


def install_statusline(
    settings_path: Path,
    command: str,
    *,
    force: bool = False,
    refresh_interval: int = DEFAULT_REFRESH_INTERVAL,
) -> dict:
    """幂等地把 statusLine 合并进 settings.json。

    返回 {"action": str, "path": str, "backup": str|None}。
    action ∈ created / updated / skipped_foreign / forced。

    不存在 → 建文件写入。
    存在无 statusLine → 合并添加（保留原键）。
    存在本插件 statusLine → 原位刷新（幂等）。
    存在他者 statusLine + force=False → 不动，返回 skipped_foreign。
    存在他者 statusLine + force=True → 备份原文件再覆盖。

    refresh_interval：写进 payload 的 `refreshInterval`（秒）。CC 文档要求最小为 1，
    传 <1 自动夹到 1。让后台子 agent 跑 flow 改变 git/状态时主会话空闲也按 timer 刷新
    状态栏（OMC 缓存包装器的等效、且是 CC 原生支持的字段，无需自建 wrapper）。
    """
    refresh_interval = max(1, int(refresh_interval))
    payload = {"type": "command", "command": command, "refreshInterval": refresh_interval}

    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _write(settings_path, {"statusLine": payload})
        return {"action": "created", "path": str(settings_path), "backup": None}

    raw = settings_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        raise SetupError(f"settings.json 不是合法 JSON，未改动：{e}") from e

    if not isinstance(data, dict):
        raise SetupError("settings.json 顶层不是 JSON 对象，未改动")

    existing = data.get("statusLine")

    if existing is None:
        data["statusLine"] = payload
        _write(settings_path, data)
        return {"action": "created", "path": str(settings_path), "backup": None}

    if is_kdev_statusline(existing):
        data["statusLine"] = payload  # 幂等刷新自己的路径
        _write(settings_path, data)
        return {"action": "updated", "path": str(settings_path), "backup": None}

    # 他者 statusLine
    if not force:
        return {"action": "skipped_foreign", "path": str(settings_path), "backup": None}

    backup_path = settings_path.parent / (settings_path.name + ".bak")  # settings.json.bak
    backup_path.write_text(raw, encoding="utf-8")  # 原样备份
    data["statusLine"] = payload
    _write(settings_path, data)
    return {"action": "forced", "path": str(settings_path), "backup": str(backup_path)}
