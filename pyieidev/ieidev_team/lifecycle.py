"""lifecycles/*.yml 命名生命周期模板加载（MVP 仅 full-delivery）。"""
from pathlib import Path

import yaml


class TemplateError(Exception):
    pass


def lifecycles_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "lifecycles"


def list_templates() -> list:
    d = lifecycles_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yml"))


def load_template(template_id) -> dict:
    path = lifecycles_dir() / f"{template_id}.yml"
    if not path.exists():
        raise TemplateError(f"unknown template: {template_id!r}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))
