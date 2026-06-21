# 用例编写骨架（按场景挑模板复制改字段）

> **核心原则**：复制示例改字段，不要从空白文件开始写。模板的 `tests/test_example.py` 已沉淀 6 类典型用例，覆盖了所有标准约定。
>
> 配套文件：`assets/test_arNN_skeleton.py`（直接复制改字段）。

---

## 文件级约定（强制）

### 文件命名

```
tests/test_arNN_<module>.py
```

- `arNN` = 业务模块号（ar01, ar02, ar03, ...）
- `<module>` = 该模块语义（snake_case 英文）

✅ 示例
- `test_ar01_login.py`
- `test_ar03_project_manual.py`
- `test_ar06_version_manual.py`

### 模块顶部 docstring（强制）

每个测试模块顶部**必须**写：

```python
"""
需求 AR-XXX-NN  <模块名>
覆盖用例 TC-XXX-NN-NNN ~ TC-XXX-NN-NNN

本模块覆盖：
- 基本流：...（列出主要场景）
- 异常流：...
- 备选流：...

⚠ UI 差异：
- 测试用例文档说『xxx按钮』，实际 UI 为『yyy』
- TC-NNN 涉及的『zzz 区域』当前 UI 未提供，将 skip 并记录
"""
```

UI 差异有就写、没有就略，但**不能省覆盖范围那段**——评审看模块概览靠它。

---

## 函数级约定（强制）

| 项 | 规则 | 示例 |
|---|---|---|
| 函数名 | `test_tcNNN_<slug>` | `test_tc014_add_project_all_fields` |
| docstring 首行 | **强制格式** `TC-AR<8 位 AR 编号>-<3 位序号>: <一句话中文标题>。` | `"""TC-AR04001004-004: 点击'展开/折叠'按钮 — 切换全部树节点状态。"""` |
| 标签 | 至少 3 个：模块 + 流类型 + 优先级 | `@pytest.mark.ar03 @pytest.mark.basic @pytest.mark.p1` |

❌ 反例（CSV 自动归档失效 / HEADED 气泡显示无意义内容）
- `test_新增项目`（中文，conftest 解析不出 TC 编号）
- `test_addProject14`（不符合 `test_tcNNN_` 模式）
- 只打 `@pytest.mark.p1`（缺模块和流类型）
- docstring 首行省略 / 写英文 / 只写 "TC-NNN" 不带标题

**为什么强制**：

1. 模板 `conftest._extract_tc` 用 `test_tcNNN_` 前缀解析 TC 编号
2. 模板 `conftest.pytest_runtest_makereport` 用 docstring 第一行填缺陷 CSV 的"用例名称"列
3. **HEADED 模式步骤气泡**（`utils/step_bubble.py`）顶部 chip 直接渲染 docstring 第一行——**渲染到屏幕上让人核对**，写裸函数名（`TEST_TC04001004004_EXPAND_COLLAPSE`）观察者根本看不出对应哪条业务用例

命名漂移会让 ① 自动归档失效 + ② 调试时分不清当前在哪条用例。

---

## 用例命题翻转 — 异常流反复挂前置不可达时的正确反应

**触发现象**：

- 一条异常流用例（`@pytest.mark.exception`）反复 fail，且 fail 在保存被接受、写库成功
- 用户肉眼观察 UI 发现：用例假设的"未填某字段"状态在 UI 上**根本不可达**（字段已带默认值 / 字段不可清空）
- 副作用：每次失败都伴随真实数据写入 + cleanup 卡住（如 `[601] 该产品线下尚有项目`）

**根因**：用例命题（"未选状态被拦截"）与实现（"字段恒有默认值不可清空"）不匹配——用例在测一个**不可达状态**，原地 assert 失败是正确的反向证据，但不是产品 bug。

**错误反应**：改 fixture 让其更"对得上"、放宽断言、`pytest.skip("环境数据不全")`——这些都是把问题埋深。

**正确反应 — 翻转命题**：

| 维度 | 改前（不可达异常流）| 改后（正向契约）|
|---|---|---|
| 函数名 | `test_..._status_unselected` | `test_..._status_default_non_clearable` |
| 标题 | "状态未选 — 应阻止保存" | "状态存在默认值 — 无法清空" |
| Marker | `@pytest.mark.exception` | `@pytest.mark.basic`（结构性正向契约）|
| Fixture | 全表填充走保存流 | 仅 `logged_page`，只读弹窗结构 |
| 断言 | 弹窗状态（间接、易误判）| ① 默认值非空 ② 清空动作不生效 — **双契约** |
| 数据副作用 | 每次写库 → 孤儿数据 | **零写入** |

```python
# 翻转后的新断言（直接说违反了哪条设计假设）
default_status = page_obj.get_status_value()
assert default_status and default_status.strip(), (
    "BUG[真实-UI/业务流程行为偏离预期]: 状态字段无默认值 — 违反'状态恒有有效值'设计契约"
)
cleared = page_obj.clear_status()
after = page_obj.get_status_value()
assert not cleared and after.strip() == default_status.strip(), (
    f"BUG[真实-UI/业务流程行为偏离预期]: 字段误开 clearable，状态可空 — 违反'状态恒有值'契约 "
    f"(default={default_status!r}, after_clear={after!r})"
)
```

**判别准则（用例失败时第一动作）**：

```
异常流用例反复挂 + 用户/肉眼看出"前提在 UI 不可达"
   → 不是后端漏校验缺陷，是用例命题错位
   → 翻转为正向契约（"X 必有默认值 + X 不可被清空"）
   → 用例 marker 从 exception 改为 basic
   → 副作用消失（零数据写入）
```

**沉淀**：当一条 `@pytest.mark.exception` 反复挂 + 每次都伴随数据污染（`cleanup ... failed: 该产品线下尚有项目`），**先翻转命题，不要先怀疑后端**。这是源项目踩出来的反复教训。

---

## 标签矩阵（pytest.ini 注册的）

```
优先级：p1 / p2 / p3                           — p1 核心 / p2 常规 / p3 边界容错
流类型：basic / exception / alternative        — happy path / 错误输入 / 取消回退
集合：smoke / regression                       — 可叠加
模块：ar01 / ar02 / ...（按业务拆）
特殊：db / api / slow                          — 触发特殊运行条件
```

新加 marker **必须**先在 `pytest.ini` 注册（`--strict-markers` 拒绝未注册的）。

---

## 骨架 1 — 基本流（新增 + 列表断言）

```python
import time
import pytest

from pages.base_page import BasePage
from pages.<your>_page import <Your>ListPage, <Your>FormPage
from utils.logger import get_logger, step
from utils.screenshot import capture

logger = get_logger("arNN")


def unique_name(prefix: str = "AutoTest") -> str:
    """毫秒级时间戳后缀，同一秒连跑也不冲突。"""
    return f"{prefix}-{int(time.time() * 1000) % 10_000_000}"


def open_add_form(page) -> <Your>FormPage:
    lp = <Your>ListPage(page, logger)
    lp.open()
    lp.click_new()
    return <Your>FormPage(page, logger)


# ============================================================
#  TC-NNN  基本流：<场景一句话>
# ============================================================
@pytest.mark.arNN
@pytest.mark.basic
@pytest.mark.p1
@pytest.mark.smoke               # 可选；冒烟集
def test_tcNNN_<slug>(logged_page):
    """TC-NNN：<用例标题>。"""
    logger.info("TC-NNN 开始")
    form = open_add_form(logged_page)
    name = unique_name("TCNNN")

    step(logger, 1, "<业务步骤 1>")
    form.tab_basic()
    form.fill_name(name)
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空，无法继续")

    step(logger, 2, "保存并断言成功")
    form.save()
    capture(logged_page, "TC-NNN", "saved")     # 关键节点截图（可选）
    BasePage(logged_page, logger).assert_save_success("TC-NNN <场景>")

    step(logger, 3, "回列表 → 按名称搜索 → 行可见")
    lp = <Your>ListPage(logged_page, logger)
    lp.open()
    lp.search_by_name(name)
    lp.row_by_name(name).wait_for(state="visible", timeout=6000)
```

---

## 骨架 2 — 异常流（必填空 / 超长 / 非法）

**强制**：异常流**禁止**用裸 `assert`，必须用 `assert_save_blocked` 或 `assert_field_validation`。

```python
from tests._helpers import assert_save_blocked


# ============================================================
#  TC-NNN  异常流：<字段名> 超长应阻止保存
# ============================================================
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p1
def test_tcNNN_<field>_overlong(logged_page):
    """TC-NNN：<字段名> 输入 1001 字符应阻止保存。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))

    step(logger, 1, "故意填超长 <字段名>")
    form.fill_overview("X" * 1001)

    step(logger, 2, "保存 → 断言被阻止")
    form.save()
    capture(logged_page, "TC-NNN", "overlong")
    assert_save_blocked(
        logged_page,
        "项目概述与目标",
        reason="1001字符应阻止保存",
    )
    # 失败信息：保存未被阻止：1001字符应阻止保存；
    #           field-error='' toast='新增成功' url='.../list'
    #           state=fields={'项目概述与目标': {'value': 'PPPP...', 'length': 1001}}
    # CSV 自动归类："UI 漏校验：超长/非法值未拦截，直接保存成功"
```

`assert_save_blocked` 的判定标准（任一即视为已阻止）：
- field-error 非空
- toast 含错误
- URL 还在表单页

**禁止反例**：
```python
form.fill_overview("X" * 1001)
form.save()
assert form.get_field_error("项目概述与目标") != "", "应有错误"
# ↑ 失败信息只剩 "应有错误" — 不知道是 UI 漏校验、后端 422、还是脚本读错字段
```

### 骨架 2 变体 — 截断 / 规整型异常流（必备）

⚠ **写"超长 / 越界 / 非法值"用例前先按 `references/element-plus-pitfalls.md` 坑 5 配套的判定矩阵跑 `tools/probe_overlong.py`**。`actual_len == limit && maxlength == limit` 时是合法 UX 截断，不能用 `assert_save_blocked`，必须用以下变体：

```python
from tests._helpers import assert_field_truncated_to, assert_input_number_regulated


# ============================================================
#  TC-NNN  异常流变体：maxlength 自动截断（合法 UX）
# ============================================================
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p2
def test_tcNNN_<field>_truncated(logged_page):
    """TC-NNN：<字段名> 输入 1001 字符前端自动截断到 1000，截断后保存成功。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))

    step(logger, 1, "故意填超长 <字段名>（1001）")
    form.fill_<field>("X" * 1001)

    step(logger, 2, "断言前端自动截断到 1000（合法 UX）")
    assert_field_truncated_to(logged_page, "<字段名>", 1000, type_hint="textarea")

    step(logger, 3, "保存 → 截断后值合法应成功")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 截断后保存")


# ============================================================
#  TC-NNN  异常流变体：input-number blur 规整（合法 UX）
# ============================================================
@pytest.mark.arNN
@pytest.mark.exception
@pytest.mark.p2
def test_tcNNN_<field>_regulated(logged_page):
    """TC-NNN：<input-number 字段> 输入 -1 blur 规整为 0，保存成功。"""
    form = open_add_form(logged_page)
    form.tab_basic()
    form.fill_name(unique_name("TCNNN"))

    step(logger, 1, "断言 -1 被 blur 规整为 0（合法 UX）")
    assert_input_number_regulated(
        logged_page, "<字段名>",
        raw_input=-1, expected_after_blur=0,
    )

    step(logger, 2, "保存 → 规整后值合法应成功")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 规整后保存")
```

**判定指引**（详见 element-plus-pitfalls.md 坑 5 配套段）：

- `actual_len == limit && maxlength == limit` → 合法 UX 截断 → 用 `assert_field_truncated_to` + `assert_save_success`
- `actual_len == limit+1 && maxlength is None` → input 接收全部 → 用 `assert_save_blocked`
- input-number `-1 → "0"`（规整）→ 用 `assert_input_number_regulated` + `assert_save_success`
- input-number `-1 → "-1"`（未规整）→ 用 `assert_save_blocked`

**血泪典故**：源项目首轮 6 条这类用例都用 `assert_save_blocked`，结果全部 FAIL（因为前端确实截断/规整了，保存就是成功），第二轮跑 probe_overlong 后才重判为合法 UX。

---

## 骨架 3 — 取消 / 备选流

```python
# ============================================================
#  TC-NNN  备选流：行内删除点取消
# ============================================================
@pytest.mark.arNN
@pytest.mark.alternative
@pytest.mark.p2
def test_tcNNN_delete_cancel(logged_page):
    """TC-NNN：列表行内点删除，弹框选取消，行仍存在。"""
    form = open_add_form(logged_page)
    name = unique_name("TCNNN")
    form.tab_basic(); form.fill_name(name)
    try:
        form.select_first_dropdown("产品线")
    except TimeoutError:
        pytest.skip("产品线下拉空")
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN 准备数据")

    step(logger, 1, "回列表 → 行内删除 → 选取消")
    lp = <Your>ListPage(logged_page, logger)
    lp.open()
    lp.search_by_name(name)
    lp.delete_by_name(name, confirm=False)      # 关键：confirm=False 走取消

    step(logger, 2, "断言行仍在")
    assert lp.row_by_name(name).count() == 1, "取消后行不应消失"
```

---

## 骨架 4 — 接口级用例（不需要 UI fixture）

```python
import pytest
from utils.api import post, is_endpoint_alive

ENDPOINT = "/api/your/endpoint"

# 接口未上线 → 模块级 skip（避免逐条用例都报连接错误）
pytestmark = pytest.mark.skipif(
    not is_endpoint_alive(ENDPOINT),
    reason=f"接口 {ENDPOINT} 不可达"
)


@pytest.mark.arNN
@pytest.mark.api
@pytest.mark.p1
def test_tcNNN_push_basic():
    """TC-NNN：合法数据推送应返回 200。"""
    r = post(ENDPOINT, json={"id": "v1", "name": "..."})
    assert r.status_code == 200, f"接口失败 {r.status_code}: {r.text[:200]}"
```

---

## 骨架 5 — DB 校验补强

```python
from utils import db


def test_tcNNN_add_with_db_check(logged_page):
    """TC-NNN：新增 + DB 校验入库一条，且关键字段一致。"""
    form = open_add_form(logged_page)
    name = unique_name("TCNNN")
    form.tab_basic(); form.fill_name(name)
    form.save()
    BasePage(logged_page, logger).assert_save_success("TC-NNN")

    rows = db.query("SELECT * FROM project WHERE name=%s", (name,))
    if rows is None:
        pytest.skip("DB 未配置")        # 标准 skip 模式
    assert len(rows) == 1, f"DB 应入库 1 条，实际 {len(rows)}"
```

---

## 骨架 6 — 数据预制 fixture：让"前置数据空 → SKIP"转 PASS

> 用于 SKIP 三分法的 **C.2 类**（"没有 RDM 项目"、"没有未关联版本"等前置数据问题）。
> 把"用例自己 try-skip"换成"fixture 通过 mock/seed API 预制 + yield + 清理"，
> SKIP 转 PASS。源项目第四轮通过这一招把 TC-001/004 从 SKIP 转 PASS。

**前提**：项目有可调用的 mock 后端（如 `ruoyi-fastapi-mock` 跑在 9199）或有 seed/admin
API 能注入测试数据。下游项目复制本骨架，把 `is_alive() / add_xxx() / delete_xxx()` 替换成
你们自己的 mock 客户端调用。

```python
# tests/test_arNN_xxx.py
import pytest

# 业务侧的 mock 客户端：is_alive / add_xxx / delete_xxx 三件套
from utils import biz_mock  # ← 下游项目实现：utils/biz_mock.py


def _unique_payload_name(prefix: str = "AutoTest") -> str:
    import time
    return f"{prefix}-{int(time.time() * 1000) % 10_000_000}"


@pytest.fixture
def seeded_dept():
    """fixture：mock 后端预制一条产品线，yield 给用例，结束后清理。

    - mock 不可达 → 模块级 skip（**不是**用例失败，避免假缺陷）
    - 预制成功 → yield payload（含 id / name / 其它字段）
    - teardown 自动 delete（无论用例 PASS / FAIL，避免脏数据）
    """
    if not biz_mock.is_alive():
        pytest.skip("mock 后端不可达（参考 .env.example 配置）")
    payload = biz_mock.add_dept(name=_unique_payload_name("自动化产品线"))
    yield payload
    try:
        biz_mock.delete_dept(payload["id"])
    except Exception as e:
        # 清理失败仅 warn，不让用例 teardown 抛异常
        import logging
        logging.warning(f"[seeded_dept] 清理 id={payload['id']} 失败：{e}")


# ============================================================
#  TC-NNN  基本流：用 seeded_dept 让"前置数据"用例从 SKIP 转 PASS
# ============================================================
@pytest.mark.arNN
@pytest.mark.basic
@pytest.mark.p1
def test_tcNNN_sync_with_seeded_data(logged_page, seeded_dept):
    """TC-NNN：mock 端预制产品线后，平台同步应能找到这条数据。"""
    expected_name = seeded_dept["name"]

    step(logger, 1, "触发同步")
    page_obj = ProductLineSyncPage(logged_page, logger)
    page_obj.open()
    page_obj.trigger_sync()

    step(logger, 2, "在平台列表里断言能搜到 mock 端预制的名称")
    page_obj.search_by_name(expected_name)
    page_obj.row_by_name(expected_name).wait_for(state="visible", timeout=8000)
```

**关键设计点**：

| 选择 | 理由 |
|---|---|
| `is_alive()` 不通过则 `pytest.skip` | mock 端口未开 → 该测的"环境前置"无法满足，正确归为 A 类配置缺失（不是脚本错） |
| 用 `yield` + try/except 清理 | 即使用例 FAIL，清理仍执行；清理失败仅 warn 不抛异常（避免 teardown 噪音）|
| `_unique_payload_name` 用毫秒时间戳 | 与 `unique_name` 同模式，连跑不冲突 |
| fixture 范围默认 `function` | 每个用例独立预制 + 清理，不共享状态（除非性能敏感且数据可共享时改 `module`）|
| **不要**把 mock 客户端封装放业务 PageObject | 它属于 utils 层（外部 API 客户端），不是 UI 抽象 |

**血泪典故**：源项目第四轮加 `rdm_seeded_dept` fixture 后，TC-001/004（产品线同步）
从 SKIP（"无 RDM 数据"）→ PASS。这种从 SKIP 转 PASS 的覆盖率提升比"忍受长期 SKIP"
价值大得多——**前提是你有可控的 mock 后端**。

---

## 提 PR 前的自检清单

- [ ] 文件名 `test_arNN_<module>.py`
- [ ] 模块顶部 docstring 写明覆盖范围 + UI 差异
- [ ] 函数名 `test_tcNNN_<slug>`，三位编号
- [ ] 每条 docstring 第一行是用例标题
- [ ] 至少 3 个标签（模块 + 流类型 + 优先级）
- [ ] 异常流用 `assert_save_blocked` / `assert_field_validation`，不用裸 assert
- [ ] 新增类用例名称用 `unique_name(prefix)`
- [ ] UI 暂未提供 → `pytest.skip`，不用 `assert`
- [ ] 关键步骤用 `step(logger, N, ...)`
- [ ] `tests/conftest.py` 已为新资源类型 `register_cleanup`（详见 infra-standards.md）
