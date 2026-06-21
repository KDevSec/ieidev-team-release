#!/usr/bin/env python3
"""CQO 监督员 L-a 逐事件 hook —— PostToolUse(matcher=Bash) 常驻监听的廉价烟雾报警.

定位（spec 2026-06-18-CQO监督员-design §4.2 L-a 行 + §4.4 L-a 行）：
  CC 无真 daemon，「常驻后台每条事件全检」= 给**写事件的 CLI 调用**挂 PostToolUse hook。
  每次某 agent 跑 `python3 -m ieidev_core record-gate/advance/dispatch-*`（事件落
  events.jsonl）**之后**，本 hook 触发，跑一段**纯 python、零 LLM、廉价**的确定性规则
  全检（读刚写入的 events 尾 + handoff + 文件存在性）→ 命中可疑模式 → 写
  `.ieidev/memory/staff/cqo/WARN-<时间戳>.md` 信号文件（goal 棒间消费后删，L-c）。

纪律（hook + 防套娃，spec §8）：
  - **先判**是不是 ieidev_core 写事件调用——不是就**立刻静默退出**，绝不拖慢别的 bash。
  - **零 LLM、零派单**：纯规则匹配（逻辑全在 ieidev_core.cqo_la，带测试），绝不起 agent。
  - **同步、快、5s 超时内**；任何异常都吞掉降级（hook 绝不阻断会话）。
  - **只读 + 只写自己 scope**：不写 events.jsonl、不碰状态机；只往 staff/cqo/ 落 WARN。

薄壳：规则全在 ieidev_core/cqo_la.py（单测 pyieidev/tests/test_cqo_la.py）；本脚本只做
  stdin 解析 + workspace 定位 + 调 cqo_la + 落 WARN 文件（E2E 测 tests/test_cqo_event_audit_hook.py）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))

# cqo_la 在打包内 pyieidev/ 下。真实运行时 CLI 用 PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev；
# hook 子进程不一定带该 env，故按 hook 文件位置自包含解析 hooks/../pyieidev 注入 sys.path。
_BUNDLED_PY = SCRIPT_DIR.parent / "pyieidev"
if _BUNDLED_PY.is_dir():
    sys.path.insert(0, str(_BUNDLED_PY))

# continue:true → PostToolUse 不阻断后续；suppressOutput → 不往会话刷噪（命中只落文件）。
_CONTINUE = json.dumps({"continue": True, "suppressOutput": True})


def _emit_and_exit(code: int = 0) -> int:
    print(_CONTINUE)
    return code


def _read_events_tail(workspace: str, slug: str, n: int = 50):
    """读刚写入的 events.jsonl 尾（最多 n 行）。缺文件 / 坏行 → []（降级）。"""
    if not slug:
        return []
    path = Path(workspace) / ".ieidev" / "features" / slug / "events.jsonl"
    if not path.is_file():
        return []
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _write_warn(workspace: str, flow, slug, command: str, hits: list) -> None:
    """落 WARN 信号文件到 .ieidev/memory/staff/cqo/WARN-<时间戳>.md。

    含：命中规则 + events 指针（flow/slug/路径）+ 触发命令 —— 供 goal 棒间（L-c）消费后删。
    复用 kdev-memory「hook 留信号 → 主控优先处理 → rm」范式（CLAUDE.md 铁规 3）。
    """
    cqo_dir = Path(workspace) / ".ieidev" / "memory" / "staff" / "cqo"
    try:
        cqo_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    ts = time.strftime("%Y%m%d-%H%M%S")
    # 同秒多 hook：用纳秒后缀防撞名
    fname = f"WARN-{ts}-{time.time_ns() % 1000000}.md"
    events_ptr = f".ieidev/features/{slug}/events.jsonl" if slug else "(无 slug)"

    lines = [
        f"# ⚠️ CQO L-a 逐事件全检命中（{ts}）",
        "",
        "> CQO 监督员 L-a 廉价规则烟雾报警（纯 python、零 LLM）。goal 编排**棒间**应优先",
        "> 读本信号 → 据命中决定是否插一次 L-b 深审 / 提示用户，**消费后删本文件**。",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| flow | `{flow}` |",
        f"| slug | `{slug}` |",
        f"| events 指针 | `{events_ptr}` |",
        f"| 触发命令 | `{command}` |",
        f"| 命中规则数 | {len(hits)} |",
        "",
        "## 命中规则",
        "",
    ]
    for h in hits:
        sev = h.get("severity", "🟡")
        rule = h.get("rule", "?")
        gate = h.get("gate")
        node = h.get("node")
        loc = " / ".join(x for x in (f"gate={gate}" if gate else "",
                                     f"node={node}" if node else "") if x)
        lines.append(f"- {sev} **{rule}**{(' （' + loc + '）') if loc else ''}")
        lines.append(f"  - {h.get('detail', '')}")
    lines.append("")
    lines.append("---")
    lines.append("_L-a 是 best-effort 确定性烟雾报警，非判决；深判交 L-b（cqo-orchestrator LLM 研判）。_")
    lines.append("")

    try:
        (cqo_dir / fname).write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    try:
        raw = sys.stdin.read()
    except OSError:
        return _emit_and_exit()
    if not raw:
        return _emit_and_exit()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return _emit_and_exit()

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return _emit_and_exit()

    # import 推迟到确认有命令后（且容错 import 失败 → 降级跳过，绝不崩 hook）
    try:
        from ieidev_core import cqo_la
    except ImportError:
        return _emit_and_exit()

    # 先判是不是 ieidev_core 写事件调用——不是就立刻静默退出（不拖慢别的 bash）
    if not cqo_la.is_event_write_call(cmd):
        return _emit_and_exit()

    parsed = cqo_la.parse_event_call(cmd)
    if not parsed:
        return _emit_and_exit()

    workspace = "."  # hook 在被测 repo 的 cwd 跑（同 commit-tracker.py）
    slug = parsed.get("slug")
    flow = parsed.get("flow")
    try:
        events = _read_events_tail(workspace, slug)
        hits = cqo_la.evaluate_rules(parsed, events=events, workspace=workspace)
    except Exception:
        # 规则层任何意外都吞掉：L-a 是烟雾报警，宁可漏报不可崩 hook
        return _emit_and_exit()

    if hits:
        _write_warn(workspace, flow, slug, cmd, hits)

    return _emit_and_exit()


if __name__ == "__main__":
    sys.exit(main())
