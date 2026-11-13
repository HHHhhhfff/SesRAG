# PRD-003正式验收缺陷修复记录

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | 003-REPAIR／1.0；项目v0.3、sesrag_v0.3 |
| 日期 | 2026-11-13；原失败与首批修复证据标记2026-11-12，运行文件名沿用其唯一标识，不据文件名推断本地日期 |
| 对应目标 | [PRD-003](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)、[ADR-003](../adr/003-sesrag-rag-mineru-implementation-plan.md)§16 |
| 依据与范围 | [缺陷报告](../../tests/sesrag-rag-mineru-test/缺陷报告.md)RAG-DEF-001～016；[修复计划](../../tests/sesrag-rag-mineru-test/缺陷修复实施与回归计划.md)；只修本轮产品及测试工程，前轮验收目录不变 |
| 当前状态 | 产品原RAG-DEF-001～010已修复并正式回归通过；工程缺口已补，真实八个办公目标复验通过；采用239通过、9受限，完整PRD仍待真实计数／效果条件满足 |

## 实际变更与边界

| 文件／模块 | 变更及原因 |
| --- | --- |
| `backend/workers/runtime.py`、新增`backend/application/stage_observation.py` | 补安全关联身份、真实构建文档／解析Job及阶段单调时钟耗时；日志和观测失败不替换业务结果，停机沿缓存身份。 |
| 新增`backend/infrastructure/rag/cloud_html.py`、`html_tables.py`、`mineru_outputs.py` | 云端产物形成规范区间前清危险原始HTML和资产；按Markdown真实代码语义保护代码，表格恢复在单元格转义前；本地txt/md原源区间不变。 |
| `backend/application/context.py`、`session_execution.py` | schema3最终选入证据分配S1…且计入预算；Plan、模型输入、ContextEvidence及Citation共用最终顺序，裁剪后重新编号。 |
| `backend/api/schemas/v3/documents.py`、`routes/v3/resources.py`、`application/index_builds.py`、`structured_chunker.py` | 严格整数；新增冻结`max_chunks`上限及正式multipart参数，超限在Embedding外发前失败。缺省50000保留旧行为和旧幂等指纹，非缺省预算参与指纹。 |
| 新增`migrations/versions/0011_rag_source_integrity.py`、`backend/db/models.py/rag_models.py` | Chunk来源绑定批次派生来源；事务延迟关系允许合法确认中间态、提交时一致；保留new/legacy_unknown/legacy_confirmed/legacy_verified。 |
| `backend/tools/confirm_legacy_rag_space.py`、`upgrade_rag_schema.py` | 按KB→Document→Build排序锁定并重验；清单整体提交／失败回滚，旧空间有证据确认，不重算旧向量；0010显式升级0011。 |
| `contracts/api_responses_v3.json`、`backend/tools/export_rag_contracts.py`、`frontend/src/types/api-v3.ts`、`docs/接口文档.md` | 同步ChunkPolicy；Location仍verified/block_only，删除说明中错误unavailable；不通过放宽DTO消除失败。 |
| `frontend/src/stores/documents.ts`、`DocumentUploader.vue` | 未知重建保留原参数／原键，原操作恢复；切片分页以文档／批次／请求代数隔离并按chunk去重。 |
| 新增`frontend/scripts/generate-event-validator.mjs`、`src/events/generated/`、`rag-event-stream.ts`、package／锁文件 | 正式事件Schema预编译为浏览器校验器；HTTP/SSE共用完整校验，依赖与漂移检查同步。生成包体积提示保留，不隐去。 |
| `tests/unit/`、`tests/api/`、`tests/integration/`相关底层测试 | 覆盖原失败、反向来源伪造、合法旧库确认、升级幂等、真实HTTP冻结、代码／表格安全及停机观测回收；不改前轮验收工程。 |
| `tests/sesrag-rag-mineru-test/` | 各受影响分类加强断言；有限cap预算、独立20+5原源标注、真实产物绑定、指标helper、有界宿主资源采样与总结；仅EVAL_001从标注缺口解限，其他真实计数前提不伪造。 |

测试新增文件职责、脚本入口与全部实际命令见该目录README和最终报告。原源投影的PDF／Office读取依赖只在测试工具使用，不作为产品本地解析或MinerU回退。未自动提交／推送／重置。

底层测试与本轮工程实际变动进一步列明：

| 文件 | 职责／本次调整 |
| --- | --- |
| `frontend/tests/documents.test.ts`、`rag-event-stream.test.ts`（新增） | 独立覆盖重建未知响应身份、分页交错／重复、事件完整Schema负例。 |
| `tests/unit/test_rag_context_order.py`、`test_rag_worker_observability.py`（新增） | 证据重排／裁剪S编号及停机观测不遗留任务；已有`test_context_planning.py`同步正式预算行为。 |
| `tests/unit/test_rag_chunking_v3.py`、`test_rag_mineru_tables_v3.py`、`test_rag_migrations_v3.py` | 严格整数／cap、危险HTML与代码语义、来源升级及约束；均保留原断言。 |
| `tests/api/test_rag_resources_v3.py`、`tests/integration/rag_v3_pg_probe.py`、`test_execution_integrity.py`、`test_v2_run_execution.py` | 真实multipart冻结与拒绝、0011升级探针及合法旧来源／执行一致性。 |
| 本轮`specific_test_script/{chunking,compatibility,execution,mineru,performance,retrieval,vectors}-tests.py` | 对应原失败及新cap补强断言、正式来源/编号/日志核验；EVAL_001解限。 |
| 本轮`helpers/{source_annotations,evaluation_metrics,resource_observation,evidence_capture,selftest_engineering}.py`（新增） | 独立源金标／指标、有界资源观测、严格请求证据采集与工程正负自测；用途均已进局部README。 |
| 本轮`helpers/{live_cases,synthetic_rows,orchestrate,environment_probe,environment_cases,selftest_preparation,audit_cases}.py` | 共享有限预算、Computed夹具排除、统计归并、最终资料挂载和PDF按hash元数据选择；环境与覆盖审计适配。 |
| 本轮`fixtures/source-annotations.json`与`.schema.json`（新增）、`case-catalog.json`、`manifest.json`、`requirements-test.lock`、两份Compose | 固定20+5金标、可验证性／分类接线及仅测试读取依赖；tools只读挂载正式接口文档和两份非Secret YAML。 |

精确到单个文件的本任务变更清单保存在[交付审计](../../tests/sesrag-rag-mineru-test/artifacts/rag-repair-20261112-results/handoff-audit.json)的`changed_files`，与任务起始指纹比较，不能把本任务之前已有的未提交测试工程全部归为本次新增。

## 审批发现与处理

- 独立前端审查通过；数据库审查后又由实际工程接线发现上传Form缺失，新增multipart失败回归后修正并复核。
- 旧v1合法`legacy_verified`、默认幂等指纹和确认锁顺序均在整体检查中补齐，避免来源防伪约束破坏兼容路径。
- 云HTML初版被独立审查复现转义反引号绕过及表格管道列损失；修正为Markdown token语义及转义前恢复，真实ZIP内存样本复核通过。
- 后端353例通过时出现异步观测任务回收警告；定位停机最终日志仍查询数据库，按停止／取消边界修复并追加回收验证。最终结果以后续正式记录为准。

## 真实服务与未退出边界

额度已通过生产生成适配器真实短请求收到非空回答确认恢复；这是协议连通性，不是完整Thread/Run/Worker验收。模型专用计数适用依据、冻结词表／消息模板或严格上界尚未确认，不能只改verified。公开资料复核见[计数记录](../../tests/sesrag-rag-mineru-test/计数资料复核记录.md)。DNS恢复已由八个目标的新正式MinerU解析、结果下载及归一化确认；原未知提交未自动重提。扫描PDF初次选择错误额外消耗1job，修复选择器后补测：共9个新逻辑云作业，最终八个正确目标均通过。

完整真实检索／重排／生成效果与四能力性能仍需相关计数前提。标注集准备、局部性能及离散资源采样不能冒充这些未执行目标。最终失败／受限的具体用例、原因与后续方向维护在缺陷报告。

## 最终验证与交付

正式完整本机`rag-repair-20261113-local2`：220通过，退出0，清理passed；ENV十例完整生命周期审计通过，包含正常启动、数据准备、分类执行、证据汇总、失败／超时／强停恢复及重复清理。真实DOCX、DOC、文本PDF、扫描PDF、XLSX、XLS、PPTX、PPT八个目标和预算例通过，正式生成准入明确返回`COUNTER_EVIDENCE_MISSING_generation`且未外发。248例最终采用239通过、0未通过、9受限、0工程错误，逐例回填与原始hash核对见[测试报告](../../tests/sesrag-rag-mineru-test/测试报告.md)和[采用索引](../../tests/sesrag-rag-mineru-test/artifacts/rag-repair-20261112-results/adopted-results.json)。

完整本机与七格式采用FrozenBuild `7ac937b6738a375690b417cc`；最后仅真实PDF选择器及离线测试变化，以envscan复验后采用`53534717c92a35f6739ad4ad`完成扫描补测。产品代码未再变化，两个构建的范围分别保留，不宣称同源完整两轮。

开发层实际验证命令及结果：

```powershell
# 项目根目录；实际最终结果354 passed，日志在本轮artifacts/rag-repair-20261113-backend-final.log。
.venv/Scripts/python.exe -m pytest tests/unit tests/api tests/integration -q -W error::pytest.PytestUnraisableExceptionWarning
.venv/Scripts/python.exe -m ruff check backend tests/unit tests/api tests/integration
.venv/Scripts/python.exe -m mypy backend
.venv/Scripts/python.exe -m backend.tools.export_rag_contracts --check
# frontend目录；57项单测、类型、Lint、构建及生成漂移检查通过。
npm run test:unit
npm run typecheck
npm run lint
npm run build
npm run check:api
```

宿主48项基线＋最终19项新增工程自测通过，最终tools内19项也通过。真实PG开发验证及正式Compose覆盖空库／重复升级、来源防伪、旧库可信确认与合法v1发布；PG性能10000有效Chunk、100预热＋100测量p95=52.080ms、错误0，仅代表本机局部数据库召回。前端既有v-html警告和约551KB主包体积提示保留。

最终机械审批核对248个唯一用例、239个复现／稳定性字段、9个受限原因及留空字段、逐例证据hash、所有运行清理passed；容器／卷／网络无本套件残留，runtime/tmp为空；前轮验收目录及HEAD保持不变。缓存、冻结镜像和脱敏证据有意保留，不执行全局prune。审批发现的报告统计、旧分类口径和额外云作业披露已更正。

整体代码审批与最终交付文档独立审批均通过，Critical 0、Important 0；文档审批发现README旧迁移0010及All旧219例已同步0011／220。本任务84个实际变动文件的`git diff --check`通过，最终机械审计和分类覆盖审计通过；这不扩大九项受限的结论。

仍未完成的范围：真实模型计数适用资料／冻结与边界校准，以及依赖它们的真实向量／query／rerank／正式生成、完整效果和四能力性能；需要供应商实际部署的tokenizer／消息模板或可证明严格上界，详见[缺陷报告](../../tests/sesrag-rag-mineru-test/缺陷报告.md)DEF-012～014。Linux宿主、真实键盘Ctrl+C、生产认证及生产SLO未测；未重跑旧PRD正式验收。不声称完整PRD验收通过。
