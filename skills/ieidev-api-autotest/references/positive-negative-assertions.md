# 统一响应校验出口 + 正向/异常断言纪律

每个接口封装方法都应过一个**统一响应校验出口**（一个集中的 `check_result(...)` 之类的方法），它的行为由"是否声明为异常流"决定——**这是 API 测试最容易踩的一处语义**。

## 三态语义

统一校验出口建议支持三种调用：

```python
client.create(payload)                                     # 正向：仅断言"业务成功"，返回 response
client.create(payload, test_desc='参数缺失')                # 异常：仅断言"业务失败"
client.create(payload, test_desc='参数缺失',
              err_code='E_001', err_message='不能为空')       # 异常 + 校验错误码 + 文案
```

出口内部骨架（命名按你项目）：
```python
def check_result(self, response, test_desc, err_code, err_message):
    if not test_desc:                                       # 正向流
        assert response['success'] is True, f"期望业务成功，实际 {response}"
        return response
    assert response['success'] is False, f"期望业务失败，实际 {response}"   # 异常流
    if err_code:
        assert err_message in response['msg'] and response['code'] == err_code
```

> 这里的"业务成功标志"（`success` / `code==200` / 具体约定）按你后端的响应壳约定取，模式不变。

## 陷阱：负向用例误用"正向封装"

业务封装（如 `query_list(name=None, test_desc='', ...)`）**默认走正向流**——内部断言"业务成功"。当一个**负向用例**（无权限 / 越权 / 参数非法，期望后端拒绝）调用这个默认封装：

```python
# ❌ 错：后端正确返回 403 业务失败，但封装在正向流里先抛 AssertionError（断"业务成功"失败）
resp = client.query_list()
assert resp.get("success") is False     # ← 永远走不到这行
```

后端**行为是对的**（403 拒绝正是用例要验证的），却被封装误判成红。这是 **script 假红**，不是 real-defect。

### 正确写法（二选一）

**A. raw 请求，绕过正向校验（推荐，最直白）**
```python
resp = client.get("/api/<resource>/list")      # raw，不过正向 check_result
assert resp.get("success") is False, "无权限用户调列表后端应拒绝"
assert resp.get("code") == 403, f"应 403 拒绝，实测 code={resp.get('code')}"
```

**B. 给封装传显式异常模式参数，切到异常流校验**
```python
resp = client.query_list(test_desc="无权限用户调列表")   # 切异常流，断"业务失败"
```

## 判别口诀

- **正向用例**（期望成功）→ 走封装默认正向流，断业务成功。
- **负向用例**（期望拒绝）→ 走 **raw 请求** 或显式异常模式，断业务失败（+ code/msg）。
- 同一模块里，create 侧负向用例用 raw 请求、query 侧负向却用了默认正向封装 → **不对称 = 陷阱信号**，对齐成 raw。

## 为什么这条值得单列

负向用例的"红"有两种来源：① 后端没拒绝（real-defect，该红）；② 后端正确拒绝但封装误判（script 假红，不该红）。混用正向封装会把②伪装成①，要么让你误报缺陷，要么让你为了消红去弱化断言——两条都违反第零原则。把负向路径与正向校验出口隔开，红才有意义。
