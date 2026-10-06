# PR-001：SesRAG 项目 Demo 实施结果

**对应 PRD**：[`docs/prd/001-SesRAG-项目Demo-PRD.md`](../prd/001-SesRAG-项目Demo-PRD.md)
**对应 ADR**：[`docs/adr/001-sesrag-demo-implementation-plan.md`](../adr/001-sesrag-demo-implementation-plan.md)
**版本**：v0.1
**日期**：2026-10-05
**状态**：已实施，调研完成；存在待补验证项

## 1. 实施范围

已完成 Demo 的前后端分离和 Docker Compose 纵向链路：Thread/Message/Run、PostgreSQL 持久 Task、Worker lease/heartbeat/retry/优雅停机、Run Event Journal 与 SSE 投影、txt/md/docx 文档索引、pgvector 兼容存储、Mock/可选 OpenAI-compatible Provider，以及 Vue 工作台。

主要实现文件和目录包括 `backend/`、`frontend/`、`migrations/`、`contracts/`、`tests/`、`docker/`、`docker-compose.yml`、`.env.example` 和 `docs/runbooks/demo-development.md`。

## 2. 结果与差异

- PostgreSQL 保存会话、任务、事件、文档和 Chunk 事实；Redis 只负责通知和 readiness。
- Demo 使用内部 `index_batch` 和 `active_index_batch_id`，尚未提供完整项目的公开 `DocumentVersion` 审核、发布和回滚流程，符合 PRD 非目标。
- Demo 默认单 owner、Mock Provider 和本地上传卷，不包含生产认证、RBAC、多租户和工具沙箱。

## 3. 验证证据

实施提交中保留了后端单元/API/SQLite 集成测试、Ruff、mypy、前端检查、Compose 配置和主链路验证记录；本次调研又基于当前分支重新执行了可用的本地检查。历史验收记录见 [`docs/test/001-SesRAG-项目Demo-test.md`](../test/001-SesRAG-项目Demo-test.md)，本次复核的实际结果和限制见第 10 节。

## 4. 未完成事项

完整项目 PRD 的 PRD1～PRD4 能力仍需按路线拆分实施；本结果不代表生产认证、可靠 MQ、工具系统或知识库版本化已经交付。

## 5. 调研范围、依据与判定口径

### 5.1 调研范围

本次调研针对分支 `sesrag_v0.1` 的当前提交 `0d7a61c`，核对以下内容：

- PRD 需求：`docs/prd/001-SesRAG-项目Demo-PRD.md` 的 F-TH、F-RUN、F-WK、F-RAG、前端工作台、非功能需求和验收标准。
- 实施方案：`docs/adr/001-sesrag-demo-implementation-plan.md` 的对象模型、状态机、事务边界、异常行为、文件路线和测试门禁。
- 当前实现：`backend/`、`frontend/`、`migrations/`、`contracts/`、`docker/`、`docker-compose.yml`、`tests/` 以及 `.env.example`。
- 配套说明：`README.md`、`docs/runbooks/demo-development.md`、`docs/test/001-SesRAG-项目Demo-test.md` 和 `contracts/run_event_v1.json`。

实现提交相对于此前仅有文档的基线新增或变更 108 个文件，约 6,348 行新增、177 行删除；其中后端、前端、迁移、契约、部署和测试文件主要为新增，原有 PRD 被重命名为编号化文件，`AGENTS.md` 和当前任务说明发生了文档更新。提交证据来自 `git show --stat 0d7a61c` 和 `git show --name-status 0d7a61c`。

### 5.2 判定口径

| 标记 | 含义 |
| --- | --- |
| **已落地** | 代码、配置或契约中已有对应机制；不等于所有异常分支都经过自动化验证。 |
| **已验证** | 有当前测试或本次可重复命令的直接证据。 |
| **部分落地** | 主路径存在，但与 PRD/ADR 的完整行为、边界或前端恢复要求仍有差异。 |
| **待验证/缺口** | 代码可能有初步处理，但当前没有足够测试、依赖环境不可用，或实现与方案不一致。 |
| **非 Demo 范围** | 完整项目 PRD 的后续能力，当前不应按 Demo 缺陷处理。 |

后文严格区分“代码存在”“测试覆盖”和“与方案完全一致”，方便后续直接转化为测试点和测试用例。

## 6. 实际工程变动与文件职责

### 6.1 根目录、部署和配置

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `.env.example`、`pyproject.toml` | 新增 | 分别提供运行参数模板和 Python 依赖/pytest/Ruff/mypy 配置。参数覆盖数据库、Redis、上传目录、lease、重试、deadline、RAG 和 Provider。 |
| `docker-compose.yml` | 新增 | 编排 `postgres`、`redis`、`migrate`、`api`、`worker`、`frontend`，共享 PostgreSQL 与 uploads volume，并配置服务依赖和健康检查。Compose 结构符合 Demo 目标，但当前文件把数据库密码写死为 Demo 默认值，且 `api/worker` 依赖 Redis healthy，Redis 完全不可用时不会按代码降级逻辑启动。 |
| `docker/api/Dockerfile` | 新增 | 以 Python 3.12 构建 API/Worker 共用镜像，安装项目依赖并复制 backend/migrations。 |
| `docker/frontend/Dockerfile`、`frontend/package.json`、`package-lock.json` | 新增 | 构建 Vue/Vite 前端开发容器。当前脚本只有 `dev`、`build`、`typecheck`、`lint`，没有 ADR 预期的 Vitest、Playwright 或独立 ESLint 脚本。 |
| `alembic.ini`、`migrations/env.py`、`migrations/versions/0001_initial_demo.py` | 新增 | 提供首版迁移入口，启用 pgvector 并通过 SQLAlchemy metadata 创建业务表。迁移具备启动能力，但没有为每个约束写独立迁移测试；当前 Ruff 对 `migrations/env.py` 和首版迁移报告格式/导入问题。 |

### 6.2 后端 API、应用层、领域和数据库

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `backend/app.py`、`backend/config.py`、`backend/api/dependencies.py` | 新增 | 创建 FastAPI、异步数据库 session、Redis notifier、上传目录和应用生命周期；`ApplicationError` 映射为稳定 JSON 错误。 |
| `backend/api/routes/threads.py`、`runs.py`、`documents.py`、`health.py` | 新增 | 提供 `/api/v1` Thread/Message、Run/Event/SSE/取消、文档上传/索引和 live/ready 路由。业务编排主要转交 application 层，没有把长时间模型任务放在 HTTP 请求中。 |
| `backend/api/schemas/` | 新增 | 定义 Thread/Message、Run/Event 和 Document 响应/请求结构；前端 `frontend/src/types/api.ts` 当前是手工同步，不是生成文件。 |
| `backend/application/threads.py` | 新增 | 创建 Thread、列表/归档、按 owner 读取；在锁定 Thread 后递增 Message seq，在同一事务创建用户 Message、Run、Task 和 `run.created`/`task.queued`。支持 `Idempotency-Key`，但 `messages` 表只有普通索引，没有 ADR 规划的非空唯一约束，并发重复幂等仍需补测。 |
| `backend/application/runs.py` | 新增 | 读取 Run/Task、按 `after_seq` 查询 Event、处理取消。取消会把 Run 设为 `cancelled`，尝试把非终态 Task 设为 `cancelled`，并追加 `run.cancelled`；SSE 断开不会调用此路径。 |
| `backend/application/documents.py` | 新增 | 校验扩展名、大小和 MIME，先把文件保存到共享 storage，再提交 Document 与 `index_document` Task；数据库提交失败时清理文件。支持重试索引时复用活动中的索引任务。 |
| `backend/application/errors.py` | 新增 | 定义 `ApplicationError`、`TransientTaskError`、`PermanentTaskError`。后两个类型已定义，但 Run Handler 当前没有按 `retryable` 属性进行完整分类，需在测试和后续实现中关注。 |
| `backend/domain/enums.py`、`entities.py` | 新增 | 定义 Run/Task/Document/Message 状态和纯函数状态转移、`ChunkDraft`。状态转移函数有单测，但生产写回代码仍有直接赋值，未统一通过转移函数强制状态机。 |
| `backend/db/models.py`、`db/base.py`、`db/session.py` | 新增 | 持久化 `ThreadModel`、`MessageModel`、`RunModel`、`TaskModel`、`RunEventModel`、`DocumentModel`、`ChunkModel`，并为 PostgreSQL 使用 pgvector、SQLite 测试使用 JSON。模型具备大部分领域字段，但没有 ADR 中计划的复合唯一幂等约束、显式检查约束和独立 repository/unit-of-work 层。 |

### 6.3 基础设施、Worker 和 RAG

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `backend/infrastructure/events/journal.py` | 新增 | 锁定 Run 的 `next_event_seq`，追加不可变 RunEvent，并按 seq 补放。终态 assistant Message、Run/Task 状态和 terminal Event 在 Run Handler 的同一事务提交。 |
| `backend/infrastructure/events/redis_notifier.py` | 新增 | Redis 只发布 Run 唤醒、维护 Worker readiness key；Redis 不可用时连接对象为空，SSE 服务端实际继续使用数据库轮询。当前 SSE 路由没有真正订阅 Redis，因此行为是“轮询降级实现”，不是 ADR 描述的通知唤醒实现。 |
| `backend/infrastructure/queue/postgres_queue.py` | 新增 | 用 `FOR UPDATE SKIP LOCKED` 领取 queued Task，递增 generation/attempt，设置 lease；续租、running、成功、retry 和过期回收均带 worker/generation 条件。当前没有单独写入 `task.leased` Event，且 deadline 只在领取筛选时检查。 |
| `backend/workers/runtime.py`、`workers/main.py` | 新增 | Worker 生成稳定 `worker_id`，执行 claim loop、readiness、heartbeat 和按 Task kind 分发 handler。收到 SIGTERM 后停止新领取，但当前 loop 对运行中任务的宽限等待只 `sleep(min(grace, 1))`，且停止标志会让 lease heartbeat 提前退出；完整优雅停机语义仍需补强和实测。 |
| `backend/workers/handlers/run_handler.py` | 新增 | 按 Embedding -> active batch 检索 -> `retrieval.completed` -> ModelProvider 增量 -> `answer.delta` -> assistant Message/citations/terminal Event 顺序执行；在开始、每个增量和最终提交前检查取消或 generation。 |
| `backend/workers/handlers/index_handler.py` | 新增 | 执行 `uploaded -> indexing -> indexed|failed`，解析、切分、Embedding，使用 batch id 写 Chunk，完成后切换 `active_index_batch_id` 并删除旧批次。事务回滚可避免半批次 Chunk 提交，但未有完整的旧活动批次失败恢复测试。 |
| `backend/infrastructure/rag/parsers.py`、`chunker.py`、`pgvector_store.py` | 新增 | 支持 txt/md/docx；按字符大小和 overlap 保存 seq/offset；检索返回 Evidence。当前 PostgreSQL pgvector 主要作为向量字段存储，Demo 规模下在 Python 中计算 cosine 并排序，不是数据库侧 ANN/BM25/RRF 检索。 |
| `backend/infrastructure/storage/local_files.py` | 新增 | 使用 `documents/<document_id>/source<extension>` storage key，临时文件替换落盘，并校验读取路径不能逃逸上传根目录。 |
| `backend/infrastructure/providers/mock.py`、`openai_compatible.py` | 新增 | Mock Embedding/Model 用于离线确定性验收；OpenAI-compatible Provider 使用 HTTP 请求。真实 Provider 的认证失败、参数错误、超时和 5xx 当前没有完整错误码映射，通用异常会走 `RUN_FAILED`/`INDEX_FAILED` 重试路径，和 ADR 计划的可重试/不可重试区分仍有差异。 |

### 6.4 前端、契约和测试

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `frontend/src/pages/WorkspacePage.vue`、`components/` | 新增 | 提供 Thread 列表、消息输入、Run 时间线、取消、文档上传、引用展示和 Markdown 清洗。主工作台结构已经存在，但没有独立浏览器 E2E 测试。 |
| `frontend/src/api/`、`events/run-event-stream.ts` | 新增 | 封装 Thread/Run/Document API，使用 EventSource 接收事件并按 `seq` 在 Run store 去重。当前 `openRunStream` 同时打开 SSE 和异步 `replayEvents`，且 answer delta 的 UI 追加没有独立去重；这是后续重点测试风险。 |
| `frontend/src/stores/`、`types/api.ts` | 新增 | Pinia 保存事实投影和 API 类型。刷新时会恢复 Thread/Message/Run 摘要和文档列表，但不会自动恢复最近 Run 的事件时间线；运行结束后的 assistant Message 也没有在 `message.completed` 后自动重新读取 Thread。 |
| `contracts/run_event_v1.json`、`contracts/README.md` | 新增 | 固定 Event envelope、seq 和事件类型；当前代码实际没有生成 `task.leased` 事件，契约枚举与事件生产结果需在后续契约测试中校对。 |
| `tests/` | 新增 | 共 16 项 Python 测试，覆盖 API 主链路、Mock Worker、文档索引/召回、lease 回收、状态机、切分、解析器、Mock Provider 和 retry delay。没有 `tests/conftest.py`、独立 SSE API 测试、并发 claim 测试、完整错误分类测试、前端单测或 Playwright 测试文件。 |

## 7. PRD 功能落地核对

### 7.1 Thread 与 Message（F-TH）

| 需求 | 当前实现与文件 | 调研结论和后续测试关注点 |
| --- | --- | --- |
| F-TH-01 创建、列出、读取、归档 | `backend/api/routes/threads.py`；`backend/application/threads.py`；`ThreadModel` | 主路径已落地，API 测试覆盖创建和归档；列表、详情、owner 隔离和更新时间排序没有完整自动化覆盖。 |
| F-TH-02 追加用户 Message | `create_message_run` 锁定 Thread、递增 `next_message_seq`，`messages(thread_id, seq)` 有唯一约束 | 已落地；需补并发两个请求、不同幂等键和数据库唯一约束冲突测试。 |
| F-TH-03 assistant Message | `backend/workers/handlers/run_handler.py` 在最终事务创建 assistant Message，保存 citations 和 Run ID | 后端持久化主路径已落地；前端实时显示存在缺口：回答增量到达时 assistant Message 可能尚未在 `threadStore` 中，终态事件也未触发重新读取 Thread。 |
| F-TH-04 刷新恢复 | `get_thread_detail` 返回 Messages/Runs；`WorkspacePage.bootstrap` 调用 `loadThreads` | 服务端事实恢复已落地；前端只恢复会话摘要和消息，不自动恢复当前 Run/Event 时间线，需 E2E 验证并补齐。 |

### 7.2 Run、Task 与 Event（F-RUN）

| 需求 | 当前实现与文件 | 调研结论和后续测试关注点 |
| --- | --- | --- |
| F-RUN-01 每次问题创建 Run | `create_message_run` 同事务创建用户 Message、Run、RunSnapshot、Task 和初始 Events | 已落地；`tests/api/test_core_api.py` 验证首次创建和 Idempotency-Key 重复返回。并发幂等仍未验证。 |
| F-RUN-02 状态持久化 | `domain/enums.py`、`RunModel.status`、`WorkerRuntime._record_run_failure` | 主要状态和重试回写已落地；deadline 失败、Provider 错误分类和完整 retry_waiting 回路没有完整集成测试。 |
| F-RUN-03 Task 领取 | `postgres_queue.py`、`TaskModel` | lease、attempt、generation、deadline 字段和 SKIP LOCKED 主路径已落地；当前没有单独 Task repository/QueuePort 抽象。 |
| F-RUN-04 Event 追加 | `journal.py`、`RunEventModel`、`contracts/run_event_v1.json` | seq 锁定、唯一约束、终态事务已落地；实际未追加 `task.leased`，应明确作为契约/实现差异和测试点。 |
| F-RUN-05 查询/SSE | `backend/api/routes/runs.py`、`frontend/src/events/run-event-stream.ts` | after_seq、Last-Event-ID、终态关闭已实现；服务端是数据库轮询而非 Redis 唤醒订阅，前端 SSE/replay 并发去重需验证。 |
| F-RUN-06 取消 | `cancel_run`、Run Handler 多个步骤检查 `cancelled` | 主路径已落地，测试覆盖 queued Run 取消；running 中取消、迟到 Provider 结果、取消后的事件序列尚缺专项测试。 |

### 7.3 Worker 调度（F-WK）

| 需求 | 当前实现与文件 | 调研结论和后续测试关注点 |
| --- | --- | --- |
| F-WK-01 PostgreSQL 权威队列 | `TaskModel`、`postgres_queue.py`、Redis notifier 仅做通知 | 已落地；Compose 依赖 Redis 的启动条件与“Redis 可降级”设计存在运行环境差异。 |
| F-WK-02 lease 领取 | `claim_next_task` 使用 `SKIP LOCKED`、generation+1、attempt+1 | 已落地；当前 lease claim 没有写 `task.leased` Event，需补测试或更新方案。 |
| F-WK-03 heartbeat | `WorkerRuntime._lease_heartbeat`、`renew_lease` | 机制已落地；只有 lease 未过期、worker/generation 匹配才能续租；没有长任务实测或 heartbeat 失败后的处理测试。 |
| F-WK-04 过期回收/stale write | `requeue_expired` 和所有主要写回的条件查询 | 基本落地，`test_lease_recovery.py` 验证代数递增和旧 Worker 续租失败；尚未覆盖旧 Worker 完成回写、两个 Worker 并发 claim。 |
| F-WK-05 有界重试 | `schedule_retry`、`retry_delay_seconds`、`max_attempts` | 退避函数和状态写回已实现；测试只验证退避数值，未覆盖达到最大次数、Run 状态、错误码和真实异常分类。 |
| F-WK-06 优雅停机 | `request_stop`、`run_forever`、信号安装 | 已有停止标记，但宽限期和运行中 lease 续租行为与 ADR 的完整语义不完全一致，当前没有 SIGTERM/容器重启自动化测试。 |
| F-WK-07 可观测日志 | `runtime.py` 的 claim、lease lost、task failed 日志 | 关键日志带 task/worker/generation；并非每个 release/retry/success 都有一致结构化日志，需补日志断言和敏感字段检查。 |

### 7.4 文本 RAG（F-RAG）

| 需求 | 当前实现与文件 | 调研结论和后续测试关注点 |
| --- | --- | --- |
| F-RAG-01 文档登记 | `documents.py`、`DocumentModel`、`LocalFileStorage` | 元数据、hash、storage key、状态和共享卷已落地；测试只覆盖不支持扩展名和正常 Markdown 索引，大小/MIME/路径清理需补。 |
| F-RAG-02 解析 | `parsers.py` | txt/md/docx 主路径已实现；单测只验证 md 和不支持扩展名，docx、损坏文件和编码错误需补。 |
| F-RAG-03 切分 | `chunker.py`、`ChunkDraft`、ChunkModel | 字符切分、overlap、seq、offset 已验证；Token 近似、超长文档和边界参数需补。 |
| F-RAG-04 Embedding/索引 | `MockEmbeddingProvider`、`index_handler.py`、`EmbeddingType` | 确定性 mock、固定维度校验、候选 batch 和 active 切换已落地；没有真实 Provider/pgvector 容器验证。 |
| F-RAG-05 召回 | `pgvector_store.py:search_chunks` | Top-K、active batch、cosine 和 Evidence DTO 已落地并有 SQLite 集成测试；当前是 Python 排序，不是完整向量索引/混合检索。 |
| F-RAG-06 生成 | `MockModelProvider`、`OpenAICompatibleProvider`、`run_handler.py` | Mock 主路径已验证；真实模型网络、流式协议、超时、认证和响应结构未验证。 |
| F-RAG-07 引用 | Run Handler 的 citations 和 `MessageModel.citations_json` | 后端会从实际 Evidence 生成引用；测试尚未断言引用只来自实际召回 chunk，前端只展示文件名和 offset。 |
| F-RAG-08 失败语义 | `ApplicationError`/`PermanentTaskError`、Worker retry/fail 写回 | 解析空文档、Embedding 维度等局部失败有错误码；Provider/向量库失败没有按 ADR 完整区分可重试与不可重试，deadline 也没有真正执行。 |

### 7.5 前端最小工作台

Thread 列表/创建、消息输入、文档上传、Run 状态/事件展示、取消、Markdown 清洗和引用展示均有 Vue 组件或 store 对应实现。前端 typecheck/build 可以通过，但当前没有 Vitest/Playwright 测试；重点缺口是：

1. `WorkspacePage` 在 Run 完成后没有重新拉取 Thread，assistant 最终消息可能要刷新浏览器才显示。
2. `run-event-stream.ts` 同时启动 SSE 和 replay，虽然 Run store 按 seq 去重，但 assistant delta 的 UI 投影没有相同去重保护。
3. 刷新页面只加载 Thread 和 Document，未恢复最近 Run 的 Event Journal 和 Run 面板状态。
4. 文档上传后只把 `uploaded` 响应插入 store，没有轮询或 SSE 更新到 `indexed/failed` 的前端流程。

## 8. 核心功能机制与异常行为核对

### 8.1 事实来源与事务边界

- PostgreSQL 是 Thread、Message、Run、Task、RunEvent、Document、Chunk 的事实存储；Redis notifier 只发布唤醒和 readiness key。
- Message/Run/Task/初始事件同事务提交，避免只落用户消息而没有执行记录。
- Event 通过锁定 `RunModel.next_event_seq` 分配 seq；最终 assistant Message、Run/Task 成功状态、`message.completed` 和 `run.succeeded` 同一事务提交。
- 文档索引先写候选 batch，完成后切换 `active_index_batch_id`；检索只读活动批次，事务异常通常会回滚本批次插入。

### 8.2 取消、失败、重试和恢复

| 场景 | 代码当前行为 | 是否完全符合 ADR/PRD |
| --- | --- | --- |
| queued Run 取消 | API 将 Run/Task 置为 cancelled，追加 `run.cancelled`。 | 主路径符合；已有 API 单测。 |
| running Run 取消 | API 写取消状态；Run Handler 在增量和最终写回前检查 Run 状态，避免迟到 assistant 成功。 | 基本符合；缺专项并发测试。 |
| lease 过期 | Worker 下一轮先 `requeue_expired`，清空 worker/lease，未超 attempt 的 Task 回 queued，generation 在下次 claim 时递增。 | 基本符合；缺真实多 Worker 竞争测试。 |
| 旧 generation 写回 | 续租、running、成功、retry 等函数使用 worker/generation 条件，找不到任务时返回 false。 | 机制符合；旧完成回写和事件影响未完整断言。 |
| 普通异常 | Run Handler 对非 ApplicationError 调 `schedule_retry`，统一错误码 `RUN_FAILED`；Worker 再把 Run 设 retry_waiting 或 failed。 | 与 ADR 的错误分类不完全一致；认证/参数错误可能被重试。 |
| deadline | `claim_next_task` 过滤已过 deadline 的 queued Task。执行中没有 deadline 检查、超时取消或 `TASK_DEADLINE_EXCEEDED` 写回。 | 未完全落地。 |
| Provider 故障 | OpenAI-compatible HTTP 异常通常作为普通异常处理；没有稳定映射 5xx/超时/认证/参数错误。 | 未完全落地。 |
| Redis 不可用 | RedisNotifier 连接失败后 client 为空，API/SSE可继续使用数据库；但 Compose 的服务依赖可能阻止 API/Worker 启动。 | 代码降级符合，Compose 行为有差异。 |
| PostgreSQL 不可用 | 没有内存成功状态；API/Worker 会抛出基础设施异常。 | 基本符合“不伪造成功”，但没有 503/退避集成测试。 |
| Worker SIGTERM | stop_event 阻止下一轮领取；当前实现会停止 heartbeat，并只等待最多 1 秒。 | 仅部分符合优雅停机设计。 |
| SSE 断开 | 服务端生成器结束，不写取消；前端可再次调用补放接口。 | 后端符合；前端自动恢复和去重需补测。 |
| 文档损坏/空文档/维度不匹配 | 通过 `PermanentTaskError` 写 failed 和错误码；普通读取/Provider 异常走 `INDEX_FAILED` 重试。 | 主路径符合；候选批次保留/清理和旧活动批次需专项测试。 |

## 9. 与实施方案的符合性评估

### 9.1 已基本符合的设计

1. 模块化单体后端、独立 API/Worker/Frontend 容器和 Compose 目录结构已建立。
2. Thread/Message/Run/Task/RunEvent/Document/Chunk 的持久对象和主要关系已建立。
3. PostgreSQL 作为事实来源、Redis 作为通知、SSE 按 Event Journal 补放的主原则已实现。
4. Task lease、generation、attempt、heartbeat、retry、过期回收和 stale generation 条件写回已有代码与部分测试。
5. 文本文档登记、解析、字符切分、Embedding、候选 batch、召回、Mock 生成和 citations 主链路已实现。
6. API 版本前缀、错误 envelope、事件 JSON Schema、共享上传卷、Markdown 清洗和配置模板已建立。

### 9.2 需要在后续测试或实现中明确的差异

| 差异 | 影响 | 建议处理 |
| --- | --- | --- |
| `task.leased` 事件在契约/ADR 中声明，但代码没有追加 | 事件回放无法观察真实领取时刻，契约测试可能漏报 | 明确补充事件生产，或修订 ADR/契约并保留差异说明。 |
| deadline 只用于 claim 过滤 | 长时间运行 Task 可能超过硬截止时间仍继续执行 | 增加运行中 deadline 检查、稳定错误码和集成测试。 |
| Provider 错误分类不完整 | 认证/参数错误可能消耗重试次数，测试无法确认失败语义 | 让 Provider 映射 `TransientTaskError`/`PermanentTaskError`，补超时/5xx/认证测试。 |
| Worker graceful shutdown 实现弱于方案 | 停机时 heartbeat 提前退出，当前任务可能依赖 lease 回收而非宽限完成 | 调整 shutdown 状态机并做 SIGTERM/重启测试。 |
| 前端最终消息和重连投影不完整 | 用户可能看不到流式或最终 assistant 内容，刷新后 Run 时间线丢失 | 补 terminal 后 Thread reload、事件投影幂等和 E2E。 |
| 实际缺少 `Port`、repository、unit-of-work 等 ADR 预留文件 | 当前 Demo 可运行，但替换 Queue/Vector/Provider 仍需直接改调用方 | 后续 PRD1/PRD2 实施时先抽取稳定 Port，不要把 Demo 直接函数当完整架构已完成。 |
| Ruff 当前复核失败、Docker daemon 不可用 | 不能把当前工作区称为所有质量门禁通过 | 先处理迁移格式问题并启动 Docker Desktop，再补 Compose smoke。 |

## 10. 本次复核命令与结果

本次在 `sesrag_v0.1` 当前工作区执行了以下命令：

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `python -m pytest -q` | **通过** | 16 passed，1 个 Starlette/httpx 弃用警告。 |
| `mypy backend` | **通过** | 46 个后端源文件无错误。 |
| `npm run typecheck` | **通过** | `frontend/package.json` 的 `vue-tsc --noEmit`。 |
| `npm run build` | **通过** | Vite 生产构建成功。 |
| `docker compose config` | **通过** | Compose 配置可解析。 |
| `ruff check .` | **未通过** | `migrations/env.py` 和 `migrations/versions/0001_initial_demo.py` 存在导入排序/格式问题，另有一处超长行。 |
| `ruff format --check .` | **未通过** | 上述两个 migration 文件需要格式化。 |
| `docker compose ps` / `docker info` | **未完成** | Docker daemon 未运行，报 `dockerDesktopLinuxEngine` named pipe 不存在，未进行本轮容器 smoke。 |

本次没有修改代码、迁移或测试文件，因此 Ruff 和 Docker 的缺口仅记录在调研结果中，不在本任务内擅自扩大为实现修复。

## 11. 后续测试设计建议

以下内容不是已通过的测试，而是根据当前实现和 PRD/ADR 差异整理的测试输入清单：

### P0：事实、并发和终态正确性

1. 同一 Thread 并发发送相同 `Idempotency-Key`，确认只生成一个 Message、Run、Task。
2. 两个 Worker 并发 claim 同一队列，确认只有一个 lease，generation/attempt 只递增一次。
3. 旧 generation 在新 Worker 接管后执行 renew、retry、成功回写，确认不改变当前 Task/Run/assistant Message。
4. Event Journal 并发追加，确认 seq 连续、唯一、按序补放；补充 `task.leased` 是否应存在的契约断言。
5. assistant Message、Run/Task terminal state、`message.completed` 和 terminal Event 原子提交，模拟提交失败后确认无半链路终态。

### P0：Worker 生命周期和失败语义

1. 运行中 SIGTERM、lease heartbeat、宽限结束和容器重启组合场景。
2. deadline 在 queued、running、retry_waiting 三种阶段的行为，确认稳定 `TASK_DEADLINE_EXCEEDED`。
3. Provider 超时、连接失败、HTTP 5xx、401/403、参数 4xx 分别确认重试次数、错误码、Run 状态和 Event。
4. PostgreSQL 暂时不可用、Redis 不可用、Redis 重启，确认事实不丢失且服务不会伪造成功。

### P0：文档索引与引用

1. txt/md/docx 正常索引、UTF-8 编码错误、损坏 docx、空文件、超 10 MiB、扩展名/MIME 不匹配。
2. Embedding 维度不匹配、索引中途异常、已有 active batch 重建失败，确认旧索引可检索且候选批次不污染。
3. query 无证据、Top-K、多文档召回和引用身份，确认 citations 只能来自本次 Evidence。

### P1：前端和安全

1. SSE 首次补放与实时事件同时到达，确认 answer delta、Event Journal 和最终消息均不重复。
2. Run 完成、失败、取消后刷新页面，确认 Thread、assistant Message、Run 和 Event 时间线一致。
3. 文档上传完成后状态从 uploaded 到 indexed/failed 的刷新和重试；前端不显示 storage key、Secret 或宿主路径。
4. Markdown XSS、错误响应、超长输入、非法文件名和路径逃逸。

## 12. 调研结论与审批

### 12.1 结论

当前 Demo 已经形成可运行的后端持久化会话、PostgreSQL Task/lease、文本 RAG、Event Journal/SSE 和 Vue 工作台纵向切片，核心目录和主要对象关系与 PRD/ADR 基本一致。后端主链路和离线 RAG 流程有可重复的 16 项 Python 测试，类型检查和前端生产构建也已通过。

但“基本实现”不等于“PRD/ADR 每个验收点都已闭环”：当前最重要的未闭环是 deadline、Provider 错误分类、graceful shutdown、`task.leased` 事件、幂等并发约束、前端最终消息/刷新恢复和 Compose smoke。Ruff 质量门禁也需要修复 migration 格式后重新执行；Docker smoke 需要在 Docker daemon 可用时补做。

### 12.2 审批结果

- [x] PRD 已落地部分、对应实现模块和主要行为已逐项列出。
- [x] 实施方案中的对象、事实来源、事务边界、状态机、lease/generation、RAG batch 和 SSE 机制已与代码核对。
- [x] 新增项目文件、目录职责和实施提交范围已说明；对预期文件但当前不存在的 Port、repository、前端测试等也已明确标注。
- [x] 取消、重试、租约过期、旧 generation、Redis/数据库故障、文档错误、Provider 故障、deadline 和停机行为已区分“当前代码行为”和“方案预期”。
- [x] 已记录当前可重复验证结果、失败门禁和 Docker 环境阻碍，没有把未运行的检查写成通过。
- [x] 已给出可直接转化为测试点/测试用例的 P0/P1 清单。

**审批结论**：本调研文档已基本达到“说明开发需求、实际变动、核心功能行为、异常机制、方案差异和后续测试入口”的要求。Demo 可作为后续测试设计的代码基线，但在补齐上述 P0 缺口并重新验证前，不应宣称完全通过 PRD/ADR 的全部验收标准或达到生产级可靠性。
