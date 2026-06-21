# 3.4 API 滥用

> 概述：API 是调用方和被调用方之间的连接，最常见的滥用是调用方未能正确调用被调用方。

## 3.4.1 文件安全

### 规则
- 禁止将外部文件存储于可执行目录。
- 应对文件类型进行限制（对类型、大小做严格校验，仅允许业务所需类型上传）。
- 应将外部文件名进行随机化处理（避免直接使用真实文件名）。
- 应避免路径拼接（保存目录建议后台写死并对文件名校验）。
- 应对用户输入的文件进行校验（保存到本地文件系统时，必须对路径进行合法校验）。

### 反例
```python
upload_dir = "/var/www/html/uploads/"                       # 可执行目录
file_path = upload_dir + request.files["file"].filename     # 路径拼接 + 真实文件名
request.files["file"].save(file_path)                       # 不校验类型/大小/路径
```

### 正例
```python
import os
import uuid

ALLOWED_EXTENSIONS = ["txt", "xlsx"]
UPLOAD_DIR = "/var/data/upload/"   # 非可执行目录，写死

def allowed_file(filename):
    if ('.' in filename and '..' not in filename and
            os.path.splitext(filename)[1].lower().lstrip(".") in ALLOWED_EXTENSIONS):
        return filename
    return None

def save_upload(req_file):
    if not allowed_file(req_file.filename):
        raise ValueError("invalid file type")
    if req_file.content_length > 10 * 1024 * 1024:
        raise ValueError("too large")
    name = uuid.uuid4().hex + os.path.splitext(req_file.filename)[1]
    absolute_path = os.path.join(UPLOAD_DIR, name)
    normalized_path = os.path.normpath(absolute_path)
    if not normalized_path.startswith(UPLOAD_DIR):
        raise IOError()
    req_file.save(normalized_path)
```

### 适用场景
所有文件上传 / 下载接口；从 HTTP / SMB / S3 拉取后落盘的位置；文件名直接来自外部输入时。

---

## 3.4.2 权限管理安全

### 规则
- 正确使用 umask 和 chmod（umask 易与 chmod 参数混淆：umask 用于为新建文件设置初始权限，会通过 mode 参数关闭对应权限）。
- 授权遵守最小权限原则（细粒度访问控制，账户仅持有完成授权任务所需的最小权限）。
- 应定期清理不需要的权限（清理非必需用户的权限）。
- 系统应默认进行身份认证。

### 反例
```python
os.umask(0)               # 撤销 umask 防护
os.chmod(path, 0o777)     # 全开权限
```

### 正例
```python
import os
os.umask(0o077)           # 新建文件默认仅 owner 可读写
os.chmod(path, 0o600)     # 仅 owner 可读写
# 应用账户：只持有"执行授权任务"所需的最小权限；定期审计/清理
```

### 适用场景
任何 `os.umask` / `os.chmod` / `os.fchmod` / `pathlib.Path.chmod` / Linux 用户权限分配；系统初始化默认认证策略时。
