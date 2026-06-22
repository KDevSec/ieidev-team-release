r"""frontend.render_shell —— 全局 HUD 的 client-render shell（#9 Plan-2 Task 2）。

复用 scratch/hud-mockup.html 的 CSS / JS（逐字拷贝为 Python 字符串），把 JS 从
「内联常量 DATA/PROJ + 硬编码左树」改造为「由 model 驱动」：

  - `boot(model)`     从 model.projects[].goals 构建 DATA/PROJ、renderTree、填 KPI、起首选。
  - `renderTree(m)`   按 model.projects 生成左树（项目分组可折叠 + goal 行：state→icon/class/pctmini/owner 徽标）。
  - `buildActive()`   直接返回 model.active_dispatches（Plan-1 已算好，不再现推）。
  - `reboot(m)`       实时模式 SSE 重渲：快照 UI 态（选中 key / 各 proj 折叠 / lens / drawer）→ 重渲 → 恢复。

两种渲染模式：
  - model 给定（静态/离线）→ 内联 ``window.__MODEL__ = <json>``，``boot`` 直接消费，不连 SSE。
  - model=None（实时）     → ``window.__MODEL__ = null``，``fetch('/model.json')`` + ``EventSource('/events')``。

自包含、零外链（无外部字体/CDN/JS/CSS）。model JSON 内联时把 ``</`` → ``<\/`` 转义防 ``</script>`` 截断注入。
"""
import json

__all__ = ["render_shell"]


# ====================================================================
# CSS —— 逐字拷自 mockup <style>，仅删 body::before 噪点纹理（其 data-URI
# 内含 xmlns='http://www.w3.org/2000/svg'，与「零外链」自包含约束的
# 字面校验冲突；该规则为 0.035 不透明度装饰层，移除后视觉 ≥90% 一致）。
# ====================================================================
_CSS = r""":root{
  --bg:#081120; --bg-2:#0a1626; --panel:#13243c; --panel-2:#16273f;
  --line:#26405f; --line-soft:#1b3050;
  --ink:#d7e2f0; --mut:#8ea4be; --mut-2:#5f7596; --white:#f2f7fc;
  --blue:#4a9eff; --teal:#2ec5b6; --gold:#f5b740; --red:#ff5d6c; --green:#43dd8b;
  --blue-glow:rgba(74,158,255,.45); --teal-glow:rgba(46,197,182,.4);
  --cjk:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;
  --mono:ui-monospace,"SFMono-Regular","JetBrains Mono","Cascadia Code","Consolas",monospace;
  --r:10px; --r-sm:7px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font-family:var(--cjk); color:var(--ink); font-size:13px; line-height:1.55;
  background:
    radial-gradient(1100px 620px at 78% -8%, rgba(46,197,182,.10), transparent 60%),
    radial-gradient(900px 560px at 8% 108%, rgba(74,158,255,.10), transparent 55%),
    var(--bg);
  overflow:hidden;
}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.app{display:grid;grid-template-columns:330px 1fr;grid-template-rows:auto auto 1fr;height:100vh}

/* ============ 顶部全局条 ============ */
.topbar{
  grid-column:1/-1;display:flex;align-items:center;gap:14px;
  padding:11px 20px;background:linear-gradient(180deg,#13243c,#0e1d31);
  border-bottom:1px solid var(--line);position:relative;z-index:5;
}
.logo{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--white);letter-spacing:.3px}
.logo .mk{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--blue),var(--teal));color:#06101e;font-size:13px;font-weight:800}
.logo small{font-weight:600;color:var(--mut);font-size:11px;letter-spacing:2px;text-transform:uppercase}
.topbar .scope{font-family:var(--mono);font-size:11px;color:var(--mut);
  border:1px solid var(--line);border-radius:20px;padding:3px 11px}
.topbar .scope b{color:var(--teal)}
.spacer{margin-left:auto}
.kpi{display:flex;gap:18px;align-items:center;font-size:11px;color:var(--mut)}
.kpi b{color:var(--white);font-family:var(--mono);font-size:15px;font-weight:700;margin-right:3px}
.kpi .dot{color:var(--blue)}.kpi .dot.g{color:var(--green)}.kpi .dot.y{color:var(--gold)}
.live{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:700;
  color:var(--green);letter-spacing:1px}
.live i{width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 10px var(--green);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.78)}}
.refresh{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--mut);
  border:1px solid var(--line);border-radius:7px;padding:4px 9px;cursor:pointer;user-select:none}
.refresh:hover{border-color:var(--blue);color:var(--blue)}
.refresh i{animation:spin 6s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
.gen{font-family:var(--mono);font-size:10.5px;color:var(--mut-2)}

/* ============ 在跑总览带（活跃派单 = 未配对 dispatch-start 的聚合，非「员工占用」）============
   主语 = goal/派单；角色只是属性。孤儿派单（start 久无 done）按 ts 老化标 stale。 */
.empband{grid-column:1/-1;display:flex;align-items:center;gap:12px;
  padding:9px 20px;background:linear-gradient(180deg,#0c1c30,#0a1626);
  border-bottom:1px solid var(--line);position:relative;z-index:4}
.empband .bandlab{display:flex;flex-direction:column;justify-content:center;gap:2px;
  flex:0 0 150px;padding-right:12px;border-right:1px solid var(--line)}
.empband .bandlab .t{font-size:11.5px;font-weight:700;color:var(--white)}
.empband .bandlab .s{font-family:var(--mono);font-size:9px;color:var(--mut-2)}
.lens{flex:0 0 auto;display:flex;align-items:center;gap:6px;padding-right:12px;border-right:1px solid var(--line)}
.lchip{display:flex;align-items:center;gap:6px;cursor:pointer;border:1px solid var(--line);
  border-radius:20px;padding:4px 9px 4px 7px;background:#0e1d31;user-select:none;white-space:nowrap}
.lchip .lav{font-size:13px;filter:grayscale(.4)}
.lchip .lnm{font-size:11px;color:var(--mut)}
.lchip .lcnt{font-family:var(--mono);font-size:10px;color:var(--mut-2);background:transparent;
  border-radius:10px;min-width:15px;text-align:center;padding:0 4px}
.lchip.has{border-color:rgba(74,158,255,.3)}
.lchip.has .lav{filter:none}
.lchip.has .lnm{color:var(--ink)}
.lchip.has .lcnt{background:var(--blue);color:#06101e;font-weight:700}
.lchip:hover{border-color:var(--blue)}
.lchip.on{border-color:var(--blue);background:rgba(74,158,255,.16);box-shadow:0 0 0 1px var(--blue) inset}
.lchip.on .lnm{color:var(--white)}
.lchip .lwarn{color:var(--gold);font-size:10px;margin-left:-2px}
.lclear{flex:0 0 auto;font-family:var(--mono);font-size:10px;color:var(--blue);cursor:pointer;
  border:1px solid rgba(74,158,255,.3);border-radius:20px;padding:3px 9px;white-space:nowrap}
.lclear:hover{background:rgba(74,158,255,.1)}
.eband{flex:1;display:flex;align-items:center;gap:10px;overflow-x:auto;padding-bottom:2px}
.eband::-webkit-scrollbar{height:6px}.eband::-webkit-scrollbar-thumb{background:#1d324d;border-radius:3px}
.acount{flex:0 0 auto;font-family:var(--mono);font-size:10px;color:var(--mut);
  border:1px solid var(--line);border-radius:20px;padding:3px 10px;white-space:nowrap}
.acount b{color:var(--green)}.acount .w{color:var(--gold)}
.acard{flex:0 0 auto;display:flex;align-items:center;gap:10px;min-width:236px;max-width:310px;
  background:linear-gradient(180deg,rgba(74,158,255,.07),#0e1d31);
  border:1px solid rgba(74,158,255,.3);border-radius:9px;padding:7px 11px;cursor:pointer}
.acard:hover{border-color:var(--blue)}
.acard.stale{background:#1a1510;border-color:rgba(245,183,64,.4)}
.acard .aav{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;flex:0 0 30px;
  font-size:15px;background:#0a1626;border:1px solid var(--blue);color:var(--blue);position:relative}
.acard.stale .aav{border-color:var(--gold);color:var(--gold)}
.acard .aav::after{content:"";position:absolute;width:8px;height:8px;border-radius:50%;
  background:var(--green);box-shadow:0 0 8px var(--green);right:-3px;top:-3px;animation:pulse 1.5s infinite}
.acard.stale .aav::after{background:var(--gold);box-shadow:0 0 8px var(--gold);animation:none}
.acard .abody{flex:1;min-width:0}
.acard .arow1{display:flex;align-items:center;gap:7px}
.acard .apj{font-family:var(--mono);font-size:11px;color:var(--teal);font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.acard .abadge{font-family:var(--mono);font-size:9px;border-radius:20px;padding:0 6px;white-space:nowrap;flex:0 0 auto}
.acard .abadge.run{color:var(--green);border:1px solid rgba(67,221,139,.35)}
.acard .abadge.st{color:var(--gold);border:1px solid rgba(245,183,64,.4)}
.acard .arow2{font-size:10.5px;color:var(--mut);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.acard .arole{color:var(--ink);font-weight:600}
.acard .and{font-family:var(--mono);color:var(--ink)}
.acard .ael{font-family:var(--mono);color:var(--mut-2)}
.aempty{flex:1;color:var(--mut-2);font-size:11.5px;padding-left:4px}

/* ============ 左侧任务树 ============ */
.tree{background:linear-gradient(180deg,#0a1626,#091322);border-right:1px solid var(--line);
  overflow-y:auto;padding:12px 0 28px}
.tree::-webkit-scrollbar{width:8px}.tree::-webkit-scrollbar-thumb{background:#1d324d;border-radius:4px}
.tree-head{display:flex;align-items:center;gap:8px;padding:4px 16px 12px;color:var(--mut);
  font-size:10.5px;letter-spacing:2px;text-transform:uppercase}
.tree-head .ln{flex:1;height:1px;background:var(--line)}
.search{margin:0 14px 12px;display:flex;align-items:center;gap:8px;background:#0c1a2c;
  border:1px solid var(--line);border-radius:8px;padding:7px 10px;color:var(--mut-2);font-size:12px}
.search input{background:none;border:0;outline:0;color:var(--ink);font-family:var(--cjk);
  font-size:12px;width:100%}

.proj{margin:2px 0}
.proj-h{display:flex;align-items:center;gap:8px;padding:7px 16px;cursor:pointer;user-select:none;
  color:var(--ink);font-weight:600;font-size:12.5px}
.proj-h:hover{background:rgba(74,158,255,.06)}
.proj-h .caret{color:var(--mut-2);font-size:10px;transition:transform .18s;width:9px}
.proj.collapsed .caret{transform:rotate(-90deg)}
.proj.collapsed .proj-body{display:none}
.proj-h .pname{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.proj-h .ppath{font-family:var(--mono);font-size:9.5px;color:var(--mut-2);font-weight:400}
.proj-h .cnt{font-family:var(--mono);font-size:10px;color:var(--mut);
  background:#10203a;border:1px solid var(--line);border-radius:10px;padding:1px 7px}
.proj-body{padding:2px 0 6px}

.goal{display:flex;align-items:center;gap:9px;padding:7px 14px 7px 30px;cursor:pointer;
  position:relative;border-left:2px solid transparent}
.goal:hover{background:rgba(74,158,255,.05)}
.goal.sel{background:linear-gradient(90deg,rgba(74,158,255,.16),transparent 90%);
  border-left-color:var(--blue)}
.goal .ic{width:16px;text-align:center;font-size:12px;flex:0 0 16px;position:relative}
.goal .gname{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12.5px}
.goal .pctmini{font-family:var(--mono);font-size:10px;color:var(--mut)}
.goal.active .ic{color:var(--blue)}
.goal.active .gname{color:var(--white)}
.goal.done{opacity:.55}
.goal.done .ic{color:var(--green)}
.goal.done .gname{color:var(--mut)}
.goal.stale .ic{color:var(--gold)}
.goal.stale .gname{color:var(--gold);opacity:.85}
.goal.stale .pctmini{color:var(--gold)}
.own{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;flex:0 0 18px;
  font-family:var(--mono);font-size:9px;font-weight:700;color:#06101e;
  background:linear-gradient(135deg,#7fb6ff,#4a9eff);border:1px solid rgba(255,255,255,.25)}
.own.alt{background:linear-gradient(135deg,#5fe0cf,#2ec5b6)}
.goal.active .ic::after{content:"";position:absolute;left:18px;top:50%;width:5px;height:5px;
  margin-top:-2.5px;border-radius:50%;background:var(--blue);box-shadow:0 0 7px var(--blue-glow);
  animation:pulse 1.6s infinite}

.donegrp{margin:6px 14px 0;border-top:1px dashed var(--line)}
.donegrp-h{display:flex;align-items:center;gap:7px;padding:9px 2px 6px 16px;cursor:pointer;
  color:var(--mut-2);font-size:10.5px;letter-spacing:1px}
.donegrp-h .caret{font-size:9px;transition:transform .18s}
.donegrp.collapsed .caret{transform:rotate(-90deg)}
.donegrp.collapsed .donegrp-body{display:none}

/* ============ 右栏 ============ */
.detail{overflow-y:auto;padding:20px 26px 40px;position:relative}
.detail::-webkit-scrollbar{width:9px}.detail::-webkit-scrollbar-thumb{background:#1d324d;border-radius:4px}
.empty{display:grid;place-items:center;height:100%;color:var(--mut-2);font-size:13px}

.d-head{display:flex;align-items:flex-start;gap:16px;margin-bottom:18px}
.d-title h1{font-size:21px;color:var(--white);font-weight:700;letter-spacing:.3px;line-height:1.25}
.d-title .sub{display:flex;align-items:center;gap:10px;margin-top:6px;color:var(--mut);font-size:11.5px}
.d-title .slug{font-family:var(--mono);color:var(--teal);background:rgba(46,197,182,.1);
  border:1px solid rgba(46,197,182,.25);border-radius:5px;padding:1px 8px;font-size:11px}
.ownerbadge{display:inline-flex;align-items:center;gap:7px;color:var(--mut);font-size:11px}
.ownerbadge .own{width:20px;height:20px;font-size:9.5px}
.ring{--p:60;flex:0 0 92px;width:92px;height:92px;border-radius:50%;display:grid;place-items:center;
  background:
    radial-gradient(closest-side,var(--panel) 79%,transparent 80% 100%),
    conic-gradient(var(--teal) calc(var(--p)*1%), #1c3050 0);
  position:relative}
.ring::after{content:"";position:absolute;inset:6px;border-radius:50%;box-shadow:inset 0 0 18px rgba(46,197,182,.25)}
.ring b{font-family:var(--mono);font-size:23px;color:var(--white);font-weight:700;line-height:1}
.ring small{font-size:9.5px;color:var(--mut);margin-top:2px}

.card{background:linear-gradient(180deg,var(--panel-2),#12233a);border:1px solid var(--line);
  border-radius:var(--r);margin-bottom:14px;overflow:hidden}
.card-h{display:flex;align-items:center;gap:9px;padding:9px 14px;font-size:12px;font-weight:700;
  color:var(--white);border-bottom:1px solid var(--line);background:rgba(255,255,255,.015)}
.card-h .tag{margin-left:auto;font-family:var(--mono);font-size:10px;font-weight:600;color:var(--mut)}
.card-b{padding:13px 14px}

/* 阶段路线 */
.route{display:flex;align-items:stretch;gap:0}
.rstep{flex:1;position:relative;display:flex;flex-direction:column;align-items:center;gap:7px;padding:4px 6px}
.rstep .node{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:15px;
  background:#0e1d31;border:2px solid var(--line);color:var(--mut);z-index:2}
.rstep .rlab{font-size:11px;color:var(--mut);font-weight:600}
.rstep .rflow{font-family:var(--mono);font-size:9px;color:var(--mut-2)}
.rstep::before{content:"";position:absolute;top:21px;left:-50%;width:100%;height:2px;background:var(--line);z-index:1}
.rstep:first-child::before{display:none}
.rstep.done .node{border-color:var(--teal);color:var(--teal);background:rgba(46,197,182,.1)}
.rstep.done::before{background:var(--teal)}
.rstep.done .rlab{color:var(--ink)}
.rstep.active .node{border-color:var(--blue);color:var(--blue);background:rgba(74,158,255,.12);
  box-shadow:0 0 0 4px rgba(74,158,255,.13),0 0 16px var(--blue-glow);animation:nodepulse 1.8s infinite}
.rstep.active::before{background:linear-gradient(90deg,var(--teal),var(--blue))}
.rstep.active .rlab{color:var(--white)}
@keyframes nodepulse{0%,100%{box-shadow:0 0 0 4px rgba(74,158,255,.13),0 0 16px var(--blue-glow)}
  50%{box-shadow:0 0 0 7px rgba(74,158,255,.05),0 0 22px var(--blue-glow)}}
.rstep.pending{opacity:.7}

.nodebar{display:flex;align-items:center;gap:12px;margin-top:14px;padding:9px 12px;
  background:#0e1d31;border:1px solid var(--line);border-radius:var(--r-sm);font-size:12px}
.nodebar .k{color:var(--mut);font-size:11px}
.nodebar .v{font-family:var(--mono);color:var(--white);font-weight:600}
.nodebar .run{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--gold);
  border:1px solid rgba(245,183,64,.3);background:rgba(245,183,64,.08);border-radius:20px;padding:2px 10px}

.wt{display:flex;align-items:center;gap:10px;font-size:12px}
.wt .ic{color:var(--teal)}
.wt code{font-family:var(--mono);font-size:11.5px;color:var(--ink);background:#0c1a2c;
  border:1px solid var(--line);border-radius:5px;padding:2px 9px}
.wt .intent{font-size:10.5px;color:var(--mut);border:1px dashed var(--line);border-radius:5px;padding:1px 7px}

/* story TODO */
.story{display:flex;align-items:center;gap:11px;padding:8px 4px;border-bottom:1px solid rgba(255,255,255,.045)}
.story:last-child{border-bottom:0}
.story .box{font-size:15px;flex:0 0 18px;text-align:center}
.story.done .box{color:var(--green)}.story.prog .box{color:var(--gold)}.story.pend .box{color:var(--mut-2)}
.story .title{flex:1;font-size:12.5px;color:var(--ink)}
.story.done .title{color:var(--mut)}
.story .sr{font-family:var(--mono);font-size:10px;color:var(--blue);background:rgba(74,158,255,.08);
  border:1px solid rgba(74,158,255,.22);border-radius:5px;padding:1px 7px;cursor:default}
.story .sid{font-family:var(--mono);font-size:10px;color:var(--mut-2)}
.story .stt{font-family:var(--mono);font-size:10px}
.story.done .stt{color:var(--green)}.story.prog .stt{color:var(--gold)}.story.pend .stt{color:var(--mut-2)}

/* 监督员告警（原 CQO）*/
.card.alert .card-h{color:var(--red);background:rgba(255,93,108,.06)}
.alertrow{display:flex;align-items:flex-start;gap:10px;padding:7px 2px;font-size:12px;color:var(--ink)}
.alertrow .ic{color:var(--gold);flex:0 0 16px}
.alertrow.crit .ic{color:var(--red)}
.alertrow .meta{margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--mut-2)}
.noalert{color:var(--green);font-size:12px;display:flex;align-items:center;gap:8px}

/* —— 评审流水：时间 + 内容 + 状态 时间线（v2 重做）—— */
.gtl{display:flex;flex-direction:column}
.grow{display:flex;align-items:flex-start;gap:12px;padding:9px 2px;border-bottom:1px solid rgba(255,255,255,.045)}
.grow:last-child{border-bottom:0}
.grow .gts{font-family:var(--mono);font-size:10.5px;color:var(--mut-2);flex:0 0 96px;padding-top:2px}
.grow .gmid{flex:1;min-width:0}
.grow .gname{font-size:12.5px;color:var(--white);font-weight:600}
.grow .gmeta{font-size:10.5px;color:var(--mut);margin-top:1px}
.grow .gmeta .by{font-family:var(--mono);color:var(--blue)}
.grow .gissues{margin-top:5px;display:flex;flex-direction:column;gap:3px}
.grow .gissues div{font-size:11px;color:var(--red);display:flex;gap:6px}
.grow .gissues div::before{content:"›";color:var(--red);opacity:.7}
.grow .gstat{flex:0 0 auto;font-family:var(--mono);font-size:11px;font-weight:700;
  border-radius:6px;padding:3px 10px;white-space:nowrap;height:fit-content}
.grow .gstat.pass{color:var(--green);border:1px solid rgba(67,221,139,.35);background:rgba(67,221,139,.07)}
.grow .gstat.fail{color:var(--red);border:1px solid rgba(255,93,108,.45);background:rgba(255,93,108,.08)}

.note{font-size:10.5px;color:var(--mut-2);font-style:italic;margin-top:8px}
.phase2{font-size:10px;color:var(--mut-2);border:1px dashed var(--line);border-radius:5px;
  padding:1px 7px;font-style:normal}

/* 可点击钻入的 affordance */
.ring.clk,.nodebar.clk{cursor:pointer}
.ring.clk:hover{filter:brightness(1.12)}
.nodebar.clk:hover{border-color:var(--blue)}
.story.clk{cursor:pointer}
.story.clk:hover{background:rgba(74,158,255,.06)}
.story .chev{flex:0 0 12px;color:var(--mut-2);font-size:11px;opacity:0;transition:opacity .15s}
.story.clk:hover .chev{opacity:1}

/* —— 详情抽屉 —— */
.scrim{position:fixed;inset:0;background:rgba(4,9,18,.62);backdrop-filter:blur(2px);
  opacity:0;pointer-events:none;transition:opacity .22s;z-index:20}
.scrim.open{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100vh;width:452px;max-width:93vw;z-index:21;
  background:linear-gradient(180deg,#0e1d31,#0b1626);border-left:1px solid var(--line);
  box-shadow:-26px 0 64px rgba(0,0,0,.5);transform:translateX(100%);
  transition:transform .26s cubic-bezier(.2,.7,.3,1);display:flex;flex-direction:column}
.drawer.open{transform:none}
.drawer-h{display:flex;align-items:flex-start;gap:10px;padding:16px 18px;border-bottom:1px solid var(--line)}
.drawer-h .dh-t{flex:1;min-width:0}
.drawer-h h2{font-size:16px;color:var(--white);font-weight:700;line-height:1.3}
.drawer-h .dh-sub{font-family:var(--mono);font-size:11px;color:var(--mut);margin-top:5px}
.drawer-h .x{cursor:pointer;color:var(--mut);font-size:18px;line-height:1;padding:3px 7px;border-radius:6px}
.drawer-h .x:hover{background:rgba(255,255,255,.06);color:var(--white)}
.drawer-b{flex:1;overflow-y:auto;padding:16px 18px}
.drawer-b::-webkit-scrollbar{width:8px}.drawer-b::-webkit-scrollbar-thumb{background:#1d324d;border-radius:4px}
.dsec{margin-bottom:18px}
.dsec .dl{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--mut-2);
  margin-bottom:9px;display:flex;align-items:center;gap:8px}
.dsec .dl::after{content:"";flex:1;height:1px;background:var(--line)}
.dkv{display:flex;gap:10px;font-size:12.5px;padding:4px 0}
.dkv .k{color:var(--mut);flex:0 0 84px}
.dkv .v{color:var(--ink);font-family:var(--mono);flex:1}
.dpill{font-family:var(--mono);font-size:10px;border-radius:6px;padding:1px 8px}
.dpill.done{color:var(--green);border:1px solid rgba(67,221,139,.35)}
.dpill.prog{color:var(--gold);border:1px solid rgba(245,183,64,.35)}
.dpill.pend{color:var(--mut-2);border:1px solid var(--line)}
.gwt{background:#0c1a2c;border:1px solid var(--line);border-radius:8px;padding:11px 13px;
  font-size:12px;line-height:1.75;margin-bottom:8px}
.gwt b{color:var(--teal);font-family:var(--mono);font-size:10.5px;margin-right:4px}
.tl{position:relative;padding-left:16px}
.tl::before{content:"";position:absolute;left:3px;top:5px;bottom:9px;width:2px;background:var(--line)}
.tl .ti{position:relative;padding:0 0 13px 8px;font-size:12px;color:var(--ink)}
.tl .ti::before{content:"";position:absolute;left:-13px;top:3px;width:8px;height:8px;border-radius:50%;
  background:var(--mut-2);box-shadow:0 0 0 3px rgba(95,117,150,.12)}
.tl .ti.done::before{background:var(--green);box-shadow:0 0 0 3px rgba(67,221,139,.15)}
.tl .ti.now::before{background:var(--blue);box-shadow:0 0 0 3px rgba(74,158,255,.18);animation:pulse 1.6s infinite}
.tl .tt{font-family:var(--mono);font-size:10px;color:var(--mut-2);margin-left:8px}
.dstage{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.045);font-size:12px}
.dstage:last-child{border-bottom:0}
.dstage .si{width:18px;text-align:center}
.dstage.done .si{color:var(--teal)}.dstage.active .si{color:var(--blue)}.dstage.pending .si{color:var(--mut-2)}
.dstage .snm{flex:1}
.dstage .su{font-family:var(--mono);font-size:10px;color:var(--mut-2)}
.placeholder{font-size:10.5px;color:var(--mut-2);font-style:italic;margin-top:6px}

.detail>*{animation:rise .45s cubic-bezier(.2,.7,.3,1) backwards}
.detail .d-head{animation-delay:.02s}
.detail .card:nth-of-type(1){animation-delay:.06s}
.detail .card:nth-of-type(2){animation-delay:.10s}
.detail .card:nth-of-type(3){animation-delay:.14s}
.detail .card:nth-of-type(4){animation-delay:.18s}
.detail .card:nth-of-type(5){animation-delay:.22s}
.detail .card:nth-of-type(6){animation-delay:.26s}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
"""


# ====================================================================
# 骨架 HTML —— body 结构。拷自 mockup <body>，删左树硬编码 .proj/.donegrp、
# 顶部 KPI 硬编码数字、empband 注释外的硬编码；保留所有容器骨架（JS 注入）。
# 顶栏 scope / gen / KPI 数值留空占位，由 boot() 的 renderKPI 填。
# ====================================================================
_SHELL_HTML = r"""<div class="app">

  <!-- ===== 顶部全局条 ===== -->
  <div class="topbar">
    <div class="logo"><span class="mk">i</span>ieidev 全局 HUD <small>数字员工总台</small></div>
    <span class="scope" id="scope">scope <b>--</b></span>
    <div class="spacer"></div>
    <div class="kpi" id="kpi"></div>
    <span class="refresh" onclick="location.reload()"><i>⟳</i> 刷新</span>
    <span class="gen" id="gen">生成 —</span>
    <span class="live"><i></i>LIVE</span>
  </div>

  <!-- ===== 在跑总览带（活跃派单 = 全机未配对 dispatch-start 的聚合；主语是 goal，非员工占用）===== -->
  <div class="empband">
    <div class="bandlab"><span class="t">⚡ 在跑总览</span><span class="s">活跃派单 · 本机全局</span></div>
    <div class="lens" id="lens"><!-- 员工 lens：点角色筛该角色当前在跑的 goal（×N 并行）--></div>
    <div class="eband" id="eband"><!-- JS 注入 --></div>
  </div>

  <!-- ===== 左侧任务树（JS renderTree 注入项目分组 + goal 行）===== -->
  <nav class="tree">
    <div class="tree-head">任务树 <span class="ln"></span></div>
    <div class="search">🔎 <input placeholder="过滤项目 / goal…"></div>
    <div id="tree"><!-- JS 注入 --></div>
  </nav>

  <!-- ===== 右栏 ===== -->
  <main class="detail" id="detail"></main>
</div>

<!-- ===== 详情抽屉（点 story / 进度 钻入第 3 层）===== -->
<div class="scrim" id="scrim" onclick="closeDrawer()"></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true">
  <div class="drawer-h">
    <div class="dh-t"><h2 id="dwTitle">—</h2><div class="dh-sub" id="dwSub"></div></div>
    <span class="x" onclick="closeDrawer()" title="关闭 (Esc)">✕</span>
  </div>
  <div class="drawer-b" id="dwBody"></div>
</aside>
"""


# ====================================================================
# JS —— 大部分逐字拷自 mockup <script>（render/openStory/openProgress/jump/
# setLens/renderLens/renderActive/toggleProj/drawer 全部沿用），仅按契约：
#   C 加固 #4：goal/acard/story 行从内联 onclick 改为 data-attr + 一次性 document
#   级事件委托（含引号的 key/slug 结构上免疫），sel(el,key) 退役为 selByEl(el)；
#   删 内联 const DATA / const PROJ / 硬编码 ROSTER 对象 / 末尾 3 行硬启动；
#   buildActive() 改为直接返回 window 上的 model.active_dispatches；
#   renderActive 用 it.node（model 字段名，mockup 里叫 it.nd）；
#   新增 boot / reboot / renderTree / renderKPI / 双模 + SSE 启动。
# DATA/PROJ/_MODEL 成为模块级 let，由 boot 填。
# ====================================================================
_JS = r"""
/* ===== 模型态：boot 填 ===== */
let DATA = {};          /* key -> goal（消费 build_global_model 的 goal 契约）*/
let PROJ = {};          /* key -> {name} */
let _MODEL = null;      /* 当前 model（含 counts/active_dispatches/roster/...）*/

const ROLE_AV = {"需求架构师":"🧭", "开发工程师":"🛠", "测试工程师":"🧪", "评审专家":"⚖️"};
const ROLE_SHORT = {"需求架构师":"需求", "开发工程师":"开发", "测试工程师":"测试", "评审专家":"评审"};

const ICON = {done:"☑", in_progress:"◐", pending:"☐"};
const SCLS = {done:"done", in_progress:"prog", pending:"pend"};
// esc：转义 & < > "（" → &quot;，文本内容与双引号属性 data-*="..." 双安全）。
// 单引号在双引号属性里无害，故不转 '；保持 data-key="${esc(...)}" 对含 ' 的 slug 原样承载。
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
// 注：emp.act 含受信 <b> 标记，按设计原样注入（静态常量，非用户输入）

let CUR = null;          /* 当前选中 goal key */
let _lens = null;        /* 当前选中的员工 lens（null = 不筛选）*/

/* ===== 在跑总览：直接返回 Plan-1 已算好的 active_dispatches（不再从 DATA 现推）===== */
function buildActive(){
  return ((_MODEL && _MODEL.active_dispatches) || []).map(d => ({
    key:d.key, goal:d.goal, proj:d.proj, role:d.role,
    av:ROLE_AV[d.role]||'•',
    nd:d.node, elapsed:d.elapsed||'', stale:!!d.stale,
  }));
}

/* 员工 lens：花名册来自 model.roster（字符串数组）→ 派生 av/short。
   点角色 → 筛该角色当前在跑的 goal（可 ×N 并行）。 */
function _roster(){
  return ((_MODEL && _MODEL.roster) || []).map(emp => ({
    emp, av:ROLE_AV[emp]||'•', short:ROLE_SHORT[emp]||emp,
  }));
}
function renderLens(){
  const items = buildActive();
  const cnt = {}, sc = {};
  for(const it of items){ cnt[it.role]=(cnt[it.role]||0)+1; if(it.stale) sc[it.role]=(sc[it.role]||0)+1; }
  document.getElementById('lens').innerHTML = _roster().map(r=>{
    const n = cnt[r.emp]||0, s = sc[r.emp]||0, on = _lens===r.emp;
    return `<div class="lchip ${on?'on':''} ${n?'has':''}" onclick="setLens('${r.emp}')"
      title="${r.emp}：当前 ${n} 个在跑 goal${s?`（含 ${s} 疑停）`:''}">
      <span class="lav">${r.av}</span><span class="lnm">${r.short}</span>
      <span class="lcnt">${n}</span>${s?'<span class="lwarn">⚠</span>':''}</div>`;
  }).join('');
}
function setLens(emp){ _lens = (_lens===emp)?null:emp; renderLens(); renderActive(); }

function renderActive(){
  let items = buildActive();
  if(_lens) items = items.filter(i=>i.role===_lens);
  const running = items.filter(i=>!i.stale).length;
  const stale = items.filter(i=>i.stale).length;
  const count = _lens
    ? `<div class="acount">${esc(_lens)} · <b>${running}</b> 在跑${stale?` · <span class="w">${stale} 疑停</span>`:''}</div>`
      + `<div class="lclear" onclick="setLens('${_lens}')">✕ 清除</div>`
    : `<div class="acount"><b>${running}</b> 在跑${stale?` · <span class="w">${stale} 疑停</span>`:''}</div>`;
  const cards = items.length
    ? items.map(it=>`
      <div class="acard ${it.stale?'stale':''}" data-key="${esc(it.key)}" title="跳到该 goal">
        <div class="aav">${it.av}</div>
        <div class="abody">
          <div class="arow1">
            <span class="apj" title="${esc(it.proj)}/${esc(it.key)}">${esc(it.proj)}/${esc(it.key)}</span>
            ${it.stale ? '<span class="abadge st">⚠ 孤儿·疑停</span>' : '<span class="abadge run">● 在跑</span>'}
          </div>
          <div class="arow2"><span class="arole">${esc(it.role)}</span> · <span class="and">${esc(it.nd)}</span>${it.elapsed?` · <span class="ael">已 ${esc(it.elapsed)}</span>`:''}</div>
        </div>
      </div>`).join('')
    : (_lens ? `<div class="aempty">${esc(_lens)} 当前无在跑 goal（空闲）</div>`
             : '<div class="aempty">当前无在跑派单 · 全机空闲（所有 goal 已交付或等待派单）</div>');
  document.getElementById('eband').innerHTML = count + cards;
}

function render(key){
  CUR = key;
  const d = DATA[key];
  const host = document.getElementById('detail');
  if(!d){ host.innerHTML = '<div class="empty">选择左侧任意 goal 查看进度</div>'; return; }

  const route = (d.route||[]).map(s=>`
    <div class="rstep ${s.st}">
      <div class="node">${s.st==='done'?'✓':s.st==='active'?'◐':'○'}</div>
      <div class="rlab">${esc(s.emp)}</div>
      <div class="rflow mono">${esc(s.flow)}</div>
    </div>`).join('');

  const wt = d.worktree||{};
  const wtTxt = wt.concrete
    ? `<code>${esc(wt.concrete)}</code>`
    : (wt.intent==='worktree' ? `<span class="intent">隔离 worktree（意向，待落点）</span>`
      : wt.intent==='inline' ? `<span class="intent">inline 当前分支（意向）</span>`
      : `<span class="intent">待 dev 段自动判定</span>`);

  const ss = d.stories||{items:[]};
  const stories = (ss.items||[]).map(it=>`
    <div class="story clk ${SCLS[it.status]||'pend'}" data-story="${esc(it.id)}" title="查看故事详情">
      <span class="box">${ICON[it.status]||'☐'}</span>
      <span class="sid mono">${esc(it.id)}</span>
      <span class="title">${esc(it.title)}</span>
      <span class="sr mono" title="回溯需求（Phase-1 落 source_sr 字段）">↩ ${it.sr==null?'预留':esc(it.sr)}</span>
      <span class="stt mono">${esc(it.status)}</span>
      <span class="chev">›</span>
    </div>`).join('') || '<div class="note">故事清单待 decompose 填实</div>';

  const alerts = (d.alerts&&d.alerts.length)
    ? d.alerts.map(a=>`
      <div class="alertrow ${a.crit?'crit':''}">
        <span class="ic">${a.crit?'■':'▲'}</span>
        <span>${esc(a.text)}</span>
        <span class="meta">${esc(a.meta)}</span>
      </div>`).join('')
    : '<div class="noalert">● 无告警</div>';

  // 评审流水：时间 + 内容 + 状态（v2 重做）
  const gates = (d.gates&&d.gates.length)
    ? d.gates.map(g=>{
        const iss = (g.issues&&g.issues.length)
          ? `<div class="gissues">${g.issues.map(x=>`<div>${esc(x)}</div>`).join('')}</div>` : '';
        return `<div class="grow">
          <div class="gts">${esc(g.ts)}</div>
          <div class="gmid">
            <div class="gname">${esc(g.name)} <span class="mono" style="color:var(--mut-2);font-size:10px">${esc(g.id)}</span></div>
            <div class="gmeta">评审方 <span class="by">${esc(g.by)}</span> · 第 ${esc(g.it)} 轮${g.v==='PASS'?' · 无遗留问题':` · ${(g.issues||[]).length} 项待修`}</div>
            ${iss}
          </div>
          <div class="gstat ${g.v==='PASS'?'pass':'fail'}">${g.v==='PASS'?'✓ 通过':'✕ 未通过'}</div>
        </div>`;
      }).join('')
    : '<div class="note">尚无评审记录</div>';

  const staleBanner = d.state==='stale'
    ? `<div class="card alert"><div class="card-h">⚠ workspace 失联（stale）</div>
        <div class="card-b"><div class="alertrow"><span class="ic">▲</span><span>${esc(d.stale||(d.alerts&&d.alerts[0]&&d.alerts[0].text)||'workspace 失联')}</span></div></div></div>`
    : '';

  const nd = d.node||{};
  const ownAlt = ((PROJ[key]||{}).alt) ? 'alt' : '';
  host.innerHTML = `
    <div class="d-head">
      <div class="ring clk" style="--p:${d.pct}" onclick="openProgress()" title="查看链进度详情"><b>${d.pct}%</b><small>链进度</small></div>
      <div class="d-title">
        <h1>${esc(d.title)} ${d.state==='done'?'<span style="color:var(--green);font-size:14px">✓ 已交付</span>':''}</h1>
        <div class="sub">
          <span class="slug">${esc(d.slug)}</span>
          <span class="ownerbadge"><span class="own ${ownAlt}">${esc((d.owner||'?').slice(0,2))}</span> owner ${esc(d.owner)} <span class="phase2">单机 MVP · 多人为 phase-2 预留</span></span>
        </div>
      </div>
    </div>

    ${staleBanner}

    <div class="card">
      <div class="card-h">🧭 阶段路线 <span class="tag">需求 → 开发 → 测试</span></div>
      <div class="card-b">
        <div class="route">${route}</div>
        <div class="nodebar clk" onclick="openProgress()" title="查看当前进度详情">
          <span class="k">当前节点</span><span class="v">${esc(nd.flow)} · ${esc(nd.current_node)}</span>
          <span class="k" style="margin-left:6px">状态</span><span class="v">${esc(nd.status)}</span>
          <span class="run">第 ${esc(nd.run)} 轮</span>
        </div>
        <div class="wt" style="margin-top:12px">
          <span class="ic">⎇</span><span class="k" style="color:var(--mut);font-size:11px">worktree</span> ${wtTxt}
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-h">☑ Story TODO <span class="tag">${ss.done}/${ss.total} · ${ss.pct}%</span></div>
      <div class="card-b" style="padding-top:4px">${stories}</div>
    </div>

    <div class="card alert">
      <div class="card-h">🛡️ 监督员告警 <span class="tag">blocked + gate FAIL + circuit-breaker</span></div>
      <div class="card-b">${alerts}</div>
    </div>

    <div class="card">
      <div class="card-h">🔍 评审流水 <span class="tag">时间 · 评审项 · 评审方 · 状态</span></div>
      <div class="card-b" style="padding-top:4px"><div class="gtl">${gates}</div></div>
    </div>
  `;
}

/* ===== 选中委托：data-attr + 一次性 document 级事件委托（替代逐行内联 onclick）=====
   理由（C 加固 #4）：把 goal.key / story.id 直接拼进内联 onclick 串，含单/双引号的
   key 会撑破 JS 字符串 / HTML 属性 → handler 失效或注入。改为 data-key/data-story
   承载 + 在 document 上委托，key 走 dataset 不再经过 JS 串拼接，结构上免疫引号。
   监听只挂一次（_JS 加载时执行一次，不在 reboot/render 里重挂）。 */
function selByEl(el){
  document.querySelectorAll('.goal.sel').forEach(x=>x.classList.remove('sel'));
  el.classList.add('sel');
  render(el.dataset.key);
}
document.addEventListener('click', function(e){
  const t = e.target;
  if(!t || !t.closest) return;
  const g = t.closest('.goal[data-key]');     if(g){ selByEl(g); return; }
  const a = t.closest('.acard[data-key]');     if(a){ jump(a.dataset.key); return; }
  const s = t.closest('.story[data-story]');   if(s){ openStory(s.dataset.story); return; }
});
function toggleProj(h){ h.parentElement.classList.toggle('collapsed'); }
/* 从全局员工带跳到某 goal：展开其所在分组 + 高亮树 + 渲染右栏 */
function jump(key){
  const g = [...document.querySelectorAll('.goal')].find(x => x.dataset.key === key);
  document.querySelectorAll('.goal.sel').forEach(s=>s.classList.remove('sel'));
  if(g){ g.classList.add('sel');
    const p=g.closest('.proj'); if(p) p.classList.remove('collapsed');
    const dg=g.closest('.donegrp'); if(dg) dg.classList.remove('collapsed');
    g.scrollIntoView({block:'nearest'});
  }
  render(key);
}

/* ===== 详情抽屉（第 3 层钻入）===== */
const _SPILL = {done:'done', in_progress:'prog', pending:'pend'};
const _STXT = {done:'已完成', in_progress:'进行中', pending:'待开始'};
function openDrawer(){ document.getElementById('scrim').classList.add('open');
  document.getElementById('drawer').classList.add('open'); }
function closeDrawer(){ document.getElementById('scrim').classList.remove('open');
  document.getElementById('drawer').classList.remove('open'); }
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDrawer(); });

function openStory(id){
  const d = DATA[CUR]; if(!d) return;
  const it = ((d.stories||{}).items||[]).find(s=>s.id===id); if(!it) return;
  const cls = _SPILL[it.status]||'pend';
  // 状态时间线（mock：真实从 events / story 状态变更取）
  const steps = [{l:'创建 · 待开始 pending', cls:'done'}];
  if(it.status==='in_progress') steps.push({l:'进入开发 · in_progress', cls:'now'});
  if(it.status==='done'){ steps.push({l:'进入开发 · in_progress', cls:'done'},{l:'完成 · done', cls:'done'}); }
  const tl = steps.map(s=>`<div class="ti ${s.cls}">${esc(s.l)}<span class="tt">mock ts</span></div>`).join('');
  document.getElementById('dwTitle').innerHTML = `${esc(it.id)} · ${esc(it.title)}`;
  document.getElementById('dwSub').innerHTML = `${esc(d.title)} · ${esc(d.slug)}`;
  document.getElementById('dwBody').innerHTML = `
    <div class="dsec">
      <div class="dl">概览</div>
      <div class="dkv"><span class="k">状态</span><span class="v"><span class="dpill ${cls}">${esc(_STXT[it.status]||it.status)}</span></span></div>
      <div class="dkv"><span class="k">回溯需求</span><span class="v" style="color:var(--blue)">↩ ${it.sr==null?'预留':esc(it.sr)}</span></div>
      <div class="dkv"><span class="k">实现阶段</span><span class="v">开发工程师 · coding</span></div>
      <div class="placeholder">↩SR 回溯 / story↔派单关联为 Phase-1 落地字段（现 build_roadmap.items 仅 id/title/status）。</div>
    </div>
    <div class="dsec">
      <div class="dl">验收标准 (GWT)</div>
      <div class="gwt"><b>Given</b>用户处于登录页<br><b>When</b>提交「${esc(it.title)}」相关操作<br><b>Then</b>系统按预期校验并反馈</div>
      <div class="placeholder">示例占位 —— Phase-1 从 AR / 用户故事文档取真实 AC。</div>
    </div>
    <div class="dsec">
      <div class="dl">状态时间线</div>
      <div class="tl">${tl}</div>
    </div>`;
  openDrawer();
}

function openProgress(){
  const d = DATA[CUR]; if(!d) return;
  const nd = d.node||{};
  const stages = (d.route||[]).map(s=>{
    const ico = s.st==='done'?'✓':s.st==='active'?'◐':'○';
    const run = (d.emps||[]).find(e=>e.emp===s.emp && e.st==='running');
    const u = run&&run.usage ? `<span class="su">${esc(run.usage)}</span>` : '';
    return `<div class="dstage ${s.st==='active'?'active':s.st}"><span class="si">${ico}</span>
      <span class="snm">${esc(s.emp)} · ${esc(s.flow)}</span>${u}</div>`;
  }).join('');
  const gates = (d.gates||[]).length
    ? d.gates.map(g=>`<div class="dstage ${g.v==='PASS'?'done':'active'}">
        <span class="si">${g.v==='PASS'?'✓':'✕'}</span>
        <span class="snm">${esc(g.name)} · 第${esc(g.it)}轮 · <span style="color:var(--mut)">${esc(g.by)}</span></span>
        <span class="su">${esc(g.ts)}</span></div>`).join('')
    : '<div class="placeholder">尚无评审记录</div>';
  const wt = d.worktree||{};
  const wtTxt = wt.concrete || (wt.intent==='worktree'?'隔离 worktree（意向）':wt.intent==='inline'?'inline 当前分支':'待判定');
  document.getElementById('dwTitle').innerHTML = `${esc(d.title)} · 链进度详情`;
  document.getElementById('dwSub').innerHTML = `${esc(d.slug)} · owner ${esc(d.owner)}`;
  document.getElementById('dwBody').innerHTML = `
    <div class="dsec">
      <div class="dl">概览</div>
      <div class="dkv"><span class="k">链进度</span><span class="v">${d.pct}%（story ${(d.stories||{}).done}/${(d.stories||{}).total}）</span></div>
      <div class="dkv"><span class="k">当前节点</span><span class="v">${esc(nd.flow)} · ${esc(nd.current_node)} · 第${esc(nd.run)}轮</span></div>
      <div class="dkv"><span class="k">状态</span><span class="v">${esc(nd.status)}</span></div>
      <div class="dkv"><span class="k">worktree</span><span class="v">${esc(wtTxt)}</span></div>
    </div>
    <div class="dsec">
      <div class="dl">阶段明细（需求 → 开发 → 测试）</div>
      ${stages}
    </div>
    <div class="dsec">
      <div class="dl">评审历史</div>
      ${gates}
    </div>
    <div class="dsec">
      <div class="dl">最近事件流</div>
      ${(d.events&&d.events.length)
        ? `<div class="tl">${d.events.map(ev=>`<div class="ti"><span>${esc(ev.kind)} ${esc(ev.detail)}</span><span class="tt">${esc(ev.ts)}</span></div>`).join('')}</div>`
        : '<div class="placeholder">无事件</div>'}
    </div>`;
  openDrawer();
}

/* ===== 左树：按 model.projects 生成（项目分组可折叠 + goal 行）===== */
function _goalRow(g, alt){
  const st = g.state;                                      // active | done | stale
  const ic = st==='done'?'✓' : st==='stale'?'⚠' : '◐';
  const pctmini = st==='stale' ? 'stale' : `${g.pct}%`;
  const own = (g.owner||'?').slice(0,2);
  return `<div class="goal ${st}" data-key="${esc(g.key)}">
      <span class="ic">${ic}</span><span class="gname">${esc(g.title)}</span>
      <span class="pctmini">${esc(pctmini)}</span>
      <span class="own ${alt?'alt':''}" title="${esc(g.owner||'')}（owner）">${esc(own)}</span>
    </div>`;
}
function renderTree(model){
  const projs = (model.projects||[]);
  const html = projs.map((p,i)=>{
    const alt = (i%2===1);                                 // 交替 owner 徽标配色（视觉区分项目）
    const all = (p.goals||[]);
    // done 的 goal 折叠灰显保留（Phase-0 锁定决策）：非 done 行内渲染，done 收进
    // 本项目末尾的可折叠「已完成」组（复用 .donegrp/.donegrp-h/.donegrp-body）。
    const live = all.filter(g=>g.state!=='done');
    const done = all.filter(g=>g.state==='done');
    const rows = live.map(g=>_goalRow(g, alt)).join('');
    const donegrp = done.length
      ? `<div class="donegrp collapsed">
        <div class="donegrp-h" onclick="this.parentElement.classList.toggle('collapsed')">
          <span class="caret">▼</span> 已完成 · 灰显折叠（${done.length}）
        </div>
        <div class="donegrp-body">${done.map(g=>_goalRow(g, alt)).join('')}</div>
      </div>`
      : '';
    const body = (rows || (done.length ? '' : '<div class="note" style="padding:6px 16px">（无 goal）</div>'));
    return `<div class="proj">
      <div class="proj-h" onclick="toggleProj(this)">
        <span class="caret">▼</span>
        <span class="pname">${esc(p.name)} <span class="ppath">${esc(p.path||'')}</span></span>
        <span class="cnt">${all.length}</span>
      </div>
      <div class="proj-body">${body}${donegrp}</div>
    </div>`;
  }).join('');
  document.getElementById('tree').innerHTML = html || '<div class="note" style="padding:10px 16px">registry 暂无登记项目</div>';
}

/* ===== 顶部 KPI / scope / 生成时间 ===== */
function renderKPI(model){
  const c = model.counts||{};
  document.getElementById('scope').innerHTML = `scope <b>${esc(model.scope||'--')}</b> · 本机 registry`;
  document.getElementById('gen').textContent = `生成 ${model.generated_at||'—'}`;
  document.getElementById('kpi').innerHTML =
    `<span><b>${c.projects||0}</b>项目</span>`
    + `<span><span class="dot">◐</span> <b>${c.active||0}</b>活跃</span>`
    + `<span><span class="dot g">✓</span> <b>${c.done||0}</b>完成</span>`
    + `<span><span class="dot y">⚠</span> <b>${c.stale||0}</b>stale</span>`;
}

/* ===== boot：消费 model，构建 DATA/PROJ，全量渲染，默认选首个（优先 active）===== */
function _firstKey(model){
  let first = null, firstActive = null;
  for(const p of (model.projects||[])){
    for(const g of (p.goals||[])){
      if(first===null) first = g.key;
      if(firstActive===null && g.state==='active') firstActive = g.key;
    }
  }
  return firstActive || first;
}
function boot(model){
  _MODEL = model || {};
  DATA = {}; PROJ = {};
  (_MODEL.projects||[]).forEach((p,i)=>{
    (p.goals||[]).forEach(g=>{
      DATA[g.key] = g;
      PROJ[g.key] = {name:p.name, alt:(i%2===1)};
    });
  });
  renderKPI(_MODEL);
  renderTree(_MODEL);
  renderLens();
  renderActive();
  const k = (CUR && DATA[CUR]) ? CUR : _firstKey(_MODEL);
  if(k){
    const el = [...document.querySelectorAll('.goal')].find(x => x.dataset.key === k);
    if(el) el.classList.add('sel');
    render(k);
  } else {
    render(null);
  }
}

/* ===== reboot：SSE 重渲，保住 UI 态（选中 key / 各 proj 折叠 / lens / drawer 开合）===== */
function _snapshotUI(){
  // 哪些 proj 当前折叠（按 model.projects 顺序的 index 集合）
  const collapsed = [];
  document.querySelectorAll('.tree .proj').forEach((el,i)=>{ if(el.classList.contains('collapsed')) collapsed.push(i); });
  return {
    cur: CUR, lens: _lens, collapsed,
    drawerOpen: document.getElementById('drawer').classList.contains('open'),
  };
}
function _restoreUI(snap){
  // 折叠态按 index 还原
  document.querySelectorAll('.tree .proj').forEach((el,i)=>{
    if(snap.collapsed.indexOf(i) >= 0) el.classList.add('collapsed');
  });
  if(!snap.drawerOpen) closeDrawer();   // boot 不主动开 drawer；若快照前是开的则保持（不强制关）
}
function reboot(model){
  const snap = _snapshotUI();
  _lens = snap.lens;
  CUR = (snap.cur && (model.projects||[]).some(p=>(p.goals||[]).some(g=>g.key===snap.cur))) ? snap.cur : null;
  boot(model);
  _restoreUI(snap);
}

/* ===== 双模启动 =====
   静态/离线：window.__MODEL__ 存在 → boot，不连 SSE。
   实时：window.__MODEL__ 为 null/缺 → fetch('/model.json') + EventSource('/events')。 */
function _start(){
  if(window.__MODEL__){
    boot(window.__MODEL__);
    return;
  }
  fetch('/model.json').then(r=>r.json()).then(m=>boot(m)).catch(()=>render(null));
  try{
    const es = new EventSource('/events');
    es.onmessage = () => {
      fetch('/model.json').then(r=>r.json()).then(m=>reboot(m)).catch(()=>{});
    };
  }catch(e){ /* EventSource 不可用则静态降级 */ }
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', _start);
}else{
  _start();
}
"""


def render_shell(model=None, *, generated_at=None):
    """组装自包含的全局 HUD shell HTML。

    Args:
        model: build_global_model / build_workspace_model 产出的模型 dict。
            给定 → 内联 ``window.__MODEL__``（静态/离线，不连 SSE）。
            None → JS ``fetch('/model.json')`` + ``EventSource('/events')``（实时）。
        generated_at: 可选；若 model 缺 generated_at 时回填到内联模型的展示用字段。

    Returns:
        str: 完整 ``<!DOCTYPE html>...`` 文档，零外链。
    """
    if model is not None:
        m = model
        if generated_at is not None and not m.get("generated_at"):
            m = dict(m)
            m["generated_at"] = generated_at
        # </ → <\/ 转义：防 JSON 里出现 </script> 截断内联脚本（注入防护）
        payload = json.dumps(m, ensure_ascii=False).replace("</", "<\\/")
        model_inline = "window.__MODEL__ = " + payload + ";"
    else:
        model_inline = "window.__MODEL__ = null;"

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>ieidev 全局 HUD · 数字员工总台</title>\n"
        "<style>" + _CSS + "</style>\n"
        "</head>\n<body>\n"
        + _SHELL_HTML
        + "<script>" + model_inline + "\n" + _JS + "</script>\n"
        "</body>\n</html>\n"
    )
