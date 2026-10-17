# Demo 临时测试环境 Runbook

本流程只操作本次`sesrag-demo-smoke-<随机ID>`资源，不操作开发project。完整参数/文件用途见[环境README](../../tests/demo-smoke/README.md)，依据为[TEST-001](../test/001-SesRAG-项目Demo-test-plan.md)。

## 启动并自动结束

确认Docker Desktop Linux Engine运行，以PowerShell7.4+从根目录执行：

```powershell
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1
```

入口构建、等待就绪、按21分类manifest执行、收集报告、销毁资源。当前产品缺陷会failed，未满足完整条件的子项会blocked（顶层enabled分类归failed），不可改退出码强行通过。报告在artifacts/run_id，密码只在runtime且正常结束删除；脚本映射/限制和试跑证据见[任务3～4记录](../../tests/demo-smoke/任务3-4实施与审批记录.md)。

2026-10-07已复核工具与总入口，见[任务1～任务2记录](../../tests/demo-smoke/任务1-2准备与审批记录.md)。当前分类执行和中文详细摘要均需要本机Node24.15+的24.x或26+（不支持25），Python工具用项目.venv/Python3.12；产品frontend容器仍Node20。任务1～2历史记录的仅环境启动条件不能替代当前完整入口依赖。重装及工具探针见[tooling](../../tests/demo-smoke/tooling/README.md)。当前没有需要导入的全局业务SQL，Schema与空库由迁移准备；各用例经API独立创建数据。

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

ADR-002 基础阶段已修复 `migrations/env.py` 读取环境 URL，隔离环境仍保留只读测试启动适配器；若 migrate 非零不要跳过迁移门禁。当前 API ready 执行实际 PG/Redis 有界探测，入口还精确核对当前 Alembic head、vector 及 frontend 代理。ADR002已完成正式两轮，具体纳入目标及blocked见[复验报告](../../tests/demo-smoke/复测和验收报告.md)§9，严格入口仍可能非零。

DOC/RAG和LIFE会通过固定`-HarnessScenario`再次调用同一总入口，独立project/卷/owner，复用主run本次源码镜像。LIFE故意错误报告/超时仅证明运行器，不是产品passed。所有嵌套身份登记父runtime/nested-runs.json；分类异常时finally恢复，外层分类被杀后由主清理阶段按登记身份再兜底。主入口也被硬杀时仍无法finally：查父登记和各nested run_id，逐一CleanupRunId，不能只清主project就宣称全部零残留。无权威runtime标记时停止自动删除，先核对summary资源归属。

`nested-recovery`为固定LIFE兜底自检：父分类部署并保留子环境，再故意超时；父运行器必须按登记精确恢复子环境且报告`nested_recovery.cleaned=true`。它不是父入口本身硬杀的证明。总入口另生成`summary-详细.md`，逐项中文摘要不能覆盖`categories/*.json`中的failed/blocked；完整试跑后可运行`node tests/demo-smoke/tooling/check-coverage.mjs tests/demo-smoke/artifacts/<run_id>`核对记录完整性。

## 磁盘边界

ADR002 Task5d增加`process-resources.json`、`frontend-resources.json`和`execution-resources.json`恢复：主入口先核对PID出生时间/可执行文件、辅助容器精确run/project/purpose标签，再观察关闭。不要按历史裸PID执行taskkill；登记不匹配则失败并保留runtime，不猜测改closed。前端跨进程登记有5秒排他锁，异常会释放；父进程硬杀遗留锁由完整CleanupRunId随runtime精确移除，不能手动删登记继续跑。

固定故障`compose-config-failure`、`migration-failure`、`real-db-probe-failure`、`worker-readiness-timeout`、`frontend-readiness-timeout`、`redis-strict`必须阻断分类；`redis-cold`专用降级仍要求PG/head/vector/API/前端及真实Run完成，健康Worker unknown/0不被伪改ready。`cleanup-failure`/`cleanup-share-read`使用本次runtime真实None/Read共享锁；可读不代表可删除。删除前原子保存`runtime/<run_id>-recovery.json`固定白名单恢复胶囊，删除失败保留并恢复缺失材料，最后胶囊删除失败也非零；它含凭据，不得复制到artifact/日志。CleanupRunId严格校验并可恢复仅剩胶囊的情况。`hard-kill-recovery`在真实浏览器/SSE/Worker屏障后终止父runner树，随后独立CleanupRunId；硬杀没有自动finally，Windows可捕获Ctrl+C当前仍无可靠注入工具，独立保留blocked。

主入口必须由shell=false包装记录实际child close码与summary一致（硬杀没有summary应明确记录）。LIFE机器可读逐项预算15000秒含特殊nested-recovery420及失败finally，21分类合计59070秒；独立QLT21600包括缺报告时真实调用17220秒依赖分类上限，普通all已有完整分类时QLT消费本run报告。默认部署/常规主清理额外3600秒的分解见工具README；最坏16个遗留nested恢复再加3840秒，默认包装59070+7440=66510秒，自定义build/wait/session增加差额。此为有限操作/工程预留，不声称覆盖无上限资源数或磁盘阻塞；具体冻结预算由最终验收负责人设置，不使用无限wait。

每次容器写层、容器日志、PG/uploads/Redis匿名卷及运行tmp/runtime都应释放，本次唯一镜像tag也应消失。共享基础镜像、BuildKit缓存、Playwright安装和默认保留的脱敏artifact不是本次业务数据残留；长期由用户按需要管理这些缓存/报告，不自动全局删除。Docker虚拟磁盘文件未立即变小不能单独判残留，先核对Docker资源和项目目录证据。
