# 后端集成验证

`conftest.py` 提供文档测试独立 SQLite 和上传目录。`test_document_boundaries.py` 覆盖上传清理、Parser错误结算与事务外Embedding；`test_rag_review_fixes.py` 覆盖空白兼容、双故障收尾、巨大整数以及解析进程取消/spawn/output/ZIP边界。

`test_provider_http.py` 使用仅绑定127.0.0.1的临时 HTTP/SSE 服务，验证三片流、跨Task迭代、安全分型、响应头及body总预算，fixture负责关闭，无生产测试路由。

`rag_pg_probe.py` 在控制者指定的全新 `sesrag_rag_*` 数据库升级正式迁移并测试并发索引复用、慢Embedding无长事务、候选失败保留旧active、提交屏障回滚、最终发布锁与flush跨租约/截止、位置回退保留。只通过应用/队列推进事实；测试时钟与Session屏障位于测试中，不写SQL伪造状态。该脚本不创建/删除数据库或Docker资源。

`test_worker_flow.py`、`test_document_flow.py`、`test_lease_recovery.py` 验证完整应用/Worker流程。`test_execution_integrity.py` 覆盖执行租约、重试/截止结算、取消、Worker关停/恢复、安全日志与旧版快照恢复；SQLite仅用于单进程事务/状态验证，不证明 PostgreSQL 并发锁。

`execution_pg_probe.py` 使用显式 `DATABASE_URL` 指向新建隔离 PostgreSQL 数据库，先执行正式 Alembic，再以真实多连接测试幂等提交、竞争领取、旧代数拒绝、重试到期、取消/成功交错、Journal序号与回滚、等待锁期间租约过期。必须只使用专属测试库；脚本不删除数据库，也不修改业务状态 SQL。

```powershell
.venv/Scripts/python.exe -m pytest tests/integration -q
# 已在安全运行环境注入 DATABASE_URL 后：
.venv/Scripts/python.exe tests/integration/execution_pg_probe.py
```

容器运行当前工作区时，必须同时只读挂载仓库、指定工作目录并设置 `PYTHONPATH=/work`，防止镜像内旧代码覆盖当前模块。运行证据与精确清理命令见 Task 2 阶段报告。

`test_v2_run_execution.py` 实际运行 v2 创建/Queue/Worker/Context/Journal/终态事务；覆盖历史与分支隔离、实际选择的引用、真实本地 HTTP ModelRequest、取消确认/回收、每尝试计划、独立定时 flush、冻结资源额度、无效空流和最终 flush 跨授权回滚。SQLite 用于状态与事务回归，不证明 PostgreSQL 行锁。

`session_pg_probe.py` 必须使用操作者新建的空库 `sesrag_session_probe_*`，且仅从显式 `SESSION_PG_PROBE_URL` 读取连接；拒绝非空库及其他命名空间，不创建/删除库或修改开发数据库。它先运行正式迁移，再用独立连接、Asyncio Barrier 和 `pg_blocking_pids` 等待图验证取消/成功两种锁序、并发幂等/不同 Branch 创建、来源 Task 无反锁、旧代数拒绝、最终 flush 跨授权回滚和取消优先回收。时间边界使用测试时钟，锁竞争使用真实 PostgreSQL；保留测试库便于审计，清理由操作者显式执行。

```powershell
# 安全注入专属空库 SESSION_PG_PROBE_URL 后，在仓库根目录运行：
.venv/Scripts/python.exe -m tests.integration.session_pg_probe
```
