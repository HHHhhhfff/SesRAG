# TEST-002 运行器收尾报告

- 开始日期：2026-10-21；收尾日期：2026-10-22（Asia/Shanghai）
- 范围：依据 `.superpowers/test-002-resume-brief.md`，完成运行器安全生命周期、失败路径、自测及根代理追加的 ready 分类调度、FrozenBuild 接线和受限 resource helper。
- 状态：JS 运行器及框架替身验证完成；本子任务不启动 Docker 资源，真实环境闭环由根代理统一执行。
- 未提交、推送、重置或覆盖其他代理/用户修改；未编写任何产品分类脚本，manifest 八类仍为 planned。

## 实际修改文件

原分配的六个 JS 文件：

1. `tests/sesrag-persistent-session-workspace-test/tooling/orchestrator.mjs`
2. `tests/sesrag-persistent-session-workspace-test/tooling/resources.mjs`
3. `tests/sesrag-persistent-session-workspace-test/tooling/process-registry.mjs`
4. `tests/sesrag-persistent-session-workspace-test/tooling/category-runner.mjs`
5. `tests/sesrag-persistent-session-workspace-test/tooling/report.mjs`
6. `tests/sesrag-persistent-session-workspace-test/tooling/self-tests.test.mjs`

根代理明确追加授权后还修改 `tooling/compose.mjs`，使 `waitService` 使用 `compose ps -a -q`，能够看到迁移/Profile 初始化等已退出容器。根代理在 orchestrator 中追加的 runtimeInventory import 和采证调用均已保留。其余 Compose、Python、Provider、PowerShell 入口、Schema、模块说明文件由其他代理维护。

## 生命周期与安全处理

- 先创建本轮报告目录，再进入统一 try/finally；初始化、磁盘/工具前提、Docker 前提、部署、探测或采证失败均继续清理。初始化替身失败已验证自身锁、runtime、tmp 被释放且产生失败报告。
- 使用安全 run_id、随机 owner、私有 runtime ACL、原子 session/resource ledger 和公开无凭据 recovery ledger。创建资源前先记意图；公开账本以可执行路径的 SHA-256 保存进程身份，避免公开宿主路径。
- 活跃锁核验 PID、创建身份和可执行身份；存活进程拒绝 Cleanup，未完成旧锁要求先恢复清理，不直接以新运行覆盖。
- 中断信号阻止后续创建子进程和部署。采证/清理使用独立有限预算；构建共享 1800 秒、Environment 初始化共享 300 秒，分类有单类/7200 秒总预算，采证 120 秒、清理 180 秒。
- 磁盘检查改用 Node fs.statfs，适配 Windows/Linux；浏览器路径固定 suite 缓存；子进程默认剔除开发 WS/COMPOSE/DSN/数据库/模型 Secret。
- 分开解码 stdout/stderr，使用流式 UTF-8 解码；机器 JSON 不再混入 Docker Compose stderr 进度。输出受限，超限整段舍弃以防泄漏半段 Secret，分类/Docker 都把截断判为工具错误。
- 先脱敏再写公开日志；补充已知 Linux 宿主根路径清洗并保留 HTTP 内网地址，Windows 路径清洗不吞 XML/JSON 引号。发布分类文本证据前再统一清洗。
- 进程创建身份不可读时登记 unverified PID，不静默漏账。父进程退出时使用 Windows CIM 或 Linux /proc/进程组核对子孙；发现存活子孙须登记并按身份回收，查询失败或归属不可证明则保留未知残留，不按名称或猜测 PID 杀进程。终止等待有界，失败不让管道无限挂住父入口。
- 参数/工具/协议错误使用 2，环境前提受限使用 3，捕获中断使用 130，清理失败/未知优先使用 4。产品失败 1 与未运行 3 的统计均保留；采证失败不能环境 passed/exit0。

## 资源清理与恢复

- 删除前核验 Engine/context、run_id、owner 和已登记 project；先核验候选资源，再允许 Compose down，防止错误 owner 被 Compose 按 project 提前删除。
- 分类清理使用 projectOnly，保留同轮 build project 的默认网络；最终清理才做整个 run 的标签/登记 project 扫描。
- 镜像 tag 必须严格属于本轮；已登记 ID 必须一致；构建意图中 ID 为空时只接受本轮稳定 suite/source 标签匹配的镜像，不全局 prune。
- 删除结束再独立查询容器、网络、卷和 project 残留，复核既有资源是否缺失。报告含进程、runtime、tmp、镜像 tag、既有资源和保留缓存边界。
- Docker/进程审计通过后才删除私有凭据和临时目录；失败时保留恢复账本。恢复不要求重新制造 Compose 凭据，可按已核验资源逐项清理。
- 重复 Cleanup 仍执行独立审计，不能仅相信旧 cleanup.json=passed。若原运行被强停且没有 summary，恢复报告为 mode=Cleanup、environment=incomplete、product_acceptance=not_run；不倒填环境成功。

## Environment 接线

- 真实顺序为构建专有镜像 → PG/Redis/Provider → 正式 Alembic migration → 正式 Profile 初始化 → API/Worker/前端健康 → 技术探测 → 采证 → finally 清理与独立审计。
- tools 每次显式唯一 name、run/owner 标签并记意图；Provider 协议自测只运行一次。
- Python 探测接口按已完成脚本实际支持的 `environment_probe.py --json` 调用；不传未实现的 URL 参数。
- fixture 通过正式 prepare-fixtures 参数生成并读取实际 manifest；Python 工具框架自测一次，收集 JUnit 和日志。
- PostgreSQL 专库工具自测先核验 PG 容器标签，再从该容器读取 system_identifier，调用 `db-admin.py self-test --expected-server-id ... --expected-namespace ...`。self-test 自行创建空库、检查、删除和复核；不传该模式禁止的 --database。
- Environment 的产品 passed/failed/blocked/not_run 计数为 0，产品验收固定 not_run；技术失败使用 environment_status/reason/harness_error。
- `mainRun(options, { afterBaseServices })` 可供根代理在基础服务健康后注入失败，普通命令行不提供跳过清理开关。

## 后续 ready 分类与 FrozenBuild

- All/Selected 遇到 planned 分类，在部署前退出 3 并产覆盖/摘要报告；未知/重复分类或协议错误退出 2。
- ready 分类才按登记脚本真实执行，各自全新 project、独立卷/运行上下文、fixture、顺序采证和立即清理；不会退化为运行 Environment。
- Node 调用 `node <script> --context <context.json>`；PowerShell 使用 `-ContextPath`。工作目录为 SUITE_ROOT。context 位于 `runtime/<run>/<category>/context.json`，result 默认位于 `artifacts/<run>/categories/<category>/result.json`，console.log 同目录。
- context 经过严格 Schema/身份/相对目录校验；分类结果校验 case 身份/遗漏/重复/额外 case、汇总与退出码、证据存在性/普通文件/相对路径/真实路径；拒绝历史遗留结果、路径逃逸、目录证据、符号链接和 Windows ADS。
- 分类只显式获得本轮 PROVIDER_CONTROL_TOKEN、MODEL_API_KEY、固定 PLAYWRIGHT_BROWSERS_PATH；不授予宿主开发 DSN。专库操作经受限 helper。
- resource_helper 是相对入口 `tooling/orchestrator.mjs`。CLI 使用 `--resource-helper --run-id <run> --category <category> --action <action> [--service <service>]`；支持 inspect/restart/stop/start（仅 api/worker/provider）、add-worker/remove-worker、create-probe/inspect-probe/drop-probe。核验活跃主运行、当前分类、Engine、project 和容器标签后才执行，并记录操作意图/结果及 helper 子进程。
- Selected/All 构建后从 tools 读取实际 Python/importlib.metadata 依赖并调用独立 frozen-builds 模块保存匿名镜像归档；指定 FrozenBuild 时严格载入同源/同 ID 归档，不静默重建。该模块由 Python 工具代理实现，本文件只负责接线。
- All 即使分类通过，也必须 quality_prerequisites=ready 才能宣布 product_acceptance=passed；pending/blocked 保持 incomplete/3。目前没有产品分类/质量验收脚本，运行器不会凭环境成功宣称这些前提 ready。

## 真实验证记录

关键失败路径先补最小失败用例并实际观察失败，再修正实现。已覆盖缺报告、非零伪 passed、超时、错误 case 身份/重复/遗漏、路径越界、错误 owner/Engine、初始化失败、采证失败甚至采证目录不可写、活跃运行拒绝恢复、旧 passed 无账本、晚出现残留、非法镜像账本、UTF-8 分块、开发环境隔离、进程创建身份缺失、父先退子孙仍存活、分类 scope、日志截断、质量门禁和阶段总预算。

最终执行命令：

```powershell
npm test
node --check tooling/orchestrator.mjs
```

- 最终 npm test：**73 tests，73 passed，0 failed，0 skipped，退出码 0**，总耗时约 32.2 秒；包含根代理的 Compose/入口 5 项、冻结归档 24 项、runtime inventory 3 项和本运行器 41 项。
- 语法检查：退出码 0（后续最终 npm test 又完整导入执行了所有 JS 模块）。
- 用 Node spawnSync 原生状态核验 `node tooling/orchestrator.mjs --mode All` 和 `--mode Selected --categories session`：均为 **原生退出码 3**，均生成报告，无部署。PowerShell 原生命令包装可能把非零归一为 1，因此此处特意读取原生 status。
- 这两次 CLI 记录：`ws-20261021t151523z-d0ffd05f`（All）、`ws-20261021t151523z-73b7fa83`（Selected session）；后续仅安全/门禁修复，不改变 planned 拦截逻辑。
- 全仓 `git diff --check` 当时退出 1，仅报用户既有 `docs/当前任务说明.md:32` 行尾空白；该文件不属于本子任务，未修改其内容。

## 未运行与风险

- 本子任务未执行 Docker build/up 或真实环境闭环；根代理统一执行正常两轮、半途失败、中断、强停恢复和重复 Cleanup。最终真实运行结果应以其 artifacts 为准。
- ready 串行调度已用临时框架脚本真实调用验证，不属于产品分类验收。八类仍 planned，后续产品脚本、完整需求覆盖和质量前提实际证据仍未建立。
- FrozenBuild 的 archive/tar 安全行为由其 24 项替身测试验证；真实 Engine 匿名归档兼容性及 Selected/All 完整容器路径还需真实执行证据。
- Windows 进程身份和树审计使用 CIM，存在额外延迟；身份/树不能证明时有意失败并保留恢复信息，不扩大终止范围。
- 若父进程创建身份已经缺失，发现的子孙标为 ownership_unverified；不能把只有 PID/当前创建信息的候选当作已证明归属的进程终止。此时保留未知/失败残留，可能需要人工核验后处理；已用安全反例验证不会猜杀或虚报 passed。
- `PurgeToolCache` 明确尚未实现；入口会安全拒绝并退出 2，不删除缓存，不给出缓存清空承诺。此范围偏差已通知根代理调整公开说明。
- 本报告不是产品 PRD 验收结论，也不把环境/Provider/工具框架自测计为产品通过数。
