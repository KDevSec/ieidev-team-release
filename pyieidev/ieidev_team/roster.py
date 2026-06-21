"""staff.yml + per-员工 node-table 的解析助手（lint / confirm 共用）。"""
from pathlib import Path

import yaml


class RosterError(Exception):
    pass


def team_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_staff() -> dict:
    return yaml.safe_load((team_root() / "staff.yml").read_text(encoding="utf-8"))


def _staff(staff):
    return staff if staff is not None else load_staff()


def employee(emp, staff=None):
    return _staff(staff).get("employees", {}).get(emp)


def is_flow_owner(emp, staff=None) -> bool:
    e = employee(emp, staff)
    return bool(e) and e.get("kind") == "flow-owner"


def _node_table_map(e) -> dict:
    """归一化：单数 node_table → {flow: path}；复数 node_tables 原样。"""
    if "node_tables" in e:
        return dict(e["node_tables"])
    if e.get("node_table"):
        # 单数：从表里读 flow 字段作 key
        path = e["node_table"]
        data = yaml.safe_load((team_root() / path).read_text(encoding="utf-8"))
        return {data["flow"]: path}
    return {}


def flows_for(emp, staff=None) -> list:
    e = employee(emp, staff)
    if not e:
        return []
    return sorted(_node_table_map(e).keys())


def node_table_data(emp, flow, staff=None) -> dict:
    e = employee(emp, staff)
    if not e:
        raise RosterError(f"unknown employee: {emp!r}")
    nt = _node_table_map(e)
    if flow not in nt:
        raise RosterError(f"{emp!r} has no flow {flow!r} (has {sorted(nt)})")
    return yaml.safe_load((team_root() / nt[flow]).read_text(encoding="utf-8"))


def gate_specs(emp, flow, staff=None) -> dict:
    return node_table_data(emp, flow, staff).get("gate_specs", {})


def delivery_node(emp, flow, staff=None):
    return node_table_data(emp, flow, staff).get("delivery_node")
