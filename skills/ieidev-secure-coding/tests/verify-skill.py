"""Structural verifier for ieidev-team secure-coding skill.

Checks the skill for:
- SKILL.md frontmatter (name + description)
- SKILL.md required sections (首次激活 / 项目检测 / Layer 1 / Layer 2 / Reference 索引)
- Each reference file present with expected top heading
- Each numbered subsection (## 3.X.Y) has a complete 规则/反例/正例 triplet
- Files without numbered subsections (e.g. 06-error-handling) have at least one
  top-level ## 规则 / ## 反例 / ## 正例 block

Run from anywhere:
    python3 skills/secure-coding/tests/verify-skill.py
"""
import re
import sys
from pathlib import Path

# Script is at skills/secure-coding/tests/verify-skill.py
# PLUGIN_ROOT resolves to skills/secure-coding/
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT

REQUIRED_SKILL_SECTIONS = [
    "首次激活",
    "项目检测",
    "Layer 1",
    "Layer 2",
    "Reference 索引",
]

# Per-skill configuration: (skill-name, [(reference-filename, category, expected-subsection-count), ...])
# skill-name "" means SKILLS_DIR itself (i.e. secure-coding/)
SKILLS = [
    (
        "",
        [
            ("01-input-validation.md", "3.1", 10),
            ("02-security-features.md", "3.2", 11),
            ("03-encapsulation.md", "3.3", 5),
            ("04-api-misuse.md", "3.4", 2),
            ("05-time-and-state.md", "3.5", 1),
            ("06-error-handling.md", "3.6", 0),
            ("07-code-quality.md", "3.7", 1),
            ("08-environment.md", "3.8", 3),
        ],
    ),
]


def check_skill_md(skill_dir, errors):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"missing: {skill_md}")
        return
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{skill_md.name}: missing YAML frontmatter")
    if f"name: {skill_dir.name}" not in text:
        errors.append(f"{skill_md.name}: frontmatter missing 'name: {skill_dir.name}'")
    if "description:" not in text:
        errors.append(f"{skill_md.name}: frontmatter missing 'description:'")
    for section in REQUIRED_SKILL_SECTIONS:
        if section not in text:
            errors.append(f"{skill_md.name}: missing required section '{section}'")


def check_reference(skill_dir, filename, category, expected_subs, errors):
    path = skill_dir / "references" / filename
    if not path.exists():
        errors.append(f"missing reference: {path}")
        return
    text = path.read_text(encoding="utf-8")
    if not re.search(rf"^# {re.escape(category)} ", text, re.MULTILINE):
        errors.append(f"{filename}: missing top heading '# {category} ...'")
    if expected_subs > 0:
        sub_pattern = rf"^## {re.escape(category)}\.\d+ "
        found = len(re.findall(sub_pattern, text, re.MULTILINE))
        if found != expected_subs:
            errors.append(
                f"{filename}: expected {expected_subs} subsections matching "
                f"'## {category}.X', found {found}"
            )
        rules = len(re.findall(r"^### 规则", text, re.MULTILINE))
        bad = len(re.findall(r"^### 反例", text, re.MULTILINE))
        good = len(re.findall(r"^### 正例", text, re.MULTILINE))
        if rules != expected_subs or bad != expected_subs or good != expected_subs:
            errors.append(
                f"{filename}: expected {expected_subs} 规则/反例/正例 triplets, "
                f"found 规则={rules}, 反例={bad}, 正例={good}"
            )
    else:
        for label in ("规则", "反例", "正例"):
            if not re.search(rf"^## {label}", text, re.MULTILINE):
                errors.append(f"{filename}: missing top-level '## {label}' block")


def main():
    errors = []
    for skill_name, refs in SKILLS:
        skill_dir = SKILLS_DIR / skill_name
        if not skill_dir.is_dir():
            errors.append(f"missing skill dir: {skill_dir}")
            continue
        check_skill_md(skill_dir, errors)
        for fn, cat, n in refs:
            check_reference(skill_dir, fn, cat, n, errors)
    if errors:
        print("VERIFY FAILED")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("VERIFY OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
