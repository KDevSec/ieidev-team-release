# 失败三分法 — framework / script / real-defect

跑完一片红，**不要凭印象瞎猜**。每条 FAIL 必须落到三类之一，处置方式各不同。核心纪律：只有 framework + script 假红才允许改脚本；real-defect 保留红。

## 三分决策树

```
一条 FAIL
  │
  ├─ 后端响应体（captured 输出 / junit <failure>）是什么？
  │    看 code / msg / 业务成功标志的真值，不看 assert 文案臆断
  │
  ├─① 失败发生在「请求都没正常发出/收到」层面？
  │     （登录失败、token 为空、连接 RST/EOF、归档基建报错）
  │     → framework：改基建（登录/客户端/归档），不动业务断言
  │
  ├─② 后端响应「符合用例本意」，但用例写法让断言够不着？
  │     （负向用例走了正向封装；账号名没对齐预置；字段路径/URL 写错；
  │      正向流没轮询确认就查）
  │     → script：修脚本写法，不弱化业务断言
  │
  └─③ 后端响应「不符合用例本意」，且本意是对的？
        （应有的字段缺失、格式不符、数据范围未裁剪、越权未拦截、唯一性未约束）
        → real-defect：保留红 + 录 defects_<ts>.csv + 不 xfail
```

## 关键：先证"run 非 stale"，再下结论

判 framework vs real-defect 拿不准时，先排除"看的是旧报告"：
- 看 `reports/<ts>/` 时间戳是不是本次跑的；
- 看**同模块的关联 PASS 用例**是否同批跑出来（证明登录/连接是通的）；
- 再看后端真实响应体定位崩在测试侧（harness）还是产品侧。

说不清就**当 real-defect 保留红**——第零原则：藏起来的红 = 任务失败，宁可多保留一条待核实的红。

## 各类的标准处置

| 类 | 例 | 处置 | 禁止 |
|---|---|---|---|
| framework | 登录连接 RST 致 setup ERROR；类级 headers 共享致 401 级联 | session 级登录 + 实例级 headers + retry+退避（见 `infra-standards.md`） | 用 retry 掩盖断言级 flaky |
| script | 负向走正向封装（误红）；账号名没对齐预置（永远 SKIP） | 改 raw 请求；对齐预置账号 | 把强断言换永真弱断言 |
| real-defect | 字段缺失 / 时间戳格式不符 / 数据范围未生效 / 越权未拦截 | 保留红 + defects.csv + 汇总报告标注 | 伪造字段 / 改预期 / skip / xfail / try-except 吞 |

## defects_<ts>.csv 怎么读

conftest 的根因归类函数自动给"原因分析"列归类（已知缺陷标签 + 通用 heuristic）。但这是**粗粒度辅助**——权威真值永远是 `junit` `<failure>` + captured 输出里的后端响应体。归类与响应体冲突时，以响应体为准，并考虑给归类函数补一条更精确的 heuristic（见 `infra-standards.md`）。

## 修完必须重跑验证，不靠推断

改了 framework/script 假红后，**重新跑**对应用例确认转绿（或单测复检），不要靠"我觉得改对了"。real-defect 不重跑求绿——它本来就该红。
