# 自动化触发机制（hooks 细节）

## 什么时候读本文件

- 需要理解某个 hook（Stop / SessionStart / SessionEnd / PreCompact / PostToolUse / UserPromptSubmit）的具体行为、触发条件、输出格式时
- 排查"为什么 hook 没触发 / 触发了但没效果"时
- 配置 strict 模式、调整 hook 行为时
- 修改 `hooks/` 下脚本前的背景了解

## 我不负责什么

- **记录自身的字段格式与触发时机** → `references/六类记录-schema.md` 和 SKILL.md 的总览表
- **triggers 关键词如何选** → `references/triggers-写法.md`

---

## 三层触发方式（总览）

skill 本身**不会自动执行**——它只在被 Claude 召唤后提供指令。真正的"自动记录"靠三层组合：

### 1. 自然触发（skill 本职）

用户自然语言命中 description 关键词时被召唤：
- 初始化：说"建立工程记忆 / 给项目加 .ieidev / 搞个记忆机制"
- 每日汇总：说"写今天的总结 / 生成每日汇总 / 交接给明天 / 总结一下今天"
- 续航：新会话时提到"看下昨天做到哪了 / 上次我们讨论到什么"—— skill 会被召唤来读 `.ieidev/memory/`

### 2. 主动触发（CLAUDE.md 指令式）

初始化时写进项目 CLAUDE.md 的触发规则段（见 `references/初始化-claude-md-模板.md`），让**每个新进入项目的智能体都读到**"这个项目有记忆制度"。后续所有步骤完成时，Claude 按 CLAUDE.md 的指令自动调用记录流程——**不需要用户每次说"记一下"**。这是本 skill 的主力机制。

### 3. 自动触发（Hook，插件自带）

`ieidev-memory` 插件安装后自动启用多层 hook，无需用户手动配 `settings.json`。下面逐一展开。

---

## Stop hook（软提醒，默认）

Claude 每次要停下时检查 `.ieidev/memory/` 状态，向下一轮上下文注入文本提醒。检测项：

- 今天无汇总
- 汇总过时
- 执行日志今天空
- **过去日期有条目但缺汇总**——最后一条是跨天会话场景的兜底：晚上 23:55 干到次日 01:30 不关会话 → SessionEnd 不触发 → 昨天汇总被遗漏；Stop hook 扫源文件里所有 `日期：YYYY-MM-DD`，发现任何早于今日且对应 `每日汇总/<date>.md` 不存在的，都会提醒补写。
- **📦 归档提醒**：执行日志最早条目跨月 / 踩坑或决策日志最早条目跨季度时提醒切档（详见 `references/切档与归档.md`）

SessionStart 的 `<ieidev-memory-brief>` 里也会把缺失汇总日期列在 ⚠️ 待处理段（双保险）。

---

## Strict 模式（条件阻塞，opt-in）

项目根 `touch .ieidev/memory/strict` 即启用。

**触发阻塞的条件**：执行日志今天空 + 工作区有变更 + (≥2 文件变更 或 命中里程碑白名单如 `specs/**/*.md`) → `exit 2` 阻塞 Stop，Claude 必须落盘后才能真正结束。

带 `stop_hook_active` 保护不会无限循环。

`rm .ieidev/memory/strict` 关闭。

---

## PostToolUse hook

Claude 用 `Write/Edit/MultiEdit` 命中里程碑白名单（Spec Kit 产物、契约 YAML、方法论铁规）时，立刻提醒追加 Step 到执行日志。

日常源码编辑不打扰。

---

## SessionEnd hook（兜底）

会话真正结束（客户端关闭、切项目）时，若今天执行日志无条目但工作区有变更 → 写 `.ieidev/memory/WARN-未记录-YYYY-MM-DD.md` 文件，列出变更快照。

下次进入项目 CLAUDE.md 触发规则段会让 Claude 看到并提醒补记。

---

## SessionStart hook（`<ieidev-memory-brief>` 注入）

新会话启动时注入 `<ieidev-memory-brief>...</ieidev-memory-brief>` 摘要，内含：

- 今日进度（最近完成的 Step）
- 当前状态 frontmatter 字段（phase / iteration / current_step / pending_decisions / unresolved_gotchas）
- ⚠️ 待处理项：WARN 文件、checkpoint 文件、缺失的每日汇总日期
- ⚠️ **CLAUDE.md 接口漂移**（0.5.0+）：调用 `hooks/lib/claude_md_lint.py` 比对 skill 的 `claude_md_contract` 和项目 `CLAUDE.md`，检测缺少的 hook 注入标签 / hook 产出文件模式 / 贯穿 session 铁规。缺失时在 brief 里列出，并提示用户召唤 skill 说"修 CLAUDE.md 漂移"获得精确 diff patch

Claude 看到 brief 应先处理⚠️条目再做用户新任务。

### 接口漂移 lint 的行为边界

- **只读**：lint 不修改任何文件，只报告漂移项
- **非阻塞**：lint 失败（contract 解析错、CLAUDE.md 解析不出 kdev 章节等）都静默降级，不影响 brief 其他内容
- **渐进式披露**：brief 里只列缺少的具体项 + 一行召唤指引；真正的 diff 生成与 Edit 走 skill（用户批准后执行）
- **append-only 友好**：skill 的 `claude_md_contract` 新增字段只会让老 CLAUDE.md 触发 lint 警告，不会让它立刻失效——用户可选择忽略或修复

---

## PreCompact hook（压缩前兜底）

会话即将被压缩时，把当前 `.ieidev/memory/` 关键文件的原文快照写到 `.ieidev/memory/checkpoints/压缩前-*.md`。

**一般情况 Claude 不需要主动看**；只在以下场景读：
- 用户说"上次压缩前的细节"
- 当前 `.ieidev/` 文件有缺失但 checkpoint 里有原文
- 执行日志有空当期且同时段有 checkpoint（说明压缩时没来得及落盘）

Checkpoint 7 天后 PreCompact hook 自动清理，不用手工维护。

---

## UserPromptSubmit hook（triggers 召回）

每次用户提交 prompt 时，扫 `.ieidev/memory/` 里所有带 `triggers:` 字段的条目（含归档目录），用 literal substring 匹配，命中就注入 `<ieidev-memory-recall>` 指针（只含编号 + 标题 + 文件路径，不塞全文）。

扫描源（0.4.0+）：
- **踩坑日志**：`.ieidev/memory/踩坑日志.md` + `.ieidev/memory/归档/踩坑日志-*.md`（老坑照样召回）
- **执行日志**：`.ieidev/memory/执行日志.md` + `.ieidev/memory/归档/执行日志-*.md`（今日/昨日过滤会把归档里的老 Step 剔除）
- **方法论铁规**：`.ieidev/memory/方法论铁规.md`
- **项目级 spec**：见 `references/triggers-写法.md` 里的 7 个约定路径

Session 去重：`.ieidev/memory/state/trigger-sessions.json`，TTL 60 分钟。

---

## 为什么需要多层而不是一层

Stop hook 的 stdout 提醒在"用户不再输入，会话自然 idle"时不会被读到；Strict 模式用 exit 2 强制 Claude 再工作一轮来处理；SessionEnd 则是真关门前的最后落痕。Spec Kit 这类长流程里三层缺一不可。

---

## 边界说明

hook 只能运行 shell 命令、不能让 Claude 做智能判断——它的作用是：

- **戳一下 Claude 的注意**（软提醒，Stop / PostToolUse / SessionStart）
- **拒绝让 Claude 就此罢工**（硬阻塞，Strict 模式）
- **在 Claude 失效场景下补课**（SessionEnd 的 WARN 文件 / PreCompact 的 checkpoint）

真正的决策（该不该写、写什么）仍由 skill 负责。不要想用 hook 代替 skill。
