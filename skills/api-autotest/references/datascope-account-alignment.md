# 受限账号对齐环境预置 + 数据范围/越权用例

数据范围 / 越权类用例靠"以受限画像账号身份调接口"来验证。这里有两个反复踩的坑：**账号名要对齐预置脚本真实创建的账号**，以及**数据范围断言要忠实（否则弱绿）**。

## 坑 1：自造账号名 → 用例永远 SKIP（假覆盖）

环境账号通常由一个 **预置脚本单点创建**。受限登录工厂（`restricted_login(username)` 之类的 fixture）用该用户名 + 默认密码登录，**登录失败就返回 None → 用例 `pytest.skip`**。

如果用例引用了预置脚本从未创建的账号名，它就**永远 SKIP**，假装"已覆盖"。

```python
@pytest.fixture
def restricted_login():
    def _login(username, password=DEFAULT_PWD):
        client = ResourceClient(username=username, password=password)
        return client if client.headers.get("Authorization") else None  # 登录失败 → None
    return _login
```

### 接受限账号前先 grep 预置真实创建的全集

```bash
grep -n 'create_user(username=' <预置脚本>
```

只能用这份清单里出现的名字。**禁止**自造"语义更细但没人创建"的账号名（如 `..._scoped` / `..._covering`）——那等于把一条本该实跑的用例钉死在 SKIP。

## 典型受限画像（按你项目预置实际为准）

| 画像 | 权限点 | 数据范围 | 验证什么 |
|---|---|---|---|
| 无某权限点 | 缺 list / create | — | 调对应接口应被拒绝（4xx） |
| 有权限点无数据范围 | 有 | 空集（看不到任何数据） | 列表空态 |
| 受限子树 | 有 | 本部门及以下 | 越权/覆盖对照（自带种子数据） |
| 受限集合 | 有 | 指定部门集合（与子树不交叠） | 不覆盖对照 |

## 坑 2：数据范围断言"弱绿"——只断 success+list 不算验证

数据范围用例若只断 `resp.get("success") is True` + `isinstance(data, list)`，**永远绿**——它没校验"裁剪"这件事本身。这是弱绿，不是验证。

忠实断言要校验"看得到该看的、看不到不该看的"：

```python
# 读侧越权（受限子树用户不应看到他部门种子）
names = {n["name"] for n in iter_nodes(resp["data"])}
leaked = SET_OF_OUT_OF_SCOPE_SEEDS & names
assert not leaked, f"复现：受限用户看到授权外资源 {leaked}，数据范围未裁剪"

# 跨部门可见性（覆盖自建可见 / 不覆盖不可见）
covering.create({"name": name})                 # 由覆盖用户自建 → 落其数据范围内
assert any(n["name"] == name for n in iter(cov)), "覆盖用户应可见自建记录"
assert not any(n["name"] == name for n in iter(non)), "不覆盖用户不应可见他部门记录"

# 写侧越权（超范围上级新增应拒绝）
resp = client.post(URL, data={"name": "...", "parentId": out_of_scope_parent})
assert resp.get("success") is False, "上级超出授权数据范围新增应被拒绝"
```

如果后端**数据范围根本没生效**（受限用户看/写授权外资源），这些忠实断言会命中 → 真红，**保留红**。这正是测试的产出，不是 bug。先用一段探针确认地面真相（受限账号各看到几条、是否含越权种子），再决定断言的预期方向——但不论结果如何都不弱化断言。

## 重要边界：禁止改被测让数据范围"看起来生效"

数据范围未生效是**后端缺陷**。不要改后端、不要把断言降级成弱绿来回避。保留红 + 录 `defects_<ts>.csv` + 在汇总报告标注。若同一系统的 UI 自动化也测了同一条数据范围，注明"与 UI 侧同源缺陷"便于交叉印证。
