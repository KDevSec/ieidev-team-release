# 3.2 安全特性

> 概述：安全特性主要关注访问控制、密码管理、密钥管理、权限管理等问题。

## 3.2.1 访问控制安全

### 规则
- 数据库访问控制：应确保对数据库的访问是经过授权的，防止攻击者访问未经授权的记录。
- 应避免用户输入更改文件权限。

### 反例
```python
# 用户输入直接影响文件权限
os.chmod(path, int(request.GET["mode"], 8))
```

### 正例
```python
# 服务端固定权限值，外部不可控
os.chmod(path, 0o600)
# 数据库访问通过受控账户 + 应用层授权
```

### 适用场景
任何文件权限设置 (`os.chmod` / `os.fchmod` / `pathlib.Path.chmod`)；构建数据库连接 / DAO 层；接收用户身份后访问受控资源时。

---

## 3.2.2 密码管理安全

### 规则
- 禁止使用空密码。
- 禁止使用密码硬编码。
- 禁止把密码变量设为 NULL。
- 禁止采用明文形式存储密码。
- 禁止在注释中存储密码。
- 禁止使用弱密码学算法加密方式加密存储密码。
- 禁止单独使用加密哈希算法加密存储密码。

### 反例
```python
DB_PASSWORD = ""                     # 空密码
DB_PASSWORD = "P@ssw0rd123"          # 硬编码
# password = "my_secret"             # 注释里存密码
user.password = md5(plain).hexdigest()  # 仅哈希、无 salt
```

### 正例
```python
import os
DB_PASSWORD = os.environ["DB_PASSWORD"]   # 从环境变量/密钥管理服务读取

# 存储用户密码：使用 KDF（PBKDF2 / bcrypt / argon2）+ salt
import hashlib, os
salt = os.urandom(16)
hashed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 200_000)
```

### 适用场景
读取/写入数据库口令、API 密钥、用户密码；初始化连接配置；处理认证流程。

---

## 3.2.3 密钥管理安全

### 规则
- 禁止使用空加密密钥。
- 禁止使用硬编码加密密钥。
- 禁止使用空 HMAC 密钥。
- 禁止使用硬编码 HMAC 密钥。
- 禁止使用空 PBE 密码。
- 禁止使用硬编码 PBE 密码。
- 禁止把加密密钥变量设为 NULL。
- 禁止明文存储私钥。

### 反例
```python
from hashlib import pbkdf2_hmac
dk = pbkdf2_hmac('sha256', '', salt, 100000)   # 空 PBE 密码
HMAC_KEY = "abcdef"                             # 硬编码 HMAC 密钥
```

### 正例
```python
import os
HMAC_KEY = os.environ["HMAC_KEY"].encode()
password = os.environ["PBE_PASSWORD"].encode()
dk = pbkdf2_hmac("sha256", password, salt, 200_000)
# 私钥从受控密钥管理服务（KMS）/HSM 加载，不落盘明文
```

### 适用场景
任何 `cryptography.hazmat.primitives.kdf` / `hashlib.pbkdf2_hmac` / `hmac.new` / 私钥加载；KMS 调用；密钥轮换流程。

---

## 3.2.4 加密算法安全

### 规则
- 禁止使用弱加密算法（如 DES）。
- 采用 RSA 加密时应使用填充模式。
- 加密算法中禁止使用不安全的初始化矢量（IV）；IV 应使用加密伪随机数值生成器创建。
- 加密算法中禁止使用不安全的操作模式：推荐 CTR 模式，避免 ECB 与 CBC（ECB 对相同明文块产生相同密文；CBC 易受密文填塞攻击）。
- 加密算法中禁止使用较短的密钥长度：RSA 至少 2048 位。
- 避免使用流密码。
- 加密算法中禁止用户控制密钥大小。

### 反例
```python
from Crypto.Cipher import DES, AES
cipher = DES.new(key, DES.MODE_ECB)              # 弱算法 + ECB
iv = b"\x00" * 16                                # 静态 IV
cipher = AES.new(key, AES.MODE_CBC, iv)          # CBC + 静态 IV
key_size = int(request.GET["bits"])              # 用户控制密钥大小
```

### 正例
```python
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

iv = os.urandom(16)
cipher = Cipher(algorithms.AES(key), modes.CTR(iv))    # AES-CTR + 随机 IV

private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ciphertext = private.public_key().encrypt(
    plain,
    padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
)
```

### 适用场景
任何 `Crypto.Cipher` / `cryptography.hazmat` / 自实现加解密；RSA 密钥生成；构造 IV / nonce。

---

## 3.2.5 加密哈希算法安全

### 规则
- 禁止使用弱加密哈希算法（如 MD2、MD4、MD5、RIPEMD-160、SHA-1）。
- 禁止使用空 PBE Salt。
- 禁止使用硬编码 PBE Salt。
- 禁止使用用户控制的 PBE Salt。
- 禁止使用不安全的 PBE 迭代次数。
- 禁止使用空 Salt。
- 禁止使用硬编码 Salt。
- 禁止使用可预测的 Salt。
- 禁止使用用户控制的 Salt。

### 反例
```python
import hashlib
hashlib.md5(b"x").hexdigest()                       # 弱哈希
salt = b""                                          # 空 Salt
salt = b"static-salt"                               # 硬编码 Salt
salt = request.GET["salt"].encode()                 # 用户控制 Salt
hashlib.pbkdf2_hmac("sha256", pw, salt, 1000)       # 迭代次数过低
```

### 正例
```python
import os, hashlib
salt = os.urandom(16)                                          # 随机 Salt
dk = hashlib.pbkdf2_hmac("sha256", password, salt, 200_000)    # 足够迭代次数
# 或使用 bcrypt / argon2 等成熟 KDF
```

### 适用场景
`hashlib.md5/sha1/...` / `hashlib.pbkdf2_hmac` / 自实现 KDF；Salt 生成；密码哈希存储。

---

## 3.2.6 随机数安全

### 规则
- 推荐使用密码学的 PRNG，避免使用统计学的 PRNG。
- 禁止使用硬编码的 Seed（不应使用常量参数）。
- 禁止使用用户控制的 Seed。
- 避免使用弱熵源。

### 反例
```python
import random
random.seed(42)                       # 硬编码 Seed
token = random.random()               # 统计学 PRNG，输出可预测
```

### 正例
```python
import secrets, os
token = secrets.token_urlsafe(32)     # 密码学 PRNG
nonce = os.urandom(16)
```

### 适用场景
生成会话 ID / token / 一次性密码 / Salt / IV / 非业务展示性的随机数。

---

## 3.2.7 Cookie 安全

### 规则
- 应将 Secure、HttpOnly 属性设为 TRUE（Secure 仅 HTTPS 发送；HttpOnly 阻止客户端脚本读取）。
- 应将 CSRF_COOKIE_SECURE、SESSION_COOKIE_SECURE、SESSION_COOKIE_HTTPONLY 显式设为 True。
- 应尽可能限制域和域路径的设置。
- 应避免将敏感数据存储在永久性的 Cookie 中。

### 反例
```python
res.set_cookie("emailCookie", email)                # 默认未启用 Secure/HttpOnly
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = False
res.set_cookie("token", value, max_age=3650*86400)  # 永久 cookie 存敏感数据
```

### 正例
```python
from django.http.response import HttpResponse
res = HttpResponse()
res.set_cookie("emailCookie", email, secure=True, httponly=True)

# Django settings
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True

# 限制域和路径
res.set_cookie(
    "sessionid", value,
    path="/MyForum",
    domain="communitypages.example.com",
    secure=True, httponly=True,
)
```

### 适用场景
任何 `set_cookie` / `Set-Cookie` 头；Django/Flask 会话配置；OAuth/CSRF 状态。

---

## 3.2.8 传输安全

### 规则
- 应将应用程序配置为通过 SSL/TLS 发送 HTTP 重定向。
- 应设置具有足够到期时间的 HSTS 头文件，并将其应用于子域。
- 禁止与邮件服务器建立未加密的连接。
- 禁止采用弱 SSL 协议（SSLv2、SSLv23、SSLv3 包含多个缺陷，不应用于敏感数据传输）。
- SSL 连接时，应启用服务器身份认证（不应禁用服务器证书验证）。

### 反例
```python
import smtplib, ssl, requests
smtplib.SMTP("smtp.example.com", 25)             # 明文 SMTP
ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)         # 弱协议
requests.get(url, verify=False)                   # 禁用证书验证
```

### 正例
```python
# Django settings
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# SMTP over TLS
import smtplib
smtp = smtplib.SMTP_SSL("smtp.example.com", 465)

# requests 默认 verify=True；显式指定 CA bundle 时也保持开启
requests.get(url, verify=True)
```

### 适用场景
配置 web 框架 / 反向代理 / SMTP / outbound HTTP；自建 ssl.SSLContext；签发或验证证书。

---

## 3.2.9 Flask 使用安全

### 规则
- 应遵循 Flask 安全规范（参考 Flask 官方文档的安全注意事项：https://flask.palletsprojects.com/en/latest/security/ ）。

### 反例
```python
# 略——具体内容以 Flask 官方文档为准
```

### 正例
```python
# 编码时阅读 https://flask.palletsprojects.com/en/latest/security/
# 关键点：禁用 debug、Secret key 来自环境、CSRF 防护、安全 cookie 配置
```

### 适用场景
项目 import flask；定义 `app = Flask(...)` / 路由 / 表单处理时。

---

## 3.2.10 Django 使用安全

### 规则
- 应妥善保存 SECRET_KEY（泄露后攻击者可伪造会话；若使用 Pickle 序列化会话还可能 RCE）。
- 应验证 Host 标头（不可将 "*" 指定为 ALLOWED_HOSTS 唯一条目；该设置被 `django.http.HttpRequest.get_host()` 验证 Host 标头使用）。
- 应使用 JSON 而非 Pickle 对会话数据进行序列化（Django 1.6+ 默认 `django.contrib.sessions.serializers.JSONSerializer`）。
- 应保持 Django 自带的安全特性开启（XSS / CSRF / SQL 注入 / 点劫持 / SSL/HTTPS / 主机头验证。详见 https://docs.djangoproject.com/en/3.0/topics/security/ ）。

### 反例
```python
# settings.py
SECRET_KEY = "django-insecure-..."                              # 仓库可见
ALLOWED_HOSTS = ["*"]                                            # 不验证 Host
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"
```

### 正例
```python
# settings.py
import os
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = ["app.example.com", "api.example.com"]
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"
# 自带安全 middleware 全部启用
```

### 适用场景
所有 Django 项目的 `settings.py`；处理 HOST 头 / 反向代理配置；会话序列化变更时。

---

## 3.2.11 隐私安全

### 规则
- 敏感数据应进行加密存储（如 SHA2、RSA 等算法）；应使用独立的存储层，并在访问层开启访问控制；包含敏感信息的临时文件或缓存一旦不再需要应立刻删除。
- 禁止将敏感数据展示、存储：禁止写入到外部介质（控制台、文件系统、网络等）；应在后台进行脱敏处理；接口须返回脱敏后内容，禁止由前端/客户端脱敏。
- 敏感数据传输的过程应进行加密。
- 禁止由不可信赖的数据来控制敏感数据。

### 反例
```python
print(f"user={user.email}, password={user.password}")    # 落入控制台/日志
return jsonify({"id_card": user.id_card})                # 接口直接返回敏感字段
```

### 正例
```python
def mask_id(s: str) -> str:
    return s[:6] + "*" * (len(s) - 10) + s[-4:]

return jsonify({"id_card": mask_id(user.id_card)})
# 落库前对敏感字段加密；缓存设置 TTL；不再使用立即清理
```

### 适用场景
处理用户个人信息 / 身份证 / 手机号 / 支付信息 / 密钥；日志输出 / 接口序列化 / 缓存 / 临时文件。
