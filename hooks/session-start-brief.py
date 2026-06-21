#!/usr/bin/env python3
"""ieidev-memory SessionStart hook（v0.8 转 Python，逻辑沿用 v0.7.1+）

新会话启动时向 Claude 注入 .ieidev/memory/ 当前状态摘要 + ⚠️ 待处理事项。
按 source 分档：
  - startup / clear：完整摘要
  - resume：精简（Claude 已有前文上下文）
  - compact：提醒 checkpoint 在哪

输出格式：JSON (hookSpecificOutput.additionalContext) 注入。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

from _utf8 import force_utf8_stdio  # noqa: E402
force_utf8_stdio()  # Windows GBK 兼容：v0.8.1+ 统一处理 emoji 编码

from migrate import ieidev_memory_migrate  # noqa: E402
from frontmatter import read_state_field  # noqa: E402
from missing_summaries import list_missing_past_summaries  # noqa: E402
from worktree_link import worktree_link_kdev  # noqa: E402
from promote_scan import scan_promote_candidates  # noqa: E402
from distill_trigger import check_distill_trigger  # noqa: E402
from pending_commits import format_brief_hint as pending_format_brief_hint  # noqa: E402
from skill_version import detect_drift as skill_detect_drift  # noqa: E402
from scope import shared_dir, list_staff, staff_dir  # noqa: E402
from memory_config import read_rating_mode, rating_mode_configured, read_brief_verbosity  # noqa: E402

SUPPRESS = json.dumps({"continue": True, "suppressOutput": True})


def _read_source() -> Tuple[str, str]:
    """返回 (source, session_id)。"""
    if sys.stdin.isatty():
        return "startup", "unknown"
    try:
        raw = sys.stdin.read()
    except OSError:
        return "startup", "unknown"
    if not raw:
        return "startup", "unknown"
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return "startup", "unknown"
    source = data.get("source") or "startup"
    session_id = str(data.get("session_id") or "unknown")
    return source, session_id


def _git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def _glob_warn_files(ieidev_dir: Path, max_items: int = 5) -> List[str]:
    return sorted(str(p) for p in ieidev_dir.glob("WARN-*.md"))[:max_items]


def _glob_checkpoint_files(ieidev_dir: Path, max_items: int = 3) -> List[str]:
    cp_dir = ieidev_dir / "checkpoints"
    if not cp_dir.is_dir():
        return []
    files = [p for p in cp_dir.glob("压缩前-*.md") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in files[:max_items]]


def _log_today_status(log_file: Path, today: str) -> str:
    if not log_file.is_file():
        return "空"
    try:
        text = log_file.read_text(encoding="utf-8")
    except OSError:
        return "空"
    if today not in text:
        return "空"
    step_count = sum(1 for line in text.splitlines() if line.startswith("## Step "))
    return f"今日有 {step_count} 条 Step（含历史）"


def _last_heading(path: Path, prefix: str) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    last = ""
    for line in text.splitlines():
        if line.startswith(prefix):
            last = line
    return last


def _staff_scope_block(ieidev_dir: Path) -> str:
    """scoped 布局：列每个员工 scope 的 Step 数 + 最新 Step。flat → 空字符串。"""
    staff = list_staff(ieidev_dir)
    if not staff:
        return ""
    lines = ["", "👥 **员工 scope 进度**："]
    for sid in staff:
        log = staff_dir(sid, ieidev_dir) / "执行日志.md"
        count = 0
        latest = ""
        if log.is_file():
            try:
                text = log.read_text(encoding="utf-8")
            except OSError:
                text = ""
            for line in text.splitlines():
                if line.startswith("## Step "):
                    count += 1
                    latest = line[len("## "):].strip()
        tail = f"（最新 {latest}）" if latest else ""
        lines.append(f"- {sid}: {count} 条 Step{tail}")
    return "\n".join(lines)


def _claude_md_drift_hint() -> str:
    """跑 claude_md_lint.run_lint，返回 brief hint 或空字符串。"""
    contract_file = SCRIPT_DIR.parent / "skills" / "ieidev-memory" / "references" / "初始化-claude-md-模板.md"
    lint_lib = LIB_DIR / "claude_md_lint.py"
    claude_md = Path("CLAUDE.md")
    if not (claude_md.is_file() and contract_file.is_file() and lint_lib.is_file()):
        return ""
    try:
        spec = importlib.util.spec_from_file_location("claude_md_lint", lint_lib)
        if spec is None or spec.loader is None:
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.run_lint(contract_file, claude_md)
        return mod.format_hint_for_brief(result) or ""
    except Exception:
        return ""


def _distill_hint(ieidev_dir: Path) -> str:
    """蒸馏触发提醒（详见 references/蒸馏触发机制.md）。

    - mode=auto + should_trigger → 后台 Popen 跑 distill.py --auto-context；
      brief 注入 "已开始后台自动蒸馏"
    - mode=manual + should_trigger → brief 注入 "建议蒸馏：[原因]，跑 /ieidev-team:memory-distill"
    - mode=auto 且 .last-distill-auto 在最近 24h 内 → brief 注入 "上次自动蒸馏完成于 X"
    - 否则返回空字符串（不注入）

    失败时不抛错（hook 必须健壮）：返回空字符串。
    """
    try:
        check = check_distill_trigger(ieidev_dir)
    except Exception:
        return ""

    # 检查是否有最近的自动蒸馏成功标记
    auto_marker = ieidev_dir / ".last-distill-auto"
    recent_auto_msg = ""
    if auto_marker.is_file():
        try:
            mtime = auto_marker.stat().st_mtime
            import time
            age_hours = (time.time() - mtime) / 3600
            if age_hours <= 24:
                from datetime import datetime
                when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                recent_auto_msg = (
                    f"  - 🤖 上次自动蒸馏完成于 {when}（数据集在 .ieidev/memory/dataset/）"
                )
        except OSError:
            pass

    if not check.should_trigger:
        # 不触发但仍要把最近的自动蒸馏标记露出来
        return recent_auto_msg

    reasons_str = "；".join(check.reasons) if check.reasons else "阈值满足"

    if check.mode == "auto":
        # auto 模式：后台 Popen 跑 distill.py，不阻塞 hook
        try:
            import subprocess
            distill_lib = SCRIPT_DIR / "lib" / "distill.py"
            if distill_lib.is_file():
                subprocess.Popen(
                    [sys.executable, str(distill_lib), str(ieidev_dir), "--auto-context"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,  # detach 子进程，hook 立刻可返回
                )
                msg = (
                    f"  - 🤖 **已开始后台自动蒸馏**（{reasons_str}）—— "
                    f"结果将在 .ieidev/memory/dataset/，失败时会写 WARN-distill-failed-*.md。"
                    f"\n    （如不希望自动跑，可在 .ieidev/memory/config.yaml 写 `distill.mode: manual`）"
                )
                return msg + ("\n" + recent_auto_msg if recent_auto_msg else "")
        except Exception:
            # Popen 失败 → 降级为 manual 提醒
            pass

    # manual 模式 或 auto Popen 失败 → 仅提醒
    msg = (
        f"  - 📋 **建议蒸馏**（{reasons_str}）—— "
        f"跑 `/ieidev-team:memory-distill` 把项目记录沉淀到 docs/ + 打包到 .ieidev/memory/dataset/"
    )
    return msg + ("\n" + recent_auto_msg if recent_auto_msg else "")


def _step_hint(log_file: Path, today: str, rating_mode: str = "user-required", max_list: int = 5) -> str:
    """跑 step_completeness.run_check + format_hint_for_brief。"""
    lint_lib = LIB_DIR / "step_completeness.py"
    if not (log_file.is_file() and lint_lib.is_file()):
        return ""
    try:
        spec = importlib.util.spec_from_file_location("step_completeness", lint_lib)
        if spec is None or spec.loader is None:
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.run_check(log_file, today, rating_mode=rating_mode)
        return mod.format_hint_for_brief(result, max_list=max_list) or ""
    except Exception:
        return ""


def _rating_setup_hint(ieidev_dir: Path) -> str:
    """首次（config 无 rating.mode 键、且未提示过）→ 返回一次性评分模式设置提示。

    用 state/.rating-setup-shown marker 去重，保证"一次性"。已配置或已提示过 → 空串。
    """
    if rating_mode_configured(ieidev_dir):
        return ""
    marker = ieidev_dir / "state" / ".rating-setup-shown"
    if marker.is_file():
        return ""
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError:
        pass
    return (
        "<ieidev-memory-rating-setup>\n"
        "ieidev-memory 评分模式可配置。当前默认 user-opt-in（自评后轻提一句，不回应就过）。\n"
        "• 说\"关掉评分\"→ model-only（只模型自评，零追问）\n"
        "• 说\"严格评分\"→ user-required（每 Step 必追问）\n"
        "• 随时一句话切换，Claude 改 config.yaml 立即生效。\n"
        "</ieidev-memory-rating-setup>"
    )


def _build_brief(
    mode: str,
    today: str,
    git_branch: str,
    warn_files: List[str],
    checkpoint_files: List[str],
    log_today: str,
    summary_today_status: str,
    missing_past: str,
    drift_hint: str,
    step_hint: str,
    promote_hint: str,
    distill_hint: str,
    state_phase: str,
    state_iter: str,
    state_step: str,
    state_last: str,
    state_pending: str,
    state_unresolved: str,
    recent_step: str,
    recent_q: str,
    recent_g: str,
    pending_hint: str = "",
    skill_drift_hint: str = "",
    staff_block: str = "",
    rating_setup_hint: str = "",
    verbosity: str = "normal",
) -> str:
    """按 mode 组装 brief 文本。返回带换行的 markdown 字符串。"""

    # ---- 三层分层共享计算 ----
    p0_lines: List[str] = []
    p1_lines: List[str] = []
    p2_lines: List[str] = []

    # P0: WARN 文件 + 今日半残 Step
    for w in warn_files:
        p0_lines.append(f"  - {w}")
    if step_hint and "今日" in step_hint:
        p0_lines.append(step_hint)

    # P1: 跨天汇总缺失 / CLAUDE.md 漂移 / 历史半残 / 沉淀提醒
    if missing_past:
        p1_lines.append(
            f"  - 过去日期缺每日汇总（跨天会话遗漏）：{missing_past} —— "
            f"调用 ieidev-memory skill 按日聚合源文件补写，严禁回翻会话上下文"
        )
    if drift_hint:
        p1_lines.append(drift_hint)
    if step_hint and "今日" not in step_hint:
        p1_lines.append(step_hint)
    if promote_hint:
        p1_lines.append(promote_hint.rstrip("\n"))
    if distill_hint:
        p1_lines.append(distill_hint.rstrip("\n"))

    # P2: checkpoint references
    for c in checkpoint_files:
        p2_lines.append(f"  - {c}")

    p0_block = "\n".join(p0_lines) + ("\n" if p0_lines else "")
    p1_block = "\n".join(p1_lines) + ("\n" if p1_lines else "")
    p2_block = "\n".join(p2_lines) + ("\n" if p2_lines else "")

    parts: List[str] = []

    if mode == "resume":
        parts.append("项目有 .ieidev/ 工程记忆。本次会话是 resume（Claude 已有前文上下文）。")
        if p0_block or p1_block:
            parts.append("⚠️ 待处理：")
            if p0_block:
                parts.append("🔴 " + p0_block.rstrip("\n"))
            if p1_block:
                parts.append("🟡 " + p1_block.rstrip("\n"))
        if rating_setup_hint:
            parts.append("\n" + rating_setup_hint)
    elif mode == "compact":
        parts.append("项目有 .ieidev/ 工程记忆。刚从压缩中恢复。")
        if checkpoint_files:
            parts.append("📦 压缩前 checkpoint（可回读细节）：")
            parts.extend(f"  - {c}" for c in checkpoint_files)
        if p0_block:
            parts.append("🔴 未处理的 P0 阻塞：\n" + p0_block.rstrip("\n"))
        if p1_block:
            parts.append("🟡 需核对：\n" + p1_block.rstrip("\n"))
        if rating_setup_hint:
            parts.append("\n" + rating_setup_hint)
    else:
        # startup / clear / default
        if verbosity == "compact":
            cparts: List[str] = [f"项目有 .ieidev/ 工程记忆（brief.verbosity=compact）。当前（{today}）："]
            for w in warn_files:
                cparts.append(f"🔴 {w}")
            if step_hint and "今日" in step_hint:
                cparts.append("🔴 " + step_hint)
            if state_pending:
                cparts.append(f"- pending_decisions: {state_pending}")
            prog_one = f"📊 今日进度：执行日志 {log_today}；汇总 {summary_today_status}"
            if git_branch:
                prog_one += f"；分支 {git_branch}"
            cparts.append(prog_one)
            cparts.append("🗂 完整 brief（项目状态/最近条目/半残/distill/promote）已写入 "
                          ".ieidev/memory/brief-detail.md，按需 Read。")
            if rating_setup_hint:
                cparts.append("\n" + rating_setup_hint)
            return "\n".join(cparts)

        parts.append(f"项目有 .ieidev/ 工程记忆。当前状态（{today}）：\n")
        if p0_block:
            parts.append("🔴 **P0 硬阻塞（立刻处理）**：\n" + p0_block)
        if p1_block:
            parts.append("🟡 **P1 需核对**：\n" + p1_block)
        if p2_block:
            parts.append("⚪ **P2 参考**：\n" + p2_block)

        prog = ["📊 **今日进度**：", f"- 执行日志：{log_today}", f"- 每日汇总：{summary_today_status}"]
        if git_branch:
            prog.append(f"- 当前分支：{git_branch}")
        if pending_hint:
            prog.append(f"- {pending_hint}")
        if skill_drift_hint:
            prog.append(f"- {skill_drift_hint}")
        parts.append("\n".join(prog))

        if state_phase or state_iter or state_step:
            state_block = ["", "🎯 **项目状态（来自 当前状态.md frontmatter）**："]
            if state_phase:
                state_block.append(f"- phase: {state_phase}")
            if state_iter:
                state_block.append(f"- iteration: {state_iter}")
            if state_step:
                state_block.append(f"- current_step: {state_step}")
            if state_last:
                state_block.append(f"- last_updated: {state_last}")
            if state_pending:
                state_block.append(f"- pending_decisions: {state_pending}")
            if state_unresolved:
                state_block.append(f"- unresolved_gotchas: {state_unresolved}")
            parts.append("\n".join(state_block))

        if recent_step or recent_q or recent_g:
            recent = ["", "📝 **最近条目**："]
            if recent_step:
                recent.append(f"- {recent_step}")
            if recent_q:
                recent.append(f"- {recent_q}")
            if recent_g:
                recent.append(f"- {recent_g}")
            parts.append("\n".join(recent))

        if staff_block:
            parts.append(staff_block)

        parts.append("\n💡 **建议**：如需详细上下文，Read .ieidev/memory/当前状态.md 和最近的 .ieidev/memory/每日汇总/*.md。")
        if rating_setup_hint:
            parts.append("\n" + rating_setup_hint)

    return "\n".join(parts)


def main() -> int:
    # 自动迁移
    ieidev_memory_migrate()

    # secondary worktree 自动 symlink/junction
    try:
        worktree_link_kdev()
    except Exception:
        pass

    ieidev_dir = Path(".ieidev/memory")
    today = date.today().isoformat()
    git_branch = _git_branch()

    if not ieidev_dir.is_dir():
        print(SUPPRESS)
        return 0

    shared = shared_dir(ieidev_dir)
    rating_mode = read_rating_mode(ieidev_dir)
    verbosity = read_brief_verbosity(ieidev_dir)
    rating_setup_hint = _rating_setup_hint(ieidev_dir)

    source, session_id = _read_source()

    # 数据收集
    warn_files = _glob_warn_files(ieidev_dir)
    checkpoint_files = _glob_checkpoint_files(ieidev_dir)
    log_file = shared / "执行日志.md"
    log_today = _log_today_status(log_file, today)
    summary_today_status = "已生成" if (shared / "每日汇总" / f"{today}.md").is_file() else "未生成"
    missing_past = list_missing_past_summaries(str(ieidev_dir), today)
    drift_hint = _claude_md_drift_hint()
    step_hint = _step_hint(log_file, today, rating_mode=rating_mode,
                           max_list=999 if verbosity == "verbose" else 5)
    promote_hint = scan_promote_candidates(str(ieidev_dir), today)
    distill_hint = _distill_hint(ieidev_dir)

    state_phase = read_state_field("phase")
    state_iter = read_state_field("iteration")
    state_step = read_state_field("current_step")
    state_last = read_state_field("last_updated")
    state_pending = read_state_field("pending_decisions")
    state_unresolved = read_state_field("unresolved_gotchas")

    recent_step = _last_heading(log_file, "## Step ")
    recent_q = _last_heading(shared / "决策日志.md", "## Q")   # "## Q" catches both "Q-NNN" and "Q YYYYMMDD-..."
    recent_g = _last_heading(shared / "踩坑日志.md", "## G")   # "## G" catches both "G-NNN" and "G YYYYMMDD-..."
    staff_block = _staff_scope_block(ieidev_dir)

    # pending-commits hint
    pending_hint = pending_format_brief_hint(
        ieidev_dir / "state",
        now=int(time.time()),
    )

    # R-005: SKILL.md SHA drift check
    cached_sha, current_sha = skill_detect_drift(session_id, Path.cwd(), ieidev_dir / "state")
    if cached_sha is not None and current_sha is not None and cached_sha != current_sha:
        skill_drift_hint = (
            f"⚠️ SKILL.md 在你会话启动后被升级"
            f"（cached={cached_sha[:7]} → current={current_sha[:7]}）— "
            f"建议 /clear restart 加载新 skill"
        )
    else:
        skill_drift_hint = ""

    brief_kwargs = dict(
        mode=source, today=today, git_branch=git_branch, warn_files=warn_files,
        checkpoint_files=checkpoint_files, log_today=log_today,
        summary_today_status=summary_today_status, missing_past=missing_past,
        drift_hint=drift_hint, step_hint=step_hint, promote_hint=promote_hint,
        distill_hint=distill_hint, state_phase=state_phase, state_iter=state_iter,
        state_step=state_step, state_last=state_last, state_pending=state_pending,
        state_unresolved=state_unresolved, recent_step=recent_step, recent_q=recent_q,
        recent_g=recent_g, pending_hint=pending_hint or "", skill_drift_hint=skill_drift_hint,
        staff_block=staff_block, rating_setup_hint=rating_setup_hint, verbosity=verbosity,
    )
    brief = _build_brief(**brief_kwargs)

    if verbosity == "compact" and source in ("startup", "clear", "default", ""):
        # source "compact" = 压缩后恢复会话，由上面的 mode=="compact" 分支处理，不写 detail
        # 把"全量 normal brief"写盘供主动查阅（compact 注入的是裁剪版）
        detail = _build_brief(**{**brief_kwargs, "mode": "startup",
                                 "rating_setup_hint": "", "verbosity": "normal"})
        try:
            (ieidev_dir / "brief-detail.md").write_text(
                f"# ieidev-memory brief-detail（{today} 全量）\n\n{detail}\n", encoding="utf-8")
        except OSError:
            pass

    if not brief.strip():
        print(SUPPRESS)
        return 0

    full = f"<ieidev-memory-brief>\n{brief}\n</ieidev-memory-brief>"

    print(json.dumps({
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": full,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
