---
name: codegraph-spec-link
description: spec ↔ code 语义对齐审计——通过 LLM subagent 把 spec 文档（FR 表格行 + section）关联到代码节点（documents 边），输出统一两维报告（实现状态 + 同步状态）。触发时机：用户说"spec 对齐 / 需求追溯 / 哪些需求没做 / 文档代码同步审计 / spec-link"，或对一份 PRD 做实现状态盘点时。
---

# /codegraph-spec-link

> 节点 ID / tag 命名约定：详见 [conventions.md](references/conventions.md)
>
> **本 skill 取代了旧的 `codegraph-doc-sync`**。它依靠 LLM 真实判定每条 spec intent 是否有代码实现，比 UA 自动产的浅 `documents` 边可靠得多。

## §0.5 PYTHONPATH 自包含（照抄即可）

🔴 **每条调 ingestor 的 python 命令都行内自带 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev` 前缀 + `python3 -m ieidev_ingestor`，不靠一次 `export` / `cd` 给后续命令兜底**——因为 Claude Code 的 Bash 工具每次调用都是全新 shell、环境变量不跨调用持久（官方："Shell state (env vars) does not persist"），靠跨调用变量必然报 `No module named 'ieidev_ingestor'`。下文每条 `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_ingestor ...` 都已照此自包含写好，照抄整条即可、每条单独必成功。此 `python -m` 调用方式与 core/team/hud 全仓四包一致。（`${CLAUDE_PLUGIN_ROOT}` 在本 skill 内容读取时已就地替换成绝对安装路径。）

## 前置条件

- `.understand-anything/knowledge-graph.json` 存在（由 `/codegraph-build` 构建）
- 图谱里含有 `document` 节点（即 UA build 时把 markdown 纳入了，未被 `.understandignore` 排除）
- 在 git 仓库（漂移检测需要 `git log`）

## Step 1：前置面板 1（开场知情同意）

向用户展示：

````markdown
## 即将执行: /codegraph-spec-link

### 这次会做什么
1. **prepare**（本地）：扫图谱里的 document 节点，按 B+ 粒度抽 spec intent（FR 表格行 + section），对每条 intent 用关键词重叠做候选检索，写 intents.json
2. **judge**（LLM）：对每条 intent 派一个 sonnet subagent 判定（implemented / partial / not_found）
3. **finalize**（本地）：把 verdicts 写成 `documents` 边（direction=backward, weight=confidence），更新 graph extras，生成两维统一报告

### 成本提示 ⚠️
- 实际 LLM 调用数 = 抽出的 intent 数（PRD 风格的 spec 通常 10~50 条）
- **不建议在按"请求次数"计费的 coding plan 上跑** —— 建议切到 API 计费
- 估算耗时：几分钟（intent 多并发 5 个）

### 这次会产生
- 更新 `.understand-anything/knowledge-graph.json`（新增/重写 documents 边 + extras 元数据）
- `.understand-anything/intermediate/spec-link-intents.json` / `spec-link-verdicts.json`
- `.understand-anything/reports/spec-link-<timestamp>.md`（详细报告）

### 跑完后你可以做的事
- 直接读上面报告里的"❌ 未发现实现"列表 → 那些是建议人工先核对的
- `/codegraph-trace` —— 双向追溯（含本次产生的 documents 边）
- `/codegraph-impact` —— 变更安全爆炸半径
- `/codegraph-build` —— 全图谱重建（也烧 LLM，按需）

### 继续? [y/n]
````

用户 `n` → 退出并报告"用户取消"。
用户 `y` → 进 Step 2。

如果命令行含 `--yes` 则跳过此 prompt。

## Step 2：跑 prepare

```bash
mkdir -p .understand-anything/intermediate .understand-anything/reports
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_ingestor spec-link-prepare \
    --graph .understand-anything/knowledge-graph.json \
    --source-root . \
    --out .understand-anything/intermediate/spec-link-intents.json
```

预期：`prepared N intent(s) from M doc node(s) -> ...`

读 intents.json，获取精确 intent 数 N。

## Step 3：前置面板 2（精确成本 + 再次确认）

向用户展示：

````markdown
### prepare 完成 ✅

- doc 节点数：M
- 抽出 intent 数：N（详见 intents.json）

### 即将进入 judge 阶段
- 派出 **N 个 sonnet subagent**，并发上限 5
- 估算 token：约 50~100K 输出
- 估算耗时：约 ⌈N/5⌉ × 几秒 ≈ X 分钟

### 继续 judge? [y/n]
- `y` → 进入 judge
- `n` → 跳过 judge，直接拿现有 owned 边出报告（**会标注"使用过期数据"**）
````

`--yes` 同样跳过。

## Step 4：派 subagent 判定（并发 5）

对每条 intent 派一个 sonnet 通用 subagent。Prompt 模板：

````
You are a spec-to-code semantic linker.

## Task
Given a spec intent and a list of candidate code nodes, determine which candidates implement the intent. Output strict JSON.

## INPUT

intent_id: {{intent_id}}
intent_title: {{intent_title}}
intent_text: {{intent_text}}

candidates (target_node_id MUST be chosen verbatim from this list — do NOT invent ids):
[
  {"node_id": "<id>", "summary": "<summary>"},
  ...
]

## OUTPUT — strict JSON only, no prose:

{
  "intent_id": "<echo input>",
  "status": "implemented" | "partial" | "not_found" | "error",
  "linked": [
    {"target_node_id": "<node_id from candidates>", "confidence": <0.0..1.0>, "reason": "<1 sentence, language matches intent_text>"}
  ]
}

## Rules
- target_node_id MUST be from the candidates list exactly. Do not invent ids. Do not modify ids.
- status semantics:
  - "implemented": one or more candidates fully implement the intent (confidence ≥ 0.7 for at least one linked entry)
  - "partial": some candidates partially address it, none fully (max confidence in [0.4, 0.7))
  - "not_found": no candidate plausibly implements; linked = [].
- linked may be empty only when status is "not_found" or "error".
- reason: ONE sentence, same language as intent_text (中文 intent → 中文 reason).
- If anything blocks judgment, set status="error" and put diagnostic in reason of a single fake entry — DO NOT crash.
- Return ONLY the JSON object. No code fences, no commentary.
````

每个 subagent 返回严格 JSON。主控解析失败 → 标 `status="error"` 自动兜底。

汇总所有 verdicts 写到：
```bash
.understand-anything/intermediate/spec-link-verdicts.json
```
结构（外层包一层 schema）：
```json
{"schema_version": 1, "generated_at": "<iso>", "verdicts": [...]}
```

## Step 5：跑 finalize

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/pyieidev python3 -m ieidev_ingestor spec-link-finalize \
    --graph .understand-anything/knowledge-graph.json \
    --verdicts .understand-anything/intermediate/spec-link-verdicts.json \
    --source-root . \
    --report-dir .understand-anything/reports
```

预期：`wrote N documents edge(s); report -> .understand-anything/reports/spec-link-<ts>.md`

## Step 6：报告输出

- 读 `.understand-anything/reports/spec-link-<ts>.md`，把"📊 摘要" + "❌ 未发现实现"段打到对话流给用户
- 完整报告留在文件里，用户可后续查看

## 失败处理

| 现象 | 应对 |
|---|---|
| 图谱无 document 节点 | prepare 会报"0 doc node"，提示用户重跑 `/understand --full` 让 UA 把 docs 纳入 |
| prepare 抽出 0 intent | doc 文件存在但无 H2-H4 / 无 FR 表 → 检查 doc 结构，可能要补 heading |
| subagent 返回非 JSON | 主控标 `status="error"`，finalize 跳过；报告里列出 |
| git 不可用（漂移段跳过） | 报告标"git 不可用"，其他维度正常 |
| 用户在面板 2 选 n | 跳过 judge，仍跑 finalize（用现有 verdicts.json 若存在；否则只重渲报告） |

## 不要做

- ❌ 不要绕过两次前置面板（除非 `--yes`），否则用户被意外烧钱
- ❌ subagent prompt 里的 candidates 列表里的 node_id 不能改、不能创造
- ❌ 不要在 LLM 判定阶段读源码——所有信息已经在 candidates summary 里；要更深需求请走"重跑 build 让 UA 给更好的摘要"
- ❌ 不要重做漂移逻辑——直接用 finalize 提供的"未发现实现 + 漂移 + 缺文档"三段
