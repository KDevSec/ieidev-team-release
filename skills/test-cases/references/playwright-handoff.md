# Playwright Handoff Conventions

The fielded test cases this skill emits are consumed by downstream Playwright generators (e.g. `ieidev-team:ui-autotest`, `testcases-to-playwright-pipeline`). They parse the `测试步骤` / `前置条件` / `测试数据` fields to produce Page Object actions, locator selectors, and parametrized test data. To make that parse reliable, the steps must follow a small vocabulary.

This file is the **only** source of generative content this skill is allowed to use. Everything else (用例编号, 用例名称, pass-through fields, 预期结果) is verbatim from the upstream 测试点 .md.

## Vocabulary

### Menu items: `【...】`

Wrap any sidebar-menu / top-nav menu item in Chinese fullwidth square brackets:

| Source (测试点 标题 fragment) | Step rendering |
|---|---|
| "项目管理-产品线管理-新增" | `点击【项目管理】→【产品线管理】，进入产品线列表页` |
| "系统管理 - 用户管理" | `点击【系统管理】→【用户管理】` |

The downstream generator maps `【X】` → a click on the menu item with text X.

### Button labels: `"..."` (Chinese double quotes)

Wrap button labels in Chinese fullwidth double quotes:

| Source | Step rendering |
|---|---|
| "新增" 按钮 | `点击"新增"按钮` |
| "确认" / "取消" 对话框 | `点击"确认"按钮` |

Maps to `page.get_by_role("button", name="X").click()` or the project's equivalent helper.

### Field labels: bare in Chinese double quotes + 填写/选择

```
填写"名称"字段为 "测试产品线A"
选择"状态"字段为 "进行中"
勾选"是否启用"复选框
```

Maps to `fill` / `select_option` / `check`.

### Account credentials

Default: `admin` / `admin123`. Only deviate when the 测试点 标题 explicitly names another account (e.g. "项目经理 PM-01 登录，...").

Standard login step:

```
1. 使用 admin / admin123 登录系统
```

When the upstream tooling has a shared login fixture (auth_state), the renderer can collapse this to:

```
1. 使用 admin 账号已登录（共享 auth_state）
```

— but only when the upstream example demonstrates this shorthand. When in doubt, write out the full step.

### Form submission

```
N. 点击"保存"按钮，等待提交完成
```

Maps to `click + wait_for_response`. If the source 预期结果 specifies a toast / dialog / list refresh, the wait target is implicit and need not be written into the step — the assertion belongs to 预期结果.

## What NOT to do

- **Do not** invent preconditions the source row didn't promise. If the 测试点 标题 says "新增顶级产品线（接口主路径）", do not add "先确保 admin 已登录二次确认 + 关闭浏览器全部缓存" — the source doesn't require it.
- **Do not** add cleanup / teardown steps inside 测试步骤. Cleanup belongs to the Page Object fixture layer, not the test case definition.
- **Do not** translate menu/button labels into English. The downstream selector matching is byte-exact against the UI's Chinese text.
- **Do not** use `应当 / should / expect / assert` keywords inside 测试步骤. Assertions belong in 预期结果, which is already verbatim from the source.
- **Do not** invent specific test data values when the source doesn't constrain them — pick the simplest plausible value and let downstream parametrization vary it if needed.

## Worked examples

**Source (测试点 .md row):**

```
| 1 | 超级管理员登录，项目管理-产品线管理，新增顶级产品线（接口主路径） | 1. 列表新增一行<br>2. 名称、描述与录入一致 | 基本流 | 是 | 是 | 是 | 1 |
```

**Output block:**

```
- 用例编号：TC-AR04001001-001
- 用例名称：超级管理员登录，项目管理-产品线管理，新增顶级产品线（接口主路径）
- 需求编号：AR-SATP-04.001.001
- 用例类型：基本流
- 优先级：1
- 是否准入：是
- UI 自动化：是
- API 自动化：是
- 前置条件：admin 账号可登录；产品线列表中不存在名称为 "测试产品线A" 的记录
- 测试数据：
  - 名称：测试产品线A
  - 描述：自动化用例的测试产品线
- 测试步骤：
  1. 使用 admin / admin123 登录系统
  2. 点击【项目管理】→【产品线管理】
  3. 点击"新增"按钮
  4. 填写"名称"字段为 "测试产品线A"
  5. 填写"描述"字段为 "自动化用例的测试产品线"
  6. 点击"保存"按钮
- 预期结果：
  1. 列表新增一行
  2. 名称、描述与录入一致
```

**Source (异常流 row):**

```
| 4 | 超级管理员登录，新增顶级产品线，名称为空 | 1. 校验提示：名称不能为空 | 异常流 | 是 | 是 | 否 | 2 |
```

**Output block:**

```
- 用例编号：TC-AR04001001-004
- 用例名称：超级管理员登录，新增顶级产品线，名称为空
- 需求编号：AR-SATP-04.001.001
- 用例类型：异常流
- 优先级：2
- 是否准入：是
- UI 自动化：是
- API 自动化：否
- 前置条件：admin 账号可登录
- 测试数据：
  - 名称：（留空）
- 测试步骤：
  1. 使用 admin / admin123 登录系统
  2. 点击【项目管理】→【产品线管理】
  3. 点击"新增"按钮
  4. 不填写"名称"字段
  5. 点击"保存"按钮
- 预期结果：
  1. 校验提示：名称不能为空
  2. 平台数据保持不变   ← 异常流补齐（源未声明时追加）
```

Note: "平台数据保持不变" appears here because (a) the row is 异常流, and (b) the source 预期结果 did not include this bullet. Had the source already included it, we would copy it verbatim — never duplicate.
