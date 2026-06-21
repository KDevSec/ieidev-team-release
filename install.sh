#!/usr/bin/env bash
#
# ieidev-team 一行装机（OMC 式 Layer-1）。
#
#   curl -fsSL .../install.sh | bash      # 或克隆后 ./install.sh
#
# 做四件事，全程幂等、可重跑：
#   1. 注册 marketplace（claude plugin marketplace add KDevSec/ieidev-team）
#   2. 装 plugin           （claude plugin install ieidev-team@ieidev）
#   3. 接 statusLine       （HUD setup 写 settings.json，指向已装插件绝对路径）
#   4. 验证装后即见状态栏   （跑安装好的 __main__.py，应输出「ieidev 团队…」）
#
# 设计取自 OMC（docs/.../oh-my-claudecode）：用 Claude Code **文档化的 plugin 子命令**
# 注册 marketplace / 装插件，而**不**手写 ~/.claude/plugins/known_marketplaces.json 等
# CC 内部配置（版本脆）。幂等判定委托给 ieidev_hud.installer 决策核（对 list --json 判在/不在）。
#
# 安全：所有写操作落在 ${CLAUDE_CONFIG_DIR:-~/.claude}。设 CLAUDE_CONFIG_DIR=<临时目录>
# 即可对沙箱配置目录演练，绝不碰真实 ~/.claude（测试/CI 正是这么跑的）。

set -euo pipefail

# ── 可覆盖参数（环境变量）──
MARKETPLACE_SOURCE="${IEIDEV_MARKETPLACE_SOURCE:-KDevSec/ieidev-team}"  # 也可传本地路径做离线装
PLUGIN_SCOPE="${IEIDEV_PLUGIN_SCOPE:-user}"                              # user|project|local
SETUP_SCOPE_FLAG="--user"                                                # HUD setup 默认写用户级
[ "$PLUGIN_SCOPE" = "project" ] && SETUP_SCOPE_FLAG="--project"

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

log()  { printf '  %s\n' "$*"; }
ok()   { printf '✅ %s\n' "$*"; }
warn() { printf '⚠️  %s\n' "$*"; }
die()  { printf '⛔ %s\n' "$*" >&2; exit 1; }

# ── 0. 前置检查 ──
command -v claude  >/dev/null 2>&1 || die "未找到 claude CLI。请先装 Claude Code，再重跑。"
command -v python3 >/dev/null 2>&1 || die "未找到 python3。状态栏需要 python3。"

# installer 决策核：优先用「已装插件里的」副本（装后），否则用「本仓 / curl 落地的」副本（装前）。
# 这样 install.sh 既能在源仓 dogfood，也能被 curl 单独跑。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
INSTALLER_PYDIR=""
if [ -d "$SCRIPT_DIR/pyieidev/ieidev_hud" ]; then
  INSTALLER_PYDIR="$SCRIPT_DIR/pyieidev"   # 源仓 / 克隆布局
fi
# 小工具：对 list --json 判在/不在（委托 ieidev_hud.installer，缺则保守当"不在"→去跑幂等的 add/install）
inst() {  # inst <subcmd> ; stdin = list --json
  local sub="$1"
  if [ -n "$INSTALLER_PYDIR" ]; then
    PYTHONPATH="$INSTALLER_PYDIR" python3 -m ieidev_hud.installer "$sub"
  else
    return 2  # 决策核不可用 → 调用方按"不在"处理
  fi
}

printf '== ieidev-team 一行装机（config dir: %s）==\n' "$CONFIG_DIR"

# ── 1. 注册 marketplace（幂等）──
MK_LIST="$(claude plugin marketplace list --json 2>/dev/null || echo '[]')"
if printf '%s' "$MK_LIST" | inst marketplace-present; then
  log "marketplace 'ieidev' 已注册，跳过"
else
  log "注册 marketplace: claude plugin marketplace add $MARKETPLACE_SOURCE"
  claude plugin marketplace add "$MARKETPLACE_SOURCE" || die "marketplace add 失败（检查源 $MARKETPLACE_SOURCE 是否可达/有效）"
  ok "marketplace 已注册"
fi

# ── 2. 装 plugin（幂等）──
PG_LIST="$(claude plugin list --json 2>/dev/null || echo '[]')"
if printf '%s' "$PG_LIST" | inst plugin-present; then
  log "plugin 'ieidev-team@ieidev' 已安装，跳过"
else
  log "安装 plugin: claude plugin install ieidev-team@ieidev --scope $PLUGIN_SCOPE"
  # install 即便有跨 marketplace 依赖告警（understand-anything）仍会成功，故不让告警阻断
  claude plugin install "ieidev-team@ieidev" --scope "$PLUGIN_SCOPE" || die "plugin install 失败"
  ok "plugin 已安装"
fi

# ── 3. 定位已装插件根（含 pyieidev/）──
PG_LIST="$(claude plugin list --json 2>/dev/null || echo '[]')"
PLUGIN_ROOT="$(printf '%s' "$PG_LIST" | inst plugin-path || true)"
if [ -z "${PLUGIN_ROOT:-}" ] || [ ! -d "$PLUGIN_ROOT/pyieidev/ieidev_hud" ]; then
  # 决策核不可用 / 路径异常时兜底用缓存约定路径
  PLUGIN_ROOT="$(ls -d "$CONFIG_DIR"/plugins/cache/*/ieidev-team/*/ 2>/dev/null | sort -V | tail -1)"
  PLUGIN_ROOT="${PLUGIN_ROOT%/}"
fi
[ -d "${PLUGIN_ROOT:-/nonexistent}/pyieidev/ieidev_hud" ] || die "装好后未定位到含 pyieidev/ 的插件根（PLUGIN_ROOT=$PLUGIN_ROOT）"
log "插件根: $PLUGIN_ROOT"

# ── 4. 接 statusLine（HUD setup，指向已装插件绝对路径，幂等）──
log "接 statusLine 进 settings.json（$SETUP_SCOPE_FLAG）"
PYTHONPATH="$PLUGIN_ROOT/pyieidev" python3 -m ieidev_hud setup "$SETUP_SCOPE_FLAG" --workspace "$(pwd)" \
  || die "HUD setup 失败"

# ── 5. 验证装后即见状态栏（跑装好的 __main__.py，自举 sys.path，不依赖 PYTHONPATH）──
LINE="$(env -u PYTHONPATH python3 "$PLUGIN_ROOT/pyieidev/ieidev_hud/__main__.py" statusline </dev/null 2>/dev/null || true)"
if printf '%s' "$LINE" | grep -q "ieidev 团队"; then
  ok "状态栏就绪：$(printf '%s' "$LINE" | sed 's/\x1b\[[0-9;]*m//g')"
else
  warn "statusLine 渲染未输出预期品牌串（装机仍算成功，重载/重启 session 后状态栏应生效）"
fi

printf '\n'
ok "ieidev-team 装机完成。重载插件（/reload-plugins）或重启 session 后状态栏生效。"
log "下一步可跑：/ieidev-team:goal 或 /ieidev-team:flow-driver"
log "可选依赖（缺则 code-graph 不可用）：claude plugin install understand-anything@understand-anything"
