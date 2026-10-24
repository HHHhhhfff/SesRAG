# 分类测试脚本约定

此目录放PRD-002的8类产品脚本及它们的runtime/support/probes；`manifest.json`已登记108例，8类均为`ready/required=true`。脚本—用例完整映射见[套件README](../README.md#分类脚本与用例对应)。ready表示能被调度，不表示产品通过。Provider环境夹具和运行器自测仍归`fixtures/`、`tooling/`，不计产品用例。

## 接口

- Node 脚本：`node <script.mjs> --context <context.json>`。
- PowerShell 脚本：`pwsh -NoProfile -File <script.ps1> -ContextPath <context.json>`。
- 脚本只从本次 context 读取安全地址、run/environment/category 身份和 artifact/tmp 相对目录。Secret 由入口单独授予运行时进程，不得放进命令行、context、日志或报告。
- 每个脚本必须按登记的 case ID 输出 `result.json` 和中文 `console.log`，逐例提供实际观察、状态、需求 ID、测试点 ID及证据路径；文件落在本分类 artifact 目录。
- 分类失败必须返回非零状态；无用例、缺报告、错误 run ID、重复/遗漏/额外 case、绝对/越界证据路径或实际观察为空由总入口判为 `harness_error`，不能成功退出伪装通过。

## 结果和证据的具体约定

1. 工作目录为 suite 根；`context.artifact_dir` / `context.tmp_dir` 都是相对 suite 的本轮路径。禁止据自己所在目录猜测 run_id 或结果目录。用 `context.expected_case_ids` 核对必须交付的完整集合。
2. 在本分类 artifact 目录原子写入 `result.json`；外层字段为 `schema_version=1`、`run_id`、`environment_id`、`category`、ISO UTC 开始/结束时间、`status`、`cases` 和 `evidence`。以 `schemas/category-result.schema.json` 为字段真源，不另造另一套格式。
3. 每例提供 `case_id/test_point_ids/requirement_ids/title/type/status/expected/actual/reason_code/reason/evidence_paths/duration_ms`。`actual` 必须来自当前执行的实际观察；不能复制预期结果、固定打印成功或在失败时继续标 passed。
4. 状态判定：存在断言失败→`failed` / 退出1；没有 failed 但存在前提受限或未运行→`blocked` / 退出3；全部登记用例实际通过→`passed` / 退出0；工具/报告协议错误→退出2。failed 与 blocked 并存时，逐例都保留，外层 failed。不能把 blocked 当作 skip-pass。
5. `evidence_paths` 与外层 `evidence` 都相对**本轮 artifact 根**，例如 `categories/session/request-summary.json`；文件必须确实存在。仅允许 `categories/diagnostics/browser/services` 下安全相对路径；禁止绝对路径、反斜线、`..`、符号链接、历史轮次或上级目录。
6. 每例中文日志至少包括编号、验证目标、关键动作/对象身份、实际观察和判定。需要完整 Prompt 或原始 trace 才能判断的场景应先设计安全采证方式；禁止先把秘密写到公开 artifact 再擦除。证据被截断且影响判定时必须说明并标受限/错误，不能继续通过。

## 主入口与后续验收

```powershell
# 调试指定分类；或试跑完整8类。均由入口部署、采证及清理。
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session,context'
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode All
```

完成产品用例、脚本和自测后，才能将对应 manifest 项从 planned 改为 ready，并同步 `case_ids`、需求映射与超时。总入口串行创建/清理各分类独占 project；总入口拒绝覆盖不完整时，不应通过改为 `required=false` 或缩小 case 集合规避。

八类均为必需分类。`tooling/case-catalog.mjs` 以 `test-cases.md` 第3节各分类的 `####` 用例标题为完整清单；ready 项必须登记该类全部用例（18/13/8/30/18/13/2/6），遗漏、错类、未知 ID 或真实路径越界的脚本在部署前拒绝。一个分类可用一个入口依次调用本类多个模块，但不能只登记已写好的部分来绕过剩余用例。All 的未接入报告按设计清单统计108例 not_run，不是0例通过。

质量前置只由当轮 quality 分类经协议校验后的 `QLT_002`、`QLT_003` 真实结果判定：两例均 passed 才能 ready。Environment 或不含 quality 的 Selected 仍为 pending；工具安装、自检或 manifest=ready 均不能替代这两例正式结果。

## 实际执行与证据分层

后端回归探针只挂载后端、tests、迁移、contracts和pyproject等后端输入，不保证存在`/work/frontend`。后端API单测不能读取前端文件；应用版本与pyproject的比较留在后端API测试，跨前后端发布版本由宿主quality分类QLT_002请求真实`/openapi.json`并与frontend/package.json比较。不得为修工程错误删除产品版本断言或把缺文件当skip/pass。

session/context/model/run/compatibility先调用`probes/backend-regression-probe.py`，以`case-selectors.json`逐例指定节点；`@case::`是本套件应用/Worker补充断言，`@migration::`是补充迁移断言，`@pg::`是独立真实PG探针。JUnit节点未找到、跳过或失败必须保留。各类`*-runtime.mjs`补充正式HTTP、容器、Provider实收和真实索引观察；runtime成功不得覆盖关联回归失败或跳过。迁移在PG专库运行，不能用SQLite结果冒充PG。

workspace仅由真实Chromium交互生成DOM证据；传输故障只能重排/延迟真实Journal或注入明确错误，不伪造持久成功事实。performance保存全部样本和误差区间，区间跨越阈值记blocked。quality保存每项实际命令及负样本结果；QLT_005在分类内等待外层finally，总入口额外部署两个独立环境验证分类退出19和实际超时，最终状态由正常/异常项目清理、全轮独立残留审计及源码一致性结算。分类自测、技术探针和历史环境记录均不能替代当轮事实。

`result.json`为逐例汇总，`<case_id>.json`为单例观察；后端还有`backend-regression.json`、`pytest-regression.xml/log`、`postgres-cases.json`，性能另存30样本原始时间区间。公开证据只含安全身份/hash/计数，完整请求或原始秘密不进入artifact。

`run-evidence-runtime.mjs`补足真实PG/REST/SSE阶段和首片证据，不能以静态契约样本或SQLite替代；`probes/run-facts.py`只读当前分类PG。CTX_005/006包含无裁剪/裁剪/摘要/内部重试四种实际Worker计划及冻结计数复算，CTX_007另验父子/兄弟/嵌套派生隔离，RUN_023把七种协议故障送过正式适配器及Worker至终态。workspace覆盖刷新三状态、上下文四状态、时间线四路径、跨Thread/兄弟Branch共20组迟到响应，以及按钮pending/模型偏好/归档边界。

私有进程环境`WS_EVIDENCE_SECRETS`只提供首次发布前的脱敏集合；`product-category.mjs`在逐例观察、证据和result写入前清洗全部四类凭据，不能依靠质量分类末尾扫描才补救。MOD_006必须等必需公开接口正文全部读完，空数组或读取失败不算通过。预期工具失败只有确切退出19、无超时/截断/信号才成立。

UI_003使用workspace独有15秒退避、首片后真实传输断开、停Worker保持retry_waiting，并在刷新时核对实际状态；finally恢复后确认旧代草稿不进入新答案。UI_005中详情加载时分支控件确实不存在；该细分场景在真实浏览器调用现有store action驱动第二选择，不伪造状态或控件，其余分支切换仍点现有选择器。该能力边界应随证据记录。

UI_011用`browser-support.mjs:assertUnavailableModel`同时验证原生disabled、`:disabled`、原因说明及真实键盘跳过，不使用已最小复现有偏差的label内`option.isDisabled()`或强制赋值的`selectOption`判断不可选。必须遍历全部可用项且没有业务POST，避免用全控件禁用或无操作掩盖失败。RUN_015/024用`support.mjs:releaseThenRestore`保证Provider释放异常也执行服务启动/就绪，释放与恢复异常均不能默认为成功。

## 隔离、安全与维护

- 每类在全新 Compose 子 project 和独立业务数据卷中串行执行；用例动态经正式 API/产品操作生成事实，不固定 SQL 预造 Run、终态、租约或成功事件。
- 只可使用总入口提供的受限 resource helper 重启或检查本分类服务；禁止直接执行全环境 `down -v`、清表、删 artifact、删其它 project/volume/image，或安装全局工具。
- helper 的 `inspect/start/stop/restart` 通常仅允许 api/worker/provider；仅 run 分类额外允许 postgres/redis，以支持 RUN_024。调用 `node tooling/orchestrator.mjs --resource-helper --run-id <context.run_id> --category <context.category> --action stop --service redis`（start/restart/inspect 同理）。每次核验主进程、Engine、活跃 project、run/owner 标签并记录动作。动作返回只说明命令完成，恢复后必须有界等待 readiness；finally 恢复失败则停止受污染分类，不借用其它分类服务。
- 代码注释使用中文并标明覆盖的 case ID；一个脚本原则上只覆盖一个分类。跨分类断言放入其唯一主要归属的分类，避免重复统计。
- 调整脚本、依赖、case ID、超时或前置条件时同步更新 `manifest.json`、`test-cases.md` 与 `test-plan.md`，先跑脚本自身正/负协议自测，再运行对应 Selected。

详见 [总接入计划](../test-plan.md) 和 [TEST-002 环境方案](../../../docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)。
