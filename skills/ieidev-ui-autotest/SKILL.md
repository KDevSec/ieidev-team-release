---
name: ieidev-ui-autotest
description: |
  **核心基座（第零原则）：测试脚本的目的是执行测试、发现 BUG，不是生成通过率高的 reports 报告。所有规范、约束、流程都服务于这一条——红是产出，不是失败；遇到冲突永远选这条。**
  写 / 改 / 接入 Playwright + pytest + Element-Plus 自动化测试时使用本 skill。它把 playwrightmode 模板（D:\ClaudeCode\KDevSec\playwrightmode）从源项目反复打磨出来的 6 大类规范——**STEP 0 环境/菜单/弹窗实测前置**、登录复用、资源清理、四件产物归档、Element-Plus 三大坑、用例命名、失败诊断——固化为下游项目（KDevSec / Gen9 / 可信评估 / vfadmin 等）的强制实践。**用户提到下列任何关键词，都应主动加载：写 / 加 / 补 / 接入 / 优化测试用例、test_arNN、TC-NNN、PageObject、el-select 点不到 / 下拉、toast 抓不到、is_field_readonly、defects_<ts>.csv、recon_elements、recon_env_bootstrap、menu_list.md、probe_dom、用例为什么挂、登录复用、资源清理、Element-Plus 自动化测试、playwrightmode、playwrighttest、登录测试环境获取菜单、采集菜单结构、测试环境实测、UI 与 spec 对不上**。即使用户没明说"playwrightmode"四个字，只要项目里有 ``pages/base_page.py`` + ``conftest.auth_state`` + ``utils/cleanup_registry.py`` + ``tools/recon_elements.py`` 等模板特征文件，或者用户说"登录测试环境采菜单/写测试用例 .md/把 spec 与 UI 对齐"，都视为本 skill 适用范围。**第一动作恒为：检查 recon/menu_list.md 是否存在且新鲜——不存在/过期就先调用独立 skill `ieidev-env-recon` 完成 STEP 0**（STEP 0 标准动作已迁出到 `ieidev-env-recon`；本 skill 仅在 `recon/menu_list.md` 就绪后走 STEP 1+。本 skill 的 `assets/recon_env_bootstrap.py` + `references/env-recon-bootstrap.md` 作为 fallback 保留）。
---

# playwrightmode 自动化测试编写规范

本 skill 服务于**基于 playwrightmode 模板搭建的下游项目**。模板原型在 `D:\ClaudeCode\KDevSec\playwrightmode\`，下游项目（如 `playwrighttest` / Gen9 / 可信评估）会复制其 `conftest.py` / `pages/base_page.py` / `utils/` / `tools/` 形成自己的测试目录。

下游项目可能改了业务字段、加了 fixture、扩了 PageObject，但**这 6 大类规范是模板沉淀出来的核心资产，绕过它们的代价已经被验证过——不要重新踩**。

---

## 第零原则（基座）— 测试脚本的目的：发现 BUG，不是刷通过率

**所有 6 大规范、5 条约束、10 步流程，都是这一条基座原则的具体落地**：

> **测试脚本的目的是执行测试、发现 BUG，而不是生成通过率高的 reports 报告。**
> **当本原则与"让 reports 好看 / 让 CSV 干净 / 让用例都绿"冲突时，永远选本原则。**

### 为什么要把这条单列为基座

测试脚本写多了，作者会不自觉地把"绿色"当成产物——脚本一红就改脚本让它绿、断言一硬就软化让它过、用例一挂就 `pytest.skip` 让它消失、`defects_<ts>.csv` 一长就调宽容忍度让它短。**这是把"评估系统"调成了"安抚系统"**——评审看到的是 100% 通过率，但每条用例都已经失去发现真问题的能力，假绿掩盖了真红。

源项目踩过的所有最贵的坑——约束 4 的"否定性 UI 假 SKIP"、约束 3 的"前缀清理误删真实数据"、约束 2 的"异常流断言只剩『应有错误』非空就过"——共同的根因都是这条：**作者下意识在把脚本"调通"，而不是让脚本"打出真问题"**。第零原则单列在所有规范之前，就是为了在每次写代码 / 改代码 / 优化前先在心里过一遍方向。

### 三条直接推论（写脚本 / 改脚本 / 评审脚本时按这三条判）

**推论 1 — 红是产出，不是失败。**
脚本红了的第一动作是走 `references/failure-diagnosis.md` 的三分法（**脚本缺陷 / 用例设计问题 / 真实 UI/后端缺陷**）。三类里**只有"脚本缺陷"才允许改脚本**；后两类必须保留红色，把信息提给业务/产品/后端处理——必要时在 issue 链接到 CSV + 截图 + 复现日志。**改脚本让真 bug 变绿是 bug 隐藏行为**，不是优化。

**推论 2 — `pytest.skip` 不能用来"洗"通过率。**
skip 只允许两种情形：

- **(a) UI 真不存在**：用 **playwright MCP**（`browser_navigate` → `browser_snapshot` 取 DOM 真值 → `browser_take_screenshot` 截图）实测 + 探测器复检过（约束 4 的「探测器 + 兜底 skip」模式，UI 后续实装能自动恢复）；
- **(b) 上游依赖未就绪**：环境 / 数据 / 关联模块未到位，在 docstring 写明依赖项与解锁条件。

**为了让 CSV 看起来干净而 skip，等同于把真缺陷从评估视野里抹掉**——比让用例红更糟，因为没人会去复跑 skip 的用例（约束 4 已经踩过 4 条 P2 假 SKIP 一整迭代的坑）。

**推论 3 — 断言不放宽、超时不放大、`try/except` 不吞异常。**

| 看到这种写法 | 立即停手，因为它在做的事是 |
|---|---|
| `assert form.get_field_error("xxx") != ""` | 反正非空就行 → 把"必须报特定错误"调成"随便报点什么都过" |
| `page.wait_for_timeout(10000)` 当兜底 | "加大点也许就过了" → 把 timing flaky 用更长 sleep 掩盖 |
| `try: step() except Exception: pass` | 步骤挂了不要紧 → 让脚本在错误状态下继续，下游断言还能"碰巧绿" |
| 把 `assert_save_blocked` 换成 `assert True` 或注释掉 | 直接拆掉测试目的 |
| 异常流改成"只要不报错就算过" | 异常流的本质就是"该报错却没报"才是 bug，反过来写就废了 |

要么用 `assert_save_blocked` / `assert_field_validation` 等模板封装的精确断言；要么承认现场看不准 → 用 **playwright MCP**（`browser_navigate` → `browser_snapshot` 取 DOM 真值）实地复检 → 再写精确断言。**绝不写"反正能过的"断言**。

### 写完 / 改完每段代码必须自问的三道判定

```
1. 如果业务 UI / 后端真的有 bug，这条用例会不会红？
   答"会" → 合格；答"不一定 / 看情况" → 重写

2. 这次"优化"做的是 [假红 → 真绿]（脚本 bug 修了），
                    还是 [真红 → 假绿]（真 bug 被掩盖了）？
   只有前者算优化；后者必须 revert

3. 这条 pytest.skip / 这个放宽的断言 / 这次延长的超时 —— 实测复检过吗？
   没有 → 退回去；有 → 在代码注释里贴 playwright MCP 实测时间 + 截图路径
```

**Reports 是评估证据，不是评估目标。100% 通过率本身没有意义——能定位真 bug 的失败远比好看的绿色有价值。**

---

## 用户首轮请求里的 4 条铁规（每个项目接入时同步落地）

> 来源：用户在 `/ui-autotest` 首次调用【技术要求】段固定的 4 条；本框架已在 KDevSec/playwrighttest v2.3 验证（105 PASS / 8 真 bug / 4 探测器 SKIP）。这 4 条是**底线**，任何 round-extra 优化都不能违反。

### R1 — 数据预制走 API，不走 UI

> 用户原话："增加数据预制操作，如：项目列表测试需要产品线，在项目列表/新增测试脚本之前，新增统一的产品线数据预制操作"

| 维度 | 规则 |
|---|---|
| **预制方式** | 通过 `/docker-api`（或对应后端 API），毫秒级、确定性 |
| **预制位置** | pytest fixture 在 setup 阶段执行；命名 `fresh_<resource>` / `<scenario>_<resources>` |
| **唯一性** | 资源名带 ms 时间戳 + 前缀（`unique_name("AT_PL")`），方便日志 grep |
| **禁止** | UI 流"先点新增产品线再点新增项目"做数据预制——慢、易碎、找不到 SUT bug |

### R2 — 依赖资源显式预制 + 用例后清理

> 用户原话："存在依赖操作的时候，应当在测试用例中增加该操作 ...（如「已存在产品线 B」） ... 且对应用例脚本执行完成后，清理预制数据资源"

| 维度 | 规则 |
|---|---|
| **预制范围** | 用例 docstring 列出的所有「前置条件」资源，**逐一**显式创建 |
| **隐式条件不补** | 字典 / sysUsers 等环境基线由 session fixture 一次性保证 |
| **清理粒度** | function level（**禁止** session 级前缀清理 — 见约束 3）|
| **清理顺序** | 类型内 LIFO + 类型间 FK rank（version → project → productline）|
| **清理鲁棒性** | 失败一次重试 + ignore_missing |
| **注册时机** | `cleanup.add(rtype, rid)` **紧跟资源创建后**调用，不要插在断言后（中途断言失败会跳过未注册的资源 → 数据泄漏） |

### R3 — 测试目的：发现 BUG，不刷通过率

这是**第零原则**的另一种表述。R3 的具体落地见上节"三条直接推论 + 三道判定"。

### R4 — 用例之间独立，无执行依赖

> 用户原话："测试用例之间应独立执行，不应存在执行依赖关系，如：用例 2 执行不应依赖用例 1 的执行结果"

| 维度 | 实现 |
|---|---|
| **数据独立** | 每用例自创资源（带 ms 时间戳），互不冲撞 |
| **状态独立** | 每用例独立 BrowserContext，加载共享 storage_state 但 cookies 隔离 |
| **顺序独立** | 用例可任意 `pytest <单个用例>` 单跑；任意打乱顺序结果一致 |
| **登录独立** | 登录态走 storage_state（session fixture 一次产出），不依赖前置用例 |

**禁止模式**：全局变量传 ID（`global created_id; ... use(created_id)`）/ 用例靠固定测试数据（`page.click_row("产品线B")` 假设环境有这条）。

### 验证清单（任何新增 / 改动用例都要过）

- [ ] **R1**：用例没用 UI 流做数据预制？所有依赖资源都来自 fixture / API？
- [ ] **R2**：用例 docstring 列的前置资源都被 setup 显式创建？所有 setup 创建的资源都 `cleanup.add(...)` 紧跟注册了？
- [ ] **R3**：每条断言能在真 bug 出现时 RED 吗？没有"反正能过"的写法？SKIP 是否带"已用 playwright MCP（browser_snapshot）实测复检"标注？
- [ ] **R4**：用例可以独立单跑通过吗？打乱顺序 / 重复执行结果一致吗？

不过任一条 → 用例不合格，改到合格再合并。

---

## 何时该读哪个 reference

下列分支按"用户问题类型"决定下一步动作。**不是每条任务都要全读 5 个 reference**——按需读。

| 用户场景 | 第一时间读 |
|---|---|
| **首次接入测试环境 / 菜单可能变了 / `recon/menu_list.md` 不存在或过期** | **调用独立 skill `ieidev-env-recon`**（STEP 0 已迁出；本 skill `references/env-recon-bootstrap.md` + `assets/recon_env_bootstrap.py` 仅作 fallback）|
| 新增一个测试模块（test_arNN_xxx.py）/ 接入新页面 | `references/case-skeleton.md` + `assets/test_arNN_skeleton.py` |
| 写 / 优化测试用例 Markdown 文档（spec.md / 用例.md） | 先调用 `ieidev-env-recon` 拿到 `recon/menu_list.md` → 再用 `assets/test_case_doc_header.md.tpl` 在用例文档头部插入"测试环境与导航约定"节 |
| 写新的业务 PageObject / 改 BasePage | `references/element-plus-pitfalls.md` |
| el-select 点不到 / toast 抓不到 / readonly 误判 / Tab 切换 flaky | `references/element-plus-pitfalls.md`（直接定位陷阱） |
| 用例之间数据残留 / 清理失败 / 登录慢 / 报告路径乱 | `references/infra-standards.md` |
| 看 `reports/defects_<ts>.csv` 失败原因 / 失败诊断 / 提 issue 还是改脚本拿不准 | `references/failure-diagnosis.md` |

reference 文件都不超过 200 行，按需读完即用。

---

## 五条不可妥协约束（即使你"看起来想到了更简单的写法"也不要破）

> 这五条都是 **第零原则（基座）** 在不同场景的具体落地——本质都是为了让脚本"在真有 bug 时能红"，而不是"看起来都过"。读约束之前，先把第零原则那三条推论在心里过一遍。

这五条是源项目（KDevSec/playwrighttest）反复翻车后定下来的硬规则，写代码前先在心里过一遍：

### 约束 1 — 不要绕过 BasePage 直接拼 Element-Plus 的 locator

> **错误的迹象**：你正想写 `page.locator(".el-select-dropdown__item:has-text('xxx')").click()` 或 `"is-disabled" in page.locator(".el-select").get_attribute("class")`。

Element-Plus 有 6 个反复踩出的坑（下拉假可见、select 穿透禁用、toast 3 秒消失、按钮文本互相包含、input-number fill 绕过 spinner、Tab 切换竞态），每个坑的解决方式都已封装到 `pages/base_page.py`。下游项目调它就行：

```python
self.select_option_by_label("产品线", "操作系统")    # 不要拼 .el-select-dropdown__item
self.is_field_readonly("项目名称")                  # 不要拼 .is-disabled
bp.assert_save_success("TC-014 创建项目")           # 不要 wait networkidle 5s 再读 toast
```

详细症状/根因/正确写法在 `references/element-plus-pitfalls.md`。**有疑问就读它，不要凭直觉造轮子**——直觉造的轮子在源项目都翻过车。

### 约束 2 — 用例命名 / 标签 / 异常流断言不能漂移

> **错误的迹象**：你正想用 `test_新增项目` 或 `test_addProject14` 这种名字；或者只打了一个 `@pytest.mark.p1`；或者异常流写了 `assert form.get_field_error("xxx") != ""`。

模板的 `conftest` 有一套自动归档逻辑——它**依赖**这些命名约定才能把缺陷写进 `defects_<ts>.csv`：

| 约定 | 谁依赖 | 漂移的代价 |
|---|---|---|
| 函数名 `test_tcNNN_<slug>`（NNN 三位） | `_extract_tc` 解析 TC 编号 | CSV 里"用例"列变空，无法回溯 |
| docstring 第一行写用例标题 | CSV "用例名称"列 | 评审看不出这条用例是干嘛的 |
| 至少 3 个标签（模块 / 流类型 / 优先级） | `pytest -m` 过滤 / 报告分组 | 没法只跑冒烟 / 只跑 p1 |
| 异常流用 `assert_save_blocked` / `assert_field_validation` | `_classify_root_cause` 自动归类 | 失败信息只剩"应有错误" |
| 新增用例名走 `unique_name(prefix)` | per-test cleanup + 数据隔离 | 同名冲突 + 脏数据 |
| UI 暂未提供 → `pytest.skip` | CSV 假缺陷过滤 | CSV 累计真假混杂 |

骨架在 `references/case-skeleton.md` + `assets/test_arNN_skeleton.py`。**复制改字段，不要从空白文件开始写**。

### 约束 3 — 资源新增/清理走"三道关 + register_cleanup"，禁止 session 级前缀清理

> **错误的迹象**：你正想在 `pytest_sessionfinish` 里按 `("TC", "AutoTest")` 前缀扫表批量删除；或者在 PageObject 的 edit 页面也调 `_emit_resource_created`；或者让 cleanup 死等 30s。

源项目曾用前缀批量清理，结果**误删了手工录入的真实数据**。模板换成了 function 级 + 三道关：

```
form.save() →
   ├─ url 含 /add 吗？           ← 第一道关
   ├─ 表单读到名称吗？            ← 第二道关
   ├─ toast 含『成功』吗？         ← 第三道关
   └─ 三道全过 → _emit_resource_created("rtype", name)
                  └─► 走到 tests/conftest.py 的 register_cleanup → 用例 teardown 自动删
```

下游项目接入新资源类型时，在 `tests/conftest.py` 调 `register_cleanup("project", _del_project)`，删除函数内用 `_row_exists` 快判（300ms），**不要死等**。

详细机制 + 反例 + 注册模板：`references/infra-standards.md` §2。

### 约束 4 — 否定性 UI 注释（"X 不存在 / X 未提供"）必须实测验证

> **错误的迹象**：你正想凭一句注释 / docstring / optimize 历史 / skip reason 写
> `pytest.skip("当前 UI 未提供 'xxx' 表格")`，或者直接相信 PageObject 里
> "UI 没有 xxx 字段"的注释跳过实装。

**这是源项目踩的最贵的坑**——比绕基类、命名漂移、误清理加起来还贵。第八轮源项目曾把
"项目人员 Tab 没有项目组成员表格"硬编码 skip 4 条 P2 用例；注释、PageObject docstring、
optimize 历史、skip reason 四处互相引用形成"事实回声"，越读越笃信。直到一次例行复跑
现场拍快照——UI **早已实装**该表格 5 列，4 条假 SKIP 全部该 PASS。

**为什么否定性事实特别危险**：

| 性质 | 否定性事实（"X 不存在"） | 肯定性事实（"X 这样做"） |
|---|---|---|
| 写下时是否真 | 是 | 是 |
| UI 演进后会失效 | ✅ 会（UI 加东西很常见）| ❌ 不会（UI 不会自己抽筋删元素）|
| 谁会主动复检 | **没人**（skip 用例长期没人跑）| 测试自己（每次跑都验证）|
| 暗债沉淀路径 | 注释→docstring→optimize→skip reason 四处复制成"共识" | 不存在 |

**强制做法**：

✅ DO ——"探测器 + 兜底 skip"模式（让 UI 后续实装能自动恢复）

```python
# PageObject 里写探测器
def has_member_table(self) -> bool:
    return self._member_table().count() > 0

# 用例里调探测器，兜底 skip
def test_xxx(logged_page):
    form = open_xxx_form(logged_page)
    if not form.has_member_table():
        pytest.skip("当前 UI 未实测到项目组成员表格（已用探测器复检）")
    # 真步骤 ...
```

✅ DO —— 在写脚本/skip 前**先用 playwright MCP 实地复检**

```
用户说"加 TC-026 但 UI 没那个表格" / 文件头注释说"UI 未提供"
→ 第一动作：用 **playwright MCP**（`browser_navigate` → `browser_snapshot` 取 DOM 真值 → `browser_take_screenshot` 截图）+ tools/probe_*.py 现场截图
→ 实测确认后再决定走"探测器+兜底 skip"还是"实装真步骤"
```

❌ DON'T —— 凭注释/历史日志硬编码 skip

```python
def test_xxx(logged_page):
    pytest.skip("当前 UI 未提供 '项目组成员' 表格")  # ← 这就是源项目踩过的坑
```

**模板对应规范**：`STANDARDS.md §1.1`（playwrightmode 模板已把这条升级为铁规）。

**配合 playwright MCP 实地复检**：见下一节。任何"否定性 UI 注释"的实测复检都必须用 playwright MCP 实地复检，不允许自己拍脑袋判断。

### 约束 5 — 用例池入口契约：只对 `是否UI自动化=是` 的用例写 UI 自动化脚本

> **错误的迹象**：你正想直接拿一份测试用例 .md 就开始写 PageObject / pytest 脚本，没核对每条用例的「是否UI自动化」字段；或者只看了 TC 编号 / 用例名称就开工，没注意字段值是"否 / 待定 / 空白"。

**来源**：上游 skill `ieidev-team:ieidev-test-cases` 渲染规约——`是否UI自动化` + `是否API自动化` 是用例 .md 每个 `【测试用例信息】` 块的 MANDATORY 字段，明确约定 "downstream pipelines split UI ↔ API automation lanes by grepping these two exact field names"。本 skill（UI 自动化下游）按这条契约硬 gate；并行的 `ieidev-team:ieidev-uicase-to-apicase` / API 自动化 skill 按 `是否API自动化=是` 分流，互不重叠。

**第一动作**（写任何 PageObject / pytest 脚本之前）：

```bash
# 把 "是否UI自动化：是" 的用例切片为候选池（兼容全角/半角冒号 + 常见 yes 变体）
grep -nE "是否UI自动化[：:][[:space:]]*(是|Y|yes|true|✓)" 测试用例.md
```

**对三种字段值的处理**：

| 字段值（归一化后） | 动作 |
|---|---|
| `是 / Y / yes / true / ✓` | ✅ **唯一允许进入 UI 自动化编写通道**的用例 |
| `否 / N / no / false` | ❌ **refuse 写 UI 脚本**——告知用户该用例分流通道：纯接口校验 → `ieidev-team:ieidev-uicase-to-apicase` + `kdev-api-test-scaffold`；性能 / 安全 / 日志审计 → 手写 / 其它专用通道 |
| `待定 / TBD / 空白 / 字段缺失` | 🟡 **不在下游兜底**——告知用户先回 `ieidev-team:ieidev-test-cases` 把字段补齐，再回来调用本 skill；本 skill 不臆测、不放行 |

**显式 override 通道**（保留正当例外，但要可审计）：

某些 P1 关键路径用例按规约标了"否"（如："接口已覆盖即可"的核心业务流），业务实际仍要求 UI 兜底回归。此时**允许**用户在该用例的 `【测试用例信息】` 块内追加一行注释：

```
# override-ui-automation: <可审计理由，如"P1 核心登录流，接口已覆盖但需 UI 回归看门狗，PM 确认 2026-MM-DD">
```

带这条注释的用例可放行进入 UI 编写通道。**未带注释强行让我写 → refuse**。所有 override 用例必须在最终交付的 `RUN_SUMMARY.md` 加一段「override 清单」（用例编号 + 理由 + override 时间），方便评审追溯。

**为什么是硬 gate 而不是 warn**：

把 `是否UI自动化=否` 的用例（多为纯接口校验 / 后端事件断言 / 日志审计 / 性能 / SSO 单点 / 第三方回调）硬塞 UI 通道 → 不得不绕 UI 间接断言（"点了按钮没报错就当通过"）→ 断言被迫弱化 → 假绿。这违反 **第零原则** 和 **R3**。Warn-only 模式在 LLM 自驱场景下会被自己说服跳过——同类暗债沉淀路径已经在约束 4 "否定性 UI 假 SKIP"上踩过：写下时是真的、没人主动复检、注释→docstring→optimize→reason 四处复制成"共识"，最终 4 条 P2 用例假 SKIP 一整迭代。这次提前用硬 gate 拦截。

---

## 用 playwright MCP 实地复检的时机

**触发条件**：本 skill 被加载后，凡是涉及"脚本新建 / 编辑 / 优化"的环节，**必须**用 playwright MCP 工具实地复检，再继续操作。原因：playwright MCP 提供 `browser_navigate`/`browser_snapshot`/`browser_take_screenshot`/`browser_console_messages` 等工具直接操控浏览器 — DOM 侦察 + 截图调试 + 控制台抓取，这是判断"字段名 / selector / 异步状态"是否还跟 UI 一致的最快路径，比凭记忆造轮子或只跑 `recon_elements.py` 信息量更大。

| 子任务 | 何时用 playwright MCP 复检 |
|---|---|
| 新建测试脚本（test_arNN_xxx.py / 新 PageObject） | 在跑 `tools/recon_elements.py` 之前或之后，用 playwright MCP 做一次实地侦察：`browser_navigate` 访问 → `browser_snapshot` 拿到当前 DOM/selector 真值 → `browser_take_screenshot` 截图 |
| 编辑已有脚本（改字段名 / 改断言 / 加用例） | 用户给的字段名跟 `recon_dump.json` / 已有 PageObject 不一致时，必须用 playwright MCP（`browser_navigate` → `browser_snapshot`）实地访问页面对一遍 DOM，**不要凭记忆改** |
| 优化/诊断（用例挂了 / flaky / `defects_<ts>.csv` 的根因不清楚） | 用 playwright MCP 直接 reproduce：`browser_navigate` → `browser_snapshot` 取 DOM + `browser_take_screenshot` 全页截图 + `browser_console_messages` 抓控制台日志，再去判 PageObject 缺陷 / UI 差异 / 真实 bug 三分法 |

**调用方式**：

直接使用 playwright MCP 工具序列：`browser_navigate(url)` → `browser_snapshot()` → `browser_take_screenshot()`，按需追加 `browser_console_messages()` 抓日志。拿到结果再回到本 skill 的 6 大规范继续写代码。**先用 playwright MCP 拿现场 DOM 真值 → 再回到 ieidev-team:ieidev-ui-autotest 落规范**。

> ⚠️ **禁止跳过**：哪怕你"觉得"字段名没变 / "记得"上次能点 / "估计"是 timing 问题——只要进入新建/编辑/优化分支，先用 playwright MCP（`browser_navigate` → `browser_snapshot`）拿现场 DOM 真值，再说下一步。源项目踩过太多次"凭印象写、UI 早变了"的坑。
>
> 🔴 **最贵的子坑——否定性 UI 注释**（与上一条约束 4 配套）：
> 当代码 / 注释 / docstring / optimize 历史 / skip reason 任何地方说
> "X 不存在 / X 未提供 / 当前 UI 没有 Y"，**第一动作必须是**用 playwright MCP（`browser_navigate` → `browser_snapshot` → `browser_take_screenshot`）
> 实地复检——这种否定性事实在 UI 演进后失效是常态，但因为 skip 用例长期没人复跑，
> 暗债会沉淀。源项目曾因此让 4 条 P2 用例假 SKIP 了一整迭代。
> 实测确认 UI 真没有后，再走"探测器+兜底 skip"模式（写法见约束 4），**不要硬编码 skip**。

---

## STEP 0 — 环境 / 菜单 / 弹窗实测前置（已迁出到独立 skill `ieidev-env-recon`）

> **来源**：vfadmin / KDevSec 实战经验。spec 文档常滞后于真实 UI——按钮叫「新增项目」实际只叫「新增」、对话框叫「新增产品线」实际叫「添加产品线」、工具栏「展开全部 / 折叠全部」实际是单按钮 toggle、spec 漏列必填字段。凭 spec 写出的脚本/用例第一跑就挂；先做 5 分钟 STEP 0 实测前置，省 5 小时调试 + 用例文档反复返工。

### STEP 0 现在由独立 skill `ieidev-env-recon` 承担

`ieidev-env-recon` 提供：
- 4 阶段标准流程（登录 → 菜单全树 → 目标页探针 → 弹窗探针）
- 自动渲染 `recon/menu_list.md` 权威文档（含 §6 差异表）
- 可选回写模式（`--cases <path>` → propose 测试用例步骤修正补丁）

**调用方式**（用户口语触发即可）：
- "登录测试环境采一下菜单 / recon 一下 / 抓菜单 / 写脚本前先采一遍"
- 或直接 `Skill(skill="ieidev-env-recon")`

### 何时跳 STEP 0

只有在**所有**下列条件成立时才能跳 STEP 0：

- 当前测试项目根目录已有 `recon/menu_list.md`
- `recon/menu_list.md` 头部声明的"采集时间"在本 sprint 内
- 用户明确说"菜单未变 / UI 未动"
- 不涉及新接入页面 / 新写测试用例文档

任一条件不成立 → 调用 `ieidev-env-recon` 重跑。

### STEP 0 与 STEP 1（`tools/recon_elements.py`）边界

| 维度 | STEP 0（`ieidev-env-recon`）| STEP 1（本 skill）|
|---|---|---|
| 范围 | 全菜单 + 多页面 + 弹窗 一次性采集 | **单页面**深度元素 dump |
| 触发 | 接入新环境 / 长时间未跑 / 写新测试用例文档 | 写某个 PageObject 之前 |
| 输出 | `recon/menu_list.md` + 4 类 JSON | `tools/recon_dump.json`（单页） |
| 谁是权威 | 全局菜单 / 跨页文案 / 弹窗标题 | 单页字段 disabled / readonly / 选项 |
| 一次跑完管多久 | 一个 sprint（菜单未变即可复用） | 写一个 PageObject 一次 |

**两者不重叠**：STEP 0 负责"导航 + 文案"（独立 skill），STEP 1 负责"字段 + 状态"（本 skill）。

### Fallback：本 skill 内置资产（如 `ieidev-env-recon` 不可用）

如果运行环境没装 `ieidev-env-recon`，或者用户明确要求不嵌套调用其他 skill，**本 skill 仍保留可独立跑的 fallback**：

- `assets/recon_env_bootstrap.py` —— 独立 Python + Playwright 一键脚本
- `references/env-recon-bootstrap.md` —— 4 阶段流程详细说明 + selector 策略

用法与 `ieidev-env-recon` 相同（改 `BASE_URL` / `USER` / `PWD` / `TARGET_PAGES`，跑脚本，按 §阶段 4 渲染 `menu_list.md`）。**优先级**：`ieidev-env-recon` > 本 skill fallback。

---

## 标准 10 步开发流程（STEP 0 完成后，接入新业务模块按顺序走）

> **前置 GATE（约束 5 落地，先于 step ① 执行）**：在跑 recon 之前先把用例池过一遍 ——
> `grep -nE "是否UI自动化[：:][[:space:]]*(是|Y|yes|true|✓)" 测试用例.md > candidates.txt`。
> 候选数为 0 → 告知用户"本批无 UI 自动化用例，是否走 `ieidev-team:ieidev-uicase-to-apicase` 改派"；
> 候选数 > 0 → **仅对候选用例**启动下面 10 步；
> 字段空缺 / 待定 → 回 `ieidev-team:ieidev-test-cases` 补字段，不兜底；
> override 用例 → 单列在 `RUN_SUMMARY.md` 「override 清单」段。

```
①  跑 tools/recon_elements.py 侦察目标页面（强制；不能跳）
   - 输出 tools/recon_dump.json + 全页截图
   - 字段名 / 按钮名 / Tab 名以这份 dump 为准，不以测试用例文档为准
   - **配套**：先用 playwright MCP（`browser_navigate` → `browser_snapshot` → `browser_take_screenshot`）
     直连页面拿一次实时 DOM（locator + screenshot），与 recon_dump 交叉印证
②  对照陷阱速查（references/element-plus-pitfalls.md）确认要用的 BasePage 方法
③  复制 pages/example_page.py 为 pages/<your>_page.py，改 LIST_URL / 字段名 / Tab
   - List 类：search / row 定位 / 行内按钮
   - Form 类：tab / fill / select / save（save 内做三道关）
④  字段判断有怀疑 → 按现象选对探针（都在 tools/ 下），先实测再改脚本
   ┌──────────────────────────────────────────────────────────────────────┐
   │ 现象                              │ 跑哪个探针            │ 看输出哪个字段       │
   ├───────────────────────────────────┼───────────────────────┼──────────────────────┤
   │ 字段 disabled / readOnly 判定矛盾  │ tools/probe_dom.py    │ inputInfo[*].disabled │
   │ "超长字符未拦截 / 负数被保存"     │ tools/probe_overlong  │ verdict（合法 UX？）  │
   │ "下拉空 → SKIP" 但你不确信         │ tools/probe_select.py │ items_no_search[*]    │
   │ 否定性 UI 注释（"X 不存在"）       │ playwright MCP（browser_snapshot/browser_take_screenshot） │ 全页截图 + DOM 真值   │
   └──────────────────────────────────────────────────────────────────────┘
   - probe_overlong：按 STANDARDS §6.3 判定矩阵，区分"合法 UX 截断 / 接收全部 / maxlength 设错"
   - probe_select：用 boundingClientRect+offsetParent 筛真实可见 items，区分
     "脚本踩下拉假可见"还是"真实数据空"（多选/single 都适用）
   - **probe_* 拿不到的动态状态**（hover/focus 后才出现的元素、异步 toast、shadow DOM）
     → 用 playwright MCP（`browser_navigate` → `browser_snapshot` → `browser_evaluate`）现场验证，
       拿到 selector 真值后再回来改 PageObject
⑤  在 tests/conftest.py 追加 register_cleanup("<your_rtype>", _del_xxx)
   - _del_xxx 必须用 _row_exists 快判，不死等
⑥  复制 tests/test_example.py 为 tests/test_arNN_xxx.py
   - 模块顶部 docstring 写覆盖范围 + UI 差异
   - 复制 6 类示例（basic 全字段 / basic 仅必填 / except 必填空 / except 超长 /
     列表筛选 / 编辑+删除）改业务字段
⑦  按用例约定写：函数名 test_tcNNN_<slug>、3 标签、step、unique_name
⑧  跑 pytest tests/test_arNN_xxx.py -v
⑨  看 reports/defects_<ts>.csv 自动归类，按 references/failure-diagnosis.md 分三类处理
⑩  在 STANDARDS.md 末尾"优化历史"追加索引（findings_<YYYYMMDD>.md）
```

**为什么 ① 不能跳**：源项目第一轮基线 21 条 AR-03 失败，绝大多数是"脚本按文档写、UI 早已迭代"。一次 5 分钟的 recon 省 5 小时调试——这条经验已经验证过太多遍了。

---

## 当用户要"写一条新用例"时的标准动作清单

如果用户的请求很具体（"给项目编辑页加 TC-022：项目名称超长应阻止保存"），按下面的顺序操作，**不要先写代码再补这些步骤**：

0. **用例池入口过滤（约束 5，强制）**：该用例的 `是否UI自动化` 字段值是什么？
   - `是` → 继续往下走
   - `否` → **refuse**，告知用户走 `ieidev-team:ieidev-uicase-to-apicase` / 手写其它通道；不要因为"用户已经让我写"就放行
   - `待定 / 空白` → 让用户先回 `ieidev-team:ieidev-test-cases` 补字段
   - 用户带 `# override-ui-automation: <理由>` 注释强行要求 → 放行，但记到 `RUN_SUMMARY.md` 「override 清单」
1. **STEP 0 前置（强制）**：当前测试项目根目录有 `recon/menu_list.md` 吗？没有 / 过期 → **调用独立 skill `ieidev-env-recon`** 把 `menu_list.md` 产出来，并把测试用例 `.md` 头部「测试环境与导航约定」节补上（`assets/test_case_doc_header.md.tpl`）。如 `ieidev-env-recon` 不可用，fallback 用本 skill 的 `assets/recon_env_bootstrap.py` + `references/env-recon-bootstrap.md`。**这一步在所有写代码 / 改用例文档动作之前**。
2. **确认前提**：当前目录里有 `pages/base_page.py` 和 `tests/conftest.py` 吗？没有就提醒用户先 bootstrap 模板。
2. **确认字段名**：用户给的字段名（"项目名称"）和 `recon/menu_list.md` + `tools/recon_dump.json` 一致吗？不一致以 recon 为准，并提醒用户。两份 recon 都跟用户说法都对不上时 → 用 playwright MCP（`browser_navigate` → `browser_snapshot`）现场访问页面再确认一遍 DOM。
3. **确认 PageObject 已存在**：`pages/<biz>_page.py` 里有 `fill_<field>` 方法吗？没有就先在 PageObject 上加，再写用例。**新加 PageObject 方法前**先用 playwright MCP（`browser_navigate` → `browser_snapshot`）拿一次实时 selector，避免凭文档造方法。
4. **拿骨架改字段**：从 `assets/test_arNN_skeleton.py` 复制对应类型（基本流 / 异常流），改 TC 编号、字段名、断言文案。
5. **跑一次确认**：`pytest tests/test_arNN_xxx.py::test_tcNNN_xxx -v`。**用户没让你跑就不跑**——只是建议用户跑。
6. **报告产出**：变了哪几个文件、新增 TC 编号、是否需要 register_cleanup。

---

## 当用户要"诊断失败"时的标准动作

用户说"看下 defects_<ts>.csv" 或 "TC-XXX 为什么挂"，**不要凭印象瞎猜根因**：

1. 找到 CSV → 看"原因分析"列（自动归类已经分了）
2. 找到对应截图 → `screenshots/<ts>/<test_name>_failure_<ts>.png`
3. 找到日志 → `logs/test_run_<ts>.log` 看 `步骤 N` 哪一步挂的
4. 按 `references/failure-diagnosis.md` 的三分法判断：
   - **脚本缺陷**（PageObject 写错） → 修 PageObject 重跑
   - **用例设计问题**（文档与 UI 不一致） → 提 PR 改用例文档
   - **真实 UI/后端缺陷** → 提 issue + 不 xfail（保持作为回归看门狗）
5. **三分法拿不准**（截图模糊 / 现象偶发 / 不知道是 timing 还是真 bug）→
   用 playwright MCP（`browser_navigate` → `browser_snapshot` → `browser_take_screenshot` → `browser_console_messages`）
   现场复现（拿 console log + 全页截图 + DOM snapshot），再回头判三分。
   **不要凭印象猜根因 → 直接贴报告给用户**。

---

## 你必须知道的几个关键文件位置

| 文件 | 作用 | 何时读 |
|---|---|---|
| `pages/base_page.py` | Element-Plus 通用交互 + 反馈断言 + 资源追踪 | 写 PageObject 前必读 |
| `tests/_helpers.py` | `assert_save_blocked` / `assert_field_validation` | 写异常流必读 |
| `tests/conftest.py`（业务） | `register_cleanup` 注册资源清理 | 接入新资源类型时改 |
| `conftest.py`（根） | session 级 fixture / 失败钩子 / CSV 归类 | 一般不动；扩归类规则才改 |
| `tools/recon_dump.json` | 当前页面字段/按钮真值 | PageObject 字段名以这个为准 |
| `recon/menu_list.md` | **测试环境菜单 + 跨页 UI 元素权威文档（STEP 0 产出）** | **写测试用例 `.md` / 改 PageObject / 加导航宏 时强制对照** |
| `recon/menu_tree.json` `recon/pages_*.json` `recon/dialogs_*.json` | STEP 0 机器可读侦察产物 | menu_list.md 的原始数据；自动化脚本可直接 import |
| `STANDARDS.md` | 6 大规范全集（强制 + 推荐） | 与 reference 冲突时以 STANDARDS 为准 |

---

## 沟通节奏

- **用户没让你跑测试就不要跑**——只是建议命令（`pytest tests/test_arNN_xxx.py -v`），让用户自己跑。
- **不要重写已经存在的 PageObject 方法**——先 grep 确认 `pages/<biz>_page.py` 里有没有 `fill_<field>`，没有再加。
- **用户给的字段名跟 recon_dump 不一致时直接说**："文档说『项目名称』，但 recon_dump.json 里是『项目名』，按 dump 为准——确认吗？"
- **遇到 Element-Plus 现象拿不准时直接读陷阱速查**，不要凭"我记得 select 应该……"——这本就是源项目踩出来的反直觉清单。
