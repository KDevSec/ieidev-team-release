"""ieidev-memory v0.14 P-C1 一次性迁移：flat `.ieidev/memory/*` → scoped `shared/` + `staff/<id>/`。

⚠️ 手动调用，**不**自动跑（不像 migrate.py），**不**在 kdev-agents 框架仓上跑——
只有多员工 dogfood 工作区需要。幂等：已 scoped（`shared/` 存在）→ 不再搬 markdown，
仅补建缺失的 staff 目录。

只搬 markdown 内容文件；machine-local plumbing（state/ checkpoints/ dataset/ config.yaml
strict .last-*）留 root。复用 ieidev_sync 写 `.ieidev/.gitignore`。

CLI: python3 migrate_scope.py [--staff dev-engineer,req-architect] [--root .ieidev/memory]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date as _date
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import is_scoped  # noqa: E402

# 迁入 shared/ 的 markdown 内容（文件 + 目录）
_SHARED_ITEMS = [
    "执行日志.md",
    "决策日志.md",
    "踩坑日志.md",
    "skill-feedback.md",
    "当前状态.md",
    "改进建议.md",
    "方法论铁规.md",
    "conventions.md",
    "每日汇总",
    "归档",
]

# ⚠️ STALE（P-C2/Q-019）：staff 叙事 scope 已收窄——叙事仅 CEO/shared，员工 = events + handoffs
# （无 per-员工叙事 Step），staff 目录稀疏化为仅 reviewer/cqo（dev/req 机器侧无足迹）。
# 此 DEFAULT_STAFF 仍是旧 P-C1「全家桶」模型，待 P-C2 Phase B/C 重构。
# defer 窗口期勿照此启用 scoped，否则会建出已判死的 dev/req 目录。见 P-C2 spec §8.2 / §0.5。
DEFAULT_STAFF = ["dev-engineer", "req-architect"]


def migrate_to_scoped(
    root: "Path | str",
    staff: List[str] = DEFAULT_STAFF,
    today: str = "",
) -> Dict:
    """flat → scoped 迁移（幂等）。返回 {'migrated': bool, 'moved': [...], 'staff_created': [...]}。"""
    root = Path(root)
    if not today:
        today = _date.today().isoformat()
    result: Dict = {"migrated": False, "moved": [], "failed": [], "staff_created": []}

    if not root.is_dir():
        return result

    def _ensure_staff() -> None:
        for sid in staff:
            d = root / "staff" / sid
            if not d.is_dir():
                d.mkdir(parents=True, exist_ok=True)
                result["staff_created"].append(sid)

    # 已 scoped → 仅补建 staff，不再搬 markdown
    if is_scoped(root):
        _ensure_staff()
        return result

    # 建 shared/ 并搬 markdown
    shared = root / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    for item in _SHARED_ITEMS:
        src = root / item
        if not src.exists():
            continue
        try:
            shutil.move(str(src), str(shared / item))
            result["moved"].append(item)
        except OSError as e:
            result["failed"].append(item)
            print(f"[ieidev-memory] ⚠️ 迁移失败，保持原位：{item}（{e}）", file=sys.stderr)
    result["migrated"] = True

    _ensure_staff()

    # .ieidev/.gitignore（复用 ieidev_sync；root.parent == .ieidev）
    try:
        from ieidev_sync import _ensure_machine_local_gitignore
        _ensure_machine_local_gitignore(root.parent)
    except Exception:
        pass

    # 迁移说明
    notice = root / f"MIGRATED-scope-{today}.md"
    lines = [
        f"# ieidev-memory P-C1 scope 迁移：{today}",
        "",
        "flat 布局已迁为 scoped：markdown 内容进 `shared/`，新增 per-员工 `staff/<id>/`。",
        "",
        "## 已迁入 shared/",
        "",
    ]
    lines += [f"- `{m}`" for m in result["moved"]] or ["_（无）_"]
    if result["failed"]:
        lines += ["", "## ⚠️ 迁移失败（保持原位，请手动处理）", ""]
        lines += [f"- `{m}`" for m in result["failed"]]
    lines += ["", "## 新建 staff scope", ""]
    lines += [f"- `staff/{s}/`" for s in staff]
    lines += [
        "",
        "## 留在 root（machine-local / 配置，未迁）",
        "",
        "- `state/` `checkpoints/` `dataset/` `config.yaml` `strict` `.last-*`",
        "",
        "---",
        "本文件由 migrate_scope.py 生成，处理完可删。",
    ]
    try:
        notice.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="ieidev-memory flat → scoped 迁移（一次性幂等）")
    parser.add_argument("--staff", default=",".join(DEFAULT_STAFF),
                        help="逗号分隔的员工 canonical id（默认 dev-engineer,req-architect）")
    parser.add_argument("--root", default=".ieidev/memory", help=".ieidev/memory 路径")
    args = parser.parse_args()
    staff = [s.strip() for s in args.staff.split(",") if s.strip()]
    result = migrate_to_scoped(Path(args.root), staff=staff)
    if result["migrated"]:
        print(f"[ieidev-memory] 已迁为 scoped：搬入 shared/ {len(result['moved'])} 项；"
              f"建 staff {result['staff_created']}")
    else:
        print(f"[ieidev-memory] 已是 scoped（或空），补建 staff {result['staff_created']}")
    if result.get("failed"):
        print(f"[ieidev-memory] ⚠️ {len(result['failed'])} 项迁移失败，请手动处理：{result['failed']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
