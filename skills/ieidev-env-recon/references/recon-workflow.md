# 4 阶段流程详解 — selector 策略 / 边缘情况 / 现场判断

> 当 SKILL.md §4 的简化叙述不够时来这里。本文档把每阶段的真实代码 / 选择器 / 现场常见坑写全。

---

## 阶段 1 — 登录并采左菜单全树

### 登录页 selector 兜底链

不同后台模板（RuoYi / vfadmin / 自研）登录页 selector 略有差异。按下面顺序兜底：

```python
SEL_USERNAME = 'input[placeholder*="账号"], input[placeholder*="用户"], input[name="username"]'
SEL_PASSWORD = 'input[type="password"], input[name="password"]'
SEL_CAPTCHA  = 'input[placeholder*="验证码"]'
SEL_LOGIN_BTN = 'button:has-text("登 录"), button:has-text("登录"), button[type="submit"]'
```

如果上面都点不上：
- 看页面是不是套了一层 iframe（少见但 RuoYi 旧版本有）
- 验证码是不是图片型（必须 OCR / 跳过验证码 / mock 后端 — 开发环境通常输任意值即过）

### 展开菜单的多 pass 策略

```python
for _ in range(4):
    page.evaluate("""
        () => document.querySelectorAll('.el-sub-menu:not(.is-opened) > .el-sub-menu__title')
                       .forEach(el => el.click())
    """)
    page.wait_for_timeout(500)
```

为什么要 4 轮：嵌套子菜单展开是异步的，第一轮展开一级、第二轮展开二级…。固定 4 轮足够覆盖绝大多数后台（很少有超过 3 级嵌套）。

### 树遍历选择器（含 RuoYi 兼容）

```js
const root = document.querySelector('.el-menu--vertical');
function walk(node) {
  const items = [];
  // 标准 Element-Plus：<li class="el-sub-menu"> 或 <li class="el-menu-item">
  // RuoYi 包装：<div><a><li class="el-menu-item">…
  const children = node.querySelectorAll(':scope > .el-sub-menu, :scope > .el-menu-item, :scope > div');
  // 递归处理…
}
```

**坑**：RuoYi-Vue3 把每个菜单项额外包了一层 `<div><a>`，标准 `:scope > .el-menu-item` 抓不到，要补 `:scope > div` 分支。Vue-Element-Admin 没这层包装。

**兜底**：始终 dump `sidebar.html`（sidebar outerHTML）—— 脚本采树失败时 Claude 可读 HTML 重新构建。

### 输出 schema（`menu_tree.json`）

```json
[
  {"type": "item", "title": "首页", "route": "/index"},
  {"type": "submenu", "title": "项目管理", "children": [
    {"type": "item", "title": "产品线管理", "route": "/pm/productline"},
    {"type": "item", "title": "项目列表",   "route": "/pm/project"},
    {"type": "item", "title": "版本列表",   "route": "/pm/version"},
    {"type": "item", "title": "关联变更日志", "route": "/pm/linkChangeLog"}
  ]},
  {"type": "submenu", "title": "系统管理", "children": [...]}
]
```

`title` 字段是后续 PageObject `MENU_NAMES` 字典的源头；保持中文原文，不要翻译。

---

## 阶段 2 — 每个目标页的 UI 元素探针

### 探针 JS

```js
() => {
  const q = (sel) => Array.from(document.querySelectorAll(sel))
                          .map(e => (e.innerText || e.getAttribute('placeholder') || '').trim())
                          .filter(Boolean);
  return {
    url:           location.href,
    title:         document.title,
    breadcrumb:    q('.el-breadcrumb__inner'),
    formLabels:    q('.el-form-item__label'),
    placeholders:  Array.from(document.querySelectorAll('input[placeholder], textarea[placeholder]'))
                      .map(e => e.getAttribute('placeholder')).filter(Boolean),
    buttons:       q('button'),
    tableHeaders:  q('.el-table th .cell'),
    tabs:          q('.el-tabs__item'),
    dialogTitles:  q('.el-dialog__title, .el-drawer__title'),
    h1h2:          q('h1, h2, h3, .el-page-header__content')
  };
}
```

### `wait_for_timeout(2500)` 是必须的

`networkidle` 表示网络空闲，但 Element-Plus 的 `el-table` 与异步搜索区初始化在 networkidle 之后还要一拍。**2.5 秒经验值**：覆盖 95% 场景；如果某页表格异常大可调到 5 秒。

### 工具栏按钮的"噪音过滤"

`buttons` 抓全部 `<button>`，会带上：
- 真实工具栏按钮（"新增" / "导出" / "刷新" / "重置"）
- 行内操作按钮（"编辑" / "删除"，每行一份，可能几十个）
- 弹出的 toast / 浮层按钮（残留）
- 分页器的"上一页" / "下一页" / "GO"

如果只关心工具栏，二次过滤：

```js
buttons: Array.from(document.querySelectorAll('.app-container .el-form-item button, .app-container .toolbar button'))
              .map(e => e.innerText.trim())
              .filter(Boolean)
```

或者保留全集，让人渲染 `menu_list.md` 时按 DOM 位置归类。**默认推荐保留全集**，少损失信息。

### `placeholders` 是 selector 黄金料

`page.locator('input[placeholder="请输入项目名称"]')` 比 `page.locator('.el-form-item:has-text("项目名称") input')` 稳得多。所有探针都要把 placeholder 完整 dump。

### `tableHeaders` 顺序敏感

```js
tableHeaders: q('.el-table th .cell')
```

**保持数组顺序**（不要 sort）—— 列顺序本身就是断言点。spec 写"列顺序是 A,B,C"，实测可能是 A,C,B —— 这是 spec 错。

---

## 阶段 3 — 每个 新增 / 编辑 弹窗探针

### 点击新增前等 2 秒

```python
page.goto(BASE_URL + route, wait_until="networkidle")
page.wait_for_timeout(2000)
page.click('button:has-text("新增"):not([disabled])', timeout=5000)
page.wait_for_timeout(1500)
```

`:not([disabled])` —— 有些页面新增按钮要先选行或满足条件才能点。先用这个过滤；如果还点不到要看看是不是要先选条件（少见，单独处理）。

### 弹窗探针 JS

```js
() => {
  const dlg = document.querySelector('.el-dialog:not([style*="display: none"]), .el-drawer__wrapper:not([style*="display: none"])');
  if (!dlg) return {error:'no open dialog detected'};
  const q = (sel) => Array.from(dlg.querySelectorAll(sel))
                          .map(e => (e.innerText || e.getAttribute('placeholder') || '').trim())
                          .filter(Boolean);
  return {
    title:          (dlg.querySelector('.el-dialog__title, .el-drawer__title') || {}).innerText || '',
    formLabels:     q('.el-form-item__label'),
    requiredFields: q('.is-required .el-form-item__label'),
    placeholders:   Array.from(dlg.querySelectorAll('input[placeholder], textarea[placeholder]'))
                      .map(e => e.getAttribute('placeholder')).filter(Boolean),
    buttons:        q('.el-dialog__footer button, .el-drawer__footer button')
  };
}
```

### 必填字段的判别

**只认 `.is-required` class**，不认其他启发式（红星 / 必填提示文案）。Element-Plus 的 `<el-form-item :rules="..." required>` 会自动加 `is-required` class 到 `.el-form-item`。

```js
requiredFields: q('.is-required .el-form-item__label')
```

> 反例：有些 spec 凭"红星 = 必填"判断，但有的开发会用 CSS 而非 `required` 属性渲染红星，导致 spec 漏列必填字段。以 `is-required` 为准。

### 按钮文案的空格陷阱

Element-Plus 默认按钮文案 `确 定` / `取 消`（中间一个空格），PageObject 用 `:has-text("确定")` 不一定能匹配（取决于 Playwright 版本对空格的处理）。

**推荐**：dump 时保留原文（含空格），PageObject 消费时用正则兼容：

```python
locator(':text-matches("确\\s*定")')
```

---

## 阶段 4 — 渲染 `menu_list.md`

完整骨架见 [menu-list-template.md](menu-list-template.md)。本节只讲渲染思路。

1. 从 `menu_tree.json` 渲染 §1 顶级菜单表 + §2 完整树（ASCII 美化）
2. 从 `pages_<name>.json` 渲染 §3 每页 UI 元素详表（按 SKILL.md 列出的 6 个子节）
3. §4 登录页关键元素 —— 从阶段 1 截图与 placeholder 抽
4. §5 通用 UI 约定 —— 项目模板里的固定项（菜单根 selector / 弹窗根 selector / 按钮空格约定）
5. **§6 差异表 = 最有价值的一节**：把 `recon` 实测和已有 spec 文档逐条对照，列出差异、影响的 TC 编号

### §6 差异表的填法

如果有 spec，对比下列 4 个维度：
- 菜单名（spec 写 vs 实测）
- 工具栏按钮（spec 写 vs 实测，含数量差异）
- 弹窗标题（spec 写 vs 实测）
- 必填字段（spec 列 vs 实测 `is-required`）

**没有 spec 也要填这一节**：留空时显式写"无可对照 spec — 本次为环境初采"，让评审知道这是基线而非"无差异确认"。

---

## 一键脚本兜底

如果交互式 playwright MCP 操控不顺（网络问题 / 显示问题 / 想纳入 CI），用 `assets/recon_env_bootstrap.py`：

```bash
# 1. 编辑配置区
$ vim assets/recon_env_bootstrap.py  # 改 BASE_URL / USER / PWD / TARGET_PAGES

# 2. 一键跑
$ python3 assets/recon_env_bootstrap.py

# 3. 产物自动落到 ./recon/
$ ls recon/
menu_list.md  menu_tree.json  pages_*.json  dialogs_*.json  screenshots/  sidebar.html
```

脚本约束：
- 必须 headless（CI 与本地一致；可观察行为通过截图回放）
- 不依赖任何项目模板文件（独立可跑）
- 字段名 / 按钮名 / 表头一切以本脚本输出为权威，不以 spec 为权威
