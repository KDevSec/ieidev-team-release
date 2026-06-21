import sys
from pathlib import Path

# 按绝对路径直跑本文件时，sys.path[0] 是 ieidev_hud/ 自身；`from ieidev_hud.cli import main`
# 需父目录在 path 上。setup 写出的 statusLine 命令正是绝对路径直跑本文件，故此处自举
# 父目录（绕开 PYTHONPATH，FF-2）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ieidev_hud.cli import main

if __name__ == "__main__":
    sys.exit(main())
