# markdown 切片导出（蒸馏管道）

## 什么时候读本文件

- 用户说"导出蒸馏数据 / export-md / 知识蒸馏 / 把记录弄出来训练 / 训练数据"
- 准备实现 `/ieidev-team:memory-distill` 命令
- 想理解为什么 ieidev-memory 不引入 JSONL 中间格式
- 设计 sanitize 规则

## 核心决策：不引入 JSONL

**主存 = markdown，导出 = markdown 切片包，不走 JSONL。**

这是 **终态决策**，不留升级口。

### 为什么不用 JSONL

| 反对理由 | 详细 |
|---|---|
| 现代蒸馏管道直接吃 markdown | Axolotl / Unsloth / HuggingFace SFT trainer / 等都原生支持 markdown / text 输入 |
| 维护成本 | 多一层 markdown → JSONL → 训练 = 多一个 export 脚本 + schema 漂移检测 + 字段映射文档 |
| 序列化转义噩梦 | verbatim 字段含中文引号 / emoji / 换行 / 反斜杠，JSON 转义后人眼几乎不可读 |
| **叙事丢失（最关键）** | markdown body 的"带因果链 reasoning trace"塞 JSONL 字段会被切碎，丢失蒸馏价值最高的部分 |
| git diff 友好 | JSONL 改一个字段，整行 diff 显示，PR review 体验差 |
| schema 演化 | markdown 字段缺失能容忍；JSON 字段缺失会触发 parse error |

### 为什么 markdown 才是顶级蒸馏样本

`执行日志.md` 里的 Step 条目天然包含**带因果链的自由叙事**。例如评分差异分析段：

> 这次顺畅度 5/5 是因为前次 G-007 已经把双适配的坑记录过了，所以这次开工前我先 Read 了那条，绕过了同样的判断分支。说明 hook 的 trigger 召回这次起作用了——也就是说 ieidev-memory 召回路径走通了一次完整闭环。

这种"上下文 → 决策 → 行为 → 验证"的因果链是蒸馏价值最高的 reasoning trace。

JSONL 拆字段后只剩 `{score: 5, reason: "前次记录帮了"}` —— 丢失了完整逻辑链和具体细节。

## 三个切片包

`/ieidev-team:memory-distill` 命令产出三个独立的 markdown 文件（输出位置：`.ieidev/memory/dataset/`），每个 **self-contained**（便于外部消费 / 分享 / 上传）：

### 1. `dataset-full.md`

**内容**：全量条目按时间排，含 Step + Q + G + F + R，sanitize 后原样拼接。

**用途**：
- 通用语料 / 项目知识图谱 / RAG knowledge base
- 给智能体"读完一个项目的完整故事"

**生成规则**：
- 按日期升序排列（同日按编号）
- 不同类型之间不分组，按时间线交织（这就是真实工作流的形态）
- 每条前面加一个 H3 标记 `### [来源：执行日志.md]` 或 `### [来源：skill-feedback.md]` 之类

### 2. `dataset-misalignment.md`

**内容**：只含**差值 ≥ 1.5 的 Step**——模型自评 vs 用户真实评分的 gap。

**用途**：**顶级对齐数据**。这种"模型觉得 5 用户觉得 3"的样本带有**真实 ground-truth 评分**，外面买不到。用于：
- 训练 reward model
- DPO 偏好对（用户分高的为 chosen，模型自评不准的为 rejected）
- 修正模型自我评估偏差

**筛选条件**：
- Step 的"评分差异分析段"含 `差值 ≥ 1.5`（绝对值）
- 双评分段完整（模型自评 + 用户评分都有时分戳，未污染）
- subject = project（避免和 skill 反馈污染——skill 引起的差值另算）

**输出格式**：每条 Step 完整原文，含执行事实段 + 双评分 + 评分差异分析。

### 3. `dataset-skill-feedback-by-subject/<slug>.md`

**内容**：F-NNN 按 subject 切片，每 subject 一个独立 markdown。

**文件命名**（slug 是 subject 的安全化版本）：
- `dataset-skill-feedback-by-subject/plugin-ieidev-memory.md`
- `dataset-skill-feedback-by-subject/skill-brainstorming.md`
- `dataset-skill-feedback-by-subject/methodology-TDD.md`
- `dataset-skill-feedback-by-subject/tool-bash.md`
- `dataset-skill-feedback-by-subject/unknown.md`（一般跳过——见下方"unknown 过滤"）

**用途**：**每个 subject 的"未来 skill 自主优化训练集"**——用 plugin:ieidev-memory 的 F 条目训出"如何让 ieidev-memory 改进"的指令微调样本。

**筛选规则**：
- 只导出 `subject_confidence: high` 的（medium / low 进抽检池单独导出）
- 跳过 `subject: unknown`
- 跳过 `verbatim` 为空的（违反铁规 2，数据废条）

## sanitize 必做

导出前必须 sanitize：

| 类型 | 处理 |
|---|---|
| email（`*@*.*` 模式） | 替换为 `<email>` |
| 内部路径（含 home 目录用户名 `/home/<user>/` 等） | 替换 `/home/<user>/` 为 `<home>/`；保留相对路径 |
| API key / token / secret 模式（含 `sk-`、`ghp_`、`AKIA`、`Bearer` 等前缀） | 替换为 `<redacted>` |
| 内部 URL（含 `localhost` / `127.0.0.1` / `*.internal` / `*.local` / 私有域名） | 替换为 `<internal-url>` |
| 公网 URL（github / npm / 公开域名等） | 保留 |
| IP 地址（私网段 10.* / 172.16-31.* / 192.168.*） | 替换为 `<private-ip>` |
| 公网 IP | 保留 |

具体正则和白名单等首批数据出来后再定（未决问题之一）。

**导出时必须 sanitize 验证**：导出脚本完成后再扫一遍输出文件，确保没有漏脱。

## 实现路径

复用现有 `hooks/lib/weekly.py` 的 `parse_entries` 函数解析 markdown，按筛选条件 filter，按编号或时间排序，sanitize 后写入三个目标文件。

### 伪代码骨架

```python
def export_markdown_slices(ieidev_dir: Path, out_dir: Path):
    steps = parse_entries(ieidev_dir / "执行日志.md", r"^##\s+Step\s+\S+")
    qs    = parse_entries(ieidev_dir / "决策日志.md", r"^##\s+Q-\d+")
    gs    = parse_entries(ieidev_dir / "踩坑日志.md", r"^##\s+G-\d+")
    fs    = parse_entries(ieidev_dir / "skill-feedback.md", r"^##\s+F-\d+")
    rs    = parse_entries(ieidev_dir / "改进建议.md", r"^##\s+R-\d+")

    # 含归档
    for archived in (ieidev_dir / "归档").glob("*.md"):
        ...

    # dataset-full.md（按日期升序交织）
    all_entries = sorted(steps + qs + gs + fs + rs, key=lambda e: e["date"])
    write_full(out_dir / "dataset-full.md", all_entries)

    # dataset-misalignment.md
    misalign = [s for s in steps
                if abs(diff_score(s["body"]) or 0) >= 1.5
                and not is_voided(s)
                and step_subject(s) == "project"]
    write_misalignment(out_dir / "dataset-misalignment.md", misalign)

    # dataset-skill-feedback-by-subject/<slug>.md
    high_conf_fs = [f for f in fs
                    if f["subject_confidence"] == "high"
                    and f["subject"] != "unknown"
                    and f["verbatim"]]
    by_subject = group_by_subject(high_conf_fs)
    for subject, entries in by_subject.items():
        slug = slugify(subject)  # plugin:ieidev-memory -> plugin-ieidev-memory
        write_skill_feedback(out_dir / "dataset-skill-feedback-by-subject" / f"{slug}.md", entries)

    # sanitize 整个 out_dir
    sanitize_recursive(out_dir)

    # 验证 sanitize 完整
    verify_no_leaks(out_dir)

    return {
        "files_written": [...],
        "stats": {
            "full_entries": len(all_entries),
            "misalignment_entries": len(misalign),
            "by_subject": {s: len(es) for s, es in by_subject.items()},
        },
        "sanitize_status": "verified" | "leaks_found",
    }
```

## 不要做的事

- ❌ 不要把切片包写回 `.ieidev/memory/` 根目录（导出是只读消费动作，输出到 `.ieidev/memory/dataset/` 子目录隔离）
- ❌ 不要修改原 markdown 条目（导出脚本只读）
- ❌ 不要为蒸馏方便而把 markdown 转 JSONL（终态决策，违反此条 = 违反 SKILL.md 顶部架构原则）
- ❌ 不要在切片包里改写 verbatim 字段（违反 F-NNN 铁规 2）
- ❌ 不要 sanitize 影响 verbatim 字段的核心吐槽内容（只脱敏 PII，不要改原话情绪）

## subagent 化建议（决策 4 落地）

markdown 切片导出是**大单次操作**（解析全量文件 + 写多个切片包 + sanitize），适合走 subagent：

- `hybrid` 模式：调 subagent 同步等返回，主会话拿到`{files_written, stats, sanitize_status}` 摘要后继续
- `inline` 模式：主会话同步内联

详见 `references/subagent-落盘机制.md`。

## 用户视角的体验

| 用户说 | skill 动作 |
|---|---|
| "导出蒸馏数据 / export-md" | 走 `/ieidev-team:memory-distill`，产出 3 类切片包 |
| "把 ieidev-memory 的反馈导出来" | 只生成 `dataset-skill-feedback-by-subject/plugin-ieidev-memory.md` |
| "导出对齐数据 / misalignment" | 只生成 `dataset-misalignment.md` |
| "全量导出 / 把所有的弄出来" | 三类都生成 |

完成后向用户报告：
- 产出几个文件 / 文件路径
- 每类多少条目
- sanitize 是否通过

## 未决问题（首批数据出来后再定）

1. sanitize 规则细节：脱敏 email / 内部路径 / API key / 内部 URL / 私网 IP 的具体正则和白名单
2. medium 置信度 F 条目的导出策略（单独 抽检池 还是混入主切片）
3. 一个 verbatim 引用了另一个用户的对话（嵌套引用）时如何脱敏
4. 是否同时输出每个切片包的 `.metadata.json`（条目数 / sanitize 统计 / 生成时间）便于消费方校验
5. 多项目聚合切片（合并多个 .ieidev/memory/ 目录的 F-NNN）何时启用
