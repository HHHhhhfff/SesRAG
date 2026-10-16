# 分类测试接入约定

ADR002正式复验已在同一278文件冻结基线上完成两个稳定轮all（实际Round1与Round3；中间Round2睡眠扰动失败及恢复另见报告§9.1.1）：`20261012t212827-13fa1d31`、`20261013t014325-e2009999`。各纳入检查及具体blocked、真实child/summary、质量/性能与资源边界见[复测和验收报告](../复测和验收报告.md)§9；149卡片和104原问题逐项追溯。20261007原failed与专项失败全部保留，严格all非零不能被写成整体命令通过。

全量审查窄修：`execution-coverage.mjs`新增末flush queue/failure/events，正式RUN/WK/EVT与QLT必测集合共用ID；`dep-tests.mjs`与`qlt-tests.mjs`执行根Compose四配置及实际容器消费。`fe-component-checks.mjs`和`fe-workspace.test.ts`新增成功重试历史错误检查，原35项均保留，当前36项由真实Vitest标题逐一采集，QLT完整集合随之消费。测试细节与有界预算见[工具README](../tooling/README.md)。

本目录已按用例前缀接入21分类入口，149用例均有明确归属；实际断言与尚未满足条件的子项分别记录，不能凭声明齐全宣称完整行为覆盖。脚本/辅助文件和对应的用例范围见[环境README](../README.md#分类脚本与用例映射)，试跑及未完成目标见[任务3～4记录](../任务3-4实施与审批记录.md)。不得提交空断言脚本改为enabled。

ADR002 Task5a的`execution-coverage.mjs`在msg/run/wk/can/evt/sse/hlt尾部接入原受限子目标：真实PG竞争/回滚、Runtime重试/取消、Linux生产main信号、实际HTTP/SSE、readiness和日志。一次场景可给多个TP提供各自独立断言及原始证据；不复制统一passed。驱动及持续Worker控制接口见[tooling README](../tooling/README.md#5a-真实执行驱动)。旧“未准备驱动”文字保留为历史说明，以当前每个check实际执行结果为准；5a专项不是正式两轮all。

MSG001/MSG003通过`run-test-driver.mjs::assertMessageSource`严格比较正式响应/PG的user_input和assistant_generation及同Message创建时间；公开/PG任一来源仅复制role均失败。控制器真实API/PG探针也消费相同断言并含这两种负哨兵，正式MSG保留独立来源check。

ADR002 Task5b的`document-rag-coverage.mjs`接入DOC/PAR/CHK/IDX/RAG/SEC/ARC的文档commit/写故障、候选发布、pg_stat_activity、正式配置与真实HTTP/SSE协议检查。每个HTTP状态/畸形输入单独check，预期为手定稳定错误分类；不由一个正常断言覆盖未运行矩阵。相同case可共享一次真实场景证据，不同case重新准备数据库和身份。工具及启动/清理边界见[5b工具](../tooling/README.md#5b-文档与真实http协议驱动)。`document-rag-focused.mjs`仅新增检查专项，不替代正常分类或正式两轮all。

`par-driver.py`生成真实docx字节并调用生产Parser；仅`empty_docx`/`table_only`接受明确的`EMPTY_DOCUMENT`，输出`parse_status=expected_empty_error`、错误码和Parser来源，仍保留原字节供正式HTTP上传。正常fixture及其他错误继续失败，不把空错误伪装为成功ParsedDocument。`../tooling/test_par_fixture_driver.py`运行真实driver验证字节保留、正常解析、异常不被吞和成功/异常时临时目录收束；不进入产品manifest。完整PAR仍保留全区域支持独立blocked。

## 接入步骤

Task5d：DEP003/009使用固定nested migration-failure/redis-cold，LIFE接配置/DB/ready/文件锁/父runner硬杀恢复；QLT缺同run报告时执行正式分类，完整集合含30browser+36component与5a/5b每个必测ID。PERF002已提供真实订阅屏障和UTC误差区间。所有新增驱动用途与精确清理见[5d工具说明](../tooling/README.md#5d-生命周期契约与性能)，未执行的结果不得改passed。

`life-budget.json`为LIFE实际driver读取的有限时间预算，含普通300、特殊nested-recovery420、恢复240等分项与15000秒分类总限；工具`lifecycle-budget.test.mjs`校核加总和正式manifest下界。`cleanup-share-read`补原None锁的共享读拒删除路径，两者均要求失败4、胶囊/恢复材料完整、正式CleanupRunId3及胶囊/资源零残留。

ADR002 Task5c已将FE原9个持久化受限目标接入真实PG/Worker/当前源码浏览器；原17组件不删除，Task4新增18项按中文标题逐项映射，共35。正常浏览器19目标及两个FE010恢复目标全部保留；两个旧queued断线目标改为真实running首片/真socket/后片PG补放，删除历史空replay篡改。完整浏览器集合30项与组件36项（5c原35为历史）导出见`../tooling/frontend-checks.mjs`；QLT须消费完整集合，不能只验旧19。原ordinary-browser-offline仍独立blocked；其余结果依本次证据，不沿用历史报告。资源登记与工具边界详见[5c驱动说明](../tooling/README.md#5c-真实持久浏览器驱动)。

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
- 根Compose与隔离覆盖均通过合法同源Vite代理统一HTTP/SSE/健康；真实慢Provider、PG事务屏障、本地HTTP协议和持久浏览器驱动已接入。双owner仍按ADR非目标暂缓；具体可验证性以本轮check为准。
- Node可import项目本目录安装的playwright；运行器设置`PLAYWRIGHT_BROWSERS_PATH=tests/demo-smoke/.cache/ms-playwright`，浏览器只下载到该项目目录。

总入口默认镜像构建、全新随机project、Mock且384维，开始前做真实DB和基础服务检查。这些仅是环境前提，不替代本目录后续产品断言。

## 任务3的分类和数据实施约定

当前已按DEP/HLT/TH/MSG/RUN/WK/CAN/DOC/PAR/CHK/IDX/RAG/EVT/SSE/FE/OWN/SEC/PERF/ARC/QLT/LIFE拆分，同类一入口。历史七大类只是环境实施时的占位路线，正式manifest已替换；联合用例仍按原主前缀归属，关联点逐项报告。doc-limit/rag-empty专属入口不在主manifest重复计数，结果由doc/rag关联。

QLT独立运行时若无本run报告，会以相同六参数调用对应正式分类；有界进程树适配器关闭其后代，启动/超时异常必须失败。FE门禁按`frontend-checks.mjs`显式验证30项浏览器和36项组件完整集合，其他回归按5a/5b逐ID消费，另核149用例真源防部分分类冒充完整。辅助结果在同run categories/、过程在evidence/qlt/standalone-*.log及真实进程结果JSON；辅助执行不改变manifest选择范围，不消费历史专项拼接结果。

FE_009的`fe-sse-transport.mjs`是限定本例Run/Origin的真实字节透传与socket断开工具，`fe-sse-transport-selftest.mjs`仅工具正负自检；不合成Event，不绕过浏览器CORS。running完整分片现在由5c真实Worker/PG驱动断言；普通离线前提继续独立blocked，受控断线不能替代它。

Python/Node依赖及独立组件/Lint入口已准备，见[tooling](../tooling/README.md)。本目录`.test.ts`由fe-tests.mjs按Vitest配置调用并逐项生成分类报告，不能向manifest填写.ts。工具探针及LIFE故意错误报告哨兵在tooling，仅由明确harness自检调用，不进入正式产品manifest。

PowerShell分类初始化必须明确UTF-8：

```powershell
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Console]::OutputEncoding
```

运行器进程适配器统一UTF-8读stdout/stderr，向子进程传PYTHONIOENCODING=utf-8。每个用例日志用中文输出编号、阶段、输入安全摘要、预期/实际、关联ID及证据位置；注释标明涉及用例编号，不打印凭据或全部Prompt。

数据依据[数据策略](../fixtures/data-strategy.md)：无全局SQL种子/导入钩子，固定安全fixture已有；每用例自己准备业务ID，失败不影响后续用例。真实函数保存点用于避免大型任务污染，不能伪造state/seq/generation。HTTP恰10MiB和空库正式Run已提供独立环境；E2/E4及特定配置/故障驱动已实际接入并两轮复验；O条件按ADR暂缓，工具安装本身仍不构成行为证据。
