---
description: 目标总编排——把一个高层目标 LLM 路由到命名生命周期模板，渲染一屏编排结论人确认，再主会话顺序链式调 /ieidev-team:flow-driver 跑通跨数字员工的交付流水线（MVP：full-delivery 三段：需求→开发→测试）
argument-hint: <高层目标>
---

# /ieidev-team:goal

把"一个高层目标"端到端编排成跨数字员工的交付流水线。调用本命令即加载 goal skill（总编排 / 目标总编排 / 一个目标跑通需求到测试）。

## 用法

```
/ieidev-team:goal 做用户认证功能
/ieidev-team:goal 给 X 项目加一个导出 CSV 的功能
/ieidev-team:goal 实现订单退款流程并出测试
```

## 参数

- `<高层目标>`：必填。一句自然语言描述的高层交付目标（不是单员工任务——单员工跑用 `/ieidev-team:flow-driver`）。
- `--auto`：可选。无人值守模式——跳过需求澄清问答、confirm 停靠、drive 段人闸停靠（不写 pause-gate 标记）。适合已对齐方案的全自动场景，自负风险。

## 三段

1. **plan**：LLM 把目标对号入座到 `lifecycles/*.yml` 模板，产 delivery-plan（封闭 schema）。confidence 低或贴两模板时必填 runner_up。
2. **confirm**：`ieidev_team.lint.validate` 校验过 → `confirm.render_screen` 渲染一屏编排结论，人确认 / 微调（`apply_edit` 循环）。
3. **drive**：冻结 delivery-plan 落 `features/<slug>/delivery-plan.yml`，主会话**顺序**调 `/ieidev-team:flow-driver` 跑各段（同 slug 接力 + 停人闸），各段评审由 flow-driver 内部按 node-table 触发。

## 硬约束

你（主控）是目标总编排器，**只能主会话跑**——子 agent 不能再开子 agent，所以**绝不**把 `/ieidev-team:flow-driver` 当 `Agent()` 子 agent 派出去（那样它就无法再派 capability agent）。drive 段在主会话里**顺序调** `/ieidev-team:flow-driver`（它也跑主会话，内部才派 capability agent）。

参数原文：`$ARGUMENTS`

按 `goal` skill 的 SKILL.md 步骤执行。
