# Output Templates §6.1 – §6.11

Default language: 中文. Section IDs are stable across modes — you may omit sections per the §4 mode mapping in SKILL.md, but never renumber.

## §6.1 Header

```
# 测试设计文档：[被测对象]
- 测试基础(Test Basis)：[需求/规约/产品说明/用户文档/源码 路径]
- 范围(Scope)：[产品说明? 用户文档? 软件? 各域简要说明]
- 模式(Mode)：feature-spec | api-contract | full-conformity
- 选用技术：[列表 + 一句话理由]
- 风险等级：[High/Medium/Low + 理由]
- 测试环境：[OS/浏览器/网络/数据规模/账号体系/外部依赖版本]
- 测试人员独立性：[内部自测 / 独立 QA / 第三方测评机构]
- 测试数据来源：[生产脱敏 / 合成 / 手工编排]
- 适用标准：ISO/IEC/IEEE 29119-4 + GB/T 25000.51-2016
```

## §6.2 Quality Coverage Matrix

See `references/quality-characteristics.md` for the row template and per-sub-characteristic minimum testing approach.

```
| 质量特性 | 子特性     | 在范围? | 关联条件      | 用例数 | 备注                        |
|----------|-----------|---------|---------------|--------|-----------------------------|
| 功能性    | 功能完备性  | 是      | COND-001..010 | 18     | 覆盖产品说明全部功能         |
| 性能效率  | 时间特性   | 是      | COND-101      | 3      | p50<200ms / p95<500ms       |
```

## §6.3 Test Conditions

```
| ID       | 测试条件描述                | 关联需求/规约 | 关联子特性  |
|----------|-----------------------------|---------------|-------------|
| COND-001 | 用户使用合法凭证登录          | REQ-AUTH-1    | 功能正确性   |
| COND-101 | 登录接口 p95 响应 < 500ms     | NFR-PERF-1    | 时间特性     |
```

## §6.4 Coverage Items (按技术分组)

```
| CI ID    | 技术  | 覆盖项描述                  | 关联条件 |
|----------|-------|---------------------------|----------|
| CI-EP-01 | EP    | 密码长度 ∈ [8,64] 有效等价类 | COND-001 |
| CI-BV-01 | BVA   | 密码长度 = 8（下边界）       | COND-001 |
| CI-PERF-1| Bench | p95 ≤ 500ms @ 100 并发     | COND-101 |
```

## §6.5 Test Cases

每条用 29119-4 + 25000.51 全字段。Coverage / Quality Sub-char / Domain 三栏不可省 — 双标准对接的硬约束。

```
TC-[ID] [简短标题]
---
目标(Objective)：[一句话]
覆盖项(Coverage)：[CI-NN, ...]                          ← 必填
质量子特性(Quality Sub-characteristic)：[功能正确性 / 时间特性 / ...]   ← 必填
所属域(Domain)：[产品说明 / 用户文档 / 软件]              ← 必填
技术(Technique)：[EP/BVA/DT/ST/Pairwise/MCDC/...]
优先级(Priority)：P0/P1/P2/P3   依据：[影响×可能性]
前置条件(Preconditions)：...
测试数据(Test Data)：...
测试步骤(Steps)：1...2...3...
预期结果(Expected Result)：[明确可断言；区分 UI/API/DB/日志多面]
后置条件(Postconditions)：[资源回收 / 状态回滚]
```

If `--example` was given, render the table per the user's example layout — but each row must still carry the three mandatory fields above (as adjacent columns or as a suffix on the title). See `references/template-override.md`.

## §6.6 Product Description & User Documentation Tests (full-conformity only)

针对**产品说明的每条声明**和**用户文档的每个步骤**：

```
TC-DOC-[ID]
---
所属域：用户文档 | 产品说明
被测声明：[复制原文，标出处]
检查项：
  - 是否完整（无缺漏）
  - 是否正确（与软件实际行为一致）
  - 是否一致（不同文档之间不矛盾）
  - 是否易理解（术语 / 步骤 / 截图清晰）
验证方式：[实操执行文档步骤 / 双向对照软件 / 评审清单]
预期：声明为真且与软件一致
```

产品说明里"性能"、"兼容性"等量化承诺必须有对应 TC 验证（承诺"支持 1000 并发"就要有 1000 并发的负载测试用例）。

In `feature-spec` / `api-contract`, skip §6.6 with one line reason: e.g., "用户文档尚未发布，本期不在范围；待 docs PR 合入后单独补 TC-DOC 集"。

## §6.7 Coverage Summary

```
| 维度               | 完成准则                          | 覆盖率/达成 |
|--------------------|-----------------------------------|-------------|
| EP                 | 所有等价类覆盖                    | 100%        |
| BVA                | min±1 / max±1 全覆盖              | 100%        |
| DT                 | 所有规则行覆盖                    | 100%        |
| ST 0-switch        | 所有合法转换 + 所有非法转换尝试   | 100%        |
| 8×31 质量特性      | 在范围子特性 100% 至少 1 用例     | 计算填入    |
| 产品说明声明        | 每条声明 ≥1 TC                    | 计算填入    |
| 用户文档步骤        | 每个 procedure ≥1 TC              | 计算填入    |
```

## §6.8 Conformity Evaluation (25000.51 §7)

```
| 要求来源              | 要求项               | 关联用例     | 实测结果 | 一致性结论     |
|-----------------------|----------------------|--------------|----------|----------------|
| 产品说明 §2.1         | "支持 1000 并发"     | TC-101..103  | 实测 850 | 不符合         |
| 用户手册 §3.5         | 安装步骤 1-7         | TC-DOC-01    | 通过     | 符合           |
| 需求 REQ-AUTH-1       | 登录鉴权             | TC-001..004  | 通过     | 符合           |
| GB/T 25010 信息安全性 | OWASP Top 10         | TC-SEC-01..10| 1 失败   | 部分符合       |
```

结论用词只能是 **符合 / 部分符合 / 不符合**，并给出依据用例 ID 与实测数据。

In `feature-spec` / `api-contract` modes you may use a lighter form: per-FR pass/fail before any measurements exist (placeholder until execution).

## §6.9 Requirements Traceability Matrix（双向）

```
| 来源                  | 测试条件 | 覆盖项                 | 测试用例           |
|-----------------------|----------|------------------------|--------------------|
| REQ-AUTH-1            | COND-001 | CI-EP-01, CI-BV-01..02 | TC-001..TC-004     |
| 产品说明 §2.1         | COND-101 | CI-PERF-1              | TC-101..103        |
| GB/T 25010 易用性     | COND-201 | CI-A11Y-1              | TC-A11Y-01..05     |
```

## §6.10 Defect Categorisation (placeholder unless execution data exists)

```
| 缺陷 ID | 描述 | 严重度(致命/严重/一般/轻微) | 关联用例 | 关联要求 | 状态 |
```

## §6.11 Risk & Out-of-Scope

显式列出未覆盖的子特性、未测的产品说明条目、被裁剪的范围。隐藏未覆盖项是反 25000.51 的 — 即使是负面信息也必须暴露。
