#!/usr/bin/env python3
"""
CLAUDE.md 接口契约 lint
=======================

比对 ieidev-memory skill 的 `claude_md_contract`（在 `references/初始化-claude-md-模板.md`
顶部 frontmatter）vs 项目的 `CLAUDE.md`，检测接口级漂移。

**设计原则**：
- 只扫"接口"层（hook 注入标签 / hook 产出文件模式 / 3 条贯穿 session 铁规）
- 不扫"实现"层（schema / 评分机制 / 编号规则 等 —— 这些不在契约里）
- 纯字面子串匹配 + 主题关键词匹配 —— 不做语义理解
- 无外部依赖（YAML 简易自解析；不 import yaml）

**输出**：dict / JSON，字段：
    {
      "status": "ok" | "drift" | "no-claude-md" | "no-ieidev-section"
              | "no-contract" | "contract-parse-error",
      "missing_hook_tags": ["<tag>"] ,
      "missing_hook_files": ["pattern"],
      "missing_rule_themes": [("实时落盘", ["关键词 alternatives"])],
      "summary": "一行人类可读描述",
    }

调用方（session-start-brief.py，v0.7 之前是 .sh）拿 JSON 后决定是否注入 ⚠️ 提示。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# 每条贯穿铁规用"至少一个主题关键词在 CLAUDE.md 里命中"表示存在
# 关键词集合选得比较宽松，避免 CLAUDE.md 里用等价表达但被 lint 误报
RULE_THEME_KEYWORDS = {
    "实时落盘": ["实时落盘", "立刻追加", "立即追加", "每做完一步", "持续追加"],
    "文件聚合不翻会话": ["文件聚合", "不翻会话", "从 .ieidev/memory/", "不要翻会话", "不翻会话上下文"],
    "优先处理 hook 产出": ["优先处理", "hook 产出", "WARN", "ieidev-memory-brief", "ieidev-memory-recall"],
}

# marker 切块（v0.18 / spec-kit 风格托管块）——与 claude_md_merge 对齐，本文件自包含不 import
_RE_MARK_BEGIN = re.compile(r"<!--\s*BEGIN ieidev-team:智能体自动记录规则.*?-->")
_RE_MARK_END = re.compile(r"<!--\s*END ieidev-team:智能体自动记录规则\s*-->")


def parse_contract(contract_text: str) -> dict[str, list[str]] | None:
    """从 frontmatter 里抽取 claude_md_contract 的三个列表字段。

    简易 YAML 解析（不引入 PyYAML）——只处理这 3 个 list 字段：
      hook_injection_tags / hook_file_patterns / cross_session_rules

    返回 None 表示 frontmatter 缺失或没找到 claude_md_contract 区块。
    """
    m = re.match(r"^---\s*\n(.*?)\n---", contract_text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)

    # 定位 claude_md_contract 区块（顶级 key 后面的缩进块）
    c_match = re.search(
        r"^claude_md_contract:\s*\n((?:[ \t]+.+\n?)+)",
        fm,
        re.MULTILINE,
    )
    if not c_match:
        return None
    contract_block = c_match.group(1)

    return {
        "hook_injection_tags": _extract_list("hook_injection_tags", contract_block),
        "hook_file_patterns": _extract_list("hook_file_patterns", contract_block),
        "cross_session_rules": _extract_list("cross_session_rules", contract_block),
    }


def _extract_list(key: str, yaml_block: str) -> list[str]:
    """在 yaml_block 里找 `<key>:`，然后收集其下的 `- item` 列表项。

    容错：引号 / 空白 / 嵌套 key 结束都处理。不支持数组的 JSON flow 语法。
    """
    items: list[str] = []
    lines = yaml_block.split("\n")
    in_list = False
    key_indent = 0

    for line in lines:
        # 跳过空行（但不退出 list 收集，YAML 允许空行）
        if not line.strip():
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if in_list:
            if stripped.startswith("- "):
                val = stripped[2:].strip()
                # 剥掉两侧的 " 或 ' 引号
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                    val = val[1:-1]
                items.append(val)
                continue
            # 缩进 <= key 的缩进 → list 结束
            if indent <= key_indent:
                break
            # 其他同层或更深的结构（不应发生在 list 下），也退出
            break

        # 还没进入 list：找 key
        if stripped.startswith(f"{key}:"):
            after = stripped[len(key) + 1 :].strip()
            if after:  # 单行形式 `key: [a, b]` —— 本简易解析器不支持
                return []
            in_list = True
            key_indent = indent

    return items


def extract_ieidev_section(claude_md_text: str) -> str | None:
    """从 CLAUDE.md 里抽出托管规则段正文。

    v0.18+：优先按 BEGIN/END marker 切块（spec-kit 风格托管块）。
    无 marker（老项目）或 marker 半残时，回退到按 `## 智能体自动记录规则`
    标题边界抽取。找不到返回 None（项目未装过 ieidev-memory 规则段）。
    """
    # 优先：marker 切块（含配对 marker 时）
    bm = _RE_MARK_BEGIN.search(claude_md_text)
    em = _RE_MARK_END.search(claude_md_text)
    if bm and em and bm.end() < em.start():
        return claude_md_text[bm.start():em.end()]

    # 回退：按标题抽段（无 marker / marker 半残的老项目）
    lines = claude_md_text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+智能体自动记录规则\s*$", line):
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}\s+\S", lines[j]) and not re.match(r"^##\s+智能体自动记录规则", lines[j]):
            end = j
            break

    return "\n".join(lines[start:end])


def check_drift(contract: dict[str, list[str]], ieidev_section: str) -> dict[str, Any]:
    """核对 contract 的三类字段 vs 规则段内容。"""
    missing_tags = [t for t in contract.get("hook_injection_tags", []) if t not in ieidev_section]
    missing_files = [
        f for f in contract.get("hook_file_patterns", []) if not _file_pattern_matches(f, ieidev_section)
    ]

    # 3 条铁规：每条只要任一主题关键词命中就算存在
    missing_themes: list[tuple[str, list[str]]] = []
    for theme, keywords in RULE_THEME_KEYWORDS.items():
        if not any(kw in ieidev_section for kw in keywords):
            missing_themes.append((theme, keywords))

    drift = bool(missing_tags or missing_files or missing_themes)
    return {
        "drift": drift,
        "missing_hook_tags": missing_tags,
        "missing_hook_files": missing_files,
        "missing_rule_themes": missing_themes,
    }


def _file_pattern_matches(pattern: str, text: str) -> bool:
    """判断 file pattern 在 text 里有没有被提及。

    匹配策略从严到宽逐级尝试（任一命中即算存在）：
      1. 完整 pattern 字面匹配（pattern 无 * 时唯一判据）
      2. pattern 的基名（最后一节路径）带 glob 的 regex 匹配——容忍用户 CLAUDE.md
         只写文件名而不写完整路径
    这样契约里写 `.ieidev/memory/WARN-未记录-*.md`，用户 CLAUDE.md 写 `WARN-未记录-*.md`
    也算命中——接口粒度足够。
    """
    # Level 1: 字面匹配（无 glob 时必须走这条）
    if "*" not in pattern:
        return pattern in text
    escaped_full = re.escape(pattern).replace(r"\*", r".*")
    if re.search(escaped_full, text):
        return True

    # Level 2: 基名匹配（容忍缺失路径前缀）
    basename = pattern.rsplit("/", 1)[-1]
    if "*" not in basename:
        return basename in text
    escaped_base = re.escape(basename).replace(r"\*", r".*")
    return re.search(escaped_base, text) is not None


def build_summary(result: dict[str, Any]) -> str:
    """给 hook 注入用的一行概述（中文）。"""
    status = result.get("status")
    if status == "ok":
        return "CLAUDE.md 接口契约齐全"
    if status == "no-claude-md":
        return "项目无 CLAUDE.md（skill 未初始化）"
    if status == "no-ieidev-section":
        return "CLAUDE.md 无「智能体自动记录规则」章节（未启用 ieidev-memory）"
    if status == "no-contract":
        return "skill contract 未定义（跳过 lint）"
    if status == "contract-parse-error":
        return "skill contract 解析失败（跳过 lint）"

    parts: list[str] = []
    if result.get("missing_hook_tags"):
        parts.append(f"缺 hook 标签 {len(result['missing_hook_tags'])} 个")
    if result.get("missing_hook_files"):
        parts.append(f"缺 hook 文件模式 {len(result['missing_hook_files'])} 个")
    if result.get("missing_rule_themes"):
        parts.append(f"缺贯穿铁规 {len(result['missing_rule_themes'])} 条")
    return "CLAUDE.md 接口漂移：" + "，".join(parts)


def run_lint(contract_path: Path, claude_md_path: Path) -> dict[str, Any]:
    """主入口：读取两个文件，比对，返回 dict。"""
    # 1. CLAUDE.md 不存在
    if not claude_md_path.is_file():
        return {"status": "no-claude-md", "summary": build_summary({"status": "no-claude-md"})}

    # 2. contract 不存在 / 解析失败
    if not contract_path.is_file():
        return {"status": "no-contract", "summary": build_summary({"status": "no-contract"})}
    contract = parse_contract(contract_path.read_text(encoding="utf-8"))
    if contract is None:
        return {
            "status": "contract-parse-error",
            "summary": build_summary({"status": "contract-parse-error"}),
        }

    # 3. CLAUDE.md 里无 ieidev-memory 规则段（未启用）
    claude_text = claude_md_path.read_text(encoding="utf-8")
    section = extract_ieidev_section(claude_text)
    if section is None:
        return {"status": "no-ieidev-section", "summary": build_summary({"status": "no-ieidev-section"})}

    # 4. 真正的 drift check
    drift_result = check_drift(contract, section)
    status = "drift" if drift_result["drift"] else "ok"
    result = {"status": status, **drift_result}
    result["summary"] = build_summary(result)
    return result


def _fmt_themes_for_hint(themes: list[tuple[str, list[str]]]) -> list[str]:
    """brief 提示里展示贯穿铁规缺失 —— 只显示主题名不显示 alternatives 长列表。"""
    return [theme for theme, _ in themes]


def format_hint_for_brief(result: dict[str, Any]) -> str | None:
    """把 lint 结果格式化成给 SessionStart brief 注入的文本。

    返回 None 表示无需注入（无漂移或项目未启用 skill）。
    """
    if result.get("status") != "drift":
        return None

    lines: list[str] = ["- CLAUDE.md 接口漂移："]
    if result.get("missing_hook_tags"):
        lines.append(f"  · 缺 hook 注入标签：{', '.join(result['missing_hook_tags'])}")
    if result.get("missing_hook_files"):
        lines.append(f"  · 缺 hook 产出文件模式：{', '.join(result['missing_hook_files'])}")
    if result.get("missing_rule_themes"):
        themes = _fmt_themes_for_hint(result["missing_rule_themes"])
        lines.append(f"  · 缺贯穿 session 铁规：{' / '.join(themes)}")
    lines.append("  · 召唤 ieidev-memory skill 说「修 CLAUDE.md 漂移」获得精确 diff patch")
    return "\n".join(lines)


def main() -> int:
    """CLI 入口：`claude_md_lint.py <contract_path> <claude_md_path>` → stdout JSON。"""
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {"status": "usage-error", "summary": "usage: claude_md_lint.py <contract> <claude.md>"},
                ensure_ascii=False,
            )
        )
        return 2
    contract_path = Path(sys.argv[1])
    claude_md_path = Path(sys.argv[2])
    result = run_lint(contract_path, claude_md_path)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
