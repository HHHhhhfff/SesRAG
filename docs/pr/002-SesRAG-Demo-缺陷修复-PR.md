# PR-002：SesRAG Demo 缺陷修复实施记录

- **编号**：002
- **版本**：v0.1（正式两轮后实际交付）
- **日期**：2026-10-13（UTC+8）
- **状态**：纳入修复及本机可验证范围已实施；平台Ctrl+C原P0变体/方案暂缓未完整动态验收；2026-10-13独立规格✅/质量Approved（仅该范围）
- **对应 PRD**：[001 Demo PRD](../prd/001-SesRAG-项目Demo-PRD.md)
- **对应 ADR**：[ADR-002 缺陷修复方案](../adr/002-SesRAG-Demo-缺陷修复-plan.md)
- **结果真源**：[复测和验收报告](../../tests/demo-smoke/复测和验收报告.md)；原 [测试报告](../../tests/demo-smoke/测试报告.md) 与 [缺陷报告](../../tests/demo-smoke/缺陷报告.md) 保留为 2026-10-07 历史基线。
- **代码基线**：`sesrag_v0.1`，HEAD `dabc45c82f076880403a7c19c296947609db92da`，包含未提交及用户暂存修改；本次不自动提交、推送、重置或改写暂存区。

## 1. 当前交付与历史阅读边界

正式结果见第6节：278文件冻结同源两轮all、逐check无failed、149卡片及104原项回填、质量/性能/精确清理已保存。严格主入口因明确blocked非零，不能写所有P0全部动态通过。**以下§1后续旧段落及§2～5为原中期历史，保留发现/修复/未执行事实；其中5d/I1/I2/N1待修表述不再代表当前状态。**

### 原阶段范围（历史）

本轮修复仍交付单用户开发 Demo，不增加生产认证、知识库完整版本审核发布、工具授权系统、真实模型效果或生产 SLO。PostgreSQL 保存事实，Redis/SSE/页面只提供通知或投影；重试不创建第二组用户 Message/Run。

基础、执行、RAG 后端及前端专项已通过相应独立规格/质量审查。真实执行驱动阶段又发现并修复 Run 最终 flush 跨期发布、422 无效输入回显以及索引日志业务关联缺失。5a执行、5b文档/协议、5c持久浏览器测试驱动及各自修正均已限定批准；5d独立QLT又发现PAR空fixture兼容缺口，已完成最小测试驱动修正及限定审查，完整PAR20passed/1原定blocked、实际exit2。当前继续5d剩余门禁；完整all正式两轮、整体审批及最终验收尚待完成，专项通过数量不能代替退出条件。

## 2. 实际变更与文件职责

“新增”以本轮修复前代码为参照；Git 是否已被用户暂存不改变其实现职责。用户原有的完整 PRD 重命名、任务说明及 AGENTS/通用规范编辑保留，不归功于本轮代码修复。

| 修复包 | 修改已有模块 | 新增文件及用途 | 实际行为与边界 |
| --- | --- | --- | --- |
| RM-01 基础 | `backend/config.py`、`app.py`、`api/routes/health.py`、`api/schemas/`、`db/models.py`、根 Compose/环境模板、Alembic 配置/入口/0001 | `migrations/versions/0002_demo_integrity.py`；基础 API/配置/完整性/迁移测试与 `tests/unit/foundation_pg_probe.py` | 有限正值/组合/384 校验；运行时 Secret；PG 有界探测和安全503；Redis真实降级/重连；固定历史迁移及约束；旧事实保留/冲突拒绝。请求422只公开安全字段。 |
| RM-02 会话事实 | `application/threads.py`、`runs.py`、`workers/handlers/run_handler.py`、Message公开投影 | `application/task_execution.py`、`tests/integration/test_execution_integrity.py`、`execution_pg_probe.py` | Thread锁内幂等复查、共享消息seq；冻结完整非Secret快照、旧Mock显式解码；最终Message/Run/Task/Event整组提交。最后flush后检查保留的lease/deadline，跨期整组回滚。 |
| RM-03 调度 | `queue/postgres_queue.py`、`workers/runtime.py`、`main.py` | `infrastructure/queue/adapter.py` | UUID Worker；身份/期限条件写回；回排/尝试耗尽/截止业务结算；独立readiness、DB退避与有界停机。六动作日志包含适用run_id或document_id；审查发现并纠正索引漏关联及旧断言跳过，严格真实PG复验。完整分类/两轮仍待。 |
| RM-04 Journal/SSE | `events/journal.py`、`redis_notifier.py`、`api/routes/runs.py` | `tests/api/test_execution_stream.py` | 领取与task.leased同事务；序号锁/回滚；握手前404、兼容Header游标、终态及空后缀EOF；断线不取消。真实历史/实时屏障与网络断线驱动已接入，诊断完整EVT/SSE通过，正式两轮待执行。 |
| RM-05 文档/RAG | `application/documents.py`、上传路由、`storage/local_files.py`、Parser、pgvector、真实Provider、两个handler | `application/vector_validation.py`、`rag/parser_process.py`、`0003_chunk_locations.py`；文档/协议/边界单测、`rag_pg_probe.py`、`test_rag_review_fixes.py`、文档测试conftest | 10MiB+1有界读取、安全basename与精确清理；永久/暂态错误区别；基础位置；事务外Embedding、候选/active/Task原子发布；真实流/协议校验和响应预算。multipart进入路由前总配额不是Parser保证。 |
| RM-06 前端 | `frontend/src/api/`、`events/`、`stores/`、`pages/`、`components/`、styles、Vite、package/lock | `api/health.ts`、`frontend/README.md`；扩展既有Workspace组件测试 | 临时回答不写Thread；最新attempt草稿独立；run/seq去重、终态GET与Journal后缀、刷新/重连、迟到请求隔离；文档有界刷新/健康/引用键盘。根Compose同源代理。诊断完整30浏览器/35组件通过；普通offline独立blocked，正式两轮仍待。 |
| RM-07 边界/契约 | handler/runtime适配、契约文档、前端依赖/类型、PRD/ADR栈说明 | `domain/ports/__init__.py`、`providers/factory.py`；Thread/Run/Health/API响应/Citation/Evidence Schema；`frontend/scripts/generate-api-types.mjs` | 纯DTO/非空协议；实际依赖注入；单页原生Vue、去未用Router；Schema生成类型、只读漂移检查。5d已实现Event payload联合并有53响应动态矩阵，最终独立批准/正式两轮仍待。 |
| RM-08 测试工程 | 总入口的head/凭据映射、`category-kit`、分类/工具README及测试工程 | `tests/demo-smoke/tooling/pg-*`、`worker-bootstrap.py`、`worker-controller.py`、`execution-focused.mjs`（5a已限定批准）；本记录及复测报告 | 真PG/双连接/屏障/真实main进程；逐TP绑定具体断言，Journal比较含payload hash；创建前登记辅助资源，finally精确关闭；禁止SQL伪造state/generation/seq。5b/5c与PAR窄修已批准，5d主入口硬杀兜底有阶段证据，完整门禁及正式两轮尚待，不提前称最终闭环完成。 |

模块导航见 [后端](../../backend/README.md)、[前端](../../frontend/README.md)、[契约](../../contracts/README.md)、[API测试](../../tests/api/README.md)、[集成测试](../../tests/integration/README.md) 和 [测试工具](../../tests/demo-smoke/tooling/README.md)。新增文件在对应模块说明登记职责；接口真源只维护 [接口文档](../接口文档.md) 和契约，README不复制完整接口表。

## 3. 回归中发现的问题及处理

| 问题 | 原因与处理 | 已有证据及未完成边界 |
| --- | --- | --- |
| RAG中期五项问题 | 空白兼容、双故障清理、Provider响应头预算、巨大整数分型、最终发布/Parser取消证据；恢复波逐项修复 | 后端126项、真实PG13专项与独立审查；原中断/RED保留，不外推正式all。 |
| 前端三项异步问题 | 不同attempt草稿拼接、旧cancel污染刷新版本、同Thread逆序提交切回旧Run；执行边界/epoch/提交序号分别保护 | 新4项先fail，最终35组件passed，独立限定复审批准；实际慢Worker浏览器仍待。 |
| Run最终flush跨期 | 最后lease检查后数据库等待跨期；保留原期限并在全部flush后commit前再检查 | assistant/terminal × lease/deadline四组合真实PG RED→GREEN，全部五表列和双游标回滚；授权检查线性化边界不承诺commit网络零耗时。 |
| 请求422回显输入 | FastAPI默认RequestValidationError含input/ctx；安全白名单投影、固定摘要、严格Schema和生成类型同步 | raw ASGI九变体先fail后10passed，后端136及35组件passed，独立审查批准；全状态矩阵/未知回退补测仍待5d。 |
| 索引日志漏业务关联/测试误判 | Runtime.log缺document_id，5a断言直接跳过index；先严格关联及raw哨兵RED，再最小加document_id | 持久两类Task格式RED2→27定向GREEN、真实PG六动作×两类26断言通过、独立窄审批准；5a修正分类复验和限定复审均批准。 |
| Journal观察及负哨兵清理缺口 | Event观察漏payload，初始控制器验证体无finally；补规范化hash/内存payload-only负哨兵/终态前提及正确身份finally | 真实重入及故意异常后实际容器不存在/登记closed通过，最新135资源快照，限定复审批准；不是总入口硬杀恢复证据。 |

具体原始证据、命令和资源身份见复测报告第8节；工作目录中的详细独立审查是阶段辅助，不替代交付报告。测试运行器输出脱敏不用于证明产品没有泄漏，安全断言直接检查原始响应/持久事实/日志。

## 4. 已运行的当前专项门禁

- `.venv/Scripts/python.exe -m pytest tests/unit tests/api tests/integration -q --tb=short`：最新422修复后136 passed，1条既有Starlette/httpx弃用warning，exit0。
- `npm run unit:frontend --prefix tests/demo-smoke`：最新35 passed；`generate:api`、`check:api`、`typecheck`通过。前端构建/ESLint阶段通过，保留1条DOMPurify后v-html提示，最终仍需全量门禁重新执行。
- Ruff/mypy阶段命令通过；真实PG迁移、执行与RAG分阶段专项有记录。它们使用当前源码只读挂载，不把旧API镜像当修复验收。
- 新执行工具正负哨兵、SIGTERM、崩溃恢复、实际SSE/快照等专项陆续验证；分类接入未结束，不提前更新正式卡片为通过。

## 5. 未完成、暂缓与退出条件

当前未完成：5d生命周期/全响应契约/最新性能/完整质量门禁及独立批准，整体代码审批、冻结后至少两轮all、149用例回填/104原问题闭环和最终资源审计。5a/5b/5c及PAR窄修已限定批准，不再属于未实施项；执行专项不是正式all验收。当前诊断环境暂存，最终必须精确CleanupRunId；不global prune。

历史续办节点：5b 实施及独立审查批准时，无 Critical/Important；81 个新增检查有当前通过引用（初次失败保留并定向复验，不冒充一次完整重跑），330 条共享辅助资源登记 closed。当时5c开始、5d未开始；这不是当前未实施状态。

2026-10-13 最新阶段：5c完成当前源码镜像的完整FE（66项65passed/1明确普通offline blocked，实际exit2、未超时），35组件及30浏览器完整集合无缺失，故意异常finally探针通过；FE015独立RunPanel覆盖缺口修正及限定复审也已批准。新增frontend控制器/合法Vite代理/真实TCP网关/资源登记/组件和浏览器完整集合工具，仅tests；主生产代码未因此变更。旧诊断专属卷/runtime/tmp已精确清理，原证据保留；新诊断仍暂存。5d已修旧browser集合helper并有文件锁/硬杀恢复阶段证据，但完整5d批准、整体审查及正式两轮仍待。

同次独立QLT完整20项中17passed/3failed：状态机独立预期表漏合法回收边、WK编号声明解析门禁、PAR fixture兼容。前两项测试侧修正待新目录复验；PAR旧驱动误将正确的EMPTY_DOCUMENT当作整个fixture生成失败，10项级联失败。新增`tooling/test_par_fixture_driver.py`与`par-driver.py`白名单修正保留真实docx字节及所有正常/异常预期；完整PAR复验20passed/原全区域blocked1，独立审查批准，原failed报告保留。详见复测报告第1节；不把这类测试工程缺陷归为生产Parser失败。

明确暂缓：OWN_001生产认证/双owner、PAR_004 docx全部区域、FE_009普通offline变体、真实外部模型效果/Key/生产SLO；受控socket、正文基础解析和本机能补的驱动仍必须验证，不能借暂缓统一跳过。

本记录与ADR均不因局部passed变为最终已实施。退出时必须有逐RM/PRD八条验收证据、全部纳入P0无失败、暂缓/未解决原因和定位、完整分类两轮与清理零残留；源码/fixture/契约变更后重新冻结起算两轮。最终再次整体校审术语、状态机、接口、路径、真实步骤和证据。
## 6. 正式两轮后实际交付（2026-10-13）

对应PRD001/ADR002，HEAD dabc45c82f076880403a7c19c296947609db92da，同一冻结278文件两轮`20261012t212827-13fa1d31`/`20261013t014325-e2009999`；真实child/summary一致、未超时，cleanup及独立观察/published审计均归零。完整21分类、各质量命令/实际依赖/3+20性能、每个RM与PRD八条验收、104原项逐check及149卡片见[复验报告§9](../../tests/demo-smoke/复测和验收报告.md)。受限没有改passed；实际无failed不代表严格all命令0。

全量修复波I1各Worker路径最后flush授权/I2根Compose四配置真实消费/M1重试成功历史错误/5b候选非空/N1证据JSON均已实施并限定批准，正式两轮重新实际执行；5d生命周期/契约/依赖/性能亦已批准并复验，不再列未修。根Compose同源已修，30浏览器/36组件为当前总集，原35保留。

### 6.2 明确暂缓、平台受限与必要后续

| RM/原用例 | 具体问题与定位 | 原因、影响及必要性 | 后续/用户动作 |
| --- | --- | --- | --- |
| Demo非目标 / OWN_001 | `specific_test_script/own-tests.mjs`的A/B列表、跨owner详情/归档/消息/Run/Event/cancel/index/retrieval/SSE共15子检查；当前后端配置固定OWNER_ID，未生产认证。 | 生产双owner认证/RBAC不属于本次修复范围；当前单开发owner不能作为生产隔离证据。P2范围限制，不判产品动态通过。 | 完整认证/多租户PRD确认后单独实施；本机测试不需要真实Key或额外授权。 |
| RM-05 / PAR_004全区域 | `backend/infrastructure/rag/parsers.py:parse_document`仅承诺正文段落基础位置；`par-tests.mjs`的full-region-support保留blocked。 | 表格、页眉、文本框等全部区域尚未被产品范围确认。正文及空/损坏文件仍纳入并实际测试。P2范围澄清，不能把正文passed外推全部区域。 | 用户确认docx区域需求后新PRD/ADR与fixture矩阵；本次不实现半成品入口。 |
| RM-06/08 / FE_009 ordinary-browser-offline | `specific_test_script/fe-tests.mjs`的ordinary-browser-offline；实际重连逻辑在`frontend/src/events/run-event-stream.ts`/run store，受控socket在`tooling/frontend-persistent.mjs`。 | 本机Chromium setOffline不能可靠使已建立空闲SSE触发error，无法命中前置。类型2环境受限；真socket断线及三片/游标/PG补放两轮仍纳入。P1验证条件，未执行变体不凑通过。 | 更换可观察网络故障环境后补该变体；当前无需用户提供凭据。 |
| RM-08 / LIFE_006平台Ctrl+C | `specific_test_script/life-tests.mjs`的`LIFE_006__TP-LIFE-005__capturable_interrupt`；Windows测试平台缺可靠可捕获Console Ctrl+C注入。 | 普通finally、子分类超时、父runner整树硬杀与独立恢复有实际证据，但硬杀不等价可捕获Ctrl+C。原卡片P0验证限制保持：blocked且未完整动态验收；不能声称所有P0全部动态通过。已实施仅限落地修复及本机可验证范围。 | 必须在可注入真实Console Ctrl+C环境补测finally及精确恢复，保留真实退出与资源事实；不关闭保护或裸PID杀进程。本机无该注入API时用户无需提供Key，另安排控制台环境补验。 |
| RM-05/08 / 真实模型效果、Key、生产SLO | `MockModelProvider`、`provider_protocol.py`本地服务、PERF本机单Worker20样本。 | Mock/本地协议仅证明流程、身份、错误及有限样本延迟；不能证明检索效果、供应商稳定性或生产容量。方案明确非目标。 | 完整Provider/评测/容量PRD单独定义，不要求用户现在提供真实Key。 |

既有前端DOMPurify后局部`vue/no-v-html`提示保留，ESLint要求0error且没有新增warning；不全局关闭规则。LF→CRLF及npm新版notice如实保留，不因此改全仓行尾/全局依赖。5d历史FE_014偶发健康失败未能单独确定产品根因，后续完整诊断及正式两轮需按实际新结果报告，不用旧passed覆盖原failed；原证据仍在历史§8。

### 6.3 等价替代路径和交付边界

方案可选生产`test_provider_server.py`由tests/demo-smoke/tooling/provider_protocol.py及worker-bootstrap/controller承担；生产只有Port/Adapter工厂，没有测试控制路由。方案可选`backend/workers/logging.py`由现有WorkerRuntime.log承担；Parser/Queue/Vector/Provider Port统一在backend/domain/ports/__init__.py，未新增第二套基础设施字段。方案可选独立reconnect/projection文件由现有run store及run-event-stream分层承担，页面只编排。真实业务数据由应用函数/正式HTTP创建，SQL仅观察；Fixture、协议替身与故障hook全部在tests。

本轮不stage/commit/push/reset，不改用户index；已有AGENTS、通用规范、当前任务说明和完整PRD重命名不是本轮实施成果。root README/CONTEXT/接口/ADR等重叠文件只归本轮明确段落职责，不声称整文件字节均由本轮产生。docs/test/001测试plan为既有ADR002验证边界差异，本Task6仅核对。正式结果回填/metadata在第二轮结束及最终冻结check成功之后发生；测试间版本一致由冻结文件hash证明，交付文档改变后不再假称全部hash仍等于被测基线。

### 6.1 完整实际新增/修改文件及用途

以各已批准任务限定包/实际报告的职责路径合并，HEAD差异仅核存在性；共201个任务实现/文档文件（98新增/103已有文件本轮职责）。用户AGENTS/通用规范/任务说明/完整PRD重命名排除；重叠README/CONTEXT/接口/ADR不归整个旧byte。docs/test/001测试plan已有ADR002边界差异，本Task6仅核对。Task6结果导航的原测试/缺陷报告新增导航另列，不回写正文。

| 实际文件 | 变更性质 | 用途/职责 |
| --- | --- | --- |
| `.env.example` | 修改（仅本轮职责） | 部署/配置/依赖与运行时安全边界 |
| `alembic.ini` | 修改（仅本轮职责） | 部署/配置/依赖与运行时安全边界 |
| `backend/api/routes/documents.py` | 修改（仅本轮职责） | 正式HTTP/SSE适配、安全错误与公开投影 |
| `backend/api/routes/health.py` | 修改（仅本轮职责） | 正式HTTP/SSE适配、安全错误与公开投影 |
| `backend/api/routes/runs.py` | 修改（仅本轮职责） | 正式HTTP/SSE适配、安全错误与公开投影 |
| `backend/api/schemas/documents.py` | 修改（仅本轮职责） | 正式HTTP/SSE适配、安全错误与公开投影 |
| `backend/api/schemas/threads.py` | 修改（仅本轮职责） | 正式HTTP/SSE适配、安全错误与公开投影 |
| `backend/app.py` | 修改（仅本轮职责） | 启动/配置/ORM映射 |
| `backend/application/documents.py` | 修改（仅本轮职责） | 持久事实、短事务及执行授权边界 |
| `backend/application/runs.py` | 修改（仅本轮职责） | 持久事实、短事务及执行授权边界 |
| `backend/application/task_execution.py` | 新增（任务包归属；非凭untracked推断） | 持久事实、短事务及执行授权边界 |
| `backend/application/threads.py` | 修改（仅本轮职责） | 持久事实、短事务及执行授权边界 |
| `backend/application/vector_validation.py` | 新增（任务包归属；非凭untracked推断） | 持久事实、短事务及执行授权边界 |
| `backend/config.py` | 修改（仅本轮职责） | 启动/配置/ORM映射 |
| `backend/db/models.py` | 修改（仅本轮职责） | 启动/配置/ORM映射 |
| `backend/domain/entities.py` | 修改（仅本轮职责） | 纯领域DTO/Port与状态规则 |
| `backend/domain/ports/__init__.py` | 新增（任务包归属；非凭untracked推断） | 纯领域DTO/Port与状态规则 |
| `backend/infrastructure/events/journal.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/events/redis_notifier.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/providers/factory.py` | 新增（任务包归属；非凭untracked推断） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/providers/mock.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/providers/openai_compatible.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/queue/adapter.py` | 新增（任务包归属；非凭untracked推断） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/queue/postgres_queue.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/rag/parser_process.py` | 新增（任务包归属；非凭untracked推断） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/rag/parsers.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/rag/pgvector_store.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/infrastructure/storage/local_files.py` | 修改（仅本轮职责） | 可替换Adapter、协议校验与资源边界 |
| `backend/README.md` | 新增（任务包归属；非凭untracked推断） | 启动/配置/ORM映射 |
| `backend/workers/handlers/index_handler.py` | 修改（仅本轮职责） | Worker执行、关停、日志及handler编排 |
| `backend/workers/handlers/run_handler.py` | 修改（仅本轮职责） | Worker执行、关停、日志及handler编排 |
| `backend/workers/main.py` | 修改（仅本轮职责） | Worker执行、关停、日志及handler编排 |
| `backend/workers/runtime.py` | 修改（仅本轮职责） | Worker执行、关停、日志及handler编排 |
| `CONTEXT.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `contracts/api_responses_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/citation_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/document_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/evidence_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/health_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/message_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/README.md` | 修改（仅本轮职责） | 版本化正式Schema及真源导航 |
| `contracts/run_event_v1.json` | 修改（仅本轮职责） | 版本化正式Schema及真源导航 |
| `contracts/run_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `contracts/thread_v1.json` | 新增（任务包归属；非凭untracked推断） | 版本化正式Schema及真源导航 |
| `docker-compose.yml` | 修改（仅本轮职责） | 部署/配置/依赖与运行时安全边界 |
| `docs/adr/001-sesrag-demo-implementation-plan.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/adr/002-SesRAG-Demo-缺陷修复-plan.md` | 新增（任务包归属；非凭untracked推断） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/pr/002-SesRAG-Demo-缺陷修复-PR.md` | 新增（任务包归属；非凭untracked推断） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/prd/001-SesRAG-项目Demo-PRD.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/runbooks/demo-development.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/runbooks/demo-smoke-environment.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `docs/接口文档.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `frontend/package-lock.json` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/package.json` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/README.md` | 新增（任务包归属；非凭untracked推断） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/scripts/generate-api-types.mjs` | 新增（任务包归属；非凭untracked推断） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/api/documents.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/api/health.ts` | 新增（任务包归属；非凭untracked推断） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/api/http.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/api/runs.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/api/threads.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/components/DocumentUploader.vue` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/components/MessageTimeline.vue` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/components/RunTimeline.vue` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/components/ThreadList.vue` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/events/run-event-stream.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/pages/WorkspacePage.vue` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/stores/documents.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/stores/run.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/stores/thread.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/styles.css` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/src/types/api.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/tsconfig.tsbuildinfo` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `frontend/vite.config.ts` | 修改（仅本轮职责） | 事实投影/契约生成/合法同源代理与工作台交互 |
| `migrations/env.py` | 修改（仅本轮职责） | 固定历史迁移、安全增量约束与位置兼容 |
| `migrations/versions/0001_initial_demo.py` | 修改（仅本轮职责） | 固定历史迁移、安全增量约束与位置兼容 |
| `migrations/versions/0002_demo_integrity.py` | 新增（任务包归属；非凭untracked推断） | 固定历史迁移、安全增量约束与位置兼容 |
| `migrations/versions/0003_chunk_locations.py` | 新增（任务包归属；非凭untracked推断） | 固定历史迁移、安全增量约束与位置兼容 |
| `pyproject.toml` | 修改（仅本轮职责） | 部署/配置/依赖与运行时安全边界 |
| `README.md` | 修改（仅本轮职责） | 本轮文档职责与证据导航（保留原有修改） |
| `tests/api/README.md` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/api/test_document_limits.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/api/test_execution_stream.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/api/test_foundation_health.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/api/test_foundation_public_fields.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/api/test_validation_safety.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/demo-smoke/compose/docker-compose.demo-smoke.yml` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/compose/run-migrations.py` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/lib/api-contracts.mjs` | 新增（任务包归属；非凭untracked推断） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/category-kit.mjs` | 修改（仅本轮职责） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/category-kit.test.mjs` | 修改（仅本轮职责） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/category-report-contract.mjs` | 修改（仅本轮职责） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/process-identity.mjs` | 新增（任务包归属；非凭untracked推断） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/quality-category-gate.mjs` | 新增（任务包归属；非凭untracked推断） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/lib/smoke-common.ps1` | 修改（仅本轮职责） | 测试公共协议/身份/报告/有界执行 |
| `tests/demo-smoke/README.md` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/requirements-tools.txt` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/run-demo-smoke.ps1` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/self-tests.ps1` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/specific_test_script/arc-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/can-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/chk-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/dep-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/doc-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/document-rag-coverage.mjs` | 新增（任务包归属；非凭untracked推断） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/evt-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/execution-coverage.mjs` | 新增（任务包归属；非凭untracked推断） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/fe-component-checks.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/fe-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/fe-workspace.test.ts` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/hlt-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/idx-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/life-budget.json` | 新增（任务包归属；非凭untracked推断） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/life-runner-driver.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/life-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/manifest.json` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/msg-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/par-driver.py` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/par-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/perf-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/qlt-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/rag-driver.py` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/rag-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/README.md` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/run-test-driver.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/run-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/sec-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/sse-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/specific_test_script/wk-tests.mjs` | 修改（仅本轮职责） | 21分类逐case/TP断言及完整必测集合 |
| `tests/demo-smoke/test-cases.md` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/test-plan.md` | 修改（仅本轮职责） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/demo-smoke/tooling/check-python-tools.py` | 修改（仅本轮职责） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/check-tools.mjs` | 修改（仅本轮职责） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/cleanup-registered.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/cleanup-registered.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/compose_rag_consumer.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/compose-rag-check.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/compose-rag-check.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/contract-focused.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/contracts.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/document-rag-focused.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/environment-evidence.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/execution-focused.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-bootstrap.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-checks.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-components.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-controller.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-focused.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-harness.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-lifecycle-probe.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-panel.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-persistent.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-resources.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/frontend-resources.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/harness-fixtures/deployment.json` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/harness-fixtures/hard-kill-recovery.json` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/harness-fixtures/life-hard-kill.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/harness-fixtures/README.md` | 修改（仅本轮职责） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/harness-overrides.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/http-contract-matrix.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/lifecycle-budget.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/lifecycle-focused.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/lint-frontend.mjs` | 修改（仅本轮职责） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/performance-events.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_contract_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_document_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_flush_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_harness.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_network_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_provider_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_queue_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_rag_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg_run_scenarios.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg-execution.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg-execution.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/pg-execution.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/provider_protocol.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/quality-category-gate.test.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/README.md` | 修改（仅本轮职责） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/test_contract_fallback.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/test_par_fixture_driver.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/test_provider_protocol.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/worker-bootstrap.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/worker-controller-probe.mjs` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/tooling/worker-controller.py` | 新增（任务包归属；非凭untracked推断） | 隔离真实驱动/工具门禁/生命周期证据，详见工具README |
| `tests/demo-smoke/复测和验收报告.md` | 新增（任务包归属；非凭untracked推断） | 隔离Compose总入口/用例追溯/故障与结果记录 |
| `tests/integration/conftest.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/execution_pg_probe.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/rag_pg_probe.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/README.md` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/test_document_boundaries.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/test_execution_integrity.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/test_lease_recovery.py` | 修改（仅本轮职责） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/test_provider_http.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/integration/test_rag_review_fixes.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/foundation_pg_probe.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/README.md` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/test_foundation_config.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/test_foundation_integrity.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/test_foundation_migrations.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |
| `tests/unit/test_rag_boundaries.py` | 新增（任务包归属；非凭untracked推断） | 单元/API/集成失败回归或显式真实PG探针 |

Task6另外修改`tests/demo-smoke/测试报告.md`、`缺陷报告.md`仅开头当前导航；正式结果/能力/预算/状态回填在末冻结check后，14文件真实before与限定diff保存于协调目录，不新增顶级生产目录。另新增`tests/demo-smoke/ADR002-正式验收关键证据.json`（第202个实际任务文件，99新增/103修改）用于随库保存278输入哈希、实际三轮关键事实和资源审计白名单；用途在测试README登记。新增协调观察/审计/补丁生成器及JSON是ignored本地交付辅助，未进入生产或正式manifest。未提交/推送/重置/更改index。

稳定比较为实际Round1与Round3；中间Round2宿主睡眠跨300秒nested截止，514passed/1failed/18blocked原结果及正式恢复保留，详见复验报告§9.1.1。它不计稳定验收轮且未覆盖原失败。metadata/结果回填后5个冻结文档变化，其余273输入相同；当前全部278同hash不再成立，末freeze成功时机在所有正式编辑之前。

