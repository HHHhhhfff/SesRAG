# SesRAG 项目 Demo 产品需求文档

**版本**：v0.1

**状态**：已确认，作为 Demo 实施基线

**日期**：2026-10-03

**对应范围**：`D:\Agentic_RAG\SesRAG` 的第一阶段可运行产品

## 1. 文档目的

本 PRD 定义 SesRAG 的第一阶段 Demo。Demo 不是一次性的技术样例，而是一个可运行、可重启、可继续扩展的纵向切片：用户能够创建持久化会话，提交问题，由 Worker 执行一次简单文本 RAG，看到回答和引用，并在服务重启后恢复历史和任务状态。

本文件只约束 Demo 的交付范围。完整产品的长期目标、PRD1～PRD4 和暂不落地的能力见 `SesRAG-完整项目-PRD.md`，两者不可混用。

## 2. 产品目标

### 2.1 目标

1. 验证 `Thread -> Message -> Run -> Task/Worker -> Event Journal -> assistant Message` 的持久化主链路。
2. 验证文本知识库的最小闭环：导入、解析、切分、Embedding、索引、召回、带引用回答。
3. 验证任务在 PostgreSQL 中排队、领取、租约续期、失败重试和优雅停机后的恢复。
4. 验证前后端分离、SSE 事件投影和 Docker Compose 多容器启动方式。
5. 为后续替换队列、向量库、模型 Provider、工具系统和知识库版本化保留稳定接口。

### 2.2 非目标

Demo 不交付以下能力：多租户计费、生产级认证与 RBAC、人工审批/HITL、任意代码沙箱、Web 搜索、SQL 工具、复杂 Skill Registry、Milvus 集群、混合检索和 Rerank、知识库审核发布、完整 RAG 评测平台、移动端和 Electron 客户端。

Demo 可以保留这些能力所需的稳定接口边界，但不得提供一个行为不完整且会被误认为正式能力的半成品入口。

## 3. 用户与核心场景

### 3.1 目标用户

- **开发者/维护者**：通过 Compose 启动系统，导入少量文本，检查会话、任务和事件行为。
- **内部使用者**：在浏览器中创建会话，围绕指定文本资料提问，查看引用和执行状态。

Demo 默认单用户、单工作区、开发环境使用。身份边界通过 `owner_id` 或等价字段保留，但不把 Demo 的开发认证当作生产安全方案。

### 3.2 主流程

1. 用户启动 Compose，打开前端。
2. 用户创建 Thread，上传或导入 `.txt`、`.md`、`.docx` 文档；`.doc` 由解析器适配器预留，未安装对应依赖时返回明确的“不支持/未配置”错误。
3. 系统创建索引任务，Worker 解析文档、切分文本、生成 Embedding 并写入 Demo 向量存储。
4. 用户在 Thread 中发送问题；API 追加用户 Message，创建 Run 和对应 Task 后立即返回。
5. Worker 领取 Task，执行检索和回答生成，持续追加 Event Journal；前端通过 SSE 订阅，断线后可按序号补放。
6. 系统在同一 Run 下保存最终 assistant Message、引用和终态事件。
7. 用户刷新页面或重启服务后，仍可看到 Thread、Messages、Runs 和可重放事件。

## 4. 功能需求

### 4.1 Thread 与 Message

| 编号 | 需求 | 验收要点 |
| --- | --- | --- |
| F-TH-01 | 创建、列出、读取和归档 Thread | Thread 有稳定 ID、标题、创建/更新时间和 owner；列表按更新时间倒序。 |
| F-TH-02 | 在 Thread 中追加用户 Message | Message 具有 Thread 内单调 `seq`、role、正文、时间和来源。 |
| F-TH-03 | 保存 assistant 最终 Message | assistant Message 关联唯一 Run，可保存 Markdown 正文、引用列表和生成状态。 |
| F-TH-04 | 刷新后恢复会话 | 页面重新加载从 API 获取事实历史，不依赖浏览器本地缓存恢复。 |

### 4.2 Run、Task 与事件

| 编号 | 需求 | 验收要点 |
| --- | --- | --- |
| F-RUN-01 | 每次用户提问创建一个 Run | Run 固定关联 Thread、用户 Message、模型/检索配置快照和创建时间。 |
| F-RUN-02 | Run 状态可持久化 | Demo 支持 `queued`、`running`、`retry_waiting`、`succeeded`、`failed`、`cancelled`。 |
| F-RUN-03 | 任务可被 Worker 领取 | Task 保存 `task_id`、`run_id`、`state`、`attempt`、`worker_id`、`generation`、`lease_expires_at`、`available_at` 和 `deadline_at`。 |
| F-RUN-04 | 事件追加写入 | Event 保存 `event_id`、`run_id`、`seq`、`type`、安全 payload 和创建时间；同一 Run 的 seq 单调递增。 |
| F-RUN-05 | 查询和订阅事件 | 提供按 `after_seq` 查询事件和 SSE 订阅；客户端按 seq 去重。 |
| F-RUN-06 | 取消 Run | 取消只改变持久状态并通知 Worker；Worker 在步骤边界检查取消，不将 SSE 断开误判为取消。 |

### 4.3 Worker 调度最小闭环

| 编号 | 需求 | 验收要点 |
| --- | --- | --- |
| F-WK-01 | PostgreSQL 权威任务队列 | API 创建任务即落库；Redis 不保存最终任务状态。 |
| F-WK-02 | 租约领取 | Worker 使用事务和条件更新领取可用任务，生成新的 `generation` 和租约过期时间。 |
| F-WK-03 | 心跳/续租 | Worker 在处理期间定时续租；续租必须校验 task_id、worker_id、generation。 |
| F-WK-04 | 过期回收 | 其他 Worker 可回收已过期租约；旧 Worker 的写回被拒绝并记录事件。 |
| F-WK-05 | 有界重试 | 可重试错误按固定退避重排，超过最大 attempt 进入 `failed` 并记录错误码。 |
| F-WK-06 | 优雅停机 | Worker 收到 SIGTERM 后停止领取新任务，当前任务在宽限期内完成或释放租约；Compose 重启后任务可继续。 |
| F-WK-07 | 可观测日志 | 每次领取、续租、释放、重试、成功、失败日志包含 task_id、run_id、worker_id、generation。 |

### 4.4 文本知识库与最小 RAG

| 编号 | 需求 | 验收要点 |
| --- | --- | --- |
| F-RAG-01 | 文档登记 | 保存文档 ID、原始文件名、扩展名、大小、内容哈希、来源、状态和创建时间。 |
| F-RAG-02 | 解析适配器 | 首版实现 txt、md、docx；解析器通过统一接口返回纯文本和基础位置信息。 |
| F-RAG-03 | 切分 | 使用可配置的字符/Token 近似切分，保存 chunk 序号、起止位置和父文档 ID。 |
| F-RAG-04 | Embedding 与索引 | 通过 EmbeddingPort 生成向量；默认使用 pgvector 或等价可替换存储。未配置真实模型时可使用确定性 mock provider。 |
| F-RAG-05 | 召回 | 按 query 生成向量并返回 Top-K chunk，包含文档、chunk、分数和文本片段。 |
| F-RAG-06 | 生成 | 通过 ModelProvider 生成基于证据的回答；未配置外部模型时使用可测试的 mock 回答。 |
| F-RAG-07 | 引用 | assistant Message 记录引用的 document_id、chunk_id、标题/文件名和片段位置；不得凭空生成引用。 |
| F-RAG-08 | 失败语义 | 解析、Embedding、索引、向量库或模型失败时 Run 显式失败；不能返回“未找到资料”冒充基础设施故障。 |

### 4.5 前端最小工作台

- Thread 列表和创建入口。
- 会话消息流，区分用户、assistant、运行中和失败状态。
- 文档导入与索引状态展示。
- Run 状态、事件时间线、引用展开和重新连接。
- 取消正在运行的 Run。
- 开发环境下展示 API/Worker/数据库健康状态；不展示 Secret。

## 5. 领域模型与状态机

### 5.1 核心对象

```text
Thread
├── Message(seq, role=user|assistant, content)
└── Run
    ├── RunSnapshot(model, retrieval, prompt version)
    ├── Task(attempt, lease, generation, deadline)
    ├── EventJournal(seq, type, payload)
    └── AssistantMessage

Document
└── Chunk(seq, text, location, embedding)
```

Demo 的 `RunSnapshot` 创建后不可修改；`Run Context`、Tool Audit 和 Checkpoint 只在完整项目实现，Demo 不模拟这些对象。

### 5.2 状态约束

```text
Task: queued -> leased/running -> succeeded
                         ├-> retry_waiting -> queued
                         ├-> cancelled
                         └-> failed

Run: queued -> running -> retry_waiting -> queued
                         └-> succeeded|failed|cancelled
```

所有状态变更由后端事务执行并追加事件。终态不可逆；重试只改变 Task attempt，不创建新的 Run。

## 6. 技术路线与部署

### 6.1 技术选型

| 层 | Demo 选型 | 选择理由与扩展边界 |
| --- | --- | --- |
| API | Python 3.12、FastAPI、Pydantic v2 | 异步 HTTP/SSE，契约清晰。领域服务不依赖 FastAPI。 |
| 数据库 | PostgreSQL 16、SQLAlchemy 2、Alembic、psycopg | 保存所有业务事实、任务、事件和文档元数据。 |
| 向量 | pgvector | 减少 Demo 基础设施；通过 VectorStorePort 预留 Milvus/其他向量库。 |
| 通知 | Redis | 只做低延迟事件通知和短期缓存，不能成为事实来源。 |
| 模型 | OpenAI-compatible ModelProvider、EmbeddingProvider | 统一外部模型边界；提供 mock provider 便于离线验收。 |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Naive UI、marked、DOMPurify、Lucide Vue | 组件化、类型化、Markdown 安全渲染和可替换 UI。 |
| 测试 | pytest、pytest-asyncio、Ruff、mypy；Vitest、vue-tsc、ESLint；Playwright smoke | 覆盖领域不变量、契约和主流程。 |

### 6.2 Compose 服务

Demo 的 `docker-compose.yml` 至少包含：

| 服务 | 职责 | 持久化/依赖 |
| --- | --- | --- |
| `frontend` | Vite 开发服务器或静态资源服务 | 依赖 `api` |
| `api` | HTTP、SSE、Thread/Run/Document API | PostgreSQL、Redis |
| `worker` | 任务领取、索引、RAG 执行 | PostgreSQL、Redis、共享上传目录 |
| `postgres` | 业务事实和 pgvector | named volume |
| `redis` | 通知和短缓存 | named volume 可选 |

应用镜像、数据库迁移和健康检查要能在全新环境启动。模型 Key、数据库密码和其他 Secret 通过 `.env` 或 Secret 机制注入，不写入镜像和 Git。

### 6.3 推荐目录

```text
backend/
  api/             # routes、schemas、SSE
  domain/          # entities、states、ports
  application/     # thread、run、document、task use cases
  infrastructure/  # postgres、redis、pgvector、providers
  workers/         # worker entrypoint、lease loop、handlers
frontend/src/
  pages/ components/ stores/ api/ events/ types/
migrations/
contracts/
tests/
docker/
docs/
```

## 7. API 与事件契约

首版正式前缀为 `/api/v1`，示例接口如下：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/threads` | 创建 Thread |
| `GET` | `/threads` | 列出 Thread |
| `GET` | `/threads/{thread_id}` | 读取 Thread、Messages、Runs 摘要 |
| `POST` | `/threads/{thread_id}/messages` | 创建用户 Message 并启动 Run |
| `GET` | `/runs/{run_id}` | 读取 Run 当前状态 |
| `GET` | `/runs/{run_id}/events?after_seq=n` | 补放事件 |
| `GET` | `/runs/{run_id}/events/stream` | SSE 事件流 |
| `POST` | `/runs/{run_id}/cancel` | 请求取消 |
| `POST` | `/documents` | 上传/登记文本文档 |
| `GET` | `/documents` | 列出文档及索引状态 |
| `POST` | `/documents/{document_id}/index` | 创建索引任务 |
| `GET` | `/health/live`、`/health/ready` | 存活与就绪检查 |

事件最小类型：`run.created`、`task.queued`、`task.leased`、`run.started`、`retrieval.completed`、`answer.delta`、`message.completed`、`run.succeeded`、`run.failed`、`run.cancelled`、`task.retry_scheduled`。

SSE 仅是 Event Journal 的投影；客户端必须保存最后 seq，并通过 `after_seq` 补放，不能只依赖连接期间收到的事件。

## 8. 非功能需求

- **可恢复性**：API、Worker、Redis 任一进程重启后，已提交的 Thread、Message、Run、Task、Document 和 Event 不丢失。
- **并发正确性**：同一 Task 同时只能有一个有效 lease；旧 generation 的心跳和完成回写必须失败。
- **可测试性**：无外部模型 Key 时能用 mock provider 完成全部自动化验收。
- **可观测性**：日志包含关联 ID；健康检查区分进程存活和依赖就绪。
- **安全基线**：上传目录不暴露为静态目录；Markdown 输出经过清洗；错误响应不泄露 Secret、堆栈和宿主路径。
- **性能目标**：在本地开发规模（单 Worker、少量文档）下，创建消息 API 在 1 秒内返回 Run ID；事件首包在任务开始后 2 秒内可见。该目标不作为生产 SLO。

## 9. Demo 验收标准

1. 全新环境执行 `docker compose up --build` 后，API、前端、Worker、PostgreSQL、Redis 均健康。
2. 可创建 Thread，发送问题，并在数据库中看到用户 Message、Run、Task、Event 和 assistant Message。
3. Worker 崩溃或容器重启后，未完成任务能依靠租约过期重新领取，不产生重复最终 assistant Message。
4. Worker 收到 SIGTERM 后不再领取新任务，当前任务完成或释放租约；重启后队列继续工作。
5. 导入 txt/md/docx 后能完成索引；问题回答至少引用一个实际召回 chunk，或明确返回无相关证据。
6. SSE 断开并重连后，前端通过 `after_seq` 补齐事件且不重复显示。
7. 取消 Run 后 Worker 停止后续模型/检索步骤，Run 进入 `cancelled`，不会被迟到成功回写覆盖。
8. 自动化测试覆盖：状态机、事件序号、租约代数、过期回收、重试、取消、文档解析、召回和 API 契约。

## 10. 实施顺序

1. 工程骨架、Compose、配置、健康检查和数据库迁移。
2. Thread/Message/Run/Event 数据模型及 API。
3. PostgreSQL Task Queue、lease、heartbeat、retry、graceful shutdown。
4. 文档登记、解析、切分、EmbeddingPort、pgvector 检索。
5. ModelProvider、RAG Run handler、引用和 mock provider。
6. Vue 会话页面、事件重连、文档状态和取消操作。
7. 集成测试、Playwright smoke、README/Runbook 和本 PRD 对照验收。

## 11. Demo 完成后的演进原则

- 保持 `/api/v1` 和 Thread/Message/Run/Event 的语义稳定；新增字段优先向后兼容。
- 通过 Port 替换 pgvector、Redis 通知和 ModelProvider，不把替换工作扩散到领域层。
- 将 Demo 的 Task 演进为完整项目的业务 Task + Run Attempt；保留 task_id、run_id、generation、attempt、deadline 等字段。
- 将 Demo 的单一文档集合演进为 DocumentVersion、candidate build、审核和原子发布，不直接改写当前索引。
- 任何生产级能力先更新完整 PRD/ADR，再拆成独立可验收的实现任务。
