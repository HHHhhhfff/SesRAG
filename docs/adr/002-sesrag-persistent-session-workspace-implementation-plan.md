# ADR-002：SesRAG 持久化会话与对话工作台实施方案

**编号**：002

**状态**：已实施（原两轮104例及本次最终108例均有完整证据；小缺陷001～004已处理，005未定义）。

**版本**：v0.2

**日期**：2026-10-20；当前编号/导航/最小修复及验收状态更新：2026-10-24。

**对应项目开发版本**：`sesrag_v0.2` / `v0.2`

**适用范围**：在第一轮 Demo 和 ADR-001基础缺陷修复基线上实施 v0.2 持久化会话、分支对话、可恢复流式运行、多模型选择、上下文预算和对话工作台。

**依据**：[`docs/prd/002-SesRAG-持久化会话与对话工作台-PRD.md`](../prd/002-SesRAG-持久化会话与对话工作台-PRD.md)

**关联基线**：[`001 Demo PRD`](../prd/001-SesRAG-项目Demo-PRD.md)、[`ADR-001 Demo 实施方案`](001-sesrag-demo-implementation-plan.md)、[`ADR-001 缺陷修复方案`](001-SesRAG-Demo-缺陷修复-plan.md)、[`CONTEXT.md`](../../CONTEXT.md)、[`接口文档`](../接口文档.md)。

**实施结果**：功能实现和分类/质量门禁证据见[PR-002](../pr/002-SesRAG-持久化会话与对话工作台-PR.md)。 原验收与补充发现见[测试报告](../../tests/sesrag-persistent-session-workspace-test/测试报告.md)；2026-10-24最小修复、工程问题处理及最终108例通过/清理见[修复验收报告](../../tests/sesrag-persistent-session-workspace-test/小缺陷修复与回归验收报告.md)。

**取代关系**：本ADR在Demo及ADR-001基础缺陷修复上扩展v0.2；不取代原Demo历史记录。此前正文自称ADR-003是编号残留，当前统一为ADR-002。

**本版修订**：在 v0.1 原有方案基础上，明确 §6 的接口新增/修改/保留清单、v1/v2 契约及调用方处置策略，并同步文件清单、实施路线和验证门禁；不改变产品范围，不表示相关 API 已实施。 2026-10-24校准编号002、当前验收入口及结果来源；设计阶段的原预计与旧专项不能充当本轮正式证据。

### 2026-10-24 小缺陷修复决策（WS-DEF-001～004）

本次是既有需求的最小补齐，原功能范围与接口契约不变。工作台侧栏增加“普通会话／已归档”两个互斥视图；复用 `include_archived=true` 返回的摘要事实与全量排序游标，在 store 按 `archived_at` 过滤当前已加载集合，**不新增归档 API、不把服务端 include_archived 误解为只查归档**。两个视图共享分页进度；空视图但 `has_more=true` 时明确提示继续加载，不能宣布服务端没有此类会话。归档/取消归档后切到目标视图并保留当前 Thread/Branch；有效归档偏好恢复归档只读视图，无效/无偏好回普通视图，新建回普通视图。切视图使旧选择和迟到分页失效，保留既有 epoch 隔离。

修复文件为 `frontend/src/stores/thread.ts`、`components/ThreadList.vue`、`pages/WorkspacePage.vue` 和侧栏样式；先以 `frontend/tests/thread-store.test.ts` 建立失败回归，再补本轮 Playwright 用例/矩阵/manifest。应用 OpenAPI 版本从已安装 `sesrag` 包元数据读取，单一源是 `pyproject.toml`；轻量 API 测试验证前后端发布版本一致。文档编号/当前验收导航原地校准；安全扫描日志改称包含 artifact、Git 和 dist 的合计扫描次数，不改历史原始证据或扫描断言。

实施路线：失败断言 → 最小代码/导航修复 → 本机单元、类型、Lint、构建和测试工程门禁 → 规范及需求双轴校审 → 当前源码新建镜像执行一轮 All（含故障清理）→ 回填真实结果与修复验收记录。原报告未定义 WS-DEF-005；本次不擅自将弃用警告等其他事项编号为第五缺陷，交付明确列为未有定义。

## 1. 决策摘要

本方案采用“持久事实 + 派生投影 + 版本化快照”的路线：PostgreSQL 继续保存 Thread、Branch、Message、Run、Task、RunEvent、ModelProfile 和上下文计划的事实/元数据；SSE、Redis 和 Vue 状态只作为事件投影，不能宣布终态。Branch 用父分支和分叉消息表达路径，不复制祖先 Message；用户主动重试/重新生成创建新的 Run 和必要的子 Branch，自动 Task 重试仍属于原 Run。

本轮新增 `/api/v2` 会话接口及 v2 契约，承载 Branch、模型选择、上下文摘要、显式重试和重新生成；v1 会话兼容范围由 Thread 的 `conversation_version` 限定，具体见 §6.1。文档上传、索引和健康接口继续复用现有协议。两个 API 版本共用应用服务与 PostgreSQL 事实，不建设绕过 Thread/Message/Run 的平行聊天系统。所有跨前后端字段先更新 `contracts/` 和 `docs/接口文档.md`，再生成前端类型。

实施顺序为：先建立数据与契约边界，再完成 Branch 和 Profile/快照基础，随后接入上下文、可恢复流式 Run 和取消/重试/重新生成，最后完成工作台、迁移兼容、Compose 和回归验收。任何新能力不能通过前端临时状态或重新提交一条相同用户消息来伪造持久化恢复。

方案比较：不采用“复制完整消息历史作为分支”，因为重复事实容易与重生成结果冲突；不采用“仅在浏览器保存分支和草稿”，因为无法满足刷新和重启恢复。采用父分支/分叉锚点、不可变消息、逐尝试 ContextPlan 和持久事件，在现有 PostgreSQL/Worker 架构中实现。

## 2. 目标、边界与可预估结果

### 2.1 本方案必须实现的结果

1. 同一 Thread 可拥有默认 Branch 和多个子 Branch；祖先消息只保存一次，分支读取能得到正确的共同前缀和本分支后续。
2. 后续 Run 使用当前 Branch 的持久历史，并生成可审计的 ContextPlan；上下文裁剪、摘要、预算超限和来源范围可解释。
3. 服务端提供多个安全 ModelProfile，创建 Run 时冻结模型和执行配置；真实凭据不进入数据库公开字段、事件、日志或浏览器。
4. 增量回答和关键状态先追加 Event Journal，再由 SSE/前端投影；刷新、断线、API/Worker 重启和租约回收可恢复同一 Run 的观察或继续执行。
5. 用户中断、自动重试、显式重试和重新生成语义清楚且互不混淆；旧答案、失败记录和事件保持可追溯。
6. Markdown 消息安全渲染，现有文本 RAG 的 Evidence/Citation 绑定当前 Run，切换 Thread/Branch 不串流、不串引用。
7. 旧 Demo 数据经可重复 Alembic 迁移升级；无法安全解释的旧快照或冲突事实进入明确失败/人工处理路径，不静默猜测或删除。

### 2.2 本轮不实施

- 完整项目 PRD 的 PRD1 生产级多租户调度、优先级/配额/背压/死信、Queue 替换。
- 工具 Registry、工具执行、Shell/代码执行、人工审批、`waiting_input` Checkpoint、Tool Audit 和隐藏思维链展示。
- 跨 Thread 的语义记忆、用户画像、自动事实抽取、Thread 物理删除和数据保留策略。
- 文档 `DocumentVersion` 审核/发布、独立本地目录知识库、混合检索、Rerank、真实模型质量和生产 SLO。
- Electron、移动端、生产认证、RBAC、跨用户共享。

### 2.3 实施完成后的预期产品形态

用户在工作台选择 Thread/Branch 和 ModelProfile，提交问题后获得一个可恢复 Run。页面显示持久事件时间线和 Markdown 增量；完成后读取服务端最终 Message。用户可以取消运行、重试失败/取消 Run、重新生成成功回答或从历史消息创建 Branch；所有操作均可在服务端按 Thread/Branch/Run 关系追溯。

## 3. 现有基线和关键兼容约束

### 3.1 当前代码已提供的能力

- `ThreadModel`、`MessageModel`、`RunModel`、`TaskModel`、`RunEventModel`、`DocumentModel`、`ChunkModel` 及 PostgreSQL/SQLite 测试模型。
- `create_message_run` 的 Thread 锁、Idempotency-Key、RunSnapshot、主 Task 和初始事件事务。
- `postgres_queue.py` 的 lease、generation、attempt、deadline、重试和旧执行者条件写回。
- `journal.py`、`runs.py` 和前端 `run.ts` 的事件追加、SSE/after_seq 补放、去重、终态事实刷新。
- Mock/OpenAI-compatible Provider、pgvector Evidence/Citation、Markdown DOMPurify 渲染和 Compose 多容器部署。

### 3.2 本轮必须正面处理的差异

1. `MessageModel.run_id` 的现有唯一 assistant 索引继续保留；`RunModel.user_message_id` 去掉唯一约束、补 FK/普通索引，从而允许一个用户输入被多个 Run 引用。不新增同义的 `input_message_id` 或 `run_inputs` 表。
2. 当前 Thread 只有平铺 `seq`，Branch 需要新增路径身份和分叉锚点；不能复制祖先消息或依赖前端数组切片作为事实。
3. 当前单组 `Settings`/`provider_factory` 需扩展为 ModelProfile 注册和安全展示；RunSnapshot 必须含 Profile 版本与上下文策略，但不能含 Key。
4. 当前 Run 状态没有 `cancelling`，取消接口直接结算 cancelled；v2 Run 增加持久取消请求与 Worker 确认边界。旧 Run 保留 schema v1 解码/事件兼容，不重写历史终态。
5. 当前 Run Handler 只把问题和 RAG Evidence 传给 Provider；需加入 Branch 历史、ContextPlan 和有限摘要，并保证自动 Task 重试不拼接跨尝试 delta。
6. 当前前端只恢复最近 Run/Thread 的部分状态；需要恢复所选 Branch、非终态 Run、最后 seq、临时投影和终态事实，并新增模型/分支/重试控制。

## 4. 总体架构与数据流

### 4.1 运行拓扑

```text
Browser/Vue Workspace
  ├─ /api/v2/threads、branches、models、runs、context
  └─ SSE /api/v2/runs/{run_id}/events/stream
            │
            ▼
API（校验、事实写入、只读投影、取消/显式操作）
            │ PostgreSQL 事实事务 + Redis 唤醒
            ▼
Worker Runtime（claim/lease/heartbeat/retry/恢复）
            │
            ├─ Context Builder（Branch history / summary / budget）
            ├─ RAG Adapter（现有文本 Evidence）
            └─ Provider Adapter（ModelProfile 快照，stream）
            │
            ▼
PostgreSQL：Thread / Branch / Message / Run / Snapshot / Context / Task / Event / ModelProfile
```

### 4.2 事实来源和事务边界

- PostgreSQL 是所有会话、分支、模型 Profile 版本、ContextPlan 元数据、Run、Task 和 Event 的事实来源；Redis 只发布唤醒，SSE 只读取 Journal。
- 创建消息 Run：锁定 Thread 和当前 Branch，验证提交锚点，写入用户 Message、Run、RunSnapshot、Task、SessionOperation、`run.created`/`task.queued`，同一事务提交；不在 HTTP 请求中调用 Provider。
- 领取 Run：沿用 `task_id + worker_id + generation`，在租约事务内追加 `task.leased`；Run 自动重试只更新 Task attempt/lease 和 Run retry 状态。
- 成功终态：唯一 assistant Message、Run/Task 终态、`message.completed` 和 `run.succeeded` 在同一事务内提交。失败/取消只提交状态、错误码及对应终态事件，不创建最终 assistant Message；冲突或失租整体回滚。
- 显式重试/重新生成：在新 Run/子 Branch 的创建事务中保存来源关系，不修改旧 Run、旧 assistant Message 或旧 Event Journal。
- ContextPlan：通常在每次已领取尝试中、RAG 召回之后且回答生成之前发布；mandatory 预检失败时直接发布 budget_exceeded 计划，不调用 RAG/模型。记录来源范围、证据身份、裁剪/摘要策略和预算；完整 Prompt 不落库。一个 Run 可有多个不可变尝试计划，详情指向最近计划，旧计划不覆盖。

### 4.3 Port/Adapter 边界

新增 `BranchRepository`、`ConversationContextPort`、`TokenCounter`、`ModelProfilePort` 协议及普通 DTO。应用服务管理事务；纯路径/预算算法只消费 DTO，SQL 查询封装在 Repository，SQLAlchemy Model 不进入 Provider/Context Port。`ModelProvider` 从仅接收 question/evidence 演进为接收 `ModelRequest`（有序 role/content、输出上限、选定 Evidence 身份）；旧调用适配由 schema v1 解码器承担。`EmbeddingPort`、`VectorStorePort`、`QueuePort`/`TaskLease` 保持现有职责。PostgreSQL、Redis、pgvector、OpenAI-compatible HTTP 和 Mock 仍位于 `backend/infrastructure/`，厂商类型不得进入领域 DTO。

## 5. 核心对象设计

### 5.1 对象总表

| 对象 | 类型 | 主要职责 | 身份/边界 |
| --- | --- | --- | --- |
| `Thread` | 已有，扩展 | 长期会话容器、归档、协议代际和更新时间。 | `thread_id` 唯一；`owner_id` 必须匹配当前开发身份；不因归档删除事实。 |
| `Branch` | 新增 | 表示 Thread 内一条可继续对话的路径。 | `branch_id` 唯一；必须属于一个 Thread；默认 Branch 无父 Branch；子 Branch 记录父 Branch 和分叉消息。 |
| `Message` | 已有，扩展 | 保存用户输入和 assistant 最终回答，支持 Branch 路径读取。 | `message_id` 唯一；创建 Branch 的祖先 Message 不复制；`thread_id` 与 Branch Thread 一致；用户消息可关联多个 Run。 |
| `Run` | 已有，扩展 | 一次模型执行和可恢复终态。 | `run_id` 唯一；只属于一个 Thread/Branch 和一个用户 Message；自动重试不新建 Run；用户显式操作可新建关联 Run。 |
| `RunSnapshot` | `runs.snapshot_json` 扩展 | 冻结 ModelProfile、Provider、RAG 和 Context 策略。 | 创建后不可变；只保存非 Secret；缺失/不兼容快照返回 `INVALID_RUN_SNAPSHOT`。 |
| `ModelProfile` | 新增 | 服务端维护可选择模型的安全配置和版本。 | `profile_id + version` 唯一；禁用 Profile 不能用于新 Run，但旧 Snapshot 可按兼容策略恢复。 |
| `ContextPlan` | 新增 | 记录 Run 某次执行尝试实际使用的历史、证据、摘要、裁剪和预算。 | `context_plan_id` 唯一；`task_id + generation` 唯一；发布后只读，不保存完整 Prompt。 |
| `ConversationSummary` | 新增 | 对较早历史的可追溯简易摘要。 | 必须属于一个 Thread/Branch；保存覆盖消息范围和策略版本；不能跨 Branch 复用。 |
| `Task` | 已有，扩展语义 | Worker 队列任务和自动执行尝试。 | `kind=run` 只能关联 Run；attempt/generation 变化不创建新 Run。 |
| `RunEvent` | 已有，扩展类型 | 持久化状态和增量。 | `run_id + seq` 唯一、追加不可更新；事件 payload 不含 Secret/完整 Prompt。 |
| `SessionOperation` | 新增，内部幂等记录 | 保存创建消息/分支、显式重试和重生成的请求指纹及结果身份。 | `thread_id + idempotency_key` 唯一；同键不同请求返回 409，不生成重复事实。 |
| `Citation/Evidence` | 已有 | 当前 Run 实际 RAG 证据及引用。 | 只引用当前 Run 的 Evidence；分支切换不得复用临时引用。 |

### 5.2 主要字段设计

下表 UUID 表示逻辑身份；数据库物理类型沿用现有 `String(36)`，避免同一仓库出现两套 ID 编码。除明确可变的选择/状态字段外，消息正文、来源关系、Snapshot、已发布计划和摘要版本均不可原地覆盖。

#### `threads` 的扩展

保留 owner/title/seq/archived/timestamps，新增 `conversation_version`（1 或 2，旧数据为 1）；v2 创建为 2，旧 Thread 在首次 v2 会话写入时按 §6.1 原子升级（读取/取消旧 Run 不触发升级）。标题修剪首尾空白后为 1～200 字符。归档 Thread 可以读取和取消现有 Run，但创建新消息、分支、重试或重新生成返回 `THREAD_ARCHIVED`（409）；归档不自动取消已有执行。

上述标题非空和修剪约束仅用于新的 v2 创建/显式重命名请求；v2 响应按持久化值原样投影 legacy 标题，包括空字符串和空白字符串。只修改归档等元数据而升级 conversation_version 时也不隐式重命名；响应契约与新写入请求契约分别校验，既有 v1 合法历史不因读取或元数据升级而改写。

#### `branches`

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `branch_id` | UUID PK | 分支稳定身份。 |
| `thread_id` | UUID FK、索引 | 所属 Thread。 |
| `parent_branch_id` | UUID nullable FK | 根分支为空；子分支指向直接父分支。 |
| `fork_message_id` | UUID nullable FK | 分叉位置；根分支为空，子分支必须引用父路径中已存在的 Message。 |
| `name` | 1～80 字符 | 展示名称；省略时服务端生成，修剪后不得为空。 |
| `is_default` | 布尔 | 每个 Thread 恰有一个默认 Branch。 |
| `head_message_id` | nullable FK | 本路径的当前末尾 Message；新子分支初始为 fork Message。 |
| `version` | 非负整数 | 每次末尾推进递增；请求中的 expected_version 只作乐观校验，由服务端分配新值。 |
| `created_at` / `updated_at` | UTC 时间 | 生命周期和最近活动。 |

分支约束：`parent_branch_id`、`fork_message_id` 必须同时为空或同时非空；父 Branch 与 fork Message 的 Thread 必须一致；分叉点必须在父路径，且不能是非终态 Run 的未完成用户输入。父/分叉关系创建后不可改，不提供分支删除接口。默认 Branch 用部分唯一索引保证“至多一个”，创建事务保证“至少一个”。同一分叉点允许多个子 Branch，不对 `(parent_branch_id, fork_message_id)` 建唯一约束；重复请求只按 SessionOperation 幂等键复用结果。跨 owner/Thread 返回 404，非法路径返回 422。

#### `messages` 的扩展

只新增 `branch_id`（创建该消息的 Branch，FK/索引）；保留 `thread_id`、`seq`、`role`、`source`、`content`、`status`、`run_id`、`citations_json`、`created_at`。不新增重复表示路径的 `parent_message_id`，不把摘要创建为 system Message。`seq` 继续是 Thread 全局事实顺序；Branch 展示顺序由祖先路径的截断前缀 + 本分支消息按 seq 计算，路径内 seq 可以不连续。

`Message.run_id` 明确表示“最初创建该 Message 的 Run”：user 指初始 Run，assistant 指唯一产出 Run。执行输入的唯一真源为非唯一的 `Run.user_message_id`，不得从 Message.run_id 推断该输入只能被执行一次。旧指针保持不变，重试/重新生成不创建重复 user Message；新 assistant 必须使用新 message_id。旧 Message 幂等列保留供 v1 读取/写入，v2 创建操作统一记录在 SessionOperation，不双写两套幂等结果。

#### `runs`

保留 `run_id`、`thread_id`、`status`、`snapshot_json`、`assistant_message_id`、`primary_task_id`、`next_event_seq`、`cancel_requested_at`、`last_error_code` 和时间字段；新增或调整：

- `branch_id`：执行所属 Branch。
- `user_message_id`：保留原字段名，去除唯一约束并补 FK/索引；必须指向同 Thread 且位于本 Branch 路径的 user Message。
- `parent_run_id`：显式重试/重新生成的来源 Run，可为空。
- `operation_kind`：`initial`、`user_retry`、`regenerate`、`branch_continue`。
- `context_plan_id`：最近一次已发布计划，可为空；计划本体以 run_id/task_id/generation 追溯全部尝试。
- `model_profile_id`、`model_profile_version`：便于查询，真实执行仍以 Snapshot 为准。
- `execution_schema_version`：旧 Run 为 1，新 v2 Run 为 2；决定快照解码和事件协议，不因 API 读取升级而变化。

同一 Branch 最多一个非终态 Run（包含 cancelling），以 Branch 行锁和 Run 部分唯一索引共同保证。v2 提交新消息需 `expected_version`，v1 按 §6.2.2 在锁内隐式使用默认 Branch；末尾变化返回 `BRANCH_HEAD_CHANGED`，已有活动 Run 返回 `BRANCH_BUSY`，均为 409。不同 Branch 可以并发，Thread 的 seq 仍由短事务锁串行分配。

Snapshot schema 2 固定 owner、branch/输入锚点、选中 Profile 的完整非敏感版本、Prompt/上下文/摘要/TokenCounter 版本及参数、输出预留、检索配置和执行上限。不得仅保存 Profile ID 后在恢复时读取当前可变模型参数。自动重试仍用原 Snapshot；用户显式操作生成新的 Snapshot，并记录 parent_run_id。

实施细化：`retrieval` 明确冻结 `enabled`、`top_k`、`embedding_dimensions`、`embedding_model`、`embedding_provider_kind`、无凭据的 `embedding_base_url` 和 `embedding_config_ref`。Mock模式由创建时的配置决定，不按模型名称猜测；真实Embedding只通过受信alias运行时取凭据。恢复/自动重试不得读取当前Settings覆盖服务地址或模型；切换生成Profile不改变这组检索配置。缺字段或不安全URL的schema2快照明确失败，不猜测默认值。上述字段仅位于服务端快照，公开Run摘要继续只展示安全预算与检索开关/top_k/维数。

#### `model_profiles`

| 字段 | 约束 | 说明 |
| --- | --- | --- |
| `profile_id` | 稳定字符串，复合 PK 第一列 | 公开选择身份，不含 Secret。 |
| `version` | 正整数，复合 PK 第二列 | `profile_id + version` 唯一，模型/预算配置不可原地修改。 |
| `display_name` | 字符串 | 前端安全展示名称。 |
| `provider_kind` | 枚举 | `mock`、`openai_compatible` 等 Adapter 类型。 |
| `model_name` / `generation_params` | 字符串 / 有界 JSON | 生成模型和允许的生成参数，不接收任意上游参数。 |
| `base_url` | 无凭据 URL | 不含用户信息、密码、敏感 query。 |
| `context_window_tokens` / `max_output_tokens` | 正整数 | 上下文预算和输出预留上限。 |
| `status` / `is_default` | `enabled`/`disabled`；布尔 | 可变的选择策略；当前默认必须唯一且 enabled。`invalid` 是运行时配置检查结果，不是第二套配置真源。 |
| `tokenizer_kind` / `tokenizer_version` | 受支持的计数策略 | 与 Provider/模型声明的 Token 语义匹配，未知策略不可提交。 |
| `tokenizer_config` | 有界 JSON | 显式 encoding_name、消息框架开销和校准版本；不是任意可执行 tokenizer 插件。 |
| `config_ref` | 受信环境变量引用 | 仅存 alias，例如 `env:MODEL_API_KEY`，不存 Key 值；请求不能指定任意环境变量名。 |
| `created_at` / `updated_at` | UTC 时间 | 版本审计。 |

本轮固定采用“数据库元数据表 + 显式导入命令 + 运行时 Secret”：迁移种入两个可区分的 Mock Profile（普通和小上下文预算），默认普通 Profile；API/Worker 启动只读表，不自动覆盖配置。`backend.tools.sync_model_profiles` 将受信非 Secret JSON 导入表，相同版本/不同模型配置拒绝导入，变更须增加 version；仅启禁用/默认选择可原地更新，导入事务和默认部分唯一索引保证默认启用项恰有一个。示例 JSON 是导入输入，不是运行时第二真源。服务端提供默认 Profile ID/version；显式选项失效返回 `MODEL_PROFILE_UNAVAILABLE`，不得悄悄换默认；同 Profile 可有多个显式启用版本，前端以 ID/version 成对区分。

已有 Snapshot 不因 Profile 禁用而变化；其非敏感配置仍可恢复，Secret 引用无法解析则永久失败 `MODEL_CREDENTIAL_UNAVAILABLE`。`INVALID_RUN_SNAPSHOT` 只用于快照格式/版本无效。生成模型可以切换，Embedding 和索引空间本轮固定为现有 384 维及同一 Embedding 配置，独立写入 Snapshot 的 retrieval 部分；不得随生成 Profile 切换 Embedding 模型去检索现有索引。改变 Embedding 空间和重建知识库属于后续 ADR。

#### `context_plans` / `conversation_summaries`

`context_plans` 保存 `context_plan_id`、`run_id`、`task_id`、`generation`、`attempt`、`thread_id`、`branch_id`、`anchor_message_id`、有序 `selected_message_ids`、有界 `omitted_message_ids/reasons`、`summary_ids`、`selected_evidence`（document/chunk/batch/location 身份与内容 hash）、`trim_policy_version`、`counter_version`、`estimated_input_tokens`、`reserved_output_tokens`、`safety_margin_tokens`、`context_window_tokens`、`status=ready|budget_exceeded`、`created_at`。候选窗口外的裁剪只保存 Branch 路径范围/数量/原因，不无限罗列全部旧 ID。一个 task/generation 最多一份发布结果，未执行到规划阶段可以没有计划；不得保存完整 Prompt 或不必要的证据原文。

`conversation_summaries` 保存 `summary_id`、`thread_id`、`branch_id`、有序 `covered_message_ids`、展示用 from/to seq、`source_hash`、`source_segments`（实际摘取的字符范围）、`summary_text`、`summary_policy_version`、`source_run_id`、`created_at`。不以 seq 连续区间代替真实路径身份。重建产生新 summary_id，不更新已有版本；复用时校验同 Branch、来源 hash 和策略版本，不能把父 Branch 摘要直接带入子 Branch。

#### `session_operations`

字段为 `operation_id`、`thread_id`、`idempotency_key`、`kind=message|branch|retry|regenerate`、`request_hash`、`result_branch_id/message_id/run_id/task_id`、`created_at`。同 Thread 的 key 唯一，hash 使用规范化的原始请求（含操作类型、目标 Branch/来源 Run、显式 Profile/version、正文和锚点）；未传默认选项记录“未传”标记，不能在重放时按新的默认值算成另一请求。不额外保存请求原文。幂等记录与结果事实原子提交；回滚不留下“处理中”死记录；重复同键同内容返回原结果，异内容返回 `IDEMPOTENCY_CONFLICT`。v2 消息/分支/retry/regenerate 创建要求该头，缺失返回 422；创建 Thread 不强制该头，v1 保持原有可选幂等规则。

### 5.3 关系和身份约束

```text
Thread 1 ──< Branch
Branch 1 ──< Message（祖先通过 parent/fork 逻辑读取，不复制）
Branch 1 ──< Run
Message(user) 1 ──< Run
Run 1 ── 0..N ContextPlan（每次执行代数最多一份）
Branch 1 ──< ConversationSummary
Run 1 ── 1 primary Task（attempt/generation 单调推进，不新增 Task 表行）
Run 1 ──< RunEvent
Run 1 ── 0..1 final assistant Message
Run ──> ModelProfile(profile_id, version) + immutable Snapshot
```

实现时必须用数据库 FK/唯一索引/CHECK 或应用锁保证：

- 所有跨对象 thread_id 一致，owner 校验不能只依赖前端传值；Run 输入可以是祖先 Branch 创建的 Message，但必须在该 Run 的路径内。新 assistant 的 branch_id 必须等于产出它的 Run.branch_id，不能错误要求继承的 user 也有相同创建 Branch。
- 一个 Thread 恰有一个默认 Branch；同分叉点可有多个子分支，幂等只按 SessionOperation 判断。
- 一个 Run 只有一个输入 Message 和至多一个最终 assistant Message；显式新 Run 通过 `parent_run_id` 追溯，不覆盖旧 Run。
- Event `seq` 只在当前 Run 内递增；ContextPlan 和 Summary 只读；Profile 版本不可原地改变。
- `Task` 的租约条件仍为 `task_id + worker_id + generation`；旧 Worker 不能写新 Run 代数或终态。
- 本轮每个 Run 恰有一个 kind=run Task，以 Task.run_id 部分唯一索引及 primary_task_id 一致性检查保证；文档索引 Task 不受该索引影响。应用创建事务在 flush 后补齐互指，不能提交缺主 Task 的 Run。

## 6. API、契约和前端接口方案

### 6.1 版本策略

新增 v2 Schema 并生成独立 TypeScript 类型。HTTP 资源由 `/api/v2` 区分版本，Event envelope 继续显式包含 `schema_version`。这里的“新增 v2”不表示删除 v1 或复制一套业务事实；接口层、事实代际、契约和调用方分别按以下规则处理。

#### 6.1.1 版本维度与对象访问范围

| 版本维度 | 决定的行为 | 不代表什么 |
| --- | --- | --- |
| HTTP 路径 `/api/v1`、`/api/v2` | 选择请求/响应契约、接口可用能力和投影方式。 | 访问 v2 不自动把旧 Run/Event 转成 schema 2。 |
| `Thread.conversation_version` | 选择该 Thread 允许的会话级读写入口；1 可兼容 v1，2 由 v2 管理。 | Alembic 结构升级或 v2 只读请求不推进该值。 |
| `Run.execution_schema_version` | 决定执行快照解码、事件写入协议和 legacy/v2 取消语义；创建后固定。 | Thread 升级、换浏览器或改 Profile 均不改变已有 Run 的执行代际。 |
| Event envelope 的 `schema_version` | 决定单条持久事件的精确校验分支；schema 1 原样保留，schema 2 用新契约。 | 事件名称相同不表示两代 payload 可以互换；不能把 schema 2 改标为 1。 |

本轮对象访问兼容范围固定如下：

| 对象/入口 | 行为 |
| --- | --- |
| 旧 Thread、v1 创建 Thread | `conversation_version=1`，仍可使用 v1 原有会话读写接口；服务端补默认 Branch，但不向 v1 返回新字段。新建 legacy Run 保持 schema 1。 |
| v2 新建 Thread | `conversation_version=2`，由 v2 管理；v1 列表不列出，按 ID 访问返回 409 `API_VERSION_REQUIRED`。 |
| v2 读取旧 Thread | 不改变 conversation_version；归一化读取默认 Branch/历史，旧 Run/Event 保持原执行协议。 |
| v2 首次会话写入旧 Thread | 仅指 PATCH Thread、创建 Branch/消息、retry/regenerate；在 Thread 锁中确认不存在非终态 legacy Run，再将 version 原子推进到 2，并完成同一写操作；有活动旧 Run 返回 409 `LEGACY_RUN_ACTIVE`，先等待或取消旧 Run。请求校验/状态检查失败时整个事务回滚，不留下仅升级 version 的半结果。推进后不可自动降回 1。 |
| 旧 Run 的 GET/Event/SSE/cancel | 即使 Thread 后来升级，仍可按旧 Run ID 使用 v1；校验 execution_schema_version=1。v2 Run 不能交给 v1 投影，返回 `API_VERSION_REQUIRED`，不伪造 cancelling 为其他状态。 |
| v2 读取/取消旧 Run | Run 详情按 v2 包装，标明 legacy；旧 Event 作为 schema 1 分支原样补放，不追加伪造历史。取消按 Run.execution_schema_version 分派：旧 Run 沿用已验收的 legacy 行为，新 schema 2 Run 使用 §7.6。读取和取消均不推进 Thread.conversation_version；旧活动 Run 可以先经 v2 取消，再另行提交会话升级写操作。 |
| Document/索引/Health | 继续使用现有 v1/health 接口，不复制第二套上传索引服务。 |

v1/v2 共享权限、幂等、任务和终态保护代码，只有解码/契约及明确的 legacy 行为有版本适配；工作台切换到 v2 会话接口。兼容不承诺保留旧 v1 同会话多 Run 并发：部署 v0.2 后，仍为 conversation_version=1 的 Thread 使用 v1 提交时，同样先查原有幂等记录，再在默认 Branch 活动 Run 冲突时明确返回 409 `BRANCH_BUSY`，不能让新唯一约束异常泄漏。已为 version=2 的 Thread 则先按会话级入口规则拒绝 v1，不因命中旧幂等键而继续写入。所有版本检查均在 owner 校验之后，不可访问的身份仍返回 404。

兼容适配只承诺 v0.2，后续废弃必须另行明确，不长期扩大 legacy 功能。数据库迁移不等于自动升级 Thread 产品协议，也不改写旧快照；同一 Thread 可以同时保留 schema 1 的历史 Run 和 schema 2 的后续 Run，读取和执行按各自身份分派。

#### 6.1.2 契约文件的保留、新增与替代边界

| 当前/计划契约 | 本轮处置 | 兼容和变更边界 |
| --- | --- | --- |
| `thread_v1.json`、`message_v1.json`、`run_v1.json` | 保留，冻结 v1 公开结构。 | 不塞入 Branch/Profile/Context 字段，不向 v1 RunStatus 增加 cancelling；v1 只输出其允许访问的 legacy 事实。新 v2 对应契约接替新工作台的会话表达，不覆盖或重命名这些文件。 |
| `run_event_v1.json` | 保留，冻结 schema 1 的 envelope 和既有 11 类 type/data 联合。 | 旧 Run 后续事件也按 schema 1 写入；不在此契约新增 schema 2 事件、不重写历史 data、不通过放宽 additionalProperties 掩盖差异。 |
| `api_responses_v1.json` | 保留既有响应包装和错误结构。 | v1 列表仍为原数组，详情/提交/归档/取消/EventList 不加入 v2 字段或分页包装。新增兼容拒绝码通过现有 ErrorResponse 的 code/message 表达，更新接口文档及 route/status 测试矩阵，不需放宽成功契约。请求参数校验 422 继续使用原安全 ValidationErrorResponse；应用层业务错误仍使用 ErrorResponse。 |
| `document_v1.json`、`evidence_v1.json`、`citation_v1.json`、`health_v1.json` | 保留并复用。 | 文档/索引/健康不新增同义 v2 契约；v2 Message/完成事件的 Citation 引用既有契约。citation_v1 的历史联合仅服务旧引用，新生成 Citation 仍必须通过 evidence_v1 的完整身份校验。检索事件的身份 DTO 复用 run_event_v1 中 RetrievalItem 定义，不强行套用包含 filename 的完整 Citation。 |
| `thread_v2.json`、`branch_v2.json`、`message_v2.json`、`run_v2.json` | 新增。 | 明确 Branch、输入复用、来源 Run、cancelling 和安全快照/计划摘要；不以修改 v1 Schema 代替新增版本。v2 读取旧 Run 时按 v2 结构投影并标明 legacy；缺少的 Profile/计划按 Schema 明确为空，不伪造模型选择或 ContextPlan。 |
| `model_profile_v2.json`、`context_plan_v2.json` | 新增。 | 仅公开安全模型选项、预算/策略/范围元数据；不输出 Secret、完整 Prompt 或摘要原文。 |
| `run_event_v2.json` | 新增，作为 v2 HTTP/SSE 的事件联合入口。 | 用显式引用的 schema 1 分支与严格的 schema 2 分支组成互斥联合，以 schema_version 判别。schema 1 分支直接引用 run_event_v1，schema 2 分支定义 §6.3 的新旧事件名称及执行身份；不得接受任意 object、降级改标或按名称猜版本。schema 2 Run 只能产生 schema 2 事件。 |
| `api_responses_v2.json` | 新增。 | 定义 §6.2 的 v2 请求/响应包装、分页和显式操作结果；通用业务错误及请求参数校验 422 结构引用 api_responses_v1 中对应 $defs，不另建不同的错误格式。应用层业务 422 仍引用 ErrorResponse；读取 legacy Run 的 EventList/SSE 使用上述严格事件联合。 |

这里的“保留”指公开契约和既有成功响应语义保留；后端共用 DTO、序列化与校验实现可以重构，但输出必须分别通过所属版本契约。v1 因代际/Branch 排斥增加的明确 409 是本 ADR 批准的行为收紧，不应被包装为成功，也不要求以修改 v1 JSON Schema 的状态枚举来实现。两个版本都按错误来源分派：请求参数类型、必填或字段范围校验产生的 422 使用安全 detail 数组；应用层业务错误使用 code/message，包括 MODEL_PROFILE_REQUIRED、BRANCH_LIMIT_EXCEEDED 等业务 422。同一接口可能返回这两类 422，route/status 动态矩阵必须校验明确的两分支联合，不能只按 HTTP 状态码猜响应结构。

#### 6.1.3 调用方迁移、弃用范围与禁止的适配

| 对象 | 本轮保留/调整 | 本轮不做的处置 |
| --- | --- | --- |
| 服务端 v1 会话路由及 legacy 解码器 | 保留 §6.2.2 的全部 9 个入口，在原路由/服务中补代际校验、默认 Branch 和单活动 Run 适配。 | 不删除、不返回 410、不重定向到 v2，不新增同名 alias；不在 v1 接口开放模型选择、分支、retry/regenerate。 |
| 新工作台会话 client | 新增 api/v2 client，Thread/Run 操作统一切到 v2；旧数据也经 v2 的 legacy 读取/取消分支展示。 | 新工作台停止使用 v1 会话 client，不代表服务端 v1 已废弃；遇到 409/未知版本不自动回落 v1 或再提交相同正文。 |
| 既有前端 `api/threads.ts`、`api/runs.ts` | 保留 v1 签名及调用能力，用于 legacy 回归；新工作台迁走其会话调用。 | 不悄悄把原 v1 client 的路径改成 v2；不把两代字段合并为可选字段堆积的公共类型。 |
| `frontend/src/types/api.ts`、生成器既有调用方式 | 保留 v1 类型产物与导出；新增独立 api-v2.ts。默认 generate/check 覆盖两代产物，保持既有 --check 和 --output 路径参数可用；--output 仍只生成 v1 临时产物，新增显式 --version v2 与 --output 配合生成 v2 临时产物。 | 不手工改生成类型、不覆盖 api.ts 为 v2、不用 TypeScript 断言绕过契约。v2 引用 v1 公共类型时显式 import/别名，避免同名导出冲突；两代漂移哨兵分别校验。 |
| 前端文档 client、共用 HTTP、Event stream 和 Markdown 层 | 文档 client 继续 v1；复用 HTTP/清洗基础设施。Event stream 增加明确版本入口与 schema 判别，保留 v1 回归入口，新工作台使用 v2；消费 schema 1 时按原 task.leased/run.started 边界重建尝试草稿，不要求旧 answer.delta 具备 v2 的 generation 字段。 | 不因为全局 base URL 切换而把 documents 发到不存在的 /api/v2/documents；不让 v1 解析器接收 schema 2，不为兼容前端而回写或补造旧事件字段。 |

本轮**不正式废弃任何已发布的 v1 HTTP 入口或 v1 契约文件**；由 v2 接替的是新工作台的会话调用和新增能力表达。明确不再支持的是“通过 v1 操作 conversation_version=2 的 Thread”“通过 v1 读取/取消 schema 2 Run”以及“同一默认 Branch 并发创建多个活动 Run”。这些情况分别明确拒绝，不能静默降级、丢字段、将 cancelling 映射为 running/cancelled、生成假 Event 或复制新用户消息来兼容。遇到未支持的执行/事件版本必须明确报错，不能套用 schema 1 解码；历史读取也不能因未知版本触发写入。

接口真源仍为 `docs/接口文档.md` 和 `contracts/`，README 只维护导航。任何 v2 API 上线前必须同步后端 Schema、契约 JSON、前端生成类型、接口文档和 API/契约测试。

### 6.2 新增/修改接口

以当前仓库 `backend/api/routes/threads.py`、`runs.py`、`documents.py`、`health.py` 为基线。变更性质按完整的“HTTP 方法 + 路径”判定：§6.2.1 的 15 个 v2 路由均为新增，其中标为“既有能力演进”的条目需要修改/复用已有应用服务；§6.2.2 才是原路径上的兼容修改，不能将其误实现为另一条新增接口。所有保留入口见 §6.2.3，不在本轮直接替换原 URL。

#### 6.2.1 新增的 v2 路由及其与已有能力的对应关系

| 方法 | 新增 v2 路径 | 能力来源/既有接口 | 主要用途与具体演进 |
| --- | --- | --- | --- |
| `GET` | `/api/v2/models` | 全新能力；无对应 v1。 | 返回安全可选择 ModelProfile：id、version、display_name、provider_kind、context/output budget、status/reason，不含 Key/DSN。 |
| `GET` | `/api/v2/threads` | 既有列表能力演进：GET /api/v1/threads。 | 返回 Thread 摘要及默认 Branch/归档状态，支持 include_archived 和基于 updated_at/thread_id 的分页，默认 50、最大 200；可列出 owner 下 version 1/2 Thread，响应按 v2 包装，不改变 v1 数组。 |
| `POST` | `/api/v2/threads` | 既有创建能力演进：POST /api/v1/threads。 | 创建 conversation_version=2 的 Thread，并原子创建默认 Branch；v1 创建仍为 version 1。 |
| `PATCH` | `/api/v2/threads/{thread_id}` | 部分演进：POST /api/v1/threads/{thread_id}/archive；重命名/取消归档为新增能力。 | 修改标题、归档/取消归档；不删除事实。v2 统一用 PATCH 承接归档，不再另增 POST /api/v2/threads/{thread_id}/archive 别名。 |
| `GET` | `/api/v2/threads/{thread_id}` | 既有详情能力演进：GET /api/v1/threads/{thread_id}。 | 以 branch_id（省略取默认）返回路径、Branch version/head、Message 和本页相关 Run 摘要；另返回活动/最近 Run 身份。消息按 before_seq/limit 分页，返回路径游标，不一次加载全部消息/Run。 |
| `GET` | `/api/v2/threads/{thread_id}/branches` | 全新能力；无对应 v1。 | 列出 Branch。 |
| `POST` | `/api/v2/threads/{thread_id}/branches` | 全新能力；无对应 v1。 | 用 parent_branch_id/fork_message_id/名称创建子 Branch；按 Idempotency-Key 复用同次请求。 |
| `POST` | `/api/v2/threads/{thread_id}/messages` | 既有提交能力演进：POST /api/v1/threads/{thread_id}/messages。 | 用 branch_id/content/expected_version/可选 model_profile_id+version 创建用户 Message、Run、Snapshot、Task；ContextPlan 由 Worker 后续生成。operation_kind/parent_run_id 由服务端推导，客户端不得伪造；v1 不增加这些请求字段。 |
| `GET` | `/api/v2/runs/{run_id}` | 既有详情能力演进：GET /api/v1/runs/{run_id}。 | 返回状态、Branch、Snapshot 安全摘要、ContextPlan 摘要、来源 Run 和 Task 状态；legacy 事实按 §6.1 投影。 |
| `GET` | `/api/v2/runs/{run_id}/events` | 既有补放能力演进：GET /api/v1/runs/{run_id}/events。 | 用 after_seq 按 seq 分页补放，返回 next_after_seq/has_more；单页默认 200、最大 1000，SSE 内循环沿同一游标追平。v1 继续原 events 包装，不增加 v2 分页字段。 |
| `GET` | `/api/v2/runs/{run_id}/events/stream` | 既有 SSE 能力演进：GET /api/v1/runs/{run_id}/events/stream。 | SSE，支持 Last-Event-ID，断线不取消；输出 run_event_v2 联合，可补放旧 schema 1 事件。 |
| `POST` | `/api/v2/runs/{run_id}/cancel` | 既有取消能力演进：POST /api/v1/runs/{run_id}/cancel。 | schema 2 Run 对未执行任务直接取消，活动执行先持久化 cancelling；终态幂等返回，详见 §7.6。schema 1 Run 按 §6.1 legacy 取消，响应仍按 v2 取消包装；不升级 Thread。 |
| `POST` | `/api/v2/runs/{run_id}/retry` | 全新显式操作；不是已有 Task 自动重试接口。 | 对失败/取消 Run 创建同输入的新 Run；原路径末尾仍为该输入时复用 Branch，否则另建子 Branch。默认复制原 Profile 版本，显式选定覆盖必须通过启用校验；来源为 schema 1 时按 §7.4 显式选 Profile。 |
| `POST` | `/api/v2/runs/{run_id}/regenerate` | 全新显式操作；无对应 v1。 | 对成功 Run 创建新 Branch/Run 和替代回答，旧回答仍可读；legacy 来源按 §7.4 处理。 |
| `GET` | `/api/v2/runs/{run_id}/context` | 全新能力；无对应 v1。 | 默认最近计划，可用 generation 查询历史；未规划时 200 plan=null/reason=not_planned，指定不存在的代数返回 404；legacy Run 也不伪造历史计划，不返回完整 Prompt。 |

#### 6.2.2 修改并保留原路径的 v1 会话接口

下表均为**已有接口的兼容修改**，不是新增路由。保留原请求字段、成功响应结构和原有幂等头规则；新增的版本/Branch 冲突拒绝行为必须更新接口文档和测试。共同应用服务新增内部版本参数/DTO，不要求旧客户端提交 Branch/Profile。

| 已有方法与路径 | 本轮明确修改内容 | 保留行为 |
| --- | --- | --- |
| POST /api/v1/threads | 创建 version=1 Thread 时同事务补默认 Branch。 | 仍返回 v1 ThreadSummary 和 201，不输出 Branch 字段。 |
| GET /api/v1/threads | 增加 conversation_version=1 过滤，不列出 v2 Thread。 | 保留原列表数组、归档过滤和既有查询方式，不注入 v2 分页参数/包装。 |
| GET /api/v1/threads/{thread_id} | owner 校验后，version=2 返回 409 API_VERSION_REQUIRED；只对 version=1 输出旧平铺历史。 | 保留 v1 ThreadDetail 的 thread/messages/runs，不泄漏 v2 分支后续。 |
| POST /api/v1/threads/{thread_id}/archive | owner 校验后增加 Thread 代际限制；version=2 拒绝。 | 原地保留只归档能力和 200 {thread_id, archived:true}；不改为 PATCH，不承担取消归档。 |
| POST /api/v1/threads/{thread_id}/messages | version=1 时隐式选默认 Branch，先查旧 Message 幂等记录，再校验 busy/归档；新 Run 写 schema 1 并同步 Branch head/version。version=2 返回 API_VERSION_REQUIRED。 | content 请求、可选 Idempotency-Key、首次 201/复用 200 和 MessageRunResponse 保留；不强制 v2 的 expected_version/Profile/SessionOperation。 |
| GET /api/v1/runs/{run_id} | owner 校验后按 execution_schema_version 判断；只允许 schema 1，schema 2 返回 409 API_VERSION_REQUIRED。 | 旧 Run 即使所属 Thread 已升级仍可读取；保持 v1 Run/Task 结构和状态枚举。 |
| GET /api/v1/runs/{run_id}/events | 增加同样的 Run 代际限制，只补放原 schema 1 事件。 | 原 {events:[...]} 和 after_seq 规则保留，不新增 next_after_seq/has_more。 |
| GET /api/v1/runs/{run_id}/events/stream | 在发送 SSE 200 前完成 owner/Run 代际检查；schema 2 返回 409。 | schema 1 原样补放，保留 SSE id/event/data、游标规则、断线不取消及终态空后缀有界关闭。 |
| POST /api/v1/runs/{run_id}/cancel | 按 Run 代际限制访问；schema 1 继续 legacy 结算及终态保护，schema 2 拒绝。 | 旧 Run 不因 Thread 升级而失去取消入口；不输出 cancelling，不把 v2 活动取消硬映射为旧状态。 |

#### 6.2.3 保留原协议、不新增同义 v2 的接口

| 已有方法与路径 | 本轮处置 |
| --- | --- |
| POST /api/v1/documents | 保留文档上传和 document_v1 响应，复用现有索引链路。 |
| GET /api/v1/documents | 保留文档列表和原响应包装。 |
| POST /api/v1/documents/{document_id}/index | 保留显式重建索引和 Task 返回协议。 |
| GET /health/live | 保留原路径和存活响应。 |
| GET /health/ready | 保留原路径、200/503 和 health_v1 响应。 |

这些入口可因共用服务/部署配置变化增加内部回归验证，但本轮不改变公开方法、路径、请求和响应，不复制 /api/v2/documents 或 /api/v2/health。v2 工作台通过原文档 client 调用文档接口。

#### 6.2.4 v2 共同行为和游标兼容

以下创建约定仅适用于 v2，不回溯修改 §6.2.2 的 v1 请求：创建类接口首次返回 201、幂等复用返回 200，结果包含该操作实际产生的 Branch/Message/Run/Task ID，不为只创建 Branch 的响应伪造 Message/Run/Task。仅首次创建 Thread 不强制幂等键；消息/分支/retry/regenerate 必须提供。新消息 Profile 不传时选择服务端默认；retry/regenerate 按 §7.4 复制来源或要求显式选择。传入时 ID/version 必须成对。消息继续限制为 1～20,000 字符；空白输入无效。身份不符返回 404，状态/锚点冲突返回 409，格式/范围错误返回 422；业务错误保持安全 code/message，请求参数校验的 422 保持 §6.1 的安全 detail 数组，业务 422 不改包装。上下文预算失败发生于异步 Run，不把已返回的创建成功响应改成 HTTP 失败。

SSE 的 v1/v2 都保持 Header Last-Event-ID 优先于 query after_seq；无法解析或负数游标归 0。普通 GET /events 的 after_seq 则保持非负整数校验，非法值返回 422。SSE 沿 Run 全局 seq 补放，断线只停止观察；终态且游标之后无事件时有界关闭，不伪造终态事件。v2 仅增加分页/事件联合和新状态支持，不借版本演进改变这些既有恢复语义。

### 6.3 事件类型

以下是 schema 2 新 Run 的事件设计：沿用 `run.created`、`task.queued`、`task.leased`、`run.started`、`retrieval.completed`、`answer.delta`、`task.retry_scheduled`、`message.completed`、`run.succeeded`、`run.failed`、`run.cancelled` 的类型名称，按 v2 payload 校验，并新增：

- `context.planned`：安全的预算、裁剪和摘要范围摘要。
- `context.compacted`：摘要创建/更新的身份和覆盖范围。
- `run.cancelling`：服务端已记录取消请求，尚未宣布终态。
- `run.retry_created`：在新 Run Journal 中保存用户显式重试的来源关系。
- `run.regenerated`：在新 Run Journal 中保存重新生成的新 Branch/来源 Run；不向已经终态的旧 Run 追加事件。

独立 Branch 创建的事实来自 Branch 表和 API 返回，不为它伪造一个 RunEvent。执行相关 v2 Event 的 data 增加 task_id/attempt/generation；初始创建/用户控制事件允许这些字段为空。seq 仍在 Run 内全局递增，不随尝试重置。除 answer.delta 正文及现有必要检索证据身份外，事件只带 ID、状态、计数、范围摘要、错误码和安全展示字段；不带完整 Prompt、摘要全文、API Key、原始凭据或隐藏思维链。`run_event_v2.json` 明确联合 schema 1 历史事件和 schema 2 新事件，旧 Event 不回写升级。

## 7. 关键行为和处理流程

本节新增执行流程面向 execution_schema_version=2 的 Run。schema 1 Run 的创建、自动重试、恢复和取消通过 §6.1 的 legacy 适配共用事实/终态保护服务，不强行增加 Profile、ContextPlan、cancelling 或 schema 2 事件；其显式 retry/regenerate 才按 §7.4 创建新 schema 2 Run。Thread/默认 Branch 的迁移与 head 维护仍覆盖 legacy 数据，不能因保留旧投影而漏写内部关系。

### 7.1 创建 Thread/Branch

1. API 按 owner 校验请求；创建 Thread 和默认 Branch 在同一事务提交。
2. 创建子 Branch 时锁定 Thread/父 Branch，先查 SessionOperation，再校验 fork 位于父路径且不是活动 Run 的未完成输入。记录 parent/fork，初始 head=fork，version=0；同键重放原结果，不同键允许在同位置另建 Branch。
3. 分支读取先解析根到当前 Branch 的父链，再按 fork 锚点截取祖先 Message，追加本 Branch 新消息；不复制 Message，不使用前端缓存作为事实。
4. 重命名/归档/取消归档只改 Thread 展示元数据，不改 Message/Run；旧 Thread 的首次 v2 会话写入还按 §6.1 原子推进 conversation_version。列表按 updated_at 倒序、thread_id 次序稳定排序。默认排除归档，归档列表可打开，取消归档回普通列表；归档写入边界见 §5.2。

### 7.2 创建 Run 和上下文锚点

1. API 先做 owner/输入校验，锁 Thread/Branch；在检查 head/busy/Profile 之前查幂等记录，以保证已成功请求在状态后来变化时仍能重放。
2. 对新请求校验未归档、expected_version、无活动 Run、Profile/version 启用且配置完整；分配 Thread seq，写 user Message、Run、Snapshot、Task、SessionOperation 和初始事件，更新 Branch head/version 后提交。
3. Snapshot 锚点为本次 user Message；后续历史只取该路径到此锚点，排除提交之后新增内容、其他分支后续、其他尝试 delta。ContextPlan 此时为空，不在 API 事务里读取无限历史或调用摘要/模型。
4. Worker 完成召回后按 §7.7 构造 ContextPlan，并在当前有效租约下短事务发布及追加 context.planned；预算失败发布 budget_exceeded 计划并原子结算 failed。计划发布数据库故障回滚本次短事务，由 Task 有界重试，不能撤销已经成功创建的用户消息和 Run。

### 7.3 Worker 执行、流式和恢复

1. Worker 按现有 QueuePort 领取 Task，追加 task.leased，使用 Task -> Run 锁序检查取消/deadline/generation；追加携带尝试身份的 run.started。没有有效租约不得调用下游或发布计划。
2. 从 RunSnapshot 的冻结参数构建 Provider，Secret 按受信 config_ref 在运行期注入，不读取当前 Profile 模型参数；无效快照为 INVALID_RUN_SNAPSHOT，凭据缺失为 MODEL_CREDENTIAL_UNAVAILABLE。
3. 执行 RAG -> ContextPlan -> 回答生成。模型流先经过有界聚合，再将 answer.delta 按当前 task_id/generation 写 Journal，提交后才可被 SSE 观察。每次自动尝试从空答案缓冲开始；已有尝试的事件不删除、不拼入新答案。
4. 取消、失租、deadline、Provider 失败在每个可中断边界检查。取消请求后进入 `cancelling`，只有 Worker/回收器安全确认后写 `cancelled`；失租的旧 Worker 只能得到拒绝，不能追加终态或 assistant。
5. 最终提交按 Task -> Run -> Thread -> Branch 锁序，复查保存的原 lease/deadline/generation/cancel 状态；分配 Thread seq，写唯一 assistant、当前计划所用 Evidence 的 citations、Branch head/version、终态 Event 和状态。最后一次 flush 后、commit 前仍复查原授权时间，不能靠续租复活旧授权。
6. 浏览器刷新/断线只关闭 SSE；客户端按最后 seq 补放。API 重启读取持久 Run/Journal；Worker 重启依赖 lease 回收和同一 RunSnapshot 重新执行未完成 attempt，不承诺 Provider token 级续算。

### 7.4 用户重试、重新生成和分支

- `/retry` 只允许 failed/cancelled Run；来源终态只读，输入复用 user_message_id。若来源 Branch head 仍是该输入且无其他活动 Run，复用 Branch；否则从该输入位置新建子 Branch，避免将新回答追加到不相关后续之后。新 Run 的 operation_kind=user_retry、parent_run_id=旧 Run；不修改原 user Message.run_id。
- `/regenerate` 只允许 succeeded Run；每个不同幂等键的操作都从该输入（包含输入、不包含旧回答）创建独立子 Branch，再创建 operation_kind=regenerate 新 Run。不得因分叉点相同而复用上次已经生成答案的 Branch；旧回答及后续分支保持原样。
- 用户从历史消息创建 Branch 后，后续 `branch_continue` Run 的 ContextPlan 只读取分支锚点以前的共同祖先及本 Branch 内容。
- 自动 Task 重试不调用这些 API、不生成新 Message/Run；只改变 Task attempt/generation 和 Run 的 `retry_waiting/running` 投影。

显式操作默认复制原 Profile 版本及上下文/生成策略作为新 Snapshot（新 Run 刷新自身 ID/锚点），仍须确认该 Profile 可用于新 Run；已禁用或缺少凭据时明确拒绝，允许用户显式选择另一可用 Profile。旧 Run 的自动恢复不受新 Run 启用策略影响。重试/重新生成请求也经过归档/busy/幂等规则，不支持对非终态 Run“再启动一次”。

对没有 Profile 版本的 schema 1 终态 Run，v2 retry/regenerate 必须显式选择可用 Profile；省略时返回 422 MODEL_PROFILE_REQUIRED，UI 给出选择提示。新 Run 使用 schema 2 当前策略并记录来源 legacy Run，不能假装已恢复一个不存在的旧 Profile 版本。

### 7.5 前端状态投影

- `threadStore` 管理 Thread/Branch 选择、分支 epoch 和服务端事实；迟到 HTTP/SSE 回调必须带 `thread_id + branch_id + run_id + epoch`。
- `runStore` 以 run_id + seq 去重（不是以 attempt 重置 seq）；草稿按 task_id + generation 分段。收到 terminal/message.completed 后重新 GET Run/Branch 和事件后缀，以最终 Message 替换当前草稿；failed/cancelled 的部分正文留在运行历史，不能显示为完成回答。
- 浏览器本地只保存所选 Thread/Branch/Run 偏好，启动时由服务端验证；无效则回到非归档 Thread 的默认 Branch。活动 Run 优先于最近终态 Run。完整刷新丢失草稿时，必须重放该 Run 的已有 Journal 来重建，不能只恢复 last_seq 却跳过其之前的正文；同页短线重连才从内存中已应用的 last_seq 接续。切换时关闭旧流并用 epoch 丢弃迟到回调。
- `modelStore` 读取安全 ModelProfile；提交前校验选择，运行后只显示 Snapshot 摘要和上下文处理提示。
- retry/regenerate 默认不发送全局保存的模型偏好，由服务端复制来源Profile。查看该Run后，用户在模型控件手动切换才构成显式覆盖；legacy来源仍要求选定可用Profile。含糊网络结果的原操作重发继续冻结首次payload/幂等键，不随之后选择变化。
- `MessageTimeline` 保留 Markdown 清洗和 Citation 展开；Branch/重试/重新生成操作只调用正式 API，不在本地复制或拼接事实。

### 7.6 Run/Task 状态、取消与竞态

Run 保留 queued/running/retry_waiting/succeeded/failed/cancelled，新增 cancelling；Task 沿用原状态集合，不增加 cancelling。Task 处于 leased 时，Run 仍可能是 queued，取消必须以 Task 事实判断是否已有执行者，不能只看 Run 展示状态。

| 触发条件 | Run / Task 的结果 | 持久行为 |
| --- | --- | --- |
| 新建 | queued / queued | 同事务写初始事件，不调用模型。 |
| 领取并开始 | running / leased -> running | attempt/generation 按现有领取逻辑推进，run.started 带两者；领取前检查 deadline/cancel。 |
| 可重试故障且仍有次数/时间 | retry_waiting / retry_waiting | 保存稳定错误码、退避和 task.retry_scheduled；下一次仍属同 Run。 |
| 成功 | succeeded / succeeded | 原子提交最终 Message、Branch head 和终态事件。 |
| 不可重试故障、次数耗尽或 deadline | failed / failed | 保存安全错误码，无最终 assistant；deadline 使用现有稳定码，不重排过期任务。 |
| cancel，Task queued/retry_waiting 且无有效执行者 | cancelled / cancelled | 可直接结算，写 cancel_requested_at/run.cancelled，清 lease。 |
| cancel，Task leased/running | cancelling / 保持原活动 Task 状态 | 记录取消请求和 run.cancelling；后续生成/事件/成功写入被拒绝；Worker 的取消确认使用独立路径。 |
| Worker 确认或租约回收器确认已取消 | cancelled / cancelled | 有效执行者用 task_id/worker_id/generation 确认；回收器以 Task 锁、取消标记和到期条件确认；清 lease 并写唯一 run.cancelled。 |
| 终态后重复 cancel/迟到成功 | 原终态不变 | 重复 cancel 返回事实；迟到执行写入拒绝，不追加冲突事件。 |

取消请求与成功以 Task -> Run 锁和事务先后裁决：成功先提交则取消只读返回 succeeded；取消先提交则成功被拒绝。已持久 cancelling 优先于随后到期/故障结算，最后归为 cancelled；没有取消请求才按 deadline 失败。Worker 观察取消后关闭流/取消可中断等待、停止续租，并在原有效 lease 内走专用确认事务；已失租则交回收器处理，不能经普通 release 把任务重新排队。Worker 停机/失租不会把取消中的 Run 回排为 running；未能主动确认则等租约回收，UI 保持 cancelling，不能定时伪报终态。外部模型可能在服务端停止读取后仍在计算/计费，本轮保证不再接受其事实写回，不承诺撤销上游计算。

### 7.7 上下文、摘要与 RAG 的确定处理

1. 从 Snapshot 解析固定的计数器、预算和锚点。mandatory_input 为必要系统指令、当前 user 输入与协议开销；以 mandatory_input + 输出预留 + 安全余量对窗口作预检，后续 available_input 公式不再次重复扣除。若预检已超限，发布 budget_exceeded 计划并失败，不调用 Embedding/回答 Provider。
2. 在当前 Branch 的允许路径内，历史只含锚点以前的 user/最终 assistant；不含其他 Run 的 delta。按 Run.user_message_id 组成完整轮次，不能只凭相邻数组下标配对。历史失败/取消的独立输入不纳入完整轮次，原文仍可读，并记录 omitted 原因。若以成功 Run 的 user 为分叉点而排除了旧回答，该未配对输入作为可裁剪的独立历史单元处理，不伪造 assistant；本次输入作为 mandatory 单独出现一次。
3. RAG 继续以当前问题检索现有 owner 知识库。先持久 retrieval.completed，再在预算中选择证据；不同 Thread 仍可能召回同一文档，这不是对话隔离失败。系统指令明确历史、摘要、检索文本均为非可信数据，不能覆盖安全指令。
4. 输入预算公式为 `available_input = context_window - reserved_output - safety_margin`。先移除分数最低的 Evidence（同分按 document_id/chunk_id 稳定排序），再从最旧完整轮次起裁剪；近期优先，不截断当前问题、系统指令或输出预留。记录原始/选用/移除的消息与证据身份和原因。
5. 默认采用 `trim_then_extract_v1` 简易压缩：若发生历史裁剪，将被移除的较早完整轮次按原顺序、每条最多前 128 个 Unicode 字符摘取，带角色标记；按摘要 Token 上限停止添加，记录实际 message_id/字符区间/hash，未摘取部分仍列为裁剪，不能声称已完整总结。算法是确定性的提取摘要，不增加第二次模型调用，也不宣称语义总结质量。摘要与已选原始轮次不得重复覆盖；如加入摘要会超限，继续裁掉更旧轮次，仍不够则放弃摘要、保留确定裁剪结果。也支持显式 `trim_only_v1`；摘要构造失败退回该策略并记录安全原因。
6. 每次输入都重新计数；mandatory 仍无法放入时为 CONTEXT_TOO_LARGE。发布 ready 计划后才调用回答 Provider。`ConversationSummary` 原文仅在服务端受控上下文内使用；UI/API 只显示影响范围/策略/预算，不提供完整 Prompt 或摘要原文。本轮摘要只生成新版本，不删除源消息；同 Branch 后续 Run 可复用来源/策略完全匹配的摘要。
7. 计数器通过 TokenCounter Port 注入。Mock 使用确定性计数器进行边界测试；真实 OpenAI-compatible Profile 使用显式配置的 `tiktoken` encoding，连同消息框架开销和安全余量计入总预算。未知 encoding/模型 Token 语义不可猜测为字符除四，必须将该 Profile 标为不可用并说明配置原因。真实上游仍报告 context-length 错误时归为 CONTEXT_TOO_LARGE，不静默换模型/扩预算；后续需校准该 Profile 的计数器，不能宣称 tokenizer 对所有兼容服务都准确。
8. ModelRequest 按 system、摘要数据、已选历史、当前输入和本次 Evidence 构造有序消息，adapter 将 reserved_output 映射到受支持的上游输出参数。最终 Citation 只引用该次 ContextPlan 实际送入模型的 Evidence；被预算移除的证据不能仍出现在最终引用中。计划保存证据身份/hash，不要求 Worker 重启复算同一批检索内容；新尝试可以重新检索并发布新计划，历史计划保持可审计。

### 7.8 有界配置、性能与安全展示

| 边界 | 本轮基线与超限行为 |
| --- | --- |
| Branch 图 | 单 Thread 最多 100 个 Branch，父链最多 32 层；超限返回 422 BRANCH_LIMIT_EXCEEDED，遍历检查环并限制深度。 |
| 历史与分页 | UI/API 每页默认 50、最大 200 条；Context 最近候选最多 200 条/200,000 字符，窗口边界不得只留下完整轮次的一半，超大旧轮次整体排除并记录原因，不静默截断正文。单条 mandatory 输入不能被候选限制截断。 |
| Mock Profile | 两个 Profile 默认 context_window 分别为 8192/2048、reserved_output 为 1024/256，安全余量 128；简易摘要上限 512，至少保留当前输入，近期完整轮次尽预算容纳。真实 Profile 上限由导入配置显式给出且必须通过组合校验。 |
| Task/流式 | 保留现有默认 3 次尝试、600 秒 deadline、60 秒步骤/Provider 预算、120 秒回答流预算、4096 次原始 delta 和 1,000,000 字符上限。所有上限在新 Snapshot 中冻结；超过输出/协议资源限制使用稳定错误码，不作为无知识回答。 |
| 持久 Event 速率 | delta 聚合每 100 ms 至多提交一次，末尾强制 flush；聚合缓冲最多 64 KiB，溢出明确失败。每 Run 最多 15,000 个常规事件，另预留取消/错误/终态槽位，额度耗尽时原子 failed/RUN_EVENT_LIMIT，不丢最后终态。非 delta 状态事件不被合并。 |
| SSE/UI 延迟 | v2 SSE 轮询基线 200 ms，Redis 只是加速；客户端批量渲染间隔不超过 100 ms。以首 delta 提交时间到 DOM 出现时间实测 ≤1 秒，API 提交 p95 ≤1 秒；不计上游首 token 时间。 |

这些值是实施默认，不是已测结果。聚合器必须有独立定时 flush，不能等待下一个 Provider delta 才发布已收到的首片；只有 stream 正常结束后才允许成功。可配置值须有限且校验组合（例如输出预留+余量小于窗口）；Run 执行相关值冻结在 Snapshot，分页/SSE/界面刷新属于观察参数，不改变执行配置。长检索/计数/摘要在锁外进行，活动执行继续受租约/取消保护，达到候选历史上限必须有可见的安全裁剪说明。Markdown 保留原文并经 DOMPurify 渲染；流式每次渲染也必须清洗，危险 URL/属性不得由“流中暂未闭合”绕过。浏览器本地偏好不存正文、Secret 或可信终态。

## 8. 异常、风险与回滚设计

| 场景 | 处理行为 | 结果/证据 |
| --- | --- | --- |
| Branch 所属 Thread/owner 不符 | API 404；不创建事实。 | 安全错误码，不暴露其他 owner。 |
| fork 消息不在父路径或分支环 | API 422；事务回滚。 | 保留原 Branch，不生成孤儿分支。 |
| Profile disabled/配置不完整 | 新 Run 409 MODEL_PROFILE_UNAVAILABLE；旧 Snapshot 参数不变，缺凭据明确 MODEL_CREDENTIAL_UNAVAILABLE。 | 不静默回退 Mock/默认模型。 |
| Provider 401/403/参数错误 | 永久失败，不消耗无限重试；保留 `PROVIDER_HTTP_*` 和安全摘要。 | Run failed，不能伪装无证据。 |
| Provider 超时/408/429/5xx/连接失败 | 按错误分类有限自动重试；达到上限进入 failed。 | Task attempt、退避、Run Event 可追溯。 |
| Provider 返回超大或持续缓慢的错误正文 | 成功流和非2xx正文共用累计字节及绝对时长限制；不先无界读取正文。 | 超限为安全 `PROVIDER_RESPONSE_LIMIT` 或 `PROVIDER_TIMEOUT`，不暴露原始错误正文。 |
| 上下文裁剪后仍超限 | 保存 `CONTEXT_TOO_LARGE`，不调用模型。 | ContextPlan 记录预算失败，原消息完整。 |
| 简易摘要构造失败 | 按固定策略退回 trim_only；mandatory 超限仍明确失败。 | 不生成无来源摘要，不删除历史。 |
| SSE 断开/浏览器刷新 | 只停止观察，按 seq 补放；不调用 cancel。 | Run 继续执行，事件不重复。 |
| 取消与成功同时到达 | 以锁和 commit 前条件检查的先到持久事实为准。 | 只有一个终态；迟到方安全拒绝。 |
| Worker 失租/重启 | 旧 Worker 停止写回，回收器按 generation 重新排队。 | 同一 Run/用户 Message，不重复最终 assistant。 |
| 旧 v0.1 Snapshot/迁移冲突 | 旧 Mock 快照按 ADR-002 兼容规则解码；无法解释的快照永久失败。 | 不猜测新默认值，不覆盖旧事实。 |
| Context/Branch 表迁移失败 | Alembic 在事务中失败，保留备份和旧版本；禁止手工改版本表。 | 通过 Runbook 回滚/恢复，不能启动不兼容应用。 |

### 8.1 事务和锁顺序

延续现有执行层 `Task -> Run -> Thread`，扩展为 `Task -> Run -> Thread -> Branch`；Event seq 由已经锁定的 Run 分配，Message seq 由 Thread 分配。不允许一条路径锁 Thread 后再等待已有 Task/Run，与执行终态形成反序。

- Worker 的事件/续租/失败/回收先锁 Task，再按需锁 Run；成功继续锁 Thread/Branch 推进 head。取消也使用 Task -> Run，不锁 Thread/Branch。
- 创建消息/Branch/显式新 Run 只锁 Thread -> Branch，然后插入全新的 Run/Task，不再对已存在的来源 Run/Task 加锁。来源只能是不可逆终态，读取足以验证；活动 Run 排斥由 Branch 锁及部分唯一索引保证。按同键查幂等必须先于状态冲突检查。
- Context 计算和 HTTP/摘要/模型调用不持数据库行锁；计划/摘要发布重新验证 Task/Run 的租约身份后在短事务完成。不能因为计划已生成而绕过取消或 lease 检查。
- 涉及多 Branch 时按 branch_id 稳定次序锁定；数据库死锁/锁超时按现有有界故障语义回滚，不吞掉为“无资料”。PG 多连接测试覆盖新建/取消/成功/回收交界，而非只凭 SQLite 结果判断。

### 8.2 迁移与回滚策略

发布采用停写升级：停止 API 接受新写入，优先让旧 Worker 完成/显式释放，再停止 Worker；确认进程全部退出，备份 PostgreSQL/上传卷及旧镜像版本，然后由 Compose migrate 执行 `alembic upgrade head`。不允许 v0.1 进程与新结构并行写入。

| revision（线性依赖） | 结构、回填及检查 |
| --- | --- |
| 0004_v2_session_branches，承接 0003 | 新建 Branch/SessionOperation；Thread 增加 conversation_version=1；现有每个 Thread 创建一个 default Branch，所有旧 Message/Run branch_id 回填到它，head 为最高 seq Message。Run 去掉 user_message_id 唯一约束、加 FK/索引；增加 parent_run_id/operation_kind/execution_schema_version=1，旧 operation_kind=initial。先 nullable 回填，检查后收紧必要 NOT NULL。保留旧 Message.run_id、seq、正文、ID、时间和幂等键。 |
| 0005_v2_profiles_context，承接 0004 | 新建 Profile 复合主键表、ContextPlan/Summary 和索引；迁入两个固定 Mock Profile 元数据；Run 的 profile/context 指针允许旧 Run 为空，旧 Snapshot 不回写。Profile 导入命令在迁移后显式运行，不能让 Alembic 从本机 Secret/当前 MODEL_NAME 猜测历史配置。 |
| 0006_v2_run_guards，承接 0005 | Run 状态为现有 String，不引入数据库原生 Enum；补允许 cancelling 的 CHECK、Branch 单活动 Run/每 Run 单主 Task 的部分唯一索引及必要跨对象约束。若旧数据同 Thread 有多个非终态 Run（v1 原允许），停止并输出冲突 ID/类别，先由旧兼容应用完成/取消，不能任意选一个。新事件 schema 在代码/契约定义，不为它修改或伪造旧 Journal。 |

迁移预检包括悬空/非 user 输入、跨 Thread 指针、主 Task 缺失/重复/互指不符、重复最终 assistant、活动 Run 冲突、Thread seq 计数器落后于最大 Message seq 和非法状态；旧 Snapshot 的可解码性作为只读诊断，不能解释时保留原文，待旧 Run 实际恢复明确失败。升级不自动重跑终态 Run，不为旧历史构造 ContextPlan 或 Summary。旧默认 Branch head 在后续 legacy 完成时也由共用执行服务推进。

验证必须覆盖全新库、含 queued/running/retry_waiting/三种终态和幂等历史的复制库、冲突负样本，以及 `upgrade head` 再次执行无变化；迁移事务失败保留原 revision/事实，不手工 stamp 掩盖。记录前后对象数量、ID/正文/事件 hash 和 revision。

回退边界：尚未产生 v2 写入时，在停止新进程、验证无 conversation_version=2 Thread/schema2 Run/子 Branch/多 Run 共用输入/Context/Summary/SessionOperation 后，方可执行到 `0003_chunk_locations` 的受保护 downgrade，再启动旧应用。迁移种入的 Mock Profile/默认 Branch 是允许移除的派生基线；人工导入的 Profile 先导出配置，不能无提示丢失。任一 v2 业务事实存在则 downgrade 必须拒绝，不能丢表或恢复唯一约束导致丢事实；优先修复向前，确需恢复旧版则恢复升级前数据库和卷备份，并明确其之后新增事实的导出/停写处理。禁止 `downgrade base`，也禁止直接用旧镜像写入已升级库。

## 9. 项目文件和目录变更

以下保留设计确认时的预计清单；具体落地文件以PR-002实际变动为准，预计文件名不作为已创建证据。括号中的同目录文件必须分职责实现；新增 Python 包补 `__init__.py`。本 ADR 首版交付已包含 PRD 关联、README 导航和 CONTEXT 设计来源。

实施命名映射：预计的`test_branch_context.py`拆分为`tests/unit/test_branch_paths.py`与`test_context_planning.py`；`test_v2_run_states.py`/`test_v2_provider_context.py`的执行断言落入`tests/integration/test_v2_run_execution.py`与`test_provider_http.py`；预计`fixtures/v2-session/`改为`fixtures/v2-profiles.json`及分类内独立动态数据。新增应用服务进一步拆为`session_threads.py`、`session_runs.py`、`session_execution.py`，`migrations/v2_session_checks.py`集中迁移只读预检。职责不变，避免为匹配预计文件名复制第二套实现。

### 9.1 预计新增文件/目录

| 路径 | 用途 | 使用阶段 |
| --- | --- | --- |
| `migrations/versions/0004_v2_session_branches.py` | Branch、消息/Run 关系和旧数据回填。 | 阶段 1 迁移；升级和回滚验证。 |
| `migrations/versions/0005_v2_profiles_context.py` | ModelProfile、ContextPlan、ConversationSummary 和索引。 | 阶段 1 建表，阶段 2～3 消费。 |
| `migrations/versions/0006_v2_run_guards.py` | cancelling 状态 CHECK、单 Branch 活动 Run 和跨对象约束预检。 | 阶段 1，正式部署执行完整迁移链。 |
| `backend/application/branches.py` | Branch 创建、路径解析、fork 校验和归档边界。 | 阶段 1、v2 API。 |
| `backend/application/session_operations.py` | 创建类操作的规范化 hash、幂等冲突和结果记录。 | 阶段 1，后续显式操作复用。 |
| `backend/application/context.py` | Token 预算、裁剪、摘要选择、ContextPlan 发布。 | 阶段 3、Worker。 |
| `backend/application/model_profiles.py` | Profile 列表、启用校验、版本和安全展示 DTO。 | 阶段 2、v2 API。 |
| `backend/domain/ports/session.py` | Branch/Context/Profile/TokenCounter 协议与 ModelRequest、计划和摘要 DTO。 | 阶段 1～3，隔离 ORM。 |
| `backend/infrastructure/session/branches.py`、`context.py`、`model_profiles.py` | 同一新包中的 PostgreSQL 路径读取、上下文计划/摘要存取、Profile 版本存取；不放预算业务规则。 | 阶段 1～3。 |
| `backend/infrastructure/providers/registry.py` | Profile -> Provider Adapter 解析和 Secret 运行时注入。 | 阶段 2。 |
| `backend/tools/sync_model_profiles.py` | 显式导入安全 JSON、版本冲突检查和默认/启禁用更新命令；只由维护者调用，不增加 HTTP 管理入口。 | 阶段 2，部署配置与测试。 |
| `docker/model-profiles.example.json` | 不含 Secret 的两个 Mock/真实 Profile 配置结构示例，真实配置必须显式填写可支持的 tokenizer/预算；不自动装载覆盖数据库。 | 阶段 2、5。 |
| `backend/api/routes/v2/threads.py`、`runs.py`、`models.py` | 同一 v2 路由包中新增 §6.2.1 的 15 条路由；既有能力复用应用服务，Branch 路由归 threads、context 读取归 runs，不新增 v2 archive 别名。 | 阶段 1～3。 |
| `backend/api/schemas/v2/threads.py`、`runs.py`、`models.py`、`context.py` | 同一 v2 Schema 包中的输入校验、安全响应和 Event 联合；不承载业务规则。 | 阶段 0～3。 |
| `contracts/thread_v2.json`、`branch_v2.json`、`message_v2.json`、`run_v2.json` | 同一 contracts 目录的 Thread/Branch/Message/Run 结构。 | 阶段 0，接口实现之前。 |
| `contracts/model_profile_v2.json`、`context_plan_v2.json`、`run_event_v2.json`、`api_responses_v2.json` | 模型安全字段、上下文摘要、legacy/v2 Event 联合和 v2 请求响应包装；复用 Evidence/Citation v1。 | 阶段 0～3。 |
| `frontend/src/api/v2/threads.ts`、`runs.ts`、`models.ts`、`frontend/src/types/api-v2.ts` | v2 client 分资源调用和独立生成类型；保留 api.ts/v1 client，复用原 http.ts 及 v1 文档接口，按 §6.1.3 迁移新工作台调用。 | 类型在阶段 0，client 在阶段 4。 |
| `frontend/src/stores/model.ts`、`frontend/src/stores/branch.ts` | 模型/分支选择和事实状态。 | 阶段 3～4。 |
| `frontend/src/components/BranchSelector.vue`、`ModelSelector.vue`、`ContextNotice.vue` | 分支、模型和上下文处理交互。 | 阶段 4。 |
| `frontend/src/components/RunActions.vue` | 取消、重试、重新生成按钮及服务端状态。 | 阶段 4。 |
| `frontend/src/markdown/render.ts` | 从组件提取公共 marked/DOMPurify 清洗入口，持久消息和草稿共用。 | 阶段 4。 |
| `backend/infrastructure/providers/context_counter.py` | Mock 确定性计数和 tiktoken encoding Adapter；不认识的真实配置明确拒绝。 | 阶段 2～3。 |
| `tests/unit/test_branch_context.py`、`tests/api/test_v2_session_api.py` | Branch、上下文、契约和安全投影单测/API 测试。 | 各阶段开发。 |
| `tests/integration/session_pg_probe.py` | 真实 PostgreSQL 多连接、迁移回填、分支并发、快照和终态屏障。 | 阶段 1～3。 |
| `tests/unit/test_model_profiles.py`、`tests/unit/test_v2_run_states.py` | 版本/Secret/默认选择、取消/重试/终态与有限资源边界回归。 | 阶段 2～3。 |
| `tests/integration/test_v2_provider_context.py` | 可控 Mock/HTTP Provider 上下文实收断言、模型快照和错误分类。 | 阶段 2～3。 |
| `tests/sesrag-persistent-session-workspace-test/specific_test_script/` | 当前独立工程的session/context/model/run/workspace/compatibility/performance/quality八分类，取代原预计接入旧Demo工程的做法。具体文件和用例见该目录README。 | 阶段5，按manifest调度。 |
| `tests/sesrag-persistent-session-workspace-test/fixtures/` | 两Thread/多Branch、预算与慢/失败Provider等安全合成素材；按实际目录README准备，不存真实Key。 | 阶段5。 |
| `frontend/tests/workspace-components.test.ts`、`frontend/tests/thread-store.test.ts` | 当前前端自有组件/Markdown/状态及归档视图回归；正式Chromium结果另由独立suite采集。 | 阶段4～5。 |
| `docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md` | 后续正式测试环境、需求/用例矩阵、命令和验收边界；不覆盖 Demo 方案。 | 阶段 5 前确定。 |
| `docs/pr/002-SesRAG-持久化会话与对话工作台-PR.md` | 实施差异、真实变更及验证证据；对应 ADR-002/PRD-002，Demo历史修复记录已统一编号001。 | 阶段 5 完成后回填。 |

新增目录必须在对应模块 README 登记；测试脚本遵守 `tests/sesrag-persistent-session-workspace-test/specific_test_script/README.md` 的分类协议，不能单独销毁总入口拥有的容器/卷。

### 9.2 预计修改文件/目录

| 路径 | 修改内容和目的 | 阶段 |
| --- | --- | --- |
| `backend/db/models.py` | 增加 Branch/Profile/Context/Summary/SessionOperation 映射，扩展 Thread/Message/Run 字段，去除输入唯一约束。 | 1～2 |
| `backend/domain/enums.py`、`ports/__init__.py`、`application/errors.py` | cancelling 枚举、新 DTO/ModelRequest 协议和安全错误分类；明确现有 ModelProvider 签名演进。 | 1～3 |
| `backend/application/threads.py`、`runs.py` | 版本边界、Branch 锚点创建/读取、显式重试/重新生成/取消和幂等事务。 | 1～3 |
| `backend/workers/handlers/run_handler.py`、`backend/application/task_execution.py` | 消费 ContextPlan/Profile Snapshot，按 generation 分隔 delta，新增计划发布/取消确认和最终 Message/Branch 原子提交。 | 3 |
| `backend/infrastructure/queue/postgres_queue.py`、`adapter.py`、`backend/workers/runtime.py` | 保持 lease/generation，取消中不回排，过期取消结算；关联 Branch/Profile 的安全日志。 | 3 |
| `backend/infrastructure/providers/factory.py`、`openai_compatible.py`、`mock.py` | 将 ModelRequest 转上游消息、输出上限和流式协议；旧 Snapshot 单独解码，Embedding 空间保持原配置。 | 2～3 |
| `backend/infrastructure/events/journal.py` | 按 Run execution_schema_version 写 Event，v2 执行身份、事件上限/终态预留和分页补放。 | 3 |
| `backend/api/routes/threads.py`、`runs.py`、`api/schemas/`、`dependencies.py`、`app.py` | 原地适配 §6.2.2 的 9 条 v1 路由并装配新增 v2 路由，维护共同权限/服务依赖；v1 Schema 不新增 v2 公开字段。 | 1～3 |
| `contracts/README.md`、`frontend/scripts/generate-api-types.mjs` | 登记 §6.1.2 契约保留/引用/新增策略，按 §6.1.3 保留 CLI 兼容并生成 api.ts/api-v2.ts；分别检查两代类型漂移与同名引用。 | 0～5 |
| `frontend/src/pages/WorkspacePage.vue`、`stores/thread.ts`、`stores/run.ts`、`events/run-event-stream.ts`、`api/http.ts` | Branch/Model 作用域、Run 全刷新重放、generation 分段、终态刷新和操作反馈；v1/v2 同源 base 一致。 | 4 |
| `frontend/src/components/MessageTimeline.vue`、`RunTimeline.vue`、`ThreadList.vue`、`frontend/src/styles.css` | 分支消息显示、Markdown/引用保持安全、状态和操作控件。 | 4 |
| `backend/config.py`、`.env.example`、`docker-compose.yml` | 新默认预算/限额、SSE 200ms、Profile 受信 Secret alias 注入，API/Worker 配置同源；legacy Settings 不隐式生成新 Profile。 | 2～5 |
| `pyproject.toml`、`docker/api/Dockerfile` | 添加并锁定经验证的 tiktoken 版本，构建时预备支持 encoding 的缓存；Mock 不依赖运行时网络下载，缺缓存明确配置不可用。 | 2 |
| `README.md`、`backend/README.md`、`frontend/README.md`、`CONTEXT.md`、`docs/接口文档.md` | 模块新增文件职责、术语/代际、v2 协议和操作导航；只在接口文档维护正式接口表。 | 各阶段 |
| `docs/runbooks/demo-development.md`、`demo-smoke-environment.md`（同 runbooks 目录） | Windows/Linux 停写备份/迁移/受限回退、Profile 导入/Secret、部署更新及测试资源回收命令。 | 2、5 |
| `tests/sesrag-persistent-session-workspace-test/specific_test_script/manifest.json`、`run-workspace-tests.ps1`、`compose/docker-compose.workspace-test.yml`（均在本轮套件内） | 独立接入八分类与受控Provider，保留入口的创建、采证和销毁所有权。 | 5 |
| `tests/sesrag-persistent-session-workspace-test/README.md`、`test-plan.md`、`specific_test_script/README.md`及`tooling/*.test.mjs`（均在该套件内） | 分类ID、结果协议、自测和清理门禁；旧149例不是v0.2完整覆盖依据。 | 5 |

### 9.3 暂不新增/不修改的文件边界

本轮不引入 LangChain/LangGraph、Milvus、Electron、MQ 集群或新的认证服务；不把 `DocumentModel.active_index_batch_id` 直接改名为公开 `DocumentVersion`；不修改历史 `0001`～`0003` 迁移文件，而以新迁移承接 v2。§6.1.2 列出的全部 v1 契约和前端 api.ts 保留，不能按“v2 已替代”删除；§6.2.3 的文档/索引/健康路由公开协议保持原样。

## 10. 技术路线和新增工具

| 能力 | 选型 | 原因和边界 |
| --- | --- | --- |
| 分支/上下文事实 | PostgreSQL + SQLAlchemy/Alembic | 与现有事实来源、锁和迁移一致；不引入独立图数据库。 |
| Token 预算 | TokenCounter Port + Mock 确定计数 + 真实模型显式 tiktoken encoding | 唯一新增主要 Python 库为 tiktoken；预算和误差边界见 §7.7，不把近似字符计数伪装为所有真实模型 tokenizer。 |
| 摘要 | 确定性提取摘要 trim_then_extract_v1，失败退 trim_only_v1 | 本轮真实交付带来源的简易压缩，不仅提供 Mock 占位；不额外调用摘要模型，不引入 LangChain/LangGraph。 |
| 多模型 | `ModelProfile` 元数据表 + Secret 运行时引用 + Provider Registry | 支持 Mock 和 OpenAI-compatible；凭据不进数据库/前端。 |
| 流式传输 | PostgreSQL Event Journal + SSE/Last-Event-ID，保留现有 Redis 唤醒 | 满足断线补放；不把 WebSocket 当事实来源。 |
| 前端 | Vue 3 + TypeScript + Pinia + marked/DOMPurify + 现有组件；不引入 Router/UI 大框架 | 复用当前工作台和生成类型；新增分支/模型组件。 |
| 测试 | pytest/pytest-asyncio、真实 PostgreSQL、可控本地 HTTP/SSE Provider、Vitest、Playwright、Compose smoke | 覆盖锁、恢复、协议、浏览器作用域和资源清理；Mock 不证明模型效果。 |

不新增底层消息队列、向量库或桌面运行时。只有当上下文计数或 Profile 存储需求证明现有路线不足时，另建 ADR 说明替换理由。

本轮受支持的真实encoding基线为`cl100k_base`，与构建阶段预热资产配对；应用先核验缓存文件的大小及固定SHA-256，缺缓存/损坏/不支持的encoding明确不可用。API/Worker不通过tiktoken的默认cache miss机制临时联网下载。将来扩展encoding时同时登记资产来源/hash、构建预热和离线负样本，不把SDK已知的所有encoding都默认为当前镜像可用。

## 11. 分阶段实施路线

### 阶段 0：契约和迁移设计冻结

1. 依据 §12 建立每条需求的预期/负样本：跨 Thread/Branch 哨兵、同输入多 Run、三类重试、generation 分段、取消/成功竞态、旧快照/协议迁移。
2. 先将文档内的契约设计落到 contracts/ 和接口文档，按 §6.1.2 保留 v1 并新增 v2 JSON Schema、错误码及严格 legacy 联合；按 §6.1.3 扩展类型生成器，检查 v1 导出/CLI 兼容和 v2 独立类型，增加合法样本、缺归属/非法状态/Secret 字段的拒绝断言。§6.2.1/6.2.2/6.2.3 分别登记新增、原地修改和保留接口，禁止将同一能力误建为另一套事实服务。本方案和后续实施均遵守仓库不自动提交/推送规则。
3. 确认各阶段文件表和迁移预检查询；先在专用 fixture 上设计全新库/旧库/冲突库/降级拒绝的失败断言，不调用开发库。
4. 退出条件：契约、字段、锁序、状态表和回退边界完成自审；类型生成与 Schema 负样本检查可运行，未实现的运行行为测试能明确失败，不能用占位通过。

### 阶段 1：数据模型、迁移和 Branch

1. 先运行预期失败的迁移/路径/API 测试；实现 0004～0006、ORM 和必要 FK/索引/CHECK，一次完成数据库基线，后续阶段不再临时创造不兼容字段。
2. 实现 Branch/SessionOperation Repository 与创建服务，保留 Run.user_message_id 字段但允许一对多；固定 Message.run_id 的创建者语义。
3. 实现 Thread/Branch v2 创建/读取/分页、重命名、归档/取消归档、fork 与幂等；在原有 v1 接口补 §6.2.2 的会话/Run 代际和单活动 Run 边界及 legacy 完成时 head 更新。实现首次成功 v2 会话写入的原子升级、失败回滚及读取/取消不升级规则。
4. 退出条件：全新库/旧事实复制库/冲突库/重复升级/无 v2 事实的 downgrade 测试通过；跨 Thread/祖先截断/同点多 Branch/同键重放/异内容冲突/归档规则均有独立断言。该阶段不开放尚未接线的新 Run UI。

### 阶段 2：ModelProfile、计数器和 Snapshot 基础

1. 先写双 Profile/版本冲突/禁用/缺 Secret/tokenizer 无效的失败测试；实现 Profile Repository、安全列表和显式导入命令，不在启动时读 JSON 覆盖表。
2. 实现 ModelRequest/TokenCounter、Mock 双 Profile、tiktoken encoding Adapter 和 Provider Registry；将 Profile 生成配置与固定 Embedding 配置拆开。
3. 完成 Snapshot schema 2 创建/恢复和 schema 1 legacy 解码；Profile 参数固定在 Snapshot，只有受信 Secret alias 在运行时解析。
4. 退出条件：修改默认/禁用 Profile 不改变已有 Snapshot；新 Run 选项完整校验，不回退 Mock；真实 HTTP 测试 Provider 确实收到选定模型、role history 和输出上限，凭据扫描不泄漏。尚未集成的 Context 行为由 DTO 级测试验证，不宣称端到端完成。

### 阶段 3：Context、可恢复流式 Run 与用户操作

1. 先增加 Context 裁剪/真实历史实收/摘要来源/generation 分段/取消竞态的失败测试；实现 §7.7 的锁外计算和授权短事务发布。
2. 接线消息创建、Worker RAG -> 计划 -> ModelRequest -> delta -> 成功原子提交，增加事件聚合和有限资源配置；未完成 draft 不写 Message。
3. 实现 §7.6 的 queued/active 取消、确认和回收优先级；实现显式 retry/regenerate 的 Branch 选择、SessionOperation 和新 Run 来源关系。
4. 退出条件：Provider 实收只有允许路径；每次尝试计划保留；预算/摘要失败回退、引用过滤、有限重试、重启/租约/旧写拒绝、取消成功竞态及同点多次重生成在真实 PG/可控 HTTP 下通过；新旧 Run/Event 契约均无漂移，legacy 恢复不产生 schema 2 事件，schema 2 Run 不能经 v1 投影。

### 阶段 4：前端工作台与用户控制

1. 先写失败组件/浏览器用例；增加 Branch/Model store 和选择控件，以 Thread/Branch/Run/epoch 隔离响应，以 run_id/seq 去重，以 task_id/generation 分隔尝试。新工作台按 §6.1.3 全面使用 v2 会话 client，文档 client 仍为 v1，旧会话 client 保留用于 legacy 回归。
2. 实现刷新恢复、非终态自动观察、SSE 重连、终态事实刷新、上下文提示和失败安全摘要。
3. 增加取消、显式重试、重新生成、从消息创建 Branch 的操作和状态禁用规则。
4. 退出条件：组件和 Playwright 覆盖正常/断线/全刷新从 Journal 重建/切会话/分支/模型/Markdown XSS，以及重命名/归档/取消归档；旧消息不重复、不串流、不被覆盖。新增 Markdown 共用入口在持久与流式渲染路径均被调用。

### 阶段 5：集成、部署和验收

1. 接入 v0.2 迁移到 Compose `migrate`，更新 `.env.example`、Runbook、README、模块 README。
2. 执行后端单测、契约/类型生成检查、真实 PostgreSQL 多连接探针、Provider 协议、前端 typecheck/build/Vitest/Playwright。
3. 正式测试使用 `tests/sesrag-persistent-session-workspace-test/` 独立八分类，不维护或复用已退出本分支的旧Demo验收目录。独立fixture经总入口完成启动、测试、报告、销毁和残留检查；同一冻结源码至少执行两轮正式回归，已完成的原两轮详见本轮测试报告；本次小修另按授权执行一轮。
4. 退出条件：PRD 第 9 节全部验收及 §12 P0/P1 需求均有真实证据；失败/blocked/未运行单列，未满足项不能写为全部完成；完成 PR-002 及验收记录，再按 §13.3 判断是否可改为“已实施”。

## 12. PRD 覆盖矩阵

| PRD 需求 | 实施方案落点 | 主要文件/测试证据 |
| --- | --- | --- |
| FR-TH-01、FR-TH-02、FR-MEM-01 | Branch/Thread 事实、归档、历史路径、消息持久和隔离。 | `backend/application/branches.py`、`threads.py`、迁移 0004、v2 Thread API、`test_v2_session_api.py`、Playwright。 |
| FR-BR-01 | 父 Branch + fork Message + 子 Branch 读取和幂等。 | `branches.py`、`BranchModel`、Branch API、`tests/unit/test_branch_paths.py`、`test_context_planning.py`。 |
| FR-BR-02 | `operation_kind`、`parent_run_id`、新 Run/子 Branch；自动 Task 重试保持原 Run。 | `runs.py`、`task_execution.py`、`run_handler.py`、Run API、PG 并发测试。 |
| FR-MOD-01、FR-MOD-02 | §5.2/§7.3/阶段2：Profile 单一真源、版本快照、Secret runtime injection；双 Mock 可选择。 | `model_profiles.py`、`providers/registry.py`、0005、`model_profile_v2.json`、Provider 实收/变配置恢复测试。 |
| FR-STR-01、FR-STR-02 | §6.3/§7.3/阶段3：先提交 Event 再 SSE、按 seq 补放、按 generation 分草稿。 | `journal.py`、`routes/v2/runs.py`、`run.ts`、`run_event_v2.json`、SSE/浏览器测试。 |
| FR-REC-01、FR-REC-02 | 事实恢复、非终态自动观察、Worker lease/generation 继续执行。 | `WorkspacePage.vue`、`thread.ts`、`runtime.py`、`tests/integration/session_pg_probe.py`、`tests/sesrag-persistent-session-workspace-test/specific_test_script/probes/postgres-cases.py`、Playwright。 |
| FR-RUN-01 | cancelling 状态、取消边界、迟到结果保护和幂等终态。 | `runs.py`、`task_execution.py`、0006、取消/成功竞态测试。 |
| FR-OBS-01、FR-MD-01 | 时间线安全摘要、Markdown 清洗、Citation 展开、禁止隐藏思维链。 | `RunTimeline.vue`、`MessageTimeline.vue`、`ContextNotice.vue`、安全/组件测试。 |
| FR-CTX-01、FR-CTX-02 | ContextPlan、TokenCounter、裁剪/摘要来源和预算失败。 | `context.py`、`context_counter.py`、0005、上下文单元/PG 测试。 |
| FR-RAG-01 | 复用现有 Evidence/Citation，绑定 Run/Branch 投影，禁止跨流引用。 | `run_handler.py`、`pgvector_store.py`、RAG 回归和浏览器测试。 |
| FR-ERR-01 | Provider/上下文/取消/基础设施稳定错误码、有限重试和安全日志。 | `errors.py`、Provider Adapter、Worker runtime、HTTP/故障测试。 |
| NFR-SEC-01、NFR-SEC-02、NFR-ISO-01 | Secret 引用、请求脱敏、Branch/Run scope、DOMPurify。 | `config.py`、v2 schemas、frontend stores、SEC/FE 测试。 |
| NFR-REL-01、NFR-REL-02 | PostgreSQL 事实、Task -> Run -> Thread -> Branch 锁序、SSE 投影、lease recovery。 | 0004～0006、`task_execution.py`、真实 PG/Compose smoke。 |
| NFR-PERF-01、NFR-CAP-01 | API/首 delta 预算、Context/stream/event 有界配置。 | `config.py`、context/provider adapters、`tests/sesrag-persistent-session-workspace-test/specific_test_script/performance-tests.mjs`、PERF_001/002。旧v1性能分类只作兼容回归。 |
| NFR-OBS-01、NFR-TEST-01 | 关联 ID、Context 安全摘要、Mock/慢/失败 Provider、可重放证据。 | `runtime.py`、测试工具、v0.2 smoke 报告。 |
| NFR-MIG-01、NFR-DEP-01 | 新迁移、旧快照兼容、Compose migrate、Runbook/README 更新。 | `migrations/versions/0004..0006`、`docker-compose.yml`、部署/回滚测试。 |

## 13. 验证、质量门禁和退出条件

### 13.1 开发阶段门禁

- 后端：`python -m pytest tests/unit tests/api tests/integration -q`、`mypy backend`、`ruff check .`、`ruff format --check .`。
- 契约：`npm run generate:api --prefix frontend`、`npm run check:api --prefix frontend`（实施后同时覆盖 v1/v2 两份产物）；Schema 动态验证覆盖成功、422、404、409、取消、模型禁用和错误脱敏；--output 的 v1 兼容模式和显式 --version v2 临时输出均有漂移负哨兵。
- 前端：`npm run typecheck --prefix frontend`、`npm run build --prefix frontend`、`npm run lint --prefix frontend`、`npm run test:unit --prefix frontend`。
- 真实 PostgreSQL：迁移全新/旧数据复制库、Branch 并发/幂等、Context 发布、Run 终态屏障、lease/generation、重启恢复。
- Compose/浏览器：按 Runbook 启停、迁移退出码、API/Worker/Redis/PG readiness、SSE 重连、刷新/切 Thread/Branch、资源清理。

性能验收在健康、单用户、同机 Compose 下预热后至少采集 30 次独立提交，记录样本量、配置、逐次响应时间及 p95 算法；不能只选最快一次。首 delta 延迟复用现有时钟误差区间/订阅屏障方法，分别记录 Event 持久时间、浏览器观察时间和误差上界；无法满足测量前提时标为验证不足，不将模型首 token 等待混入或排除失败样本。具体操作和脚本在后续正式测试方案细化，本次仅确认门禁目标。

针对 §6 的兼容适配，后续实施还必须逐项提供下列证据；不能仅以新增 v2 路由成功代替旧协议回归：

| 必验场景 | 可判断结果 |
| --- | --- |
| 路由和正式文档对照 | §6.2.1 的 15 条 v2 新路由、§6.2.2 的 9 条原地适配 v1 路由、§6.2.3 的 5 条保留路由均有 method/path/status 契约矩阵；没有重复 archive/聊天/文档别名。 |
| 旧 Thread 由两个版本访问 | v1 原成功包装不变；v2 GET/取消不升级；活动 legacy Run 阻止会话升级；成功的 v2 会话写入与 version=2 同事务，失败不推进 version。 |
| 升级后旧/新 Run 并存 | v1 Thread 级入口拒绝 version=2，但旧 Run 按 ID 仍可 GET/Event/SSE/cancel；新 Run 经 v1 全部拒绝，且 SSE 在发送 200 前拒绝。 |
| 事件精确版本和恢复 | schema 1 原样通过旧契约及 v2 联合，schema 2 只通过对应新分支；改标、混合 payload、未知版本明确失败；断线/刷新按 seq 补放且不触发取消。 |
| 兼容请求与冲突 | v1 可选幂等头/旧响应、同键复用及 Branch busy 明确拒绝；v2 消息/分支/retry/regenerate 强制幂等、提交锚点和 Profile 配对不反向强加给旧请求；409、参数校验 422、业务 422 分别符合所属包装。 |
| 调用方和无关资源回归 | 新工作台只发 v2 会话请求，不自动回落 v1；文档仍发 v1，健康原路径不变；legacy client/类型和生成 CLI 可独立回归，两份生成产物均可检测漂移。 |

### 13.2 必须保留的证据

每个需求/测试点至少保留用例 ID、Branch/Thread/Run/Task 关联、Event seq、迁移 revision、Provider 场景、脱敏日志和报告路径。失败、blocked、未运行和环境受限必须分别记录；不能用 Mock 成功替代真实 Provider 效果，也不能用 SQLite 结果替代 PostgreSQL 并发证明。

### 13.3 ADR 完成判定

只有满足 PRD 第 9 节验收、迁移和回退演练、契约/类型同步、Compose smoke、前后端测试和两轮稳定回归，并完成 `docs/pr/` 结果记录后，才将本 ADR 从“已接受”更新为“已实施”。如方案被实质反转，保留本 ADR 为历史并新增 superseding ADR，不能在原文隐式改写决策。

## 14. 风险和后续决策入口

- **上下文摘要质量**：简易摘要可能丢失事实；本轮以来源可追溯和安全边界为目标，不宣称语义质量。后续可在独立 ADR 引入评测和版本化摘要。
- **多模型 Provider 差异**：不同模型的 tokenizer、流式协议和上下文上限不同；统一 Profile/Adapter，协议异常不应泄漏到领域层。
- **旧快照兼容**：真实 Provider 的旧快照缺少 Secret 可能无法恢复；必须显式失败并保留原 Run，不自动切换 Mock。
- **Branch 图复杂度**：循环、深链和大量分支会增加读取成本；通过深度/数量有界配置和索引保护，超限返回明确错误，不在本轮引入图数据库。
- **SSE 与实时投影**：SSE 不是事实来源；任何丢通知都必须可由 after_seq 补放，浏览器测试要覆盖交界窗口。
- **迁移回退**：已产生 v2 事实后 downgrade 可能无法无损回退；优先备份恢复和兼容应用切换，Runbook 明确禁止 base 降级删除业务事实。

## 15. 原设计确认时的整体校审记录

本节记录原设计确认阶段，当时只完成设计文档，未实施代码、迁移或产品验收。校审对照 PRD-002 的功能/非功能清单与当时的 models、threads/runs 应用服务、Queue、Run Handler、契约、前端和 smoke 入口，检查结果如下：

| 校审项 | 结论与调整 |
| --- | --- |
| 范围与需求覆盖 | §12 逐项覆盖 PRD 的全部 FR/NFR；非目标与完整项目边界一致，P1 仍为本轮交付要求。 |
| 对象与单一真源 | 收敛为 Run.user_message_id，保留 Message 创建者指针；删除额外输入关系备选。Profile 表为唯一运行元数据源，配置 JSON 仅显式导入。 |
| 分支/幂等/重生成 | 同点多子分支与请求幂等分开；重新生成始终独立路径，失败输入重试按末尾决定复用/分叉，旧事实不覆盖。 |
| 执行与异常一致性 | 锁序统一为现有 Task -> Run -> Thread 的扩展；区分 queued 直接取消和活动 cancelling；每 generation 独立 ContextPlan/草稿，终态只取持久事实。 |
| 上下文与技术选型 | ContextPlan 放在 Worker 召回后发布，mandatory 超限预先失败；固定提取摘要而非模糊的摘要模型备选，明确 tiktoken/Mock 计数与校准限制。 |
| 文件/路线/兼容 | 新增和修改文件均列用途与阶段，阶段依赖与正文一致；v1 代际边界、三个新迁移、旧快照和拒绝有损 downgrade 均明确。 |
| 本版接口变更消歧 | 对照现有路由逐条列为 15 条新增 v2、9 条原地适配 v1、5 条保留路由；v2 PATCH 承接归档，未新增 archive 别名；“能力演进”和“新增 URL”分别标明。 |
| 本版契约/调用方处置 | v1 契约保留冻结，v2 独立新增并严格引用 schema 1；本轮不正式删除/废弃 v1。新工作台切换、旧 client 保留、两代类型生成和拒绝降级的边界已与 §9/§11/§13 对齐。 |
| 本版交叉行为校正 | 明确 v2 读取/取消旧 Run 不触发 Thread 升级，legacy 不产生 v2 执行事实；区分业务错误 code/message 与请求参数校验 422 的安全 detail 包装，显式 retry/regenerate 的 Profile 规则不被“默认模型”概述覆盖。 |

本节是设计阶段的文档校审结论，不是实现测试证据；§13的实现测试、性能及两轮回归结果应查阅PR-002与TEST-002。

