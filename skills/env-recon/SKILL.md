---
name: env-recon
description: |
  登录测试环境 → 实测抓取左菜单全树 / Tab / 按钮 / 字段 / 弹窗 → 持久化为 `recon/menu_list.md` + 4 类 JSON + 截图，作为后续测试用例 .md 与 PageObject 的 UI 文案权威源。可选地对已有测试用例 .md 反向 diff，propose 步骤修正补丁（菜单名 / 按钮文案 / 弹窗标题 / 必填字段对齐）。从 `ieidev-team:ui-autotest` 的 STEP 0 抽离独立，让"实测前置"在不写 Playwright 脚本的场景也可独立调用。

  **用户提到下列任何关键词，都应主动加载本 skill**：登录测试环境采菜单 / 抓菜单 / 抓页面 / probe / probe DOM / recon 一下 / env recon / 实测前置 / 实测对齐 spec / spec 与 UI 对不上 / 测试用例步骤与 UI 对不上 / 用例里写的按钮名不对 / 菜单名变了 / 现在的 UI 是什么样 / 写脚本之前先采一遍 / 把 menu_list.md 重新生成 / probe_dom / menu_list 过期了 / 让用例步骤与 UI 对齐 / 让 spec 与 UI 对齐 / 帮我看一下测试环境长什么样 / 弹窗标题对不上 / 必填字段对不上。

  **与 `ieidev-team:ui-autotest` 的边界**：本 skill 只管"侦察 + 产物 + diff patch 建议"；不写 Playwright 用例、不跑 pytest、不做缺陷三分。下游 `ieidev-team:ui-autotest` / `testcases-to-playwright-pipeline` 把本 skill 的 `recon/menu_list.md` 当 STEP 0 已完成的前置消费。**如果用户既要采菜单又要立即写脚本跑 → 先本 skill 再 `ieidev-team:ui-autotest`**，两者顺序串联。
---

# ieidev-env-recon — 测试环境实测侦察 + 用例步骤回写

把测试环境当"UI 文案权威源"采一遍：登录 → 全菜单树 → 目标页面元素 dump → 新增/编辑弹窗 dump → 渲染 `recon/menu_list.md`。可选地把同目录下的测试用例 .md 拿来 diff，把"用例里按 spec 写的菜单/按钮文案"和"实测 UI 文案"对一对，propose 一份补丁（用户决定接不接）。

---

## 第零原则 —— UI 是权威，spec/文档不是

下游项目踩过的所有最贵的坑都源于一个误解："spec 写'新增项目'按钮，那 UI 肯定就叫'新增项目'"。**实际上**：

- spec 说"新增项目"，UI 实际只叫"新增"
- spec 说弹窗"新增产品线"，UI 实际叫"添加产品线"
- spec 说工具栏有"展开全部 / 折叠全部"两个按钮，UI 实际是一个 toggle
- spec 漏列"显示顺序"是必填，UI 实际带 `is-required` class

**凭文档写出来的 selector / 用例步骤第一跑就挂，平均浪费 30-90 分钟换 selector**。本 skill 存在的意义就是花 5 分钟把这些差异提前捞出来。

> **原则**：任何 spec 与 `menu_list.md` 冲突时，以 `menu_list.md` 为准；并在测试用例 .md 头部声明这一点，让评审无歧义。

---

## 何时执行本 skill

| 场景 | 是否必做 |
|---|---|
| 第一次接入某测试环境（无 `recon/menu_list.md`） | ✅ 必做 |
| 测试用例文档刚移交、还没对照过 UI | ✅ 必做 |
| `recon/menu_list.md` 采集时间早于本次需求开始时间 | ✅ 必做 |
| UI 一段时间未跑、菜单可能变了（>1 周）| ✅ 必做 |
| 用户说"用例步骤里那些菜单/按钮文案对不对得上 UI" | ✅ 必做（带 `--cases` 进入回写模式）|
| 同一环境同一 sprint 内已采集过且 UI 未改 | ❌ 跳过，沿用 |

---

## 输入与输出

### 输入

最低限度需要：

- **测试环境地址**：`BASE_URL`（如 `http://192.168.x.x:8080/`）
- **凭据**：`USER` / `PWD`（默认 `admin` / `admin123`）
- **目标页面列表**：希望覆盖的路由 + 是否要探弹窗

可选：

- **`--cases <path>`**：已有的测试用例 .md（或目录），开启"回写模式"——recon 完成后对 cases diff，propose 步骤修正补丁

### 输出

写到测试项目根目录下的 `recon/`（如不存在则建）：

```
recon/
├── menu_list.md           # 人类可读：菜单树 + 每页 UI 元素清单 + 与 spec 差异表（必产出，权威源）
├── menu_tree.json         # 机器可读：左侧菜单全树（路由 + 文案）
├── sidebar.html           # 兜底：sidebar outerHTML（采树脚本失败时给 Claude 解析）
├── pages_<page>.json      # 每页 form labels / buttons / table headers / placeholders / tabs
├── dialogs_<page>.json    # 每页 新增/编辑 弹窗 标题 / 必填字段 / 按钮
└── screenshots/
    ├── 01_login.png
    ├── 02_landing.png
    ├── 03_menu_expanded.png
    ├── pm_<page>.png      # 每页 full_page 截图
    └── dlg_<page>.png     # 每个弹窗 full_page 截图
```

回写模式额外输出（仅当 `--cases <path>` 传入）：

```
recon/
├── case_diff.md           # 人类可读差异报告：每个不一致点 → 影响哪些 TC-NNN
└── patches/
    └── <case-filename>.patch.md  # 每个 case .md 的建议补丁（diff 风格，不直接改源文件）
```

`menu_list.md` 是后续写测试用例 / PageObject 的**权威文案源**；任何与之冲突的 spec 或文档都以 `menu_list.md` 为准。

---

## 4 阶段标准流程（playwright MCP 执行）

> **第一动作**：用 **playwright MCP** 的 `browser_*` 工具操控浏览器（`browser_navigate` 访问 → `browser_snapshot` 取可访问性树 / DOM 真值 → `browser_take_screenshot` 截图取证 → `browser_click` / `browser_type` 交互）。
> 或者直接用本 skill 的 `assets/recon_env_bootstrap.py` 一键脚本（独立 Python + Playwright，不依赖任何浏览器 skill）。
>
> **两条路径选哪条**：
> - 用户在交互式 session 里、想边看边调 → playwright MCP（`browser_*` 工具临场操控）
> - 用户要把这一步纳入 CI / 一键复跑 / 不在 session 里手把手看 → 用 `assets/recon_env_bootstrap.py`

### 阶段 1 — 登录并采左菜单全树

- 访问 `BASE_URL`，输入账号 / 密码 / 验证码（开发环境通常任意 4 位通过；首选填 `1234`）
- 点击"登 录"按钮（注意中文按钮可能带空格 → selector 用 `:text-matches("登\\s*录")` 或 `:has-text("登录"), :has-text("登 录")` 双兜底）
- 等待 `/index` 或业务首页 `networkidle`
- 用 JS 注入逐层点击 `.el-sub-menu__title` 展开菜单（多 pass，处理嵌套；至少 4 轮，每轮间 500ms）
- 用 JS 遍历 `.el-menu` 写出 `{type, title, route, children}` 树 → `menu_tree.json`
- 兜底：把 sidebar `outerHTML` dump 到 `sidebar.html`（Claude 可在脚本采树失败时回退用 HTML 解析）
- 全页截图 `03_menu_expanded.png`

完整选择器策略与边缘情况见 [references/recon-workflow.md](references/recon-workflow.md)。

### 阶段 2 — 每个目标页的 UI 元素探针

对每个目标路由 `(name, route)`：

```python
page.goto(BASE_URL + route, wait_until="networkidle")
page.wait_for_timeout(2500)  # 给 el-table / 异步搜索区一点时间
info = {
  "url":           location.href,
  "breadcrumb":    Array.from('.el-breadcrumb__inner'),
  "formLabels":    Array.from('.el-form-item__label'),     # 搜索区/表单字段名
  "placeholders":  Array.from('input[placeholder], textarea[placeholder]').map(getAttribute('placeholder')),
  "buttons":       Array.from('button'),                    # 工具栏按钮全集
  "tableHeaders":  Array.from('.el-table th .cell'),
  "tabs":          Array.from('.el-tabs__item'),
  "dialogTitles":  Array.from('.el-dialog__title, .el-drawer__title'),
}
```

输出 `pages_<page>.json` + 全页截图 `pm_<page>.png`。

> **关键判别**：
> - 工具栏按钮文案优先从 `buttons` 数组提取；如果 toast / 浮动按钮污染列表，按 DOM 位置过滤（在 `.app-container` 内、不在 `.el-message` 内）
> - 表格列名以 `tableHeaders` 顺序为准——很多 spec 写错列顺序或漏列
> - `placeholders` 用来锁定 input/select 的精确选择器：`page.locator('input[placeholder="请输入项目名称"]')`

### 阶段 3 — 每个 新增 / 编辑 弹窗探针

只对**写操作页面**（不含纯查询页）执行：

```python
page.goto(BASE_URL + route, wait_until="networkidle")
page.click('button:has-text("新增"):not([disabled])')
page.wait_for_timeout(1500)
dlg_info = {
  "title":          '.el-dialog__title' 实际文本,                    # 真实标题
  "formLabels":     '.el-dialog .el-form-item__label' 全部,         # 全部字段名
  "requiredFields": '.el-dialog .is-required .el-form-item__label', # 必填字段（认 class）
  "placeholders":   '.el-dialog input[placeholder]' 的 placeholder,
  "buttons":        '.el-dialog__footer button',                   # 确定/取消/保存
}
```

输出 `dialogs_<page>.json` + 截图 `dlg_<page>.png`。

> **关键判别**：
> - 弹窗标题常与 spec 文档差异最大（"添加" vs "新增"、"修改" vs "编辑"）——不要假设"按钮叫新增 → 弹窗叫新增 XXX"
> - 必填字段以 `is-required` class 为准，spec 漏列必填的情况很常见
> - 按钮文案带空格：`确 定` / `取 消` / `保 存`，PageObject 定位用 `:text-matches("确\\s*定")` 兼容

### 阶段 4 — 渲染 `menu_list.md`（人类可读权威文档）

读完 4 类 JSON 后按 [references/menu-list-template.md](references/menu-list-template.md) 的骨架渲染。

最重要的是 §6 差异表 —— "既有 spec / 文档 vs 实际 UI"的逐条对照，列影响范围（哪些 TC 受影响）。这一节是 STEP 0 → 后续工序的桥梁。

---

## 5 — 回写模式（仅当 `--cases <path>` 传入）

用户传入 `--cases <path-to-测试用例.md>`（或目录）时，在阶段 4 后追加一段：

1. 读 cases.md，解析其中所有 `点击【XXX】` / `点击"XXX"按钮` / `填写"XXX"字段` / `弹窗"XXX"` 这类 UI 锚点
2. 与 `recon/menu_list.md` 的 §1-§3（菜单 / 按钮 / 字段 / 弹窗）逐条比对
3. 在 `recon/case_diff.md` 写出差异表
4. 在 `recon/patches/<case-filename>.patch.md` 生成 markdown-friendly diff 风格的补丁建议（**不直接改源文件**，让用户决定是否接受）

完整 diff 算法、补丁格式、误报防止见 [references/case-diff-patch.md](references/case-diff-patch.md)。

> **重要**：回写模式只 propose 补丁，**不直接编辑用户的测试用例 .md**。补丁风险面：
> - "用例写的'新增项目'按钮"可能是 spec 对的、UI 错的（产品 bug），盲改用例会掩盖 bug
> - 同名菜单不同路由（如 `项目管理 > 产品线管理` vs `数据管理 > 产品线管理`）需要人识别
>
> 所以本 skill **永远只输出 patch 文件**，由用户人工评审后再 apply（推荐用 `patch -p0 < recon/patches/xxx.patch.md` 或手动 copy）。

---

## STEP 0 完成 → 立刻做的事

1. 把 `recon/menu_list.md` 路径写进当前测试用例 `.md` 的文档头部，作为「UI 元素权威源」声明
2. 比对 spec 与 `menu_list.md §6` 差异表，挑出影响 TC-NNN 的项，**立刻**编辑测试用例文档把按钮 / 弹窗 / 列名改对（或接受本 skill 在回写模式输出的 patch）
3. 在测试用例顶部插入「测试环境与导航约定」节（环境表 + 菜单导航表 + 弹窗标题 + 按钮空格约定）—— 后续 PageObject 和 pytest 用例直接消费这些宏，避免每条用例都重复登录/导航文案
4. 如果项目已接入 `ieidev-team:ui-autotest` 的 playwrightmode 模板，**同步 `pages/base_page.py` 的 `MENU_NAMES` 字典**与 `menu_list.md §2` 共生（路由 → 中文名映射）
5. 后续如果要写 Playwright 脚本 → 切换到 `ieidev-team:ui-autotest` 走 STEP 1 ~ STEP 10

---

## 与 `ieidev-team:ui-autotest` 的边界（再次明确）

| 维度 | ieidev-env-recon（本 skill） | ieidev-team:ui-autotest |
|---|---|---|
| 主要产物 | `recon/menu_list.md` + 4 类 JSON + 截图 + 可选 patch | pytest 测试集 + Playwright 脚本 + `defects_<ts>.csv` |
| 关注点 | UI 文案权威源 + 用例步骤对齐 | 脚本生成 + 跑 + 缺陷三分类 |
| 是否动 UI | 只读侦察 | 只读侦察 + 写操作（新增/编辑/删除测试数据）|
| 何时调 | 写脚本之前 / 用例评审之前 / 新环境接入 | 用例已对齐 UI、要开始写脚本 |
| 谁是上游谁是下游 | 上游：产物给下游消费 | 下游：消费 `recon/menu_list.md` |
| 是否回写用例 .md | ✅ 在回写模式 propose patch（不直接改）| ❌ 不动用例 .md |

**单调用 vs 串联调用**：
- 用户只想看一眼测试环境 / 对齐 spec → 单独 `ieidev-env-recon`
- 用户要"采完菜单立即写脚本跑全量" → 先 `ieidev-env-recon`（采菜单 + 对齐用例）→ 再 `ieidev-team:ui-autotest`（写脚本 + 跑 + 三分）
- 用户已在 `ieidev-team:ui-autotest` skill 里、第一动作发现 `recon/menu_list.md` 不存在或过期 → 反向调用本 skill 完成 STEP 0 再继续

---

## 反例（不要这样做）

❌ "spec 说有'新增项目'按钮 → PageObject 直接 `button:has-text('新增项目')`" → 实际只叫"新增"，第一跑就 timeout
❌ "上个 sprint 跑过 recon 了，菜单应该没变" → UI 加了一个 `AI 管理` 一级菜单导致 `项目管理` 在 sidebar 的 nth-child 索引偏移
❌ "弹窗肯定叫'新增产品线'" → 实际是"添加产品线"，`wait_for_selector('.el-dialog__title:has-text("新增产品线")')` 永远超时但截图能看到弹窗已弹 → 误判成"弹窗没弹"
❌ "回写模式 propose 的 patch 直接 apply" → 没人工评审，可能把"UI 错的、spec 对的"产品 bug 掩盖掉
❌ "在 `ieidev-team:ui-autotest` 的 STEP 0 已经手写过 recon 脚本，本 skill 重复造轮子" → 不重复，本 skill 把 recon 抽离为独立可单调能力，且新增了回写补丁能力；下游 `ieidev-team:ui-autotest` 直接消费同一份产物

✅ 任何"我以为"都先跑本 skill 复检 —— 凭印象写的 selector / 字段判断在源项目都翻过车。

---

## 自检清单（结束前过一遍）

**产物完整性**

- [ ] `recon/menu_list.md` 存在且包含 §1-§6 六节（菜单 / 树 / 各页元素 / 登录页 / 通用约定 / 差异表）
- [ ] `recon/menu_tree.json` 存在且非空（不是 `{"error": ...}`）
- [ ] 每个 `TARGET_PAGES` 中的页面都有对应的 `pages_<name>.json` + `pm_<name>.png`
- [ ] 写操作页面都有 `dialogs_<name>.json` + `dlg_<name>.png`
- [ ] `screenshots/` 至少含 `01_login.png` / `02_landing.png` / `03_menu_expanded.png`

**权威性声明**

- [ ] `menu_list.md` 头部写明 "本文件为 UI 文案权威源，冲突时以本文件为准"
- [ ] `menu_list.md §6` 差异表非空（如果环境与 spec 完全一致才允许为空，且需在差异表底部显式写"无差异 — 实测对齐"）

**回写模式（仅当 `--cases <path>` 传入）**

- [ ] `recon/case_diff.md` 存在
- [ ] `recon/patches/*.patch.md` 每条变更注明影响的 TC-NNN
- [ ] 没有直接编辑用户的测试用例 .md 源文件

**与下游契约**

- [ ] 输出的 4 类 JSON 字段名 (`menu_tree.json` / `pages_*.json` / `dialogs_*.json`) 与 `ieidev-team:ui-autotest` 历史约定一致 — 不要为了改名而改名（下游可能已经 grep 这些字段）
- [ ] `menu_list.md §2` 树结构可被代码化（路由 → 中文名映射可机械抽取，供 `MENU_NAMES` 字典消费）

---

## 一键脚本兜底

如果 playwright MCP 不可用、或用户希望非交互式一键跑：

1. 复制 `assets/recon_env_bootstrap.py` 到测试项目根目录
2. 修改顶部"配置区"：`BASE_URL` / `USER` / `PWD` / `TARGET_PAGES`
3. `python3 recon_env_bootstrap.py`
4. 产物直接落到 `./recon/`

脚本是独立可跑的，**不依赖任何项目模板文件**，只需要 `pip install playwright && playwright install chromium`。
