# ieidev_core/cqo_la.py
"""CQO 监督员（元监督）的 **L-a 逐事件 hook** 纯规则层 — 常驻监听的廉价烟雾报警.

定位（spec 2026-06-18-CQO监督员-design §4.2 L-a 行 + §4.4 动作菜单 L-a 行）：
  CC 无真 daemon，「常驻后台每条事件全检」翻译成 —— 给**写事件的 CLI 调用**挂
  `PostToolUse(matcher=Bash)` hook：每次 agent 跑 `ieidev_core record-gate/advance/
  dispatch-*`（事件落 events.jsonl）**之后**，跑一段**纯 python、零 LLM、廉价**的确定
  性规则全检 → 命中可疑模式 → 写 `staff/cqo/WARN-*.md` 信号（L-c 在 goal 棒间消费后删）。

分层（与 cqo_audit.py 同纪律 = 确定性逻辑沉到带测试纯函数，IO 壳薄）：
  - 本模块 = **纯规则 + 命令解析**（带测试，零 IO 除文件存在性检查）。
  - hooks/cqo-event-audit.py = 薄壳：读 stdin → 调本模块判 / 跑规则 → 写 WARN 文件。

约束（callee + 防套娃 + hook 纪律，spec §8）：
  - **零 LLM、零派单**：纯确定性规则匹配，绝不在 hook 里起 agent / 跑 LLM。
  - **只读消费**：读 events 尾 + handoff + 文件存在性；**不写** events.jsonl、不碰状态机。
  - **快**：同步、5s 超时内（hook 纪律）；非 ieidev_core 写事件调用**立刻静默退出**，
    不拖慢别的 bash。
  - **best-effort 烟雾报警**：规则是确定性的「可疑」提示，不是判决；深判交 L-b LLM agent。

MVP 规则集（3 条，可扩展；每条都对应 spec §4.4 L-a 行的例子）：
  R1 record-gate-by-mismatch  —— review-kind gate 的 verdict by 不是评审专家（被自评糊弄）
  R2 advance-past-impl-no-tests —— advance 过 TDD 实现节点但 workspace 无任何测试文件
  R3 gate-pass-artifact-missing —— record-gate PASS 但对应 node handoff 列的产物文件不存在
"""
from __future__ import annotations

import shlex
from pathlib import Path

# 写事件的子命令（这些 CLI 调用会 append events.jsonl / 推状态机）。
# 只读子命令（show/events/cqo-audit/list-*/resume/next-step/...）**不在**此集，hook 跳过。
EVENT_WRITE_SUBCOMMANDS = frozenset({
    "record-gate", "advance", "dispatch-start", "dispatch-done",
})

# 评审专家 by 身份前缀 —— review-kind gate 的 verdict 必须 by 评审专家出。
REVIEWER_BY_PREFIXES = ("reviewer",)

# TDD 实现节点：node-table 标注「含TDD」的实现节点（dev-engineer.node-table.yml
# n6b-impl-subagent = "subagent 派单实现(含TDD)"）。advance 到这些节点后应有测试文件。
IMPL_TDD_NODE_TOKENS = ("impl",)

# 测试文件识别（廉价启发式）：路径里有 test 段 / 文件名 test_*.py 或 *_test.* / spec 文件。
_TEST_DIR_NAMES = ("tests", "test", "__tests__", "spec", "specs")


def _strip_env_prefix(parts: list[str]) -> list[str]:
    """剥掉命令前置的 `KEY=VAL` 环境变量赋值（如 `PYTHONPATH=x python3 ...`）。"""
    i = 0
    while i < len(parts) and "=" in parts[i] and not parts[i].startswith("-"):
        # 形如 KEY=VAL（且不是某个 flag 的 --k=v）→ 视为 env 前缀
        head = parts[i].split("=", 1)[0]
        if head and all(c.isalnum() or c == "_" for c in head):
            i += 1
            continue
        break
    return parts[i:]


def _tokenize(cmd: str) -> list[str] | None:
    """安全切词；坏命令（不闭合引号等）→ None（hook 当作不可解析、静默跳过）。"""
    try:
        return shlex.split(cmd)
    except ValueError:
        return None


def _find_ieidev_core_invocation(parts: list[str]) -> int | None:
    """返回 `-m ieidev_core` 的 `ieidev_core` token 下标，否则 None。

    严格匹配 `-m ieidev_core` 相邻对，杜绝 `echo ieidev_core ...` / 子串误判。
    """
    for i in range(len(parts) - 1):
        if parts[i] == "-m" and parts[i + 1] == "ieidev_core":
            return i + 1
    return None


def is_event_write_call(cmd: str) -> bool:
    """命令是不是 `... -m ieidev_core <写事件子命令> ...`。

    非（普通 bash / 只读 ieidev_core 子命令 / 坏命令）→ False，hook 据此静默跳过。
    """
    if not cmd or "ieidev_core" not in cmd:
        return False
    parts = _tokenize(cmd)
    if not parts:
        return False
    parts = _strip_env_prefix(parts)
    idx = _find_ieidev_core_invocation(parts)
    if idx is None or idx + 1 >= len(parts):
        return False
    subcommand = parts[idx + 1]
    return subcommand in EVENT_WRITE_SUBCOMMANDS


def parse_event_call(cmd: str) -> dict | None:
    """把一条 ieidev_core 写事件调用解析成 {subcommand, flow, slug, positionals, flags}。

    `_common` argparse 形态：`<subcommand> <flow> <slug> [extra positionals] [--flag val ...]`
    （flow/slug 是 _common 的两个固定位置参数）。非写事件调用 → None。
    """
    if not is_event_write_call(cmd):
        return None
    parts = _strip_env_prefix(_tokenize(cmd) or [])
    idx = _find_ieidev_core_invocation(parts)
    assert idx is not None  # is_event_write_call 已保证
    rest = parts[idx + 1:]  # [subcommand, flow, slug, ...]
    subcommand = rest[0]
    body = rest[1:]

    positionals: list[str] = []
    flags: dict[str, str | bool] = {}
    i = 0
    while i < len(body):
        tok = body[i]
        if tok.startswith("--"):
            if "=" in tok:
                k, v = tok.split("=", 1)
                flags[k] = v
            elif i + 1 < len(body) and not body[i + 1].startswith("--"):
                flags[tok] = body[i + 1]
                i += 1
            else:
                flags[tok] = True
        else:
            positionals.append(tok)
        i += 1

    flow = positionals[0] if len(positionals) >= 1 else None
    slug = positionals[1] if len(positionals) >= 2 else None
    extra = positionals[2:]
    return {
        "subcommand": subcommand,
        "flow": flow,
        "slug": slug,
        "positionals": extra,
        "flags": flags,
    }


# ---------- helpers ----------

def _by_is_reviewer(by: str | None) -> bool:
    if not by:
        return False
    return any(by.startswith(p) for p in REVIEWER_BY_PREFIXES)


def _is_impl_tdd_node(node: str | None) -> bool:
    if not node:
        return False
    return any(tok in node for tok in IMPL_TDD_NODE_TOKENS)


def _workspace_has_test_file(workspace: str) -> bool:
    """workspace 里有没有任何测试文件（廉价启发：test 目录 / test_*.py / *_test.* / *.spec.*）。

    只扫源码区，跳过 .git / .ieidev / node_modules / __pycache__ 等噪声目录，控成本。
    """
    root = Path(workspace)
    if not root.is_dir():
        return False
    skip_dirs = {".git", ".ieidev", "node_modules", "__pycache__", ".pytest_cache",
                 ".venv", "venv", "dist", "build"}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in skip_dirs for part in rel_parts):
            continue
        name = p.name
        if any(seg in _TEST_DIR_NAMES for seg in rel_parts[:-1]):
            return True
        if name.startswith("test_") or "_test." in name or ".spec." in name or ".test." in name:
            return True
    return False


def _handoff_artifacts_for_node(workspace: str, slug: str | None, node: str | None):
    """扫 .ieidev/features/<slug>/handoffs/*/<node>.handoff.json，返回其 artifacts[]（合并）。

    遍历所有 employee 子目录（hook 不知具体哪个员工写的）。坏 JSON / 缺文件 → 跳过。
    """
    import json
    if not slug or not node:
        return []
    handoffs = Path(workspace) / ".ieidev" / "features" / slug / "handoffs"
    if not handoffs.is_dir():
        return []
    arts: list[str] = []
    for emp_dir in handoffs.iterdir():
        if not emp_dir.is_dir():
            continue
        hf = emp_dir / f"{node}.handoff.json"
        if not hf.is_file():
            continue
        try:
            data = json.loads(hf.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for a in data.get("artifacts", []) or []:
            if isinstance(a, str):
                arts.append(a)
    return arts


# ---------- 规则 ----------

def _rule_by_mismatch(parsed: dict) -> dict | None:
    """R1：review-kind gate 的 verdict by 不是评审专家 → 可疑（被自评/同体糊弄）。"""
    if parsed["subcommand"] != "record-gate":
        return None
    flags = parsed["flags"]
    if flags.get("--kind") != "review":
        return None
    by = flags.get("--by")
    if _by_is_reviewer(by):
        return None
    return {
        "rule": "record-gate-by-mismatch",
        "severity": "🟡",
        "gate": flags.get("--gate"),
        "node": flags.get("--node"),
        "detail": (f"review-kind gate 的 verdict by={by!r} 不是评审专家（reviewer-*）"
                   "——评审 gate 应由评审专家出判定，疑似被同体自评/糊弄，建议核对该 gate。"),
    }


def _rule_impl_no_tests(parsed: dict, workspace: str) -> dict | None:
    """R2：advance 到 TDD 实现节点后 workspace 无任何测试文件 → 疑似 TDD 没真做。"""
    if parsed["subcommand"] != "advance":
        return None
    to_node = parsed["positionals"][0] if parsed["positionals"] else None
    if not _is_impl_tdd_node(to_node):
        return None
    if _workspace_has_test_file(workspace):
        return None
    return {
        "rule": "advance-past-impl-no-tests",
        "severity": "🟡",
        "node": to_node,
        "detail": (f"advance 到 TDD 实现节点 {to_node!r}，但 workspace 里没找到任何测试文件"
                   "——疑似 TDD 红绿循环没真跑（假绿风险），建议核对测试是否落账。"),
    }


def _rule_pass_artifact_missing(parsed: dict, workspace: str) -> dict | None:
    """R3：record-gate PASS 但对应 node handoff 声明的产物文件不存在 → 疑似空过。"""
    if parsed["subcommand"] != "record-gate":
        return None
    flags = parsed["flags"]
    if flags.get("--verdict") != "PASS":
        return None
    node = flags.get("--node")
    arts = _handoff_artifacts_for_node(workspace, parsed["slug"], node)
    missing = [a for a in arts if not (Path(workspace) / a).exists()]
    if not missing:
        return None
    return {
        "rule": "gate-pass-artifact-missing",
        "severity": "🟡",
        "gate": flags.get("--gate"),
        "node": node,
        "detail": (f"gate 判 PASS，但对应节点 {node!r} 的 handoff 声明的产物文件不存在："
                   f"{missing} —— 疑似 gate 点头但产物未真落账，建议人工核对。"),
    }


def evaluate_rules(parsed: dict | None, events: list, workspace: str) -> list[dict]:
    """跑全部 L-a 确定性规则，返回命中列表（每条 {rule, severity, detail, ...}）。

    `events` 当前规则集未用到（保留为下一刀「读 events 尾做趋势规则」的接口，
    与 cqo_audit 的 events 消费对齐）；故意保留参数以稳定 hook 调用面。
    parsed 为 None（非事件调用）→ 直接空。
    """
    if not parsed:
        return []
    hits: list[dict] = []
    for fn, needs_ws in (
        (_rule_by_mismatch, False),
        (_rule_impl_no_tests, True),
        (_rule_pass_artifact_missing, True),
    ):
        hit = fn(parsed, workspace) if needs_ws else fn(parsed)
        if hit:
            hits.append(hit)
    return hits
