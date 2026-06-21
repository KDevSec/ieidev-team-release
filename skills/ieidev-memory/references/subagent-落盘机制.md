# subagent 化落盘机制（hybrid / inline 两档）

## 什么时候读本文件

- 实现 `.ieidev/memory/config.yaml` 的 `record_mode` 切换
- 在每日汇总 / weekly / markdown 切片导出 / F-NNN 实体写入时决定走 subagent 还是主会话内联
- 评估某条记录是否值得 subagent 化
- 用户问"记录太占上下文 / subagent / hybrid / record_mode / 落盘方式"

## 这个机制存在的原因

ieidev-memory 的实时落盘需要做大量文件 I/O（Read / Edit / Write），这些动作：
1. **消耗主会话上下文 token**（Read 一个 200 行的执行日志.md 约 1.5k token）
2. **用户看到主会话满屏"我在写日志"打断思路**（housekeeping 噪音占据 UX）

把"写入"剥离到 subagent → 节省主会话上下文 + 改善对话体验。

**但不是所有记录都适合 subagent 化**：subagent 启动开销摊在小高频记录上不划算，且某些动作必须主会话同步（如评分裂解、subject 推断、用户确认）。

## 两档配置

`.ieidev/memory/config.yaml`：

```yaml
record_mode: hybrid   # hybrid（默认） | inline
```

未配置 = 视同 `hybrid`（fail-open 偏 UX 友好）。

| 档位 | 适用场景 |
|---|---|
| **`hybrid`（默认）** | 小高频留主会话内联，大单次 + F-NNN 实体写入走 subagent。Claude Code 等支持 Agent / Task tool 的平台默认值。 |
| **`inline`** | 全部主会话内联。**平台不支持 subagent**（非 Claude Code 平台 / Claude.ai web）/ **用户偏好极简**（每个动作要看见） |

**"全 subagent" 档不提供** —— subject 推断 / 评分裂解 / F-NNN 落盘前确认在物理上必须主会话同步，"全 subagent" 是虚假选项。

## 动作分类（按 hybrid 模式）

### A. 主会话同步内联（hybrid 和 inline 两档都这么干）

| 动作 | 为什么必须主会话 |
|---|---|
| subject 三级推断（L1/L2/L3） | 必须同步 + 影响后续数据归属 |
| 评分裂解（拆 Step + F 两条草稿） | 必须同步 + 单次 token 小 |
| F-NNN 落盘前一句话确认 | 必须等用户答复 |
| 单条 Step 落盘（写入执行日志） | 高频 + 必须同步等用户评分 |
| Q-NNN 决策记录（用户答完立刻写） | 必须同步 + 用户答完立刻写 |
| 当前状态.md 顺手改 frontmatter | 高频 + 单次 token 极小（一行字段改动） |
| G-NNN 踩坑落盘 | 高频 + 单次 token 小 |
| R-NNN 改进建议落盘 | 中频 + 单次 token 小 |

### B. hybrid 模式额外走 subagent（inline 模式回退主会话同步）

#### B-1. 同步等返回（主会话拿到 subagent 状态行才继续）

| 动作 | subagent 收益 |
|---|---|
| 每日汇总（读 5 文件 + 拼装 + 写入） | 解析 + 拼装 token 量大，省主会话 5-10k token |
| weekly 聚合（读 7 天数据 + 四段骨架） | 同上，量更大 |
| markdown 切片导出 | 解析全量 + 写 3 个切片，量最大 |

#### B-2. 异步 fire-and-forget（主会话不等）

| 动作 | 为什么异步 |
|---|---|
| **F-NNN 实体写入**（用户确认 subject 之后） | **最大杠杆点**——让随口吐槽不打断对话；用户已确认草稿，subagent 只是 format + write |
| 长文件 lint 扫描 | 后台跑，结果通过 hook 注入下次会话 |

## subagent 调用契约

主会话调 subagent 时，**只传必需信息**，不传 transcript（避免传递成本抵消节省）：

### 传入（最低成本原则）

```
- 任务类型（"daily-summary" | "weekly" | "export-md" | "F-write"）
- 已构造好的草稿（事实段 + 用户原话 verbatim 等）
- 目标文件路径
- .ieidev/memory/ 当前状态摘要（如需要——比如下一个 F 编号要拿最大 +1）
```

⚠️ **绝不传 transcript**——读 transcript 传过去的 token 量会抵消节省，本末倒置。subagent 负责 `format + write + lint`，不读对话历史。

### 返回（必须含审计摘要）

```json
{
  "written_to": "skill-feedback.md:L83",
  "status": "ok" | "error",
  "error_msg": null | "<reason>",
  "lint_warnings": [],
  "stats": {  // 任务相关，比如 export-md 给文件数 / 条目数
    "files_written": 3,
    "entries": 47
  }
}
```

**无审计摘要 = subagent 默写错误且主会话无感知 = 数据信任崩塌。** 这是硬约束。

## fallback：Agent / Task tool 不可用时降级 inline

**不写运行时环境检测**。SKILL.md 里直接声明："如果 Agent / Task tool 不可用 → 自动降级到 inline 模式。"

Claude 看到工具不在可用列表，会自然降级，无需显式 detection 逻辑（Claude Code skill 也没这能力，强写容易错）。

## F-NNN 异步落盘的完整流程

```
[ 主会话（同步内联）]
├─ 1. 检测到 5 类语义之一
├─ 2. 推断 subject（L1/L2/L3）
├─ 3. 起草 F-NNN（subject + verbatim + type + diagnosis 等）
├─ 4. 一句话向用户确认："听到你说 [X 摘要]，记 F 给 subject [Y]，对吗？"
├─ 5. 用户回答"对" / "不是" / "subject 错了应该是 Z"
└─ 6a. "对" → fire-and-forget subagent → 跳到下面 ↓
    6b. "不是" → 丢草稿，主会话继续

[ 主会话（fire-and-forget 后）]
└─ 7. 主会话不等 subagent，直接继续主线对话
    （状态行 "F-NNN → skill-feedback.md:Lxxx" 在下一个工具调用空隙到达）

[ subagent（后台）]
├─ 8. 读 skill-feedback.md（拿当前 F 最大编号 → +1）
├─ 9. 拼装 F-NNN 条目（含 frontmatter 字段 + body）
├─ 10. 文件末尾追加（不是覆盖）
├─ 11. lint（subject 合法 / verbatim 非空 / type 合法 / 字段完整）
└─ 12. 返回 {written_to, status, lint_warnings, ...}
```

## 命令模板分支逻辑（hybrid 下 subagent / inline 下内联）

`/ieidev-team:memory-daily`、`/ieidev-team:memory-weekly`、`/ieidev-team:memory-distill` 这三个命令的 command.md 模板应包含分支：

```markdown
读 .ieidev/memory/config.yaml 取 record_mode（未配置默认 hybrid）。

if record_mode == "hybrid" 且 Agent/Task tool 可用：
    用 Agent / Task tool 调 subagent
    传入：聚合所需的草稿和路径、subagent 任务类型
    subagent 返回 {written_to, status, lint_warnings, stats} 后向用户报告

else（record_mode == "inline" 或 Agent tool 不可用）：
    主会话直接 Read 文件 + 拼装 + Write 输出
    用户看见全部动作
```

## 实现工程量预估

| 增量 | 工程量 |
|---|---|
| config.yaml 读取 + record_mode 切换 helper | 1 小时 |
| F-NNN 写入 subagent prompt 模板（含 fire-and-forget 流程） | 1 小时 |
| 每日汇总 / weekly / export-md 命令模板加分支 | 1 小时 |
| subagent 返回审计摘要 schema 落实 | 半小时 |
| **总约半天** | |

## 未决问题（首批数据出来后再定）

1. **fire-and-forget 失败如何告警**：主会话已不等，subagent 写入失败的错误怎么浮出？候选方案：
   - 写入 `.ieidev/memory/state/F-write-errors.log`，下次 SessionStart hook 检测并 brief 注入
   - 等下次主会话工具调用空隙，把 subagent 返回当 system message 注入
2. **多 subagent 并发写同一文件的竞态**：如果两条 F 同时 fire-and-forget，争抢 skill-feedback.md 怎么办？候选方案：
   - advisory lock（fcntl flock）
   - subagent 写入用 append 模式 + 文件锁
   - F 编号原子分配（读最大值用 O_EXCL 创建临时占位文件）
3. **subagent 调用的 token 计费**：是否计入主会话上下文？如何让用户透明感知？
4. **hybrid 模式下用户突然想"看一下记录"怎么办**：主会话不知道 subagent 写了啥具体细节
   - 解法：subagent 返回的 `written_to: file:line` 主会话可以 Read 那个范围给用户看
5. **subagent 中断后的状态机**：subagent 跑到一半被中断，主会话怎么知道要重试？
