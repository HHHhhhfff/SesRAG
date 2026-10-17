# SesRAG 完整项目产品需求文档

**编号**：002

**版本**：v0.1

**状态**：长期目标基线，允许按阶段修订

**日期**：2026-10-03

**产品名称**：SesRAG

**适用范围**：SesRAG 完整目标产品及 PRD1～PRD4 演进路线

**关联文档**：[`001-SesRAG-项目Demo-PRD.md`](001-SesRAG-项目Demo-PRD.md)

## 1. 产品愿景

SesRAG 是一个类似 Codex 的、以持久化会话为中心的对话式 RAG Agent 平台。它不把一次提问视为不可恢复的 HTTP 调用，而是把长期会话、消息事实、一次执行、任务尝试、事件日志、工具调用和知识库版本建模为可恢复、可审计、可观测的对象。

产品长期重心有两个：

1. **类 Codex 的持久化会话对话模式**：Thread 长期存在，Run 可流式执行、暂停、取消、恢复和重放。
2. **可靠 Worker 调度**：任务拥有租约、心跳、代数、重试、背压、优雅停机和持久事件，进程重启不改变业务事实。

RAG 首期只聚焦文本型知识源，先保证流程、可追溯性和扩展边界，再逐步提升检索质量和知识库治理能力。

## 2. 产品原则

- **事实优先**：PostgreSQL 保存业务事实；缓存、消息通知、SSE 和前端状态都不能取代事实存储。
- **一次正式执行路径**：所有对话执行都通过 canonical Thread/Message/Run/Event 接口，不长期维护第二套 `/chat` 逻辑。
- **可恢复而非伪流式**：流式输出是持久 Event Journal 的投影；断线、刷新和进程重启后可以补放和恢复。
- **显式失败**：Provider、队列、数据库和索引故障不能伪装成“没有知识”或普通空回答。
- **接口隔离**：模型、Embedding、向量库、消息队列、对象存储和工具运行时都通过 Port/Adapter 替换。
- **版本化发布**：文档内容、模型配置、工具能力和评测基线都应有明确版本或快照。
- **最小权限**：能力可见、能力授权和能力执行分层；Secret 只留在服务端受控边界。

## 3. 产品范围与阶段

完整产品分为四个相互衔接的产品需求包。每个需求包都必须独立可测试，并在不破坏前一阶段正式契约的前提下交付。

| 需求包 | 名称 | 核心结果 | 依赖 |
| --- | --- | --- | --- |
| PRD1 | Worker 租约与任务调度 | 可恢复、可审计、可水平扩展的任务执行底座 | Demo 的 Task/Event 基础 |
| PRD2 | 持久化会话与 Agent Runtime | 类 Codex 的 Thread/Run/流式输出/工具调用/恢复 | PRD1 |
| PRD3 | 可装配工具与知识库工作台 | 文本检索、文档预览、本地目录知识库和能力注册 | PRD1、PRD2 |
| PRD4 | 知识库版本化与评测发布 | 采集、审核、索引重建、评测、发布和回滚 | PRD1～3 |

## 4. PRD1：Worker 租约、任务调度与持久事件

### 4.1 目标

把“任务正在执行”从进程内状态提升为可恢复的持久业务状态，支持多 Worker、故障接管、有限重试、背压和优雅停机。

### 4.2 领域对象

```text
Task
├── task_id             # 业务任务稳定身份
├── tenant_id           # 配额、隔离、审计和计费边界
├── state                # queued/running/retry_waiting/succeeded/failed/cancelled
├── task_version        # 防止旧消息覆盖新状态
├── deadline_at          # 整个任务硬截止时间
├── operation_id         # 外部副作用的稳定幂等身份
└── RunAttempt
    ├── run_id
    ├── worker_id
    ├── generation
    ├── lease_expires_at
    ├── attempt
    ├── progress/checkpoint
    └── last_error

QueueMessage(message_id, task_id, task_version_hint, available_at)
BusinessEvent(event_id, task_id, run_id, operation_id, seq, type, payload)
```

这里的 `RunAttempt` 是 Worker 对一个业务 Task 的某次执行尝试；会话层的 `Run` 仍然是用户一次提问的完整执行身份。Task 重试可以产生新的 `RunAttempt`，但不能创建新的 Thread、用户 Message 或会话层 Run。

### 4.3 功能需求

- 支持按租户、队列、优先级和 `available_at` 领取任务。
- 领取时原子写入 `worker_id + generation + lease_expires_at`；只有当前 generation 能续租、报告进度和提交终态。
- 心跳续租有间隔、最大延迟和截止时间；续租失败后处理器进入停止写回流程。
- 租约过期可由回收器重新排队；同一任务的旧消息可重复投递，但必须由 task_version/generation 去重。
- 支持指数退避、最大 attempts、不可重试错误分类、死信或人工处置状态。
- 支持队列深度、租户配额、并发上限和全局背压；系统过载时 API 返回可诊断的限流/排队状态。
- Worker 收到 SIGTERM/SIGINT 后停止领取，等待运行中任务到达安全边界；超时任务由租约回收机制接管。
- 每个任务和每次尝试产生持久 BusinessEvent，可按 seq 查询、重放和审计。
- 任务处理器支持幂等执行；涉及外部副作用时必须使用 operation_id 和结果去重。

### 4.4 验收标准

在两个 Worker 并发竞争同一任务、一个 Worker 中途断电、Redis 暂时不可用、数据库连接短暂失败和优雅停机的测试中，最终只能产生一个权威终态；任务不会丢失，旧 generation 不会覆盖新 generation，事件序号不会重复。

## 5. PRD2：类 Codex 持久化会话与 Agent Runtime

### 5.1 领域关系

```text
Thread（长期会话）
├── Message（用户问题、assistant 最终回答、历史事实）
└── Run（一次问题的完整执行）
    ├── Execution Snapshot（不可变执行快照）
    ├── Event Journal（追加事件）
    ├── Checkpoint（可选恢复点）
    ├── Run Context（仅本次 Run）
    ├── Tool Audit（授权、调用和结果审计）
    ├── Model Snapshot
    ├── Capability/Guardrail Snapshot
    └── terminal state
```

### 5.2 Run 生命周期

正式状态：`queued`、`running`、`waiting_input`、`cancelling`、`succeeded`、`failed`、`cancelled`、`expired`。

`waiting_input` 是暂停态，不是终态；恢复必须继续同一个 Run、Checkpoint、assistant Message 和 Event 序列。终态只能由持久事务写入最终消息和 terminal Event。

### 5.3 功能需求

- Thread 支持创建、改标题、归档、列表、读取和所有权校验。
- Message 使用 Thread 内单调序列；原始用户 Message append-only，派生摘要/记忆不能覆盖事实来源。
- 创建 Run 时冻结模型 profile、Prompt/Skill 版本、工具能力、检索配置、预算和租户策略。
- 前端通过 SSE 接收 `run.started`、文本增量、工具调用、检索证据、审批请求、checkpoint、消息完成和 terminal Event。
- SSE 断连只停止观察；客户端通过 `Last-Event-ID` 或 `after_seq` 补放事件。
- 支持真实取消：API 写入取消请求，Worker 在模型、检索和工具步骤间检查并以明确事件结束。
- 支持工具调用循环、最大步数、deadline、上下文预算、重复调用 fingerprint 和错误分类。
- 工具调用前经过 Registry/Guardrail；需要人工批准的工具必须在 Run 创建前获得授权或进入 `waiting_input`。
- Tool Audit 记录工具版本、输入摘要、授权结果、执行结果摘要、错误和耗时，但不得泄露 Secret。
- 支持 ModelProvider、EmbeddingProvider、RerankerProvider 的统一异步接口；每个外部调用只有一个重试所有者。
- 支持恢复、重放和导出脱敏执行记录；不能通过重新创建一个相似 Run 来冒充恢复。

### 5.4 验收标准

- 两个客户端同时观察同一 Run 时，事件按 seq 去重且最终 assistant Message 只有一个权威版本。
- SSE 断开、API 重启或 Worker 重启后，客户端可通过 `Last-Event-ID`/`after_seq` 补齐事件，Run 不会因为观察者断开而被取消。
- `waiting_input` 恢复继续使用原 Run、Checkpoint、assistant Message 和事件序列；不会生成新的用户问题。
- 模型配置、工具权限和检索配置在 Run 创建后冻结；控制面修改只影响之后创建的 Run。
- 取消、超时、Provider 失败、工具拒绝和检索为空分别产生可识别状态/错误码，且迟到的成功回写不能覆盖终态。
- 工具调用的授权、输入摘要、结果摘要和错误均可审计，Secret 不出现在事件、日志和前端。

### 5.5 类 Codex 交互要求

- 左侧显示可恢复 Thread 列表，主区显示 Message 与运行中的 Event 投影，详情区显示 Run 状态、引用和工具轨迹。
- 刷新、浏览器休眠、SSE 断开后，页面自动恢复当前 Thread 和未终止 Run 的观察状态。
- 用户能够停止当前 Run、重试失败 Run、从 checkpoint 提交输入并继续同一 Run。
- 运行中的增量内容在最终 `message.completed` 前不得被标记为最终回答。

## 6. PRD3：可装配工具与文本知识库工作台

### 6.1 工具系统

工具系统分为四层：

1. **Registry**：工具名称、版本、输入输出 Schema、角色要求、网络和资源范围。
2. **Capability session**：针对一个 Run 计算工具可见性和授权快照。
3. **Guardrail**：在 handler 执行前验证参数、域名、路径、配额、敏感字段和审批状态。
4. **Adapter/Runtime**：执行已获准的工具，并写入 Tool Audit。

首批可装配工具：文本检索、文档预览、目录扫描、受限 HTTP JSON Tool。任意 Shell/Python、SQL、Web Research 和 Sandbox 只有在独立安全设计、隔离运行时和审计测试完成后才能启用，默认关闭。

### 6.2 文本知识库

- 支持上传文件、配置本地文档目录和手动触发采集。
- 首批格式为 `.txt`、`.md`、`.docx`；`.doc`、PDF、表格和图片通过独立 Parser Adapter 扩展，不改变上层索引契约。
- 统一输出 `Document`、`DocumentVersion`、`Chunk`、`SourceLocation` 和解析诊断。
- 文档预览必须经过所有权、路径和版本校验，不暴露宿主绝对路径。
- 检索结果包含知识库、版本、文档、chunk、位置、召回方式和分数，可在回答中生成稳定引用。
- 支持 Dense、BM25、Hybrid、RRF、Auto-merging 和可选 Rerank；每一种策略均通过 RetrievalPort 接入并写入 RAG Trace。
- 检索失败、无结果、证据不足和模型失败有不同错误语义和前端展示。

### 6.3 验收标准

- 禁用或无权限的工具不会出现在当前 Run 的可见能力中；即使客户端伪造工具名或参数，服务端仍拒绝执行。
- 文档预览只能访问当前用户有权访问的已登记文档版本，不暴露宿主绝对路径或任意本地文件。
- `.txt`、`.md`、`.docx` 可通过同一 ParserPort 进入索引；新增格式只增加 Adapter，不改变 Document/Chunk 契约。
- 检索结果包含稳定的知识库、版本、文档、chunk 和位置身份；回答引用只能指向本次 Run 实际取得的证据。
- 向量库、Embedding 或解析器故障会以明确错误结束任务，不会被包装成正常的无结果回答。

## 7. PRD4：知识库版本化、审核、评测与发布

### 7.1 版本生命周期

```text
source -> collected -> parsed -> candidate_indexed -> review_pending
       -> approved -> published -> retired
                         └-> rejected/failed
```

- 原始 source 和解析结果可追溯；内容哈希用于去重和增量采集。
- 每次索引构建生成不可变 `DocumentVersion` 和 exact manifest，candidate 在隔离 scope 构建。
- 审核人可以查看变更摘要、解析错误、chunk 预览和影响范围，并批准或驳回。
- 发布通过 PostgreSQL CAS 原子切换 current version；构建失败或评测不达标不污染线上版本。
- 支持回滚到上一个已发布版本和按知识库/租户设置发布策略。

### 7.2 评测

- Dataset、Case、Observation、Baseline、Gate 和 Report 全部版本化。
- 评测覆盖检索相关性、证据可回答性、引用正确性、回答 groundedness、完整性、冲突披露和延迟/成本。
- Evaluation Job 使用独立 Worker，创建时冻结 Model Snapshot、Knowledge Base Version 和评测规则。
- 发布前可以运行离线 smoke、回归集和质量 Gate；Gate 失败阻止发布或要求人工确认。
- 报告保留 case、证据身份、judge reason、错误码和与 baseline 的差异，不能只保存一个总分。

### 7.3 验收标准

- candidate 构建期间，当前 published version 继续可检索；candidate 失败不会改变 current 指针。
- 发布只能通过带版本校验的 CAS 完成；并发发布时至多一个版本成功成为 current，失败方得到可诊断冲突。
- 审核记录包含审核人、时间、版本、结论和理由；未审核或评测 Gate 未通过的版本不能按正常流程发布。
- 发布后可按版本查询文档、chunk、manifest、索引状态和 RAG Trace，并能回滚到上一已发布版本。
- Evaluation Job 固定知识库版本、模型快照和评测规则；同一 Dataset/配置可以重跑并比较 baseline，而不会覆盖历史报告。

## 8. 完整技术架构

### 8.1 推荐组件

| 组件 | 正式职责 | 备注 |
| --- | --- | --- |
| FastAPI API | HTTP、SSE、认证、Thread/Run/Document/Control API | 无长时间业务执行循环 |
| Conversation/Run Service | Thread、Message、Run 生命周期和事务编排 | 只依赖 Port |
| Task/Worker Runtime | 任务领取、租约、执行、心跳、重试和停机 | 可水平扩展 |
| PostgreSQL | 所有业务事实、事件、版本、审计、控制面 | 权威存储 |
| Redis | 低延迟事件通知、短期缓存、共享限流 | 不保存最终事实 |
| pgvector（Demo/小规模） | 低运维向量存储 | 通过 VectorStorePort 替换 |
| Milvus（规模化可选） | Dense/BM25/Hybrid 向量检索 | 仅保存可重建索引数据，不决定发布 |
| Object Storage/MinIO | 原始文档、构建产物和大对象 | URI 与所有权分离 |
| Model/Embedding/Rerank Provider | 外部模型能力 | API Key 只在服务端 |
| Vue 前端 | 会话、任务、知识库和管理工作台 | 只做服务端状态投影 |

### 8.2 部署

开发和单机部署使用 Docker Compose，至少包含 `frontend`、`api`、`worker`、`postgres`、`redis`，需要时增加 `object-storage` 和 `milvus` profile。生产可在 Compose 基础上由 systemd、Kubernetes 或等价 supervisor 管理 API、Worker 和定时清理任务，但服务必须共享同一 release、迁移版本和配置。

### 8.3 技术路线决策

- 后端选择 Python 3.12 + FastAPI + SQLAlchemy/Alembic，因为异步 IO、类型契约和 Python RAG 生态适合本项目。
- 前端选择 Vue 3 + TypeScript + Vite + Pinia + Vue Router；Naive UI、marked、DOMPurify、Lucide Vue 和可选 Shiki 提供稳定工作台基础。
- LangChain/LangGraph 可以作为 Provider/Graph 编排实现，但领域事实、Task/Run 状态和 Event 契约不能交给框架隐式管理。
- Demo 先用 PostgreSQL/pgvector，完整项目按规模和检索能力引入 Milvus；替换必须只影响 Adapter 和部署 profile。
- Demo 先用 PostgreSQL 任务表，完整项目再评估 Redis Streams、NATS、RabbitMQ 或 Kafka。选择标准是租约语义、持久性、回压、可观测性和运维成本，而不是库的流行度。
- Electron 不作为首版前端形态；浏览器 Web 应用先验证持久会话和 Worker 主流程，桌面端以后通过复用 API/契约实现。

## 9. 权限、安全与租户隔离

- 生产支持用户、租户、工作区和管理员角色；所有 Thread、Document、Run、Task、Artifact 和 Evaluation Job 均做服务端所有权校验。
- Access Token 只保存在浏览器内存；Refresh Token 使用 HttpOnly、Secure、固定 Path Cookie 并可撤销和轮换。
- API Key、DSN 密码、Cookie Secret、模型输入中的 credential 和工具 Secret 不进入数据库公开字段、事件、Checkpoint、评测报告或前端。
- 上传使用大小、扩展名、MIME、内容哈希、路径和解析超时限制；本地目录只允许显式配置的根路径。
- Web/HTTP Tool 使用固定 HTTPS、域名 allowlist、私网阻断、超时、响应大小和 Content-Type 限制。
- Sandbox 若启用，必须使用无网络、无宿主挂载、资源受限的独立运行时；Guardrail 不被 Sandbox 取代。
- 前端 Markdown、文档预览和工具输出全部做 XSS 清洗；日志默认脱敏。

## 10. 可观测性与运维

- 结构化日志统一携带 `tenant_id`、`thread_id`、`run_id`、`task_id`、`attempt`、`generation`、`worker_id`、`event_seq`。
- 指标至少包括 API 延迟/错误率、队列深度、租约过期数、重试数、任务处理时长、事件积压、模型 Token/成本、检索命中和引用覆盖率。
- Trace 将一次 API 请求关联到 Run、Task、Provider、Retrieval、Tool 和数据库事务。
- 提供 `/health/live`、`/health/ready`、依赖诊断、迁移状态和 Worker readiness；readiness 不能只表示进程存在。
- Runbook 覆盖迁移、备份恢复、租约异常、死信处置、索引重建、版本回滚、Secret 轮换和优雅停机。

## 11. 质量目标与验收

### 11.1 可靠性目标

- 已提交的 Thread、Message、Run、Task、Event、DocumentVersion 和 Evaluation Job 在单进程重启后不丢失。
- 同一 Task 的有效执行尝试在任一时刻最多一个；旧 generation 不能覆盖新状态。
- 终态事件和最终 assistant Message 可通过重放重建；SSE 断开不改变业务结果。
- 文档 candidate 构建失败不影响当前 published version。

### 11.2 质量门禁

- Python：pytest、pytest-asyncio、Ruff、mypy、迁移测试、契约测试和故障注入测试。
- Frontend：ESLint、Prettier、vue-tsc、Vitest、构建检查和 Playwright 主流程。
- Integration：Compose smoke、API/Worker/DB/Redis 重启、并发领取、租约过期、模型超时、向量库不可用。
- RAG：固定 Dataset、Observation、baseline、回归 Gate 和可追溯 Evidence identity。
- Security：认证生命周期、权限隔离、上传安全、URL/路径策略、Secret 脱敏、Markdown XSS 和工具审计。

## 12. 路线图

### 阶段 A：Demo

完成 Thread/Message/Run/Event、PostgreSQL Task Queue、最小租约/心跳/重试、文本 RAG、引用、SSE 和 Compose。

### 阶段 B：PRD1

抽象 QueuePort，补齐多 Worker、优先级、租户配额、背压、死信、operation_id、任务事件查询和生产级停机/恢复。

### 阶段 C：PRD2

引入 Checkpoint、waiting_input、模型快照、工具循环、取消、工具审计、恢复/重放、认证和 Thread 工作台。

### 阶段 D：PRD3

引入 Tool Registry/Skill、文本检索工具、文档预览、本地目录知识库、对象存储和可选 Milvus；完善 Guardrail 和能力控制面。

### 阶段 E：PRD4

引入 DocumentVersion、采集审核、candidate build、原子发布/回滚、评测 Worker、质量 Gate、baseline 和知识库管理工作台。

### 阶段 F：生产化

补齐多租户、RBAC、限流、备份恢复、SLO、容量压测、灾难演练、Secret 轮换、成本控制和正式运维 Runbook。

## 13. Demo 到完整项目的兼容策略

1. Demo 的 `/api/v1`、Thread/Message/Run/Event 字段作为第一版契约；新增能力优先新增可选字段或新资源，不改变已有终态语义。
2. Demo 的 Task 逐步增加 tenant_id、task_version、operation_id、deadline_at 和 RunAttempt；不把 attempt 误建模成新 Thread 或新用户 Message。
3. Demo 的 Event payload 从一开始带 `schema_version` 和安全关联 ID；后续通过契约迁移扩展工具、Checkpoint、RAG Trace 和 Artifact。
4. Demo 的 pgvector、PostgreSQL 队列和 mock Provider 都实现正式 Port；完整项目替换实现时不得把具体依赖泄漏到 application/domain。
5. Demo 的单一文档集合升级为不可变 DocumentVersion；发布采用 candidate + manifest + CAS，不直接覆盖 current index。
6. 所有新增生产能力先进入本 PRD 的对应需求包，并拆成独立 ADR、迁移、契约和测试任务。

## 14. 明确暂不承诺的能力

除非后续 PRD/ADR 明确批准，产品不承诺：自动修改用户本地文件、无限制 Shell/代码执行、任意公网抓取、绕过权限的跨租户检索、把模型上下文当作事实数据库、没有审计的工具调用、无版本的线上索引覆盖、以及通过前端状态推断任务完成。

本 PRD 是完整项目的总目标，不要求一次实现全部能力。每次迭代都必须回到相应需求包，明确本期交付、兼容性、迁移、测试和回滚方式。
