#!/usr/bin/env python3
"""
ieidev-memory triggers 核心：sanitize + scan + match + dedup

输入：stdin JSON (Claude Code UserPromptSubmit hook 的输入)
输出：stdout JSON (hookSpecificOutput.additionalContext 或 suppressOutput)

扫描的数据源（按优先级）：
  1. .ieidev/memory/踩坑日志.md 中每条 ## G-NNN 下紧跟的 triggers: 行
  2. .ieidev/memory/执行日志.md 中今日/昨日 Step 的 triggers: 行（日期字段筛选）
  3. .ieidev/memory/方法论铁规.md 中每条规则的 triggers: 行
  4. 项目级 spec 文件（7 个约定路径）：
     constitution.md / spec.md / principles.md / AGENTS.md
     .specify/constitution.md
     docs/constitution.md / docs/principles.md

triggers: 字段支持的格式（在每条标题的下一行或 frontmatter 里）：
  triggers: ["关键词1", "关键词2"]           # JSON array（推荐）
  triggers: [关键词1, 关键词2]                # 无引号 YAML-like
  triggers: 关键词1, 关键词2                  # 逗号分隔
  triggers:                                    # YAML 多行
    - 关键词1
    - 关键词2

匹配算法：literal substring + toLowerCase
Session 去重：.ieidev/memory/state/trigger-sessions.json，TTL 60 分钟
每 session 限额：3 条（按命中 trigger 数量倒排）

渐进式披露：注入只含编号 + 标题 + 路径，让 Claude Read 细节。
"""

from __future__ import annotations
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==================== 配置 ====================

IEIDEV_DIR = Path(".ieidev/memory")
STATE_FILE = IEIDEV_DIR / "state" / "trigger-sessions.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import shared_dir, staff_log_files  # noqa: E402
from step_id import id_label_fragment  # noqa: E402

# 约定的项目级 spec 文件扫描路径
SPEC_PATHS = [
    "constitution.md",
    "spec.md",
    "principles.md",
    "AGENTS.md",
    ".specify/constitution.md",
    "docs/constitution.md",
    "docs/principles.md",
]

DEDUP_TTL_SECONDS = 60 * 60  # 60 分钟
MAX_INJECT = 3


# ==================== Sanitize ====================

def sanitize_prompt(text: str) -> str:
    """移除代码块、XML 标签、URL、文件路径、git diff 等，避免字面量误触发。"""
    # 1. Markdown 代码块
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # 2. 行内代码
    text = re.sub(r"`[^`\n]+`", " ", text)
    # 3. XML 标签块
    text = re.sub(r"<(\w[\w-]*)[\s>][\s\S]*?</\1>", " ", text)
    # 4. 自闭合 XML
    text = re.sub(r"<\w[\w-]*(?:\s[^>]*)?\s*/>", " ", text)
    # 5. URL
    text = re.sub(r"https?://\S+", " ", text)
    # 6. 块引用
    text = re.sub(r"^\s*>\s.*$", "", text, flags=re.MULTILINE)
    # 7. git diff 头
    text = re.sub(r"^(?:diff\s+--git\s+a/|index\s+[0-9a-f]+\.\.|(?:---|\+\+\+)\s+[ab]/|@@\s+-\d+).*$", "", text, flags=re.MULTILINE)
    # 8. 文件路径（至少一个 / 的 token）
    text = re.sub(r"(?:(?<=\s)|(?<=^))[./]?(?:[\w.-]+/)+[\w.-]+", " ", text, flags=re.MULTILINE)
    return text


# ==================== Triggers 解析 ====================

_TRIGGER_LINE_RE = re.compile(r"^\s*triggers\s*:\s*(.*)$", re.IGNORECASE)
_YAML_LIST_ITEM_RE = re.compile(r"^\s*-\s*(.+?)\s*$")


def parse_triggers_value(raw: str) -> list[str]:
    """解析 triggers: 后面的值。支持多种格式，返回去重后的关键词列表。"""
    raw = raw.strip()
    if not raw:
        return []

    triggers: list[str] = []

    # JSON array: ["a", "b"]
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                triggers = [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            # 容忍没引号的 [a, b]
            inner = raw[1:-1]
            triggers = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
    else:
        # 逗号分隔的裸文本
        triggers = [x.strip().strip("\"'") for x in raw.split(",") if x.strip()]

    # 去重（保序）
    seen = set()
    result = []
    for t in triggers:
        key = t.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(t)
    return result


def parse_multiline_triggers(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """解析 YAML 多行列表：triggers: 下面若干行缩进 `- xxx`。
    返回 (triggers_list, 消费的行数)"""
    result = []
    i = start_idx
    while i < len(lines):
        line = lines[i]
        m = _YAML_LIST_ITEM_RE.match(line)
        if m:
            item = m.group(1).strip().strip("\"'")
            if item:
                result.append(item)
            i += 1
        else:
            break
    return result, i - start_idx


# ==================== 数据源扫描 ====================

def _read_file(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _extract_entries_with_triggers(
    lines: list[str],
    heading_pattern: re.Pattern[str],
    id_extractor,
    source_tag: str,
    file_path: str,
    date_filter=None,
) -> list[dict]:
    """通用扫描器：找所有命中 heading_pattern 的标题，下面紧跟的 triggers: 收集。

    date_filter: 可选 callable(date_str) -> bool，用于"今日/昨日"过滤
    """
    entries = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        m = heading_pattern.match(line)
        if not m:
            i += 1
            continue

        entry_id, title = id_extractor(m, line)
        entry_date = None
        triggers: list[str] = []

        # 在这个 heading 后面到下一个 heading 之间查找 triggers: 和 日期：
        j = i + 1
        while j < n:
            next_line = lines[j]
            if heading_pattern.match(next_line):
                break
            # 日期（支持"日期：2026-04-20"或"date: 2026-04-20"）
            date_m = re.match(r"^\s*(?:日期|date)[：:]\s*(\d{4}-\d{2}-\d{2})", next_line)
            if date_m:
                entry_date = date_m.group(1)
            # triggers
            tm = _TRIGGER_LINE_RE.match(next_line)
            if tm:
                value = tm.group(1)
                if value:
                    triggers.extend(parse_triggers_value(value))
                else:
                    # 多行 YAML
                    multi, consumed = parse_multiline_triggers(lines, j + 1)
                    triggers.extend(multi)
                    j += consumed
            j += 1

        if triggers and (date_filter is None or entry_date is None or date_filter(entry_date)):
            entries.append({
                "id": entry_id,
                "title": title,
                "triggers": triggers,
                "path": file_path,
                "source": source_tag,
                "date": entry_date,
            })

        i = j if j > i else i + 1

    return entries


def _iter_memory_files(prefix: str) -> list[Path]:
    """主文件（shared 解析）+ 归档子目录下同前缀归档文件。"""
    base = shared_dir(IEIDEV_DIR)
    paths = []
    main = base / f"{prefix}.md"
    if main.is_file():
        paths.append(main)
    archive_dir = base / "归档"
    if archive_dir.is_dir():
        paths.extend(sorted(archive_dir.glob(f"{prefix}-*.md")))
    return paths


def scan_g_entries() -> list[dict]:
    """扫踩坑日志主文件 + 归档（含季度归档）。

    踩坑召回要覆盖全部历史档——老坑也要防重踩。
    """
    entries = []
    # 双认：G-NNN（旧顺序号）+ G <时间戳>（v0.17/Q-020）——grammar 由 step_id 单一托管
    heading_re = re.compile(rf"^##\s+({id_label_fragment('G')})[：:]\s*(.+?)\s*$")
    for path in _iter_memory_files("踩坑日志"):
        lines = _read_file(path)
        if lines is None:
            continue
        entries.extend(_extract_entries_with_triggers(
            lines, heading_re,
            lambda m, line: (m.group(1), m.group(2)),
            "G",
            str(path),
        ))
    return entries


def scan_step_entries() -> list[dict]:
    """扫执行日志主文件 + 归档，日期过滤只留今日/昨日。

    月度归档里的 Step 都是老的，被 date_filter 剔除——扫到但不会召回。
    """
    # v0.7+: 允许测试/eval 通过 IEIDEV_TRIGGER_TODAY=YYYY-MM-DD 固定"今日"基准，
    # 避免 fixture 硬编码日期随真实时间漂移导致 eval 失败
    override = os.environ.get("IEIDEV_TRIGGER_TODAY", "").strip()
    if override:
        try:
            base = datetime.fromisoformat(override)
        except ValueError:
            base = datetime.now()
    else:
        base = datetime.now()
    today = base.strftime("%Y-%m-%d")
    yesterday = (base - timedelta(days=1)).strftime("%Y-%m-%d")
    date_ok = lambda d: d in (today, yesterday)

    entries = []
    # 双认（显式，去掉旧的脆弱 [\w.-]+ 通配）：Step <时间戳> + 旧顺序号/前缀-N
    heading_re = re.compile(rf"^##\s+({id_label_fragment('Step')})[：:]\s*(.+?)\s*$")
    # shared / flat 主线
    for path in _iter_memory_files("执行日志"):
        lines = _read_file(path)
        if lines is None:
            continue
        entries.extend(_extract_entries_with_triggers(
            lines, heading_re,
            lambda m, line: (m.group(1), m.group(2)),
            "Step", str(path), date_filter=date_ok,
        ))
    # per-员工 scope（scoped 布局才有；flat 下 staff_log_files 返回 []）
    for scope_id, path in staff_log_files("执行日志.md", IEIDEV_DIR):
        lines = _read_file(path)
        if lines is None:
            continue
        scoped = _extract_entries_with_triggers(
            lines, heading_re,
            lambda m, line: (m.group(1), m.group(2)),
            "Step", str(path), date_filter=date_ok,
        )
        for e in scoped:
            e["scope"] = scope_id
        entries.extend(scoped)
    return entries


def scan_tiegui_entries() -> list[dict]:
    """扫 .ieidev/memory/方法论铁规.md 的每条规则。"""
    path = shared_dir(IEIDEV_DIR) / "方法论铁规.md"
    lines = _read_file(path)
    if lines is None:
        return []
    # 铁规标题可能是 `## 规则名` 或 `## 铁规: 规则名` 之类，宽松匹配
    heading_re = re.compile(r"^##\s+(.+?)\s*$")
    return _extract_entries_with_triggers(
        lines, heading_re,
        lambda m, line: (f"铁规·{m.group(1).strip()}", m.group(1).strip()),
        "铁规",
        str(path),
    )


def scan_spec_frontmatter(path: Path) -> dict | None:
    """扫 spec 文件的 frontmatter，如果含 triggers 就返回整个文件作为一条记录。"""
    lines = _read_file(path)
    if lines is None or not lines:
        return None
    if lines[0].strip() != "---":
        return None

    # 找 frontmatter 终点
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    fm_lines = lines[1:end_idx]
    triggers: list[str] = []

    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        m = _TRIGGER_LINE_RE.match(line)
        if m:
            value = m.group(1)
            if value:
                triggers.extend(parse_triggers_value(value))
            else:
                multi, consumed = parse_multiline_triggers(fm_lines, i + 1)
                triggers.extend(multi)
                i += consumed
        i += 1

    if not triggers:
        return None

    # 标题从 body 第一个 `# xxx` 取，否则用文件名
    title = path.stem
    for line in lines[end_idx + 1:]:
        hm = re.match(r"^#\s+(.+?)\s*$", line)
        if hm:
            title = hm.group(1).strip()
            break

    return {
        "id": f"spec·{path.name}",
        "title": title,
        "triggers": triggers,
        "path": str(path),
        "source": "spec",
        "date": None,
    }


def scan_spec_inline(path: Path) -> list[dict]:
    """扫 spec 文件的 `## 规则名` + triggers: 行（和铁规同模式）。"""
    lines = _read_file(path)
    if lines is None:
        return []
    heading_re = re.compile(r"^##\s+(.+?)\s*$")
    return _extract_entries_with_triggers(
        lines, heading_re,
        lambda m, line: (f"spec·{m.group(1).strip()}", m.group(1).strip()),
        "spec",
        str(path),
    )


def scan_all_specs() -> list[dict]:
    """扫所有约定的 spec 路径。每个文件先试 frontmatter，再试 inline。"""
    entries = []
    for rel in SPEC_PATHS:
        p = Path(rel)
        if not p.exists():
            continue
        # 文件级 frontmatter
        fm_entry = scan_spec_frontmatter(p)
        if fm_entry:
            entries.append(fm_entry)
        # 条目级 inline
        entries.extend(scan_spec_inline(p))
    return entries


# ==================== 匹配 ====================

def match_entries(prompt_lower: str, entries: list[dict]) -> list[tuple[dict, int]]:
    """对每个 entry 做 substring 匹配，返回 (entry, score) 倒序。"""
    results = []
    for entry in entries:
        score = 0
        for trig in entry["triggers"]:
            if trig.lower() in prompt_lower:
                score += 1
        if score > 0:
            results.append((entry, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ==================== Session 去重 ====================

def load_dedup_state() -> dict:
    """读 session 去重状态文件，清理过期 session。"""
    if not STATE_FILE.exists():
        return {"sessions": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sessions": {}}

    now = time.time()
    sessions = data.get("sessions", {})
    pruned = {}
    for sid, sess in sessions.items():
        ts = sess.get("timestamp", 0)
        if now - ts <= DEDUP_TTL_SECONDS:
            pruned[sid] = sess
    data["sessions"] = pruned
    return data


def save_dedup_state(data: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # 非致命


def filter_already_injected(
    matches: list[tuple[dict, int]],
    session_id: str,
    state: dict,
) -> list[tuple[dict, int]]:
    sess = state["sessions"].get(session_id, {})
    injected = set(sess.get("injected_ids", []))
    return [(e, s) for e, s in matches if e["id"] not in injected]


def record_injections(session_id: str, ids: list[str], state: dict) -> None:
    now = time.time()
    sess = state["sessions"].setdefault(session_id, {"injected_ids": [], "timestamp": now})
    existing = set(sess.get("injected_ids", []))
    existing.update(ids)
    sess["injected_ids"] = sorted(existing)
    sess["timestamp"] = now


# ==================== 输出 ====================

def format_recall(selected: list[dict]) -> str:
    """生成 <ieidev-memory-recall> 块。渐进式披露：只含 id + title + 路径。"""
    lines = [
        "<ieidev-memory-recall>",
        "检测到你提到的内容匹配到以下记忆（如需细节，Read 对应文件）：",
        "",
    ]
    for entry in selected:
        source_label = {
            "G": "踩坑", "Step": "今日进度", "铁规": "铁规", "spec": "项目 spec",
        }.get(entry["source"], entry["source"])
        scope = entry.get("scope")
        scope_tag = f"·{scope}" if scope else ""
        lines.append(f"- **{entry['id']}**（{source_label}{scope_tag}）{entry['title']}")
        lines.append(f"  → `{entry['path']}`")
    lines.append("")
    lines.append("（相关记忆本会话只注入一次；若不相关请忽略）")
    lines.append("</ieidev-memory-recall>")
    return "\n".join(lines)


def emit_suppress() -> None:
    json.dump({"continue": True, "suppressOutput": True}, sys.stdout)


def emit_context(context: str) -> None:
    json.dump({
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }, sys.stdout, ensure_ascii=False)


# ==================== 主流程 ====================

def main() -> int:
    # 读 hook 输入
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        emit_suppress()
        return 0

    prompt = data.get("prompt") or ""
    session_id = data.get("session_id") or data.get("sessionId") or "unknown"

    if not prompt.strip():
        emit_suppress()
        return 0

    # 项目没启用 .ieidev/memory/ → 静默
    if not IEIDEV_DIR.is_dir():
        emit_suppress()
        return 0

    # Sanitize + lowercase
    prompt_lower = sanitize_prompt(prompt).lower()

    # 扫所有数据源
    all_entries = []
    all_entries.extend(scan_g_entries())
    all_entries.extend(scan_step_entries())
    all_entries.extend(scan_tiegui_entries())
    all_entries.extend(scan_all_specs())

    if not all_entries:
        emit_suppress()
        return 0

    # 匹配
    matches = match_entries(prompt_lower, all_entries)
    if not matches:
        emit_suppress()
        return 0

    # 去重
    state = load_dedup_state()
    matches = filter_already_injected(matches, session_id, state)
    if not matches:
        emit_suppress()
        return 0

    # 限额
    selected = [e for e, _ in matches[:MAX_INJECT]]

    # 记录已注入
    record_injections(session_id, [e["id"] for e in selected], state)
    save_dedup_state(state)

    # 输出
    context = format_recall(selected)
    emit_context(context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
