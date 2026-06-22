# hooks/block-advance-past-gate.py
"""PreToolUse(Bash) hook：被停靠的 slug 不许推进到下一段（#7 硬停）。
deny 是确定性的，auto/skipAutoPermissionPrompt 绕不过（同 block-unattributed-commit）。
hook 自身异常一律 fail-open（放行），绝不卡死 Bash。"""
import shlex
import sys
from pathlib import Path

# hook 自举 sys.path 找 ieidev_core（不靠 PYTHONPATH）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pyieidev"))

# 被硬停的推进动词（其余动词只读/记账，不拦）。
_ADVANCE_VERBS = ("dispatch-start", "advance", "start-run")
# 这三个动词里所有「布尔（store_true）」flag：无取值，不吃后随 token。
# 其余 --flag 一律按 "--flag value" 对处理（吃掉下一个 token）。
_BOOL_FLAGS = frozenset({"--auto-mode", "--reflow"})


def _parse_advance(command):
    """argv 感知解析推进命令 → {"slug": str, "ws": str|None} 或 None（非推进命令）。

    定位 `ieidev_core <verb>` 后按 argv 规则扫描：跳过 "--flag value" 对 / "--flag=value" /
    布尔 flag，第 1 个 positional 作 flow、第 2 个作 slug；slug 不限字符集（允许 unicode）。
    workspace 优先取命令自带 --workspace 值（缺省由调用方回退 cwd）。
    shlex 解析异常向上抛，由 decide_block 统一 fail-open。
    """
    tokens = shlex.split(command or "")
    verb_idx = None
    for i in range(len(tokens) - 1):
        if tokens[i] == "ieidev_core" and tokens[i + 1] in _ADVANCE_VERBS:
            verb_idx = i + 1
            break
    if verb_idx is None:
        return None

    positionals = []
    ws = None
    j = verb_idx + 1
    n = len(tokens)
    while j < n:
        tok = tokens[j]
        if tok.startswith("--"):
            name, sep, inline_val = tok.partition("=")
            if sep:                       # --flag=value：自带值，单 token
                if name == "--workspace":
                    ws = inline_val
                j += 1
            elif tok in _BOOL_FLAGS:      # 布尔 flag：无取值
                j += 1
            else:                          # "--flag value" 对：值是下一个 token
                if tok == "--workspace" and j + 1 < n:
                    ws = tokens[j + 1]
                j += 2
        elif tok.startswith("-") and len(tok) > 1:
            # 单横线短 flag（这些动词目前没有；稳妥起见按布尔处理，不吃下一个 token）
            j += 1
        else:
            positionals.append(tok)
            j += 1

    if len(positionals) < 2:
        return None                       # flow/slug 不全 → 当不完整命令放行
    return {"slug": positionals[1], "ws": ws}


def decide_block(command: str, workspace: str):
    try:
        from ieidev_core import gate_pause
        parsed = _parse_advance(command)
        if not parsed:
            return None
        slug = parsed["slug"]
        ws = parsed["ws"] or workspace    # 命令自带 --workspace 优先，缺省回退 cwd
        gates = gate_pause.active_pauses(ws, slug)
        if not gates:
            return None
        return {"deny": True, "slug": slug, "gates": gates,
                "reason": (f"🛑 human_gate {gates} 待确认：审阅本段计划/产物后，"
                           f"非 --auto 下回复确认，或 `python -m ieidev_core confirm-gate {slug} {gates[0]}` 解锁。")}
    except Exception:
        return None  # fail-open


def main():
    import json
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail-open
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    workspace = data.get("cwd") or "."
    verdict = decide_block(command, workspace)
    if verdict and verdict.get("deny"):
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": verdict["reason"],
        }}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
