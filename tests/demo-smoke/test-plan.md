# Demo 分类测试后续接入计划

**编号**：001

**版本**：v0.5

**日期**：2026-10-07

**状态**：环境/分类及任务5两轮all已执行，任务6结果已整理；产品验收不通过，受限子项待补

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
- E2完整慢Provider/事务屏障、E4协议服务、双owner环境尚未实施；真实纯函数、短deadline生产函数、queued停Worker、空库/大小独立新库仅解除对应子项。

## 当前执行与后续补齐

当前主入口按dep→hlt→th→msg→run→wk→can→doc→par→chk→idx→rag→evt→sse→fe→own→sec→perf→arc→qlt→life调度，前一分类失败不阻断后类。LIFE的协议哨兵不能进入正式产品manifest；固定HarnessScenario从tooling/harness-fixtures读取，所有嵌套身份持久登记至父runtime，子分类finally和总入口清理阶段均按身份精确恢复。

实施步骤及校审追踪见[任务3～4实施计划](任务3-4实施计划.md)。任务5已经在同一冻结基线执行两轮all，149实际结果和104复现/稳定性已填写；45暂不可完整动态只填实际结果，90字段按要求保持空，不机械凑447项。任务6见[测试报告](测试报告.md)、[缺陷报告](缺陷报告.md)和[审批记录](任务5-6执行与审批记录.md)。下一阶段先修已证实问题、补受限时序/协议/身份/故障驱动，再重新冻结并完整两轮验收。此次不修产品、不降低预期，原设计目标保留。
