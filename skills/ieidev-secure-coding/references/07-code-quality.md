# 3.7 代码质量

> 概述：低质量代码可能会导致不可预测的行为。

## 3.7.1 避免使用硬编码文件分隔符

### 规则
- 不同的操作系统使用不同的字符作为文件分隔符（Windows 使用 `\`，UNIX 使用 `/`）。在不同平台上运行时，硬编码分隔符会导致应用程序逻辑执行错误。
- 应使用语言库提供的独立于平台的 API。

### 反例
```python
path = directoryName + "\\" + fileName       # Windows 风格硬编码
path = directoryName + "/" + fileName        # UNIX 风格硬编码
```

### 正例
```python
import os
fd = os.open(os.path.join(directoryName, fileName), os.O_RDONLY)

# 或使用 pathlib（推荐，3.6+）
from pathlib import Path
p = Path(directoryName) / fileName
```

### 适用场景
任何路径拼接 / 文件名构造；从配置项 / 环境变量读取目录后拼装；跨平台分发的代码。
