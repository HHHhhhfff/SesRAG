# Demo 本机隔离临时测试环境

本目录实施[TEST-001](../../docs/test/001-SesRAG-项目Demo-test-plan.md)的环境基础设施及后续分类脚本。已接入21分类，涉及149用例，部分完整故障/并发条件仍逐项blocked。部署→分类执行→报告→销毁→残留检查由总入口负责。任务5两轮正式all已完成：产品验收failed、资源清理passed；见[测试报告](测试报告.md)、[缺陷报告](缺陷报告.md)、[执行与审批记录](任务5-6执行与审批记录.md)。历史试跑/脚本校审见[任务3～4记录](任务3-4实施与审批记录.md)。

## 前提与运行

需要PowerShell **7.4+**（用`pwsh`，不使用Windows PowerShell 5.1）、Docker Desktop Linux Engine及支持`!override`的Compose **2.24.4+**。初次构建需能下载Python/Node依赖；默认Mock无外部Key。新准备的完整宿主测试工具要求Node **24.15+的24.x或26+**（不支持25）；Python工具用根目录`.venv`中的 **3.12**，不使用系统默认3.11。产品frontend容器仍Node20，未升级产品依赖。

从仓库根目录执行：

```powershell
pwsh -NoProfile -File tests/demo-smoke/self-tests.ps1
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1
# 手工检查：显示本次地址，就绪后等待输入；按Enter报告并自动销毁。
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Interactive
```

总入口在任意当前目录调用都能定位仓库；输出实际API/frontend地址、run_id和报告位置。默认不长期保留环境。正式验收不可启用KeepContainers；失败、blocked子项或未执行目标不能改写为通过。

| 参数 | 默认 | 作用/安全边界 |
| --- | --- | --- |
| ProjectName | sesrag-demo-smoke | project前缀，可加安全小写后缀；入口总会追加本次随机ID，拒绝接管已有资源。与方案建议的完整名称覆盖不同，此约束保证隔离。 |
| ApiPort / FrontendPort | 18000 / 15173 | 首选端口；占用或重复自动替换，只绑定127.0.0.1。 |
| Build | true | 默认构建本次镜像；false必须显式传BackendImage和FrontendImage，均为已有本地镜像，不自动复用开发镜像。复用不保证代码最新，只用于诊断。 |
| Category | all | 所有manifest项或一个名称；子集通过不等于完整PRD通过。 |
| HarnessScenario | 无 | 仅限固定子场景not-ready、disabled、protocol、missing-script、nested-recovery、rag-empty、doc-limit。前五为LIFE运行器自检，后两为RAG空库/DOC大小边界，不是另一套正式all验收；不接受任意manifest路径。复用主run本次镜像、创建独立project并交总入口销毁。 |
| WaitTimeoutSeconds | 180 | up和健康等待共享总限时，不含构建。 |
| BuildTimeoutSeconds | 900 | 独立构建限时，首次网络安装可能较慢。 |
| SessionSeconds | 0 | 就绪后有界暂停供外部检查，不执行产品断言。 |
| Interactive | false | 就绪后等Enter；硬杀进程需恢复清理。 |
| KeepArtifacts | true | 默认保留报告；显式`-KeepArtifacts:$false`表示接受删除本次报告，清理失败时仍保留。 |
| KeepContainers | false | 仅诊断保留，返回cleanup_deferred/5，保留runtime/tmp，必须后续CleanupRunId。 |
| CleanupRunId | 无 | 用本次runtime标记精确恢复清理；原summary先另存，不重新启动。 |

可复制`compose/.env.demo-smoke.example`为`.env.demo-smoke.local`修改4个整数选项；命令行参数优先。不读取根.env作为测试配置。

| 配置/运行变量 | 必填与默认 | 用途 |
| --- | --- | --- |
| SMOKE_API_PORT / SMOKE_FRONTEND_PORT | 模板可选，18000/15173 | 首选端口，最终值写runtime；按输出地址访问。 |
| SMOKE_WAIT_TIMEOUT_SECONDS | 模板可选，180 | 启动/健康总等待秒数，10～3600。 |
| SMOKE_BUILD_TIMEOUT_SECONDS | 模板可选，900 | 构建秒数，30～7200。 |
| SMOKE_PROJECT | 运行必需，入口生成 | 唯一project及本次镜像前缀，不指向开发project。 |
| SMOKE_OWNER_ID | 运行必需，入口生成 | 本次独立owner，不是生产认证。 |
| SMOKE_DB_PASSWORD | 运行必需，入口随机生成 | 临时DB密码，仅runtime/compose.env保存，不提交Git、不写默认报告。 |
| VITE_API_BASE_URL | 覆盖固定为空 | 已有Vite代理统一HTTP/SSE来源；不关闭CORS、不修复根Compose跨域问题。 |
| WORKER_ID | 覆盖由project生成 | 单测试Worker唯一身份；多Worker分类需另准备不同ID。 |

MOCK_PROVIDER=true、默认384维、AUTO_CREATE_SCHEMA=false固定；api/worker/migrate共用后端镜像。migrate只读挂载`run-migrations.py`，将DATABASE_URL注入既有Alembic配置；原迁移入口忽略环境变量的产品缺口仍保留。

## 文件与使用阶段

| 文件/目录 | 职责 | 阶段 |
| --- | --- | --- |
| run-demo-smoke.ps1 | 唯一生命周期入口、调度和报告/清理 | 每次运行 |
| lib/smoke-common.ps1 | 路径安全、脱敏、有界子进程、端口及fixture准备 | 预检/执行/清理 |
| self-tests.ps1 | 运行器辅助机制自检，不是产品分类 | 改运行器后 |
| tooling/ | 工具探针、覆盖校核及固定harness自检输入；探针不进入正式manifest | 安装/校审/运行器专项 |
| lib/category-kit.mjs / category-kit.test.mjs | 六参数客户端、限定project诊断、只读PG、中文逐项报告/证据、嵌套总入口恢复及自检 | 分类执行/改工具后 |
| lib/category-report-contract.mjs | 验证分类Schema/身份/重复ID及完整浏览器检查集合；局部报告不可当完整门禁通过 | QLT_007报告校验 |
| requirements-tools.txt | Windows/Python3.12工具环境完整版本快照；根.venv安装，非应用镜像新依赖锁 | 工具准备/重装 |
| eslint.config.mjs / vitest.config.mjs | 独立ESLint及真实前端组件测试工具配置，产品用例为空仍非零 | 任务3编写门禁/组件脚本 |
| compose/docker-compose.demo-smoke.yml | 根Compose上的端口/owner/密码/image/log覆盖 | 部署 |
| compose/.env.demo-smoke.example | 非Secret配置模板 | 配置前 |
| compose/run-migrations.py | 测试Alembic启动适配，不替换迁移 | migrate |
| specific_test_script/ | 21分类入口、按类别驱动、manifest、报告Schema和接入协议；详见下表 | 接入/执行 |
| tooling/check-coverage.mjs | 声明与报告逐用例/TP校核，单列无断言及未完成子项，不把blocked算覆盖完成 | 校审/试跑后 |
| tooling/lint-frontend.mjs | 固定仓库根执行真实前端源码ESLint，防止npm改变cwd导致全部忽略；TS未定义标识由独立vue-tsc门禁校验 | QLT_007/Lint |
| tooling/render-summary.mjs | 根据本次分类JSON生成中文逐分类/用例摘要；不填正式验收结果、不声明稳定性 | 总入口报告阶段 |
| tooling/harness-fixtures/ | 固定LIFE协议故障自检及DOC/RAG独立环境薄入口；不是伪产品测试 | LIFE/独立边界场景 |
| test-plan.md | 分类实施次序、前提及退出条件 | 分类脚本接入前 |
| test-cases.md | 中文用例、前置条件、逐测试点覆盖和两轮实际结果；有记录不等于完整执行 | 分类脚本设计/结果追溯 |
| 测试报告.md | 两轮正式all、分类/用例统计、PRD验收、质量/性能及清理结论 | 任务5～6结果交付 |
| 缺陷报告.md | 失败并集及暂不可/局部受限逐用例定位、原因/影响/建议与真实复现入口 | 缺陷处理/补测依据 |
| 任务5-6执行与审批记录.md | 冻结基线、执行命令、证据及最终校审记录 | 执行审计 |
| fixtures/ | 文本、docx XML源、事件期望；运行时生成docx | 数据准备 |
| fixtures/data-strategy.md | 当前不需要统一SQL种子的依据、各用例独立API创建数据及后续边界 | 任务1/任务3数据设计 |
| package.json / package-lock.json | 独立Playwright/Ajv/ESLint/Vitest等精确依赖与工具命令 | 工具安装 |
| runtime/<run_id>/ | context.json/compose.env/resources.json，含临时凭据 | 运行中，正常结束删除 |
| tmp/<run_id>/ | 生成fixture/后续大文件 | 运行中，正常结束删除 |
| artifacts/<run_id>/ | summary/cleanup/manifest、分类JSON、编排/健康/服务日志 | 默认保留脱敏证据 |
| .cache/ / node_modules/ | 项目内浏览器和npm工具缓存，不是每次运行数据 | 长期复用 |
| 测试点设计与需求覆盖矩阵.md | 原子目标/覆盖，可测状态为设计基线 | 用例设计/校审 |

运行目录、依赖、缓存和本地配置由.gitignore/.dockerignore排除；报告不发送到构建上下文。fixture和分类规范见子目录README；实际记录见[环境验证记录](../../docs/test/001-SesRAG-Demo-临时测试环境验证记录.md)。

产品测试设计和真实结果见[测试用例](test-cases.md)，与[测试点矩阵](测试点设计与需求覆盖矩阵.md)逐项关联。旧文档的“尚无产品脚本”为历史设计状态；当前脚本不改变正确预期。任务5按两轮证据填写149实际结果、104复现/稳定性；45暂不可完整动态只填原因和局部证据，后两栏空。慢任务/事务屏障、双owner和本地Provider协议替身仍待补，其中39用例至少一轮实际失败，不能据记录齐全宣布全面通过。

正式证据为`artifacts/20261007t072506-2fc5b075`和`artifacts/20261007t075158-2907bbdf`；第二轮另存`frozen-baseline.json`（164文件基线）、`two-round-comparison.json`（逐检查差异）、`final-resource-audit.json`（本轮主/子资源只读审计）、`document-result-validation.json`（149字段/191点/104问题条目/846检查Schema及证据链接的交付校核）。JSON/中文日志是原始依据，报告只给安全摘要；artifacts默认Git忽略，提交文档不会自动携带证据，需保留本机目录或另行脱敏归档。

## 分类脚本与用例映射

所有入口在`specific_test_script/`；正式名称为下表第一列，可用`-Category doc`等单独执行。每类用例独立准备业务身份，组合目标拆为`用例ID__TP-ID__子项`；同一用例的准备可复用，其他用例不依赖前例passed。前一断言失败继续后项；环境前置失败单独记录，不用SQL修改事实来制造结果。

| 分类 / 入口 | 用例 | 主要职责 |
| --- | --- | --- |
| dep / dep-tests.mjs | DEP_001～009 | 六服务/迁移/共享卷/配置与实际PG约束 |
| hlt / hlt-tests.mjs | HLT_001～005 | PG/Redis真实故障、健康真实性和重启持久恢复 |
| th / th-tests.mjs | TH_001～004 | 会话创建/排序/详情/归档 |
| msg / msg-tests.mjs | MSG_001～008 | Message字段/seq/幂等/普通并发及assistant事实 |
| run / run-tests.mjs | RUN_001～007 | 创建原子事实/快照/状态/成功事务 |
| wk / wk-tests.mjs | WK_001～025 | 实际PG正常claim/短deadline/退避/重启/DB故障/日志；完整E2子项保留blocked |
| can / can-tests.mjs | CAN_001～006 | queued取消、终态幂等、取消错误；步骤/最终提交竞态待补 |
| doc / doc-tests.mjs | DOC_001～011 | 文档元数据、格式/MIME/大小/hash/路径、索引请求和重建 |
| par / par-tests.mjs | PAR_001～004 | 三格式真实解析、编码/损坏/空文/docx非段落区域 |
| chk / chk-tests.mjs | CHK_001～002 | 字符/Unicode切分/offset/overlap及非法参数 |
| idx / idx-tests.mjs | IDX_001～007 | 真实索引/向量/源丢失、配置边界、active/事务受限子项 |
| rag / rag-tests.mjs | RAG_001～008 | PG Top-K/余弦、空库正式Run、非空回答/delta/引用、Provider配置；E4协议待补 |
| evt / evt-tests.mjs | EVT_001～005 | envelope/seq/游标/重启/实际事件类型 |
| sse / sse-tests.mjs | SSE_001～005 | 真实HTTP SSE/游标优先级/断线/EOF/缺对象语义 |
| fe / fe-tests.mjs | FE_001～015 | Playwright页面及真实Workspace/store组件投影/恢复/重连/隔离 |
| own / own-tests.mjs | OWN_001 | 双owner完整场景未准备，逐TP明确blocked，不模拟生产登录 |
| sec / sec-tests.mjs | SEC_001～005 | 文件非公开/逃逸symlink/XSS双角色渲染/脱敏/内存风险 |
| perf / perf-tests.mjs | PERF_001～002 | 3预热+20提交样本/分位值；执行首包时钟条件待补 |
| arc / arc-tests.mjs | ARC_001～004 | 人工数据流校审+AST边界/实际Port/技术栈/迁移历史 |
| qlt / qlt-tests.mjs | QLT_001～007 | 全状态边、既有pytest、后前端质量命令和API/Event门禁 |
| life / life-tests.mjs | LIFE_001～009 | 独立总入口运行的隔离/协议/报告/清理/诊断恢复和危险路径 |

辅助文件：`run-test-driver.mjs`提供会话/queued/SSE有界准备；`{doc,par,chk,idx,rag}-driver.py`在Linux容器中调用真实生产函数（需要事务隔离时用外层回滚/保存点，不伪造状态）；`fe-workspace.test.ts`/`fe-component-checks.mjs`挂载真实组件并逐项映射结果，仅替换外部HTTP/SSE传输时序；`life-runner-driver.mjs`/`life-path-driver.ps1`驱动限定身份的独立总入口和路径自检。`fe-native-stream-probe.mjs`仅诊断真实HTTP/Vite/Chromium空SSE响应的连接前提，不进入manifest，不产生产品通过结论。

`doc-limit-tests.mjs`及`rag-empty-tests.mjs`不在正式manifest重复计数：由doc/rag分类通过固定HarnessScenario启动新库，验证真实HTTP恰10MiB（暂停Worker直到销毁，避免15420块索引）和真实空库Run；主报告关联nested证据。LIFE自检部署5个独立父run，其中nested-recovery再部署1个子run；另有daemon不可达及无效恢复凭据检查，不部署资源。验证空分类、非法报告、超时树、disabled、KeepContainers及分类超时后父登记兜底清理；自检哨兵只在tooling，不宣称产品passed。耗时会高于单纯主链路，可查看各类中文日志。

FE_009的浏览器局部场景仅把第一次HTTP历史交付控制为空（保存正式API真实事件摘要），让真实原生SSE读取PG初始帧；后续HTTP透传。`fe-sse-transport.mjs`将生产client的本例正式SSE请求以HTTP302导向限定本例Run/前端Origin的本地透传服务，PG帧原字节传递，真实销毁socket触发error，不合成事件或关闭CORS。`fe-sse-transport-selftest.mjs`仅检查工具边界、真实断开/游标恢复及不重连负哨兵，不进入manifest。这是受控传输服务断开检查，不代表正式API自然返回空历史；普通浏览器offline与running分片完整续流仍独立blocked。

```powershell
node --test tests/demo-smoke/lib/category-kit.test.mjs
node tests/demo-smoke/tooling/check-coverage.mjs
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc
# 完整试跑结束后检查所有用例/TP是否产生记录及哪些子项未完成
node tests/demo-smoke/tooling/check-coverage.mjs tests/demo-smoke/artifacts/<run_id>
```

## 任务1～任务2准备状态

工具安装/重装及检查见[tooling说明](tooling/README.md)，本轮实际证据与审批见[准备与审批记录](任务1-2准备与审批记录.md)。没有全局业务SQL或导入脚本：Demo没有账号/身份基线表，owner由配置生成，七业务表初始为空；用例通过正式API独立创建事实，详见[数据策略](fixtures/data-strategy.md)。迁移已接入不等于虚假数据导入。

任务1～2的总入口/工具验证为历史证据；任务3新增21前缀分类替换七大类占位。当前执行和未落实目标以任务3～4记录及本次artifact为准；不把准备记录转成产品结果。

## Playwright工具

已在本目录独立安装playwright 1.63.0及Chromium，未更改frontend依赖；真实浏览器分类已在fe/sec/doc接入。重装时：

```powershell
npm ci --prefix tests/demo-smoke --cache tests/demo-smoke/.cache/npm
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'tests/demo-smoke/.cache/ms-playwright'
node tests/demo-smoke/node_modules/playwright/cli.js install chromium
```

分类Node脚本可import playwright，入口设置项目内浏览器路径。系统npm缓存不可写时仍用上面的项目缓存，不修改全局配置。

新增完整工具检查命令（仓库根）：

```powershell
.\.venv\Scripts\python.exe tests/demo-smoke/tooling/check-python-tools.py
npm run tools:check --prefix tests/demo-smoke
```

工具检查只用哨兵组件/数据。`npm run unit:frontend --prefix tests/demo-smoke`选择真实组件断言，产品失败返回1；工具探针通过不代表组件通过。`npm run lint:frontend --prefix tests/demo-smoke`为真正ESLint；原frontend的lint仍只是vue-tsc。QLT逐条保留真实退出/输出，不能构建通过替代交互。依赖/浏览器/.venv/egg-info长期复用，不算每run业务残留。

## 状态与报告

退出码：0 passed（选中分类真实通过且清理成功）；1 failed；2 blocked；3 not_ready；4 cleanup_failed；5 cleanup_deferred。空/未接入分类不能passed，清理失败高于测试失败；summary分别保留test_status和cleanup_status。

报告含summary.json/md、summary-详细.md（逐分类/用例中文投影）、manifest.json、categories/、environment/（脱敏Compose config/ps/up/down/health/实际DB探测）和logs/（构建、6服务最近2000行）。按run_id保留，恢复清理前另存旧summary；详细摘要生成失败计报告失败。`check-coverage.mjs <artifact>`额外生成case-coverage.json。分类原始JSON是完整子项依据，摘要截短说明不替代它。未接入分类明确not_ready及空checks，不伪造测试结果。

## 清理与磁盘保留

正常结束/可捕获异常进入finally：终止分类子进程→收集证据→按父runtime/nested-runs.json精确恢复尚存子环境→`down --volumes --remove-orphans`→检查project标签容器/网络/卷及捕获的匿名卷→删本次唯一image tag→删本次tmp/runtime。子环境身份验证失败仍继续清理已验证主环境，但保留父runtime并报告清理失败。路径解析和link检查防止删除仓库根、开发数据或其他项目。

清理失败时尽可能删tmp、保留最小runtime凭据以便重试，不报告无残留。诊断保留或硬杀进程后：

```powershell
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -CleanupRunId <输出的run_id>
```

不执行global prune。删除容器释放写层/容器日志，删PG/uploads/Redis匿名卷释放业务数据；本次image tag删除后，共享基础镜像和BuildKit缓存仍可能占空间，这是有意复用缓存，不代表Docker虚拟磁盘物理文件立即缩小。

artifact默认保留。容器日志上限10MiB×2且随容器删除，报告只截末尾；长期仍需人工按run_id管理报告。不要对runtime/artifacts根目录笼统递归删除；不再需要的精确报告目录可移至回收站。Playwright浏览器约数百MiB及node_modules长期供后续测试使用，不计作每次环境残留。

## 已知边界

基础健康和DB探测不证明PRD全通过。lease/retry/deadline/前端恢复等业务缺口未修复；完整慢Provider/事务屏障、双owner/E4协议等仍待准备，分类blocked不是passed。静态架构检查含人工判断及AST证据，不证明完整替换/并发；后续实现改变应重新校审。硬终止/关机无法finally，必须恢复清理；runtime也丢失时按记录project标签只读定位残留，再人工确认精确资源，禁止全局清理。
