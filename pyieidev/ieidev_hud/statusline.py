"""通道① 命令行状态栏 —— 单行 ANSI（truecolor，无底色、无 emoji，柔和色）。

接 Claude Code statusLine.type=command；字段全部映射到真实数据：
团队 │ 需求「name」pct% · flow·node(第run轮·状态) │ 评审摘要 │ 待处理 n
无 per-员工事件（P-B 才有），故「员工忙闲」用 active 单棒状态 + 最近 gate by 表达。
"""

_E = "\033"
_R = f"{_E}[0m"
_BRAND = f"{_E}[38;2;96;160;240m"   # 柔和品牌蓝
_TXT = f"{_E}[38;2;168;182;204m"    # 柔和浅灰
_GOLD = f"{_E}[38;2;224;168;72m"    # 柔和金（数字/告警）
_DIM = f"{_E}[38;2;88;102;128m"     # 暗灰分隔

_SEP = f"{_DIM} │ {_TXT}"
_NAME_MAX = 16


def _trunc(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _status_word(status):
    return {"in_progress": "运行", "blocked": "阻塞"}.get(status, status or "—")


def _latest_gate_word(feature):
    gates = feature.get("gates") or []
    if not gates:
        return None
    g = gates[-1]
    return f"评审 {g.get('verdict')}（第{g.get('iter')}轮·{g.get('by')}）"


def render(model):
    """model = datasource.build_hud_model(...) → 单行 ANSI 字符串。"""
    primary = model.get("primary")
    if primary is None:
        n = model.get("feature_count", 0)
        tail = f"{_SEP}功能 {n} 个" if n else ""
        return f"{_BRAND}ieidev 团队{_DIM} │ {_TXT}暂无在跑需求{tail}{_R}"

    name = _trunc(primary.get("display_name"), _NAME_MAX)
    pct = primary.get("completion_pct", 0)
    alerts = primary.get("alert_count", 0)

    parts = [f"{_BRAND}ieidev 团队{_TXT}"]
    seg2 = f"需求「{name}」{_GOLD}{pct}%{_TXT}"
    active = primary.get("active")
    if active:
        seg2 += (f" · {active.get('flow')}·{active.get('current_node')}"
                 f"（第{active.get('run')}轮·{_status_word(active.get('status'))}）")
    parts.append(seg2)
    gate_word = _latest_gate_word(primary)
    if gate_word:
        parts.append(gate_word)
    parts.append(f"{_GOLD}待处理 {alerts}{_TXT}" if alerts else f"{_TXT}无告警")

    return _SEP.join(parts) + _R


def safe_fallback():
    """坏数据/异常兜底：永不抛、永不多行。"""
    return f"{_BRAND}ieidev 团队{_DIM} │ {_TXT}HUD 数据读取降级{_R}"
