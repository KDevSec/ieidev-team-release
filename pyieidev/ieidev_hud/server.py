"""通道③ serve —— 方案 A：stdlib http.server 轮询式实时进展页（零第三方依赖）。

机制：每次 GET / 从 datasource 重新读 .ieidev/features/ → dashboard.render → 返回
新鲜 html。现有页面内联的 2 秒 auto-reload 让浏览器轮询 → 看到 live 进展。
复用现有 dashboard.render + datasource，不重写渲染。

观测层铁律（FF）：派生非真相、坏数据降级。
- 单次请求出错 → 返回降级页，server 继续（不崩）。
- 缺/空 features → 渲染「暂无在跑」不报错（datasource + dashboard 已各自容错）。

只用标准库：http.server / socketserver / threading / webbrowser。
"""
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ieidev_hud import dashboard, datasource

_DEFAULT_HOST = "127.0.0.1"   # 默认只绑本机，不对外
_DEFAULT_PORT = 8765

# render_page 连 dashboard.render 都炸时的最终兜底页（极端降级，仍带 2 秒 auto-reload 自愈）
_DEGRADED_PAGE = (
    "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
    "<title>ieidev HUD</title>"
    "<script>setTimeout(function(){location.reload();},2000);</script></head>"
    "<body><p>ieidev HUD 暂时无法渲染（已降级，自动重试中…）</p></body></html>"
)


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def render_page(workspace):
    """读 datasource + dashboard.render → 新鲜 html 字符串。永不抛：

    datasource 坏 → 退化成空 model（dashboard 渲染「暂无」）；
    连 render 都炸 → 返回最终兜底降级页。
    """
    try:
        try:
            model = datasource.build_hud_model(workspace)
        except Exception:
            model = {"features": [], "feature_count": 0, "primary": None}
        return dashboard.render(model, generated_at=_now_iso())
    except Exception:
        return _DEGRADED_PAGE


class _HUDServer(ThreadingHTTPServer):
    """绑定 workspace 的 server；ThreadingHTTPServer 让 auto-reload 轮询不互相阻塞。"""
    daemon_threads = True       # 进程退出不被请求线程挂住
    allow_reuse_address = True  # Ctrl-C 重启时端口不卡 TIME_WAIT

    def __init__(self, server_address, workspace):
        self.workspace = workspace
        super().__init__(server_address, _HUDRequestHandler)


class _HUDRequestHandler(BaseHTTPRequestHandler):
    server_version = "ieidev-hud/serve"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._serve_dashboard()
        else:
            self._send_404()

    def _serve_dashboard(self):
        html = render_page(self.server.workspace)   # render_page 自身永不抛
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")   # 轮询要新鲜，禁缓存
        self.end_headers()
        self.wfile.write(body)

    def _send_404(self):
        body = b"404 - HUD only serves / (live dashboard)\n"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        # 静默逐请求日志：页面每 2 秒 auto-reload，否则终端会被请求行刷屏。
        return


def make_server(workspace, *, host=_DEFAULT_HOST, port=_DEFAULT_PORT):
    """创建并绑定 HUD server（不 serve）。端口被占 → 抛 OSError。

    port=0 → 系统分配临时端口（实际端口见 server_address[1]）。
    测试用此入口在临时端口起 server 发真请求。
    """
    return _HUDServer((host, port), workspace)


def serve(workspace, *, host=_DEFAULT_HOST, port=_DEFAULT_PORT, open_browser=False):
    """CLI 阻塞入口：起 server、serve_forever，Ctrl-C 优雅退出。

    返回退出码：正常停 0；端口被占等绑定失败 1（清晰报错、不阻塞、不崩）。
    """
    try:
        httpd = make_server(workspace, host=host, port=port)
    except OSError as e:
        sys.stderr.write(
            f"无法在 {host}:{port} 起 HUD 服务 —— {e}\n"
            f"（端口可能被占用：换 --port，或 --port 0 让系统自动分配）\n"
        )
        return 1

    actual_port = httpd.server_address[1]
    url = f"http://{host}:{actual_port}"
    print(f"HUD serving at {url}（Ctrl-C 停）", flush=True)
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
