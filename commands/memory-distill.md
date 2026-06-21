---
description: 知识蒸馏统一入口——按 .ieidev/memory/ 里每条记录的 subject 字段路由数据：subject=project 的走"促沉淀"阶段让用户挑成熟规则写入 docs/ 反哺项目；subject=skill/plugin/tool/methodology/collaboration 的走"打数据集"阶段全量打包到 .ieidev/memory/dataset/ 三个 markdown 切片，喂给对应 skill 的维护方做自主进化。markdown 既给人看也给机器训，两条数据路径一个命令完成。绝不输出 JSONL（架构终态决策）。触发短语：导出蒸馏数据 / 蒸馏 / distill / 把记录弄出来训练 / 导出 markdown / 沉淀到 docs / 沉淀知识 / 反哺项目 / 反馈给 skill / promote。
argument-hint: [无参数 | --out <dir> | --no-sanitize | --skip-promote]
---

# /ieidev-team:memory-distill

**知识蒸馏统一入口** —— 把 `.ieidev/memory/` 里的原始记录按 subject 字段**自动路由到两条数据路径**：

```
.ieidev/memory/ 全量原始记录
       │
       ↓ 按 subject 字段路由
       │
       ├── subject = project                ──→ promote 阶段（人工挑选）
       │   (项目内方法论 / 决策 / 高分           ──→ docs/ 项目知识库
       │    Step / 高频踩坑)                     ──→ 抽象成规则反哺项目
       │
       └── subject = skill:X / plugin:X      ──→ dataset 阶段（自动打包）
           tool:X / methodology:X /              ──→ dataset-skill-feedback-by-subject/<slug>.md
           collaboration:X                       ──→ 喂给对应 skill 维护方做自主进化
                                                 ──→ 同时进 dataset-full.md / misalignment.md
```

**核心设计**：subject 字段不只是数据标签，是**路由器**。打分时确定的 subject 决定这条数据下游怎么消费。

## 探查 record_mode

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory_config.py"`

## 阶段 1：promote（subject=project 的条目 → 人工挑选 → docs/ 反哺项目）

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/lib/promote-list.py"`

### 你的任务（promote 阶段）

根据上面 promote-list 的输出：

1. **列出所有 pending 条目** —— 这些都是 subject = project 的候选（项目内方法论 / 决策 / 高分 Step / 高频踩坑等）
2. **向用户询问**："这些条目哪些要沉淀到 `docs/` 反哺项目？（全选 / 指定编号 / 全跳过 / 跳过整个 promote 阶段）"
3. 对用户确认要沉淀的每条：
   - 读源条目原文
   - **抽象成规则 / 教程 / ADR** 写入 `promote_target` 指向的 `docs/` 文件（允许合并相似条目、改写、删过期内容——这是项目永久资产，要"加工"）
   - 更新源条目 frontmatter：`promote_status: done` + `promote_target: <path>` + `promote_date: YYYY-MM-DD`
4. 对用户确认跳过的条目：
   - 更新源条目 frontmatter：`promote_status: skipped`，`promote_target` 存理由
5. **promote 阶段完成后**执行：
   ```bash
   touch .ieidev/memory/.last-promote
   ```

### 推荐 docs/ 去向（按源条目类型）

| 源条目（subject=project） | 推荐 docs/ 去向 |
|---|---|
| 改进建议.md R-NNN 定稿条目 | `docs/05-报告/实战总结-<项目名>.md` 反思章节 |
| 方法论铁规.md | `docs/08-开发规范.md` 或项目 `CLAUDE.md` |
| 踩坑日志.md G-NNN 高频类 | `docs/04-架构/踩坑索引.md` |
| 决策日志.md Q-NNN 架构级 | `docs/04-架构/ADR-NNN-<slug>.md` |
| 执行日志.md Step 4.5+ 高分经验 | `docs/05-报告/实战项目总结.md` |
| 日常 G-NNN / Step 现场 | **不沉淀**（这些是过程痕迹，留给 dataset 阶段全量打包） |
| **F-NNN（skill 反馈，subject != project）** | **不在本阶段处理** —— F-NNN 的 subject 是 skill/plugin/tool 等，自动走 dataset 阶段的 by-subject 切片 |

**严禁替用户拍板** —— 若用户拒绝某条，标 `skipped` 即可，不要硬推。
**也可以全跳过** —— 用户答"跳过 promote"或没有 pending 条目时，直接进阶段 2。

## 阶段 2：dataset（按 subject 切片 → 喂给训练管道 / skill 自主进化）

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/lib/distill.py" $ARGUMENTS`

### 你的任务（dataset 阶段）

根据上面 `distill.py` 的产出：

- **如果 record_mode == "hybrid"** 且 `Agent`/`Task` tool 可用且数据量大（>100 条 / >50KB）：
  - bash 命令已经把切片产出文件写盘了；stdout 也已在主会话上下文
  - 可以选择再开一个 subagent 做摘要避免主会话 Read 大文件
  - 否则直接读 stdout 给用户做汇报

- **如果 record_mode == "inline"** 或 Agent tool 不可用：
  - 直接读上面 `distill.py` 的 stdout，整理成给用户的报告

### 向用户汇报（两阶段统一）

1. **promote 阶段（subject=project 路径）**：
   - 抽象成规则反哺项目：N 条沉淀到 `docs/` —— 列文件路径
   - 跳过：M 条（列编号 + 理由）
   - 还有 K 条 pending

2. **dataset 阶段（subject=skill/plugin/tool 路径）**：
   - 三个切片包（确保不是 .jsonl 是 .md）：
     - `dataset-full.md`（全量按时间，**含刚标的 promote 标签，下游可按此分级**）
     - `dataset-misalignment.md`（差值 ≥ 1.5 的 Step，对齐数据顶级原料）
     - `dataset-skill-feedback-by-subject/<slug>.md`（**按 subject 一个文件**，喂给对应 skill 维护方做自主进化）
   - 每类切片的条目数 + sanitize 验证状态
   - 下游消费方式：直接喂蒸馏管道（Axolotl / Unsloth / HuggingFace SFT trainer 都原生吃 markdown）

3. **subject 路由效果**（如本次有 promote 标记）：
   - "刚标的 N 条 `promote_status: done` 已自然进 dataset-full.md，下游训练可按这个字段过滤'人工沉淀过的成熟样本' vs '原始过程样本'"

## 设计哲学：subject 是路由器

旧设计（v0.x 之前）有两个独立命令：`/ieidev-memory-promote`（人沉淀）+ `/ieidev-memory-export-md`（机器训练）——把"人和机器"当成两套数据通道。

新设计（统一为 `/ieidev-team:memory-distill`）—— 因为：

1. **打分时确定的 subject 字段已经是天然的路由器** —— subject=project 的数据天然属于"反哺项目"路径，subject=skill:X 的数据天然属于"喂给 skill 维护方"路径
2. **markdown 既给人看也给机器训**，输出格式相同，没必要分两个命令
3. **两条路径互补**：promote 是"挑成熟规则反哺项目"（加工 / 改写 / 抽象），dataset 是"原文打包训练用"（保留 reasoning trace 不改写）。两阶段顺序跑能让 dataset 自然包含 promote 标签

## 关键约束

- **绝无 .jsonl 文件产出** —— 架构终态决策（详见 SKILL.md "下游"段 + `references/markdown-切片导出.md`）
- 原 `.ieidev/memory/*.md` 在 dataset 阶段**不修改**（promote 阶段会改 frontmatter 标记，这是预期的）
- 默认开启 sanitize；**严禁向用户建议加 `--no-sanitize` 后分享数据**（仅测试用）
- promote 阶段**严禁替用户拍板** —— 必须问"全选 / 指定 / 跳过"
- 两阶段都跑完才算完成；如果中途 promote 失败也要继续 dataset 阶段（不要让一个阶段失败阻塞另一个）

## 参数

- 无参数：跑两个阶段，promote 输出到 `./docs/`，dataset 输出到 `./.ieidev/memory/dataset/`
- `--out <dir>`：自定义 dataset 输出目录
- `--no-sanitize`：**仅测试用**，跳过 dataset 阶段的 PII 脱敏
- `--skip-promote`：跳过阶段 1，只跑 dataset（适合 promote 已批处理完想单独重跑数据集时）

## 详见

- `references/markdown-切片导出.md` —— dataset 切片包内容 / 筛选规则 / sanitize / 不引入 JSONL 论证
- `references/subject-推断与评分裂解.md` —— subject 字段的 L1/L2/L3 自动推断（数据路由的源头）
- `references/skill-反馈通道-F.md` —— F-NNN 为什么直接进 dataset by-subject 切片（不走 promote）
- `references/subagent-落盘机制.md` —— hybrid / inline 两档配置
