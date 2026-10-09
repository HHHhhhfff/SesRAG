# 分类测试接入约定

本目录已按用例前缀接入21分类入口，149用例均有明确归属；实际断言与尚未满足条件的子项分别记录，不能凭声明齐全宣称完整行为覆盖。脚本/辅助文件和对应的用例范围见[环境README](../README.md#分类脚本与用例映射)，试跑及未完成目标见[任务3～4记录](../任务3-4实施与审批记录.md)。不得提交空断言脚本改为enabled。

## 接入步骤

1. 根据[测试点矩阵](../测试点设计与需求覆盖矩阵.md)及[已设计用例](../test-cases.md)确定主测试点ID、数据子项和单一验证目标；用例中的待补条件须先准备，不能直接将缺口标通过。
2. 按manifest路径新增`.ps1`或`.mjs`，完成正常/异常输入、证据、退出码和清理自有客户端。
3. 生成满足[category-result.schema.json](category-result.schema.json)的JSON，验证真正失败能返回非零；不得把已知缺陷自动跳过后报passed。
4. 在[manifest.json](manifest.json)中将该项改为`enabled`，设置合理有界timeout_seconds，再通过总入口指定`-Category <name>`验证接入。
5. 正式验收选择all并检查所有必测分类完成。子集通过不等于全部PRD通过，summary会记录category_selection。

## 统一参数与进程边界

PowerShell使用同名param，Node从process.argv解析下列参数（拼写和大小写固定）：

```text
-BaseUrl <http://127.0.0.1:api-port>
-FrontendUrl <http://127.0.0.1:frontend-port>
-RunId <本次run_id>
-ArtifactDir <本次报告绝对目录>
-RuntimeDir <本次运行绝对目录>
-FixtureDir <本次tmp中生成的fixture目录>
```

`FixtureDir/upload-safe/`有txt/md及生成的smoke.docx，稳定源位于仓库fixtures；不得从宿主任意目录搜资料。大文件/损坏文档写到RuntimeDir同级的本次tmp/run_id内，不进Git，不留artifact原文。

总入口为每类创建独立子进程，超时/可捕获中断终止进程树。退出0且Schema合法、run_id/category一致、非空checks全部passed才通过。没有报告、错误报告、空checks的passed、子进程非零或超时均失败。未接入项由入口生成not_ready/空checks；分类可以记录blocked/skipped/not_ready，但这些不构成通过。

每类写`<ArtifactDir>/categories/<manifest.name>.json`，至少包含：schema_version=1、run_id、category、status、UTC started_at/finished_at、非空checks、evidence。每个check包含id（用例ID）、test_point_id、status、自然语言expected/actual、evidence路径数组；关联Thread/Run/Task/document/generation/seq可作为扩展字段。

联合/参数化用例使用`id=<用例ID>__<测试点ID>__<子项>`区分检查；`test_point_id`仍只填一个TP ID，不以一条笼统passed覆盖全部关联目标。子项的blocked/not_ready/failed不能被其他子项通过覆盖；当前运行器把不满足整体passed协议的enabled分类归为failed，分类原报告保留各子项的具体状态，不能把它误写成顶层自动返回blocked。

证据路径应相对ArtifactDir且不能逃逸，失败记录可复现输入摘要/状态码/关联日志；不得记录真实Key、数据库密码、完整Prompt或无必要原文。运行器会再次脱敏主报告和stdout，但分类自己的截图/附加文件必须自行脱敏。

## 不可越过的边界

- 业务操作经正式HTTP/SSE；必要容器内DB诊断只读，不改生产状态伪造结果。
- RuntimeDir/context.json可获取本次project和地址；compose.env含临时凭据，只供必要容器诊断，不打印/复制到报告。
- 禁止自行Compose down/global prune，禁止碰开发project、删除其他分类报告或改变主环境owner/project；环境销毁仅由总入口负责。DOC/RAG空库及LIFE运行器专项可通过固定HarnessScenario调用同一总入口创建独立新project，明确记录嵌套身份，异常时finally以CleanupRunId恢复；不得自行构造任意manifest/生产测试后门。
- 浏览器、SSE、HTTP客户端及其他自建进程须在分类finally关闭，禁止启动逃逸的后台服务；不得禁用浏览器CORS策略掩盖产品缺陷。
- 当前同源Vite代理为合法测试部署配置，但不代表根Compose跨域缺口已修复；慢Provider/双owner/事务屏障尚未完整准备。新增真实Settings/纯函数/短deadline驱动只解除其对应子项，不解除完整E2/O/E4条件。
- Node可import项目本目录安装的playwright；运行器设置`PLAYWRIGHT_BROWSERS_PATH=tests/demo-smoke/.cache/ms-playwright`，浏览器只下载到该项目目录。

总入口默认镜像构建、全新随机project、Mock且384维，开始前做真实DB和基础服务检查。这些仅是环境前提，不替代本目录后续产品断言。

## 任务3的分类和数据实施约定

当前已按DEP/HLT/TH/MSG/RUN/WK/CAN/DOC/PAR/CHK/IDX/RAG/EVT/SSE/FE/OWN/SEC/PERF/ARC/QLT/LIFE拆分，同类一入口。历史七大类只是环境实施时的占位路线，正式manifest已替换；联合用例仍按原主前缀归属，关联点逐项报告。doc-limit/rag-empty专属入口不在主manifest重复计数，结果由doc/rag关联。

QLT独立运行时若无本run FE报告，会以相同六参数调用真实FE入口；有界进程树超时适配器关闭其Chromium/Vitest后代，启动/超时异常必须失败。浏览器门禁另外校验Schema、run/category、重复ID和完整19项浏览器检查集合，不把组件/完整场景blocked混成浏览器passed。辅助FE结果在同run categories/fe.json、过程在evidence/qlt/standalone-fe.log及进程结果JSON；辅助执行不改变manifest选择范围。

FE_009的`fe-sse-transport.mjs`是限定本例Run/Origin的真实字节透传与socket断开工具，`fe-sse-transport-selftest.mjs`仅工具正负自检；不合成Event，不绕过浏览器CORS。普通离线前提与running完整分片条件仍独立blocked，受控断线不能替代它们。

Python/Node依赖及独立组件/Lint入口已准备，见[tooling](../tooling/README.md)。本目录`.test.ts`由fe-tests.mjs按Vitest配置调用并逐项生成分类报告，不能向manifest填写.ts。工具探针及LIFE故意错误报告哨兵在tooling，仅由明确harness自检调用，不进入正式产品manifest。

PowerShell分类初始化必须明确UTF-8：

```powershell
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Console]::OutputEncoding
```

运行器进程适配器统一UTF-8读stdout/stderr，向子进程传PYTHONIOENCODING=utf-8。每个用例日志用中文输出编号、阶段、输入安全摘要、预期/实际、关联ID及证据位置；注释标明涉及用例编号，不打印凭据或全部Prompt。

数据依据[数据策略](../fixtures/data-strategy.md)：无全局SQL种子/导入钩子，固定安全fixture已有；每用例自己准备业务ID，失败不影响后续用例。真实函数保存点用于避免大型任务污染，不能伪造state/seq/generation。HTTP恰10MiB和空库正式Run已提供独立环境；完整E2/O/E4及特定配置/故障驱动仍需后续实施，工具安装不解除这些限制。
