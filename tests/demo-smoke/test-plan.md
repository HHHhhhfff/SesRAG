# Demo 分类测试接入与ADR002复验计划

ADR002正式复验已在同一278文件冻结基线上完成两个稳定轮all（实际Round1与Round3；中间Round2睡眠扰动失败及恢复另见报告§9.1.1）：`20261012t212827-13fa1d31`、`20261013t014325-e2009999`。各纳入检查及具体blocked、真实child/summary、质量/性能与资源边界见[复测和验收报告](复测和验收报告.md)§9；149卡片和104原问题逐项追溯。20261007原failed与专项失败全部保留，严格all非零不能被写成整体命令通过。

ADR002 Task5d已新增固定部署/文件锁/硬杀恢复驱动、同run完整QLT消费、HTTP与Event联合契约及3预热+20样本首执行事件测量。当前正式两轮及历史专项结果写在复验报告；历史20261007用例结果不回写。可捕获Ctrl+C因Windows缺注入机制仍blocked；OWN/普通offline/docx区域暂缓不因新工具自动解除。

ADR002 Task5c新增真实PG/Worker持久浏览器驱动，覆盖原9个FE受限目标；36组件逐标题消费（原35保留），旧19浏览器及两个FE010恢复目标保留。当前执行结果与历史两轮报告分开保存；ordinary-browser-offline按ADR继续blocked。完整集合、故障时精确停启、真实字节透传和资源登记边界见[5c工具](tooling/README.md#5c-真实持久浏览器驱动)。5d已将30浏览器/36组件完整集合及frontend-resources硬杀恢复纳入门禁；有驱动不等于已通过两轮验收。

**编号**：001

**版本**：v0.6（ADR002当前接入状态）

**日期**：2026-10-13（20261007原计划保留）

**状态**：20261007原方案/失败为历史；ADR002两轮已执行，当前范围限制与纳入目标见复验报告

**依据**：[正式测试方案](../../docs/test/001-SesRAG-项目Demo-test-plan.md)、[测试点矩阵](测试点设计与需求覆盖矩阵.md)、[测试用例](test-cases.md)、[分类协议](specific_test_script/README.md)

## 实施边界

已准备隔离Compose、总入口、临时fixture、manifest/报告Schema、报告及清理机制。后续文档任务交付149个中文用例/191个测试点；任务3按前缀接入21分类。`self-tests.ps1`仅验证运行器安全辅助机制，不是产品验收分类。当前脚本映射见[README](README.md#分类脚本与用例映射)，真实执行/未落实子项见[任务3～4记录](任务3-4实施与审批记录.md)。

2026-10-07任务1～任务2已补Python3.12项目环境及Node24.15+独立工具、工具配置/探针；无需全局数据库SQL种子，详见[数据策略](fixtures/data-strategy.md)。总入口真实闭环及六参数中文协议复核见[准备与审批记录](任务1-2准备与审批记录.md)。这些不是任务5正式产品验收，不回填用例实际结果。

## 接入顺序

| 阶段 | manifest名称/计划脚本 | 优先测试范围 | 接入前条件 | 退出条件 |
| --- | --- | --- | --- | --- |
| 1 | service-health / 00-service-health.ps1 | DEP/HLT及实际迁移约束、ready真实性 | E1环境就绪、只读DB诊断 | 独立用例/报告，不只重复入口基础健康检查 |
| 2 | thread-run-api / 10-thread-run-api.ps1 | TH/MSG/RUN/CAN，身份、快照、幂等、终态 | 明确当前代码差异，准备双owner隔离方式 | 正常/并发幂等失败能诊断，不以SQLite替代PG锁 |
| 3 | worker-lease-recovery / 20-worker-lease-recovery.ps1 | WK，lease、generation、重试、deadline、SIGTERM | 补可控慢任务/屏障、不同Worker身份；不伪造DB状态 | 完整接管/迟到拒绝/停机证据；已知缺口实际failed |
| 4 | document-rag / 30-document-rag.ps1 | DOC/PAR/CHK/IDX/RAG，三格式、active、引用 | 复用FixtureDir，需要时生成超限/损坏数据 | 错误和空证据区分，candidate不污染active |
| 5 | event-sse-recovery / 40-event-sse-recovery.ps1 | EVT/SSE，游标、补放、seq、断线 | 有界SSE客户端、E2可控追加时序 | 补放不缺失，terminal行为/权限可诊断 |
| 6 | frontend-workspace / 50-frontend-workspace.mjs | FE/SEC，浏览器恢复、投影、清洗 | 已安装Playwright/Chromium；按已设计用例编写脚本，补特定网络/交错控制 | 正常浏览器安全策略下的可复现结果和脱敏证据 |
| 7 | fault-safety / 60-fault-safety.ps1 | 故障、权限、敏感异常、文件安全 | 按需补本地Provider替身/哨兵，不接真实外部Key | 失败退出码及finally关闭自有客户端 |

优先P0再P1/P2；同目标由一个分类负责，其他分类复用证据。功能点、自动化门禁点和执行闭环点不混计产品覆盖。

上表保留历史大类路线，任务3已按21前缀拆分，正式manifest与README为实际名称/路径/超时真源。Node入口输出Schema报告，组件.test.ts由fe入口逐项调用；未满足的完整子项保留blocked，不能用ID声明数量替代实际断言覆盖。

## 每类完成后的校审

- 根据已设计用例实施参数化子项，每个关联测试点独立断言和报告；实际结果按执行证据登记，不能只写模块名称或把本设计当执行结果。
- 为实现缺口与环境不足分别记failed/blocked，禁止因“暂未实现”删减需求。
- 运行指定分类，核对manifest/JSON Schema/退出码/子进程结束/资源清理；再改enabled。
- 接入全部必测项后运行all，对照PRD8条验收和测试点第5节覆盖矩阵；目前`not_ready`不代表产品已验收。
- 历史阶段E2/E4完整驱动未备；ADR002 Task5a/b/c已补真实慢Provider/事务/HTTP协议和浏览器交错，当前逐项结果按本run证据核验；双owner等ADR暂缓仍独立保留。

## 当前执行与后续补齐

2026-10-12 ADR002 Task5a补齐会话/Worker/取消/Journal/SSE驱动：每例唯一PG库、生产应用/Queue/Runtime推进、事务和Port屏障、只读独立观察连接、Linux main实际SIGTERM/SIGKILL、真实socket SSE、真实httpx冻结模型请求。创建前登记辅助容器至`execution-resources.json`，分类finally关闭，临时库随本project卷由总入口销毁；5d负责总入口硬杀兜底及WK分类超时预算。新增专项命令使用`tooling/execution-focused.mjs`和独立artifact子目录，不替代正式分类及all。所有原blocked子目标的最新实现/结果以`execution-coverage.mjs`及本次分类JSON为准，历史两轮报告不回写。任意吞取消协程/同步线程无法强杀的限制单列；实际生产httpx与psycopg取消需使用Linux main专项证据。

当前主入口按dep→hlt→th→msg→run→wk→can→doc→par→chk→idx→rag→evt→sse→fe→own→sec→perf→arc→qlt→life调度，前一分类失败不阻断后类。LIFE的协议哨兵不能进入正式产品manifest；固定HarnessScenario从tooling/harness-fixtures读取，所有嵌套身份持久登记至父runtime，子分类finally和总入口清理阶段均按身份精确恢复。

实施步骤及校审追踪见[任务3～4实施计划](任务3-4实施计划.md)。任务5已经在同一冻结基线执行两轮all，149实际结果和104复现/稳定性已填写；45暂不可完整动态只填实际结果，90字段按要求保持空，不机械凑447项。任务6见[测试报告](测试报告.md)、[缺陷报告](缺陷报告.md)和[审批记录](任务5-6执行与审批记录.md)。上述是20261007历史后续顺序；ADR002已完成驱动/修复与正式两轮，原设计目标、流程和预期保持。
## ADR002 Task5b 增量驱动接入说明

DOC/PAR/CHK/IDX/RAG/SEC/ARC的历史E2/E4缺口现由`tooling/pg_document_scenarios.py`、`pg_rag_scenarios.py`、`pg_provider_scenarios.py`和`provider_protocol.py`提供真实PG/Runtime/HTTP条件，分类通过`document-rag-coverage.mjs`逐case/TP/fixture执行；脚本存在不等于验收通过。正式结果仍须读取本run报告，不改写原两轮记录。

执行前须完成工具5项token/原始哨兵/未知端点/真实socket清理检查。每场景独立数据库，容器创建前登记，源码ro挂载；finally准确标签清理，硬杀恢复归总入口5d。HTTP状态、畸形结构、三片未结束HTTP流的Journal持久边界各有独立检查。超时fixture缩短的是测试进程Provider预算，不能作为60秒生产预算/SLO证据。当前专项和未运行完整分类的区别须在交付报告明确；原ADR暂缓的docx区域、双owner、普通offline不被本次覆盖替代。
