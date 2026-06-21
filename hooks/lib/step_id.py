"""ieidev-memory v0.11 Step ID 加分支前缀机制。

提供：
- compute_branch_slug(): git 当前分支名 → 可放在文件名/Step ID 里的 ASCII slug
- read_counter(slug, state_dir): 读取分支独立计数器
- increment_counter(slug, state_dir): flock 保护 atomic 递增，返回新值
- mint_next_step_id(state_dir, slug=None): 一站式 slug + 递增 → "Step <slug>-<N>"

被 SKILL.md 引用：模型在写 Step 条目前调用 mint_next_step_id() 拿 ID。
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


STRIPPED_PREFIXES = ("feature/", "feat/")


def _git_query(*args: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _sanitize_slug(s: str) -> str:
    """非 [a-zA-Z0-9\\-_] 一律转 -，连续 - 合并，去首尾 -。空字符串 fallback 'unknown'。"""
    s = re.sub(r"[^a-zA-Z0-9\-_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def sanitize_slug(s: str) -> str:
    """Public wrapper for slug sanitization (reused by scope.resolve_step_slug)."""
    return _sanitize_slug(s)


def compute_branch_slug() -> str:
    """当前 git 分支 → slug。

    无 commit 的新仓库（git init 后没 commit）`rev-parse --abbrev-ref HEAD` 退出码 128，
    fallback 到读 `.git/HEAD` 的 `ref: refs/heads/<name>` 行（即便没 commit 也存在）。
    见 R-003。
    """
    branch = _git_query("rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        branch = _branch_from_head_file()
        if branch is None:
            return "unknown"
    if branch == "HEAD":
        return "detached"
    for prefix in STRIPPED_PREFIXES:
        if branch.startswith(prefix):
            branch = branch[len(prefix):]
            break
    return _sanitize_slug(branch)


def _branch_from_head_file() -> Optional[str]:
    """R-003 兜底：读 .git/HEAD 的 `ref: refs/heads/<name>` 拿分支名。"""
    git_dir = _git_query("rev-parse", "--git-dir")
    if not git_dir:
        return None
    head_file = Path(git_dir) / "HEAD"
    if not head_file.is_file():
        return None
    try:
        content = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "ref: refs/heads/"
    if content.startswith(prefix):
        return content[len(prefix):]
    return None


# ── Task 2: per-branch atomic counter ────────────────────────────────────────


def _counter_path(slug: str, state_dir: Path) -> Path:
    return state_dir / f"step-counter-{slug}.txt"


def read_counter(slug: str, state_dir: Path) -> int:
    """读 slug 的计数器值；不存在或损坏 → 0。"""
    p = _counter_path(slug, state_dir)
    if not p.is_file():
        return 0
    try:
        text = p.read_text(encoding="utf-8").strip()
        return int(text) if text else 0
    except (OSError, ValueError):
        return 0


def _flock_exclusive(fd: int) -> None:
    """跨平台 exclusive lock。POSIX: fcntl.flock；Windows: msvcrt.locking。"""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)


def _flock_release(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def increment_counter(slug: str, state_dir: Path) -> int:
    """atomic 递增 slug 的计数器，返回新值。

    锁策略：在 counter 文件上做 LOCK_EX，临界区里 read-modify-write。
    并发安全：20 线程并发 increment 同一 slug 不丢失、不重复。
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    p = _counter_path(slug, state_dir)
    fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        _flock_exclusive(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 64).decode("utf-8", errors="replace").strip()
        try:
            cur = int(raw) if raw else 0
        except ValueError:
            cur = 0
        new = cur + 1
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{new}\n".encode("utf-8"))
        os.fsync(fd)
        return new
    finally:
        _flock_release(fd)
        os.close(fd)


# ── Task 3: mint_next_step_id one-stop interface ──────────────────────────────


def mint_next_step_id(state_dir: Path, slug: Optional[str] = None) -> str:
    """一站式：算 slug（如未传）→ atomic 递增 counter → 返回格式化的 Step ID。

    返回如 "Step main-9" / "Step cluster-x1-1"。
    """
    if slug is None:
        slug = compute_branch_slug()
    n = increment_counter(slug, state_dir)
    return f"Step {slug}-{n}"


# ── P-C2 Group A: timestamp-based record ID primitive ─────────────────────────

RECORD_TYPES = ("Step", "Q", "G", "R", "F")


def _now_stamp(when: "datetime.datetime | None" = None) -> str:
    """Return a YYYYMMDD-HHMMSS timestamp string for the given (or current) datetime."""
    when = when or datetime.datetime.now()
    return when.strftime("%Y%m%d-%H%M%S")


def _who_suffix() -> str:
    """Return git-email local-part (sanitized) or empty string if unavailable."""
    email = _git_query("config", "user.email")
    if not email:
        return ""
    local = email.split("@", 1)[0]
    s = _sanitize_slug(local)
    return "" if s == "unknown" else s


def _dup_index(rec_type: str, base: str, state_dir: Path) -> int:
    """Atomically return and increment the collision counter for (rec_type, base).

    First call returns 0 (no suffix needed); subsequent calls with the same
    arguments return 1, 2, ... enabling `.N` deduplication.
    Uses flock for concurrent safety.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_slug(f"{rec_type}-{base}")
    p = state_dir / f"dupidx-{safe}.txt"
    fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        _flock_exclusive(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 64).decode("utf-8", errors="replace").strip()
        try:
            cur = int(raw) if raw else 0
        except ValueError:
            cur = 0
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, f"{cur + 1}\n".encode("utf-8"))
        os.fsync(fd)
        return cur
    finally:
        _flock_release(fd)
        os.close(fd)


def mint_record_id(
    rec_type: str,
    state_dir: Path,
    when: "datetime.datetime | None" = None,
    who: "str | None" = None,
) -> str:
    """Mint a new timestamp-based record ID for the given type.

    Format: ``<Type> <YYYYMMDD-HHMMSS>[-<who>][.<n>]``

    - If ``who`` is not provided, uses ``_who_suffix()`` (git email local-part).
    - If no git / email is available, the ``-who`` suffix is omitted entirely.
    - Collisions within the same second get a ``.1``, ``.2``, … suffix (atomic).

    Raises ``ValueError`` for unknown record types.
    """
    if rec_type not in RECORD_TYPES:
        raise ValueError(f"unknown record type: {rec_type!r}")
    ts = _now_stamp(when)
    who = _who_suffix() if who is None else who
    base = f"{ts}-{who}" if who else ts
    n = _dup_index(rec_type, base, state_dir)
    core = base if n == 0 else f"{base}.{n}"
    return f"{rec_type} {core}"


# ── Record-ID grammar: single source of truth ────────────────────────────────
# These fragments are the ONE place the record-ID grammar lives. trigger-match,
# distill, and step_completeness all build their heading regexes from
# id_label_fragment(), so the legacy↔timestamp dual recognition can never drift
# between modules again — the drift that silently dropped timestamp-form G
# entries from trigger recall before this was centralized.

_TS_PAT = r"\d{8}-\d{6}"  # bare YYYYMMDD-HHMMSS

# Timestamp id core: YYYYMMDD-HHMMSS[-<who>][.<dup>]
#   who: word/dash, sanitized (no dots);  dup: .<digits>, independent of who.
TS_ID_CORE = rf"{_TS_PAT}(?:-[\w-]+)?(?:\.\d+)?"

# Legacy Step id core — enumerated (NOT a catch-all wildcard), covering every
# historical form in 执行日志: "1"/"9" (sequence), "5.5" (decimal),
# "main-90"/"ieidev-hud-1"/"M-7" (prefix-N).
_LEGACY_STEP_CORE = r"(?:\d+(?:\.\d+)?|[\w-]+-\d+)"


def id_label_fragment(rec_type: str) -> str:
    """Regex fragment matching a full record-ID *label* of ``rec_type``,
    dual-recognizing the timestamp scheme and the legacy forms.

    The fragment is **unanchored** and has **no capturing groups of its own**
    (all internal groups are non-capturing), so a caller can wrap it in a
    heading regex — ``rf"^##\\s+({id_label_fragment('G')})..."`` — and rely on
    its own ``(...)`` being group 1 with no surprises.

    Raises ``ValueError`` for unknown record types.
    """
    if rec_type == "Step":
        return rf"Step\s+(?:{TS_ID_CORE}|{_LEGACY_STEP_CORE})"
    if rec_type in ("Q", "G", "R", "F"):
        return rf"{rec_type}(?:-\d+|\s+{TS_ID_CORE})"
    raise ValueError(f"unknown record type: {rec_type!r}")


# ── parse_record_id: dual-scheme recognition (legacy + timestamp) ──────────────

# New timestamp scheme: "<Type> <YYYYMMDD-HHMMSS>[-<who>][.<dup>]"
_RE_NEW = re.compile(rf"^(Step|Q|G|R|F)\s+({TS_ID_CORE})$")

# Legacy Step classifier (canonical mintable prefix-N forms): "Step main-87" /
# "Step cluster-x1-2". Intentionally stricter than _LEGACY_STEP_CORE — the
# heading scanners accept the broader historical zoo, this only classifies IDs.
_RE_OLD_STEP = re.compile(r"^(Step)\s+([\w\-\.]+-\d+)$")

# Legacy compact forms: "Q-018", "G-003", "R-001", "F-007"
_RE_OLD_QGRF = re.compile(r"^(Q|G|R|F)-(\d+)$")


def parse_record_id(label: str) -> "dict | None":
    """Parse a record-ID label, returning a dict with keys ``type``, ``id``, ``scheme``.

    Recognises both the new timestamp scheme and the legacy forms.
    Returns ``None`` for lines that are not record IDs.
    """
    label = label.strip()
    m = _RE_NEW.match(label)
    if m:
        return {"type": m.group(1), "id": m.group(2), "scheme": "timestamp"}
    m = _RE_OLD_STEP.match(label)
    if m:
        return {"type": m.group(1), "id": m.group(2), "scheme": "legacy"}
    m = _RE_OLD_QGRF.match(label)
    if m:
        return {"type": m.group(1), "id": m.group(2), "scheme": "legacy"}
    return None
