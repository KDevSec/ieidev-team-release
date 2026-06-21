"""强制 sys.stdout / sys.stderr 用 UTF-8 编码 —— Windows GBK console 兼容（v0.8.1+）

v0.8.0 引入 emoji 输出（🔴🟡⚪📊🎯📝💡 在 brief；⚠️ 📦 在 stop reminders；
📦💡⚠️🚀📌 在 weekly 输出）。Windows 中文环境默认 GBK 编码，subprocess 调
Python hook 时 `print` / `sys.stdout.write` 含 emoji 会抛 UnicodeEncodeError。

dac5cfe 在 weekly.py 加了 inline reconfigure；v0.8.1 抽成共享 helper 给所有
emoji-输出的 hook 入口（session-start-brief / stop-check / pre-compact-check / weekly）。

最低 Python 版本：3.7（`stdout.reconfigure` 在 3.7 引入）。
非 TextIOWrapper 替换场景（如 stdout 被某些 mock 接管）下静默失败，不阻断 hook。
"""

from __future__ import annotations

import sys


def force_utf8_stdio() -> None:
    """把 sys.stdout / sys.stderr 切到 UTF-8（如果当前不是）。

    幂等；多次调用安全。失败静默，不阻断 hook 主流程。
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            current = (stream.encoding or "").lower()
            if current != "utf-8":
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass  # 静默失败：mock 接管 / Python 3.6（理论不该到）/ 文件已关闭等
