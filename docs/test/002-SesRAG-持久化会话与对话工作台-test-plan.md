# TEST-002：持久化会话与对话工作台测试实施方案

- **编号**：002
- **方案版本**：v1.7（追加任务5～6同源两轮正式结果与证据入口）
- **对应项目版本 / 分支**：v0.2 / `sesrag_v0.2`
- **状态**：已实施；任务5～6同源两轮All各104通过，清理通过、退出0，312个用例执行字段已回填；补充差异仍见缺陷报告，不宣称PRD零差异
- **日期**：2026-10-23
- **适用范围**：本机 Docker Linux 容器中的 PRD-002 隔离临时测试环境、总入口、基础工具/数据、报告和资源清理闭环。
- **依据**：[PRD-002](../prd/002-SesRAG-持久化会话与对话工作台-PRD.md)、[实施 ADR（当前路径002）](../adr/002-sesrag-persistent-session-workspace-implementation-plan.md)、[简要实施记录](../pr/002-SesRAG-持久化会话与对话工作台-PR.md)、[实施结果调研](../pr/002-SesRAG-持久化会话与对话工作台-实施结果调研.md)、[接口文档](../接口文档.md)。
- **执行规范**：[仓库通用开发规范](../项目开发和修改的通用执行规范.md)、[测试文件通用规范](../../tests/实施测试文件时的通用规范.md)、根目录 `AGENTS.md`。
- **当前核对基线**：HEAD `595eb04`，已有上一任务调研及导航的未提交修改；本方案依据当前源码核对。实施与正式执行时须重新记录实际提交、工作区差异、源码指纹和工具版本。
- **实施/验证结果**：环境历史见[环境实施与验证记录](../../tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)，正式两轮结果见[测试报告](../../tests/sesrag-persistent-session-workspace-test/测试报告.md)、[缺陷报告](../../tests/sesrag-persistent-session-workspace-test/缺陷报告.md)及已回填用例。下文保留原环境设计、职责边界与实施路线，其设计语态不表示当前未完成；当前事实以本字段和结果报告为准。
- **准备/接入历史**：任务1～2补齐契约样本、前端工具及总入口，见[准备核验记录](../../tests/sesrag-persistent-session-workspace-test/测试准备与总入口核验记录.md)；任务3～4脚本/试跑和修订见[脚本校审记录](../../tests/sesrag-persistent-session-workspace-test/测试脚本实施与试跑校审记录.md)，其阶段未回填正式结果。任务5～6已独立完成两轮All，未拼接这些不同源码历史重跑。

## 1. 决策摘要与方案边界

本轮单独建设 `tests/sesrag-persistent-session-workspace-test/`，不恢复、不依赖、不扩展旧 `tests/demo-smoke/`。采用**独立 Compose 文件 + 复用应用构建定义 + 每次运行独立资源所有权**：应用使用当前仓库的 API/Worker 和前端 Dockerfile；测试编排另外定义端口、卷、受控 Provider、工具容器和初始化顺序，不合并根开发 Compose，不复用开发 `.env` 或数据卷。

宿主使用 PowerShell 7 总入口与项目内 Node 工具，Python/数据库辅助工具放在本轮工具镜像中。主入口负责预检、构建、部署、就绪、分类调度、报告、销毁和残留审计。后续分类只接收运行上下文，按协议报告结果，不拥有整个环境的销毁权限。

为避免故障注入、Profile 变更、文档索引和任务残留干扰其他分类，选择**每个分类独立子 Compose project、串行执行、分类结束立即清理**。每轮最多构建一次应用镜像（也可载入已冻结镜像），各子环境共用该轮专有镜像tag；网络、数据库卷、上传卷、Provider记录和临时地址分别独立。代价是重复启动/迁移，但更适合本机功能验收的可复现性。分类内部按后续用例隔离数据，不通过整体重置掩盖同一用例内的恢复行为。

### 1.1 本方案后续实施的交付范围

1. 专属目录、说明文档、工具安装/检查入口和锁文件。
2. 独立 Compose、应用/工具镜像构建接线、随机凭据、动态本机端口和独占临时存储。
3. 正式迁移、显式 Profile 初始化、合成文档/输入素材和受控 HTTP/SSE Provider。
4. 总调用脚本、分类注册/调用/结果契约、框架自测、环境技术探测。
5. 运行上下文、中文日志、JSON/Markdown报告、证据采集、失败/中断清理与恢复清理。
6. 后续具体测试脚本的编写约定和接入计划。

### 1.2 不在本方案实施范围内

- 不编写或执行具体产品分类测试脚本；本测试环境方案本身不直接实施测试点矩阵和测试用例。这些内容由独立后续任务完成；当前矩阵、用例和8类脚本已分别交付，具体状态及真实结果以各自文档和脚本校审记录为准。
- 不修复产品代码、API、状态机、数据库结构或交互缺陷，不通过测试专用产品路由绕过业务流程。
- 不把上一轮全部 Demo 用例、旧149用例或旧26分类机械搬入本轮；只为 PRD-002 需求及其依赖的兼容/RAG事实准备验证条件。
- 不将生产认证/RBAC、多租户、工具调用、跨会话语义记忆、知识库版本发布、真实模型质量或生产 SLO 纳入验收承诺。
- 不承诺所有外部供应商均可用；默认受控本地 Provider 不使用真实Key、不产生外部模型费用。
- 原方案编写任务不创建实际脚本或容器；本次独立环境实施任务按阶段A～E落地基础设施和真实演练，但仍不编写产品分类用例/脚本。

环境技术探测、Provider自检和运行器自测属于测试基础设施实现，可在实施本方案时编写；它们不等同于 FR/NFR 分类脚本，不能填充产品用例通过数。

### 1.3 与现有文档的关系

ADR当前文件名为002，正文仍有003；简要PR及README也有历史编号/测试入口残留，识别时以真实文件路径和PRD-002为准。本方案按用户最新要求，替换其中“把本轮验收合入旧demo-smoke”的**测试组织方式**，不改变ADR的产品设计、不降低PRD验收标准。

本文件是新独立验收的实施方案；简要PR记载的旧专项/两轮all属于历史记录，不能冒充本方案执行结果。旧失败和blocked可作为后续设计线索，不直接计入新用例统计。状态只能依据本套件真实证据更新，不能因旧历史结果而改成已验收。

## 2. 目标、完成层级与技术取舍

### 2.1 可预估目标

实施本方案后，在具备Docker Linux Engine的本机，执行一个总入口即可得到：

- 与开发环境隔离、可重复启动的PostgreSQL/Redis/API/Worker/前端/受控Provider。
- 正式迁移head、可用的Mock及受控HTTP模型配置、有限工具依赖和可追溯配置摘要。
- 未接入产品分类时，能够运行环境验证并完成报告与清理；报告明确 `product_acceptance=not_run`。
- 分类接入后，无需改写生命周期即可按选择运行，收集每用例结果并在故障后仍尝试清理。
- 成功、失败、可捕获中断都有清理证据；不可捕获终止有明确恢复入口，不虚报自动零残留。

### 2.2 三个不同的完成层级

| 层级 | 本方案实施时是否完成 | 判断口径 |
| --- | --- | --- |
| 方案完成 | 本次完成 | 范围、目录/文件、数据、协议、生命周期、清理和路线明确，完成文档校审。 |
| 环境实施完成 | 本次已完成 | 最终安全修复后两次独立正常环境闭环、修复前历史三轮、失败清理和恢复清理演练均有真实证据；没有具体产品用例也可达成。 |
| PRD正式验收完成 | 后续用例/脚本接入后完成 | 全需求覆盖、开发质量检查、PG/浏览器/Compose证据及至少两轮同源All；失败、blocked、未运行不能算通过。 |

`Environment`模式退出0只表示基础设施闭环通过；即使部署健康，也不能表示持久会话、取消竞态或流式恢复已经验收。

### 2.3 选型及替代方案

| 决策 | 采用 | 不采用的方案及原因 |
| --- | --- | --- |
| 编排 | 专属独立Compose，复用应用Dockerfile | 不叠加根Compose override，避免固定8000/5173和开发卷配置继承、环境变量误用。 |
| 分类隔离 | 每分类独立子project，串行，镜像每轮共享 | 不在一个长期库反复清业务表；避免Profile/知识库/故障残留难以恢复。 |
| 运行器 | PowerShell 7 + Node项目工具 | 不同时维护Windows/Linux两套生命周期脚本；不要求宿主Python或全局pytest。 |
| 浏览器 | 宿主项目内Playwright Chromium | 无需给容器挂Docker socket或运行特权浏览器；仅回环端口访问前端。 |
| 模型/检索输入 | 应用Mock + 本地受控OpenAI-compatible HTTP/SSE，真实tiktoken | 不用快速Mock证明慢流、认证/HTTP错误和真实请求字段；不依赖公网供应商才能验收。 |
| 数据准备 | 正式迁移/显式Profile导入；业务事实后续经API创建 | 不导入整份开发库，不用固定SQL预造成功Run/终态/租约来“通过”行为验收。 |

## 3. 环境前提、版本和工具准备

### 3.1 本机前提

- 支持Windows PowerShell 7.4+ + Docker Desktop Linux Engine；或Linux + Docker Engine + PowerShell 7.4+。Windows PowerShell 5.1不是受支持入口。
- Docker Compose插件2.24.4+，支持JSON配置输出、端口查询、project标签及`down --volumes --remove-orphans`；Docker守护进程必须是Linux容器模式。
- 宿主Node.js 24 LTS；具体Node/PowerShell/Compose/Engine版本在preflight记录。前端运行镜像仍沿用项目Dockerfile的Node20，工具Node24与受测前端运行时分别记录，不能混称。
- 推荐Docker可用4核、8GiB内存及至少15GiB可用磁盘；记录实际值。低于推荐不自动断言产品性能失败；镜像/服务启动不足时报环境blocked，性能未满足测量前提单列。
- 首次安装允许拉取镜像、npm/Python依赖和构建时词表；API/Worker请求路径不隐式下载tokenizer。离线执行需事先准备镜像和缓存，缺资产应明确失败。
- 同一suite只允许一个活跃总入口（文件锁含PID/开始时间/run_id）；不影响另一个开发Compose。清理只针对该轮已登记资源。

不检查或输出根`.env`内容，不使用开发数据库可访问性作为测试前提，不从用户全局Python/浏览器缓存猜测工具已准备好。

### 3.2 工具和依赖归属

| 工具 | 安装/位置 | 本方案实施与后续用途 |
| --- | --- | --- |
| PowerShell、Docker、Compose、Node24 | 宿主已安装；preflight检测版本和可执行路径 | 主入口与容器生命周期。若Docker未安装/无法由当前用户启动，报告实际阻碍及需用户处理内容。 |
| Playwright、Ajv（含format校验） | suite自己的`package.json/package-lock.json`和`node_modules/`；精确版本与lockfile固定 | 浏览器能力自检、分类结果/上下文JSON校验，后续浏览器/API契约分类复用。 |
| Chromium | suite的`.cache/ms-playwright/`，由PLAYWRIGHT_BROWSERS_PATH显式指向 | 首次安装后空页启动/关闭自检；后续真实浏览器，不使用全局任意Chrome版本。 |
| Python3.12、pytest/asyncio、Ruff、mypy、aiosqlite及应用依赖 | `compose/Dockerfile.python-tools`构建的工具镜像，依赖文件锁定 | 环境探测、fixture准备、PG专库管理；后续开发回归与探针。无需宿主`.venv`。 |
| jsonschema等Python契约工具 | suite的`requirements-tools.txt`精确版本固定，包含`format-nongpl` extras；pyproject开发依赖也声明格式检查器 | 后续契约验证；不能只用TS检查替代Schema动态校验，非法date-time必须实际拒绝。 |
| 前端ESLint、Vitest、Vue Test Utils、jsdom | 后续任务1～2已补到frontend自身package/lock和独立配置，Node范围见frontend README | 后续quality入口；三项toolchain探针仅验证SFC/DOM/定时器，不代替工作台组件回归。 |
| tiktoken0.8.0 / cl100k_base | 复用应用依赖/镜像预热资产，工具镜像也有同资产 | 检查离线加载、合成预算素材；缺失/损坏不联网兜底。 |

`requirements-tools.txt`固定工具层精确版本；构建后保存`pip freeze`，应用依赖仍遵守当前pyproject范围，记录解析版本和镜像ID。suite的package-lock固定Node依赖，使用`npm ci`。后续复验使用该轮镜像与依赖指纹；若应用依赖重解析改变，不声称两轮完全同源同环境。

计划实施的准备命令（在仓库根目录，Windows/Linux统一由pwsh调用）：

```powershell
npm ci --prefix tests/sesrag-persistent-session-workspace-test --cache tests/sesrag-persistent-session-workspace-test/.cache/npm
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/setup-tools.ps1
```

setup-tools只安装本项目Chromium、检查已有依赖和生成工具自检记录，不安装系统Docker、不改系统PATH、不启动产品环境。Linux缺少浏览器系统库时列出Playwright检测的缺失项及该发行版安装命令；需要系统管理员操作才报告用户处理，不反复重试浏览器。工具镜像构建由总入口完成。

## 4. Compose拓扑、配置与隔离

### 4.1 服务组成及职责

| 服务 | 镜像/启动依据 | 存储、依赖和访问边界 |
| --- | --- | --- |
| postgres | `pgvector/pgvector:pg16`，记录实际digest | 独占postgres_data卷；主库`sesrag_workspace`、测试用户sesrag；不发布5432到宿主。 |
| redis | `redis:7-alpine`，记录digest | 仅临时容器可写层，不配持久化卷、不发布6379；通知/Worker readiness，不代替PG。 |
| provider | 本轮Python工具镜像，运行fixture服务 | 容器内8080；推理端点和控制端点分开，只有控制端口发布到127.0.0.1随机端口。状态仅内存，重启有新实例身份。 |
| migrate | 本轮应用镜像，正式`alembic upgrade head` | PG健康后执行一次；必须exit0且实际revision匹配预期，不启用auto_create_schema。 |
| profile-init | 同一应用镜像，正式`backend.tools.sync_model_profiles` | migrate成功、Provider健康后导入合成Profile JSON；exit0后API/Worker才启动。不是任意SQL初始化服务。 |
| api | 复用`docker/api/Dockerfile`构建 | 专属DSN/owner/虚假Key；共享本子环境uploads卷；8000仅映射127.0.0.1动态端口。 |
| worker | 与API相同image ID，正式`python -m backend.workers.main` | 同DSN/配置/uploads；默认1个Worker，禁止固定container_name/重复WORKER_ID，未来分类可注册第二Worker。 |
| frontend | 复用`docker/frontend/Dockerfile` | VITE_API_BASE_URL为空、API_PROXY_TARGET=`http://api:8000`；5173映射127.0.0.1动态端口，HTTP/SSE/health同源。 |
| python-tools | `compose/Dockerfile.python-tools`；Compose tools profile，默认按需`run --rm` | 用于探测、输入准备、只读事实查询、专库管理；主机无PG端口也能经服务名访问。仅对已经登记且仍存活的工具容器允许exec，不要求常驻工具服务。不可挂Docker socket。 |

应用镜像只在api服务定义build，migrate/profile-init/worker引用同轮专有image tag；避免每个服务分别构建而获得不同解析依赖。先构建api，再构建以其为base的工具镜像，最后前端；基础镜像pull发生在构建阶段，不在分类之间重新pull。

工具镜像以构建参数指向本轮应用image，补装工具依赖和suite辅助代码；provider使用同工具image，不新增公网服务。Python工具容器需要读源码时，只读挂载`backend/`、`migrations/`、`contracts/`、`tests/unit/`、`tests/api/`、`tests/integration/`、pyproject及alembic配置到`/work`对应位置，`working_dir=/work`、`PYTHONPATH=/work`。不得整个挂载含根`.env`的仓库；写入只能到本轮artifact/tmp映射或容器临时目录。

挂载tests时也要保留其实际包标记（如存在`tests/__init__.py`则单独只读挂载）；当前为namespace目录，不因规划示例假造该文件。集成探针通过实际可解析的模块/脚本入口调用，并在工具自检中确认导入来源位于`/work`，不误加载镜像或第三方的同名tests包。

应用API/Worker/前端使用镜像中的冻结源码，非宿主热挂载。报告分别记录镜像与受测源码/工具挂载指纹；若运行前后源码变化，取消“同源”声明，不用镜像旧代码和宿主新模块混合解释结果。

### 4.2 配置基线和变量来源

| 配置 | 本方案固定口径 | 目的 |
| --- | --- | --- |
| DSN / PG密码 | 每轮强随机，DSN密码URL编码；容器内`postgres:5432/sesrag_workspace` | 不使用开发DSN；不提交、打印或写公开报告。 |
| OWNER_ID | `workspace-test-owner`，合成基线 | Thread隔离仍是同owner下Thread/Branch隔离，不声称多租户认证。 |
| MOCK_PROVIDER | `false` | Embedding/legacy生成指向本地受控HTTP，便于后续注入网络/协议故障；新v2生成仍按各Run选择的Profile。 |
| MODEL_BASE_URL / MODEL_NAME / EMBEDDING_MODEL_NAME | `http://provider:8080/v1` / `ws-http-a` / `ws-embedding-384` | 满足Settings真实Provider组合校验；不指向公网。 |
| MODEL_API_KEY | 每轮随机虚假哨兵，API/Worker服务端相同；config_ref仍`env:MODEL_API_KEY` | 测协议和泄密，不使用真实凭据。控制端另用独立token。 |
| VECTOR_DIMENSION / RAG_TOP_K / CHUNK_SIZE / CHUNK_OVERLAP | `384/5/800/120` | 保持现有检索空间；Profile换模不得改变Embedding。 |
| TASK_LEASE_TTL / HEARTBEAT / MAX_ATTEMPTS / RETRY_BASE_DELAY / DEADLINE | `30/10/3/2/600` | 基线沿用产品默认；stop_grace_period至少30秒，高于Worker20秒宽限及释放预算。 |
| WORKER_SHUTDOWN_GRACE / QUEUE_POLL / SSE_POLL / HEALTH_PROBE_TIMEOUT | `20/1/0.2/2`（秒） | 不为了验收变快偷偷改租约/流式/业务阈值。 |
| AUTO_CREATE_SCHEMA | `false` | 只走正式迁移，不能由create_all绕过旧库验证。 |

所有Compose插值变量使用本轮命名空间`WS_TEST_*`，模板为`compose/.env.workspace-test.example`，无真实秘密、每项有含义/必填/生成方说明。主入口生成`runtime/<run_id>/compose.env`；Compose显式指定该env文件、project-directory和file，不自动加载根`.env`。子进程剔除外部同名WS_TEST变量及COMPOSE_FILE/COMPOSE_PROJECT_NAME等冲突变量，避免宿主环境覆盖专用env；保留必要Docker连接配置并校验实际context/Engine身份。

密码、虚假Key和控制token各自使用加密随机源生成不少于32字节的base64url文本，避免env插值字符歧义；DSN仍正确URL编码。runtime目录仅当前操作者可读写（Linux目录0700/文件0600，Windows限制为当前用户所需ACL），错误信息不回显生成值。

未来分类确需短租约/缺Key/不同设置时，必须登记scenario配置、重建该子环境受影响服务、记录差异并在分类完成后销毁；不能用这些缩短配置的测量结果替代默认性能验收。总入口基础就绪判断在故障注入前完成，不把预期故障当成部署失败。

### 4.3 隔离与所有权约束

1. `run_id`使用UTC时间加随机后缀，如`ws-20261021t010203z-a1b2c3d4`；格式固定、不可含路径字符。project使用长度受限的`sesrag-ws-<随机后缀>-<分类>`；Environment模式分类名为env。不能手动传任意开发project。
2. 子project采用Compose默认独占网络和命名卷，卷禁止external、禁止固定跨project的name；禁止容器挂宿主开发data/uploads、根`.env`和Docker socket。
3. 回环端口由Docker原子分配，使用`host_ip:127.0.0.1`、`published:"0"`与target指定；再通过`compose port`查询实际地址。不先找空闲端口再绑定；拿不到明确映射则失败，不回落8000/5173。
4. 新建容器、网络和卷携带本轮owner token/PRD/run_id标签并登记资源账本，主入口检查Compose project标签一致。镜像用`sesrag-ws-app:<run_id>`、`sesrag-ws-frontend:<run_id>`、`sesrag-ws-tools:<run_id>`，不覆盖开发tag；其归属以本轮tag、image ID及账本核验。冻结镜像跨轮复用时不修改镜像内容或强加新run_id标签，构建标签只记录稳定构建指纹，避免为换标签而破坏同image ID约束。
5. 每轮启动前保存仅包含资源身份的既有资源快照；结束确认测试资源零残留且既有资源未被删除。原有构建缓存、基础镜像和明确共享工具缓存不归本轮销毁范围，必须单列保留。
6. suite运行锁只限制本suite；不同PRD环境或开发Compose可共存。默认串行，不并行运行性能与故障注入。

## 5. Provider、数据和数据库准备

### 5.1 受控Provider是环境支撑，不是产品测试脚本

`fixtures/provider/server.py`运行独立进程，不向产品API添加任何测试路由：

- 推理端口8080：`POST /v1/chat/completions`按兼容协议输出SSE和`[DONE]`；`POST /v1/embeddings`返回稳定、有限、384维向量；`GET /health`返回实例身份和就绪状态。
- 控制端口8081：`GET /health`；带独立Bearer token的`PUT /control/scenario`、`POST /control/reset`、`GET /control/observations`。只绑定测试容器网络/宿主回环映射，前端不代理控制端，不得到token。
- 预备有界场景：normal、slow、stall-after-first-delta、empty、malformed、disconnect、context-limit、http-error；场景参数限制片段数、延迟/停顿、HTTP码及响应字节上限。缺场景/参数非法明确400，不猜默认成功。
- normal分多片输出，slow/stall支持“已收到请求/已发首片/等待释放”的控制屏障；后续脚本据屏障同步，不靠固定sleep猜测Run已经进入某状态。
- 按模型标识和本地场景记录request序号、role/正文长度/hash、max_tokens/生成参数及安全哨兵匹配。保留可控虚假输入供内存断言，不在默认日志/公开artifact存完整Prompt、Authorization或系统指令。
- 环境初始化只做Provider协议自检、重置和模型配置准备；对Run状态、恢复、重试等业务断言留给后续分类。Provider自身故障为harness_error，产品面对故障的行为不符才是产品failed。

控制请求使用schema_version=1，至少定义kind、目标model、分片/间隔/停顿、HTTP状态、请求序号匹配和屏障释放；初版限制最多8192片、单片65536字节、整响应8MiB、单次停顿180秒、观测最多100条/合计8MiB。允许构造超过产品限额但有界的输入，不能把Provider自己的限额误报为产品限额生效。超过观察容量明确返回截断/溢出标记，不静默丢掉必要记录；场景切换前须确认上次请求已结算或重置。

Embedding可以复用当前MockEmbeddingProvider的确定性算法，但由真实HTTP端点返回；这只证明协议/空间一致和证据身份，不证明语义检索质量。Provider记录与场景每个子project独立，分类重启Provider时必须重新确认instance_id。

### 5.2 统一基线与按用例动态事实

本方案**不新增通用业务seed SQL**。理由是当前单owner没有账号表，Thread/Message/Run/Task/Event均应由业务路径创建；全局预造失败/成功记录会使后续断言脱离真实执行。

采用以下固定素材：

| 素材 | 准备方式 | 使用阶段/边界 |
| --- | --- | --- |
| `fixtures/baseline.json` | 固定合成owner、Profile身份/预算预期、fixture版本和模型标识 | 实施阶段A定义，部署/上下文/报告校验使用；不包含RunID或真实用户数据。 |
| `fixtures/model-profiles.json` | 保留迁移种入的mock-default@1、mock-small@1及其不可变配置；另加ws-http-a@1、ws-http-b@1 | profile-init正式导入；默认仍mock-default，HTTP两项可用，生成模型标识不同。 |
| HTTP Profile配置 | a窗口8192/输出1024，b窗口2048/输出256；cl100k_base、每消息4/请求2 token框架开销、calibration_version=`workspace-fixture-v1`、安全余量128/摘要512 | 受控协议服务的明确计数口径，不宣称适合真实供应商；两个enabled HTTP选项均使用受信Secret alias。 |
| `fixtures/documents/history-sentinel.md`、`evidence.txt` | 无隐私的中文/英文哨兵及稳定行号，带fixture版本/hash | 后续RAG分类经正式上传/索引；本方案不预造document/chunk或索引成功事实。 |
| `tooling/prepare-fixtures.py` | 确定种子生成长历史片段、Markdown/XSS文本、最小合法DOCX至`tmp/<run_id>/inputs/`；用当前计数器输出长度/token/hash清单 | 素材准备与框架检查；不创建产品Thread/Run、不执行业务用例。用例具体阈值组合后续决定。 |

可用Profile列表须在部署后确认启用状态及唯一默认；导入任何字段冲突必须失败，不能删旧配置再“成功”。本轮JSON无Secret值，base_url仅为`http://provider:8080/v1`。随机Key只写runtime注入。Profile禁用/换默认等可变情形由未来model分类自行构造，基线不全局禁用选项。

按用例创建的数据：Thread/Branch/消息/Run、队列任务、摘要、Event、上传索引和重试记录均由后续脚本通过正式API/Worker推进；每例使用唯一命名空间/幂等键，并保留对象身份。共享知识库的RAG用例须在自己的子环境内控制上传集，不能继承前一分类文档。数据库只读查询用于核对事实，不通过UPDATE状态/lease/generation造出行为结果。

### 5.3 PG探针与迁移专库

`tooling/db-admin.py`只在本轮postgres容器内创建/删除已登记专库：

- 主应用库由PostgreSQL容器初始化，只有正式migrate写Schema。
- `sesrag_session_probe_<随机后缀>`为保留的`tests/integration/session_pg_probe.py`提供**新空库**；使用独立`SESSION_PG_PROBE_URL`，不传主库DSN。探针自行执行正式迁移，禁止预先种Profile/业务表破坏其空库检查。
- `sesrag_ws_migration_<随机后缀>`供后续compatibility分类做0003旧事实/冲突/升级/受限回退；用例夹具和具体旧事实脚本不在本方案实施。
- 主入口登记namespace、project/PG容器身份、数据库名后才创建；脚本使用参数化连接和安全SQL标识符，拒绝非白名单前缀、非本轮后缀、非预期PG实例和非空probe库。
- PG探针保留数据库的原设计不变；本轮运行器负责收集脱敏摘要后清理专库，最终还销毁整个专属postgres_data卷。开发库永远不在清理候选中。

本方案实施时验证“创建一个空probe库→确认无业务表→删除并核验”；不调用真实业务探针完成产品竞态验收。专库无法删除时保留问题清单，最终卷销毁可消除物理数据；报告同时说明库级清理问题和最终物理资源结果。

## 6. 目录结构及文件职责

根路径统一为 `tests/sesrag-persistent-session-workspace-test/`，下文“suite”均指它。实施后README须说明各入口、阶段、模式、工具安装和所有runtime/artifact保留策略。

```text
tests/sesrag-persistent-session-workspace-test/
├── README.md
├── test-plan.md
├── 环境实施与验证记录.md      # 阶段E实际运行后新增
├── run-workspace-tests.ps1
├── setup-tools.ps1
├── package.json
├── package-lock.json
├── requirements-tools.txt
├── tooling/
│   ├── orchestrator.mjs
│   ├── compose.mjs
│   ├── resources.mjs
│   ├── frozen-builds.mjs
│   ├── preflight.mjs
│   ├── category-runner.mjs
│   ├── report.mjs
│   ├── process-registry.mjs
│   ├── environment_probe.py
│   ├── prepare-fixtures.py
│   ├── db-admin.py
│   ├── provider-selftest.py
│   ├── test_environment_tools.py
│   ├── compose-entry.test.mjs
│   ├── frozen-builds.test.mjs
│   └── self-tests.test.mjs
├── schemas/
│   ├── run-context.schema.json
│   ├── category-result.schema.json
│   └── run-summary.schema.json
├── compose/
│   ├── docker-compose.workspace-test.yml
│   ├── .env.workspace-test.example
│   └── Dockerfile.python-tools
├── fixtures/
│   ├── README.md
│   ├── baseline.json
│   ├── model-profiles.json
│   ├── documents/
│   │   ├── history-sentinel.md
│   │   └── evidence.txt
│   └── provider/
│       └── server.py
├── specific_test_script/
│   ├── README.md
│   └── manifest.json
├── runtime/                  # 运行后生成；凭据/恢复上下文，Git忽略
├── artifacts/                # 运行后按run_id生成；脱敏证据，Git忽略
├── tmp/                      # 运行后生成；结束删除，Git忽略
├── node_modules/             # 安装后生成；Git忽略
└── .cache/                   # 项目浏览器/npm缓存；Git忽略
```

**本环境方案的实施不创建**`test-cases.md`或`session-tests.mjs`等具体产品分类脚本，也不创建空白用例文件伪装准备完成。测试点矩阵单独维护于[测试点设计与需求覆盖矩阵](../../tests/sesrag-persistent-session-workspace-test/测试点设计与需求覆盖矩阵.md)；用例与脚本按后续接入计划及`specific_test_script/README.md`接入。

### 6.1 预计新增文件的职责和阶段

阶段A～E的执行顺序见§13。

| 文件/目录 | 主要职责 | 首次使用阶段 |
| --- | --- | --- |
| `README.md` | 安装、目录图、总入口模式/命令、结果解读、清理/恢复、工具缓存清理 | A建骨架，E回填实测命令。 |
| `test-plan.md` | 后续用例和分类脚本接入路线、依赖顺序与待完成清单；需求覆盖矩阵单独维护，不与本文环境总方案混淆 | A；后续接入持续更新。 |
| `run-workspace-tests.ps1` | 唯一生命周期主入口，参数校验、run_id/所有权、阶段编排、try/finally、最终退出码 | D，E闭环验证。 |
| `setup-tools.ps1` | 只安装suite浏览器/检查Node依赖，记录工具自检结果 | B。 |
| `package.json/package-lock.json` | 本suite Node依赖及setup/selftest命令，npm ci可重复安装 | A/B。 |
| `requirements-tools.txt` | Python工具固定版本；应用仍装当前pyproject的dev工具范围并记录最终解析集 | B工具镜像。 |
| `tooling/compose.mjs` | 显式Compose参数、短命令超时、端口发现、阶段化启动/健康/日志收集；检查每次native exit code；实现时以Node单一逻辑替代原规划`lib/compose.psm1` | C/D。 |
| `tooling/resources.mjs`、`orchestrator.mjs` | 运行锁、资源账本、project/标签/路径校验、分类与最终清理、幂等恢复；实现时以Node单一逻辑替代原规划`lib/resources.psm1`，PowerShell只做公开参数入口 | C/D，E破坏路径自测。 |
| `tooling/frozen-builds.mjs` | 后续Selected/All镜像ID归档、源码/归档指纹核验和同ID挂本轮tag，Environment不强制归档 | D，阶段F实际分类接入时使用。 |
| `tooling/provider-selftest.py`、`test_environment_tools.py`、`compose-entry.test.mjs`、`frozen-builds.test.mjs` | Provider协议、Python工具保护、Compose编排/入口和冻结镜像工具自测，不是产品分类脚本 | B～E。 |
| `tooling/preflight.mjs` | 版本/路径/manifest/schema/浏览器/源码指纹和工具检查；不输出秘密 | B/D。 |
| `tooling/case-catalog.mjs`、`case-catalog.test.mjs` | 后续任务1～2新增：解析正式104例清单、验证ready整类覆盖与必需类别、拒绝脚本越界；包含受限故障控制自测 | 分类接入前及任务1～2核验。 |
| `tooling/category-runner.mjs` | 有界调用分类、传context路径、记录子进程、校验输出与退出码 | D；先用框架自测fixture验证，未来才调产品分类。 |
| `tooling/report.mjs` | 脱敏、JSON Schema校验、中文汇总、原子写临时再rename、证据索引/hash和总判定 | D/E。 |
| `tooling/process-registry.mjs` | 记录PID/创建时间/父子关系/可执行身份；只终止经核验的本轮子树 | D/E。 |
| `tooling/environment_probe.py` | 数据库/扩展/revision、离线encoding、模型基线与地址可访问性技术探测 | C/E。 |
| `tooling/prepare-fixtures.py` | 确定性输入生成及token/长度/hash清单；不创建会话事实 | B/C。 |
| `tooling/db-admin.py` | 仅本轮PG专库创建/空库检查/只读诊断/删除，不暴露公网PG | C/E，后续PG分类。 |
| `tooling/self-tests.test.mjs` | manifest/超时/结果协议/脱敏/路径保护/资源所有权等运行器自测，不算产品用例 | B～E。 |
| `schemas/run-context.schema.json` | 后续分类可读取的安全运行上下文格式 | A/D。 |
| `schemas/category-result.schema.json` | 单分类逐用例结果协议 | A/D。 |
| `schemas/run-summary.schema.json` | 顶层环境/产品/清理/源码状态及各分类汇总协议 | A/D。 |
| `compose/docker-compose.workspace-test.yml` | 以上独立服务、网络、卷、动态回环端口和标签；不extends开发Compose | C。 |
| `compose/.env.workspace-test.example` | 只含非Secret默认值和由入口生成的必填占位说明 | A/C。 |
| `compose/Dockerfile.python-tools` | 以本轮应用镜像补工具和Provider辅助代码，安装阶段准备依赖 | B/C。 |
| `compose/Dockerfile.npm-cache` | 任务1～2额外新增的可选工具：将项目内已校验公开npm缓存预热到BuildKit，不复制进镜像/不输出tag；处理宿主可下载而容器官方包超时的准备条件 | 仅下载不稳定时的准备阶段，命令与边界见suite README。 |
| `fixtures/README.md`、`baseline.json`、`model-profiles.json` | 数据边界、可重复基线、Profile导入及用途，不存业务终态 | A/C。 |
| `fixtures/documents/history-sentinel.md`、`evidence.txt` | 后续历史/检索可追溯合成原文 | B，分类接入后使用。 |
| `fixtures/provider/server.py` | 环境用受控Provider、屏障和安全观测 | B/C。 |
| `specific_test_script/README.md` | 分类接口、脚本语言/数据隔离/日志/禁止越权/结果约定 | A/D。 |
| `specific_test_script/manifest.json` | 8个分类的注册意向，初始planned/未绑定脚本；后续显式接入 | A/D。 |
| `runtime/`、`tmp/`、`artifacts/` | 临时配置/输入/报告，详见§10～11；目录由运行时创建 | D/E。 |
| `环境实施与验证记录.md` | 回填本方案A～E的真实环境命令/结果、负例与恢复清理证据，不替代产品验收报告 | E实测后新增。 |
| `测试准备与总入口核验记录.md` | 后续任务1～2的工具/数据准备、额外新增修改、主入口核验及当轮环境证据 | 任务1～2，不替代104例正式验收。 |

不新建顶级工程目录。helper可以在实施时为单一职责拆分，但须更新本表/README并保持主入口、context与结果协议一致，不能无记录另建平行入口。

### 6.2 已有文件的修改范围

| 文件 | 本次编写方案时 | 后续实施本方案时 |
| --- | --- | --- |
| 本TEST-002文件 | 新增并校审 | 回填版本/实施状态/环境验证记录链接，不能将其改成产品全通过报告。 |
| `docs/test/README.md`、根`README.md` | 新增本方案导航，区分当前方案与旧历史结果 | 补新suite实际入口/目录用途，修复此次涉及的旧验收导航；未运行命令不得标通过。 |
| `.gitignore`、`.dockerignore` | 不修改 | 加入suite的runtime/artifacts/tmp/node_modules/.cache及运行env，保证秘密/大文件既不跟踪也不进入镜像构建上下文。验证跟踪文件中没有误留。 |
| 产品`backend/`、`frontend/src/`、`contracts/`、`migrations/`、根`docker-compose.yml`、应用Dockerfile/根`.env.example` | 不修改 | 原则不修改；本suite独立定义工具/配置。发现产品缺陷记录，不能借环境实施绕过或偷改产品行为。 |
| 旧`tests/demo-smoke/` | 不恢复 | 不恢复、不挂载、不引用其依赖。 |
| `tests/api/test_v2_schemas.py`、前端Lint/组件工具相关文件 | 原环境搭建轮不修改；后续任务1～2显式补齐工具前置 | 契约fixture/格式依赖与前端质量工具、配置、lockfile、README独立修复，见§12及准备记录；不实施产品分类脚本。 |
| `docker/frontend/Dockerfile` | 原环境搭建轮沿用 | 任务1～2实跑复现两次npm下载超时后，显式改为锁文件npm ci、BuildKit公开包缓存与有界下载重试/并发；不改业务启动命令，不忽略安装错误。缓存不进镜像且按共享构建缓存保留。 |
| `docs/adr/002-…`等历史记录 | 不改写历史结果 | 如同步测试组织说明，仅注明改用本TEST-002，不反向改写既有测试结果或产品不变量。 |

## 7. 总入口、上下文和分类接入协议

### 7.1 主入口参数

| 参数 | 约定 |
| --- | --- |
| `-Mode` | `Environment`（默认）、`Selected`、`All`、`Cleanup`四值，拒绝未知值。 |
| `-Categories` | Selected必填的逗号分隔分类ID字符串；其它模式禁止。只从manifest白名单选择，不接收shell命令。 |
| `-RunId` | 仅Cleanup必填，从已有账本恢复；正常执行由总入口生成，不让用户覆盖run_id碰撞资源。 |
| `-FrozenBuild` | Selected/All可用，值为已有冻结构建指纹，不能是任意宿主路径；从suite缓存读取经校验的镜像归档/manifest，避免两轮复验重解析依赖。 |
| `-HoldSeconds` | 仅Environment可用，默认0，范围0～3600；就绪后有限保留供手工观察，计时到或可捕获取消后仍finally清理。 |
| `-PurgeToolCache` | 仅Cleanup可用，要求suite无活跃运行；额外清理项目安装依赖/浏览器缓存，默认不启用。 |

**实施差异（显式保留）**：本轮没有实施可选的 `-PurgeToolCache` 删除能力；传入该参数会明确退出2，不能当作已执行缓存清理。正常运行的容器/卷/临时数据清理不依赖此开关。工具缓存及冻结归档有意保留并记录大小；后续独立实现缓存清理时必须补无活跃运行、祖先链接、路径和删除身份保护。本表其余运行参数已接入；不以无条件递归删除缓存来凑齐方案。

固定阶段预算：构建最长1800秒、每子环境就绪最长300秒、分类默认900秒（manifest可声明至1800秒）、整轮分类总预算7200秒、收集120秒、清理每子环境/最终各180秒。单条Docker诊断命令默认30秒，构建命令使用独立长预算。上述是测试运行器预算，不修改产品Run的60/120/600秒等限额；native命令失败必须读取退出码，不能只依赖PowerShell ErrorAction。

Selected/All首次构建后将3个image ID以**无run专属tag引用的归档**保存到`.cache/frozen-builds/<构建指纹>/images.tar`，同目录`manifest.json`记录源码/工具/依赖指纹、image ID和归档hash。后续`-FrozenBuild`先校验当前受测/工具源码一致及归档hash，再载入同ID并挂本轮tag；校验失败退出2，不静默重建，载入也不得恢复上一轮run专属tag。不能重新解析一套依赖冒充同构建。归档不得包含Secret/运行数据，使用不可覆盖的内容指纹目录，容量计入工具缓存。每轮仍删除本轮tag/卷，冻结归档保留供下一轮；清缓存会移除归档，届时需重新准备并记录基线。Environment模式不要求导出此复验归档。

Environment始终只创建一个env子project，做技术探测并清理；Selected只运行登记的分类；All要求全部required分类已接入且覆盖门禁完整；Cleanup不重新构建/部署/执行产品，重复运行应幂等。

### 7.2 运行对象与身份

| 对象 | 必要字段和职责 |
| --- | --- |
| RunSession（总运行） | schema_version、run_id、mode、UTC开始时间、源码/依赖指纹、Docker context/Engine身份、owner_token、项目列表、总结果。与产品Run不是同一对象。 |
| EnvironmentLease（子环境） | environment_id、category、project_name、资源标签、镜像tag/ID、端口、卷/网络/容器ID、初始化阶段、ledger状态。 |
| CategoryContext（安全上下文） | run_id/environment_id/category、api_base_url/frontend_base_url/provider_control_url、artifact/tmp相对目录、fixture版本、resource_helper入口和期望case_ids。 |
| RuntimeSecrets（私有） | PG密码/DSN、虚假MODEL_API_KEY、Provider控制token等，保存在runtime私有文件或受控子进程环境，不进入CategoryContext和公开报告。 |
| CategoryResult | 分类和逐用例状态、测试目标/实际观察、证据引用、耗时与异常归因。 |
| ResourceLedger | 创建意图、实际资源身份、归属标签、进程身份、清理动作/结果及剩余项；清理前写盘，强停后可恢复。 |

上下文文件写到`runtime/<run_id>/<category>/context.json`，只含安全字段；对应的secrets文件同目录权限受限。脚本需要DSN或控制token时，从运行器显式授予的子进程环境/私有文件读取，禁止通过命令行参数/日志传递。子进程不得继承开发MODEL_API_KEY或DATABASE_URL。

总运行账本固定为`runtime/<run_id>/session.json`，资源增删账本为`runtime/<run_id>/resource-ledger.json`，每次动作原子更新；创建子环境时由总入口生成该子project的Compose插值文件，不把一个project的端口/资源身份复用给另一分类。owner_token是非Secret的资源随机标识，随脱敏账本摘要发布到artifact以便恢复；不等同于Provider控制token。

### 7.3 分类注册和执行

manifest每项含`category`、`required`、`status=planned|ready`、`script`、`timeout_seconds`、`case_ids`、`requirements`。初始8类均planned、script=null、case_ids=[]；这是明确未接入，不是空脚本通过。

- 分类ready前，后续必须已有测试点/用例、唯一case_ids、有效脚本、依赖/前提和结果协议检查。具体脚本统一放`specific_test_script/`，优先`.mjs`，必要时`.ps1`；不混合无关分类。
- Node分类调用为`node <登记脚本绝对路径> --context <context.json绝对路径>`；PowerShell分类为`pwsh -NoProfile -File <登记脚本> -ContextPath <context.json>`。脚本无业务参数命令拼接。
- All在分配容器前检查全部required分类及case_ids；未接入直接coverage不完整、退出3并生成报告，不启动无意义环境，也不输出产品passed。Selected选中planned同样拒绝，未知分类为参数/harness错误。
- 调度默认串行；每分类使用全新子project。前一分类failed但其环境已清理可继续；无法确认清理成功则停止新部署，剩余分类not_run。失败结果保留，不自动重跑直到变绿。
- 同一分类内用例尽量独立创建数据和重置Provider场景；前置失败影响的用例标blocked，不能把未执行的其它用例标failed或passed。破坏服务的分类必须经资源helper登记操作，不得碰别的project。
- 具体脚本不可`down -v`整个环境、清空数据库表、删除artifact或安装全局依赖。可以通过经校验的helper检查/启动/重启/停止本子环境api/worker/provider、申请专库或第二Worker；仅run分类额外可控制postgres/redis供RUN_024故障验证。必须核验当前run/owner/活跃project/Engine并记录动作；恢复后有界等待readiness，动作返回不代表服务已就绪。
- 八类必须required=true；ready的case_ids须与`test-cases.md`第3节本类别的完整集合相等（共104例），由case-catalog与preflight校验，缺失/错类/未知ID或真实脚本路径越界在部署前拒绝。planned的All/Selected报告设计清单的not_run数量，不按空登记表统计为0。
- quality前置只有当轮经结果协议校验的QLT_002/003均passed才标ready；Environment及未执行quality的Selected为pending。工具已安装或manifest已ready不作为通过证据。

### 7.4 分类结果契约

分类完成时在自己的artifact目录原子写`result.json`，并将逐例中文过程信息写`console.log`。最少字段：

| 层级 | 字段与规则 |
| --- | --- |
| 外层 | schema_version=1、run_id、environment_id、category、开始/结束时间、status、cases、evidence。身份必须与context一致。 |
| 每用例 | case_id、test_point_ids、requirement_ids、中文title/type、status、expected、actual、reason_code、reason、evidence_paths、duration_ms。case_id必须在登记集合内且唯一；实际观察不能为空。 |
| status | passed、failed、blocked、not_run；外层另允许harness_error。未满足前提为blocked，不把暂不可验证当skip通过。 |
| evidence_paths | 只允许本轮artifact内相对路径，文件必须存在；禁止绝对路径/`..`逃逸和指向上一轮报告。 |

分类退出码：0仅全部登记用例passed；1存在业务断言failed；2工具/协议错误；3前提受限或未运行。进程exit0但缺报告、空cases、缺登记case、重复/额外case、错误run_id、证据缺失、汇总与子项不符均判harness_error。出现failed又blocked时仍保留全部子项，外层failed；runner不能吞掉非零码。

中文日志每例带case_id、目标、关键步骤/对象ID、实际观察和判定；Secret/完整Prompt不写。expected可以先由用例定义，actual必须来自本次实际数据，不能复制expected充数。本方案不在此预设具体case编号。

## 8. 完整生命周期与失败行为

### 8.1 正常执行路线

```text
校验工具/范围/注册 → 生成run_id与账本 → 构建本轮镜像
    → 对每个已选分类（Environment只取env）：
        新建子project与私有配置
        → PostgreSQL/Redis/Provider就绪
        → 正式迁移 → Profile初始化
        → API/Worker/前端就绪 → 写安全context
        → 环境技术探测 / 后续分类执行
        → 收集日志/结果/证据 → 清理子环境 → 核验残留
    → 移除本轮镜像tag/临时文件 → 最终清理审计 → 汇总报告/退出码
```

依赖顺序必须显式分阶段，不能单纯对全部服务`up --wait`后把migrate退出容器当作部署失败；也不能API已200就忽略Worker未就绪。

### 8.2 阶段检查与报告

| 阶段 | 必须观察的条件 | 失败处理 |
| --- | --- | --- |
| 预检 | 工具版本、Linux Engine、磁盘、manifest/schema、源码范围、允许路径、无冲突活跃锁 | 写preflight失败，不启动容器；cleanup=not_required。 |
| 构建 | 专用tag创建意图已登记；build成功、镜像ID/源码/依赖和词表资产可核对 | 保留脱敏构建日志；删已产生的本轮tag；不运行分类。 |
| 基础服务 | pg_isready成功、真实SELECT1、pgvector扩展资产可安装；Redis ping；Provider两个health与instance_id匹配 | 300秒内有界轮询，超限environment blocked，保留容器状态/日志后清理。 |
| 迁移 | migrate exit0、实际alembic_version等于当前代码head（基线0006_v2_run_guards） | 记录revision/安全错误，不使用create_all/跳迁移兜底；后续not_run。 |
| Profile | profile-init exit0；4个基线Profile身份/预算/可用性及唯一默认符合基线 | 不静默删表/换默认；环境未准备好，不继续业务用例。 |
| 应用就绪 | /health/live；/health/ready HTTP200且PG/Redis ready、worker_count≥1；前端同源页面/health可读；浏览器启动关闭自检 | Worker未知不判正常就绪；记录健康原始安全字段，不能只看容器running。 |
| 执行 | Environment只技术探测；其它模式按context执行真实分类 | 分类超时终止已登记进程，标harness_error；业务failed按实记录。 |
| 收集 | 分类报告/日志/证据校验、容器状态、受控请求摘要、源码结束指纹 | 不因收集异常跳过finally；缺必要证据不能判passed。 |
| 清理 | 本轮资源全部按账本审计，公共资源未误删；报告最后更新cleanup状态 | 失败退出4，留恢复账本/最小私有配置及剩余ID；不能打印“零残留”。 |

pgvector扩展在主库迁移创建，因此基础PG阶段先检查扩展可安装/镜像支持，迁移阶段再确认主库`vector`已安装；不得在主库抢先建业务Schema。环境探测可以验证工具、表/revision和端点，不创建Thread/Run来替代产品用例。

### 8.3 异常、中断和恢复

- 总入口使用`try/finally`，每次资源创建先写意图再执行，完成后补资源ID；即使启动半途失败，也能按run/project标签补发现账本未回填资源。
- 日志、报告或某个探测失败不会跳过其它必要收集与清理；若Docker暂不可用，清理结果为unknown/failed，不能因查询返回空或命令报错而认为没有资源。
- 用户可捕获Ctrl+C：停止调度，取消/终止已登记分类进程，有限收集后清理；最终码130，原已失败用例保留。Windows控制台无法可靠注入Ctrl+C时不伪造信号测试通过，可用可控进程终止验证恢复路径并将信号覆盖单列受限。
- 强杀主进程、Docker服务停止、断电不能保证finally执行。下次运行先发现未完成账本并报告；操作者用Cleanup模式恢复，不直接开始新一轮压上去。若Docker context/Engine身份不同，拒绝在新Engine执行原账本清理，待回到原目标后重试。
- 在收集阶段中断留下的中间报告标incomplete；恢复清理只补清理证据，不把未执行业务用例改成passed。最终报告以临时文件+原子替换写入，避免半截JSON被当成通过结果。

### 8.4 总退出码和结果层次

| 退出码 | 含义 |
| --- | --- |
| 0 | 当前选择范围满足要求且清理通过；Environment只对应环境通过，Selected只对应所选分类，不代表全PRD。 |
| 1 | 已执行产品用例有真实断言失败。 |
| 2 | 配置/工具/结果契约/源码变化/报告缺失等harness错误。 |
| 3 | 环境前提受限、required分类未接入、覆盖不完整或必需项not_run。 |
| 4 | 本轮清理失败/未知，有残留或无法核验，优先于其它非中断码。 |
| 130 | 可捕获用户取消且清理成功；清理未成功则4，并保留interrupted原因。 |

优先级：4 → 130 → 2 → 1 → 3 → 0；报告保留全部原因，不用一个退出码覆盖真实业务失败/blocked数。无资源创建时cleanup=not_required也可满足预检阶段的清理要求，但不能给环境部署passed。

## 9. 后续分类及需求覆盖边界

本节只定义分类责任和环境能力，不是测试点文档或测试用例；所有分类脚本在后续任务编写。required初始8类，不以“分类名存在”代替覆盖；后续每个FR/NFR要关联具体测试点和case_id。

| 分类ID / 未来脚本 | 主要责任 | 本方案提供的条件 |
| --- | --- | --- |
| session / `session-tests.mjs` | Thread生命周期/分页、Branch路径、幂等、隔离与输入身份；不重复执行浏览器DOM断言 | 独立PG/owner、API、稳定Profile；case动态API数据。 |
| context / `context-tests.mjs` | 历史实收、预算裁剪、摘要来源/回退、选中Evidence与最终Citation | 计数器/词表、长文本和证据素材、受控Provider观测。 |
| model / `model-tests.mjs` | Profile选择/禁用/版本、Snapshot、Secret及生成/Embedding配置冻结 | 双Mock+双HTTP、导入工具、受控HTTP错误/观测和环境重建helper。 |
| run / `run-tests.mjs` | Journal/SSE、自动/显式重试/重生成、取消竞态、失租/重启与有限资源/错误 | 慢/停顿/故障Provider、服务操作helper、专属PG probe库；不把SQLite当PG锁。 |
| workspace / `workspace-tests.mjs` | 真实浏览器恢复/切换/流式投影、交互状态和Markdown/XSS | 项目Chromium、同源前端、可控网络/流和截图trace。 |
| compatibility / `compatibility-tests.mjs` | 15条v2/9条适配v1/5条保留入口的契约及旧事实迁移/回退 | 当前contracts、独立迁移库、正式Alembic、后续旧事实fixture。 |
| performance / `performance-tests.mjs` | 健康基线下提交p95与持久首delta到DOM延迟 | 单Worker/单用户独立环境、精确时间/误差与至少30样本；禁止同时故障注入。 |
| quality / `quality-tests.mjs` | 开发pytest/Ruff/mypy、类型漂移/typecheck/build、前端Lint/组件等正式门禁 | 工具容器/Node和质量结果接入；§12依赖修复后才能完整执行。 |

性能方法必须由后续脚本落实：至少30个独立消息提交，以宿主单调时钟测发起到收到Run身份的时长，p95用nearest-rank（排序后第ceil(0.95×N)个），保存全样本和失败请求，不只挑成功/最快样本。提交传输错误单列故障和样本完整性，不能静默重发后替换原样本。

首delta测量不能直接把Event.created_at/occurred_at当作commit时间：当前代码在提交前赋值。采用Provider屏障先确认观察器/订阅就绪，再用独立PG可见性查询将首delta提交时点夹在[L,U]（上次不可见查询开始、首次可见查询结束，映射到宿主单调时钟）。每次查询须取得新的READ COMMITTED语句快照或使用独立短事务，不能反复读取REPEATABLE READ长事务的旧快照。浏览器首次DOM显示时点也用校准区间[D低,D高]；延迟区间为[max(0,D低−U), max(0,D高−L)]。上界≤1秒才判满足，下界>1秒判超限，其余为测量不足；必须保留查询/时钟校准样本，不将上游首token等待算进该延迟，也不把不确定区间判通过。

### 9.1 功能需求覆盖关系

| PRD需求 | 后续主分类（必要协同） | 本方案落实的可测前提 |
| --- | --- | --- |
| FR-TH-01 | session（workspace） | API/归档状态与浏览器选择基线；归档混排现状保留待测，不改预期迁就实现。 |
| FR-TH-02 | session（context/workspace） | 每分类新库，双Thread/兄弟分支哨兵与迟到HTTP可控观测。 |
| FR-MEM-01 | context（run/workspace） | PG事实、ModelRequest观测、API/Worker重启和浏览器刷新入口。 |
| FR-BR-01 | session | 分叉/路径API、只读事实查询，不复制祖先的数据准备方式。 |
| FR-BR-02 | run（session/workspace） | 同输入新Run/Branch、自动attempt和幂等的完整链路环境。 |
| FR-MOD-01 | model（workspace） | 4项基线Profile及安全列表、双HTTP模型标识。 |
| FR-MOD-02 | model | 显式Profile导入、重建服务/Key环境、Provider实收及冻结检索条件。 |
| FR-STR-01 | run（workspace） | 慢流/停顿、持久Event与DOM观测通道。 |
| FR-STR-02 | run（workspace） | SSE/HTTP分页、浏览器断开控制、回放证据；无真实cancel替身。 |
| FR-REC-01 | workspace | 真实Chromium、同源UI和localStorage/刷新控制。 |
| FR-REC-02 | run | 真实PG、Worker重启/失租/迟到屏障，专库探针接入点。 |
| FR-RUN-01 | run（workspace） | queued/active可控Provider和服务边界，Task/Run只读核对。 |
| FR-OBS-01 | workspace（run） | 安全日志/事件/模型/上下文投影、无隐藏思维与工具占位。 |
| FR-CTX-01 | context | 真实tiktoken/Mock可区分、预算输入生成、mandatory超限无调用观测。 |
| FR-CTX-02 | context | 摘要/来源元数据、同分支复用与失败注入的工具能力；不预造摘要成功。 |
| FR-MD-01 | workspace | Markdown/XSS合成输入、真实DOM/脚本执行观察。 |
| FR-RAG-01 | context（workspace） | txt/md/docx素材、正式上传索引、稳定384维HTTP Embedding、证据身份。 |
| FR-ERR-01 | run（model/compatibility） | HTTP错误/超时/空流/坏流/DB与Redis服务操作，安全错误证据。 |

### 9.2 非功能需求覆盖关系

| PRD需求 | 后续分类/门禁 | 环境要求与证据边界 |
| --- | --- | --- |
| NFR-SEC-01 | model、compatibility、quality | 随机虚假Secret哨兵，公开字段/报告/日志扫描，原始私有文件不进artifact。 |
| NFR-SEC-02 | workspace | 真实DOMPurify执行结果，不以字符串检查代替浏览器XSS。 |
| NFR-ISO-01 | session、context、workspace | 路径/摘要/迟到投影哨兵；不扩为多租户认证。 |
| NFR-REL-01 | run、compatibility | 真实PG连接/事务屏障、Journal/终态事实和回滚；SQLite仅开发回归。 |
| NFR-REL-02 | run、workspace | 进程重启、lease回收、观察恢复，不承诺供应商token位置续算。 |
| NFR-PERF-01 | performance | p95提交≤1秒；首持久delta到DOM≤1秒；至少30独立提交、测时误差和全部样本记录。 |
| NFR-CAP-01 | context、run | 冻结窗口/输出/事件/时长边界、终态预留，运行器预算不能修改产品额度。 |
| NFR-OBS-01 | run、workspace | Run/Thread/Branch/Task/generation/seq和Profile可关联；安全观测摘要。 |
| NFR-TEST-01 | quality及全部分类 | 可控Provider、计数器、PG/Compose/浏览器；先关闭§12工具链依赖缺口。 |
| NFR-MIG-01 | compatibility | 独立空库/0003旧事实复制库/冲突库，不操作开发库、不走create_all。 |
| NFR-DEP-01 | 环境门禁、quality | 使用正式应用构建/迁移/Worker命令，部署/退出/资源审计；无Secret进镜像/前端。 |

PRD第9节十项总验收分别由：1=session/run/workspace；2=context；3=model/workspace；4=run/workspace；5=run；6=run/session；7=session/context；8=context/workspace；9=run/model/compatibility；10=quality和全部分类报告共同证明。环境验证只为它们提供条件。

### 9.3 条件受限和不应误报的内容

- 环境正常但尚无分类脚本：所有产品用例not_run/覆盖待接入，不能passed。
- 真实供应商可用性、语义检索/摘要质量、生产SLO、跨租户认证不属于默认本轮验收；不能因没有这些资源阻塞本地协议/状态测试，也不能宣称由Mock证明。
- 浏览器离线、Windows Ctrl+C注入、时钟误差等必须按实际能力确认；优先用真实Chromium离线API/受控代理或Linux容器进程信号。只能测连接关闭时须写明无法证明完整离线场景，不能换场景而保留原用例passed。
- 历史Run UI可操作范围、归档混排与默认选择、摘要候选窗口等调研差异已纳入独立测试点矩阵，保持PRD目标和实际观察分开；没有明确偏离证据前不自行扩需求。
- 正式All默认要求本地可验证required项无failed/blocked/not_run；确需范围豁免时保留非全通过状态和明确批准依据，不能自动降低required属性换取exit0。

## 10. 报告、日志和证据收集

### 10.1 输出组织

```text
artifacts/<run_id>/
├── summary.json                 # schema约束的最终机器结果
├── summary.md                   # 中文总览；标明模式/范围，产品是否已测
├── environment.json             # 工具/硬件、镜像、源码/依赖指纹、非Secret配置
├── source-manifest.json         # 受测产品/工具文件hash，前后对比
├── cleanup.json                 # 各子project和最终清理审计
├── evidence-index.json          # 证据相对路径、大小、hash、截断说明
├── console.log                  # 主入口脱敏中文阶段日志
└── categories/<category>/
    ├── context.public.json
    ├── result.json              # Environment使用技术探测result，无产品cases
    ├── summary.md
    ├── console.log
    ├── diagnostics/             # 健康、状态/revision、PG事实/Provider安全摘要
    ├── services/                # Docker服务日志，必须脱敏
    └── browser/                 # 后续分类截图/trace/HAR，按脱敏规则采集
```

所有结果分run_id保存、不覆盖历史；Environment和产品CategoryResult使用不同Schema分支（环境结果`checks`，产品结果`cases`），不能用健康检查伪装业务case。

summary必须分别含`environment_status`、`product_acceptance=not_run|partial|passed|failed|incomplete`、`cleanup_status`、`source_unchanged`、`frozen_build`（构建指纹，无归档时null）、selected/required分类、passed/failed/blocked/not_run/harness_error统计、原始退出码、最终退出码与未执行原因。Environment只能product_acceptance=not_run；Selected最多partial；All只有required覆盖完整、无失败/受限、证据完整且清理成功时passed。

### 10.2 必需证据和脱敏

- 构建、工具版本、image ID/digest、迁移revision、启动和清理阶段状态；API/Worker/frontend/provider及依赖服务的必要日志/退出信息。
- 后续产品用例保留Thread/Branch/Run/Task、attempt/generation、Event seq、ContextPlan/Profile和证据身份；Provider只保存安全角色/长度/hash/哨兵匹配，完整实收可在受控进程内断言。
- API错误保留安全code/detail与HTTP状态，禁止保存原DSN、环境变量全集、Docker inspect Env、完整Compose展开配置或原始HTTP认证头。
- 原始日志/浏览器trace在私有runtime内先处理；动态虚假Secret、DSN密码、宿主绝对路径和认证字段清洗后才发布artifact。不得先写入公开console/artifact再事后补擦。trace/HAR无法可靠清洗则关闭该内容采集，保留安全截图/控制台/网络元数据并注明原因。
- 诊断单文件默认上限10MiB、单分类100MiB、单轮500MiB；达到上限保留头尾和截断标记。用例必要证据缺失或截断影响判断时不能passed，不静默省略证据。避免无界docker logs/Provider请求全文撑满磁盘。
- 源码指纹覆盖backend/frontend源码与构建配置（含前端tests、ESLint/Vitest配置）、contracts、migrations、suite工具/fixtures/锁文件；`test-cases.md`作为分类覆盖门禁输入也参加指纹，其余suite纯说明Markdown不参加。排除runtime/artifacts/tmp/node_modules/.cache、Secret文件及前端构建产物。记录HEAD及dirty文件路径/hash，不能只记录HEAD忽略未提交源码。正式两轮完成后才回填用例结果，冻结运行之间不改用例清单。

收集期间Docker停止或某个服务日志不可读须逐项记失败，不生成空白“全部日志已收集”。最终报告在清理后更新，不能在down之前提前固定cleanup=passed。

## 11. 清理、零残留核验和恢复清理

### 11.1 资源所有权和删除顺序

1. 停止新分类与本轮浏览器/脚本子进程，先采集有限诊断；进程按PID+创建时间+父子关系+可执行身份校验，拒绝仅凭PID或名称杀进程。禁止`taskkill /IM node.exe`等全局操作。
2. 对当前子project执行明确file/env/project-directory/project的`docker compose down --volumes --remove-orphans --timeout 30`；包含migrate/profile-init和tools运行容器。one-off工具容器使用`--rm`并显式name/owner标签登记，硬杀遗留由标签回收。
3. 清理仍存的本轮额外Worker/专库工具容器及注册资源；任何label不符的对象拒绝删除并报告。数据库物理文件和上传在独占卷内，卷删除是释放它们的必要步骤，只有down无卷删除不合格。
4. 所有子project结束后移除本轮3个专有镜像tag。删tag前核验绑定image ID与账本一致；不强制按image ID删除共享引用。不使用`--rmi all`删基础镜像，不运行全局`docker system/image/volume/builder prune`。
5. 正常清理成功后删除`tmp/<run_id>`、`runtime/<run_id>`及临时浏览器profile/原始未脱敏文件。删除前将恢复所需的非Secret资源身份写到artifact清理报告；路径必须解析为suite下对应run_id子目录。
6. 清理失败时，保留最小runtime账本及必要私有配置用于恢复，明确报告其仍存在和用途；大临时文件能安全移除的先移除。不得为了声称目录干净先删掉唯一恢复凭据。Cleanup成功后再清除这些私有文件。

Windows删除用PowerShell LiteralPath并核验绝对路径；Linux同样拒绝符号链接/路径逃逸。拒绝空run_id、`..`、workspace根、盘符根、home和无法确认的目标。不得递归删除suite根或artifacts作为“本轮清理”。

### 11.2 必须独立检查的残留

| 对象 | 清理通过的可观察结果 |
| --- | --- |
| 容器 | Docker `ps -a`按本轮所有子project及owner标签查询均为空，包括已停止/one-off容器。命令报错不等于空。 |
| 网络 | 本轮子project网络与注册附属网络不存在，未误删既有网络。 |
| 卷 | 本轮postgres_data/uploads及登记的命名/匿名卷不存在；Compose文件避免声明匿名卷，意外产生仍需登记审计。 |
| 镜像tag | 本轮app/frontend/tools tag不存在；基础镜像或同ID其它tag允许保留并列明。 |
| 宿主进程/端口 | 本轮主机子进程树已退出；对应端口映射不存在。动态端口被其它进程随后占用不能据此杀其它进程。 |
| runtime/tmp | 当前run_id目录及原始私有日志/临时profile不存在，或因清理失败明确列剩余；不存在全局目录删除。 |
| 既有资源 | 启动前已存在的开发容器/网络/卷未被本入口删除。并发外部变更只能如实列差异，不能自动归因本入口。 |

仅收到`down`退出0不足以判“零残留”。最终cleanup.json记录预期资源、实际删除、复查命令结果、残留ID及保留项。Docker不可查询时为unknown/failed，停止新部署，恢复后再核验。

### 11.3 明确保留的东西及空间策略

- `artifacts/<run_id>`保留脱敏报告/证据，默认Git忽略、不自动删除历史；当前实现记录采证时的套件累计容量，不能据此推导单轮增量。需要磁盘配额或单轮增量验收时，必须另行采样该run开始/结束的容量，并提醒操作者按run_id归档/移除。
- `node_modules/`、`.cache/`和Docker通用构建缓存/基础镜像作为工具缓存保留，不称为业务运行残留。报告列出保留类别及可测大小；无法精确分摊Docker共享缓存则明确未知。
- `.cache/frozen-builds/`可能保留正式复验镜像归档，应单列其大小/指纹及用途；它不保留业务卷或运行Secret。正式两轮之间不要清除需要复用的冻结构建。
- 原计划的 `-PurgeToolCache` 本轮明确未实施，入口拒绝并退出2；不得用该命令声称空间已释放。后续只允许在无活跃运行时清理本suite依赖/缓存，不清全局npm/浏览器/Docker缓存。历史artifact删除另由操作者按明确run_id处理，不作为自动生命周期副作用。
- 本方案的零残留指**本轮运行容器/网络/业务数据卷/专有tag/进程/私有临时目录**清干净；可见报告和明确缓存有意保留。连续运行不积累数据库/上传大文件，报告/缓存占用也须可见。

### 11.4 恢复清理的调用方式

实施后统一用同一脚本Cleanup模式，不要求用户手拼docker资源名：

```powershell
# 将示例run_id替换为console/cleanup.json列出的实际值。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Cleanup -RunId ws-20261021t010203z-a1b2c3d4
```

Cleanup依次尝试读取本轮`runtime/<run_id>/session.json`、`artifacts/<run_id>/recovery-ledger.json`、既有`cleanup.json`内的ledger，核验Engine/context和run/owner/project身份后才扫描标签并恢复清理。私有账本或Secret已不存在，但公开恢复账本仍可验证时，可依据已登记身份和实际标签/资源ID逐项清理；不为Compose插值重新制造原数据库凭据。

**实施差异（保守安全边界）**：原规划“全部账本缺失但标签唯一即可自动回收”未实施。上述全部账本均丢失时，入口报告“找不到该 run_id 的恢复账本”并退出2，不凭标签猜测原Engine/owner，不宣称资源已清干净。须先恢复可信账本，或由操作者逐项核对原Engine与资源所有权后另行处理；资源仍存时不得先删除artifact恢复材料。本次演练验证了保留公开账本的恢复与幂等清理，没有验证全账本丢失后的自动回收。

## 12. 已知缺口的处理边界

| 调研项 | 当前问题/影响 | 本方案的处理 |
| --- | --- | --- |
| GAP-01（测试点文档QGAP-01） | 原契约测试读取已删旧样本，无法到达断言。 | 任务1～2已新增tests/api/fixtures/v2-contract-samples.json及说明、改测试引用，覆盖DTO/JSON Schema、16类事件与legacy Run；补jsonschema格式依赖并执行正/负断言。它不是数据库seed，开发测试不依赖新suite。正式QLT_002仍待分类执行。 |
| GAP-02（测试点文档QGAP-02） | 原frontend lint引用旧脚本，前端缺独立组件工具入口。 | 任务1～2已在frontend补ESLint/Vitest/Vue Test Utils/jsdom、配置/命令/锁文件及README，工具探针验证SFC/DOM/定时器。真实产品组件用例仍待后续；正式QLT_003不能以三项工具探针或历史报告代替。 |
| GAP-03/04 | 编号和旧验收组织/TEST链接残留。 | 本文/新增导航明确002及新专属目录，旧合并策略不再执行；历史记录不抹除。实施时同步本次涉及的使用导航，广泛文档重编号校准另行处理。 |
| GAP-05 | FastAPI显示version仍0.1.0，其它包为0.2.0。 | 记录产品元数据差异，不在环境任务中偷改app；后续quality/compatibility记录观察及处理，不据此绕过v2行为验证。 |

Environment技术模式不依赖完整pytest/Lint才可部署；summary明确`quality_prerequisites=pending`。工具前置现已补齐，正式All仍要求quality分类实际执行QLT_002/003并通过协议校验后，才将前置标ready；任一未通过标blocked，未执行保持pending。后续修复若改变受测文件，先冻结新指纹，再跑完整两轮，不能混用修复前后结果。

## 13. 实施路线、依赖与阶段退出条件

以下保留方案的实施顺序。当前环境工程已按A～E落地并执行复核；框选项及真实命令以本次[环境记录](../../tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)的最终结果回填。产品分类仍在阶段F，不自动提交或推送。

### 阶段A：目录/协议/范围冻结（已完成）

- [x] 新建suite README、test-plan、specific_test_script README和8类planned manifest，明确暂不新增用例/分类脚本。
- [x] 新建3份JSON Schema和baseline/Profile数据定义；先定义字段/退出码/所有权和runtime/artifact规则，再实现调用方。
- [x] 更新`.gitignore/.dockerignore`及导航；检查`git check-ignore`和构建上下文，防止运行数据上传。
- [x] 退出：全部预计文件有归属/用途/阶段；29项FR/NFR均有未来分类；Environment与产品验收统计完全分离；planned不能pass。

### 阶段B：工具、Provider和输入准备（已完成）

- [x] 固定Node/Python工具依赖，完成setup-tools、离线encoding/Chromium检查，不依赖旧suite路径。
- [x] 实现受控Provider、场景/屏障协议、安全观测、素材生成器；先用协议自测验证非法场景/超限/缺token拒绝，再连产品环境。
- [x] 实现preflight/Schema负样本自测，Provider响应/生成素材可重复，两个HTTP Profile可由正式校验器解析。
- [x] 退出：独立工具安装可复现；浏览器启动关闭成功；词表/384维和Profile自检真实通过，所有输出不泄Secret。尚未执行产品用例。

### 阶段C：隔离部署和初始化（已完成）

- [x] 新建独立Compose及工具Dockerfile、动态端口/owner标签/卷；以正式构建和migrate/同步Profile路径启动。
- [x] 实现compose helper、environment_probe、db-admin和资源创建账本；核对就绪顺序、Worker数量和同源代理。
- [x] 创建/删除专属空probe库，确认主库和开发容器不受影响；不调用业务PG探针冒充环境检查。
- [x] 退出：root开发端口/卷可共存，主库revision/Profile/健康/词表/Provider均可检查，子project身份可审计；有启动失败诊断。

### 阶段D：总调用、报告和清理（已完成）

- [x] 实现主入口四模式、预算、runtime上下文/Secret分离、分类runner和进程登记；用框架自测替身验证exit0缺报告、非零、超时、重复case/错误run_id等反例。
- [x] 实现中文/JSON汇总、证据索引/脱敏、源码前后指纹、失败逐项保留；分类脚本仍为planned。
- [x] 实现分类finally清理、全轮镜像tag/目录清理、零残留扫描和Cleanup恢复；先验证拒绝路径逃逸/错误标签/错误Engine后再验证正向删除。
- [x] 退出：不依赖任何产品分类也能Environment闭环；All/Selected遇未接入分类明确拒绝并产报告；清理失败优先退出4。

### 阶段E：本机环境闭环复核与交付（已完成）

- [x] 保留三次修复前独立Environment历史证据，并在最终安全修复后重新执行两次独立Environment；每次新run_id、空数据库和独占卷，均验证部署→技术探测→证据→销毁→资源审计。
- [x] 实际验证部署半途故障清理；用框架注入/替身验证报告缺失和收集失败仍finally；明确哪些是运行器自测、哪些是真实Docker演练。
- [x] 做一次可控主入口强停后的Cleanup恢复演练；恢复后确认容器/网络/卷/tag/私有目录无残留且重复Cleanup安全。真实Ctrl+C未单独验证，已在环境记录中列为限制。
- [x] 补suite README/test-plan实际命令、工具版本、报告解释/清理方式；在suite下新增`环境实施与验证记录.md`，记录环境演练真实结果和限制。
- [x] 最终检查修改文件、秘密/大文件忽略、源码未被运行器改写；只宣布“环境实施完成”，不宣布FR/NFR正式通过。

### 阶段F：后续独立任务（本方案不实施）

1. 任务1～2已补GAP-01/02工具前置并核验总入口；后续质量分类仍须正式执行，发现产品缺陷按独立任务处理。
2. 测试点矩阵与`test-cases.md`均已设计，覆盖84点/104例，并关联当前可验证性、原受限原因、观察目标和需求ID；新增实现差异时继续校准矩阵与用例。
3. 按8分类编写脚本及case独立夹具，接入manifest，从planned转ready；当前清单104例，ready登记必须完整，不沿用旧149或把框架自测数当产品用例数。
4. 执行Selected专项排错后冻结源码/工具/镜像，至少两轮All；每轮每分类新project，使用同一构建镜像ID/依赖集或明确记录变化，不拼接选择性重跑结果。
5. 回填测试用例结果/复现步骤/稳定性，分别生成测试报告和缺陷报告；记录失败、blocked、未运行、实现缺口和环境限制。原始失败不被后续通过覆盖。

## 14. 约定调用与复现记录

以下为实际入口约定，阶段E的本机执行结果、run_id和退出码见环境记录；不能据命令存在推断测试通过。统一在仓库根目录，Windows/Linux都使用pwsh：

```powershell
# 环境部署/技术探测/报告/清理，尚无产品分类也可执行。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Environment

# 可选：就绪后保留120秒供观察，到期仍自动清理。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Environment -HoldSeconds 120

# 独立任务3～4已将8类完整登记为ready；执行结果仍须以当轮实际证据判断。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session,context'
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode All
```

不提供默认`KeepEnvironment`或跳过清理开关。手工观察使用有界Hold；需要保留故障证据应先收集artifact，不能让数据库卷无限堆积。复现记录必须写实际命令、run_id、模式/分类、配置差异、工具/镜像/源码指纹、退出码和报告相对路径；不能只写“重跑脚本”。

## 15. 方案实施验收清单

| 编号 | 环境实施验收要求 | 必须保留的证据 |
| --- | --- | --- |
| ENV-01 | 专属目录与文件均按职责准备，README/接入计划/协议清楚，无旧smoke依赖 | 文件清单、路径/链接检查；环境阶段manifest planned状态保留为历史，任务3～4现为8类完整ready。 |
| ENV-02 | 工具版本、浏览器、离线词表和依赖可验证 | setup/preflight、lock/hash、浏览器启动关闭和encoding结果。 |
| ENV-03 | 隔离端口/project/卷/凭据，不接触开发资源 | 前后资源快照、回环动态映射、标签/账本、Secret/忽略检查。 |
| ENV-04 | PostgreSQL/Redis/Provider、迁移/Profile、API/Worker/前端顺序就绪 | 实际head/扩展/Profile、exit code、健康/worker_count和同源结果。 |
| ENV-05 | 至少两次空环境闭环可重复且未冒充产品验收 | 最终基线两个Environment run_id（`ws-20261021t173537z-f389cbb8`、`ws-20261021t174008z-5408188f`）均为 environment passed、product not_run、cleanup passed；修复前三轮仅作历史证据。 |
| ENV-06 | 分类协议正确，未接入/空结果/缺报告/错身份不pass | 运行器反例自测输出；All planned返回3，环境探测不填产品cases。 |
| ENV-07 | 失败/中断仍清理，强停可恢复且幂等 | 真Docker失败/强停恢复演练、框架失败替身结果分别记录。 |
| ENV-08 | 容器/网络/卷/tag/进程/runtime/tmp无本轮残留 | cleanup.json独立扫描；既有资源不被误删，缓存/报告明确保留。 |
| ENV-09 | 中文日志/JSON/报告真实、脱敏、有界且证据可追溯 | summary/evidence-index、文件hash、缺证据/截断/错误记录。 |
| ENV-10 | 产品/开发测试未被隐式修复或跳过，后续路线明确 | Git差异、GAP前置状态及test-plan计划，未运行项逐项列出。 |

以上为环境验收基准；逐项动态证据和未验证限制见环境记录。设计校审、替身自测、真实Docker演练与产品验收必须分别表述。

## 16. 风险、校审及本次交付状态

| 风险/校审项 | 设计处理与最终口径 |
| --- | --- |
| 环境成功被误认为产品通过 | 四模式、独立environment/product/cleanup结果；planned/空cases不允许All通过。 |
| 前一分类污染后一分类 | 独立子project、串行、每分类收集后销毁；共享的仅该轮镜像tag，业务卷不共享。 |
| 源码/镜像不一致 | 应用镜像冻结、工具只读挂载明确目录、源码前后hash和image ID记录；变化不能声明同源验收。 |
| 随机端口/SSE同源 | Docker动态回环映射、实际查询地址，HTTP/SSE共用前端代理，不继承开发固定端口。 |
| Worker就绪/迁移误判 | migrate/profile-init按退出成功检查，Worker readiness独立等待，数据库200不代表整个环境就绪。 |
| 缺慢流/错误前提 | Provider作为环境服务提供屏障/场景、真实HTTP兼容/tiktoken及独立PG专库，不伪造业务终态。 |
| 清理中断/误删/磁盘增长 | 创建前账本、owner标签/Engine/路径核验、有界finally和恢复；删数据卷/专有tag，缓存/报告单列。 |
| 已知测试工具缺口 | GAP-01/02在任务1～2中显式补工具前置，后续QLT_002/003正式结果仍是验收门禁；不恢复旧工程、不改产品行为。 |
| 需求覆盖和实施边界 | §9映射18项FR/11项NFR/十项总验收；§6/§13明确本环境方案与独立测试点矩阵、后续用例/具体脚本的边界。 |
| 文档前后一致 | 统一suite路径、run_id/子project关系、8分类、四模式、退出码、目录职责与阶段；本次校审已核对冻结镜像复用、commit测时区间、恢复账本路径、环境验证记录文件职责、链接、29个需求ID、关键命名和范围，避免两轮依赖漂移及“发生时间=提交时间”的误判。 |

**当前交付边界**：环境历史、任务1～2准备及任务3～4调试分别保留；任务5～6已在源码`684a5e22b94598517bcaeb25fe8a4ab750c758e34acdf0c6b70f97faafec3de7`下完成两轮All，R1=`ws-20261023t020902z-9fa22610`，R2=`ws-20261023t030707z-c936fff7`，各104 passed、其余0、清理passed、退出0。R2实际加载R1 FrozenBuild，镜像/依赖和运行前后源码一致；真实quality门禁、正常/主动失败/超时清理均重新执行。Linux宿主和真实Ctrl+C未新增专项实测，不从Linux容器推定宿主已验；可选PurgeToolCache仍拒绝。结果、保留缓存、归档UI等4项补充问题和最终校审见两份报告。回填后test-cases指纹变化，当前树重测需重新冻结；原执行源码归档及镜像缓存保留供精确追溯。
