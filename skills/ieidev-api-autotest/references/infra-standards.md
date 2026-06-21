# 基建规范 — 归档四件产物 / 登录 / 重试 / 失败归类 / 残留

这些通常落在 `conftest.py` + HTTP 客户端基类 + 跨用例汇总脚本里。一般不动；只在扩归类规则或接新环境时改。下面是"为什么这么设计"，避免下游改坏。

## 四件产物归档（conftest 自动，无需手填 --junitxml/--html）

`pytest_configure` 建 `reports/<ts>/`（ts=YYYYMMDD_HHMMSS），`pytest_sessionfinish` 收尾，一次执行一文件夹：

```
reports/
├── <ts>/
│   ├── junit_<ts>.xml        # 机器可解析（三分计数的权威源）
│   ├── report_<ts>.html      # 自包含 HTML 报告（建议汉化/可直接发邮件）
│   ├── defects_<ts>.csv       # 用例 / 名称 / 复现步骤 / 错误信息 / 原因分析 / (截图，API 留空)
│   └── test_run_<ts>.log     # 运行日志（含后端响应体，三分诊断靠它）
└── RESULT_<date>_full.md     # 跨用例汇总（汇总脚本产出）
```

**交付声明必须附这四件**（defects.csv 即使 0 条也建表头）。"测试已通过"不附 evidence = 视为未执行。

## 登录复用 + token 隔离（治 401 级联 / 连接 RST）

两个反复验证的修复，**不要回退**：
- **会话级登录 + 登录容错重试**：原来每用例登录 N 次，放大了后端偶发连接 RST。session 级登录一次。
- **客户端 headers 实例级隔离**（`self.headers = dict(BaseClient.headers)`）：原来类级共享，受限账号登录失败会清空共享 Authorization → 污染管理员 client → 后续 401 级联。实例级隔离后，受限账号失败不影响管理员。

## 重试 + 退避（只治传输层，不掩盖断言 flaky）

`retry_count` + 各请求方法加退避，**仅在请求无响应（连接 RST / 空响应）时重连**。

🔴 红线：retry 只重连**传输层**。**禁止**用 retry/sleep 去重试一个**断言失败**的用例求绿——那是掩盖 flaky/real-defect。断言级失败一次就是一次。

## 失败根因归类（扩规则的口径）

conftest 里的根因归类函数给 defects.csv "原因分析"列归类。优先级：① 用例显式 `BUG[<分类>]:` 标签 → 直接采信；② 关键字 heuristic（已知缺陷标签 + 业务成功标志缺键 / 401 / 5xx / 连接 RST / 负向数据副作用）；③ 兜底"待人工分析"。

新增一类真缺陷标签时，在更泛的规则**之前**补一条精确 heuristic，让 CSV 标注准确：
```python
if "<新缺陷标签>" in msg or "<该缺陷的特征短语>" in msg:
    return "<新缺陷标签>：<一句话说明>"
```
注意 heuristic 顺序——更具体的放前面（避免被泛 "'success'"/"KeyError" 规则抢先误标）。改完归类要**重跑一次**让 CSV 重新生成。

## 残留资源 loud-warn（Fail Loud）

后端**无 DELETE 接口**的资源，cleanup 不能真删 → 只 `log.warning` 留痕，**不假装清理**。多轮全量会在后端累积测试前缀资源——在汇总报告残留段写明"需 API/DBA 按前缀批量清"。不要为了"干净"伪造删除调用。

## 跨用例汇总

跑完全量后跑汇总脚本，按 junit classname 自动分节（不硬编码模块名），输出 `RESULT_<date>_full.md`：合计三分 + 分节结果表 + 三分诊断 + 残留 warn。
