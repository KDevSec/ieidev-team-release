# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

> 发版提示：`package.json`（npm 装机件）与 `.claude-plugin/plugin.json`（插件本体）的 `version` 需**同步 bump**，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## [0.2.0] - 2026-06-22

数字员工编排底座 0.2.0：交互硬停 + 计划说明书/Story TODO + 全局 HUD（client-render + SSE）。

### Added

- **#7 goal 交互层 + 硬停机制**：目标总编排渲一屏编排结论让人确认（confirm 屏：阶段路由 + worktree + story 估算）；human_gate 人闸硬停（`--auto` 防写即不触发）。
- **#8 计划说明书 + Story TODO**：`build_roadmap` 纯函数从 delivery-plan + 工作区文件派生阶段路线（需求→开发→测试）+ worktree + 用户故事 checklist（链进度 %）；confirm 屏与 HUD 渲染。
- **#9 全局 HUD（client-render + serve --global/SSE）**：本机 registry（`~/.ieidev-team/registry.json`，立项自动登记、owner=git email@host）+ 全局多项目聚合数据层；复用对齐稿 mockup 的客户端渲染 shell（`render` / `render --global` 内联 model 出静态 hud.html；`serve --global` = `/`(shell) + `/model.json` + `/events` SSE 实时台，干掉 2s 全页刷新）；侧边任务树 + 在跑总览（活跃派单，孤儿派单按 ts 老化标 stale）+ 监督员告警 + 评审流水 + 详情抽屉（真事件流 newest-first cap12）。

### Changed

- **退役服务端 dashboard 渲染**：`ieidev_hud/dashboard.py` 服务端出 HTML 的渲染路径退役，统一到 `frontend.py` 客户端渲染 shell（per-feature 与 global 同一视觉，消除漂移）；HTML 结构断言迁 Playwright DOM 冒烟（含无浏览器结构冒烟兜底 + CI chromium 非-skip 闸），数据派生断言迁 model 层测试。

### Notes

- 测试：5 套测试树共 **1099** 用例全绿。
- 诚实债：团队同步为 phase-2（本期只埋 owner 字段 + UI 预留位）；story 回溯 SR 字段预留（恒 None，前端渲 `↩ 预留`）。

## [0.1.3] - 2026-06-21

活体 dogfood（v0.1.2 首跑）暴露问题批修（#1/#3/#4/#5/#6）。

### Fixed

- **#1 状态栏空白（🔴）**：`setup.py:build_statusline_command` 去掉 `--workspace ${workspaceFolder}`——CC 不展开该变量导致 argparse 报错、状态栏每次刷新均空白；改为只发 `statusline`，workspace 由 stdin JSON cwd 自动解析。
- **#4 HUD 进度恒 0%（🟡）**：`req-architect-decompose.md` 将 `add-story` 升级为 🔴 必做并写明后果；`cqo_la.py` 新增 R4 规则 `advance-past-decompose-no-stories`（利用 `phase_history[-1].from` 检测离开 decompose 节点时 `stories[]` 为空 → 落 WARN 信号）。
- **#5 全自动下 human_gate 不保证硬停（🟡）**：`goal SKILL.md` §3.3 step4 + §5 新增诚实债 4，明示 `auto + skipAutoPermissionPrompt` 下 human_gate 为建议性停靠、不保证硬停，并注明后续计划与当前工作方式。
- **#3a handoff-write 晦涩报错（⚪）**：`cli.py:cmd_handoff_write` 捕获 `JSONDecodeError` 并重抛带 `--gate-input 须合法 JSON` 提示的 `ValueError`，取代原来的 `Expecting value: line 1 column 1`。
- **#3b show 命令 flow 不符返回全 null（⚪）**：`show <wrong-flow> <slug>` 现在在输出中追加 `_note` 字段明示 flow 不符并指出实际 flow，避免歧义；按 slug 取真状态逻辑不变。
- **#6 产物落点不一致（⚪）**：`node-agent-routing.md` 新增「产物落点规范」section，统一约定 `handoffs/<emp>/` 为权威 baton 源，`docs/` 副本为可选人类浏览副本、不作机器输入。

### Notes

- 测试：全套 **1001** 用例全绿（新增 6 个 TDD 测试：R4 CQO 规则×3、goal 诚实债串×1、bad JSON 报错×1、show flow 不符×1）。

## [0.1.2] - 2026-06-21

全部 skill 名补 `ieidev-` 品牌前缀（防跨插件裸名冲突）。

### Changed

- **skill 名全加 `ieidev-` 前缀**：20 个 skill 目录 `skills/<x>/` → `skills/ieidev-<x>/`；SKILL.md frontmatter `name: <x>` → `name: ieidev-<x>`；全仓所有 `ieidev-team:<x>` 引用同步更新为 `ieidev-team:ieidev-<x>`。

  受影响 skill：`api-autotest`、`ar-authoring`、`codegraph-{build,impact,spec-link,trace}`、`constitution-authoring`、`detailed-design-authoring`、`env-recon`、`flow-driver`、`frontend-design`、`goal`、`memory`、`qa`、`secure-coding`、`sr-authoring`、`test-{cases,points}`、`ui-autotest`、`uicase-to-apicase`。

- **命令名不变**：`/ieidev-team:goal`、`/ieidev-team:flow-driver`、`/ieidev-team:memory-distill`、`/ieidev-team:memory-weekly`、`/ieidev-team:setup` 命令已被 CC 命名空间化，无裸名冲突，保持不变。

### Notes

- 测试：全套 **995** 用例全绿（本次新增断言钉死新 skill 名，零功能回归）。
- API 变更：在 CC `/` 菜单中，skill 由 `/qa`、`/memory` 等裸名改为 `/ieidev-qa`、`/ieidev-memory` 等全局唯一名。

## [0.1.1] - 2026-06-21

OMC 式**自包含装机**：npm 装机包自带完整插件本体，装机不再依赖源码仓库可达。

### Changed

- **npm 包自包含**：`package.json` `files` 从「6 个装机件」扩成「装机件 + 完整插件树」（`.claude-plugin/` / `agents/` / `skills/` / `commands/` / `hooks/` / `orchestration/` / `lifecycles/` / `standards/` / `staff.yml` + 4 个 runtime python 包）。tarball 254 文件 / ~594KB。
- **本地路径装机**：`bin/cli.js` / `install.sh` 默认 marketplace 源改为「包根有 `.claude-plugin/marketplace.json` → 用包内本地路径 `marketplace add`；否则回退 GitHub 源」。`IEIDEV_MARKETPLACE_SOURCE` 仍可覆盖。**装完插件复制进 `~/.claude/plugins/cache/`，全程不碰 git 源码仓**——闭合「装机依赖私有源仓」缺口。

### Added

- `scripts/prepack-clean.js` + `package.json` `prepack` 钩子：打包前清 `__pycache__`/`*.pyc`（`files` 白名单内 `.npmignore` 无效，须物理清理）。

### Notes

- 测试：全套 **995** 用例全绿（+8：自包含打包 6 + 双壳本地路径装机 2）。
- 分发：自包含 `.tgz` 作公开仓 `KDevSec/ieidev-team-release` GitHub Release 资产（不上 npm registry）。

## [0.1.0] - 2026-06-20

首个版本。从 [KDevSec/kdev-agents](https://github.com/KDevSec/kdev-agents) 的「数字员工集群」（多插件）**clean-room 抽取**成自包含单插件 `ieidev-team`，源仓保持冻结。

### Added

- **编排引擎 + 业务员工**：需求架构师 / 开发工程师 / 测试工程师 / 评审专家 4 类数字员工 + `goal`（CEO 总编排）skill，按 `staff.yml` 注册、各自有 SOP flow（`orchestration/*.node-table.yml`）。
- **CQO 监督员**：跨 flow 质量监督——L-a 逐事件全检 hook（确定性规则）+ L-b circuit-breaker 机械聚合层 + L-c 棒间建议（建议非拦截、防套娃叶子）。
- **记忆底座**：`memory` skill——持久工程记忆 + 智能召回 + 蒸馏导出 + 周报；七层防线 hook 系统（SessionStart/UserPromptSubmit/Stop/PostToolUse/PreCompact/SessionEnd）。
- **能力 skill**：`sr-/ar-/detailed-design-/constitution-authoring`、`frontend-design`、`test-points/test-cases/ui-autotest/api-autotest/uicase-to-apicase/qa`、`codegraph-build/impact/trace/spec-link`、`env-recon`、`secure-coding`、`flow-driver`。
- **HUD 状态栏 + 实时进展页**：状态栏品牌 `ieidev 团队`，`ieidev_hud serve` 提供 stdlib http 轮询式实时进展 HTML 页。
- **OMC 式装机**：`npx ieidev-team` / `bash install.sh` / `claude plugin` 手动三步，幂等可重跑、共用同一决策核（`ieidev_hud.installer`），走文档化 `claude plugin` 子命令、不碰 Claude Code 内部 config，`settings.json` 安全合并保留用户键。
- **4 个自包含 python 包**：`ieidev_core`（引擎内核）/ `ieidev_team`（业务库）/ `ieidev_hud`（状态栏+装机）/ `ieidev_ingestor`（代码图摄取），统一 `python -m` + 行内 `PYTHONPATH` 调用，无需 pip。
- **统一测试入口 + CI**：`pytest.ini`（importlib 模式）一条命令跑全部 5 套测试，GitHub Actions py3.12 CI。

### Changed（相对源仓 kdev-agents）

- **去公司前缀**：`kdev` → `ieidev`（包名 / 命名空间 / 记忆目录 `.kdev/`→`.ieidev/` / 状态栏品牌）；保留上游出处 `KDevSec/kdev-agents` 与内容契约类标识（`kdev:` tag / `kdev-sec:` node ID）。
- **去第三方依赖**：移除 `spec-kit` / `gstack` / `webapp-testing` / 外部 `frontend-design`，改为仓内自家 authoring skill + `qa` 方法论 skill + `frontend-design` fork。
- **单插件化**：原多插件（core/team/hud/ingestor/memory/code-graph）合并为单一自包含插件。
- **命名归一**：skill/command/agent 全裸名（插件层自动加 `ieidev-team:` 命名空间），去冗余前缀。

### Notes

- 测试：5 套测试树共 **970** 用例全绿（root memory 437 + core 179 + team 142 + hud 120 + ingestor 92）。
- 唯一外部依赖：`understand-anything` marketplace（可选，仅 `codegraph-*` 用，跨 marketplace 依赖已声明）。

[0.2.0]: https://github.com/KDevSec/ieidev-team-release/releases/tag/v0.2.0
[0.1.1]: https://github.com/KDevSec/ieidev-team-release/releases/tag/v0.1.1
[0.1.0]: https://github.com/KDevSec/ieidev-team-release/releases/tag/v0.1.0
