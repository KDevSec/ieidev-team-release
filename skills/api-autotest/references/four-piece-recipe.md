# 分层四件套配方 — 接入一个业务模块 `<m>`

把一个业务模块接入 API 测试，写"四件套"：单接口封装 + 复合动作 + 参数化数据 + pytest 用例，再到 conftest 补一个 fixture。下面用中性伪代码示范一个资源 `<resource>`（增 / 查 两接口）的接法——把 `<resource>` / `<Resource>Client` / 路径前缀换成你项目的实际命名即可。

## 件 1 — `service/<m>/<m>_client.py`：单接口薄封装

每个**真实存在的接口**写一个方法（**只覆盖接口清单里有的**，不要凭对称性臆造没有的 GET-by-id / PUT / DELETE）。每个方法发请求后过**统一响应校验出口**（见 `positive-negative-assertions.md`）。

```python
from service.httpclient import HttpClient   # 你项目的 HTTP 客户端基类

_PREFIX = "/api/<resource>"   # 路径前缀以接口清单 / OpenAPI 为准

class ResourceClient(HttpClient):
    def query_list(self, name=None, test_desc='', err_code='', err_message=''):
        """GET 列表。name=None 取全量；传 name 走后端过滤（便于按名反查）。"""
        url = f"{_PREFIX}/list"
        if name is not None:
            url = f"{url}?name={quote(str(name))}"
        resp = self.get(url)
        return self.check_result(resp, test_desc, err_code, err_message)   # 统一响应校验出口

    def create(self, payload, test_desc='', err_code='', err_message=''):
        """POST 新增。payload 只放 schema 字段。"""
        resp = self.post(_PREFIX, data=payload)
        return self.check_result(resp, test_desc, err_code, err_message)
```

要点：
- **payload 只传 schema 字段**。schema 没有的字段不要传、不要假设后端会存。
- 方法签名带 `test_desc / err_code / err_message`，把三态校验语义透传给调用方。

## 件 2 — `service/<common_action>.py`：跨接口复合动作

正向流的"创建 + 轮询确认"封装在这里，用例不直接拼。正向流**必须轮询确认**（后端写入有延迟）。

```python
class CommonAction:
    def add_resource(self, name=None, test_desc='', **kw):
        """新增 + 正向流按名轮询确认。:return (resource_id, name)；异常流返回 (None, name)"""
        name = name or f"AT_{rand_name()}"          # 测试数据统一前缀，便于事后批量识别/清理
        self.client.create({"name": name, **kw}, test_desc=test_desc)
        if test_desc:                                # 异常流：校验已在 check_result 完成，不查列表
            return None, name
        assert wait_until_present(                   # 正向流：轮询确认（治写入延迟，不裸 sleep）
            self.client.query_list, match_field="name", expect=name), \
            f"创建后查询列表失败，{name} 不在列表中"
        return self.find_id(name), name

    @staticmethod
    def warn_residual(rid, name):
        """后端无 DELETE 接口 → 无法真删，loud warn 留痕（Fail Loud，不假装清理）。"""
        log.warning(f"⚠️ 残留未清理（后端无 DELETE）：id={rid} name={name!r}；需 API/DBA 清。")
```

要点：
- id 解析、树形展平、深度计算等公共助手都放这里，用例复用。
- **没有 DELETE 接口的资源**：cleanup 只 loud-warn，不写假删除。

## 件 3 — `data/<m>/<m>_data.py`：参数化数据

正向 + 负向输入集，供 `@pytest.mark.parametrize` 用。负向集（异常名称、超长串、控制字符、注入子串、全空白）建议集中到一个公共特殊字符集模块。每行末列可带分类标签。

```python
NAME_FILTER_ABNORMAL = [
    ("blank",   "   ",               "全空白"),
    ("ctrl",    "\x01\x02",          "仅控制字符"),
    ("toolong", "A" * 5000,          "超长串（网关可能 414 优雅拒绝）"),
    ("inject",  "<script>x</script>","含注入子串"),
]
```

## 件 4 — `testcase/<m>/test_<m>_*.py`：pytest 用例

- 类名 `Test<Module><Action>`；函数名 = 被验证行为（`test_no_list_perm_returns_403`），禁空名。
- **docstring 第一行 = `<用例编号> <用例名称>`**（便于注入报告 / 回溯）。
- 注入 fixture：复合动作（管理员）/ `cleanup`（LIFO 善后）/ 受限登录工厂 / 软断言（一条用例收集多个校验点）。
- happy path ≤50%，必含等价类边界 + 异常流 + 错误注入。每条至少一个**业务断言**（不能只 `assert status_code == 200`）。

```python
class TestResourceCreate:
    def test_create_basic(self, common_action, cleanup, soft_assert):
        """<编号> 管理员新增 <resource>，输入合法名称，应创建成功并可查到"""
        rid, name = common_action.add_resource()             # 正向：复合动作 + 轮询确认
        cleanup(common_action.warn_residual, rid, name)
        node = common_action.find_by_name(name)
        assert node is not None, f"新增后未查到 {name}"          # 业务断言
        soft_assert.true_("source" in node,
                          "复现：新增记录缺 source 字段")        # 否定断言——命中即真缺陷，保留红
        soft_assert.assert_no_errors()
```

## 件 5（半件）— conftest 补 client fixture

在"业务模块 client fixture 在此处按需追加"处补一行：

```python
@pytest.fixture
def resource_client(common_action):
    return common_action.client
```

## marker 体系（建议自动还原）

conftest 可在 `pytest_collection_modifyitems` 自动补：未打分类 → `smoke + basic + full`；显式 `smoke` 但没 `basic` → 补 `basic`；所有用例补 `full`。这样下游只需在异常流方法上打 `@pytest.mark.negative`，其它按需。
