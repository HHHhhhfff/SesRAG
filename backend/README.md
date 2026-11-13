# 后端模块

`api/` 保存 HTTP/SSE 路由与公开投影，`application/` 保存应用事务边界，`domain/` 保存稳定对象与协议，`infrastructure/` 实现适配器，`workers/` 编排租约与处理器。正式接口见 [接口文档](../docs/接口文档.md)。

## v0.3 RAG 实施模块

本轮需求／决策为PRD-003／ADR-003。下列是新增实现，旧协议兼容模块继续保留；真实模型计数前提和独立验收状态见[实施记录](../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)。

| 文件／目录 | 主要职责 |
| --- | --- |
| `domain/rag.py`、`rag_profiles.py`、`rag_snapshot.py`、`ports/rag.py` | 九格式固定路由、纯DTO、版本化配置／空间、冻结只读工具绑定与可替换能力 |
| `db/rag_models.py` | 知识库、解析Job／产物／块、构建、视图、工具、Bundle／实际上下文证据、GC记录的持久映射 |
| `application/knowledge_bases.py`、`rag_profiles.py`、`rag_operations.py` | owner范围、不可变配置导入、独立资源操作幂等；不以文件hash充当远端幂等 |
| `application/index_builds.py`、`parse_jobs.py`、`rag_task_execution.py` | 上传／重建／取消事务、单Job检查点、正常等待让出、有效租约结算和旧active保护 |
| `application/retrieval_views.py`、`retrieval.py`、`evidence_assembly.py`、`source_locations.py` | 冻结批次集合、共用诊断／检索、邻近合并、重排／dense分数及实际来源映射 |
| `application/rag_sessions.py`、`rag_run_execution.py`、`legacy_rag.py` | 接入原会话事务、schema3事实、每代只读工具、旧可信384空间守卫和旧协议新写引用FK保护 |
| `application/rag_capacity.py`、`rag_gc.py`、`rag_retention.py` | 保守软预算、带引用保护的批次清理、独立诊断七天保留及三十天墓碑；保留未知提交摘要 |
| `infrastructure/rag/office_validation.py`、`isolated_processing.py`、`local_structure.py`、`structured_chunker.py` | 原件格式预检、有界子进程、本地文本结构／规范文本切片；不解析办公正文或执行Office |
| `infrastructure/rag/mineru_client.py`、`mineru_outputs.py`、`html_tables.py` | 精准API申请／原件PUT／轮询／下载、安全包验证、HTML表格转文本结构、可靠PDF页映射 |
| `infrastructure/rag/download_safety.py`、`artifact_store.py` | 精确域／逐跳出站检查、DNS绑定公网IP、限量读取、AES-GCM私有能力状态 |
| `infrastructure/rag/vector_search.py`、`providers/bailian_embedding.py`、`bailian_rerank.py`、`rag_registry.py` | PG物化范围后精确cosine排序、显式1024维、float32归一化、独立原生重排与真实／Mock替换 |
| `api/routes/v3/`、`api/schemas/v3/` | 资源／诊断／会话HTTP与SSE适配及严格公开投影；请求字段见正式接口文档 |
| `workers/handlers/index_build_handler.py`、`retrieval_diagnostic_handler.py` | 有界构建及诊断编排，复用持久队列与generation，不增平行事实源 |
| `tools/sync_rag_profiles.py`、`upgrade_rag_schema.py`、`confirm_legacy_rag_space.py` | 显式导入、分段升级至0011和有证据的旧空间确认，迁移不读模型Key／不调用云端 |
| `tools/export_rag_contracts.py`、`check_rag_providers.py`、`cleanup_rag_artifacts.py` | 契约导出／漂移检查、显式公开合成样本真实探针、安全维护入口 |

部署配置、命令和旧库回滚见[v0.3 Runbook](../docs/runbooks/rag-v3-development.md)。新向量Profile支持声明空间，`VECTOR_DIMENSION=384`只约束legacy配置。Windows子进程仍无Linux RLIMIT；容器检查补充Linux实际运行证据。旧PRD正式验收目录不纳入本轮维护。

ADR-002 增加的 `domain/ports/__init__.py` 定义纯 Python 的 TaskLease、Parser/位置、IndexedChunk/Evidence DTO，以及非空 Queue/Parser/VectorStore/Embedding/Model 协议，不引入 ORM 或厂商 SDK。

`application/task_execution.py` 统一 Task 身份、租约/截止、取消和最终消息事务；`vector_validation.py` 验证固定 384 维、有限且 float32 可表示数值。Worker Runtime 是组合根：绑定 `queue/adapter.py` 的事务适配器、`providers/factory.py` 的快照 Provider 工厂、`rag/pgvector_store.py` 的向量适配器和 `rag/parsers.py` 的 Parser；handler 实际消费这些注入依赖。

`rag/parser_process.py` 为内部解析子进程入口，不是 HTTP 接口。仅处理经过存储根目录校验的源文件；10 MiB 源、40 MiB ZIP 展开、100000 ZIP 条目/基础位置、64 MiB 序列化输出和 30 秒运行限额。Linux 另有 512 MiB 地址空间/30 秒 CPU 限额；Windows 不提供 RLIMIT。取消或超时回收子进程，不承诺通用沙箱。纯文本模式按 txt/md 行、docx 正文段落提供位置；空白非空文本保留既有字符切分行为，真正空文本永久失败。

索引候选在数据库事务外构建；最终 Task→Document 锁、chunks/active/Task succeeded 一次提交。任何 flush 后跨租约/截止均回滚；失败统一交 Runtime/Queue 结算。`migrations/versions/0003_chunk_locations.py` 为位置字段迁移，降级保留已有证据列；旧历史不补造位置。

运行与配置入口见根 README；测试职责与命令见 [集成测试](../tests/integration/README.md)。上传路由的有界读取不代表 multipart 接收阶段的网络或磁盘总配额。

Worker JSON 日志保留 `document_id/parse_job_id/index_batch_id/run_id/retrieval_execution_id/task_id/worker_id/generation/attempt/error_code/stage/duration_ms`；不适用的关联为空。新索引任务从 IndexBuild 读取真实文档及解析身份；每次 parse/chunk/embed/publish 调度和 Run 的 retrieval/generation 边界记录单调时钟耗时，普通生命周期记录耗时为零。`application/stage_observation.py` 提供旁路阶段观测，观测异常不改变业务结果；不读取正文或输出原始异常。

`infrastructure/rag/cloud_html.py` 仅清理云端 full.md 的原始 HTML 和外部图片资产，再转换正常 HTML 表格；代码块及行内代码保留字面语义。清理发生在规范文本与区间生成前，本地 txt/md 位置算法不变。schema3 的 S1… 来源编号按最终选入 ContextPlan 顺序重算并参与预算；计划、ContextEvidence 和 Citation 同序。

`api/schemas/v2/` 是 ADR-003 的独立契约 DTO：`threads.py` 定义会话/分支/消息请求及分页投影，`runs.py` 定义 Run、安全快照、精确两代Event payload与显式操作请求，`models.py` 定义安全 Profile 与成对版本选择，`context.py` 定义无正文/凭据的上下文与摘要来源元数据。`__init__.py` 提供禁止额外字段的基类；身份字段保留字符串以兼容既有内部 DTO。这里只校验公开结构，不代替业务层的 owner/路径/版本/租约判断。

ADR-003 已挂载 v2 Thread/Branch/Model/Run/Context 路由及显式 Run 操作，并完成 v1 legacy 守卫和协议兼容。`application/session_threads.py` 管理安全投影、UTC 时间、keyset 游标与元数据升级事务；`branches.py` 管理父链/有效 fork 区间、分叉、100 分支/32 层限制；`session_operations.py` 保存请求摘要与原子幂等结果。`domain/ports/session.py` 提供纯 Python Branch/路径区间 DTO 与端口，`infrastructure/session/branches.py` 实现 SQL 区间读取、分页和稳定顺序锁定，HTTP 详情不会物化全部历史。迁移 `0004`～`0006` 支持 Branch、ModelProfile/ContextPlan 与 Run 状态/唯一性约束；Compose/真实 PostgreSQL 两轮验收结果见 TEST-002。

`api/routes/v2/models.py` 和 `application/model_profiles.py` 提供安全的 Profile 列表与运行时可用性原因；`infrastructure/session/model_profiles.py` 是元数据唯一真源，`backend.tools.sync_model_profiles` 仅在显式调用时导入 JSON，启动不读取或覆盖配置。示例位于 `docker/model-profiles.example.json`。版本内模型/预算/tokenizer/生成参数不可变，同版本差异拒绝，只有 enabled/default 策略可调整。真实Provider必须使用显式tiktoken，不能使用Mock计数器。`providers/registry.py` 按 schema 2 快照重建生成与Embedding Provider；retrieval冻结Embedding kind、无凭据地址、模型和Secret alias，恢复不读取当前Settings覆盖。Secret 仅允许 `env:MODEL_API_KEY` alias，Embedding 仍固定 384 维并独立于生成 Profile。HTTP成功与错误正文均受累计字节和绝对时长限制。

`application/context.py` 是无 ORM 的确定性预算、完整轮次裁剪和 `trim_then_extract_v1` 摘录算法；`infrastructure/session/context.py` 批量加载正文，候选身份从 `resolve_scope` 和显式 `list_path_messages(..., limit=200)` 取得。`providers/context_counter.py` 提供 Mock 词法计数与 `token_counter_from_profile(profile)`：真实计数器从冻结 Profile 读取 encoding、消息/请求框架开销、校准版本；counter version 是覆盖完整配置的 36 字符 `tt1:` 摘要，适配持久化 40 字符上限。完整配置仍在 Snapshot 中，真实服务须自行校准。Snapshot 2 校验 Context/执行字段、上限及其与冻结 Profile 的一致性。

真实计数器当前支持`cl100k_base`离线资产，由Docker构建显式预热；`load_encoding_offline`先检查资产存在、大小和SHA-256，再进入tiktoken，缺失/损坏/不支持的encoding明确不可用。API/Worker的普通请求不负责下载词表。扩展encoding时须在`ENCODING_ASSETS`登记固定来源/hash并同步构建预热和离线负样本；标准tiktoken缓存目录变量只影响查找位置，不触发隐式下载。

`application/session_runs.py` 管理 v2 消息与显式新 Run 的 Thread→Branch 原子创建、幂等重放、Profile 选择和安全读取；`api/routes/v2/runs.py` 挂载控制与分页/SSE。`application/session_execution.py` 在无行锁阶段执行 mandatory 预检、RAG、历史规划和 ModelRequest；短事务按 Task→Run 重新授权发布每代计划/摘要，独立 100ms 时钟 flush 有界 delta，最终沿 Task→Run→Thread→Branch 结算。schema1 handler 和 payload 保持旧协议。取消中的 Task 保持活动直到专用有效租约确认或过期回收；异常/停机 release 不把 cancelling 回排。

失败/取消的无完整回答输入以 `incomplete_turn` 记录省略；用户输入创建者曾失败但显式 retry 已成功时，按实际 assistant 的输入关系保留完整轮次。摘要提取异常回退 `trim_only_v1`，结构化日志记录 `SUMMARY_EXTRACTION_FAILED` 和关联身份，不包含源文或异常正文；计数器/mandatory 故障不会伪装成摘要回退。

`../migrations/versions/0011_rag_source_integrity.py` 将切片来源绑定批次派生来源状态，并允许可信旧空间确认在同一事务更新；PostgreSQL另外保护来源转换与确认依据。`ChunkPolicy.max_chunks`冻结切片数量预算，超限在Embedding外发前整体失败。
