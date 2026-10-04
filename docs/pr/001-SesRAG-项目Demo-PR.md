# PR-001：SesRAG 项目 Demo 实施结果

**对应 PRD**：[`docs/prd/001-SesRAG-项目Demo-PRD.md`](../prd/001-SesRAG-项目Demo-PRD.md)
**对应 ADR**：[`docs/adr/001-sesrag-demo-implementation-plan.md`](../adr/001-sesrag-demo-implementation-plan.md)
**版本**：v0.1
**日期**：2026-10-05
**状态**：已实施，基本验证完成

## 1. 实施范围

已完成 Demo 的前后端分离和 Docker Compose 纵向链路：Thread/Message/Run、PostgreSQL 持久 Task、Worker lease/heartbeat/retry/优雅停机、Run Event Journal 与 SSE 投影、txt/md/docx 文档索引、pgvector 兼容存储、Mock/可选 OpenAI-compatible Provider，以及 Vue 工作台。

主要实现文件和目录包括 `backend/`、`frontend/`、`migrations/`、`contracts/`、`tests/`、`docker/`、`docker-compose.yml`、`.env.example` 和 `docs/runbooks/demo-development.md`。

## 2. 结果与差异

- PostgreSQL 保存会话、任务、事件、文档和 Chunk 事实；Redis 只负责通知和 readiness。
- Demo 使用内部 `index_batch` 和 `active_index_batch_id`，尚未提供完整项目的公开 `DocumentVersion` 审核、发布和回滚流程，符合 PRD 非目标。
- Demo 默认单 owner、Mock Provider 和本地上传卷，不包含生产认证、RBAC、多租户和工具沙箱。

## 3. 验证证据

后端单元/API/SQLite 集成测试、Ruff、mypy、前端 lint/typecheck/build、Compose 配置和健康检查，以及 Thread/Message/Run/Worker/RAG/SSE 主链路均已完成基本验证。详细命令、环境和验收矩阵见 [`docs/test/001-SesRAG-项目Demo-test.md`](../test/001-SesRAG-项目Demo-test.md)。

## 4. 未完成事项

完整项目 PRD 的 PRD1～PRD4 能力仍需按路线拆分实施；本结果不代表生产认证、可靠 MQ、工具系统或知识库版本化已经交付。
