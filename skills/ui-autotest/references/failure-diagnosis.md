# 失败诊断与缺陷归档

> 用例失败后**不要凭印象瞎猜根因**——四件产物时间戳对齐，CSV 自动归类已经做了大部分工作。
>
> 本 reference 教 Claude 用模板的"自动诊断套路"做失败分析，而不是蹲在 stack trace 前手工 grep。

---

## §1 失败诊断的标准动线（按顺序走）

```
TC-XXX 挂了 / 用户拿来一个失败
   │
   ▼
① 定位 RUN_TS（reports/、screenshots/、logs/ 里都用同一个时间戳）
   - 用户给了 RUN_TS / 文件名 → 直接用
   - 用户没给 → 看 reports/ 最新一个 defects_*.csv
   │
   ▼
② 读 reports/defects_<ts>.csv 找到 TC-XXX 行
   - "原因分析"列已自动归类（见 §3 表格）
   - "失败截图"列给了对应 PNG 绝对路径
   - "错误信息"列已限 500 字符的根因摘要
   │
   ▼
③ 按需补充查证：
   - 看 logs/test_run_<ts>.log 找 "TC-XXX" 块的 step 序列 → 哪一步挂的
   - 看 screenshots/<ts>/<test_name>_failure_<ts>.png → 失败时画面
   - 看 reports/report_<ts>.html → pytest-html 完整报告
   │
   ▼
④ 用三分法判定（见 §2）：
   - 脚本缺陷 → 修 PageObject / 用例脚本，重跑
   - 用例设计问题 → 提 PR 改用例文档
   - 真实 UI / 后端缺陷 → 提 issue（不 xfail，作回归看门狗）
```

**关键技巧**：CSV 已经把"原因分析"做了 80% 的工作。**先看 CSV 再翻日志**，不要反着来。

---

## §2 失败三分法（强制使用）

模板的优化经验显示，每条失败必须分入三类之一，**不允许"待人工分析"占比超过 30%**——超过了就该补 `_classify_root_cause` 规则。

### 类别 A：脚本缺陷（最常见）

**特征**：UI 表现正常，但脚本读不到 / 点不到正确元素。

**典型表现**：
- 脚本写"项目名称"，UI 实际是"项目名"
- 脚本用 `nth(2)` 定位行内按钮，行序变了
- 切 Tab 后立刻操作，撞上渲染竞态

**处理**：
1. 跑 `python tools/recon_elements.py` 对照 `recon_dump.json` 看 UI 真值
2. 修 PageObject 字段定位 / 等待 / 行内查找
3. 重跑用例验证 PASS
4. 在 `tools/findings_<YYYYMMDD>.md` 记录"改了哪几个文件 + 验证 PASS"

### 类别 B：用例设计问题

**特征**：UI 和脚本都没问题，但用例文档与 UI 假设不一致。

**典型表现**：
- 测试用例文档说"必填校验应阻止保存"，UI 实际允许保存（产品决定不校验）
- 文档说"应显示工号列"，UI 没这个字段
- 文档预期 toast 文案是"创建成功"，UI 实际是"新增成功"

**处理**：
1. **不要硬改脚本去迁就文档**——这是制造假绿
2. 脚本里用 `pytest.skip("UI 未提供 xxx")` 或调整断言
3. 提 PR 改用例文档（找产品 / PM 确认）
4. 在 `tools/findings_<YYYYMMDD>.md` 记录"文档假设 vs 实际 UI 截图"

### 类别 C：真实 UI / 后端缺陷

**特征**：UI 表现就是不对，脚本暴露的是真问题。

**典型表现**：
- input-number 设了 `min=0`，但 fill 负数能保存（坑 5）
- toast 里出现"系统接口422异常"
- 必填字段为空也保存成功（UI 漏校验）

**处理**：
1. **不 xfail**——保留为 FAIL 作为回归看门狗
2. 提 issue（含复现步骤 + 期望 + 实际 + 推断根因）
3. 在 `tools/findings_<YYYYMMDD>.md` 记录"真实 UI/后端缺陷"
4. issue 修复后该用例自动转 PASS

---

## §2.5 SKIP 三分法（每轮全量后必做）

> **触发时机**：每完成一轮全量回归（或重构后），对**所有 SKIP 用例**做一次三分类，
> 判断"是否合理 / 是否有可优化空间"。**长期 SKIP 是暗债的温床**——不做归因
> 复检，迟早被假 SKIP 反咬一口（参考主 SKILL.md 约束 4 / 第 8 轮血泪）。

### 类别 A：环境配置缺失（最常见）

**特征**：DB / API_TOKEN / 第三方服务等环境变量未配。

**典型表现**：
- `pytest.skip("DB 未配置（APP_DB_*），跳过 dept.rdm_id 校验")`
- 模块级 `pytest.mark.skipif(not is_endpoint_alive(...))`

**处置**：
- 模板 `.env.example` 列出所有配置；
- module-level skip 给出明确"配几行环境变量即可解锁 N 条"的指引；
- 配置即解锁，**不需要改脚本**。

### 类别 B：UI 实际未提供（最危险）

**特征**：测试用例文档假定的元素当前 UI 不存在。

**典型表现**：
- `pytest.skip("当前 UI 未提供 'xxx 表格'")`
- `pytest.skip("项目详情页无版本相关 Tab")`

**处置**：

1. **必须先按主 SKILL.md 约束 4 实测复检**——否定性 UI 注释会随 UI 演进失效；
2. 实测确认 UI 真没有 → 用"探测器 + 兜底 skip"模式（PageObject 写探测器函数，
   用例调它兜底 skip），**不要硬编码 skip**；
3. 实测发现 UI 已实装 → 立刻实装真步骤，把假 SKIP 转 PASS（参考第 8 轮：
   4 条假 SKIP → 4 PASS）；
4. 同步反馈 PM/产品确认是产品决策不实现，还是迭代未到。

### 类别 C：数据/环境状态依赖

**特征**：异常流需要外部条件（"RDM 不可达"才能跑），或前置数据未预制。

**典型表现**：
- `pytest.skip("RDM 当前可达，无法验证不可达场景")`
- `pytest.skip("没有未关联版本，先跑 TC-058 制造")`

**处置（按可优化性分两子类）**：

- **C.1 完全依赖外部条件**（如"RDM 不可达"）→ 接受 SKIP（自动化无法控制）；
- **C.2 可优化**（"前置数据空"）→ 写**数据预制 fixture**（mock/seed）让 SKIP 转 PASS。
  例如源项目第四轮加 `rdm_seeded_dept` fixture 把 TC-001/004 从 SKIP→PASS。
  写法见 `references/case-skeleton.md` 骨架 6。

### 判定流程模板

```
全量跑完 → 列出 SKIP 列表 → 对每一条问 3 个问题：
  1. skip 消息含具体原因？        ← 否则改 skip 消息（违反 §4.5）
  2. 原因属于 A/B/C 哪一类？
  3. 这类对应处置策略做了吗？
     - A：模板 .env.example 全？module-level skip 含配置指引？
     - B：是不是凭注释硬 skip？换成探测器+兜底 skip
     - C：能否用 mock/seed 数据让 PASS？
```

### "假 SKIP → 真 FAIL" 是脚本质量提升的信号（不要回退）

修复某个 PageObject bug（例如多选下拉假可见）后，原本 SKIP 的用例开始正确执行，
结果暴露出真实的后端/UI 缺陷 → 转成 FAIL。**这是好事不是退化**：

| 状态 | 含义 |
|---|---|
| 修复前 SKIP | "脚本判定下拉空所以跳过" → 真实缺陷被脚本 bug 掩盖 |
| 修复后 FAIL | "脚本能选中下拉项了，保存返回 422" → 真实暴露后端缺陷 |

判定原则：

- ✅ 若 FAIL 归类为 C 类真实 UI/后端缺陷 → 保留 FAIL 作"回归看门狗"，**不修脚本**；
- ❌ 不要为了"通过率好看"把 FAIL 改回 SKIP——这是 §1.1 暗债的反向版本。

**实际案例**：源项目第四轮修 `select_security_role` 后，TC-010/037 从 SKIP→FAIL
（4 条同根因 422）。通过率从 73→72，但**测试质量上升**——从"假 SKIP 掩盖缺陷"
变成"真 FAIL 准确反映后端 422"，给开发的 issue 同根因合并 1 条。

---

## §3 CSV 自动归类规则速查

`conftest._classify_root_cause` 的归类规则（自上而下，先 specific 后 generic）：

| 匹配条件（出现在错误信息中） | 归类 | 多半是 |
|---|---|---|
| 含 `系统接口422异常` | 后端接口 422 异常 | 类别 C（真实缺陷） |
| `toast='新增成功' field-error=''`（异常流） | UI 漏校验 | 类别 C（真实缺陷） |
| `min 属性=` + `input 实际值='-` | input-number 负数绕过 | 类别 C（真实缺陷） |
| `val='1.5' err=''` | input-number 未限整数 | 类别 C（真实缺陷） |
| `未禁用 / is_field_readonly` | 字段禁用判断与 UI 不一致 | 类别 A 或 C（先 probe_dom） |
| `TimeoutError + el-select-dropdown__item` | Element-Plus 下拉脆弱 | 类别 A（脚本绕过基类） |
| `Timeout` | 元素等待超时 | 类别 A（等待不够 / 元素不存在） |
| `ImportError` | 脚本依赖缺失 | 类别 A（环境/依赖） |
| `未找到` + `下拉` | 下拉空 | 类别 B 或 C（数据 / 后端） |
| `重名 / 已存在` | 数据冲突（清理失败） | 类别 A（unique_name 没用 / cleanup 失败） |
| 其它 | （待人工分析） | 需要补归类规则 |

### 当"待人工分析"占比超 30% → 补归类规则

在根 `conftest._classify_root_cause` 内追加规则。**优先级 = 在函数内的位置**（自上而下，先 specific 后 generic）。下游项目独有的归类规则也加在这里，**不需要 fork 模板**。

---

## §4 自带证据的 6 种断言（强制用这些，不要写裸 assert）

模板提供的"自带证据"断言：

| 场景 | 用法 | 失败信息样例 |
|---|---|---|
| 期望保存成功 | `BasePage(page).assert_save_success(detail)` | `保存未成功（TC-014 创建项目）；页面反馈='系统接口422异常'` |
| 不确定成功失败 | `ok, text = BasePage(page).save_and_wait_feedback()` | 返回真实 toast 文案 |
| 期望保存被阻止 | `assert_save_blocked(page, label, reason)` | `保存未被阻止：1001字符应阻止保存；field-error='' toast='新增成功' state=...` |
| 期望字段校验报错 | `assert_field_validation(page, label, msg_suffix)` | `字段 'xxx' 校验未触发；err='' input value='...'` |
| 期望前端 maxlength 截断（合法 UX）| `assert_field_truncated_to(page, label, max_len, type_hint='auto')` | `字段『xxx』未被截断到 1000：实际长度=1001 maxlength属性='1001' 标签='textarea'` |
| 期望 input-number blur 规整（合法 UX）| `assert_input_number_regulated(page, label, raw, expected)` | `字段『xxx』未被规整为 '0'：raw=-1 blur后val='-1' min属性='0' step='1'` |

后两个断言用于 §6.3 的"截断/规整型异常流"用例——异常流不是只有"应阻止保存"
一种范式，前端自动截断或规整本身就是合法 UX，**用例应该断言这个 UX 是否生效**，
而不是简单期望"保存失败"。详见 `references/element-plus-pitfalls.md` 坑 5 配套段。

❌ 永远不要写
```python
assert ok, "SVN 保存未成功"
# ↑ 不知道是后端 422、UI 没渲染完、还是 toast 没抓到
```

❌ 也不要写
```python
assert form.get_field_error("xxx") != "", "应有错误"
# ↑ 失败信息只剩 "应有错误"
```

---

## §4.5 失败信号自闭环 + 三分支判定模式

> **原则**：用例失败的那一刻，所有定位需要的信息都应该出现在 `assert` / `pytest.fail` 消息里：现象 + 数据 + 判断。下游（CSV / 工单 / 群消息）只是搬运，**不是再加工**。如果 CSV 摘要里只有 `None != 297`，说明用例层就丢了信息——不是 CSV 的问题。

### 三分支判定模式（"UI 操作 → 期望落库"类用例的通用骨架）

```python
# 1. 执行关键操作
vp.click_dialog_button("确 定", dialog_title="重新关联到项目")
logged_page.wait_for_timeout(1000)

# 2. 在 toast 自动消失前（~3s 窗口）抓取它，区分成功/失败/异常关键字
toast_hit  = vp.wait_for_toast_any("成功", "失败", "错误", "异常", timeout=2000)
toast_full = vp.visible_toast_text()

# 3. 回查 DB / API 拿到真实落库状态
rec = api.find_version(ver_no)
actual_pid = rec.get("projectId")

# 4. 三分支判定（每条都用 BUG[<分类>]: 三段式 — 见 §4.6）
if actual_pid == p2_id:
    return                                           # ✅ happy path
if toast_hit and toast_hit != "成功":
    pytest.fail(
        f"BUG[真实-后端拒绝]: 重新关联 V→P2 被前后端拒绝；"
        f"UI 弹出 toast «{toast_full}»，DB projectId 仍为 {actual_pid!r}（期望 {p2_id}）。"
        f"证据指向真实业务流程缺陷，非脚本问题。"
    )
pytest.fail(
    f"BUG[真实-静默丢失]: 点击「确 定」后无 toast 反馈，但 DB projectId 仍为 {actual_pid!r}（期望 {p2_id}）。"
    f"请求可能未发出 / 未提交。toast_text={toast_full!r}"
)
```

**为什么这样写**：

| 决策 | 原因 |
|---|---|
| `pytest.fail()` 而非 `assert` | assert 失败时 pytest 会重写表达式追加 `assert None == 297`，混入摘要噪音；`pytest.fail(msg)` 直接给消息，干净 |
| 三分支区分缺陷形态 | 成功 / 后端拒绝（带 toast）/ 静默丢失（无 toast）→ 三类的根因和工单走向截然不同，用例层就分清楚比让人事后猜更高效 |
| toast + DB 双取证 | toast 是后端 → 前端的实时反馈通道；DB 是真值落点。两路对照能一眼看出是"前端没显示"还是"后端没收到"还是"后端收了没存" |
| `wait_for_toast_any("成功","失败","错误","异常")` | Element-Plus 的 `.el-message` / `.el-notification` 在 ~3s 后自动消失；列出关键字主动等 |

### §4.6 BUG[<分类>]: 三段式 — 富 BUG 摘要约定

格式：

```
BUG[<分类>]: <现象 + 期望 vs 实际 + 证据>
```

模板 `conftest._classify_failure` 的正则会**优先采信**作者写的 `BUG[<分类>]:` 标签——直接作为 CSV「原因分类」列的值，而不是跑 keyword heuristic 把它埋进"待人工分析"。

**推荐分类词表**（与 §3 CSV 自动归类同源，方便聚合；CSV 不做白名单校验，必要时可扩）：

- `真实-后端拒绝`
- `真实-后端静默丢失`
- `真实-UI/业务流程行为偏离预期`
- `真实-后端 API 拒绝/异常`
- `脚本缺陷-元素定位/超时`
- `脚本缺陷-元素未找到`
- `用例设计问题-前置数据缺失`
- `用例设计问题-断言期望与 spec 不符`

**写法骨架**：

```python
pytest.fail(
    f"BUG[<分类>]: <一句话现象>；"
    f"<期望值> vs <实际值>；"
    f"<证据：toast 引文 / DB 字段值 / 截图路径>"
)
```

例：

```python
pytest.fail(
    f"BUG[真实-后端拒绝]: 重新关联 V→P2 被前后端拒绝；"
    f"UI 弹出 toast «{toast_full}»，DB projectId 仍为 {actual_pid!r}（期望 {p2_id}）。"
    f"证据指向真实业务流程缺陷，非脚本问题。"
)
```

**改造前后对比**（同一 BUG，CSV 摘要列）：

```
改前: tests/test_ar07001002_unlink_relink.py:73:  ⏎     def test_tc07001002003_relink(...): ...
改后: BUG[真实-后端拒绝]: 重新关联 V→P2 被前后端拒绝；UI 弹出 toast «系统未知错误，请反馈给管理员»，DB projectId 仍为 None（期望 301）。证据指向真实业务流程缺陷，非脚本问题。
```

改后那行**直接能写进缺陷工单 / 周报 / 同步给后端的群消息**，零编辑成本。

### 框架侧配套：摘要列改取异常原文（已落地于 mode 模板的 conftest）

```python
# conftest.pytest_runtest_makereport 内
exc = getattr(call, "excinfo", None)
if exc is not None and exc.value is not None:
    clean = str(exc.value)
    clean = clean.split("\nassert ", 1)[0]   # 剥离 pytest 重写的 "assert <expr>" 噪音
else:
    clean = str(rep.longrepr)[:2000]
summary = clean.replace("\r","").replace("\n", " ⏎ ").strip()[:600]
```

**两个独立的输入**：
- 分类（`_classify_failure`）跑在 `full_repr`（带 traceback）—— 关键词触面更广
- 摘要（CSV 列）取 `call.excinfo.value` —— 用例作者写的原文，干净文本

---

## §5 灾难恢复速查（出大问题时）

| 症状 | 第一时间做什么 |
|---|---|
| 单条用例 reproduce | `pytest <nodeid> -v -s` |
| 看用例步骤序列 | `logs/test_run_<ts>.log` 找 `[arNN] 步骤 N` |
| 看失败时画面 | `screenshots/<ts>/<test_name>_failure_<ts>.png` |
| 看自动归类 | `reports/defects_<ts>.csv` "原因分析"列 |
| 仍判不出 → 调 headed 模式 | `set APP_HEADLESS=0 && set APP_SLOW_MO=300` |
| DOM 属性奇怪 | `python tools/probe_dom.py`（修 LABELS）→ `tools/probe_dom.json` |
| "超长字符未拦截 / 负数被保存"疑似漏校验 | `python tools/probe_overlong.py`（修 OVERLONG_FIELDS / INPUT_NUMBER_FIELDS）→ 看 `verdict` 字段判合法 UX 还是漏校验（参考坑 5 配套） |
| "下拉空 → SKIP" 不确信真假 | `python tools/probe_select.py`（修 SELECT_LABELS）→ 看 `items_no_search[*]`（visible-idx 筛选，避开"下拉假可见"坑）|
| 否定性 UI 注释（"X 不存在"）但脚本写法混乱 | **第一动作**用 playwright MCP（`browser_navigate` → `browser_snapshot` → `browser_take_screenshot`）实地复检——参考主 SKILL.md 约束 4 |
| 元素定位失效 | `python tools/recon_elements.py` 对比新旧 `recon_dump.json` |
| 全量大批量挂 | 看 logs 是否有 `[session] 首次登录` 重复 → 登录复用炸了 |

---

## §6 优化记录沉淀

每轮"侦察 + 修脚本 + 跑测试"结束后，按 `tools/findings_template.md` 复制到 `tools/findings_<YYYYMMDD>.md`，分三类填写：

1. **脚本缺陷**（已修复）→ 改了哪几个文件 + 验证 PASS
2. **用例设计问题**（提 PR 改文档）→ 文档假设 vs 实际 UI 截图
3. **真实 UI/后端缺陷**（提 issue）→ 复现步骤 + 期望 + 实际 + 推断根因

完成后在 `STANDARDS.md` 末尾"优化历史"追加一行索引：

```
| 2026-04-27 | tools/findings_20260427.md | AR-03 项目手动管理 | pages/project_page.py / tests/test_ar03_xxx.py |
```

这套"沉淀-索引"机制让模板能跨项目演进——别人复用模板时能看到所有历史踩坑记录。

---

## 一句话总结

**遇到失败 → 先读 CSV 自动归类 → 再三分法判 → 修对应位置**——这套套路源项目验证过几十次，比"凭印象 grep stack"快至少 5 倍。
