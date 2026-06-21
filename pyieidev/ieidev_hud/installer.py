"""ieidev_hud/installer.py — OMC 式一行装机的「决策核」（纯函数 + 薄 CLI，可单测）。

install.sh 是编排壳（驱动 `claude plugin ...` CLI + HUD setup）；**幂等判定逻辑**集中在本
模块的纯函数里，对着 `claude plugin marketplace list --json` / `claude plugin list --json` 的
输出做"在不在"的判断，避免在 shell 里手撕 JSON、也避免直接写 CC 内部配置文件
（known_marketplaces.json / installed_plugins.json 版本脆——见报告风险段）。

设计同 setup.py：核心逻辑是纯函数（吃字符串、吐结构），CLI 只做 stdin→函数→stdout/exit-code
的转接，故 shell 侧能 `python3 -m ieidev_hud.installer <subcmd>` 拿到 0/1 判定，全程可对
mock 配置目录 + mock `claude` 二进制做 TDD。
"""
from __future__ import annotations

import json
import sys

# marketplace.json 的 name 字段 = ieidev；plugin.json 的 name = ieidev-team。
# 故安装目标是 ieidev-team@ieidev（plugin@marketplace）。
MARKETPLACE_NAME = "ieidev"
PLUGIN_NAME = "ieidev-team"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"

# `claude plugin marketplace add <source>`：默认 GitHub repo 简写；可被环境/参数覆盖成本地路径。
DEFAULT_MARKETPLACE_SOURCE = "KDevSec/ieidev-team"


def _loads_array(raw: str) -> list:
    """把 `claude ... list --json` 的输出解析成 list；空/坏数据一律当空 list（保守，宁可重跑幂等步）。"""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def marketplace_present(list_json: str, name: str = MARKETPLACE_NAME) -> bool:
    """`marketplace list --json` 里有没有 name==<name> 的条目。"""
    for entry in _loads_array(list_json):
        if isinstance(entry, dict) and entry.get("name") == name:
            return True
    return False


def plugin_present(list_json: str, plugin_id: str = PLUGIN_ID) -> bool:
    """`plugin list --json` 里有没有 id==<plugin_id> 的条目（已装即跳过 install）。"""
    for entry in _loads_array(list_json):
        if isinstance(entry, dict) and entry.get("id") == plugin_id:
            return True
    return False


def plugin_install_path(list_json: str, plugin_id: str = PLUGIN_ID) -> str | None:
    """取已装插件的 installPath（shell 用它定位 pyieidev/ 跑 HUD setup + 验证）。"""
    for entry in _loads_array(list_json):
        if isinstance(entry, dict) and entry.get("id") == plugin_id:
            p = entry.get("installPath")
            return p if isinstance(p, str) and p.strip() else None
    return None


def marketplace_add_argv(source: str = DEFAULT_MARKETPLACE_SOURCE) -> list[str]:
    """注册 marketplace 的 claude argv（文档化稳健路径，非手写 known_marketplaces.json）。"""
    return ["plugin", "marketplace", "add", source]


def plugin_install_argv(plugin_id: str = PLUGIN_ID, scope: str = "user") -> list[str]:
    """装插件的 claude argv。scope 默认 user（与 `claude plugin install` 默认一致）。"""
    return ["plugin", "install", plugin_id, "--scope", scope]


# ── 薄 CLI：供 install.sh 调用，吃 stdin（list --json），靠 exit-code 表达"在/不在" ──
# 约定：present → exit 0；absent → exit 1（shell `if python3 ...; then 跳过; else 做; fi`）。

def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except (OSError, ValueError):
        return ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write("usage: installer <marketplace-present|plugin-present|plugin-path|marketplace-name|plugin-id|marketplace-source>\n")
        return 2
    cmd = args[0]

    if cmd == "marketplace-present":
        return 0 if marketplace_present(_read_stdin()) else 1
    if cmd == "plugin-present":
        return 0 if plugin_present(_read_stdin()) else 1
    if cmd == "plugin-path":
        p = plugin_install_path(_read_stdin())
        if p is None:
            return 1
        sys.stdout.write(p)
        return 0
    if cmd == "marketplace-name":
        sys.stdout.write(MARKETPLACE_NAME)
        return 0
    if cmd == "plugin-id":
        sys.stdout.write(PLUGIN_ID)
        return 0
    if cmd == "marketplace-source":
        sys.stdout.write(DEFAULT_MARKETPLACE_SOURCE)
        return 0

    sys.stderr.write(f"unknown subcommand: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
