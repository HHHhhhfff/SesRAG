# 测试工具与运行器协议探针

`compose-rag-check.test.mjs`通过真实Context将带双引号、Windows/Unix traceback及合成Secret的失败结果落盘，要求JSON可解析并保持exit1/诊断信息且脱敏；配置driver局部先脱敏原始stdout/stderr/error再结构化写证据，共享Context不变。该负哨兵与真实10容器证据的JSON解析校验一并执行。

全量审查窄修新增 `pg_flush_scenarios.py`：真实 PG 的 queue/failure/events 三组最后 flush 屏障，26 个路径×lease/deadline 自然到期组合，独立连接逐行比较 Task/Run/Document/Message/Journal 及两个游标；每组继续受 Python 65 秒、容器 driver 90 秒截止。`compose-rag-check.mjs` 从根 Compose 真实解析四配置，只将非敏感字段记录到证据；预登记10个容器分别消费 API/Worker 配置，`compose_rag_consumer.py` 用正式创建/索引/Run 证明快照、切分和Top-K，非法配置在实际启动模块导入时拒绝。每容器45秒，finally按精确标签回收，数据库交自有卷最终清理。

`frontend-components.mjs` 本轮收集36项（原35项加成功重试历史错误文案），`fe-component-checks.mjs`逐标题映射与`frontend-checks.mjs`导出的QLT集合一起扩展。以下旧阶段35项文字为历史基线，当前计数以此段及可执行集合为准。新增PG三组映射RUN/WK/EVT并由QLT要求；DEP和QLT直接执行根Compose消费门禁。

本轮有界预算更新：DEP从600到1800秒，新增消费预算按12×30秒Compose解析、10×45秒容器执行、10×25秒精确回收合计1060秒，另留140秒余量；WK从2700到3000秒，容纳新增3×90秒driver。RUN/EVT各新增90秒仍在既有余量内。QLT独立分类预算和为17220秒，加Compose1060秒和负哨兵30秒后仍有3290秒供其余门禁。21分类总59070秒，默认主包装加7440为66510秒，取代下文旧57570/65010数字；不声称无限主机资源规模的数学上界。

本目录存放工具检查、覆盖校核和固定harness输入；工具哨兵和协议探针不进入正式产品manifest，不回填用例正式验收结果。任务3新增`check-coverage.mjs`和`harness-fixtures/`：LIFE用明确自检manifest故意触发错误协议，DOC/RAG薄入口调用specific_test_script中的独立边界断言，不将哨兵passed当产品passed。

## 5a 真实执行驱动

`pg-execution.mjs` 提供 `pgScenario(ctx, scenario, {timeoutMs})`，从现有分类 Context 创建本 project 的具名 `--rm` 测试容器，仓库只读挂 `/work` 并设置 `PYTHONPATH=/work`，避免旧诊断镜像覆盖当前源码。创建前写 `RuntimeDir/execution-resources.json` 的准确 project/run/name/labels，finally 核验标签后清理自己的容器；数据库 `sesrag_5a_<token>` 留在本 project PG 卷中，交总入口销毁。5d 已接入总入口 finally/CleanupRunId 登记兜底，实际验收结果仍以本轮报告为准。

`pg-execution.py` 每场景通过 Alembic 建独立库，调用正式应用、Queue、handler、Runtime 推进状态；SQL 仅用于观察、DDL 建库或精确连接故障。`pg_run_scenarios.py` 管会话/取消/Journal事务；`pg_queue_scenarios.py` 管租约、重试、崩溃、日志、readiness；`pg_network_scenarios.py` 管真实HTTP/SSE、冻结Provider和Linux main。`pg_harness.py` 提供有界 `Gate`、真实 PG `Harness`、慢/失败 `Provider` 和 `ChildWorker`。`worker-bootstrap.py` 只给生产 `backend.workers.main.main` 注入测试 Provider（production阶段保留真实Provider）；生产 loop、signal handler、退出清理保持真实，Linux SIGTERM/SIGKILL由父控制进程发到精确 PID。`pg-execution.test.mjs` 为输出协议及资源身份的正负工具哨兵，不计产品验收。

`specific_test_script/execution-coverage.mjs` 将原5a blocked逐case/TP/sub接入msg/run/wk/can/evt/sse/hlt；同分类复用一次场景的独立子断言与原始证据。`execution-focused.mjs` 仅验证新增覆盖，必须用独立ArtifactDir（例如本run的`task5a-focused`），环境变量`SMOKE_EXECUTION_CATEGORY`只允许上述七分类；它不是正式all或完整分类。最终发布四组合复用`tests/integration/execution_pg_probe.py::final_publication_probe`真实PG验证；原RED与修复后GREEN历史均保留。测试进程专用clock/Port/session包装不是生产配置开关。

需要只复验某个新增子目标时，`execution-focused.mjs`接受测试工具专用`SMOKE_EXECUTION_SUB`逗号分隔子项（筛选为空必须失败）；应另指新的ArtifactDir，不覆盖已完成专项报告。正式分类不消费此筛选变量。WK旧300秒预算与早期600秒建议已被完整场景最坏有界预算2700秒取代，依据见下文5d预算说明；实测耗时不作为最坏上限。

### 5b/5c 持续控制接口

`await startControlledWorker(ctx, settings={})`创建本project已登记`--rm`容器、唯一库和随机`127.0.0.1`端口，返回：

- `baseUrl`：真实生产API挂载根路径；用正常HTTP创建Thread/Run/上传。与主环境库隔离，浏览器须将该次API请求合法代理到此地址。
- `controllerPid`、`resource`：控制进程PID和本次容器身份。
- `await start(stage='delta')`：启动真实main；`embed`/`model`在对应调用暂停，`delta`在首片已持久、第二片前暂停；`production`保留实际Provider，5b可把base URL指向同Compose网络已登记HTTP服务（此模式应由协议服务观察调用，不能awaitReached文件屏障）；返回`controller_pid/worker_pid/running/reached/released/exit_code`。
- `await status()`、`await awaitReached()`：查询/有界等待屏障，不能只凭UI判断事实。
- `await facts(runId)`：独立PG读取本服务Run/Task/Message身份、Journal序列、游标。
- `await release()`：放行该Worker Provider；三片会继续真实写Journal。
- `await stop()`：精确PID SIGTERM，等待生产main退出并返回exit_code。
- `await close()`：finally必须调用；放行/停止、保存日志、核验容器标签并精确关闭；无Worker也可关闭。

`worker-controller.py`只在测试容器提供`/__test/*`控制端点，未给生产app添加测试路由；`worker-controller-probe.mjs`真实验证未启动清理、非法阶段拒绝、首片running、三片完成、exit0和容器消失。所有测试HTTP服务在容器内关闭socket，生产create_app的uvicorn lifespan负责engine/notifier关闭；mount控制器显式finally关闭。execution-resources硬杀兜底已接总入口，最终生命周期验收由总入口负责。

`settings`只允许MOCK_PROVIDER、MODEL_BASE_URL、MODEL_API_KEY、MODEL_NAME、EMBEDDING_MODEL_NAME、RAG_TOP_K、TASK_DEADLINE、TASK_LEASE_TTL、TASK_HEARTBEAT_INTERVAL、WORKER_SHUTDOWN_GRACE。值经子进程环境注入，不进入命令行证据；API和Worker均消费同配置，owner继承Context。仅使用虚拟测试Key。上传/数据库/资源身份不能通过此参数覆盖。实际OpenAI协议fixture服务属于5b；本工具只提供可指向它的真实Worker生命周期。

## 5b 文档与真实HTTP协议驱动

`pg_document_scenarios.py`复用5a Harness/Queue/Runtime，负责本例上传文件部分写失败、保存后登记commit失败、活动Task复用、Document锁竞争、多块候选/旧active真实检索、独立engine的pg_stat_activity采样以及普通Parser/Embedding错误耗尽。`pg_rag_scenarios.py`负责最终发布commit屏障、正式Top-K消费、真实search故障、实际Port包装替换及容器内生产Worker main配置启动拒绝/Mock对照。故障只作用本例session或Port，不SQL写state/generation/seq。

`provider_protocol.py`是已预登记场景容器中的真实HTTP/1.1 TCP服务，仅绑定该容器loopback；`ProtocolServer(token, endpoint, mode, gate).serve()`返回本例随机端口URL，token必须8位小写hex。生产httpx实际访问`/<token>/v1/embeddings`或`chat/completions`，行为由构造时fixture配置，不从Prompt触发。它记录endpoint/model/stream/分片时间，不记录Authorization、Prompt或响应原文；所有listener/writers/tasks在finally关闭，并检查实际关闭状态。此接口不提供跨容器控制端口，5c继续使用5a controller。子进程和socket均归已登记父容器，5d按同一个execution-resources.json进行硬杀恢复。

`pg_provider_scenarios.py`包含embed/chat各400/401/403/404/408/429/500/503、真实网络挂起超时、socket断开/连接拒绝、12种Embedding畸形结构/数值/维度、9种chat SSE异常、index383/385/384对照及HTTP永久/临时错误。三片流各在HTTP未结束时由独立PG观察Journal，然后才放下一片。超时场景只在测试进程将生产适配器总预算缩短为0.25秒，真实TCP及httpx取消逻辑保持不变；不证明60秒生产延迟指标。拒绝连接的chat例使用两个真实Provider Port，使Embedding成功而chat端口未listen，仍由正式Runtime结算。

`assert_safe_raw`先在内存扫描原始HTTP响应、Message/Event/Task/snapshot与Runtime默认日志，再交Context写脱敏证据，避免测试自动脱敏掩盖产品泄漏。仅使用合成Key、URL凭证片段、宿主路径标记和上游正文哨兵；不输出原文。`test_provider_protocol.py`是工具token/泄漏负哨兵及真实未知token/活跃连接异常清理检查，不计产品验收。

`specific_test_script/document-rag-coverage.mjs`将doc/par/chk/idx/rag/sec/arc原受限目标接入逐case/TP/fixture检查。同case允许共享场景，各case重新建独立库；Citation使用Task3的`contracts/evidence_v1.json`严格验证。`document-rag-focused.mjs`只运行新增5b检查，接受六参数和固定`SMOKE_DOCUMENT_RAG_CATEGORY`，可选`SMOKE_DOCUMENT_RAG_SUB`筛选，必须使用独立ArtifactDir，不能当完整分类/all。每场景沿用`pgScenario`的创建前登记、源码ro挂载和准确标签finally清理；独立库保留在本project卷，交总入口销毁。

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests/demo-smoke/tooling -p test_provider_protocol.py
```

上述驱动的新增覆盖不改写原两轮历史报告；当前执行结果以本次category JSON和execution原始证据为准。docx全区域、双owner和普通浏览器offline仍按各自ADR范围保留受限。

## 其他文件职责

### 5d 生命周期、契约与性能

`lib/process-identity.mjs`以PID+出生时间+可执行文件确认进程，拒绝缺身份或已复用PID。`frontend-resources.mjs`创建前登记owner身份，创建后登记实际进程身份；`smoke-common.ps1`登记总入口分类进程。`cleanup-registered.mjs`供总入口finally/CleanupRunId消费进程、frontend与execution登记：先核验run/project和容器精确标签，再关闭本次进程/容器并观察消失；失败保留runtime。`cleanup-registered.test.mjs`真实硬杀父Node后回收Chromium，并验证错误出生身份不杀对照进程。

Windows快速子进程的MainModule可能在加载前为空；PowerShell适配器启动前只解析Application为绝对exe路径并实际使用该路径，出生时间来自自有Process句柄。快速退出未取得出生身份时必须先观察真实退出再closed；仍活跃的采样/登记异常保留错误并用已有Process句柄终止/等待，不能按无身份裸PID恢复。self-tests含30次快速exit7、函数入口拒绝和活跃登记异常清理；工具另独立比对活跃Node/pwsh出生时间与实际路径。

前端共享登记使用5秒排他锁保护整个读改写，避免QLT父/FE子并发覆盖或损坏JSON；取锁与原子rename共享同一5秒截止，Windows分享占用的EPERM/EACCES/EBUSY仅有界重试。永久rename失败保留旧registry和`.tmp` pending，释放锁后抛错，不能标作closed。工具4进程各20项真实并发新增+closed、错误run异常释放、遗留锁超时、瞬态及永久rename故障均须通过。辅助容器清理一次只读名称清单，再仅按登记的精确名称/标签检查实际存量，不因大量已关闭历史登记逐次启动Docker造成清理超时。

Node子进程spawn中的身份/登记异常进入可await rejection，不从EventEmitter逃逸；finally按已核验身份终止进程树，没有身份时只使用自有ChildProcess，关闭管道最多等5秒，保留原错误与额外清理错误。ENOENT原错可捕获，真实非零快速退出不变成成功；工具真实活跃EIO哨兵验证调用方catch/finally及PID关闭。

`harness-overrides.mjs`只生成固定部署故障覆盖；`lifecycle-focused.mjs`用同一正式主入口及源镜像创建不同nested project/唯一tag，验证配置错误、迁移42、Redis冷启动降级及正式Run执行、真实数据库不存在探测失败、Worker/前端未就绪、真实FileShare.None和FileShare.Read删除失败以及完整硬杀恢复。Windows真实Ctrl+C注入未具备，保持独立blocked；taskkill不冒充可捕获中断。固定`cleanup-share-read`与原`cleanup-failure`均要求真实4→CleanupRunId3及零残留。专项接受六参数和固定`SMOKE_LIFECYCLE_SCENARIOS`逗号列表，报告必须新ArtifactDir。

运行目录递归删除前原子保存单文件`runtime/<run_id>-recovery.json`胶囊，固定白名单保留context、compose.env、override、资源与nested登记的原始字节；它含恢复凭据，仅属于ignored runtime，禁止复制到artifact/日志。可读预检已取消：其他删除任意失败都保留胶囊并恢复缺失材料，已有同内容只读共享文件不重写；runtime删除完成后最后删除胶囊，最后删除失败同样非零可恢复。CleanupRunId先验证run/project/marker/普通文件/白名单再恢复，无runtime但有胶囊也可恢复；冲突/链接/越界拒绝。主/子清理和assertClean都检查胶囊残留。锁专项armed时内存备用材料仅供RED失败后的精确安全兜底，不进入报告、不计通过。

`lib/api-contracts.mjs`统一注册版本Schema跨文件引用；`http-contract-matrix.mjs`/`contract-focused.mjs`运行正式HTTP成功、校验/业务错误、PG故障503矩阵，原始响应先校验安全哨兵再写证据；`pg_contract_scenarios.py`补真实Runtime retry/failed事件。`contracts.test.mjs`拒绝错type/data。`test_contract_fallback.py`验证未知校验type/动态loc的固定fallback。前端生成器`--output <本run tmp文件>`生成后逐字diff，finally删临时文件；漂移不得直接重写正式类型作为通过。

`lib/quality-category-gate.mjs`要求同run正式完整分类、唯一ID/Schema/总体状态一致、每个正式用例TP覆盖、必测passed和证据存在；缺报告真实运行对应正式入口，创建前采样源码hash并保存实际命令/时间/退出。5a/5b导出目标及30browser+35component均纳入。除明确PAR004区域支持和FE009 ordinaryoffline blocked外任一未通过都拒绝；不从历史/多个专项拼接成passed。`quality-category-gate.test.mjs`拒绝漏TP、未知blocked、缺证据与伪总体状态。`environment-evidence.mjs`保存host/API/Worker各自实际版本和pip check，不假定镜像和宿主相同。

QLT_007最后的`actual-runtime-dependencies`正式调用environment-evidence六参数工具，前面的PG/Worker故障均已finally恢复，在all主入口销毁容器之前保存本轮三端版本、三pip check和真实子进程结果。采样失败不能复用诊断快照或写passed；分类报告明确引用版本/进程证据，正式两轮分别采样。

`performance-events.mjs`在23次Run逐次停止本project Worker、实际订阅收到创建事实后放行；前3次预热，后20次测量同run.started事实到客户端到达。前后宿主/Worker/API/PG UTC往返校准给保守误差区间，宿主UTC相对单调时钟跳变或区间跨2秒为blocked。保存环境负载和SSE关闭登记，证明本地Mock流程目标，不证明生产SLO。

Starlette1.7优先使用httpx2 TestClient，原warning来自旧httpx兼容路径。开发依赖固定httpx2/httpcore2 2.13.1及truststore0.10.4；生产Provider继续httpx0.28.1。ESLint当前仅保留已DOMPurify清洗Markdown处vue/no-v-html警告，新增警告失败；不关闭规则或静默过滤输出。

分类预算按有限driver调用核算，而非实测平均：5a按同分类缓存场景数（MSG3/RUN9/WK25/CAN7/EVT1/SSE3/HLT1），5b按case+scenario缓存数（DOC6/PAR1/CHK1/IDX10/RAG59/SEC2/ARC1），每PG driver上限90秒，另留原基线与容器清理余量。因而WK2700、RAG6000、RUN1200、CAN900、DOC1500、IDX1200秒；正常专项实际远短于上限。FE1800覆盖30浏览器的有界控制器/页面步骤及35组件；PERF900覆盖23次启停/订阅/20秒流截止及校准。QLT21600为独立缺报告时EVT/SSE/WK/RUN/CAN/DOC/PAR/CHK/IDX/RAG/FE预算之和16920秒，再加质量命令、契约矩阵、恢复与I/O余量4680秒；正式all已具备同run报告时只校验，不重复该全量。

LIFE预算由`../specific_test_script/life-budget.json`提供，driver实际消费ordinary/recovery/daemon/special/client数值；`lifecycle-budget.test.mjs`验证总和及manifest下界。15000秒=14×300普通/固定nested+90daemon+420特殊nested-recovery+4×240显式恢复+180客户端含关闭+16×240全部登记失败finally恢复+315×15只读诊断槽+585本地报告/调度预留。315槽为保守工程预留，不是无界主机进程数/磁盘阻塞的数学上限；分类总截止仍15000，异常超时须由父入口登记恢复。21分类总57570秒，不能沿用旧47370/3小时包装。

父包装默认部署/常规主清理可另预留3600秒：build900+up180+readiness180+preflight180+收日志/inspect540+登记180+down120+残留诊断120+两tag120+报告/文件180+调度900=3600。这只针对默认参数和无遗留nested常规路径；若分类被杀且仍有16个nested待恢复，需再预留16×240=3840秒，建议Task6总包装默认使用manifest总+7440秒（65010秒），自定义build/wait/session还须增加差额；不得称+3600覆盖最坏失败恢复。包装必须保持Node计时器有限范围，产品退出/summary不能由包装exit替代。

### 5c 真实持久浏览器驱动

`frontend-persistent.mjs`在真实浏览器中执行9个原受限目标，另供`fe-tests.mjs`两个旧断线ID复用同样真实running流程。首片PG提交后暂停第二片；永久错误经正式Runtime结算；replay只延迟完整真实响应，SSE字节沿用`fe-sse-transport.mjs`；socket断开期间PG继续写后片，恢复携带已消费游标。切Thread与queued/running刷新均核对正式API、独立PG facts及页面，不合成Event或写SQL业务状态。`frontend-checks.mjs`导出QLT所需完整30个浏览器ID及35个组件ID；普通offline另保留blocked，不纳入passed集合。

`frontend-controller.py`和`frontend-bootstrap.py`仅为测试入口，复用5a Harness/ChildWorker/controller_app；固定failure阶段通过普通Provider Port注入安全码及内存敏感哨兵，前端原始DOM扫描完成后只存命中布尔。共享工具增加可选bootstrap/worker_factory/harness_options，默认5a调用不变。`startControlledWorker(ctx, settings, {frontend:true})`仅选择固定前端测试入口，无任意脚本或生产后门。

`frontend-harness.mjs`启动受登记的当前源码Vite，以合法`API_PROXY_TARGET`指向本例TCP字节网关/独立PG控制器。Vite端口由OS分配并strictPort监听；不复用旧frontend镜像，不禁用CORS。网关关闭真实listener/socket形成浏览器API路径不可达，同时直接API对照仍可用。健康故障分别停止本例Worker、指定run的PostgreSQL、Redis，逐次finally恢复；Worker健康检查跨真实TTL重新点击，Redis使用本project逻辑库15隔离主Worker readiness键。PG/Redis故障禁止与其他本run任务并发执行。

`frontend-resources.mjs`在Browser/context/page/SSE/Vite/relay/子进程创建前写`RuntimeDir/frontend-resources.json`，与5a的`execution-resources.json`共同归父run。字段为schema_version、parent_run_id、project、resources[]；每条含id/kind/owner_pid/status，创建后补pid/port/url，真正close/exit后补观察字段再closed。正常和异常finally关闭，Browser记录真实进程退出、context关闭事件、page.isClosed，SSE透传记录连接closed。`frontend-resources.test.mjs`验证错误run拒写、真实非零退出不吞错、超时杀自有进程树。父入口硬杀不会执行这些finally，5d必须按owner_pid及登记PID/容器标签恢复，且核对当前进程身份防止PID复用。

`frontend-components.mjs`收集原17+Task4新增18项真实Vitest结果，精确标题唯一匹配、总数35及进程退出均校验，保存完整JSON/stdout/stderr。`frontend-focused.mjs`仅用于新增专项，六参数与分类相同；`SMOKE_FRONTEND_MODE=components`选35组件，默认持久浏览器，可用`SMOKE_FRONTEND_SUB`逗号列出固定子项目。正式`fe-tests.mjs`不读专项筛选，不将专项报告当全分类。

`frontend-lifecycle-probe.mjs`在真实running首片已PG提交、页面/SSE已观察后故意抛出测试错误；finally结束后核验所有自身登记closed及Chromium PID消失。它保存armed与cleanup证据供LIFE006消费，不计产品分类，也不代替总入口硬杀恢复。

`frontend-panel.test.mjs`是FE015观测负哨兵：只在内存替换A的Run身份、可见running/succeeded或同seq事件，确认B面板完整核对会拒绝。真实切换场景在放行A前及A终态后分别核对B正式API/独立PG cancelled和完整Journal；Run身份读取RunTimeline根节点的Vue props，另独立核对可见状态和seq/type，不修改组件或产品事实。

```powershell
node --test tests/demo-smoke/tooling/frontend-resources.test.mjs
# 专项另外指定独立ArtifactDir，不能覆盖正式同run报告。
$env:SMOKE_FRONTEND_MODE='components'
node tests/demo-smoke/tooling/frontend-focused.mjs <六参数>
```

所有场景只证明流程、持久身份和投影，不证明外部模型效果。普通浏览器offline、OWN、PAR范围仍按ADR暂缓。正式all仍须重建冻结源码主镜像，不能以当前Vite专项替代。

| 文件 | 职责/何时使用 |
| --- | --- |
| check-tools.mjs | Chromium中文DOM/关闭、Ajv契约工具、ESLint真实解析/拒绝非法语法、Vitest组件工具启动自检。依赖安装后运行。 |
| check-python-tools.py | Python3.12、开发依赖导入/版本和JSON Schema正反哨兵校验。使用根.venv运行。 |
| vitest-tool-probe.test.ts | 独立Vue组件及Pinia驱动组件两探针，核对挂载/点击/更新/卸载、测试目录依赖解析；非产品用例。 |
| vitest-tools.config.mjs | 专门选择上述探针，不能混入正式组件测试include。 |
| dispatch-probe.ps1/.mjs | 六参数、含空格路径和中文输出哨兵；由父目录self-tests调用，无HTTP或数据库副作用。 |
| check-coverage.mjs | 149用例/191测试点的声明路由及本次报告核对；另列只有blocked和可验证基线仍有受限子项。不是行为全覆盖证明。 |
| render-summary.mjs | 读取本次summary/categories，生成summary-详细.md中文投影，不回填用例卡片。 |
| lint-frontend.mjs | 固定仓库根调用ESLint真实扫描frontend/src；空/全部ignored必须失败，产品错误返回1。npm lint:frontend使用此入口。 |
| harness-fixtures/ | 固定LIFE协议/超时/登记兜底故障输入，以及DOC/RAG专属边界薄入口；只允许总入口的HarnessScenario白名单选择。 |

父目录[eslint.config.mjs](../eslint.config.mjs)限定frontend/src，独立于frontend旧的lint=vue-tsc；[vitest.config.mjs](../vitest.config.mjs)限定specific_test_script中的test/spec，**没有用例退出非零**。Vue Node入口及test-utils/Pinia/vue-demi内联配置保证同一测试runtime；Vue为前端同版本3.5.43，Pinia alias明确指向frontend安装的同一模块，避免测试包另装一份activePinia。不改变产品bundle；因此宿主frontend依赖也须按锁安装。

## 重装与调用

ESLint针对TS/带TS的Vue不启用core `no-undef`，因为它误将DOM类型当运行时变量；未定义标识由独立`vue-tsc`门禁检查，其他TS/Vue推荐规则保留。工具自检包含DOM类型正哨兵及非法TS语法负哨兵。Vitest工具探针显式替换include集合，不合并产品组件用例；产品失败不能变成工具依赖缺失。

当前总入口调度分类并生成中文详细摘要，需要本机**Node24.15+的24.x或26+**（本次24.18；依赖不支持25），不能继续按历史“仅PowerShell/Docker即可完整闭环”理解。PowerShell7.4+/Docker/Compose负责环境生命周期；不升级frontend容器的Node20。Python必须3.12，不能使用PATH中的3.11；无需uv或全局安装。

仓库根运行（Python3.12绝对路径替换为机器实际安装路径）：

```powershell
& '<Python3.12绝对路径>' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tests/demo-smoke/requirements-tools.txt --cache-dir tests/demo-smoke/.cache/pip
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
npm ci --prefix tests/demo-smoke --cache tests/demo-smoke/.cache/npm
# 前端锁文件不改动；宿主typecheck、build及Pinia工具探针需要实际源码依赖。
npm ci --prefix frontend --cache tests/demo-smoke/.cache/npm
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path (Get-Location) 'tests/demo-smoke/.cache/ms-playwright'
node tests/demo-smoke/node_modules/playwright/cli.js install chromium
.\.venv\Scripts\python.exe tests/demo-smoke/tooling/check-python-tools.py
npm run tools:check --prefix tests/demo-smoke
pwsh -NoProfile -File tests/demo-smoke/self-tests.ps1
```

Windows/Python3.12的完整依赖快照在[requirements-tools.txt](../requirements-tools.txt)，不作为Linux应用镜像新锁；Node精确直接版本和完整传递依赖见package.json/package-lock.json。JSON Schema分别可用PS Test-Json、Node Ajv2020+formats或Python jsonschema；HTTP/SSE用PS/.NET或Node原生fetch流，SQL诊断用容器psql，无需另安装宿主数据库客户端。

## 产品门禁与分类命令

```powershell
# 真正的独立ESLint；不得把产品失败规则静默关闭。
npm run lint:frontend --prefix tests/demo-smoke
# 已接入真实Workspace组件断言，失败返回1；不是工具探针。
npm run unit:frontend --prefix tests/demo-smoke
# 原有前端类型检查/构建仍按frontend/package.json运行。
npm run typecheck --prefix frontend
npm run build --prefix frontend
# 使用项目Python而非系统3.11；任务3～4试跑不代替任务5稳定性验收。
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend tests migrations
.\.venv\Scripts\python.exe -m ruff format --check backend tests migrations
.\.venv\Scripts\python.exe -m mypy backend
```

安装工具不代表产品门禁通过。ADR002 E2/E4/C的真实慢任务、PG提交屏障、特殊配置、HTTP/SSE及持久浏览器驱动已接入并正式两轮复验；O双owner仍按ADR非目标暂缓。工具准备历史不能替代本轮原始报告；当前结果与范围限制见[复验报告](../复测和验收报告.md)§9。

PowerShell分类开头必须设置`[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)`及`$OutputEncoding=[Console]::OutputEncoding`；Python输出用UTF-8。运行器进程适配器按UTF-8读stdout/stderr并传PYTHONIOENCODING。Node原生UTF-8。详细协议见[分类README](../specific_test_script/README.md)。
