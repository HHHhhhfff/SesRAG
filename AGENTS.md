# SesRAG Agent 开发约束

本文件是 SesRAG 仓库的项目级约束。它约束 AI 和开发者如何演进工程，不替代产品需求文档、架构决策记录或运维手册。进入子目录后，如存在更近的 `AGENTS.md`，先读取更近的规则。

## 1. 项目定位与权威文档

SesRAG 是一个前后端分离、Docker Compose 部署的持久化会话 RAG 应用。产品演进顺序是：先交付可运行 Demo，再围绕持久会话、可恢复 Run 和 Worker 调度完善核心能力，最后扩展工具系统与知识库生命周期。

权威文档顺序如下：

1. `docs/prd/SesRAG-项目Demo-PRD.md`：当前 Demo 的交付边界和验收标准。
2. `docs/prd/SesRAG-完整项目-PRD.md`：完整目标产品和分阶段路线。
3. 后续新增的 `docs/adr/`：已确认的架构决策和不变量。
4. 代码、测试、部署文件：当前可执行实现。

当实现与 PRD 冲突时，先记录差异并更新 PRD 或 ADR，再修改代码；不得用隐式兼容分支长期掩盖冲突。

## 2. 仓库组织约束

目标目录按职责组织，避免按临时功能堆放文件：

```text
SesRAG/
├── backend/                 # FastAPI、领域服务、Worker、适配器
│   ├── api/                 # HTTP/SSE 路由与请求响应模型
│   ├── domain/              # Thread、Run、Task、Document 等领域对象
│   ├── application/         # 用例编排和事务边界
│   ├── infrastructure/     # SQL、Redis、向量库、模型 Provider
│   └── workers/             # 任务领取、租约、心跳、优雅停机
├── frontend/                # Vue 3 + TypeScript 前端
├── migrations/              # Alembic 数据库迁移
├── contracts/               # 版本化 API/Event/Tool JSON Schema
├── tests/                   # 单元、契约、集成和端到端测试
├── docs/                    # PRD、ADR、Runbook、开发说明
├── docker/                  # 应用镜像及运行辅助文件
├── docker-compose.yml       # 本地开发编排
├── pyproject.toml           # Python 依赖和质量工具
└── frontend/package.json    # 前端依赖和脚本
```

新增模块必须归入已有职责；只有当边界稳定且有独立生命周期时才新建顶级目录。不要把业务逻辑放进路由函数、ORM 模型或 Vue 页面组件中。

## 3. 核心领域不变量

- `Thread` 是长期会话容器；`Message` 保存事实历史；`Run` 表示一次用户输入触发的完整执行。
- 一个 Run 只能绑定一个 Thread、一个用户 Message 和至多一个最终 assistant Message。重试是同一 Run 下的执行尝试，不得重复创建用户消息。
- Run 的状态和 Event Journal 以 PostgreSQL 为事实来源。SSE、Redis Pub/Sub 和前端状态都是投影，不得直接宣布终态。
- Event 按 Run 内 `seq` 单调递增、追加写入且不可更新；终态事件必须与最终消息在同一事务边界内提交。
- Worker 领取任务必须使用 lease/generation 条件更新；旧 Worker 的迟到心跳和完成回写不得覆盖新一代执行者。
- Worker 进程收到停止信号后停止领取新任务，允许当前任务在截止时间内完成或显式释放租约；不得静默丢弃已领取任务。
- 外部模型、Embedding、向量库和队列都通过 Adapter/Port 接入。领域层不能直接依赖具体厂商 SDK。
- 失败、超时、取消和“检索为空”必须区分；基础设施故障不得伪装成无知识回答。
- Secret、API Key、数据库密码和原始凭证不得进入 Message、Run、Event、日志或前端状态。
- 文档索引以 `DocumentVersion` 或等价不可变版本为边界；构建中的候选版本不得污染当前可检索版本。

## 4. API、契约和迁移

- 正式 API 使用版本前缀，例如 `/api/v1`；不创建平行的旧聊天接口来绕过正式 Run/Event 流程。
- API 响应、SSE Event、任务事件和工具结果要有版本化契约；跨前后端修改先更新契约真源，再生成或同步类型。
- ORM Schema 变更必须提供 Alembic 迁移和迁移测试。禁止只改模型不改迁移，禁止运行时双读双写掩盖破坏性变更。
- 幂等键、版本号、事件序号、租约代数等并发控制字段必须由服务端生成和校验，不能信任前端传入的最终状态。

## 5. Worker 与持久化执行

- Demo 阶段以 PostgreSQL 任务表作为权威队列，Redis 只承担通知和短期缓存；后续通过 QueuePort 替换为 Redis Streams 或其他 MQ。
- 任务领取、租约续期、重试退避、取消、过期回收和终态落库必须可测试，不能依赖进程内内存状态。
- 每个 Worker 要有稳定 `worker_id`；每次领取生成单调递增的 `generation`，所有写回都带 `task_id + generation` 条件。
- 任务处理器必须幂等，外部副作用使用 `operation_id` 或等价幂等标识。异常要写入可诊断错误码、attempt 和最近进度。
- 任务循环使用有界超时和取消检查；禁止无限重试、无限递归和无上限事件/上下文增长。

## 6. RAG 与模型调用

- 文档解析、切分、Embedding、索引、召回和生成分别位于可替换的 Port/Adapter；不要把一种向量库或模型的字段泄漏到领域层。
- Demo 先支持文本型文档和简单召回；优化效果、混合检索、Rerank、评测和版本发布必须按完整 PRD 分阶段加入。
- 检索结果要保留文档、版本、chunk、位置和分数等证据身份；回答引用只能引用本次 Run 实际获得的证据。
- 每个 Run 创建时冻结模型和检索配置快照，运行中修改配置不得改变已开始的 Run。

## 7. 前端约束

- 前端只负责交互和状态投影，不能自行推断 Run 终态或修改任务状态。
- 会话页面按 Event `seq` 去重并支持断线重连/补放；刷新页面后从服务端恢复 Thread、Message、Run 和事件。
- API 类型和 Event 类型从契约同步，避免手写第二套字段定义。
- 页面、组件、store 和 API client 分层；不要把请求、事件解析、Markdown 清洗和展示逻辑全部放进单个页面。

## 8. 质量与安全门禁

- 新增功能先写失败测试，再写最小实现；至少覆盖正常路径、重试/超时、并发或重启恢复中的关键不变量。
- 提交前按改动范围运行后端单测、契约测试、前端类型检查、Lint、构建和 Compose smoke test；未运行的检查必须在交付说明中列出。
- 日志使用结构化字段，默认不记录完整 Prompt、Secret、文档原文和工具敏感参数；为 `thread_id`、`run_id`、`task_id`、`worker_id` 提供关联字段。
- 文件上传限制扩展名、大小、路径和 MIME；解析器不得任意访问宿主路径。工具和外部 URL 能力默认关闭，采用显式白名单。
- 不自动提交、推送、重置或覆盖用户已有修改；不为“兼容旧实现”新增第二套事实来源。

## 9. 文档维护

- 产品范围变化更新 `docs/prd/`；架构不变量或技术取舍变化新增/更新 `docs/adr/`；启动、迁移、故障处理变化更新 `docs/runbooks/`。
- 需求中出现“后续再做”的能力必须进入完整 PRD 的路线图或明确列为非目标，不在 Demo 中偷偷实现半成品。
- 文档使用稳定术语：统一使用 `Thread`、`Message`、`Run`、`Task`、`Worker`、`Event Journal`、`Document Version`。
