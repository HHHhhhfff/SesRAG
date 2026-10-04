# Demo 本地开发 Runbook

## 启动

```powershell
Copy-Item .env.example .env
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
- 文档失败：查看 Document 的 `last_error_code` 和 Worker 日志，不要把基础设施错误当成“无相关资料”。

## 停止

```powershell
docker compose down
```

只在明确需要清空本地 PostgreSQL 数据时使用 `docker compose down -v`。

