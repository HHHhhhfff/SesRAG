# ADR-002：SesRAG Demo 缺陷修复实施方案

- **文档类型**：问题缺陷修复实施方案 / 架构决策 ADR
- **编号**：002
- **版本**：v1.1（实施结果metadata同步，原决策范围不变）
- **状态**：已实施（仅纳入修复范围及本机可验证目标；LIFE_006可捕获Ctrl+C原P0平台变体未完整动态验收，方案暂缓保持blocked；2026-10-13该范围独立规格✅/质量Approved）
- **日期**：2026-10-13（UTC+8；原方案2026-10-11）
- **产品/适用范围**：SesRAG Demo 当前分支 `sesrag_v0.1` 的代码、部署、契约、前端和本机隔离测试工程；不扩展为完整项目 PRD2/PRD3/PRD4。
- **对应阶段/依赖**：001 Demo PRD 实施及两轮正式测试验收之后的缺陷修复阶段；以 001 Demo PRD、对应实施方案、调研文档和本轮测试结果为输入。本文件已使用用户指定的 `-plan.md` 文件名，正文类型为 ADR，不再新增 `docs/prd/` 下的重复 PRD。
- **依据**：
  - [001 Demo PRD](../prd/001-SesRAG-项目Demo-PRD.md)
  - [001 Demo 实施方案](001-sesrag-demo-implementation-plan.md)
  - [两轮正式测试报告](../../tests/demo-smoke/测试报告.md)
  - [缺陷报告](../../tests/demo-smoke/缺陷报告.md)
  - [测试用例](../../tests/demo-smoke/test-cases.md)
  - [测试点及需求覆盖矩阵](../../tests/demo-smoke/测试点设计与需求覆盖矩阵.md)
  - [接口文档](../接口文档.md)

实施证据：[PR002实际实施记录](../pr/002-SesRAG-Demo-缺陷修复-PR.md)及[复验报告§9](../../tests/demo-smoke/复测和验收报告.md)，正式两轮`20261012t212827-13fa1d31`/`20261013t014325-e2009999`在同一278文件冻结版本上执行、末check成功后才更新此metadata。纳入且本机可验证P0无failed，不声称所有P0全部动态通过；平台Ctrl+C限制与具体后续保留，真实SIGTERM/硬杀恢复/finally已实测。

## 1. 决策摘要

本 ADR 将两轮正式测试中已证实的实现缺陷、明确的静态风险，以及可在仓库内补齐的测试工程缺口，整理为一个可实施、可回归的修复包。修复的事实来源仍为 PostgreSQL；Thread、Message、Run、Task、RunEvent、Document、Chunk 的身份、状态和事件顺序不得由前端或测试脚本伪造。

本 ADR 的架构决策是：以数据库事实、条件写回和不可变快照作为一致性边界；以 Queue/Provider/Parser/Vector Store Port 隔离可替换基础设施；以本地可控测试驱动和两轮回归证据作为缺陷关闭门槛。文件变更按第 5 节和第 6 节的阶段顺序实施，未实施的项目不得提前标记为已完成。

本轮优先恢复以下不变量：

1. 同一业务身份只能产生一组幂等事实；终态、事件和最终 assistant Message 不可被迟到执行逆转。
2. Task 的 lease、generation、deadline、retry 和 Worker 停机行为有界且可恢复；旧 Worker 不能覆盖新执行者。
3. 文档索引失败必须明确结算，候选批次不能污染当前 active 索引；Provider 错误不得伪装成空知识回答。
4. API 健康、错误、SSE、前端状态和文档状态都必须是持久事实的安全投影。
5. 正式测试必须能在仓库内使用本地可控驱动验证关键时序，并保留真实失败和清理证据。

本 ADR 不把“测试脚本有记录”视为产品通过，也不把外部模型效果、生产容量和 Demo 明确非目标纳入本轮承诺。

### 1.1 编号与来源约定

- `RM-01` 至 `RM-08` 是本 ADR 内部的修复包编号，用于实施分工、文件映射和阶段退出条件。
- `DEP_*`、`MSG_*`、`RUN_*`、`WK_*`、`CAN_*`、`DOC_*`、`PAR_*`、`IDX_*`、`RAG_*`、`EVT_*`、`SSE_*`、`FE_*`、`SEC_*`、`PERF_*`、`ARC_*`、`QLT_*`、`LIFE_*`、`OWN_*` 是 `tests/demo-smoke/test-cases.md` 的测试用例编号；测试报告和缺陷报告沿用同一编号。
- `TP-*` 是 `tests/demo-smoke/测试点设计与需求覆盖矩阵.md` 的测试点编号；它用于测试点追溯，不替代测试用例编号。
- “测试报告/缺陷报告”均指 `tests/demo-smoke/测试报告.md` 和 `tests/demo-smoke/缺陷报告.md`；表中出现的用例编号默认可回溯到这两份报告及其测试用例卡片。
- 文中“001 Demo PRD §9”均明确指向 `docs/prd/001-SesRAG-项目Demo-PRD.md` 的第 9 节，不指向本文件。

## 2. 当前基线与问题范围

两轮测试基线如下：

| 项目 | 结果 |
| --- | --- |
| 正式运行 | `20261007t072506-2fc5b075`、`20261007t075158-2907bbdf` |
| 分类/检查 | 每轮 21 分类、423 个检查 |
| 子项结果 | 第一轮 `236/69/118`，第二轮 `237/68/118`（通过/失败/受限） |
| 两轮并集的执行结果分布（互斥） | 45 个用例的已记录检查全部通过；39 个含失败（含 WK_023 不稳定）；25 个局部通过但仍有受限子项；40 个纯受限、未实际断言；合计 149 个用例 |
| 原设计的动态可验证性分类（与上行结果分布交叉，不重复计数） | 45 个用例被设计为暂不可完整动态验证，其中 5 个有局部断言；完整限制仍未解除 |
| 清理 | 两轮 Compose、网络、卷、唯一镜像 tag、runtime/tmp 均清理成功 |
| 主要缺口 | 幂等并发、Task/Run 终态、重试回排、健康真实性、SSE 边界、前端事实投影、Provider 协议、测试时序驱动 |

问题来源分为三类：

- **类型1：代码、契约、迁移或配置缺陷**。可通过仓库代码/文件修复，但必须补迁移、契约和回归测试。
- **类型2：本机测试条件限制**。例如当前 Chromium 对已建立空闲 SSE 的普通 `setOffline` 不产生断线事件；不能把环境限制写成产品已经失败。
- **类型3：测试工程或观测条件缺口**。包括慢 Provider、真实 PG 双连接屏障、双 owner 配置、本地 HTTP Provider 替身、清理故障哨兵等。本轮优先在仓库内补齐；补齐前不能写成通过。

## 3. 修复边界

### 3.1 本轮纳入

- `backend/`：配置校验、API 错误和健康、会话幂等、Run/Task 终态、Worker 队列和 lease、RAG/Provider/存储、日志和错误脱敏。
- `frontend/`：增量临时投影、终态事实刷新、事件去重/重连、Run/Document/健康状态展示、Thread 切换隔离和引用展开。
- `migrations/`、`contracts/`、`docker-compose.yml`、`.env.example`、`docs/接口文档.md`：数据库约束、Event/API 契约、Secret/依赖边界和迁移历史稳定性。
- `tests/` 与 `tests/demo-smoke/`：本地慢/失败 Provider、双连接屏障、HTTP 协议替身、故障 Compose/harness、HTTP 全字段契约和质量门禁；所有测试资源必须纳入总入口清理。
- `README.md`、模块 README、Runbook 和测试文档：同步新的环境变量、迁移、错误语义、测试命令和验收证据。

### 3.2 本轮不纳入

- 生产认证、RBAC、多租户和完整 `OWNER_ID` 访问模型。Demo 当前明确使用单一 `local-user`，不因 `OWN_001` 的双 owner 动态条件缺失而偷偷增加认证系统。
- 真实外部模型的效果、长期容量、生产 SLO、真实 Key 和供应商服务稳定性。Provider 协议使用本地替身验证，Mock 不证明检索效果。
- 未经产品范围确认的 docx 表格、页眉、文本框等全部区域支持。`PAR_004` 保留为范围澄清项，不直接把观察结果升级为 P0 功能承诺。
- 普通浏览器离线模拟这一特定环境条件。`FE_009` 的受控 socket 断线和重连产品逻辑仍纳入；`ordinary-browser-offline` 因类型2环境限制暂缓。
- 完整项目的 DocumentVersion 审核/发布、工具授权审计、人工 Checkpoint 和 MQ 替换；这些属于完整项目路线图。

## 4. 修复包与详细需求

优先级定义：P0 为事实、状态、数据安全和核心验收阻断；P1 为主要用户行为、可观测性和测试闭环；P2 为架构一致性和非阻断质量改进。

### RM-01：配置、部署、健康与数据库约束（P0）

**对应问题**：`DEP_005`、`DEP_006`、`DEP_007`、`DEP_008`、`DEP_009`、`HLT_002`、`HLT_003`、`ARC_003`。

**问题和原因**：

- 根 Compose 在 `docker-compose.yml` 的 postgres/migrate/api/worker environment 中写死数据库凭据；测试 Compose 的随机凭据不能修复根部署边界。
- `backend/config.py:Settings` 接受零值、负值和 `heartbeat >= lease TTL` 等非法组合；向量配置可改为 128，但 `EmbeddingType` 的 PG 列固定为 `vector(384)`。
- 初始迁移缺少 `messages(thread_id, idempotency_key)` 唯一保护和 Task `kind/run_id/document_id` 互斥 CHECK。ADR §4.2 的“应用校验”和 §6.1 的“数据库检查”口径也需要统一。
- `ready` 未执行真实 PG/Redis 有界探测；数据库异常返回 500 而不是稳定 503，Redis client 非空会被误判为 ready。Compose 又硬依赖 Redis healthy，与通知降级设计冲突。
- `migrations/versions/0001_initial_demo.py` 使用当前 ORM 的 `Base.metadata.create_all/drop_all`，历史迁移会随未来模型漂移。

**代码/文件定位**：`docker-compose.yml`、`.env.example`、`backend/config.py`、`backend/api/routes/health.py`、`backend/app.py`、`backend/infrastructure/events/redis_notifier.py`、`backend/db/models.py`、`migrations/versions/0001_initial_demo.py`、`docs/接口文档.md`。

关键对象/函数：`Settings`、`health.ready`、`application_error_handler`、`RedisNotifier.connect/ready_worker_count`、`EmbeddingType.load_dialect_impl`、`MessageModel.__table_args__`、`TaskModel`、初始 Alembic `upgrade/downgrade`。

**影响范围**：部署 Secret 暴露面、服务启动与就绪判断、PG/Redis 故障时的可用性，以及新旧数据库升级后的完整性约束；错误可能导致部署拒绝启动、错误报告健康，或将无效事实写入数据库。

**待修复内容**：

1. 统一运行时 Secret 注入。Compose 只引用运行时环境变量或 Docker Secret，`.env.example` 只提供说明性占位值；Secret 不进入镜像、前端、Event、默认日志。
2. 在 Settings 初始化阶段校验所有正值、组合关系和支持的向量维度。若 Demo 只支持 384，非 384 必须明确拒绝；不得允许配置启动后才在 PG 写入时失败。
3. 本 ADR 将数据库完整性目标明确为：Message 幂等复合唯一；Task kind 与 run/document 关联互斥 CHECK；保留已有 seq、FK、唯一约束。实施时先修订 ADR-001 §4.2/§6.1 的“应用校验/数据库约束”冲突，再补 Alembic 迁移。迁移必须是固定 `op` 定义，不能继续依赖当前 ORM metadata。迁移不得静默删除既有数据；增加唯一约束前须检测冲突并以可诊断方式中止，降级不得误删业务表或用户事实。
4. `live` 只表示进程存活；`ready` 对 PG、Redis、Worker 分别执行有界探测并返回稳定状态。数据库连接异常映射为安全 503/错误码；Redis 不可用时仍能以 PostgreSQL 事实来源启动并标记降级。
   请求校验失败仍返回 HTTP 422 和可诊断的字段位置/错误类型，但不得回显无效输入、原异常上下文或上游 URL；完整响应契约和前端生成类型须同步。原始响应安全扫描须发生在测试运行器自动脱敏之前。
5. 根 Compose 的 Redis 依赖与降级策略一致：Redis 冷启动失败不能阻断 PG 权威业务启动，通知延迟/降级必须可观测。
6. 2026-10-13 全量审查补充：根 Compose 必须同时向 API/Worker 显式传入 VECTOR_DIMENSION、RAG_TOP_K、CHUNK_SIZE、CHUNK_OVERLAP，默认与 Settings 一致（384/5/800/120）。验证须经过根 Compose 解析和隔离容器真实启动/消费，覆盖非法值拒绝、快照和切分/召回，不能只直接构造 Settings；不复制 `.env` 或 Secret 入镜像。

**预期结果和验收标准**：

- 新环境不打印固定数据库密码；扫描 Compose、镜像和前端产物不得发现测试 Secret。
- 非法 lease/heartbeat/retry/deadline/vector 参数在启动前失败并返回可诊断错误；384 配置与 PG 列一致。
- 重复迁移不改变事实；迁移历史不受当前 ORM 修改影响；实际 PG 目录存在要求的唯一/CHECK 约束。
- 停 PG 时 `ready` 不再宣称 database ready，业务依赖错误为稳定 503；停 Redis 时显示 degraded 且 Thread/Message/Run 事实仍可写入/读取。
- 新增 DEP/HLT/QLT 对应检查两轮通过；迁移、健康、Compose smoke 和迁移回滚测试通过。
- 从已有 `0001_initial_demo` 数据库升级时，既有 Thread/Message/Run/Task/Event/Document/Chunk 行保持不变；如唯一约束数据冲突，迁移整体失败并报告冲突，不做自动合并/删除。

### RM-02：Thread/Message/Run 事实幂等和事务边界（P0）

**对应问题**：`MSG_001`、`MSG_006`、`MSG_007`、`MSG_008`、`RUN_002`、`RUN_003`、`RUN_004`、`RUN_005`、`RUN_006`。

**问题和原因**：

- Message DB 有 `created_at`，公开 Schema/投影缺失；独立来源语义未定义。Document 也缺少公开来源语义。
- `create_message_run` 在锁 Thread 前查询幂等键，拿锁后不复查；数据库缺幂等唯一，普通并发已实际产生多组 Message/Run/Task。
- RunSnapshot 模型/检索配置存在硬编码或使用运行时 Settings，跨配置时可能不遵守创建时快照。
- Handler 只防止 cancelled 重入，缺少 succeeded/failed 终态不可逆和单一 assistant 保护；用户 Message 与 assistant seq 分配未共享同一 Thread 锁协议。
- 初始/最终事务故障、重入和交错时序尚未有真实屏障，无法证明原子可见。

**代码/文件定位**：`backend/application/threads.py`、`backend/application/runs.py`、`backend/db/models.py`、`backend/api/schemas/threads.py`、`backend/workers/handlers/run_handler.py`、`migrations/versions/0001_initial_demo.py`、`frontend/src/types/api.ts`。

关键对象/函数：`create_message_run`、`get_thread_detail`、`get_run_detail`、`MessageResponse`、`RunModel.snapshot_json`、`process_run_task` 最终提交段、`append_event`。

**影响范围**：会话提交接口的重试与并发行为、Thread 内消息顺序、Run 的执行配置、最终回答持久化和重放；竞态可能造成重复用户消息/Run/Task、半完成结果或历史顺序不一致。

**待修复内容**：

1. 冻结公开 Message/Document 来源契约。Message `source` 表示 `user_input` 或 `assistant_generation` 等消息来源，不能只是 role 的重复；Document `source` 表示安全的逻辑来源（Demo 上传默认为 `local_upload`），不得公开宿主路径。同步 DB、Schema、投影、前端类型和接口文档，并保留 `created_at`。
2. 将幂等查询、Thread 行锁、锁内复查和写入放在同一事务；增加数据库唯一约束，唯一冲突时返回原始 Message/Run/Task，不产生第二组事实。
3. Run 创建时完整写入不可变快照；Handler 从快照解析模型、Provider、Top-K 等配置，不读取运行中变化的配置。
   升级恢复时需显式解释旧快照协议：旧版 `model=mock` 且仅含 retrieval/prompt version 的快照按该版本固定 384 维、持久 Thread owner 恢复，不写回修改快照，也不读取新默认值猜测。缺少可恢复真实 Provider 配置的快照以永久错误 `INVALID_RUN_SNAPSHOT` 明确结算；禁止为恢复成功静默切换模型。
4. 终态写回使用 `run_id + task_id + worker_id + generation` 和当前状态条件；succeeded/failed/cancelled 不可逆；assistant Message 按 Run 唯一创建，重复 Handler 必须幂等返回。
5. 用户和 assistant 分配 Thread `seq` 使用同一锁协议；最终 assistant、终态 Event、Run/Task 状态在一个事务边界内提交或整体回滚。
   实施细化（2026-10-12 真实 PG 回归发现）：在取得 Task/Run/Thread 锁后保留本代原始 lease/deadline，最终 assistant、状态和终态 Event 的数据库 flush/锁等待完成后、commit 前再校验该时间边界；不能因已在 ORM 中设为 succeeded 并清空 lease 就跳过校验。若写入等待期间跨越租约或硬截止，整个事务回滚，Thread 消息游标和 Run Event 游标也不得前移。对应 `complete_run` 及 RUN_005/WK_009/WK_025 的最终写回屏障。

**预期结果和验收标准**：

- 同 Thread 同 Key 的并发请求无论调度顺序都只返回一组 ID；不同 Key 不共享结果。
- RunSnapshot 与实际 Provider/检索调用参数一致；修改服务默认配置不会改变已创建 Run。
- 重复完成、旧 attempt、终态取消和最终 assistant 重入均不逆转或重复写入；事件 seq 单调且无缺口。
- 注入初始 flush、最终 commit、双事务交错故障时，事实整体回滚或整体可见，不出现半完成状态。
- MSG/RUN/EVT/QLT 相关新增屏障测试在真实 PostgreSQL 上两轮通过。

### RM-03：Worker lease、重试、deadline、停机和日志（P0）

**对应问题**：`WK_001`～`WK_025`（`WK_003`、`WK_016`、`WK_023`、`WK_024` 已有动态失败或不稳定证据）、`HLT_004`、`CAN_006`。

**问题和原因**：

- 默认 `worker_id` 只用 PID，跨容器可能碰撞；领取/续租/成功写回的条件和提交时保护不完整。
- `retry_waiting` 没有到期回排为 `queued` 的入口；queued 超过 deadline 也没有结算路径；达到 attempt 上限只改 Task，可能不结算 Run/Document/Event。
- 失租后 Handler 没有停止昂贵步骤；运行中 deadline、SIGTERM grace、readiness TTL 和当前任务等待没有统一边界。
- DB 异常发生在 `run_forever` 的 Handler 捕获范围外，缺有界重连退避；WK_023 两轮一失败一通过，根因未定位。
- claim/success/renew/retry/release 日志缺少结构化关联字段。

**代码/文件定位**：`backend/workers/runtime.py`、`backend/workers/main.py`、`backend/infrastructure/queue/postgres_queue.py`、`backend/workers/handlers/run_handler.py`、`backend/workers/handlers/index_handler.py`、`backend/db/models.py`。

关键对象/函数：`WorkerRuntime.__init__/run_once/_lease_heartbeat/_record_run_failure/run_forever/heartbeat`、`claim_next_task/renew_lease/mark_running/mark_succeeded/schedule_retry/requeue_expired`、`process_run_task/process_index_task`。

**影响范围**：所有 Run 与索引 Task 的分发、重试、deadline、Worker 故障恢复和停机；异常可能导致任务永久滞留、重复副作用、旧 Worker 覆盖新执行结果，或无法从日志定位任务执行者。

**待修复内容**：

1. Worker 身份由运行时生成稳定且跨实例唯一的 ID；显式 `WORKER_ID` 仍可用于测试和诊断。
2. Worker 的 claim、renew、mark running/succeeded、retry、release、run.started、增量 Event 与初始 Document indexing 写回，必须在全部可能阻塞的 flush 后、commit 前复查本代授权 lease/deadline。续租使用变更前的授权时间，领取使用新生成的本代时间，清空 lease 或设终态不能免除检查；越界整体回滚。旧 generation 只能得到安全拒绝并有审计事件。2026-10-13 全量审查细化：原句把“回收”也纳入未过期条件，与调度器合法到期结算冲突；requeue_expired、settle_failure(require_active=False) 和取消独立按其锁/状态规则执行，不要求仍有效的 Worker lease。
3. 增加 `retry_waiting -> queued` 到期回排；统一 attempt 上限、deadline 和业务对象结算，保证 Run/Document/Task/Event 不互相矛盾。
4. 在每个昂贵步骤前检查取消、deadline 和 lease；失租停止后续 Provider/检索/增量。SIGTERM 停止领取新任务，当前任务在 grace 内完成、释放或等待有界回收。
5. 将数据库领取/回收异常包在队列循环边界，采用有界退避并恢复；readiness 心跳与任务 lease 心跳分离。
6. 使用结构化日志 formatter，所有六类动作至少包含 `task_id`、`run_id`（Run 任务）或 `document_id`（索引任务）、`worker_id`、`generation`、`attempt` 和安全错误码。2026-10-12 实施审查细化：关联 ID 必须准确对应该动作的持久 Task，不能仅判断字段存在；索引任务 `run_id` 可以为空，但不能因此跳过 `document_id`。原始日志安全检查须在运行器证据脱敏前完成。

**预期结果和验收标准**：

- 两个真实 PG Worker 只能一个领取同一 Task；旧 Worker 的续租、事件、成功和失败回写均不改变新代数事实。
- 临时错误按退避重试，达到上限后 Run/Document/Task 明确 failed；deadline 前后的 queued、running、retry_waiting 均有确定终态。
- DB 短断期间 Worker 不退出、不无限热循环，恢复后无需手动重启；若测试驱动未命中故障窗口，报告必须标记 blocked 而非 passed。
- SIGTERM、宽限内/超宽限任务、lease 过期和重启恢复均有真实 PG/容器证据。
- 日志可按关联 ID 追踪六类动作，且不泄露凭据、Prompt、文档原文或宿主路径。

### RM-04：取消、事件 Journal 和 SSE 边界（P0）

**对应问题**：`CAN_001`～`CAN_006`、`EVT_001`、`EVT_002`、`SSE_002`～`SSE_005`。

**问题和原因**：

- Worker 领取后没有追加 `task.leased`；并发 append/rollback 屏障缺失。
- 取消只在部分步骤检查；最终取消与成功提交缺少提交时互斥；`retry_waiting` 可能因回排缺失而处于不一致状态。
- SSE 不存在 Run 时已发送 HTTP 200，终态游标之后的空后缀继续轮询；历史补放和实时追加边界尚无确定性屏障。

**代码/文件定位**：`backend/infrastructure/events/journal.py`、`backend/infrastructure/queue/postgres_queue.py`、`backend/workers/handlers/run_handler.py`、`backend/application/runs.py`、`backend/api/routes/runs.py`、`contracts/run_event_v1.json`。

关键对象/函数：`append_event`、`claim_next_task`、`cancel_run`、`get_run_events`、`stream_events` 的握手前校验与 generator、`process_run_task` 各步骤检查。

**影响范围**：取消接口的终态竞争、Run 执行事件的可恢复性及浏览器订阅生命周期；客户端断线、重连或终态边界可能造成 Run 被错误取消、事件漏放/重复或 SSE 长时间不结束。

**待修复内容**：

1. 在领取事实事务中追加带 `worker_id/generation/attempt` 的 `task.leased` Event；并发追加和回滚保持 seq 无重复、无空洞。
2. 在 embedding、retrieval、model、delta 和最终提交边界检查取消/lease/deadline；取消与成功采用条件更新或锁保证先到者决定终态。
3. SSE 返回流前完成 Run/owner 校验；不存在 Run 返回正式 404/稳定错误码。
4. SSE 以 `after_seq`/`Last-Event-ID` 补放，处理历史读取与新追加交界；发送 terminal Event 后关闭，已越过 terminal 的空后缀也必须有界关闭。
5. 断线只停止观察，不取消 Run；客户端重连使用最后 seq 补放并去重。

**预期结果和验收标准**：

- 正常 Journal 顺序包含 `task.leased`，所有 Event 符合 v1 Schema，seq 严格递增。
- 取消步骤不再调用后续 Provider，迟到成功无法覆盖 cancelled；重复取消保持原终态。
- 不存在 Run 的 SSE 在握手前返回 404；终态和空后缀连接在约定时间内结束。
- 历史与实时事件无缺失、无重复；断线恢复不改变 Run 状态。

### RM-05：文档登记、解析、索引发布和 RAG Provider（P0/P1）

**对应问题**：`DOC_001`、`DOC_005`～`DOC_009`、`PAR_001`、`PAR_002`、`PAR_003`、`CHK_002`、`IDX_002`～`IDX_007`、`RAG_001`、`RAG_002`、`RAG_005`、`RAG_006`、`RAG_007`、`RAG_008`、`SEC_004`。

**问题和原因**：

- Document 来源契约和超长文件名错误不稳定；上传路由在大小校验前对 `UploadFile` 全量 `read()`。
- 保存成功后 commit 故障和不可写存储缺少精确故障驱动，且 `storage.save` 不在完整回滚边界内。
- 普通解析/源文件错误统一进入 retry_waiting，Document 停在 indexing；没有错误分类、到期回排和耗尽结算。
- 并发 index 查询/提交之间没有串行化；候选发布和 Task 成功分属两个事务；慢 Embedding 在长事务内执行。
- Parser 结果缺基础位置；Top-K 未拒绝 0/负值；Provider 未验证 JSON，真实 Adapter 使用 `stream:false` 只返回一次完整正文。
- 异常字符串可能进入 Task/Event/日志，截断不等于脱敏。

**代码/文件定位**：`backend/application/documents.py`、`backend/api/routes/documents.py`、`backend/api/schemas/documents.py`、`backend/infrastructure/storage/local_files.py`、`backend/infrastructure/rag/parsers.py`、`chunker.py`、`pgvector_store.py`、`backend/infrastructure/providers/openai_compatible.py`、`backend/workers/handlers/index_handler.py`、`backend/workers/handlers/run_handler.py`、`backend/infrastructure/queue/postgres_queue.py`。

关键对象/函数：`upload_document`、`create_document/list_documents/create_index_task`、`LocalFileStorage.save/read`、`ParsedDocument/parse_document`、`chunk_text/search_chunks`、`OpenAICompatibleProvider.embed/stream_answer`、`process_index_task/process_run_task`、`schedule_retry/requeue_expired`。

**影响范围**：上传资源使用和错误安全、Document 状态结算、索引重建期间旧索引可用性、检索证据完整性及模型错误对用户的表达；失败可能使文档卡在处理中、候选索引污染可检索结果，或把 Provider 故障伪装成无知识回答。

**待修复内容**：

1. 在流式/有界读取阶段拒绝超过 10 MiB 的上传；文件写入、DB commit、临时文件和源文件清理必须有明确事务边界，错误不得泄露路径或堆栈。
   文件名只作为安全展示标签，不控制存储路径；兼容已有路径样式输入时规范化为 Windows/Unix 分隔符下的 basename，保存及公开该安全逻辑名，存储仍由 UUID 决定。安全 Unicode/HTML 文字名保留纯文本显示；空名、控制字符和超长名明确拒绝。不得为通过安全检查无说明地把所有既有路径样式输入改为失败，也不得公开原宿主路径。
2. 为超长文件名、编码错误、损坏 docx、源丢失、空文档、Provider 错误分别定义稳定错误码和可重试/不可重试分类；不可修复输入直接结算 failed，普通临时错误按统一 Queue 回排。
3. 对同一 Document 的活动 index Task 使用行锁或唯一约束；重复请求复用同一 Task/batch。候选批次完成后再以原子事务切换 active，失败保留旧 active。
4. 将慢 Embedding 移出长数据库事务；提交阶段只做短事务，保证候选/active/Task 状态一致。
5. 定义 Parser 基础位置 DTO；保留 chunk 字符 offset，不把两者混为同一语义。`RAG_TOP_K` 必须大于 0；向量维度必须与配置/Schema一致。
6. OpenAI-compatible Adapter 校验 HTTP 状态、JSON 结构、向量维度、非空内容和错误分类；实现真正有界的流式响应消费，临时/永久错误由统一 Task Runtime 处理。
7. 统一异常公开摘要、错误码和日志脱敏；不把原始异常字符串写进公开 Event、Task 错误或默认日志。

**预期结果和验收标准**：

- 超限上传在有界读取阶段拒绝且无 Document/Task/文件残留；不可写/commit 故障有安全错误和精确清理证据。
- 坏输入明确 failed 或按约定重试并最终结算，Document 不永久停 indexing；正常空文档不产生 active 索引。
- 并发重建只存在一个活动 Task；失败重建不污染旧 active；发布和 Task succeeded 不出现半发布窗口。
- 解析结果、Chunk、Evidence 保留 document/chunk/位置/分数身份；K<=0 明确拒绝。
- 本地 HTTP/SSE Provider 替身覆盖 400/401/403/5xx/超时/畸形 JSON/三片流，结果符合错误和增量语义。

### RM-06：前端事实投影和工作台行为（P0/P1）

**对应问题**：`FE_003`、`FE_004`、`FE_005`、`FE_006`、`FE_008`、`FE_009`、`FE_011`、`FE_012`、`FE_013`、`FE_014`、`FE_015`，以及 `QLT_007` 中对应的 Vitest/Playwright 失败。

**问题和原因**：

- `appendAssistantDelta` 只追加已存在的 assistant；终态后不重新读取最终 Message。
- Run store 的 `append` 只改 events，不刷新服务端 Run 状态；失败原因不展示。
- replay 与 SSE 交界按 seq 去重但正文增量仍重复；完成 Message 还能继续追加历史 delta。
- EventSource 出错后直接 close，无重连编排；刷新只恢复 Thread/Document，不恢复 Run/事件。
- 文档上传后没有有界刷新 indexed/failed；引用只有静态 span；健康点没有 API/Worker/DB 实时事实；切 Thread 未隔离旧流。

**代码/文件定位**：`frontend/src/pages/WorkspacePage.vue`、`frontend/src/stores/thread.ts`、`run.ts`、`documents.ts`、`frontend/src/events/run-event-stream.ts`、`frontend/src/components/MessageTimeline.vue`、`RunTimeline.vue`、`DocumentUploader.vue`、`frontend/src/api/`、`frontend/src/types/api.ts`。

关键对象/函数：`WorkspacePage.ask/selectThread/bootstrap`、`threadStore.appendAssistantDelta/selectThread`、`runStore.observe/append`、`documentStore.load/upload`、`openRunStream/replayEvents`、MessageTimeline citation 渲染、RunTimeline 状态/错误渲染。

**影响范围**：用户在工作台中观察生成进度、最终回答、Run/Document 状态、失败原因、引用和健康状态的准确性；当前投影问题会让页面与服务端事实不一致，或在刷新、重连、切换 Thread 后显示重复、过期或串线内容。

**待修复内容**：

1. 建立以 `run_id` 为作用域的临时 assistant 投影；终态后用服务端最终 Message 替换，不把临时正文当持久事实。
2. 任何 terminal/状态事件到达后重新读取 Run/Thread 事实；展示 `last_error_code` 和安全摘要，停止按钮只按服务端状态显示。
3. 统一事件消费入口，以 `run_id + seq` 判定首次消费；完成 Message 不再追加历史 delta；replay 与 SSE 交界不重复。
4. 实现有界自动重连或明确重连入口，保存最后 seq；断线不得调用 cancel。
5. 刷新/切 Thread 时恢复对应 Run、事件和非终态订阅；关闭旧 stream，迟到回调必须带当前 Run/Thread 作用域。
6. Document 非终态执行有界轮询或事件刷新，终态停止并显示错误码；引用支持键盘可操作的展开详情，展示安全 document/chunk/location。
7. 调用健康接口并分别展示 API/Worker/DB 的 ready/degraded/unknown；不展示 Secret 或宿主路径。

**预期结果和验收标准**：

- 首个增量可见，最终正文和引用无需刷新即可与服务端一致且只出现一次。
- queued/running/succeeded/failed/cancelled 在页面按服务端事实变化；失败原因可诊断且不泄密。
- SSE 断线后能按最后 seq 补放，Run 不被取消；刷新和 Thread 切换不会串流。
- indexed/failed 文档状态和错误码可在页面更新；引用可展开查看证据身份。
- FE 组件、Playwright 正常/受控断线场景两轮通过；普通浏览器 offline 场景仍按暂缓项处理。

### RM-07：架构边界、迁移历史和技术栈一致性（P1）

**对应问题**：`ARC_002`、`ARC_003`、`ARC_004`。

**代码/文件定位**：`backend/workers/runtime.py` 与两个 handler 的具体 Adapter imports、`backend/domain/`（当前缺正式 Port 模块）、`migrations/versions/0001_initial_demo.py:upgrade/downgrade`、`frontend/package.json`、`frontend/src/main.ts`、`frontend/src/App.vue`、Demo PRD/ADR 前端栈说明。

**影响范围**：后续替换队列、解析器或向量存储时的模块耦合，旧环境重建/升级的一致性，以及团队按文档安装和维护前端依赖的确定性；这些问题主要影响演进和发布可靠性，不直接等同于某一用户请求的动态失败。

**待修复内容**：

- 定义非空 `QueuePort`、`VectorStorePort`、`ParserPort` 及 Provider 协议，Worker/Handler 通过注入依赖具体 Adapter；不为形式解耦增加无用层。
- 固定历史迁移，新增模型变化必须用新 revision；补升降级/漂移测试。
- 本轮确认 Demo 继续单页原生 Vue 组件，暂不引入 Vue Router 和 Naive UI 的页面运行依赖；更新 Demo PRD/ADR/README 的当前栈声明，删除未使用依赖（若确有实际调用则保留并记录）。完整产品可另行选择。不得为“消除静态失败”机械加依赖。

**验收标准**：架构扫描能定位 Port/Adapter 边界；历史 revision 在模型改变后仍产生相同 Schema；技术栈文档、package.json、入口注册和实际消费一致。

### RM-08：测试工程和质量门禁补齐（P1）

**对应问题**：`DEP_003`、`HLT_004`、`MSG_006`～`MSG_008`、`RUN_002`～`RUN_006`、`WK_001`、`WK_002`、`WK_004`～`WK_021`、`WK_023`～`WK_025`、`CAN_001`～`CAN_006`、`DOC_006`～`DOC_009`、`IDX_003`～`IDX_005`、`IDX_007`、`RAG_002`、`RAG_005`～`RAG_008`、`EVT_002`、`SSE_002`～`SSE_004`、`FE_003`、`FE_005`、`FE_008`、`FE_009`、`FE_011`、`FE_014`、`FE_015`、`SEC_004`、`PERF_002`、`ARC_002`、`QLT_002`～`QLT_006`、`LIFE_002`、`LIFE_006`、`LIFE_008`。

**代码/文件定位**：`tests/demo-smoke/specific_test_script/{run,wk,can,doc,idx,rag,evt,sse,fe,sec,perf,arc,qlt,life}-tests.mjs` 及对应 Python driver；`tests/demo-smoke/run-demo-smoke.ps1`、`lib/smoke-common.ps1`、`compose/`、`tooling/`。

**影响范围**：缺陷能否在本机稳定复现、并发与故障路径能否被真实验证、失败证据能否保留，以及修复后能否通过两轮回归确认；测试驱动缺失本身不证明产品行为通过或失败，也不能替代 RM-01 至 RM-07 的产品代码修复。

**待修复内容**：

1. 在 `tests/demo-smoke/tooling/` 增加可控慢 Provider、逐步屏障、提交故障、错误 Provider 和本地 OpenAI-compatible HTTP/SSE 服务；所有进程由总入口登记、超时和清理。FE 用例还须能创建真实 Thread/Run/Document，在真实 Worker 推进慢分片/终态，并通过只读 PG 诊断，而不只使用组件传输替身。
2. 增加真实 PostgreSQL 双连接/双 Worker 驱动，用于 lease、generation、seq、取消、重试、事务交错和过期回收；禁止 SQL 直接伪造业务状态。
3. 增加测试专用 Compose/harness 覆盖迁移失败、Redis 冷启动、DB probe、Worker/frontend readiness timeout、清理失败和 `CleanupRunId` 恢复；失败必须保留报告并返回非零。
4. 为所有正式 API 成功/异常响应建立版本化 JSON Schema，并校验前端类型与契约同步；补齐 Journal/SSE、真实 PG lease、retry/cancel、RAG 发布门禁。租约回归包括 queued deadline、WK_023 故障命中窗口和 recovery、claim/success 结构化日志；前端回归包含 Document 状态、健康故障态和 Thread 切换迟到流。
5. 完成首执行事件延迟测量：订阅前置屏障、跨容器时钟校准、预热后20个样本、负载和误差记录；每个样本从本次 `run.started` 事实到客户端首次收到对应执行 Event 均小于2秒。不把 `run.created` 代替首执行事件；如果时钟误差/采样能力不足以判断2秒边界，继续标记blocked，不判通过或失败。
6. 修复迁移文件 Ruff import/format 问题；Vitest/Playwright 失败必须回到 RM-06 根因，不得通过放宽断言或跳过组件解决。处理本轮 ESLint 0 错误/57 警告的既有基线，逐项检查生产前端源码警告，修复有明确收益的警告；未处理项需说明原因，门禁不得新增警告。

**验收标准**：受限测试均能明确运行或明确返回 blocked；补齐后关键 P0 场景两轮通过，错误/超时/中断/清理都有原始证据；所有质量命令的实际退出码与报告一致。

### 4.9 修复包实施变更映射

下表把第 4 节各修复包的处理方向落到可执行的仓库变更。路径表示预期职责边界；实施时若发现实际模块路径不同，必须在实施结果文档中记录等价替换，不得把职责重新塞回路由、页面或 Worker 入口。

| 修复包 | 修改现有文件/目录及主要内容 | 可能新增文件/目录及主要职责 | 使用阶段 |
| --- | --- | --- | --- |
| RM-01 | `backend/config.py` 增加启动期参数组合校验；`backend/api/routes/health.py` 和 `backend/app.py` 统一 probe/503 错误；`docker-compose.yml`、`.env.example`、`docker/` 改为运行时 Secret 和 Redis 降级；`backend/db/models.py`、`migrations/versions/` 固化约束；`docs/接口文档.md` 记录健康契约 | `migrations/versions/0002_demo_integrity.py`（或等价新 revision）固定唯一/CHECK；`docs/runbooks/` 增加迁移和健康故障流程；`tests/demo-smoke/compose/` 增加故障 Compose | 阶段 1；阶段 5 回归 |
| RM-02 | `backend/application/threads.py`、`runs.py` 将幂等查询、锁内复查、快照和终态写回放入同一事务；`backend/db/models.py`、`backend/api/schemas/threads.py`、`frontend/src/types/api.ts`、`docs/接口文档.md` 同步 source/created_at/快照契约；`backend/workers/handlers/run_handler.py` 保护终态和 assistant 唯一性 | `contracts/message_v1.json`、`contracts/run_v1.json` 或等价版本化 Schema；`tests/demo-smoke/tooling/transaction-barrier.*` 提供真实 PG 双连接屏障 | 阶段 1 契约和迁移；阶段 2 事务闭环；阶段 5 回归 |
| RM-03 | `backend/infrastructure/queue/postgres_queue.py` 补齐 generation/lease/deadline/retry 条件更新和回排；`backend/workers/runtime.py`、`main.py` 增加停机、退避和稳定 worker_id；`backend/workers/handlers/` 在昂贵步骤前检查租约；统一日志配置 | `backend/workers/logging.py`（如现有日志配置无法承载关联字段）；`tests/demo-smoke/tooling/worker-barrier.*`、`tests/demo-smoke/compose/worker-fault.yml` | 阶段 2；阶段 5 回归 |
| RM-04 | `backend/infrastructure/events/journal.py`、`postgres_queue.py` 在同一事务写入 lease Event；`backend/application/runs.py`、`run_handler.py` 统一取消/终态条件；`backend/api/routes/runs.py` 修正 SSE 握手、补放和终态关闭；`contracts/run_event_v1.json` 固化事件字段 | `tests/demo-smoke/tooling/sse-harness.*` 和 `tests/demo-smoke/tooling/socket-fault.*` 产生可控断线、迟到追加和重连屏障 | 阶段 2；阶段 4 前端联调；阶段 5 回归 |
| RM-05 | `backend/application/documents.py`、`backend/api/routes/documents.py`、`backend/infrastructure/storage/local_files.py` 实施有界上传和清理；`backend/infrastructure/rag/` 补位置 DTO、候选/active 发布；`backend/infrastructure/providers/openai_compatible.py` 校验协议和流式响应；`index_handler.py`、`run_handler.py` 统一错误结算；`docs/接口文档.md` 更新错误码 | `backend/infrastructure/providers/test_provider_server.py` 或 `tests/demo-smoke/tooling/provider-server.*` 提供本地 HTTP/SSE 替身；必要时新增 `backend/infrastructure/rag/ports.py` | 阶段 3；阶段 5 回归 |
| RM-06 | `frontend/src/stores/`、`events/`、`api/` 实现 run 作用域投影、重连和事实刷新；`WorkspacePage.vue`、`MessageTimeline.vue`、`RunTimeline.vue`、`DocumentUploader.vue` 修正状态展示、引用和 Thread 隔离；`frontend/src/types/api.ts` 同步契约 | `frontend/src/events/reconnect-policy.ts`、`frontend/src/stores/run-projection.ts`（仅在现有模块无法清晰承载时新增）；`tests/demo-smoke/tooling/frontend-fixtures/` 提供真实 API 数据准备 | 阶段 4；阶段 5 回归 |
| RM-07 | `backend/domain/`、`backend/workers/handlers/` 抽离 Queue/Parser/Vector/Provider Port；`migrations/versions/0001_initial_demo.py` 固定历史定义；`frontend/package.json`、`main.ts`、`App.vue` 与 PRD/README 统一技术栈说明 | `backend/domain/ports/queue.py`、`parser.py`、`vector_store.py` 或等价 Port 文件；`tests/architecture/` 增加依赖方向和迁移漂移检查 | 阶段 4；阶段 5 质量门禁 |
| RM-08 | `tests/demo-smoke/run-demo-smoke.ps1`、`lib/`、`specific_test_script/` 接入真实屏障、Schema、Provider、故障和清理检查；`README.md`、Runbook、测试文档记录命令和证据 | `tests/demo-smoke/tooling/`（慢/失败 Provider、双连接、清理哨兵）；`tests/demo-smoke/compose/`（故障场景）；`contracts/*.schema.json`（正式 API/Event 响应）；必要的 `tests/demo-smoke/fixtures/` | 各阶段按需接入；阶段 5 全量回归 |

每个新增文件必须有唯一职责并在所属 README/Runbook 中登记。测试文件产生的进程和临时资源必须由总测试入口登记、超时和清理；测试故障配置不得污染开发 Compose、生产配置或 PostgreSQL 事实来源。生产部署修复仍按 RM-01 合法修改根 Compose。若实施中确认无需新增某个“可能新增”文件，应在实施结果中说明由哪个现有模块承接其职责。

## 5. 文件和目录变更清单

| 阶段 | 新增或修改位置 | 主要职责 |
| --- | --- | --- |
| 契约与迁移 | `contracts/`、`migrations/versions/`、`backend/db/models.py`、`backend/api/schemas/`、`docs/接口文档.md` | 固定 Message/Document 来源、Task 约束、Event/API 错误和兼容规则 |
| 配置与部署 | `backend/config.py`、`docker-compose.yml`、`.env.example`、`docker/`、Runbook | Secret、参数校验、健康探测、Redis 降级、依赖边界 |
| 会话与执行 | `backend/application/threads.py`、`runs.py`、`backend/workers/handlers/` | 幂等、快照、终态、取消、事务和错误结算 |
| 队列与 Worker | `backend/infrastructure/queue/`、`backend/workers/runtime.py`、`main.py`、日志配置 | lease/generation、回排、deadline、停机、退避和结构化日志 |
| RAG/存储 | `backend/application/documents.py`、`backend/api/routes/documents.py`、`backend/infrastructure/rag/`、`providers/`、`storage/` | 有界上传、解析位置、候选发布、Provider 协议、错误分类和脱敏 |
| 前端 | `frontend/src/api/`、`events/`、`stores/`、`pages/`、`components/`、`types/` | 事实刷新、临时增量、重连、恢复、健康和引用交互 |
| 测试工程 | `tests/demo-smoke/specific_test_script/`、`tooling/`、`compose/`、`fixtures/`、`run-demo-smoke.ps1` | 真实屏障、故障 harness、协议替身、Schema 门禁、报告和清理 |
| 文档 | `README.md`、`CONTEXT.md`、`docs/runbooks/`、`docs/test/`、本 ADR | 路由、稳定术语、可执行流程、回归结果和缺陷关闭记录 |

新增测试文件不得修改开发 Compose 的事实来源；必须使用唯一 project、owner、runtime/tmp 和总入口清理。新增环境变量必须在 `.env.example`、README 和 Runbook 中说明默认值、安全边界和是否必填。

### 5.1 现有文件/目录修改职责

| 现有位置 | 修改内容 | 主要目的 |
| --- | --- | --- |
| `backend/config.py` | 增加正值、范围、组合关系和 Provider/向量维度校验 | 在进程启动前拒绝不可执行配置 |
| `backend/api/routes/health.py`、`backend/app.py` | 拆分 live/ready，执行 PG、Redis、Worker 有界探测并映射稳定错误 | 防止健康接口误报并统一故障语义 |
| `backend/application/threads.py`、`runs.py`、`documents.py` | 统一事务、幂等、快照、终态、取消和文档状态结算 | 保护持久事实和业务状态机 |
| `backend/infrastructure/queue/`、`backend/workers/` | 条件领取/续租/回排、deadline、停机、退避和关联日志 | 防止旧 Worker 写回及任务永久滞留 |
| `backend/infrastructure/events/`、`backend/api/routes/runs.py` | Event Journal 顺序、SSE 握手、补放和终态关闭 | 让事件投影可恢复且有界 |
| `backend/infrastructure/rag/`、`providers/`、`storage/` | 解析位置、候选发布、Provider 协议、错误分类和清理 | 保证索引与生成失败可诊断、可回滚 |
| `frontend/src/` | 以服务端事实刷新终态、按 run/seq 去重、重连和 Thread 隔离 | 避免页面显示临时或串线状态 |
| `migrations/versions/`、`contracts/` | 新增 revision 和版本化 JSON Schema，固定历史迁移 | 让数据库和接口演进可审计 |
| `README.md`、`docs/接口文档.md`、`docs/runbooks/`、`CONTEXT.md` | 更新命令、环境变量、错误语义、术语和故障处理 | 保持实现、文档和运维入口一致 |

### 5.2 可能新增文件/目录及使用阶段

| 新增位置 | 用途 | 使用阶段 |
| --- | --- | --- |
| `migrations/versions/0002_*.py` 及后续 revision | 固定数据库约束、兼容升级和安全降级 | 阶段 1、阶段 5 |
| `contracts/*_v*.json` | API、Message、Run、Event 和错误响应的版本化契约 | 阶段 1、2、4、5 |
| `backend/domain/ports/` | Queue、Parser、Vector Store、Provider 的最小端口协议 | 阶段 3、4 |
| `tests/demo-smoke/tooling/` | 慢/失败 Provider、双连接屏障、故障注入和只读诊断驱动 | 阶段 2、3、5 |
| `tests/demo-smoke/compose/` | 迁移失败、Redis/DB 故障、Worker/readiness 超时等隔离编排 | 阶段 1、2、5 |
| `tests/demo-smoke/fixtures/` | 可重复的文档、Provider 响应和边界数据 | 阶段 3、5 |
| `tests/architecture/` | Port 依赖方向、迁移漂移和契约同步门禁 | 阶段 4、5 |
| `docs/runbooks/` 新流程文档 | 部署、故障注入、清理和回归执行步骤 | 各阶段实施和交付 |

上述“可能新增”不是一次性承诺的文件清单；实施者应先复用现有模块，只有职责独立、生命周期稳定且无法由现有文件清晰承载时才创建新文件。

### 5.3 跨文件约束

1. 数据库字段、Pydantic Schema、`contracts/`、前端类型和 `docs/接口文档.md` 必须在同一变更中同步；不得只改其中一层。
2. 新增环境变量必须同时登记 `.env.example`、README 和 Runbook，并说明必填性、默认值、Secret 边界和测试覆盖。
3. 所有测试进程、网络、卷、临时镜像 tag、runtime/tmp 都由 `run-demo-smoke.ps1` 统一登记和清理；清理失败必须保留证据并返回非零。
4. 修复代码不得通过删除断言、放宽预期、直接 SQL 伪造状态或把测试替身当作生产效果证明来关闭缺陷。

## 6. 实施顺序与阶段退出条件

### 阶段 1：契约、迁移和配置基础

**输入/前置条件**：冻结当前 `sesrag_v0.1` 代码和数据库基线，确认两轮测试报告中的 104 个非完整通过用例仍可追溯；先修订 ADR-001 §4.2/§6.1 的约束口径。

**实施任务**：更新 `contracts/`、`backend/api/schemas/`、`backend/config.py`、健康路由、Compose/环境变量和固定 Alembic revision；补齐 Message 幂等、Task 关联互斥、向量维度及 PG/Redis probe。

**验证证据**：新空库 `alembic upgrade head`、重复升级、降级/再升级；非法配置启动失败；PG/Redis 停止时 ready/503/degraded 响应；只读 SQL 检查约束；Secret 扫描结果。

**退出条件**：迁移和约束测试通过，配置拒绝可诊断，健康接口不误报，已有事实未被迁移删除或改写；否则停在本阶段，不进入并发业务修复。

### 阶段 2：Task/Run/Worker 事实闭环

**输入/前置条件**：阶段 1 已通过；准备真实 PostgreSQL 双连接和可控 Worker/Provider 屏障，不允许用 SQL 直接伪造 Task/Run 终态。

**实施任务**：按 RM-02 至 RM-04 修改会话事务、快照、队列条件写回、回排、deadline、停机、Event Journal、取消和 SSE；接入 `tests/demo-smoke/tooling/` 的双连接、迟到写回和 socket 断线驱动。

**验证证据**：同 Key 并发只产生一组事实；旧 generation 写回被拒绝；retry_waiting 到期回排；deadline、SIGTERM、取消/成功竞争；Event seq 和 `task.leased`；SSE 404、补放、终态关闭和断线重连日志。

**退出条件**：真实 PG 双连接屏障覆盖旧 generation、重试、取消、终态和断线补放；所有旧写回被拒绝，终态不可逆且没有重复 assistant/Event。

### 阶段 3：文档、RAG 和 Provider

**输入/前置条件**：阶段 1 的向量维度、错误契约和 Task 状态已固定；准备隔离上传目录、文档 fixtures 和本地 HTTP/SSE Provider 替身。

**实施任务**：完成有界上传/清理、Parser 位置 DTO、候选批次与 active 原子切换、索引并发保护、Top-K/维度校验、Provider HTTP/流式协议和错误脱敏。

**验证证据**：doc/md/txt 正常与坏输入；超长文件名、10 MiB 边界、空文档、源丢失、不可写目录和 commit 故障；并发重建；Provider 400/401/403/5xx/超时/畸形 JSON/三片流；PG active 与候选只读查询。

**退出条件**：三格式正常/错误、候选发布、源丢失、错误结算、K/维度边界、协议畸形响应和安全脱敏均有独立证据；失败文档不永久停留在 indexing。

### 阶段 4：前端事实投影和架构一致性

**输入/前置条件**：阶段 2 的 Event/SSE 契约和阶段 3 的 Document/Provider 错误码已稳定；前端类型从版本化契约同步。

**实施任务**：完成 run 作用域临时投影、终态刷新、按 `run_id + seq` 去重、自动重连、刷新/切 Thread 隔离、Document/健康/引用展示；同时抽离必要 Port、固定历史迁移并校正文档技术栈。

**验证证据**：Vitest 组件状态转换；Playwright 正常、受控 socket 断线、刷新和切 Thread；API/Worker/DB 健康故障态；架构依赖扫描、迁移漂移检查、前端 typecheck/build/lint。

**退出条件**：组件和浏览器正常/受控断线/刷新/切换 Thread 两轮通过；前端只投影服务端事实；Port、迁移历史、技术栈文档一致。普通 browser offline 仍按第 8 节 blocked 处理。

### 阶段 5：测试门禁、全量回归和缺陷关闭

**输入/前置条件**：阶段 1 至 4 的变更已通过各自退出条件；冻结被测文件、镜像 tag、Compose project、测试 fixtures 和工具版本。

**实施任务**：完成 RM-08 的测试 harness、Schema 门禁、清理哨兵和报告汇总；执行 `run-demo-smoke.ps1` 的完整 all 至少两轮；同步填写测试用例、测试报告、缺陷报告和 `docs/pr/` 结果记录。

**验证证据**：每个分类脚本原始 stdout/stderr、summary JSON、PG/Compose 诊断、前后端质量命令退出码、清理资源审计和脱敏扫描；报告必须区分 passed/failed/blocked。

**退出条件**：

- `tests/demo-smoke/test-cases.md` 中纳入范围的失败项不再失败；暂缓项仍明确标记，不得伪造通过。
- `docs/prd/001-SesRAG-项目Demo-PRD.md` §9 的八项 Demo 验收逐项有真实证据；所有 P0 失败为 0。
- pytest、mypy、Ruff、前端 typecheck/build/ESLint、Vitest、Playwright、API/Event Schema 门禁结果可追溯。
- Compose、网络、卷、临时镜像 tag、runtime/tmp 无残留；报告和脱敏证据可复核。

只有阶段 5 的全部退出条件满足，且实施结果文档已记录实际文件、命令、结果和遗留 blocked 项，才允许把本 ADR 状态从“已接受”改为“已实施”。

## 7. 验收矩阵

| 验收域 | 必须验证的目标 | 证据 |
| --- | --- | --- |
| 配置/迁移/健康 | Secret 不落盘、非法参数拒绝、约束完整、ready/503/degraded 正确 | DEP/HLT/QLT 分类 JSON、迁移日志、只读 PG 查询 |
| 会话事实 | Message 来源/时间、并发幂等、快照、终态不可逆、seq/事务原子性 | MSG/RUN/EVT 分类、API 响应、PG 事实和 Event Journal |
| Worker | 唯一领取、lease/generation、回排、deadline、取消、SIGTERM、DB 恢复和日志 | WK/CAN/HLT 分类、Worker 日志、双连接屏障 |
| 文档/RAG | 有界上传、错误结算、候选隔离、发布原子性、证据、Provider 协议 | DOC/PAR/IDX/RAG/SEC 分类、文件清单、PG/HTTP 证据 |
| SSE/前端 | 重连补放、临时增量、终态刷新、失败原因、文档状态、健康和引用 | SSE/FE/QLT 分类、Playwright/Vitest 报告 |
| 架构/质量 | Port 边界、历史迁移、技术栈一致、完整门禁 | ARC/QLT、Ruff、mypy、类型检查和构建输出 |
| 测试生命周期 | 失败/中断/超时/清理故障可诊断且可恢复 | LIFE、总入口 summary、cleanup、资源审计 |

## 8. 暂缓项与明确忽略项

以下内容不是本轮修复验收的“通过条件”，但必须保留在后续路线或测试缺口记录中：

| 项目 | 对应用例/报告项 | 暂缓原因 | 后续处理 |
| --- | --- | --- | --- |
| Demo 双 owner/生产认证隔离 | `OWN_001` | 当前 Demo PRD 明确固定 `local-user`，未承诺认证/RBAC；增加双 API/Worker 会扩大产品范围 | 完整项目认证 PRD 冻结后另立需求；测试工程可保留 not-ready，不伪造通过 |
| docx 表格/页眉/文本框全区域 | `PAR_004` | PRD 只承诺 docx 解析纯文本和基础位置，未定义所有区域 | 先在 PRD/CONTEXT 明确支持区域，再单独修复和验收 |
| Chromium 普通 offline 空闲 SSE 断线 | `FE_009` 的 `ordinary-browser-offline` | 本机浏览器/代理条件无法可靠触发前置，属于类型2；受控 socket 断线重连逻辑仍必须修复 | 更换网络故障注入环境后补测 |
| 真实模型效果、外部 Key、生产容量/SLO | RAG Provider 的效果和性能外推 | Demo 使用 Mock 只证明流程、身份、错误语义，不证明效果和生产服务 | 完整项目 Provider/评测 PRD 单独定义 |
| 迁移失败/清理失败等故障若无法在当前主机注入 | `DEP_003`、`LIFE_002`、`LIFE_006`、`LIFE_008` 的外部故障变体 | 本轮只允许仓库内 harness；禁止破坏开发环境或全局清理 | 测试 harness 补齐后再运行；无法注入时保持 blocked |

暂缓不等于删除需求或修改原测试预期；任何暂缓项必须在后续报告中继续显示为 blocked/not-ready。

## 9. 需求与缺陷追踪关系

下表覆盖测试报告/缺陷报告中的所有 104 个非完整通过用例；同一用例可能同时落入代码修复和测试驱动两个修复包。

| 修复包/暂缓项 | 覆盖用例 |
| --- | --- |
| RM-01 | `DEP_005`、`DEP_006`、`DEP_007`、`DEP_008`、`DEP_009`、`HLT_002`、`HLT_003`、`ARC_003` |
| RM-02 | `MSG_001`、`MSG_006`、`MSG_007`、`MSG_008`、`RUN_002`、`RUN_003`、`RUN_004`、`RUN_005`、`RUN_006` |
| RM-03 | `HLT_004`、`WK_001`～`WK_021`、`WK_023`～`WK_025`、`CAN_006` |
| RM-04 | `CAN_001`～`CAN_006`、`EVT_001`、`EVT_002`、`SSE_002`～`SSE_005` |
| RM-05 | `DOC_001`、`DOC_005`～`DOC_009`、`PAR_001`～`PAR_003`、`CHK_002`、`IDX_002`～`IDX_007`、`RAG_001`、`RAG_002`、`RAG_005`～`RAG_008`、`SEC_004`、`SEC_005` |
| RM-06 | `FE_003`、`FE_004`、`FE_005`、`FE_006`、`FE_008`、`FE_009`、`FE_011`、`FE_012`、`FE_013`、`FE_014`、`FE_015`、`QLT_007` |
| RM-07 | `ARC_002`、`ARC_003`、`ARC_004` |
| RM-08 | `DEP_003`、`HLT_004`、`MSG_006`～`MSG_008`、`RUN_002`～`RUN_006`、`WK_001`、`WK_002`、`WK_004`～`WK_021`、`WK_023`～`WK_025`、`CAN_001`～`CAN_006`、`DOC_006`～`DOC_009`、`IDX_003`～`IDX_005`、`IDX_007`、`RAG_002`、`RAG_005`～`RAG_008`、`EVT_002`、`SSE_002`～`SSE_004`、`FE_003`、`FE_005`、`FE_008`、`FE_009`、`FE_011`、`FE_014`、`FE_015`、`SEC_004`、`PERF_002`、`ARC_002`、`QLT_002`～`QLT_006`、`LIFE_002`、`LIFE_006`、`LIFE_008` |
| 暂缓：Demo 非目标 | `OWN_001` |
| 暂缓：产品范围待确认 | `PAR_004` |
| 暂缓：本机浏览器条件 | `FE_009` 的 `ordinary-browser-offline` 子项 |

## 10. 完成定义与文档审批

本 ADR 只有在以下条件全部满足时才可将状态更新为“已实施”：

1. 每个 RM 修复包有代码/迁移/契约或测试文件变更记录，且 README/Runbook 已说明新增文件和命令。
2. P0 需求和对应测试点在真实 PostgreSQL、Docker Compose 和合法浏览器安全策略下两轮通过；暂缓项仍单独标记。
3. 所有 API/Event/数据库变更已同步 `docs/接口文档.md`、`contracts/`、Alembic、前后端类型和测试。
4. 回归报告列出每个原失败/受限用例的状态、证据、复现步骤和是否稳定；不以删除断言、放宽预期或仅运行静态检查关闭缺陷。
5. 资源清理、Secret 脱敏、日志关联和测试目录越界检查通过。

### 本次文档审批结论

- 已覆盖测试报告和缺陷报告中 104 个非完整通过用例；追踪矩阵列出每个用例的修复包或明确暂缓原因。
- 已区分代码缺陷、可在仓库内补齐的测试工程缺口、类型2环境限制和 Demo 非目标，没有把 blocked 伪装为 failed 或通过。
- 待修复内容包含问题解释、原因、代码/文件定位、影响、处理方向、预期结果和验收标准；阶段路线、文件变更和回归闭环明确。
- `DEP_008` 的 ADR“应用校验/数据库 CHECK”口径冲突已显式列为需澄清事项，不通过隐式改口径解决。
- `OWN_001`、`PAR_004`、普通 browser offline 和真实外部模型效果已明确暂缓，不影响本轮纳入范围的代码和测试工程修复。

**原方案审批结果（2026-10-11历史）**：本ADR获准作为实施基线，当时仅方案整理。**当前实施结果（2026-10-13）**：纳入修复已落地，真实两轮及追踪证据见开头链接；OWN/PAR全区域/ordinaryoffline暂缓、LIFE006原P0平台Ctrl+C仍未完整动态验收，2026-10-13独立规格✅/质量Approved仅批准纳入修复及本机可验证目标和本次交付，不批准上述未动态验收变体。
