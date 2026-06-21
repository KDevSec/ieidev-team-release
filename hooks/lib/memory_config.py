"""ieidev-memory 配置读取（.ieidev/memory/config.yaml）

只支持 stdlib——`yaml` 不是标准库，所以 config.yaml 使用极简子集，
用 line-based parser 解析。未配置 = 视同 hybrid + auto（fail-open）。

字段：
- record_mode: hybrid | inline  —— 落盘路径配置（详见 references/subagent-落盘机制.md）
- distill.mode: auto | manual   —— 蒸馏触发模式（详见 references/蒸馏触发机制.md）
- distill.reminder_days: 7（默认）
- distill.reminder_new_f: 10（默认）
- distill.reminder_new_misalign: 3（默认）
- rating.mode: model-only | user-opt-in | user-required  —— 评分模式（默认 user-opt-in）
- brief.verbosity: compact | normal | verbose  —— SessionStart brief 详略（默认 normal）

支持两种语法：顶层 flat key（`distill_mode: auto`）和一层嵌套（`distill:` + 缩进 `mode: auto`）。
parser 内部统一用 dot notation 存储（`distill.mode`）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

RecordMode = Literal["hybrid", "inline"]
VALID_RECORD_MODES: tuple[RecordMode, ...] = ("hybrid", "inline")

DistillMode = Literal["auto", "manual"]
VALID_DISTILL_MODES: tuple[DistillMode, ...] = ("auto", "manual")

RatingMode = Literal["model-only", "user-opt-in", "user-required"]
VALID_RATING_MODES: tuple[RatingMode, ...] = ("model-only", "user-opt-in", "user-required")
DEFAULT_RATING_MODE: RatingMode = "user-opt-in"

BriefVerbosity = Literal["compact", "normal", "verbose"]
VALID_BRIEF_VERBOSITY: tuple[BriefVerbosity, ...] = ("compact", "normal", "verbose")
DEFAULT_BRIEF_VERBOSITY: BriefVerbosity = "normal"

# 蒸馏触发阈值默认值（详见 references/蒸馏触发机制.md）
DEFAULT_DISTILL_REMINDER_DAYS = 7
DEFAULT_DISTILL_REMINDER_NEW_F = 10
DEFAULT_DISTILL_REMINDER_NEW_MISALIGN = 3


def _parse_kv_yaml(text: str) -> dict[str, str]:
    """极简 YAML 子集 parser。

    支持：
    - 顶层 `key: value`
    - 一层嵌套 `parent:` + 后续缩进行 `  child: value`（统一存为 `parent.child`）
    - 顶层 flat key（含 `_` 或 `.`）也接受（`distill.mode: auto` / `distill_mode: auto`）
    - 注释 `#` / 空行忽略
    - 不支持列表、多行字符串、深嵌套

    返回 flat dict，嵌套 key 用 dot notation。
    """
    result: dict[str, str] = {}
    current_parent: str | None = None  # 当前打开的 parent block

    for raw in text.splitlines():
        # 去掉行尾注释（但保留 # 在 value 内部的情况——简化版直接砍）
        line = raw.split("#", 1)[0].rstrip()

        if not line:
            # 空行不立即关闭 parent block（用户可能在 block 内空格）
            continue

        # 是否缩进行
        is_indented = line[0] in (" ", "\t")
        stripped = line.lstrip()

        if ":" not in stripped:
            # 不是 key:value，关闭 parent block
            current_parent = None
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not key:
            current_parent = None
            continue

        if is_indented:
            # 缩进行：作为 current_parent 的子字段
            if current_parent is not None:
                result[f"{current_parent}.{key}"] = value
            # 没有 parent 的缩进行直接忽略（malformed yaml）
        else:
            # 顶层行
            if value:
                # 顶层 key: value（flat key 可能含 `.`）
                result[key] = value
                current_parent = None
            else:
                # 顶层 key: （无 value）= 打开 parent block
                current_parent = key

    return result


def _read_config(ieidev_dir: Path | str) -> dict[str, str]:
    """读 .ieidev/memory/config.yaml 并 parse。文件不存在 / 读错都返回空 dict。"""
    config_path = Path(ieidev_dir) / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return _parse_kv_yaml(text)


def read_record_mode(ieidev_dir: Path | str = ".ieidev/memory") -> RecordMode:
    """读 record_mode 字段。未配置 / 非法值 → hybrid。"""
    config = _read_config(ieidev_dir)
    value = config.get("record_mode", "").lower()
    if value in VALID_RECORD_MODES:
        return value  # type: ignore[return-value]
    return "hybrid"


def read_distill_mode(ieidev_dir: Path | str = ".ieidev/memory") -> DistillMode:
    """读 distill.mode 字段。未配置 / 非法值 → auto（默认开启自动模式）。

    用户拍板 (2026-05-16)：自动模式是默认，符合"opt-out 比 opt-in 摩擦小"原则。
    用户不想自动跑就写 `distill.mode: manual` 或 `distill_mode: manual`。
    """
    config = _read_config(ieidev_dir)
    # 兼容 flat key 和嵌套 key
    value = (config.get("distill.mode") or config.get("distill_mode") or "").lower()
    if value in VALID_DISTILL_MODES:
        return value  # type: ignore[return-value]
    return "auto"


def read_rating_mode(ieidev_dir: Path | str = ".ieidev/memory") -> RatingMode:
    """读 rating.mode 字段。未配置 / 非法值 → user-opt-in（插件默认，温和）。

    承 Q-002：本项目 config 写 `rating.mode: model-only`（机读化"用户不再评分"决策）。
    兼容 flat dot-key（`rating.mode`）、嵌套（`rating:` + `mode:`）、下划线（`rating_mode`）。
    """
    config = _read_config(ieidev_dir)
    value = (config.get("rating.mode") or config.get("rating_mode") or "").lower()
    if value in VALID_RATING_MODES:
        return value  # type: ignore[return-value]
    return DEFAULT_RATING_MODE


def rating_mode_configured(ieidev_dir: Path | str = ".ieidev/memory") -> bool:
    """config 是否显式写了 rating.mode 键（用于 brief 首次提示判断）。"""
    config = _read_config(ieidev_dir)
    return ("rating.mode" in config) or ("rating_mode" in config)


def read_brief_verbosity(ieidev_dir: Path | str = ".ieidev/memory") -> BriefVerbosity:
    """读 brief.verbosity 字段。未配置 / 非法值 → normal（现行行为）。

    compact 只注入 WARN + pending_decisions + 今日进度一行，其余写 brief-detail.md；
    verbose 全量（不截断半残清单）。
    """
    config = _read_config(ieidev_dir)
    value = (config.get("brief.verbosity") or config.get("brief_verbosity") or "").lower()
    if value in VALID_BRIEF_VERBOSITY:
        return value  # type: ignore[return-value]
    return DEFAULT_BRIEF_VERBOSITY


def _read_int_default(config: dict[str, str], keys: tuple[str, ...], default: int) -> int:
    """从 config 按 key 顺序取整数；解析失败返回 default。"""
    for key in keys:
        if key in config:
            try:
                return int(config[key])
            except (ValueError, TypeError):
                return default
    return default


def read_distill_thresholds(ieidev_dir: Path | str = ".ieidev/memory") -> dict[str, int]:
    """读三个触发阈值：reminder_days / reminder_new_f / reminder_new_misalign。

    返回 dict 含三个整数字段。未配置项用默认值。
    """
    config = _read_config(ieidev_dir)
    return {
        "reminder_days": _read_int_default(
            config,
            ("distill.reminder_days", "distill_reminder_days"),
            DEFAULT_DISTILL_REMINDER_DAYS,
        ),
        "reminder_new_f": _read_int_default(
            config,
            ("distill.reminder_new_f", "distill_reminder_new_f"),
            DEFAULT_DISTILL_REMINDER_NEW_F,
        ),
        "reminder_new_misalign": _read_int_default(
            config,
            ("distill.reminder_new_misalign", "distill_reminder_new_misalign"),
            DEFAULT_DISTILL_REMINDER_NEW_MISALIGN,
        ),
    }


def main() -> int:
    """CLI：打印当前项目的 record_mode（旧兼容用法）。

    --all 打印所有 config 字段 JSON。
    """
    import json
    import sys
    args = sys.argv[1:]
    kdev = ".ieidev/memory"
    show_all = False
    for arg in args:
        if arg == "--all":
            show_all = True
        else:
            kdev = arg

    if show_all:
        out = {
            "record_mode": read_record_mode(kdev),
            "distill_mode": read_distill_mode(kdev),
            **read_distill_thresholds(kdev),
            "rating_mode": read_rating_mode(kdev),
            "brief_verbosity": read_brief_verbosity(kdev),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(read_record_mode(kdev))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
