# 003：RAG检索增强与MinerU接入实施结果调研

| 字段 | 内容 |
| --- | --- |
| 编号／文档版本 | 003／1.0 |
| 日期 | 2026-11-08（America/New_York） |
| 项目版本／分支 | v0.3.0／`sesrag_v0.3` |
| 调研状态 | 已完成源码、契约、迁移及已有证据核对；本文件不代表全部产品验收通过 |
| 代码基线 | 当前实施提交 `b4c134c`；本轮实施差异基点 `58d9d1d4207fc61d043cbf3271308f8d14d71005` |
| 产品依据 | [PRD-003：RAG检索增强与MinerU接入](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md) |
| 决策依据 | [ADR-003：实施方案](../adr/003-sesrag-rag-mineru-implementation-plan.md) |
| 已有交付记录 | [PR-003：实施结果简要说明](003-SesRAG-RAG检索增强与MinerU接入-PR.md)；本文件进一步核对具体机制、差异和测试关注点，不替代该交付记录 |
| 其他依据 | [正式接口文档](../接口文档.md)、[稳定术语](../../CONTEXT.md)、[开发与升级Runbook](../runbooks/rag-v3-development.md) |
| 文档用途 | 为后续独立的测试方案、测试点和测试用例提供可追溯的当前实现基线，不在本次调研中修改产品代码或执行付费上游验收 |

## 1. 调研范围、方法与结论口径

本次围绕 PRD-003 的46项功能需求及12项非功能需求，交叉阅读领域对象、应用用例、基础设施适配器、Worker、数据库迁移、API/JSON Schema、前端和本轮新增测试。调研以当前可执行源码为准，同时比较 PRD 的目标与 ADR 的决策，不能仅凭简要说明中的“已实现”认定验收完成。

本文使用三种结论口径：**已落地**指已找到对应代码路径和约束；**部分落地／待验收**指主路径存在，但部分目标有缺口或缺正式验证；**受限**指当前配置或验证条件阻止完整证明。历史检查日志只作为已有证据，本次实际运行的检查单列于第9节。代码静态存在、Mock通过、真实协议请求成功和完整产品验收是不同层次的证据。

总体结论如下：

- 知识库、四类版本化配置、不可变向量空间、九格式固定解析路由、逐次办公原件外发确认、异步解析与构建、PG精确检索、重排、邻近增强、冻结视图、受控工具、实际上下文引用和工作台主链路均有代码落点。
- 向量数据库是 **PostgreSQL + pgvector**。本轮生产路径在SQL中做范围过滤、cosine排序和LIMIT；没有引入Milvus，也没有建设ANN或混合检索。
- 真实MinerU已有七种办公格式和额外扫描PDF的安全协议观测；真实Embedding/rerank也有独立协议观测。**真实模型的专用输入计数仍未完成校准，正式Profile受 `INPUT_COUNTER_UNVERIFIED` 阻断**，不能据此宣称真实模型全链路或检索效果通过。
- 回答结构化Citation的来源约束已落地，但模型输入未加入与展示引用一致的逐条编号，**正文引用标记的稳定对应闭环仍有缺口**；日志关联和全阶段计时也只部分实现。
- 标注效果集、万级Chunk性能验证和本轮独立正式验收工程尚不能由现有开发检查替代。后续测试应把已实现路径、代码缺口和外部前提受限分别列出。

## 2. 从既有版本演进的边界

### 2.1 保留的事实源与基础能力

继续采用FastAPI、Vue 3/Pinia、PostgreSQL、Redis和Docker Compose。`Thread → Branch/Message → Run → Task → Event Journal` 的会话主模型保留；PostgreSQL是Run、任务、解析和构建事实源，Redis和SSE只传递通知或投影。新RAG没有另建绕过持久会话的平行聊天接口。

当前owner仍来自服务端`Settings.owner_id`，本轮没有新增登录、多租户认证或完整RBAC。源码里的owner检查是资源范围约束；后续越权用例应使用受控多owner数据和服务端身份条件，不能把当前演示配置视为生产认证方案。

原来的Document、Chunk、旧 `index_document` 任务及v1/v2会话历史并未整体删除。新能力新增v3资源与会话契约入口，复用既有事务、队列、取消和终态提交机制。旧文本写入被补入新批次和引用保护体系；旧DOCX写入则显式要求升级，避免旧客户端未经确认就由本地解析变成外发。

### 2.2 新增模块的职责

| 层次 | 主要落点 | 当前职责与边界 |
| --- | --- | --- |
| 领域与协议 | [domain/rag.py](../../backend/domain/rag.py)、[rag_profiles.py](../../backend/domain/rag_profiles.py)、[rag_snapshot.py](../../backend/domain/rag_snapshot.py)、[ports/rag.py](../../backend/domain/ports/rag.py) | 固定路由、版本化配置和空间hash、冻结快照、只读工具和适配边界；不在领域层解释厂商响应。 |
| 持久化 | [db/rag_models.py](../../backend/db/rag_models.py)、[db/models.py](../../backend/db/models.py)、迁移0007～0010 | 新对象、关系约束、不可变事实、多维向量、历史引用保护与任务协议。 |
| 应用编排 | [application/index_builds.py](../../backend/application/index_builds.py)、[parse_jobs.py](../../backend/application/parse_jobs.py)、[retrieval.py](../../backend/application/retrieval.py)、[rag_sessions.py](../../backend/application/rag_sessions.py) | 上传/重建、检查点推进、冻结视图、检索与诊断、会话接线；外部等待不占用长期数据库事务。 |
| 外部适配 | [infrastructure/rag/](../../backend/infrastructure/rag/)、[providers/rag_registry.py](../../backend/infrastructure/providers/rag_registry.py) | 本地结构解析、MinerU、产物安全、切片、PG查询、真实/Mock模型；切片和增强当前主要是独立函数模块，并非全部已有可替换Port。 |
| 执行与投影 | [workers/runtime.py](../../backend/workers/runtime.py)、[handlers/index_build_handler.py](../../backend/workers/handlers/index_build_handler.py)、[frontend/src/stores/rag.ts](../../frontend/src/stores/rag.ts) | 持久队列和有效代推进、等待让出、前端状态读取及事件投影；页面不能宣布数据库终态。 |

本轮独立测试文件集中于通用unit/api/integration下的RAG v3文件、`tests/fixtures/rag-v3/`和对应前端测试。**前轮 `tests/sesrag-persistent-session-workspace-test/` 正式验收目录不属于本轮实施范围**；运行共用底层回归不等于维护上一轮验收工程。

## 3. 核心对象、关系与不可变边界

以下字段是解释行为所需的主要字段，不是第二份完整接口契约。正式字段与读写规则以[接口文档](../接口文档.md)和JSON Schema为准。

| 对象 | 主要身份／字段 | 当前含义、关系与边界 |
| --- | --- | --- |
| KnowledgeBase | `id/owner/name/enabled/is_default/embedding_space_id/scope_revision` | 同owner名称去首尾空白后1～80字符，精确匹配唯一；默认库受部分唯一约束。绑定空间及owner不可随意改变；停用阻止新上传/重建/视图，保留历史依赖读取。 |
| 四类Profile | kind、identity、version、config/hash、enabled/security状态 | Parser、Embedding、Rerank、Retrieval分别版本化；导入同身份版本异内容返回冲突。普通选择停用和安全阻断分开：已冻结执行可继续使用普通停用版本，安全blocked仍拒绝。 |
| EmbeddingSpace | provider/model/revision、维度、normalization、metric、purpose_mapping及描述hash | 维度1～2000；同维不同模型或规则仍是不同空间。生成模型切换不能改变库空间；旧384维数据来源不明不能凭维度猜测归属。 |
| Document | owner、KB、不可变source hash/存储身份、extension、tags、active/latest指针 | 独立上传得到独立文档身份；源内容变化不能覆盖旧源。标签和库范围影响新视图；active与最新尝试分开表达。 |
| RagOperation | owner/scope/key、request hash、结果身份 | 对上传/重建/诊断等资源操作去重；同键异请求409。它保证本地业务重放，不等同于MinerU提供exactly-once。 |
| ParseJob / Artifact / ParsedBlock | document/source/parser hash、stage/state、远端能力状态、text hash、块/位置 | Job保存单一路线检查点；私有远端能力单独加密存储。Artifact和块提供规范文本及可靠位置，后续切片不重新猜造原件结构。 |
| IndexBuild / Chunk | document、batch、parse job、冻结chunker/space、seq、text hash、vector及dimension | 候选与active隔离；Chunk按批次稳定顺序。成功Build和已发布Chunk由PG保护不可UPDATE；最终发布同时更新指针和任务结果。 |
| RetrievalView | owner/KB/space、冻结批次清单、filters、scope revision/hash | 某次执行实际可见的知识范围；不是指向“随时最新active”的动态查询。后续发布或标签修改不会改写已冻结视图。 |
| RetrievalExecution / ToolCall | view、safe snapshot、状态/分数/候选/计时、Task/generation、error/degradation | 独立诊断或Run工具执行的检索事实。Tool成功不表示Run成功；一次有效执行代只有受控逻辑调用。 |
| EvidenceBundle / Component | doc/batch、命中与邻近片段、规范文本范围/hash、来源、dense/rerank身份 | 合并同文档同批次文本区间；组件记录来源身份，文本不因重叠组件重复堆叠。增强范围与生成最终输入范围是两个阶段。 |
| ContextEvidence / MessageCitationLink | ContextPlan、Bundle/组件、实际范围/hash、Message/Citation关联 | 只保护真正选入模型上下文的证据；最终结构化引用从这些范围生成。并不意味着回答正文已掌握对应引用编号。 |
| LegacyEvidenceRef / GCRecord | 旧引用保护关系；过期资源墓碑 | 保护旧会话可恢复的历史批次；已丢失旧Chunk不伪造。诊断过期墓碑用于410，不是恢复数据副本。 |

主要代码见[ORM对象](../../backend/db/rag_models.py)、[Profile导入与解析](../../backend/application/rag_profiles.py)、[库用例](../../backend/application/knowledge_bases.py)、[操作幂等](../../backend/application/rag_operations.py)。`replay()`在PostgreSQL使用advisory事务锁处理“记录尚不存在时”的并发重放；唯一约束作为持久后盾。关系约束还校验active/latest所指Build属于同Document和批次，不能只靠前端传入ID保持一致。

## 4. 上传、解析和检查点恢复的实际机制

### 4.1 九格式固定路线与授权

`parser_for()`、`ParseRequest.resolve()`在[domain/rag.py](../../backend/domain/rag.py)规定 `format_router_v1`：

- `txt/md` 固定本地解析；不转换为DOCX，不调用MinerU，提交云端授权字段反而被拒绝。
- `doc/docx/pdf/xls/xlsx/ppt/pptx` 固定MinerU原件流程；每次上传或重建均要求 `cloud_consent=true` 与当前授权版本 `mineru-office-outbound-v1`。授权不是永久记住的用户偏好。
- 办公路线未配置或已知不可用时拒绝新构建；解析确定失败、无文本、超时等均明确失败，**没有转格式、换解析器或本地回退成功状态**。

[office_validation.py::validate_source](../../backend/infrastructure/rag/office_validation.py)在申请远端工作前校验basename、扩展名、MIME、非空和10MiB限制。文本要求UTF-8；OOXML执行ZIP成员/XML关系等结构安全预检；OLE校验相应流及已知危险标记。PDF只做文件头/尾等浅验证，不包含完整本地PDF解析、页数探测或加密状态识别。上述预检不是本地Office正文解析，不应在测试报告中写成能拒绝一切恶意/畸形文件。

### 4.2 操作幂等、冻结与产物复用

[index_builds.py::upload_document/start_build/rebuild_document](../../backend/application/index_builds.py)在受owner与库状态约束的短事务中登记操作、Document、ParseJob、IndexBuild和Task，冻结路由、ParserProfile、chunker、模型空间及预算。同一操作键重放返回原结果；不同操作对相同源字节可以创建独立Document，不以source hash跨owner复用资源。

重建同Document时，可复用source hash和parser/protocol hash完全一致的成功Artifact；已有同配置活动构建可复用，冲突配置返回 `INDEX_BUILD_BUSY`。旧本地DOCX产物不会被认作新MinerU解析产物。即使可能复用办公Artifact，重建请求仍须逐次授权。未知远端结果后的新工作按 `remote_outcome` 要求潜在重复成本确认，并非只判断一个stage字符串。

### 4.3 MinerU请求与阶段推进

[MinerUClient](../../backend/infrastructure/rag/mineru_client.py)采用精准API本地文件流程：向固定API origin申请上传URL，绑定唯一data_id/文件身份，原字节PUT，再查询原batch结果。PUT不附带API Bearer；应用没有为了“上传后解析”再创建第二套任务。

[parse_jobs.py::advance_parse_job](../../backend/application/parse_jobs.py)一次有效领取主要推进一个阶段。持久stage含 `preparing → submitting → uploading → remote_waiting/running/converting → downloading → completed`；Job state另行表达 queued/running/waiting/succeeded/failed/cancelled，不能把远端done等同于本地active成功。申请前先提交 `submitting` 检查点：若进程重启时只知提交可能发生，按未知结果结束，不能自动再申请。

正常远端等待由[rag_task_execution.py::yield_task](../../backend/application/rag_task_execution.py)和队列回排让出，不消耗故障failure_count。解析总deadline受Task截止和配置控制（默认解析300秒），轮询有上限（默认60次）；外部调用有有界超时。上传应答不明优先查询已知batch；恢复等待、下载仍使用同一远端工作身份。远端签名能力由[ArtifactStore.save_state](../../backend/infrastructure/rag/artifact_store.py)以AES-GCM保存，32字节密钥、12字节随机nonce及对象key作为AAD，不进入公开Job响应。

### 4.4 下载、归一化和可靠位置

[download_safety.py](../../backend/infrastructure/rag/download_safety.py)对来源host、协议/端口、DNS解析IP和每次跳转校验；[mineru_outputs.py::normalize_package](../../backend/infrastructure/rag/mineru_outputs.py)拒绝目录逃逸、符号链接、重复路径、加密成员、嵌套压缩及异常展开比。当前主要限额为10000个条目、总展开256MiB、单成员64MiB、ratio 100、路径240字符；不是无限解压后再清理。

解析产物要求唯一有效 `full.md`；[html_tables.py](../../backend/infrastructure/rag/html_tables.py)将真实Excel产物中的表格归一化为安全文本。仅图片或没有有效文本的产物返回 `MINERU_EMPTY_OUTPUT`，不下载外部资产补齐“成功”。PDF的content-list另有32MiB限制；只有唯一精确文本匹配且page_idx合法，才标记为原源已验证页码。其他情况保留规范块位置，不猜Word页码、PPT页号或Excel单元格。

[local_structure.py::parse_text](../../backend/infrastructure/rag/local_structure.py)将Markdown标题、段落、代码、表格等转ParsedBlock，避免未覆盖文本静默丢失；txt按非空行提取，保留原源行号。云端Markdown规范块与原源位置明确分开，这直接影响后续切片和证据展示的预期。

### 4.5 错误、取消和远端结果不明

认证、额度、临时网络、协议失败、明确解析失败和提交未知分别有稳定错误码。非幂等申请的网络/损坏响应/身份不明被保守归类为 `MINERU_SUBMISSION_UNKNOWN`（Job stage为 `submission_unknown`），不会自动重提；安全可重试请求也只在同一路线内有界重试。

[settle_rag_task()](../../backend/application/rag_task_execution.py)同时记录本地终态与远端结果：上游明确failed保持failed；已到下载阶段表示远端完成；已经提交或处于submitting时，本地取消/超时可记 `unknown_may_continue`。因此“本地已取消”不保证云端撤回文件、停止处理或退费。取消、截止与发布竞争受Task有效代和终态条件保护，不能用迟到产物覆盖本地结论。

## 5. 构建、检索、增强和引用的实际机制

### 5.1 候选构建和原子发布

[index_build_handler.py::process_index_build_task](../../backend/workers/handlers/index_build_handler.py)执行解析/复用 → 切片 → 批量Embedding → 发布。Artifact读取复核text hash；先存候选Chunk，分批向量化（默认batch 16），以Task进度检查点恢复，不把外部等待放进长事务。

[structured_chunker.py::split_artifact](../../backend/infrastructure/rag/structured_chunker.py)的 `structure_v1`优先选择size后半段的结构块结尾；过长块可拆，保留 `character_v1` 兼容模式。单Chunk受8192 UTF-8字节及Profile输入限制，最多50000个Chunk；实际overlap不超过片段长的一半，保证游标前进。片段hash、seq、块身份和字符范围为后续邻近扩展提供稳定依据。

发布前核对数量、连续seq、空间、维度、非空向量及文本hash，并在flush后重新校验租约。成功Build、Document active、scope_revision与Task完成原子提交；失败、取消、失租不能切active。latest已在登记构建的事务中指向最新尝试，不等于成功发布；旧active在新候选构建期间继续检索。发布新批次不会立即删除历史引用依赖。

### 5.2 模型协议与启用限制

[bailian_embedding.py](../../backend/infrastructure/providers/bailian_embedding.py)调用兼容协议 `/compatible-mode/v1/embeddings`，当前真实配置显式请求1024维；query与document用途按同一空间规则映射，不随意加入供应商未支持的参数。该适配器校验返回数量和响应索引，[vector_validation.py](../../backend/application/vector_validation.py)校验维度、有限数值、非零及float32可表示性，统一 `l2_float32_v1`，避免写入一套归一化、查询另一套。

[bailian_rerank.py](../../backend/infrastructure/providers/bailian_rerank.py)使用原生text-rerank协议；query最多2048字节，每候选前缀最多4096字节，总请求预算65536字节，按UTF-8边界分配并记录范围。响应索引须完整、唯一、在范围内，分数有限且在0～1。它不是把cosine再排一遍的假重排。

但是，当前真实Embedding/rerank的 `counter_status`仍为unverified；[rag_profiles.py::profile_reason](../../backend/application/rag_profiles.py)返回 `INPUT_COUNTER_UNVERIFIED`，阻止正式Profile使用。Profile校验只能检查校准状态及依据字段存在，不能自动证明人工填写依据真实。现有协议探针能证明请求/响应兼容，不能证明专用计数上界、长输入安全或完整入库/检索验收。

### 5.3 冻结视图、过滤和SQL Top-K

[retrieval_views.py::freeze_retrieval/load_scope](../../backend/application/retrieval_views.py)在库锁下冻结当前成功active批次集合（最多1000项）、Profile、space和过滤；query就是本次用户原文，不拼接会话历史改写查询。`document_ids/extensions=None`表示不额外限制，空集合表示空范围；`tags_all`按AND语义匹配，不能把空集合错误解释为“全部”。

执行使用已冻结manifest而非重新查最新active，仍复核owner、库、空间、依赖和安全blocked。[vector_search.py::VectorSearch.search](../../backend/infrastructure/rag/vector_search.py)在PostgreSQL以MATERIALIZED CTE先限定owner/KB/batch/space/dimension/state，再算pgvector cosine距离并ORDER BY/LIMIT；并列按distance、document、batch、seq、chunk稳定排序。只有SQLite测试后备使用Python距离计算，不能把这个分支当生产PG实现，也不能用SQLite证明PG优化器或多维隔离。

### 5.4 重排、空结果和降级

[retrieval.py::execute_retrieval](../../backend/application/retrieval.py)为诊断和Run共用：校验冻结依赖 → query Embedding → dense候选 → 可选rerank → top_k → 邻近增强。开始、Embedding前、rerank前复查安全禁用，减少配置被封禁后继续付费的窗口；不表示可以撤销已完成外部调用。

关闭、尚未执行、合法空检索、失败和显式dense降级分别记录。候选不足按实际返回，不越库或换批次补足。默认rerank失败终止；只有冻结策略为 `dense_fallback` 且错误在允许名单内，才保留dense结果并写degraded原因。认证错误 `RERANK_AUTH_FAILED`、安全/空间/向量错误不在可降级名单，不能把它们伪装成成功空结果。

冻结批次集合为空时，当前编排先验证query和冻结依赖，再直接返回empty，不调用query Embedding或rerank。无答案问题则可能仍有向量近邻：本轮没有自动无答案分类器或可调相关性阈值，不能把“没有相关答案”与“候选数为零”当成同一判定。

### 5.5 两阶段文本预算与实际输入证据

[evidence_assembly.py::assemble_evidence](../../backend/application/evidence_assembly.py)对同文档、同批次seq±radius（0/1/2）扩展，合并重叠区间，从该批次Artifact重建正文；anchor/components/hash和分数身份另行保存。默认增强总文本上限16000字符、组件上限100。**增强阶段可以截取范围，并记录 `enhancement_truncated` 及去除原因**，不能说所有阶段都完全不裁剪。

调用次序由[session_execution.py::process_session_run](../../backend/application/session_execution.py)控制：mandatory预算预检 → 付费检索和上述邻近增强 → [context.py](../../backend/application/context.py)结合历史与Bundle规划生成上下文。生成预算对Bundle整组选择/舍弃，不在Bundle内部再次静默clip。[session_execution.py::publish_plan](../../backend/application/session_execution.py)只为实际选入范围保存ContextEvidence；[task_execution.py::complete_run](../../backend/application/task_execution.py)从这些范围生成Citation2/MessageCitationLink，与最终assistant、Run/Task及终态Event在同一事务提交。没有进入模型输入的候选或被舍弃范围不能出现在结构化引用中。

**仍需明确的实现缺口**：`context.py::messages_for()`传入证据时主要是“非可信检索证据”提示与正文，没有逐条注入与UI引用一致的 `S1` 等标识；`complete_run()`中的 `label=str(index)` 仅是关系元数据。由此可以确认结构化引用身份受实际输入约束，不能确认回答正文能稳定生成、对应和校验逐条编号。后续须独立测试“事实引用来自实际输入”和“正文标记能正确指向展示引用”，不能把两者合并后判全通过。

结构化引用按选入集合生成，不是逐句语义支持校验器。某证据已进入Prompt并形成Citation，不等于模型回答中的每个断言都受该证据支持；正确性和错误引用仍须结合标注内容单独验收。

### 5.6 历史证据的读取与分页

[retrieval.py::read_bundle](../../backend/application/retrieval.py)先通过Execution/View检查owner，再按Bundle固定批次读取Build/Artifact/Component。它复核Artifact全文hash、组件所属document/batch、组件是否位于原Chunk范围内，以及相应正文片段hash；缺失或不匹配返回`EVIDENCE_UNAVAILABLE`，不会换用当前active重新拼一份“历史证据”。

正文每页最多4000字符，`offset`是Bundle正文内相对字符偏移；组件与位置里的区间则相对规范Artifact文本。当前分页只切分`text`，返回的components/locations仍描述整个Bundle，不代表当前页已含全部组件正文。[EvidenceViewer.vue](../../frontend/src/components/EvidenceViewer.vue)沿`next_offset`续读，并按Bundle身份/epoch丢弃迟到响应。后续应分别断言分页拼回的固定正文、元数据范围和原源位置质量，不能混用三个坐标含义。

## 6. 持久会话、工具、事件和工作台

### 6.1 新Run冻结和执行代隔离

[rag_sessions.py](../../backend/application/rag_sessions.py)接入既有Thread/Branch事务创建schema3 RunSnapshot及RetrievalView，冻结非Secret完整RAG配置与实际批次。默认库、标签、active、模型选择等后续变化只影响新用户输入；显式retry/regenerate默认保留来源Run的RAG快照和视图。无可靠旧视图的历史Run不能用当前知识冒充过去，返回 `LEGACY_RETRIEVAL_VIEW_UNAVAILABLE`。

显式retry/regenerate可按既有会话契约选择新的生成ModelProfile；这一选择不重选原Run的EmbeddingSpace、RetrievalProfile或RetrievalView。应分别核对生成模型变动与检索快照保持，不能将“复用RAG配置”误解为所有生成参数永远禁止调整。

[rag_run_execution.py](../../backend/application/rag_run_execution.py)将版本化只读 `rag.search@1`作为固定工具接入现有执行。输入无法覆盖owner/space/view或注入URL、SQL；工具结果按不可信检索证据放入模型消息，不提升为系统授权。每Task/generation受逻辑调用次数约束；自动队列重试不创建新的会话Run或用户消息，旧代迟到不能写新代结果。生成失败、工具成功和Run最终成功分别表示。

### 6.2 事件与三代兼容

v3 Run/Event/Context/Citation与v1/v2历史并存。Event Journal继续按Run seq追加，SSE断线通过after_seq或Last-Event-ID补放；Redis通知不是终态事实源。[events/journal.py](../../backend/infrastructure/events/journal.py)与迁移保护保持Journal不可更新/删除，前端按序号去重，工具完成不能提前宣布回答成功。

v1 txt/md保留本地旧契约，新增写入时补齐可引用批次及连续文本Artifact；v1 DOCX上传/重建返回 `DOCUMENT_WRITE_UPGRADE_REQUIRED`，不静默外发。旧客户端遇到无法表达的schema3需升级。历史旧引用能保护存在的Chunk，已经被前版本删除的文本无法重造；迁移不改写旧Message/Event JSON。

### 6.3 前端交互与安全展示

[RagPanel.vue](../../frontend/src/components/RagPanel.vue)、[stores/rag.ts](../../frontend/src/stores/rag.ts)负责库/Profile、开关、Top-K、重排、半径、过滤和诊断；候选预算candidate_k由所选Profile携带，当前页面没有独立candidate_k输入。[stores/documents.ts](../../frontend/src/stores/documents.ts)及上传组件负责九格式、逐次授权、active/latest、刷新/重建/取消。未确认办公外发不提交；txt/md不显示可选增强开关；未知进度不应展示伪百分比。设置只影响后续Run，诊断不创建Message/Run或调用生成模型。

[EvidenceViewer.vue](../../frontend/src/components/EvidenceViewer.vue)展示文档/批次、分数、片段正文、位置、组件和hash；parser信息在上传/构建投影，rerank降级在RagPanel诊断或RunTimeline事件中表达，不能把这些不同投影混写为EvidenceViewer已直接显示。[markdown/render.ts](../../frontend/src/markdown/render.ts)清洗外部Markdown并阻断外部资产/脚本。规范块位置必须与原源位置区分，缺页码/单元格等不猜造。

前端用epoch等控制迟到响应污染当前选中对象；上传存在保留未知操作键的路径。**不能据此概括所有写操作均保留未知结果键**：重建当前每次生成 `crypto.randomUUID()`，没有与上传完全相同的pending重放管理。重建请求已到服务端但应答丢失时应重点测试是否误启重复操作或只能由后续身份查询恢复。

### 6.4 接口与契约的实际变动边界

正式请求、响应和错误表统一维护在[接口文档第8节](../接口文档.md#8-v03-rag-与-mineru接口)，本节只说明实施落点和兼容关系。

| 变动 | 实际文件／对象 | 调研结论 |
| --- | --- | --- |
| 新增v3资源与诊断入口 | [routes/v3/resources.py](../../backend/api/routes/v3/resources.py)、[retrieval.py](../../backend/api/routes/v3/retrieval.py) | 知识库/Profile/文档/标签/构建/取消/切片与独立诊断/Bundle读取有独立DTO；不将远端能力URL或私有路径作为前端下载接口。 |
| 新增v3会话适配入口 | [routes/v3/sessions.py](../../backend/api/routes/v3/sessions.py)、[application/session_runs.py](../../backend/application/session_runs.py) | 新消息、事实读取、Context/Event/SSE、取消/重试/再生成进入既有Thread/Message/Run事务。Thread/Branch元数据及生成ModelProfile目录继续复用v2，没有另一套v3会话身份库。 |
| 修改旧写入与读取兼容 | [application/documents.py](../../backend/application/documents.py)、[session_threads.py](../../backend/application/session_threads.py)、[legacy_rag.py](../../backend/application/legacy_rag.py) | v1 DOCX写入要求升级；文本旧写入口保留。v3能读三代历史，旧客户端无法表达schema3时明确升级；没有把旧JSON改写成新版本。 |
| 新增16份契约及前端同步 | [export_rag_contracts.py::SCHEMAS](../../backend/tools/export_rag_contracts.py)、[contracts/](../../contracts/)、[generate-api-types.mjs](../../frontend/scripts/generate-api-types.mjs)、[api-v3.ts](../../frontend/src/types/api-v3.ts) | 资源/Run/Message/Event/Context按v3命名，Citation/Evidence/工具结果按v2，固定工具定义/输入按v1。文件后缀不能一律当作全系统版本；它们各有自己的schema_version或协议身份。 |

前端的[parseV3Event](../../frontend/src/events/rag-event-stream.ts)验证版本、Run/seq、执行身份及必要载荷，再交给store去重；其运行时检查不是后端完整JSON Schema联合验证。前端生成类型同步通过也不能证明恶意或畸形Event的每个字段都已在浏览器端严格拒绝。

### 6.5 Worker、等待和并发配置的实际口径

[WorkerRuntime._dispatch/run_forever](../../backend/workers/runtime.py)处理`run/index_document/index_build/retrieval_diagnostic`四类Task。当前每个Worker进程仍串行`await run_once()`，不会因将并发配置调大就自动生成多个执行协程；租约心跳与readiness可独立运行，正常云端等待持久让出后可领取其他工作。收到停机信号后停止领取，对在途执行遵守宽限期、取消、显式释放和租约回收流程。

[claim_next_task](../../backend/infrastructure/queue/postgres_queue.py)对`index_build/retrieval_diagnostic`计数，并以跨Worker的PG事务锁共享限制：有效容量为`min(RAG_PIPELINE_CONCURRENCY, RAG_TMP_BUDGET_BYTES // 384MiB)`。等待已释放租约不占运行槽；`run`内嵌的检索不属于这两个Task类型的专用计数。ADR配置表称“每Worker文档／诊断上限”，与当前全局门限口径有差异，应在后续文档同步和并发测试中明确，不能据配置值直接承诺吞吐。

`attempt`记录物理领取次数，正常轮询可能增加；新任务的错误重试上限依据`failure_count`，不能因正常等待耗尽错误预算。Worker日志中的`success`只表示本轮handler返回，等待让出也可能出现；业务成功必须以数据库Task/Build/Run终态为准。

## 7. 异常、安全、迁移与生命周期核查

| 条件／风险 | 当前实现行为和定位 | 后续验证应观察什么 |
| --- | --- | --- |
| 安全blocked与普通停用 | [rag_profiles.py::resolve_profile](../../backend/application/rag_profiles.py)、[retrieval.py::validate_frozen_retrieval](../../backend/application/retrieval.py)：冻结执行可用普通停用版本，安全阻断仍生效 | 创建后停用/blocked、两个外部阶段之间blocked，不静默换Profile或空间。 |
| 非幂等提交未知 | ParseJob先保存submitting；未知结果本地失败且保留可能继续，无自动重新申请 | 在请求前、已发送后、应答损坏、DB写回前分别中断；上游申请次数及重复成本提示。 |
| Worker失租／取消与发布竞争 | [rag_task_execution.py](../../backend/application/rag_task_execution.py)、[index_build_handler.py](../../backend/workers/handlers/index_build_handler.py)：task/worker/generation及租约校验、原子发布 | 两个真实PG连接竞争，新代成功后旧代不能切active、写终态或重复回答。 |
| SSRF／签名URL／压缩产物 | 逐跳host/DNS/IP检查、PUT不带Bearer、能力状态加密、ZIP限额和路径校验 | 恶意重定向、解析IP变化、截断包、重复/嵌套成员；公开响应和默认日志无私有能力。源码校验不等同于已完成攻击面验收。 |
| 无文本／模型坏向量／重排坏索引 | `MINERU_EMPTY_OUTPUT`、vector_validation、rerank响应映射验证 | 明确失败、无active切换，不返回误导性的空成功或补新候选。 |
| 数据库、日志和计时 | RetrievalExecution存候选、错误、去除原因、query_embedding/dense/rerank/assembly计时；Worker日志主要task/run/document/worker/generation/attempt/error | 新任务原有run/document可能为空，须由DB关联Build/Execution；解析缺完整分阶段耗时及通用上游trace/usage。不可宣称全链路默认日志关联已齐全。 |
| 失败候选／历史引用清理 | [rag_gc.py::collect/protected](../../backend/application/rag_gc.py)：创建时间超过默认24h且已终态，锁定并检查active/latest/view/Bundle/LegacyRef；清理不删source，保留Job错误/hash/未知摘要 | 时间按created_at，不是终态后再等24h；dry-run/apply、锁序、引用并发、重复清理、文件丢失/残留；历史批次仍可读。实际无独立gc_state状态机。 |
| 独立诊断过期 | [rag_retention.py::collect_diagnostics](../../backend/application/rag_retention.py)：创建时间超过7天、已终态且无ContextEvidence依赖才删专属view/Bundle，墓碑自创建保留30天 | 不是完成后再等7天；先410 `RAG_RESOURCE_EXPIRED`，墓碑过期后404；Run view不按诊断7天清理。 |
| 容量不足 | [rag_capacity.py](../../backend/application/rag_capacity.py)：默认总10GiB/临时1GiB软预算，构建reserve640MiB、临时reserve384MiB | 满额前置拒绝、并发预留/异常释放、active保护；这是软预算，不能当磁盘硬配额或证明无临时峰值。 |
| 旧库升级 | 0007 catalog → 显式bootstrap → 0008构建/vector → 0009视图/证据 → 0010任务/schema3 | 0007检测有效租约，存在则拒绝升级，要求先停Worker并等待；它不主动停止租约，并收尾遗留DOCX。0008要求默认库前置且隔离未知空间，0009保护旧引用；不自动付费回填或猜384向量归属。 |
| 旧空间确认及回退 | [confirm_legacy_rag_space.py](../../backend/tools/confirm_legacy_rag_space.py)仅可信来源确认；连续片段可重建精确Artifact；降级门禁拒绝新事实 | 备份前后一致性、不可恢复旧Chunk说明；出现v3事实/schema3/非384等不能删事实绕过downgrade，依赖一致备份恢复。 |

迁移实际文件 `0009_rag_views_tools_and_evidence.py` 的revision是 `0009_rag_views_tools_evidence`，缩短是为兼容Alembic版本列长度，并非缺失迁移。生产升级、配置导入和受限清理命令见[本轮Runbook](../runbooks/rag-v3-development.md)；清理工具入口是 `backend.tools.cleanup_rag_artifacts`，不应把应用模块名 `rag_gc`误写成可执行CLI。

[isolated_processing.py](../../backend/infrastructure/rag/isolated_processing.py)提供解析子进程的跨平台超时/取消后kill与wait；只有非Windows平台额外设置512MiB `RLIMIT_AS`与30秒 `RLIMIT_CPU`。正式Docker Linux环境具备该限制，Windows本机直接跑进程没有等价硬内存限制，后续不要把两种环境的资源隔离结果互相替代。

## 8. 按PRD需求逐项核对

本节编号均来自[PRD-003功能需求与非功能需求清单](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)，不是测试用例编号。表中“已落地”只描述源码实施；涉及真实服务、并发、恢复、安全或效果的要求仍须设计独立验收用例。第12节进一步列出本轮181个变更文件。

### 8.1 功能需求核对（RAG-001～RAG-046）

| PRD需求／要验证的产品行为 | 当前实现、文件与核心函数／对象 | 调研结论 | 后续测试关注点 |
| --- | --- | --- | --- |
| RAG-001：最小知识库管理、默认库和owner范围 | [knowledge_bases.py](../../backend/application/knowledge_bases.py)的create_base/patch_base/load_base；KnowledgeBaseModel及唯一约束 | 已落地。名称1～80、同owner唯一，启停及默认库持久保存；停用拒绝新工作，不撤回历史视图。 | 同名/空白/长度边界、两个owner、默认库并发、停用时在途任务和历史读取；ID越权响应不能泄漏存在性。 |
| RAG-002：不可变EmbeddingSpace、同空间写查 | [domain/rag.py::EmbeddingSpace](../../backend/domain/rag.py)的空间描述hash及[rag_profiles.py](../../backend/domain/rag_profiles.py)配置约束；[rag_models.py](../../backend/db/rag_models.py)空间与库约束；load_scope/VectorSearch | 已落地。空间由模型、修订、维度、归一化等共同确定，不因生成模型变化而变化。 | 同维异模型、同模型异维、不同normalization或用途映射、篡改库空间、旧未知384空间隔离。 |
| RAG-003：九格式、MIME/内容/文件名和10MiB限制 | [office_validation.py::validate_source](../../backend/infrastructure/rag/office_validation.py)；[domain/rag.py](../../backend/domain/rag.py)格式集合 | 已落地有界预检；PDF仅浅校验，不能称完整内容安全鉴定。 | 九格式分别正例，空/超限/伪扩展/MIME/路径、损坏OOXML/OLE、只有合法PDF头尾的畸形样本；拒绝前不申请云工作。 |
| RAG-004：固定路线与办公逐次外发授权，无回退 | [rag.py::parser_for/ParseRequest.resolve](../../backend/domain/rag.py)、[rag_profiles.py::select_parser](../../backend/application/rag_profiles.py)、start_build | 已落地。文本固定local；七办公固定mineru，缺授权或已知不可用拒绝；没有可选增强/本地兜底。 | 阻断MinerU时txt/md仍可入库；授权版本/撤销/重建授权、已知不可用、确定失败后无本地成功状态。 |
| RAG-005：安全元数据、标签和白名单过滤 | [index_builds.py::validate_tags/project_document](../../backend/application/index_builds.py)、[retrieval_views.py](../../backend/application/retrieval_views.py) | 已落地。系统身份与用户标签分离，筛选参与冻结manifest。 | 非法键/嵌套/长度、标签修改只影响新视图；document/extension/tags组合与空集合语义。 |
| RAG-006：不可变源、上传/重建本地幂等 | [rag_operations.py::replay](../../backend/application/rag_operations.py)、upload_document/rebuild_document；source hash | 已落地。本地锁与唯一键处理并发；同源独立上传不是跨owner共享文档，也不保证远端exactly-once。 | 同键同内容/异内容、首次并发、应答丢失重放、相同字节两次独立上传、变化源不能覆盖旧历史。 |
| RAG-007：MinerU申请/原件PUT/同batch查询协议 | [mineru_client.py::MinerUClient](../../backend/infrastructure/rag/mineru_client.py)、advance_parse_job | 已落地。API Bearer只发固定API，PUT无Bearer，校验file/data_id关系。 | HTTP/业务code双重错误、身份缺失/重复、申请次数、PUT字节hash、存储端不收到API Token；当前单文件工作不构造超大合批。 |
| RAG-008：持久解析阶段、未知进度、active才可检索 | [parse_jobs.py::advance_parse_job](../../backend/application/parse_jobs.py)、project_build/project_document、前端documents store | 已落地。远端状态和本地构建状态分开，无进度不应虚构百分比。 | done但尚未下载/向量化/发布、重启/刷新、unknown字段显示、latest失败与旧active并列。 |
| RAG-009：路由/Parser/协议/预算冻结 | [index_builds.py::start_build](../../backend/application/index_builds.py)、ParseJob/IndexBuild快照、profile解析 | 已落地。恢复不按新默认重选，不转换txt/md或Office格式。 | 修改默认Parser/模型/支持选项后恢复；冻结hash一致、不支持选项拒绝、原件hash不变。 |
| RAG-010：云端Markdown/JSON归一化与可靠位置 | [mineru_outputs.py::normalize_package](../../backend/infrastructure/rag/mineru_outputs.py)、[html_tables.py](../../backend/infrastructure/rag/html_tables.py)、source_locations | 已落地。唯一full.md和有效文本要求，PDF可靠匹配才给原页，其他明确规范块位置。 | 八类真实输出分别检查正文/标题/表格；畸形content-list、重复text、缺坐标、只有图片；不猜Word/PPT/Excel坐标。 |
| RAG-011：安全下载、ZIP和资源限额 | [download_safety.py](../../backend/infrastructure/rag/download_safety.py)、normalize_package、ArtifactStore | 已落地主要防护，仍需故障/恶意输入验收。 | 私网/DNS/重定向、Token传播、Zip Slip/符号链接/重复成员/嵌套包/炸弹/截断；失败后临时空间可清理。 |
| RAG-012：检查点恢复、正常等待不耗错误、拒绝旧代 | [parse_jobs.py](../../backend/application/parse_jobs.py)、[rag_task_execution.py::yield_task/lock_build_execution](../../backend/application/rag_task_execution.py)、PostgresQueue | 已落地。单工作恢复和有效代写回有落点；submitting未知不能重提。 | 在上传/等待/下载各断点重启，正常轮询多次不耗failure_count；两Worker旧代迟到写回。 |
| RAG-013：认证/额度/临时错误/超时/提交未知分类 | MinerUClient错误映射、[rag_task_execution.py::settle_rag_task](../../backend/application/rag_task_execution.py)、start_build | 已落地。安全请求有界重试；非幂等未知结束并保留may_continue，人工新工作提示重复成本。 | 401/403/429/5xx/网络断开/坏响应/明确failed/无文本；上游可能继续与本地失败分别可见。 |
| RAG-014：本地取消/总截止、不承诺远端取消 | [index_builds.py::cancel_build](../../backend/application/index_builds.py)、settle_rag_task、Worker截止检查 | 已落地。本地终态与remote_outcome分离，不能撤销已外发事实。 | 申请前/提交不明/远端等待/已done/发布瞬间取消，最终只有一个本地终态，旧active不受损。 |
| RAG-015：统一ParsedBlock与本地/云端来源映射 | [local_structure.py::parse_text](../../backend/infrastructure/rag/local_structure.py)、normalize_package、ParsedBlockModel | 已落地。文本不依赖MinerU；办公由云端产物归一化，无本地正文回退。 | txt行号、Markdown标题/代码/表格、未覆盖文本保留、云端规范块与原源位置区分，各格式独立样本。 |
| RAG-016：结构切片/长块拆分/兼容窗口/输入限额 | [structured_chunker.py::split_artifact](../../backend/infrastructure/rag/structured_chunker.py)、chunker配置、Embedding计数门禁 | 已落地切片算法；真实专用计数校准未完成，不能判真实长输入安全通过。 | size/overlap非法值、长中文/emoji、结构边界和字节上限、前进无死循环、真实计数校准后超限预拒绝。 |
| RAG-017：不可变Chunk批次、seq/hash/块/位置 | [db/models.py::ChunkModel](../../backend/db/models.py)与0008/0009约束、split_artifact、[source_locations.py](../../backend/application/source_locations.py) | 已落地。相同文本跨文档保持不同身份，PG保护发布后不可UPDATE。 | seq连续、重建新身份、同文本不同源、字符范围与位置精确映射；非法直接写入和旧引用保护。 |
| RAG-018：独立EmbeddingProfile/Space和真实多维链路 | [bailian_embedding.py](../../backend/infrastructure/providers/bailian_embedding.py)、[rag_registry.py](../../backend/infrastructure/providers/rag_registry.py)、EmbeddingSpace | 部分落地/受限。384及1024存储/协议证据存在；真实Profile因计数未校准不可用，完整真实入库/查询未验收。 | 先校准计数并锁Profile；真实文档及query同空间、384与不同维度隔离、1～2000边界，不以Mock替真实通过。 |
| RAG-019：文档/query向量有效性校验 | [vector_validation.py](../../backend/application/vector_validation.py)、BailianEmbedding、VectorSearch | 已落地。数量、维度、有限值、零向量、float32与归一化一致检查。 | NaN/Inf/超范围/零/错维/少返回/重复index、微小向量、非法query与候选发布不发生。 |
| RAG-020：候选隔离、有效代和原子active发布 | [index_build_handler.py::process_index_build_task](../../backend/workers/handlers/index_build_handler.py)、lock_build_execution、迁移guard | 已落地。有完整性验证及flush后再验租约，不对外暴露半批次。 | 各阶段故障、失租/取消/提交竞争，真实PG读者并发，不可变触发器、active/Task/Build一致终态。 |
| RAG-021：历史批次/引用/产物保留及范围清理 | [rag_gc.py::protected/collect](../../backend/application/rag_gc.py)、LegacyEvidenceRef、ContextEvidence关系 | 已落地主要保护；旧实现已删除内容不可恢复。 | 新发布后旧Run/引用逐字一致，view/Bundle/旧协议新引用保护、并发GC、source不删、摘要留存。 |
| RAG-022：同源冻结配置重建与合法复用 | [index_builds.py::start_build/rebuild_document](../../backend/application/index_builds.py)、ParsedArtifact复用检查 | 已落地。相同配置活动工作复用、冲突拒绝；办公重建仍确认外发。前端未知重建键需另测。 | 同/异Parser协议hash、旧本地DOCX不能冒充MinerU、源/owner匹配、应答丢失重复点击、旧active一直可用。 |
| RAG-023：PG精确cosine、授权过滤先于计算与LIMIT | [vector_search.py::VectorSearch.search](../../backend/infrastructure/rag/vector_search.py)、[pgvector_store.py](../../backend/infrastructure/rag/pgvector_store.py) | 已落地。MATERIALIZED范围CTE和数据库排序；已有PG开发probe，不等于万级性能通过。 | 独立距离对照、并列稳定、混维过滤、EXPLAIN/实际SQL证明不全量拉Python；实际pgvector版本记录。 |
| RAG-024：冻结view/owner/库/space/白名单过滤 | [retrieval_views.py::freeze_retrieval/load_scope](../../backend/application/retrieval_views.py)、VectorSearch、邻近查询 | 已落地。manifest限定成功批次，None/空集合语义分开，tags_all AND。 | 越owner/库/空间、候选及新批次不可见；全部过滤组合、非法SQL/URL字段、超长query拒绝，邻近不越文档批次。 |
| RAG-025：candidate_k与top_k、空/不足/稳定顺序 | [domain/rag.py::RetrievalPolicy](../../backend/domain/rag.py)、execute_retrieval/VectorSearch | 已落地。candidate_k 1～100、top_k 1～20且不大于前者，空视图合法成功空。 | 各边界/相等/逆序非法，0或少候选不补外部文档；固定向量同视图重复身份顺序。 |
| RAG-026：真实rerank与长度/索引/分数契约 | [bailian_rerank.py](../../backend/infrastructure/providers/bailian_rerank.py)、RerankPort、Profile门禁 | 部分落地/受限。真实原生协议观测成功，生产Profile仍待输入计数校准；未完成正式全链路。 | 请求确含query和候选、超长UTF-8范围、响应漏/重/越index、坏分数；启用后真实身份映射与返回计数。 |
| RAG-027：开关rerank、同候选排序和两种分数 | [retrieval.py::execute_retrieval](../../backend/application/retrieval.py)、RetrievalExecution、EvidenceBundle | 已落地。关闭不调重排，开启只从dense候选中选top_k；不保证每查询改善。 | Mock可控交换顺序、真实模型排序与cosine区分、dense/rerank排名和分数独立，不补新文档。 |
| RAG-028：默认失败及显式dense_fallback | [retrieval.py](../../backend/application/retrieval.py)、Rerank错误白名单与冻结policy | 已落地。受控服务/协议/预算错误才可degraded；认证/安全/空间/向量错误拒绝降级。 | off/empty/failed/degraded分别验证，401/403不能降级，fallback保持dense候选与原因/Profile，UI独立标记。 |
| RAG-029：同批次邻近扩展和区间合并 | [evidence_assembly.py::assemble_evidence](../../backend/application/evidence_assembly.py) | 已落地。半径0～2、同doc/batch、重叠合并、总字符及组件上限，记录去除/截取。 | 首尾/相邻多命中/重复范围/不连续Chunk、无跨批拼接、默认及极限预算、文本与组件范围对照。 |
| RAG-030：Context预算与仅实际输入引用 | [context.py](../../backend/application/context.py)、publish_plan/complete_run、ContextEvidence/MessageCitationLink | 结构化证据闭环已落地；正文引用编号闭环部分缺失。增强可截取，生成预算整Bundle选择；未注入逐条展示编号。 | 丢弃Bundle不能引用、真实范围hash、可靠位置；独立检查模型实际收到标识与回答正文引用，不能只查关系行。 |
| RAG-031：可追溯RAG Trace、阶段及删减原因 | RetrievalExecution、ToolCall、ContextPlan、[retrieval.py](../../backend/application/retrieval.py)计时 | DB事实链已落地；默认日志全身份/上游trace/全阶段计时不足，属部分落地。 | 从Message→Run→Tool→Execution→view/batch→Context追溯，失败/空/off/预算未选分开，缺日志字段与解析计时明确列缺口。 |
| RAG-032：版本化只读rag.search与固定Run接线 | [domain/ports/rag.py](../../backend/domain/ports/rag.py)、tool契约、[rag_run_execution.py](../../backend/application/rag_run_execution.py) | 已落地固定工具与绑定；无动态工具代码/任意Agent循环。诊断共用execute_retrieval。 | 工具版本/绑定可读，关闭不访问依赖，任意工具名拒绝，诊断与会话相同query/view得到同规则。 |
| RAG-033：工具输入/权限/次数及不可信证据 | [rag_run_execution.py](../../backend/application/rag_run_execution.py)、freeze_retrieval、strict DTO、context消息组装 | 已落地服务端约束和不可信提示边界；不能以此承诺模型绝不会受提示注入影响。 | owner/space/view/URL/SQL额外字段、重复逻辑调用、恶意文档不成为系统指令或授权；读权限再次校验。 |
| RAG-034：ToolCall绑定Task/generation与自动重试 | [rag_run_execution.py](../../backend/application/rag_run_execution.py)、[rag_task_execution.py](../../backend/application/rag_task_execution.py)、ToolCall唯一关系 | 已落地。工具开始/结果受有效代保护，自动重试不新增Run/用户Message。 | 前代失败回排、新代重新调用、旧代迟到、工具成功后生成失败，最终无重复assistant。 |
| RAG-035：创建Run时冻结全量安全RAG配置/view | [rag_sessions.py](../../backend/application/rag_sessions.py)、[domain/rag_snapshot.py](../../backend/domain/rag_snapshot.py)、RunSnapshot3 | 已落地。非Secret快照与视图同事务创建，运行中不改知识范围；安全禁用可阻断后续调用。 | 创建并发发布/改标签/换默认Profile，自动重试同view；快照/日志扫描无Key/URL/路径，blocked行为单列。 |
| RAG-036：retry/regenerate复用原快照和视图 | [rag_sessions.py](../../backend/application/rag_sessions.py)及[session_runs.py](../../backend/application/session_runs.py)来源Run接线、legacy限制 | 已落地。新用户消息获得新view，显式重试不悄悄取最新；旧无view历史受限返回错误。 | 三种入口对照view/hash，依赖失效/安全blocked/视图缺失、旧Run兼容；相同view不承诺生成逐字相同。 |
| RAG-037：版本化工具/检索Event、补放及终态一致 | [events/journal.py](../../backend/infrastructure/events/journal.py)、complete_run、[rag-event-stream.ts](../../frontend/src/events/rag-event-stream.ts) | 已落地。Journal事实、seq追加与三代投影，终态Message/Event同事务；不展示隐藏思维链。 | 断线/刷新/重复/乱序、Last-Event-ID/after_seq、Redis故障、工具完成不结束Run、事务失败无半终态。 |
| RAG-038：新契约、旧历史可读与DOCX写升级 | v3 API/契约、[legacy_rag.py](../../backend/application/legacy_rag.py)、0007～0010迁移 | 已落地主要兼容路径。v1文本仍本地，DOCX写要求升级；旧事实不伪造补齐。 | v1/v2/v3读取、旧DOCX任务收尾/无外发、schema3旧客户端错误、可信/未知旧空间、引用仍可恢复。 |
| RAG-039：九格式上传固定提示与每次授权 | [DocumentUploader.vue](../../frontend/src/components/DocumentUploader.vue)、documents store、RAG标签 | 已落地前端固定路线。具体前后端授权均需测，不能只靠勾选框存在判通过。 | 选/换文件重置授权、取消不提交、txt/md无云选项、办公不可用提示、每次重建授权与服务端422。 |
| RAG-040：构建详情、active/latest、刷新/重建/取消 | [stores/documents.ts](../../frontend/src/stores/documents.ts)及DocumentUploader、project_document/project_build | 已落地主路径。前端状态来自服务端，失败最新构建与旧可用批次分开。 | 排队/等待/向量化/发布/未知进度、刷新恢复、取消竞态、应答未知操作；不能把active可用误报最新成功。 |
| RAG-041：RAG设置、诊断与后续Run生效 | [RagPanel.vue](../../frontend/src/components/RagPanel.vue)、[stores/rag.ts](../../frontend/src/stores/rag.ts)、create_diagnostic | 已落地。诊断异步只检索不生成；当前不提供具体生成ModelProfile的Context预算preview，ADR已记此边界。 | 前后端参数边界、选库/策略后的迟到响应、候选/分数/去除原因、无Run/Message/生成费用；不把诊断增强全等同最终选入。 |
| RAG-042：证据、安全渲染和独立降级状态 | [EvidenceViewer.vue](../../frontend/src/components/EvidenceViewer.vue)、DocumentUploader、RagPanel/RunTimeline、source_locations、[markdown/render.ts](../../frontend/src/markdown/render.ts) | 已落地分散投影。EvidenceViewer显示batch/文本/位置等，parser在构建，degraded在诊断/事件，不是同一组件全部直接展示；无解析fallback成功态。 | 重建后旧证据一致、位置缺失中文说明、外链图片/脚本/危险HTML清洗、跨投影追溯parser及降级，degraded不混同解析回退。 |
| RAG-043：九格式真实输入/安全证据 | [fixtures/rag-v3/manifest.json](../../tests/fixtures/rag-v3/manifest.json)、[provider-observations.json](../../tests/fixtures/rag-v3/provider-observations.json) | 已准备10个文件：九格式加扫描PDF；已有八办公输出归一化观测。不是完整格式效果验收。 | 固定hash样本逐格式核对正文/结构，PDF文本+扫描；真实Key/额度/网络缺失逐项列受限，不用txt/md或Mock冒充办公通过。 |
| RAG-044：真实Embedding/rerank独立协议/可运行输入 | [check_rag_providers.py](../../backend/tools/check_rag_providers.py)、两适配器、provider-observations | 部分落地。两类协议成功观测已存；真实Profile计数阻断，真实入库查询/重排全流程未完成。 | 先锁计数算法/证据和Profile，再有界真实联调；记录model/revision/dim/输入计数与限制，不等同效果通过。 |
| RAG-045：20有答案+5无答案标注集与效果指标 | [fixtures/rag-v3/README.md](../../tests/fixtures/rag-v3/README.md)及开发probe；未找到完成的20+5标注集和同view指标报告 | 未完成验收材料。少量协议样本不能代替九格式/中英/跨片段的检索效果评估。 | 冻结20有答案+5无答案及答案范围；dense平均Recall@20≥0.85，报告MRR@5/Recall@5及排序提升/下降，同view核对跨片段增强；无答案不强求向量零命中，受限逐格式说明。 |
| RAG-046：独立正式测试/环境/报告/清理与部署资料 | [run_rag_v3_check.py](../../tests/integration/run_rag_v3_check.py)、compose.rag-v3.yml、[Runbook](../runbooks/rag-v3-development.md) | 开发级独立Compose闭环、fixtures和运维说明已落地；完整正式TEST-003工程/测试点/用例/报告尚非完成状态。 | 后续独立编制正式验收工程，不改前轮目录；启停/导入/分类执行/证据/销毁与失败路径finally检查，真实服务受限单列。 |

### 8.2 非功能需求核对（NFR-001～NFR-012）

| PRD需求／要验证的产品行为 | 当前实现、文件与核心函数／对象 | 调研结论 | 后续测试关注点 |
| --- | --- | --- | --- |
| NFR-001：外发授权、凭据仅服务端、非Secret快照 | ParseRequest、select_parser、[artifact_store.py](../../backend/infrastructure/rag/artifact_store.py)、v3安全投影、环境alias | 主要机制已落地；上游保留/地域政策没有被代码证明，不作额外承诺。 | 未授权无外发；响应/Event/Message/快照/前端/默认日志/报告扫描无Secret或签名能力；错误不可回显原始异常。 |
| NFR-002：受限出站和不可信文件/工具内容 | [download_safety.py](../../backend/infrastructure/rag/download_safety.py)、office_validation、normalize_package、工具strict DTO、Markdown清洗 | 已落地分层防护；预检和LLM不可信提示不能替代完整安全验收。 | DNS/私网/metadata/非法协议端口/重定向、上传Bearer隔离、ZIP炸弹/路径/注入；前端不直连私有存储。 |
| NFR-003：PG事实源、单路线恢复、终态/旧代保护 | [postgres_queue.py](../../backend/infrastructure/queue/postgres_queue.py)、rag_task_execution、Journal、发布事务、0007～0010约束 | 已落地。Redis/SSE不直接写终态，不用不明提交自动重提。 | 实际多连接/重启/失租，提交未知、半发布、重复终态、Redis不可用、断线补放；SQLite不能替代并发证明。 |
| NFR-004：请求/等待/文本/重试/事件/资源有界 | [parse_jobs.py](../../backend/application/parse_jobs.py)的deadline/poll、受控请求、structured_chunker、rerank预算、RetrievalPolicy、[isolated_processing.py](../../backend/infrastructure/rag/isolated_processing.py) | 主要上限已落地；Windows无等价RLIMIT，磁盘为软预算；专用并发门限实际跨Worker共享且仅计构建/诊断。 | 各上限±1、Unicode字节边界、长等待停机、kill+wait、错误次数、多个Worker与run内检索的计数边界、Linux资源限制。 |
| NFR-005：全身份关联与阶段计时、安全错误 | RetrievalExecution timings/候选/原因、Task/Build/Tool关系、[workers/runtime.py](../../backend/workers/runtime.py)日志 | 部分落地。DB可关联，默认日志字段和解析全阶段duration/上游trace及usage不完整；新任务旧run/document字段可为空。 | 从单失败追溯完整链路并列缺失字段，区分重试恢复/降级/失败；日志不含query/原文；补观测后再验收全覆盖。 |
| NFR-006：各能力清楚分层与可替换性 | [ports/rag.py](../../backend/domain/ports/rag.py)含ParseGateway/ArtifactNormalizer/EmbeddingPortV2/VectorSearchPort/RerankPort；chunker与增强独立函数 | 主要模块边界已落地，未建设独立ChunkerPort/EnhancementPort；不能宣称所有能力均可通过配置热切换。 | Mock/真实适配契约一致、领域无厂商字段、路由/页面不复制规则；函数边界是否足够支撑故障注入及后续替换。 |
| NFR-007：确定性、故障注入、真实证据分列 | 本轮unit/api/integration与[fixtures README](../../tests/fixtures/rag-v3/README.md)、Mock registry、PG probes | 已具备开发测试基础；正式用例仍需编制，真实生成/重排不承诺逐字确定。 | 独立算Top-K和范围、所有恢复断点可控、真实/Mock/源码调研证据分列，固定Profile/view/hash。 |
| NFR-008：万Chunk/100次查询的性能报告 | [vector_search.py](../../backend/infrastructure/rag/vector_search.py)及[rag_v3_pg_probe.py](../../tests/integration/rag_v3_pg_probe.py)；未见满足规模与资源记录的p50/p95报告 | 性能验收未完成。不能用短probe耗时或Mock延迟推定数据库p95≤1秒。 | ≥10000有效Chunk和100次预热查询，记录CPU/内存/扩展版本；数据库与外部阶段分开，p50/p95/错误率/峰值资源及受限说明。 |
| NFR-009：存储分类、容量、历史保护和受限清理 | [rag_capacity.py](../../backend/application/rag_capacity.py)、[rag_gc.py](../../backend/application/rag_gc.py)、rag_retention、cleanup_rag_artifacts | 已落地软预算/dry-run/apply/引用保护，默认不删source及开发数据。 | 源/规范产物/临时/失败候选量化，满额不损active，引用并发、权限/路径、残留重扫，不执行全局prune。 |
| NFR-010：版本化契约与不伪造历史的升级/回退 | [contracts/](../../contracts/)、v3 schemas/生成器、迁移0007～0010、confirm_legacy_rag_space | 主要实现及只读漂移校核已落地；非空旧库需显式步骤，出现新事实后不能普通downgrade。 | 三代契约/读取，旧未知空间、DOCX任务、已丢片段、backup恢复及拒绝降级门禁；不自动付费回填。 |
| NFR-011：中文阶段/错误/限制、有界分页 | [rag-labels.ts](../../frontend/src/components/rag-labels.ts)、RagPanel/EvidenceViewer、API分页投影 | 主要交互已落地，细节需浏览器验收；前端README轮询次数与源码存在文档残留。 | 中文区分active/latest失败/不可用/空/degraded，未知进度、列表及证据分页、无堆栈/路径，键盘与刷新状态。 |
| NFR-012：Compose可复现、前提明确、Windows/Linux说明 | [docker-compose.yml](../../docker-compose.yml)、[Runbook](../runbooks/rag-v3-development.md)、无Secret配置模板、独立smoke | 已有部署路径和历史闭环证据；本次未重新启动Compose或真实服务。无本地Office/PDF转换或隐式模型下载。 | 两系统按Runbook准备；缺MinerU时txt/md可用、办公明确不可用；真实模型计数受限、共享卷/密钥/清理/失败退出。 |

## 9. 验证证据、适用范围与后续测试材料

### 9.1 本次实际执行的离线校核（2026-11-08）

以下检查由本次调研执行，安全摘要位于本机Git忽略目录 `data/rag-implementation/research-20261108/verification.json`。忽略目录不是可跨机器保证存在的交付物，后续测试应自行归档报告。命令均从仓库根目录执行。

| 本次命令／检查 | 实际结果 | 能证明与不能证明的范围 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m backend.tools.export_rag_contracts --check` | 退出码0，16份导出契约无漂移 | 可证明当前导出与schema真源一致；不代替所有请求/响应行为验收。 |
| `npm run check:api --prefix frontend` | 退出码0，生成API类型无漂移 | 可证明生成类型与契约同步；本次没有因此宣称前端全部交互或浏览器通过。 |
| `.venv/Scripts/python.exe -m pytest tests/unit/test_rag_chunking_v3.py tests/unit/test_rag_mineru_tables_v3.py tests/unit/test_rag_profiles_v3.py tests/unit/test_rag_sql_scope_v3.py tests/unit/test_rag_vector_normalization_v3.py tests/api/test_rag_contracts_v3.py -q` | **26 passed in 3.30s** | 选定离线切片、表格、Profile、SQL范围、向量归一化与契约回归；不包含本次真实上游、完整PG并发或全量测试。 |
| 根据manifest逐个读取fixture并核对字节数和SHA-256 | 10个文件全部一致 | 九格式加扫描PDF固定输入未漂移；不能证明当前上游仍提供相同结果。 |
| Git基点至当前实施提交逐文件比对 | 181项：124新增、57修改、无删除 | 第12节机械覆盖该差异；不是本次调研新增181个文件。 |

本次没有重新启动Docker Compose、没有真实MinerU/模型外发、没有重跑后端全量及前端全套测试、没有浏览器/效果/性能正式验收。这些未运行项不能写成“本次通过”。

### 9.2 2026-10-30实施阶段已有证据

以下是已存在的历史结果，详细命令及边界见[PR-003](003-SesRAG-RAG检索增强与MinerU接入-PR.md)。该简要文档中“修改仍在工作区”是其撰写时状态；当前实施已纳入 `b4c134c`，不得将旧时间点叙述当当前Git状态。

| 历史证据 | 已核对的内容 | 对后续验收的限制 |
| --- | --- | --- |
| `data/rag-implementation/all-tests-final.txt` | 后端全量记录 **316 passed in 120.73s** | 历史开发回归；其中受控HTTP/SQLite结果不等同真实上游或真实PG并发。 |
| PR-003记录的前端检查 | 26项/4文件测试通过、类型和构建通过；Lint为0错误、1条既有v-html警告 | 本次未重跑这些完整检查，不将开发单测替代浏览器视觉/交互验收。 |
| 三轮独立Compose开发smoke；最后run `sesrag-rag-check-15e869a51b` 的summary | 最后一轮probe成功、cleanup退出0，运行标签下container/volume/network/image清单为空 | 证明当轮闭环，不推定今天所有Docker资源实时无残留。记录位于忽略的data目录。 |
| 本轮PG probe | pgvector 0.8.2、384/1024维、独立cosine对照、7项数据库guard、旧到新证据、Run/Context/Citation/SSE/前端代理 | 开发级真实PG证据；不是完整性能、升级场景或正式产品测试矩阵。 |
| [provider-observations.json](../../tests/fixtures/rag-v3/provider-observations.json) | 七种办公格式加扫描PDF的真实产物可归一化；真实Embedding两文档加一query均1024维；rerank返回索引顺序[0,1] | 有安全统计不等于真实全链路/排序改善。两模型counter_status仍unverified，生产Profile不启用。 |

办公输出统计能帮助后续准备断言基线：docx为1691字符/42块，文本PDF为1500字符/40块并有20个可靠原源位置；扫描PDF为60字符/1块并有1个原源位置；pptx为470字符/12块；xls/xlsx各1561字符/1块；doc为47字符/1块；ppt为188字符/7块。非PDF观测中的原源位置数为0，不能在用例中硬要求真实产物没有提供的页码、幻灯片号或单元格。统计是历史观测，不能要求今后云服务逐字不变。

### 9.3 可直接复用和必须另备的测试材料

[tests/fixtures/rag-v3/](../../tests/fixtures/rag-v3/)提供本地txt/md、七办公及扫描PDF、manifest、生成器、真实安全观测。旧doc/ppt公共样本有NOTICE和Apache-2.0许可证，正式测试复制时保留来源与许可。现有开发测试已覆盖多种安全/恢复负例，后续可作为设计参考，不能直接把测试文件名当完整测试点。

后续仍应独立准备：20+5标注集及标准答案来源；万级Chunk性能数据；真实模型计数校准证据与受控Profile；云端各格式内容/结构验收材料；多连接/重启故障注入；浏览器逐次授权、未知请求、事件恢复和证据渲染场景；正式分类脚本、逐用例结果、缺陷定位和资源销毁报告。受限原因必须分为代码/配置及测试工程缺口与不可由本机满足的外部服务条件，不能笼统归为“暂不可验证”。

## 10. 与目标的差异、未完成项和测试风险

| 项目 | 当前事实、主要定位与影响 | 后续方向／验收边界 |
| --- | --- | --- |
| 真实模型计数门禁 | Embedding/rerank适配和协议观测存在，但真实Profile因未校准被阻断；涉及RAG-016/018/026/044。属于明确的工程/配置前提缺口，不能仅归因于缺Key。 | 按锁定模型/revision完成专用计数校准及证据，再导入新版本Profile；不通过把状态字段改成verified来伪造依据。完成后重测真实入库/query/rerank及长输入。 |
| 回答正文引用编号 | ContextEvidence和Citation2实际输入约束存在；context.messages_for未注入对应展示编号，complete_run标签只是关系元数据。影响正文声明与证据点击对应，属实现闭环缺口。 | 后续明确编号注入/输出校验/展示一致策略，并分别验收结构化来源和正文标记。本次调研不以已有引用行判该目标全通过。 |
| 观测关联和全阶段计时 | RetrievalExecution有部分计时/候选/错误；日志不能直接覆盖所有新身份，上游trace/usage和解析阶段duration不足。涉及RAG-031/NFR-005。 | 补安全关联字段、分阶段耗时和适当上游追踪；现阶段从DB关联定位，并在正式报告注明缺失观测。 |
| 能力Port覆盖 | 现有5个Protocol覆盖解析/归一化/Embedding/向量搜索/rerank，切片和增强是独立函数模块，未完全形成可替换Port。 | 后续若需替换/故障注入，明确函数边界是否足够；不要在设计说明或验收结论写成每环节已经统一Port化。 |
| 诊断与生成预算 | 诊断可展示检索/增强结果，但没有绑定某生成ModelProfile的最终Context预算preview；ADR已列实施边界。 | 用例区分增强范围与模型实际选入范围；以真实Run ContextPlan证明最终输入，不能拿诊断全部证据当最终引用集合。 |
| 未知重建请求 | documents store重建每次新UUID，未像上传pending保留未知key。服务端幂等存在，不保证前端应答丢失时自动正确重放。 | 设计“服务端已登记但响应丢失”场景，核对忙碌复用/新操作、重复成本确认和恢复提示，按实际结果确定缺陷。 |
| 并发及GC锁序的说明差异 | ADR配置表写“每Worker文档／诊断上限”，实际claim采用全局共享门限、单进程串行，且该专用计数不含Run内检索。ADR §4.3的GC段写KB→Build且不反向等待Task，当前collect实际Task→KB→Document→Build，与该段文字不同。 | 后续将决策说明与当前锁序/容量口径对齐；以多连接测试验证创建视图、发布、GC、取消竞争与死锁/超时，不仅检查单进程成功。当前调研记录差异，不直接判定已有死锁或吞吐达标。 |
| 效果与性能 | RAG-045的20+5和NFR-008的万Chunk/100查询未有完整验收报告。 | 独立标注/冻结view、分格式效果评估、真实PG性能统计；外部或硬件受限需记录，不能由Mock/单次probe代替。 |
| 正式验收工程 | 本轮已有独立开发smoke与fixtures；尚不能据此说RAG-046的正式分类测试/测试点/用例/报告已齐备。 | 后续TEST-003独立设计与实施，保留失败、受限和清理证据；不维护前轮验收目录。 |
| 文档历史残留 | CONTEXT旧段仍列Task仅run/index_document、事件仅1/2，后部v3与代码已有4类Task/3代Event；frontend README轮询旧描述30次，documents.ts当前60次；PR-003工作区状态是历史时间点。 | 后续同步文档时按当前源码消除残留；本次仅记录差异，不能把旧说明当当前运行边界。 |
| 平台及容量隔离 | Docker Linux有解析RLIMIT；Windows直接进程缺等价硬内存限制；磁盘采用软预算，容量阈值不等于硬配额。 | 正式测试记录运行平台，实测Linux容器限制和并发临时峰值；不能推定Windows直接运行有相同资源隔离。 |

以上没有发现必须由用户手工处理才能完成本次“调研文档”任务的阻碍。真实服务启用、产品修复和正式验收属于后续工作，当前不越过调研范围新增半成品入口或修改运行规则。

## 11. 本次文档整体校审

本次交付是新增详细调研文件，并在根[README](../../README.md)和[docs/pr/README](README.md)增加导航；不修改产品代码、既有PRD/ADR或前轮正式验收工程，不自动提交/推送。源代码本轮124新增/57修改的完整清单见第12节，应与本次三份文档交付分开理解。

| 校审项目 | 结论 |
| --- | --- |
| 范围与来源 | 文档围绕PRD-003/ADR-003及当前v0.3实施提交，编号来源明确；与简要交付、源码、接口真源和既有证据交叉核对。 |
| 功能与非功能覆盖 | 第8节逐项列出46项RAG及12项NFR，每项给出当前机制/文件/结论/测试关注点；不以宽泛模块总结替代需求核对。 |
| 行为贯通 | 固定九格式、办公逐次外发、无解析回退、未知提交不重提、候选原子发布、冻结view、实际上下文引用与三代兼容前后一致。 |
| 不确定性与差异 | 计数门禁、正文编号、观测、诊断预算、未知重建、效果/性能/正式验收、文档残留均明确记录；未将未完成目标写成通过。 |
| 证据口径 | 2026-11-08本次26项/契约/类型/hash检查与2026-10-30历史316项/前端/Compose/真实协议分开；本次未运行项已列明。 |
| 文件及职责 | 第2～7节解释模块与对象，后续第12节逐文件标注新增/修改、实际职责和结论，便于测试按路径定位。 |
| 机械完整性校验 | 46项功能与12项非功能均各出现一个核对表行；181条路径及新增/修改标记与Git差异一致；三份交付文档的本地链接有效，表格列数一致，定向diff格式检查通过。 |

本次文档自审已完成，并纠正了初稿中接口/组件名称、页面参数、迁移租约前置行为、GC时间起点及latest/active提交时点等描述，使其与实际源码一致。以上结论是调研文档的完整性与可追溯性校审，不是对尚未执行的产品验收作通过判定。

## 12. 逐文件变更说明清单

以`58d9d1d → b4c134c`的Git差异为依据，共181个文件：新增124、修改57，无删除。该区间包含需求设计、治理和实施记录，不把其中每一份文档都算作运行功能。当前用户对任务说明的工作区修改不计入已提交实现，且本次保持原样。

下表的“新增/修改”均相对上述实施前基线；既有但本轮未改的Parser、会话模型、通知等依赖在机制章节说明，不伪列为新增。本次新调研文件及导航修改发生在该提交之后，另见第11节交付校审。

### 12.1 基础配置与治理（5个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`.env.example`](../../.env.example) | 修改 | 本轮配置、外发开关、出站域、私有状态密钥、存储与并发预算示例；不含真实凭据。 |
| [`.gitignore`](../../.gitignore) | 修改 | 排除运行期配置、私有状态、data证据与临时文件。 |
| [`CONTEXT.md`](../../CONTEXT.md) | 修改 | 补充本轮知识库、解析、构建、空间、视图、证据、工具与计数术语；旧总述仍有历史残留，见差异章。 |
| [`README.md`](../../README.md) | 修改 | 本轮能力、目录、依赖、配置及操作文档入口。 |
| [`pyproject.toml`](../../pyproject.toml) | 修改 | 0.3.0版本、加密/旧Office容器等运行依赖及独立样本生成可选依赖。 |

### 12.2 后端接口与契约DTO（13个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`backend/api/routes/v3/__init__.py`](../../backend/api/routes/v3/__init__.py) | 新增 | v3路由包边界。 |
| [`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py) | 新增 | 知识库/Profile/文档/标签/构建/取消/切片的HTTP适配与安全投影。 |
| [`backend/api/routes/v3/retrieval.py`](../../backend/api/routes/v3/retrieval.py) | 新增 | 独立诊断执行、查询、取消和Bundle读取的HTTP适配。 |
| [`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py) | 新增 | 复用会话应用服务，提供v3消息/Run/上下文/事件/SSE/重试等入口。 |
| [`backend/api/schemas/v3/__init__.py`](../../backend/api/schemas/v3/__init__.py) | 新增 | 严格DTO基类，拒绝额外字段。 |
| [`backend/api/schemas/v3/context.py`](../../backend/api/schemas/v3/context.py) | 新增 | ContextPlan3及实际证据投影。 |
| [`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py) | 新增 | 文档、切片、构建、重建及标签DTO。 |
| [`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py) | 新增 | 工具/检索新事件载荷及三代事件映射。 |
| [`backend/api/schemas/v3/knowledge_bases.py`](../../backend/api/schemas/v3/knowledge_bases.py) | 新增 | 知识库资源与创建/修改DTO。 |
| [`backend/api/schemas/v3/profiles.py`](../../backend/api/schemas/v3/profiles.py) | 新增 | 可用配置及不可用原因安全DTO。 |
| [`backend/api/schemas/v3/retrieval.py`](../../backend/api/schemas/v3/retrieval.py) | 新增 | 诊断、检索执行、Bundle和组件DTO。 |
| [`backend/api/schemas/v3/sessions.py`](../../backend/api/schemas/v3/sessions.py) | 新增 | 三代Message/Run/引用及v3会话请求投影。 |
| [`backend/app.py`](../../backend/app.py) | 修改 | 注册v3路由和本轮可公开错误码。 |

### 12.3 后端应用、领域与持久化（33个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`backend/README.md`](../../backend/README.md) | 修改 | 后端本轮分层、模块用途、工具与配置说明。 |
| [`backend/application/context.py`](../../backend/application/context.py) | 修改 | 将不可信证据加入预算计划；schema3采用user角色，按整Bundle取舍。 |
| [`backend/application/documents.py`](../../backend/application/documents.py) | 修改 | 保留v1文本写入时点，旧DOCX写入要求升级与外发确认。 |
| [`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py) | 新增 | 同文档同批次邻近合并、去重、增强字符预算、组件范围与来源截取。 |
| [`backend/application/index_builds.py`](../../backend/application/index_builds.py) | 新增 | 上传/重建、格式/授权/容量校验、幂等构建、查询/取消与active/latest投影。 |
| [`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py) | 新增 | 库的owner边界、创建/配置、空间绑定及默认库操作。 |
| [`backend/application/legacy_rag.py`](../../backend/application/legacy_rag.py) | 新增 | 从旧连续Chunk物化规范正文并保护旧引用，不猜造历史原文。 |
| [`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py) | 新增 | 解析检查点、同一MinerU任务的推进/轮询/未知提交/产物归一化。 |
| [`backend/application/rag_capacity.py`](../../backend/application/rag_capacity.py) | 新增 | 总存储与临时存储软预算、引用资源预估和容量拒绝。 |
| [`backend/application/rag_gc.py`](../../backend/application/rag_gc.py) | 新增 | 按批次、引用与锁保护的保守清理；默认dry-run。 |
| [`backend/application/rag_operations.py`](../../backend/application/rag_operations.py) | 新增 | owner/作用域/幂等键/请求摘要去重与并发首次请求串行化。 |
| [`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py) | 新增 | 显式导入不可变配置版本、空间与启用/安全状态及可用性守卫。 |
| [`backend/application/rag_retention.py`](../../backend/application/rag_retention.py) | 新增 | 独立诊断过期、410墓碑及受保护引用关系保留。 |
| [`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py) | 新增 | 每Task/generation的只读工具调用、检索阶段事件、恢复/中断与上下文身份。 |
| [`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py) | 新增 | 将旧生成快照升级为schema3、冻结RAG绑定及三代Run读取。 |
| [`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py) | 新增 | 有效代/租约与取消检查，索引构建及诊断任务的失败结算。 |
| [`backend/application/retrieval.py`](../../backend/application/retrieval.py) | 新增 | 共用诊断/Run检索流程、冻结配置安全复查、召回/重排/增强与证据读取。 |
| [`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py) | 新增 | 冻结库/过滤/空间/active批次集合与历史scope读取。 |
| [`backend/application/session_execution.py`](../../backend/application/session_execution.py) | 修改 | schema3检索接入、先预算后付费调用、ContextEvidence与实际选入证据。 |
| [`backend/application/session_runs.py`](../../backend/application/session_runs.py) | 修改 | 在既有Thread/Branch事务创建Run/视图；三代重试、再生成与取消兼容。 |
| [`backend/application/session_threads.py`](../../backend/application/session_threads.py) | 修改 | 按Run/Message实际协议投影历史会话。 |
| [`backend/application/source_locations.py`](../../backend/application/source_locations.py) | 新增 | 来源映射的公开、范围裁剪和缺失语义。 |
| [`backend/application/task_execution.py`](../../backend/application/task_execution.py) | 修改 | 新终态证据关系、工具结算与Message/Run/Task/Journal原子完成。 |
| [`backend/application/vector_validation.py`](../../backend/application/vector_validation.py) | 修改 | 扩展可配置维度与有限值校验，保留旧路径默认维度兼容。 |
| [`backend/config.py`](../../backend/config.py) | 修改 | MinerU、共享私有目录、存储/临时预算及RAG容量等Settings校验。 |
| [`backend/db/models.py`](../../backend/db/models.py) | 修改 | 扩展Document/Chunk/Task/Run/ContextPlan本轮关联及协议字段。 |
| [`backend/db/rag_models.py`](../../backend/db/rag_models.py) | 新增 | 库/Profile/空间/操作/解析/构建/视图/执行/工具/证据/保留关系ORM映射。 |
| [`backend/domain/enums.py`](../../backend/domain/enums.py) | 修改 | 增加index_build、retrieval_diagnostic和waiting_external等状态/任务枚举。 |
| [`backend/domain/ports/__init__.py`](../../backend/domain/ports/__init__.py) | 修改 | 兼容现有Evidence/向量等Port的本轮元数据扩展。 |
| [`backend/domain/ports/rag.py`](../../backend/domain/ports/rag.py) | 新增 | ParseGateway、ArtifactNormalizer、EmbeddingPortV2、VectorSearchPort和RerankPort协议；切片/增强实际使用独立模块函数。 |
| [`backend/domain/rag.py`](../../backend/domain/rag.py) | 新增 | 固定路由、解析请求、切片/检索策略及安全DTO/摘要工具。 |
| [`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py) | 新增 | 空间描述符、四类配置和输入计数状态/配额约定。 |
| [`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py) | 新增 | schema3冻结绑定及固定rag.search@1输入输出定义。 |

### 12.4 适配器、Worker与维护工具（29个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py) | 修改 | 三代事件联合验证、Run序号锁与有界Journal额度。 |
| [`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py) | 新增 | 真实文档/查询向量接口、批量/index/维度检查与float32归一化。 |
| [`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py) | 新增 | 真实原生rerank接口、候选身份/分数和错误分类。 |
| [`backend/infrastructure/providers/mock.py`](../../backend/infrastructure/providers/mock.py) | 修改 | 补充确定性RAG向量/重排行为，用于流程验证。 |
| [`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py) | 新增 | 按冻结配置选择适配器、Secret别名、真实counter启用阻断。 |
| [`backend/infrastructure/queue/adapter.py`](../../backend/infrastructure/queue/adapter.py) | 修改 | QueuePort对新任务让出及状态行为的适配。 |
| [`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py) | 修改 | 新任务领取容量、generation/lease、waiting_external及failure_count重试语义。 |
| [`backend/infrastructure/rag/artifact_store.py`](../../backend/infrastructure/rag/artifact_store.py) | 新增 | 受控目录下私有能力状态的加密存取与安全文件操作。 |
| [`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py) | 新增 | HTTPS、域/公网地址、DNS绑定、跳转及大小限制。 |
| [`backend/infrastructure/rag/html_tables.py`](../../backend/infrastructure/rag/html_tables.py) | 新增 | 外部HTML表格安全文本化，不执行HTML/脚本。 |
| [`backend/infrastructure/rag/isolated_processing.py`](../../backend/infrastructure/rag/isolated_processing.py) | 新增 | 有界子进程解析/切片与超时隔离。 |
| [`backend/infrastructure/rag/local_structure.py`](../../backend/infrastructure/rag/local_structure.py) | 新增 | txt/md本地结构块及行/标题位置归一化。 |
| [`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py) | 新增 | MinerU申请上传/原字节上传/状态/产物协议；不执行本地回退。 |
| [`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py) | 新增 | 外部JSON/Markdown/表格产物安全归一化及可靠位置映射。 |
| [`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py) | 新增 | OOXML/OLE格式与容器校验；不提供本地Office正文解析。 |
| [`backend/infrastructure/rag/pgvector_store.py`](../../backend/infrastructure/rag/pgvector_store.py) | 修改 | 旧向量写入兼容时补齐构建/空间/正文身份和新引用保护。 |
| [`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py) | 新增 | 结构优先切片、长块/字符窗口和字节配额，保留块区间。 |
| [`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py) | 新增 | PG范围先物化后cosine排序/LIMIT；SQLite仅验证用分支。 |
| [`backend/tools/check_rag_providers.py`](../../backend/tools/check_rag_providers.py) | 新增 | 显式授权的固定合成输入真实协议探针和安全统计。 |
| [`backend/tools/cleanup_rag_artifacts.py`](../../backend/tools/cleanup_rag_artifacts.py) | 新增 | 保守清理命令入口，预览/执行及受保护资源统计。 |
| [`backend/tools/confirm_legacy_rag_space.py`](../../backend/tools/confirm_legacy_rag_space.py) | 新增 | 有可信依据时显式确认旧向量空间，拒绝默认猜测。 |
| [`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py) | 新增 | 16份JSON Schema导出及--check漂移门禁。 |
| [`backend/tools/sync_rag_profiles.py`](../../backend/tools/sync_rag_profiles.py) | 新增 | 显式导入非Secret版本配置及bootstrap。 |
| [`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py) | 新增 | 分段迁移与默认库/Profile初始化编排，不自动调用云服务。 |
| [`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py) | 新增 | 解析/切片/分批Embedding/校验/原子发布新构建；云端等待让出。 |
| [`backend/workers/handlers/index_handler.py`](../../backend/workers/handlers/index_handler.py) | 修改 | 保留旧txt/md索引兼容并阻断旧DOCX写入。 |
| [`backend/workers/handlers/retrieval_diagnostic_handler.py`](../../backend/workers/handlers/retrieval_diagnostic_handler.py) | 新增 | 无聊天Message/Run的独立检索任务执行。 |
| [`backend/workers/handlers/run_handler.py`](../../backend/workers/handlers/run_handler.py) | 修改 | 会话Run选择schema3检索并使用现有执行链路。 |
| [`backend/workers/runtime.py`](../../backend/workers/runtime.py) | 修改 | 调度四类Task、让出等待、停机及新任务失败结算。 |

### 12.5 版本化JSON契约（17个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`contracts/README.md`](../../contracts/README.md) | 修改 | 登记新契约与导出/类型同步方式。 |
| [`contracts/api_responses_v3.json`](../../contracts/api_responses_v3.json) | 新增 | 资源/会话请求响应及三代事件统一导出目录；由DTO导出，不是独立手写规则。 |
| [`contracts/citation_v2.json`](../../contracts/citation_v2.json) | 新增 | 实际ContextEvidence引用身份/范围；由DTO导出，不是独立手写规则。 |
| [`contracts/context_plan_v3.json`](../../contracts/context_plan_v3.json) | 新增 | schema3上下文选择及预算投影；由DTO导出，不是独立手写规则。 |
| [`contracts/document_v3.json`](../../contracts/document_v3.json) | 新增 | 文档及active/latest构建投影；由DTO导出，不是独立手写规则。 |
| [`contracts/evidence_v2.json`](../../contracts/evidence_v2.json) | 新增 | Bundle/组件/来源与正文分页投影；由DTO导出，不是独立手写规则。 |
| [`contracts/index_build_v3.json`](../../contracts/index_build_v3.json) | 新增 | 候选构建状态和安全错误投影；由DTO导出，不是独立手写规则。 |
| [`contracts/knowledge_base_v3.json`](../../contracts/knowledge_base_v3.json) | 新增 | 知识库/空间资源；由DTO导出，不是独立手写规则。 |
| [`contracts/message_v3.json`](../../contracts/message_v3.json) | 新增 | 三代消息及新版引用投影；由DTO导出，不是独立手写规则。 |
| [`contracts/rag_binding_v3.json`](../../contracts/rag_binding_v3.json) | 新增 | Run冻结RAG配置/视图/固定工具；由DTO导出，不是独立手写规则。 |
| [`contracts/rag_profile_v3.json`](../../contracts/rag_profile_v3.json) | 新增 | 安全可用配置清单；由DTO导出，不是独立手写规则。 |
| [`contracts/retrieval_v3.json`](../../contracts/retrieval_v3.json) | 新增 | 诊断/Run检索执行及trace；由DTO导出，不是独立手写规则。 |
| [`contracts/run_event_v3.json`](../../contracts/run_event_v3.json) | 新增 | 按版本和type区分的三代事件联合；由DTO导出，不是独立手写规则。 |
| [`contracts/run_v3.json`](../../contracts/run_v3.json) | 新增 | schema3及历史Run事实投影；由DTO导出，不是独立手写规则。 |
| [`contracts/tool_rag_search_input_v1.json`](../../contracts/tool_rag_search_input_v1.json) | 新增 | 固定只读检索工具输入；由DTO导出，不是独立手写规则。 |
| [`contracts/tool_rag_search_result_v2.json`](../../contracts/tool_rag_search_result_v2.json) | 新增 | 固定检索工具结果与Bundle身份；由DTO导出，不是独立手写规则。 |
| [`contracts/tool_v1.json`](../../contracts/tool_v1.json) | 新增 | 只读工具定义和每代调用上限；由DTO导出，不是独立手写规则。 |

### 12.6 部署与迁移（10个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`docker-compose.yml`](../../docker-compose.yml) | 修改 | 共享RAG私有卷、环境、容量与分段升级启动命令。 |
| [`docker/api/Dockerfile`](../../docker/api/Dockerfile) | 修改 | 本轮依赖与构建缓存/网络超时相关调整。 |
| [`docker/rag-bootstrap.example.json`](../../docker/rag-bootstrap.example.json) | 新增 | 无Secret的默认库及初始配置示例。 |
| [`docker/rag-profiles.example.json`](../../docker/rag-profiles.example.json) | 新增 | 四类Profile模板，真实counter仍未验证，不能直接当启用证明。 |
| [`migrations/rag_checks.py`](../../migrations/rag_checks.py) | 新增 | 活动租约预检、旧DOCX收尾、默认库/旧批次回填、旧引用保护与回退门禁。 |
| [`migrations/rag_guards.py`](../../migrations/rag_guards.py) | 新增 | PG层Profile/空间/构建/证据与Journal不可变触发器。 |
| [`migrations/versions/0007_rag_catalog_and_profiles.py`](../../migrations/versions/0007_rag_catalog_and_profiles.py) | 新增 | 建库/Profile/空间/幂等操作及Document基础扩展；先排空旧执行。 |
| [`migrations/versions/0008_rag_builds_and_vectors.py`](../../migrations/versions/0008_rag_builds_and_vectors.py) | 新增 | 解析/规范产物/构建、多维vector、旧未知空间隔离与同文档指针约束。 |
| [`migrations/versions/0009_rag_views_tools_and_evidence.py`](../../migrations/versions/0009_rag_views_tools_and_evidence.py) | 新增 | 冻结视图、检索/工具/Bundle/实际证据/引用关系和旧引用保护。 |
| [`migrations/versions/0010_rag_task_and_run_protocol.py`](../../migrations/versions/0010_rag_task_and_run_protocol.py) | 新增 | 新任务类型、外部等待/失败计数、Run协议/view以及数据库不变量。 |

### 12.7 前端模块（26个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`frontend/README.md`](../../frontend/README.md) | 修改 | 前端新增模块职责、配置/交互及开发检查入口。 |
| [`frontend/package-lock.json`](../../frontend/package-lock.json) | 修改 | 同步前端依赖锁定与版本。 |
| [`frontend/package.json`](../../frontend/package.json) | 修改 | 更新0.3.0版本及现有前端工具链声明。 |
| [`frontend/scripts/generate-api-types.mjs`](../../frontend/scripts/generate-api-types.mjs) | 修改 | 由新Schema生成v3类型并提供--check门禁。 |
| [`frontend/src/api/http.ts`](../../frontend/src/api/http.ts) | 修改 | 适配v3请求错误与通用HTTP处理。 |
| [`frontend/src/api/v2/threads.ts`](../../frontend/src/api/v2/threads.ts) | 修改 | 旧Thread元数据请求与v3工作台复用衔接。 |
| [`frontend/src/api/v3/rag.ts`](../../frontend/src/api/v3/rag.ts) | 新增 | 库/Profile/文档/构建/诊断/证据v3请求。 |
| [`frontend/src/api/v3/sessions.ts`](../../frontend/src/api/v3/sessions.ts) | 新增 | v3会话/Run/上下文/事件及操作请求。 |
| [`frontend/src/components/ContextNotice.vue`](../../frontend/src/components/ContextNotice.vue) | 修改 | 展示schema3上下文实际证据与预算信息。 |
| [`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue) | 修改 | 九格式、逐次办公外发授权、构建/取消及active/latest状态。 |
| [`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue) | 新增 | 按固定Bundle读取/分页展示来源正文及可靠位置。 |
| [`frontend/src/components/MessageTimeline.vue`](../../frontend/src/components/MessageTimeline.vue) | 修改 | 新引用及证据入口，保持消息Markdown安全展示。 |
| [`frontend/src/components/RagPanel.vue`](../../frontend/src/components/RagPanel.vue) | 新增 | 检索启用、库/策略/topK/半径/过滤及独立诊断面板。 |
| [`frontend/src/components/RunActions.vue`](../../frontend/src/components/RunActions.vue) | 修改 | v3重试/重新生成兼容与错误提示。 |
| [`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue) | 修改 | 工具/检索阶段及中文事实状态展示。 |
| [`frontend/src/components/rag-labels.ts`](../../frontend/src/components/rag-labels.ts) | 新增 | 安全错误码、阶段、来源和远端结果的中文映射。 |
| [`frontend/src/events/rag-event-stream.ts`](../../frontend/src/events/rag-event-stream.ts) | 新增 | 三代事件适配、必要字段校验、HTTP补放与SSE连接。 |
| [`frontend/src/markdown/render.ts`](../../frontend/src/markdown/render.ts) | 修改 | DOM清洗及远程资源加载阻断。 |
| [`frontend/src/pages/WorkspacePage.vue`](../../frontend/src/pages/WorkspacePage.vue) | 修改 | 编排本轮面板/上传/证据交互，复用会话工作台。 |
| [`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts) | 修改 | 文档/构建轮询、操作幂等、确定拒绝与未知网络结果管理。 |
| [`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts) | 新增 | RAG范围/策略状态、输入校验、独立诊断轮询和epoch隔离。 |
| [`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts) | 修改 | 三代Run事实、事件seq去重/补放、重连和迟到响应隔离。 |
| [`frontend/src/stores/thread.ts`](../../frontend/src/stores/thread.ts) | 修改 | 按v3事实读取与现有Thread/Branch元数据配合。 |
| [`frontend/src/styles.css`](../../frontend/src/styles.css) | 修改 | RAG面板、上传状态、来源/证据和工作台布局。 |
| [`frontend/src/types/api-v3.ts`](../../frontend/src/types/api-v3.ts) | 新增 | 从契约生成的新类型；不是手写第二份接口真源。 |
| [`frontend/tests/rag-workspace.test.ts`](../../frontend/tests/rag-workspace.test.ts) | 新增 | 外发确认、错误/幂等、范围/诊断及安全渲染的组件/store回归。 |

### 12.8 本轮开发测试和固定输入（38个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`tests/api/README.md`](../../tests/api/README.md) | 修改 | 新v3契约/资源/会话开发测试导航。 |
| [`tests/api/test_rag_contracts_v3.py`](../../tests/api/test_rag_contracts_v3.py) | 新增 | 导出Schema、三代事件/引用及严格版本边界回归。 |
| [`tests/api/test_rag_resources_v3.py`](../../tests/api/test_rag_resources_v3.py) | 新增 | 库/上传/格式/授权/幂等/构建/证据及安全API回归。 |
| [`tests/api/test_rag_session_v3.py`](../../tests/api/test_rag_session_v3.py) | 新增 | 冻结Run、重试/再生成、历史读取与v3会话事件回归。 |
| [`tests/api/test_v2_schemas.py`](../../tests/api/test_v2_schemas.py) | 修改 | 调整旧DTO的本轮兼容断言。 |
| [`tests/fixtures/rag-v3/LICENSE-APACHE-2.0.txt`](../../tests/fixtures/rag-v3/LICENSE-APACHE-2.0.txt) | 新增 | 两个公共旧Office样本的许可证。 |
| [`tests/fixtures/rag-v3/NOTICE`](../../tests/fixtures/rag-v3/NOTICE) | 新增 | 公共样本来源与署名说明。 |
| [`tests/fixtures/rag-v3/README.md`](../../tests/fixtures/rag-v3/README.md) | 新增 | 固定输入、manifest/真实安全统计与取证边界说明。 |
| [`tests/fixtures/rag-v3/generate_fixtures.py`](../../tests/fixtures/rag-v3/generate_fixtures.py) | 新增 | 生成合成新格式/扫描样本；联网下载旧Office需显式参数。 |
| [`tests/fixtures/rag-v3/knowledge-scan.pdf`](../../tests/fixtures/rag-v3/knowledge-scan.pdf) | 新增 | 独立图像扫描PDF文本识别输入。 |
| [`tests/fixtures/rag-v3/knowledge.docx`](../../tests/fixtures/rag-v3/knowledge.docx) | 新增 | 合成DOCX固定正文/结构输入。 |
| [`tests/fixtures/rag-v3/knowledge.md`](../../tests/fixtures/rag-v3/knowledge.md) | 新增 | 合成本地Markdown结构/行号输入。 |
| [`tests/fixtures/rag-v3/knowledge.pdf`](../../tests/fixtures/rag-v3/knowledge.pdf) | 新增 | 合成PDF正文/页面输入。 |
| [`tests/fixtures/rag-v3/knowledge.pptx`](../../tests/fixtures/rag-v3/knowledge.pptx) | 新增 | 合成六页PPTX输入，不覆盖全部20事实。 |
| [`tests/fixtures/rag-v3/knowledge.txt`](../../tests/fixtures/rag-v3/knowledge.txt) | 新增 | 合成本地纯文本输入。 |
| [`tests/fixtures/rag-v3/knowledge.xls`](../../tests/fixtures/rag-v3/knowledge.xls) | 新增 | 真实旧Excel容器的合成表格输入。 |
| [`tests/fixtures/rag-v3/knowledge.xlsx`](../../tests/fixtures/rag-v3/knowledge.xlsx) | 新增 | 合成OOXML表格输入。 |
| [`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json) | 新增 | 10个文件的字节数/hash和第三方来源；九格式加扫描PDF。 |
| [`tests/fixtures/rag-v3/provider-observations.json`](../../tests/fixtures/rag-v3/provider-observations.json) | 新增 | 历史真实七办公格式/扫描PDF及向量/重排安全统计，无能力URL/Key。 |
| [`tests/fixtures/rag-v3/public-slides.ppt`](../../tests/fixtures/rag-v3/public-slides.ppt) | 新增 | 来自Apache POI的真实旧PPT公共样本。 |
| [`tests/fixtures/rag-v3/public-word.doc`](../../tests/fixtures/rag-v3/public-word.doc) | 新增 | 来自Apache POI的真实旧DOC公共样本。 |
| [`tests/integration/README.md`](../../tests/integration/README.md) | 修改 | 本轮独立开发闭环、协议和恢复检查说明。 |
| [`tests/integration/compose.rag-v3.yml`](../../tests/integration/compose.rag-v3.yml) | 新增 | 随机项目开发环境，不映射宿主端口、不借用旧验收编排。 |
| [`tests/integration/conftest.py`](../../tests/integration/conftest.py) | 修改 | 本轮集成数据/配置fixture与测试依赖配合。 |
| [`tests/integration/rag_v3_pg_probe.py`](../../tests/integration/rag_v3_pg_probe.py) | 新增 | 真实PG/pgvector、空间隔离、约束及v3产品纵向探针。 |
| [`tests/integration/run_rag_v3_check.py`](../../tests/integration/run_rag_v3_check.py) | 新增 | 启动/日志/探针/finally销毁及残留复查的开发检查总入口。 |
| [`tests/integration/test_execution_integrity.py`](../../tests/integration/test_execution_integrity.py) | 修改 | 新链路兼容的执行/原子性回归调整。 |
| [`tests/integration/test_rag_provider_protocols_v3.py`](../../tests/integration/test_rag_provider_protocols_v3.py) | 新增 | 受控transport模拟真实供应商协议/故障，不自动付费。 |
| [`tests/integration/test_rag_recovery_v3.py`](../../tests/integration/test_rag_recovery_v3.py) | 新增 | 解析检查点、未知提交、代数/租约、取消/恢复/GC/证据等回归。 |
| [`tests/unit/README.md`](../../tests/unit/README.md) | 修改 | 本轮结构、配置、SQL、归一化及迁移测试导航。 |
| [`tests/unit/test_rag_chunking_v3.py`](../../tests/unit/test_rag_chunking_v3.py) | 新增 | 结构/长段/重叠及范围切片单测。 |
| [`tests/unit/test_rag_migrations_v3.py`](../../tests/unit/test_rag_migrations_v3.py) | 新增 | 四段实际迁移、revision长度与库/空间约束回归。 |
| [`tests/unit/test_rag_mineru_tables_v3.py`](../../tests/unit/test_rag_mineru_tables_v3.py) | 新增 | 真实形态HTML表格文本化和空输出单测。 |
| [`tests/unit/test_rag_office_inputs_v3.py`](../../tests/unit/test_rag_office_inputs_v3.py) | 新增 | OOXML/OLE格式、容器与安全边界单测。 |
| [`tests/unit/test_rag_profiles_v3.py`](../../tests/unit/test_rag_profiles_v3.py) | 新增 | 不可变配置/空间、固定路线及未验证计数守卫单测。 |
| [`tests/unit/test_rag_sql_scope_v3.py`](../../tests/unit/test_rag_sql_scope_v3.py) | 新增 | 授权/空间先物化的PG SQL结构检查，不独自证明PG执行计划性能。 |
| [`tests/unit/test_rag_vector_normalization_v3.py`](../../tests/unit/test_rag_vector_normalization_v3.py) | 新增 | l2_float32_v1与非有限/零向量/维度边界单测。 |
| [`tests/unit/test_v2_session_migrations.py`](../../tests/unit/test_v2_session_migrations.py) | 修改 | 既有会话迁移基线与本轮新增revision兼容调整。 |

### 12.9 文档（10个）

| 项目文件 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| [`docs/adr/003-implementation-progress.md`](../../docs/adr/003-implementation-progress.md) | 新增 | 分阶段开发进度与检查历史，不是正式验收报告。 |
| [`docs/adr/003-sesrag-rag-mineru-implementation-plan.md`](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md) | 新增 | 本轮架构方案、已记录实际拆分差异与退出门槛。 |
| [`docs/pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md`](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md) | 新增 | 此前简要交付、历史检查与剩余门槛。 |
| [`docs/pr/README.md`](../../docs/pr/README.md) | 修改 | 结果文档导航，原实施提交已加入PR-003入口。 |
| [`docs/prd/003-SesRAG-RAG与MinerU-调研依据.md`](../../docs/prd/003-SesRAG-RAG与MinerU-调研依据.md) | 新增 | 需求设计阶段官方资料、选型与服务能力调研；不是当前源码结论。 |
| [`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md) | 新增 | 本轮46功能/12非功能、九格式及验收边界。 |
| [`docs/runbooks/demo-development.md`](../../docs/runbooks/demo-development.md) | 修改 | 原本机部署入口衔接本轮运行方式。 |
| [`docs/runbooks/rag-v3-development.md`](../../docs/runbooks/rag-v3-development.md) | 新增 | Windows/Linux环境、Secret注入、分段升级、真实探针、清理和恢复流程。 |
| [`docs/当前任务说明.md`](../../docs/当前任务说明.md) | 修改 | 用户任务上下文变更；纳入Git差异计数，不视为产品交付文件，本次不覆盖。 |
| [`docs/接口文档.md`](../../docs/接口文档.md) | 修改 | 第8节正式v3资源/会话/工具/证据与三代兼容真源。 |
