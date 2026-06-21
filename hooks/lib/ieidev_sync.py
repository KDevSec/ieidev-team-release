"""ieidev-memory git 托管自举 (Q-009): .ieidev/ 独立 nested repo + ieidev-sync.yml 自举.

代码仓 .gitignore 忽略 /.ieidev/；tracked 的 ieidev-sync.yml 记"记忆仓 remote"。
SessionStart 自举：
  - .ieidev/.git 存在                  -> pull（永远拿最新，胜 submodule 钉死 SHA）
  - 无 .git，.ieidev/ 空/缺，有 remote  -> clone（新机器零手动）
  - 无 .git，.ieidev/ 有内容，有 remote -> init（把本机已有记忆转成 nested repo + 首推）
  - 无 remote                        -> 中文托管提醒（强烈建议、非强制）
SessionEnd/rollup -> commit + push。
全程 stdlib-only —— hook 不能因缺依赖而炸。
"""
import subprocess
from pathlib import Path

REMINDER = (
    "检测到工程记忆尚未 git 托管。强烈建议建立独立记忆仓（nested repo）并在 "
    "ieidev-sync.yml 登记，以便跨机器 / 团队同步、换机不丢记忆。是否现在初始化？"
)


def read_sync_config(repo_root):
    """Parse the flat ieidev-sync.yml -> {'memory_repo': url|None, 'branch': str}."""
    cfg = {"memory_repo": None, "branch": "main"}
    path = Path(repo_root) / "ieidev-sync.yml"
    if not path.exists():
        return cfg
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key in cfg and val:
            cfg[key] = val
    return cfg


def reminder_text():
    """The 中文 托管提醒 (记忆架构 §9.4)."""
    return REMINDER


def decide_action(*, has_git, ieidev_nonempty, remote):
    """Pure SessionStart bootstrap decision.

    Returns one of:
      'pull'   — .ieidev/ is already a repo (fetch latest).
      'clone'  — no repo, .ieidev/ empty/absent, a remote is configured (new machine).
      'init'   — no repo, .ieidev/ already has local content, a remote is configured
                 (convert this machine's existing memory into the nested repo + first push).
      'remind' — no remote configured (emit the 中文 托管提醒; do nothing destructive).
    """
    if has_git:
        return "pull"
    if remote:
        return "init" if ieidev_nonempty else "clone"
    return "remind"


# Fixed identity for the nested memory repo's own commits (hermetic; the code repo's
# AI/human identity is separate and set elsewhere).
_GIT_ID = ["-c", "user.name=ieidev-memory", "-c", "user.email=ieidev@local", "-c", "commit.gpgsign=false"]

# Machine-local memory (NOT hosted to the shared memory repo) — §5.3 #13/#14/#15/#16.
# Bare names (no internal slash) match at any depth: covers flat (.ieidev/memory/state/)
# and scoped (.ieidev/state/) layouts.
_MACHINE_LOCAL_GITIGNORE = """# ieidev-memory nested repo — machine-local, not hosted (§5.3)
state/
checkpoints/
hud.md
dataset/
"""


def _ensure_machine_local_gitignore(kdev):
    """Write .ieidev/.gitignore excluding machine-local dirs if absent."""
    gi = Path(kdev) / ".gitignore"
    if not gi.exists():
        gi.write_text(_MACHINE_LOCAL_GITIGNORE, encoding="utf-8")


def _git(args, cwd, *, identity=False):
    pre = _GIT_ID if identity else []
    return subprocess.run(["git", *pre, *args], cwd=str(cwd),
                          capture_output=True, text=True)


def _ieidev_dir(repo_root):
    return Path(repo_root) / ".ieidev"


def bootstrap(repo_root):
    """SessionStart bootstrap. Returns {'action', 'ok', 'message'}. Never raises."""
    repo_root = Path(repo_root)
    kdev = _ieidev_dir(repo_root)
    has_git = (kdev / ".git").exists()
    ieidev_nonempty = kdev.exists() and any(kdev.iterdir())
    cfg = read_sync_config(repo_root)
    remote = cfg["memory_repo"]
    branch = cfg["branch"]
    action = decide_action(has_git=has_git, ieidev_nonempty=ieidev_nonempty, remote=remote)

    if action == "remind":
        return {"action": "remind", "ok": True, "message": reminder_text()}

    if action == "pull":
        r = _git(["pull", "--ff-only"], cwd=kdev)
        return {"action": "pull", "ok": r.returncode == 0,
                "message": (r.stderr or r.stdout).strip()}

    if action == "clone":
        kdev.parent.mkdir(parents=True, exist_ok=True)
        # -b <branch>: the freshly-bootstrapped memory remote's HEAD may still point at the
        # host git's default branch (e.g. master) rather than our configured branch, which
        # would make a plain clone check out nothing. Clone the configured branch explicitly.
        r = _git(["clone", "-b", branch, remote, str(kdev)], cwd=repo_root, identity=True)
        if r.returncode == 0:
            # Chinese memory filenames must show as UTF-8 (not octal-escaped) in git output.
            _git(["config", "core.quotepath", "false"], cwd=kdev)
        return {"action": "clone", "ok": r.returncode == 0,
                "message": (r.stderr or r.stdout).strip()}

    # action == "init": convert existing local .ieidev/ into the nested repo + first push
    _ensure_machine_local_gitignore(kdev)   # don't push machine-local counters/checkpoints (§5.3)
    msgs = []
    for args, ident, tolerate in [
        (["init", "-b", branch], True, False),
        # Chinese memory filenames must show as UTF-8 (not octal-escaped) in git output.
        (["config", "core.quotepath", "false"], False, False),
        (["remote", "add", "origin", remote], False, True),   # tolerate "already exists"
        (["add", "-A"], False, False),
        (["commit", "-m", "chore(ieidev-memory): bootstrap nested memory repo"], True, False),
        (["push", "-u", "origin", branch], True, False),
    ]:
        r = _git(args, cwd=kdev, identity=ident)
        msgs.append(f"git {args[0]}: rc={r.returncode}")
        if r.returncode != 0 and not tolerate:
            return {"action": "init", "ok": False,
                    "message": "; ".join(msgs) + " :: " + (r.stderr or "").strip()}
    return {"action": "init", "ok": True, "message": "; ".join(msgs)}


def sync_push(repo_root, message="chore(ieidev-memory): session sync"):
    """SessionEnd/rollup: commit + push .ieidev/. Returns {'ok', 'pushed', 'message'}. Never raises."""
    kdev = _ieidev_dir(repo_root)
    if not (kdev / ".git").exists():
        return {"ok": True, "pushed": False, "message": "no .ieidev/.git; skip (untracked memory)"}
    _git(["add", "-A"], cwd=kdev)
    status = _git(["status", "--porcelain"], cwd=kdev)
    if not status.stdout.strip():
        return {"ok": True, "pushed": False, "message": "nothing to commit"}
    c = _git(["commit", "-m", message], cwd=kdev, identity=True)
    if c.returncode != 0:
        return {"ok": False, "pushed": False, "message": (c.stderr or c.stdout).strip()}
    p = _git(["push"], cwd=kdev)
    return {"ok": p.returncode == 0, "pushed": p.returncode == 0,
            "message": (p.stderr or p.stdout).strip()}
