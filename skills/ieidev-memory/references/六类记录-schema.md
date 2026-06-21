# 六类记录 schema 详细规范

## 什么时候读本文件

- 第一次写某类记录、不确定字段格式时
- 需要查"模型他评 / 用户评分 / 双评分锁定 / 当前状态 frontmatter 字段"等具体要求时
- 审阅历史记录条目是否规范时

## 我不负责什么

- **什么时候触发记录** → 回 SKILL.md 的"六类记录触发时机总览"
- **triggers 关键词怎么选** → `references/triggers-写法.md`
- **记录写完后如何召回** → `references/triggers-写法.md` + `references/自动化机制-hooks.md`

---

## v0.17+ ID 格式（Q-020）— 新编 Q/G/R/F 全走时间戳形

**新编条目统一用 `mint_record_id("<Type>", state_dir)` 生成 ID**，格式为 `<Type> <YYYYMMDD-HHMMSS>-<who>`（本地时间戳）。

```python
from step_id import mint_record_id
from pathlib import Path
q_id = mint_record_id("Q", Path(".ieidev/memory/state"))  # => "Q 20260613-150000-ly"
g_id = mint_record_id("G", Path(".ieidev/memory/state"))  # => "G 20260613-150100-ly"
r_id = mint_record_id("R", Path(".ieidev/memory/state"))  # => "R 20260613-150200-ly"
f_id = mint_record_id("F", Path(".ieidev/memory/state"))  # => "F 20260613-150300-ly"
```

**现存 `Q-NNN` / `G-NNN` / `R-NNN` / `F-NNN` 顺序 ID 冻结**——不再 mint，但 `parse_record_id` 继续双认（向后兼容）。各 § 的格式示例保留旧格式作为历史文档，新编条目请用时间戳形。

---

## status 字段语义（钉死 · Q-决策）

**`status` = 评分/销账态，合法值只有 4 种**：

| 值 | 含义 |
|---|---|
| `open` | 进行中 / 待评分（默认，缺失等价 open） |
| `scored` | 评分完整已闭环 |
| `voided-faded` | 褪色补录占位，不强求补 |
| `voided-r-<NNN>` | 显式 R-NNN 销账（NNN 为数字，如 `voided-r-003`） |

🚫 **`status` ≠ 修复态**。踩坑/任务的**修复进展**（`fixed` / `mitigated` / `处置中` / 修复日期）
**不写进 status**——写进 body 的「解决 / 处置进展」段，加一行如：

> `**修复态**：fixed（2026-06-10，加 n9c-increment gate）`

理由：status 被 hook（`step_completeness` 欠评扫描、`distill` misalignment 切片）当**评分态枚举**消费；
把修复态塞进 status 会让评分态语义漂移、下游误判。**不新增 `fix_status` 字段**（YAGNI——目前无消费者；
修复态是人读的 body 叙述，不需要机读枚举）。

> 防御：`status_schema.warn_unknown_status()` 在 `step_completeness` / `distill` 遇非枚举 status 时
> 告警一行（不静默当未评分）。`status_schema.is_voided_status()` 认 `voided-faded` 与 `voided-r-<数字>`。

---

## 1. 决策日志.md（Q-NNN / Q 时间戳形）

**何时写**：凡是"智能体不应该替用户拍板"的问题——技术栈选择、需求边界、trade-off、命名、不可逆操作前的确认。**不记**：纯信息性问题（"这个文件在哪"）。

**格式**（以下示例为旧顺序 ID，**仅供参考；新编条目用时间戳形，如 `## Q 20260613-150000-ly: 标题`**）：
```markdown
## Q-007: 是否在 MVP 阶段引入 Docker？  <!-- legacy 顺序 ID，冻结 -->
日期：2026-04-15
status: open | scored | voided-faded | voided-r-nnn
promote_status: pending | done | skipped
promote_target: docs/XX                    # 若已沉淀则填写
promote_date: 2026-04-24                   # 若已沉淀则填写
选项：
- (A) 引入 —— 部署一致性好，但增加学习/构建成本
- (B) 不引入，裸机 Node.js —— 简单，但后续换机器要重装
用户选择：B
理由：Sprint 0 只一人用，换机器概率低，不值得换 Docker 的复杂度
```

**为什么有效**：带选项和理由的决策能被未来的智能体"理解并延伸"，而不是死记结论。下次遇到类似选择时，能看出之前的取舍逻辑是否仍然成立。

### 条目状态与沉淀字段（v0.7+）

Q-NNN 条目的 frontmatter 可加以下字段（缺失等价于默认值，历史条目无需手工迁移）：

**status**（销账）：决策是否已完整评分
- `open` —— 进行中 / 待评分（默认）
- `scored` —— 评分完整已闭环
- `voided-faded` —— 褪色补录占位，不强求补
- `voided-r-nnn` —— 显式 R-NNN 销账
- ⚠️ status **只表示评分/销账态，不表示修复态**；决策的后续进展/修订写 body，勿塞 status（统一语义见顶部「status 字段语义（钉死）」）。

**promote_\* 字段**（沉淀）：决策是否沉淀到团队文档
- `promote_status: pending | done | skipped` —— 默认 pending
- `promote_target` —— 沉淀后填写目标路径（如 `docs/04-架构/ADR-XXX.md`）；skip 时填理由（如 "个人偏好，无团队价值"）
- `promote_date` —— 沉淀完成日期（YYYY-MM-DD）

> 字段语义详见 SKILL.md「条目状态与沉淀字段（v0.7+）」节。

---

## 2. 踩坑日志.md（G-NNN / G 时间戳形）

**何时写**：任何"我绕了弯才发现"的事——配置踩坑、API 行为和文档不符、工具链 bug、命令语法错误、依赖冲突。

**格式**（以下示例为旧顺序 ID，**仅供参考；新编条目用时间戳形，如 `## G 20260613-150100-ly: 标题`**）：
```markdown
## G-012: pnpm install 在 workspace 根目录会漏装子包依赖  <!-- legacy 顺序 ID，冻结 -->
triggers: ["pnpm install", "pnpm i", "workspace 依赖"]
日期：2026-04-15
status: open | scored | voided-faded | voided-r-nnn
promote_status: pending | done | skipped
promote_target: docs/XX                    # 若已沉淀则填写
promote_date: 2026-04-24                   # 若已沉淀则填写
现象：子包 import 报错 "Cannot find module 'xxx'"，package.json 里明明写了
原因：pnpm 默认只装 root，需要 --recursive 或在子包目录单独跑
解决：统一在子包里跑 `pnpm install`，或 root 跑 `pnpm -r install`
```

**`triggers:` 必须有**：下次用户再说"跑 pnpm install 报错了"时，UserPromptSubmit hook 就能自动召回 G-012 的指针给 Claude。标 triggers 的规范见 `references/triggers-写法.md`。

**为什么按编号不按日期**：G-NNN 可以被其他文件（执行日志、每日汇总）直接引用，形成超链网络。这是"可检索的记忆"的基础。

### 条目状态与沉淀字段（v0.7+）

G-NNN 条目的 frontmatter 可加以下字段（缺失等价于默认值，历史条目无需手工迁移）：

**status**（销账）：踩坑是否已完整评分
- `open` —— 进行中 / 待评分（默认）
- `scored` —— 评分完整已闭环
- `voided-faded` —— 褪色补录占位，不强求补
- `voided-r-nnn` —— 显式 R-NNN 销账
- ⚠️ status **只表示评分/销账态，不表示修复态**。踩坑的**修复进展**（fixed/mitigated/处置中/日期）写进 body「解决」段（如 `**修复态**：fixed（YYYY-MM-DD，…）`），**不重载 status**（统一语义见顶部「status 字段语义（钉死）」）。

**promote_\* 字段**（沉淀）：踩坑是否沉淀到团队文档/wiki
- `promote_status: pending | done | skipped` —— 默认 pending
- `promote_target` —— 沉淀后填写目标路径（如 `docs/05-常见问题/pnpm-workspace.md`）；skip 时填理由（如 "只影响本项目"）
- `promote_date` —— 沉淀完成日期（YYYY-MM-DD）

> 字段语义详见 SKILL.md「条目状态与沉淀字段（v0.7+）」节。

---

## 3. 执行日志.md（每步记录 + 双评分）

**何时写**：每完成一个有明确边界的工作单元（一个任务、一次评审、一次实验）就追加一条。粒度比 commit 粗、比迭代细。

**schema**（缺字段用 `—` 或 `待补`）：
```markdown
## Step main-7: 实现 token 采集器核心循环
triggers: ["采集器", "核心循环", "token 收集"]
日期：2026-04-15
status: open | scored | voided-faded | voided-r-nnn
about: project                              # 缺省可不写，默认 project；详见下方「about 字段」段

### 执行
- 写了 collector/core/collect.js
- 跑通端到端一次采样

### 产出物
- collector/core/collect.js (commit a3f2b1)
- 单测 6/6 通过

### 执行事实（模型客观陈列）
- 工具调用次数：约 22
- 报错 / 命令失败次数：2（见 G-011、G-012）
- 绕路次数：1（先试了轮询，改用事件钩子）
- 本步 token 消耗感：中（单次会话约 40% 预算）
- 使用的 skill：[bmad-create-architecture, subagent-driven]

> 颗粒度说明：**估算即可**，不需要精确计数。目的是拉出趋势信号（"这步比上一步更费劲"），不是精确审计。调用次数给个量级（约 10 / 20 / 50+）、token 消耗感给档位（低/中/高/偏高）、报错和绕路数精确到整数。

> **"使用的 skill" 字段语义**（v0.6.0 新增）：
>
> - 列出本 Step 实际触发过的 skill 名（`Skill` tool 调用过的、或 subagent 类协作机制），用 JSON 数组 `[x, y]` 或 YAML 多行格式
> - **N/A** 仅用于**纯对话驱动 / 账本维护 / 目录整理**等模型全程未触发任一 skill 的场景
> - **"无"**：本 Step 本该触发但没触发任何 skill（属异常信号，evaluate 是否 skill 触发机制失效）
> - **硬规**：触发过任一 skill 就**必须**列名，即使用户感受"没啥帮助"——skill 的正/负贡献通过顺畅度 + 一句话评价传达，不通过省略字段表达
> - 用途：跨 Step 按 skill 聚合做"skill 体感"分析时靠这个字段命中（不需要独立评分维度）

### 模型他评（recorder 独立读 transcript 后写入并锁定）
- 完成时间：2026-04-15 14:32    # 必须带时分，用于反锚定审计
- 执行质量：4/5
- 本步最值得扣分的一点：G-012 的 pnpm 坑应该在初始化阶段就规避，属于前置调研不足（取证自 transcript 第 3 段 Edit 报错后重读）
  （强制要求：必须填一条**有证据引用**的扣分项，不允许空，避免讨好式打分）

<!-- P-C1b：本段由 step-recorder subagent 独立读 transcript 抽事实后给出（执行质量 + 取证自 transcript 的扣分项），故称"模型他评"而非主会话"自评"。历史条目仍可为 `### 模型自评`，两者都被半残检测认。 -->

<!-- ---- 以下为锁定后的用户评分，模型不得回填修改上方他评段 ---- -->

### 用户评分
- 完成时间：2026-04-15 14:35    # 必须晚于模型他评段
- 顺畅度：—/5    # 🚨 必须当场采集，不允许留过夜
- 用户评价：
- 🚨 关键 GAP：

### 评分差异分析（只记录，不强制闭环）
- 模型 vs 用户差值：
- **差值 ≥ 2** → 方法论盲区信号。把原话 + 事实段 + 两方评分一并追加到 `改进建议.md`，新编 R-NNN 条目。**不强制回写铁规、不强制在本项目内做任何修改**——这是给未来 skill 作者看的原料。
- **差值 = 1 且用户评价含负面文本**（"返工 / 对不上 / 又错了 / 太啰嗦 / 又绕了"等）→ 同样追加到 `改进建议.md`，标为"弱信号"，不单独编号，聚合在相近主题下。
- **差值 = 0 或 1 且评价中性正面** → 无需额外动作，评分本身已在执行日志里。

**不做什么**：
- 不累计计数、不自动升格、不做归零 —— 记录本身已经够用
- 不在项目内强制执行这些信号提炼出的规则 —— 除非用户明确说"加进方法论铁规"
- 不判断同类 —— 未来 skill 作者 review 时自会聚类

### 与预期的偏差
- 原计划用轮询，实际发现事件钩子更合适（见 G-009）

### 发现
- pnpm -r test 在 monorepo 下比单包 test 慢 3 倍，值得后续优化
```

### model-only 下的用户评分段（rating.mode）

当 `.ieidev/memory/config.yaml` 设 `rating.mode: model-only`（机读化 Q-002）时，用户评分段**留空骨架 + 标销账**，**绝不拷自评分伪填**（伪填 = 假用户评分，污染 misalignment 切片）：

```markdown
## Step <id>: <title>
status: voided-faded   # 半残销账：rating.mode=model-only（承 Q-002），用户评分段不主动采集
...
### 用户评分
- 完成时间：—
- 顺畅度：—/5
- 用户评价：
> 半残销账：rating.mode=model-only（承 Q-002），用户评分段保留骨架不主动采集

### 评分差异分析
- n/a（model-only 跳过用户评分）
```

Step header 内联 `status: voided-faded` 即让 `step_completeness` 跳过欠评扫描（v0.15+ 起内联 status 也被解析）。`user-opt-in` 同样不追问，但**不**盖 voided（用户随时可填）；`model-only`/`user-opt-in` 下"用户评分段空"由 hook 读 `rating.mode` 豁免，不算半残。

### about 字段（subject 归属）

Step 评分**默认归属 `project`**（评的是项目结果），所以 `about: project` 可以不写。

只有 Step 评分**完全**是关于某个 skill 而不是项目结果时才显式写 `about: skill:X`——但这种情况极少（绝大多数 Step 是项目动作，对 skill 的评价应该走 F-NNN 通道而不是 Step 评分）。

| 场景 | about 取值 |
|---|---|
| 默认（评项目结果） | `project` 或不写 |
| 这个 Step 是 "测试某 skill 是否好用" 这种 meta 任务 | `skill:<name>` |
| 这个 Step 评的是协作模式 | `collaboration:<pattern>` |

**重点**：如果用户给 Step 打分时夹带 skill 反馈（"4 分但 X 太吵"），**不要**改 Step 的 about——应**评分裂解**拆出 F-NNN（详见下方）。

### 评分裂解（用户评分夹带 skill 反馈时）

用户给 Step 打分时常夹带 skill 反馈，例：

> "顺畅度 4 分，主要是 ieidev-memory 召回太吵打断了节奏"

**正确处理**：拆两条独立条目落盘，绝不能塞同一条。

| 条目 | 文件 | 内容要点 |
|---|---|---|
| 1 | 执行日志.md Step 评分段 | 顺畅度 4/5，用户评价段记项目部分（subject 隐含 = project） |
| 2 | skill-feedback.md F-NNN | subject: plugin:ieidev-memory / type: 痛点 / verbatim: 用户原话保留 skill 吐槽那段 |

**判断是否要拆**：用户的评价里若提到 skill / plugin / tool 名字、5 类语义关键词、方法论或协作模式名 → 一定要拆。中性叙述或对智能体本身工作的吐槽不拆。

完整规则、L1/L2/L3 推断、置信度字段见 **`references/subject-推断与评分裂解.md`**。

### Step 状态字段（v0.7+）

Step 条目的 frontmatter 可加以下字段（缺失等价于默认值，历史条目无需手工迁移）：

**status**（销账）：Step 是否已完整评分
- `open` —— 进行中 / 待评分（默认）
- `scored` —— 评分完整已闭环
- `voided-faded` —— 褪色补录占位，不强求补
- `voided-r-nnn` —— 显式 R-NNN 销账
- ⚠️ status **只表示评分/销账态，不表示修复态**（统一语义见顶部「status 字段语义（钉死）」）。

> 注：Step 条目不走团队沉淀（过程记录留在本地），故**不涉及** `promote_*` 字段。
> 字段语义详见 SKILL.md「条目状态与沉淀字段（v0.7+）」节。

### v0.17+ ID 格式：`Step <YYYYMMDD-HHMMSS>-<who>`（Q-020）

从 v0.17 起，Step ID 改为时间戳格式（coordination-free，worktree/多机不撞）。详见 [SKILL.md](../SKILL.md) 的「多 worktree 并发场景：时间戳记录 ID（v0.17 / Q-020）」一节。

- 旧顺序 ID（`Step N` 无前缀、`Step <branch-slug>-N` 分支前缀）**冻结**，不再 mint，但继续被 `parse_record_id` 解析（双认向后兼容）。
- `step_id_prefix_since` HTML 注释保留作历史标识，不再驱动 minting。

**双评分机制的设计意图**：
- **模型陈列事实 + 自评顺畅度**：事实段是无偏数据，自评是模型的主观感受。**强制"必须写一条扣分项"**防止讨好式打满分。
- **用户评分**：保持简单——1-5 分 + 一句话，对应同一个"顺畅度"维度，方便直接比较。
- **差值即信号**：两者相近说明方法论透明；差值 ≥ 2 分说明有盲区——智能体觉得顺、用户觉得难受是典型症状（比如"agent 写得很快但写出的东西用户看着累"）。这是 R-NNN 最主要的触发源。
- **为什么要实时采集用户评分**：感受会随时间褪色，第二天补的分数失真严重。

**锁定铁规（反他评污染）**：
模型他评段**必须先完整写入文件**，并向用户口头公布他评分数，之后才能询问用户评分。用户评分段的时间戳**必须晚于模型他评段**（分钟精度）。若两段时间戳倒置或相同，视为**他评污染**，该步不计入评分差值统计，并在每日汇总里标记为"污染样本"。

时间戳是唯一硬证据——文件结构上两段紧挨着，没有时间戳的话无法事后审计模型是否先看了用户评分再"他评"。

### Step 粒度：自然停顿点（不是机械分割）

"每完成一个有明确边界的工作单元"——**边界由工作流的"自然停顿点"决定**，看人-模型协作的节奏信号，而不是机械按 phase / todo 数量切。

**三个停顿信号（任一命中 → 该触发 Step 完成闸门）**：

1. **时长信号**：模型连续独立执行较长（量级约 **30min–1h** / 工具调用约 **30 次以上**）
2. **干预信号**：中间需要用户决策（升 Q-NNN）、拍板取舍、确认产出物
3. **验收信号**：有可 review 的产出（代码 / 文档 / eval 结果）且用户会对它有感受

**和 phase / todo 的映射（三种都合法）**：

- **1 phase → 1 Step**（默认：phase 本就是按直觉做出的自然停顿划分）
- **2 phase → 1 Step**（两 phase 都短 + 中间无干预 → 合并打分）
- **1 phase → N Steps**（phase 内部有明确决策点或验收点 → 切开）

**反模式**：

- 每 todo 一 Step → 评分疲劳（todo 是 Step 内的动作分解，不是 Step 本身）
- 整需求一 Step → 感受褪色、信号失真
- 机械按 phase 切 → phase 可能只是思维组织，未必是停顿点

**闸门触发时机**：看到任一停顿信号时，skill 主动走 Step 四段流程（执行事实 → 模型他评 → 公布 → 追问用户评分 → 评分差异分析）。这就是"何时把 todo list 里的一组 completed 折叠成一条 Step 条目"的判断依据。

---

## 4. 每日汇总/YYYY-MM-DD.md

**何时写**：会话结束前，智能体主动写入当天汇总。不是流水账——是"给下一个会话的交接班"。

**与执行日志的边界（必读）**：
- **执行日志** = 每步完整记录（事实 + 双评分 + GAP + 偏差 + 发现），是原始数据源
- **每日汇总** = 指向执行日志的索引 + 跨步洞察 + 未完成项 + 明日计划，**不复述执行日志已有的细节**
- 每步的详细评分写在执行日志里，每日汇总只提"Step 7 顺 / Step 8 低分 🚨"级别的速览
- 汇总的价值是**下次开会话时 30 秒能接上工作**，不是再读一遍今天的日志

**格式**：
```markdown
# 每日汇总：2026-04-15

## 完成的工作（速览，详情见执行日志）
- Step 7: 采集器核心循环 ✓（顺 4/4）
- Step 8: 仪表盘接入实测数据 🚨（模型 5 / 用户 3，差值 -2 → 已追加 R-003 到改进建议）

## 未完成项
- 异常重试逻辑尚未加（Step 9 做）

## 明日计划
- Step 9: 异常重试 + 断网恢复

## 本日新增踩坑 / 决策 / 改进信号
- G-012（pnpm workspace 依赖）
- Q-008（采集频率定为 5 分钟）
- R-003（产出速度与细节对齐脱钩 —— 详见改进建议.md）

## 负面评价观察
- Step 6: 用户说"又返工了一点"（差值 1，已记入执行日志；未到 R 阈值，仅留痕）
```

**为什么按日不按迭代**：迭代边界是项目事件，日是生物节律。人每次打开新会话会问"昨天我们做到哪了"——按日汇总直接回答这个问题。

---

## 5. 改进建议.md（R-NNN / R 时间戳形）【重要】

这是**本 skill 最主要的下游产物**。每次评分差值 ≥ 2、每次用户留下明显负面反馈、每次踩坑触发对方法论/工具链的反思——都在这里留一条原始记录，**不要提炼、不要总结、不要过滤**。

消费者不是当前项目，而是未来某个 skill 作者（或智能体）回头 review 几个项目的改进建议.md，从中聚类、归纳、产出新 skill 或改进既有方法论。**原始信号比结论更有价值**，因为结论需要跨项目才能归纳，单项目内提炼容易过拟合。

**格式**（以下示例为旧顺序 ID，**仅供参考；新编条目用时间戳形，如 `## R 20260613-150200-ly: 标题`**）：
```markdown
## R-001: 智能体高速产出与细节对齐脱钩  <!-- legacy 顺序 ID，冻结 -->
日期：2026-04-15
项目：token-statistics
promote_status: pending | done | skipped
promote_target: docs/XX                    # 若已沉淀则填写
promote_date: 2026-04-24                   # 若已沉淀则填写
触发：执行日志 Step 8 评分差值 -2（模型自评 5/5，用户 3/5）
模型自评原话："代码一次跑通，token 消耗低，顺畅"
用户评价原话："subagent 写得快但字段名对不上 PRD，又得我返工"
事实段：工具调用约 12 次、0 报错、0 绕路、token 低
初步诊断：智能体把"代码能跑"当完成，用户把"对齐 PRD"当完成——两套验收标准
可能的改进方向（留给未来 skill 作者判断，不是本项目执行）：
  - 需求→代码的桥接环节缺少对齐检查（可做成 pre-commit skill？）
  - 或：让智能体在写代码前先复述 PRD 字段（类似 TDD 先写断言）

## R-002: commit 粒度混乱
日期：2026-04-12
项目：token-statistics
promote_status: pending | done | skipped
promote_target: 
promote_date: 
触发：用户反馈"这个 commit 混进了三件事"
用户评价原话："commit 8a3e0f0 把 PRD 扩展 + 基线计划 + brainstorm 三件事打包了"
初步诊断：智能体为了"进度快"把无强耦合的变更合并提交
可能的改进方向：
  - commit 粒度准则是否应该成为智能体 pre-commit 的硬 check？
```

**写的原则**：
- 原话 + 事实 + 评分数据齐全，不要删减
- 诊断是可选的——写出来辅助未来 review，但不要强行拔高成"铁律"
- "改进方向"用疑问/假设语气，不要断言"必须怎么做"
- 同一项目的 R 编号递增，跨项目不共享（靠"项目"字段识别）

### 沉淀字段（v0.7+）

改进建议.md 的 R-NNN 条目可加以下字段（缺失等价于默认值，历史条目无需手工迁移）：

**promote_\* 字段**（沉淀）：改进建议是否沉淀到团队文档或新 skill
- `promote_status: pending | done | skipped` —— 默认 pending
- `promote_target` —— 沉淀后填写目标路径（如 `docs/06-方法论/字段对齐检查.md` 或 skill 名）；skip 时填理由（如 "项目特异性，无通用价值"）
- `promote_date` —— 沉淀完成日期（YYYY-MM-DD）

> 注：改进建议本身**不走销账**（无 `status` 字段），因为它的生命周期是"记录 → 沉淀 / 跳过"，不涉及评分锁定。
> 字段语义详见 SKILL.md「条目状态与沉淀字段（v0.7+）」节。

---

## 6. 方法论铁规.md（项目自愿启用的硬规则，可选）

如果项目团队/用户希望**在本项目内强制执行**某些规则（而不只是记录），才建这个文件。否则可以不建。

**什么时候用**：
- 用户明确说"从今往后这个规则必须遵守"
- 反复踩同一类坑后，项目自愿立规避免再犯
- 跨文件一致性要求（文件格式、编号规则）

**与改进建议.md 的区别**：
- `改进建议.md` = **候选信号**，给未来 skill 作者 review，不强制项目内执行
- `方法论铁规.md` = **项目自愿启用的规则**，本项目智能体必须遵守

一条改进建议可以**不动**、或**升级**到铁规/项目宪章（如果用户/团队决定执行）。两者不是上下游关系，是平行的两种用法。

**和项目级宪章的关系**：方法论铁规.md 是"只给 AI 看"的规则位置；如果规则要**对外宣称**（人类团队也读、跟 API 契约一样是项目资产），应升级到项目根的 `constitution.md` / `AGENTS.md` / `.specify/constitution.md` 等约定位置——升级流程见 `references/规则升级流程.md`。

---

## 7. 当前状态.md（带 YAML frontmatter 的单一真相源）【重要】

这个文件既要**人可读**（body 部分用自由文本写"当前在做什么"），又要**脚本可读**（frontmatter 里放结构化字段给 hook/skill 脚本用）。

**为什么要 frontmatter**：
- SessionStart hook 需要秒报"当前 phase / iteration / current_step"给 Claude
- 脚本式 lint / checkpoint 需要能程序化判断"状态多久没更新了"
- Claude 读 frontmatter 比读自由文本快、准，不会 hallucinate

**格式（frontmatter 字段固定，body 自由）**：

```markdown
---
phase: plan | exec | verify | done
iteration: "Sprint 0" | "迭代 1" | "Phase 2"
current_step: 23
last_updated: 2026-04-19
pending_decisions: [Q-007, Q-008]
unresolved_gotchas: [G-014]
---

# 当前状态

（自由文本 body：描述当前正在做什么、最近的关键决策、预期下一步、其他任何值得留下的上下文）

## 进行中 Step 的 todos 分解（可选，仅当前 Step 使用）

Step 20（v0.6.0 skill 字段）分解：
- [x] 改 references §3 字段模板 + 字段语义
- [x] 改 SKILL.md 速览段 + 闸门字段枚举
- [ ] 造 eval-11 fixture
- [ ] 跑 discriminating eval 并归档 iter-8
- [ ] bump plugin.json + CHANGELOG
```

**字段语义**：

| 字段 | 值类型 | 含义 |
|---|---|---|
| `phase` | `plan` / `exec` / `verify` / `done` | 当前大阶段。**不是强制状态机**，回退跳步都允许——只是给 Claude 一个参考 |
| `iteration` | 字符串 | 当前迭代/Sprint 命名，自由文本（"Sprint 0"、"迭代 1"、"Phase 2" 都行） |
| `current_step` | 字符串 | 最近完成的 Step 标识（v0.11 前是整数如 `8`；v0.11+ 是带前缀字符串如 `main-9` / `cluster-x1-1`） |
| `last_updated` | `YYYY-MM-DD` | frontmatter 最后修改日期（不是文件 mtime） |
| `pending_decisions` | 列表 `[Q-007, Q-008]` | 开着未定的 Q-NNN。用户答了就移出 |
| `unresolved_gotchas` | 列表 `[G-014]` | 已记录但未解决的 G-NNN（已有 workaround 的不算"未解决"） |

**更新时机（每次都顺手改 frontmatter，不要攒到汇总时）**：
- 完成一个 Step → 更新 `current_step` + `last_updated`；清空 body 的「进行中 Step 的 todos 分解」段（或折叠进 Step 条目的"执行"段留个轨迹）
- 开一个 Q-NNN 待用户决策 → 加到 `pending_decisions`；用户答了 → 移出
- 记一个 G-NNN 但没立即解决 → 加到 `unresolved_gotchas`；解决后 → 移出
- 阶段切换（plan 完成进入 exec 等）→ 更新 `phase`
- 新 Sprint/迭代开始 → 更新 `iteration`
- **TodoWrite 首次 emit 3+ todos 时** → 落 body 的「进行中 Step 的 todos 分解」段；每次 todo 状态变化（完成/新增）顺手同步。用于跨 session 接力时回读"当前 Step 做到哪了"。单个 todo completed **不**触发 Step 闸门——闸门看三个停顿信号（见 §3）

**兼容性**：
- 已有项目的 `当前状态.md` 没 frontmatter 也能工作（hook 脚本 fallback 到"无 frontmatter"模式）
- 初始化新项目时 skill 应主动写 frontmatter 骨架
- 修改 frontmatter**不需要征求用户许可**——和其他 `.ieidev/memory/` 文件一样，授权一次后自维护
