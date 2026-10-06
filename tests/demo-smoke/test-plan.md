# Demo 分类测试后续接入计划

**编号**：001

**版本**：v0.1

**日期**：2026-10-06

**状态**：环境基础设施实施；产品分类脚本和具体用例待后续独立任务

**依据**：[正式测试方案](../../docs/test/001-SesRAG-项目Demo-test-plan.md)、[测试点矩阵](测试点设计与需求覆盖矩阵.md)、[分类协议](specific_test_script/README.md)

## 实施边界

已准备隔离Compose、总入口、临时fixture、版本化manifest/分类报告Schema、报告及清理机制。此次不准备测试用例或产品分类断言。`self-tests.ps1`只验证运行器安全辅助机制，不是产品验收分类，不进入manifest。

## 接入顺序

| 阶段 | manifest名称/计划脚本 | 优先测试范围 | 接入前条件 | 退出条件 |
| --- | --- | --- | --- | --- |
| 1 | service-health / 00-service-health.ps1 | DEP/HLT及实际迁移约束、ready真实性 | E1环境就绪、只读DB诊断 | 独立用例/报告，不只重复入口基础健康检查 |
| 2 | thread-run-api / 10-thread-run-api.ps1 | TH/MSG/RUN/CAN，身份、快照、幂等、终态 | 明确当前代码差异，准备双owner隔离方式 | 正常/并发幂等失败能诊断，不以SQLite替代PG锁 |
| 3 | worker-lease-recovery / 20-worker-lease-recovery.ps1 | WK，lease、generation、重试、deadline、SIGTERM | 补可控慢任务/屏障、不同Worker身份；不伪造DB状态 | 完整接管/迟到拒绝/停机证据；已知缺口实际failed |
| 4 | document-rag / 30-document-rag.ps1 | DOC/PAR/CHK/IDX/RAG，三格式、active、引用 | 复用FixtureDir，需要时生成超限/损坏数据 | 错误和空证据区分，candidate不污染active |
| 5 | event-sse-recovery / 40-event-sse-recovery.ps1 | EVT/SSE，游标、补放、seq、断线 | 有界SSE客户端、E2可控追加时序 | 补放不缺失，terminal行为/权限可诊断 |
| 6 | frontend-workspace / 50-frontend-workspace.mjs | FE/SEC，浏览器恢复、投影、清洗 | 已安装Playwright/Chromium；补产品用例、网络控制 | 正常浏览器安全策略下的可复现结果和脱敏证据 |
| 7 | fault-safety / 60-fault-safety.ps1 | 故障、权限、敏感异常、文件安全 | 按需补本地Provider替身/哨兵，不接真实外部Key | 失败退出码及finally关闭自有客户端 |

优先P0再P1/P2；同目标由一个分类负责，其他分类复用证据。功能点、自动化门禁点和执行闭环点不混计产品覆盖。

## 每类完成后的校审

- 对照测试点编写原子用例，给出预期/实际/证据，不能只写模块名称。
- 为实现缺口与环境不足分别记failed/blocked，禁止因“暂未实现”删减需求。
- 运行指定分类，核对manifest/JSON Schema/退出码/子进程结束/资源清理；再改enabled。
- 接入全部必测项后运行all，对照PRD8条验收和测试点第5节覆盖矩阵；目前`not_ready`不代表产品已验收。
- E2慢Provider/步骤屏障、E4协议服务、双owner环境本轮未实施，后续先明确隔离/退出/报告策略再接入。
