# SesRAG Demo

SesRAG Demo 是一个前后端分离、Docker Compose 部署的持久化会话 RAG 纵向切片。当前实现覆盖 Thread/Message/Run、PostgreSQL 持久任务、Worker lease/heartbeat/retry、文本文档索引、pgvector 存储、SSE Event Journal 投影和 Vue 工作台。

## 目录

```text
backend/       FastAPI、领域对象、应用服务、基础设施适配器和 Worker
frontend/      Vue 3 + TypeScript 工作台
migrations/    Alembic 数据库迁移
contracts/     Run Event JSON Schema
tests/         单元、API 和集成测试
docker/        API/Worker 与前端镜像定义
docs/prd/      Demo 与完整项目 PRD
docs/adr/      实施方案和架构决策
docs/pr/       PRD 实施完成后的开发结果记录
docs/test/     PRD 测试验收方案和结果
docs/runbooks/ 部署、开发、故障和验收说明
CONTEXT.md     稳定术语及其来源、状态
AGENTS.md      仓库级 AI 开发约束
```

## 文档入口

- 产品目标：[`docs/prd/`](docs/prd/)，当前 Demo 为 [`001-SesRAG-项目Demo-PRD.md`](docs/prd/001-SesRAG-项目Demo-PRD.md)，完整目标为 [`002-SesRAG-完整项目-PRD.md`](docs/prd/002-SesRAG-完整项目-PRD.md)。
- 实施方案与架构决策：[`docs/adr/`](docs/adr/)。
- 开发结果与测试验收：[`docs/pr/`](docs/pr/)、[`docs/test/`](docs/test/)。
- 部署、故障和验收流程：[`docs/runbooks/`](docs/runbooks/)；代码修改规范见 [`docs/项目开发和修改的通用执行规范.md`](docs/项目开发和修改的通用执行规范.md)。
- 接口唯一说明：[`docs/接口文档.md`](docs/接口文档.md)；稳定术语见 [`CONTEXT.md`](CONTEXT.md)；仓库级 AI 规则见 [`AGENTS.md`](AGENTS.md)。

## 快速启动

要求 Docker Desktop、Docker Compose 和 Node.js 20（仅本地前端开发需要）。后端镜像使用 Python 3.12；宿主机不需要安装 Python 3.12。

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

访问：

- 前端：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- Readiness：<http://localhost:8000/health/ready>

首次启动由 `migrate` 容器执行 Alembic 迁移。PostgreSQL 使用 `pgvector/pgvector:pg16`，API 和 Worker 共享 `uploads` volume。停止服务使用 `docker compose down`；需要删除本地数据库卷时才使用 `docker compose down -v`。

## 环境变量

`.env.example` 已逐项注释。核心配置如下：

| 配置 | 必填 | 作用 |
| --- | --- | --- |
| `DATABASE_URL` | Compose 默认值可用 | PostgreSQL 连接串，保存所有业务事实和向量 |
| `REDIS_URL` | Compose 默认值可用 | Event 唤醒和 Worker readiness；不可用时退化为数据库轮询 |
| `REDIS_ENABLED` | 否 | 是否启用 Redis 通知，单元测试设为 `false` |
| `UPLOAD_DIR` | 是 | API/Worker 共享上传目录，不能配置为公开静态目录 |
| `VECTOR_DIMENSION` | 否 | Embedding 维度，默认 384，Provider 返回维度必须一致 |
| `TASK_LEASE_TTL` / `TASK_HEARTBEAT_INTERVAL` | 否 | Worker lease 和续租周期，默认 30/10 秒 |
| `TASK_MAX_ATTEMPTS` / `TASK_RETRY_BASE_DELAY` | 否 | 有界重试次数和指数退避基数 |
| `TASK_DEADLINE` | 否 | 单任务硬截止时间，超时进入 `failed` 并记录 `TASK_DEADLINE_EXCEEDED` |
| `RAG_TOP_K` | 否 | 默认召回数量，默认 5 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 否 | 文本切分大小和重叠字符数 |
| `MOCK_PROVIDER` | 否 | 默认 `true`，不需要外部模型 Key 即可验收主流程 |
| `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME` | 使用真实 Provider 时必填 | OpenAI-compatible 生成模型配置，Secret 只注入服务端 |

Demo 默认使用 `OWNER_ID=local-user`，不提供生产认证、RBAC 或多租户隔离。

## 接口文档

正式接口前缀为 `/api/v1`。完整的请求响应、错误码、Event envelope、SSE 重连和兼容规则只维护在 [`docs/接口文档.md`](docs/接口文档.md)；该文档是前端接口说明的唯一来源。Run Event 先写 PostgreSQL，再由 SSE 投影；Redis 只负责唤醒，客户端必须按 `seq` 去重并在断线后从 `after_seq` 补放。

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

Compose 验收：

```powershell
docker compose up -d --build
docker compose ps
Invoke-WebRequest http://localhost:8000/health/ready
```

完整实施边界、对象关系、异常行为和阶段退出条件见 [`docs/adr/001-sesrag-demo-implementation-plan.md`](docs/adr/001-sesrag-demo-implementation-plan.md)；Demo 产品验收口径见 [`docs/prd/001-SesRAG-项目Demo-PRD.md`](docs/prd/001-SesRAG-项目Demo-PRD.md)；完整产品长期目标见 [`docs/prd/002-SesRAG-完整项目-PRD.md`](docs/prd/002-SesRAG-完整项目-PRD.md)。
