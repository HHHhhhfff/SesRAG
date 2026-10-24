# SesRAG 持久化会话与对话工作台 PRD

**编号**：002

**版本**：v0.2

**状态**：已确认且已实施；原同源两轮各104通过，2026-10-24补充缺陷001～004修复后最终完整回归108通过、清理通过、退出0；005原报告未定义。

**日期**：2026-10-18

**适用范围**：`sesrag_v0.2` 第二轮迭代；在现有 SesRAG Demo 上交付浏览器端持久化对话与会话工作台能力。

**对应实施 ADR**：[`ADR-002 持久化会话与对话工作台实施方案`](../adr/002-sesrag-persistent-session-workspace-implementation-plan.md)（已实施；功能及验收证据见实施结果）。


**实施状态更新日期**：2026-10-24。产品范围与验收阈值不变；当前结果见[测试报告](../../tests/sesrag-persistent-session-workspace-test/测试报告.md)和[缺陷报告](../../tests/sesrag-persistent-session-workspace-test/缺陷报告.md)，历史失败/blocked不再代表本轮当前状态。 最新小修与真实回归结论见[修复验收报告](../../tests/sesrag-persistent-session-workspace-test/小缺陷修复与回归验收报告.md)，不把首次工程失败与最终通过合为同源两轮。

**依据和参考(上一轮迭代和实施相关)**：
- [`001 Demo PRD`](001-SesRAG-项目Demo-PRD.md)
- [`完整项目 PRD`](SesRAG-完整项目-PRD.md)
- [`ADR-001 Demo 实施方案`](../adr/001-sesrag-demo-implementation-plan.md)
- [`PR-001 Demo 实施记录`](../pr/001-SesRAG-项目Demo-PR.md)
- [`ADR-001 Demo 缺陷修复方案`](../adr/001-SesRAG-Demo-缺陷修复-plan.md)
- [`PR-001 Demo 缺陷修复记录`](../pr/001-SesRAG-Demo-缺陷修复-PR.md)
- [`接口文档`](../接口文档.md)。

**其他**：本 PRD 是第二轮迭代的产品目标和验收基线。依据当前分支实际代码描述已有能力；实施后的当前结果查阅PR-002/TEST-002。已有能力只有在本 PRD 明确列入验收范围时才算本轮验收项，文档中的现状说明不代表本轮测试已通过。

## 1. 文档目的

本 PRD 将 SesRAG v0.2 的下一轮产品方向收敛为一套可验收的持久化会话工作台：用户可以在不同会话中独立持续对话，查看回答生成过程，在刷新或服务恢复后回到原会话和运行，选择可用模型，并通过重试、重新生成、中断和消息分支管理对话过程。

第一轮 Demo 已具备 Thread、Message、Run、Task、Event Journal、SSE、文本 RAG 和 Vue 工作台等基础。本轮在这些对象和事实来源之上扩展产品行为，不将 Demo 的单用户开发配置误认为生产级身份系统，也不把完整 Agent、工具运行时或知识库生命周期一次性纳入本轮。本文件是完整项目 PRD 中持久化会话方向的 v0.2 范围子集，不取代完整项目 PRD 对 PRD1～PRD4 的路线安排，也不宣称已完成完整 Agent Runtime。

## 2. 产品目标

1. 使 Thread 成为可长期保存和恢复的会话容器；同一会话的历史可供后续 Run 使用，不同会话之间的对话内容和摘要严格隔离。
2. 提供由持久事件驱动的流式回答、执行过程观察、断线补放、页面恢复和用户中断能力。
3. 支持从服务端已配置的多个模型配置中为新 Run 选择模型，并固定本次执行使用的模型和上下文策略。
4. 在模型输入限制内使用当前分支的对话上下文，支持裁剪和有来源记录的简易历史压缩，保留原始消息事实。
5. 支持失败后重试、成功后重新生成和从历史消息建立分支；任何新结果都不覆盖已经保存的消息或执行记录。
6. 安全渲染 Markdown，并保留现有文本 RAG 的引用和错误语义。

## 3. 目标用户与主要场景

### 3.1 目标用户

- 本机或内部开发环境中的单用户操作者，使用浏览器工作台维护多个长期会话。
- SesRAG 项目维护者，用 Mock 或已配置的模型 Provider 验证流式、恢复、分支和模型快照行为。

本轮继续沿用当前 Demo 的单一 `owner_id` 开发边界。此边界不是登录认证、跨用户隔离或生产授权承诺。

### 3.2 主要场景

1. 用户创建多个 Thread；分别连续提问，刷新页面或重启服务后，每个 Thread 都恢复各自的消息历史和最近 Run 状态。
2. 用户在发送新消息前选择一个可用模型；Run 开始后，模型配置变化不影响该 Run。
3. 用户观察排队、检索、生成增量、重试、完成、失败或取消等状态；SSE 中断后系统按事件序号补齐，不重复或丢失已持久化内容。
4. 用户遇到失败时重新尝试；对已完成回答请求重新生成时，旧答案仍可查看并可继续使用对应分支。
5. 用户从历史消息建立独立分支，沿不同上下文继续对话，而不改变原分支。
6. 对话历史超出当前模型可用上下文时，系统保留最近必要上下文并压缩或裁剪较早轮次；无法满足预算时明确报错，不悄悄丢掉当前问题。

## 4. 产品范围

### 4.1 本轮纳入

- Thread 与消息历史的持久化读取、会话选择、恢复和隔离。
- 以 Thread 分支为范围的上下文构建；派生摘要不得取代原始消息。
- 持久事件驱动的流式回答、进度时间线、事件补放和刷新恢复。
- 新 Run 的模型配置选择、服务端配置的模型选项展示和执行快照。
- 模型上下文预算、旧轮次裁剪和有来源信息的简易压缩。
- Worker 自动重试、用户显式重试、成功回答重新生成和消息分支的明确区分。
- 用户中断运行及迟到结果保护。
- Markdown 消息的安全渲染，以及现有文本文档检索和引用在分支/重试场景下的正确关联。

### 4.2 本轮不纳入

- 独立的跨会话语义记忆、自动提取用户画像或把模型摘要当作事实数据库。这里的“长期记忆”指持久保存的会话历史，以及受 Thread/Branch 限定的派生上下文摘要。
- 生产级登录、RBAC、多租户、会话共享和跨用户协作。Thread 隔离只保证本地 Demo 的会话上下文不串用。
- Thread 的物理删除、选择性消息删除和数据保留期限管理。本轮会话不自动过期；归档只影响列表/使用状态，不删除历史。
- 工具注册/执行、任意 Shell 或代码执行、工具授权、人工审批和 `waiting_input` Checkpoint。后续工具运行时产生的安全事件可扩展到时间线，但本轮不要求真实工具调用，也不允许伪造工具事件。
- Skill/Prompt 管理控制台、Web 搜索、图片/音频/视频等多模态输入、Electron 或移动端。
- 文档知识库版本化、审核发布、独立文档目录知识库、混合检索、Rerank 或生产级检索效果指标；本轮沿用 Demo 已有文本 RAG 边界。
- PRD1 范围的完整生产级 Worker 调度、优先级、租户配额、背压和死信管理。本轮只要求会话 Run 能安全使用现有持久任务执行能力。
- 生产 SLO、长期容量和真实模型输出质量保证。Mock Provider 可用于流程验收，不证明模型效果。

## 5. 核心对象与基本关系

以下是产品语义，具体表结构、接口和 Provider 组合方式由后续 ADR 决定。

| 对象 | 含义与主要职责 | 关系与边界 |
| --- | --- | --- |
| `Thread` | 长期会话容器，保存标题、所有者、创建/更新时间和归档状态。 | 包含多个 `Branch`；拥有会话消息和多个 `Run`。归档不等于删除历史。 |
| `Branch` | Thread 中一条可继续对话的路径，记录分支点及当前路径位置。 | 可引用父分支和分叉消息；读取分支时组合共同祖先与本分支消息，不复制或改写祖先事实。每个 Thread 至少有一个默认分支。 |
| `Message` | 用户输入或 assistant 最终回答等不可变会话事实，保存正文、角色、来源、时间和创建它的分支/Run 关系。 | 用户消息可被多个重新生成的 Run 引用；后代 Branch 可沿分支关系读取共同祖先消息；每个 Run 至多产生一个最终 assistant Message。已保存正文不因重新生成而覆盖。 |
| `Run` | 对某个用户输入的一次完整执行身份，包含状态、来源消息、分支、快照和可选最终回答。 | 一个 Run 只属于一个 Thread、一个 Branch 和一个用户 Message；重试/重新生成建立新的 Run 并记录来源关系。Worker 对同一 Run 的自动重试仍是同一 Run。 |
| `RunSnapshot` | Run 创建时冻结的执行配置。 | 至少包含模型 Profile 标识/版本、Prompt 版本、上下文预算/策略、RAG 配置和必要的非敏感执行参数；不保存 API Key、Secret 或原始凭据。 |
| `ModelProfile` | 服务端配置且可供用户选择的模型选项。 | 前端仅得到安全展示字段和可用性；凭据留在服务端。修改或移除 Profile 不得静默改变已创建 Run 的快照。 |
| `Event Journal` | Run 内按序追加的执行事实，是流式内容和状态恢复的事实来源。 | 每个 Run 内 `seq` 单调递增；SSE 和页面是投影，断线通过 `after_seq`/等价游标补放。 |
| `ContextPlan` / `ConversationSummary` | 某个 Run 实际选取、裁剪或压缩的分支上下文及其来源说明。 | 严格限定于一个 Thread/Branch；摘要记录覆盖的消息范围和策略版本，是可重建的派生数据，不覆盖原始 Message。 |
| `Task` / 执行尝试 | Worker 执行 Run 的队列任务和内部尝试状态。 | 基础租约、心跳、期限和有界重试沿用现有调度边界；基础设施自动重试不创建重复用户消息或会话层 Run。 |

关系概览：

```text
Thread
└── Branch（主分支及其分支点/继承路径）
    ├── Message（不可变消息；祖先消息可被后代分支引用）
    ├── Run（一次模型执行）
    │   ├── RunSnapshot + ContextPlan
    │   ├── Task / 内部执行尝试
    │   ├── Event Journal（持久增量和状态）
    │   └── 至多一个最终 assistant Message
    └── ConversationSummary（可选派生摘要，带消息范围）
```

## 6. 功能需求

优先级说明：P0 为会话事实正确性、核心交互和恢复阻断项；P1 为增强会话效率和可解释性，但仍属于本轮 v0.2 交付范围。

| 编号 | 功能需求 | 验收标准 | 优先级 |
| --- | --- | --- | --- |
| FR-TH-01 | 用户可以创建、列出、打开、重命名、归档和取消归档 Thread。Thread 列表按最近更新时间排序；归档后历史仍可读取，不能被误当作物理删除。 | 创建后刷新仍可读取；标题、归档和取消归档状态在 API/界面一致；归档 Thread 不再作为默认活跃会话，但仍可从归档列表打开，取消归档后回到普通列表。 | P0 |
| FR-TH-02 | 每个 Thread 独立保存用户消息、assistant 最终回答、Run 和派生摘要。构建新 Run 时只读取当前 Thread/Branch 的对话历史，不得将其他 Thread 的消息、摘要或临时流式文本带入 Prompt。 | 使用包含明显哨兵内容的两个 Thread 交替提问；Provider 收到的上下文只包含当前 Thread/Branch 的允许历史；刷新和切换会话后消息、Run、事件和答案均不串线。 | P0 |
| FR-MEM-01 | 持久化会话历史作为长期对话记忆；用户消息和已完成回答按事实保留，后续 Run 可以使用当前分支的历史。临时 `answer.delta` 只能是运行投影，不能提前成为已完成 Message。 | 重启 API/Worker 和刷新浏览器后历史正文、顺序、角色、Run 关联及完成状态一致；运行中刷新不会把未完成草稿显示成已完成事实。 | P0 |
| FR-BR-01 | 用户可从选定的历史消息位置创建新 Branch 并继续对话。原 Branch 保持原样；新 Branch 展示共同历史前缀和自己的后续消息。 | 新分支有稳定身份和明确分叉点；两个分支的新增消息、摘要、Run 和回答互不覆盖；选择不同分支时可读取正确路径；共同祖先消息不会被重复创建成新事实。 | P1 |
| FR-BR-02 | 支持对失败/取消的回答重新尝试，以及对已完成回答重新生成。用户操作创建可追溯的新 Run/回答路径，保留原始用户输入、旧回答、失败记录和事件。自动 Task 重试与用户显式重试必须在 UI 和数据语义上可区分。 | 自动重试沿用同一会话 Run 和用户 Message；用户显式重试/重新生成使用新 Run 身份并关联原 Run/输入；成功旧回答不被覆写；每个 Run 最多一个最终 assistant Message；失败的新尝试不污染仍可查看的旧分支。 | P0 |
| FR-MOD-01 | 用户可在发起新 Run 前从服务端配置的多个 ModelProfile 中选择模型，并看到当前选择。列表只返回安全展示字段及明确的启用状态；仅启用且配置完整的 Profile 可用于新 Run，默认选择由系统提供。 | 当配置两个或更多可选 Profile 时，前端可区分和选择它们；禁用或配置不完整的 Profile 不可提交并显示安全说明；Provider 在运行期才发生的超时/认证等故障由 Run 错误语义处理；API Key、完整 DSN 和其他 Secret 不出现在前端或模型列表响应。 | P0 |
| FR-MOD-02 | 创建 Run 时固定选中的 ModelProfile 及其版本/模型标识、必要生成参数；Profile 的后续更改只影响新 Run。真实模型凭据通过服务端 Secret 配置解析，不写入 Run、Event 或前端状态。 | 建立 Run 后修改默认 Profile/模型参数，再恢复或重试该 Run；原 Run 使用其快照且不静默切换模型。Profile 已不可用时返回明确、可诊断错误，不自动回退到 Mock 或其他模型。 | P0 |
| FR-STR-01 | 对话生成时将安全的状态变化和回答增量先持久化为 Run Event，再投影到 SSE/UI。至少可区分排队、开始、检索完成（适用时）、生成增量、内部重试、成功、失败、取消。 | 在慢速 Provider 下可观察到增量而非只在结束后出现整段回答；UI 按服务端状态展示；Event 的 seq 严格递增，终态只在最终 Message 与终态事实成功提交后显示。 | P0 |
| FR-STR-02 | SSE/浏览器断开只停止观察，不取消 Run。客户端记录最后处理的 Event 序号，重连或刷新后补放后续事件并去重。 | 在任意已提交 seq 断开并重连，事件按序补齐且没有重复可见增量；断开期间 Run 仍可成功/失败；终态 Run 不会因重连被重新执行。 | P0 |
| FR-REC-01 | 浏览器刷新或重新打开工作台时，从服务端恢复 Thread 列表、所选 Thread/Branch、持久消息和最近 Run 状态；若 Run 非终态，则恢复观察并从已持久 Event 位置继续订阅。 | 刷新前后 Thread/Branch/消息顺序和 Run 终态一致；运行中刷新后继续看到该 Run 的新事件；刷新、切换 Thread 或关闭 SSE 不会发送取消命令。浏览器本地偏好只能提示选择，服务端读取结果为事实。 | P0 |
| FR-REC-02 | API/Worker 重启或 Worker 任务租约回收后，系统通过同一 Run/Task 的现有持久执行机制继续处理；已经持久化的事件可重放。重启后模型 Provider 可从 RunSnapshot 重建。 | 受控停止/重启后 Thread、Run、Task 和 Event 身份保持不变；不重复创建用户输入和会话 Run；旧执行者的迟到结果不能覆盖当前代或终态。恢复可重做一次未完成的模型调用，不承诺从 Provider 内部 token 位置精确续算。 | P0 |
| FR-RUN-01 | 用户可以中断 queued、running 或 retry_waiting Run。排队/等待重试的任务可直接取消；运行中 Run 记录取消请求，Worker 在可中断边界停止 Provider/后续检索执行并明确结算为 cancelled。SSE 断开不等同于中断。 | 中断成功后 Run/Task 状态及事件可查询；取消后的迟到 Provider 结果不能提交成功 Message 或覆盖终态；未确认取消时 UI 保持 cancelling/处理中等真实状态，不能伪报成功。部分增量保留在事件历史，不作为完成回答。 | P0 |
| FR-OBS-01 | 工作台提供可读的 Run 状态/事件时间线，展示排队、执行、检索、重试、取消和终态等关键进展及安全错误码/摘要。 | 时间线事件能对应唯一 Run 且按序展示；页面不根据本地定时器推断状态。不得展示隐藏思维链、完整 Prompt、Secret、原始敏感 Provider 请求/响应或宿主路径。当前版本没有工具执行，不得伪造工具调用；未来工具轨迹需由另行批准的工具 Runtime 事件提供。 | P0 |
| FR-CTX-01 | 每个新 Run 根据所选模型的上下文上限、系统指令、检索证据、历史轮次和输出预留预算构造 ContextPlan。超限时优先保留安全策略、当前用户输入和近期完整对话轮次，并按边界裁剪较早轮次。 | 注入可控 Token 计数/模型上下文上限验证预算；裁剪结果仅来自当前分支，较旧完整轮次按确定规则减少；当前用户输入、必要系统指令和输出预留不能被静默截断。若发生裁剪或摘要，界面显示安全的上下文处理提示和受影响的历史范围，不展示完整 Prompt。仍无法满足预算时明确返回 `CONTEXT_TOO_LARGE` 类错误且不调用 Provider。 | P0 |
| FR-CTX-02 | 当仅裁剪不足或配置要求压缩时，系统可将较早历史轮次压缩为受 Thread/Branch 限定的简易摘要，并记录来源消息范围、摘要策略版本和生成时间。摘要是派生上下文，不替换或删除原消息。 | 触发压缩后后续 Run 可读到对应摘要和最近原始轮次；摘要不跨 Thread/Branch 复用，原始消息仍能完整查看；压缩失败时按确定策略继续裁剪或明确失败，不得构造无来源的“记忆”。 | P1 |
| FR-MD-01 | 用户和 assistant 消息以 Markdown 文本保存和展示；支持常见段落、标题、列表、链接、行内代码及代码块。渲染使用允许的安全规则清洗不可信内容。 | 常见 Markdown 结构正确展示；消息中的脚本、事件处理属性、危险 URL 和 HTML 注入不能执行；持久保存的原文与渲染 DOM 分离；失败/流式增量最终仍与保存的 Markdown 正文一致。 | P0 |
| FR-RAG-01 | 保留现有文本 RAG 的检索和引用能力。运行时间线显示检索状态时，引用必须仍关联当前 Run 实际获得的 Evidence；不同 Thread/Branch 的对话上下文隔离不得伪装成文档知识库已隔离。 | 有召回时最终消息引用的 document/chunk/batch/location 来源于该 Run 的 Evidence；无证据与检索基础设施失败表现不同；Thread/Branch 切换不会把另一 Run 的临时引用或增量展示到当前回答。 | P1 |
| FR-ERR-01 | 模型不可用、超时、上下文超限、取消、检索为空和基础设施故障应有可区分的安全结果；支持的可重试故障进入有界自动重试，不可重试故障不得无限尝试。 | 每类场景可通过状态、稳定错误码/安全摘要或 Event 区分；不把 Provider/数据库故障伪装为“无相关资料”；响应和日志不泄露 Secret、Prompt 原文或内部堆栈。 | P0 |

## 7. 关键行为与状态约定

### 7.1 正常消息执行

1. 用户在当前 Thread/Branch 编辑问题并选择 ModelProfile。
2. API 验证 Thread/Branch 归属和输入，创建一个不可变用户 Message、Run、RunSnapshot 与 Task；相同 Idempotency-Key 的重复请求不得产生第二份事实。
3. Worker 按 RunSnapshot 构造当前 Branch 的 ContextPlan，执行可选 RAG 检索和模型调用；每条对用户可见的执行进展先写入 Event Journal，再用于 SSE 投影。
4. 正文增量只作为该 Run 当前尝试的临时投影；完成时在持久化事务内写入唯一最终 assistant Message 和成功终态，随后 UI 用服务端最终事实替换临时投影。

### 7.2 恢复与重试

- 页面恢复是恢复观察，不等于创建新 Run 或重新发送用户问题。
- Worker/Provider 故障引起的自动重试沿用原 Run 和用户 Message；新的执行尝试必须有清晰边界，避免新旧增量拼接成错误答案。
- 用户主动重试失败/取消的 Run 或重新生成成功回答时，创建新 Run 并保留 `retry_of_run_id`/`regenerates_run_id` 等可追溯关系；若生成替代回答，应进入独立 Branch，旧回答继续可读。
- 已成功 Run 不可被取消或覆盖。取消与成功竞争时只有一个持久终态获胜；另一方不能追加冲突的完成事实。

### 7.3 上下文记忆和压缩

- 对话历史、摘要及分支前缀必须按 Thread/Branch 解析；严禁从其他 Thread 复用消息或摘要。
- 原始 Message 是用户事实；摘要、Token 估算和 ContextPlan 是派生数据，可以重建、失效或按版本更新，但不得破坏原文。
- 系统必须能说明一个 Run 使用了哪些历史范围/摘要版本以及采用的上下文预算策略；不要求把敏感完整 Prompt 暴露在 UI 或普通日志中。
- 超预算时优先裁剪较早完整轮次；不能满足条件则明确失败，不得静默丢失当前输入或越过模型上限调用 Provider。

### 7.4 Run 状态

会话层 Run 至少支持 `queued`、`running`、`retry_waiting`、`cancelling`、`succeeded`、`failed` 和 `cancelled`。`cancelling` 是持久取消请求后的非终态；排队或等待重试的任务可直接结算为 `cancelled`，运行任务在 Worker 确认停止或按既定租约恢复机制安全结算后进入 `cancelled`。`succeeded`、`failed`、`cancelled` 是不可逆终态。自动重试的 Task 可经历 `retry_waiting` 并回到 `running`，但不得因此新建会话层 Run；终态 Run 的用户显式重试/重新生成通过新 Run 表达。

```text
queued ──> running ──> succeeded
  │           ├──> failed
  │           ├──> retry_waiting ──> running（同一 Run 的自动重试）
  │           │        ├──> failed
  │           │        └──> cancelled
  │           └──> cancelling ──> cancelled
  ├──> failed（如 deadline 或不可重试错误）
  └──> cancelled
（旧执行者失租/迟到写回不得改变新代或终态）
```

## 8. 非功能需求

| 编号 | 类别 | 需求和验收口径 |
| --- | --- | --- |
| NFR-SEC-01 | 安全 | 模型/API 密钥只在服务端配置与 Provider 调用中使用；不得进入 Message、RunSnapshot、Event、前端 payload 或默认日志。错误信息可诊断但不能返回 Secret、Prompt 原文、内部堆栈和宿主路径。 |
| NFR-SEC-02 | Markdown 安全 | Markdown 渲染必须对不可信用户输入和模型输出执行 HTML 清洗；测试脚本/危险属性/危险协议链接不得执行。 |
| NFR-ISO-01 | 会话隔离 | 每次上下文构造、摘要读取、流式投影和 Branch 遍历都校验 Thread/Branch/Run 关联；错误或迟到响应不能跨会话显示。 |
| NFR-REL-01 | 事实可靠性 | PostgreSQL 继续作为 Thread、Message、Run、Task、Event 和摘要元数据事实来源；SSE、Redis、前端缓存均为投影。事件按 Run 单调追加；最终 Message 与 Run 终态具备原子提交语义。 |
| NFR-REL-02 | 恢复 | API、Worker 或浏览器重启后可从持久事实恢复会话和可恢复 Run 的观察状态；租约过期和旧执行者写回遵守现有 generation 条件。 |
| NFR-PERF-01 | 响应性 | 在本机 Compose 验收环境、数据库健康且单用户交互时，消息提交 API 的 p95 在 1 秒内返回 Run 身份；从服务端提交首个 delta Event 到本地 UI 可见不超过 1 秒。该目标不包含模型上游首 token 等待时间，也不等同于生产 SLO。 |
| NFR-CAP-01 | 上下文与资源边界 | 输入 Token 预算必须为有限值，并预留输出预算；流式答案长度、事件速率和执行时长沿用服务端有界配置。不得通过无限扩展对话上下文规避模型限制。 |
| NFR-OBS-01 | 可观察性 | Run、Thread、Branch 和 Event 序号可关联；日志/时间线区分服务端事实与临时 UI 投影，记录上下文裁剪/摘要范围和模型 Profile 标识但不记录凭据。 |
| NFR-TEST-01 | 可测试性 | Mock Provider、可控慢速/失败 Provider、可控 Token 计数器及真实 PostgreSQL/Compose 测试能够验证模型快照、分支隔离、预算裁剪、取消竞争、重连和恢复；Mock 不用作真实效果证明。 |
| NFR-MIG-01 | 兼容迁移 | 现有 Demo 数据升级不得静默删除 Thread、Message、Run、Event 或文档事实。迁移需可重复验证；破坏性操作、回退边界、旧快照兼容和恢复步骤由对应 ADR 说明。 |
| NFR-DEP-01 | 部署 | 开发部署继续通过 Docker Compose 管理前后端、API、Worker、PostgreSQL 和 Redis；Profile Secret 不写入镜像、前端构建产物或版本控制。 |

## 9. 验收标准

本 PRD 的完整验收至少满足以下结果，具体矩阵、测试数据和命令由后续测试方案制定：

1. Thread/Branch/Message/Run 在刷新、API/Worker 重启后可按服务端事实恢复；Thread 和 Branch 之间无消息、摘要、引用或流式草稿串用。
2. Thread 内连续对话确实把当前 Branch 的允许历史传给 Provider；超出 Context Budget 时可验证裁剪/压缩结果及来源，不丢失原始消息，不静默截断当前输入。
3. 配置至少两个可用 ModelProfile 时用户可选择模型；创建后的 Run 快照固定，凭据不进入持久公开字段和前端。
4. 流式增量和关键状态来自持久 Journal；按任意游标重连/刷新都能补齐事件、消除重复，且不因断线取消 Run。
5. 用户中断能产生明确持久状态；取消与成功竞争、Provider 迟到、Worker 租约失效时不产生相互矛盾的最终消息或终态。
6. Worker 自动重试不创建重复用户消息或 Run；用户显式重试/重新生成创建可追溯的新 Run/Branch，旧回答和失败记录保持可读。
7. 从任意支持的历史消息位置建立 Branch 后，两条对话路径可分别继续，消息和摘要只按对应路径参与上下文。
8. 常见 Markdown 正确渲染，恶意 HTML/脚本/危险链接无法执行；文本 RAG 的引用仍来自当前 Run 的实际检索证据。
9. 队列、Provider、数据库、检索、上下文压缩等失败具有可区分且不泄密的错误语义；无条件的“成功”“无知识”或静默回退都不作为故障替代。
10. 后端单元/契约/迁移测试、前端类型检查与组件/浏览器测试、Docker Compose 集成回归均按后续测试方案执行并记录真实结果；未运行项不得标为通过。

## 10. 立项时的实现基线与本轮差距

下表保留PRD确认时从哪里演进的历史基线，不代表实施后的当前缺口，也不代表这些实现已通过 v0.2 验收。文件名和对象来自立项时仓库；当前实际落地及剩余限制见文首结果文档。

| 能力 | 当前代码基线 | 本轮产品差距 |
| --- | --- | --- |
| Thread/Message/Run | `backend/db/models.py`、`backend/application/threads.py`、`backend/application/runs.py`、`backend/api/routes/threads.py`、`frontend/src/stores/thread.ts` | 有持久会话与消息主链路；需要扩展 Branch/路径选择、重命名/完整归档行为，并让会话历史实际进入后续模型上下文。 |
| Run Snapshot/Provider | `backend/application/threads.py`、`backend/workers/handlers/run_handler.py`、`backend/infrastructure/providers/`、`backend/config.py` | 当前配置主要是单个 Mock 或单个 OpenAI-compatible 模型；需支持多个安全 Profile、选择和快照解析，旧快照需兼容。 |
| SSE/Event Journal | `backend/infrastructure/events/journal.py`、`backend/api/routes/runs.py`、`frontend/src/events/run-event-stream.ts`、`frontend/src/stores/run.ts` | 已有持久事件、增量、补放和重连基础；需按 Thread/Branch 恢复所选 Run，并使新分支、重新生成和取消边界一致。 |
| 前端会话与消息 | `frontend/src/pages/WorkspacePage.vue`、`frontend/src/components/ThreadList.vue`、`frontend/src/components/MessageTimeline.vue`、`frontend/src/components/RunTimeline.vue` | 已有 Markdown 清洗和状态时间线；需增加 Profile 选择、Branch 切换/创建、明确区分重试与重新生成、长期上下文状态。 |
| Worker 与 RAG | `backend/infrastructure/queue/`、`backend/workers/`、`backend/workers/handlers/run_handler.py`、`backend/infrastructure/rag/` | 继续使用 PostgreSQL 持久任务、现有 lease/retry 和文本 RAG；新增上下文处理须保持任务幂等、引用身份和故障分类。 |
| 数据契约与迁移 | `contracts/`、`migrations/versions/`、`frontend/src/types/api.ts` | 新对象、状态和事件必须版本化；字段、事件类型、前端类型和接口文档由实施 ADR 确定并保持同步。 |

## 11. 后续实施拆分建议

本 PRD 定义同一个 v0.2 产品目标，但实施时建议按可独立验证的纵向切片拆分 ADR/PR：

1. **会话分支与上下文事实**：Branch/分叉关系、历史读取、跨会话隔离、上下文预算和压缩来源。
2. **多模型与可恢复流式运行**：ModelProfile、不可变 Snapshot、Event/SSE、刷新/重启恢复和错误语义。
3. **用户控制与工作台交互**：取消、显式重试、重新生成、分支切换和 Markdown 安全展示。
4. **集成与发布验收**：迁移/旧数据兼容、Compose 验证、端到端回归、Runbook 与 README 更新。

以上是建议拆分，不预先规定每项对应的模块、表结构、API 路径或模型 SDK；具体实现决策应在对应 ADR 中明确。

## 12. 产品边界决策记录

- “长期记忆”按可追溯的 Thread/Branch 会话历史理解，摘要只是派生上下文，不是跨会话用户画像或事实库。
- “思考过程显示”指持久化的执行阶段、状态、检索结果摘要、重试和错误等可公开进展；不显示模型私有隐藏思维链。工具执行能力不在本轮范围。
- “流式会话”指 Event Journal 持久化后向客户端投影；浏览器连接不是执行本身，连接中断不能取消 Run。
- “重试”区分 Worker 自动尝试和用户显式操作。自动尝试沿用同一 Run；用户重试和重新生成创建新的、可追溯的 Run，不覆盖旧结果。
- “不同会话独立”指对话消息、分支、摘要、运行投影和上下文彼此隔离；当前 Demo 的单一 owner 文档知识库是否共享不在本 PRD 中改造，也不视为多租户隔离。
- 真实工具调用、审批恢复点、跨会话语义记忆和生产认证应进入后续 PRD/ADR，不得以本 PRD 的 UI 占位或事件预留宣称已经交付。
