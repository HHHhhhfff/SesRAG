# SesRAG Demo

v0.2 当前代码的详细落地、文件变动和需求核对见[PR-002实施结果调研](docs/pr/002-SesRAG-持久化会话与对话工作台-实施结果调研.md)。本轮及后续PRD的本机验收独立组织；当前正式入口为[PRD-002测试套件](tests/sesrag-persistent-session-workspace-test/README.md)。旧Demo验收文件只在上一版本/测试分支查阅，当前导航不再指向已退出目录。

v0.2 当前[TEST-002正式测试实施方案](docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)已建立独立的本机Compose测试环境、总入口、工具/素材和报告清理流程，入口及职责见[测试套件说明](tests/sesrag-persistent-session-workspace-test/README.md)，实际演练结果见[环境实施与验证记录](tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)。独立[测试点矩阵](tests/sesrag-persistent-session-workspace-test/测试点设计与需求覆盖矩阵.md)与[测试用例设计](tests/sesrag-persistent-session-workspace-test/test-cases.md)已完成；任务1～2的工具前置和总入口核验见[准备记录](tests/sesrag-persistent-session-workspace-test/测试准备与总入口核验记录.md)。任务3～4已接入8类104例脚本，真实试跑及修订证据见[脚本校审记录](tests/sesrag-persistent-session-workspace-test/测试脚本实施与试跑校审记录.md)；任务5～6现已完成同源两轮All，各104通过、0失败/受限/未运行/工程错误，清理通过；结果及真实命令见[测试报告](tests/sesrag-persistent-session-workspace-test/测试报告.md)，归档呈现等4项补充发现见[缺陷报告](tests/sesrag-persistent-session-workspace-test/缺陷报告.md)，原104例执行字段已回填。本次最小修复新增4个归档用例，当前登记108例，最终完整回归108通过、清理通过、退出0；首轮工程失败如实保留，未定义005不作虚构处理。改动及本轮真实结果见[小缺陷修复与回归验收报告](tests/sesrag-persistent-session-workspace-test/小缺陷修复与回归验收报告.md)。

SesRAG 是一个前后端分离、Docker Compose 部署的持久会话 RAG 应用。v0.2 在保留文本文档索引/pgvector 与 v1 文档 API 的同时，已增加持久 Thread/Branch、Run/Context/Event Journal、Profile 选择与冻结快照、重试/重新生成/取消和 Vue 对话工作台。Worker 仍以 PostgreSQL 持久任务和有限 lease 执行。

Demo基础缺陷修复的历史记录位于[PR-001](docs/pr/001-SesRAG-Demo-缺陷修复-PR.md)；旧测试artifact应在上一版本/测试分支查阅，不作为当前版本可执行命令或本轮验收结果。

## 目录

```text
backend/       FastAPI、领域对象、应用服务、基础设施适配器和 Worker
frontend/      Vue 3 + TypeScript 单页工作台；模块与生成入口见frontend/README.md
migrations/    Alembic 数据库迁移
contracts/     Thread/Message/Run/Document/Health、响应/引用和 Run Event 版本化 JSON Schema
tests/         单元、API 和集成测试
tests/sesrag-persistent-session-workspace-test/ 本轮独立环境、统一入口、工具、接入规范和按run_id保存的证据
docker/        API/Worker 与前端镜像定义
docs/prd/      Demo、v0.2 与完整项目 PRD
docs/adr/      实施方案和架构决策
docs/pr/       PRD 实施完成后的开发结果记录
docs/test/     PRD 测试验收方案和结果
docs/runbooks/ 部署、开发、故障和验收说明
CONTEXT.md     稳定术语及其来源、状态
AGENTS.md      仓库级 AI 开发约束
```

## 文档入口

- 产品目标：[`docs/prd/`](docs/prd/)，当前 Demo 为 [`001-SesRAG-项目Demo-PRD.md`](docs/prd/001-SesRAG-项目Demo-PRD.md)，v0.2 持久化会话与对话工作台为 [`002-SesRAG-持久化会话与对话工作台-PRD.md`](docs/prd/002-SesRAG-持久化会话与对话工作台-PRD.md)，完整目标为 [`SesRAG-完整项目-PRD.md`](docs/prd/SesRAG-完整项目-PRD.md)。
- Demo基础缺陷修复方案：[ADR-001](docs/adr/001-SesRAG-Demo-缺陷修复-plan.md)；历史范围及结果见[PR-001](docs/pr/001-SesRAG-Demo-缺陷修复-PR.md)。
- 实施方案与架构决策：[`docs/adr/`](docs/adr/)。
- v0.2 持久化会话与对话工作台实施方案：[ADR-002](docs/adr/002-sesrag-persistent-session-workspace-implementation-plan.md)；实际代码和剩余验证缺口见 [PR-002调研](docs/pr/002-SesRAG-持久化会话与对话工作台-实施结果调研.md)。
- v0.2 [简要实施记录](docs/pr/002-SesRAG-持久化会话与对话工作台-PR.md)保留当时专项及两轮历史结果；新的独立 [TEST-002方案](docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)与[环境验证记录](tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)分别记录本轮环境设计及真实结果，不复用旧历史结果。
- PRD-002 测试点与需求覆盖：[测试点设计与需求覆盖矩阵](tests/sesrag-persistent-session-workspace-test/测试点设计与需求覆盖矩阵.md)已设计；[本轮测试目录说明](tests/sesrag-persistent-session-workspace-test/README.md)列出当前文档、环境和脚本状态。测试点“可验证”不等于测试已执行或通过。
- Demo历史变更：[基础缺陷修复记录](docs/pr/001-SesRAG-Demo-缺陷修复-PR.md)。当前v0.2验收只使用本轮独立套件。
- 开发结果与测试验收：[`docs/pr/`](docs/pr/)、[`docs/test/`](docs/test/)。Demo 正式测试实施方案见 [`docs/test/001-SesRAG-项目Demo-test-plan.md`](docs/test/001-SesRAG-项目Demo-test-plan.md)，历史验收结果见 [`docs/test/001-SesRAG-项目Demo-test.md`](docs/test/001-SesRAG-项目Demo-test.md)。
- 部署、故障和验收流程：[`docs/runbooks/`](docs/runbooks/)；代码修改规范见 [`docs/项目开发和修改的通用执行规范.md`](docs/项目开发和修改的通用执行规范.md)。
- 接口唯一说明：[`docs/接口文档.md`](docs/接口文档.md)；稳定术语见 [`CONTEXT.md`](CONTEXT.md)；仓库级 AI 规则见 [`AGENTS.md`](AGENTS.md)。
- 工程技能配置：`docs/agents/` 保存 [GitHub Issues 工作流](docs/agents/issue-tracker.md)、[分诊标签映射](docs/agents/triage-labels.md)和[领域文档读取规则](docs/agents/domain.md)；使用现有 `CONTEXT.md` 和 `docs/adr/`。

## 快速启动

本地 Compose 部署支持 Windows（PowerShell 7.4+、Docker Desktop Linux Engine）和 Linux（Docker Engine、Compose v2）。首次部署、PostgreSQL 凭据生成/恢复、迁移备份与回退、容器更新和验证命令统一见[Demo 本地开发 Runbook](docs/runbooks/demo-development.md)。`.env.example` 仅为模板，不能原样用于启动；不要在已有 PostgreSQL 数据卷时重新生成数据库密码或覆盖 `.env`。

后端镜像使用 Python 3.12，宿主机无需安装 Python 3.12。服务就绪后访问：

- 前端：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- Readiness：<http://localhost:8000/health/ready>

首次启动由 `migrate` 容器执行 Alembic 迁移。PostgreSQL 使用 `pgvector/pgvector:pg16`，API 和 Worker 共享 `uploads` volume。停止服务使用 `docker compose down`；只有明确确认要永久清除本项目数据库与上传文件、且所需数据已备份后，才使用 `docker compose down -v`。升级、回退、备份和恢复步骤见本地开发 Runbook。

## 环境变量

`.env.example` 已逐项注释。核心配置如下：

| 配置 | 必填 | 作用 |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | 是 | PostgreSQL 初始化密码，运行时注入，不提交真实值 |
| `DATABASE_URL` | 是 | API/Worker/迁移使用的连接串；密码 URL 编码并与 PostgreSQL 初始化配置一致，不输出到报告或默认日志 |
| `REDIS_URL` | Compose 默认值可用 | Event 唤醒和 Worker readiness；不可用时退化为数据库轮询 |
| `REDIS_ENABLED` | 否 | 是否启用 Redis 通知，单元测试设为 `false` |
| `UPLOAD_DIR` | 是 | API/Worker 共享上传目录，不能配置为公开静态目录 |
| `VECTOR_DIMENSION` | 否 | Demo 仅支持 384；其他值启动前拒绝，Provider 返回维度必须一致 |
| `TASK_LEASE_TTL` / `TASK_HEARTBEAT_INTERVAL` | 否 | Worker lease 和续租周期，默认 30/10 秒 |
| `TASK_MAX_ATTEMPTS` / `TASK_RETRY_BASE_DELAY` | 否 | 有界重试次数和指数退避基数 |
| `TASK_DEADLINE` | 否 | 单任务硬截止时间，超时进入 `failed` 并记录 `TASK_DEADLINE_EXCEEDED` |
| `WORKER_SHUTDOWN_GRACE` | 否 | 停止领取后等待当前任务的宽限期，默认 20 秒；超过宽限期取消执行并释放有效租约 |
| `QUEUE_POLL_INTERVAL` / `SSE_POLL_INTERVAL` | 否 | 默认分别为 1 / 0.2 秒，控制任务领取和持久事件观察；必须为有限正值，不改变已冻结 Run 的执行限制 |
| `HEALTH_PROBE_TIMEOUT` | 否 | 单步依赖探测/Redis 操作超时，默认 2 秒，必须为有限正值；ready 执行真实 PG/Redis 探测，PG 故障 503，Redis 故障降级 |
| `RAG_TOP_K` | 否 | 默认召回数量，默认 5 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 否 | 文本切分大小和重叠字符数 |
| `MOCK_PROVIDER` | 否 | 默认 `true`，不需要外部模型 Key 即可验收主流程 |
| `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME` / `EMBEDDING_MODEL_NAME` | 使用真实 Provider 时必填 | OpenAI-compatible 地址、服务端 Key、生成模型及 Embedding 模型配置；Secret 只注入服务端，地址不允许 URL 凭证或敏感 query |
| `VITE_API_BASE_URL` | 否 | 默认空，HTTP/SSE/health统一请求同源前端；显式值仅接受无凭据HTTP(S) origin，不承载Secret |
| `API_PROXY_TARGET` | 否 | Vite服务端代理目标，宿主默认`http://127.0.0.1:8000`，根Compose显式为`http://api:8000`；不进入浏览器产物 |

Demo 默认使用 `OWNER_ID=local-user`，不提供生产认证、RBAC 或多租户隔离。v0.2 的 `ModelProfile` 是数据库中的版本化非 Secret 元数据，默认 Mock Profile 由 0005 迁移提供；自定义 Profile 必须显式导入，`config_ref=env:MODEL_API_KEY` 运行时从 API/Worker 环境读取凭据，不把密钥写入 JSON、Run Snapshot、Event 或前端。真实 Profile 的 tokenizer encoding/框架开销/校准版本须显式配置，未校准的兼容 Provider 不构成精度或生产 SLO 证明。

v2生成模型由Profile选择；`MOCK_PROVIDER`控制既有Embedding与legacy生成模式。仅配置真实v2生成Profile时可以保留Mock Embedding，仍须给API/Worker提供该Profile所需Key。变更Secret后需同时重建API和Worker环境；Embedding的kind/地址/模型/Secret alias冻结在Run的retrieval中，不能随生成Profile或后续Settings更改而漂移。

真实tokenizer当前支持镜像已预热的`cl100k_base`；应用先验证离线资产，不在API/Worker请求中隐式下载词表。缺失/损坏/不支持的encoding会使Profile明确不可用，后续扩展须配对更新资产登记、构建和验证。

参数在 `Settings` 初始化时校验：租约/心跳/重试/截止时间及轮询必须为正值，心跳须小于租约，`RAG_TOP_K > 0`，`0 <= CHUNK_OVERLAP < CHUNK_SIZE`。Compose 拒绝缺失密码或 DSN；复制模板不等于凭据已经配置。

根 Compose 将 `VECTOR_DIMENSION/RAG_TOP_K/CHUNK_SIZE/CHUNK_OVERLAP` 同时注入 API 和 Worker，未设置时分别为 `384/5/800/120`，非法值在启动加载 Settings 时拒绝。API 冻结向量维度与 Top-K 到 RunSnapshot，Worker 按快照检索并按启动切分配置索引；切分不是已有 Run 的可变配置。`.env` 仅用于 Compose 插值，不复制进镜像。容器的 Redis 地址和 `/data/uploads` 为根编排固定值，宿主直接运行时才读取对应宿主设置。

迁移 `0001_initial_demo.py` 使用固定历史定义；新增 `0002_demo_integrity.py` 提供 Message 幂等/assistant 唯一、Task 关联互斥及安全来源字段。遇到旧事实冲突会中止，不自动合并或删除；降级保留来源列，非空数据库禁止降到 base。迁移和健康操作见 [开发 Runbook](docs/runbooks/demo-development.md)。基础回归在 `tests/unit/test_foundation_*.py`、`tests/api/test_foundation_*.py`；`tests/unit/foundation_pg_probe.py` 仅用于显式隔离 PG 迁移验证，不对开发库运行。

## 持久执行模块

`backend/application/task_execution.py` 集中负责租约/取消检查、步骤调用保护、执行事件写入和最终回答原子提交；`backend/infrastructure/queue/postgres_queue.py` 负责领取、续租、回排和失败结算；`backend/workers/runtime.py` 负责进程循环、独立 readiness 心跳、停机和安全关联日志。失租或取消会停止后续写回，不把迟到结果归为成功。

Worker 写回在最后一次 flush 后、commit 前复查保存的授权时间；续租不能用新 lease 复活旧授权，失败/重试/增量与索引初态越界也整体回滚。scheduler 的到期回收和取消保持独立条件。前端按当前 Run 状态解释历史错误：failed 显示执行失败，retry_waiting 显示等待重试，succeeded 显示上次尝试错误已恢复，不删除后端历史错误码。

Run 创建时冻结非 Secret 的模型/检索配置，后续修改默认配置不改变已有 Run。旧版 Mock 快照按旧协议固定 384 维和持久 Thread owner 恢复；无法恢复的快照明确失败为 `INVALID_RUN_SNAPSHOT`，不会猜测或切换模型。执行保护目前使用单步骤 60 秒、模型流总计 120 秒、4096 个增量和 1,000,000 字符硬上限，另受任务 deadline 约束。同步线程中的调用无法被强杀，这不等同于进程隔离或外部副作用撤销。

ADR-002 的 v2 后端与前端工作台已接线 Thread/Branch、Run/Context/Event/SSE、Profile快照、取消、显式重试及重新生成。`backend/application/session_runs.py` 管理 v2 原子创建和用户操作，`session_execution.py` 管理冻结策略下的 RAG、计划、ModelRequest 与独立定时 delta 发布。历史专项和两轮结果保留于[简要实施记录](docs/pr/002-SesRAG-持久化会话与对话工作台-PR.md)，当前实现及验证缺口见[实施结果调研](docs/pr/002-SesRAG-持久化会话与对话工作台-实施结果调研.md)。新的 [TEST-002](docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md) 已建立独立环境与接入协议，产品分类和同源两轮正式执行已完成，当前结论见[测试报告](tests/sesrag-persistent-session-workspace-test/测试报告.md)及[缺陷报告](tests/sesrag-persistent-session-workspace-test/缺陷报告.md)，不承载旧结果。接口与恢复约定见 [正式接口文档](docs/接口文档.md)。

v2 Profile 元数据由迁移 seed 两个 Mock 选项。真实 Profile 使用显式 JSON 导入：`.venv/Scripts/python.exe -m backend.tools.sync_model_profiles docker/model-profiles.example.json`（按需替换为本地受控配置文件）；运行时只从配置中的 `env:MODEL_API_KEY` 读取 Secret，配置文件和数据库都不得保存 Key。Profile JSON 的 `base_url` 不得包含认证信息、query 或 fragment；真实 Tokenizer 的 `tokenizer_config` 除预算字段 `safety_margin_tokens`、`summary_max_tokens` 外，必须显式提供受支持的 `encoding_name`、每条消息开销 `message_overhead_tokens`、整次请求开销 `request_overhead_tokens` 和非空校准版本 `calibration_version`。计数器从冻结的 Profile 配置构建，真实计数器版本以 36 字符稳定摘要标识 encoding、包版本、框架开销、校准版本及 Profile tokenizer 版本，完整配置保留在冻结的 Profile 中；配置须按目标服务校准，不保证适用于所有兼容服务。真实模型需在 API/Worker 运行环境设置 `MODEL_API_KEY`，该变量不返回给浏览器、不落入 Run Snapshot 或日志。Embedding 模型仍使用固定 384 维检索空间，不能随生成模型切换。

Worker 默认 ID 为进程内稳定的 UUID 身份；动作日志为含 `action/task_id/run_id/document_id/worker_id/generation/attempt/error_code` 的 JSON。Run 任务按 `run_id` 关联，索引任务按 `document_id` 关联且 `run_id` 可为空；关联值准确对应持久 Task，不能因空 `run_id` 跳过文档关联。日志区分 claim、renew、release、retry、success、failure，并保留安全拒绝信息，不记录原始异常或文档正文。Redis 恢复后 readiness 会重新探测，不需要通过修改持久任务状态恢复。

Worker 控制面数据库阶段有 5 秒预算；停止标记可中断回收、领取和 mark-running 等待。超宽限后先停止续租，再在 1 秒内尝试释放，每轮取消清理最多等待 0.5 秒；释放未成功会留下安全 reject 并交正常租约回收，不伪报 release。这些是协作式异步取消预算，不保证任意吞取消的自定义适配器或同步线程能被强杀；容器停止超时是最后保护边界。

对应测试用途及安全运行边界见 [`tests/api/README.md`](tests/api/README.md) 和 [`tests/integration/README.md`](tests/integration/README.md)。`execution_pg_probe.py` 必须运行于专属新建隔离库，不能对开发库执行；阶段专项测试不替代完整分类两轮回归。

## 文档与可替换 RAG 模块

模块职责和限制见 [`backend/README.md`](backend/README.md)。纯 DTO/协议集中在 `backend/domain/ports/__init__.py`，Worker 组合根注入 `queue/adapter.py`、`providers/factory.py`、pgvector 与 Parser，候选计算在事务外、发布在 Task/Document 锁保护的短事务中。`vector_validation.py` 在写入前拒绝非 384 维、非有限及超出 float32 的数值。真实 Provider 配置见上表，只向服务端注入凭据。

`rag/parser_process.py` 是内部有界解析入口：源 10 MiB、ZIP 展开 40 MiB、ZIP 条目/位置各 100000、输出 64 MiB、运行 30 秒；Linux 另有 512 MiB 地址空间/30 秒 CPU 限制，Windows 无 RLIMIT。基础位置与 chunk 字符 offset 分开；真正空文本失败，非空空白文本保留原字符切分行为。路由 `read(MAX+1)` 不代表 multipart 接收前的网络/磁盘总配额，也不构成任意代码沙箱。

`0003_chunk_locations.py` 增加位置列，降级保留证据、旧记录不补造位置。`tests/integration/test_rag_review_fixes.py` 与本地 HTTP 专项补兼容/双故障/超时等回归；`rag_pg_probe.py` 只用于全新专属隔离库，验证真实发布/回滚/租约边界。测试用途见 [单元说明](tests/unit/README.md) 和 [集成说明](tests/integration/README.md)，正式两轮状态仍以验收报告为准。

## 接口文档

旧 Demo/文档接口保持 `/api/v1`；v0.2 Thread/Branch/Model/Run/Context 使用 `/api/v2`。完整请求响应、错误码、Event envelope、SSE重连和兼容规则只维护在 [`docs/接口文档.md`](docs/接口文档.md)。Run Event 先写 PostgreSQL，再由 SSE 投影；Redis只负责唤醒，客户端按 `seq` 去重并在断线后补放。

## 测试

宿主机纯单元/API/SQLite 集成测试：

```powershell
python -m pytest -q
ruff check .
ruff format --check .
```

前端：

```powershell
cd frontend
npm install
npm run typecheck
npm run build
```

前端模块职责、同源代理、类型生成和质量命令见 [`frontend/README.md`](frontend/README.md)。宿主 Vite 使用本机 API 地址；根 Compose 的浏览器 HTTP/SSE/health 都走同源代理。根 `.env` 不由宿主 Vite 自动加载，可用进程环境或 `frontend/.env.local` 配置代理目标。单页原生组件保留 DOMPurify，不额外引入 Router/UI 库。类型由版本化 Schema 通过 `npm run generate:api --prefix frontend` 生成，`check:api` 检查漂移；当前已配置独立ESLint/Vitest/Vue Test Utils/jsdom及组件断言，质量工具不再依赖旧验收目录。实际命令结果与负例门禁见[脚本校审记录](tests/sesrag-persistent-session-workspace-test/测试脚本实施与试跑校审记录.md)，安装完成不等于质量通过。

本轮本机隔离测试环境按[TEST-002](docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)在 `tests/sesrag-persistent-session-workspace-test/` 独立准备。Windows/Linux统一使用PowerShell 7入口，配有独立Compose、动态回环端口、每分类专属子环境和报告/清理恢复流程。准备及执行命令见[套件README](tests/sesrag-persistent-session-workspace-test/README.md)，环境历史见[环境记录](tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md)，本轮工具及总入口证据见[准备记录](tests/sesrag-persistent-session-workspace-test/测试准备与总入口核验记录.md)。104例分类脚本已接入，脚本—用例对应及试跑结果分别见套件README和[脚本校审记录](tests/sesrag-persistent-session-workspace-test/测试脚本实施与试跑校审记录.md)；正式两轮各104通过、结果已回填，完整证据及保留差异见[测试报告](tests/sesrag-persistent-session-workspace-test/测试报告.md)和[缺陷报告](tests/sesrag-persistent-session-workspace-test/缺陷报告.md)，不以环境验证替代产品验收。旧 `tests/demo-smoke` 已退出本分支，不再作为当前推荐的可执行入口。

开发Compose的基础检查（不等于完整隔离测试验收）：

```powershell
docker compose up -d --build
docker compose ps
Invoke-WebRequest http://localhost:8000/health/ready
```

完整实施边界、对象关系、异常行为和阶段退出条件见 [`docs/adr/001-sesrag-demo-implementation-plan.md`](docs/adr/001-sesrag-demo-implementation-plan.md)；Demo 产品验收口径见 [`docs/prd/001-SesRAG-项目Demo-PRD.md`](docs/prd/001-SesRAG-项目Demo-PRD.md)；完整产品长期目标见 [`docs/prd/SesRAG-完整项目-PRD.md`](docs/prd/SesRAG-完整项目-PRD.md)。
