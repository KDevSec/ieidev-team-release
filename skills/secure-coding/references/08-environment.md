# 3.8 环境

> 概述：本部分涵盖源代码之外的所有内容，对产品安全性至关重要。

## 3.8.1 响应安全

### 规则
- 应设置安全的 HTTP 响应头：添加 `X-Content-Type-Options: nosniff`；设置 `X-Frame-Options` 并合理设置允许范围。
- 应设置安全的 HTTP 响应类型：禁止非 HTML 类型的响应包设置为 `text/html`；当 `Content-Type` 为 `text/html` 时，需要对响应体进行编码处理。

### 反例
```python
response = HttpResponse(user_input, content_type="text/html")   # 未编码
# 缺少 X-Content-Type-Options / X-Frame-Options
```

### 正例
```python
import bleach
clean = bleach.clean('an <script>evil()</script> example')
response = HttpResponse(clean, content_type="text/html")
response["X-Content-Type-Options"] = "nosniff"
response["X-Frame-Options"] = "SAMEORIGIN"
```

### 适用场景
任何 HTTP 响应构造；模板渲染输出；接入安全响应头中间件时。

---

## 3.8.2 部署安全

### 规则
- 应在生产环境中关闭 debug 模式。
- 禁止使用不安全的组件（不该在生产环境中部署的组件）。
- 应在软件发布前，去除所有与调试和测试相关的代码、配置、文件等。
- 应确保开发环境与生产环境的物理隔离。
- 禁止对敏感资源使用可预测的名称。

### 反例
```python
DEBUG = True                          # 生产开启 debug
INSTALLED_APPS += ["debug_toolbar"]   # 调试组件入生产

from django.conf.urls import patterns
from django.contrib import admin
admin.autodiscover()
urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),    # 可预测
    ...
)
```

### 正例
```python
DEBUG = False
ALLOWED_HOSTS = ["app.example.com"]

# 不可预测的管理后台路径
urlpatterns = patterns(
    '',
    url(r'^myappcontrol/', include(admin.site.urls)),    # 不可预测
    ...
)
```

### 适用场景
production settings.py / docker-compose / k8s 配置；CI/CD 发布脚本；管理后台路由设计。

---

## 3.8.3 版本安全

### 规则
- 推荐使用 Python 3.6+ 的版本。

### 反例
```python
# requirements / runtime 锁定到 Python 2.x 或 3.5 以下
```

### 正例
```python
# pyproject.toml
[project]
requires-python = ">=3.6"
```

### 适用场景
新项目初始化；CI 镜像选择；语言版本升级评估。
