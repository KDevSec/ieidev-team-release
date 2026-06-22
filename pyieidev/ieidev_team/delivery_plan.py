"""delivery-plan.yml schema：解析 + 形状校验 + 冻结读写。

语义校验（emp 真存在 / handoff 合法 / gate id 真存在）在 lint.py。
delivery-plan.yml 由 CEO 确认后冻结写一次、之后不改；进度从 dispatch 事件派生。
"""
import numbers
from pathlib import Path

import yaml

REQUIRED_KEYS = frozenset(
    {"template_id", "slug", "goal", "confidence", "stages"})


def _normalize_stage(s: dict) -> dict:
    """YAML 1.1 parses bare `on` key as boolean True; normalise back to string."""
    if True in s and "on" not in s:
        s = dict(s)
        s["on"] = s.pop(True)
    return s


def parse(text) -> dict:
    plan = yaml.safe_load(text) or {}
    plan.setdefault("review_overrides", {})
    plan.setdefault("human_gates", [])
    if isinstance(plan.get("stages"), list):
        plan["stages"] = [_normalize_stage(s) for s in plan["stages"]]
    return plan


def structural_errors(plan) -> list:
    errs = []
    for k in REQUIRED_KEYS:
        if k not in plan or plan[k] in (None, ""):
            errs.append(f"missing required key: {k}")
    conf = plan.get("confidence")
    if not isinstance(conf, numbers.Real) or isinstance(conf, bool) \
            or not (0.0 <= float(conf) <= 1.0):
        errs.append(f"confidence must be a number in [0,1], got {conf!r}")
    stages = plan.get("stages")
    if not isinstance(stages, list) or not stages:
        errs.append("stages must be a non-empty list")
    else:
        for i, s in enumerate(stages):
            for f in ("emp", "flow", "on"):
                if f not in s:
                    errs.append(f"stage[{i}] missing field: {f}")
    return errs


def path(workspace, slug) -> Path:
    return Path(workspace) / ".ieidev" / "features" / slug / "delivery-plan.yml"


def write(workspace, plan) -> Path:
    p = path(workspace, plan["slug"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
                 encoding="utf-8")
    return p


def read(workspace, slug):
    p = path(workspace, slug)
    if not p.exists():
        return None
    try:
        plan = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(plan, dict) and isinstance(plan.get("stages"), list):
            plan["stages"] = [_normalize_stage(s) for s in plan["stages"]]
        return plan
    except (yaml.YAMLError, OSError):
        return None


def needs_clarification(plan, threshold: float = 0.6) -> bool:
    """置信度门控：plan confidence < 阈值 → 需先和人澄清需求（#7）。
    缺 confidence → 不强制（False）；非数值 → 保守要求澄清（True）。"""
    if "confidence" not in (plan or {}):
        return False
    try:
        return float(plan["confidence"]) < threshold
    except (TypeError, ValueError):
        return True
