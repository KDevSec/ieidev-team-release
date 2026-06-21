---
name: codegraph-impact
description: 计算代码变更对安全规范的影响——基于 UA /understand-diff 拿到爆炸半径，再叠加 kdev:security_rule 节点过滤。触发时机：用户说"这段改动有什么安全风险 / 影响了哪些规范 / 安全爆炸半径 / pre-merge 安全审查"，或在 PR 评审/发版前做安全确认时。
---

# /codegraph-impact

> 节点 ID / tag 命名约定：详见 [conventions.md](references/conventions.md)

回答：本次代码改动间接影响了哪些安全规范？哪些规则需要回归测试？

## 前置条件

- `.understand-anything/knowledge-graph.json` 存在并含安全规则节点（即跑过 [`/codegraph-build`](../codegraph-build/SKILL.md)）
- 当前在 git 仓库

## 流程

### Step 1：调 UA 取爆炸半径

调 UA skill `/understand-diff`（即 understand-anything 插件的爆炸半径命令），拿到：
- L1 直接修改的节点
- L2 间接调用链上的节点
- L3 语义关联节点

### Step 2：过滤出安全相关节点

对 L1/L2/L3 每个节点 N：

1. 在 `knowledge-graph.json` 搜以 N 为 source/target 的边
2. 邻居中带 `kdev:security_rule` tag 的 → 受影响规范

### Step 3：聚合报告

```markdown
# 本次变更安全影响报告

## 变更概览

- 修改文件：N
- 直接受影响代码节点（L1）：N
- 间接受影响（L2）：N

## 受影响的安全规范（按严重度倒序）

| 规则 ID | 规则名 | 受影响代码 | 严重度 | 建议 |
|---|---|---|---|---|
| 3.2.1 | 加密算法选择 | crypto/aes.py:encrypt | high | 跑回归 |
| 3.1.1 | 命令操作安全 | api.py:execute | high | 人工复审 |

## 未直接关联但需关注

- 改动碰了 auth 模块，但当前图谱未关联 3.5.x 鉴权规范——建议人工补充关联

## 建议测试

- `tests/test_crypto.py::test_aes_key_size`
- `tests/test_api.py::test_command_injection`
（基于 `tested_by` 边推荐）
```

## 严重度规则

| 信号 | 严重度 |
|---|---|
| L1 节点关联 `kdev:severity:high` 规则 | **high** |
| L1 关联 `kdev:severity:medium` 或 L2 关联 `high` | **medium** |
| 仅 L3 关联 | **low** |

无 severity tag 默认 medium。

## 失败处理

| 现象 | 应对 |
|---|---|
| git 无 diff | 提示 stage 或指定 base ref |
| 受影响节点 0 但代码动了大量 | 图谱过期，跑 `/codegraph-build` |
| UA 报错 | 查 `.understand-anything/` 日志，常见图谱版本不匹配 |

## 不要做

- ❌ 不要不调 `/understand-diff` 直接根据 git diff 行号瞎报——失去图谱间接关联价值
- ❌ 不要在没建图时调本 skill——先要求建图
- ❌ 不要把 L3 语义关联等同 L1 高危——分级输出
