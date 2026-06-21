"""ieidev-memory P-C0.5 一次性迁移：Q-002 后半残 Step 批量盖 `status: voided-faded`。

承接 Q-002（本项目 2026-05-27 拍板"用户不再评分"）。旧版无 rating.mode 机制时
recorder 写的 Step 用户评分段留 `—` 但没盖 status → step_completeness 一直当半残 nag。
本脚本对"仅因用户评分空才半残"（扣分项等真问题不动）的 post-cutoff Step 盖章销账。

幂等：已有 status（围栏或内联）的 Step 跳过；可反复跑。
只读写传入文本/文件，不碰其它 .ieidev/memory/ 文件。

CLI: python3 migrate_void_faded.py [--log .ieidev/memory/执行日志.md] [--cutoff 2026-05-27]
                                    [--today YYYY-MM-DD] [--apply]
默认 dry-run（打印将盖章的 Step）；--apply 才落盘。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as _date
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from step_completeness import parse_steps, check_step  # noqa: E402

DEFAULT_CUTOFF = "2026-05-27"  # Q-002 拍板日


def void_faded_backlog(log_text: str, cutoff_date: str, today: str) -> Tuple[str, List[str]]:
    """返回 (new_text, stamped_labels)。

    盖章条件（全满足）：
      - step.status is None（未盖过；幂等）
      - date >= cutoff_date
      - check_step(user-required) 非空 AND check_step(model-only) 空
        （即半残纯由用户评分空导致；扣分项等真问题保留 nag）

    按 parse_steps 的连续 body 切片逐条重建（不用全局 str.replace），
    对重复标题鲁棒。
    """
    steps = parse_steps(log_text)
    if not steps:
        return log_text, []
    # prefix = 第一条 Step 之前的内容（文件头）。第一条 body 以首个 `## Step` 开头，
    # 之前无同样切片，find 取到的就是首条起点。
    prefix = log_text[: log_text.find(steps[0]["body"])]
    stamped: List[str] = []
    new_bodies: List[str] = []
    for step in steps:
        body = step["body"]
        should_stamp = (
            step.get("status") is None
            and (step.get("date") or "") >= cutoff_date
            and check_step(step, rating_mode="user-required")
            and not check_step(step, rating_mode="model-only")
        )
        if should_stamp:
            status_line = (
                f"status: voided-faded   # 半残销账 {today}: "
                f"rating.mode=model-only（承 Q-002，用户评分段保留骨架不主动采集）"
            )
            head, sep, rest = body.partition("\n")  # head = "## Step ...: title"
            body = head + "\n" + status_line + (sep + rest if sep else "\n")
            stamped.append(step["label"])
        new_bodies.append(body)
    return prefix + "".join(new_bodies), stamped


def main() -> int:
    parser = argparse.ArgumentParser(description="Q-002 后半残 Step 批量销账（幂等）")
    parser.add_argument("--log", default=".ieidev/memory/执行日志.md")
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    parser.add_argument("--today", default=_date.today().isoformat())
    parser.add_argument("--apply", action="store_true", help="落盘（默认 dry-run 只打印）")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.is_file():
        print(f"[migrate_void_faded] 找不到 {log_path}", file=sys.stderr)
        return 1
    text = log_path.read_text(encoding="utf-8")
    new_text, stamped = void_faded_backlog(text, args.cutoff, args.today)
    if not stamped:
        print("[migrate_void_faded] 无需盖章（已全部销账或无 post-cutoff 半残）")
        return 0
    print(f"[migrate_void_faded] {'已盖章' if args.apply else 'DRY-RUN 将盖章'} "
          f"{len(stamped)} 条：{', '.join(stamped)}")
    if args.apply:
        log_path.write_text(new_text, encoding="utf-8")
        print(f"[migrate_void_faded] 已写回 {log_path}")
    else:
        print("[migrate_void_faded] 这是 dry-run；加 --apply 落盘")
    return 0


if __name__ == "__main__":
    sys.exit(main())
