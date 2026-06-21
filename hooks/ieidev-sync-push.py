#!/usr/bin/env python3
"""SessionEnd: commit + push the .ieidev/ nested memory repo (Q-009). Best-effort, never blocks."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import ieidev_sync  # noqa: E402


def main():
    repo_root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        res = ieidev_sync.sync_push(repo_root)
    except Exception as exc:
        print(f"[ieidev-sync] push skipped: {exc}", file=sys.stderr)
        return
    if not res["ok"]:
        print(f"[ieidev-sync] push failed: {res['message']}", file=sys.stderr)


if __name__ == "__main__":
    main()
