#!/usr/bin/env python3
"""ieidev-memory Stop hook（v0.8 转 Python，逻辑沿用 v0.7）

每次 Claude 要停下时检查 .ieidev/ 状态并向 Claude 注入提醒文本。

六条软提醒规则（stdout，exit 0）：
  1. 项目无 .ieidev/        → 静默退出
  2. 今天无汇总            → 提醒生成
  3. 汇总存在但源文件更新   → 提醒追加新增条目
  4. 执行日志今天空         → 提醒实时落盘
  5. 过去日期有条目但缺汇总 → 提醒补写（跨天会话遗漏的兜底）
  6. 主文件跨月/跨季度       → 提醒归档切档
  7. Step 完整度扫描        → 今日新增 Step 字段半残软提醒

阻塞规则（stderr，exit 2）—— 仅当 .ieidev/memory/strict 开关存在时启用。
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from _utf8 import force_utf8_stdio  # noqa: E402
force_utf8_stdio()  # Windows GBK 兼容：v0.8.1+ 统一处理 emoji 编码

from migrate import ieidev_memory_migrate  # noqa: E402
from milestone import is_milestone_path  # noqa: E402
from missing_summaries import list_missing_past_summaries  # noqa: E402
from archive_hint import collect_archive_hints  # noqa: E402
from pending_commits import format_brief_hint as pending_format_brief_hint  # noqa: E402
from scope import shared_dir  # noqa: E402
from memory_config import read_rating_mode  # noqa: E402


def _read_stop_hook_active() -> bool:
    if sys.stdin.isatty():
        return False
    try:
        raw = sys.stdin.read()
    except OSError:
        return False
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return False
    return bool(data.get("stop_hook_active"))


def _step_completeness_scan(
    log_path: Path, today: str, rating_mode: str
) -> Tuple[int, str]:
    """调 step_completeness.py 模块，返回 (today_half_count, hint_text)。"""
    lib = LIB_DIR / "step_completeness.py"
    if not lib.is_file() or not log_path.is_file():
        return 0, ""
    try:
        spec = importlib.util.spec_from_file_location("step_completeness", lib)
        if spec is None or spec.loader is None:
            return 0, ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.run_check(log_path, today, rating_mode=rating_mode)
        result["_today_iso"] = today
        hint = mod.format_hint_for_stop(result) or ""
        count = int(result.get("today_half_complete", 0) or 0)
        return count, hint
    except Exception:
        return 0, ""


def _porcelain_substantive_changes() -> Tuple[int, bool]:
    """读 git status --porcelain，统计实质变更数 + 命中里程碑标记。"""
    try:
        in_repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return 0, False
    if in_repo.returncode != 0:
        return 0, False

    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return 0, False
    if r.returncode != 0 or not r.stdout.strip():
        return 0, False

    substantive = 0
    milestone_hit = False
    for line in r.stdout.splitlines():
        if not line:
            continue
        # porcelain 格式："XY path" 或 "XY path -> newpath"
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        # 去 porcelain 对含空格路径加的引号
        path = path.strip('"')

        if path.startswith(".ieidev/"):
            # .ieidev/ 内部变更通常不计入"实质工作"
            # 例外：白名单命中（如 .ieidev/方法论铁规.md）
            if is_milestone_path(path):
                milestone_hit = True
                substantive += 1
        else:
            substantive += 1
            if is_milestone_path(path):
                milestone_hit = True

    return substantive, milestone_hit


def main() -> int:
    ieidev_memory_migrate()

    ieidev_dir = Path(".ieidev/memory")
    if not ieidev_dir.is_dir():
        return 0

    shared = shared_dir(ieidev_dir)
    today = date.today().isoformat()
    rating_mode = read_rating_mode(ieidev_dir)
    summary_file = shared / "每日汇总" / f"{today}.md"

    stop_hook_active = _read_stop_hook_active()

    reminders: List[str] = []

    # 2. 今天无汇总
    if not summary_file.is_file():
        reminders.append(
            f"[ieidev-memory] 今天（{today}）还没有生成每日汇总。"
            f"如果本轮是当日最后一次工作，请调用 ieidev-memory skill 从 .ieidev/memory/ 聚合当天记录生成汇总。"
        )
    else:
        # 3. 汇总存在 → 检查源文件 mtime 是否 > 汇总
        stale: List[str] = []
        try:
            sm = summary_file.stat().st_mtime
        except OSError:
            sm = 0.0
        for name in ("执行日志.md", "决策日志.md", "踩坑日志.md", "改进建议.md"):
            src = shared / name
            if not src.is_file():
                continue
            try:
                if src.stat().st_mtime > sm:
                    stale.append(name)
            except OSError:
                pass
        if stale:
            reminders.append(
                f"[ieidev-memory] 今天的每日汇总（{summary_file}）生成后，"
                f"这些源文件又有新活动：{' '.join(stale)}。"
                f"若本轮是最后一次会话，请将新增条目追加到汇总末尾（不要覆盖已有内容）。"
            )

    # 4. 执行日志今天空
    log_file = shared / "执行日志.md"
    log_empty_today = False
    if log_file.is_file():
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if today not in text:
            log_empty_today = True
            reminders.append(
                "[ieidev-memory] 执行日志里今天没有任何条目。如果本轮完成了工作步骤，"
                "请实时追加 Step 记录到 .ieidev/memory/执行日志.md。"
            )

    # 5. 过去日期缺每日汇总
    missing_past = list_missing_past_summaries(str(ieidev_dir), today)
    if missing_past:
        reminders.append(
            f"[ieidev-memory] ⚠️ 过去日期在 .ieidev/memory/ 源文件里有条目，"
            f"但 每日汇总/<日期>.md 不存在：{missing_past}。"
            f"典型原因是跨天会话未关，SessionEnd 没触发。"
            f"请调用 ieidev-memory skill 按这些日期聚合源文件生成汇总——严禁回翻会话上下文；"
            f"若某日源文件信息不足请在汇总里坦白标注。"
        )

    # 6. 归档提醒
    archive_hints = collect_archive_hints(str(ieidev_dir))
    if archive_hints:
        reminders.append(
            f"[ieidev-memory] 📦 主文件已跨越归档边界，建议调用 ieidev-memory skill 切档"
            f"（将老条目迁到归档文件，主文件只留当前月/当前季）：\n{archive_hints}"
            f"切档步骤见 SKILL.md 的「文件切档与归档」章节。改进建议.md 不切档。"
        )

    # 7. Step 完整度扫描（按 rating.mode 降级）
    #   model-only：完全跳过半残检测；user-opt-in / user-required：照扫
    if rating_mode == "model-only":
        step_today_half, step_hint = 0, ""
    else:
        step_today_half, step_hint = _step_completeness_scan(log_file, today, rating_mode)
        if step_hint:
            reminders.append(step_hint)

    # 8. pending-commits 阈值软提醒
    state_dir = ieidev_dir / "state"
    pending_hint = pending_format_brief_hint(state_dir, now=int(time.time()))
    if pending_hint:
        reminders.append(pending_hint)

    # ---- 严格模式：阻塞 ----
    strict_flag = (ieidev_dir / "strict").is_file()
    if not stop_hook_active and strict_flag and log_empty_today:
        substantive, milestone_hit = _porcelain_substantive_changes()
        if substantive >= 2 or milestone_hit:
            sys.stderr.write(
                f"[ieidev-memory/strict] 检测到 .ieidev/memory/执行日志.md 今天无任何条目，"
                f"但工作区有 {substantive} 处未提交变更（命中里程碑={'yes' if milestone_hit else 'no'}）。\n"
                f"请先追加至少一条 Step 记录到 .ieidev/memory/执行日志.md"
                f"（说明今天完成了哪些工作单元、产出物路径、模型自评），再结束本轮。\n"
                f"如需临时关闭严格模式：rm .ieidev/memory/strict\n"
            )
            return 2

    if not stop_hook_active and strict_flag and step_today_half > 0 and rating_mode == "user-required":
        sys.stderr.write(
            f"[ieidev-memory/strict] 今日新增 {step_today_half} 条 Step 但字段半残"
            f"（用户评分段时分戳空 / 扣分项空 等）。\n"
            f"请当场采集用户评分 + 补扣分项，再结束本轮。"
            f"长期漂移用 R-NNN 改进建议记录。\n"
            f"如需临时关闭严格模式：rm .ieidev/memory/strict\n"
        )
        return 2

    # 软提醒输出
    if reminders:
        sys.stdout.write("\n".join(reminders) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
