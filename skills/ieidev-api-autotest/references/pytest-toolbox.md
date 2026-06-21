# pytest 工程工具箱（借鉴自 python-testing-patterns，全部带第零原则护栏）

这 5 个是 pytest 内置 / 生态里**与第零原则同向**的工程细节——它们让测试更诚实、更可审计、更能发现 BUG，而不是用来洗绿。每个工具下面都写清了**护栏（边界）**：越过护栏就会滑回 kdev 的禁区（mock 被测 / xfail / 弱绿），那时立刻停。

来源对照：python-testing-patterns（纯 pytest 技术手册）的可借鉴子集。它的 `patch("requests.get")` mock 后端 + `@pytest.mark.xfail` 两块是 kdev 明确禁区，**不在本文件**——反而是反面教材。

---

## 1. `monkeypatch.setenv / delenv` — 测试 harness 自己的环境读取

环境配置（base_url / 管理员账号密码 / 超时 / 受限账号名）现在多是改文件硬编码。用 `monkeypatch` 可以让"环境变量未设置走默认 / 设置走覆盖"两条路径都被覆盖，且改动只在单条用例内生效、用例结束自动还原，不污染别的用例。

```python
def test_base_url_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)   # raising=False：本来就没设也不报错
    assert resolve_base_url() == "http://test.local"     # 断言默认值生效（业务断言，不是永真）

def test_base_url_honors_override(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://staging.local")
    assert resolve_base_url() == "http://staging.local"
```

🚧 **护栏**：只 patch **测试自己读取**的环境变量（harness 的配置入口）。**绝不**用 monkeypatch 去替换被测后端的逻辑、响应或客户端方法——那就是 mock 被测对象，违反 R1 + 第零原则（测试自圆其说）。判别信号：你 patch 的对象属于"测试基建"还是"产品代码"？后者立刻停。

---

## 2. `tmp_path` 内置 fixture — 本地测试产物的隔离与自动清理

四件 evidence（junit / HTML / defects.csv / 日志）落盘、以及用例运行中产生的任何**本地临时文件**，走 pytest 内置的 `tmp_path`（一个 `pathlib.Path`），而不是手写 `/tmp/xxx` 再手动删。pytest 给每条用例独立目录、自动隔离、跑完自动回收，正好补 R2「用例后清理」里"本地文件类善后"的空缺。

```python
def test_export_writes_csv(tmp_path, api_client):
    out = tmp_path / "export.csv"          # 每条用例独占目录，互不串扰
    api_client.export_to(out)
    assert out.exists()
    assert "用户名" in out.read_text()      # 校内容，不只校存在
```

🚧 **护栏**：`tmp_path` 只管**本地文件**善后。**后端资源**（创建出来的用户/角色/部门/产品线等）的清理仍然走 R2 的 `cleanup` 栈（LIFO 逆序）；后端无 DELETE 接口的资源仍然 `loud warn` 留痕，**不能**用 tmp_path 的"本地自动清理"假装后端也清干净了——那是 Fail Loud 的反面。

---

## 3. `--strict-markers` + 集中声明 marker — Fail Loud 的代码级拦截

`--strict-markers` 让任何**未声明 / 拼错**的 marker（手滑写成 `@pytest.mark.integraton`）直接报错，而不是被 pytest 静默当成无效标记跳过。kdev 最怕的就是"静默 skip 假装覆盖"，这个开关把它变成代码级硬拦截，与第零原则 + Fail Loud 完全同频。配套在 `pytest.ini` / `pyproject.toml` 里集中声明合法 marker：

```ini
# pytest.ini
[pytest]
addopts = --strict-markers --tb=short
markers =
    smoke: 冒烟用例
    datascope: 数据范围 / 越权画像用例
    negative: 负向 / 异常流用例
```

🚧 **护栏**：`--strict-markers` 只约束 marker 拼写合法性，**不解禁 xfail**。三态铁规依旧只有 PASS / FAIL / SKIP——已知缺陷留 FAIL + defects.csv，未实现改 SKIP（带可审计理由），**禁用 `@pytest.mark.xfail`**。别因为这里出现了 marker 配置就顺手把 xfail 也声明进去。

---

## 4. 参数化的可读子用例名 `pytest.param(..., id=...)` / `fixture(params=...)`

参数化数据层（正向 + 负向输入集）用 `pytest.param(..., id="业务语义名")` 给每个参数组起**可读 id**，junit 报告里就显示 `test_create[空名拒绝]` 而不是 `test_create[--None-0]`。这直接服务 kdev"用例 docstring / 编号要能注入报告、可回溯"的诉求——红的时候一眼看出是哪个业务场景挂了。

```python
@pytest.mark.parametrize("payload,expect_ok", [
    pytest.param({"name": "正常产品线"},  True,  id="合法名称_应通过"),
    pytest.param({"name": ""},           False, id="空名_应被拒"),
    pytest.param({"name": "x" * 256},    False, id="超长名_应被拒"),
])
def test_create_productline(api_client, payload, expect_ok):
    resp = api_client.post_raw("/productline", json=payload)   # 负向走 raw（约束 2）
    assert resp_ok(resp) is expect_ok                          # 业务断言
```

🚧 **护栏**：(a) id 用业务语义命名，不要 `case1/case2`。(b) 参数化**不能**把负向输入塞进"内部默认断言业务成功"的封装里跑——那会把后端正确的拒绝误判成红（约束 2 的 script 假红）；负向分支仍走 raw 请求 + 断言业务失败。(c) 每个参数组仍要落到至少一条业务断言（Rule 9），不能退化成 `assert resp is not None`。

---

## 5. property-based / hypothesis — 对边界做模糊探测找真缺陷

`hypothesis` 的 `@given` 自动生成大量边界输入，特别适合 kdev 关心的**唯一性约束、数据范围裁剪、字段边界**这类否定性断言——它的目标（自动找会让断言失败的输入 = 找 BUG）和第零原则天然一致，是参数化数据层之上的"模糊探测"加强。

```python
from hypothesis import given, strategies as st

@given(name=st.text(min_size=1, max_size=64))
def test_create_then_query_roundtrip(api_client, name):
    # property：任何合法名建成后，列表查询都应能查到它（数据一致性）
    api_client.create_productline(name)        # 复合动作内含轮询确认（R1）
    assert name in api_client.list_names()     # 命中不一致就是 real-defect
```

🚧 **护栏**：(a) hypothesis 找到的违反就是 **real-defect，保留红 + 录 defects.csv**——**禁止**因为"偶发 / 不是每次都挂"就 xfail / skip / 加 try-except 吞掉（那正是 flaky 掩盖，第零原则禁区）。若怀疑是 harness 抖动而非真缺陷，按 `failure-triage.md` 先证"非 stale + 看后端响应体"再定性，说不清当 real-defect。(b) property 仍要编码 WHY（约束 4 / Rule 9）——断的是"为什么这条业务规则重要"，不是 `assert isinstance(x, list)` 这种永真弱断言。(c) 引入 hypothesis 是新依赖 + 偶发性成本，接入前与用户确认；不要默默加进 requirements。

---

## 一页速记

| 工具 | 补 kdev 的什么空缺 | 护栏（越界即停） |
|---|---|---|
| `monkeypatch.setenv/delenv` | 环境读取的默认/覆盖双路径覆盖 | 只 patch 测试自己的配置入口，绝不 patch 被测后端 |
| `tmp_path` | R2 本地文件善后 | 后端资源善后仍走 cleanup 栈 / loud-warn |
| `--strict-markers` | Fail Loud 拦截拼错的静默 skip | 不解禁 xfail，三态铁规不变 |
| `pytest.param(id=)` | 报告里可读子用例名、可回溯 | 负向仍走 raw（约束 2）；每组留业务断言 |
| `hypothesis @given` | 边界模糊探测找真缺陷 | 违反保留红，禁 xfail/skip 掩盖偶发 |
