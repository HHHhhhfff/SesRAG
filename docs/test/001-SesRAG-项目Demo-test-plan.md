# TEST-001：SesRAG 项目 Demo 测试实施方案

**编号**：001

**版本**：v0.2

**状态**：已确认；阶段1～4基础设施已实施，后续任务3已接入分类；正式验收结果以任务5记录为准

**日期**：2026-10-06

**适用范围**：SesRAG 第一阶段 Demo 的本机 Docker Compose 测试环境、总测试入口、测试报告和资源清理闭环

**依据**：

- [`docs/prd/001-SesRAG-项目Demo-PRD.md`](../prd/001-SesRAG-项目Demo-PRD.md)
- [`docs/adr/001-sesrag-demo-implementation-plan.md`](../adr/001-sesrag-demo-implementation-plan.md)
- [`docs/pr/001-SesRAG-项目Demo-PR.md`](../pr/001-SesRAG-项目Demo-PR.md)

## 1. 方案摘要

本方案为 SesRAG Demo 设计一套可在 Windows 本机执行的 Docker Compose 测试实施基础设施。测试运行器在宿主机执行，负责创建隔离的 Compose 项目、启动 PostgreSQL/Redis/migrate/api/worker/frontend 服务，依次调用已接入的分类测试脚本，收集日志和结构化报告，最后销毁容器、网络、卷和临时文件。

方案的核心事实来源仍是 PostgreSQL；测试脚本只能通过正式 `/api/v1` 接口、SSE、健康检查和必要的 Docker 诊断观察行为，不直接修改生产代码中的事实状态。测试运行使用独立 Compose project name、独立端口和 Compose 管理的临时卷，避免污染开发环境。

本方案实施的是“临时测试环境 + 总测试脚本 + 测试数据准备 + 报告/清理约定”。具体分类测试脚本、测试点文档和测试用例文档不在本方案内直接实现，后续必须按照本方案规定的接口和阶段接入。

## 2. 目标、非目标与验收口径

### 2.1 目标

1. 在本机 Docker Desktop 上可重复启动一套与开发环境隔离的 Demo 测试环境。
2. 通过一个 PowerShell 总入口完成启动、等待就绪、分类测试调用、报告汇总和资源释放。
3. 为 Thread/Message/Run、Task lease、Worker 恢复、文本 RAG、Event Journal/SSE、取消和安全边界预留清晰的分类测试入口。
4. 每次运行以唯一 `run_id` 保存报告、容器状态、健康快照和必要日志，不覆盖历史证据。
5. 无论测试成功、失败、中断还是环境阻塞，都执行清理；清理失败必须进入最终报告并返回非零结果。
6. 让后续测试点和测试用例可以在不改变环境生命周期的情况下独立接入。

### 2.2 非目标

- 本方案不实现各类具体测试脚本的断言逻辑。
- 本方案不编写详细测试点文档或测试用例文档；这些文档按后续测试需求单独维护。
- 本方案不修复当前代码已知缺口，例如 deadline、Provider 错误分类、`task.leased` 事件或 graceful shutdown；测试方案只为这些缺口提供验证入口。
- 本方案不引入生产认证、多租户、真实外部模型、Milvus、专用消息队列或完整项目 PRD1～PRD4 能力。
- 本方案不把测试环境的默认数据库密码、Mock Provider 或单 owner 配置当作生产安全方案。

### 2.3 总体通过口径

一次测试运行只有同时满足以下条件才能标记为 `passed`：

1. Docker daemon 可用，Compose 配置解析成功。
2. migrate 成功退出，api、worker、postgres、redis、frontend 达到本方案规定的就绪条件。
3. 所有被配置为 `enabled` 的分类测试脚本返回成功，且报告中的检查项没有失败。
4. 总入口完成 `docker compose down --volumes --remove-orphans`，确认本次 Compose project 不再有运行中或残留容器。
5. `runtime/` 和 `tmp/` 本次运行目录已删除；报告、日志和诊断证据已保存到对应 `artifacts/<run_id>/`。

`blocked` 表示环境无法满足测试前提，例如 Docker daemon 未启动；`failed` 表示环境已启动但测试或清理失败；`not_ready` 表示分类脚本尚未接入，不得伪装成通过。总入口不能因为没有分类脚本而返回 `passed`。

## 3. 测试架构与数据流

```text
PowerShell 总入口
  ├─ 预检：Docker、Compose、端口、目录和配置
  ├─ 生成 run_id、runtime/、tmp/、artifacts/<run_id>/
  ├─ docker compose -p <isolated-project> up -d --build
  ├─ 等待 migrate、postgres、redis、api、worker、frontend 就绪
  ├─ 按 manifest 顺序调用 specific_test_script/*
  │    └─ 通过 HTTP/SSE、Docker 状态和必要日志观察系统
  ├─ 汇总各分类 JSON/JUnit 结果、健康快照和 Compose 日志
  └─ finally：停止并删除容器/网络/卷，删除 runtime/tmp，写最终 summary
```

测试脚本不直接连接宿主机 PostgreSQL，也不把 Redis 消息当作事实。需要核对持久化结果时，优先调用正式 API；需要核对 Worker lease/generation、迁移或容器状态时，只读取测试项目对应的数据库或 Docker 诊断信息，并把诊断行为记录到报告中。

## 4. 测试范围映射

分类测试脚本后续按以下边界接入。表中是测试实施入口和预期覆盖范围，不是本方案直接交付的测试用例。

| 分类 | 计划脚本入口 | 主要覆盖 | 关联 PRD/ADR |
| --- | --- | --- | --- |
| 服务启动与健康 | `specific_test_script/00-service-health.ps1` | Compose 配置、迁移退出、live/ready、Worker readiness、前端可访问性 | PRD 验收 1；ADR 阶段 1、阶段 7 |
| Thread/Message/Run API | `specific_test_script/10-thread-run-api.ps1` | Thread CRUD、Message seq、幂等、Run Snapshot、取消、API 错误响应 | F-TH-01～04、F-RUN-01/02/06 |
| Worker 调度与恢复 | `specific_test_script/20-worker-lease-recovery.ps1` | claim、lease、heartbeat、generation、过期回收、重试、deadline、SIGTERM | F-WK-01～07；ADR 5.2、5.7 |
| 文档登记与索引 | `specific_test_script/30-document-rag.ps1` | txt/md/docx、大小/MIME、解析、切分、Embedding、active batch、Top-K、引用 | F-RAG-01～08 |
| Event Journal/SSE | `specific_test_script/40-event-sse-recovery.ps1` | seq、after_seq、Last-Event-ID、断线补放、重复事件、终态关闭 | F-RUN-04/05；ADR 7.2/7.3 |
| 前端工作台 | `specific_test_script/50-frontend-workspace.mjs` | 页面启动、创建会话、提问、事件展示、刷新恢复、文档状态、Markdown 清洗 | 前端最小工作台；ADR 阶段 6/7 |
| 故障与安全边界 | `specific_test_script/60-fault-safety.ps1` | Redis/Worker 重启、Provider 配置错误、非法文件、路径逃逸、Secret/路径泄漏 | PRD 非功能需求；ADR 5.7、11 |

分类脚本可以使用PowerShell或Node.js。根据本次环境实施任务授权，已在`tests/demo-smoke`独立安装Playwright/Chromium供后续接入，不改前端依赖；具体浏览器测试脚本仍由后续任务编写。

## 5. 目录与文件设计

本方案规定的本地隔离测试资源全部集中在 `tests/demo-smoke/`。该目录只服务本机临时测试，不承载生产运行文件，也不与 `tests/unit`、`tests/api` 的宿主机测试 fixture 混用。

### 5.1 目标目录

```text
tests/demo-smoke/
├── README.md
├── run-demo-smoke.ps1
├── specific_test_script/
│   └── README.md
├── fixtures/
│   ├── README.md
│   ├── upload-safe/
│   │   ├── smoke.md
│   │   ├── smoke.txt
│   │   └── smoke.docx                 # 后续需要时加入二进制 fixture
│   ├── upload-invalid/
│   │   └── unsupported.exe.txt        # 后续脚本可改名或复制为非法扩展名
│   └── expected/
│       └── event-types.json
├── compose/
│   ├── docker-compose.demo-smoke.yml
│   └── .env.demo-smoke.example
├── runtime/                            # 运行时地址/配置，必须 Git 忽略
├── artifacts/                          # 按 run_id 保存报告和证据，默认 Git 忽略
└── tmp/                                # 运行期间生成的大文件和临时内容，结束后删除
```

`runtime/`、`artifacts/` 和 `tmp/` 是运行目录，不要求提交空目录；若工具需要目录存在，应由总入口在每次运行开始时创建。`smoke.docx`、超大文件、损坏文件等二进制或大体积 fixture 只有在确实被分类测试使用时才加入，避免把无用途的测试数据长期放进仓库。

### 5.2 文件职责和使用阶段

| 路径 | 类型 | 主要职责 | 使用阶段 |
| --- | --- | --- | --- |
| `tests/demo-smoke/README.md` | 新增文档 | 说明本机先决条件、目录用途、运行命令、报告位置和清理保证；不复制 PRD/ADR 的完整内容。 | 环境搭建完成后、日常运行前 |
| `tests/demo-smoke/run-demo-smoke.ps1` | 新增脚本 | 唯一总入口；负责预检、run_id、Compose 生命周期、脚本调度、报告汇总和 finally 清理。 | 所有正式本机 Demo Smoke 运行 |
| `tests/demo-smoke/specific_test_script/README.md` | 新增文档 | 约定分类脚本命名、参数、退出码、输出报告 schema 和不得越过的事实来源边界。 | 分类脚本接入前 |
| `specific_test_script/*` | 后续新增 | 每个脚本只负责一个测试分类；本方案只规定接口，不实现其断言。 | 分类测试阶段 |
| `tests/demo-smoke/fixtures/` | 新增目录/数据 | 提供安全文档、非法输入和事件期望等稳定输入；大文件优先运行时生成。 | RAG、错误和安全分类测试 |
| `tests/demo-smoke/compose/docker-compose.demo-smoke.yml` | 新增 Compose 覆盖文件 | 在仓库根 `docker-compose.yml` 之上覆盖隔离端口、owner、Mock Provider 和测试专用环境变量，不复制整份生产编排。 | Compose 启动阶段 |
| `tests/demo-smoke/compose/.env.demo-smoke.example` | 新增配置模板 | 说明测试 project name 前缀、API/前端宿主端口、等待超时、测试 owner 和报告策略；不放 Secret。 | 预检和本地配置阶段 |
| `tests/demo-smoke/runtime/` | 运行时目录 | 保存本次 API 地址、Compose project name、端口和进程间临时元数据；不得进入 Git。 | 预检至清理阶段 |
| `tests/demo-smoke/artifacts/<run_id>/` | 报告目录 | 保存 summary、分类 JSON/JUnit、健康快照、Compose ps、迁移日志、服务日志和清理结果；默认保留以便追溯。 | 测试执行和结束汇总 |
| `tests/demo-smoke/tmp/<run_id>/` | 临时目录 | 保存脚本生成的超大文件、损坏文件、下载响应和短期中间数据；清理阶段必须删除。 | 分类测试执行期间 |
| 根 `.gitignore` | 修改 | 增加 `tests/demo-smoke/runtime/`、`tests/demo-smoke/artifacts/`、`tests/demo-smoke/tmp/`，避免运行凭据、日志和大文件误提交。 | 目录首次加入仓库时 |
| 根 `README.md` | 修改 | 在测试章节增加正式总入口、Docker 前提、报告路径和清理命令链接；不复制分类测试用例。 | 测试基础设施接入完成后 |

本方案实施时只新增测试基础设施和必要 fixture；分类脚本、测试点文档、测试用例文档由后续任务在 `specific_test_script/`、`docs/test/` 或对应测试文档中单独交付。

## 6. Compose 隔离环境设计

### 6.1 编排方式

总入口使用根编排和测试覆盖文件叠加：

```powershell
docker compose `
  --project-name $composeProject `
  --file docker-compose.yml `
  --file tests/demo-smoke/compose/docker-compose.demo-smoke.yml `
  up --detach --build
```

覆盖文件只修改测试所需差异：

- 为 api、frontend 暴露测试专用宿主端口，默认使用 `18000` 和 `15173`；总入口预检占用情况，必要时选择空闲端口并通过环境变量传入。
- 将 `OWNER_ID` 设置为本次测试专用 owner，例如 `demo-smoke-<run_id>`，避免与开发数据混淆。
- 默认主环境固定 `MOCK_PROVIDER=true`，不要求外部模型 Key；真实外部供应商效果不属于本机 smoke。ADR-002 的协议故障专项可以使用生产 OpenAI-compatible Adapter 访问测试目录内的本地 HTTP/SSE 服务，使用虚拟凭据，不访问外部供应商，专项资源仍由同一总入口登记和清理。
- 保持 API/Worker 共享 uploads volume，但使用独立 Compose project name 产生隔离的网络和命名卷。
- 不向宿主机暴露 PostgreSQL/Redis 端口；测试通过 API、SSE、Docker health 和必要的容器内诊断访问它们。
- 为 frontend 注入测试 API 地址，确保浏览器访问的是本次测试 API 端口。

测试 project name 必须包含 `sesrag-demo-smoke` 和 run_id 的短标识。禁止使用固定开发 project name 作为正式测试 project name，避免旧容器或旧卷被误复用。

### 6.2 就绪条件

总入口必须按以下顺序判断就绪，不以 `docker compose up` 返回成功作为唯一依据：

1. `docker info` 成功，Docker daemon 可用。
2. `docker compose config` 成功，覆盖文件和变量可解析。
3. `postgres` 和 `redis` healthcheck 为 healthy。
4. `migrate` 容器退出码为 0；非零立即停止分类测试并进入清理。
5. API `/health/live` 返回 HTTP 200 且 `status=ok`。
6. API `/health/ready` 返回 HTTP 200、`database=ready`；Redis 正常时 `redis=ready`，Worker readiness 出现且 `worker_count >= 1`。
7. frontend 测试端口可建立 HTTP 连接；页面可用性由前端分类脚本负责。

每个等待步骤使用有界超时、固定轮询间隔和剩余时间记录。超时报告必须包含 `docker compose ps`、相关服务最近日志和最后一次健康响应。

## 7. 总入口脚本设计

### 7.1 参数和输入

`run-demo-smoke.ps1` 是唯一正式入口，建议支持以下参数：

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `-ProjectName` | 自动生成 | 覆盖 Compose project name；必须经过安全字符校验。 |
| `-ApiPort` | `18000` | API 宿主端口；冲突时可由脚本选择空闲端口。 |
| `-FrontendPort` | `15173` | 前端宿主端口。 |
| `-Build` | `true` | 是否执行镜像构建；正式干净验收默认开启。 |
| `-Category` | `all` | 执行全部已接入分类，或只执行一个 manifest 名称。 |
| `-KeepArtifacts` | `true` | 默认保留报告；显式关闭时仅在用户明确接受后删除报告。 |
| `-KeepContainers` | `false` | 仅用于诊断失败现场；正式验收不得开启。 |
| `-WaitTimeoutSeconds` | `180` | 服务启动和健康检查总超时。 |

脚本启动时读取 `tests/demo-smoke/compose/.env.demo-smoke.example` 对应的本地配置，运行时值写入 `runtime/<run_id>.json`，不写回模板，也不输出 Secret。

### 7.2 分类脚本调用协议

总入口通过一个受版本控制的 manifest 确定分类顺序。每个已接入分类脚本必须接受同一组参数：

```text
-BaseUrl <API base URL>
-FrontendUrl <frontend URL>
-RunId <run id>
-ArtifactDir <absolute artifact directory>
-RuntimeDir <absolute runtime directory>
-FixtureDir <absolute fixture directory>
```

脚本约定：

- 返回码 `0` 表示该分类全部检查通过；非零表示分类失败或阻塞。
- 将结果写入 `<ArtifactDir>/categories/<category>.json`，至少包含 `schema_version`、`run_id`、`category`、`status`、开始/结束时间、检查数组和证据路径。
- 失败时保留请求摘要、响应状态、容器日志引用和可复现输入，但不得写入 API Key、数据库密码、完整 Secret 或无必要的文档原文。
- 不自行执行 Compose down，不删除其他分类的 artifact，不改变测试 project name。
- 尚未接入的脚本在 manifest 中标为 `not_implemented`，总入口将整体状态定为 `not_ready`，而不是跳过后报成功。

### 7.3 结束和退出码

总入口维护原始测试退出码和清理退出码：

| 情况 | 总体状态 | 建议退出码 |
| --- | --- | ---: |
| 所有启用分类通过且清理通过 | `passed` | 0 |
| Docker/Compose 前提不满足 | `blocked` | 2 |
| 分类测试失败 | `failed` | 1 |
| 存在未接入分类或方案尚未具备可执行测试 | `not_ready` | 3 |
| 测试结束清理失败 | `cleanup_failed` | 4 |

即使分类测试中途失败、PowerShell 抛出异常或用户中断，脚本也必须进入 finally 清理流程；清理失败不能被原始测试失败覆盖。

## 8. 报告、证据和保留策略

每次运行生成 `artifacts/<run_id>/`，最少包含：

```text
artifacts/<run_id>/
├── summary.json                 # 总体状态、退出码、时间、版本和清理结果
├── summary.md                   # 面向人工阅读的摘要
├── manifest.json                # 本次实际调用的分类脚本和版本
├── categories/                  # 各分类 JSON/JUnit 报告
├── environment/
│   ├── compose-config.txt
│   ├── compose-ps-before.txt
│   ├── compose-ps-after.txt
│   ├── health-live.json
│   └── health-ready.json
├── logs/
│   ├── migrate.log
│   ├── api.log
│   ├── worker.log
│   ├── frontend.log
│   ├── postgres.log
│   └── redis.log
└── cleanup.json
```

`summary.json` 至少记录：

- `schema_version`、`run_id`、`compose_project`、当前 Git commit、开始/结束时间。
- 测试环境端口、Mock Provider 标识、owner 标识摘要和分类状态。
- 启动、测试、报告收集、Compose down、卷删除、runtime/tmp 清理各阶段状态。
- `passed/failed/blocked/not_ready/cleanup_failed` 的明确最终状态和退出码。
- 失败分类、阻塞原因、日志路径和后续复现命令。

artifact 默认保留，便于比较历史运行；其中不得包含 Secret、完整 API Key、数据库凭证、宿主绝对路径以外的敏感内容或不必要的完整文档原文。`runtime/` 和 `tmp/` 无论运行结果都必须清理，不作为报告保留手段。

## 9. 资源释放与残留检查

清理必须按以下顺序执行：

1. 停止分类测试进程，关闭 SSE、浏览器和 HTTP 客户端。
2. 收集 `docker compose ps -a`、服务日志和最后健康状态到 artifact；日志收集失败也要记录。
3. 执行 `docker compose down --volumes --remove-orphans`，目标只能是本次 `composeProject`。
4. 再次执行 `docker compose ps -a`，确认本次 project 没有容器；检查本次 project 创建的网络和卷已删除。
5. 删除精确的 `runtime/<run_id>` 和 `tmp/<run_id>` 路径；删除前验证路径位于 `tests/demo-smoke/` 内，禁止对仓库根目录或通配宽目录执行递归删除。
6. 写入 `cleanup.json`，包含每个清理步骤的命令摘要、结果、残留容器/卷/网络列表和时间。

`-KeepContainers` 只允许诊断时使用，并必须在 summary 中标记 `cleanup_deferred`；正式验收和 CI 兼容运行不得使用该参数。报告保留与容器/卷保留严格分离。

## 10. 分阶段实施路线

每个阶段完成后都要执行本阶段的静态检查和最小运行验证；未完成的后续分类脚本不影响基础设施阶段交付，但总测试入口必须如实返回 `not_ready`。

### 阶段 1：测试目录、命名和忽略规则

**新增/修改**：`tests/demo-smoke/README.md`、`tests/demo-smoke/specific_test_script/README.md`、`tests/demo-smoke/fixtures/README.md`、根 `.gitignore`、根 `README.md` 测试入口。

**工作内容**：创建本地测试资源边界、运行目录规则、报告命名、Secret 脱敏和清理说明；将 runtime/artifacts/tmp 加入忽略规则；不新增具体测试断言。

**退出条件**：目录职责清晰，README 能解释正式方案入口和历史结果记录的区别，Git 不会追踪运行凭据、日志和临时大文件。

### 阶段 2：Compose 测试覆盖和配置模板

**新增**：`tests/demo-smoke/compose/docker-compose.demo-smoke.yml`、`tests/demo-smoke/compose/.env.demo-smoke.example`。

**工作内容**：定义隔离 project 使用的 API/frontend 端口变量、测试 owner、Mock Provider、共享 uploads volume 和服务环境覆盖；不复制根 Compose 的完整服务定义。

**退出条件**：在 Docker daemon 可用时，叠加 Compose 文件可以通过 `docker compose config`；测试 project 不占用开发固定端口，不暴露 PostgreSQL/Redis 端口。

### 阶段 3：总入口脚本和生命周期闭环

**新增**：`tests/demo-smoke/run-demo-smoke.ps1`。

**工作内容**：实现预检、run_id、端口检查、Compose up、migrate/health 等待、manifest 调度、报告收集、finally 清理、残留检查和退出码映射。先允许分类 manifest 为空，但必须返回 `not_ready`，不能虚报成功。

**退出条件**：可在分类脚本为空时完成“启动 -> 健康检查 -> 报告 -> down -> 卷/网络清理 -> runtime/tmp 删除”闭环；任一阶段失败都能保留诊断并清理。

### 阶段 4：稳定 fixture 和分类脚本接口

**新增**：`tests/demo-smoke/fixtures/upload-safe/*`、必要的 `upload-invalid/*`、`expected/event-types.json`、分类脚本接口文档。

**工作内容**：准备小型、可审计的 txt/md/docx 输入和非法扩展名样例；定义分类脚本的参数、退出码和 JSON 报告 schema。超过 10 MiB、损坏二进制和路径逃逸输入由分类脚本在 `tmp/<run_id>` 中动态生成。

**退出条件**：fixture 不含 Secret，分类脚本可以只依赖明确的 `BaseUrl`、FixtureDir 和 ArtifactDir；临时大文件不会留在 Git 或 artifacts。

### 阶段 5：接入分类测试脚本

**范围说明**：本方案不直接实现这些脚本；后续按第 4 节顺序逐个接入，并复用阶段 3 的生命周期。

**接入顺序**：服务健康 -> Thread/Run API -> Worker lease/恢复 -> 文档 RAG -> Event/SSE -> 前端工作台 -> 故障/安全。

**退出条件**：每个分类脚本有独立报告、可重复输入和非零失败码；manifest 中所有启用分类均不再是 `not_implemented`。

### 阶段 6：正式验收和历史报告

**工作内容**：在 Docker Desktop 可用的本机执行干净构建、主流程、重启/故障注入和资源清理；将 summary、日志和分类结果保存在唯一 run_id 下。对照 PRD/ADR 和后续测试用例文档填写实际结果。

**退出条件**：所有启用分类通过，Compose 资源无残留，runtime/tmp 无残留，报告包含完整失败/跳过/阻塞信息；若任何质量门禁未执行，最终状态不能写成 `passed`。

## 11. 与当前仓库实际情况的衔接

1. 当前根 `docker-compose.yml` 已提供 `postgres`、`redis`、`migrate`、`api`、`worker`、`frontend`，测试方案复用它，不另建一套平行事实来源。
2. 当前 Demo 默认 Mock Provider、单 owner 和固定开发端口；测试覆盖文件负责把 owner、端口和 project 隔离，不能通过修改生产 Compose 默认值来实现隔离。
3. 当前 `docs/test/001-SesRAG-项目Demo-test.md` 是历史测试验收记录，不是本方案；它的已执行结果不能替代本方案规定的完整生命周期和残留检查。
4. 当前已有`tests/demo-smoke`隔离覆盖、总入口、fixture准备、manifest/Schema、接入计划及说明；具体分类脚本和用例仍未交付。当前Python测试、前端typecheck/build和环境启动验证不自动等价于Docker smoke全部通过。环境证据见[验证记录](001-SesRAG-Demo-临时测试环境验证记录.md)。
5. 当前调研已发现 deadline、Provider 错误分类、graceful shutdown、`task.leased`、前端终态恢复等差异；分类脚本必须将这些差异纳入失败或待验证报告，不得只验证最短成功链路。

## 12. 测试实施方案审批清单

- [x] 明确本机 Docker Compose 隔离部署方式、服务、端口、project name 和数据卷边界。
- [x] 明确 `tests/demo-smoke` 集中管理临时测试环境文件和 README，且与正式方案文档职责区分。
- [x] 明确总入口脚本从启动、等待、分类调用、报告收集到资源销毁的完整闭环。
- [x] 明确分类脚本目录、参数协议、退出码、报告 schema 和不直接修改事实来源的约束。
- [x] 明确 fixture、runtime、artifacts、tmp 的用途、保留/删除策略和 Secret 边界。
- [x] 明确可能新增和修改的文件、各自职责以及所属实施阶段。
- [x] 明确本方案不直接实施具体分类脚本、测试点文档和测试用例文档。
- [x] 明确测试失败、环境阻塞、未接入脚本和清理失败的不同最终状态。
- [x] 明确测试过程中断、失败和用户取消时仍需执行清理，避免容器、网络、卷和临时文件残留。

**审批结论**：本方案作为 Demo 正式测试实施基础设施的基线。它与 Demo PRD、ADR 和实施结果调研保持一致，先解决可重复、可隔离、可报告、可清理的测试执行闭环；具体分类测试脚本、测试点和测试用例必须在后续任务中按本方案接口接入，不得将未实现内容标记为已通过。

## 13. 环境实施细化（2026-10-06）

本节固定实际落地细节，其余章节中的“新增/后续”是原设计路线，不表示当前仍缺环境文件。具体文件和参数真源见[测试环境README](../../tests/demo-smoke/README.md)，分类接入计划见[test-plan.md](../../tests/demo-smoke/test-plan.md)。

- 新增`lib/smoke-common.ps1`、`self-tests.ps1`、`specific_test_script/manifest.json`及`category-result.schema.json`；self-tests只验证运行器基础设施，不是产品分类用例。
- 本机入口最低PowerShell7.4、Compose2.24.4。端口用`!override`替换，DB/Redis不发布，API/frontend只绑定127.0.0.1；project参数作为安全前缀，始终追加随机ID，并拒绝已有同名资源。
- DB密码每次随机生成，存于Git忽略的`runtime/<run_id>/compose.env`；运行元数据改为`runtime/<run_id>/context.json`，便于按整目录回收。环境输出/日志/报告脱敏，运行目录和工具缓存同时Docker忽略。
- 发现产品`migrations/env.py`不读取DATABASE_URL；新增测试专用`compose/run-migrations.py`将本次URL注入既有Alembic配置，仍运行同一正式迁移，不改产品代码或Schema。
- 前端VITE_API_BASE_URL覆盖为空，经已有Vite代理统一HTTP/SSE来源；根Compose跨域问题仍为产品差异，不用浏览器禁用安全策略回避。
- 增加独立BuildTimeoutSeconds=900，启动up和健康检查仍共享WaitTimeoutSeconds=180；增加SessionSeconds/Interactive供临时人工检查，CleanupRunId供诊断保留或中断后的精确恢复清理。
- 默认清理还删除本次唯一镜像tag，核对捕获的匿名卷；不做global prune。基础镜像/BuildKit/Playwright缓存和脱敏artifact有意保留，不承诺Docker宿主虚拟磁盘物理文件立即压缩。
- 正常清理runtime/tmp；清理失败时尽可能清tmp并保留最小runtime恢复凭据，不虚报无残留。KeepContainers诊断返回cleanup_deferred/5，正式验收不可用；原有0～4语义保持。
- txt/md为版本化小fixture，docx正文维护为XML并按固定ZIP时间生成到tmp；用例接收生成后的FixtureDir，结束删除，避免提交无用二进制和大文件。
- 全7类manifest当前not_implemented，部署/报告/清理成功仍返回not_ready/3。阶段5/6产品分类接入和正式验收不在本轮实施。

## 14. 后续测试准备任务更新（2026-10-07）

环境实施之后已另行设计149个测试用例并覆盖191个点，见[用例文档](../../tests/demo-smoke/test-cases.md)。本方案第11节“用例未交付”等文字为环境实施时的历史状态，不作为当前交付判断。

后续任务1～任务2补齐项目Python3.12开发环境及独立Node24.15+的浏览器/契约/Lint/组件工具，复核总入口并补UTF-8调用协议；没有跨用例统一SQL基线需求，数据准备见[策略](../../tests/demo-smoke/fixtures/data-strategy.md)。真实环境闭环、恢复清理、工具探针与剩余边界见[准备/审批记录](../../tests/demo-smoke/任务1-2准备与审批记录.md)。产品容器Node20/业务依赖及正式manifest未变，具体产品分类仍未接入，不能把工具自检当正式验收。

## 15. 分类实施任务更新（2026-10-07）

任务3将历史七大类占位拆为21前缀分类，按149用例设计接入真实断言，完整待补子项独立blocked。当前名称/脚本/用途/用例映射见[环境README](../../tests/demo-smoke/README.md#分类脚本与用例映射)，manifest为可执行调度真源。任务4试跑与独立校审见[实施记录](../../tests/demo-smoke/任务3-4实施与审批记录.md)；本方案之前章节“具体脚本未接入”只描述环境阶段历史，不代表当前交付状态。

新增固定HarnessScenario只限LIFE协议自检、doc-limit接受边界和rag-empty正式空库Run；使用同一总入口独立project及临时卷，薄入口不重复计主manifest覆盖。嵌套run身份持久登记至父runtime，分类finally及总入口CleanupRunId精确兜底，硬杀主入口仍须恢复；不接受任意外部manifest、global prune或改产品状态。无统一业务seed需求，新增大型数据只留本次临时范围。

当前试跑不能证明稳定性或全部PRD通过：完整E2事务/慢Provider、O双owner、E4真实HTTP协议驱动仍受限，产品缺陷按正确预期failed。正式两轮结果回填/测试和缺陷报告属任务5～6，不在任务3～4提前宣布通过。

LIFE新增固定`nested-recovery`分类超时父登记兜底自检；中文报告投影为`summary-详细.md`，当前完整入口需要宿主Node工具。QLT独立执行可调用真实FE子分类并以完整检查集合校验，受控SSE断线只限本例字节透传，不代替普通离线/慢Provider完整场景。实际试跑和审查修正证据以任务3～4记录为准。

## 16. 正式两轮测试与结果交付（2026-10-07）

任务5～6已在相同dirty工作区、164个被测产品/脚本/契约/锁/fixture文件冻结不变的基线上，依次完成`20261007t072506-2fc5b075`与`20261007t075158-2907bbdf`两个完整all。各21分类、423检查；分别通过236/237、失败69/68、受限118/118。主入口均failed/1，部署/报告收集/清理均passed；唯一状态波动为WK_023数据库恢复，不得以第二轮通过覆盖第一轮失败。

结果与PRD八项验收见[测试报告](../../tests/demo-smoke/测试报告.md)，失败并集和局部/暂不可共104条问题登记见[缺陷报告](../../tests/demo-smoke/缺陷报告.md)，真实命令、冻结/资源证据与校审见[执行审批](../../tests/demo-smoke/任务5-6执行与审批记录.md)。[用例](../../tests/demo-smoke/test-cases.md)已填149实际结果及104复现/稳定性，45暂不可完整动态后两栏按要求保留空。前述“待正式验收”等是各阶段历史；当前是执行闭环与报告完成，不是产品验收通过。修复/补驱动后须重新完整验证。

## 17. ADR-002 修复阶段的验证边界（2026-10-12）

当前按 [ADR-002](../adr/002-SesRAG-Demo-缺陷修复-plan.md) 修复代码和测试工程，旧两轮结果继续作为缺陷基线，不覆盖为新通过记录。本阶段先补本机可满足的慢 Provider、真实 PG 多连接、故障/清理驱动，再冻结更新后的实现执行完整两轮。最终结论、明确暂缓及纳入但未解决事项在 `tests/demo-smoke/复测和验收报告.md` 中交付；此节不是测试结果。

确定性故障测试允许测试目录内的进程导入正式 application、Queue、Journal、Runtime/Handler，并用该用例的 session factory 或 Port 包装屏障/一次故障；仍由生产业务函数创建及推进 Thread/Run/Task/Document，不以 SQL 修改 state、seq、generation 伪造条件。SQL 观察连接保持只读；真正的 PG 锁/接管竞争不能由 SQLite 或组件传输替身代替。测试 bootstrap、协议替身和控制路由不得加入正式生产 API。

常规环境继续要求 Redis 正常和 Worker 可见心跳；专用 Redis 冷启动降级场景单独使用已确认的就绪条件，验证 PG 权威业务可继续，不全局放宽普通门禁。迁移版本比较使用当前固定迁移目录的真实 Alembic head，不硬编码旧 `0001`。运行时随机数据库凭据同时映射根 Compose 必填环境变量，不输出密码。

`OWN_001`、`PAR_004`、`FE_009 ordinary-browser-offline`、真实外部模型效果和生产容量按 ADR-002 暂缓；其他已纳入的仓库可补条件不能仅以“驱动尚未准备”宣称修复完成。分类原报告保留 failed/blocked；含明确暂缓的 all 即使纳入检查全部通过，严格主入口仍可能非零，验收报告必须解释两种口径，不修改退出码强行 passed。
