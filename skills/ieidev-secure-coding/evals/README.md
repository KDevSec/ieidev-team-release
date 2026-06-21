# secure-coding skill — Evaluation Fixtures

本目录存放评测 fixture，配套 design spec 与实施计划见：

- 设计：[`docs/skills/ieidev-secure-coding/2026-04-29-01-secure-coding-skill-eval-design.md`](../../../docs/skills/ieidev-secure-coding/2026-04-29-01-secure-coding-skill-eval-design.md)
- 计划：[`docs/skills/ieidev-secure-coding/2026-04-29-01-secure-coding-skill-eval-plan.md`](../../../docs/skills/ieidev-secure-coding/2026-04-29-01-secure-coding-skill-eval-plan.md)
- 报告：[`docs/skills/ieidev-secure-coding/eval-2026-04-29.md`](../../../docs/skills/ieidev-secure-coding/eval-2026-04-29.md)

## 重跑步骤（手动）

### A 段（触发可靠性，3 用例）

派 3 个 fresh subagent（Claude Code Agent 工具，`subagent_type: general-purpose`），每个 prompt：

```
Please review the following Python file. Report any concerns, bugs, or
improvements you'd suggest. Be thorough.

```python
<贴 fixtures/A-trigger/a0X-*.py 的全文>
```
```

**关键：prompt 不可提及 "security" / "skill" / "secure-coding"** —— 否则 A 段失去意义。

判定：subagent 是否自动 invoke `secure-coding` skill？invoke 后 Read 的 reference 是否对应 fixture 实际问题？

### B 段（漏洞召回率，8 用例）

派 8 个 fresh subagent，每个 prompt：

```
Use the secure-coding skill (available in your environment) to
review the following Python file. List every security issue you find,
with the category number (3.1 / 3.2 / ... / 3.8) and the recommended fix.

```python
<贴 fixtures/B-recall/b0N-*.py 全文>
```
```

评分对照 `b0N-*.expected.txt` sidecar 的预埋漏洞清单：

- 命中数 = 预埋漏洞中被报告出来的条数
- 漏报数 = 预埋数 - 命中数
- 误报数 = 报告了但 sidecar 未列的"问题"（人工判断真实性）
- 召回率 = 命中 / 预埋

如探针发现 subagent 看不到 plugin skill，启用兜底：在 prompt 前注入 `plugins/ieidev-secure-coding/skills/secure-coding/SKILL.md` + 8 个 reference 全文。

### D 段（对抗 / 误报，4 用例）

人工评估，无需 subagent。每个 fixture 文件头 docstring 写明"为什么安全"，按 SKILL.md 关键词映射表查对应 reference，模拟 reference 规则判定，看是否会误报。

### C 段（完成清单实战）

无 fixture。在主会话内对 4 个真实业务场景按"朴素实现 → 走 8 项 gate → 评估"三步法演练。详见 plan Task 8-11。

## Fixture 索引

```
fixtures/
├── A-trigger/                          # 3 个，文件头不写测试提示
│   ├── a01-vulnerable.py               # SQL 拼接 + eval
│   ├── a02-clean.py                    # 干净 CRUD
│   └── a03-borderline.py               # subprocess shell=False + yaml.safe_load
├── B-recall/                           # 8 个 .py + 8 个 .expected.txt sidecar
│   ├── b01-input.py                    # 3.1 输入验证
│   ├── b01-input.expected.txt
│   ├── b02-security.py                 # 3.2 安全特性
│   ├── b02-security.expected.txt
│   ├── ... (b03-b07 同结构) ...
│   ├── b08-environment.py              # 3.8 环境
│   ├── b08-environment.expected.txt
│   └── b08-environment.requirements.txt # 旧依赖样本
└── D-adversarial/                      # 4 个，docstring 写明"为何安全"
    ├── d01-subprocess-safe.py
    ├── d02-yaml-safe-load.py
    ├── d03-random-non-crypto.py
    └── d04-md5-checksum.py
```

## 评测频率建议

每次 skill 大版本变更（SKILL.md 或任何 reference 改动）后跑一次回归。日常微调（fixing typos / 加新关键词）无需重跑。
