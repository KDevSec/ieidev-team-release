# ieidev-team

ieidev 数字员工集群——自包含单插件（编排引擎 + 记忆底座 + 业务员工 + 能力 skill）。

从 [KDevSec/kdev-agents](https://github.com/KDevSec/kdev-agents) clean-room 抽取并通用化（去公司定制前缀、去第三方依赖、单插件化）。源仓保持冻结，本仓为通用产品going-forward 主线。

## 安装

前置：

- **必需**：[Claude Code](https://docs.claude.com/claude-code) CLI（`claude`）+ `python3`（编排引擎与状态栏需要）。
- **可选**：`understand-anything` marketplace —— `codegraph-*` 代码图 skill 的后端（装机时作为跨 marketplace 依赖自动声明，缺失则仅 codegraph 能力降级，不影响主流程）；Playwright MCP server —— `qa` / `ui-autotest` 黑盒 UI 测试需要（缺失则这两类测试 env-gated 跳过）。

### 一行装机（推荐，跨平台）

```sh
npx ieidev-team
```

幂等、可重跑：注册 marketplace → 装插件 `ieidev-team@ieidev` → 接状态栏，装好后状态栏出现 `ieidev 团队 …`。重载插件（`/reload-plugins`）或重启 session 后生效。

> 📦 **自包含装机（v0.1.1+）**：npm 包**自带完整插件本体**。装机用**包内本地路径** `marketplace add`，`plugin install` 把插件复制进 `~/.claude/plugins/cache/`——**全程不碰 git 源码仓**，源码仓私有也能装。从公开 Release 装：下载 `.tgz` → `npm i -g ./ieidev-team-X.Y.Z.tgz && ieidev-team`。

常用开关：

```sh
npx ieidev-team --project                      # 写项目级状态栏（当前目录 .claude/settings.json）
npx ieidev-team --marketplace-source <本地路径>  # 覆盖 marketplace 源（默认=包内自带插件本地路径）
npx ieidev-team --help                          # 全部开关
```

### 或：shell 装机脚本

```sh
curl -fsSL https://raw.githubusercontent.com/KDevSec/ieidev-team/main/install.sh | bash
# 或克隆后 ./install.sh
```

`npx ieidev-team` 与 `install.sh` **同序同命令、共用同一个幂等决策核**（`ieidev_hud.installer`），二者等价——前者跨平台（node 自带），后者 unix shell。

### 或：手动装（`claude plugin` 子命令）

```sh
claude plugin marketplace add KDevSec/ieidev-team   # 注册 marketplace
claude plugin install ieidev-team@ieidev            # 装插件
/ieidev-team:setup                                  # 在 Claude Code 会话内接状态栏
```

三步与上面两种装法等价；`/ieidev-team:setup` 幂等合并写 `settings.json`，保留你已有的键。

## 装后体验

- **状态栏**：Claude Code 底部出现 `ieidev 团队 …`，实时显示在跑的需求 / 当前节点 / 员工忙闲；无在跑任务时显示 `ieidev 团队 │ 暂无在跑需求`。
- **一句话起活**：

  ```text
  /ieidev-team:goal <高层目标>
  ```

  `goal`（CEO 总编排）把高层目标拆成交付链，按需求→开发→测试→评审的顺序调度数字员工，关键节点发函 CQO 监督员做质量复核、在人工闸停下等你确认。
- **单员工直跑**：`/ieidev-team:flow-driver <emp> --task <...>` 直接驱动某个数字员工跑它的 SOP flow。
- **实时进展页**：`PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_hud serve` 起本地轮询式 HTML 进展页。

## 集群概览

**数字员工**（`staff.yml` 注册，各自有编排 SOP）：

| 员工 | 职责 |
|------|------|
| 需求架构师 `req-architect` | 需求澄清 → SR 规格 → 拆解（AR + 用户故事）→ 原型 → 方案设计 |
| 开发工程师 `dev-engineer` | 环境对齐 → 实施计划 → 编码/前端实现 → 安全自评 → E2E 视觉验收 → 部署 |
| 测试工程师 `test-engineer` | 黑盒测试点/用例设计 → UI/API 自动化执行 |
| 评审专家 `reviewer` | 方案/SR/故事/原型/代码/安全/测试设计/测试覆盖 多维度百分制评审 gate |
| **CEO 总编排** = `goal` skill | 高层目标 → 交付链编排 + 人工闸 + 发函 CQO |
| **CQO 监督员** = `cqo-orchestrator` | 跨 flow 质量监督（L-a 逐事件全检 + L-b circuit-breaker 聚合 + L-c 棒间建议），建议非拦截 |

**能力 skill**（员工与主控按需调用）：

- 需求/设计撰写：`sr-authoring` · `ar-authoring` · `detailed-design-authoring` · `constitution-authoring`
- 前端/原型：`frontend-design`
- 测试：`test-points` · `test-cases` · `ui-autotest` · `api-autotest` · `uicase-to-apicase` · `qa`
- 代码图：`codegraph-build` · `codegraph-impact` · `codegraph-trace` · `codegraph-spec-link`
- 工程底座：`memory`（持久工程记忆 + 召回 + 蒸馏）· `env-recon`（被测环境踩点）· `secure-coding`（Python 安全编码规范）· `flow-driver`（通用 flow 引擎驱动）

> 编排引擎、记忆底座与 HUD 状态栏由 `pyieidev/` 下 4 个自包含 python 包（`ieidev_core` / `ieidev_team` / `ieidev_hud` / `ieidev_ingestor`）支撑，均以 `python -m` 行内自带 `PYTHONPATH` 方式调用，无需 pip 安装。
