# Demo 本地开发 Runbook

## 启动

```powershell
Copy-Item .env.example .env
# 必须替换 .env 的 POSTGRES_PASSWORD 和 DATABASE_URL 占位值；密码须 URL 编码。
docker compose up -d --build
docker compose ps
```

确认 `migrate` 已退出码 0，`api` 和 `worker` 正常运行，再打开前端。API 访问 `http://localhost:8000/docs`，前端访问 `http://localhost:5173`。

## 主流程验收

1. 创建 Thread。
2. 上传 `.txt`、`.md` 或 `.docx`。
3. 等待文档状态变为 `indexed`。
4. 在 Thread 中发送问题，观察 Run 状态、Event 时间线和 citations。
5. 刷新页面，确认 Message、Run 和文档状态从服务端恢复。
6. 执行 `docker compose restart worker`，确认未完成 Task 在 lease 到期后可以重新领取。

## 故障检查

- `api` 失败：查看 `docker compose logs api`，检查迁移和 `DATABASE_URL`。
- `worker` 不领取：查看 `docker compose logs worker`，检查 PostgreSQL 连接、Task 状态和 lease。
- Redis 不可用：系统仍应使用 PostgreSQL 轮询；SSE 延迟增加但任务事实不能丢失。
- `/health/live` 只表示 API 进程存活；`/health/ready` 实际探测 PG/Redis，PG 故障返回 503 和 `DATABASE_UNAVAILABLE`，Redis 不可用返回 degraded，Worker 无可见心跳返回 unknown，不能据此宣称 Worker 已停止。
- 文档失败：查看 Document 的 `last_error_code` 和 Worker 日志，不要把基础设施错误当成“无相关资料”。

## 停止

```powershell
docker compose down
```

只在明确需要清空本地 PostgreSQL 数据时使用 `docker compose down -v`。

## 数据库升级和安全回退

先备份已有库，并在维护窗口停止业务写入；使用同一份运行时 `DATABASE_URL` 执行迁移，不打印完整 DSN。`0001_initial_demo` 为固定历史定义，后续变化由新的 revision 实施。`0002_demo_integrity` 会检测幂等消息重复、同 Run 多 assistant、Task 目标关联冲突；发现冲突即中止，不删事实，需根据备份和业务身份人工诊断后再次升级。

降级到 `0001_initial_demo` 只撤销新约束，保留 Message/Document 来源列并允许旧调用方省略；再次升级只补齐空来源。非空库降到 `base` 会被拒绝，不能把卸载初始迁移用作业务回滚。开发卷删除属于另行明确的数据清空操作，不是本次迁移自动步骤。

## 持久执行故障诊断

- 以 `task_id` 及适用的 `run_id`（Run任务）或 `document_id`（索引任务）关联 Worker JSON 日志，核对 `worker_id/generation/attempt/error_code` 和 claim、renew、retry、release、success、failure 动作；另一业务关联为空合法。旧代数的 reject 不代表新执行者失败；不要手工修改 state/generation 来“解锁”。
- `retry_waiting` 是退避期；到期仅 Task 回 queued，Run 保持 retry_waiting，重新开始才回 running。超过硬截止或耗尽尝试会统一结算业务对象，查看 `TASK_DEADLINE_EXCEEDED` / `TASK_ATTEMPTS_EXHAUSTED`。
- 关停 Worker 先停止领取，当前任务在 `WORKER_SHUTDOWN_GRACE` 内完成或释放；容器停止超时应大于应用宽限期，不能把 Docker 强杀当作优雅完成。
- 控制面 DB 阶段最多 5 秒，超宽限后释放最多 1 秒，每轮取消清理 0.5 秒。释放超时会停止续租并记录 `RELEASE_TIMEOUT_OR_UNAVAILABLE`，租约到期后由正常回收器处理；观察此拒绝不能写成成功释放。数据库取消回滚和真正 Linux SIGTERM 需要分别验证，不以调用停止方法代替进程信号验收。
- 升级后的旧 Mock Run 按旧快照协议恢复；`INVALID_RUN_SNAPSHOT` 表示冻结配置无法安全恢复。保留原事实并定位创建时配置，不能使用当前模型默认值替换旧快照。
- DB 暂断恢复无需手工重启 Worker；验证时必须观察同进程安全错误、退避和恢复后新任务执行，不能只看 Docker restart policy 或容器状态。

