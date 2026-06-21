# 3.3 封装

> 概述：封装与边界绘制有关，意味着代码不会被滥用。

## 3.3.1 输出安全

### 规则
- 应避免使用标准输出。
- 推荐使用 Python 日志工具，而不是标准输出语句（`print` / `sys.stdout` / `sys.stderr`）。

### 反例
```python
print("hello world")              # 不推荐
sys.stdout.write("debug info")    # 不推荐
```

### 正例
```python
import logging
logging.debug("hello world")      # 推荐
```

### 适用场景
任何需要输出诊断信息的位置；调试信息 / 进度提示 / 错误反馈。

---

## 3.3.2 网络安全

### 规则
- 应在 Django 应用程序中启用跨站点伪造请求（CSRF）中间件保护。

### 反例
```python
# 未启用 CsrfViewMiddleware
MIDDLEWARE_CLASSES = (
    # 'django.middleware.csrf.CsrfViewMiddleware',  ← 注释掉了
)
```

### 正例
```python
MIDDLEWARE_CLASSES = (
    ...
    'django.middleware.csrf.CsrfViewMiddleware',
    ...
)
```

### 适用场景
Django 项目 settings.py 中配置 MIDDLEWARE / MIDDLEWARE_CLASSES 时；表单类视图的 csrf_exempt 装饰使用时；调整跨站策略时。

---

## 3.3.3 边界安全

### 规则
- 应在程序中定义清晰的信任边界。
- 将可信和不可信数据（如数据库、文件流）分别存储；当数据要从不可信侧传输到可信侧时，应使用验证逻辑进行判断。

### 反例
```python
def save(req):
    db.insert(req.json)            # 不分边界，外部数据直接落库
```

### 正例
```python
def save(req):
    payload = validate_schema(req.json)   # 边界验证
    db.insert(payload)                    # 验证后才进入可信侧
```

### 适用场景
设计 API / 服务层接口；接收消息队列消息；从文件 / 网络读入数据后入库。

---

## 3.3.4 内容策略安全

### 规则
- 应配置正确的 CSP（内容安全策略）。
- 避免使用 `unsafe-inline` 和 `unsafe-eval` 指令。
- 避免配置过于宽松的策略，如 `*`。

### 反例
```python
response["Content-Security-Policy"] = "default-src * 'unsafe-inline' 'unsafe-eval'"
```

### 正例
```python
response["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.example.com; "
    "object-src 'none'"
)
```

### 适用场景
任何 HTTP 响应头设置；前端模板/中间件添加 CSP；接入 django-csp / flask-talisman 等工具时。

---

## 3.3.5 跨资源共享策略安全

### 规则
- 应避免定义过于宽松的跨资源共享策略（CORS）。将 `*` 用作 `Access-Control-Allow-Origin` 表明应用数据可供任何域的 JavaScript 访问。

### 反例
```python
response["Access-Control-Allow-Origin"] = "*"
```

### 正例
```python
ALLOWED_ORIGINS = {"https://app.example.com", "https://admin.example.com"}
origin = request.headers.get("Origin", "")
if origin in ALLOWED_ORIGINS:
    response["Access-Control-Allow-Origin"] = origin
    response["Vary"] = "Origin"
```

### 适用场景
任何 `Access-Control-Allow-Origin` / `Access-Control-Allow-Credentials` 头；接入 django-cors-headers / flask-cors 等工具时。
