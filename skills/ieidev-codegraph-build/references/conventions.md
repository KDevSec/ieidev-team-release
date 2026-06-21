# codegraph 图谱命名约定（节点 ID + tag）

> 单一权威来源。trace / impact / spec-link / build 4 个 skill 引用本文件（每个 skill 的 `references/conventions.md` 保持同步）。
> 修改前先看 `pyieidev/ieidev_ingestor/ieidev_ingestor/tags.py` 和 `graph_io.py`（**源码是真的真相**）。

---

## 节点 ID 模式

| Kind | ID 模式 | 示例 |
|---|---|---|
| 文件 | `file:<relative_path>` | `file:app/web/api.py` |
| 函数 | `function:<relative_path>:<name>` | `function:app/web/api.py:execute_command` |
| 类 | `class:<relative_path>:<name>` | `class:app/models/user.py:User` |
| 文档 | `document:<relative_path>` | `document:docs/auth-spec.md` |
| 安全规则 | `kdev-sec:rule:<rule_id>` | `kdev-sec:rule:3.1.1` |
| 漏洞 | `kdev-sec:vuln:<slug>` | `kdev-sec:vuln:sql-injection` |

**前缀规则**：本插件自定义节点统一用 `kdev-sec:` 前缀（与 ingestor 灌注代码契约一致，**不可改名**，否则破坏与 Understand-Anything 图谱及 ingestor 的契约），避免与 UA 内置节点 ID 冲突。UA 内置节点（file / function / class / document 等）沿用 UA 的 `<type>:<path>` 模式。

---

## UA 节点 type 白名单（21 种）

来源：`pyieidev/ieidev_ingestor/ieidev_ingestor/graph_io.py:UA_NODE_TYPES`（pinned by contract test）。

### 代码结构
| type | 含义 |
|---|---|
| `file` | 源码文件 |
| `function` | 函数 / 方法 |
| `class` | 类定义 |
| `module` | 包 / 模块 |

### 概念 / 配置 / 文档
| type | 含义 |
|---|---|
| `concept` | 抽象概念（安全规则节点用此 type） |
| `config` | 配置文件或配置项 |
| `document` | 文档文件（PRD / spec / markdown） |

### 服务 / 数据
| type | 含义 |
|---|---|
| `service` | 外部服务 / 微服务 |
| `table` | 数据库表 |
| `endpoint` | HTTP 接口端点 |
| `pipeline` | 数据处理管道 |
| `schema` | 数据 schema |
| `resource` | 云资源 / 基础设施资源 |

### 业务领域
| type | 含义 |
|---|---|
| `domain` | 业务领域 |
| `flow` | 业务流程 |
| `step` | 流程步骤 |

### 知识 / Wiki
| type | 含义 |
|---|---|
| `article` | 知识文章 |
| `entity` | 知识实体 |
| `topic` | 主题 |
| `claim` | 声明 / 断言 |
| `source` | 知识来源 |

---

## UA 边 type 白名单（35 种）

来源：`pyieidev/ieidev_ingestor/ieidev_ingestor/graph_io.py:UA_EDGE_TYPES`（pinned by contract test）。

### 代码结构关系
| type | 含义 |
|---|---|
| `imports` | 导入依赖 |
| `exports` | 导出声明 |
| `contains` | 包含关系（模块→文件，文件→函数） |
| `inherits` | 继承 |
| `implements` | 接口实现 |
| `calls` | 函数调用 |
| `subscribes` | 事件订阅 |
| `publishes` | 事件发布 |
| `middleware` | 中间件链 |

### 数据 / IO 关系
| type | 含义 |
|---|---|
| `reads_from` | 读取数据来源 |
| `writes_to` | 写入数据目标 |
| `transforms` | 数据转换 |
| `validates` | 数据校验 |

### 依赖 / 测试 / 配置
| type | 含义 |
|---|---|
| `depends_on` | 通用依赖 |
| `tested_by` | 被测试覆盖（指向测试节点） |
| `configures` | 配置关系 |

### 语义 / 关联
| type | 含义 |
|---|---|
| `related` | 通用语义关联 |
| `similar_to` | 相似 |

### 部署 / 基础设施
| type | 含义 |
|---|---|
| `deploys` | 部署关系 |
| `serves` | 服务提供 |
| `provisions` | 资源供给 |
| `triggers` | 触发 |
| `migrates` | 数据迁移 |
| `routes` | 路由 |

### 文档 / Schema
| type | 含义 |
|---|---|
| `documents` | 文档对代码的覆盖关系（spec-link 写：direction=backward，weight=LLM confidence） |
| `defines_schema` | Schema 定义 |

### 流程
| type | 含义 |
|---|---|
| `contains_flow` | 包含业务流程 |
| `flow_step` | 流程步骤关系 |
| `cross_domain` | 跨业务域关联 |

### 知识引用
| type | 含义 |
|---|---|
| `cites` | 引用来源 |
| `contradicts` | 矛盾 / 反驳 |
| `builds_on` | 基于 / 扩展 |
| `exemplifies` | 举例说明 |
| `categorized_under` | 分类归属 |
| `authored_by` | 作者关系 |

---

## tag 命名约定

> ⚠️ tag 命名空间为 `kdev:`——这是 ingestor 灌注代码与 UA 图谱之间的**内容契约标识符**，**不可改名**（P1 port 时已确认保留）。

### 格式

- `kdev:<kind>` —— 仅类型（kind-only）
- `kdev:<kind>:<value>` —— 类型 + 值
- kind 字符集：`[a-z][a-z0-9_]*`（详见 `tags.py:_KIND_RE`）
- value 字符集：`[a-z0-9_.\-]+`（详见 `tags.py:_VALUE_RE`）
- 多值用多个 tag（不要在 value 里塞逗号 / 分号）

### 现有 kind 表

来源：`pyieidev/ieidev_ingestor/ieidev_ingestor/tags.py` 常量 + `security_rules.py:rule_to_node` 实际调用。

| kind | 带 value？ | 含义 | 示例 tag | 来源文件 |
|---|---|---|---|---|
| `security_rule` | 否（kind-only） | 标记节点为安全规则 | `kdev:security_rule` | `tags.py:KIND_SECURITY_RULE` |
| `vulnerability` | 否（kind-only） | 标记节点为漏洞 | `kdev:vulnerability` | `tags.py:KIND_VULNERABILITY` |
| `compliance` | 否（kind-only） | 标记节点为合规要求 | `kdev:compliance` | `tags.py:KIND_COMPLIANCE` |
| `rule_id` | 是 | 规则编号（dot 分隔） | `kdev:rule_id:3.1.1` | `security_rules.py:rule_to_node` |
| `category` | 是 | 规则所属分类（来自文件名 slug） | `kdev:category:input_validation` | `security_rules.py:rule_to_node` |
| `source` | 是 | 规则来源插件 / 数据源 | `kdev:source:kdev-secure-coding` | `security_rules.py:rule_to_node` |
| `severity` | 是 | 严重度（high / medium / low） | `kdev:severity:high` | `codegraph-impact/SKILL.md`（impact 查询用） |

**注 1**：`kdev:source:kdev-secure-coding` 中的 value `kdev-secure-coding` 是 ingestor 灌注代码写死的**来源标识字面值**，描述规则数据的源头来历，**不随插件改名而改**（破坏 list-tags 核对断言与下游查询）。本插件内对应的安全规范 skill 现名为 `ieidev-team:ieidev-secure-coding`，其 references 目录即灌注源（见 build skill Step 3 的 `--rules-dir`）。
**注 2**：`severity` tag 在 impact skill 的严重度规则中被引用（`kdev:severity:high` / `kdev:severity:medium`），但当前 `security_rules.py` 不自动注入——需要在灌入时手动或扩展 ingestor 添加。`rule_id` / `category` / `source` 由 `rule_to_node` 自动注入。

### 新增 kind 流程

1. 在 `tags.py` 加常量（如 `KIND_CWE = "cwe"`）
2. 验证字符集：kind 必须匹配 `[a-z][a-z0-9_]*`，value 必须匹配 `[a-z0-9_.\-]+`
3. 更新本文件"现有 kind 表"，补充 kind / 含义 / 示例 / 带 value？/ 来源文件
4. 跑 `pyieidev/ieidev_ingestor/tests/test_tags.py` 确认 `make_tag` / `parse_tag` / `has_kind` 通过

---

## 节点 ID 编码约定

本插件自有节点统一使用 `kdev-sec:` 前缀以避免与 UA 内置节点 ID 冲突（前缀是 ingestor 契约字面值，**不可改名**）。

| 前缀 | 含义 | ID 示例 |
|---|---|---|
| `kdev-sec:rule:` | secure-coding 安全规则节点 | `kdev-sec:rule:3.1.1` |
| `kdev-sec:vuln:` | 漏洞实例节点（尚未自动注入） | `kdev-sec:vuln:sql-injection` |

`<rule_id>` 来自 markdown heading 编号（如 `3.1.1`），由 `security_rules.py:_RULE_HEADING_RE` 解析。

---

## 必填字段（来自 `graph_io.py`）

### 节点必填字段（`REQUIRED_NODE_FIELDS`）

| 字段 | 类型 | 约束 |
|---|---|---|
| `id` | string | 唯一，遵守节点 ID 模式 |
| `type` | string | 必须在 UA_NODE_TYPES 白名单内 |
| `name` | string | 人类可读名称 |
| `summary` | string | 简短摘要 |
| `tags` | list[string] | 可含 kdev tag，格式见上 |
| `complexity` | string | `simple` / `moderate` / `complex` 三选一 |

### 边必填字段（`REQUIRED_EDGE_FIELDS`）

| 字段 | 类型 | 约束 |
|---|---|---|
| `source` | string | 必须是已存在的节点 ID |
| `target` | string | 必须是已存在的节点 ID |
| `type` | string | 必须在 UA_EDGE_TYPES 白名单内 |
| `direction` | string | `forward` / `backward` / `bidirectional` 三选一 |
| `weight` | float | `[0, 1]` 闭区间 |

---

## 维护

- 修改本文件**必须**同步修改 `tags.py` / `graph_io.py` 的常量或正则（源码是真相），并同步 4 个 skill 各自的 `references/conventions.md` 副本。
- contract test（`pyieidev/ieidev_ingestor/tests/` 下 UA 兼容测试）守护 UA 白名单变化——CI 失败意味着 UA 上游 schema 变动，需重新核对本文件。
- 新增节点 ID 前缀须在"节点 ID 编码约定"章节登记，并在对应 SKILL.md 的节点 ID 表中补充一行。
