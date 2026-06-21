# GB/T 25010 Quality Characteristics — minimum-technique floor

For each sub-characteristic marked **in scope** in the §6.2 Quality Coverage Matrix, generate at least the testing approach below. Do not generate cases for sub-characteristics out of scope; record the reason in §6.2 instead.

These are floors, not ceilings. Real risk-driven testing combines techniques.

## 8.1 功能性 Functional Suitability

| Sub-char | Minimum approach |
|---|---|
| 功能完备性 | 需求覆盖矩阵：声明的每个功能 ≥1 用例 |
| 功能正确性 | EP + BVA + Decision Table 组合 |
| 功能适合性 | Scenario Testing — 用户能否真正完成核心任务 |

## 8.2 性能效率 Performance Efficiency

| Sub-char | Minimum approach |
|---|---|
| 时间特性 | 响应时间 / 吞吐量基准；正常 / 峰值 / 极限三档 |
| 资源利用性 | CPU / 内存 / 磁盘 / 网络占用度量 |
| 容量 | 最大并发 / 数据量 / 连接数边界（BVA 思想） |

## 8.3 兼容性 Compatibility

| Sub-char | Minimum approach |
|---|---|
| 共存性 | 与同环境其他软件并存不冲突；配置矩阵 + Pairwise |
| 互操作性 | 与已声明外部系统/格式/协议交互；接口契约测试 |

## 8.4 易用性 Usability

| Sub-char | Minimum approach |
|---|---|
| 可识别适合性 / 易学性 / 易操作性 | 任务式可用性测试（典型用户无人辅助完成核心任务） |
| 用户差错防御性 | 错误输入 / 误操作 / 撤销恢复（错误推测） |
| 用户界面舒适性 | 视觉/交互一致性清单 |
| 可访问性 | WCAG 2.1 AA 清单（颜色对比 / 键盘可达 / 屏幕阅读器 / ARIA） |

## 8.5 可靠性 Reliability

| Sub-char | Minimum approach |
|---|---|
| 成熟性 | 长时间运行 / 故障频率 |
| 可用性 | SLA 测算（如 99.9% 在 30 天窗口） |
| 容错性 | 故障注入：网络断 / 依赖宕 / 磁盘满 / 超时 |
| 易恢复性 | 崩溃后恢复时间 / 数据完整性 / 断点续传 |

## 8.6 信息安全性 Security

| Sub-char | Minimum approach |
|---|---|
| 保密性 | 鉴权 / 加密 / 敏感数据脱敏 |
| 完整性 | 防篡改 / 签名校验 |
| 抗抵赖性 | 审计日志不可删 |
| 可核查性 | 操作可追溯到主体 |
| 真实性 | 身份验证强度 |

强制清单：OWASP Top 10 · SQL 注入 · XSS · CSRF · 越权（IDOR / 权限提升）· 敏感配置泄漏。

## 8.7 维护性 Maintainability

模块化 / 可重用性 / 易分析性 / 易修改性 / 易测试性 — 多为静态评审项；测试侧验证：日志可读、错误码规范、配置外置、接口稳定。

## 8.8 可移植性 Portability

| Sub-char | Minimum approach |
|---|---|
| 适应性 | 多环境部署（OS / 浏览器 / 分辨率矩阵） |
| 易安装性 | 全新安装 + 升级 + 回滚 + 卸载残留 |
| 易替换性 | 与被替换产品的功能 / 数据迁移等价 |

---

## How to fill §6.2 Matrix

```
| 质量特性    | 子特性          | 在范围? | 关联条件          | 用例数 | 备注                         |
|-------------|-----------------|---------|-------------------|--------|------------------------------|
| 功能性      | 功能完备性      | 是      | COND-001..010     |  18    | 覆盖产品说明全部功能         |
| 兼容性      | 互操作性        | 否      | —                 |   0    | 系统无外部接口，已确认范围外 |
```

In `feature-spec` and `api-contract` modes, you may omit rows where the sub-characteristic is unambiguously not in scope. In `full-conformity` mode, list all 31 rows — third-party assessors expect to see the full matrix even when most rows say "否".
