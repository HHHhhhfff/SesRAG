# PRD-002 本机隔离测试套件

本目录承载 v0.2「持久化会话与对话工作台」的独立测试环境和验收工程；不复用、不恢复 `tests/demo-smoke/`。任务5～6已完成两轮同源码/依赖/镜像的All，两轮各104通过、0失败/受限/未运行/工程错误，清理通过，退出0；[用例](test-cases.md)的312个执行字段已回填。详细结果、真实命令和证据见[测试报告](测试报告.md)，归档呈现、版本元数据、文档残留和扫描计数措辞4项补充问题见[缺陷报告](缺陷报告.md)。任务3～4不同源码试跑历史仍保留于[脚本校审记录](测试脚本实施与试跑校审记录.md)，没有拼接旧结果冒充本轮通过。 2026-10-24已完成WS-DEF-001～004最小修复，新增归档4点/4例，最终108例完整All通过、清理通过、退出0；首轮2项工程失败保留单列，最新结论以[修复回归报告](小缺陷修复与回归验收报告.md)为准。

## 当前状态

2026-10-24最小修复新增TP-THR-09～12及UI_015～018，仍由`workspace-tests.mjs`和现有总入口执行：互斥归档视图、真实分页迟到隔离、首屏外归档偏好和归档视图中新建。QLT_006用中文明确标注artifact/Git/dist合计扫描次数；新增formatter自测属于工程门禁，不计产品用例。上述18例workspace在两次修复轮均通过；最终108例全通过。完整变更及最新回归结果见[小缺陷修复与回归验收报告](小缺陷修复与回归验收报告.md)，原104例两轮证据保留。

| 文件/目录 | 用途 | 状态 |
| --- | --- | --- |
| [测试点设计与需求覆盖矩阵](测试点设计与需求覆盖矩阵.md) | PRD-002 的测试目标、需求映射、代码依据和本机可验证性。 | 已完成设计；不是执行结果。 |
| [test-cases.md](test-cases.md) | 当前8类108例、88点，324个最新执行字段已据真实结果填写；原104例两轮文字标为历史。 | 最终108通过；新增四例有真实Chromium证据。 |
| [测试报告](测试报告.md) | 任务5～6：正式两轮基线、环境/命令、分类与性能/质量结果、证据和清理校审。 | 两轮各104 passed；自动化集通过，不宣称PRD零差异。 |
| [缺陷报告](缺陷报告.md) | 原4项补充发现及2026-10-24修复状态，原失败/受限集合保留。 | 001～004已处理；005原报告未定义。 |
| [任务5～6最终校审](artifacts/任务5-6最终校审.json) | 两轮逐例对照、证据hash、字段/链接/覆盖与独立残留审计。 | 交付阶段生成的机器可读记录；Git忽略，交接时随证据保留。 |
| [test-plan.md](test-plan.md) | 用例和8类产品脚本的接入路线、先决条件与完成状态。 | 8类已登记 ready；具体试跑结论另见校审记录。 |
| [run-workspace-tests.ps1](run-workspace-tests.ps1) | `Environment`/`Selected`/`All`/`Cleanup` 生命周期主入口。 | Environment仅技术探测；Selected/All执行登记分类并统一清理。 |
| [specific_test_script/README.md](specific_test_script/README.md) | 分类脚本的接口、数据隔离、超时、日志和报告要求。 | 包括runtime、浏览器和容器内探针的接入说明。 |
| `specific_test_script/manifest.json` | 登记8类脚本、完整case ID和有界超时。 | 全部 `ready/required=true`；ready表示可调度，不表示用例通过。 |
| `compose/docker-compose.workspace-test.yml` | 独立 PostgreSQL、Redis、受控 Provider、迁移、Profile 导入、API、Worker、前端和按需工具镜像。 | 环境入口；不继承根 Compose。 |
| `fixtures/` | 安全的合成基线、4 个 Profile 和文本文档素材；Provider 仅提供受控协议能力。 | 环境/未来测试输入，不预造 Thread、Run、成功事件等业务事实。 |
| `tooling/`、`schemas/` | 预检、结果协议、环境探测、分类运行器和资源所有权工具。 | 生命周期逻辑统一为 Node 模块；PowerShell 只保留入口，不再维护重复的 `lib/*.psm1`。自测不算产品用例。 |
| `环境实施与验证记录.md` | 记录环境交付阶段的正常/故障清理、强停恢复和限制。 | 历史环境证据；当前产品正式结果见测试报告。 |
| [测试准备与总入口核验记录](测试准备与总入口核验记录.md) | 任务1～2的工具/数据审计、总入口补强、实际命令与本轮环境闭环证据。 | 不替代产品用例结果或后续测试/缺陷报告。 |
| [测试脚本实施与试跑校审记录](测试脚本实施与试跑校审记录.md) | 任务3～4的脚本交付、逐例映射、真实试跑、工程问题修正和清理审计。 | 试跑证据与正式两轮验收分开。 |
| `runtime/` | 本轮临时 Compose 配置、秘密和恢复账本。 | 运行时创建并 Git 忽略；成功清理后删除，清理失败时保留最小恢复材料。 |
| `artifacts/` | 按 `run_id` 保存脱敏报告和证据。 | 运行时创建并 Git 忽略；默认保留，需由操作者按明确 run ID 管理。 |
| `tmp/` | 本轮合成的大输入和原始私有日志。 | 运行时创建并 Git 忽略；正常结束清除。 |
| `node_modules/`、`.cache/` | 本套件 npm 依赖、Chromium、npm/pip 和可选冻结镜像归档。 | 安装后创建并 Git 忽略；属于明示工具缓存，不当作业务残留。 |

## 环境准备与执行

前提：PowerShell 7.4+、Node.js 24 LTS、Docker Compose 插件 2.24.4+ 和 Docker Desktop/Linux Engine。所有 npm/浏览器缓存都限定在本目录，不安装全局依赖、不修改系统 PATH。

```powershell
npm ci --prefix tests/sesrag-persistent-session-workspace-test --cache tests/sesrag-persistent-session-workspace-test/.cache/npm
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/setup-tools.ps1
npm test --prefix tests/sesrag-persistent-session-workspace-test --cache tests/sesrag-persistent-session-workspace-test/.cache/npm
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Environment
```

`Environment`只验证基础设施和正式部署路径，报告明确`product_acceptance=not_run`。按需调试分类或试跑整轮：

```powershell
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session,context'
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode All
```

Selected/All先冻结本轮源码、依赖和镜像，再串行创建8类中的所选独立project。分类产品断言失败会保留逐例结果并继续其它分类；工程错误、清理失败和中断另行判定，不能按退出0的空报告通过。

上述命令按顺序执行，不要把套件`npm test`与Environment/Selected/All并行运行：恢复清理自测也会检查suite活跃锁，真实运行活跃时会被安全门禁提前拒绝，导致自测未到达其预期的故障注入分支。该拒绝不能通过删锁或放宽活跃进程保护绕过；待真实运行清理完成后再运行自测。

`Environment` 的 `-HoldSeconds` 只能用于有限观察，默认 0 且最终仍自动清理。若清理失败，查看 `artifacts/<run_id>/cleanup.json`，再按其中同一 `run_id` 调用 `-Mode Cleanup`；不要手工猜 Compose project 名称。

## 结果与资源边界

- 报告位于 `artifacts/<run_id>/`，每轮互不覆盖。它们是脱敏证据，不包含数据库凭据、API Key、完整环境变量、Docker inspect Env、完整 Prompt 或认证头。
- 每轮使用唯一 Compose project、独占网络和 PostgreSQL/uploads 命名卷；PostgreSQL 不向宿主发布端口，API、前端和 Provider 控制端口只绑定 `127.0.0.1` 的动态端口。
- 正常退出移除本轮容器、网络、卷、专有镜像 tag、runtime 和 tmp；不运行全局 Docker prune，不删除其它 project，也不删本轮 artifacts、npm/Chromium 缓存、Docker 基础镜像或共享构建缓存。
- 分类报告提供逐例passed/failed/blocked/not_run；不把健康探测、框架自测、Provider自检或空分类报告算作产品用例通过。

正式测试组织、分类范围和实施阶段见 [TEST-002](../../docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)。

## 用例、脚本与正式结果

[测试用例](test-cases.md)按 `session/context/model/run/workspace/compatibility/performance/quality` 八类组织，分别为18/13/8/30/18/13/2/6例。每例均关联测试点；末尾提供88点、29项FR/NFR与10项整体验收的覆盖表。V/E/B是设计可验证状态，不是执行结果：原19个受限点的前置已解除并完成正式测试；当前结论以逐例执行字段、原始JSON和测试报告为准。

任务1～2准备、任务3～4接入/试跑和任务5～6两轮正式执行均已完成。两轮run_id为`ws-20261023t020902z-9fa22610`、`ws-20261023t030707z-c936fff7`；原始目录互不覆盖。ready必须登记该类别全部设计ID，8类required不得降级。断言覆盖以实现、逐例证据与报告共同核对，不以104条注册数量代替结论；原R1/R2的UI_001曾登记归档呈现差异；本次已新增双视图和UI_015～018，修复是否通过以新回归证据为准。

### 分类脚本与用例对应

| 主入口（位于`specific_test_script/`） | 用例 | 主要观察层 |
| --- | --- | --- |
| `session-tests.mjs` | SES_001～SES_018（18例） | 正式API、明确回归节点、真实PG并发探针 |
| `context-tests.mjs` | CTX_001～CTX_013（13例） | 规划器/Worker、Provider实收hash、真实文档索引及Evidence身份 |
| `model-tests.mjs` | MOD_001～MOD_008（8例） | Profile仓储/冻结快照、真实HTTP、浏览器/PG/日志秘密扫描 |
| `run-tests.mjs` | RUN_001～RUN_030（30例） | Worker/队列/事务、Journal/SSE、真实API/Worker/PG/Redis停启 |
| `workspace-tests.mjs` | UI_001～UI_018（18例） | 真实Chromium与同源工作台、网络屏障、DOM/Storage |
| `compatibility-tests.mjs` | COMP_001～COMP_013（13例） | 真实v1/v2契约、PG旧版本专库迁移及安全回退 |
| `performance-tests.mjs` | PERF_001～PERF_002（2例） | 30样本p95、持久delta与DOM同宿主单调时钟区间 |
| `quality-tests.mjs` | QLT_001～QLT_006（6例） | 实际质量命令及负例、Provider、镜像层、外层清理审计 |

每例使用独立Thread/输入命名空间，PG竞态/迁移使用本分类白名单空专库；无共享业务seed SQL。分类内部故障须finally恢复，不能因上例留下停顿或停服导致后例假失败。重复使用底层回归节点是共享证据，不把一次整文件通过自动推导为所有细粒度用例通过。

工具准备：suite锁文件提供Playwright/Ajv，Chromium由setup-tools安装；Python工具镜像使用`requirements-tools.txt`（含`jsonschema[format-nongpl]`日期格式校验依赖）。前端独立ESLint/Vitest/Vue Test Utils/jsdom及三项工具探针见[前端说明](../../frontend/README.md)。固定API字面样本归属`tests/api/fixtures/`，同时用于DTO/JSON Schema正负断言。它们都不依赖旧验收目录。

### 可选：容器npm网络不稳定时预热公开依赖缓存

正常总入口不依赖此步骤。若宿主`npm ci`成功而Docker构建连续出现官方包下载`ETIMEDOUT`，先结束该轮并确认cleanup通过，再按下列命令预热；之后仍须重新完整运行Environment。仅允许本suite由上述安装命令创建的公开包`_cacache`，不要把用户`.npmrc`、整个用户缓存或runtime当build context。该步骤没有容器/镜像tag输出，缓存属于明示保留的Docker共享构建缓存，不修改产品代码或锁文件。

```powershell
npm cache verify --cache tests/sesrag-persistent-session-workspace-test/.cache/npm
docker buildx build --file tests/sesrag-persistent-session-workspace-test/compose/Dockerfile.npm-cache --build-context npm_public_cache=./tests/sesrag-persistent-session-workspace-test/.cache/npm/_cacache --output type=cacheonly tests/sesrag-persistent-session-workspace-test/compose
# 上两步退出0后，再按前文总入口运行，不把缓存预热当部署验收。
```

## 文件与职责

| 文件 | 主要职责 / 使用阶段 |
| --- | --- |
| `setup-tools.ps1` | 准备阶段：检查项目 Node 依赖、安装同锁文件版本的 Chromium；空页启动/关闭后保存 `.cache/tools-setup.json`。不安装系统 Docker，不改 PATH。 |
| `compose/.env.workspace-test.example` | 配置变量职责模板；秘密和路径占位为空，不能直接拿来启动。真实插值文件由总入口写到本轮私有 runtime。 |
| `compose/Dockerfile.python-tools`、`requirements-tools.txt` | 构建阶段：以本轮 app 镜像为基底，补装精确版本 Python 测试依赖与套件工具；词表继承 app 的构建预热资产。 |
| `compose/Dockerfile.npm-cache` | 可选准备阶段：将已校验的本项目公开npm缓存bind预热到BuildKit的`sesrag-frontend-npm`，不复制进镜像、不输出tag；仅用于Docker下载不稳定时，不是验收入口。 |
| `tooling/preflight.mjs` | 运行前检查 Node24、8 类 manifest、3 份 Schema、浏览器和源码/工具指纹；排除秘密、依赖目录和运行数据。 |
| `tooling/case-catalog.mjs`、`case-catalog.test.mjs` | 准备/接入阶段：从正式用例清单解析8类108例，校验ready全类覆盖、必需分类和脚本真实路径；自测覆盖注册拒绝与受限故障控制。 |
| `tooling/orchestrator.mjs` | 全生命周期编排、锁/账本、构建/迁移/Profile/就绪、技术探测、采证、清理及最终报告；由 PowerShell 唯一入口调用。 |
| `tooling/compose.mjs` | 统一显式 file/env/project 参数、已退出一次性服务查询、动态回环端口发现和有界就绪等待。 |
| `tooling/resources.mjs` | Engine/所有权/路径校验、独立残留扫描和受约束清理；禁止全局 prune。 |
| `tooling/process-registry.mjs` | 子进程身份、超时、输出限额和先脱敏后发布；不按进程名批量杀进程。 |
| `tooling/category-runner.mjs` | 后续分类进程调用、逐用例身份/集合/结果/证据协议校验；缺报告或 exit0 空结果不能通过。 |
| `tooling/product-category.mjs`、`product-scripts.test.mjs` | 分类实现公共层：从用例/矩阵生成追溯字段、逐例中文输出和脱敏证据、回归/PG/runtime合并；自测校验108例注册和性能判据。 |
| `specific_test_script/*-runtime.mjs`、`support.mjs`、`browser-support.mjs` | 产品执行阶段：真实API/Provider屏障、动态业务数据和Chromium支持；不拥有Docker删除权限。 |
| `specific_test_script/probes/case-selectors.json`、`backend-regression-probe.py` | 容器阶段：逐例明确指定pytest节点，保存JUnit、日志和节点观察，不通过测试矩阵文字机械推断结果。 |
| `specific_test_script/probes/test_case_supplements.py` | 补充用例边界：摘要归属、精确预算、检索故障、不可变Profile、凭据撤销、草稿/资源上限。 |
| `specific_test_script/probes/postgres-cases.py`、`pg_migration_plugin.py` | 容器阶段：真实PG独立专库中的并发发布与旧事实迁移；用`db-admin.py`验证实例/归属并删除专库。 |
| `specific_test_script/probes/pg_case_supplements.py`、`test_migration_supplements.py` | PG补充：同Branch竞争、六类迟到写回、提交错误回滚、skip locked取消回收、旧Document/Chunk完整保留及独立Context事实回退保护。 |
| `specific_test_script/probes/quality-probe.py`、`scan-images.py`、`secret-facts-probe.py` | 质量阶段：实际后端命令及反例、镜像所有层和PG事实秘密检查；只发布命中数量/安全定位。 |
| `tooling/report.mjs`、`schemas/*.json` | 结果/上下文契约、中文摘要、JSON 和证据索引；环境、产品、清理分别判定。 |
| `tooling/frozen-builds.mjs` | 后续 Selected/All 的本轮镜像归档/指纹校验与同 ID 复用；Environment 不要求导出大归档。 |
| `tooling/runtime-inventory.mjs`、`.test.mjs` | 采证阶段：保存App/工具实际解析依赖及hash、镜像ID、宿主/前端Node、PowerShell/Compose版本和报告/工具缓存占用；不保存环境全集。 |
| `tooling/environment_probe.py` | 只读技术探测：配置、离线词表、PG vector/迁移 head/4 Profile、Redis、Provider 双端口/身份/鉴权、API/Worker、前端同源页面/health。 |
| `tooling/prepare-fixtures.py` | 将确定性的长历史、Markdown/XSS、最小合法 DOCX 生成到本轮 tmp，记录字节/字符/token/hash；不创建业务事实。 |
| `tooling/db-admin.py` | 仅本轮白名单专库管理；核验 `system_identifier`、服务端 `cluster_name`、run 后缀和所有权 comment，拒绝开发库、非空 probe 库和强制断连接。 |
| `fixtures/provider/server.py` | 独立受控 HTTP/SSE/Embedding 服务，支持有界慢流、错误、停顿屏障、按请求序号定向场景和脱敏观测；不新增产品测试路由。 |
| `tooling/provider-selftest.py` | Provider 协议自测；`--standalone` 为本机临时服务，默认由工具容器连接 Provider。支持 `--base-url` / `--control-url`；凭据仅从私有环境读取。 |
| `tooling/lifecycle-drills.mjs` | 环境框架专项：真实基础服务就绪后主动抛出预期部署故障，用于复核采证/finally/残留审计；不是产品测试脚本。 |
| `tooling/*.test.mjs`、`tooling/test_environment_tools.py` | 运行器/Compose/安装入口/Provider/素材及安全保护的框架自测；不填产品用例结果。 |

## 配置与输入边界

所有 `WS_TEST_*` 插值仅由总入口生成，不加载根 `.env`。`WS_TEST_RUN_ID/OWNER_TOKEN/PROJECT/CATEGORY` 标识本轮资源，`WS_TEST_REPO_ROOT/TMP_DIR` 定义受控挂载，`WS_TEST_*_IMAGE/SOURCE_DIGEST` 用于构建/恢复身份。专库固定用户名/数据库名，密码、DSN、虚假模型 Key 和 Provider 控制 token 各自随机生成；端口默认 `0`，由 Docker 原子分配，仅向回环发布。不要直接复制模板并填开发凭据。

不需要统一业务 seed SQL：当前没有用户账户基线，Thread/Branch/Run/Task/Event/文档事实应由后续用例经正式 API/Worker 创建。共享固定输入仅为 `fixtures/baseline.json`、4 个无秘密 Profile 和安全文档。环境阶段只执行正式迁移/Profile 导入和创建空 probe 专库→确认空库→删除→确认不存在，不执行 `session_pg_probe.py` 的业务竞态验证。

Provider 的推理端口 8080 与控制端口 8081/凭据分离。控制协议使用 `schema_version=1`，场景字段以服务实现和 `provider-selftest.py` 为准；预备 normal/slow/stall/empty/malformed/disconnect/context-limit/http-error，`stall-after-first-delta` 是 stall 的别名。控制屏障支持收到请求、首片、等待释放和完成；不得用固定 sleep 代替后续业务用例的同步条件。并发最多 32、场景最多 64、Embedding 单批最多 256；观测默认100条，本套件Compose显式设置2000条（配置合法范围1～2000），总字节仍≤8MiB，每请求消息摘要最多512条，超过容量明确标截断。屏障仅认本次配置后、尚未finished的request_seq，不能误取历史waiting_release标识。Mock/受控向量只证明协议、错误和身份，不证明检索效果。

## 恢复清理与保留项

```powershell
# 用失败现场/summary中真实run_id替换示例；不重新部署。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Cleanup -RunId ws-20261021t010203z-a1b2c3d4
```

活跃运行拒绝被Cleanup接管；不可捕获强停后，使用同一run_id恢复，并在结束再次独立扫描容器（含已停止/one-off）、网络、卷和专有tag。Docker不可查询不等于零残留。报告和工具缓存有意保留，大小见runtime-inventory及环境记录；本轮未实施可选 `-PurgeToolCache`，传入会明确退出2，不能据此声称缓存已删。不得全局prune或按进程名称批量终止。

私有`session.json`丢失时，Cleanup可读取本轮artifact内的`recovery-ledger.json`或既有`cleanup.json`中的ledger并核验资源身份。全部恢复账本都丢失时会明确拒绝并退出2，不仅凭标签自动删除；需先恢复可信账本或人工核对，不能声称已完成清理。因此资源未清完前不要删除该run的artifact恢复材料。

源码指纹包括前端生成脚本/测试/质量配置、后端/契约/迁移和本套件可执行工具、Schema、fixture、锁文件。`test-cases.md`是注册门禁输入，明确参加指纹；须在正式两轮结束后再回填结果，运行中或冻结两轮之间不要修改。其余套件纯说明Markdown排除（fixture Markdown仍包括），运行数据/依赖/Secret也排除；回填环境说明不会冒充产品源码变化。

本次已在两轮清理结束后回填，因此当前树重测应使用不带旧`-FrozenBuild`的All/Selected重新冻结。旧验收源码白名单归档及冻结镜像缓存已保存，精确重放要求见[测试报告§2](测试报告.md#2-两轮执行基线与证据)；不要绕过指纹或覆盖开发工作区。artifacts、工具缓存及冻结镜像归档是明确保留项，运行容器、卷、runtime/tmp已清理；保留证据不等于磁盘零占用。

故障控制统一用`tooling/orchestrator.mjs --resource-helper`，通常允许api/worker/provider的inspect/start/stop/restart；仅run分类额外允许PG/Redis停启和本分类Worker的SIGKILL。API动态端口在restart/start后重新发现，调用方更新地址再有界等待就绪。quality的镜像/事实/公开面扫描和全轮生命周期结算由受限白名单执行，不授予分类任意Docker命令。全轮恢复清理按project数量分配有界预算（最多20分钟），每个命令仍有超时，只有最后独立审计通过才移除runtime/tmp和锁。quality前置只有当轮QLT_002/003真实passed才能ready；Environment仍为pending，安装成功不改变产品验收状态。

补充采证模块：`specific_test_script/run-evidence-runtime.mjs`负责RUN_009/010/011/012/029的真实阶段、首片、分页/游标和关联证据；`probes/run-facts.py`只读当前分类PG，用独立READ COMMITTED连接读取指定Run，不写业务数据。workspace另有受限helper仅临时切换非默认`ws-http-b:1`的enabled/disabled，UI_011结束在finally恢复；不授予任意SQL。

workspace分类将`WS_TEST_RETRY_BASE_DELAY`设为15秒（其余分类2秒），在真实首片后用`partial-disconnect`制造HTTP分块未终结的传输错误，再停Worker保持已产生的retry_waiting，刷新必须核对该状态的实际GET及DOM，finally恢复Worker。该场景只扩展测试Provider，不改产品状态机。UI_005的分支详情加载会真实移除分支控件，此时仅该子场景使用浏览器内现有store action驱动第二选择；其余以实际控件交互，不能把不存在的控件冒充可点击。

分类进程经私有环境变量`WS_EVIDENCE_SECRETS`取得四类动态凭据的脱敏集合，仅用于首次写入公开证据前清洗；该集合不进入context、argv、浏览器或报告，普通子进程默认清除。镜像扫描逐块检查各层并用有界内存spool处理嵌套层，避免一次把大镜像层整块读入内存。

质量探针的契约负例通过`referencing.Registry`注册本地所有契约，禁止自动联网解析`$ref`。探针失败时分类仍发布已有命令日志，并把缺失命令结算失败/未执行，继续独立的前端与清理检查；不因一个探针异常丢掉整类其余结果。`tests/integration/test_v2_run_execution.py`两项HTTP测试改由`request.getfixturevalue`取得原fixture，只为兼容工具镜像固定Ruff版本的F811规则，不改测试输入或产品逻辑。

UI_011不可用模型使用原生`disabled`、`:disabled`、明确原因和真实Home/上下箭头遍历共同验证，确认所有可用项可选、禁用项被跳过且不提交业务POST。Playwright 1.64.1对`label`内`option.isDisabled()`的返回值存在判定偏差，不能以该方法或可强制赋值的`selectOption`替代浏览器原生行为；真实Chromium正例及移除disabled负例列入框架自测。RUN_015/024共享`support.mjs:releaseThenRestore`，即使Provider释放失败也必须执行服务恢复/就绪检查，原失败继续向外传播。
