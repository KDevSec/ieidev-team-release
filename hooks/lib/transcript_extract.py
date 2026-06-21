"""确定性从 transcript JSONL 切片抽结构化事实（P-C1b）。

recorder 经 Bash 调：`python3 -m transcript_extract <path> <since_offset>` → stdout JSON。
不读整文件进内存：逐行流式，按 since_offset 跳过已记录段。
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter
from pathlib import Path

_SHA_RE = re.compile(r"\[[^\]\s]+\s+([0-9a-f]{7,40})\]")


def _iter_blocks(obj: dict):
    msg = obj.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        yield from (b for b in content if isinstance(b, dict))


def _result_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return c if isinstance(c, str) else ""


def extract(path: str, since_offset: int = 0, end_offset: int | None = None) -> dict:
    tools: Counter = Counter()
    skills, subagents, files, shas, errors = set(), set(), set(), set(), []
    p = Path(path)
    if not p.is_file():
        return _result(tools, skills, subagents, files, shas, errors, unreadable=True)
    try:
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < since_offset:
                    continue
                if end_offset is not None and i >= end_offset:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                for b in _iter_blocks(obj):
                    t = b.get("type")
                    if t == "tool_use":
                        name = b.get("name", "")
                        if not name:
                            continue
                        tools[name] += 1
                        inp = b.get("input") or {}
                        if name == "Skill" and inp.get("skill"):
                            skills.add(inp["skill"])
                        elif name == "Agent" and inp.get("subagent_type"):
                            subagents.add(inp["subagent_type"])
                        elif name in ("Edit", "Write", "NotebookEdit") and inp.get("file_path"):
                            files.add(inp["file_path"])
                    elif t == "tool_result":
                        txt = _result_text(b)
                        if b.get("is_error"):
                            errors.append(txt[:120])
                        for m in _SHA_RE.findall(txt):
                            shas.add(m)
    except OSError:
        return _result(tools, skills, subagents, files, shas, errors, unreadable=True)
    return _result(tools, skills, subagents, files, shas, errors, unreadable=False)


def _result(tools, skills, subagents, files, shas, errors, unreadable):
    return {
        "tools_invoked": dict(tools),
        "tools_invoked_count": sum(tools.values()),
        "skills_invoked": sorted(skills),
        "subagents_dispatched": sorted(subagents),
        "files_touched": sorted(files),
        "commit_shas": sorted(shas),
        "errors_hit": len(errors),
        "error_samples": errors[:5],
        "unreadable": unreadable,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"unreadable": True, "error": "usage: transcript_extract <path> [since_offset]"}))
        return 2
    path = sys.argv[1]
    since = int(sys.argv[2]) if len(sys.argv) >= 3 else 0
    print(json.dumps(extract(path, since), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
