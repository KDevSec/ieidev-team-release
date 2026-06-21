---
description: 用数字员工按编排 SOP 端到端跑一个任务——主控扮演编排角色驱动 ieidev-core 引擎，逐节点派业务 agent、判 gate、调 CLI 落账，直到 terminal 或 BLOCKED
argument-hint: <employee-id> --task <task-desc-or-path> [--auto] [--slug <slug>]
---

# /ieidev-team:flow-driver

把"一个数字员工按自己的 SOP 走完一个任务"变成一条可自驱的循环。

## 用法

```
/ieidev-team:flow-driver dev-engineer --task "UED6改造考题" --auto
/ieidev-team:flow-driver dev-engineer --task ~/Projects/exam-ued6/EXAM-PROMPT.md --slug ued6-exam
/ieidev-team:flow-driver dev-engineer --task "实现用户认证模块"
```

## 参数

- `<employee-id>`：必填。员工 canonical id（如 `dev-engineer`），从 staff.yml 反查路由。
- `--task <desc-or-path>`：必填。任务描述文本，或考题/需求文档的文件路径。
- `--auto`：可选。开启 Auto Mode，所有 gate 自决不停等用户确认。
- `--slug <slug>`：可选。flow slug（默认从任务描述自动生成）。

## 你的任务

调用 `flow-driver` skill，按 SKILL.md 的步骤执行：

1. **Bootstrap**：读 staff.yml 路由员工 → 设 PYTHONPATH + NT → resume 探断点 / init 新 flow
2. **Driving Loop**：next-step → 判断节点类型 → 派 agent / 判 gate / complete → 循环
3. 直到 terminal（完成）或 blocked（停住报告）

关键：你（主控）是编排器——不要试图把编排下放给 dev-engineer-orchestrator agent 自跑（子 agent 不能再开子 agent）。

参数原文：`$ARGUMENTS`

按 `flow-driver` skill 的 SKILL.md 步骤执行。