# SesRAG 统一术语上下文

本文件是仓库稳定术语的唯一维护入口。术语用于 PRD、ADR、代码、契约、测试和交付说明时，应优先采用本文件的拼写和含义；如果代码中的旧名称与本文件冲突，应在对应变更中明确迁移，不要继续扩展两套同义词。

“已实现”表示当前 Demo 代码和测试已经提供该语义；“规划中”表示完整项目目标或 ADR 已定义，但当前实现不应假设它存在；“演进边界”表示当前实现已有替代方案或局部实现，后续应通过 Port/Adapter 扩展；“仅文档”表示术语目前只作为设计约定存在。

## 核心会话与执行对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Thread` | 长期会话容器，拥有消息顺序、归档状态和多个 Run。 | `backend/db/models.py` 的 `ThreadModel`；`backend/application/threads.py` | 已实现 |
| `Message` | Thread 内按 `seq` 排序的事实消息；角色为 `user` 或 `assistant`。 | `backend/db/models.py` 的 `MessageModel`；`backend/api/schemas/threads.py` | 已实现 |
| `Run` | 一条用户 Message 触发的一次完整执行身份；重试不会创建新的 Run。 | `backend/db/models.py` 的 `RunModel`；`backend/application/runs.py` | 已实现 |
| `RunSnapshot` | Run 创建时冻结的模型、检索和提示词版本配置，运行中只读。Demo 目前存放在 `RunModel.snapshot_json`。 | `backend/application/threads.py:create_message_run`；`docs/adr/001-sesrag-demo-implementation-plan.md` | 已实现 |
| `Run Context` | 只属于一次 Run 的临时运行上下文，不作为长期会话事实。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |
| `Checkpoint` | Run 因等待人工输入或恢复点而暂停时保存的可恢复位置。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |
| `Tool Audit` | 工具授权、调用参数摘要和结果的安全审计记录，不等同于普通 Event。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |

## Worker 与任务对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Task` | 持久化可执行工作项；Demo 支持 `run` 和 `index_document` 两类。 | `backend/db/models.py` 的 `TaskModel`；`backend/domain/enums.py:TaskKind` | 已实现 |
| `Worker` | 领取 Task、维护 lease、执行 handler 并写回事实的进程。 | `backend/workers/runtime.py`、`backend/workers/main.py` | 已实现 |
| `Worker lease` | Task 在某个 Worker 和 generation 下的有限执行租约；到期后可被其他 Worker 回收。 | `backend/infrastructure/queue/postgres_queue.py` | 已实现 |
| `worker_id` | Worker 进程的稳定身份，用于 lease 和日志关联，不是独立业务实体。 | `backend/workers/runtime.py`；`TaskModel.worker_id` | 已实现 |
| `generation` | 每次重新领取 Task 时递增的租约代数；所有续租、进度和完成写回必须匹配当前代数。 | `backend/infrastructure/queue/postgres_queue.py`；`TaskModel.generation` | 已实现 |
| `attempt` | 同一 Task 的第几次执行尝试；增加 attempt 不会创建新的 Thread、用户 Message 或 Run。 | `TaskModel.attempt`；`backend/infrastructure/queue/postgres_queue.py` | 已实现 |
| `Run Attempt` | 完整项目中对一个业务 Task 的一次 Worker 执行尝试，承载 worker、generation、lease 和 progress。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD1 设计 | 规划中 |
| `QueueMessage` | 完整项目中用于分发持久 Task 的消息身份和可用时间提示；不取代 Task 事实。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD1 设计 | 规划中 |

## 事件、证据与 RAG 对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `RunEvent` | 一条属于 Run 的不可变事件记录，包含 `schema_version`、`seq`、类型和安全数据。 | `backend/db/models.py:RunEventModel`；`backend/api/schemas/runs.py:EventResponse` | 已实现 |
| `Event Journal` | 按 Run 追加保存并可按 `after_seq` 补放的 RunEvent 集合，是执行事实来源。 | `backend/infrastructure/events/journal.py`；`contracts/run_event_v1.json` | 已实现 |
| `Citation` | assistant Message 对本次 Run 实际召回证据的结构化引用，至少包含 document、chunk、位置和分数身份。 | `backend/workers/handlers/run_handler.py`；`MessageModel.citations_json` | 已实现 |
| `Document` | 已登记的原始文档元数据和当前索引状态，不等于一个已发布知识库版本。 | `backend/db/models.py:DocumentModel`；`backend/application/documents.py` | 已实现 |
| `Document Version` | 不可变的文档内容/解析/索引版本，可作为候选、发布和回滚边界。 | `docs/prd/002-SesRAG-完整项目-PRD.md` 的 PRD4 设计 | 规划中 |
| `index batch` | Demo 内部的一次候选索引批次标识；只有批次完成后才切换 `active_index_batch_id`。 | `DocumentModel.active_index_batch_id`；`backend/workers/handlers/index_handler.py` | 已实现 |
| `Chunk` | 文档经过解析和切分后的可检索文本片段，带序号、字符位置和 Embedding。 | `backend/db/models.py:ChunkModel`；`backend/domain/entities.py:ChunkDraft` | 已实现 |
| `Evidence` | 检索返回给 Run Handler 的证据 DTO，包含 document/chunk 身份、片段、位置和分数。 | `backend/infrastructure/rag/pgvector_store.py:Evidence` | 已实现 |

## Provider、Port 与 Adapter

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Provider` | 对外部模型或 Embedding 能力的统一服务边界；Provider 失败必须映射为稳定错误语义。 | `backend/infrastructure/providers/mock.py`、`openai_compatible.py` | 已实现 |
| `ModelProvider` | 生成回答或回答增量的 Provider 接口语义。 | `backend/workers/handlers/run_handler.py`；`backend/infrastructure/providers/mock.py:MockModelProvider` | 已实现 |
| `EmbeddingProvider` | 将文本转换为固定维度向量的 Provider 接口语义。 | `backend/infrastructure/providers/mock.py:MockEmbeddingProvider` | 已实现 |
| `Port` | 领域或应用层依赖的稳定能力接口，隐藏具体基础设施实现。 | `docs/adr/001-sesrag-demo-implementation-plan.md` 的 Port/Adapter 决策 | 演进边界 |
| `Adapter` | Port 的具体基础设施实现，例如 PostgreSQL、Redis、pgvector 或 OpenAI-compatible Provider。 | `backend/infrastructure/` | 已实现 |
| `QueuePort` | 任务领取、续租、回收、重试和终态写回的可替换接口。 | `docs/adr/001-sesrag-demo-implementation-plan.md`；当前实现 `backend/infrastructure/queue/postgres_queue.py` | 演进边界 |
| `VectorStorePort` | 以统一 Evidence DTO 提供写入和 Top-K 召回的可替换接口。 | `docs/adr/001-sesrag-demo-implementation-plan.md`；当前实现 `backend/infrastructure/rag/pgvector_store.py` | 演进边界 |
| `ParserPort` | 将受限文档格式解析为纯文本和基础位置的可替换接口。 | `docs/adr/001-sesrag-demo-implementation-plan.md`；当前实现 `backend/infrastructure/rag/parsers.py` | 演进边界 |

## 术语变更规则

1. 新增稳定术语时，先在本文件增加含义、来源和状态，再更新 PRD/ADR、契约和代码引用。
2. 术语含义发生实质变化时，不直接复用旧词掩盖迁移；应在本文件注明旧含义、迁移目标和取代文档。
3. 当前 Demo 的 `index batch` 不得在没有 PRD/ADR 变更的情况下直接称为公开的 `Document Version`；两者在完整项目发布流程落地前保持区分。
4. `Run`、`Task`、`Run Attempt` 和 `attempt` 不得混用：Run 是会话执行身份，Task 是持久工作项，Run Attempt 是完整项目的执行尝试，attempt 是尝试次数。
