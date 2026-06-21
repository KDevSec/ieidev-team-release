# Output Skeleton v2 — fielded test cases (1:1 from 测试点 .md with optional h4 测试范围 sub-grouping)

This file shows the full output layout. SKILL.md §4 references this for the exact structure.

Two modes are supported — chosen by SKILL.md §1 pre-flight based on whether the upstream 测试点 .md contains `^#### 测试范围` h4 wrappers:

- **§A v2 mode (h4 present)**: 3-level layout (file → AR → 测试范围 → block); IDs `TC-AR{数字段}-G{N}-{NNN}`.
- **§B v1-downgrade mode (no h4)**: 2-level layout (file → AR → block); IDs `TC-AR{数字段}-{NNN}` (identical to [test-cases-old output-skeleton](deprecated, not in this repo)).

---

## §A v2 mode (h4 present in upstream — typical for ieidev-team:test-points output)

### File-level layout

```markdown
# <被测对象> 测试用例（fielded, Playwright-handoff, v2 with 测试范围 sub-grouping）

> 来源测试点：<absolute path-to-input-测试点.md>
> 渲染模板：<absolute path-to-example>
> 生成方式：ieidev-team:test-cases — 1:1 renderer (no re-design); mode = v2 (h4 测试范围分组)
> 上游契约：用例名称 / 用例编号 / 需求编号 / 用例类型 / 优先级 / 是否准入 / 是否UI自动化 / 是否API自动化 / 预期结果 均逐字透传，不再判
> 仅生成：测试步骤 / 前置条件 / 测试数据（按 Playwright 接驳约定派生）
> v2 hard rules: (a) AR header spec 原样不锁前缀  (b) 不自造 .01/.02 子段  (c) 角色取自 spec 不默认超级管理员  (d) h4 测试范围号编入 G{N} 段

---

## 一、AR-PRL-FUN-01.001.00 — <AR 标题原文 byte-equal from input>

### 测试范围 1 — <h4 摘要原文 byte-equal from input>

<block 1>

---

<block 2>

---

### 测试范围 2 — <下一个 h4 摘要原文>

<block 1 of 测试范围 2>   ← 流水号 reset 重新从 001 起

---

## 二、AR-PRL-FUN-01.002.00 — <下一个 AR 标题>

### 测试范围 1 — <h4 摘要>

<block N>

---

## 用例集合统计

<table — see §statistics>

## 自检清单

<from example §七 verbatim>
```

### Block layout (v2 — one block per upstream row; byte-faithful to `--example`'s §二)

```
- 用例编号：TC-AR<数字段>-G<N>-<3 digits>
- 用例名称：<= 测试点标题 byte-equal>
- 需求编号：<= input ### AR-… header byte-equal — spec 原样，不加 .01/.02 子段>
- 测试范围分组：测试范围 <N>           ← v2 新增可选字段；推荐携带便于审计，编号已硬编码在 G{N} 段
- 用例类型：<基本流 | 异常流>
- 优先级：<1|2|3|P0|P1|...>
- 是否准入：<是|否>
- 是否UI自动化：<是|否>     # 字段名一字不差对齐源 测试点 .md 列头；下游 grep 字面匹配
- 是否API自动化：<是|否>    # 字段名一字不差对齐源 测试点 .md 列头；下游 grep 字面匹配
- 前置条件：
  1. 操作人员：<spec 给定角色，非默认超级管理员>
  2. <其他环境/数据条件>
- 测试数据：<one-liner or sub-bullets, generative, constrained>
- 测试步骤：
  1. <step 1, Playwright-friendly>
  2. <step 2>
  ...
- 预期结果：
  1. <= 源 预期结果 第 1 条 byte-equal>
  2. <= 源 预期结果 第 2 条 byte-equal>
  ...
  N. 平台数据保持不变   ← 仅 异常流 且 源缺失时追加
```

**Field-order rule**: match the example's §二 / §样例 block exactly. For v2 the example is typically `SOP_测试用例MODv2.md`, which places `测试范围分组` between `需求点名称` and `用例类型`.

### Per-AR header (v2)

```
## <一|二|三|...>、<AR编号 byte-equal from input> — <AR 标题原文 byte-equal from input>
```

The AR 编号 must match the input `### AR-…` header verbatim — including spec-given prefix (`AR-PRL-FUN-` / `AR-SATP-` / `AR-KDevSec-` / 其他); **不得**加 `.01 / .02 / .03` 子段（v2 Phase 6 hard rule）.

### Per-测试范围 sub-header (v2)

```
### 测试范围 <N> — <h4 摘要原文 byte-equal from input>
```

The N value and the 摘要 text must match the upstream `#### 测试范围 N — …` h4 line verbatim — including any `（spec FRn criteria X / Y / Z）` parenthetical.

### Block ordering rule (v2)

- All blocks belonging to the same upstream 测试范围 **must be contiguous** under that `### 测试范围 N` sub-header.
- **Never** interleave blocks across 测试范围 boundaries (would lose the h4 grouping semantics + break per-group # row-number reset).
- Order within a 测试范围: follow input row order strictly (1-indexed).
- Order between 测试范围: follow input h4 order strictly (N=1, then N=2, ...).
- Order between ARs: follow input `### AR-…` order strictly.

---

## §B v1-downgrade mode (no h4 in upstream — backward-compat with test-points-old output)

Identical to [test-cases-old output-skeleton.md](deprecated, not in this repo) — reproduced inline for self-containment:

### File-level layout (v1-downgrade)

```markdown
# <被测对象> 测试用例（fielded, Playwright-handoff）

> 来源测试点：<absolute path-to-input-测试点.md>
> 渲染模板：<absolute path-to-example>
> 生成方式：ieidev-team:test-cases — 1:1 renderer (no re-design); mode = v1-downgrade (no h4)

---

## 一、AR-SATP-04.001.001 — <AR 标题原文>

<block 1>

---

<block 2>

---

## 二、AR-SATP-04.001.002 — <下一个 AR 标题>

<block N>

---

## 用例集合统计

<table>

## 自检清单

<from example §七 verbatim>
```

### Block layout (v1-downgrade)

```
- 用例编号：TC-AR<数字段>-<3 digits>     ← no G{N} segment in this mode
- 用例名称：<= 测试点标题 byte-equal>
- 需求编号：<AR-XXX-YY.YYY.ZZZ> / <FR-NNN if available>
- 用例类型：<基本流 | 异常流>
- 优先级：<1|2|3|P0|P1|...>
- 是否准入：<是|否>
- 是否UI自动化：<是|否>
- 是否API自动化：<是|否>
- 前置条件：<one-liner or multi-line bullets, generative, constrained>
- 测试数据：<one-liner or sub-bullets, generative, constrained>
- 测试步骤：
  1. <step 1>
  2. <step 2>
- 预期结果：
  1. <= 源 预期结果 第 1 条 byte-equal>
  2. <= 源 预期结果 第 2 条 byte-equal>
```

Note: `测试范围分组` field is **omitted** in v1-downgrade mode (no h4 source to carry).

---

## §statistics — Statistics table (both modes)

```
| 指标 | 数值 |
|---|---|
| AR 数 | N (== 上游 ### AR- 数) |
| 测试范围分组数 | K (v2 mode only: == 上游 #### 测试范围 数; omit row in v1-downgrade mode) |
| TC 总数 | M |
| 准入用例数 | sum where 是否准入==是 |
| 基本流 | sum where 用例类型==基本流 |
| 异常流 | sum where 用例类型==异常流 |
| UI 自动化候选 | sum where 是否UI自动化==是 |
| API 自动化候选 | sum where 是否API自动化==是 |
```

Numbers are **computed from the actual emitted blocks**, not from the input — these are sanity-check numbers. If they don't match the input's totals, the cardinality contract (§3.1) is broken; stop and report.

---

## Block separator (both modes)

Every block ends with `\n---\n`. The last block before a new `##` AR header (or `###` 测试范围 sub-header in v2 mode) also ends with `\n---\n` (consistency > visual tightness — parsing tools want a stable trailer).

---

## Self-check

Copy the example's §七 self-check verbatim if present (do not paraphrase). If the example has no §七, omit this section — do **not** invent one.

The v2 example (`SOP_测试用例MODv2.md`) has 16 self-check items (8 通用 + 8 1:1 映射 including 3 h4-related). The v1 example (`SOP_测试用例MOD.md`) has 13 items (8 通用 + 5 1:1 映射). Pick whichever the user passed as `--example`.

---

## Reporting upstream issues

When you find an issue you cannot fix (e.g. duplicate 测试点标题 within an AR — which would yield duplicate 用例名称, breaking downstream test-function-name hashing), append a "⚠️ 上游问题待回流" section at the end:

```
## ⚠️ 上游问题待回流（renderer 不修，需要上游 ieidev-team:test-points 调整）

- 重复标题：AR-PRL-FUN-01.001.00 测试范围 1 第 3 行与 测试范围 2 第 1 行的 测试点标题 完全一致 → 会生成同名 用例名称（虽然 G{N} 段不同），downstream Playwright 函数名仍可能冲突。建议给其中一行加上区分性后缀。
- 优先级缺失：AR-PRL-FUN-01.002.00 测试范围 2 第 2 行 优先级 字段为空 → 已透传为空，建议补 1/2/3。
- 角色无法定位：上游 测试点 .md 的 `## 范围与参数` 表 + `## 模式与生成元数据` 段 + 测试点标题 prefix 三处都没有角色明文 → 已使用 stop-and-ask 流程，请用户传 `--role <X>` override；本次输出暂用 `{未指定}` 占位，请在 v2 hard rule Phase 5 上游回流修复。
- 伪 AR 嫌疑：上游 测试点 .md 出现 `### AR-PRL-FUN-01.001.01` 这种带 .01/.02 子段的标题 → 违反上游 v2 Phase 6 hard rule，本 skill 已按字面渲染为伪 AR 但建议上游回流合并到 `AR-PRL-FUN-01.001.00` + 测试范围 1 h4 子层。
```

This keeps the byte-equality contract intact (no silent fixes) while surfacing what needs human attention.
