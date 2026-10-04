# ADR-001：SesRAG 项目 Demo 实施方案

**状态**：已实施

**版本**：v0.1

**日期**：2026-10-04

**适用范围**：第一阶段项目 Demo

**依据**：[`docs/prd/001-SesRAG-项目Demo-PRD.md`](../prd/001-SesRAG-项目Demo-PRD.md)

**实施结果**：Demo 已完成基本实现和本地验证；结果记录和测试验收文档按本仓库文档治理约定补充到 `docs/pr/`、`docs/test/`。

## 1. 决策摘要

SesRAG Demo 采用“模块化单体后端 + 独立 API/Worker 容器 + 独立 Vue 前端”的架构。API 和 Worker 使用同一份后端代码与同一版本配置，但承担不同进程职责；PostgreSQL 保存业务事实、任务和 Event Journal，Redis 只负责低延迟通知与短期缓存，pgvector 作为 Demo 的向量检索实现。

本方案的核心目的不是一次性堆叠全部生产能力，而是先交付一条可重启、可测试、可继续扩展的纵向链路：

```text
Thread
  -> Message
  -> Run + RunSnapshot
  -> Task（run / index_document）
  -> Worker lease / heartbeat / retry
  -> Event Journal
  -> Retrieval / Generation
  -> assistant Message + terminal Event
```

后续替换消息队列、向量库、模型 Provider、文档解析器和工具系统时，只替换 Infrastructure Adapter 或新增独立模块，不改变 Thread/Message/Run/Event 的正式语义。

## 2. 目标、边界与验收口径

### 2.1 本方案必须实现的结果

1. Compose 可以启动 `frontend`、`api`、`worker`、`postgres`、`redis` 和数据库迁移服务。
2. 用户可以创建 Thread、追加用户 Message、创建 Run，并在页面看到持久化回答和引用。
3. Worker 可以从 PostgreSQL 任务表领取任务，使用 lease/generation 续租、重试、取消和优雅停机。
4. Event Journal 是 Run 的事实来源；SSE 只投影事件，断线后可以通过 `after_seq` 补放。
5. 文本文件可以完成登记、解析、切分、Embedding、pgvector 索引、Top-K 召回和带证据回答。
6. API、Worker、Redis 或前端重启不会丢失已经提交的事实；旧 Worker 的迟到写回不会覆盖新执行者。

### 2.2 明确不在本次实施范围

本次不实现生产级认证与 RBAC、多租户计费、HITL Checkpoint、任意 Shell/Python 沙箱、Web 搜索、SQL 工具、Skill Registry、Milvus 集群、Hybrid/BM25/Rerank、知识库审核发布和完整 RAG Evaluation 平台。这些能力只通过稳定的 Port、数据字段或目录边界为完整项目保留演进位置，不提供半成品用户入口。

### 2.3 发现并固定的状态语义

PRD 同时要求 Run 支持 `retry_waiting`，并描述了回到排队态的简化图示。实施时采用以下明确语义：

```text
Task: queued -> leased/running -> succeeded
                         ├-> retry_waiting -> queued
                         ├-> cancelled
                         └-> failed

Run: queued -> running -> retry_waiting -> running
                         └-> succeeded|failed|cancelled
```

`Task` 的 `retry_waiting -> queued` 表示任务等待下一次领取；`Run` 的 `retry_waiting -> running` 表示同一次用户执行仍未结束。重试永远不会创建新的 Thread、用户 Message 或会话层 Run。

## 3. 总体架构

### 3.1 运行拓扑

```text
Browser
   |
   | HTTP / SSE / multipart upload
   v
frontend  ------------------------------+
   |                                    |
   +-------------> api -----------------+----> PostgreSQL
                         |                         |
                         +-------------------------+----> pgvector
                         |
                         +------------------------------> Redis（通知/短缓存）

worker <-------------------------------------------------+
   |                                                     |
   +---- 共享 PostgreSQL / Redis / uploads volume -------+
```

### 3.2 容器职责

| 容器 | 正式职责 | 不承担的职责 |
| --- | --- | --- |
| `frontend` | Vue 开发服务器或静态资源服务，调用 `/api/v1` | 不保存 Run 终态，不直接访问数据库 |
| `api` | HTTP、SSE、Thread/Run/Document API、配置和健康检查 | 不执行长时间模型/索引任务 |
| `worker` | 领取 Task、维护 lease、执行索引和 RAG Run、写回事件 | 不提供公开 HTTP API |
| `postgres` | Thread、Message、Run、Task、Event、Document、Chunk 和向量事实 | 不负责低延迟浏览器通知 |
| `redis` | Event 通知、SSE 唤醒、短期缓存 | 不保存最终 Run/Task 状态 |
| `migrate` | 运行 Alembic 前向迁移后退出 | 不长期运行 |

`api` 和 `worker` 必须使用同一镜像或同一代码版本。`worker` 与 `api` 共享上传卷；上传文件使用随机 storage key，不能将宿主路径暴露给前端。

Worker 使用 `worker_id` 对应的 Redis 临时键写入 readiness 心跳；API 的 ready 响应在 Redis 可用时报告最近心跳的 Worker 数量。Redis 不可用时，API 将通知和 Worker 心跳标记为 `degraded/unknown`，但只要 PostgreSQL 和迁移状态正常，业务 API 仍可 ready，因为任务事实不依赖 Redis。

### 3.3 选型决策

| 领域 | 选择 | 实施说明 |
| --- | --- | --- |
| 后端 | Python 3.12、FastAPI、Pydantic v2 | 路由层只做协议转换，领域和应用层不依赖 FastAPI。 |
| ORM/迁移 | SQLAlchemy 2、psycopg 3、Alembic | 使用 `postgresql+psycopg`；Schema 变化必须有迁移。 |
| 任务事实 | PostgreSQL 任务表 | 使用事务、`FOR UPDATE SKIP LOCKED` 和条件更新实现领取/租约。 |
| 通知 | Redis | 发布失败不影响正确性，SSE 依靠 Event Journal 数据库轮询补偿。 |
| 向量 | PostgreSQL + pgvector | Demo 减少基础设施；通过 `VectorStorePort` 预留 Milvus。 |
| 文档解析 | `txt`、`md` 原生解析，`docx` 使用 `python-docx` | 统一 `DocumentParserPort`，不把格式判断散落在 Worker。 |
| 模型 | `MockModelProvider` + 可选 OpenAI-compatible Provider | 无外部 Key 也能跑完整自动化验收；真实 Provider 失败必须显式报错。 |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Naive UI、marked、DOMPurify、Lucide Vue | 浏览器只投影服务端状态。 |
| 测试 | pytest、pytest-asyncio、Ruff、mypy、Vitest、vue-tsc、ESLint、Playwright | 单元、契约、集成和主流程验收分层执行。 |

Demo 不在领域层引入 LangChain/LangGraph 的状态管理。若未来使用 LangChain/LangGraph，只能将其放在 Model/RAG Adapter 或执行编排内部，不能取代 PostgreSQL 中的 Run、Task 和 Event 契约。

## 4. 核心对象设计

### 4.1 对象清单

| 对象 | 含义 | 主要职责 | 关键关系 |
| --- | --- | --- | --- |
| `Thread` | 长期会话容器 | 保存标题、owner、归档状态和 Message 顺序游标 | 一对多 `Message`、一对多 `Run` |
| `Message` | 会话事实消息 | 保存用户问题或最终 assistant 回答；按 Thread 内 seq 排序 | 用户 Message 启动一个 Run；assistant Message 关联一个 Run |
| `Run` | 一次用户问题的完整执行 | 保存状态、快照、取消标志、主 Task 和最终 assistant Message | 属于 Thread；关联一个用户 Message、一个主 Task、多条 Event |
| `RunSnapshot` | 创建 Run 时冻结的配置快照 | 保存模型、检索、Prompt 版本和运行参数 | 从 Run 创建后只读 |
| `Task` | 持久化可执行工作项 | 承载 `run` 或 `index_document`，保存 lease、attempt、deadline 和错误 | `run` Task 关联 Run；`index_document` Task 关联 Document |
| `RunEvent` | Run 内按 seq 追加的事件 | 记录状态、检索、增量输出、重试和终态 | 多对一 Run；唯一键 `(run_id, seq)` |
| `Document` | 已登记的原始文档 | 保存文件元数据、content hash、storage key 和索引状态 | 一对多 `Chunk`，可关联 index Task |
| `Chunk` | 文档可检索文本片段 | 保存文本、序号、字符位置和 Embedding | 多对一 Document；被 Retrieval 返回为证据 |
| `Citation` | assistant 对证据的引用 | 保存 document/chunk/location 身份 | 存在于 assistant Message 的结构化字段中 |
| `WorkerIdentity` | Worker 进程的运行身份 | 生成稳定 worker_id，参与 lease/generation 校验 | 不作为业务事实表；出现在 Task 和日志中 |

### 4.2 关系与身份约束

```text
Thread 1 ──< Message
Thread 1 ──< Run
Message(user) 1 ── 1 Run
Run 1 ── 1 primary Task(kind=run)
Run 1 ──< RunEvent
Run 1 ── 0..1 Message(role=assistant)
Document 1 ──< Chunk
Document 1 ── 0..* Task(kind=index_document; at most one nonterminal)
```

- `Thread`、`Message`、`Run`、`Task`、`RunEvent`、`Document`、`Chunk` 使用服务端生成的 UUID4。
- 一个 Run 只能绑定一个用户 Message 和至多一个最终 assistant Message；重试只能增加 Task attempt。
- Message 的 `(thread_id, seq)`、RunEvent 的 `(run_id, seq)`、Chunk 的 `(document_id, index_batch_id, seq)` 都有唯一约束。
- `Task.kind=run` 时必须有 `run_id`；`Task.kind=index_document` 时必须有 `document_id`，由应用层校验互斥关系。
- `Run.primary_task_id` 初始允许为空；事务先创建 Run，再创建引用该 Run 的 Task，最后在同一事务中回填 `primary_task_id`，避免循环外键无法插入。
- Demo 使用固定 `owner_id=local-user` 的开发身份；字段保留用于后续认证接入，但不宣称生产级身份隔离。

### 4.3 主要字段

#### Thread

`thread_id`、`owner_id`、`title`、`next_message_seq`、`archived_at`、`created_at`、`updated_at`。

#### Message

`message_id`、`thread_id`、`seq`、`role`、`content`、`status`、`run_id`、`citations_json`、`idempotency_key`、`created_at`。用户消息状态为 `completed`；assistant 消息在最终事务提交前不存在或处于 `generating`，最终写入后为 `completed`。

#### Run

`run_id`、`thread_id`、`user_message_id`、`assistant_message_id`、`primary_task_id`、`status`、`snapshot_json`、`next_event_seq`、`cancel_requested_at`、`last_error_code`、`created_at`、`updated_at`。

#### Task

`task_id`、`kind`、`run_id`、`document_id`、`state`、`attempt`、`max_attempts`、`available_at`、`deadline_at`、`worker_id`、`generation`、`lease_expires_at`、`progress_json`、`last_error_code`、`last_error_message`、`created_at`、`updated_at`。

#### RunEvent

`event_id`、`run_id`、`seq`、`schema_version`、`type`、`payload_json`、`created_at`。payload 只能包含公开安全信息、关联 ID、分数、错误码和经过截断的展示片段，不保存 API Key、原始 credential 或不必要的完整 Prompt。

#### Document / Chunk

Document 保存 `document_id`、`owner_id`、`filename`、`extension`、`size_bytes`、`content_hash`、`storage_key`、`status`、`active_index_batch_id`、`last_error_code`、`created_at`、`updated_at`。Chunk 保存 `chunk_id`、`document_id`、`index_batch_id`、`seq`、`text`、`start_offset`、`end_offset`、`embedding`、`created_at`。`index_batch_id` 是 Demo 内部的候选索引批次标识，不是完整项目的公开 DocumentVersion。

## 5. 状态机与行为设计

### 5.1 Run 状态

```text
queued -> running -> succeeded
                 ├-> retry_waiting -> running
                 ├-> failed
                 └-> cancelled
```

- `queued`：Run 已创建，主 Task 尚未开始。
- `running`：Worker 已领取并正在执行索引/检索/生成步骤。
- `retry_waiting`：当前尝试遇到可重试错误，等待退避时间；Run 身份保持不变。
- `succeeded`：assistant Message 和 `run.succeeded` 在同一事务内提交。
- `failed`：不可重试错误或超过最大 attempt，保存稳定错误码和可诊断摘要。
- `cancelled`：用户明确请求取消；迟到成功不得覆盖。硬截止时间使用 `failed` 和稳定错误码 `TASK_DEADLINE_EXCEEDED`，不伪装成用户取消。

### 5.2 Task 状态与 lease

```text
queued -> leased -> running -> succeeded
       ^             ├-> retry_waiting -> queued
       |             ├-> cancelled
       |             └-> failed
       +-- lease expired / reclaim
```

领取使用 PostgreSQL 事务：

1. 在 `state=queued`、`available_at <= now()` 且未超过 `deadline_at` 的任务中使用 `FOR UPDATE SKIP LOCKED` 选择一条。
2. 原子更新为 `leased`，写入 `worker_id`、`generation = generation + 1`、`lease_expires_at` 和 `attempt = attempt + 1`。
3. 提交后，对于 `kind=run` 追加 `task.leased`；Worker 再进入 `running` 并追加 `run.started`。`kind=index_document` 不写入 RunEvent，而是通过 Document 状态和结构化日志记录索引生命周期。

所有续租、进度和终态写回都必须带 `task_id + worker_id + generation` 条件；条件更新影响行数为 0 时，Worker 视为已经失去 lease，停止后续写回。

### 5.3 Demo 默认调度参数

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `TASK_LEASE_TTL` | 30 秒 | 单次 lease 有效期 |
| `TASK_HEARTBEAT_INTERVAL` | 10 秒 | Worker 续租周期，必须小于 lease TTL |
| `TASK_MAX_ATTEMPTS` | 3 | 单个 Task 的最大尝试次数 |
| `TASK_RETRY_BASE_DELAY` | 2 秒 | 指数退避基数，Demo 使用 `base * 2^(attempt-1)` |
| `TASK_DEADLINE` | 10 分钟 | 单个 Task 的硬截止时间 |
| `WORKER_SHUTDOWN_GRACE` | 20 秒 | 停止领取后等待运行中任务的宽限时间 |
| `QUEUE_POLL_INTERVAL` | 1 秒 | PostgreSQL 无通知时的轮询间隔 |
| `SSE_POLL_INTERVAL` | 1 秒 | Redis 通知缺失时的 Event Journal 轮询间隔 |
| `RAG_TOP_K` | 5 | 默认召回数量 |
| `CHUNK_SIZE` | 800 字符 | 首版字符切分大小 |
| `CHUNK_OVERLAP` | 120 字符 | 首版切分重叠长度 |
| `VECTOR_DIMENSION` | 384 | pgvector 和 EmbeddingProvider 必须一致 |

### 5.4 创建 Run 的事务行为

`POST /api/v1/threads/{thread_id}/messages` 在一个数据库事务中完成：

1. 校验 Thread owner、正文长度和 `Idempotency-Key`。
2. 锁定 Thread，分配下一个 Message seq，写入用户 Message。
3. 创建不可变 `RunSnapshot`，写入 Run，状态为 `queued`。
4. 创建 `Task(kind=run)`，状态为 `queued`。
5. 追加 `run.created` 和 `task.queued`。
6. 提交事务后向 Redis 发布通知；发布失败不回滚数据库事务。

重复的 `Idempotency-Key` 返回原有用户 Message/Run，不重复创建任务；同一 Thread 的不同 Key 仍然是不同用户问题。

### 5.5 RAG 执行行为

Run Handler 固定按以下顺序执行：

1. 检查 Run 是否已取消、Task lease 是否仍有效、是否超过 deadline。
2. 读取 RunSnapshot，不能读取运行中变化的模型或检索配置。
3. 生成 query embedding，调用 `VectorStorePort.search` 返回 Top-K Chunk。
4. 追加 `retrieval.completed`，保存 document/chunk/location/score 等证据身份；不保存不必要的全文副本。
5. 将问题和召回证据交给 ModelProvider 的流式接口；每个增量追加 `answer.delta`，同时在 Worker 内累计最终正文。
6. 若无相关证据，生成明确的“没有足够证据回答”结果和空引用；若 Provider/向量库失败，走失败或重试路径，不得伪装成无结果。
7. 在一个事务中创建 assistant Message、写入 citations、将 Run/Task 置为 `succeeded`，追加 `message.completed` 和 `run.succeeded`。

Mock Provider 只用于离线验收，返回确定性文本和可重复增量；真实 Provider 由 OpenAI-compatible Adapter 实现，超时、5xx 和临时网络错误归类为可重试错误，参数错误、认证失败和不支持的模型归类为不可重试错误。

### 5.6 文档索引行为

1. API 接收 multipart 文件，限制扩展名为 `.txt`、`.md`、`.docx`，限制大小和 MIME，并将文件先写入临时 storage key。
2. 文件落盘成功后，再在事务中锁定 Document；如果已有未终态的 `Task(kind=index_document)`，返回该任务而不重复创建，否则生成新的 `index_batch_id`，创建 Document 和 `Task(kind=index_document)`；数据库失败时清理临时文件。
3. Index Handler 将 Document 置为 `indexing`，通过 ParserPort 解析为纯文本和基础位置。
4. Chunker 按 `CHUNK_SIZE/CHUNK_OVERLAP` 生成稳定 seq 和字符 offset，空文档或解析结果为空视为不可重试失败。
5. EmbeddingProvider 生成固定维度向量，写入 Chunk 和 pgvector；维度不一致直接失败，不做隐式截断或填充。
6. 全部 Chunk 写入成功后，在一个短事务中将 `active_index_batch_id` 切换到本批次、删除旧批次 Chunk、将 Document 置为 `indexed` 并结束 index Task。可重试失败清理本批次 Chunk、保持 Document 为 `indexing` 并进入 Task `retry_waiting`；不可重试失败或超过最大 attempt 时清理候选批次，Document 置为 `failed`，保留错误码。如果已有 active 批次，重建期间继续使用旧批次，失败时不污染旧索引。

Demo 文档状态为 `uploaded -> indexing -> indexed|failed`。检索只读取 Document 当前的 `active_index_batch_id`。本阶段不做用户可见的 DocumentVersion 审核/发布流程；完整项目再把内部批次提升为 candidate/published 版本边界。

### 5.7 取消、异常与恢复

| 情况 | 行为 |
| --- | --- |
| 用户取消 queued Run | API 事务将 Run/Task 置为 `cancelled`，追加 `run.cancelled`，发布通知。 |
| 用户取消 running Run | API 写入 `cancel_requested_at` 并尝试将 Task 置为 `cancelled`；Worker 在步骤边界停止，迟到模型结果不能提交。 |
| Worker 进程崩溃 | lease 到期后由其他 Worker 回收；generation 增加，旧 Worker 写回被拒绝。 |
| Worker 收到 SIGTERM | 设置停止标志，停止领取新任务；运行中任务在宽限期内完成或释放，超时后依靠 lease 回收。 |
| Provider 超时/临时 5xx | 追加错误事件，Task 进入 `retry_waiting`；达到最大 attempt 后 Run/Task `failed`。 |
| Provider 认证/参数错误 | 不重试，直接 `failed`，返回稳定错误码。 |
| 解析器不支持或文件损坏 | Document/Task 明确失败，不返回空索引。 |
| Redis 不可用 | API/Worker 继续以 PostgreSQL 为事实来源；SSE 使用数据库轮询，通知延迟增加但状态不丢失。 |
| PostgreSQL 不可用 | API 返回 503；Worker 暂停领取并退避重连，不在内存中宣称任务成功。 |
| pgvector 查询失败 | Run 显式失败或按 Provider 策略重试，不返回“无相关资料”。 |
| Task 超过 deadline | Task/Run 进入 `failed`，记录 `TASK_DEADLINE_EXCEEDED`；只有用户主动请求才进入 `cancelled`。 |
| SSE 断开 | 只停止观察；客户端使用最后 seq 调用补放接口，不触发 Run 取消。 |
| 旧 generation 完成回写 | 条件更新影响 0 行，记录结构化警告，不改变当前 Task/Run 终态。 |

## 6. 数据库与事务设计

### 6.1 表与索引

首个 Alembic 迁移创建以下表和必要索引：

| 表 | 关键索引/约束 |
| --- | --- |
| `threads` | PK `thread_id`；索引 `(owner_id, updated_at desc)` |
| `messages` | PK；唯一 `(thread_id, seq)`；唯一 `(thread_id, idempotency_key)`（非空） |
| `runs` | PK；唯一 `user_message_id`；索引 `(thread_id, created_at desc)`、`(status, updated_at)` |
| `tasks` | PK；检查 `kind` 与关联 ID；索引 `(state, available_at)`、`(lease_expires_at)`、`(run_id)` |
| `run_events` | PK；唯一 `(run_id, seq)`；索引 `(run_id, seq)` |
| `documents` | PK；索引 `(owner_id, created_at desc)`、`(status)`；content hash 普通索引 |
| `chunks` | PK；唯一 `(document_id, index_batch_id, seq)`；向量索引按 pgvector 可用能力建立 |

`CREATE EXTENSION IF NOT EXISTS vector` 放在初始迁移中。迁移失败时 `migrate` 退出非零，API/Worker 不进入 ready 状态。

### 6.2 事务边界

- **创建 Message/Run/Task**：同一事务，确保不会出现只有 Message 没有 Run 的半链路。
- **追加 Event**：锁定 Run 的 `next_event_seq`，分配 seq 并插入 Event；唯一约束作为最终保护。
- **领取 Task**：锁定候选任务并条件更新 lease；提交后才执行外部 Provider。
- **续租/进度/终态**：每次是独立短事务，带 generation 条件，不持有跨模型调用的长事务。
- **最终回答**：assistant Message、Run/Task 终态和 terminal Events 同一事务提交。
- **索引批次切换**：Demo 在同一 Document 内使用 `active_index_batch_id` 做短事务切换；检索只读 active 批次，完整项目的审核/发布和跨文档 candidate/publish 不属于本方案。

## 7. API 与 Event 契约

### 7.1 API 路径

正式路径统一使用 `/api/v1`：

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| `POST` | `/api/v1/threads` | 创建 Thread |
| `GET` | `/api/v1/threads` | 按更新时间倒序列出当前 owner Thread |
| `GET` | `/api/v1/threads/{thread_id}` | 读取 Thread、Message 和 Run 摘要 |
| `POST` | `/api/v1/threads/{thread_id}/archive` | 归档当前 owner 的 Thread |
| `POST` | `/api/v1/threads/{thread_id}/messages` | 追加用户 Message，幂等创建 Run/Task |
| `GET` | `/api/v1/runs/{run_id}` | 读取 Run、Task 和 assistant Message 摘要 |
| `GET` | `/api/v1/runs/{run_id}/events?after_seq=n` | 返回 `seq > n` 的事件 |
| `GET` | `/api/v1/runs/{run_id}/events/stream` | SSE 投影，支持 `Last-Event-ID` |
| `POST` | `/api/v1/runs/{run_id}/cancel` | 请求取消并返回当前 Run 状态 |
| `POST` | `/api/v1/documents` | 上传文档并创建登记记录 |
| `GET` | `/api/v1/documents` | 列出当前 owner 的文档和索引状态 |
| `POST` | `/api/v1/documents/{document_id}/index` | 对已登记文档创建/重试索引 Task |
| `GET` | `/health/live` | 进程存活检查 |
| `GET` | `/health/ready` | 数据库和迁移为硬依赖；Redis 通知与 Worker readiness 作为可降级状态返回 |

### 7.2 Event envelope

每条 RunEvent 使用同一 envelope：

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "run_id": "uuid",
  "seq": 12,
  "type": "retrieval.completed",
  "occurred_at": "2026-10-04T00:00:00Z",
  "data": {}
}
```

首版事件类型：`run.created`、`task.queued`、`task.leased`、`run.started`、`retrieval.completed`、`answer.delta`、`task.retry_scheduled`、`message.completed`、`run.succeeded`、`run.failed`、`run.cancelled`。

`RunEvent` 只服务 `kind=run` 的 Task。`answer.delta` 只传本次增量文本；`retrieval.completed` 只传证据身份和必要展示摘要；`message.completed` 传最终 Message ID 和 citations；terminal Event 传稳定错误码或最终状态。`index_document` Task 的状态变化只写 Document/Task 数据库字段和结构化日志，不新增第二套 Event Journal。

### 7.3 SSE 重连规则

1. 客户端连接时发送 `Last-Event-ID`，服务端将其解释为 `after_seq`。
2. 服务端先查询数据库补放 `seq > after_seq` 的 Event，再订阅 Redis 通知。
3. Redis 通知只作为“有新事件”的唤醒，不携带最终事实；收到通知后重新查询数据库。
4. 客户端按 `seq` 去重并只在收到 terminal Event 后结束 Run 观察。
5. 连接断开不写取消状态，重连前端也不创建新 Run。

## 8. 新增项目文件与目录

当前仓库以文档为主。本方案实施后，新增或生成的项目文件按以下目录组织。表中“阶段”对应第 9 节实施路线。

### 8.1 根目录与部署文件

| 路径 | 用途 | 使用阶段 |
| --- | --- | --- |
| `.env.example` | 开发配置模板，包含数据库、Redis、Provider、调度和 RAG 参数，不放 Secret | 阶段 1 |
| `.gitignore` | 排除 `.env`、上传目录、构建产物、缓存和本地数据库文件 | 阶段 1 |
| `pyproject.toml` | Python 依赖、Ruff、mypy、pytest 和脚本入口 | 阶段 1 |
| `uv.lock` | Python 锁定依赖图，由 uv 生成 | 阶段 1 后生成 |
| `docker-compose.yml` | 编排 frontend/api/worker/migrate/postgres/redis、网络、卷和健康检查 | 阶段 1 |
| `docker/api/Dockerfile` | 构建 API/Worker 共用后端镜像 | 阶段 1 |
| `docker/frontend/Dockerfile` | 构建前端开发/静态资源镜像 | 阶段 1、阶段 6 |
| `README.md` | 启动、配置、测试和 Demo 验收入口 | 阶段 7 |

### 8.2 后端目录

| 路径 | 用途 | 使用阶段 |
| --- | --- | --- |
| `backend/app.py` | 创建 FastAPI 应用、挂载路由、中间件和生命周期 | 阶段 1、阶段 2 |
| `backend/config.py` | Pydantic Settings、默认参数和 Secret 引用 | 阶段 1 |
| `backend/logging.py` | 结构化日志和关联 ID 字段 | 阶段 1、阶段 3 |
| `backend/api/dependencies.py` | DB session、owner context、应用服务依赖注入 | 阶段 2 |
| `backend/api/routes/health.py` | live/ready 检查 | 阶段 1 |
| `backend/api/routes/threads.py` | Thread、Message 创建/读取路由 | 阶段 2 |
| `backend/api/routes/runs.py` | Run 状态、Event 补放、SSE、取消路由 | 阶段 2、阶段 3 |
| `backend/api/routes/documents.py` | 文档上传、列表和索引路由 | 阶段 4 |
| `backend/api/schemas/threads.py` | Thread/Message 请求响应模型 | 阶段 2 |
| `backend/api/schemas/runs.py` | Run/Task/Event 查询模型 | 阶段 2、阶段 3 |
| `backend/api/schemas/documents.py` | Document/Chunk/索引状态模型 | 阶段 4 |
| `backend/domain/enums.py` | Role、RunState、TaskState、TaskKind、DocumentState、EventType | 阶段 2 |
| `backend/domain/entities.py` | 与持久化无关的领域实体和不可变快照 | 阶段 2 |
| `backend/domain/ports.py` | Queue、Event、Provider、Parser、VectorStore、FileStorage Port | 阶段 2、阶段 3、阶段 4 |
| `backend/application/errors.py` | 可重试/不可重试错误和对外稳定错误码 | 阶段 2、阶段 3 |
| `backend/application/threads.py` | Thread 和 Message 用例、幂等事务 | 阶段 2 |
| `backend/application/runs.py` | Run 创建、取消、状态查询和 Event 读取 | 阶段 2、阶段 3 |
| `backend/application/tasks.py` | Task 创建、领取、续租、重试、终态写回 | 阶段 3 |
| `backend/application/documents.py` | 上传登记、索引任务和文档状态用例 | 阶段 4 |
| `backend/db/session.py` | SQLAlchemy Engine、AsyncSession 和事务工厂 | 阶段 1 |
| `backend/db/models.py` | Thread/Message/Run/Task/Event/Document/Chunk ORM 模型 | 阶段 2、阶段 4 |
| `backend/db/base.py` | Declarative Base 和 metadata 导出 | 阶段 1 |
| `backend/infrastructure/db/repositories.py` | SQLAlchemy Repository 实现 | 阶段 2、阶段 3、阶段 4 |
| `backend/infrastructure/db/unit_of_work.py` | 应用用例的事务边界实现 | 阶段 2 |
| `backend/infrastructure/queue/postgres_queue.py` | PostgreSQL `SKIP LOCKED` 领取、lease、回收和 retry | 阶段 3 |
| `backend/infrastructure/events/journal.py` | Event Journal 追加、补放和 terminal 事务 | 阶段 2、阶段 3 |
| `backend/infrastructure/events/redis_notifier.py` | Redis publish/subscribe 通知 | 阶段 3 |
| `backend/infrastructure/storage/local_files.py` | 共享上传卷的随机 key、临时文件和清理 | 阶段 4 |
| `backend/infrastructure/rag/parsers.py` | txt/md/docx Parser Adapter | 阶段 4 |
| `backend/infrastructure/rag/chunker.py` | 固定参数的字符切分和 offset 计算 | 阶段 4 |
| `backend/infrastructure/rag/pgvector_store.py` | pgvector 写入和 Top-K 查询 | 阶段 4、阶段 5 |
| `backend/infrastructure/providers/mock.py` | 确定性 Embedding/Model Provider | 阶段 4、阶段 5、测试 |
| `backend/infrastructure/providers/openai_compatible.py` | 可选真实模型和 Embedding Provider | 阶段 5 |
| `backend/workers/main.py` | `python -m backend.workers.main` 入口 | 阶段 3 |
| `backend/workers/runtime.py` | claim loop、heartbeat、shutdown grace 和 handler 分发 | 阶段 3 |
| `backend/workers/handlers/run_handler.py` | RAG Run 执行顺序、事件和最终回答事务 | 阶段 5 |
| `backend/workers/handlers/index_handler.py` | 文档解析、切分、Embedding 和索引 Task | 阶段 4 |

### 8.3 数据库、契约与前端目录

| 路径 | 用途 | 使用阶段 |
| --- | --- | --- |
| `alembic.ini` | Alembic 配置 | 阶段 1 |
| `migrations/env.py` | 迁移 Engine 和 metadata 配置 | 阶段 1 |
| `migrations/versions/0001_initial_demo.py` | 启用 pgvector 并创建首版业务表、索引和约束 | 阶段 1、阶段 2 |
| `contracts/README.md` | 契约版本、变更和生成流程说明 | 阶段 2 |
| `contracts/run_event_v1.json` | Event envelope 和首版事件类型 JSON Schema | 阶段 2、阶段 3 |
| `frontend/package.json` | Vue 依赖、开发、检查和构建脚本 | 阶段 1、阶段 6 |
| `frontend/tsconfig.json` | TypeScript 编译配置 | 阶段 1、阶段 6 |
| `frontend/vite.config.ts` | Vite 端口、API 代理和构建配置 | 阶段 1、阶段 6 |
| `frontend/src/main.ts` | Vue 应用入口 | 阶段 6 |
| `frontend/src/App.vue` | 根布局和路由出口 | 阶段 6 |
| `frontend/src/router/index.ts` | Workspace 路由 | 阶段 6 |
| `frontend/src/api/http.ts` | Axios/fetch client、错误和超时处理 | 阶段 6 |
| `frontend/src/api/threads.ts` | Thread/Message API client | 阶段 6 |
| `frontend/src/api/runs.ts` | Run/Event/Cancel API client | 阶段 6 |
| `frontend/src/api/documents.ts` | 上传和索引状态 API client | 阶段 6 |
| `frontend/src/events/run-event-stream.ts` | SSE 连接、Last-Event-ID、补放和 seq 去重 | 阶段 6 |
| `frontend/src/stores/thread.ts` | Thread/Message 状态投影 | 阶段 6 |
| `frontend/src/stores/run.ts` | Run/Event/连接状态投影 | 阶段 6 |
| `frontend/src/stores/documents.ts` | 文档和索引状态投影 | 阶段 6 |
| `frontend/src/types/api.ts` | API 与 Event 类型；由契约或 OpenAPI 同步 | 阶段 6 |
| `frontend/src/pages/WorkspacePage.vue` | Demo 主工作台 | 阶段 6 |
| `frontend/src/components/ThreadList.vue` | Thread 列表和创建入口 | 阶段 6 |
| `frontend/src/components/MessageTimeline.vue` | 用户/assistant 消息和 Markdown 清洗展示 | 阶段 6 |
| `frontend/src/components/RunTimeline.vue` | Event 时间线、状态、取消和重连 | 阶段 6 |
| `frontend/src/components/DocumentUploader.vue` | 文档上传和索引状态 | 阶段 6 |

### 8.4 测试与运维文档

| 路径 | 用途 | 使用阶段 |
| --- | --- | --- |
| `tests/conftest.py` | 测试数据库、Mock Provider 和应用 fixture | 阶段 2 |
| `tests/unit/test_state_machine.py` | Run/Task/Document 合法状态转移 | 阶段 2、阶段 3、阶段 4 |
| `tests/unit/test_event_journal.py` | seq 单调、补放、terminal 事务和 payload 脱敏 | 阶段 2、阶段 3 |
| `tests/unit/test_lease.py` | 并发领取、续租、过期回收和 stale generation | 阶段 3 |
| `tests/unit/test_rag_pipeline.py` | 解析、切分、Embedding、召回、引用和错误分类 | 阶段 4、阶段 5 |
| `tests/api/test_threads.py` | Thread/Message API 和幂等 | 阶段 2 |
| `tests/api/test_runs.py` | Run、Event、SSE、取消 API | 阶段 2、阶段 3 |
| `tests/api/test_documents.py` | 上传、扩展名/MIME/大小和索引 API | 阶段 4 |
| `tests/integration/test_worker_recovery.py` | Worker 崩溃、租约接管、重启和优雅停机 | 阶段 3、阶段 7 |
| `tests/integration/test_compose_smoke.py` | Compose 健康检查和主链路 | 阶段 7 |
| `frontend/src/**/*.spec.ts` | store、API client、SSE 去重和重连单测 | 阶段 6 |
| `frontend/e2e/demo.spec.ts` | 浏览器创建 Thread、上传、提问、引用和刷新恢复 | 阶段 7 |
| `docs/runbooks/demo-development.md` | 本地启动、迁移、日志、故障和验收命令 | 阶段 7 |

`frontend/src/types/api.ts` 及其他生成文件不能手工绕过契约修改；若后续采用 OpenAPI 类型生成器，应将生成命令记录在 `frontend/package.json` 和 `contracts/README.md`。

## 9. 分阶段实施路线

每个阶段必须通过本阶段测试和退出条件后，才能开始下一阶段。阶段之间按依赖顺序实施，不能先把前端页面做成另一套未落库的临时状态。

### 阶段 1：工程骨架、配置与 Compose

**新增范围**：根目录部署文件、`backend/app.py`、配置/日志、数据库连接、前后端空壳、Alembic、健康检查。

**工作内容**：

- 建立 Python/uv 和 frontend/npm 工程清单。
- 创建 PostgreSQL pgvector、Redis、API、Worker、Frontend、Migrate 服务和 named volumes。
- 配置 `.env.example`，固定本方案第 5.3 节默认值。
- API 提供 `/health/live` 和 `/health/ready`；Worker 提供启动日志和 readiness 标记。
- 完成 `0001_initial_demo.py` 的迁移入口和 `vector` 扩展检查。

**测试与退出条件**：`docker compose config` 成功；全新环境可启动依赖；live/ready 行为区分；迁移服务成功退出；API/Worker 能连接 PostgreSQL 和 Redis。

### 阶段 2：领域模型、迁移、契约和 Thread/Run API

**新增范围**：domain、db/models、repositories、unit of work、Thread/Run routes/schemas、Event Journal、`run_event_v1.json` 和对应单测/API 测试。

**工作内容**：

- 创建 `threads/messages/runs/tasks/run_events/documents/chunks` 表和约束。
- 实现 Thread 创建/列表/读取/归档、Message 创建、Run Snapshot、Run/Task 初始事件。
- 实现 Event seq 锁定分配和 `after_seq` 查询。
- 为 Message POST 加入 `Idempotency-Key`。
- 实现 Run 查询、Event 补放和取消 API；SSE 先使用数据库轮询版本，Redis 唤醒在阶段 3 接入。

**测试与退出条件**：创建一次 Message 必须同时得到 Run、Task、初始 Events；重复 Idempotency-Key 不重复创建；并发追加 Message/Event 不产生重复 seq；取消不会把 SSE 断开当成取消。

### 阶段 3：PostgreSQL Task Queue、lease、heartbeat 和 Worker

**新增范围**：`application/tasks.py`、`postgres_queue.py`、`runtime.py`、`main.py`、Redis notifier、lease/恢复测试。

**工作内容**：

- 使用 `SKIP LOCKED` 实现 claim；实现 generation、lease TTL、heartbeat、deadline、retry backoff 和过期回收。
- Worker 按 `Task.kind` 分发 handler；阶段 3 先接入可测试的最小 `run` handler 骨架。
- 实现 SIGTERM 停止领取、宽限期等待、lease 回收和 stale write rejection。
- Redis 发布只负责唤醒；数据库仍是任务和事件事实来源。

**测试与退出条件**：两个 Worker 竞争只能一个领取；旧 generation 续租/完成被拒绝；Worker 进程终止后任务可被重新领取；超过最大 attempt 进入 failed；优雅停机不再领取新任务。

### 阶段 4：文本文档登记、解析、切分、Embedding 和 pgvector

**新增范围**：文档路由/用例、local file storage、Parser/Chunker/Embedding/VectorStore Adapter、index handler、Document API 和 RAG 单测。

**工作内容**：

- 实现 txt、md、docx 的统一解析接口，记录扩展名、大小、hash、storage key 和位置。
- 创建 `index_document` Task，执行 `uploaded -> indexing -> indexed|failed`。
- 使用确定性 Mock Embedding，固定 384 维；真实 Embedding Adapter 需要在写入前验证维度。
- 以 chunk seq 和 offset 保存可追踪证据；索引失败清理本次新 Chunk。

**测试与退出条件**：三种支持格式均可索引；不支持扩展名、超限、损坏文件有明确错误；空文档不生成空索引；pgvector Top-K 返回 document/chunk/location/score；Redis 不可用不影响索引事实。

### 阶段 5：RAG Run Handler、流式回答和引用

**新增范围**：`run_handler.py`、Mock/OpenAI-compatible Provider、retrieval 逻辑、`answer.delta`/terminal Events、Run 集成测试。

**工作内容**：

- 按第 5.5 节固定的检索/生成顺序执行。
- 真实 Provider 和 Mock Provider 实现相同的 `ModelProvider`/`EmbeddingProvider` 接口。
- 在 Event Journal 中追加检索证据和回答增量；最终回答事务写入 assistant Message、citations 和 terminal Events。
- 区分无证据、Provider 故障、向量库故障、取消和超时。

**测试与退出条件**：无外部 Key 仍能完成完整 Run；回答引用只来自实际召回 Chunk；模型超时按策略重试；基础设施故障不返回无证据；取消和 stale generation 不产生错误的成功消息。

### 阶段 6：Vue Demo 工作台

**新增范围**：frontend API client、stores、SSE stream、Workspace 页面、Thread/Message/Run/Document 组件和前端单测。

**工作内容**：

- 实现 Thread 列表/创建、消息输入、Run 状态和取消。
- 实现文档上传、索引状态、引用展开和 Markdown 清洗。
- SSE 连接先补放后订阅 Redis 唤醒；按 seq 去重；刷新后从 API 恢复事实状态。
- 不在 Pinia 中持久化 Run 终态，不把本地状态当成事实来源。

**测试与退出条件**：`vue-tsc`、ESLint、Vitest 通过；断线重连不重复显示事件；刷新可恢复 Thread/Message/Run；前端不展示 Secret、宿主路径或未清洗 HTML。

### 阶段 7：集成验收、Compose Smoke 和文档

**新增范围**：集成/端到端测试、README、开发 Runbook、必要的脚本和质量门禁配置。

**工作内容**：

- 执行全新 Compose 启动、迁移、上传文档、索引、提问、SSE、刷新、取消和重启恢复。
- 注入 Worker 崩溃、Redis 不可用、模型超时、旧 generation 回写和数据库短暂不可用。
- 对照 Demo PRD 的 F-TH、F-RUN、F-WK、F-RAG 和验收标准逐条记录结果。
- 更新 README 和 Runbook；未运行的检查写入交付说明，不宣称通过。

**退出条件**：第 10 节的 PRD 追踪表全部有测试或可复现的手工证据；后端/前端质量命令通过；Compose smoke 通过；不存在未决的状态、对象、目录或错误语义冲突。

## 10. PRD 需求追踪与测试门禁

| PRD 范围 | 方案落点 | 主要证据 |
| --- | --- | --- |
| F-TH-01～04 | `threads.py`、`threads`/`messages`、Thread store | `tests/api/test_threads.py`、`demo.spec.ts` |
| F-RUN-01～06 | `runs.py`、Run Snapshot、Event Journal、SSE/取消 | `test_event_journal.py`、`tests/api/test_runs.py` |
| F-WK-01～07 | `postgres_queue.py`、`runtime.py`、lease 字段 | `test_lease.py`、`test_worker_recovery.py` |
| F-RAG-01～04 | Document API、Parser、Chunker、Embedding、Index Handler | `test_documents.py`、`test_rag_pipeline.py` |
| F-RAG-05～08 | `pgvector_store.py`、`run_handler.py`、Provider 错误分类 | `test_rag_pipeline.py`、Run 集成测试 |
| 前端最小工作台 | Workspace、Thread/Run/Document components/stores | Vitest、Playwright、Compose smoke |

### 10.1 后端质量命令

```bash
uv sync --dev --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy backend
docker compose config
docker compose up -d --build
docker compose ps
```

### 10.2 前端质量命令

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run test:unit
npm run build
npm run test:e2e
```

具体脚本名称以阶段 1 创建的 `package.json` 和 `pyproject.toml` 为准；没有执行的命令不能在完成报告中写成通过。

## 11. 风险、取舍与回滚策略

### 11.1 PostgreSQL 作为 Demo 队列

**取舍**：牺牲高吞吐专用 MQ 的吞吐上限，换取任务状态、lease、事件和业务事务位于同一事实存储，便于验证 PRD1 的核心语义。

**回滚/演进**：所有 Worker 只依赖 `QueuePort`；后续引入 Redis Streams/NATS/RabbitMQ 时新增 Adapter 和部署 profile，不改 Task/Run/Event 的领域对象。

### 11.2 pgvector 作为 Demo 向量存储

**取舍**：避免 Demo 直接运行 Milvus 及其依赖，降低首次部署复杂度；不追求大规模检索性能。

**回滚/演进**：`VectorStorePort` 只返回统一 Evidence DTO；Milvus Adapter 可以在完整项目中替换，不把 pgvector SQL 传播到 application/domain。

### 11.3 Redis 仅做通知

**取舍**：Redis 宕机只造成通知延迟，不破坏事实；SSE/Worker 通过数据库轮询继续工作。

**回滚/演进**：可替换 NotificationPort；不允许把 Redis payload 当成 terminal Event 或任务状态。

### 11.4 Mock Provider 与真实 Provider 并存

**取舍**：自动化测试不依赖外部 Key、网络和模型稳定性；真实 Provider 仍能按相同协议接入。

**限制**：Mock 结果不能作为 RAG 效果证明；它只证明任务、事件、引用身份和错误语义正确。

### 11.5 失败和重试

所有可重试错误必须是结构化错误类型，且只由 Task Runtime 负责 retry。Provider SDK 的隐式重试关闭或设为 0，避免 API、SDK、Worker 三层乘法重试。数据库事务失败可重试事务本身，但不能重复提交终态；通过唯一约束和 generation 条件保证幂等。

## 12. 方案批准后的实施规则

1. 先按第 9 节阶段顺序实施，不跨阶段创建额外的第二套事实来源。
2. 每个阶段开始前，先为本阶段不变量写失败测试，再实现最小通过版本。
3. 新增字段、Event 或 API 先更新 `contracts/`、ORM 迁移和对应测试，再修改调用方。
4. 任何需要改变 Thread/Message/Run/Event 语义的需求，先更新 Demo PRD 或新增 ADR；不能在代码中用隐藏 fallback 解决。
5. 阶段 7 完成前，不宣称 Demo 达到完整项目的认证、工具、版本化知识库或生产 SLO。

## 13. 方案审批清单

本方案在交付前按以下项目进行整体校审：

- [x] 文件和目录结构覆盖 API、Worker、前端、迁移、契约、测试、部署和 Runbook。
- [x] 每个主要文件/目录说明了职责和使用阶段。
- [x] Thread、Message、Run、RunSnapshot、Task、RunEvent、Document、Chunk、Citation 的含义、职责和关系已明确。
- [x] Task 与 Run 的重试状态语义已固定，未混淆任务尝试与会话执行身份。
- [x] lease、generation、heartbeat、过期回收、优雅停机、取消和 stale write 行为已明确。
- [x] Redis、PostgreSQL、pgvector、模型和解析器的故障行为已明确，未把基础设施错误伪装成无结果。
- [x] API、SSE、Event Journal、事务边界和前端恢复规则相互一致。
- [x] 实施阶段按依赖顺序排列，并为每阶段给出文件范围、测试和退出条件。
- [x] 方案未扩大 Demo PRD 的非目标范围，也未提前引入完整项目的生产能力。

**审批结论**：本方案作为 Demo 的实施基线；后续代码实现必须以本方案和 Demo PRD 为共同依据。若实施中发现需要改变对象关系、状态机、事实来源或正式 API，应先暂停相关实现，更新本 ADR/PRD 并重新校审。
