# PR-003：RAG检索增强与MinerU接入实施结果简要说明

| 字段 | 内容 |
| --- | --- |
| 编号／项目版本 | 003／v0.3.0，分支`sesrag_v0.3` |
| 日期 | 2026-10-30（Asia/Shanghai） |
| 状态 | 工程主体已实施，开发检查通过；存在明确的真实模型启用及正式验收缺口，不能判整轮验收通过 |
| 对应PRD | [PRD-003](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md) v1.2 |
| 对应ADR | [ADR-003](../adr/003-sesrag-rag-mineru-implementation-plan.md) v1.3（保留v1.2产品决策，补实际落地说明） |
| 实施前基点 | `58d9d1d4207fc61d043cbf3271308f8d14d71005`；本轮修改仍在工作区，未自动暂存、提交或推送 |
| 文档职责 | 说明主要文件、模块、接口、契约、验证与差异；不替代后续详细实施结果调研、TEST-003测试方案及正式报告 |

## 1. 当前交付和结论边界

沿用FastAPI、Vue/Pinia、PostgreSQL任务表与Event Journal、Redis通知和Compose。向量库仍为**PostgreSQL + pgvector**，新检索在数据库内过滤范围、计算cosine并Top-K排序；没有引入Milvus、ANN、混合检索或通用Agent框架。

九格式按`format_router_v1`固定分流：txt/md本地结构解析；doc/docx/pdf/xls/xlsx/ppt/pptx原件经MinerU精准API，上传／重建逐次确认完整原件外发；失败不转换格式、不切本地。新增知识库及不可变配置／向量空间、异步ParseJob和IndexBuild、冻结RetrievalView、真实／Mock适配、独立诊断、`rag.search@1`、实际上下文证据与引用以及工作台交互。

已通过316项后端单元／API／集成检查和26项前端测试；三轮独立Compose开发smoke均通过，最后一轮覆盖最新后端、四迁移、真实PG多维隔离、7项数据库保护、API/Worker、前端同源代理和销毁。七办公格式加扫描PDF共8个真实产物可归一化，两类真实模型协议请求成功。**但真实Embedding/rerank的专用输入计数未校准，生产Profile仍返回`INPUT_COUNTER_UNVERIFIED`并保持不可用**；真实模型完整入库／检索、效果及性能验收不能宣称通过。

未修改或调用前轮正式验收目录`tests/sesrag-persistent-session-workspace-test/`。现有底层单元／集成测试继续运行，用来守护共用租约、消息终态和兼容行为，不等于把前轮验收工程并入本轮。

## 2. 文件与模块变动

以下路径均相对仓库根；“新增”是本轮新增，“修改”是对既有模块接线或兼容调整。完整逐文件差异以当前工作区为准，模块用途同时写入对应README。

| 范围与主要文件 | 变动 | 实际职责和结果 |
| --- | --- | --- |
| `backend/domain/rag.py`、`rag_profiles.py`、`rag_snapshot.py`、`ports/rag.py` | 新增 | 九格式固定路线、空间描述hash、版本化非Secret配置、检索参数及冻结DTO、固定只读工具定义和能力Port。 |
| `backend/db/rag_models.py`；`backend/db/models.py` | 新增／修改 | 知识库、四类Profile、解析Job／产物／结构块、构建、视图、检索执行、工具、Bundle组件、实际上下文范围、旧引用保护和GC墓碑；扩展Document、Chunk、Task、Run。 |
| `backend/application/knowledge_bases.py`、`rag_profiles.py`、`rag_operations.py` | 新增 | owner范围、库名称／启停、不可变空间和配置导入、独立资源操作幂等。不同源操作不误用文件hash作为远端幂等保证。 |
| `backend/application/index_builds.py`、`parse_jobs.py`、`rag_task_execution.py` | 新增 | 上传／重建／取消短事务、冻结路由和配置、同batch检查点恢复、正常等待让出、有效代写回；成功后原子发布，失败保留旧active。 |
| `backend/infrastructure/rag/office_validation.py`、`isolated_processing.py`、`local_structure.py`、`structured_chunker.py` | 新增 | 有界输入／MIME／OOXML／OLE预检；txt/md结构解析、标题和表格等块切片、UTF-8字节配额；Linux资源限额子进程。办公预检不提取正文、不执行Office、不做本地兜底。 |
| `backend/infrastructure/rag/mineru_client.py`、`mineru_outputs.py`、`html_tables.py`、`download_safety.py`、`artifact_store.py` | 新增 | 精准API申请／原件PUT／同batch轮询／下载，安全ZIP/JSON/Markdown及HTML表格归一化；逐跳URL/DNS限制、限量读取、AES-GCM加密私有签名能力状态。 |
| `backend/infrastructure/providers/bailian_embedding.py`、`bailian_rerank.py`、`rag_registry.py`；`application/vector_validation.py` | 新增／修改 | 百炼两种独立协议；显式1024维、响应index映射、有限非零向量和float32归一化、原生rerank及候选校验；真实Profile启用前检查计数与凭据。 |
| `backend/infrastructure/rag/vector_search.py`；`pgvector_store.py` | 新增／修改 | 新查询以MATERIALIZED授权空间CTE先隔离后计算距离，PG内ORDER BY/LIMIT；旧可信384查询也改数据库排序。SQLite中的Python计算只用于测试，不是生产PG路径。 |
| `backend/application/retrieval_views.py`、`retrieval.py`、`evidence_assembly.py`、`source_locations.py` | 新增 | 冻结实际批次／过滤、共用检索和诊断、重排故障分类、同文档同批次邻近合并、分数／删减原因及可靠来源映射。 |
| `backend/application/rag_sessions.py`、`rag_run_execution.py`、`legacy_rag.py`；`session_runs.py`、`session_execution.py`、`session_threads.py`、`context.py`、`task_execution.py` | 新增／修改 | 复用既有Thread/Branch事务创建schema3快照／视图；每Task/generation只读工具、预算和实际选入证据；三代历史、旧引用FK保护、终态消息和事件同事务。 |
| `backend/infrastructure/queue/postgres_queue.py`、`adapter.py`、`events/journal.py`；`workers/runtime.py`、`handlers/*` | 新增／修改 | 增加index_build／retrieval_diagnostic，waiting_external不计失败重试；受控取消、租约恢复、旧代拒绝及v3事件；旧index_document保留文本兼容、阻断DOCX写入。 |
| `backend/application/rag_capacity.py`、`rag_gc.py`、`rag_retention.py` | 新增 | 10GiB总／1GiB临时软预算；按引用与锁保护清理；独立诊断7天／墓碑30天；保留未知提交／错误摘要。 |
| `backend/api/routes/v3/`、`schemas/v3/`；`backend/app.py`、`config.py`、`domain/enums.py` | 新增／修改 | v3资源／检索／会话路由和严格DTO、安全错误白名单及配置；正式字段在接口文档和契约。 |
| `backend/tools/{sync_rag_profiles,upgrade_rag_schema,confirm_legacy_rag_space,cleanup_rag_artifacts,check_rag_providers,export_rag_contracts}.py` | 新增 | 显式导入、分段升级、可信旧空间确认、有界清理、获准样本真实协议探针、契约导出及漂移检查；正常服务不扫描密钥文档。 |
| `migrations/versions/0007_*`～`0010_*`；`migrations/rag_checks.py`、`rag_guards.py` | 新增 | catalog、构建／多维vector、视图／证据、任务和Run协议；旧数据归属／未知空间隔离、FK、不可变触发器及安全降级门禁。 |
| `contracts/*_v3.json`、`evidence_v2.json`、`citation_v2.json`、`tool_v1.json`、`tool_rag_search_*` | 新增 | 16份导出资源／消息／Run／事件／上下文／工具契约，加固定工具输入输出及binding契约；旧事件／引用不重写。 |
| `frontend/src/api/v3/`、`types/api-v3.ts`、`events/rag-event-stream.ts`、`stores/rag.ts`；原stores/API/types/生成器 | 新增／修改 | 从契约生成类型、v3调用、三代事件、知识范围／配置／诊断状态；epoch隔离迟到响应，网络结果未知时沿用原操作键。 |
| `frontend/src/components/RagPanel.vue`、`EvidenceViewer.vue`、`rag-labels.ts`；原上传／消息／事件／上下文组件、`WorkspacePage.vue`、`markdown/render.ts`、`styles.css` | 新增／修改 | 库和策略、办公逐次授权、active/latest、诊断／证据和中文状态投影；外部Markdown资产阻断及DOM清洗；组件不自行宣布事实终态。 |
| `.env.example`、`docker-compose.yml`、`docker/api/Dockerfile`、`docker/rag-*.example.json`、`pyproject.toml`、前端package/lock | 新增／修改 | 环境／Secret alias、共享私有卷、分段迁移入口、无Secret模板、依赖及0.3.0版本；依赖构建缓存和有界网络超时。 |
| `tests/unit/test_rag_*_v3.py`、`tests/api/test_rag_*v3.py`、`tests/integration/test_rag_*v3.py`、`frontend/tests/rag-workspace.test.ts` | 新增 | 路由／空间／授权／安全／协议／切片／恢复／API／实际引用和前端回归；外部协议测试用受控transport，不自动带真实Key。 |
| `tests/fixtures/rag-v3/` | 新增 | 九格式和扫描PDF固定输入、manifest/hash、真实安全统计；两个旧Office公共样本附来源及Apache-2.0许可证。 |
| `tests/integration/compose.rag-v3.yml`、`run_rag_v3_check.py`、`rag_v3_pg_probe.py` | 新增 | 本轮独立随机项目闭环，无宿主端口、不读开发.env；真实PG和服务探针、finally收日志销毁并标签复查。 |
| 根／模块README、`CONTEXT.md`、`docs/接口文档.md`、本轮PRD/ADR及`docs/runbooks/rag-v3-development.md` | 新增／修改 | 当前术语、模块用途、正式接口、实施差异、Windows/Linux配置／升级／清理步骤和验证边界。 |

## 3. 接口、契约和迁移变化

正式API说明统一在[接口文档第8节](../接口文档.md#8-v03-rag-与-mineru接口)，此处仅描述变化，不复制另一份完整接口表。

- **新增v3资源**：知识库、可用Profile、文档／标签／构建／取消／切片、异步诊断、证据Bundle读取。
- **新增v3会话契约入口**：消息创建、Thread事实读取、Run／Context／Event／SSE、取消／retry／regenerate。内部复用原会话事务；不是另一套聊天事实源。Thread/Branch元数据和生成模型选择仍走v2。
- **修改兼容行为**：v1 DOCX上传／重建409 `DOCUMENT_WRITE_UPGRADE_REQUIRED`；v1 txt/md保留本地旧解析／错误时点并登记新批次身份。旧客户端遇到不可表达的schema3返回升级错误。v3读三代历史；对无冻结view的旧Run显式重试／重生成返回`LEGACY_RETRIEVAL_VIEW_UNAVAILABLE`，不能把现在的知识当过去视图。
- **新快照／引用**：RunSnapshot3保存完整非Secret RAG配置和view；ContextPlan3与ContextEvidence保存真正选择的Bundle组件范围；Citation2只关联这些实际输入。Event3增加工具／检索阶段，仍按Run seq追加、补放／去重，工具成功不等于Run成功。
- **严格投影**：API不输出远端batch、签名URL、私有路径、Key或原始异常。生成类型和JSON Schema导出有只读漂移检查。

迁移顺序为0007 catalog → 显式初始化配置／默认库 → 0008构建／vector → 0009视图／证据 → 0010任务／Run。最终revision为`0010_rag_task_and_run_protocol`；0009实际revision缩短为`0009_rag_views_tools_evidence`以满足Alembic PostgreSQL的32字符限制，文件名不变。源、空间、Chunk／Build／文档及active/latest指针有关系约束；PG触发器保护配置／已发布事实和Journal。

旧未知384向量不自动认定Mock；有可信部署来源才用显式确认工具。旧消息／事件保持原JSON；已经删除的旧Chunk无法重造。出现本轮事实后拒绝downgrade，回退依赖升级前数据库＋文件＋镜像的一致备份；不得用删事实绕过。具体命令见[Runbook](../runbooks/rag-v3-development.md)。

## 4. 关键状态、不变量和校审修复

1. 正常云端等待通过持久队列让出，不消耗错误重试额度；恢复只访问同一batch。提交应答未知时本地失败、不自动新申请，新操作须确认潜在重复成本。
2. 已提交后本机取消／超时不保证远端撤回：`remote_outcome=unknown_may_continue`。上游明确failed和已完成下载阶段分别保留真实failed／completed事实；不会把本机终态说成云端取消。
3. 候选构建及外部调用不持长事务；Task/worker/generation和租约检查保护发布。失败、取消、失租不切active，新成功批次不删除历史引用。
4. 新Run固定owner／库／space／批次集合和版本化策略；标签／默认配置／重建变化只影响后续新Run。安全blocked仍可阻断正在恢复的调用，普通停用不偷偷改冻结配置。
5. 真实与Mock、同维不同模型及不同维度不混查。PG先物化授权空间再计算距离，防止优化器跨空间计算导致混维错误；查询／文档使用同一float32归一化。
6. 检索空、关闭、未执行、基础设施失败及显式dense降级分别表示。重排仅允许受控错误码降级，凭据／安全错误不能降级成成功。
7. 旧txt/md新发布补齐IndexBuild、space、维度、hash和latest，并按连续／重叠一致片段物化精确正文Artifact，不重新解析或猜造历史；旧协议新写入的ContextPlan和Message引用同样建FK保护，避免仅迁移前引用受保护、迁移后旧客户端引用被GC漏掉。
8. 真实Excel产物含HTML表格，补安全文本归一化；仅图片而无有效文本失败`MINERU_EMPTY_OUTPUT`。Word/PPT/Excel缺原源定位如实标规范块，不将派生页当原页。
9. 前端确定性4xx允许修改后新操作，网络结果未知保留原幂等键；Top-K／半径／过滤／query提交前校验。每次选办公原件重置外发授权。
10. GC不删除ParseJob错误／未知提交摘要；独立诊断过期返回410并保留30天墓碑；不删source、active/latest、Run view或引用中对象，不全局prune。

上述修复先以相应负例复现，再修改并回归。迁移revision过长和前端代理Host探针分别在真实PG／容器检查中发现：前者修revision，后者按浏览器Host测试，未关闭Vite Host防护。

## 5. 验证命令与实际结果

全部从仓库根执行，Windows使用`.venv/Scripts/python.exe`，Linux替换为`.venv/bin/python`。普通pytest没有自动读取私密配置或付费上传。

| 命令／检查 | 实际结果与范围 |
| --- | --- |
| `python -m pytest tests/unit tests/api tests/integration -q` | **316 passed，120.73秒**；日志`data/rag-implementation/all-tests-final.txt`。其中含新旧底层回归；SQLite不能证明PG多连接并发。 |
| `python -m ruff check backend migrations tests/unit tests/api tests/integration` | 通过。 |
| `python -m ruff format --check backend migrations tests/unit tests/api tests/integration` | 201份文件格式通过。 |
| `python -m mypy backend` | 130个source files通过。 |
| `python -m backend.tools.export_rag_contracts --check` | 通过；生成文件与DTO一致。 |
| `npm run check:api --prefix frontend`、`npm run typecheck --prefix frontend` | 通过；类型未漂移。 |
| `npm run lint --prefix frontend` | 0错误；保留MessageTimeline清洗HTML渲染的1条`vue/no-v-html` warning，不把warning视为安全证明。 |
| `npm run test:unit --prefix frontend` | **4文件／26项通过**，包括外发授权、确定拒绝／未知重放、范围切换和恶意Markdown。 |
| `npm run build --prefix frontend` | 通过。 |
| `python tests/integration/run_rag_v3_check.py` | 三轮产品probe及清理均通过；最终证据见下文。 |

隔离运行证据：

| 随机项目 | 结果 |
| --- | --- |
| `sesrag-rag-check-aab4c943f7` | 完整smoke通过，pgvector0.8.2；384／1024共库隔离、SQL对照及5项保护通过，清理通过。 |
| `sesrag-rag-check-bdce4c5ca1` | 指针约束补修后后端和迁移通过；补active/latest关系拒绝共7项数据库保护；txt/md、诊断、schema3 Run→Context/Citation/SSE、重建后原引用、前端服务／代理通过；清理后container/volume/network/images全为空。 |
| `sesrag-rag-check-15e869a51b` | 独立审查补修后的最终源码检查通过，新增v1文本发布→v3检索→证据正文读取，原主链路／384与1024隔离／7项PG保护继续通过；容器、卷、网络和应用镜像残留全空。 |

每轮目录为`data/rag-implementation/<项目>/`，包含startup、model-import、probe、containers、cleanup及summary。最终`probe_passed=true`、`cleanup_exit=0`。最终一轮已包含中文显示／CSS和审查补修；前端检查也再次通过。开发检查不映射宿主端口，不使用开发数据库、不读取根.env；清理仅本项目资源和应用镜像，保留共享基础镜像／构建缓存。

过程中Docker异常、Hub/npm/pip超时、旧迁移revision和Host探针失败均是先前尝试，不能抹为通过；本地保留原目录。Docker恢复后已推进成功；旧失败项目留下的明确命名应用镜像单独清除，未执行全局prune。一次全量测试因离线cl100k_base缓存缺失失败，已在准备阶段显式补齐并验证离线加载，再跑上述最终316项；不是让普通请求隐式下载。

真实服务安全摘要固定在`tests/fixtures/rag-v3/provider-observations.json`：

| 真实探测 | 结果与含义 |
| --- | --- |
| doc/docx/pdf/xls/xlsx/ppt/pptx及扫描PDF | 8个产物均parsed；按当前Normalizer取出正文／结构。PDF部分可靠页映射，其他主要规范块。不是所有版式／表格语义保真证明。 |
| qwen3.7-text-embedding | 两条文档＋一条查询，显式1024维，协议成功；尚非产品真实空间完整入库／查询验收。 |
| qwen3.7-text-rerank | 原生协议返回有效候选身份／排序；本次小样本顺序为[0,1]，未证明排序改变或语义质量提高。 |

此前下载域白名单拒绝属于正确安全拦截；核实官方产物域后只读补取同一批次，没有重新上传。私有检查点／加密Key留在已忽略的`data/`，不在结果文档复制远端能力URL或凭据。

## 6. 需求覆盖与实际差异

下列编号来源于PRD-003 §8/§9，不是旧用例编号。工程实现和检查不能代替所有验收场景。

| 需求范围 | 当前实现／证据 | 剩余验证或差异 |
| --- | --- | --- |
| RAG-001～006 | 库／空间、九格式校验、固定路由、标签和幂等；单测/API回归。 | 生产认证/RBAC是原非目标，当前仍固定owner。 |
| RAG-007～015 | MinerU单Job、原件外发、状态／安全／恢复／失败／取消、本地及云端结构；真实8产物和受控故障回归。 | 七格式当前有限样本；全面结构／异常格式质量须独立验收，缺原源坐标如实显示。 |
| RAG-016～022 | 结构／字符切片、批次／hash、多维向量、候选原子发布、引用保护和重建。 | 真实模型输入计数未校准，RAG-018真实产品入库／查询门槛未完成。 |
| RAG-023～031 | PG内精确排序、范围／参数、可选重排、邻近去重、ContextEvidence、trace；真实PG及Mock工具链通过。 | RAG-026真实全链路和语义重排观测未完成。生成预算当前保守地整Bundle选择／丢弃，不做Bundle内部部分裁剪，引用仍严格只指选入内容。 |
| RAG-032～038 | 固定工具／每代调用、schema3冻结、三代兼容、事件和终态事务、旧入口升级与引用保护。 | 未做完整多Worker故障／备份恢复演练，不能仅用单进程SQLite认定全部并发边界通过。 |
| RAG-039～042 | 工作台固定授权、库／策略／诊断／证据、中文状态及安全渲染；前端26项与容器同源代理检查。 | 未完成真实浏览器全交互验收；诊断没有可选生成模型预算预览入口，核心诊断不生成Run／Message。 |
| RAG-043／044 | 九格式固定输入、真实七办公加扫描PDF、两类真实服务协议已取证。 | RAG-044计数前提及产品真实完整链路未验收，仍阻断真实Profile，不能以协议调用替代。 |
| RAG-045 | 固定源文件和manifest已准备。 | **20有答案＋5无答案标注集／Recall@20≥0.85、同视图rerank与拼接效果未完成**。当前样本不是该语义评测集。 |
| RAG-046 | 本轮独立Compose开发闭环、样本、结果和清理入口已落地。 | 后续独立TEST-003测试点／用例／分类验收及正式报告不在本次开发检查中完成。 |
| NFR-001～007／009～012 | 外发／Secret／出站边界、PG事实／有界恢复、Port分层、故障注入、容量／GC、版本兼容和Compose文件已实现并部分动态验证。 | 全面秘密泄漏扫描、真实并发停机与磁盘压力、长期恢复、浏览器安全矩阵待正式验收；软预算不等于宿主硬配额。 |
| NFR-008 | 实际SQL已在PG执行并与独立cosine结果对照，未拉全量向量到Python。 | **10000 Chunk／100次预热查询及p50/p95、资源峰值未执行**，不声称达到1秒指标或生产SLA。 |

实现拆分有以下明确调整，已同步ADR，未通过删减PRD验收掩盖缺口：

- 原计划细分路由收敛为`resources.py/retrieval.py/sessions.py`，DTO中的会话／事件集中`sessions.py`；前端调用和store收敛为`api/v3/rag.ts`／`stores/rag.ts`，页面仍仅编排，具体职责见模块README。
- `source_mapping.py/normalizer.py`职责由`application/source_locations.py`与`mineru_outputs.py/local_structure.py/html_tables.py`承接；没有空壳同名模块。输入计数目前为明确字节配额和启用守卫，未伪造专用tokenizer。
- `rag_tools.py`的固定定义在`domain/rag_snapshot.py`，执行在`rag_run_execution.py`；不增加动态工具执行器。
- 清理命令名为`cleanup_rag_artifacts`；用锁＋事务／FK和安全文件重扫代替计划中的持久gc_state，不改变引用保护目标。
- 兼容v1文本保留旧Parser／字符窗口和错误时点，发布适配共享IndexBuild／空间／引用约束；不冒充新解析产物或MinerU，不保留新DOCX本地写入分支。

## 7. 未完成事项与后续处理

| 项目 | 原因／影响 | 后续动作 |
| --- | --- | --- |
| 真实模型专用输入计数 | 缺官方tokenizer／计数能力或能证明适用边界的保守上界校准；即使Key和协议可用也不能跳过。影响真实Embedding/rerank Profile启用与RAG-018/026/044。 | 取得可复查的官方计数／上界依据并做边界校准，增加Profile版本导入；新建真实空间入库并查询，再验真实rerank，不修改Mock空间身份。需要服务方资料或操作者提供可核实依据。 |
| 效果评测和10k性能 | 目前仅开发smoke与少量真实协议样本；没有足够标注数据和正式指标记录。 | TEST-003准备20+5跨九格式标注，真实计数前提满足后同视图对照；独立PG中10k／100查询统计数据库p95及硬件资源。不是凭本次通过数字自动认定。 |
| 全面真实浏览器／异常与运维验收 | 组件替身和同源HTTP检查不能覆盖全部真实UI、并发、停机、磁盘压力和旧库备份恢复。 | 后续独立测试方案设计新分类脚本与环境，不借用前轮正式套件；失败／受限分别列报告。 |
| Bundle内细粒度预算剪裁 | 当前安全选择整Bundle，可能舍弃尚能放入的部分证据；不构成越界引用，但空间利用率低于计划。 | 后续若需要，提高预算利用率并同步ContextEvidence区间裁剪及负例；现实现不宣称已有部分截取。 |

## 8. 最终整体校审结论

最终使用code-review技能按Standards／Spec双轴只读复核：规范轴3项、需求轴3项发现，去重后5项（旧文本缺Artifact、认证错误降级、未知成本确认遗漏、阶段间安全禁用未复查、临时预算零槽位）。均补失败测试并修正；两轴再次只读复核未发现这些修复引入新的实质问题。最终316后端和第三轮Compose覆盖补修代码，而非沿用修复前结果。相关位置分别为`legacy_rag.py::materialize_legacy_text`／`PgVectorStore.replace`、`BailianRerank.rank`、`start_build`、`validate_frozen_retrieval`及`Settings.rag_tmp_budget_bytes`。

已按九格式固定路线、授权、未知提交／取消、有效代、候选与active、空间和SQL、冻结视图、工具与Run终态、实际证据、兼容和清理逐项校审；发现的可本机处理问题已修正并回归。工程主体具备可运行纵向链路，静态检查、后端／前端测试及隔离Compose开发检查通过。

不能认定全部PRD验收完成：真实模型计数是当前明确启用阻碍，另有效果、性能及完整独立验收未执行。保留这些目标与退出条件，ADR暂维持“已接受／工程主体已交付”，后续满足门槛后再转“已实施”。没有自动提交或推送，没有以旧验收结果、新Mock结果或少量真实调用替代本轮完整验收。
