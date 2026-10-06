# Demo 临时测试环境 Runbook

本流程只操作本次`sesrag-demo-smoke-<随机ID>`资源，不操作开发project。完整参数/文件用途见[环境README](../../tests/demo-smoke/README.md)，依据为[TEST-001](../test/001-SesRAG-项目Demo-test-plan.md)。

## 启动并自动结束

确认Docker Desktop Linux Engine运行，以PowerShell7.4+从根目录执行：

```powershell
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1
```

入口构建、等待就绪、处理manifest、收集报告、销毁资源。当前7类未接入，exit3/not_ready属于预期；检查summary的startup、report_collection及cleanup均passed，而不是改退出码强行通过。报告在artifacts/run_id，密码只在runtime且正常结束删除。

## 手工操作窗口

```powershell
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Interactive
```

按输出的实际端口访问API/frontend，记录操作和证据；测试结束回终端按Enter，入口自动报告及回收。不要依赖固定首选端口，冲突会换端口。人工观察不会自动转成产品passed。

## 故障/诊断后清理

1. 查`artifacts/<run_id>/summary.json`、`logs/`和`cleanup.json`，区分启动/业务/报告/清理失败。
2. 启动失败一般已经finally销毁；确认cleanup残留数组为空及runtime/tmp删除，不重复清开发资源。
3. 显式KeepContainers、可捕获中断清理失败、终端硬杀或关机后，有runtime凭据时执行：

   ```powershell
   pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -CleanupRunId <run_id>
   ```

4. 恢复清理不启动容器，按标记和run_id核对project，原summary另存。仍exit3表示分类未执行，重点看cleanup是否passed。
5. 若runtime丢失，先只读按summary中的精确project查询：`docker ps -a --filter label=com.docker.compose.project=<project>`及对应network/volume查询；人工核对目标后再按该project恢复清理，禁止global prune。

当前已知产品迁移入口不读取环境URL，隔离环境用只读启动适配器注入配置；若migrate非零不要跳过迁移门禁。API ready固定数据库字段不足以证明依赖，入口额外检查PostgreSQL实际Schema/vector及frontend代理。

## 磁盘边界

每次容器写层、容器日志、PG/uploads/Redis匿名卷及运行tmp/runtime都应释放，本次唯一镜像tag也应消失。共享基础镜像、BuildKit缓存、Playwright安装和默认保留的脱敏artifact不是本次业务数据残留；长期由用户按需要管理这些缓存/报告，不自动全局删除。Docker虚拟磁盘文件未立即变小不能单独判残留，先核对Docker资源和项目目录证据。
