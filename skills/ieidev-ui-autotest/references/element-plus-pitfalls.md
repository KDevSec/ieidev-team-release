# Element-Plus 6 大坑速查（必读）

> **关键原则**：每条都有源项目踩出来的真实症状。**正确做法已在 `pages/base_page.py` 封装好**——下游项目调它就行，不要绕过基类自己拼 locator。
>
> 若 BasePage 没有覆盖你遇到的现象，**先跑 `tools/probe_dom.py` 实证**，再决定是补到 BasePage 还是在 PageObject 内打补丁（优先前者）。

---

## 坑 1 — 下拉面板的"假可见"

**症状**：`page.locator(".el-select-dropdown__item:has-text('xxx')").click()` 没反应，或随机选错；headed 模式肉眼看下拉是关闭的。

**根因**：Element-Plus 下拉面板挂在 `body` 下，关闭时以 `display:none` 留存 DOM。Playwright 的 `:visible` / `is_visible` 判定与人眼不一致——会命中"上一次打开后被关闭、但还留在 DOM 中"的项。

**正确做法**：基类已用 `boundingClientRect + offsetParent` 双重判定真正可见。

✅ DO
```python
self.select_option_by_label("产品线", "操作系统")
self.select_first_option_by_label("产品线")  # 任意第一项
```

❌ DON'T
```python
self.page.locator(".el-select-dropdown__item:has-text('xxx')").click()
# ↑ 大概率命中隐藏项 → 点击无效或抛 Element is not visible
```

### 坑 1 变体 — 多选下拉的"items 假空"

**症状**：调用 `select_multi_options(label, count=4)` 类型方法，`items.count() > 0` 但循环点 `items.nth(i).click()` 全部抛 `Element is not visible` 或 `chosen` 没增加；用例报"下拉空 → SKIP"。

**根因**：页面同时存在多个多选下拉（例如 4 个安全角色）时，关闭的下拉以 `display:none` 留存 DOM。`items = locator(".el-select-dropdown__item")` 会数到**所有下拉**的所有项（含隐藏的），`items.nth(i)` 命中隐藏 item。

**血泪来源**：源项目第四轮发现 4 个安全角色下拉**实际各有 1 项**（"超级管理员"），旧实现误判为 0 项 → 4 条用例长期假 SKIP；修复后 SKIP→PASS。

**正确做法**：用 `boundingClientRect` + `offsetParent` 在 `page.evaluate` 内**先筛 visible idx 再点击**：

```python
visible_idxs = self.page.evaluate(
    """() => {
        const items = [...document.querySelectorAll('.el-select-dropdown__item')];
        const out = [];
        items.forEach((el, i) => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && el.offsetParent !== null) {
                out.push(i);
            }
        });
        return out;
    }"""
)
items = self.page.locator(".el-select-dropdown__item")
for idx in visible_idxs[:count]:
    items.nth(idx).click()
self.page.keyboard.press("Escape")  # 多选不会自动关 dropdown
```

**侦察工具**：怀疑下拉空时**先跑** `python tools/probe_select.py`——它用同一套 visible-idx 逻辑 dump 真实可见项，区分"脚本踩下拉假可见"还是"真实数据空"。

❌ DON'T
```python
items = self.page.locator(".el-select-dropdown__item")
for i in range(min(items.count(), count)):
    items.nth(i).click()  # 命中隐藏 item，chosen 不增加
```

---

## 坑 2 — el-select 的"穿透禁用"

**症状**：UI 上字段是灰的（不可点击），`is_field_readonly()` 返回 False。

**根因 1**：`el-select` 禁用时**外层 `.el-select` 不带 `is-disabled`**，只有内部 `input.el-select__input` 带 `disabled` 属性。

**根因 2**：`el-select` 内部 input 默认就是 `readonly`（搜索输入框），把 readonly 当 disabled 会把所有正常 select 都误判为只读。

**正确做法**：`BasePage.is_field_readonly` 已按以下顺序判定：
```
1. form-item.className 含 'is-disabled' → true
2. 内部 wrapper(.el-input/.el-select/.el-date-editor/.el-input-number) 含 'is-disabled' → true
3. 内部 input/textarea 的 disabled 属性 → true
4. 仅当 input 不在 .el-select 内时，才看 readOnly → true
```

✅ DO
```python
assert form.is_field_readonly("项目名称")
```

❌ DON'T
```python
assert "is-disabled" in self.page.locator(".el-select").first.get_attribute("class")
# ↑ 漏判 select；且会误判搜索框 readonly
```

**疑似误判的调试流程**：
1. 跑 `python tools/probe_dom.py`（修改顶部 LABELS 列表为目标字段）
2. 看 `tools/probe_dom.json` 里 `inputInfo[*].disabled` 与 `wrappers[*].className`
3. 仍判不出 → 在 `BasePage.is_field_readonly` 里**对症补条件**而非外加 hack

---

## 坑 3 — el-message 的 3 秒自消失

**症状**：保存接口返回 422，UI 红色 toast 一闪而过；脚本失败信息只有"保存未成功"，看不到后端真实错误。

**根因**：`el-message` 默认 3 秒自动消失。原写法 `form.save()` → `expect_message("成功", timeout=5000)` 累计等 5–10s，toast 早消失，再 `collect_toast_text` 也抓不到。

**正确做法**：基类的 `assert_save_success` / `save_and_wait_feedback` **点保存后立即** `wait_for(toast, timeout=4000ms)`，抢在自消失前读出。

| 场景 | 用法 |
|---|---|
| 期望成功 | `bp.assert_save_success("TC-XXX 创建项目")` |
| 不确定成功失败 | `ok, text = bp.save_and_wait_feedback()` |
| 期望被阻止 | `assert_save_blocked(page, "字段名", reason="...")` |
| 等待任意 toast | `bp.expect_message("成功")`（内置快路径） |

✅ DO
```python
form.save()
bp.assert_save_success("TC-014 创建项目")
# 失败信息：保存未成功（TC-014 创建项目）；页面反馈='系统接口422异常'
```

❌ DON'T
```python
form.save()
self.page.wait_for_load_state("networkidle", timeout=5000)  # 5s 后 toast 已消失
assert "成功" in bp.collect_toast_text()
```

---

## 坑 4 — 按钮文本互相包含

**症状**：调 `click_button("新增")` 跳到了"新增成员"行的逻辑。

**根因**：默认 `has-text` 模糊匹配 + `.first` 取首个 → 优先命中 DOM 里靠前的"新增成员"。

**正确做法**：`exact=True` 走 `span:text-is` 严格匹配。

```python
self.click_button("新增", exact=True)
# 等价：button.el-button:has(span:text-is("新增")), button:text-is("新增")
```

**业务接入时的判断标准**：按钮名容易冲突时（"新增" vs "新增成员"、"查看" vs "查看历史"、"编辑" vs "批量编辑"），**默认就加 `exact=True`**，不要等到出问题再改。

---

## 坑 5 — input-number 的 fill 绕过 spinner

**症状**：input-number 设了 `min=0`，但 `input.fill("-1")` 居然保存成功。

**根因**：`min` 仅约束 spinner 上下箭头点击，`fill` 直接写 `value`，spinner 不触发 `change` 校验；后端若也未校验就直接落库。

**模板的处理方式**：**不修脚本**（这是真实缺陷，CSV 自动归类为"input-number 的 min 仅约束 spinner"），但断言要带诊断信息：

```python
form.fill_input_by_label("新增漏洞数", "-1")
form.save()
val = page.locator('.el-form-item:has(.el-form-item__label:text-is("新增漏洞数")) input').input_value()
min_attr = page.locator('.el-form-item:has(.el-form-item__label:text-is("新增漏洞数")) input').get_attribute("min")
err = form.get_field_error("新增漏洞数")
assert err, (
    f"负数未被阻止保存：UI 没有表单校验，且保存跳回列表；"
    f"input 实际值={val!r}, min 属性={min_attr!r}"
)
```

CSV 自动归类规则：`input-number 的 min 属性仅约束 spinner，fill 与后端均未拦截负数`。

### 坑 5 配套 — 超长字段 / input-number 异常流必须先探针实测

**血泪来源**：源项目首轮把 6 条 maxlength 截断 + 1 条 input-number 规整误归"UI 漏校验"（C 类真实缺陷），第二轮跑探针后**全部重判为合法 UX**——不是漏校验，是脚本对 UX 行为预期错了。

**强制做法**：异常流"超长 / 越界 / 非法值"用例**写之前先用探针实测一次**，按下表判定，再决定用例怎么写：

#### 超长字段判定矩阵

| `actual_len`（fill 后） | `maxlength` 属性 | 结论 | 用例怎么写 |
|---|---|---|---|
| `== limit` | `= limit` | maxlength 自动截断（合法 UX）| 用 `assert_field_truncated_to(page, label, limit)` 验证截断 → `form.save()` → `assert_save_success` |
| `== limit+1` | （无） | input 接收全部字符 → 看保存后行为 | `form.save()` → `assert_save_blocked`（前端 blur 拦截 / 后端 422 / form 路径任一即阻止）|
| `== limit+1` | `= limit+1` | maxlength 设错（罕见缺陷）| 同上 + 在 issue 附 maxlength 不一致证据 |

#### input-number 判定矩阵

| `raw` 值 | blur 后 value | 结论 | 用例怎么写 |
|---|---|---|---|
| `-1` | `"0"`（被 `min=0` 规整）| 合法 UX 规整 | `assert_input_number_regulated(page, label, -1, 0)` → `form.save()` → `assert_save_success` |
| `-1` | `"-1"`（未规整）| 前端未拦截 | `form.save()` → `assert_save_blocked`，归类"input-number 负数绕过" |
| `"1.5"` | `"1.5"`（`step=1` 但未规整）| 漏校验 | 同上，归类"input-number 未限整数"|

**实测工具**：`tools/probe_overlong.py`——在脚本顶部 `OVERLONG_FIELDS` / `INPUT_NUMBER_FIELDS` 列表里配置 `{label, limit, type_hint}` / `{label, raw_input, expected_after_blur}`，跑一次直接告诉你哪一类。

**两条新 helper**（在 `tests/_helpers.py`）：

| 场景 | helper | 失败信息样例 |
|---|---|---|
| 期望前端 maxlength 截断 | `assert_field_truncated_to(page, label, max_len, type_hint='auto')` | `字段『xxx』未被截断到 1000：实际长度=1001 maxlength属性='1001' 标签='textarea'` |
| 期望 input-number blur 规整 | `assert_input_number_regulated(page, label, raw, expected)` | `字段『xxx』未被规整为 '0'：raw=-1 blur后val='-1' min属性='0' step='1'` |

详见 `STANDARDS.md §6.3`（playwrightmode 模板已固化为强制规范）。

---

## 坑 6 — 表单 Tab 切换的渲染竞态

**症状**：`form.tab_dev(); form.fill_svn(...)` 偶发 `Element is not visible`。

**根因**：`el-tabs` 切换通过 transition 动画 + 异步重渲染（200~400ms），切换后立刻操作可能撞上 DOM 还在重构。

**正确做法**：`BasePage.click_tab` 内已 `wait_for_timeout(400)`。仍 flaky 时切 Tab 后追加 `self.wait_idle(500)`：

```python
form.tab_dev()
form.wait_idle(500)
form.fill_svn("svn://...")
```

---

## 坑 7 — el-table 树表「DOM 不卸载只切 display:none」

**症状**：肉眼看见折叠/筛选生效但脚本断言失败；或同一断言"恒真"——加上展开/折叠/重置都过。

**根因**：`el-table` 配合 `tree-props` 渲染树时，**折叠不会卸载子行**——只给对应 `<tr.el-table__row>` 加 `display:none`。后果是：

- `page.locator('.el-table__row').count()` **永远等于全树节点总数**——与展开 / 折叠状态、与搜索筛选状态都**无关**
- `count() >= N`（N 是个小数字）会被"DOM 兜底"恒真，看似通过实际**失去判别力**
- `rows_after > rows_before`（行数变化）反而假性失败——前后是同一总数

**判别**：扁平表（一行一条记录、搜索 = 后端 re-fetch DOM 重建）不受此坑影响；只有树表 / 含 `tree-props` 的表受影响。

**正解**：

```python
# ❌ 错（DOM 兜底恒真）
rows = page.locator(".el-table__row").count()
assert rows >= 3

# ✅ 对（只数真可见的 + 真命中关键字的）
rows = page.locator(f'.el-table__row:visible:has-text("{keyword}")').count()
assert rows >= 3, f"expected >= 3 visible rows matching {keyword!r}, got {rows}"
```

**展开/折叠按钮**生效检测用**双信号取或**——总有一个会变：

```python
visible_rows = lambda: page.locator('.el-table__row:visible').count()
expanded_icons = lambda: page.locator(
    '.el-table__expand-icon.el-table__expand-icon--expanded'
).count()
# 三次状态间任一信号变化即按钮生效
assert len({v0, v1, v2}) > 1 or len({e0, e1, e2}) > 1
```

**code smell — 一眼可见的恒真断言**（review 时见到立刻追问"哪个是真断言"）：

| 写法 | 实际语义 |
|---|---|
| `assert a > b or a == b` | 等价 `>=`（恒真，没信号）|
| `assert count >= 0` | 恒真（count 不可能负数）|
| `assert count >= 1`（且 count 是 DOM 计数）| 在树表里几乎恒真，要加 `:visible` 才有意义 |

---

## 坑 8 — 列表搜索区 + 弹窗"同名 label"是 EL 后台管理系统的常态

**症状**：通用 form-item selector 找某个 label，全局 `count = 2`。strict-mode `.first` 走到第一个（搜索区），但搜索区点击路径与弹窗不同 → 等可见性 → 15s timeout。

```python
self.page.locator(
    '.el-form-item:has(.el-form-item__label:text-is("上级产品线"))'
).first    # count = 2 ⚠️
```

**根因**：典型 EL 后台管理页面同时有两个区域用相同字段 label：
- 列表页搜索区：作为筛选条件
- 新增/编辑弹窗：作为表单字段

直接全局 selector + `.first` 必踩。

**修复**——BasePage 沉淀**智能定位器**，自动按当前 visible dialog 限定：

```python
def _form_item_locator(self, label: str):
    """有 .el-dialog:visible 时自动限定弹窗内，否则全局。"""
    selector = (
        f'.el-form-item:has(.el-form-item__label:text-matches('
        f'"^{re.escape(label)}\\s*[：:]?\\s*$"))'
    )
    # 检查页面是否有可见 dialog
    visible_dialog = self.page.locator('.el-dialog:visible')
    if visible_dialog.count() > 0:
        return visible_dialog.locator(selector).first
    return self.page.locator(selector).first
```

所有 `fill_input_by_label / _open_select_dropdown / clear_select / get_field_error` 都走它，**禁止业务 PageObject 手写 `.el-form-item:has(...)` selector**。grep 出来一律改。

**自检清单加一项**："这个 label 在列表搜索区会出现吗？如果会，弹窗操作必须 dialog-scoped"。

**配套**：label 文本本身可能带尾随冒号（半角/全角），所以 selector 用 `:text-matches("^X\s*[：:]?\s*$")` 容错而不是 `:text-is`。

---

## 坑 9 — `keyboard.press("Escape")` 在 EL 2.x dialog 内是**破坏性**动作

**症状**：模板 `_open_select_dropdown` 头两行做"防御性收下拉"：

```python
self.page.keyboard.press("Escape")   # 防御：先收回可能开着的别的下拉
self.page.wait_for_timeout(120)
self.page.locator(".el-select").click()
```

旧 EL 1.x dialog 不响应 Escape，无害。**新版 EL 2.x dialog 默认 `close-on-press-escape: true`** —— Escape **把整个弹窗关掉**，后续 `.el-dialog:visible` 空 → 一切超时。

**规则**：

| 场景 | Escape 安全吗 |
|---|---|
| 列表页（无 dialog）收某个下拉 | ✅ 安全 |
| Dialog 内收下拉 | ❌ **关弹窗** |
| 多选下拉收回（坑 1 变体）| ⚠️ 不在 dialog 内才用；在 dialog 内点 body 空白 |

**修复**：dialog 内**改用点 body 空白处**收下拉：

```python
# dialog 内安全的"收下拉"做法
self.page.locator('.el-dialog__body').first.click(position={'x': 1, 'y': 1})
# 或者直接点 dialog 标题（不影响 form）
self.page.locator('.el-dialog__header').first.click()
```

**审计动作**：接入新项目时 grep 所有 `keyboard.press("Escape")`，标注每处的触发上下文是否含可见 dialog。

---

## 坑 10 — Playwright `:text-matches("X\s*Y")` **不匹配**带 ASCII 空格的文案

**症状**：中文按钮实测文案是「确 定」「取 消」「保 存」（中间带半角空格）。直觉写法：

```python
'.el-dialog__footer button:text-matches("取\\s*消")'   # count = 0 ❌
'.el-dialog__footer button:has-text("取消")'           # count = 0 ❌（substring 不带空格不命中）
'.el-dialog__footer button:has-text("取 消")'          # count = 1 ✅
```

**根因**：Playwright 的 `:text-matches` 不是纯 JS regex，背后有 text engine 归一化层。`\s*` **没按预期匹配 ASCII 空格** —— 这是反直觉的 quirk。

**规则**：

| 场景 | 推荐写法 |
|---|---|
| 中文带空格按钮（确 定 / 取 消 / 保 存 / 登 录 / 搜 索）| `:has-text("X Y")` **字面量写空格** |
| label 加冒号容错（首尾锚定 `^X[：:]?$`）| `:text-matches(...)` ✅ 工作正常 |
| 一般 substring 匹配 | `:has-text("X")` |

**反例**——曾在 `references/env-recon-bootstrap.md` 推荐 `:text-matches("确\\s*定")`，实测发现不工作。已修正。

**自检**：写 `:text-matches` 时如果正则里有 `\s` 或 `　`（全角空格），先用 `page.locator(...).count()` 验证 count > 0 再相信它。

---

## 附录 — Element-Plus 1.x → 2.x 废弃 class hook 速查

跨大版本接入时，"以为稳定"的 class 可能整片消失。**初次接入新项目第一件事**是 dump 一个 form-item 的 `outerHTML`，跟模板假定 selector 比对。

| 用途 | EL 1.x 写法（**已废弃**） | EL 2.x 推荐 |
|---|---|---|
| select 容器外层 | `.el-input` 内层（嵌在 select 里）| `.el-select__wrapper` 或直接稳定外层 `.el-select` |
| select 内部 input | `.el-input__inner` | `.el-select__input` |
| form-item 内容区 | `.el-form-item__content > input` | 同（保留） |
| dropdown 选项 | `.el-select-dropdown__item` | 同（保留）|
| cascader 节点 | `.el-cascader-node` | 同（保留）|
| dialog 容器 | `.el-dialog` | 同（保留）|

**实测命令**（dump 真值）：

```python
page.evaluate("""() => {
    const dlg = [...document.querySelectorAll('.el-dialog')].find(d =>
        getComputedStyle(d).display !== 'none');
    return [...dlg.querySelectorAll('.el-form-item')].map(it => ({
        label: it.querySelector('.el-form-item__label')?.textContent.trim(),
        has_select: !!it.querySelector('.el-select'),
        has_cascader: !!it.querySelector('.el-cascader'),
        has_tree_select: !!it.querySelector('.el-tree-select'),
        has_input_number: !!it.querySelector('.el-input-number'),
        has_date: !!it.querySelector('.el-date-editor'),
    }));
}""")
```

输出"控件类型矩阵"，跟 `recon/menu_list.md §3` 的"控件类型"列做交叉校验。**冲突时以 DOM 真值为准**；同时**反向修 menu_list**。

**真实踩坑记录**：spec 写「所属产品线 = el-select / el-tree-select」，实测是 `el-cascader` → 22 条 AR-05 用例 100% 失败。一字之差走 4 小时。

---

## 附：发现新陷阱时的标准流程

新版本 Element-Plus / 自研组件可能有新坑。按下面流程实证，**不要直接在 PageObject 里硬编码判断**：

1. 跑 `python tools/recon_elements.py` 看字段被识别为什么类型
2. 按现象选探针：

   | 现象 | 跑哪个探针 | 看输出哪个字段 |
   |---|---|---|
   | 字段 disabled / readOnly 判定矛盾 | `tools/probe_dom.py` | `inputInfo[*].disabled` / `wrappers[*].className` |
   | "超长字符未拦截 / 负数被保存" | `tools/probe_overlong.py` | `verdict`（合法 UX 截断 / 接收全部 / maxlength 设错）|
   | "下拉空 → SKIP" 但你不确信 | `tools/probe_select.py` | `items_no_search[*]`（visible-idx 筛选）|
   | 否定性 UI 注释（"X 不存在"）| playwright MCP（`browser_snapshot`/`browser_take_screenshot`） | 全页截图 + DOM 真值 |

3. 在 Chromium DevTools Console 手工验证 `boundingClientRect` / `offsetParent`（如还有疑问）
4. 修复方案优先**补到 `BasePage`**，让所有 PageObject 共享，不要每个页面各自打补丁
5. 把"症状 / 根因 / 修复"按 `tools/findings_template.md` 记录到 `tools/findings_<YYYYMMDD>.md`
6. 在仓库 `STANDARDS.md` 末尾"优化历史"追加索引

---

## 元素定位 3 条强制规范

### 规范 1 — form-item 走 label 组合

✅ 唯一推荐方式
```python
self.page.locator(
    f'.el-form-item:has(.el-form-item__label:text-is("{label}"))'
).first
```

❌ 禁止
```python
self.page.locator('.el-form-item').nth(3)  # 字段顺序变即坏
```

### 规范 2 — 行内按钮在 row Locator 内查找

✅ DO
```python
row = self.page.locator(f'.el-table__row:has-text("{name}")').first
row.locator('button:has-text("编辑")').first.click()
```

❌ DON'T
```python
self.page.locator('button:has-text("编辑")').nth(2).click()  # 行序变即坏
```

### 规范 3 — 等待用 wait_idle，禁止裸 wait_for_timeout 当睡眠

| 场景 | 写法 |
|---|---|
| 页面跳转后 | `self.page.wait_for_url("**/path", timeout=10000)` + `self.wait_idle()` |
| 表单切 Tab | `self.click_tab(...)` 内已 `wait_for_timeout(400)` |
| 点击保存后 | `form.save()` 内已抓 toast + `wait_for_load_state("networkidle")` |
| 关键交互间 | `self.wait_idle(800)` |
| 等元素出现 | `self.wait_for(selector, timeout)` |

❌ 禁止 `time.sleep`（阻塞 event loop，不可替代 `wait_for_timeout`）。
