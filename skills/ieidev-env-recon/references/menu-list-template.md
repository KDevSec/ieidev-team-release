# `menu_list.md` 输出骨架

> 本文件是阶段 4 的渲染模板。读完 4 类 JSON 后按本骨架填充。占位符 `<...>` 都要替换；不能替换的（如 spec 缺失）要显式写"N/A — 原因"，**不要留空**。

---

## 完整骨架

```markdown
# <系统名> 测试环境 菜单与 UI 元素清单

> **采集时间**：YYYY-MM-DD HH:MM
> **采集方式**：Playwright + headless Chromium，登录 <USER>，遍历 <N> 个目标页面
> **环境地址**：<BASE_URL>
> **用途**：作为 `<测试用例>.md` 的 UI 选择器与文案权威源；冲突时以本文件为准
> **生成 skill**：`ieidev-env-recon`（如本次跑过回写模式额外说明 `--cases <path>`）

---

## 1. 顶级菜单（左侧 sidebar，<role> 视角）

| # | 一级菜单 | 路由前缀 | 子菜单数 | 备注 |
|---|---|---|---|---|
| 1 | 项目管理 | /pm | 4 | 本次重点采集 |
| 2 | 系统管理 | /system | 9 | 字典 / 用户 / 角色 / 菜单 / 部门 / 岗位 / 参数 / 通知 / 日志 |
| 3 | 系统监控 | /monitor | 4 | 在线用户 / 定时任务 / 数据监控 / 服务监控 |
| 4 | ... |

---

## 2. 完整菜单树

```text
├─ 首页 (/index)
├─ 项目管理
│  ├─ 产品线管理 (/pm/productline)
│  ├─ 项目列表 (/pm/project)
│  ├─ 版本列表 (/pm/version)
│  └─ 关联变更日志 (/pm/linkChangeLog)
├─ 系统管理
│  ├─ 用户管理 (/system/user)
│  ├─ 角色管理 (/system/role)
│  ├─ 菜单管理 (/system/menu)
│  └─ ...
└─ ...
```

> 该树是 `pages/base_page.py` 中 `MENU_NAMES` 字典的源头；新增页面 / 路由时务必同步两侧。

---

## 3. <业务模块> 各页 UI 元素详表（实测）

### 3.1 产品线管理 `/pm/productline`

- **页面面包屑**：`项目管理` / `产品线管理`
- **顶部 Tab**：（无）
- **搜索区表单字段**：
  | 字段名 | placeholder | 控件类型 | selector 建议 |
  |---|---|---|---|
  | 产品线名称 | 请输入产品线名称 | input | `input[placeholder="请输入产品线名称"]` |
  | 上级产品线 | 请选择上级产品线 | el-cascader | `.el-cascader:has-text("上级产品线")` |
- **搜索区按钮**：`查询`、`重置`
- **工具栏按钮**：`新增`、`展开/折叠`（注：spec 写"展开全部 / 折叠全部"，实测是 1 个 toggle）
- **表格列（实际顺序）**：
  1. 编号 (id)
  2. 产品线名称
  3. 描述
  4. 挂载项目数 (tag 颜色：0=info 灰 / >0=warning 橙)
  5. 子产品线 (tag 计数同上)
  6. 创建人
  7. 创建时间
  8. 操作（新增子级 / 编辑 / 删除）
- **新增对话框**：
  - 标题：`新增产品线`
  - 字段（必填星标）：
    - ✅ 产品线名称（is-required）
    - 上级产品线（cascader, checkStrictly）
    - 描述（textarea, rows=3）
  - 底部按钮：`确 定`（注意空格）、`取 消`
  - placeholder：`请输入产品线名称`、`请输入描述`

### 3.2 项目列表 `/pm/project`

（按相同模板填）

### 3.3 版本列表 `/pm/version`

（按相同模板填；含 Tab）

- **顶部 Tab**（filter-tabs）：`全部版本`、`未关联版本`、`测评已完成`
- ...

### 3.4 关联变更日志 `/pm/linkChangeLog`

（按相同模板填）

---

## 4. 登录页关键元素

| 元素 | selector | 备注 |
|---|---|---|
| 账号输入框 | `input[placeholder="请输入账号"]` 或 `input[name="username"]` | placeholder 优先 |
| 密码输入框 | `input[type="password"]` | |
| 验证码 | `input[placeholder="请输入验证码"]` | 4 位，开发环境通常任意值 |
| 登录按钮 | `:text-matches("登\\s*录")` | 中文按钮可能带空格 |

---

## 5. 通用 UI 约定

| 元素 | 选择器建议 | 备注 |
|---|---|---|
| 左菜单根 | `.el-menu--vertical` | |
| 弹窗根 | `.el-dialog:not([style*="display: none"])` | 排除隐藏 |
| 弹窗标题 | `.el-dialog__title` | |
| 弹窗必填字段 | `.el-dialog .is-required .el-form-item__label` | 只认 `is-required` class |
| 弹窗底部按钮 | `.el-dialog__footer button` | |
| 按钮文案空格 | 用 `:text-matches("确\\s*定")` 兼容 `确定` / `确 定` | |
| toast 提示 | `.el-message` | |
| 二次确认 | `.el-message-box` | |
| 表格列名 | `.el-table th .cell` | 保持数组顺序 |

---

## 6. 已知与既有 Spec / 文档差异（最重要的一节 — STEP 0 → 用例修正的桥梁）

| # | 维度 | 既有 spec / 文档描述 | 实际 UI | 影响范围（哪些 TC） | 建议处理 |
|---|---|---|---|---|---|
| 1 | 工具栏按钮 | "展开全部 / 折叠全部" 2 个按钮 | "展开/折叠" 1 个 toggle 按钮 | TC-AR04001005-005 | 改用例步骤为"点击'展开/折叠'切换全部展开" |
| 2 | 弹窗标题 | 新增产品线 | 新增产品线 | （一致）| 无需改 |
| 3 | 必填字段 | spec 列：产品线名称 | 实测 is-required：产品线名称 | （一致）| 无需改 |
| 4 | 菜单文案 | "项目管理" | "项目管理" | （一致）| 无需改 |

> 如本次实测与 spec 完全一致 → 表格写一行"全维度一致，无需修正"+ 日期，让评审知道这是"已确认"而非"未对照"。
>
> 如本次为初采无 spec 对照 → 表格写"N/A — 无可对照 spec，本次为环境初采"。

---

## 7. （可选）回写模式产物

如本次跑了 `--cases <path>`：

- 详细 diff 报告：`recon/case_diff.md`
- 每个 case 的补丁建议：`recon/patches/<case-filename>.patch.md`

补丁规则与误报防止见 [case-diff-patch.md](case-diff-patch.md)。
```

---

## 渲染指南

### §1 — 顶级菜单表

从 `menu_tree.json` 顶层数组渲染：
- 一级菜单 = 顶层 `type=submenu` 的 `title`
- 路由前缀 = 子节点路由的共同前缀
- 子菜单数 = `children.length`

### §2 — 完整菜单树

用 box-drawing 字符（`├─` / `└─` / `│`）渲染。Python 一键脚本可以这样写：

```python
def render_tree(items, indent=""):
    lines = []
    for i, it in enumerate(items):
        last = (i == len(items) - 1)
        connector = "└─" if last else "├─"
        if it["type"] == "item":
            lines.append(f"{indent}{connector} {it['title']} ({it.get('route','')})")
        else:
            lines.append(f"{indent}{connector} {it['title']}")
            sub_indent = indent + ("   " if last else "│  ")
            lines.extend(render_tree(it.get("children", []), sub_indent))
    return lines
```

### §3 — 每页详表

每个 `TARGET_PAGES` 项渲染一个 `### 3.N <name> <route>` 子节，填以下字段（按 `pages_<name>.json` 抽）：
- 面包屑：`breadcrumb` 数组拼接 `/`
- 顶部 Tab：`tabs` 数组（空则写"（无）"）
- 搜索区表单字段：`formLabels` × `placeholders` 配对（按 DOM 顺序匹配）
- 工具栏按钮：从 `buttons` 数组挑选不重复、不属于行内的（人工剔除 / 启发式剔除）
- 表格列：`tableHeaders` 数组保持顺序
- 新增/编辑对话框：从 `dialogs_<name>.json` 抽 title / formLabels / requiredFields / buttons

### §6 — 差异表

这一节**人工渲染**，由 Claude 读完 spec + 实测后逐项比对。模板里给的示例都是占位，真实数据来自项目。

实现差异检测的算法：
- 名称 fuzzy match（编辑距离 ≤2 视为"相似但不等"，要列入差异表）
- 数量比对（按钮数 / 必填字段数 / 列数 spec 写 N，实测 M ≠ N 时列入）
- 文案完全相等 → 一致；不等 → 不一致
