"""ieidev-memory 自动迁移：.ieidev/* → .ieidev/memory/*（v0.8 转 Python）

v0.3.0 目录结构重构：所有 ieidev-memory 产物搬到 .ieidev/memory/ 子目录，
给 .ieidev/ 根目录腾出来作为插件命名空间（未来其他插件可建自己的子目录，
如 .ieidev/commit/、.ieidev/triggers/ 等）。

调用时机：每个 hook 启动时调一次 ``ieidev_memory_migrate()``，O(1) 检查，
已迁移直接返回。对新项目也做正确的事（只建目录，不搬文件）。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import shutil
from datetime import date as _date
from pathlib import Path
from typing import List


_LEGACY_MARKERS = [
    "执行日志.md",
    "决策日志.md",
    "踩坑日志.md",
    "当前状态.md",
    "每日汇总",
    "方法论铁规.md",
    "改进建议.md",
    "strict",
    "checkpoints",
]

_MIGRATE_ITEMS = [
    "当前状态.md",
    "决策日志.md",
    "踩坑日志.md",
    "执行日志.md",
    "每日汇总",
    "改进建议.md",
    "方法论铁规.md",
    "strict",
    "checkpoints",
]


def ieidev_memory_migrate() -> None:
    """执行迁移（幂等）。失败静默（迁移是"尽力而为"）。"""
    ieidev_dir = Path(".ieidev")
    new_dir = ieidev_dir / "memory"

    # 无 .ieidev/ 目录 → 无需迁移
    if not ieidev_dir.is_dir():
        return

    # 已有 .ieidev/memory/ → 已迁移（热路径必须快）
    if new_dir.is_dir():
        return

    # 检测 0.2.0 遗留
    has_legacy = any((ieidev_dir / m).exists() for m in _LEGACY_MARKERS)
    if not has_legacy:
        # WARN-*.md 也算遗留
        has_legacy = any(p.name.startswith("WARN-") and p.suffix == ".md" for p in ieidev_dir.iterdir() if p.is_file())

    # 无遗留 → 只建目录
    if not has_legacy:
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return

    # ===== 执行迁移 =====
    try:
        new_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return  # 创建目录失败 → fallback 双轨模式

    migrated: List[str] = []
    failed: List[str] = []

    for item in _MIGRATE_ITEMS:
        src = ieidev_dir / item
        if not src.exists():
            continue
        dst = new_dir / item
        try:
            shutil.move(str(src), str(dst))
            migrated.append(item)
        except OSError:
            failed.append(item)

    # WARN-*.md 单独处理
    for warn in list(ieidev_dir.iterdir()):
        if not (warn.is_file() and warn.name.startswith("WARN-") and warn.name.endswith(".md")):
            continue
        try:
            shutil.move(str(warn), str(new_dir / warn.name))
            migrated.append(warn.name)
        except OSError:
            failed.append(warn.name)

    # 写 MIGRATED-YYYY-MM-DD.md 说明文件
    today = _date.today().isoformat()
    notice = ieidev_dir / f"MIGRATED-{today}.md"
    lines: List[str] = [
        f"# ieidev-memory 目录结构迁移：{today}",
        "",
        "v0.3.0 把所有 ieidev-memory 产物迁到 `.ieidev/memory/` 子目录。",
        "",
        "**为什么**：`.ieidev/` 根目录变成插件命名空间。未来其他插件",
        "（ieidev-commit、ieidev-triggers 等）可以建自己的子目录，互不干扰。",
        "",
        "## 已迁移",
        "",
    ]
    if migrated:
        for item in migrated:
            lines.append(f"- `.ieidev/{item}` → `.ieidev/memory/{item}`")
    else:
        lines.append("_（本次无文件搬移，只建了目录）_")

    if failed:
        lines.extend([
            "",
            "## ⚠️ 迁移失败（保持原位置，请手动处理）",
            "",
        ])
        for item in failed:
            lines.append(f"- `.ieidev/{item}`（权限不足或路径冲突）")
        lines.extend([
            "",
            "如果你看到这段，说明上面这几个文件没搬成。可手工 `mv` 过去，或向插件作者反馈。",
        ])

    lines.extend([
        "",
        "---",
        "",
        "本文件由 ieidev-memory migrate hook 自动生成。处理完可随时删除。",
    ])

    try:
        notice.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass
