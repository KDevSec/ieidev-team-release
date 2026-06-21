# ieidev-team:ieidev-ui-autotest (Claude Code Skill)

Playwright + pytest + Element-Plus UI 自动化测试规范固化 skill——把 6 大类规范固化为下游项目的强制实践。属于 [ieidev-team:ieidev-ui-autotest 插件](../../.claude-plugin/plugin.json) 的核心 skill。

**第零原则（基座）**：测试脚本的目的是执行测试、发现 BUG，不是生成通过率高的 reports 报告。

skill 详情与完整规范见 [`SKILL.md`](./SKILL.md)。

---

## 安装

本 skill 随 ieidev-team:ieidev-ui-autotest 插件分发，通过 Claude Code marketplace 安装：

```bash
claude plugin marketplace add KDevSec/kdev-agents
claude plugin install ieidev-team:ieidev-ui-autotest@kdev-agents
```

安装后 skill 自动注册，触发关键词即激活。

---

## 触发

用户提到以下关键词时自动激活（详见 [`SKILL.md`](./SKILL.md) description 完整列表）：
- 写/加/补/接入/优化测试用例
- test_arNN / TC-NNN / PageObject
- el-select 点不到 / toast 抓不到 / is_field_readonly
- defects_<ts>.csv / recon_elements / 用例为什么挂
- 登录复用 / 资源清理 / Element-Plus 自动化测试
- playwrightmode / playwrighttest / UI 与 spec 对不上

---

## 资产目录

```
skills/ieidev-team:ieidev-ui-autotest/
├── SKILL.md                          # 主 skill 文件
├── README.md                         # 本文件
├── .gitignore
├── assets/
│   ├── test_arNN_skeleton.py         # 基本流/异常流用例骨架
│   ├── recon_env_bootstrap.py        # STEP 0 fallback 脚本
│   └── test_case_doc_header.md.tpl   # 用例文档头部模板
├── evals/
│   └── evals.json                    # skill 质量回归 eval
└── references/
    ├── element-plus-pitfalls.md      # Element-Plus 10 大陷阱 + 迁移附录
    ├── infra-standards.md            # 登录复用 + 资源清理双轨
    ├── case-skeleton.md              # 新增测试模块接入指南
    ├── failure-diagnosis.md          # 失败诊断流程
    └── env-recon-bootstrap.md        # STEP 0 fallback 详细流程
```

---

## 与其他 skill 的关系

- **[ieidev-env-recon](../../../env-recon)**：承担 STEP 0 环境实测前置——本 skill 在 `recon/menu_list.md` 就绪后走 STEP 1+
- **[ieidev-team:ieidev-test-points](../../../test-points)** / **[ieidev-team:ieidev-test-cases](../../../test-cases)**：上游——产出测试点/测试用例 .md
- **[ieidev-team:ieidev-uicase-to-apicase](../../../uicase-to-apicase)**：并行——`是否UI自动化=否` 的用例分流到此做 API 自动化

---

## 维护

改动建议：
- 改 `SKILL.md` 主流程 → 同步检查 `references/*.md` 是否需要新增/作废条目
- 加新 reference → 在 `SKILL.md` 的"何时该读哪个 reference"表格补一行
- 加新 Element-Plus 陷阱 → 按 `element-plus-pitfalls.md` 末尾"发现新陷阱时的标准流程"实证后追加
- 升版本 → 同步 bump `../../.claude-plugin/plugin.json` 的 `version` + 写 `../../CHANGELOG.md`
