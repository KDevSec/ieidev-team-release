"""ieidev-memory 蒸馏触发检测（详见 references/蒸馏触发机制.md）

回答两个问题：
1. 当前是否应该触发蒸馏？（基于时间 + 数据增长阈值，AND 语义）
2. 触发后该 auto 后台跑 还是 manual 仅提醒？（基于 config.distill.mode）

设计哲学：
- 阈值用 AND（时间 ≥ 7 天 AND 有新数据），避免没新数据时空跑、避免短期内疯狂跑
- 数据增长阈值用 OR（F 新增 ≥10 OR misalign 新增 ≥3 OR R 新增 ≥5），任一满足即算"有新数据"
- 默认 auto 模式（用户拍板 2026-05-16）——opt-out 比 opt-in 摩擦小
- 失败必须显式 WARN 而非静默（避免数据集质量潜伏问题）

被 session-start-brief.py 调用；返回结构化结果让调用方决定 brief 怎么注入 / 是否 Popen 后台跑。
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from memory_config import read_distill_mode, read_distill_thresholds  # noqa: E402
from scope import shared_dir  # noqa: E402


@dataclass
class TriggerCheck:
    """蒸馏触发检测结果。"""
    should_trigger: bool                 # 是否到点（时间 AND 数据增长都满足）
    mode: str                            # "auto" | "manual"
    days_since_distill: int | None       # 距上次蒸馏天数（None = 从未蒸馏）
    new_f_count: int                     # 上次蒸馏后 F-NNN 新增条数
    new_misalign_count: int              # 上次蒸馏后 misalign Step 新增条数
    new_r_count: int                     # 上次蒸馏后 R-NNN 新增条数
    thresholds: dict[str, int] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)  # 触发原因可读列表（给 brief 注入）

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _last_distill_timestamp(ieidev_dir: Path) -> float | None:
    """读 .last-distill 的 mtime（秒）。兼容旧 .last-promote 文件（取较新者）。

    返回 None 表示从未蒸馏过。
    """
    candidates = [ieidev_dir / ".last-distill", ieidev_dir / ".last-promote"]
    timestamps: list[float] = []
    for p in candidates:
        if p.is_file():
            try:
                timestamps.append(p.stat().st_mtime)
            except OSError:
                pass
    return max(timestamps) if timestamps else None


def _count_entries_after(file_path: Path, prefix_re: str, since_ts: float | None) -> int:
    """统计文件里 mtime > since_ts 的条目数（粗略估计：用文件的最后修改时间作为单条 mtime）。

    这是近似法 —— 真要精准要解析每条 frontmatter 的 `日期：` 字段。当前版本：
    - 如果文件 mtime > since_ts，则统计整文件的条目数（保守计：所有条目都算新）
    - 如果文件 mtime ≤ since_ts，返回 0
    - 这是合理的下限近似 —— 用户改过文件就说明有新增

    更精准的 per-entry mtime 留给 v2（要按"日期：YYYY-MM-DD"字段过滤）。
    """
    import re
    if not file_path.is_file():
        return 0
    try:
        file_mtime = file_path.stat().st_mtime
    except OSError:
        return 0

    # 文件未动 → 0
    if since_ts is not None and file_mtime <= since_ts:
        return 0

    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    pat = re.compile(prefix_re, re.MULTILINE)
    if since_ts is None:
        return len(pat.findall(text))

    # 文件 mtime > since_ts → 按"日期：YYYY-MM-DD"过滤（如果有该字段）
    # 用更精准的方法：按 ## heading 切，每条找日期字段
    head_re = re.compile(r"^##\s+\S+.*$", re.MULTILINE)
    date_re = re.compile(r"^\s*日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
    heads = list(head_re.finditer(text))
    count = 0
    for i, m in enumerate(heads):
        # 只看该 prefix 的 heading
        if not pat.match(m.group(0)):
            continue
        start = m.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        dm = date_re.search(body)
        if dm:
            try:
                entry_dt = datetime.fromisoformat(dm.group(1))
                if entry_dt.timestamp() > since_ts:
                    count += 1
            except ValueError:
                pass
        else:
            # 没日期字段，保守计为新（避免漏报）
            count += 1
    return count


def _count_misalign_after(execution_log: Path, since_ts: float | None) -> int:
    """统计上次蒸馏后差值 ≥ 1.5 的 Step 条数。

    需要解析 Step 条目的"评分差异分析"段。
    """
    import re
    if not execution_log.is_file():
        return 0

    try:
        text = execution_log.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    step_head = re.compile(r"^##\s+Step\s+\S+.*$", re.MULTILINE)
    diff_re = re.compile(r"差值\s*(?:[:：]\s*)?([+-]?\d+(?:\.\d+)?)")
    date_re = re.compile(r"^\s*日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
    heads = list(step_head.finditer(text))

    count = 0
    for i, m in enumerate(heads):
        start = m.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]

        # 时间过滤
        if since_ts is not None:
            dm = date_re.search(body)
            if dm:
                try:
                    entry_dt = datetime.fromisoformat(dm.group(1))
                    if entry_dt.timestamp() <= since_ts:
                        continue
                except ValueError:
                    pass

        # 差值过滤
        dv = diff_re.search(body)
        if dv:
            try:
                if abs(float(dv.group(1))) >= 1.5:
                    count += 1
            except ValueError:
                pass

    return count


def check_distill_trigger(ieidev_dir: Path | str = ".ieidev/memory") -> TriggerCheck:
    """主入口：检测当前是否到点蒸馏 + 给出原因 + 决定 auto/manual 走向。

    触发逻辑（AND 语义）：
    1. 距上次蒸馏 ≥ reminder_days
    2. 至少一个数据增长阈值满足：F 新增 ≥ reminder_new_f
       OR misalign Step 新增 ≥ reminder_new_misalign
       OR R 新增 ≥ 5（硬编码兜底，捕获改进信号积累）

    从未蒸馏（.last-distill 不存在）+ 有任何数据 → 视为应该首次蒸馏。
    """
    kdev = Path(ieidev_dir)
    mode = read_distill_mode(kdev)
    thresholds = read_distill_thresholds(kdev)

    last_ts = _last_distill_timestamp(kdev)
    now = time.time()

    if last_ts is None:
        days_since = None
    else:
        days_since = int((now - last_ts) // 86400)

    # 数据增长统计
    new_f = _count_entries_after(shared_dir(kdev) / "skill-feedback.md", r"^##\s+F-\d+", last_ts)
    new_r = _count_entries_after(shared_dir(kdev) / "改进建议.md", r"^##\s+R-\d+", last_ts)
    new_misalign = _count_misalign_after(shared_dir(kdev) / "执行日志.md", last_ts)

    reasons: list[str] = []

    # 时间满足？
    time_ok = (days_since is None) or (days_since >= thresholds["reminder_days"])
    if days_since is None:
        reasons.append("首次蒸馏（从未跑过）")
    elif time_ok:
        reasons.append(f"距上次蒸馏已 {days_since} 天（阈值 {thresholds['reminder_days']} 天）")

    # 数据增长满足？
    data_ok = False
    if new_f >= thresholds["reminder_new_f"]:
        data_ok = True
        reasons.append(f"F-NNN 新增 {new_f} 条（阈值 {thresholds['reminder_new_f']}）")
    if new_misalign >= thresholds["reminder_new_misalign"]:
        data_ok = True
        reasons.append(f"misalign Step 新增 {new_misalign} 条（阈值 {thresholds['reminder_new_misalign']}）")
    if new_r >= 5:
        data_ok = True
        reasons.append(f"R-NNN 改进建议新增 {new_r} 条（阈值 5）")

    # 首次蒸馏特殊处理：只要有任意数据就触发（用户没基线，应当尽早导出首批数据集）
    if last_ts is None and (new_f + new_r + new_misalign > 0):
        data_ok = True
    elif last_ts is None:
        # 首次蒸馏但完全无数据 → 不触发
        data_ok = False
        time_ok = False  # 无数据可蒸馏，时间条件也无意义
        reasons = ["首次蒸馏但 .ieidev/memory/ 里完全无数据，不触发"]

    should_trigger = time_ok and data_ok

    return TriggerCheck(
        should_trigger=should_trigger,
        mode=mode,
        days_since_distill=days_since,
        new_f_count=new_f,
        new_misalign_count=new_misalign,
        new_r_count=new_r,
        thresholds=thresholds,
        reasons=reasons,
    )


def main() -> int:
    """CLI：JSON 输出触发检测结果。

    用法：python3 distill_trigger.py [<ieidev_dir>]
    """
    kdev = sys.argv[1] if len(sys.argv) > 1 else ".ieidev/memory"
    result = check_distill_trigger(kdev)
    print(result.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
