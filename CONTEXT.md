# SesRAG 统一术语上下文

本文件是仓库稳定术语的唯一维护入口。术语用于 PRD、ADR、代码、契约、测试和交付说明时，应优先采用本文件的拼写和含义；如果代码中的旧名称与本文件冲突，应在对应变更中明确迁移，不要继续扩展两套同义词。

“已实现”表示当前 Demo 代码和测试已经提供该语义；“规划中”表示完整项目目标或 ADR 已定义，但当前实现不应假设它存在；“演进边界”表示当前实现已有替代方案或局部实现，后续应通过 Port/Adapter 扩展；“仅文档”表示术语目前只作为设计约定存在。

ADR002当前状态：同一冻结源码的两轮all已实际执行；纳入目标、暂缓与平台受限见[复验报告](tests/demo-smoke/复测和验收报告.md)§9。完整项目规划与Demo演进边界保持下表定义。

ADR-003/PRD-002：v0.2 持久化会话与工作台代码已接线，五个分类均有通过证据；同源正式两轮 all 已执行，但第二轮有1项失败、两轮各18项blocked，完整验收未通过。ADR-003 保持“已接受”；详情见 [TEST-002](docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md) 和 [PR-003](docs/pr/003-SesRAG-持久化会话与对话工作台-PR.md)。

## 核心会话与执行对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Thread` | 长期会话容器，拥有消息顺序、归档状态和多个 Run。 | `backend/db/models.py` 的 `ThreadModel`；`backend/application/threads.py` | 已实现 |
| `Branch` | Thread 中可继续对话的一条路径，以父 Branch 和 fork Message 组合祖先前缀与自身消息，不复制祖先；同分叉点可有多个子分支。head/version 记录本路径末尾，seq 仍为 Thread 全局顺序。 | `backend/db/models.py:BranchModel`；`backend/application/branches.py`；[ADR-003 §5/§7](docs/adr/003-sesrag-persistent-session-workspace-implementation-plan.md) | 已实现；v2-session、v2-workspace Compose 分类通过，完整两轮 all 按 TEST-002 |
| `Message` | 按 Thread 内 `seq` 排序的事实消息；角色为 `user` 或 `assistant`，具有不可变来源 Branch。祖先消息可由后代 Branch 引用；多个显式 Run 可引用同一输入消息。 | `backend/db/models.py:MessageModel`；`contracts/message_v2.json`；`backend/api/schemas/v2/threads.py` | 已实现 |
| Message `source` | 消息的安全逻辑来源；用户输入为 `user_input`，生成回答为 `assistant_generation`，不是宿主文件路径。与 role 的参与者身份语义分开。 | `MessageModel.source`；`contracts/message_v1.json`；`migrations/versions/0002_demo_integrity.py` | 已实现（ADR-002 基础修复） |
| `Run` | 一条用户 Message 触发的一次完整执行身份；Worker 对 Task 的自动尝试沿用同一 Run；用户主动重试/重新生成会创建关联原输入的新 Run。 | `backend/db/models.py:RunModel`；`backend/application/session_runs.py` | 已实现 |
| `RunSnapshot` | Run 创建时冻结的非 Secret 模型、Provider、维度、owner、Branch、输入锚点、检索、提示词、上下文和执行上限；运行中只读。schema1旧快照保持独立解码。 | `backend/db/models.py:RunModel.snapshot_json`；`backend/infrastructure/providers/registry.py` | schema1/v2均已接线；v2-model Compose 分类通过，完整两轮 all 按 TEST-002 |
| `ModelProfile` | 服务端可选择的生成模型配置，以 profile_id/version 标识不可变参数；数据库元数据为事实，显式导入文件只作输入，`env:MODEL_API_KEY` 等受信 alias 仅在 Worker 运行时解析。前端只看到安全字段。 | `backend/application/model_profiles.py`；`backend/infrastructure/session/model_profiles.py`；`backend/tools/sync_model_profiles.py` | 已实现；v2-model Compose 分类通过，完整两轮 all 按 TEST-002 |
| `ContextPlan` | Run 某次 Task/generation 实际选择的 Branch 历史、证据、裁剪/摘要及预算说明；只读计划按代保留，Run 可关联多份历史计划，完整 Prompt 不落库。 | `backend/application/context.py`；`backend/application/session_execution.py`；`migrations/versions/0005_v2_profiles_context.py` | 已实现 |
| `ConversationSummary` | 有来源 message_id/字符区间/hash/策略版本的简易派生摘要；采用确定性提取，不替换原始 Message，也不跨 Thread/Branch 复用。 | `backend/application/context.py:_extract_summary`；`conversation_summaries` 表 | 已实现 |
| `SessionOperation` | v2 消息/分支/用户重试/重生成操作的内部幂等记录，保存规范化请求 hash 和结果身份；同 Thread 同键同内容重放原结果，异内容冲突。 | `backend/application/session_operations.py`；`session_operations` 表 | 已实现 |
| `cancelling` | v2 Run 已持久化取消请求但尚未确认的非终态；Task 保持活动状态，到 Worker/到期回收确认后转 cancelled。不能由浏览器计时器推断结束。 | `backend/application/session_runs.py:cancel_session_run`；`backend/application/task_execution.py` | 已实现 |
| `ExecutionStopped` | 当前执行者因取消、失租、deadline 或终态退出的内部信号；不表示新代执行失败，不允许旧执行者追加事实或覆盖错误。 | `backend/application/task_execution.py`；`backend/workers/runtime.py` | 当前代码及执行专项已审查；ADR-002 两轮纳入目标已复验，范围限制见报告 |
| `Run Context` | 只属于一次 Run 的临时运行上下文，不作为长期会话事实。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |
| `Checkpoint` | Run 因等待人工输入或恢复点而暂停时保存的可恢复位置。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |
| `Tool Audit` | 工具授权、调用参数摘要和结果的安全审计记录，不等同于普通 Event。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD2 设计 | 规划中 |

## Worker 与任务对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Task` | 持久化可执行工作项；Demo 支持 `run` 和 `index_document` 两类。 | `backend/db/models.py` 的 `TaskModel`；`backend/domain/enums.py:TaskKind` | 已实现 |
| `Worker` | 领取 Task、维护 lease、执行 handler 并写回事实的进程。 | `backend/workers/runtime.py`、`backend/workers/main.py` | 已实现 |
| `Worker lease` | Task 在某个 Worker 和 generation 下的有限执行租约；到期后可被其他 Worker 回收。 | `backend/infrastructure/queue/postgres_queue.py` | 已实现 |
| Worker readiness | 最近一次可见的 Worker 进程存活心跳投影，不等同于某一 Task 的 lease，也不能证明任务已成功。Redis 不可用或无可见心跳时为 `unknown`，不推断为停止；心跳独立探测并在连接恢复后重建投影。 | `WorkerRuntime._readiness_loop/heartbeat`；`RedisNotifier.ready_worker_count/probe`；`backend/api/routes/health.py:ready` | 当前代码已实现；ADR-002 两轮纳入目标已复验，范围限制见报告 |
| `worker_id` | Worker 进程的稳定身份，用于 lease 和日志关联，不是独立业务实体。 | `backend/workers/runtime.py`；`TaskModel.worker_id` | 已实现 |
| `generation` | 每次重新领取 Task 时递增的租约代数；所有续租、进度和完成写回必须匹配当前代数。 | `backend/infrastructure/queue/postgres_queue.py`；`TaskModel.generation` | 已实现 |
| `attempt` | 同一 Task 的第几次执行尝试；增加 attempt 不会创建新的 Thread、用户 Message 或 Run。 | `TaskModel.attempt`；`backend/infrastructure/queue/postgres_queue.py` | 已实现 |
| `Run Attempt` | 完整项目中对一个业务 Task 的一次 Worker 执行尝试，承载 worker、generation、lease 和 progress。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD1 设计 | 规划中 |
| `QueueMessage` | 完整项目中用于分发持久 Task 的消息身份和可用时间提示；不取代 Task 事实。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD1 设计 | 规划中 |

## 事件、证据与 RAG 对象

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `RunEvent` | 一条属于 Run 的不可变事件记录，包含 schema_version、全Run单调 `seq`、类型和严格版本化安全数据；schema1与schema2各用自己的联合分支。 | `backend/db/models.py:RunEventModel`；`backend/api/schemas/v2/runs.py:EventResponse` | 已实现 |
| `Event Journal` | 以 PostgreSQL 为事实来源、按 Run 追加保存并可按 `after_seq` 补放的 RunEvent 集合；SSE/Redis/页面是投影。 | `backend/infrastructure/events/journal.py`；`contracts/run_event_v1.json`、`run_event_v2.json` | v1/v2已接线 |
| `Citation` | assistant Message 对本次 Run 实际召回证据的结构化引用，至少包含 document、chunk、位置和分数身份。 | `backend/workers/handlers/run_handler.py`；`MessageModel.citations_json` | 已实现 |
| `Document` | 已登记的原始文档元数据和当前索引状态，不等于一个已发布知识库版本。 | `backend/db/models.py:DocumentModel`；`backend/application/documents.py` | 已实现 |
| Document `source` | 文档登记的安全逻辑来源；Demo 上传为 `local_upload`，公开接口不提供 storage key 或宿主路径。 | `DocumentModel.source`；`contracts/document_v1.json`；`backend/api/schemas/documents.py` | 已实现（ADR-002 基础修复） |
| `Document Version` | 不可变的文档内容/解析/索引版本，可作为候选、发布和回滚边界。 | `docs/prd/SesRAG-完整项目-PRD.md` 的 PRD4 设计 | 规划中 |
| `index batch` | Demo 内部的一次候选索引批次标识；只有批次完成后才切换 `active_index_batch_id`。 | `DocumentModel.active_index_batch_id`；`backend/workers/handlers/index_handler.py` | 已实现 |
| `Chunk` | 文档经过解析和切分后的可检索文本片段，带序号、字符位置和 Embedding。 | `backend/db/models.py:ChunkModel`；`backend/domain/entities.py:ChunkDraft` | 已实现 |
| `Evidence` | 本次 Run 实际召回的纯 DTO，包含 document/chunk/不可变批次、文本、字符 offset、基础位置和分数；不把旧索引缺失位置伪造为新位置。 | `backend/domain/ports/__init__.py:Evidence`；`backend/infrastructure/rag/pgvector_store.py`；`contracts/evidence_v1.json` | 当前代码已实现；ADR-002 两轮纳入目标已复验，范围限制见报告 |
| `SourceLocation` | 原文本的 1 起算行号（txt/md）或正文段落号（docx），以及该行/段落的 0 起算右端不含字符区间；不是 chunk 序号。 | `backend/domain/ports/__init__.py`；`backend/infrastructure/rag/parsers.py`；`migrations/versions/0003_chunk_locations.py` | 当前代码已实现；旧索引 `locations=[]`，不重写历史 |
| `ParsedDocument` / `IndexedChunk` | Parser 的纯文本/位置结果和事务外构建的候选 chunk DTO；候选须由有效执行身份在短事务发布，不能污染当前 active。 | `backend/domain/ports/__init__.py`；`backend/workers/handlers/index_handler.py` | 当前代码与发布边界专项已审查；两轮纳入目标已复验，范围限制见报告 |

## Provider、Port 与 Adapter

| 术语 | 统一含义 | 来源 | 当前状态 |
| --- | --- | --- | --- |
| `Provider` | 对外部模型或 Embedding 能力的统一服务边界；Provider 失败必须映射为稳定错误语义。 | `backend/infrastructure/providers/mock.py`、`openai_compatible.py` | 已实现 |
| `ModelProvider` | 生成回答或回答增量的 Provider 接口语义。 | `backend/workers/handlers/run_handler.py`；`backend/infrastructure/providers/mock.py:MockModelProvider` | 已实现 |
| `ModelRequest` / `TokenCounter` | ModelRequest 是应用层交给 Provider 的普通消息/输出预算/证据 DTO；TokenCounter 是模型输入计数能力边界，Mock确定计数，真实配置显式绑定encoding/框架开销/校准版本。 | `backend/domain/ports/session.py`；`backend/infrastructure/providers/context_counter.py` | 已实现，校准真实性依Profile提供方 |
| `EmbeddingProvider` | 将文本转换为固定维度向量的 Provider 接口语义。 | `backend/infrastructure/providers/mock.py:MockEmbeddingProvider` | 已实现 |
| `Port` | 领域或应用层依赖的稳定能力接口，隐藏具体基础设施实现；协议/DTO 不引用 ORM、FastAPI 或厂商 SDK。 | `backend/domain/ports/__init__.py`；ADR-002 RM-07 | 当前代码及5b真实替换专项已审查；两轮纳入目标已复验，范围限制见报告 |
| `Adapter` | Port 的具体基础设施实现，例如 PostgreSQL、Redis、pgvector 或 OpenAI-compatible Provider。 | `backend/infrastructure/` | 已实现 |
| `QueuePort` / `TaskLease` | session 绑定适配器提供领取、续租、回收、开始、释放和失败结算；返回普通执行身份 DTO，不输出 ORM Model。 | `backend/domain/ports/__init__.py`；`backend/infrastructure/queue/adapter.py`；`backend/workers/runtime.py` | 当前代码已接线；两轮纳入目标已复验，范围限制见报告 |
| `VectorStorePort` | 以统一 Evidence/IndexedChunk DTO 提供候选替换和 Top-K 召回，由 application 承接事务。 | `backend/domain/ports/__init__.py`；`backend/infrastructure/rag/pgvector_store.py` | 当前代码及5b真实替换专项已审查；两轮纳入目标已复验，范围限制见报告 |
| `ParserPort` | 将受限源标识/格式解析为纯文本和基础位置；默认子进程受输入/展开/时间限制，不是任意代码沙箱。 | `backend/domain/ports/__init__.py`；`backend/infrastructure/rag/parsers.py`、`parser_process.py` | 当前代码已接线；Windows 无 Linux RLIMIT，报告单列资源边界 |

## 术语变更规则

1. 新增稳定术语时，先在本文件增加含义、来源和状态，再更新 PRD/ADR、契约和代码引用。
2. 术语含义发生实质变化时，不直接复用旧词掩盖迁移；应在本文件注明旧含义、迁移目标和取代文档。
3. 当前 Demo 的 `index batch` 不得在没有 PRD/ADR 变更的情况下直接称为公开的 `Document Version`；两者在完整项目发布流程落地前保持区分。
4. `Run`、`Task`、`Run Attempt` 和 `attempt` 不得混用：Run 是会话执行身份，Task 是持久工作项，Run Attempt 是完整项目的执行尝试，attempt 是尝试次数。
