# 基础设施规范（强制）

> 这部分是模板的"骨架"——登录复用、资源清理、四件产物归档。下游项目复制模板时如果改坏了这三处，整个测试体系会失效（脏数据 / 报告路径乱 / 全量耗时翻倍）。
>
> 改动这些规范前先读懂"为什么"——每条都有源项目踩坑历史。

---

## §1 登录复用：session 级 storage_state

### 强制规则

- 用例**禁止**自带登录代码
- 整个 session 只登录一次，通过 `conftest.auth_state` fixture 把 `storage_state` 缓存给所有 context
- 用例只用 `logged_page` fixture（已自动复用登录态）

✅ DO
```python
def test_xxx(logged_page):           # 用 logged_page，已自动复用登录态
    ...
```

❌ DON'T
```python
def test_xxx(page):
    BasePage(page).login()             # 每条用例重复登录
    ...
```

### 为什么

源项目改造前 109 条用例每条登录 4–6 秒；改造后整 session 1 次登录。日志看：跑 41 条 AR-06 只看到一次 `[session] 首次登录`。

### 兜底机制

`logged_page` fixture 跳首页后检测到 `/login` 路径或密码框时**自动补登录**，cookies 失效不会让用例硬挂——所以下游项目无需手动处理"会话过期"边界情况。

### §1.1 storage_state 落盘（可选；本地调试期省时）

设 `APP_AUTH_STATE_FILE=.auth_state.json` 后（默认空，每次 session 走 UI 登录），`auth_state` fixture 会把 storage_state 持久化到该文件，下次启动若文件存在且未过期（`APP_AUTH_STATE_TTL` 秒，默认 1800）则**直接 load 跳过 UI 登录**。本地反复跑单条用例排查时省 5–10 秒/次。

| 场景 | 推荐配置 |
|---|---|
| CI（每次 fresh） | 留空（默认） |
| 本地反复跑单条用例 | `APP_AUTH_STATE_FILE=.auth_state.json` |

⚠ **必须把该文件加到 `.gitignore`**——含 cookies/JWT 是敏感凭证。模板内置 `.gitignore` 已处理。

### §1.2 page-level XSS / dialog 录制（默认装配）

`conftest.page` fixture 默认挂 `page.on("dialog", ...)`：把所有 `alert()/confirm()/prompt()` 的消息记到 `request.node._xss_alerts`，自动 dismiss 避免阻塞。

XSS 注入用例可一行断言：
```python
def test_xxx_xss(logged_page, request):
    # ... 注入 payload 后 ...
    alerts = request.node._xss_alerts
    assert not alerts, f"XSS 触发了 alert：{alerts!r}"
```

即使不写 XSS 用例，挂着也无副作用（dialog 不来 → 列表恒空）。

---

## §2 资源清理：function 级 + 仅清本用例新增 — **双轨**

模板提供两条等效轨道（两条共用 `utils/cleanup_registry.py` 的 LIFO + FK rank + 失败一次重试算法），按项目情况二选一或并存：

| 轨道 | 触发方式 | 适用 | 性能 |
|---|---|---|---|
| **API 轨**（推荐） | 用例显式 `cleanup.add(rtype, id)` | 项目有后端 API（`api.add_xxx() → 返回 id`）| 毫秒级 |
| **UI 轨**（兜底） | PageObject `save()` 触发 `_emit_resource_created("rtype", name)` | 项目无 API，只能列表页 → 搜索 → 点删除 | 秒级 |

### §2.1 API 轨（推荐）

#### 工作机制

```
test body
   proj_id = api.add_project(...)
       └─► cleanup.add("project", proj_id)   ← 紧跟创建后注册（不要插断言）
              └─► CleanupRegistry._items append
   ... 后续断言失败也清得到 ...

teardown ─► CleanupRegistry.run_cleanup(logger)
            │  - 类型内 LIFO + 类型间 FK rank 排序
            │  - 第一遍删失败 → deferred，第一遍跑完后再试一次
            └─► 仍失败 → warn + 不抛异常（避免 teardown 噪音）
```

#### 接入：在 `tests/conftest.py` override 根 `cleanup` fixture

```python
from utils.cleanup_registry import CleanupRegistry

@pytest.fixture(scope="session")
def api():
    """业务 ApiClient session-scope 单例。"""
    from utils.api import shared_api
    from utils.my_api_client import MyApiClient   # 下游项目子类化 ApiClient
    return shared_api(MyApiClient)


@pytest.fixture
def cleanup(api) -> CleanupRegistry:
    reg = CleanupRegistry()
    reg.register_deleter("version",
        lambda vid: api.delete_version(int(vid), ignore_missing=True))
    reg.register_deleter("project",
        lambda pid: api.delete_project(int(pid), ignore_missing=True))
    reg.register_deleter("productline",
        lambda pid: api.delete_productline(int(pid), ignore_missing=True))
    # FK 方向：子先删，父后删
    reg.register_fk_rank("version", 0)
    reg.register_fk_rank("project", 1)
    reg.register_fk_rank("productline", 2)
    yield reg
    reg.run_cleanup(logger)
```

#### `ApiClient` 子类化的命名契约

模板的 `utils/api.py::ApiClient` 是骨架——下游子类化后，**必须遵守命名契约**：

- `add_<resource>(...) -> int`：创建并返回 id（业务接口可能返回的 body 不含 id 时自己 find 一下）
- `delete_<resource>(id, *, ignore_missing=True) -> bool`：**幂等**（用例自删后再清也不抛）
- `find_<resource>(...)`：返回 dict 或 None
- `list_<resource>(...) -> list[dict]`

这套契约让 `cleanup.register_deleter` 的 `lambda` 能直接接入。

### §2.2 UI 轨（兜底）

#### 工作机制

```
setup ──► 注册 tracker callback 到 pages.base_page._RESOURCE_TRACKER
          │
          ▼
test body
   form.save()
       ├─ url 含 /add 吗？               ← 第一道关
       ├─ 表单读到名称吗？                ← 第二道关
       ├─ toast 含『成功』吗？             ← 第三道关
       └─ 三道全过 → _emit_resource_created("rtype", name)
                       └─► tracker 登记到 created[]
          │
          ▼
teardown ─► 遍历 created[] → 调 _CLEANUP_REGISTRY[rtype](page, name)
            │  - 用例没新增？直接 return（最常见路径，零开销）
            │  - 用例自删了？_row_exists 快判 → 记『未找到』日志
            │  - 删除失败？warn 日志 + 不抛异常
            └─► 必须在 page/context 关闭前执行
```

#### 接入新资源类型（在 tests/conftest.py）

```python
from utils.cleanup_registry import register_cleanup
from pages.<your>_page import <Your>ListPage
from utils.logger import get_logger
logger = get_logger("app.cleanup")


def _delete_<your>(page, name: str) -> None:
    lp = <Your>ListPage(page, logger)
    lp.open()
    lp.search_by_name(name)
    page.wait_for_timeout(300)        # 给搜索结果渲染时间
    if page.locator(f'.el-table__row:has-text("{name}")').count() == 0:
        return                         # 用例自删了，直接返回（不死等）
    lp.delete_by_name(name, confirm=True)


register_cleanup("<your>", _delete_<your>)
```

注册后，PageObject 的 `save()` 在 `_emit_resource_created("<your>", name)` 时即可自动触发清理。

### §2.3 哪条轨道？

```
项目有 ApiClient（可登录、可 add_xxx/delete_xxx）？
  ├── 有 → 优先 API 轨（毫秒级、确定性，不受 UI 漂移影响）
  │       └── R1 铁规天然落地：数据预制走 API，清理也走 API
  └── 无 → 走 UI 轨，接受秒级耗时
       └── 后续若接入了 API，逐资源类型迁移 — 两条轨道可并存

混合场景 — 同一用例两条都用：
  - 业务后端有 API → cleanup.add("project", pid)   走 API 轨
  - UI-only 资源（无后端入口） → PageObject.save() emit   走 UI 轨
```

### §2.4 四个反例（源项目踩过的，两条轨道都适用）

❌ **session 级前缀清理**：
```python
# 在 pytest_sessionfinish 按 ("TC", "AutoTest") 前缀扫表批量删除
# → 误删手工录入的真实数据，损失工时
```

❌ **edit 页面也登记资源**（UI 轨）：
```python
def save(self):                        # form 在 /edit 时也调 _emit_resource_created
    self.click_button("保存")
    _emit_resource_created("project", name)
    # → 编辑别人的项目时被你的 cleanup 误删
```

❌ **cleanup 死等 30s**（UI 轨）：
```python
def _delete_xxx(page, name):
    page.wait_for_selector(f'.el-table__row:has-text("{name}")', timeout=30000)
    # → 用例自删了的话，每条 cleanup 等 30s
```

❌ **`cleanup.add` 延迟到断言之后**（API 轨）：
```python
proj_id = api.add_project(...)
assert ...                       # 中途断言失败 → 跳到 teardown
cleanup.add("project", proj_id)  # ← 永远不会执行，资源泄漏
```

✅ **正：紧跟资源创建后注册**：
```python
proj_id = api.add_project(...)
cleanup.add("project", proj_id)  # ← 紧跟创建后
assert ...                       # 后续断言失败也能正常清理
```

源项目曾因这一漏洞累计孤儿数据 14 productlines + 5 projects。

### 三道关的实现（在 PageObject 的 save() 里）

```python
def save(self, *, resource_type: str = "biz") -> None:
    is_add = self.ADD_URL_FRAGMENT in self.page.url        # ① 必须是新增页
    snap_name = self._snapshot_name_for_tracker() if is_add else ""  # ② 名字必须读得到

    self.click_button("保存")
    toast_text = ...抓第一条 toast，timeout=3000ms...

    if is_add and snap_name and any(
        k in toast_text for k in ("成功", "已保存", "保存成功")     # ③ 必须有"成功"反馈
    ):
        _emit_resource_created(resource_type, snap_name)
```

任一条件不满足都**不登记**，确保 cleanup 不会乱删。

**为什么 `snap_name` 必须在点击保存前读？** 保存成功后页面会跳列表，名称就读不到了，必须在表单还显示时快照。

### 清理顺序：类型内 LIFO + 类型间 FK rank + 失败一次重试

模板的 `utils/cleanup_registry.py` 在 `run_cleanup()` 里按以下规则执行：

```python
# 类型间排序键（FK 方向，先孩子后父）
order = {"version": 0, "project": 1, "productline": 2}

# Python 排序稳定 → reversed(items) 在同 key 内保留 LIFO（最近添加最先删）
sorted_items = sorted(reversed(self.items), key=lambda x: order.get(x[0], 99))
```

**两条机制**：

| 机制 | 实现 | 解决的问题 |
|---|---|---|
| **类型内 LIFO** | `reversed(self.items)` | 用例后期创建的资源（往往依赖前期创建的）先删，避免外键冲突 |
| **类型间 FK rank** | `sorted(..., key=order.get)` | 即使用例添加顺序混乱，最终也按 `version → project → productline` 反向删除 |
| **失败一次重试** | 第一遍删失败的项目记入 `deferred`，第一遍跑完后再试一次 | FK 临时冲突在兄弟节点删完后会自然释放 |

```python
deferred: list[tuple[str, int | str, Exception]] = []
for rtype, rid in sorted_items:
    try:
        fn(rid)
    except Exception as e:
        deferred.append((rtype, rid, e))
for rtype, rid, first_err in deferred:
    try:
        fn(rid)
    except Exception as e:
        log.warning(f"cleanup {rtype}={rid} failed twice: first={first_err!r}; retry={e!r}")
```

### 反例：注册时机延迟 → 数据泄漏

❌ **`cleanup.add` 写在断言之后**：

```python
proj_id = api.add_project(...)
assert ...  # 中途断言可能 fail
cleanup.add("project", proj_id)  # ← 永远不会执行
```

✅ **资源创建成功后立刻注册**：

```python
proj_id = api.add_project(...)
cleanup.add("project", proj_id)  # ← 紧跟在创建后
assert ...  # 后续断言失败也能正常清理
```

源项目曾因这一漏洞累计孤儿数据 14 productlines + 5 projects。

---

## §HUD（HEADED 模式步骤气泡）

playwrightmode 模板提供 **opt-in** 的步骤气泡 HUD，左上角实时显示当前测试 + 当前原子动作 + 最近两条历史。

| 项 | 实现 |
|---|---|
| **位置** | `utils/step_bubble.py`（前端注入脚本 + Python 推送函数） |
| **接入** | `conftest.py` 的 `context` fixture 调 `install_on_context(ctx)`；`page` fixture 调 `attach_step_method(p)` |
| **插桩点** | `BasePage` 8 个原子动作（`goto` / `click_dialog_button` / `fill_input` / `select_option` / `select_tree_select` / `select_cascader_path` / `click_row_action` / `confirm_message_box`）入口加 1 行 `self._step(...)` |
| **跨导航存活** | 用 `sessionStorage` 中转 `__pt_test` / `__pt_step` / `__pt_trail`，`add_init_script` 每次导航重挂 |
| **顶部 chip** | docstring 第一行（见 case-skeleton.md 强制约定）|
| **触发** | `HEADED=1`（可加 `SLOWMO=300`） |
| **headless** | 全程 no-op，CI 同款，零开销，无行为差异 |

### 设计原则

1. **HUD 是测试基础设施的一部分，不是装饰**——一旦插桩到原子动作层，所有用例自动获益，且失败截图天然带"挂在哪一步"的语义信号 → 三分类的判断材料从"看 trace 倒推"变成"看截图直读"
2. **opt-in 默认 off 是关键**——CI 永远走 headless 路径、零开销、零行为差异；开发者本地一行 `HEADED=1 SLOWMO=N` 切到有头 + 气泡，用完即走
3. **气泡内容用 sessionStorage 中转**——跨同源导航 0 race condition；Python 侧不需要监听复杂的 page lifecycle 事件
4. **集中插桩，不在子类里手撒**——8 个原子动作覆盖 90% 有意义步骤；少数高级语义可由用例自己 `page.step(...)` 补

### 用法

```bash
# CI 默认（headless，无气泡，零开销）
python3 -m pytest tests/...

# 本地排查（有头 + 气泡 + 慢动作）
DISPLAY=:0 HEADED=1 SLOWMO=300 python3 -m pytest tests/...
```

测试代码内可按需追加自定义步骤：

```python
def test_xxx(logged_page):
    pl = ProductLinePage(logged_page); pl.open()
    logged_page.step("准备验证展开/折叠按钮的状态切换")  # 显式补一步
    ...
```

---

## §3 四件产物时间戳归档

### 强制规则

每次 `pytest` 执行的四类产物**共用同一时间戳**：

| 产物 | 路径 | 由谁产出 |
|---|---|---|
| HTML 报告 | `reports/report_<ts>.html` | pytest-html（conftest 自动注入路径） |
| 缺陷 CSV | `reports/defects_<ts>.csv` | `conftest.pytest_sessionfinish` |
| 截图子目录 | `screenshots/<ts>/...` | `utils/screenshot.capture` + 失败钩子 |
| 执行日志 | `logs/test_run_<ts>.log` | `utils/logger.get_logger` |

时间戳对齐意味着：**给 Claude 一个失败的 TC 编号，能 1 步找到对应日志、对应截图、对应 CSV 行**。下游项目改坏这点，定位失败要翻多个目录拼时间。

### 实现关键

`utils/logger.py` 在**模块导入时**就固定 `RUN_TS`（用 `setdefault` 写回环境），`conftest.pytest_configure` **沿用同一值**而非重新生成——否则 logger 与 report 时间戳会错位。

调用顺序：
```
conftest.py 顶部 import utils.logger
   └─► utils.logger 模块加载 → 固定 RUN_TS → setdefault 到 env
       │
       ▼
pytest_configure(config)
   └─► ts = os.environ.get("APP_RUN_TS") or now()  ← 沿用 logger 已固化值
```

### 反例（修正前的 bug）

```python
# 错误：pytest_configure 每次重新生成 ts，覆盖 logger 已固化值
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
os.environ["APP_RUN_TS"] = ts
```

下游项目接入时如果想改归档路径，**保留 RUN_TS 共用**这点不能动；改路径前缀是 OK 的。

### §3.1 HTML 报告 testId 列自动拼接用例描述

**模板已固化的钩子**（`conftest.pytest_html_results_table_row`）会自动给 pytest-html 报告
的 testId 列末尾拼接用例描述，让报告里看到的不是干巴巴的
`tests/...::test_tc002_xxx` 而是
`tests/...::test_tc002_xxx —— 异常流：RDM 接口不可达`。

**这意味着**：用例 `docstring 第一行` / 上方 `# TC-XXX  描述` 注释块**不止是
缺陷 CSV 的"用例名称"列**——也是 HTML 报告 testId 的拼接来源。命名漂移会同时
让 CSV、HTML 报告的可读性都变差。

**接入提醒**：

- 用例 docstring 第一行写得**像短标题**（"异常流：邮箱格式非法应阻止"），不要写
  动作过程（"打开 form 然后填错邮箱然后点保存看 toast"）；
- 不要在 docstring 里嵌入 HTML 特殊字符（`<` `>` `&`）—— 钩子会自动 escape
  防注入，但显示效果会被转义后变难看；
- 钩子对 setup/call/teardown 三次进 hook 幂等（`" —— "` 已在则不重拼），
  不需要担心重复。

**不动的事**：钩子只作用于 HTML 报告的 cell 字面，**不污染** `report.nodeid`
（避免影响 console / junit-xml 输出）。下游项目复制模板后**不要**自行改 nodeid。

---

## §4 分层禁忌（强制）

```
┌──────────────────────────────────────────────────┐
│  tests/test_arNN_xxx.py     用例层（声明式）       │
│  └─ 只调 PageObject 方法 + 标准断言                │
├──────────────────────────────────────────────────┤
│  pages/<biz>_page.py        业务 PageObject         │
│  └─ 继承 BasePage；只暴露业务语义方法              │
├──────────────────────────────────────────────────┤
│  pages/base_page.py         通用基类（必复用）      │
│  └─ Element-Plus 通用交互 + 反馈断言 + 资源追踪    │
├──────────────────────────────────────────────────┤
│  utils/                     横向工具                 │
└──────────────────────────────────────────────────┘
```

| 行为 | 评级 | 原因 |
|---|---|---|
| PageObject 里直接 `page.evaluate` 操作 DOM | ❌ 禁止 | 应封装到 BasePage |
| PageObject 里调 `pytest.skip` | ❌ 禁止 | 业务判断属 test 层 |
| 业务 PageObject 互相 import 业务方法 | ❌ 禁止 | 应靠 BasePage 通用能力解耦 |
| 测试用例直接 `page.locator(...)` 拼字符串 | ⚠ 不推荐 | 应在 PageObject 暴露方法 |
| 在 utils 里 import pages | ❌ 禁止 | utils 不依赖业务层 |

下游项目偶尔会有一两处违反，不一定要立刻重构，但**新代码不能引入新违反**——指出来就好。

---

## §5 业务 conftest 的写法（强制）

业务 / 项目特有的 fixture 应放到 `tests/conftest.py`，**禁止**改根 `conftest.py`（保持模板的通用性）。

业务最常做的事是注册资源清理（见 §2）。其它情况：

- 加自定义 fixture（如 `rdm_mock`）→ 放 `tests/conftest.py`
- 改根 fixture 行为 → 不要直接改根 conftest，用 fixture override
- 加新 marker → `pytest.ini` 注册（`--strict-markers` 拒绝未注册的）
- 改失败钩子 / CSV 归类规则 → 改根 `conftest._classify_root_cause`（这是少数允许动根 conftest 的场景，详见 `failure-diagnosis.md`）

---

## 接入新模块的检查清单

- [ ] 用 `logged_page`，没用 `page` + 自登录
- [ ] `tests/conftest.py` 已 `register_cleanup("<rtype>", _del_xxx)`
- [ ] `_del_xxx` 用 `_row_exists` 快判，不死等
- [ ] PageObject `save()` 实现"三道关 + 资源追踪"
- [ ] 新加的 marker 已在 `pytest.ini` 注册
- [ ] 没动根 `conftest.py`（除非加 CSV 归类规则）
- [ ] 没在 PageObject 里 `pytest.skip` 或 `page.evaluate`
