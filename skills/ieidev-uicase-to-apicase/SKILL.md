---
name: ieidev-uicase-to-apicase
description: 把已有的 UI/Playwright 测试用例 .md（含 `【测试用例信息】` 块、`TC-AR{XX}{YYY}{ZZZ}-{NNN}` 编号格式）按 7 条 UI→API 转换规则批量改写为 API 测试用例 .md，作为 ieidev-team:ieidev-api-autotest 生成 pytest 四件套的直接输入。**用户提到下列任何关键词，都应主动加载**：UI→API 转换 / 把 UI 用例转成 API / 从 UI 用例派生 API 用例 / 给 UI 用例配套写一份接口测试用例 / 测试用例 UI→API / 跳过纯 UI 约束只保留接口可断言的部分 / 让一份用例同时驱动 UI 与 API 自动化 / 把 SOP_测试用例-XXX.md 转成 -api.md。即使用户没明说"UI→API"四个字，只要项目里同时存在符合标准模板（`【测试用例信息】` 块）的 UI 用例 .md + api_inventory.md / OpenAPI 清单，并要求"派生一份接口可跑的用例文档"或"分流给 API 自动化"，都视为本 skill 适用范围。这是 spec-to-testcases-pipeline → ieidev-team:ieidev-api-autotest 之间的桥接环节，与 testcases-to-playwright-pipeline 并行使用。**不要降级成手工逐条改写**，否则 16 条等价规则容易漏（特别是规则 3/4/8 的"该跳"与规则 5/6 的"必测"边界）。
---

# ieidev-team:ieidev-uicase-to-apicase

把一份已成型的 UI/Playwright 测试用例 .md，沿"UI→API 转换 7 条规则"批量改写为同结构的 API 测试用例 .md，让一份 UI 用例同时驱动 UI 与 API 两条自动化流水线。

本 skill 全局可用，服务于**任何采用 KDevSec / RuoYi 风格测试用例模板**的下游项目（KDevSec / SOP_test / Gen9 / 可信评估 / vfadmin 等）。下游项目可能改了 AR 编号前缀（如 `AR-SATP-04` / `AR-GEN-09`）、字段命名约定（RuoYi camelCase / 其他后端按其约定）、API 路径前缀（`/docker-api/` / `/api/`），但**这 7 条转换规则与 5 段产出结构是模板沉淀的核心资产**，绕过它们容易漏掉规则 3/4/8 的"该跳"或规则 5/6 的"必测"边界。

---

## 何时该用

触发场景：
- 用户给出 UI 测试用例 .md（标准模板：`【测试用例信息】` 块 + 编号 `TC-AR{XX}{YYY}{ZZZ}-{NNN}`）+ api_inventory.md / OpenAPI 清单，要求生成对应的 API 用例 .md
- 用户说"UI→API 转换 / 把 UI 用例派生一份 API 用例 / 测试用例分流给 API 自动化 / 给原 UI 用例配套接口测试文档"
- 测试设计阶段产出的 SOP_测试用例-XXX.md 需要分流给"UI 自动化"与"API 自动化"两条流水线

不适合：
- 没有 UI 用例 .md 蓝本，只有 spec.md → 走 spec-to-testcases-pipeline
- 已经有 API 用例 .md，要直接生成 pytest 四件套 → 走 ieidev-team:ieidev-api-autotest
- UI 自动化生成 → 走 testcases-to-playwright-pipeline / ieidev-team:ieidev-ui-autotest

## 在项目流水线中的位置

```
spec.md + 原型 ──[spec-to-testcases-pipeline]──► 测试用例.md (UI)
                                                  │
                                ┌─────────────────┴─────────────────┐
                                │                                   │
              [testcases-to-playwright-pipeline]            [ieidev-team:ieidev-uicase-to-apicase]   ← 本 skill
                                │                                   │
                          Playwright 用例集                  测试用例-api.md
                                                                    │
                                                          [ieidev-team:ieidev-api-autotest]
                                                                    │
                                                            pytest 四件套
```

## 核心：7 条转换规则（必须严格遵守）

每条 UI 用例按规则归类后改写。规则源自项目实践，违反任一条都会让产出脱离接口可断言边界。

| # | UI 模式 | API 改写策略 |
|---|---|---|
| 1 | 点击"新增"+ 填表 + 点"确定" | 直接调 `POST /<资源>`，断言 `HTTP 200 + body.code=200 + body.data.<id> 非空` |
| 2 | "列表新增一行 / 某字段显示 X" | `GET /<资源>/list` 或 `GET /<资源>/{id}`，断言返回包含目标记录且字段匹配 |
| 3 | "字段必填红星 / maxlength=N / 字符计数 / 自动锁定" | **跳过**（纯前端约束）；51 字符这类等价类映射到规则 6 的超长 negative |
| 4 | "弹窗标题 / 按钮文案 / cascader 显示 / tag 颜色 / 表头宽度 / tooltip" | **跳过**（纯 UI 渲染） |
| 5 | "操作日志 4 要素（FR-004）" | `GET /monitor/operlog/list?title=&beginTime=&endTime=` 验证 4 要素；关联变更走 `GET /<resource>/linkChangeLog/list` 或对应资源的关联日志接口 |
| 6 | "唯一性冲突 / 必填缺失 / 字段超长 / 越权 / 不存在 ID 报错" | 必测，断言 `body.code != 200 + body.msg 含约定文案 + 数据库无变更` |
| 7 | UI 隐含的等价类（"任意 1 字符" / "50 上界" / "51 超长" / "高危 -1/0/1.5/abc/INT_MAX"） | 整理为 API 参数化数据集，落到对应 negative/positive |
| 8 | "二次确认对话框'取消'路径" | API 层不发起请求 → **跳过**；只保留"确定"路径 |

> 规则 3、4、8 是"该跳"，规则 5、6 是"必测"——这是最容易混淆的边界。规则 1、2 是"基本流配套"，规则 7 是"等价类回收"。8 条规则覆盖一份 UI 用例 90%+ 的场景，剩余 10% 用规则 1+2 的组合即可推导。

## 工作流程

按这个顺序执行，避免漏接口、避免输出与上游 UI 文档错位。

### Step 1 — 收齐输入

向用户确认（或从上下文提取）：

1. **UI 用例文件路径**（必须含 `【测试用例信息】` 标准块；编号 `TC-AR{XX}{YYY}{ZZZ}-{NNN}` 格式）
2. **API 清单文件路径**（推荐 `apitest/<project>/api_inventory.md`；或直接 OpenAPI URL）
3. **输出文件路径**（默认 UI 用例同目录，文件名加 `-api` 后缀）
4. **资源路径前缀**（如 `/api/pm/...`、`/docker-api/system/...`，决定 API URL 拼接方式；下游项目通常按 nginx 反代约定）
5. **后端字段命名约定**（RuoYi 系 = camelCase；其他后端按其约定）
6. **AR 编号前缀风格**（如 `AR-SATP-04` / `AR-GEN-09` / `AR-VFAT-01` 等下游项目自有的前缀，沿用 UI 用例的格式）

### Step 2 — 分类清点

对 UI 用例先做一遍分类清点：每条用例属于规则 1-8 哪一类，标记"可转换"与"应跳过"两类；编号不变，跳过的在文档"已跳过的 UI 用例"段落里集中说明。

不做这一步直接动笔，会出现两种坏味道：
- 漏掉一条本该写的 negative（规则 6 边界没把握住）
- 把纯 UI 项硬塞成 API 用例（规则 3/4/8 边界没把握住，结果产出无法落到接口断言）

### Step 3 — 按 AR 段平行改写

按 UI 文档的章节顺序（一/二/三/四 + AR 子段），**保持完全相同的层级结构**改写。每个 AR 段的开头先列"已跳过的 UI 用例"清单（编号+一句原因），随后是平行的 API 用例。

编号规则：`TC-API-AR{XX}{YYY}{ZZZ}-{NNN}`，9 位需求段 + 3 位流水号沿用 UI 用例号。这样跳过的会让流水号不连续（如 -001、-003、-004），但**便于交叉追溯**——比"重新排号致使 UI 与 API 编号错位"更重要。

### Step 4 — 标准化每条 API 用例

每条 API 用例使用以下模板（与 UI 用例字段对齐，便于人工 diff）：

```
【测试用例信息】
- 用例编号：TC-API-AR{XX}{YYY}{ZZZ}-{NNN}
- 用例名称：<逐字沿用 UI 用例名称 — verbatim，禁止接口化/参数化/改写>
- 需求编号：<沿用 UI>
- 需求点名称：<沿用 UI>
- 用例类型：基本流/异常流
- 所属模块：<沿用 UI>
- 项目进程：<沿用 UI>
- 优先级：<沿用 UI>
- 前置条件：
  1. 操作人员：超级管理员  <越权/数据范围受限用例改为「对齐真实预置的受限账号」，禁默认超管，详见下方 🔴>
  2. 已通过 POST /login 拿到 access_token（受限用例用受限账号登录，非 admin）
  3. <数据预置；与 UI 用例的前置条件对应即可>
- 测试步骤：
  1. <METHOD> <URL>，Header Authorization: Bearer {token}
  2. 请求体 body = {...}
  3. 解析响应 body.code / body.msg / body.data
  4. <按需 GET 列表/详情/操作日志验证>
- 预期结果：
  1. HTTP 200 + body.code=200 + body.data.<id> 非空（或具体断言）
  2. <后续 GET 验证 + 字段匹配>
  3. <操作日志/关联变更日志断言（如适用）>
- 测试数据：
  - <字段>: <值>
```

> **🔴 越权/数据范围受限用例的「操作人员」不能默认超级管理员**：规则 6 的越权类、或前置条件限定了「数据范围受限 / 缺某权限点」的用例，`前置条件` 第 1 条「操作人员」必须改成**对齐真实预置的受限账号**（账号名必须是环境 provision 脚本真实创建的，禁止自造、禁止默认 admin/超管）。否则用全权限 admin 测越权 = 逻辑不可证伪（admin 看得到一切、做得了一切），下游 `ieidev-team:ieidev-api-autotest` 会忠实渲染成假绿。判定锚点是**前置条件/规则归类的限定语**，不是用例名是否点名账号。仅当用例确实是「全部数据范围 / 全权限」时才保留超管。与下游 `ieidev-team:ieidev-api-autotest` 约束 3「测试账号对齐真实预置」同源——本 skill 在文档层先把账号语义写对，下游 pytest 才不会假绿。

> **🔴 用例名称 verbatim 硬契约**：`用例名称` 是**身份/可追溯字段，不是可执行字段**，必须逐字沿用 UI 用例名称——禁止接口化、参数化、加 `token，<METHOD> <端点>` 前缀或任何改写。UI↔API 的 1:1 交叉追溯靠「同编号 + 同名称」两把锁，名称一改写人工 diff 就对不齐；这也与上游 `ieidev-team:ieidev-test-cases` / `kdev-test-cases-v2` 的「用例名称 == 测试点标题 verbatim」契约一致。**接口腔只落在可执行字段**：`测试步骤`（`<METHOD> <URL>`）/ `测试数据` / `预期结果` / `前置条件`。自检：`用例名称` 行去掉编号后应与 UI 源文件同编号用例逐字相等。

字段命名**遵循后端约定（RuoYi 系 camelCase / 其他后端按其约定）**。本骨架只做命名提示，实际字段以 OpenAPI schema 为准——必须在文档前言显式说明这一点，避免下游 pytest 实现时把样例值当真。

### Step 5 — 写收尾段（必备 3 段）

文档末尾必须包含 3 个收尾段，便于人工核对：

1. **第五段：用例集合统计** — AR 总数 / API 用例总数 / 跳过条数 / 准入数（优先级=1）/ 基本流 / 异常流 / 涉及接口分布
2. **第六段：已跳过 UI 用例的索引表** — `| UI 用例编号 | 跳过类别 | 原因（一句话） |`，与每个 AR 顶端的小段一一对应、不可遗漏
3. **第七段：写 API 用例自检清单** — 用 `[x]` checkbox 列出 8-10 条断言项，对应规则 1-8 是否落实

### Step 6 — 自检与交付

最后一遍 grep / 计数验证：
- `grep -c "用例编号：" 输出.md` 应等于（UI 总数 - 跳过数）
- `grep -c "用例类型：基本流"` 与 `grep -c "用例类型：异常流"` 之和等于 API 用例总数
- 输出文件每个 AR 段顶端都有"已跳过的 UI 用例"小段（即使为空也保留段标题）
- 第六段的索引表行数 = 跳过总数（与第五段统计字段一致）

数字对不上必须回到 Step 2 重新清点。

## 常见坑（生成前过一遍）

- ❌ 编号重新排号（TC-API-001 自增）→ 与 UI 用例脱钩，回不到原始 AR；要保持 UI 用例的 9+3 位流水号
- ❌ **把 `用例名称` 接口化（改成「token，GET /xxx <场景>」）→ 与 UI 源名不一致、破坏 1:1 追溯**；`用例名称` 必须 verbatim 沿用 UI，接口腔只进 `测试步骤`
- ❌ 把"二次确认对话框取消路径"也写成 API 用例 → 该路径在 API 层无请求；只覆盖"确定"路径
- ❌ `<script>alert(1)</script>` XSS 用例只写"拒绝路径" → 实际后端常常"接受+转义"，要"拒绝/接受"双路径覆盖
- ❌ "操作日志 4 要素"用 SQL 直查代替 API → 应优先用 `GET /monitor/operlog/list`（黑盒可断言）
- ❌ 字段命名乱猜（`productLineId` vs `product_line_id` 混用）→ 必须按 OpenAPI schema 统一；不确定的字段在前言里挂"以 schema 为准"声明
- ❌ 把列表行渲染色彩 / tag effect / 表头宽度当成 API 断言 → 这些是规则 4 应跳过的
- ❌ 越权/受限用例前置条件照抄模板默认「操作人员：超级管理员 + admin token」→ admin 全权限测不出数据范围裁剪，下游成假绿；必须换对齐真实预置的受限账号
- ❌ 缺第六段索引表 → 用户后续找"为什么这条 UI 用例没出现在 API 文档"时无处对照
- ❌ `优先级:1`（半角冒号）混进 `优先级：1`（全角冒号）→ grep 计数时漏掉，影响第五段准入数

## 输出物清单

每次生成完，给用户一份变更清单：

```
新增：
- <UI 用例同目录>/SOP_测试用例-XXX-api.md
  （N 条 API 用例 / M 条 UI 用例跳过 / 基本流 X 条 / 异常流 Y 条 / 优先级=1 共 Z 条）

校验通过项：
- 编号 TC-API-AR{XX}{YYY}{ZZZ}-{NNN} 与 UI 用例同号
- 每个 AR 段顶端有"已跳过的 UI 用例"清单
- 第五/六/七段（统计/索引/自检）齐备
- 文档前言显式声明"字段名以 OpenAPI schema 为准"
```

## Worked example（下游项目内的标准范本）

**SOP_test 项目实测范本**：
- 输入：`apitest/kdevsec-api-pytest/api_inventory.md`（21 个 tag / 168 接口的清单）+ `test-kdev-test-casev2.3/SOP_测试用例-kdev-test-casev2.3.md`（113 条 UI 用例）
- 输出：`test-kdev-test-casev2.3/SOP_测试用例-kdev-test-casev2.3-api.md`（97 条 API 用例 / 16 条 UI 跳过 / 基本流 52 / 异常流 45 / 优先级=1 共 13）

这份产出是本 skill 的标准范本。**新模块/新项目用该 skill 时可直接对照该文件的章节结构、跳过类别、收尾段格式**——只要下游项目使用相同的 UI 用例模板（`【测试用例信息】` 块 + `TC-AR{XX}{YYY}{ZZZ}-{NNN}` 编号），就能用同一套 7 条规则改写。

**其它下游项目接入本 skill 时**：保持 7 条规则、5 段产出结构不变；按下游项目的 AR 编号前缀、字段命名、API 路径前缀做局部替换即可。
