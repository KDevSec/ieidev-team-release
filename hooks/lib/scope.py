"""ieidev-memory v0.14 scope 解析单一真相源（P-C1 记忆 scope 分离）。

布局（opt-in 向后兼容）：
- flat（无 staff，= 现状）：`.ieidev/memory/{执行日志.md, 决策日志.md, ...}`
- scoped（迁移后）：`.ieidev/memory/{shared/<markdown>, staff/<canonical-id>/<markdown>}`

检测信号：`<root>/shared/` 目录是否存在（migrate_scope.py 创建它即开启 scoped）。

核心不变量：**flat 模式 `shared_dir(root) == root`**——所有 Tier A hook 把
`root / "执行日志.md"` 改成 `shared_dir(root) / "执行日志.md"` 后，flat 行为字节级不变。

machine-local plumbing（state/ checkpoints/ dataset/ .last-* config.yaml strict）
**永远在 root，不随 scope 迁移**。本模块只管 markdown 内容文件的 scope 解析。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

PathLike = Union[Path, str]

DEFAULT_ROOT = Path(".ieidev/memory")

# 视同 shared 的 scope 名（Step slug 回退到分支 slug）
SHARED_SCOPES = frozenset({"", "shared", "default", "project"})


def is_scoped(root: PathLike = DEFAULT_ROOT) -> bool:
    """scoped 布局 iff `<root>/shared/` 是目录。"""
    return (Path(root) / "shared").is_dir()


def shared_dir(root: PathLike = DEFAULT_ROOT) -> Path:
    """项目层 markdown 落位。scoped → root/shared；flat → root（不变量）。"""
    root = Path(root)
    return root / "shared" if is_scoped(root) else root


def staff_root(root: PathLike = DEFAULT_ROOT) -> Path:
    """per-员工 scope 的根目录 `<root>/staff/`。"""
    return Path(root) / "staff"


def staff_dir(scope_id: str, root: PathLike = DEFAULT_ROOT) -> Path:
    """某员工 scope 目录 `<root>/staff/<scope_id>/`。
    调用方负责传入干净的 canonical ASCII id（本函数不做 path-traversal 防护）。"""
    return staff_root(root) / scope_id


def list_staff(root: PathLike = DEFAULT_ROOT) -> List[str]:
    """已注册员工 canonical id 列表（`staff/` 子目录名，排序）。无 staff → []。"""
    sr = staff_root(root)
    if not sr.is_dir():
        return []
    return sorted(d.name for d in sr.iterdir() if d.is_dir())


def staff_log_files(filename: str, root: PathLike = DEFAULT_ROOT) -> List[Tuple[str, Path]]:
    """返回每个 staff scope 下存在的 `<filename>`，形如 [(scope_id, path), ...]。"""
    out: List[Tuple[str, Path]] = []
    for sid in list_staff(root):
        p = staff_dir(sid, root) / filename
        if p.is_file():
            out.append((sid, p))
    return out


def state_dir(root: PathLike = DEFAULT_ROOT) -> Path:
    """hook plumbing（counter/dedup/pending）——永远在 root，不 scoped。"""
    return Path(root) / "state"


def recorder_target_log(scope: Optional[str], root: PathLike = DEFAULT_ROOT) -> Path:
    """step-recorder 写 Step 的目标 执行日志.md。

    - shared/default/None → shared_dir(root)/执行日志.md（flat 下即 root/执行日志.md）
    - 员工 canonical id → staff/<id>/执行日志.md（flat 兜底回 root/执行日志.md）
    """
    root = Path(root)
    if scope is None or scope.strip().lower() in SHARED_SCOPES:
        return shared_dir(root) / "执行日志.md"
    if is_scoped(root):
        return staff_dir(scope.strip(), root) / "执行日志.md"
    return shared_dir(root) / "执行日志.md"


def resolve_step_slug(scope: Optional[str], root: PathLike = DEFAULT_ROOT) -> str:
    """scope → Step ID slug。

    ⚠️ Q-020：本函数已废弃用于 minting。新记录 ID 走 step_id.mint_record_id（时间戳原语）；
    本函数仅留向后兼容/历史解析（parse_record_id 双认旧形式）。

    - shared/default/project/None/空 → 分支 slug（复用 step_id.compute_branch_slug，
      产出如 `main`、`cluster-x1`；已废弃 for minting，Q-020；仅历史/兼容）
    - 其它（员工 canonical id）→ sanitize 后的 id（如 `dev-engineer`；
      已废弃 for minting，Q-020；仅历史/兼容）
    """
    # `root` is accepted for API symmetry with the rest of this module and is
    # reserved for future scope validation (e.g. checking scope_id ∈ list_staff(root));
    # it does not affect slug computation today.
    _ = root  # explicitly mark as intentionally unused
    from step_id import compute_branch_slug, sanitize_slug
    if scope is None or scope.strip().lower() in SHARED_SCOPES:
        return compute_branch_slug()
    return sanitize_slug(scope.strip())
