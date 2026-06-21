---
name: secure-coding
description: Use when 设计/编写/审查/测试 Python 后端/Web/Data 代码（Flask/Django/FastAPI/Tornado/aiohttp/Sanic/SQLAlchemy/pymysql/psycopg2/celery），或代码 *执行* SQL（cursor.execute/text()/ORM raw query）、*调用* eval/exec/compile/pickle.loads/yaml.load/subprocess/os.system、*设置* cookie/CSRF/CORS/CSP header、*处理* 密码/密钥/加密/哈希/安全随机数、*写入* 用户控制路径或调 chmod/mkstemp，或用户明确要求"安全审查/安全编码/合规检查"，或项目根目录 pyproject.toml/requirements.txt/setup.py *实际依赖* Web/Data 框架（仅文件存在不充分）。SKIP：开发防御性安全工具本身（SQL 注入检测器/WAF/SAST/扫描器/规则引擎/日志异常分析脚本）—— 这类代码 ABOUT 安全但不是被攻击面，8 类清单不适用；不接收外部输入的本地 CLI 脚本、不连数据库、不调 subprocess；仅做模式匹配/解析的工具（regex/AST/sqlparse 而不执行 SQL）；非 Python 代码或纯算法/数据分析/UI/ML 训练。例外：用户明确要求"审查这个防御工具自身的代码安全"则按正面触发。覆盖中文意图："写 Flask/Django/FastAPI 接口"、"Python 后端"、"参数化 SQL"、"加密/哈希/随机数"、"Cookie/CSRF/CORS"、"安全审查"。落地公司 8 类 Python 安全编码规范——按需查阅 references + 任务完成前 MUST 走 8 类清单核对。
---

# Python 安全编码规范 Skill

本 skill 把公司 Python 安全编码规范落到 Claude 的工作流中：description 触发为主路径，CLAUDE.md 锚点兜底，编码期按需查阅 + 完成前清单核对。

## 首次激活：自举写入 CLAUDE.md 锚点

每次本 skill 被调用，第一步执行：

1. 读取项目根目录的 `CLAUDE.md`
2. 若已包含 `secure-coding` 字样 → 跳过本节
3. 若否，按下方"项目检测"判断当前是否为 Python 后端项目；若是，向用户提议追加：
   ```
   ## 安全编码规范
   本项目所有 Python 代码改动（设计/编码/测试/审查）MUST 调用 `secure-coding` skill。
   ```
4. 用户同意 → 写入 CLAUDE.md；不同意 → 本会话不再询问
5. 若 CLAUDE.md 不存在 → 提议先创建一个最小 CLAUDE.md（或建议先跑 `/init`），再写入上述段落

## 项目检测

**强信号（任一命中即视为 Python 后端项目）：**
`pyproject.toml` / `requirements.txt` / `Pipfile` / `setup.py` 中出现：
- Web 框架：flask, django, fastapi, tornado, aiohttp, sanic, bottle, falcon, starlette, quart
- 数据/异步栈：sqlalchemy, pymysql, psycopg2, asyncpg, redis, celery, kombu, pika

**弱信号（强信号缺失时不主动自举，但仍可被 description 触发）：**
- 项目内有 `*.py` + 上述任一框架的 `import`
- 存在 `manage.py` / `wsgi.py` / `asgi.py` / `app.py`

## Layer 1 · 编码期按需查阅

写到对应代码点时，Read 对应 reference 文件验证规则。**关键词映射表**：

| 当前任务/代码出现 | Read |
|---|---|
| `cursor.execute` / SQL 拼接 / `?`/`%s` 参数化 | `references/01-input-validation.md` SQL 段 |
| `os.system` / `subprocess` / `shell=True` / `popen` / `eval` / `exec` / `compile` | `references/01-input-validation.md` 命令/动态评估段 |
| `pickle` / `marshal` / `yaml.load` / `cPickle` | `references/01-input-validation.md` 反序列化段 |
| `lxml` / `xml.etree` / `xml.dom` / XPath / XSLT | `references/01-input-validation.md` XML 段 |
| `smtplib` / `email.mime` | `references/01-input-validation.md` 邮件段 |
| 日志写入用户输入 | `references/01-input-validation.md` 日志段 |
| `re.compile` / 正则用户输入 | `references/01-input-validation.md` 正则段 |
| `redirect()` / 重定向到外部 URL | `references/01-input-validation.md` 网络段 |
| `open()` 路径用户控制 / `os.chmod` / `os.umask` | `references/04-api-misuse.md` |
| `tempfile` / `mkstemp` / `mktemp` | `references/05-time-and-state.md` |
| `hashlib` / `Crypto` / `cryptography` / `hmac` / `pbkdf2_hmac` / DES / AES / RSA | `references/02-security-features.md` 加密/哈希段 |
| `random.random` / `random.choice` / `secrets` / `os.urandom` / Seed | `references/02-security-features.md` 随机数段 |
| `set_cookie` / `Set-Cookie` / `CSRF_COOKIE_SECURE` | `references/02-security-features.md` Cookie 段 |
| Flask `app = Flask(...)` / `@app.route` | `references/02-security-features.md` Flask 段 |
| Django settings.py / SECRET_KEY / ALLOWED_HOSTS / MIDDLEWARE | `references/02-security-features.md` Django 段 |
| 用户认证 / 密码处理 / 密钥管理 | `references/02-security-features.md` 密码/密钥/访问控制段 |
| 敏感数据 / PII / 加密存储 | `references/02-security-features.md` 隐私段 |
| `print()` / `sys.stdout` / `sys.stderr` | `references/03-encapsulation.md` 输出段 |
| CSRF 中间件 / X-Frame-Options / X-XSS-Protection / `Access-Control-Allow-Origin` | `references/03-encapsulation.md` + `references/08-environment.md` |
| Content-Security-Policy / CSP | `references/03-encapsulation.md` CSP 段 |
| `try/except` / 异常向用户暴露 | `references/06-error-handling.md` |
| `os.sep` / `\` / 硬编码路径分隔符 | `references/07-code-quality.md` |
| `DEBUG=True` / 部署配置 / 依赖版本 / Python 版本 | `references/08-environment.md` |

无关键词命中的章节不要预先 Read——节省 token。

## Layer 2 · 完成前清单核对（completion gate）

声明任务完成 / 提交 commit / 创建 PR **之前** MUST 执行：

按以下 8 类逐条自检本次改动是否触发其中规则。命中即对应 Read references 验证；未命中跳过该项。

- [ ] **3.1 输入验证**：本次是否引入/修改了外部输入处理路径（HTTP 参数、请求体、文件读入、消息消费、CLI argv、环境变量）？
- [ ] **3.2 安全特性**：本次是否涉及密码、密钥、加密、哈希、随机数、Cookie、传输配置、Flask/Django settings？
- [ ] **3.3 封装**：本次是否涉及响应输出、CORS、CSP、可信/不可信边界？
- [ ] **3.4 API 滥用**：本次是否涉及文件上传/读写、权限设置（chmod/umask）？
- [ ] **3.5 时间与状态**：本次是否使用临时文件 / 共享状态 / 多线程多进程？
- [ ] **3.6 错误处理**：本次是否新增异常路径、错误响应、日志写入？
- [ ] **3.7 代码质量**：本次是否硬编码了路径分隔符或平台相关常量？
- [ ] **3.8 环境**：本次是否影响响应安全、部署配置、依赖版本、调试开关？

如与 `superpowers:verification-before-completion` skill 同时被触发，将本清单作为该 skill 的 Python 子清单提交。

## Reference 索引

- [`references/01-input-validation.md`](references/01-input-validation.md) — 3.1 输入验证与表示（10 子项：命令/动态评估/网络/数据库/SQL/XML/邮件/日志/资源/表达式）
- [`references/02-security-features.md`](references/02-security-features.md) — 3.2 安全特性（11 子项：访问控制/密码/密钥/加密/哈希/随机数/Cookie/传输/Flask/Django/隐私）
- [`references/03-encapsulation.md`](references/03-encapsulation.md) — 3.3 封装（5 子项：输出/网络/边界/CSP/CORS）
- [`references/04-api-misuse.md`](references/04-api-misuse.md) — 3.4 API 滥用（2 子项：文件/权限）
- [`references/05-time-and-state.md`](references/05-time-and-state.md) — 3.5 时间与状态（临时文件）
- [`references/06-error-handling.md`](references/06-error-handling.md) — 3.6 错误处理（4 条规则）
- [`references/07-code-quality.md`](references/07-code-quality.md) — 3.7 代码质量（路径分隔符）
- [`references/08-environment.md`](references/08-environment.md) — 3.8 环境（响应/部署/版本）
