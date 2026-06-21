# STEP 0 — 环境 / 菜单 / 弹窗实测前置（写脚本之前必做）

> **背景**：源项目 KDevSec 的实战经验。下游项目（vfadmin / Gen9 / 可信评估）测试用例文档常滞后于真实 UI——按钮叫「新增项目」实际只叫「新增」、对话框叫「新增产品线」实际叫「添加产品线」、工具栏「展开全部 / 折叠全部」实际是单按钮 toggle。
> 凭文档写出的脚本第一跑就挂；先做 5 分钟实测前置，省 5 小时调试。
> **本文件 = STEP 0 的强制 SOP**。SKILL.md 的「标准 10 步开发流程」从 STEP 1 开始；STEP 0 在 STEP 1 之前先做一遍。

---

## 何时执行 STEP 0

| 场景 | 是否必做 |
|---|---|
| 第一次接入某测试环境（无 `recon/menu_list.md` 文件） | ✅ 必做 |
| 测试用例文档刚移交、还没对照过 UI | ✅ 必做 |
| UI 一段时间未跑、菜单可能变了（>1 周）| ✅ 必做 |
| 当前 `recon/menu_list.md` 采集时间早于本次需求开始时间 | ✅ 必做 |
| 同一环境同一 sprint 内已采集过且菜单未改 | ❌ 跳过，沿用 |

---

## 输出物（4 件，固定路径）

写到测试项目根目录下的 `recon/`（如不存在则建）：

```
recon/
├── menu_list.md          # 人类可读：菜单树 + 每页 UI 元素清单 + 与 spec 差异表（必产出）
├── menu_tree.json        # 机器可读：左侧菜单全树（路由 + 文案，PageObject 引用）
├── pages_<page>.json     # 每个目标页面的 form labels / buttons / table headers / placeholders
├── dialogs_<page>.json   # 每个目标页面 `新增` / `编辑` 弹窗的标题 / 必填字段 / 按钮
└── screenshots/
    ├── 01_login.png
    ├── 02_landing.png
    ├── 03_menu_expanded.png
    ├── pm_<page>.png        # 每页 full_page 截图
    └── dlg_<page>.png       # 每个新增弹窗 full_page 截图
```

`menu_list.md` 是后续写测试用例 / PageObject 的**权威文案源**——任何与之冲突的 spec 或文档都以 `menu_list.md` 为准（并在文档头部声明这一点）。

---

## 4 阶段操作流程（用 playwright MCP 执行）

> **第一动作**：用 playwright MCP 的 browser_* 工具操控浏览器（`browser_navigate` → `browser_snapshot` → `browser_take_screenshot`）。
> 然后用 `assets/recon_env_bootstrap.py`（已模板化）作起点，按业务环境改 `BASE_URL` / `USER` / `PWD` / `TARGET_ROUTES`。

### 阶段 1 — 登录并采左菜单全树

- 访问 `BASE_URL`，输入账号密码（验证码如有则填任意 4 位），点击 `登 录`（注意中文按钮可能带空格）
- 等待 `/index` 或业务首页 networkidle
- 用 JS 注入逐层点击 `.el-sub-menu__title` 展开菜单（多 pass，处理嵌套）
- 用 JS 遍历 `.el-menu` 写出 `{type, title, route, children}` 树 → `menu_tree.json`
- 全页截图 `03_menu_expanded.png`

> 选择器策略：左菜单根 `aside .el-menu--vertical`；子菜单 `:scope > .el-sub-menu, :scope > .el-menu-item`；子菜单容器 `:scope > .el-menu`。

### 阶段 2 — 每个目标页的 UI 元素探针

对 `TARGET_ROUTES` 中每个路由：

```python
page.goto(BASE_URL + route, wait_until="networkidle")
page.wait_for_timeout(2500)  # 给 el-table / 异步搜索区一点时间
info = {
  "url": page.url,
  "formLabels":   query('.el-form-item__label'),     # 搜索区/表单字段名
  "placeholders": query('input[placeholder], textarea[placeholder]'),
  "buttons":      query('button'),                    # 工具栏按钮全集
  "tableHeaders": query('.el-table th .cell'),
  "tabs":         query('.el-tabs__item'),
  "dialogTitles": query('.el-dialog__title, .el-drawer__title'),
}
```

输出 `pages_<page>.json` + 全页截图 `pm_<page>.png`。

> **关键判别**：
> - 工具栏按钮文案优先从 `buttons` 数组提取（剔除 toast 等非工具栏按钮可按 DOM 位置过滤）
> - 表格列名以 `tableHeaders` 顺序为准——很多 spec 写错列顺序或漏列
> - `placeholders` 用来锁定 input/select 的精确选择器（`page.locator('input[placeholder="请输入项目名称"]')`）

### 阶段 3 — 每个 `新增` / `编辑` 弹窗探针

只对**写操作页面**（不含纯查询页）执行：

```python
page.goto(BASE_URL + route, wait_until="networkidle")
page.click('button:has-text("新增"):not([disabled])')
page.wait_for_timeout(1500)
dlg_info = {
  "title":          q('.el-dialog__title'),                     # 真实标题
  "formLabels":     q('.el-dialog .el-form-item__label'),       # 全部字段名
  "requiredFields": q('.el-dialog .is-required .el-form-item__label'),  # 必填字段
  "placeholders":   q('.el-dialog input[placeholder], textarea[placeholder]'),
  "buttons":        q('.el-dialog__footer button'),             # 确定/取消/保存等
}
```

输出 `dialogs_<page>.json` + 全页截图 `dlg_<page>.png`。

> **关键判别**：
> - 弹窗标题常与 spec 文档差异最大（添加 vs 新增、修改 vs 编辑）——不要假设"按钮叫新增 → 弹窗叫新增 XXX"
> - 必填字段以 `is-required` class 为准，spec 漏列必填的情况很常见
> - 按钮文案带空格：`确 定` / `取 消` / `保 存` — **必须用 `:has-text("确 定")` 精确匹配（带空格写进字面量）**；曾经推荐的 `:text-matches("确\\s*定")` 实测 count=0（详见 element-plus-pitfalls.md §坑 10）。带空格的"宽容正则匹配"在 Playwright text engine 里**不工作**

### 阶段 4 — 生成 `menu_list.md`（人类可读权威文档）

按以下骨架写出（脚本里直接渲染，或 Claude 读完 4 类 JSON 后手写）：

```markdown
# <系统名> 测试环境 菜单与 UI 元素清单

> **采集时间**：YYYY-MM-DD
> **采集方式**：Playwright + headless Chromium，登录 <USER>/<PWD>，遍历 <N> 个目标页面
> **环境地址**：<BASE_URL>
> **用途**：作为 `<测试用例>.md` 的 UI 选择器与文案权威源；冲突时以本文件为准

## 1. 顶级菜单（左侧 sidebar，<role> 视角）
<表格：一级 / 路由 / 子菜单 / 备注>

## 2. 完整菜单树
```text
<树形 ASCII>
```

## 3. <业务模块> 各页 UI 元素详表（实测）
### 3.X <页面名> `<route>`
- **页面面包屑**：…
- **顶部 Tab**（如有）：…
- **搜索区表单字段**：…（label + placeholder + 控件类型）
- **搜索区按钮**：…
- **工具栏按钮**：…（注明与 spec 差异）
- **表格列（实际顺序）**：…
- **新增/编辑对话框**：标题 / 字段 / 必填 / 字段提示 / 底部按钮

## 4. 登录页关键元素
…

## 5. 通用 UI 约定
| 元素 | 选择器建议 | 备注 |

## 6. 已知与既有 Spec / 文档差异
| 既有描述 | 实际 UI | 影响范围（哪些 TC） |
```

§6 是 STEP 0 → STEP 1+ 的桥梁：所有"按 spec 写但 UI 不一样"的点都列在这，写测试用例 / PageObject 时逐条修正。

---

## 与 STEP 1 (`tools/recon_elements.py`) 的关系

| 维度 | STEP 0（本文件） | STEP 1（`tools/recon_elements.py`） |
|---|---|---|
| 范围 | **全菜单 + 多页面 + 弹窗** 一次性采集 | **单页面**深度元素 dump |
| 触发 | 接入新环境 / 长时间未跑 / 菜单可能变 | 写某个 PageObject 之前 |
| 输出 | `recon/menu_list.md` + 4 类 JSON | `tools/recon_dump.json`（单页） |
| 依赖 | playwright MCP（browser_* 工具）+ 本文件模板脚本 | 模板内置 `tools/recon_elements.py` |
| 谁是权威 | 全局菜单 / 跨页文案 | 单页字段 disabled / readonly / 选项 |

**STEP 0 跑一次（一个 sprint 内可复用）；STEP 1 每写一个新 PageObject 跑一次**。两者不重叠，前者负责"导航 + 文案"，后者负责"字段 + 状态"。

---

## STEP 0 完成 → 立刻做的事

1. 把 `recon/menu_list.md` 路径写进当前测试用例 `.md` 的文档头部，作为「UI 元素权威源」声明
2. 比对 spec 与 `menu_list.md` §6 差异表，挑出影响 TC-NNN 的项，**立刻**编辑测试用例文档把按钮 / 弹窗 / 列名改对
3. 在测试用例顶部插入「测试环境与导航约定」节（环境表 + 菜单导航表 + STEP_LOGIN/STEP_NAV_* 步骤宏 + 弹窗标题 + 按钮空格约定）—— 后续 PageObject 和 pytest 用例直接消费这些宏，避免每条用例都重复登录/导航文案
4. **同步 `pages/base_page.py` 的 `MENU_NAMES` 字典**（详见下节"共生契约"）
5. 进入 SKILL.md 的 STEP 1 ~ STEP 10 正常流程

> 步骤 3 的具体写法看 `assets/test_case_doc_header.md.tpl`（项目级测试用例 Markdown 头部模板）。

---

## `MENU_NAMES` 与 `menu_list.md §2` 共生契约（强制）

playwrightmode 模板的 `pages/base_page.py` 维护一张 `path → 菜单中文名` 映射，HEADED 模式步骤气泡和导航日志都依赖它：

```python
# pages/base_page.py
MENU_NAMES: dict[str, str] = {
    "/pm/productline":   "产品线管理",
    "/pm/project":       "项目列表",
    "/pm/version":       "版本列表",
    "/pm/linkChangeLog": "关联变更日志",
    "/index":            "首页",
}

def menu_name_for(path: str) -> str:
    if not path:
        return ""
    base = path.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return MENU_NAMES.get(base, MENU_NAMES.get(path, path))
```

`BasePage.goto(path)` 内的步骤气泡推送：

```python
self._step(f"➜ 导航 {menu_name_for(path)}")     # 用户看到 "➜ 导航 项目列表"
# 而非 "➜ 导航 /pm/project"（路径是给程序看的，不是给观察者看的）
```

### 共生约束

1. **`MENU_NAMES` 的源头 = `menu_list.md §2`**——后者是 STEP 0 实测产物，前者是它的代码化镜像。
2. **新增页面 / 路由时**，**必须同时**：
   - 在 `recon/menu_list.md §2` 菜单树里登记
   - 在 `pages/base_page.py` 的 `MENU_NAMES` 加一条 `"<path>": "<菜单中文名>"`
3. **未命中时回退**到原始 path 输出（不抛异常，但 review 时应该能看出"哪条 path 漏了登记"）
4. 只改 PageObject 不改这两处 → review 不通过

### 反例

❌ 加了新 PageObject 但没改 `MENU_NAMES` → 步骤气泡显示路径，肉眼对照 menu_list 时一头雾水
❌ 改了 `MENU_NAMES` 但没改 menu_list.md → 下次有人跑 STEP 0 重新生成 menu_list 会丢这条登记
❌ `MENU_NAMES` 用英文 / 拼音 → 与 UI 实际中文菜单不一致，气泡误导观察者

---

## 反例（不要这样做）

❌ "我看 spec 写的是『新增项目』按钮，直接 PageObject 写 `page.click('button:has-text("新增项目")')`" → 实际 UI 只是「新增」，第一跑就 timeout

❌ "上个 sprint 跑过 recon 了，菜单应该没变" → UI 加了一个 `AI 管理` 一级菜单导致 `项目管理` 在 sidebar 的 nth-child 索引偏移

❌ "对话框肯定是『新增产品线』" → 实际是「添加产品线」，导致 wait_for_selector('.el-dialog__title:has-text("新增产品线")') 永远超时，但截图能看到弹窗已弹出 → 误判成"弹窗没弹"，浪费 30 分钟换 selector

❌ "弹窗只有产品线名称必填" → 漏掉 `显示顺序` 也是必填，TC-PVM-010（必填校验用例）漏断言一条

✅ 任何"我以为"都先跑 STEP 0 复检——凭印象写的 selector / 字段判断在源项目都翻过车。
