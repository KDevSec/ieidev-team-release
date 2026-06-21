"""ieidev-memory 里程碑路径白名单 —— 单一真相源（v0.8 转 Python）

被 stop-check.py 和 post-write-check.py 通过 import 引用。

设计原则：
  - 命中 = "这条变更大概率对应一个工作单元 Step，值得显式落盘"
  - 保持克制：日常源码/配置/脚本编辑不命中（避免 PostToolUse 刷屏）
  - 只收"有约定结构"的目录/文件名，不扫 .md 泛匹配

扩展办法：在下面 PATTERNS 列表里添加 fnmatch glob。优先通用约定。

最低 Python 版本：3.7。
"""

from __future__ import annotations

import fnmatch
from typing import List


# 命中的 glob 模式（fnmatch 风格，跨平台一致；统一用正斜杠路径）
PATTERNS: List[str] = [
    # --- Spec Kit 产物 ---
    "specs/*/*.md",
    "specs/*/contracts/*.yml",
    "specs/*/contracts/*.yaml",

    # --- 工程记忆自己的硬规 ---
    ".ieidev/memory/方法论铁规.md",
    ".ieidev/memory/shared/方法论铁规.md",  # P-C1 scoped 布局
    ".ieidev/方法论铁规.md",  # 0.2.0 遗留位置（迁移失败 fallback）

    # --- 迭代 / Sprint / 冲刺 ---
    "docs/iterations/*.md",
    "docs/iterations/*/*.md",
    "docs/sprints/*.md",
    "docs/sprints/*/*.md",
    "docs/sprint-*.md",
    "docs/迭代-*.md",
    "docs/迭代/*.md",
    "docs/迭代/*/*.md",

    # --- ADR ---
    "docs/adr/*.md",
    "docs/adr/*/*.md",
    "docs/ADR/*.md",
    "docs/ADR/*/*.md",
    "docs/decisions/*.md",
    "docs/decisions/*/*.md",
    "adr/*.md",
    "adrs/*.md",

    # --- 架构 / 设计 / PRD / 需求 ---
    "docs/architecture/*.md",
    "docs/architecture/*/*.md",
    "docs/design/*.md",
    "docs/design/*/*.md",
    "docs/设计-*.md",
    "docs/设计/*.md",
    "docs/设计/*/*.md",
    "docs/prd/*.md",
    "docs/prd/*/*.md",
    "docs/PRD-*.md",
    "docs/PRD/*.md",
    "docs/requirements/*.md",
    "docs/requirements/*/*.md",
    "docs/需求-*.md",
    "docs/需求/*.md",
    "docs/需求/*/*.md",

    # --- 根目录关键文档 ---
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "MIGRATION.md",
    "CHANGELOG.md",
    "DECISIONS.md",

    # --- 数据库 migration ---
    "migrations/*.sql",
    "migrations/*/*.sql",
    "db/migrate/*.sql",
    "db/migrate/*.rb",
    "db/migrations/*.sql",
    "db/migrations/*/*.sql",
    "prisma/migrations/*/migration.sql",
    "supabase/migrations/*.sql",
    "alembic/versions/*.py",

    # --- API / 协议契约 ---
    "openapi.yml",
    "openapi.yaml",
    "openapi.json",
    "api/openapi.yml",
    "api/openapi.yaml",
    "api/openapi.json",
    "api/schema.graphql",
    "schema.graphql",
    "*.proto",
    "proto/*.proto",
    "proto/*/*.proto",
]


def is_milestone_path(path: str) -> bool:
    """判断给定路径（项目根相对 + 正斜杠）是否命中里程碑白名单。"""
    # 标准化分隔符（容忍 Windows 反斜杠）
    norm = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(norm, pat) for pat in PATTERNS)
