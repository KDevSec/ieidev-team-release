#!/usr/bin/env python3
"""ieidev-memory weekly aggregator (v0.8 起为完全独立 CLI，无 bash wrapper)

聚合 .ieidev/memory/ 在指定日期范围内的 Step / Q / G / R 条目，按汇报四段骨架输出 markdown：
  📦 过程资产 / 💡 经验总结 / ⚠️ 问题教训 / 🚀 开发进展

调用：python3 weekly.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [<ieidev_dir>]
  - 默认 ieidev_dir: 当前 cwd 下的 .ieidev/memory
  - 默认 date_to: 今天；默认 date_from: date_to - 6 days

最低 Python 版本：3.7（`from __future__ import annotations` + typing.X）。

迭代历史：
  - v0.7.2 从 weekly.sh 内嵌 heredoc 拆出
  - v0.8.0 吸收 weekly.sh 的 CLI 解析（argparse），weekly.sh 删除
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

# Windows 兼容：强制 stdout/stderr 使用 UTF-8（避免 GBK 无法编码 emoji）
# v0.8.1 起统一走 _utf8.force_utf8_stdio helper
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _utf8 import force_utf8_stdio  # noqa: E402

force_utf8_stdio()

from scope import shared_dir, staff_log_files  # noqa: E402


def in_range(s: str | None, d_from: date, d_to: date) -> bool:
    if not s:
        return False
    try:
        return d_from <= date.fromisoformat(s) <= d_to
    except ValueError:
        return False


def parse_entries(path: Path, head_re: str) -> list[dict]:
    """按 head_re 切条目，每条含 date 字段。"""
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8")
    heads = list(re.finditer(head_re, txt, re.MULTILINE))
    items: list[dict] = []
    for i, m in enumerate(heads):
        start = m.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
        body = txt[start:end]
        dm = re.search(r"^\s*日期[:：]\s*(\d{4}-\d{2}-\d{2})", body, re.MULTILINE)
        entry_date = dm.group(1) if dm else None
        title = m.group(0).lstrip("#").strip()
        items.append({"title": title, "date": entry_date, "body": body})
    return items


def user_score(body: str) -> float | None:
    """从 ### 用户评分 子节里取顺畅度分；缺该子节时退回全文搜索（避免误取模型自评）。"""
    sec = re.search(r"###\s*用户评分.*?(?=###|\Z)", body, re.DOTALL)
    search_body = sec.group(0) if sec else body
    m = re.search(r"^\s*[-*]?\s*顺畅度[:：]\s*([\d.]+)\s*/\s*5", search_body, re.MULTILINE)
    return float(m.group(1)) if m else None


def diff_score(body: str) -> float | None:
    m = re.search(r"差值[:：]\s*([+-]?\d+(?:\.\d+)?)", body)
    return abs(float(m.group(1))) if m else None


def render(kdev: Path, d_from: date, d_to: date) -> None:
    """读 ieidev_dir 内核心文件 + 按四段骨架打印 markdown。"""
    in_range_fn = lambda s: in_range(s, d_from, d_to)  # noqa: E731

    base = shared_dir(kdev)
    steps = [s for s in parse_entries(base / "执行日志.md", r"^##\s+Step\s+\S+.*$") if in_range_fn(s["date"])]
    # per-员工 scope Step 也计入（flat 下 staff_log_files 返回 []）
    staff_step_counts: dict[str, int] = {}
    for scope_id, path in staff_log_files("执行日志.md", kdev):
        scoped = [s for s in parse_entries(path, r"^##\s+Step\s+\S+.*$") if in_range_fn(s["date"])]
        for s in scoped:
            s["scope"] = scope_id
        steps.extend(scoped)
        staff_step_counts[scope_id] = len(scoped)
    ques = [q for q in parse_entries(base / "决策日志.md", r"^##\s+Q-\d+.*$") if in_range_fn(q["date"])]
    gotchas = [g for g in parse_entries(base / "踩坑日志.md", r"^##\s+G-\d+.*$") if in_range_fn(g["date"])]
    rules = [r for r in parse_entries(base / "改进建议.md", r"^##\s+(?:R-\d+|建议\s*#?\s*\d+).*$") if in_range_fn(r["date"])]

    high_score = [s for s in steps if (user_score(s["body"]) or 0) >= 4.5]
    high_diff = [s for s in steps if (diff_score(s["body"]) or 0) >= 1.5]
    gotcha_to_rule = [g for g in gotchas if re.search(r"R-\d+", g["body"])]

    scored = [user_score(s["body"]) for s in steps if user_score(s["body"]) is not None]
    avg_score = round(sum(scored) / len(scored), 2) if scored else None

    daily = base / "每日汇总"
    covered = 0
    total_days = (d_to - d_from).days + 1
    if daily.is_dir():
        cur = d_from
        while cur <= d_to:
            if (daily / f"{cur.isoformat()}.md").exists():
                covered += 1
            cur += timedelta(days=1)

    # ========== 汇报四段骨架 ==========

    # --- 1. 过程资产 ---
    print("## 📦 过程资产（Process Assets）\n")
    print("> 本期 `.ieidev/memory/` 新增的可检索过程素材盘点。\n")
    print(f"- **Step**：{len(steps)} 条")
    print(f"- **决策 Q-NNN**：{len(ques)} 条")
    print(f"- **踩坑 G-NNN**：{len(gotchas)} 条")
    print(f"- **改进信号 R-NNN / 建议**：{len(rules)} 条")
    print(f"- **每日汇总覆盖率**：{covered}/{total_days} 天")
    print(f"- **平均用户评分**：{avg_score if avg_score else '—'}/5\n")
    if staff_step_counts:
        print("- **per-员工 scope Step**：" + "；".join(
            f"{sid} {n} 条" for sid, n in sorted(staff_step_counts.items())))
    if steps:
        print("条目索引（最多 10 条）：")
        for s in steps[:10]:
            print(f"- {s['title']}（{s['date']}）")
        if len(steps) > 10:
            print(f"- ...还有 {len(steps) - 10} 条 Step 未列出")
    print()

    # --- 2. 经验总结 ---
    print("## 💡 经验总结（Experience）\n")
    print("> 本期值得复用、沉淀、扩散的正向信号。\n")
    experience_items: list[str] = []
    for s in high_score:
        experience_items.append(f"- 🏆 **高分 Step {user_score(s['body'])}/5**：{s['title']}（{s['date']}）—— 这条顺畅度高，值得提炼方法论")
    for g in gotcha_to_rule:
        experience_items.append(f"- 📐 **踩坑升规则**：{g['title']} —— 已转化为 R-NNN 规则")
    solid_steps = [
        s for s in steps
        if (user_score(s["body"]) or 0) >= 4
        and (diff_score(s["body"]) or 99) <= 0.5
        and s not in high_score
    ]
    for s in solid_steps[:3]:
        experience_items.append(f"- ✅ **稳扎稳打**：{s['title']} —— 模型自评和用户评分基本一致，执行扎实")
    if not experience_items:
        print("- （本期无高分 Step / 踩坑升规则 / 稳扎稳打信号；可能是推进偏缓或评分未充分采集）")
    else:
        for item in experience_items:
            print(item)
    print()

    # --- 3. 问题教训 ---
    print("## ⚠️ 问题教训（Lessons）\n")
    print("> 本期暴露的方法论盲区、流程失守、差值信号。\n")
    lesson_items: list[str] = []
    for s in high_diff:
        if s not in high_score:
            ds = diff_score(s["body"]) or 0
            lesson_items.append(f"- 🔍 **评分差值 {ds}**：{s['title']}（{s['date']}）—— 模型自评和用户感受落差大，方法论盲区候选")
    unresolved_gotchas = [g for g in gotchas if not re.search(r"R-\d+", g["body"])]
    for g in unresolved_gotchas[:3]:
        lesson_items.append(f"- 🕳️ **待升规则的踩坑**：{g['title']} —— 建议评估是否立 R-NNN")
    low_score = [s for s in steps if (user_score(s["body"]) or 99) < 3]
    for s in low_score[:3]:
        lesson_items.append(f"- 🛑 **低评分**（{user_score(s['body'])}/5）：{s['title']} —— 用户体验受损，值得复盘")
    if not lesson_items:
        print("- （本期无差值 ≥ 1.5 / 低评分 / 未升规则踩坑，方法论表现稳定）")
    else:
        for item in lesson_items:
            print(item)
    print()

    # --- 4. 开发进展 ---
    print("## 🚀 开发进展（Progress）\n")
    print("> 本期实际业务推进、里程碑完成、下期计划。\n")
    state = base / "当前状态.md"
    state_body = state.read_text(encoding="utf-8") if state.exists() else ""

    if state_body:
        cleaned = re.sub(r"^---.*?---\s*\n", "", state_body, flags=re.DOTALL)
        print("**主线状态**（摘自 当前状态.md）：\n")
        print(cleaned.strip()[:500])
        print()
    else:
        print("**主线状态**：（无 当前状态.md，请 Claude 根据 Step 条目总结叙事）\n")

    milestones = [s for s in steps if re.search(r"完成|交付|ship|release|合并|上线|发布", s["title"], re.IGNORECASE)]
    if milestones:
        print("**里程碑**：\n")
        for m in milestones[:5]:
            print(f"- {m['title']}（{m['date']}）")
        print()

    print("**下期展望**：")
    nxt = re.search(r"(?:下一步|next|下周计划)[:：]?\s*\n?(.+?)(?:\n\n|\Z)", state_body, re.DOTALL | re.IGNORECASE) if state_body else None
    if nxt:
        print(f"\n{nxt.group(1).strip()[:500]}\n")
    else:
        print('（当前状态.md 未填"下一步"字段，请 Claude 整理 Step 推演下期重点）\n')

    # --- 附：待沉淀候选 ---
    print("## 📌 附录：待沉淀候选（→ docs/）\n")
    print("（执行 `/ieidev-team:memory-distill` 查看完整候选列表与去向建议）\n")

    if not (steps or ques or gotchas or rules):
        print()
        print(f"\n**本周范围内无记录**（{d_from} ~ {d_to} 在 .ieidev/memory/ 里没有对应日期的条目）")


def main() -> int:
    """v0.8 起：吸收原 weekly.sh 的 CLI 参数解析 + 默认日期 + 友好提示 + 目录检查，
    weekly.sh 已删除。直接调用 `python3 weekly.py [--from X --to Y] [<ieidev_dir>]`。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="ieidev-memory 滚动 7 天周总结（默认 today-6 ~ today），输出按汇报四段骨架组织"
    )
    parser.add_argument(
        "--from", dest="date_from", default=None,
        help="起始日期 YYYY-MM-DD（默认：date_to - 6 days）",
    )
    parser.add_argument(
        "--to", dest="date_to", default=None,
        help="结束日期 YYYY-MM-DD（默认：今天）",
    )
    parser.add_argument(
        "ieidev_dir", nargs="?", default=".ieidev/memory",
        help="`.ieidev/memory` 目录路径（默认：当前 cwd 下的 .ieidev/memory）",
    )
    args = parser.parse_args()

    today = date.today()
    try:
        d_to = date.fromisoformat(args.date_to) if args.date_to else today
        d_from = date.fromisoformat(args.date_from) if args.date_from else d_to - timedelta(days=6)
    except ValueError as e:
        print(f"weekly.py: invalid date — {e}", file=sys.stderr)
        return 2

    kdev = Path(args.ieidev_dir)
    if not kdev.is_dir():
        print(f"[ieidev-memory] 当前项目无 {kdev}，无法生成周总结")
        return 0

    print(
        f"（默认汇总过去 7 天 {d_from} ~ {d_to}；"
        "可用 `--from YYYY-MM-DD --to YYYY-MM-DD` 指定范围）"
    )
    print()

    render(kdev, d_from, d_to)
    return 0


if __name__ == "__main__":
    sys.exit(main())
