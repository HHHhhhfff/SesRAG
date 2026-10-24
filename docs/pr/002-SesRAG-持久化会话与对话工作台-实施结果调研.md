# PR-002：持久化会话与对话工作台实施结果调研

- **编号**：002（PRD-002 实施结果调研，不替代同编号的简要实施记录）
- **文档版本**：v1.0
- **项目版本 / 分支**：v0.2 / `sesrag_v0.2`
- **日期**：2026-10-20
- **状态**：已完成代码调研与文档校审；不表示已完成本轮独立正式验收
- **适用范围**：持久会话、分支、模型配置、上下文规划、Run 执行/恢复及浏览器工作台；为后续测试点和用例设计提供实现依据。
- **对应 PRD**：[002-SesRAG-持久化会话与对话工作台-PRD.md](../prd/002-SesRAG-持久化会话与对话工作台-PRD.md)
- **对应 ADR**：[002-sesrag-persistent-session-workspace-implementation-plan.md](../adr/002-sesrag-persistent-session-workspace-implementation-plan.md)
- **简要实施记录**：[002-SesRAG-持久化会话与对话工作台-PR.md](002-SesRAG-持久化会话与对话工作台-PR.md)
- **接口依据**：[接口文档](../接口文档.md)，同时核对实际路由、Pydantic DTO 和 `contracts/`。
- **代码基线**：调研开始时 HEAD 为 `595eb04`；主要实施提交为 `4433760`；文件新增/修改性质以实施前 `a204265` 到 `595eb04` 的 Git 差异为准。本次新增调研文件及导航不计入产品实施差异。

## 1. 调研结论与证据边界

PRD 的 18 项功能需求均能在当前源码中找到主要实现路径，核心对象和处理机制总体沿用 ADR 的设计：PostgreSQL 保存事实，Branch 组合历史路径，Run 冻结执行配置，Worker 在租约授权下发布上下文和增量，前端恢复事实并观察 Journal。11 项非功能需求也有对应设计和代码落点，但性能、真实 PostgreSQL 并发、进程重启和浏览器恢复等结果仍须通过本轮独立测试确认，不能仅凭静态代码判为验收通过。

本次发现两项可最小复现的开发验证缺口：现存后端 DTO 样本测试仍读取已删除的旧验收 JSON；前端 Lint 命令仍调用已删除的旧验收脚本。另有 ADR/PR 的内部编号、README/接口文档链接和旧验收入口残留。详见 §9、§10；它们不应被掩盖为全部验证已通过，也不应通过恢复上一轮验收工程来解决。

### 1.1 本次实际做了什么

1. 阅读 PRD、ADR、简要 PR、接口文档、仓库规则和模块说明，并追查实际代码与开发测试。
2. 对照 Git 历史区分实际新增、修改、沿用和移除的文件，未将 ADR 的预计文件名当成已经实现的文件。
3. 静态核对身份约束、事务、状态、错误、资源边界和前后端投影，逐项建立需求核对清单。
4. 执行一条只读类型漂移检查及两条工具链缺口的最小复现命令，结果见 §9.2。
5. 新增本调研文档并更新根目录和 `docs/pr/README.md` 的导航。未修改产品代码、契约、迁移、现有测试或用户的任务说明。

### 1.2 结论口径与验收工程边界

| 口径 | 本文含义 |
| --- | --- |
| 已定位实现 | 已追查到具体调用链、字段、条件或事务；不等于运行验证通过。 |
| 已有开发测试 | 当前分支保留了相关测试代码；除 §9.2 明确执行的项目外，本次没有重跑。 |
| 本次实测 | 只指 §9.2 列出的命令、退出码和观察结果。 |
| 待独立验收 | 需要后续专门环境、测试点/用例、运行证据及报告确认。 |
| 历史验证记录 | 简要 PR 中记录的旧运行结果，本次未复核原始运行环境，不能转写成当前独立验收结果。 |

用户已明确：本轮及后续 PRD 的本机验收独立组织，不统一进入上一轮 `tests/demo-smoke/`。当前版本已移除该旧目录的受版本控制文件；本次不恢复、不维护、不执行旧总入口。`tests/unit/`、`tests/api/`、`tests/integration/` 中与当前产品实现相关的开发测试另行保留。磁盘上存在空的 `tests/sesrag-persistent-session-workspace-test/` 目录，但没有可读取的文件或已跟踪的测试入口，不能视为新验收环境已经准备好，也不在本次调研中为其规定实施方案。

本轮不承诺生产身份认证、多租户、跨会话语义记忆、工具运行时、人工审批、知识库发布版本、真实模型效果或生产 SLO；这些非目标与 PRD 保持一致。

## 2. 从原 Demo 到当前实现的主要变化

| 方面 | 实施前基础 | 当前落地变化 |
| --- | --- | --- |
| 会话历史 | Thread/Message/Run 持久化，主要为线性对话和当前问题生成。 | 增加 Branch 路径、历史分页、重命名/取消归档；当前路径的允许历史实际进入 ModelRequest。 |
| 输入与执行身份 | 一个用户 Message 对一个初始 Run。 | 用户输入可被多个显式新 Run 引用；`Message.run_id` 保持原创建者，`Run.user_message_id` 表达本次执行输入。 |
| 模型配置 | Settings 控制单个 Mock/兼容服务。 | 新增数据库 ModelProfile，按 ID/version 选择；新 Run schema 2 冻结 Profile、预算、检索及执行策略，旧 Run 仍按 schema 1 执行。 |
| 上下文 | 没有本轮的可追溯分支预算计划。 | 新增 ContextPlan、提取摘要、TokenCounter、安全提示；超限不静默截断当前输入。 |
| 用户控制 | 旧取消、SSE 和持久任务基础。 | 新增运行中 cancelling/确认、显式 retry/regenerate、从历史消息分叉；增量按尝试隔离。 |
| 接口与前端 | v1 client、单工作台。 | 新增 15 条 v2 路由、8 份 v2 JSON 契约、独立生成类型；工作台会话操作切至 v2，文档及健康入口沿用。 |
| 数据升级 | head 为 `0003_chunk_locations`。 | 新增 0004→0005→0006；旧事实回填默认分支，冲突中止，出现 v2 业务事实后拒绝有损 downgrade。 |
| 测试与文档 | 上轮 Demo 本机验收工程。 | 保留本轮开发测试；旧验收工程退出当前分支。本轮独立正式验收须另行准备，现有残留依赖见 §10。 |

## 3. 核心对象、字段和身份关系

对象映射主要位于 [backend/db/models.py](../../backend/db/models.py)，路径/上下文/Profile 的非 ORM DTO 位于 [backend/domain/ports/session.py](../../backend/domain/ports/session.py)。

| 对象 | 主要字段与实际职能 | 身份约束、关系和调研结论 |
| --- | --- | --- |
| Thread | `thread_id`、`owner_id`、`title`、`archived_at`、`next_message_seq`、`conversation_version`、时间字段。 | 会话和 owner 边界；seq 在整个 Thread 内分配，分支可出现序号间隙。归档只限制新操作和列表选择，不删除历史。 |
| Branch | `branch_id`、`thread_id`、`parent_branch_id`、`fork_message_id`、`head_message_id`、`version`、`is_default`、`name`。 | 每个 Thread 创建默认分支；部分唯一索引防止两个默认分支，应用创建/迁移保证初始存在。父分支与 fork 成对；子路径引用祖先，不复制消息。 |
| Message | `message_id`、`thread_id`、`branch_id`、`seq`、role/source/content/status、`run_id`、`citations_json`。 | branch_id 是消息创建位置；继承祖先消息时不改写。user.run_id 是创建者；assistant.run_id 是回答执行者。每 Run 的 assistant 部分唯一索引限制至多一个最终回答。无修改历史正文的业务接口；不宣称数据库有通用不可变触发器。 |
| Run / RunSnapshot | `run_id`、`thread_id`、`branch_id`、`user_message_id`、`parent_run_id`、`operation_kind`、`execution_schema_version`、`snapshot_json`、Profile 成对字段、`context_plan_id`、`primary_task_id`、状态/取消/错误。 | 每 Run 一个输入，至多一个最终回答；source 关系以 parent_run_id 和 operation_kind 表达，而非新增 retry_of/regenerates 两套字段。Snapshot 是 JSON 值对象，不是单独表。 |
| Task | `task_id`、`kind`、`run_id`、state、attempt、worker_id、generation、lease/deadline/available 时间、进度/错误。 | 每 Run 一个 kind=run Task，部分唯一索引防重复；自动重试更新同 Task 的 attempt/generation，不创建会话 Run。索引 Task 仍独立。 |
| RunEvent / Journal | `event_id`、`run_id`、`seq`、`schema_version`、type、payload、created_at。 | seq 每 Run 单调且 `(run_id,seq)` 唯一，schema 由 Run 执行代际决定；终态后不能继续追加。SSE 的 id 使用 seq。 |
| ModelProfile | 复合主键 `profile_id/version`；provider/model/generation_params、base_url、窗口/输出预算、tokenizer 配置、config_ref、启用/默认策略。 | 表为运行元数据真源；同版本生成配置不能原地变更，默认/启禁用可以调整。config_ref 仅为受信环境变量别名，绝非 Key 值。 |
| ContextPlan | Run/Task/Thread/Branch/anchor 身份，generation/attempt，选中消息、遗漏原因/范围、summary IDs、选中证据/hash、策略/计数版本、预算/status。 | `(task_id,generation)` 唯一；一次自动重试产生另一代计划，旧计划保留。Run.context_plan_id 指向最近发布计划，执行前可能为空。持久化元数据不含完整 Prompt。 |
| ConversationSummary | Thread/Branch、covered_message_ids、from/to seq、source_hash/source_segments、summary_text、策略/source_run/time。 | 摘要是派生数据，正文保存在服务端，公开查询仅投影来源元数据。复用须同 Thread/Branch、hash 和策略；不直接复用父分支摘要，不覆盖原 Message。 |
| SessionOperation | operation_id、Thread、幂等键、kind、规范化 request_hash、结果 Branch/Message/Run/Task 指针。 | `(thread_id,idempotency_key)` 唯一；创建类操作重放原结果，异内容同键冲突；只存摘要及结果身份，不重复存输入正文。 |
| ModelRequest | role/content 消息序列、max_output_tokens、selected_evidence、generation_params。 | 由 ContextPlan 形成并交 Provider，属于执行期 DTO，不是另一份持久会话事实。 |

关系可按下列方式理解：

```text
Thread ──< Branch ──< 本分支新建 Message / Run
             └─ parent + fork ──> 共同祖先 Message（逻辑引用）
Message(user) ──< Run ──1 Task ──< attempt / generation（同一表行推进）
                   ├─0..1 最终 assistant Message
                   ├─< RunEvent
                   ├─< ContextPlan（每 task/generation 至多一份）
                   ├─冻结 Snapshot ──> Profile(id, version)及执行策略
                   └─parent_run_id ──> 来源 Run
Branch ──< ConversationSummary <── ContextPlan.summary_ids
Thread ──< SessionOperation ──> 原创建结果身份
```

不能把“输入来自祖先 Branch”误判成跨分支错误：只要该输入位于新 Run 的有效路径内即可；新 assistant 则必须写到新 Run 自己的 Branch。数据约束、owner/路径检查和应用行锁共同保证关系，不能说所有跨对象同 Thread 条件都由数据库复合外键单独保证。

## 4. 已实现的关键机制与异常行为

### 4.1 Thread 管理、归档和有界读取

- `application/threads.py:create_thread` 同事务创建 Thread 和默认 Branch；v2 指定 conversation_version=2，v1 仍为1。
- `session_threads.py:list_session_threads` 按 owner 过滤，按 `(updated_at,thread_id)` 倒序 keyset 分页；默认50、最大200，默认排除归档。游标包含带时区时间及身份，解析失败返回业务 422 `INVALID_CURSOR`，不暴露解码细节。
- `patch_session_thread` 在 Thread 锁下处理重命名、归档/取消归档，必要时执行旧会话升级；标题新写入去首尾空白且长度1～200。响应保留旧库原始标题，归档不能顺带改名。
- `session_thread_detail` 只查指定有效路径，消息用 before_seq/limit 分页并按升序返回；另外定位当前 Branch 的 active/recent Run。祖先合法历史 Run 可以随页面返回，但自动观察只选当前 Branch 的执行。
- 前端 `thread.ts` 列表请求 include_archived=true，将归档项和普通项混排并标记“已归档”；没有独立归档筛选页。归档后仍可打开和取消归档，输入/分叉/显式新 Run 被禁止。若此前存在活动 Run，归档本身不等于取消。
- 列表加载时优先恢复有效的已存选择，否则选未归档项；已保存的归档会话仍可恢复为只读选择。这是当前交互口径，需在测试设计中与 PRD 的“归档不再作为默认活跃会话”区分，确认是否需独立归档视图。

### 4.2 分支路径、分叉和并发提交

`branches.py:resolve_scope` 从目标 Branch 向父节点遍历，检查循环、父/fork 配对、所属 Thread、深度和分叉消息可见性；多级分叉把祖先的可见截止点取交集。`SQLBranchRepository.path_condition/list_path_messages` 将路径段编成 SQL 条件，按需 LIMIT，避免读取整个会话再过滤。

`create_branch` 在 owner 校验、Thread 锁、幂等重放后锁定祖先 Branch，验证 fork 在父有效路径中；跨 Thread 消息为404，不可见锚点为422。活动 Run 的输入不能作为新分叉点；同点多次使用不同幂等键可产生多个子 Branch。总分支上限100（含默认分支），路径深度上限32（含根）；超限返回 `BRANCH_LIMIT_EXCEEDED`。新 Branch 的 head=fork、version=0，不复制祖先消息。

`create_session_message` 要求 branch_id、expected_version；与数据库 Branch.version 不同返回409 `BRANCH_HEAD_CHANGED`，已有四种活动 Run 则返回409 `BRANCH_BUSY`。数据库 `uq_runs_branch_active` 再防并发穿透。不同 Branch 可以分别拥有活动 Run，但 Thread 锁短暂串行分配全局消息 seq。

### 4.3 创建事务和幂等

v2 消息、分支、retry、regenerate 均要求非空且不超过200字符的 Idempotency-Key；Thread 创建不强制。owner 校验先于重放，Thread 锁保护规范化 hash 查询/创建。`request_hash` 包含操作类型、原请求字段及可选字段“未传”标记，避免默认模型变化使原请求无法重放。

同键同内容先返回原结果，再考虑当前归档、模型可用性、Branch 末尾变化等新冲突；同键异内容为409 `IDEMPOTENCY_CONFLICT`。首次创建返回201，重放200；操作响应中的 status 可反映原 Run 当前状态，不要求逐字节冻结首次响应。

新消息事务原子提交：用户 Message、Branch head/version、Run、冻结 Snapshot、唯一 Task、初始 Event、SessionOperation 和旧 Thread 的必要升级。任何校验或后续写入失败均不能留下半个创建结果。请求DTO禁止额外字段，正文1～20000字符且不可全空白；后端保存合法原文，前端普通发送会先trim。客户端不能传入终态、owner、来源Run等服务端字段。

前端 pendingMessage/pendingFork/pendingOperation 仅在内存中保留原请求及键，切换会话、重置store等可清除待确认状态；它们没有跨整页刷新持久化，不能宣称“刷新后尚未确认的写请求”也已具备自动原键重放能力。

### 4.4 Profile 选择、版本与 Provider 重建

`0005` 种入两个 enabled Mock Profile：`mock-default@1`（8192窗口/1024输出，默认）和 `mock-small@1`（2048/256）；两者安全余量128、摘要预算512。它们区分预算配置，不代表两个真实供应商模型。

`SQLModelProfileRepository.import_profiles` 配合 `backend.tools.sync_model_profiles` 显式导入非 Secret JSON：同 ID/version 的模型、预算、tokenizer、URL 等变更拒绝；新版本才接收生成配置变化。导入必须指定一个启用默认项；API/Worker 启动不读取 JSON 覆盖表。`list_model_profiles/profile_reason` 返回 enabled/disabled/invalid 和安全 reason；没有可用默认项为503，创建新 Run 选项不可用为409 `MODEL_PROFILE_UNAVAILABLE`。

新 Run Snapshot schema2 冻结 Profile、Prompt版本、Thread/Branch/input anchor、上下文策略、检索配置和执行限额。`registry.py:provider_from_snapshot2` 严格核对字段/上限/计数器版本，重建 Mock 或 OpenAI-compatible Provider；错误分别为 `INVALID_RUN_SNAPSHOT`、`MODEL_CREDENTIAL_UNAVAILABLE`。运行恢复不重新选择当前默认项，Profile 被禁用不改已有快照；凭据无法解析则失败，不切换 Mock。

真实 Profile 只允许白名单 `env:MODEL_API_KEY`，URL 禁止凭据/query/fragment；窗口、输出、tokenizer框架开销和校准版本显式配置。tiktoken固定0.8.0，当前登记离线资产 `cl100k_base`；镜像构建预热，运行校验文件大小/hash后加载，缺失/损坏不联网补取。Mock词法计数只供离线流程，连续中文可能作为长词，不能用字符数直接推算其token，更不能证明真实模型预算精度。

生成 Profile 与 Embedding 分开：retrieval 冻结384维、Embedding kind/model/base_url/Secret alias及top_k，不能因切换生成模型或改 Settings 漂移检索空间。仅使用真实生成模型时可继续使用Mock Embedding；后者也不证明检索效果。

### 4.5 上下文选取、裁剪和摘要

主要调用链为 `process_session_run` → `check_mandatory_budget` → 检索 → `load_context_candidates/plan_context` → `publish_plan` → ModelRequest。

1. 首先只计算系统指令+当前用户输入，预留输出和安全余量。mandatory 超限时发布 budget_exceeded 计划并失败为 `CONTEXT_TOO_LARGE`；不调用 Embedding、检索或生成模型。
2. 通过有效 Branch 路径读取截至输入锚点的最近最多200条候选，再排除本次输入；正文候选上限200000字符。候选窗口以外保存范围/数量/原因，不加载全部历史原文。这里200条上限包含锚点，实际历史数可能少于200。
3. 只接受完成的assistant；对失败/取消且没有有效回答的历史user记录 incomplete_turn。若原创建Run失败而显式retry后来在当前路径成功，按assistant的run_user_message_id关联完成轮次，不因user.run_id仍指向失败创建者而丢掉整轮。
4. 证据按分数降序和身份确定顺序；超预算先移除最低分证据，再移除最旧完整轮次。当前输入/必要系统指令不能截断；不完整或孤立历史有明确遗漏说明。
5. `trim_then_extract_v1` 对因预算移除的旧消息按seq确定性摘取，每条最多128个Unicode字符、总计不超过摘要token预算。记录实际covered IDs、字符片段和源hash；不是调用摘要模型，也不是完整历史的语义压缩。为放入摘要可能再移除旧轮次，仍放不下则不用摘要。
6. 摘取过程失败可退到 `trim_only_v1`，记录安全 `SUMMARY_EXTRACTION_FAILED` 日志；TokenCounter自身失败不被当成摘要失败吞掉。超过候选窗口的原文不会被历史摘要自动无限带回，这不是跨窗口的长期语义记忆。
7. 锁外计算后，`publish_plan` 重新校验Task授权，短事务保存摘要/计划、更新Run.context_plan_id、追加context.planned/compacted。每task/generation至多一份，旧代计划不覆盖新代。摘要复用查同Thread/Branch/hash/策略，重新生成的source Run可不同但来源内容必须一致。

Context公开接口返回预算、消息ID/遗漏范围、摘要来源元数据、选中证据身份/hash，不返回完整Prompt、summary_text或证据原文。UI `ContextNotice.vue` 展示预算、裁剪数量、范围和策略；范围from/to仅供展示，路径身份仍以消息ID和分段条件为准。

### 4.6 持久流式输出、终态与浏览器恢复

`run_handler.py` 按 execution_schema_version 分派legacy或 `process_session_run`，新路径先发布run.started、retrieval.completed、上下文计划，再消费 `stream_request`。`_bounded_stream` 将一个待接收任务与独立flush时钟并行，已有缓冲不必等下一token才写入；默认100ms刷新，先提交answer.delta，SSE再读Journal。最终正文 `.strip()` 后判空，故首尾空白的临时投影与最终正文可有规范化差异。

`complete_run` 依 Task→Run→Thread→Branch 锁序，复核授权后一次提交assistant Message、Branch head/version、Run/Task succeeded、message.completed和run.succeeded。最后flush后再次用原租约/deadline检查，越界整组回滚；不把这项检查等同于网络commit物理零延迟。

`routes/v2/runs.py:stream_events` 在发送SSE响应前校验归属；Last-Event-ID优先于after_seq，负数归零，非法整数回到0。每轮分页读取持久Event，终态尾页排完才关闭；断开只退出观察，不调用取消。Redis为通知/健康辅助，新SSE本身按数据库轮询，默认0.2秒，Redis丢通知不丢事实。

前端 `run-event-stream.ts` HTTP分页补放到尾（每页默认200，最多100页）并接收SSE，统一交给 `run.ts:append`。按run_id/seq去重、排序；连续已接收seq作为重连游标。task.leased/run.started建立当前attempt边界，草稿只拼当前task/generation/attempt的delta。Event触发GET刷新，Run状态和最终消息取服务端事实，完成正文替代草稿。

`thread.ts` 的epoch、`run.ts` 的epoch/refreshVersion/Thread-Branch-Run校验共同拒绝迟到HTTP和回调。localStorage只保存选择身份/Profile偏好，不缓存消息正文或假定终态；失效身份重新读取校验。页面从active/recent定位当前Branch的Run，刷新只重建观察；断线自动重试最多3次（0.5/1/2秒），之后保留手动重连。关闭连接/卸载清理timer，不发送cancel。

### 4.7 自动重试、用户重试和重新生成

| 操作 | 允许来源和身份 | 当前路径行为 |
| --- | --- | --- |
| Worker自动重试 | 可重试故障且未耗尽attempt/deadline；同Run、同Task、同user。 | 回retry_waiting后再次领取推进attempt/generation；新计划和草稿分段；原事件保留。 |
| 用户retry | 来源Run须failed/cancelled，新Run/Task，parent_run_id=source、operation_kind=user_retry；不新建user。 | 源Branch head仍是该user且无busy时复用Branch，否则在输入点创建子Branch；原失败/取消Run保留。 |
| 用户regenerate | 来源Run须succeeded，新Run/Task，operation_kind=regenerate；仍引用原user。 | 永远从原输入建立子Branch，排除旧assistant和输入之后未来消息；同输入可多次产生不同子Branch。 |
| 普通分支继续提问 | 新user、新Run/Task。 | 子Branch为branch_continue，默认根分支为initial。 |

`create_related_run` 同样受owner、归档、路径、分支总数/深度和幂等约束。默认沿用来源Profile及冻结策略；用户明确改模型才覆盖Profile关联预算/计数器，检索/执行/Prompt仍继承源策略。legacy未保存Profile，必须显式选择。新Run仍需来源Profile当前可用于新创建，禁用/缺凭据时拒绝；这与“旧Run按已有快照继续恢复”不同。

前端 `selectionRevision` 区分“全局模型偏好”与“查看该Run后手动换模”，防止静默覆盖原模型；未确认操作重试保留原payload/key。工作台目前自动展示当前Branch active/recent Run，没有独立的全历史Run选择器；旧Run详情/Event仍能按ID通过API查询，旧回答通过分支/历史消息保留。后续应区分API可追溯性与UI可操作范围。

### 4.8 取消、失租、deadline与优雅停止

- queued/retry_waiting可直接结算Run/Task cancelled；Task为leased/running时记录cancel_requested_at、Run=cancelling、run.cancelling，Task保持执行状态直到确认，不伪报终态。
- `guarded_call` 在执行阶段及付费调用等待中约0.2秒复查授权，整步有超时；`lock_owned_task`要求task_id/worker_id/generation/active/有效lease/deadline。失租或取消抛ExecutionStopped，不再发布结果。
- runtime `_ack_cancel` 调 `acknowledge_cancellation`；授权仍有效才确认。授权已经过期时由requeue_expired安全结算；取消优先于deadline失败/重新排队，避免取消任务被复活。
- 取消/完成竞争都先锁Task再锁Run；先持久完成者保留成功，先写取消请求者阻止后续成功。重复取消和终态取消返回已有状态，不追加冲突终态。
- 原有Worker停止领取、继续心跳宽限、超时释放/租约回收机制沿用，新实现补取消确认。恢复沿用Run/Task，可重做未完成Provider调用；不承诺从供应商token位置续算。
- 外部协程取消和同步线程停止是协作式边界，不能撤销已发生的外部副作用或强杀任意同步线程；不得把UI收到cancel响应当成上游已经物理停止的证明。

### 4.9 资源上限、错误、RAG和安全展示

schema2 Snapshot保存执行上限：最多3次尝试、600秒任务deadline、60秒步骤、120秒流、4096原始增量、1000000输出字符、100ms flush、65536字节增量缓冲、15000常规Event；创建时attempt/deadline取Settings与上限的较小值。Provider HTTP另有4MiB响应及60秒总请求保护，实际生效为各层更早触发的边界，不能只按120秒推断所有上游请求时限。

常规Event额度用尽返回 `RUN_EVENT_LIMIT`；message.completed和终态/取消控制事件保留通道。缓冲超限、答案超限、空流、非字符串增量、缺[DONE]或不合法HTTP内容均有明确错误；失败后部分delta仅留Journal，不创建完成assistant。

`openai_compatible.py` 的模块函数 `check_status` 及Provider方法 `_bytes/stream_request` 将408/429/5xx、连接和超时分类为可重试错误，其余HTTP错误通常不可重试，上游context_length错误映射CONTEXT_TOO_LARGE；不回显原始响应或凭据。Worker再结合attempt/deadline有限回排，保留安全last_error_code。请求422为安全detail数组，业务错误为code/message；数据库连接/超时由app转503 DATABASE_UNAVAILABLE，不假装无知识。

检索沿用owner范围知识库。retrieval.completed是本次原始召回元数据；ContextPlan.selected_evidence才是本次送入模型的子集，最终citations也按该子集过滤，因此两者数量可不同。新Citation保留document/chunk/index_batch/location/offset/score/filename；无证据可正常生成安全回答，检索异常则失败，不能伪装空召回。分支隔离是对话上下文隔离，不是文档库多租户改造。

`markdown/render.ts` 对marked输出统一DOMPurify清洗，持久正文和草稿均调用；禁止script/style/iframe/object/embed/form、危险属性/协议，保存原文与DOM分离。RunTimeline只显示公开事件白名单、模型/预算/状态/安全错误及执行身份，不渲染完整payload或隐藏思维链，也没有工具执行事件。时间线事件名称目前多为协议英文名，中文可读阶段说明较有限，应在界面验收时实查。

### 4.10 旧事实迁移与受限回退

正式链为 `0003_chunk_locations` → `0004_v2_session_branches` → `0005_v2_profiles_context` → `0006_v2_run_guards`。0004的preflight在PostgreSQL锁定相关事实表，检查Run输入/主Task/assistant互指、孤立Task、同Thread多活动Run、过时消息计数和非法状态；发现冲突返回安全类别和至多20个相关身份，不自动删除、取消或合并事实。应用停写、备份及完整恢复操作沿用开发Runbook，不能因为迁移内部加锁就省略维护窗口。

迁移为每个旧Thread建立默认Branch，将原Message/Run关联过去；head取最后消息，Branch.version初始化为该消息seq（空会话为0）。Thread.conversation_version及旧Run.execution_schema_version仍为1，旧内容/快照/Event不重写为v2。移除旧Run输入唯一限制而保留输入外键，允许后续显式新Run复用输入；0006再以CHECK及部分唯一索引防止新活动执行/Task冲突。

各反向revision先调用guard_downgrade。存在version2 Thread/schema2 Run、子Branch、SessionOperation、多Run输入、计划或摘要时拒绝；自定义Profile配置需显式导出，不自动删除；目标base一律禁止。仅无上述事实、符合默认Profile边界的库可受限回到0003。若拒绝，应向前修复或恢复已验证备份，不能手工删除业务事实绕过。迁移是否无损仍须在新空库、旧事实复制库和冲突库做动态hash/计数/结构核对，本次未执行这些演练。

## 5. 接口、契约及兼容落地

### 5.1 实际新增的15条v2入口

以下表用于定位测试面，完整请求/响应仍以[接口文档](../接口文档.md)及契约为准，不建立第二份正式接口规范。

| 方法与路径 | 代码入口 / 实际主要行为 |
| --- | --- |
| GET `/api/v2/models` | `routes/v2/models.py` → list_model_profiles，安全模型列表与默认成对身份。 |
| POST `/api/v2/threads` | `routes/v2/threads.py:post_thread`，Thread2和默认Branch。 |
| GET `/api/v2/threads` | get_threads，owner/归档/keyset分页。 |
| GET `/api/v2/threads/{thread_id}` | get_detail，Branch路径和消息分页、active/recent身份。 |
| PATCH `/api/v2/threads/{thread_id}` | patch_thread，重命名、归档、取消归档。 |
| GET `/api/v2/threads/{thread_id}/branches` | get_branches，Branch列表。 |
| POST `/api/v2/threads/{thread_id}/branches` | post_branch，分叉和强制幂等。 |
| POST `/api/v2/threads/{thread_id}/messages` | post_message，版本锚点、新消息/Run/Task原子创建。 |
| GET `/api/v2/runs/{run_id}` | `routes/v2/runs.py:get_run`，安全模型/快照/任务/计划摘要，兼容legacy。 |
| GET `/api/v2/runs/{run_id}/context` | get_context，默认最近计划或指定generation；尚未规划返回not_planned，指定不存在代数404。 |
| GET `/api/v2/runs/{run_id}/events` | get_events，after_seq分页；默认200、最大1000，has_more/next_after_seq。 |
| GET `/api/v2/runs/{run_id}/events/stream` | stream_events，SSE数据库补放、header游标优先、终态尾页退出。 |
| POST `/api/v2/runs/{run_id}/cancel` | post_cancel，legacy旧取消或schema2请求/确认语义。 |
| POST `/api/v2/runs/{run_id}/retry` | post_retry，新Run及必要子Branch，强制幂等。 |
| POST `/api/v2/runs/{run_id}/regenerate` | post_regenerate，新Run和子Branch，强制幂等。 |

### 5.2 保留和适配的范围

| 对象 | 当前处理及核对要点 |
| --- | --- |
| 9条v1会话入口 | 原threads/runs路由文件及成功包装沿用；兼容改动在application/threads.py、runs.py。Thread级只允许conversation_version=1；Run级按execution_schema_version=1独立守卫，越界409 API_VERSION_REQUIRED，SSE先拒绝再响应。v1创建也维护默认Branch/head和busy约束。 |
| v2读旧Thread/Run | 只读不升级Thread；legacy详情的model/snapshot/context_plan为空。v2取消legacy委托旧逻辑，直接cancelled，不补造cancelling或schema2Event。 |
| 首次v2会话写旧Thread | PATCH、创建消息/Branch、retry/regenerate在Thread锁内确认无活动legacy Run后原子升级；失败回滚，活动旧Run为LEGACY_RUN_ACTIVE。Thread升级不修改旧Run/Snapshot/Event代际。 |
| 3条v1文档/索引、2条health | 保留原路由和调用方；没有新增v2 documents/index/health/archive别名。 |
| 契约与类型 | 新增8份v2 Schema；run_event_v2用严格联合直接引用旧schema1，新增16类schema2事件。原v1 JSON及api.ts保留，本轮Git差异没有改写其公开结构。 |
| 生成器 | 默认generate/check同时覆盖api.ts和api-v2.ts；旧--output默认生成v1，显式--version v2可选另一代；TypeScript不替代JSON Schema运行时校验。 |
| 工作台调用方 | api/v2三client和v2 store接线；旧api/threads.ts、runs.ts保留legacy能力。共享HTTP/事件层有版本判别，无失败自动降回v1或重复发正文。 |

四种版本须分别测试：HTTP路径、Thread.conversation_version、Run.execution_schema_version、Event.schema_version。不能因URL为v2就要求旧Journal变成schema2；不能因Thread升级就拒绝用v1按ID读取旧Run。

## 6. PRD功能需求逐项核对清单

表内“已定位”均为代码落地结论；实测状态统一见§9，不代表对应验收项已经通过。

| 需求与应有行为 | 当前实现、核心对象/函数及文件 | 调研结论与后续测试关注点 |
| --- | --- | --- |
| FR-TH-01：创建、列表、打开、重命名、归档/取消归档；历史不删除、最近更新排序。 | ThreadModel；threads.py:create_thread；session_threads.py:list_session_threads/patch_session_thread/session_thread_detail；thread.ts、ThreadList.vue、WorkspacePage.vue。 | 主链路已定位。测标题去空白/长度、旧标题保留、归档只读、取消归档、分页同时间排序/游标错误、刷新和更新排序；UI是混排标记，归档默认选择口径见§4.1。 |
| FR-TH-02：不同会话/分支消息、摘要、Prompt和流式草稿不串用。 | branches.py:resolve_scope；SQLBranchRepository.path_condition；SQLContextRepository；session_execution.py；thread.ts/run.ts的scope/epoch。 | 后端过滤和前端迟到保护已定位。两Thread哨兵、同Thread兄弟分支/再分叉、异步响应倒序、切换中完成/错误、summary查找均需实测，不能只看最终文本。 |
| FR-MEM-01：历史事实持久化，后续Run使用历史，delta不是完成Message。 | MessageModel/RunModel/RunEventModel；load_context_candidates；complete_run；run.ts:messages；session_thread_detail。 | 历史入ModelRequest及最终事务已定位。测试重启/分页原文与身份、不完整Run刷新、delta存在但assistant不存在、成功事实替换草稿、最终首尾空白处理。 |
| FR-BR-01：历史分叉保留共同前缀，原路径不覆盖、不复制祖先。 | BranchModel；create_branch/resolve_scope；SQLBranchRepository.list_path_messages；BranchSelector.vue、thread.ts:forkFrom。 | 已定位。测试user/assistant锚点、嵌套取交集、同点不同键、多分支消息seq间隙、跨Thread404/不可见422、活动输入拒绝、100总量/32深度及循环异常。 |
| FR-BR-02：自动重试不新增Run；显式retry/regenerate新身份、可追溯、旧结果保留。 | session_runs.py:create_related_run/insert_run；parent_run_id/operation_kind；Queue；RunActions.vue、run.ts:related。 | 已定位。测failed/cancelled retry复用及分叉两路、succeeded regenerate强制子分支、保留原user创建者、同点多重生成、同键重放；自动attempt仅推进原Task。 |
| FR-MOD-01：安全模型选项/默认值、多选项、禁用或缺配置不可提交。 | ModelProfileModel；model_profiles.py:profile_reason/list_model_profiles；select_profile；ModelSelector.vue/model.ts；0005 seed。 | 双Mock预算选项和受信真实Profile已定位。测成对ID/version、缺Key/禁用/encoding缺失、默认项失效503和新建拒绝409；真实服务可用性不由列表静态检查保证。 |
| FR-MOD-02：Run快照固定、运行恢复不换模型、不泄密。 | new_snapshot；registry.py:profile_snapshot/build_snapshot2/provider_from_snapshot2/embedding_from_snapshot2；sync_model_profiles。 | 已定位。修改默认/启禁用/Settings后恢复旧Run；同版本配置冲突，新版本生效；生成/Embedding分离；丢Key明确失败；显式重试的“新Run可用性”与“旧Run恢复”分别测试。 |
| FR-STR-01：持久状态/增量先于UI，阶段与终态真实。 | _bounded_stream；journal.py:append_event；complete_run；run.ts:append/refresh。 | 已定位。慢Provider首delta独立flush；Journal严格seq、持久化时点、attempt段、无冲突终态；DB写失败时UI不得出现完成事实；空流和资源限额拒绝成功。 |
| FR-STR-02：断开不取消，游标补放去重，终态不重新执行。 | routes/v2/runs.py:stream_events；session_run_events；replayV2Events/openV2RunStream；run.ts:contiguousCursor。 | 已定位。任意seq断开、HTTP/SSE交叠乱序、超过200事件分页、header优先/坏游标、终态尾页、重复事件、重连耗尽/手动连接；观察过程中统计Task/Run数量不变。 |
| FR-REC-01：刷新恢复选择/历史/最近状态，非终态恢复观察，本地偏好非真源。 | thread.ts:loadThreads/selectThread/refresh；WorkspacePage watch/bootstrap；run.ts:observe；localStorage仅身份。 | 已定位。全刷新、首屏之外已选Thread、失效Branch回默认、隐私模式、终态刷新、运行中切会话；本地pending写请求不跨刷新保存这一边界单测/交互实查。 |
| FR-REC-02：API/Worker恢复同Run/Task，快照重建，拒绝旧代写回。 | runtime.py；Queue.claim/renew/requeue_expired；lock_execution/check_locked_times；registry；session_pg_probe.py。 | 已定位恢复机制，尚须独立进程/PG验收。测SIGTERM/强停/重启、同身份新generation、失租后delta/plan/assistant/终态全拒绝；不要求上游token精确续算。 |
| FR-RUN-01：queued/等待直接取消，执行中cancelling→确认，迟到结果不能成功。 | cancel_session_run；Queue.acknowledge_cancellation/settle_cancelled/requeue_expired；runtime._ack_cancel；RunActions。 | 已定位。分别覆盖queued/leased/running/retry_waiting、重复/终态cancel、成功先提交/取消先提交、取消后deadline/失租、Provider阻塞/迟到、UI未确认不伪报。 |
| FR-OBS-01：公开状态/检索/重试/取消/终态时间线，拒绝隐藏思维和伪工具。 | Event DTO/Schema；RunTimeline.vue；ContextNotice.vue；safeErrorCode；runtime.log/context_fallback。 | 白名单投影已定位，事件标签多为协议名。测唯一Run、顺序、模型预算/历史错误语义、公开字段扫描、无Prompt/Secret/堆栈/路径；UI可读性需实查，不能只校验有16类名称。 |
| FR-CTX-01：有限模型预算，必要输入保留、旧完整轮次裁剪、有范围提示、超限不调模型。 | context.py:check_mandatory_budget/load_context_candidates/plan_context；TokenCounter；publish_plan；ContextNotice。 | 已定位。控制计数器/小窗口验证等于和超过边界、200候选/200000字符、先低分证据后旧轮次、孤立/失败轮次、mandatory超限无检索/生成调用、实际Provider消息与计划一致。 |
| FR-CTX-02：简易摘要可追溯且限Thread/Branch，失败策略确定、原消息不删。 | _extract_summary；ConversationSummaryModel；find_reusable_summary；publish_plan；context_detail。 | 确定提取已定位。测128字符片段/512预算、covered IDs/hash/offset、同来源同Branch复用/异Branch拒绝、重新构建、trim_only回退、计数器故障不吞、原文完整与公开投影不泄全文。 |
| FR-MD-01：原文保存，常见Markdown安全展示，脚本/危险链接不执行。 | markdown/render.ts:renderMarkdown；MessageTimeline.vue；run.ts草稿与事实。 | 共用清洗入口已定位。测标题/列表/代码/链接、中英文/跨delta代码块、script/onerror/SVG/危险协议、持久原文与DOM分离、最终正文切换及引用控件。 |
| FR-RAG-01：保留文本RAG，引用来自当前Run实际使用证据，空召回与故障不同。 | PgVectorStore（沿用）；session_execution.py:evidence_metadata/process_session_run；ContextPlan.selected_evidence；MessageTimeline。 | 已定位且引用过滤在裁剪之后。测召回全集≠实际子集、batch/location/hash/offset对应、被裁剪证据无最终引用、无召回、检索故障、切分支无旧引用；知识库仍为owner共享。 |
| FR-ERR-01：模型不可用/超时/预算/取消/检索/DB故障区分，重试有界且不泄密。 | openai_compatible.py:check_status/_bytes/stream_request；registry；WorkerRuntime.run_once/Queue结算；app异常处理；http.ts。 | 主要错误路径已定位。测408/429/5xx/401、context_length、断流/坏JSON/缺DONE/空流、数据库503、计划发布失败、attempt耗尽/deadline、安全响应/日志；不能把无证据当所有失败的兜底。 |

## 7. 非功能需求与PRD总验收核对

### 7.1 11项非功能需求

| 需求 | 当前实现和文件依据 | 调研结论与后续验证 |
| --- | --- | --- |
| NFR-SEC-01：凭据仅服务端、错误不泄露。 | model_profiles.py白名单/URL限制；registry公开私有分离；schemas/v2；app异常处理；http.ts安全code。 | 安全边界已定位；扫描DB快照/Event/API/前端/日志与上游认证原文；管理员输入的非Secret元数据也须遵守不放Key的约束，不宣称能识别任意正文中的秘密。 |
| NFR-SEC-02：Markdown清洗。 | renderMarkdown、DOMPurify配置及MessageTimeline。 | 已定位；需真实浏览器验证执行效果，字符串中不含script不足以替代DOM/XSS测试。 |
| NFR-ISO-01：路径、摘要、运行投影不串线。 | owner检查、resolve_scope、SQL路径/摘要条件、前端epoch/identity。 | 已定位；设计后端越界负样本、前端迟到响应和兄弟/祖先组合测试；不外推多租户认证。 |
| NFR-REL-01：PG事实、顺序事件、终态原子。 | ORM索引；journal.append_event；task_execution.complete_run；publish_plan短事务。 | 已定位；必须真实PG多连接/事务失败注入，核对Message/Branch/Run/Task/Event整体，不以SQLite代替锁证明。 |
| NFR-REL-02：重启恢复与generation拒绝。 | postgres_queue、WorkerRuntime、schema分派、前端恢复。 | 机制已定位；应在独立Compose中测API/Worker分别重启、宽限/强停、租约回收、旧Worker晚提交和cancel回收优先级。 |
| NFR-PERF-01：提交p95≤1秒，首持久delta到UI≤1秒。 | 创建短事务、锁外模型执行、100ms flush、0.2秒SSE；没有代码可以单独证明阈值。 | 本次未测。后续预热后至少30个独立提交，报告逐样本、p95算法、配置；delta测Journal提交到DOM且给时钟误差上界，不混入上游首token等待。历史旧PERF结果不抵本轮。 |
| NFR-CAP-01：上下文/答案/Event/时长有界。 | Snapshot EXECUTION_SNAPSHOT_LIMITS、ContextInput和Profile校验、HTTP 4MiB/60秒、Event预留终态。 | 已定位；各层边界值和组合先到达者、retry额度用尽仍能失败结算、单大delta等需测；不允许扩大阈值使压力样本假通过。 |
| NFR-OBS-01：对象和seq可关联，安全上下文/模型说明。 | Run/Message/Event/Plan投影与Profile身份；RunTimeline；runtime.log；context_fallback。 | 可通过run_id关联Thread/Branch，通用Worker日志主要直接含run/task/worker/generation/attempt而非每条均含Thread/Branch/Profile；测试应区分可关联与逐行字段齐全，不把后者写成已实现。 |
| NFR-TEST-01：可控Provider/计数器和PG/Compose可测。 | tests/unit、api、integration新增测试；session_pg_probe；本地HTTP Provider fixture。 | 后端开发测试面存在，但样本依赖和前端Lint已复现缺口；独立本机验收工程尚未就绪。需要新工程提供慢/故障/浏览器/重启/报告及清理，不依赖旧Demo脚本。 |
| NFR-MIG-01：历史事实保留、可重复升级、安全退回。 | 0004～0006、v2_session_checks.preflight/guard_downgrade；test_v2_session_migrations。 | 已定位；新库/旧库复制/冲突库、事实hash/计数、版本重复和拒绝降级前无结构删除需在PG验证。不能对开发库直接试降级。 |
| NFR-DEP-01：Compose继续多容器、Secret不进镜像/前端。 | docker-compose.yml、docker/api/Dockerfile、.env.example、demo-development Runbook。 | 无新增常驻基础服务；migrate走head，Profile显式导入，Secret运行时注入。独立部署/更新/恢复与残留清理需后续验收；构建词表需要构建时获取资产。 |

### 7.2 PRD第9节的10项总验收关系

| 总验收序号 | 本文覆盖位置及后续证据要求 |
| --- | --- |
| 1：持久恢复与隔离 | §3、§4.1/4.2/4.6/4.8；FR-TH-02、FR-MEM-01、FR-REC-01/02；需持久事实快照+进程/浏览器恢复证据。 |
| 2：真实历史入Provider与预算/来源 | §4.5；FR-CTX-01/02；须捕获受控Provider实收role/content，不仅断言计划存在。 |
| 3：多Profile选择和快照安全 | §4.4/4.7；FR-MOD-01/02；分别验证双Mock流程和本地真实HTTP协议；生产模型效果另议。 |
| 4：Journal流/游标补放 | §4.6、§5；FR-STR-01/02；DB提交、SSE和DOM观察需关联同run_id/seq。 |
| 5：取消与迟到竞争 | §4.8；FR-RUN-01及REL；须覆盖两种提交顺序和失租最后flush回滚。 |
| 6：自动/显式重试不覆盖历史 | §4.3/4.7；FR-BR-02；比较Run/Task/user/assistant及Branch身份数量。 |
| 7：历史分支独立继续 | §4.2/4.5；FR-BR-01；测多级路径与摘要/引用，不以只创建Branch即判通过。 |
| 8：Markdown安全与RAG证据 | §4.9；FR-MD-01、FR-RAG-01；需真实DOM和实际证据身份。 |
| 9：故障分类与无静默成功 | §4.4/4.5/4.8/4.9；FR-ERR-01；注入错误并核对状态/错误/事件/调用次数和无泄密。 |
| 10：完整质量与Compose证据 | §9、§10；先处理当前工具链缺口，再设计本轮独立验收并记录失败/受限/未运行，不复用旧报告充数。 |

## 8. 实际文件和目录变动清单

下表比较 `a204265..595eb04`，不是本次文档任务的修改清单。A=新增，M=修改，R=重命名，D=移除；“沿用”表示对比没有变化但主链路仍使用。包初始化文件仅承担组织职责；开发测试和文档分表列出，避免与产品能力混淆。

### 8.1 后端应用、数据与执行

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `backend/db/models.py` | M | 增5类持久对象Branch/SessionOperation/Profile/Plan/Summary，扩展旧Thread/Message/Run并增加Task/Run约束；具体字段见§3。 |
| `backend/domain/ports/session.py` | A | Branch路径、Profile和Context/Summary非ORM记录及仓储协议；不承担事务调度。 |
| `backend/domain/ports/__init__.py` | M | 增ModelRequest、ModelRequestMessage、ModelRequestProvider协议，保留旧stream_answer接口。 |
| `backend/application/branches.py` | A | resolve_scope/resolve_path、default_branch/create_branch；祖先截断、数量/深度/活动锚点与fork幂等。 |
| `backend/application/session_threads.py` | A | v2列表游标、Thread/Branch事实详情、元数据修改和UTC投影。 |
| `backend/application/session_operations.py` | A | request_hash、replay_operation、record_operation；创建类请求幂等事实。 |
| `backend/application/session_runs.py` | A | Profile选择/Snapshot、新Run/Task、显式操作、取消、安全Run/Context/Event查询；不是第二队列。 |
| `backend/application/context.py` | A | 纯预算和完整轮次裁剪/摘录算法、候选读取组合、遗漏范围；计划落库实际在session_execution.py。 |
| `backend/application/model_profiles.py` | A | 配置校验、可用性、安全列表、受信Secret解析；不提供浏览器任意创建Profile入口。 |
| `backend/application/session_execution.py` | A | schema2执行编排、mandatory预检、冻结检索、计划发布、定时delta、最终证据筛选。 |
| `backend/application/threads.py` | M | 默认Branch、v1列表过滤/busy/head、require_v1_thread和upgrade_for_v2_write。 |
| `backend/application/runs.py` | M | v1 Run/Thread代际守卫；旧取消/查询继续沿用。 |
| `backend/application/task_execution.py` | M | 发布授权检查扩展至Branch；最终完成事务更新Branch和assistant/终态，最后flush越界回滚。 |
| `backend/infrastructure/session/__init__.py` | A | 新仓储适配包入口。 |
| `backend/infrastructure/session/branches.py` | A | 路径元数据、SQL过滤/分页和Branch锁。 |
| `backend/infrastructure/session/context.py` | A | 有界消息正文加载及同Thread/Branch/hash/策略摘要查询；不直接决定裁剪策略。 |
| `backend/infrastructure/session/model_profiles.py` | A | 读Profile和显式事务导入；同版本不可变配置保护与默认策略更新。 |
| `backend/infrastructure/providers/registry.py` | A | 严格schema2 Snapshot校验、非SecretProfile冻结、生成及Embedding重建；旧factory未复制。 |
| `backend/infrastructure/providers/context_counter.py` | A | Mock/TikToken计数、框架/请求开销、稳定计数版本、离线资产校验。 |
| `backend/infrastructure/providers/mock.py` | M | 接收ModelRequest并复用Mock回答；不以Mock回答质量判断真实历史记忆效果。 |
| `backend/infrastructure/providers/openai_compatible.py` | M | stream_request发送规划role/content和冻结参数；HTTP错误正文有界读取、上下文错误及流格式校验。 |
| `backend/infrastructure/events/journal.py` | M | 事件按执行代际写入、schema2身份/DTO校验、常规额度和终态预留、终态后拒绝。 |
| `backend/infrastructure/queue/postgres_queue.py` | M | 取消确认/取消优先回收、领取/续租/运行守卫及事件额度耗尽时安全失败。 |
| `backend/workers/handlers/run_handler.py` | M | 按执行schema分派，旧Run保留旧生成链路。 |
| `backend/workers/runtime.py` | M | 执行停止/mark-running拒绝时补_ack_cancel；沿用有界DB/停机/重试框架。 |
| `backend/tools/sync_model_profiles.py` | A | 显式受信JSON导入CLI、连接生命周期；不自动加载、不接收客户端Secret。 |
| `backend/app.py` | M | 注册3个v2 router；原安全异常边界沿用。FastAPI声明version仍0.1.0，见§10。 |
| `backend/config.py` | M | SSE轮询默认由1改0.2秒；Snapshot执行限额不等于每项都变成env配置。 |

### 8.2 迁移、API和契约

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `migrations/versions/0004_v2_session_branches.py` | A | 执行预检；默认Branch回填、Thread代际/Run来源/执行代际、消息分支、输入一对多、SessionOperation。 |
| `migrations/versions/0005_v2_profiles_context.py` | A | Profile/Plan/Summary表和Run关联、默认Mock seed；不从当前ORM生成历史定义。 |
| `migrations/versions/0006_v2_run_guards.py` | A | Run状态/操作/schema CHECK、活动Run及Run Task唯一索引；再检既有冲突不自动删事实。 |
| `migrations/v2_session_checks.py` | A | preflight查Run输入/Task/assistant/活动冲突/计数等；guard_downgrade保护v2及自定义Profile，禁止base降级。 |
| `backend/api/routes/v2/__init__.py` | A | v2路由包组织。 |
| `backend/api/routes/v2/models.py` | A | 安全Profile列表适配。 |
| `backend/api/routes/v2/threads.py` | A | 7条Thread/Branch/消息路由，请求转应用层、响应及通知适配。 |
| `backend/api/routes/v2/runs.py` | A | 7条Run/Context/Event/SSE/用户操作路由，SSE循环只读持久事实。 |
| `backend/api/schemas/v2/__init__.py` | A | extra=forbid/from_attributes共同DTO基类。 |
| `backend/api/schemas/v2/threads.py` | A | Thread/Branch/Message请求响应、字段和分页限制、旧标题读取兼容。 |
| `backend/api/schemas/v2/models.py` | A | Profile成对请求、可用性及安全投影。 |
| `backend/api/schemas/v2/context.py` | A | 计划/摘要来源/证据及预算投影，显式not_planned。 |
| `backend/api/schemas/v2/runs.py` | A | Run状态/详情、16类schema2 payload和legacy联合、事件分页、操作请求。 |
| `contracts/thread_v2.json`、`contracts/branch_v2.json`、`contracts/message_v2.json` | A | v2持久会话/分支/消息公开契约。 |
| `contracts/model_profile_v2.json`、`contracts/context_plan_v2.json` | A | 安全Profile、预算/摘要来源及Context公开投影。 |
| `contracts/run_v2.json`、`contracts/run_event_v2.json`、`contracts/api_responses_v2.json` | A | Run/严格两代Event联合、请求/错误/分页/操作包装。 |
| `contracts/README.md` | M | 增v2与双代类型生成说明；其旧工具命令已有失效残留，不能直接当现有可运行检查。 |

### 8.3 前端

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `frontend/src/api/v2/threads.ts` | A | Thread/Branch列表详情、修改/分叉/发送和幂等键生成。 |
| `frontend/src/api/v2/runs.ts` | A | Run事实、计划/Event、取消、retry/regenerate调用。 |
| `frontend/src/api/v2/models.ts` | A | 安全模型列表调用。 |
| `frontend/src/api/http.ts` | M | 共用安全HTTP错误码处理；两代client/stream共用base。 |
| `frontend/src/stores/branch.ts` | A | Thread store的Branch选择投影，不复制会话事实。 |
| `frontend/src/stores/model.ts` | A | Profile列表/偏好/有效选择和手动选择revision。 |
| `frontend/src/stores/thread.ts` | M | v2事实、列表/消息分页、epoch、归档/分叉、版本锚点、pending原请求。 |
| `frontend/src/stores/run.ts` | M | v2事实/Event去重/连续游标、尝试草稿、终态刷新、用户操作及scope保护。 |
| `frontend/src/events/run-event-stream.ts` | M | 双代解析、v2分页补放和连接，关闭后不投影迟到HTTP。 |
| `frontend/src/pages/WorkspacePage.vue` | M | 新工作台控件/观察/归档/错误/健康编排；不承载后端状态机。 |
| `frontend/src/components/BranchSelector.vue`、`frontend/src/components/ModelSelector.vue` | A | 分支/成对模型选择及不可用项展示。 |
| `frontend/src/components/RunActions.vue`、`frontend/src/components/ContextNotice.vue` | A | 取消/重试/重生成权限状态、预算/裁剪/摘要范围展示。 |
| `frontend/src/components/MessageTimeline.vue` | M | v2历史/草稿、从消息分叉、加载更早、引用展开；改用共用清洗。 |
| `frontend/src/components/RunTimeline.vue` | M | 取消确认/操作反馈、模型快照/Context、尝试/代数、历史错误区分。 |
| `frontend/src/components/ThreadList.vue` | M | v2列表、归档标记及加载更多。 |
| `frontend/src/markdown/render.ts` | A | 持久与流式Markdown唯一清洗入口。 |
| `frontend/src/styles.css` | M | 分支/模型/操作/上下文等新控件样式。 |
| `frontend/scripts/generate-api-types.mjs` | M | 两代独立类型生成、legacy引用、CLI兼容和漂移检查。 |
| `frontend/src/types/api-v2.ts` | A | 自动生成v2类型，不是手工定义第二真源。原api.ts对比无变更。 |
| `frontend/package.json`、`frontend/package-lock.json` | M | 前端包版本至0.2.0/锁元数据；Lint仍指向旧目录，非已修复项。 |
| `frontend/tsconfig.tsbuildinfo` | M | 类型构建增量产物，不承载业务设计或需求。 |

### 8.4 部署、文档与已有模块

| 文件/目录 | 变动 | 实际职责与调研结论 |
| --- | --- | --- |
| `pyproject.toml` | M | Python项目版本0.2.0，新增固定tiktoken==0.8.0；其余路线沿用。 |
| `docker/api/Dockerfile` | M | 安装后预热cl100k_base词表供运行离线校验。 |
| `docker/model-profiles.example.json` | A | 非Secret显式导入示例；不自动成为第二配置真源，不代表部署已有真实供应商。 |
| `.env.example`、`docker-compose.yml` | M | SSE轮询默认0.2秒、模板说明；migrate既有alembic head自然覆盖新链，无新增Profile守护服务。 |
| `README.md`、`backend/README.md`、`frontend/README.md` | M | 模块职责/使用与验证导航；存在旧编号/旧验收链接残留，见§10。 |
| `CONTEXT.md` | M | Branch、Profile、Context、执行/事件代际等稳定术语说明；部分ADR-003名称仍属重编号残留。 |
| `docs/接口文档.md` | M | 增v2接口/包装/代际/事件/错误与兼容规则；不是新增的第二份接口文档。 |
| `docs/runbooks/demo-development.md`、`docs/runbooks/demo-smoke-environment.md` | M | 迁移/回退、Profile/词表、开发部署及原验收环境说明；后者旧入口不能用作本轮新验收方案。 |
| `docs/prd/002-SesRAG-持久化会话与对话工作台-PRD.md` | M | 追加实施/历史验收状态及链接，没有因此降低原产品验收阈值。 |
| `docs/adr/003-sesrag-persistent-session-workspace-implementation-plan.md` → `docs/adr/002-sesrag-persistent-session-workspace-implementation-plan.md` | R+M | 编号路径已调整，但标题/编号/正文还有003与旧测试工程要求；本轮以现路径识别，用户最新验收边界优先。 |
| `docs/pr/002-SesRAG-持久化会话与对话工作台-PR.md` | A | 简要实施/历史排错和验证记录；本调研独立补充，不覆盖历史数据。 |
| `docs/adr/002-SesRAG-Demo-缺陷修复-plan.md` → `docs/adr/001-SesRAG-Demo-缺陷修复-plan.md`；`docs/pr/002-SesRAG-Demo-缺陷修复-PR.md` → `docs/pr/001-SesRAG-Demo-缺陷修复-PR.md` | R | 上轮修复文档重编号，不是本轮新增产品能力；引用须按现路径。 |
| `docs/当前任务说明.md` | 历史M；当前另有用户工作区修改 | 任务输入，非产品源码；本次保留，不纳入产品实现文件数量或修改。 |
| `backend/api/routes/threads.py`、`runs.py`、`documents.py`、`health.py`及v1 schemas/dependencies | 沿用 | v1原路由文件并未为适配而直接改动；底层应用服务及新v2 router承担变更。不能根据ADR预计清单把它们全列为M。 |
| `backend/domain/enums.py`、`backend/application/errors.py` | 沿用 | legacy枚举/错误基类保留；schema2 cancelling由v2 DTO/应用/DB约束表达，不是遗漏数据库状态支持。 |
| `backend/infrastructure/providers/factory.py`、`backend/infrastructure/queue/adapter.py` | 沿用 | legacy解码和QueuePort适配沿用；新增能力在registry和postgres_queue，未另建平行队列。 |
| `backend/infrastructure/rag/`、文档应用服务/索引handler、`migrations/versions/0001_initial_demo.py`～`0003_chunk_locations.py` | 沿用 | 原文本文档RAG和历史迁移保留；本轮检索/引用组合在session_execution，不扩成知识库版本化。 |
| `frontend/src/api/threads.ts`、`frontend/src/api/runs.ts`、`frontend/src/api/documents.ts`、`frontend/src/types/api.ts` | 沿用 | legacy能力、文档client及v1生成类型保留；不是删除弃用或路径暗改。 |

### 8.5 当前保留的开发测试与历史验收移除

| 文件/目录 | 变动 | 具体职责/证据边界 |
| --- | --- | --- |
| `tests/unit/test_branch_paths.py` | A | 多级祖先截断/不复制、不可见fork、数量/深度/循环、有界详情读取、hash语义。 |
| `tests/unit/test_context_planning.py` | A | mandatory、证据优先裁剪、完整轮次、窗口/字符边界、摘要来源和计数器故障。 |
| `tests/unit/test_model_profiles.py` | A | URL/参数/Secret/tokenizer、离线词表负样本、Profile版本/默认、快照深拷贝/恢复和计数身份。 |
| `tests/unit/test_v2_session_migrations.py` | A | legacy回填/反复升级、事实hash、冲突预检、v2/自定义Profile拒降级、base保护；主要为SQLite迁移回归。 |
| `tests/api/test_v2_session_api.py` | A | Thread2/默认Branch、v1守卫、旧读不升级、fork幂等、归档分页、越界及legacy head。 |
| `tests/api/test_v2_run_api.py` | A | 创建/快照/重放、retry输入复用、head版本、legacy取消/模型要求、SSE游标/尾页。 |
| `tests/api/test_v2_schemas.py` | A | 字段/配对/分页/代际负样本及DTO样本；末项依赖已删除JSON，已实测失败见§9.2。 |
| `tests/integration/test_v2_run_execution.py` | A | 实际应用/Queue/Worker/计划/Journal事务链、历史实收、引用过滤、取消回收、重试/flush/限额/真实本地HTTP。SQLite不能证明PG行锁。 |
| `tests/integration/session_pg_probe.py` | A | 显式新空PG库、多连接Barrier/pg_blocking_pids、取消/成功两顺序、并发创建、来源Task无反锁、旧代/最后flush回滚、取消优先回收。 |
| `tests/integration/test_provider_http.py` | M | 新增ModelRequest实收与上游上下文错误、有界错误正文/时限等协议断言。 |
| `tests/api/test_core_api.py` | M | 旧主链路断言适配新增默认Branch/唯一活动执行等规则，仍是开发回归。 |
| `tests/unit/test_foundation_integrity.py`、`tests/unit/test_foundation_migrations.py` | M | 基础约束/迁移回归适配新head和所需关系；不表示重写0001～0003。 |
| `tests/unit/README.md`、`tests/api/README.md`、`tests/integration/README.md` | M | 补开发测试职责与PG探针运行边界。 |
| `tests/实施测试文件时的通用规范.md` | M | 测试工程规范调整，供后续独立工程遵循。 |
| `tests/demo-smoke/` 原受跟踪文件 | D | 旧Compose/总入口/分类/lib/tooling/fixture/报告/用例等从本分支移除；不逐一当作本轮新增或待恢复文件。历史版本保留，后续新验收独立。 |

## 9. 当前验证资源与本次实际执行

### 9.1 后续设计测试可复用的依据

现存开发测试可提供断言思路，但新验收必须独立拥有fixture、Provider控制、浏览器依赖、环境/报告/清理入口，不把产品开发测试强绑定到旧验收目录。

- 分支/提交：`test_nested_fork_truncates_ancestry_without_copy_and_rejects_invisible_fork`、`test_retry_reuses_input_and_immutable_creator_and_head_version`。
- 上下文：`test_mandatory_budget_fails_before_embedding_and_publishes_plan`、`test_successful_explicit_retry_turn_survives_failed_creator_context`、`test_persisted_summary_has_exact_sources_safe_projection_and_compacted_event`。
- 模型/HTTP：`test_worker_real_http_uses_frozen_model_and_planned_history`、`test_worker_embedding_rebuild_uses_frozen_endpoint_and_kind`、`test_model_request_sends_only_planned_roles_model_and_output_limit`。
- 流/资源：`test_first_delta_flushes_while_provider_stalls`、`test_event_limit_during_retry_becomes_failure_not_stuck_lease`、`test_frozen_timeout_closes_stream_and_never_publishes_success`。
- 取消/事务：`test_cancel_success_transaction_order_has_one_terminal`、`test_v2_final_publication_expiry_rolls_back_message_events_and_head`，以及PG探针的 `cancel_success_probe/creation_probe/stale_and_publication_probe/cancellation_reclaim_probe`。

PG探针只读取显式 `SESSION_PG_PROBE_URL`，要求操作者新建的空库且名称以 `sesrag_session_probe_` 开头，不读开发DATABASE_URL、不自行创建/删除数据库。它先迁移、执行后保留库供审计；不是自动部署到清理的完整闭环。新测试方案必须负责库/容器所有权与最终资源清理，不能将本探针的“保留库”误写成已经自动销毁。

### 9.2 本次命令和真实结果

执行位置为仓库根目录；仅使用已有工具，未安装依赖、启动Compose或改写测试数据。以下不是正式验收用例执行结果。

| 命令 / 检查 | 本次结果 | 结论和限制 |
| --- | --- | --- |
| `git -c core.quotepath=false diff --name-status a204265 HEAD`（按目录分批查看） | 已读取实际A/M/R/D清单。 | 用于§8文件性质；含上轮文档重编号，不将其计为新产品功能。 |
| `npm run check:api --prefix frontend` | exit 0，v1/v2生成类型与Schema无漂移。 | 只证明生成类型同步，不证明运行时DTO和全部HTTP行为正确。 |
| `.venv/Scripts/python.exe -m pytest tests/api/test_v2_schemas.py::test_json_contract_samples_also_validate_backend_dtos -q -p no:cacheprovider` | exit 1；1 failed；`FileNotFoundError`，失败于test_v2_schemas.py读取旧JSON样本。 | 路径 `tests/demo-smoke/tooling/v2-contract-samples.json` 不存在，尚未进入DTO断言；这是测试工程依赖缺口，不是DTO契约断言失败。 |
| `npm run lint --prefix frontend` | exit 1；`MODULE_NOT_FOUND`，找不到旧 `tooling/lint-frontend.mjs`。 | Lint执行器未启动，不能推断产品源码有多少Lint错误，也不能标Lint通过。 |
| 路径存在检查 | 旧总入口、旧Lint脚本和 `docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md` 均不存在。 | 简要记录/README的相关命令和链接无法在当前分支按原样复现。 |

本次**未运行**：后端完整pytest、Ruff/mypy、前端typecheck/build、组件/Vitest/Playwright、PG探针、迁移演练、Compose启停/清理、性能和真实供应商模型测试。简要PR记载的267项后端、67项前端、47项工具检查及两轮all均属于历史记录，本次不重新认证其通过状态；其中旧PERF_002传输错误和浏览器等待超时也不直接推导为当前产品缺陷已经解决或仍必然存在。

## 10. 已发现差异、缺口和测试设计注意事项

这些条目为调研定位及后续方向，本轮未修改对应代码/方案；不要求用户手动恢复旧目录。

| 编号 / 类别 | 问题或边界、代码定位与影响 | 后续处理或测试方向 |
| --- | --- | --- |
| GAP-01 / 测试工程缺口，已复现 | `tests/api/test_v2_schemas.py:test_json_contract_samples_also_validate_backend_dtos` 读取删除目录的JSON。当前该测试必在文件读取阶段失败，历史267项通过不能直接复用。 | 将开发测试所需稳定字面样本放入其自身受版本控制fixture职责内，或独立准备契约样本；保持正/负样本断言。新验收工程不得成为开发测试不可分割的依赖，更不能恢复旧smoke解决。 |
| GAP-02 / 前端工具链缺口，已复现 | `frontend/package.json:scripts.lint` 调用已删除mjs，前端README仍要求旧unit:frontend；前端自身devDependencies未提供独立ESLint/Vitest/Playwright入口。无法复现当前Lint和旧组件验收。 | 后续把必要开发质量工具放回前端或稳定工具职责，独立PRD验收提供浏览器测试依赖/入口。先修工具链再验收，不将缺入口报成产品行为失败或通过。 |
| GAP-03 / 文档/状态残留 | 当前ADR路径002但标题/编号及正文仍ADR-003，简要PR同样残留PR-003；接口文档§7/根README/CONTEXT/contracts说明仍引用003或旧测试工具。部分TEST-002链接不存在。 | 后续集中做编号/链接/现状校准；本调研统一引用真实002路径，不覆盖原历史结果，不把缺失的测试方案写成现存文件。 |
| GAP-04 / 验收边界残留 | ADR §9/§11阶段5/§12/§13仍要求在旧tests/demo-smoke合入新分类；与用户最新独立验收要求及当前删除事实不符。现阶段没有可运行的新独立总入口。 | 后续独立测试方案明确替换这部分验收组织要求，重建本轮专有数据/脚本/报告和清理链；不降低产品、安全或恢复验收标准。 |
| GAP-05 / 版本展示不一致 | `backend/app.py:create_app` 的FastAPI version仍为0.1.0；pyproject/frontend包为0.2.0。影响OpenAPI展示及按该字段识别服务版本，不能据此认定schema2未接线。 | 后续同步应用元数据并加轻量版本核对；HTTP v1/v2与项目版本含义分别说明。 |
| LIMIT-01 / 产品交互待确认 | 当前归档项混排标记，保存的归档选择可恢复只读；没有独立归档列表页。历史Run可按API读取，但UI只自动选当前Branch active/recent，没有全历史Run选择器。 | 对照PRD做真实交互测试，明确可读/可操作范围和“默认活跃”语义；如需更强交互，后续明确需求再改，不能仅由API成功推断UI完整。 |
| LIMIT-02 / 上下文及摘要边界 | 历史候选窗口有界、摘要为摘取且只处理候选内被预算裁剪的消息；Mock词法计数非真实中文tokenizer。 | 构造真实可计数样本/受控计数器，记录遗漏与来源；不以无限历史、语义摘要质量或中文字符数验收当前实现。 |
| LIMIT-03 / 验证证据不足 | 本次未执行独立Compose、PG并发/重启、浏览器/性能验收；旧all含失败/blocked，旧原始工程不在当前版本。 | 依§6/§7重新设计可验证/条件受限矩阵、独立用例和报告；旧错误仅作风险线索。多owner、真实供应商质量、平台信号等按本轮范围和实际环境分别界定。 |

## 11. 后续测试设计建议与优先顺序

本节仅为依据本次调研的测试关注点，不替代正式测试实施方案、测试点或用例文档，也不在本次新增测试脚本。

1. **先校准测试前提**：处理GAP-01/02的独立依赖，核准GAP-03/04的现行编号和验收边界；固定受测提交、迁移head和工具版本。独立工程负责启动→测试→报告→销毁→残留核验，不复用开发库/数据卷。
2. **P0事实和隔离**：消息/Run/Task幂等事务、单Branch活动Run、祖先路径、输入复用、取消/成功两顺序、旧generation/最后flush保护、v1/v2兼容拒绝和安全错误。至少同时观察API与数据库，不能只看UI成功提示。
3. **上下文和模型**：两个Thread/兄弟分支哨兵、Provider实收、mandatory等于/超限、候选窗口、完整轮次、摘要来源/回退、Profile版本/Secret/Embedding冻结、裁剪后引用子集。
4. **流与前端**：慢流独立flush、HTTP/SSE交叠和长Journal、全刷新/切Thread/Branch、重连耗尽、pending原请求、归档、Markdown实际DOM、旧答案与新草稿替换、模型手动覆盖。
5. **恢复与资源**：真实PG独立连接锁屏障、API/Worker重启/失租/取消回收、迁移新/旧/冲突库、受限回退、依赖降级与精确清理；性能独立采样满足PRD阈值，不能以Mock流程代替。

每个测试点建议追溯PRD FR/NFR、本文具体函数、可观察事实及实际环境条件；用例应独立准备数据、记录Thread/Branch/Run/Task/attempt/generation/seq/ContextPlan/Profile身份。预期结果分别断言状态、记录数量/关系、持久事件、实收上下文和DOM，不把“脚本exit0”作为唯一业务断言。

## 12. 本次整体校审

| 校审内容 | 本次结论 |
| --- | --- |
| 需求完整性 | §6逐项覆盖18项FR，§7.1逐项覆盖11项NFR，§7.2映射PRD第9节全部10项总验收；P1项没有被当作非目标跳过。 |
| 实现依据 | 行为按实际应用/仓储/Worker/前端追查；Source Run、输入创建者、Branch路径、取消确认、预算/摘要/引用机制统一，未把预计文件直接认作已新增。 |
| 文件性质 | §8按实施前后Git差异分A/M/R/D，单列沿用文件、开发测试、旧验收移除；本次导航/调研与历史产品变更分开。 |
| 测试真实性 | §9明确3条动态命令：1条通过、2条缺依赖失败；未运行检查和历史结果分别列出，没有宣布完整验收通过。 |
| 异常/边界 | 归属/幂等/并发/取消/失租/超时/资源额度、摘要回退、上游/DB安全失败、legacy代际和回退边界均有定位及后续关注点。 |
| 最新范围一致性 | 明确独立PRD验收，不恢复旧smoke；识别旧方案/简要记录残留。仅交付文档及导航，保留用户任务说明修改。 |
| 路径与文档质量 | 自动核对PRD的29个需求ID，均在逐项表中出现一次；§8涵盖对比基线内全部变动路径（旧验收目录按整体移除列示，任务说明单列）。新文档相对链接无失效，新增导航指向实际文件；代码符号及边界数值复核后修正了Worker错误入口和Provider模块函数的写法。本次文档无尾空白，导航文件的限定范围git diff --check通过；用户任务说明既有尾空白未改动。已失效历史路径明确标为残留，不冒充有效入口。 |

本文可作为下一步设计测试点和测试用例的实现参考。最终产品是否满足全部验收阈值，应由后续独立测试的真实结果决定；本次定位的工具链失败和文档残留仍需跟踪处理。
