#!/usr/bin/env python3
"""
Step 完整度扫描
===============

扫 `.ieidev/memory/执行日志.md` 的最近 N 条 Step 条目，识别"半残"
（写了但字段不全，像是"待补 / 污染样本 / 时分戳空"）。

**何时用**：
- SessionStart hook：扫最近几天的 Step，brief 里 ⚠️ 提示用户补采或销账
- Stop hook：扫今日 Step，软提醒；strict 模式下升级为 exit 2 阻塞

**"半残"判定**（任一命中即算）：
- 用户评分段的「完成时间」字段值为 `—` / 空 / 关键词（待补 / 污染样本 / TBD / TODO）
- 用户评分段的「顺畅度」字段值为 `—` / 空 / 关键词
- 模型自评段有头但无扣分项（"扣分项：" 后面没实质内容）（P-C1b 后为模型他评段，同检扣分项）

**不算半残**（刻意）：
- 执行事实段可以粗略估算，只要字段存在就认
- 双评分差异段可以缺失（允许只记录不分析）
- 触发词 triggers 字段可以缺失（另有 trigger-match hook 负责）

设计：Python 只负责扫描 + 输出 JSON，格式化消息和注入时机由 shell hook 决定。

**输出 JSON schema**：
    {
      "status": "ok" | "has_half_complete" | "no-log-file",
      "half_complete_steps": [
        {
          "step_label": "Step 8",
          "date": "2026-04-15",
          "issues": ["用户评分段时分戳为 —", "扣分项为空"]
        }
      ],
      "total_scanned": int,
      "today_half_complete": int,    # 今日创建的半残 Step 数（Stop hook 用）
      "summary": "..."
    }
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# 标记"半残"的时分戳/顺畅度值（这些表达说明字段没真填）
PLACEHOLDER_VALUES = {"—", "-", "", "待补", "污染样本", "TBD", "TODO", "待填"}

# 默认扫描最近 N 天
DEFAULT_LOOKBACK_DAYS = 14

# v0.7+ 销账信号
VOIDED_HEURISTIC_PATTERNS = (
    "**褪色补录**",      # Brief 模板语（最强信号）
    "褪色补录",           # 不带 ** 的纯文字
    "保留占位不强求补",
    "保留占位",
    "非原生当场采集",
    "无原生评分",
    "不计入差值",
)

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
from status_schema import is_voided_status, warn_unknown_status  # noqa: E402
from step_id import id_label_fragment  # noqa: E402


def _extract_inline_status(body: str) -> str | None:
    """読 Step header 伪 frontmatter 里的内联 `status:`（`## Step` 行下方、首个空行/###/> 之前）。

    真实日志的 status 多写在 header（无 --- 围栏），历史上未被解析——本函数补这个口子。
    只取冒号后第一个非空 token（容忍行尾 `# 注释`）。
    """
    lines = body.splitlines()
    for line in lines[1:]:  # lines[0] 是 "## Step ..." 标题行
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            break
        m = re.match(r"^status\s*:\s*(\S+)", s)
        if m:
            return m.group(1).strip()
    return None


def parse_steps(log_text: str) -> list[dict[str, Any]]:
    """把执行日志切成 Step 条目列表。

    每条 Step 以 `## Step <N>:` 开头，到下一个 `## Step ` 或文件结束为止。
    """
    steps: list[dict[str, Any]] = []
    # 匹配 "## Step 8: ..." / "## Step 5.5 ..." / "## Step M-7 meta 回补" / 时间戳形等变体；
    # label 文法（双认 legacy + 时间戳）由 step_id.id_label_fragment 单一托管，避免漂移。
    # 之后可选空格 + 冒号/或直接跟 title（含空格的多词标题）
    pattern = re.compile(
        rf"^##\s+({id_label_fragment('Step')})(?:\s*[:：]\s*(.+)|\s+(.+))?$",
        re.MULTILINE,
    )

    matches = list(pattern.finditer(log_text))
    for i, m in enumerate(matches):
        label = m.group(1).strip()
        # title 可能在 group(2)（冒号后）或 group(3)（空格后）
        title = (m.group(2) or m.group(3) or "").strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(log_text)
        body = log_text[start:end]
        # 提取日期字段
        date_m = re.search(r"^日期[:：]\s*(\d{4}-\d{2}-\d{2})", body, re.MULTILINE)
        entry_date = date_m.group(1) if date_m else None

        # v0.7+: extract Step body's embedded YAML frontmatter status, if any
        status_m = re.search(
            r"^---\s*$\n(.*?)^---\s*$",
            body,
            re.MULTILINE | re.DOTALL,
        )
        entry_status = None
        if status_m:
            fm_text = status_m.group(1)
            sf = re.search(r"^\s*status\s*:\s*(\S+)", fm_text, re.MULTILINE)
            if sf:
                entry_status = sf.group(1).strip()
        if entry_status is None:
            entry_status = _extract_inline_status(body)

        steps.append({
            "label": label,
            "title": title,
            "date": entry_date,
            "body": body,
            "status": entry_status,  # v0.7+
        })
    return steps


def check_step(step: dict[str, Any], rating_mode: str = "user-required") -> list[str]:
    """返回该 Step 的 issues 列表（空表示无半残）。"""
    body = step["body"]

    # v0.7+/v0.18: status = 评分/销账态。非枚举值（修复态误写）→ 告警，不静默当销账
    _status = step.get("status")
    warn_unknown_status(_status, entry_id=step.get("label", "?"))
    # 销账态（voided-faded / voided-r-<NNN>）跳过欠评扫描
    if is_voided_status(_status):
        return []

    # v0.7+: heuristic voided markers (text layer — compat for historical entries)
    for pat in VOIDED_HEURISTIC_PATTERNS:
        if pat in body:
            return []

    # v0.7+: Step title starts with "Step M-" → treat as meta-回补 placeholder
    if re.match(r"^Step\s+M-", step["label"]):
        return []

    issues: list[str] = []

    # 1. 用户评分段（仅 user-required 模式检查；model-only / user-opt-in 视空为正常）
    if rating_mode == "user-required":
        user_section = _extract_section(body, "### 用户评分") or _extract_section(body, "## 用户评分")
        if user_section is not None:
            ts = _extract_field(user_section, "完成时间")
            score = _extract_field(user_section, "顺畅度")
            if ts is None or _is_placeholder(ts):
                issues.append(f"用户评分段「完成时间」为 {_describe_placeholder(ts)}")
            if score is None or _is_placeholder(score):
                issues.append(f"用户评分段「顺畅度」为 {_describe_placeholder(score)}")
        elif (
            "## 用户评分" not in body
            and "### 用户评分" not in body
            and _has_model_self_review(body)
        ):
            issues.append("有模型自评段但无用户评分段（Step 未完整闭环）")

    # 2. 模型自评 / 模型他评段的扣分项（P-C1b：他评替换自评，两名都查）
    self_section = (
        _extract_section(body, "### 模型他评") or _extract_section(body, "## 模型他评")
        or _extract_section(body, "### 模型自评") or _extract_section(body, "## 模型自评")
    )
    if self_section is not None:
        # "扣分项：xxx" —— 冒号后面实质为空或仅占位
        deduction_m = re.search(r"^[\-\*\s]*(?:本步最值得)?扣分项[:：]\s*(.*?)$", self_section, re.MULTILINE)
        if deduction_m:
            val = deduction_m.group(1).strip()
            if _is_placeholder(val):
                issues.append(f"模型自评段「扣分项」为 {_describe_placeholder(val)}")

    return issues


def _extract_section(body: str, heading: str) -> str | None:
    """提取 body 里某个 `### heading` 章节的文本（到下一个同级或更高级标题止）。"""
    # 用 regex 找 heading 行
    heading_esc = re.escape(heading.strip())
    # 匹配 heading 那行
    m = re.search(rf"^{heading_esc}\s*$", body, re.MULTILINE)
    if not m:
        return None
    start = m.end()
    # 找下一个 ## 或 ### 开头的标题
    next_m = re.search(r"^(##|###)\s+\S", body[start:], re.MULTILINE)
    end = start + next_m.start() if next_m else len(body)
    return body[start:end]


def _extract_field(section: str, field_name: str) -> str | None:
    """从 '- 字段名：值' 形式里抽值（容错中英冒号、空格）。"""
    pattern = re.compile(
        rf"^[\-\*\s]*{re.escape(field_name)}[:：]\s*(.*?)(?:#.*)?$",
        re.MULTILINE,
    )
    m = pattern.search(section)
    if not m:
        return None
    return m.group(1).strip()


def _is_placeholder(val: str | None) -> bool:
    """判断值是否是占位符（空 / — / 待补 等）。"""
    if val is None:
        return True
    val = val.strip()
    # 完全空
    if not val:
        return True
    # 纯占位符字面量
    if val in PLACEHOLDER_VALUES:
        return True
    # "N/5" 里的 N 是 — 或空
    score_m = re.match(r"^(.+?)\s*/\s*5\s*$", val)
    if score_m and score_m.group(1).strip() in PLACEHOLDER_VALUES:
        return True
    # 含"待补"/"污染样本"等关键词（比如 "— 待补"）
    for kw in ("待补", "污染样本", "TBD", "TODO"):
        if kw in val:
            return True
    return False


def _describe_placeholder(val: str | None) -> str:
    """给错误消息用的占位符描述。"""
    if val is None or not val.strip():
        return "空"
    return f"'{val.strip()}'"


def _has_model_self_review(body: str) -> bool:
    return any(h in body for h in ("### 模型他评", "## 模型他评", "### 模型自评", "## 模型自评"))


def run_check(log_path: Path, today: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS, rating_mode: str = "user-required") -> dict[str, Any]:
    """主入口：扫执行日志，返回检测结果 dict。

    - log_path: .ieidev/memory/执行日志.md 路径
    - today: YYYY-MM-DD，用于区分"今日新增半残"
    - lookback_days: 扫最近多少天的 Step（过滤降低 noise）
    """
    if not log_path.is_file():
        return {
            "status": "no-log-file",
            "half_complete_steps": [],
            "total_scanned": 0,
            "today_half_complete": 0,
            "summary": "执行日志文件不存在",
        }

    text = log_path.read_text(encoding="utf-8")
    all_steps = parse_steps(text)

    # 按日期过滤
    scanned_steps = [s for s in all_steps if _within_lookback(s["date"], today, lookback_days)]

    half_complete: list[dict[str, Any]] = []
    today_count = 0
    for step in scanned_steps:
        issues = check_step(step, rating_mode=rating_mode)
        if issues:
            entry = {
                "step_label": step["label"],
                "date": step["date"] or "(无日期)",
                "title": step["title"],
                "issues": issues,
            }
            half_complete.append(entry)
            if step["date"] == today:
                today_count += 1

    status = "has_half_complete" if half_complete else "ok"
    summary = _build_summary(status, len(scanned_steps), half_complete, today_count)

    return {
        "status": status,
        "half_complete_steps": half_complete,
        "total_scanned": len(scanned_steps),
        "today_half_complete": today_count,
        "summary": summary,
    }


def _within_lookback(entry_date: str | None, today: str, lookback_days: int) -> bool:
    if entry_date is None:
        # 无日期的 Step 保守处理：算在扫描范围内（让用户看到也好）
        return True
    try:
        ed = date.fromisoformat(entry_date)
        td = date.fromisoformat(today)
        return (td - ed).days <= lookback_days
    except ValueError:
        return True


def _build_summary(
    status: str,
    total: int,
    half_complete: list[dict[str, Any]],
    today_count: int,
) -> str:
    if status == "no-log-file":
        return "执行日志文件不存在"
    if status == "ok":
        return f"扫描最近 {total} 条 Step，字段齐全"
    parts = [f"扫描最近 {total} 条 Step"]
    parts.append(f"发现 {len(half_complete)} 条半残")
    if today_count > 0:
        parts.append(f"其中 {today_count} 条是今日新增")
    return "，".join(parts)


def format_hint_for_brief(result: dict[str, Any], max_list: int = 5) -> str | None:
    """给 SessionStart brief 注入用的文本。返回 None 表示无需注入。"""
    if result.get("status") != "has_half_complete":
        return None
    half = result["half_complete_steps"]
    if not half:
        return None
    lines = [f"- 发现 {len(half)} 条欠评 / 半残 Step（最近 {result['total_scanned']} 条中）："]
    for s in half[:max_list]:
        issues_desc = "；".join(s["issues"][:2])  # 每条最多两个 issue
        lines.append(f"  · {s['step_label']}（{s['date']}）: {issues_desc}")
    if len(half) > max_list:
        lines.append(f"  · ...还有 {len(half) - max_list} 条未列出")
    lines.append("  · 新会话第一件事：向用户核对评分后补齐，或明确销账 (R-NNN 改进建议 / 标'污染样本' 并接受)")
    return "\n".join(lines)


def format_hint_for_stop(result: dict[str, Any]) -> str | None:
    """给 Stop hook 软提醒用的文本。只关心今日新增的半残。"""
    today_count = result.get("today_half_complete", 0)
    if today_count == 0:
        return None
    today_entries = [s for s in result["half_complete_steps"] if s.get("issues")]
    today_only = [s for s in today_entries if s["date"] == result.get("_today_iso", "")]
    # 退回最后一条标注今日的 Step 详情
    lines = [f"[ieidev-memory] ⚠️ 今日新增 {today_count} 条 Step 但字段半残（用户评分 / 扣分项空）。"]
    for s in today_only[:3]:
        lines.append(f"  · {s['step_label']}: {'; '.join(s['issues'][:2])}")
    lines.append("  · 请当场采集用户评分 + 补扣分项；长期漂移用 R-NNN 改进建议记录。")
    return "\n".join(lines)


def strict_mode_should_block(result: dict[str, Any]) -> bool:
    """strict 模式下是否应该 exit 2 阻塞。仅当今日新增半残 ≥ 1 时。"""
    return result.get("today_half_complete", 0) > 0


def main() -> int:
    """CLI 入口：`step_completeness.py <log_path> [today]` → stdout JSON。"""
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {"status": "usage-error", "summary": "usage: step_completeness.py <log.md> [today_iso]"},
                ensure_ascii=False,
            )
        )
        return 2
    log_path = Path(sys.argv[1])
    today = sys.argv[2] if len(sys.argv) >= 3 else date.today().isoformat()
    result = run_check(log_path, today)
    # 加个内部字段便于 format_hint_for_stop 使用
    result["_today_iso"] = today
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
