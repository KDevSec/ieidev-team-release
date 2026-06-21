---
description: ieidev-team 装机收口——做 plugin manifest 天生干不了的「残余接线」：Python 路径就绪验证、statusLine 接进 settings.json、探测 playwright MCP + understand-anything 依赖。幂等，重跑不破坏用户改动。
argument-hint: "[--user] [--force] [--refresh-interval N]"
---

# /ieidev-team:setup

ieidev-team 是**单插件**：agents / skills / commands / hooks 装上即由 plugin manifest 原生提供，**不需要本命令**。本命令只做 manifest 天生干不了的**残余**（仿 OMC 萎缩型 installer）：

1. **Python 路径就绪**——验证 `python3 -m ieidev_core` 等能在插件安装后跑起来；
2. **statusLine**——CC 插件不能自动注册主 statusLine，需写 `settings.json`（HUD）；
3. **依赖探测**——playwright MCP（qa / ui-autotest 用）+ understand-anything（code-graph / ingestor 用），缺则引导。

**全程幂等**：每步先探测当前状态，已就绪则跳过或原位刷新，**绝不覆盖用户既有改动**（statusLine 他者条目默认不动，除非 `--force`）。

参数原文：`$ARGUMENTS`（`--user` 写用户级 settings；`--force` 覆盖他者 statusLine 前先备份；`--refresh-interval N` 改 statusLine 定时刷新秒数，默认 10）。

---

## 第 0 步：定位插件根 + Python 路径就绪（最重要）

本插件的 4 个 python 包统一在插件根的 `pyieidev/` 下（`ieidev_core` / `ieidev_team` / `ieidev_hud` / `ieidev_ingestor`）。agents / skills 里的 `python3 -m ieidev_core ...` 调用都靠 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev` 自包含前缀跑起来——**这是装机后能跑的核心机制**（`${CLAUDE_PLUGIN_ROOT}` 在 agent / skill 内容读取时由 CC 就地替换成绝对安装路径；FF-2「`find ~` 猜路径」债已还）。本步只**验证**它真能跑。

### 0.1 解析 PLUGIN_ROOT

按优先级取插件根（命令内容里 `${CLAUDE_PLUGIN_ROOT}` **不**保证被替换，故主动解析）：

```bash
# ① shell 里若已有 CLAUDE_PLUGIN_ROOT（少数 harness 注入）直接用
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"

# ② 否则用已安装插件缓存定位（CC 标准安装路径，取最新版本目录）
if [ -z "$PLUGIN_ROOT" ] || [ ! -d "$PLUGIN_ROOT/pyieidev" ]; then
  PLUGIN_ROOT=$(ls -d "$HOME"/.claude/plugins/cache/*/ieidev-team/*/ 2>/dev/null | sort -V | tail -1)
fi

# ③ 仍找不到（dogfood 源仓 / 非标准布局）→ 让用户给出含 pyieidev/ 的插件根
echo "PLUGIN_ROOT=$PLUGIN_ROOT"
test -d "$PLUGIN_ROOT/pyieidev/ieidev_core" && echo "OK: pyieidev 就位" || echo "MISSING: 没找到 pyieidev/ieidev_core，请确认插件已安装或手动给出插件根"
```

若 ③ 报 MISSING：向用户要插件根绝对路径（含 `pyieidev/` 的目录），设进 `PLUGIN_ROOT` 再继续。

### 0.2 验证 `python3 -m ieidev_core` 真能 import（装机后能跑的硬证据）

```bash
PYTHONPATH="$PLUGIN_ROOT/pyieidev" python3 -c "import ieidev_core, ieidev_team, ieidev_hud; print('python-path OK: ieidev_core/team/hud importable')"
```

- **成功** → Python 路径机制就绪。装机后 agents / skills 里的 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_core ...` 会用同样的绝对路径跑通，无需任何全局环境改动（零配置、跨平台）。
- **`ModuleNotFoundError`** → `PLUGIN_ROOT` 不对或包未随插件装好：回 0.1 重定位；仍失败则报告用户「python 包未就位」，不要继续往下做（后续步骤的依赖都依赖它）。

> 为什么不用 `pip install -e` / 持久 PYTHONPATH 配置：自包含前缀方案**零环境污染、跨平台、不依赖用户 shell rc**，且插件升级换路径时 `${CLAUDE_PLUGIN_ROOT}` 自动跟随（pip -e 的 egg-link 会指向旧版本目录而失效）。

---

## 第 1 步：statusLine 接进 settings.json（HUD）

CC 插件**不能**自动注册主 statusLine（plugin 自带 settings.json 只认 `agent` / `subagentStatusLine` 两键，不认主 `statusLine`）。故由 HUD 的一次性 installer 幂等写入：

```bash
# 默认写项目级 <workspace>/.claude/settings.json；--user 写 ~/.claude/settings.json
PYTHONPATH="$PLUGIN_ROOT/pyieidev" python3 -m ieidev_hud setup --workspace "$(pwd)" $ARGUMENTS
```

幂等语义（installer 内置，见 `ieidev_hud/setup.py`）：

- 无 settings.json → 新建并写入；
- 有 settings.json 无 statusLine → 合并添加，**保留所有原有键**；
- 已是本插件 statusLine → 原位刷新路径 + `refreshInterval`（幂等，可反复跑）；
- **已有他者 statusLine → 默认不动**（返回 `skipped_foreign`），加 `--force` 才覆盖，且覆盖前先备份 `settings.json.bak`。

写入的 payload 带 `refreshInterval`（默认 10 秒）——让**后台子 agent 跑 flow 改变状态时，主会话空闲也按 timer 刷新 HUD**（CC 原生字段，等效 OMC 缓存包装器、无需自建 wrapper）。

完成后提示用户：**重载插件（`/reload-plugins`）或重启 session** 后状态栏生效。

---

## 第 2 步：探测 playwright MCP（qa / ui-autotest 用）

`ieidev-team:qa`（系统化 QA / 冒烟方法论）与 `ieidev-team:ui-autotest` 跑在 **playwright MCP**（`browser_*` / `mcp__*playwright*__browser_*` 工具控真实浏览器）。这是**运行时依赖**，不是第三方 skill 依赖。

探测：检查当前会话是否已有 `browser_navigate` / `browser_snapshot` 等 `playwright` MCP 工具可用（看工具清单里有没有 `playwright` 命名空间的 `browser_*`）。

- **已可用** → 报告「playwright MCP 就绪，qa / ui-autotest 可跑」。
- **缺失** → 引导用户安装并启用 playwright MCP（官方包 `@playwright/mcp` 或对应 MCP 插件），提示：装好后需重启 session 才注入 `browser_*` 工具。**不要替用户自动改全局 MCP 配置**——只给一句可照做的指引。

> qa / ui-autotest 是 env-gated（需被测环境 URL + 浏览器运行时）；没有 playwright MCP 不阻断其它员工，只是这两个能力跑不了，如实告知即可。

---

## 第 3 步：探测 understand-anything（code-graph / ingestor 用）

ingestor（`ieidev_ingestor`，code-graph 能力）依赖 **understand-anything** 插件（跨 marketplace）。它已在本插件 `plugin.json` 的 `dependencies` 里声明 + marketplace `allowCrossMarketplaceDependenciesOn` 放行，正常会**依赖级联自动装**。本步只兜底探测：

```bash
ls -d "$HOME"/.claude/plugins/cache/understand-anything/understand-anything/*/ 2>/dev/null | sort -V | tail -1
```

- **找到** → 报告「understand-anything 就绪」。
- **没找到** → 引导：`/plugin marketplace add <understand-anything marketplace>` 再 `/plugin install understand-anything@understand-anything`（或确认级联依赖已开启）。缺它只影响 code-graph，不阻断核心员工。

---

## 收尾报告（给用户一屏）

逐条汇报四件事的状态，每条 ✅ 就绪 / ⚠️ 需手动一步 / ⛔ 失败：

1. **Python 路径**（第 0 步 import 验证结果）—— 这是装机能不能跑的根，必须 ✅；
2. **statusLine**（第 1 步 action：created / updated / skipped_foreign / forced，及生效提示）；
3. **playwright MCP**（第 2 步：就绪 / 需装）；
4. **understand-anything**（第 3 步：就绪 / 需装）。

凡 ⚠️/⛔ 项，给出**下一步该敲什么**的具体指引（不要泛泛说"请配置环境"）。全 ✅ 则一句话收尾：「ieidev-team 装机残余已接线完毕，重载/重启 session 后即可用 `/ieidev-team:goal` 或 `/ieidev-team:flow-driver` 跑数字员工。」
