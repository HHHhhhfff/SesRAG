# TEST-001：SesRAG 项目 Demo 测试验收记录

**对应 PRD**：[`docs/prd/001-SesRAG-项目Demo-PRD.md`](../prd/001-SesRAG-项目Demo-PRD.md)
**对应 ADR**：[`docs/adr/001-sesrag-demo-implementation-plan.md`](../adr/001-sesrag-demo-implementation-plan.md)
**版本**：v0.1
**日期**：2026-10-05
**状态**：基本验收完成

## 1. 验收范围

覆盖 Thread/Message/Run 持久化、幂等、Event Journal 与 SSE 补放、Task lease/generation/heartbeat/retry/取消/优雅停机、文档解析/切分/Embedding/召回、引用、前端恢复和 Compose 启动健康检查。

## 2. 测试环境与命令

测试基于仓库当前代码、Python 后端测试环境、Node.js 前端依赖和 Docker Compose 本地服务；默认使用单 owner、Mock Provider 和本地上传卷。

```powershell
python -m pytest -q
ruff check .
ruff format --check .
mypy backend
cd frontend
npm run lint
npm run typecheck
npm run build
cd ..
docker compose config
docker compose up -d --build
docker compose ps
Invoke-WebRequest http://localhost:8000/health/ready
```

## 3. 已执行检查

| 检查 | 结果 |
| --- | --- |
| 后端 pytest | 通过，16 项测试通过 |
| Ruff check/format | 通过 |
| mypy backend | 通过，46 个后端源文件 |
| 前端 lint、typecheck、build | 通过 |
| `docker compose config`、迁移和服务健康检查 | 通过 |
| Thread/Message/Run/Worker/RAG/SSE/Worker 重启主链路 | 通过 |

## 4. 验收结论与限制

Demo 的基本验收目标已达到。测试使用 Demo 的单 owner、Mock Provider 和本地 Compose 配置；未将这些结果解释为生产性能、安全、多租户隔离或完整 RAG 效果证明。后续 PRD 实施需为新增状态机、工具调用、持久会话恢复和 Document Version 发布流程补充独立测试矩阵。
