"""通道② 网页实时仪表盘 —— 自包含 hud.html（内联 CSS、零外链、嵌入 auto-reload）。

视觉语言照 docs/framework/01-design/设计参考-hud-dashboard.html（深蓝底 + teal/gold）。
数据全派生，PASS/FAIL 不编分（FF-3）；员工级活动只渲染 active 单棒（per-员工事件待 P-B）。
"""
from html import escape

_RELOAD_MS = 2000      # auto-reload 间隔（毫秒）；对应 setTimeout 第二参数
_EVENT_TAIL = 12       # 事件流最多显示最新 N 条

_CSS = """
:root{--bg:#0a1422;--panel:#16273f;--line:#26405f;--ink:#d7e2f0;--mut:#8ea4be;
--white:#f2f7fc;--blue:#4a9eff;--teal:#2ec5b6;--red:#ff5d6c;--gold:#f5b740;--green:#43dd8b;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);font-family:"Microsoft YaHei","PingFang SC",sans-serif;
color:var(--ink);padding:28px 24px;min-height:100vh}
.wrap{max-width:860px;margin:0 auto;border:1px solid var(--line);border-radius:10px;
overflow:hidden;background:#0c1a2c}
.bar{display:flex;align-items:center;gap:10px;padding:10px 16px;background:#13243c;
border-bottom:1px solid var(--line)}
.brand{color:var(--blue);font-weight:bold}
.live{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11px;
font-weight:bold;color:var(--green)}
.live i{width:8px;height:8px;border-radius:50%;background:var(--green);
box-shadow:0 0 8px var(--green);animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.gen{font-size:10.5px;color:var(--mut)}
.body{padding:14px 16px;display:flex;flex-direction:column;gap:13px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.tile{border:1px solid var(--line);border-left:3px solid var(--blue);border-radius:8px;
padding:9px 12px;background:var(--panel)}
.tile.g{border-left-color:var(--green)}.tile.y{border-left-color:var(--gold)}
.tile.t{border-left-color:var(--teal)}
.tlab{font-size:10px;color:var(--mut)}
.tval{font-size:22px;font-weight:bold;color:var(--white);line-height:1.15;margin-top:2px}
.tsub{font-size:9.5px;color:var(--mut);margin-top:1px}
.sec{border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden}
.sh{background:#1f4e79;color:var(--white);font-size:13px;font-weight:bold;padding:6px 12px}
.sh.r{background:#6e2230}.sh.t{background:#185f57}.sh.y{background:#6b5113}
.sb{padding:10px 12px;font-size:12px;line-height:1.6}
.story{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.story:last-child{border-bottom:0}
.st-done{color:var(--green)}.st-prog{color:var(--gold)}.st-pend{color:var(--mut)}
.gate{display:inline-flex;gap:6px;align-items:center;border:1px solid var(--line);
border-radius:6px;padding:4px 9px;margin:3px 5px 3px 0;font-size:11px;background:#16273f}
.gate.pass{border-color:rgba(67,221,139,.4);color:var(--green)}
.gate.fail{border-color:rgba(255,93,108,.5);color:var(--red)}
.alert{color:var(--gold);padding:3px 0}
.ev{font-family:monospace;font-size:10.5px;display:flex;gap:9px;padding:2px 0;color:var(--ink)}
.ev .ts{color:var(--mut);flex:0 0 150px}
.ev .k{flex:0 0 70px;font-weight:bold;color:var(--blue)}
.muted{color:var(--mut)}
.qrow{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.note{font-size:10px;color:var(--mut);font-style:italic;margin-top:4px}
.hud-panel{display:none;border:1px dashed var(--line);border-radius:6px;
margin:4px 0 8px;padding:8px 10px;font-size:11px;color:var(--mut);background:#0e1d31}
.hud-panel:target{display:block}
.drill{color:var(--blue);text-decoration:none;font-size:10px;margin-left:6px}
"""


_EMP_DISPLAY = {"req-architect": "需求架构师", "dev-engineer": "开发工程师",
                "test-engineer": "测试工程师"}


def _render_delivery(primary):
    """有 delivery 时渲染三块：交付链进度 + 派单流 + 员工忙闲；无 delivery 返回 ""（向后兼容）。

    全字符串字段 escape()；数值字段（done_count/stage_index/tokens...）由 datasource 保证为
    int/None，原样插值（None 仅 str() 后展示，不参与 HTML 结构注入）。
    """
    d = primary.get("delivery")
    if not d:
        return ""
    # ① 交付链进度条：各 stage 圈选，已完成（i < done_count）标 pass
    steps = "".join(
        f'<span class="gate {"pass" if i < d["done_count"] else ""}">'
        f'{i+1}. {escape(_EMP_DISPLAY.get(s["emp"], s["emp"]))}</span>'
        for i, s in enumerate(d["stages"])
    )
    # stage_index → handoff_from 映射（panel 钻入展示链上游交接点）
    stages = d.get("stages") or []
    # ② 派单流：每 dispatch 一行 + 紧随的折叠详情面板（纯 CSS :target 驱动，零 JS 事件绑定）
    disp_rows = ""
    for dv in primary.get("dispatches", []):
        emp = escape(_EMP_DISPLAY.get(dv["emp"], dv["emp"] or "?"))
        st = "进行中" if dv["running"] else escape(str(dv["status"]))
        usage = (f' · {dv["subagent_tokens"]} tok' if dv.get("subagent_tokens") else "")
        usage += (f' · {dv["tool_uses"]} tools' if dv.get("tool_uses") else "")
        usage += (f' · {dv["duration_s"]}s' if dv.get("duration_s") else "")
        dot = '<i style="color:var(--green)">●</i> ' if dv["running"] else ""
        # DOM-safe 锚 id：dispatch_id 替换 # / : → -（避免破坏 href/id 语法）
        pid = "d-" + (dv["dispatch_id"] or "x").replace("#", "-").replace(":", "-")
        si = dv.get("stage_index")
        # 该 dispatch 对应 stage 的 handoff_from（stage_index 1-based）
        handoff = ""
        if isinstance(si, int) and 1 <= si <= len(stages):
            handoff = stages[si - 1].get("handoff_from") or ""
        disp_rows += (
            f'<div class="story"><span>{dot}{emp} · {escape(dv["flow"] or "")}'
            f'<a class="drill" href="#{escape(pid)}">详情▾</a></span>'
            f'<span class="muted">{st}{usage}</span></div>'
            f'<div class="hud-panel" id="{escape(pid)}">'
            f'派单 {escape(str(dv.get("dispatch_id") or ""))} · 阶段 {dv.get("stage_index")}<br>'
            f'状态 {st} · tokens {dv.get("subagent_tokens")} · tools {dv.get("tool_uses")}'
            f' · {dv.get("duration_s")}s<br>'
            f'handoff {escape(str(handoff)) or "—"}<br>'
            f'起 {escape(str(dv.get("started_at")))} · 止 {escape(str(dv.get("done_at")))}'
            f'</div>'
        )
    # ③ 员工忙闲条：busy → fail 红框
    busy_rows = "".join(
        f'<span class="gate {"fail" if a["busy"] else ""}">'
        f'{escape(_EMP_DISPLAY.get(a["emp"], a["emp"]))}：{"忙" if a["busy"] else "闲"}</span>'
        for a in primary.get("employee_activity", [])
    )
    return (
        f'<div class="sec"><div class="sh t">🧭 交付链 · {escape(str(d["template_id"]))} '
        f'（{escape(str(d["progress_label"]))}）</div><div class="sb">{steps}</div></div>'
        f'<div class="sec"><div class="sh">📡 派单流</div><div class="sb">'
        f'{disp_rows or "<span class=muted>暂无派单</span>"}</div></div>'
        f'<div class="sec"><div class="sh">👤 员工忙闲</div><div class="sb">'
        f'{busy_rows or "<span class=muted>暂无员工活动</span>"}</div></div>'
    )


def _story_cls(status):
    return {"done": "st-done", "in_progress": "st-prog"}.get(status, "st-pend")


def _story_icon(status):
    return {"done": "✅", "in_progress": "🟡", "pending": "⏳"}.get(status, "·")


def _ev_kind_label(e):
    if e.get("type") == "gate":
        return f"评审·{e.get('verdict')}"
    if e.get("type") == "transition":
        return "流转"
    return e.get("type") or "事件"


def _ev_detail(e):
    if e.get("type") == "gate":
        return escape(f"{e.get('gate') or e.get('node')} 第{e.get('iter')}轮 · {e.get('by')}"
                      f" · {len(e.get('issues', []) or [])} issues")
    if e.get("type") == "transition":
        return escape(f"{e.get('from')} → {e.get('to')}"
                      + ("（回流）" if e.get("reflow") else ""))
    return ""


def _render_empty(generated_at):
    return _page(generated_at, '<div class="sb muted">暂无在跑需求 —— '
                 '尚无 .ieidev/features/&lt;slug&gt;/ 数据（底座还没跑过）。</div>')


def _page(generated_at, inner):
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
        f"<title>ieidev HUD 驾驶舱</title>"
        f"<script>setTimeout(function(){{"
        f"var h=location.hash;location.reload();"
        f"if(h){{location.hash=h;}}"
        f"}},{_RELOAD_MS});</script>"
        f"<style>{_CSS}</style></head><body><div class=\"wrap\">"
        "<div class=\"bar\"><span class=\"brand\">🏢 ieidev 实时驾驶舱</span>"
        f"<span class=\"gen\">生成 {escape(generated_at)}</span>"
        "<span class=\"live\"><i></i>LIVE</span></div>"
        f"<div class=\"body\">{inner}</div></div></body></html>"
    )


def render(model, *, generated_at):
    """model = datasource.build_hud_model(...) → 自包含 hud.html 字符串。"""
    # 数值字段（pct/done/total/iter/run...）由 datasource 保证为 int，原样插值；所有字符串字段一律 escape()
    primary = model.get("primary")
    if primary is None:
        return _render_empty(generated_at)

    name = escape(primary.get("display_name") or primary.get("slug"))
    pct = primary.get("completion_pct", 0)
    done = primary.get("stories_done", 0)
    total = primary.get("stories_total", 0)
    active = primary.get("active")
    node_txt = escape(f"{active['flow']}·{active['current_node']}") if active else "—"
    alert_n = primary.get("alert_count", 0)

    tiles = (
        f'<div class="tile t"><div class="tlab">需求完成度</div>'
        f'<div class="tval">{pct}%</div><div class="tsub">按用户故事</div></div>'
        f'<div class="tile g"><div class="tlab">用户故事</div>'
        f'<div class="tval">{done}<span class="tsub">/{total}</span></div>'
        f'<div class="tsub">done/总</div></div>'
        f'<div class="tile t"><div class="tlab">当前阶段</div>'
        f'<div class="tval" style="font-size:15px">{node_txt}</div>'
        f'<div class="tsub">{name}</div></div>'
        f'<div class="tile y"><div class="tlab">待处理告警</div>'
        f'<div class="tval">{alert_n}</div><div class="tsub">blocked + gate FAIL</div></div>'
    )

    story_rows = "".join(
        f'<div class="story"><span>{_story_icon(s.get("status"))} {escape(s.get("title",""))}</span>'
        f'<span class="{_story_cls(s.get("status"))}">{escape(s.get("status",""))}</span></div>'
        for s in primary.get("stories", [])
    ) or '<div class="muted">无用户故事</div>'

    if active:
        act = (f'当前在跑：<b>{escape(active["flow"])} · {escape(str(active["current_node"]))}</b>'
               f' · 第 {active["run"]} 轮 · {escape(active["status"])}')
        if active.get("blocked_reason"):
            act += f' · <span style="color:var(--red)">{escape(active["blocked_reason"])}</span>'
    else:
        act = '<span class="muted">无在跑棒次</span>'
    if not primary.get("delivery"):
        act += '<div class="note">注：本需求非 CEO 编排链，仅显示单棒控制态。</div>'

    if primary.get("gates"):
        gate_html = "".join(
            f'<span class="gate {"pass" if g.get("verdict")=="PASS" else "fail"}">'
            f'{escape(str(g.get("gate") or g.get("node")))} '
            f'{escape(str(g.get("verdict")))}·第{g.get("iter")}轮'
            f'{(" · "+str(g["issues_count"])+" issues") if g.get("issues_count") else ""}</span>'
            for g in primary.get("gates", [])
        )
    else:
        gate_html = '<span class="muted">尚无评审记录</span>'

    if primary.get("alerts"):
        alert_html = "".join(
            f'<div class="alert">⚠ {escape(a.get("detail",""))}</div>'
            for a in primary.get("alerts", [])
        )
    else:
        alert_html = '<div class="muted">● 无告警</div>'

    evs = list(reversed(primary.get("events", [])))[:_EVENT_TAIL]
    if evs:
        ev_html = "".join(
            f'<div class="ev"><span class="ts">{escape(str(e.get("ts","")))}</span>'
            f'<span class="k">{escape(_ev_kind_label(e))}</span>'
            f'<span>{_ev_detail(e)}</span></div>'
            for e in evs
        )
    else:
        ev_html = '<div class="muted">无事件</div>'

    queue_html = ""
    if model.get("feature_count", 0) > 1:
        rows = "".join(
            f'<div class="qrow"><span>{escape(f.get("display_name") or f.get("slug"))}</span>'
            f'<span class="muted">{f.get("completion_pct",0)}% · '
            f'{"在跑" if f.get("active") else (f.get("feature_status") or "—")}</span></div>'
            for f in model.get("features", [])
        )
        queue_html = (f'<div class="sec"><div class="sh">📚 多功能队列'
                      f'（{model["feature_count"]}）</div><div class="sb">{rows}</div></div>')

    inner = (
        f'<div class="tiles">{tiles}</div>'
        f'<div class="sec"><div class="sh t">📋 用户故事完成度（{done}/{total} · {pct}%）</div>'
        f'<div class="sb">{story_rows}</div></div>'
        f'<div class="sec"><div class="sh">👥 当前活动</div><div class="sb">{act}</div></div>'
        f'{_render_delivery(primary)}'
        f'<div class="sec"><div class="sh y">🔍 评审流水（PASS/FAIL · 无 score）</div>'
        f'<div class="sb">{gate_html}</div></div>'
        f'<div class="sec"><div class="sh r">🛡️ 待处理告警</div><div class="sb">{alert_html}</div></div>'
        f'{queue_html}'
        f'<div class="sec"><div class="sh">🕒 实时事件流</div><div class="sb">{ev_html}</div></div>'
    )
    return _page(generated_at, inner)
