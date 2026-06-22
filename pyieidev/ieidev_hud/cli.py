"""ieidev-hud CLI —— python -m ieidev_hud {statusline,render,serve,setup}（纯只读 + 一次性安装）。

statusline：输出单行接 Claude Code statusLine（消费并忽略 stdin 的 session JSON）。
render：读 features/ → 写 <workspace>/.ieidev/hud.html（不在 features/ 下，gitignored）。
serve：起 stdlib http 服务，每次 GET 实时重渲 HUD 页（frontend client-render shell）→ 浏览器轮询看 live 进展（方案 A）。
setup：把 statusLine 幂等合并进 settings.json（OMC installer 模式）。
workspace 解析：--workspace > stdin JSON 的 cwd > 当前工作目录。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ieidev_hud import datasource, statusline, setup, server, global_datasource, frontend


def _consume_stdin():
    """读并返回 stdin（Claude Code 传 session JSON）；非 tty 才读，避免阻塞。"""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except (OSError, ValueError):
        return ""


def _workspace_from_stdin(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    for key in ("cwd", "workspace"):
        v = data.get(key) if isinstance(data, dict) else None
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            cur = v.get("current_dir") or v.get("path")
            if isinstance(cur, str):
                return cur
    return None


def _resolve_workspace(args):
    """--workspace > stdin JSON cwd > cwd。stdin 惰性消费：仅 --workspace 缺省时才读，
    避免 statusline（每键一跑）在无 EOF 管道上阻塞挂死。"""
    if getattr(args, "workspace", None):
        return args.workspace
    from_stdin = _workspace_from_stdin(_consume_stdin())
    return from_stdin or str(Path.cwd())


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_statusline(args):
    ws = _resolve_workspace(args)
    try:
        model = datasource.build_hud_model(ws)
        line = statusline.render(model)
    except Exception:
        # HUD 铁律：观测层永不崩用户视图（派生非真相，坏数据降级）
        line = statusline.safe_fallback()
    sys.stdout.write(line)
    return 0


def cmd_render(args):
    ws = _resolve_workspace(args)
    gen = datetime.now(timezone.utc)
    is_global = bool(getattr(args, "global_", False))
    try:
        if is_global:
            model = global_datasource.build_global_model(now=gen)
        else:
            model = global_datasource.build_workspace_model(ws, now=gen)
    except Exception:
        # HUD 铁律：观测层永不崩 / render 永不抛 —— model 构建失败降级出合法空 shell
        model = global_datasource.empty_model("global" if is_global else "workspace", now=gen)
    html = frontend.render_shell(model)
    out = Path(args.out) if args.out else Path(ws) / ".ieidev" / "hud.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(str(out))
    return 0


def cmd_serve(args):
    ws = _resolve_workspace(args)
    return server.serve(ws, host=args.host, port=args.port,
                        open_browser=args.open,
                        global_mode=bool(getattr(args, "global_", False)))


def cmd_setup(args):
    scope = "user" if getattr(args, "user", False) else "project"
    workspace = args.workspace or str(Path.cwd())
    plugin_root = setup.resolve_plugin_root()
    command = setup.build_statusline_command(plugin_root)
    settings_path = setup.resolve_settings_path(scope, workspace)
    refresh_interval = getattr(args, "refresh_interval", None)
    kwargs = {"force": args.force}
    if refresh_interval is not None:
        kwargs["refresh_interval"] = refresh_interval
    try:
        result = setup.install_statusline(settings_path, command, **kwargs)
    except setup.SetupError as e:
        sys.stderr.write(str(e) + "\n")
        return 1
    action = result["action"]
    path = result["path"]
    if action == "created":
        print(f"✅ 已写入 {path}，重载/重启 session 后状态栏生效")
    elif action == "updated":
        print(f"✅ 已更新 {path}，重载/重启 session 后状态栏生效")
    elif action == "skipped_foreign":
        print("未改动：已有他者 statusLine，加 `--force` 覆盖（会先备份 settings.json.bak）")
    elif action == "forced":
        print(f"✅ 已强制写入 {path}（原文件已备份至 {result['backup']}），重载/重启 session 后状态栏生效")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="ieidev-hud", description="ieidev HUD 观测层（只读）")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace",
                        help="项目工作区根（含 .ieidev/）；缺省取 stdin.cwd 或 cwd")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("statusline", parents=[common], help="通道① 单行状态栏")
    ps.set_defaults(func=cmd_statusline)
    pr = sub.add_parser("render", parents=[common], help="通道② 生成 hud.html")
    pr.add_argument("--out", help="输出路径，缺省 <workspace>/.ieidev/hud.html")
    pr.add_argument("--global", dest="global_", action="store_true",
                    help="全局 HUD：读 registry 聚合本机所有项目")
    pr.set_defaults(func=cmd_render)
    pserve = sub.add_parser("serve", parents=[common],
                            help="通道③ 起 web 服务实时看进展（方案 A 轮询）")
    pserve.add_argument("--port", type=int, default=8765,
                        help="监听端口（默认 8765；0=系统分配临时端口）")
    pserve.add_argument("--host", default="127.0.0.1",
                        help="绑定地址（默认 127.0.0.1，只本机；慎改对外）")
    pserve.add_argument("--open", action="store_true",
                        help="启动后自动用默认浏览器打开")
    pserve.add_argument("--global", dest="global_", action="store_true",
                        help="全局实时台：读 registry 聚合本机所有项目（/model.json scope=global）")
    pserve.set_defaults(func=cmd_serve)
    psetup = sub.add_parser("setup", parents=[common], help="把 statusLine 接进 settings.json")
    scope_group = psetup.add_mutually_exclusive_group()
    scope_group.add_argument("--user", action="store_true",
                             help="写入用户级 ~/.claude/settings.json（缺省 project）")
    scope_group.add_argument("--project", action="store_true",
                             help="写入项目级 <workspace>/.claude/settings.json（缺省）")
    psetup.add_argument("--force", action="store_true",
                        help="覆盖他者 statusLine（先备份 settings.json.bak）")
    psetup.add_argument("--refresh-interval", type=int, default=None, dest="refresh_interval",
                        help="statusLine 定时刷新秒数（默认 10，最小 1）；后台子 agent 跑 flow 时主会话空闲也刷新")
    psetup.set_defaults(func=cmd_setup)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
