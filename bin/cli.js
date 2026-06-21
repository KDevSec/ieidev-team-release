#!/usr/bin/env node
//
// npx ieidev-team —— OMC 式一行装机（node 原生跨平台入口）。
//
//   npx ieidev-team                          # 用户级一行装好（marketplace + plugin + statusLine）
//   npx ieidev-team --project                # 写项目级 settings.json
//   npx ieidev-team --marketplace-source <p> # 离线/本地源装（默认 GitHub 简写 KDevSec/ieidev-team）
//
// 做四件事，全程幂等、可重跑（与 install.sh **同序同命令**）：
//   1. 注册 marketplace（claude plugin marketplace add <source>）
//   2. 装 plugin        （claude plugin install ieidev-team@ieidev --scope <scope>）
//   3. 接 statusLine    （python3 -m ieidev_hud setup --user|--project --workspace <cwd>）
//   4. 验证装后即见      （跑装好的 __main__.py，应输出「ieidev 团队…」）
//
// 为什么 node 原生而非 `bash install.sh`：npx 常跨平台用（含 Windows，无 bash），node 自带。
// 为什么不发散：**幂等判定不在本文件里重写**——和 install.sh 一样委托给 ieidev_hud.installer
// 决策核（`python3 -m ieidev_hud.installer marketplace-present|plugin-present|plugin-path`，
// 喂 `claude ... list --json` 到 stdin，靠 exit-code/stdout 拿判定）。两个壳（bash + node）
// 跑同一串 claude 命令、共用同一个 Python 决策核，逻辑单一来源。
//
// 安全：所有写操作落在 ${CLAUDE_CONFIG_DIR:-~/.claude}（HUD --user 写 ${HOME}/.claude）。
// 设 CLAUDE_CONFIG_DIR=<临时目录> 即可对沙箱演练，绝不碰真实 ~/.claude（测试正是这么跑的）。

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ── 包内布局：本文件在 <pkg>/bin/cli.js，装机件 pyieidev/ 在 <pkg>/pyieidev/ ──
const PKG_ROOT = path.resolve(__dirname, '..');
const PKG_PYIEIDEV = path.join(PKG_ROOT, 'pyieidev'); // 含 ieidev_hud.installer 决策核（装前判定用）

// 安装目标（与 installer.py 常量一致；权威来源仍是 installer.py，这里只是壳显示）。
const PLUGIN_ID = 'ieidev-team@ieidev';
const DEFAULT_MARKETPLACE_SOURCE = 'KDevSec/ieidev-team';

// ── 小工具：着色日志（无 TTY/不支持时自动降级为纯文本）──
const color = process.stdout.isTTY ? (c, s) => `\x1b[${c}m${s}\x1b[0m` : (_c, s) => s;
const log = (s) => console.log('  ' + s);
const ok = (s) => console.log(color('32', '✅ ') + s);
const warn = (s) => console.log(color('33', '⚠️  ') + s);
const die = (s) => { console.error(color('31', '⛔ ') + s); process.exit(1); };

// ── argv 解析（透传 install.sh 同款开关）──
function parseArgs(argv) {
  const opts = {
    scope: process.env.IEIDEV_PLUGIN_SCOPE || 'user', // user|project|local（plugin install --scope）
    setupScope: '--user',                              // HUD setup 默认写用户级
    marketplaceSource: process.env.IEIDEV_MARKETPLACE_SOURCE || DEFAULT_MARKETPLACE_SOURCE,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--user') { opts.scope = 'user'; opts.setupScope = '--user'; }
    else if (a === '--project') { opts.scope = 'project'; opts.setupScope = '--project'; }
    else if (a === '--marketplace-source') {
      opts.marketplaceSource = argv[++i];
      if (!opts.marketplaceSource) die('--marketplace-source 需要一个值（本地路径或 owner/repo）');
    } else if (a === '-h' || a === '--help') {
      printHelp(); process.exit(0);
    } else {
      die(`未知参数：${a}（支持 --user / --project / --marketplace-source <path> / --help）`);
    }
  }
  return opts;
}

function printHelp() {
  console.log(`npx ieidev-team —— ieidev 数字员工集群一行装机

用法:
  npx ieidev-team [--user|--project] [--marketplace-source <path|owner/repo>]

选项:
  --user                写用户级 statusLine（默认）
  --project             写项目级 statusLine（当前目录 .claude/settings.json）
  --marketplace-source  marketplace 源（默认 ${DEFAULT_MARKETPLACE_SOURCE}；可传本地路径离线装）
  -h, --help            显示本帮助

环境变量:
  CLAUDE_CONFIG_DIR        配置目录（默认 ~/.claude；设临时目录可沙箱演练）
  IEIDEV_PLUGIN_SCOPE      plugin install --scope（user|project|local）
  IEIDEV_MARKETPLACE_SOURCE marketplace 源覆盖`);
}

// ── 跑外部命令（同步，继承/捕获按需）──
function run(cmd, args, { capture = false, stdin = null } = {}) {
  const r = spawnSync(cmd, args, {
    encoding: 'utf-8',
    input: stdin === null ? undefined : stdin,
    stdio: capture
      ? ['pipe', 'pipe', 'pipe']
      : (stdin === null ? 'inherit' : ['pipe', 'inherit', 'inherit']),
  });
  return r;
}

// ── claude plugin list --json / marketplace list --json → 决策核判定（委托 installer.py）──
// installerSub：marketplace-present | plugin-present | plugin-path
// 决策核不可用（无 python3 / 无 pyieidev）→ 返回 null，调用方按"不在/未知"保守处理（去跑幂等步）。
function installerDecide(pythonBin, listJson, installerSub) {
  if (!pythonBin || !fs.existsSync(path.join(PKG_PYIEIDEV, 'ieidev_hud', 'installer.py'))) {
    return null;
  }
  const r = spawnSync(pythonBin, ['-m', 'ieidev_hud.installer', installerSub], {
    encoding: 'utf-8',
    input: listJson,
    env: { ...process.env, PYTHONPATH: PKG_PYIEIDEV },
  });
  if (r.error || typeof r.status !== 'number') return null;
  // 约定：present → exit 0；absent → exit 1；plugin-path 把路径写到 stdout。
  return { present: r.status === 0, stdout: (r.stdout || '').trim(), status: r.status };
}

function claudeListJson(claudeBin, kind /* 'marketplace' | 'plugin' */) {
  const args = kind === 'marketplace'
    ? ['plugin', 'marketplace', 'list', '--json']
    : ['plugin', 'list', '--json'];
  const r = run(claudeBin, args, { capture: true });
  const out = (r.stdout || '').trim();
  return out || '[]';
}

// ── 定位已装插件根（含 pyieidev/）：优先决策核 plugin-path，否则缓存约定路径兜底 ──
function locatePluginRoot(claudeBin, pythonBin, configDir) {
  const listJson = claudeListJson(claudeBin, 'plugin');
  const decided = installerDecide(pythonBin, listJson, 'plugin-path');
  let root = decided && decided.present ? decided.stdout : '';
  if (root && fs.existsSync(path.join(root, 'pyieidev', 'ieidev_hud'))) return root;

  // 兜底：扫缓存约定路径，取版本号最大者
  const cacheGlobBase = path.join(configDir, 'plugins', 'cache');
  try {
    const candidates = [];
    for (const mk of safeReaddir(cacheGlobBase)) {
      const teamDir = path.join(cacheGlobBase, mk, 'ieidev-team');
      for (const ver of safeReaddir(teamDir)) {
        const verDir = path.join(teamDir, ver);
        if (fs.existsSync(path.join(verDir, 'pyieidev', 'ieidev_hud'))) {
          candidates.push(verDir);
        }
      }
    }
    candidates.sort(); // 字典序近似版本序（与 install.sh `sort -V | tail -1` 对齐取尾）
    if (candidates.length) return candidates[candidates.length - 1];
  } catch (_e) { /* ignore */ }
  return '';
}

function safeReaddir(p) {
  try { return fs.readdirSync(p); } catch (_e) { return []; }
}

function which(bin) {
  // 跨平台 which：用 PATH 探测（避免依赖外部 which/where）。
  const exts = process.platform === 'win32'
    ? (process.env.PATHEXT || '.EXE;.CMD;.BAT').split(';')
    : [''];
  const dirs = (process.env.PATH || '').split(path.delimiter);
  for (const d of dirs) {
    for (const ext of exts) {
      const full = path.join(d, bin + ext);
      try { fs.accessSync(full, fs.constants.X_OK); return full; } catch (_e) { /* next */ }
    }
  }
  return null;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const configDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');

  // ── 0. 前置检查（缺失给清晰报错引导）──
  const claudeBin = which('claude');
  if (!claudeBin) {
    die('未找到 claude CLI。请先装 Claude Code（https://docs.claude.com/claude-code），再重跑 `npx ieidev-team`。');
  }
  const pythonBin = which('python3') || which('python');
  if (!pythonBin) {
    die('未找到 python3。状态栏（HUD）需要 python3，请先安装后重跑。');
  }

  console.log(`== ieidev-team 一行装机（config dir: ${configDir}）==`);

  // ── 1. 注册 marketplace（幂等，判定委托决策核）──
  {
    const listJson = claudeListJson(claudeBin, 'marketplace');
    const decided = installerDecide(pythonBin, listJson, 'marketplace-present');
    if (decided && decided.present) {
      log("marketplace 'ieidev' 已注册，跳过");
    } else {
      log(`注册 marketplace: claude plugin marketplace add ${opts.marketplaceSource}`);
      const r = run(claudeBin, ['plugin', 'marketplace', 'add', opts.marketplaceSource]);
      if (r.status !== 0) die(`marketplace add 失败（检查源 ${opts.marketplaceSource} 是否可达/有效）`);
      ok('marketplace 已注册');
    }
  }

  // ── 2. 装 plugin（幂等）──
  {
    const listJson = claudeListJson(claudeBin, 'plugin');
    const decided = installerDecide(pythonBin, listJson, 'plugin-present');
    if (decided && decided.present) {
      log(`plugin '${PLUGIN_ID}' 已安装，跳过`);
    } else {
      log(`安装 plugin: claude plugin install ${PLUGIN_ID} --scope ${opts.scope}`);
      // install 即便有跨 marketplace 依赖告警（understand-anything）仍会成功，不让告警阻断。
      const r = run(claudeBin, ['plugin', 'install', PLUGIN_ID, '--scope', opts.scope]);
      if (r.status !== 0) die('plugin install 失败');
      ok('plugin 已安装');
    }
  }

  // ── 3. 定位已装插件根（含 pyieidev/）──
  const pluginRoot = locatePluginRoot(claudeBin, pythonBin, configDir);
  if (!pluginRoot || !fs.existsSync(path.join(pluginRoot, 'pyieidev', 'ieidev_hud'))) {
    die(`装好后未定位到含 pyieidev/ 的插件根（PLUGIN_ROOT=${pluginRoot}）`);
  }
  log(`插件根: ${pluginRoot}`);

  // ── 4. 接 statusLine（HUD setup，指向已装插件绝对路径，幂等）──
  log(`接 statusLine 进 settings.json（${opts.setupScope}）`);
  {
    const r = spawnSync(pythonBin, ['-m', 'ieidev_hud', 'setup', opts.setupScope, '--workspace', process.cwd()], {
      stdio: 'inherit',
      env: { ...process.env, PYTHONPATH: path.join(pluginRoot, 'pyieidev') },
    });
    if (r.status !== 0) die('HUD setup 失败');
  }

  // ── 5. 验证装后即见（跑装好的 __main__.py，自举 sys.path，不依赖 PYTHONPATH）──
  {
    const mainPy = path.join(pluginRoot, 'pyieidev', 'ieidev_hud', '__main__.py');
    const env = { ...process.env };
    delete env.PYTHONPATH; // 同 install.sh `env -u PYTHONPATH`
    const r = spawnSync(pythonBin, [mainPy, 'statusline'], {
      encoding: 'utf-8', input: '', env,
    });
    const line = (r.stdout || '');
    if (line.includes('ieidev 团队')) {
      // 去 ANSI 后展示
      ok('状态栏就绪：' + line.replace(/\x1b\[[0-9;]*m/g, '').trim());
    } else {
      warn('statusLine 渲染未输出预期品牌串（装机仍算成功，重载/重启 session 后状态栏应生效）');
    }
  }

  console.log('');
  ok('ieidev-team 装机完成。重载插件（/reload-plugins）或重启 session 后状态栏生效。');
  log('下一步可跑：/ieidev-team:goal 或 /ieidev-team:flow-driver');
  log('可选依赖（缺则 code-graph 不可用）：claude plugin install understand-anything@understand-anything');
}

main();
