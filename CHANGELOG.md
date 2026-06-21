# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

> 发版提示：`package.json`（npm 装机件）与 `.claude-plugin/plugin.json`（插件本体）的 `version` 需**同步 bump**，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

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

[0.1.1]: https://github.com/KDevSec/ieidev-team-release/releases/tag/v0.1.1
[0.1.0]: https://github.com/KDevSec/ieidev-team-release/releases/tag/v0.1.0
