"""通道③ serve —— 实时台（client-render shell + /model.json + /events SSE，零第三方依赖）。

机制（#9 Plan-2 Task 4，干掉旧的 2 秒全页 reload）：
  GET /           → frontend.render_shell(None)：client-render shell，首屏不内联数据，
                    JS 去 fetch('/model.json') + connect EventSource('/events') 增量重渲。
  GET /model.json → 实时重读 datasource → build_global_model（global_mode）/
                    build_workspace_model（per-workspace）→ JSON。永不抛：异常降级 empty_model。
  GET /events     → text/event-stream：~1s 轮询算 .ieidev/features/** 的 mtime 指纹，
                    每 tick 都写一帧——变了 push `data: tick`，否则 push 心跳 `: ping`；
                    每 tick 写让断连在 ~1s 内由失败的 write 暴露（不滞留至下次变化）；
                    client 断开（BrokenPipe/ConnectionReset）静默退出该线程。

观测层铁律（FF）：派生非真相、坏数据降级。单请求出错 → 降级，server 继续不崩。

只用标准库：http.server / socketserver / threading / webbrowser。
"""
import json
import sys
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ieidev_hud import datasource, frontend, global_datasource
from ieidev_team import registry as _registry

_DEFAULT_HOST = "127.0.0.1"   # 默认只绑本机，不对外
_DEFAULT_PORT = 8765

_SSE_POLL_SECONDS = 1.0       # mtime 指纹轮询间隔（每 tick 都写一帧）


def _now():
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# model 构建（永不抛：异常 → empty_model，仍带正确 scope + 合法形状）
# --------------------------------------------------------------------------

def build_model(workspace, *, global_mode, now):
    """实时重读 → model dict。永不抛：build_*_model 出错 → empty_model 降级。"""
    scope = "global" if global_mode else "workspace"
    try:
        if global_mode:
            return global_datasource.build_global_model(now=now)
        return global_datasource.build_workspace_model(workspace, now=now)
    except Exception:
        return global_datasource.empty_model(scope, now=now)


# --------------------------------------------------------------------------
# /events mtime 指纹（feature 落账变化的廉价检测：扫 .ieidev/features/** stat.mtime）
# --------------------------------------------------------------------------

def _features_fingerprint(workspace):
    """对一个 workspace 的 .ieidev/features/** 算 (路径,mtime) 指纹。

    走文件 mtime 聚合：feature 落账（flow-state.json / events.jsonl 写盘）必改 mtime。
    缺目录 → 空指纹（合法，无在跑）。任何 OSError 静默跳过该条目（不崩）。
    """
    fdir = Path(workspace) / ".ieidev" / "features"
    if not fdir.exists():
        return ()
    items = []
    try:
        walk = list(fdir.rglob("*"))
    except OSError:
        return ()
    for p in walk:
        try:
            items.append((str(p), p.stat().st_mtime_ns))
        except OSError:
            continue
    items.sort()
    return tuple(items)


def _global_fingerprint(now=None):
    """global 模式指纹：扫 registry 每个 workspace 的 features。registry 坏 → 空。"""
    try:
        entries = _registry.read_registry()["entries"]
    except Exception:
        return ()
    workspaces = sorted({e.get("workspace") for e in entries if e.get("workspace")})
    out = []
    for ws in workspaces:
        out.append((ws, _features_fingerprint(ws)))
    return tuple(out)


def _fingerprint(workspace, *, global_mode):
    if global_mode:
        return _global_fingerprint()
    return _features_fingerprint(workspace)


# --------------------------------------------------------------------------
# server
# --------------------------------------------------------------------------

class _HUDServer(ThreadingHTTPServer):
    """绑定 workspace + global_mode 的 server；ThreadingHTTPServer 让 SSE 长连接与
    /model.json / / 短请求不互相阻塞。"""
    daemon_threads = True       # 进程退出不被请求线程（含挂着的 SSE）挂住
    allow_reuse_address = True  # Ctrl-C 重启时端口不卡 TIME_WAIT

    def __init__(self, server_address, workspace, *, global_mode=False):
        self.workspace = workspace
        self.global_mode = global_mode
        super().__init__(server_address, _HUDRequestHandler)


class _HUDRequestHandler(BaseHTTPRequestHandler):
    server_version = "ieidev-hud/serve"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._serve_shell()
        elif path == "/model.json":
            self._serve_model_json()
        elif path == "/events":
            self._serve_events()
        else:
            self._send_404()

    # ---- GET / → client-render shell（不内联数据，JS 去拉 /model.json）----
    def _serve_shell(self):
        try:
            html = frontend.render_shell(None)
        except Exception:
            html = "<!DOCTYPE html><html><body>HUD shell 渲染失败（已降级）</body></html>"
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- GET /model.json → 实时重读 model（永不抛）----
    def _serve_model_json(self):
        model = build_model(self.server.workspace, global_mode=self.server.global_mode,
                            now=_now())
        body = json.dumps(model, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- GET /events → SSE：每 tick 写一帧——指纹变 push tick，否则心跳 : ping ----
    def _serve_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        ws = self.server.workspace
        gm = self.server.global_mode
        try:
            last_fp = _fingerprint(ws, global_mode=gm)
            # 首帧立即 push 一个 tick：client 一连上就触发一次拉取（无需等首次变化）
            self.wfile.write(b"data: tick\n\n")
            self.wfile.flush()
            while True:
                time.sleep(_SSE_POLL_SECONDS)
                fp = _fingerprint(ws, global_mode=gm)
                if fp != last_fp:
                    last_fp = fp
                    self.wfile.write(b"data: tick\n\n")
                else:
                    self.wfile.write(b": ping\n\n")   # 每 tick 写：断连 ~1s 暴露，不滞留
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # client 断开 → 静默退出该 handler 线程（不崩 server）
            return
        except OSError:
            # socket 已关 / 写失败的其他 OS 层错误：同样静默退出
            return

    def _send_404(self):
        body = b"404 - HUD serves /, /model.json, /events\n"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        # 静默逐请求日志：实时台 SSE/轮询会刷屏。
        return


def make_server(workspace, *, host=_DEFAULT_HOST, port=_DEFAULT_PORT, global_mode=False):
    """创建并绑定 HUD server（不 serve）。端口被占 → 抛 OSError。

    port=0 → 系统分配临时端口（实际端口见 server_address[1]）。
    global_mode=True → /model.json 走 build_global_model（读 registry 聚合本机所有项目）。
    测试用此入口在临时端口起 server 发真请求。
    """
    return _HUDServer((host, port), workspace, global_mode=global_mode)


def serve(workspace, *, host=_DEFAULT_HOST, port=_DEFAULT_PORT, open_browser=False,
          global_mode=False):
    """CLI 阻塞入口：起 server、serve_forever，Ctrl-C 优雅退出。

    返回退出码：正常停 0；端口被占等绑定失败 1（清晰报错、不阻塞、不崩）。
    """
    try:
        httpd = make_server(workspace, host=host, port=port, global_mode=global_mode)
    except OSError as e:
        sys.stderr.write(
            f"无法在 {host}:{port} 起 HUD 服务 —— {e}\n"
            f"（端口可能被占用：换 --port，或 --port 0 让系统自动分配）\n"
        )
        return 1

    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}"
    scope = "全局（registry 聚合）" if global_mode else "单工作区"
    print(f"HUD serving at {url} · {scope}（实时台，Ctrl-C 停）", flush=True)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass   # 无浏览器/无显示环境不影响服务

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nHUD 已停止", flush=True)
    finally:
        httpd.server_close()
    return 0
