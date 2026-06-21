# triggers 写法规范

## 什么时候读本文件

- 写新 G-NNN / Step / 方法论铁规 / 项目 spec 条目时，不确定 `triggers:` 该填什么
- 发现已有条目没标 triggers，想批量补标时
- 需要查哪些文件参与 UserPromptSubmit hook 的 triggers 扫描时

## 我不负责什么

- **各条目自身的字段格式** → `references/六类记录-schema.md`
- **hook 如何做匹配与去重的具体实现** → `references/自动化机制-hooks.md`

---

## 为什么重要

`triggers:` 字段是**智能召回的锚点**。UserPromptSubmit hook 扫 `.ieidev/memory/` 里所有带 `triggers:` 的条目，用 literal substring 匹配用户 prompt，命中就注入 `<ieidev-memory-recall>` 指针给 Claude。没有 triggers 字段 → 这条记忆永远不会被自动召回（只能靠 Claude 主动 Read 或用户显式问到）。

核心 ROI：**让已经踩过的坑不再重复、做过的决策能自然复用**。比如 G-012 记了"pnpm install 在 workspace 根目录会漏装子包依赖"；如果没标 triggers，下次用户说"跑 pnpm install 报错了"，Claude 会重新 debug 一遍；标了 triggers: ["pnpm install", "workspace 依赖"] 之后，Claude 一看到用户的 prompt 就被自动注入指针，直接知道"这坑之前栽过，解法是 `pnpm -r install`"。

---

## 谁该标、Claude 写条目时就该顺手标

| 条目类型 | Claude 写入时顺手做 |
|---|---|
| 新 G-NNN 踩坑 | 在 `## G-NNN: 标题` 下一行加 `triggers: [...]` |
| 新 Step（完成时顺手） | 在 `## Step <ts>-<who>: 标题` 下一行加 `triggers: [...]` |
| 方法论铁规 新规则 | 在 `## 规则名` 下一行加 `triggers: [...]` |
| 项目级 spec（`constitution.md`/`spec.md` 等） | 人写，放文件 frontmatter 或每条规则下 |

## 三种合法格式

**行内 JSON 数组（推荐）**：
```markdown
## G-012: pnpm install 在 workspace 根目录会漏装子包依赖
triggers: ["pnpm install", "pnpm i", "workspace 依赖"]
日期：2026-04-15
```

**简明逗号分隔**（适合短关键词）：
```markdown
## Step main-23: 实现采集器核心循环
triggers: 采集器, 核心循环, collector
日期：2026-04-19
```

**YAML 多行列表**（适合 frontmatter，用在 spec 文件上）：
```markdown
---
triggers:
  - 架构决策
  - 技术选型
  - 不可逆
---
# 项目宪章
```

---

## 关键词选择原则

- **3-5 个关键词**：少了召回率低，多了污染其他条目的匹配
- **用用户会说的口语词**：
  - ✅ "pnpm install"（命令名）、"workspace 依赖"（场景）
  - ❌ "ERR_WORKSPACE_PKG_NOT_FOUND"（错误码太特殊）
  - ❌ "error"、"bug"（太泛，会匹配所有 bug 讨论）
- **中英文都要**：`["pnpm install", "workspace 依赖"]`—— 用户可能用任一种
- **场景词 + 特征词**：G-014 aiohttp 代理 ClientDisconnected → `["aiohttp", "proxy", "ClientDisconnected"]`——既覆盖"aiohttp"的模糊讨论，也覆盖"ClientDisconnected"的具体报错

---

## 渐进式披露原则

召回注入**只含编号 + 标题 + 文件路径**，不塞全文。Claude 看到注入觉得相关自己 Read 细节。好处：
- 注入一条只 ~30 token，三条 ~100 token
- 不相关时 Claude 一眼扫过即可忽略，不浪费后续推理
- Read 一次胜过强塞内容（Claude 有权决定读不读）

---

## 项目级 spec 文件在哪

UserPromptSubmit hook 扫以下 7 个约定路径（存在即扫）：

```
项目根：
  constitution.md / spec.md / principles.md / AGENTS.md

Spec Kit 风格：
  .specify/constitution.md

docs 下：
  docs/constitution.md / docs/principles.md
```

每个文件支持两种写法：
- **文件级 frontmatter**：整个文件作为一条"规则"（适合单文件单规则）
- **行内 `## 规则名` + triggers 行**（适合单文件多规则）

两种可以混用。

---

## Session 去重

同一 session 同一条记忆**只注入一次**。实现机制：`.ieidev/memory/state/trigger-sessions.json`，TTL 60 分钟，过期 session 自动清理。避免用户反复提到同一关键词时刷屏。

---

## 常见错位

- ❌ **在每日汇总里标 triggers**：每日汇总是索引，不是原始记忆。triggers 应标在源文件（执行日志/踩坑日志）
- ❌ **写代码块举例时触发误扫**：有 sanitize 保护，Claude 写 G-NNN 条目时即使正文里放代码块举例也不会误触发（sanitize 会 strip 代码块）
- ❌ **在 Step 条目标了 triggers 但日期很老**：只有"今日/昨日"的 Step 才参与召回，`2026-03-01` 的老 Step 即便标了 triggers 也不会自动召回（属历史数据，靠每日汇总或 Claude 主动 Read）
