# 3.1 输入验证与表示

> 概述：输入验证和表示问题通常由元字符、交替编码和数字表示引起，必须对所有输入进行合法性校验。

## 3.1.1 命令操作安全

### 规则
- 避免直接调用系统命令（如 `os.system`、`os.popen`、`eval` 等），推荐使用系统 API 操作。
- 应避免拼接外部数据，并对执行的命令进行白名单限制。
- 应避免外部控制系统设置（系统设置由外部控制可能导致服务中断或意外的应用程序行为）。
- 应避免通过不可信的输入调用 memcached 操作。

### 反例
```python
import os
os.system("ping " + user_input)  # 命令注入
```

### 正例
```python
import sys
import shlex
domain = sys.argv[1]
badchars = "\n&;|'\"$()`-"
for char in badchars:
    domain = domain.replace(char, " ")
# 进一步：白名单 + 参数化的 subprocess 调用
```

### 适用场景
代码中出现 `os.system` / `subprocess` / `popen` / `commands.getoutput` / 调用外部进程时；接收 CLI 参数 / HTTP 参数 / 环境变量后将其传入 shell 时。

---

## 3.1.2 代码动态评估操作安全

### 规则
- 应避免动态解析源码指令（任何时候都应尽可能避免对代码进行动态解析）。
- 应避免直接执行和解析未验证的用户输入。
- 应避免对用户控制的数据进行反序列化（会让攻击者执行任意代码）。

### 反例
```python
import pickle
obj = pickle.loads(request.body)  # 任意代码执行
eval(user_input)                   # 动态解析
```

### 正例
```python
import json
obj = json.loads(request.body)     # 用 JSON 替代 pickle
# 对真正需要表达式求值的场景，使用 ast.literal_eval（仅字面量）
import ast
val = ast.literal_eval(user_input)
```

### 适用场景
代码中出现 `eval` / `exec` / `compile` / `pickle.loads` / `marshal.loads` / `yaml.load(..., Loader=yaml.Loader)` / `dill` / `cloudpickle`；任何接收外部字节流并反序列化的位置。

---

## 3.1.3 网络操作安全

### 规则
- 应避免向 Web 浏览器发送未经验证的数据。
- 应避免在响应头文件中包含未验证的数据。
- 应避免在 Cookie 中包含未验证的数据。
- 应启用 X-XSS-Protection 标头。
- 禁止未验证的输入控制重定向机制所使用的 URL。

### 反例
```python
# 未启用 XSS 保护
SECURE_BROWSER_XSS_FILTER = False
```

### 正例
```python
# Django settings
MIDDLEWARE_CLASSES = (
    ...
    'django.middleware.security.SecurityMiddleware',
    ...
)
SECURE_BROWSER_XSS_FILTER = True
```

### 适用场景
写入响应头 / Set-Cookie / `HttpResponseRedirect` / `flask.redirect` 时；接收外部 URL 作为重定向目标时。

---

## 3.1.4 数据库操作安全

### 规则
- 禁止在数据库连接中加入未经验证的输入。
- 避免动态构造数据库查询语句。

### 反例
```python
mysql.connector.connect(host=request.GET['host'], ...)  # 连接参数外部可控
```

### 正例
```python
# 连接参数从受信任的配置读取
mysql.connector.connect(host=settings.DB_HOST, ...)
```

### 适用场景
建立数据库连接、构造 DSN、动态拼接表名/列名时。

---

## 3.1.5 SQL 操作安全

### 规则
- 应使用参数化查询语句（强制区分数据和命令，避免 SQL 注入）。
- 推荐使用组件操作数据库（Django ORM、SQLAlchemy 等）。
- 应对接收到的外部参数进行过滤（动态拼接 SQL 时必须过滤）。

### 反例
```python
cur.execute("SELECT id FROM auth_user WHERE id=" + str(userid))  # SQL 注入
```

### 正例
```python
import mysql.connector
mydb = mysql.connector.connect(...)
cur = mydb.cursor()
userid = get_id_from_user()
cur.execute(
    "SELECT `id`, `password` FROM `auth_user` WHERE `id`=%s",
    (userid,),
)
result = cur.fetchall()

# 当必须动态拼接时，先过滤
def sql_filter(sql, max_length=20):
    dirty_stuff = ["\"", "\\", "/", "*", "'", "=", "-", "#", ";",
                   "<", ">", "+", "&", "$", "(", ")", "%", "@", ","]
    for stuff in dirty_stuff:
        sql = sql.replace(stuff, "x")
    return sql[:max_length]
```

### 适用场景
任何 `cursor.execute` / `cursor.executemany` / `db.session.execute` / raw SQL 字符串；对外部参数做表名/列名/排序方向拼接时。

---

## 3.1.6 XML 操作安全

### 规则
- 禁止使用外部实体方法。
- 禁止在 XML 文档中写入未验证的数据。
- 禁止动态构建 XPath 查询语句。
- 禁止使用未经验证的 XSL 样式表。

### 反例
```python
from lxml import etree
etree.parse(xmlSource)  # 默认可能解析外部实体（XXE）
```

### 正例
```python
from lxml import etree
xmlData = etree.parse(xmlSource, etree.XMLParser(resolve_entities=False))
```

### 适用场景
任何 XML 解析（`lxml.etree`、`xml.etree.ElementTree`、`xml.dom.minidom`）；构造 XPath 表达式；XSLT 转换。

---

## 3.1.7 邮件操作安全

### 规则
- 应避免在 SMTP 头中包含未验证的用户输入。
- 应避免直接执行未验证的 SMTP 命令。

### 反例
```python
smtp.docmd("MAIL FROM:<" + user_input + ">")  # SMTP 命令注入
```

### 正例
```python
# 使用高层接口，传入经过验证的字段
import smtplib
from email.message import EmailMessage
msg = EmailMessage()
msg["From"] = validated_sender
smtp.send_message(msg)
```

### 适用场景
使用 `smtplib` / `email` 模块；构造邮件头（From/To/Subject）拼入外部数据时。

---

## 3.1.8 日志操作安全

### 规则
- 禁止将未经验证的用户输入写入日志文件（攻击者可伪造日志条目或注入恶意信息）。

### 反例
```python
logging.info("user login: " + user_input)  # 日志注入（CRLF / 伪造）
```

### 正例
```python
# 过滤换行符 + 使用结构化字段
clean = user_input.replace("\n", "").replace("\r", "")
logging.info("user login", extra={"user": clean})
```

### 适用场景
所有 `logging.*(...)` / `logger.*(...)` / `print` 写日志的位置，形参中含外部数据时。

---

## 3.1.9 资源操作安全

### 规则
- 应避免用户输入控制资源标识符（防止访问/修改其他受保护的系统资源）。
- 应避免让用户提供目标引擎的模板（防止模板注入 / 服务器端代码执行）。

### 反例
```python
template_str = request.GET["template"]
Template(template_str).render(...)  # SSTI
```

### 正例
```python
# 模板从受信任来源加载，外部输入只作为变量
env.get_template("user_view.html").render(user=user_data)
```

### 适用场景
Jinja2 / Mako / Django Template 加载；文件路径 / S3 key / 资源 ID 接受外部输入时。

---

## 3.1.10 表达式操作安全

### 规则
- 应避免不受信任的数据被传递至应用程序并作为正则表达式使用（ReDoS / 注入）。

### 反例
```python
re.match(user_pattern, target)  # 用户控制正则 → ReDoS
```

### 正例
```python
# 白名单或预编译固定正则；如必须用户提供，限制长度并设置超时
ALLOWED = {"alpha": r"[A-Za-z]+", "digits": r"\d+"}
re.match(ALLOWED[user_choice], target)
```

### 适用场景
`re.match` / `re.search` / `re.compile` / `regex` 库；模式来自外部输入时。
