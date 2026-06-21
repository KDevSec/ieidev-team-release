# Worked example — 1 FR end-to-end through the 29119-4 pipeline

This shows the shape of output every test case should reach. Reading this once gives the model a concrete target.

## Input (the "Test Basis")

A single requirement from a feature spec:

> **FR-016**: 当 `assessment_status` 被设为"已完成"时，`assessment_result`（通过/条件通过/不通过）与 `assessment_date`（合法日期）MUST 必填；从"已完成"回退至其他状态时，系统 MUST 弹出二次确认"将清空测评结果与测评时间，是否继续？"——用户确认后清空两字段，用户取消则保持原状态。

## Step 1 — Identify the test basis

- Test basis: FR-016 (state machine + conditional required fields)
- Domain: 软件 (the executable). 产品说明 if FR-016 is also documented externally. 用户文档 if release notes describe it.
- Mode: `feature-spec` (internal PRD, no published docs yet)

## Step 2 — Quality Coverage Matrix entry

```
| 质量特性 | 子特性     | 在范围? | 关联条件          | 用例数 | 备注                                    |
|----------|-----------|---------|-------------------|--------|-----------------------------------------|
| 功能性    | 功能正确性 | 是      | COND-016a..016c   | 7      | 状态机 + 条件必填 + 二次确认               |
```

## Step 3 — Derive Test Conditions

```
| ID         | 描述                                                | 关联需求 | 关联子特性  |
|------------|----------------------------------------------------|----------|-------------|
| COND-016a  | 测评状态机的合法转换 + 非法转换                      | FR-016   | 功能正确性  |
| COND-016b  | "已完成"时 assessment_result + assessment_date 必填 | FR-016   | 功能正确性  |
| COND-016c  | "已完成→其他"回退弹二次确认；确认清空 / 取消保持      | FR-016   | 功能正确性  |
```

## Step 4 — Derive Coverage Items (apply techniques)

This is where 29119-4 technique selection bites. State machine + conditional required → **State Transition + Decision Table**.

```
| CI ID    | 技术 | 覆盖项描述                                          | 关联条件   |
|----------|------|----------------------------------------------------|------------|
| CI-ST-01 | ST   | 转换：未开始 → 进行中（合法）                        | COND-016a  |
| CI-ST-02 | ST   | 转换：进行中 → 已完成（合法 + 触发必填）             | COND-016a  |
| CI-ST-03 | ST   | 转换：已完成 → 进行中（合法 + 触发二次确认）         | COND-016a  |
| CI-ST-04 | ST   | 转换：已完成 → 未开始（合法 + 触发二次确认）         | COND-016a  |
| CI-ST-05 | ST   | 非法转换：通过 API 直传枚举外值（防御）              | COND-016a  |
| CI-DT-01 | DT   | 状态=已完成 ∧ result=空 → 拒绝                       | COND-016b  |
| CI-DT-02 | DT   | 状态=已完成 ∧ date=空 → 拒绝                         | COND-016b  |
| CI-DT-03 | DT   | 状态=已完成 ∧ result=合法 ∧ date=合法 → 接受         | COND-016b  |
| CI-DT-04 | DT   | 二次确认=确认 → result/date 清空                     | COND-016c  |
| CI-DT-05 | DT   | 二次确认=取消 → 状态/result/date 保持                 | COND-016c  |
```

## Step 5 — Write Test Cases

```
TC-016-01 编辑版本，状态从"进行中"置"已完成"+合法 result+合法 date
---
目标：验证合法的"完成"转换被接受。
覆盖项：CI-ST-02, CI-DT-03
质量子特性：功能正确性
所属域：软件
技术：ST + DT
优先级：P1   依据：核心状态机正向路径，影响高，可能性高。
前置：版本 V 测评状态=进行中。
测试数据：result=通过；date=2026-05-07。
步骤：1. 打开 V 编辑表单；2. 状态选"已完成"；3. result 选"通过"；4. date 选 2026-05-07；5. 保存。
预期：API 200；DB 中 V.assessment_status=completed, result=pass, date=2026-05-07；操作日志一条 update。
后置：删除 V（teardown）。

TC-016-02 编辑版本，状态置"已完成"但 result 为空
---
目标：验证"已完成"必填校验拒绝缺失 result。
覆盖项：CI-DT-01
质量子特性：功能正确性
所属域：软件
技术：DT (negative)
优先级：P2   依据：错误路径，影响中，可能性中。
前置：版本 V 测评状态=进行中。
步骤：1. 打开编辑；2. 状态选"已完成"；3. 不填 result；4. date 选合法日期；5. 保存。
预期：API 400；中文错误"测评结果与测评时间在已完成状态下必填"；DB 不变。
后置：— 。

TC-016-03 状态从"已完成"回退至"进行中"+二次确认=确认
---
目标：验证回退清空字段且二次确认弹框。
覆盖项：CI-ST-03, CI-DT-04
质量子特性：功能正确性
所属域：软件
技术：ST + DT
优先级：P1   依据：状态机回退路径，数据丢失风险，影响高。
前置：V 测评状态=已完成, result=通过, date=2026-05-07。
步骤：1. 打开编辑；2. 状态改回"进行中"；3. 弹框出现，文案"将清空测评结果与测评时间，是否继续？"；4. 点确认；5. 保存。
预期：弹框文案逐字匹配；保存后 DB 中 V.status=in_progress, result=NULL, date=NULL；操作日志一条。
后置：— 。

[TC-016-04 ~ TC-016-07 略：覆盖 CI-ST-01, CI-ST-04, CI-ST-05, CI-DT-02, CI-DT-05]
```

## Step 6 — RTM entry

```
| 来源    | 测试条件          | 覆盖项                | 测试用例        |
|---------|-------------------|----------------------|----------------|
| FR-016  | COND-016a..016c   | CI-ST-01..05, CI-DT-01..05 | TC-016-01..07 |
```

## What this example demonstrates

- Density: 1 FR with state-machine + conditional → 7 TCs (within the §6 band)
- 29119-4 technique routing: state machine → ST mandatory + DT for conditional rules
- 25000.51 attribution: every TC carries Quality Sub-char + Domain
- Negative cases not just "拒绝" — assert the exact 中文 error string and DB invariant
- 后置/teardown: every TC cleans up so it can re-run idempotently
- Priority reasoning made explicit, not just a number
