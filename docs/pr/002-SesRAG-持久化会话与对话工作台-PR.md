# PR-002：SesRAG 持久化会话与对话工作台实施记录

- **编号**：003
- **版本**：v0.2（实施与分类验证阶段）
- **日期**：2026-10-20
- **状态**：PRD-002 功能已实施；
- **对应 PRD**：[PRD-002 持久化会话与对话工作台](../prd/002-SesRAG-持久化会话与对话工作台-PRD.md)
- **对应 ADR**：[ADR-002 持久化会话与对话工作台实施方案](../adr/002-sesrag-persistent-session-workspace-implementation-plan.md)
- **当前分支**：`sesrag_v0.2`

## 1. 实施结果摘要

v0.2 已在既有 Thread/Message/Run/Task/Event Journal、PostgreSQL/Worker 与 Vue 工作台基础上完成持久 Branch 路径、上下文预算/摘要计划、多 ModelProfile 与 RunSnapshot、schema 2 Run/Event、可恢复 SSE、显式取消/重试/重新生成及新工作台交互。v1 文档 API 保持原路径，v1 会话协议按 ADR-003 的 `conversation_version`/`execution_schema_version` 边界保留 legacy 读取并拒绝不兼容操作。

本记录汇总实施范围及实际验证结果。五个 v0.2 分类均有通过证据，但这不等于 PRD-002 完整验收；正式两轮 `all` 均因非全通过状态返回失败，ADR-003 的 §13.3 退出条件未满足，故保持“已接受”，不能标为“已实施”。

## 2. 主要模块与文件变动

### 后端领域、迁移与 API

- `backend/db/models.py` 扩展 Thread、Message、Run、Event、Task 并增加 Branch、SessionOperation、ModelProfile、ContextPlan、ConversationSummary 等 ORM 对象。
- `migrations/versions/0004_v2_session_branches.py` 增加 Branch/执行代际/用户输入复用和操作幂等事实；`0005_v2_profiles_context.py` 增加 Profile、上下文计划/摘要与 Run 关联；`0006_v2_run_guards.py` 增加状态、单 Branch 活动 Run 和单 Run Task 数据库约束。`migrations/v2_session_checks.py` 对迁移前冲突和 downgrade 事实执行只读保护。
- `backend/application/branches.py`、`session_threads.py`、`session_runs.py`、`session_operations.py`、`context.py`、`session_execution.py` 分别承担路径、会话投影/升级、Run 创建/显式操作、幂等、上下文算法和 Worker 执行发布边界。
- `backend/api/routes/v2/` 与 `backend/api/schemas/v2/` 新增 Thread/Branch/Model/Run/Context 请求和安全响应。既有 v1 路由文件 `backend/api/routes/threads.py`、`runs.py` 保留原文件和URL；实际版本守卫与并发适配新增在它们调用的 `backend/application/threads.py`、`runs.py` 中，不将沿用的路由文件列为本次代码修改。
- `backend/infrastructure/session/` 提供 Branch、Context、ModelProfile Repository；`providers/context_counter.py`、`providers/registry.py` 与 `providers/openai_compatible.py` 实现 Profile 计数/快照 Provider 重建、真实 HTTP/SSE 和稳定错误分类。

### 契约、前端和部署

- `contracts/` 新增独立 v2 Thread/Branch/Message/Run/Event/ModelProfile/ContextPlan/API 响应契约；`frontend/scripts/generate-api-types.mjs` 保留 v1 类型生成兼容并同步生成独立 v2 类型。
- `frontend/src/api/v2/`、`stores/branch.ts`、`stores/model.ts`、扩展的 `stores/thread.ts`/`stores/run.ts` 与 `WorkspacePage.vue` 将会话工作台切换至 v2；文档 client 继续走 v1。Branch/Model/Context/Run 操作组件和 `src/markdown/` 清洗入口负责交互与安全投影。
- `docker-compose.yml` 将 SSE 默认观察间隔设为 200ms；`.env.example`、`docker/api/Dockerfile`、`pyproject.toml` 与前后端版本元数据更新以支持本轮 Profile、TokenCounter 和契约生成。
- 更新 `README.md`、`backend/README.md`、`frontend/README.md`、`CONTEXT.md`、`docs/接口文档.md`、Demo 开发/隔离测试 Runbook；新增独立 TEST-002 和本实施记录。旧 Demo 的 `测试报告.md`、`缺陷报告.md` 不改写为 v0.2 结果。

### 测试工程

- 新增 `tests/demo-smoke/v2-test-cases.md`，与旧 149 个 Demo 用例分离；新增 `v2-session`、`v2-context`、`v2-model`、`v2-run`、`v2-workspace` 五类及 `tests/demo-smoke/tooling/mock-provider.py`、`pg-execution.py`、真实 Playwright/PG 探针和 profile fixture。
- 扩展 `run-demo-smoke.ps1`、Compose override、manifest、报告/覆盖 gate 和中文日志，保持一个随机 project、一个总入口及精确资源清理所有权。

## 3. 接口和契约变动

- 新增 `/api/v2` Thread、Branch、Model、Run、Context 与 Event/SSE 路由，JSON schema 独立于 v1；Event schema 1/2 通过互斥联合校验。
- v1 成功响应结构保持；Thread/Run 版本守卫在越界操作时返回 `409 API_VERSION_REQUIRED`，旧 Run 按 legacy 契约读取/取消，v2 新 Run 不投影成 v1。
- ModelProfile 不可用于新 Run 时返回 ADR-003 约定的 `409 MODEL_PROFILE_UNAVAILABLE`；不静默回退默认模型或 Mock。请求字段校验 422 与应用业务错误包装仍按接口文档区分。
- 新 Run 冻结非 Secret Profile/Prompt/RAG/上下文/执行预算；真实凭据只通过受信环境变量 alias 在 Worker 运行时解析，不进入 DB 快照、Event 或浏览器。

## 4. 已取得的验证证据

代码/测试持续工作区已验证：Python 文件编译、Node `.mjs` 语法、Ruff check/format（126个Python文件格式检查）、mypy（76个后端源码文件）、后端 `pytest tests/unit tests/api tests/integration -q`（267项通过，含离线tokenizer缓存的3个负样本）、前端类型检查/生产构建、前端完整Vitest（67项通过）、API双版本类型漂移、契约门禁及工具自检。前端Lint实际扫描29个源码文件，无error，有一条DOMPurify后Markdown的`v-html`规则提示；没有关闭该规则。

本机复现质量命令（仓库根目录，PowerShell）：

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path (Get-Location) 'tests/demo-smoke/.cache/ms-playwright'
.\.venv\Scripts\python.exe -m pytest tests/unit tests/api tests/integration -q
.\.venv\Scripts\python.exe -m ruff check backend migrations tests/unit tests/api tests/integration
.\.venv\Scripts\python.exe -m ruff format --check backend migrations tests/unit tests/api tests/integration
.\.venv\Scripts\python.exe -m mypy backend
npm run check:api --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
npm run lint --prefix frontend
npm run unit:frontend --prefix tests/demo-smoke
$toolTests=@(rg --files tests/demo-smoke/lib tests/demo-smoke/tooling -g '*.test.mjs')
node --test @toolTests
```

Node工具单测共47项：首次未设置项目内Chromium路径，45项通过、2个浏览器生命周期探针启动失败；设置上面的`PLAYWRIGHT_BROWSERS_PATH`后，这2项定向重跑均通过。2026-10-20接续任务再次使用上述完整工具命令，47项一次全部通过（0 failed/skip）。首次失败原因是调用环境未指向已安装浏览器，并非缺少浏览器或产品功能失败；总入口本身始终显式传递该路径。

v0.2 五个分类各自经隔离总入口运行通过，且每轮 `cleanup_status=passed`：`v2-session`、`v2-context`、`v2-model`、`v2-run`、`v2-workspace`。它们覆盖真实 PostgreSQL 迁移/锁屏障、受控 Provider HTTP 请求/Secret/重试、浏览器恢复/安全渲染、取消终态及 Journal/SSE。专项通过仅为分类证据，不替代 TEST-002 的两轮 `all`。

实施排错中发现并修复：测试 ESM 辅助导入缺失、PG 探针容器挂载路径错误、同步场景被异步 await、Context 溢出样本未超出 Mock tokenizer 预算、Run 操作 Event 查错 Journal、Profile 不可用状态码与 ADR 不一致、慢 Provider 注入走错 HTTP endpoint、工作台分类等待响应顺序/按钮名称匹配以及缺少 TP-VW-003 浏览器检查。这些测试工程修复均已纳入当前工作区，后续两轮必须在冻结后重新执行。

**正式两轮 `all` 结果**：两轮均执行26个分类，使用相同受测源码指纹 `5a142b23e4d965fcea86cbfe3fee1b54abc5efea9dc19a044164a20bbe085051`，各自 `source_unchanged=true`，清理均通过且容器、网络、命名/匿名卷均为零残留。

| 轮次 | run_id | 检查结果 | 总入口与差异 |
| --- | --- | --- | --- |
| 第一轮 | `20261020t101851-7e87ca31` | 539 passed、0 failed、18 blocked；26分类 | 总入口返回失败：`v2-workspace` 首次直接进程在 Playwright `waitForResponse` 等待10秒后超时。随后 QLT 独立重跑该分类4/4通过，但不改写总入口首次失败。 |
| 第二轮 | `20261020t112514-a937df2e` | 538 passed、1 failed、18 blocked；26分类 | 唯一失败为 `PERF_002` 的消息 POST 遇到 `UND_ERR_SOCKET / other side closed`；API access log 未见对应请求。根因未确认，不自动重发写请求。 |

18项 blocked 的组成是：`PAR_004` 完整 DOCX 非正文区域范围尚未由 PRD 明确、`FE_009` 普通浏览器离线断开无法由当前 Chromium 环境可靠注入、`OWN_001` 15项需要同一数据库中两套 owner API/Worker 的测试拓扑、`LIFE_006` Windows 环境无可靠 Ctrl+C 控制台注入方式。它们并非通过。针对 `PERF_002`，独立的 `20261020t122814-27cc9e5d` PERF 分类同指纹2/2通过，20个测量样本的首事件延迟上界最大约496.5ms；这说明失败具有非稳定性，但不能确定传输层根因，也不能冲销第二轮全量失败。

修正前 `20261020t091545-b9c1f523`（指纹 `9c83484d…`）的两项失败中，LIFE 硬杀夹具竞态已按真实 PostgreSQL Journal 状态修复并进入本轮验证；原运行保留为历史证据，不与最终指纹结果拼接。

## 5. 范围差异和后续边界

- 计划文件名与实际拆分对应关系已补在ADR-003 §9：Branch/Context算法测试拆成独立文件，执行/Provider集成集中于`test_v2_run_execution.py`和`test_provider_http.py`，fixture使用版本化Profile JSON与分类内独立动态数据。没有为匹配预计名称再创建重复实现。
- legacy纯函数`backend/domain/enums.py:RunState`及其状态边测试保留schema1范围；schema2的`cancelling`由v2契约/DTO、数据库CHECK及`session_runs.py`、`task_execution.py`、Queue专用确认路径明确处理。没有将v2状态硬塞进v1响应，也不能用旧状态边单测替代schema2取消竞态验收。
- 保持 PRD-002 非目标：不实现生产认证/RBAC/多租户、工具执行/人工审批、跨会话语义记忆、真实模型效果承诺、知识库版本化发布和生产 SLO。
- v0.2 分类使用本机受控 HTTP Provider 与 Mock，验证协议、状态机和证据身份，不代表供应商可用性或生产吞吐。
- 普通浏览器离线、Windows 可捕获 Ctrl+C、完整 docx 全区域、生产双 owner 按 PRD/ADR 范围继续单列受限，不得改写成已通过。
- ADR-003 仍为“已接受”；本次正式两轮和受限项已记录，但失败/blocked 未关闭，不能将 PR-003 标记为完整验收通过，也不能将 ADR-003 改为“已实施”。

## 6. 中断接续后的整体校审与修正

以下问题均先用失败测试或真实分类失败确认，再修正实现/测试条件；不是将未通过断言删除或改为无条件通过。

| 校审发现 | 原因与处理结果 | 主要文件 |
| --- | --- | --- |
| 真实Provider可误用Mock计数器 | 连续中文被词法计数为一个词，可能低估mandatory输入。真实Provider现强制显式tiktoken配置；本机受控HTTP fixture也使用真实encoding/框架开销。新增拒绝回归已先失败后通过。 | `backend/application/model_profiles.py`、`tests/unit/test_model_profiles.py`、`tests/demo-smoke/fixtures/v2-profiles.json` |
| 计数器缺缓存会隐式联网 | 探针确认SDK默认cache miss会下载词表，不符合离线/有界行为。现明确支持`cl100k_base`构建资产，先检查大小和固定SHA-256，缺失/损坏/未知encoding直接不可用；新增负样本先失败后通过，应用不负责下载。 | `backend/infrastructure/providers/context_counter.py`、`backend/application/model_profiles.py`、`tests/unit/test_model_profiles.py`、`tests/demo-smoke/tooling/README.md` |
| UI重试默认覆盖原模型 | 全局保存/默认选择并不是用户本次明确换模。Run观察时记录选择修订，未手动切换则省略覆盖字段，由服务端复制来源快照；legacy与明确换模仍携带成对Profile。原操作网络重发继续冻结payload。 | `frontend/src/stores/model.ts`、`stores/run.ts`、`pages/WorkspacePage.vue`、`tests/demo-smoke/tooling/v2-workspace.test.ts` |
| Embedding恢复读取可变配置 | retrieval原先只冻结模型名/维数，恢复可能改用新地址，且Mock判定错误依赖模型名。现冻结kind/base_url/Secret alias，Worker仅从快照重建；索引与检索的Mock配置语义一致。真实HTTP回归在创建后改变Settings，确认仍使用原地址/模型。 | `backend/application/session_runs.py`、`session_execution.py`、`backend/infrastructure/providers/registry.py`、`tests/integration/test_v2_run_execution.py` |
| Provider错误正文读取无界 | 原先错误响应先aread整段正文，绕过累计字节/绝对时长限制。现所有正文共用有界迭代读取；大错误正文与慢错误正文测试分别验证稳定超限/超时代码。 | `backend/infrastructure/providers/openai_compatible.py`、`tests/integration/test_provider_http.py` |
| 合法子分支显示错误Run、侧栏排序滞后 | 继承的父Run只作历史，不自动观察成当前分支Run；刷新、重命名、归档统一合并服务端摘要并按最近更新时间排序。新增组件失败回归后修正。 | `frontend/src/pages/WorkspacePage.vue`、`stores/thread.ts`、`tests/demo-smoke/tooling/v2-workspace.test.ts` |
| 旧FE夹具仍走v1/首片发布竞态 | 夹具补齐schema2 Provider入口和v2路径，等待PG首delta持久化后才截取重放快照；最终引用等待服务端Message事实刷新。保留真实HTTP/SSE/PG/浏览器断言，不在产品中增加测试专用开关。 | `tests/demo-smoke/tooling/pg_harness.py`、`frontend-harness.mjs`、`frontend-persistent.mjs`、`specific_test_script/fe-tests.mjs`、`fe-sse-transport.mjs` |
| v2性能与同源证据不足 | 新增30样本v2响应性测量；总入口记录源码前后指纹，包含未提交/未跟踪输入。指纹变化、时钟误差跨阈值均不得报告通过。独立v2-model分类显式上传自己的检索文档，消除对前序分类数据的依赖。 | `tests/demo-smoke/tooling/v2-performance.mjs`、`source-fingerprint.mjs`、`source-fingerprint.test.mjs`、`run-demo-smoke.ps1`、`specific_test_script/v2-workspace-tests.mjs`、`v2-model-tests.mjs` |
| 全量QLT跨版本轮询与启动预算错误 | 实际API日志确认v2 Run被测试矩阵通过v1入口读取，服务端正确返回409。矩阵改用v2轮询；正常exit7控制进程使用10秒有界启动预算，上方故障进程的1秒超时及树清理断言不变。23项契约负哨兵重跑通过；修正前完整运行保留为排错记录，正式两轮重新计数。 | `tests/demo-smoke/tooling/http-contract-matrix.mjs`、`tests/demo-smoke/lib/category-kit.test.mjs` |
| v2 PG屏障探针未核对队列领取身份 | 第二轮真实PG探针在 `claim_next_task()` 后收到空值并在 `task.task_id` 处中断；前一轮同场景曾通过。旧代码没有核对领取到的是否为当前种子Run的Task，也没有为空领取输出队列候选，无法判断前置场景是否留下待处理项。现由 `claim_seeded_task` 校验Task身份并输出目标/候选状态；定向及后续完整运行的v2-session通过、四组真实PG屏障断言通过。此变更只补诊断和失败说明，没有增加领取重试，也尚未确定原空领取根因，不能称为生产队列缺陷已修复。 | `tests/integration/session_pg_probe.py` |
| LIFE硬杀夹具把吐片屏障当成持久提交 | `20261020t091545-b9c1f523` 的nested日志确认，在Provider第二片等待屏障后立即查询，首片仍可能位于100ms聚合缓冲中。夹具现有界轮询真实PG Journal，确认唯一首片、Run仍running且无最终assistant，再等待浏览器DOM并武装硬杀。未扩大产品时限或删除硬杀断言；修正前失败保留。 | `tests/demo-smoke/tooling/harness-fixtures/life-hard-kill.mjs` |
| 旧PERF_002消息POST传输中断 | 同轮消息POST返回`UND_ERR_SOCKET / other side closed`，API日志未见对应POST，API健康且无重启/OOM。独立只读keepalive/同步阻塞探针未复现；根因尚未确认，不改为性能超限或通过，不自动重发写请求掩盖失败。最终两轮继续观察并保留原始证据。 | `tests/demo-smoke/tooling/performance-events.mjs`、`lib/category-kit.mjs`及该run的PERF日志 |

上述修正未改变公开URL或成功响应结构；Embedding快照增加的是服务端私有字段，安全公开摘要维持原契约。正式两轮结果现已在 §4 及 TEST-002 §6 留档；其中分类专项通过仅证明相应分类行为，不能覆盖总入口失败或 blocked 项。

