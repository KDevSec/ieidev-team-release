# Template Override — merging `--example` with the dual-standard scaffolding

The user's `--example <path>` is a **rendering preference for §6.5 Test Cases only**. The skill's job is to honor it without losing the audit trail. This file shows how, by template family.

## The non-negotiable invariants

Regardless of example template, every TC row must carry these four facts somewhere:

1. **Coverage CIs** — which Coverage Items this TC exercises
2. **Quality Sub-characteristic** — which 25010 sub-characteristic
3. **Domain** — 产品说明 / 用户文档 / 软件
4. **Technique** — EP / BVA / DT / ST / Pairwise / MC/DC / Error Guess / Checklist

These can live in:
- a separate column added next to the example's existing columns, or
- a parenthetical suffix on the title, or
- a footnote anchor on each row mapping to a separate audit table

What you must **not** do: silently drop them.

## Required outer scaffolding

These sections must still appear (per §4 mode mapping in SKILL.md), in one of three placements:

- **prefix** before the rendered table
- **appendix** after the rendered table
- **companion file** `<output-stem>-audit.md` next to the main output

Pick whichever fits the example's house style. SP15-style xmind dumps usually look cleanest with a companion file; spreadsheet exports often work as a top header + footer.

## Family A — SP15 xmind / Markdown table (8-layer hierarchy)

User's example schema:

```
| # | 测试点标题 | 预期结果 | 用例类型 | 是否准入 | 是否自动化 | 优先级 | 标记 |
```

This schema is missing all four invariants. Strategy:

1. Render the §6.5 table with the user's columns intact.
2. **Add a companion audit file** `<stem>-audit.md` containing:
   - §6.1 Header
   - §6.2 Quality Coverage Matrix
   - §6.3 Test Conditions
   - §6.4 Coverage Items
   - §6.7 Coverage Summary
   - §6.8 Conformity Evaluation (light, per mode)
   - §6.9 RTM (the link from each TC row to its CIs / sub-char / domain)
   - §6.11 Risk

3. Add a single small column to the §6.5 table — `CI/SubChar` — even if narrow, so a reader can trace from row to RTM without reopening the audit file. If the user objects to the extra column, at minimum prefix the test point title with `[CI-EP-01,功能正确性,软件]` or similar.

Example rendered row keeping invariants visible:

```
| 1 | 超级管理员登录，项目管理-产品线管理，新增顶级产品线（接口主路径） | 1. 列表新增一行<br>2. 名称、描述与录入一致 | 基本流 | 是 | 是 | 1 | 🚩 | CI-EP-01,CI-BV-01 / 功能正确性 / 软件 |
```

## Family B — Excel / xlsx requirements matrix

User's example schema typically already has 10–20 columns including 模块, 优先级, 用例类型, 步骤, 预期, 实际. Strategy:

1. Render with the example's columns.
2. **Add three columns** at the right edge: `覆盖项`, `子特性`, `域`. Most assessors expect them anyway.
3. Place §6.1 / §6.2 as a top sheet (or top header rows in single-sheet mode).
4. Place §6.7 / §6.8 / §6.9 as a bottom footer.

## Family C — TestRail / Zephyr import format (CSV/JSON)

The example's schema is fixed by the import tool. Strategy:

1. Render with the tool's required columns.
2. Map invariants to **custom fields** if available (TestRail: `custom_*` fields; Zephyr: `Labels`).
3. If no custom fields available, prefix the test name: `[CI-EP-01|功能正确性|软件] ...`.
4. Emit the audit scaffolding as a separate `<stem>-audit.md` and reference it from the test plan description field.

## Family D — Plain Markdown / no example

Render §6.1–§6.11 directly per `references/output-templates.md`. No override needed.

---

## Recap

The template-override rule exists because the user usually cares about the table format their org consumes (xmind, xlsx, TestRail). The 25000.51 audit trail is non-negotiable but invisible to most internal readers; treating it as a companion file or appendix keeps both stakeholders happy.

When in doubt: **render-layer choice belongs to the user; audit-layer presence belongs to the standard**.
