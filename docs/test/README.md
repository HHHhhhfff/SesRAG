# PRD 测试文档

本目录同时保存两类文档，但职责必须区分：

- `编号X-SesRAG-xxx-test-plan.md`：正式测试实施方案，规定测试环境、目录、脚本接口、实施路线、报告和资源清理闭环，不等同于测试结果。
- `编号X-SesRAG-xxx-test.md`：测试验收方案执行后的结果记录，记录实际环境、命令、测试矩阵、通过/失败/阻塞项和证据。

当前 Demo：

- 正式测试实施方案：[001-SesRAG-项目Demo-test-plan.md](001-SesRAG-项目Demo-test-plan.md)
- 历史验收结果记录：[001-SesRAG-项目Demo-test.md](001-SesRAG-项目Demo-test.md)
- 本机隔离环境实施和验证（非产品验收）：[001-SesRAG-Demo-临时测试环境验证记录.md](001-SesRAG-Demo-临时测试环境验证记录.md)

正式测试方案至少说明：对应 PRD/ADR、版本和日期、测试边界、环境与隔离方式、目录和文件职责、总入口脚本、分类脚本协议、报告格式、失败语义、清理策略和分阶段退出条件。结果记录至少说明：实际环境、执行命令、结果、失败或跳过项、复现方式和剩余风险。未运行的检查不得写成通过。

## 持久化会话与对话工作台（002）

- [正式测试实施方案](002-SesRAG-持久化会话与对话工作台-test-plan.md)：已建立独立目录 `tests/sesrag-persistent-session-workspace-test/`、本机Compose、总入口、工具/数据、报告和清理恢复流程；实际命令、结果和限制见[环境实施与验证记录](../../tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)。环境实施与产品用例验收分别判定。
- [测试点与需求覆盖矩阵](../../tests/sesrag-persistent-session-workspace-test/测试点设计与需求覆盖矩阵.md)：84点设计及104例已接入，同源两轮All均完成；点级原受限标记为设计历史。
- [测试用例](../../tests/sesrag-persistent-session-workspace-test/test-cases.md)：104例结果/复现/稳定性312字段已按真实两轮回填。
- [正式测试报告](../../tests/sesrag-persistent-session-workspace-test/测试报告.md)、[缺陷报告](../../tests/sesrag-persistent-session-workspace-test/缺陷报告.md)：两轮各104通过、0失败/受限/未运行/工程错误，清理通过；归档呈现等4项补充问题仍登记，不宣称PRD零差异。
- 文件职责、命令与保留资源见[套件README](../../tests/sesrag-persistent-session-workspace-test/README.md)。本轮独立验收，不维护上一轮`tests/demo-smoke/`，不将旧结果改写成本轮结果。
