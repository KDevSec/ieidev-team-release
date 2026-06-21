# 3.5 时间与状态

> 概述：在多核、多 CPU 或分布式系统中，两个事件可能在同一时间发生。这类问题与线程、进程、时间和信息之间的意外交互有关，这些交互通过共享状态发生。

## 3.5.1 避免操作不安全的临时文件

### 规则
- 存在许多不同的机制来创建临时文件，多数都很容易受到各种攻击。
- 推荐使用 `tempfile` 模块对临时文件进行操作。

### 反例
```python
import os
path = "/tmp/myapp-cache"
if not os.path.exists(path):
    open(path, "w").write(data)   # TOCTOU：检查与创建之间存在竞态
```

### 正例
```python
import tempfile
# 命名临时文件，受限权限创建
with tempfile.NamedTemporaryFile(prefix="myapp-", delete=False) as f:
    f.write(data)
    tmp_path = f.name

# 或：mkstemp 提供原子安全创建
fd, tmp_path = tempfile.mkstemp(prefix="myapp-")
```

### 适用场景
任何 `/tmp` 路径硬编码；临时文件 / 临时目录创建；多进程共享中间产物。
