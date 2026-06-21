"""R-009：事件驱动 CQO 升级桥（纯函数判定层）。

闭合 P-final-review §三 D3 的「R-009 半闭合」缺口：
  - 生产端：reviewer-orchestrator 在 review gate 回函里发 `anomaly.escalate=CQO`
    （元评审异常 / 仲裁裁不动，type=meta-review-conflict|arbitration-undecided）。
  - 消费端：cqo-orchestrator 会读该字段研判。
  - 此前缺**桥接**——goal 只在自己 checkpoint（human_gate/阶段交界/收尾）派 CQO，
    元评审异常只能等下一次定时 checkpoint 顺带审，无事件驱动直达路径。

本模块把「这份 reviewer 回函要不要即时升 CQO」抽成纯函数，供 goal/SKILL.md §4.6 棒间
消费时调用（扫本段 reviewer 回函 → 命中即按 §4.5 即时发函 cqo-orchestrator）。

纯函数 / 只读 / 永不抛——goal 棒间扫信号是「下意识动作」，不得因坏文件阻塞编排（同
WARN 扫描范式）。副作用（dispatch CQO）留 SKILL.md 主会话。
"""
import json
from pathlib import Path

# reviewer 回函命名：handoffs/reviewer/<gate>.handoff.json（reviewer-orchestrator §Critical 6）。
# 只认这一后缀，隔离 *.request.json（caller 写的请求）/ *.<cap>.score.md（各 cap 评分表）。
_HANDOFF_GLOB = "*.handoff.json"


def reviewer_escalates_cqo(handoff_path) -> bool:
    """单份 reviewer 回函是否要求事件驱动升级到 CQO。

    True ⟺ JSON 顶层是 dict 且 `anomaly` 是 dict 且 `anomaly.escalate == "CQO"`。
    缺文件 / 坏 JSON / 顶层非 dict / 无 anomaly / anomaly 非 dict / escalate≠CQO → False。
    永不抛。
    """
    try:
        data = json.loads(Path(handoff_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    anomaly = data.get("anomaly")
    if not isinstance(anomaly, dict):
        return False
    return anomaly.get("escalate") == "CQO"


def reviewer_handoffs_escalating_cqo(reviewer_handoffs_dir) -> list:
    """扫一个 features/<slug>/handoffs/reviewer/ 目录，返回所有 escalate=CQO 的回函路径。

    按文件名排序（确定性）。目录不存在 → []。只看 <gate>.handoff.json，忽略 request/score。
    """
    d = Path(reviewer_handoffs_dir)
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob(_HANDOFF_GLOB)) if reviewer_escalates_cqo(p)]
