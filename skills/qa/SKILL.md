---
name: qa
description: |
  **核心基座（第零原则）：系统化 QA / 冒烟的目的是发现 BUG，不是刷通过率、不是确认"看起来还行"。所有方法、动作、报告都服务于这一条——发现一个真 bug 比跑完一百个绿步骤更有价值；遇到冲突永远选这条。**
  穿 UI 系统化 QA / 冒烟方法论 skill：把一个 web 应用当真实用户去用——导航、交互、断言状态、截图取证、记录缺陷——找出它在哪坏了。**跑在已装的 playwright MCP**（`browser_*` 工具控真实浏览器运行时），与具体后端、框架、公司项目无关。它固化一套反复验证过的 QA 方法论——**第零原则（找 bug 非刷率）**、**三档强度（quick / standard / exhaustive）**、**per-page 探查清单**、**两层取证（交互 bug 前后截图 + 静态 bug 单张标注）**、**缺陷分级（critical / high / medium / low）**、**健康分粗评**。
  **用户/编排提到下列任何场景都应主动加载本 skill**：对站点做 QA / 冒烟 / 系统化测一遍 / 找 bug / dogfood 用户流程 / 验收一次部署 / 登录金丝雀 / 穿 UI 验收 / "这个能用吗" / 视觉对照原型截图 / 把页面点一遍看哪里坏了 / build 后冒烟。即使没明说"QA"两字，只要语义是"把跑起来的 UI 当用户系统化走一遍验它对不对、找缺陷"，都视为本 skill 适用范围。
  **边界**：本 skill 是**方法论 prose skill**，不写 Playwright + pytest 自动化脚本（那是 `ieidev-team:ui-autotest` 的活）、不做 DOM 实测前置侦察落 `recon/menu_list.md`（那是 `ieidev-team:env-recon`）。本 skill 管"人/agent 临场穿 UI 用 playwright MCP 系统化探查 + 取证 + 缺陷分级 + 健康分"——是冒烟/验收/dogfood 通道，不是回归脚本通道。需被测环境 URL + playwright MCP 可用（env-gated）。
---

# 系统化 QA / 冒烟方法论（playwright MCP 版）

本 skill 是一套**与具体后端 / 框架 / 项目无关**的系统化 QA / 冒烟方法论，跑在 **playwright MCP**（`browser_*` 工具操控真实浏览器运行时）。它把"像真实用户一样把一个 web 应用走一遍、找出它在哪坏了"沉淀成可操作的步骤、取证纪律、缺陷分级与健康分。

你是 QA 工程师，不是"点一下没报错就当过"的验收员。点击每一个能点的、填每一个表单、检查每一种状态。发现 bug 时立刻取证落账，不批量、不靠记忆。

---

## 第零原则（基座）— QA 的目的：发现 BUG，不是刷通过率

所有方法都服务于这一条。当任意步骤与"让结论变绿 / 报告好看"冲突时，**永远选这条**。

- **发现的 bug 是产出，不是失败**。一次 QA 跑完零 bug 不是"成功"——更可能是没走够深、没碰边界、没看控制台。
- **不为"看起来还行"背书**。"页面加载了 / 按钮点了没崩"≠"功能对"。要断言**预期状态**真的发生（数据进了列表、toast 文案对、URL 跳对、字段值落库回显对）。
- **藏起来的 bug = 任务失败**。看到控制台红、看到布局塌、看到点了没反应——记下来，分级，取证。不要因为"可能是已知问题 / 可能无关本次改动"就跳过；标注归属，但不丢。

### 三条直接推论（探查 / 取证 / 报结论时按这三条判）

1. **断言预期状态，不止"无异常"**：每个交互后用 `browser_snapshot` 取可访问性树 / DOM 真值 + `browser_console_messages` 看有没有新报错，确认**该发生的发生了**（不只是"没崩"）。
2. **取证再下结论**：任何缺陷断言（"X 坏了 / Y 缺失 / Z 点不动"）必须有 `browser_take_screenshot` 截图 + repro 步骤兜底，不靠"我记得刚才"。否定性结论（"当前 UI 没有 X"）尤其要现场截图坐实——UI 演进后这类事实最易失效。
3. **走深而非走宽凑数**：核心流程（登录 / 主业务表单 / 列表增删改查 / 支付）多花时间逐状态探（空 / 加载 / 错误 / 溢出 / 校验），次要页（关于 / 条款）一眼带过。宁可深测 3 个核心流程，不要浅扫 30 个页面只看"加载了没"。

---

## playwright MCP 工具映射（本 skill 用到的 `browser_*`）

本 skill 不依赖任何 daemon / telemetry，只用已装 playwright MCP 暴露的浏览器工具：

| 能力 | playwright MCP 工具 | 在 QA 里干什么 |
|---|---|---|
| 导航到页面 | `browser_navigate` / `browser_navigate_back` | 打开被测 URL、在流程里前进/后退 |
| 取 DOM / 选择器真值 | `browser_snapshot` | 取**可访问性树快照**（含元素 ref），是定位元素 + 断言渲染结果的主力（替 gstack 的 `snapshot -i`）。看用户**可见渲染结果** = 黑盒允许 |
| 截图取证 | `browser_take_screenshot` | 缺陷前后对照、视觉对照原型图、归档证据 |
| 点击 | `browser_click` | 点按钮 / 链接 / 菜单项（用 snapshot 给的 ref 定位） |
| 输入 | `browser_type` / `browser_fill_form` | 填单字段 / 整表单（含空、非法、边界值） |
| 下拉 / 选项 | `browser_select_option` | el-select / 原生 select 选值 |
| 悬浮 / 键盘 | `browser_hover` / `browser_press_key` | 触发 tooltip / 菜单、Tab/Enter 键盘流 |
| 等待 | `browser_wait_for` | 等文案出现/消失、等异步加载完，替"点了立刻断言"的 flaky |
| 控制台 | `browser_console_messages` | 抓 JS 报错 / warning，是健康分 Console 维度的真值源 |
| 网络 | `browser_network_requests` / `browser_network_request` | 看 4xx/5xx 请求、API 直打验证后端 |
| 求值 | `browser_evaluate` | 读页面状态 / 元素属性做精确断言（如 readonly、disabled、值回显） |
| 视口 | `browser_resize` | 响应式：双分辨率（如 1366 / 1920）或移动视口截图对照 |
| 弹窗 | `browser_handle_dialog` | confirm / alert / beforeunload 处理 |
| 多标签 | `browser_tabs` | 新开标签页流程（如导出 / 详情页新窗） |
| 收尾 | `browser_close` | QA 跑完关闭浏览器上下文 |

> 选择器纪律：用 `browser_snapshot` 拿到的 **ref/role/name** 定位元素，不要凭记忆硬编码 CSS 选择器。snapshot 是本 skill 判断"字段名 / 按钮文案 / 异步状态"是否还跟当前 UI 一致的最快路径。

---

## 三档强度（quick / standard / exhaustive）

档位决定**走多深 + 报哪些级别的缺陷**。编排 / 用户可显式指定，缺省 **standard**。

| 档 | 何时用 | 走多深 | 报到哪一级 |
|---|---|---|---|
| **quick** | 30 秒冒烟 / build 后金丝雀 / 验一次部署没整体崩 | 首页 + 顶部 5 个导航目标。每页只看：加载了吗？控制台有错吗？明显死链/塌版吗？核心金丝雀流程（如登录）走通一遍 | critical + high |
| **standard**（缺省） | 一个功能/页面"做完了想验它对不对" | 受影响页逐个走 per-page 探查清单：交互元素都点、表单都填（空/非法/边界）、状态都看、控制台都查 | + medium |
| **exhaustive** | 上线前 / 重点模块 / 要尽量零缺陷 | standard 全量 + 响应式双视口 + 边角页 + 溢出/超长/特殊字符等 cosmetic 边界 | + low / cosmetic |

**登录金丝雀（quick 档最常用，也是所有档的入口冒烟）**：真打开登录页 → `browser_type` 填账号/密码/验证码 → `browser_click` 点登录 → `browser_wait_for` + `browser_snapshot` 断言**真进了首页**（不是"点了没报错"）。进不去 = critical，立刻取证。

---

## 工作流（5 阶段）

### 阶段 1：初始化 + 定档 + 定范围

1. 拿被测环境 URL（运行时输入，编排 / 测试人员提供）。**URL 缺失 → env-gated 阻塞**，写 blocked 原因，不空跑。
2. 确认强度档（quick / standard / exhaustive，缺省 standard）。
3. 定范围：若有"本次改动 / 受影响页 / 要 dogfood 的流程"清单（如来自 PLAN / 改动 diff / 原型图），按它切；否则全应用系统化走。

### 阶段 2：认证（如需要）

```
browser_navigate <登录 URL>
browser_snapshot                  # 找登录表单元素 ref
browser_type  <账号字段ref> "<user>"
browser_type  <密码字段ref> "[填测试账号密码——报告里绝不写明文真实口令]"
browser_click <登录按钮ref>
browser_wait_for / browser_snapshot   # 断言登录成功（进了首页/出现用户态元素）
```

- 验证码 / 2FA：请运行者提供或在浏览器里完成后让你继续。
- CAPTCHA 挡住：告知运行者"请在浏览器完成人机校验后让我继续"。

### 阶段 3：定位（map 应用）

```
browser_navigate <被测 URL>
browser_snapshot                  # 拿可访问性树：导航结构、主要可交互元素 ref
browser_take_screenshot           # 落首屏证据
browser_console_messages          # 落地页有无报错？
```

- SPA（客户端路由、无整页刷新）：导航多在按钮/菜单项，靠 `browser_snapshot` 找 nav 元素，别指望"链接列表"。

### 阶段 4：探查（per-page 清单，逐页走）

每到一页：

```
browser_navigate <page-url>
browser_snapshot
browser_take_screenshot
browser_console_messages
```

然后逐项过 **per-page 探查清单**：

1. **视觉扫描** — 看截图：布局塌没、溢出、错位、缺图。
2. **交互元素** — `browser_click` 每个按钮/链接/控件，它真的有反应吗？（断言预期状态，不止"没崩"）
3. **表单** — `browser_fill_form` / `browser_type` 填了提交。测**空提交 / 非法值 / 边界值**：校验提示对吗？该拦的拦了吗？
4. **导航** — 进出这页的每条路径都通吗？面包屑 / 返回 / 跳转对吗？
5. **状态** — 空状态、加载中、错误态、长列表溢出、超长文本，各长什么样？
6. **控制台** — 交互之后 `browser_console_messages` 有没有**新**报错？
7. **响应式**（exhaustive / 相关时）— `browser_resize` 切双分辨率或移动视口再 `browser_take_screenshot` 对照。

**深度判断**：核心功能（首页 / 仪表盘 / 主表单 / 列表 CRUD / 支付 / 搜索）多花时间逐状态探；次要页（关于 / 条款 / 隐私）一眼带过。

**quick 档**：只走首页 + 顶部 5 个导航目标，跳过逐项清单——只看：加载了？控制台有错？明显死链/塌版？金丝雀流程通？

### 阶段 5：取证 + 收尾

**缺陷立刻取证落账，不批量、不靠记忆。** 两层取证：

**交互型 bug**（断流程 / 死按钮 / 表单失败）：
```
browser_take_screenshot           # 动作前
browser_click <出问题的元素ref>    # 执行动作
browser_take_screenshot           # 动作后（暴露问题的那一张）
browser_snapshot                  # 前后 DOM 对照说明"啥变了/没变"
# 写 repro 步骤，引用这两张截图
```

**静态型 bug**（错别字 / 布局 / 缺图）：
```
browser_take_screenshot           # 单张证据，圈出问题
# 描述哪里不对
```

收尾：
1. 按下面分级与健康分粗评，给**前后健康分 + Top 缺陷清单**。
2. 汇总控制台健康（跨页累计的报错数）。
3. 填元数据：被测 URL、强度档、走过的页数、截图数、检出的框架（如有）。
4. 完成 → 回编排（本 skill 是 dev-engineer-e2e / 冒烟通道的方法论）；FAIL 走各自 flow 的 reflow。

---

## 缺陷分级（critical / high / medium / low）

| 级别 | 判据 | 例 |
|---|---|---|
| **critical** | 核心流程走不通 / 数据丢 / 整页崩 / 安全暴露 | 登录进不去、提交后数据没落、白屏报错 |
| **high** | 主要功能坏但有绕路 / 显著错误状态 | 列表筛选失效、必填校验不拦、关键按钮死 |
| **medium** | 次要功能问题 / 边界处理缺失 / 体验明显卡点 | 空状态没处理、长文本溢出、错误提示文案误导 |
| **low / cosmetic** | 视觉瑕疵 / 文案小错 / 不影响功能 | 对齐偏、错别字、hover 态缺失 |

**档与级别的关系**：quick 只处置 critical+high；standard 加 medium；exhaustive 全报到 low。**但任何档都要把看到的更低级别缺陷记下来**（哪怕本档不深究）——藏起来的就是漏掉的。

---

## 健康分粗评（轻量，给"前后对照 + ship 决策信号"）

不是精密度量，是给编排/人一个**前后可比的方向信号**。各维度 0-100，按权重取加权平均：

| 维度 | 权重 | 粗评 |
|---|---|---|
| Console（控制台报错） | 15% | 0 错=100；1-3=70；4-10=40；10+=10 |
| 链接（死链） | 10% | 每条死链 -15（下限 0） |
| 功能（Functional） | 25% | 起 100，每个 critical -25 / high -15 / medium -8 / low -3（下限 0） |
| 视觉（Visual） | 15% | 同上扣分制 |
| 交互/体验（UX） | 15% | 同上扣分制 |
| 内容（Content） | 5% | 同上扣分制 |
| 性能/响应（Perf/响应式） | 15% | 同上扣分制 |

`健康分 = Σ(维度分 × 权重)`。报告里给**QA 前→后**两个分 + 分差，让"这次修没修好"一眼可见。

---

## 与兄弟 skill 的边界（别越界）

| skill | 它管什么 | 与本 skill 的关系 |
|---|---|---|
| `ieidev-team:ui-autotest` | 写 / 改 / 跑 **Playwright + pytest 自动化脚本**（回归通道，四件套归档） | 本 skill 是**临场穿 UI 冒烟/验收/dogfood**，不写持久脚本；要落回归脚本去 ui-autotest |
| `ieidev-team:env-recon` | **实测前置侦察**：登录采菜单全树落 `recon/menu_list.md` 当 UI 文案权威源 | 本 skill 直接用 playwright MCP 临场 `browser_snapshot` 取 DOM；要沉淀权威 recon 产物去 env-recon |

三者都用 playwright（MCP / pytest），但分工不同：**env-recon 侦察建权威源 → ui-autotest 落回归脚本 → qa 临场系统化冒烟/验收找 bug**。本 skill 是"人/agent 拿浏览器把 UI 当用户走一遍"的方法论，不是脚本工程。

---

## 收尾自检（完成前过一遍）

- [ ] **第零原则**：这次跑是真在找 bug，不是为刷"绿"？深度够吗？碰边界了吗？看控制台了吗？
- [ ] **取证齐**：每条缺陷断言都有 `browser_take_screenshot` 截图 + repro 步骤？否定性结论现场坐实了？
- [ ] **断言预期态**：交互后断的是"该发生的发生了"，不是"没崩"？
- [ ] **档对齐**：按指定强度档走够深、报到对应级别？更低级别缺陷也记下了？
- [ ] **健康分**：给了前后分 + 分差 + Top 缺陷清单？
- [ ] **env-gated**：URL / playwright MCP 缺失时正确写了 blocked，没空跑凑结论？
