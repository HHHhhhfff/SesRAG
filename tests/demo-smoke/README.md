# Demo 本机隔离临时测试环境

本目录实施[TEST-001](../../docs/test/001-SesRAG-项目Demo-test-plan.md)的环境基础设施。已具备部署→就绪/后续分类执行→报告→销毁→残留检查闭环；当前7类产品测试都未接入，正常运行返回`not_ready/3`，这不是环境失败，也不是产品验收通过。

## 前提与运行

需要PowerShell **7.4+**（用`pwsh`，不使用Windows PowerShell 5.1）、Docker Desktop Linux Engine及支持`!override`的Compose **2.24.4+**。初次构建需能下载Python/Node依赖；默认Mock无外部Key。Node 20+仅安装/使用浏览器工具时需要。

从仓库根目录执行：

```powershell
pwsh -NoProfile -File tests/demo-smoke/self-tests.ps1
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1
# 手工检查：显示本次地址，就绪后等待输入；按Enter报告并自动销毁。
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Interactive
```

总入口在任意当前目录调用都能定位仓库；输出实际API/frontend地址、run_id和报告位置。默认不长期保留环境。正式验收不可启用KeepContainers；用例尚未完成时不要将exit3改写为0。

| 参数 | 默认 | 作用/安全边界 |
| --- | --- | --- |
| ProjectName | sesrag-demo-smoke | project前缀，可加安全小写后缀；入口总会追加本次随机ID，拒绝接管已有资源。与方案建议的完整名称覆盖不同，此约束保证隔离。 |
| ApiPort / FrontendPort | 18000 / 15173 | 首选端口；占用或重复自动替换，只绑定127.0.0.1。 |
| Build | true | 默认构建本次镜像；false必须显式传BackendImage和FrontendImage，均为已有本地镜像，不自动复用开发镜像。复用不保证代码最新，只用于诊断。 |
| Category | all | 所有manifest项或一个名称；子集通过不等于完整PRD通过。 |
| WaitTimeoutSeconds | 180 | up和健康等待共享总限时，不含构建。 |
| BuildTimeoutSeconds | 900 | 独立构建限时，首次网络安装可能较慢。 |
| SessionSeconds | 0 | 就绪后有界暂停供外部检查，不执行产品断言。 |
| Interactive | false | 就绪后等Enter；硬杀进程需恢复清理。 |
| KeepArtifacts | true | 默认保留报告；显式`-KeepArtifacts:$false`表示接受删除本次报告，清理失败时仍保留。 |
| KeepContainers | false | 仅诊断保留，返回cleanup_deferred/5，保留runtime/tmp，必须后续CleanupRunId。 |
| CleanupRunId | 无 | 用本次runtime标记精确恢复清理；原summary先另存，不重新启动。 |

可复制`compose/.env.demo-smoke.example`为`.env.demo-smoke.local`修改4个整数选项；命令行参数优先。不读取根.env作为测试配置。

| 配置/运行变量 | 必填与默认 | 用途 |
| --- | --- | --- |
| SMOKE_API_PORT / SMOKE_FRONTEND_PORT | 模板可选，18000/15173 | 首选端口，最终值写runtime；按输出地址访问。 |
| SMOKE_WAIT_TIMEOUT_SECONDS | 模板可选，180 | 启动/健康总等待秒数，10～3600。 |
| SMOKE_BUILD_TIMEOUT_SECONDS | 模板可选，900 | 构建秒数，30～7200。 |
| SMOKE_PROJECT | 运行必需，入口生成 | 唯一project及本次镜像前缀，不指向开发project。 |
| SMOKE_OWNER_ID | 运行必需，入口生成 | 本次独立owner，不是生产认证。 |
| SMOKE_DB_PASSWORD | 运行必需，入口随机生成 | 临时DB密码，仅runtime/compose.env保存，不提交Git、不写默认报告。 |
| VITE_API_BASE_URL | 覆盖固定为空 | 已有Vite代理统一HTTP/SSE来源；不关闭CORS、不修复根Compose跨域问题。 |
| WORKER_ID | 覆盖由project生成 | 单测试Worker唯一身份；多Worker分类需另准备不同ID。 |

MOCK_PROVIDER=true、默认384维、AUTO_CREATE_SCHEMA=false固定；api/worker/migrate共用后端镜像。migrate只读挂载`run-migrations.py`，将DATABASE_URL注入既有Alembic配置；原迁移入口忽略环境变量的产品缺口仍保留。

## 文件与使用阶段

| 文件/目录 | 职责 | 阶段 |
| --- | --- | --- |
| run-demo-smoke.ps1 | 唯一生命周期入口、调度和报告/清理 | 每次运行 |
| lib/smoke-common.ps1 | 路径安全、脱敏、有界子进程、端口及fixture准备 | 预检/执行/清理 |
| self-tests.ps1 | 运行器辅助机制自检，不是产品分类 | 改运行器后 |
| compose/docker-compose.demo-smoke.yml | 根Compose上的端口/owner/密码/image/log覆盖 | 部署 |
| compose/.env.demo-smoke.example | 非Secret配置模板 | 配置前 |
| compose/run-migrations.py | 测试Alembic启动适配，不替换迁移 | migrate |
| specific_test_script/ | manifest、报告Schema和接入协议；目前无具体脚本 | 接入/执行 |
| test-plan.md | 分类实施次序、前提及退出条件 | 编写用例前 |
| fixtures/ | 文本、docx XML源、事件期望；运行时生成docx | 数据准备 |
| package.json / package-lock.json | 独立Playwright依赖锁定 | 工具安装 |
| runtime/<run_id>/ | context.json/compose.env/resources.json，含临时凭据 | 运行中，正常结束删除 |
| tmp/<run_id>/ | 生成fixture/后续大文件 | 运行中，正常结束删除 |
| artifacts/<run_id>/ | summary/cleanup/manifest、分类JSON、编排/健康/服务日志 | 默认保留脱敏证据 |
| .cache/ / node_modules/ | 项目内浏览器和npm工具缓存，不是每次运行数据 | 长期复用 |
| 测试点设计与需求覆盖矩阵.md | 原子目标/覆盖，可测状态为设计基线 | 用例设计/校审 |

运行目录、依赖、缓存和本地配置由.gitignore/.dockerignore排除；报告不发送到构建上下文。fixture和分类规范见子目录README；实际记录见[环境验证记录](../../docs/test/001-SesRAG-Demo-临时测试环境验证记录.md)。

## Playwright工具

已在本目录独立安装playwright 1.63.0及Chromium，未更改frontend依赖，未编写产品浏览器用例。重装时：

```powershell
npm ci --prefix tests/demo-smoke --cache tests/demo-smoke/.cache/npm
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'tests/demo-smoke/.cache/ms-playwright'
node tests/demo-smoke/node_modules/playwright/cli.js install chromium
```

分类Node脚本可import playwright，入口设置项目内浏览器路径。系统npm缓存不可写时仍用上面的项目缓存，不修改全局配置。

## 状态与报告

退出码：0 passed（选中分类真实通过且清理成功）；1 failed；2 blocked；3 not_ready；4 cleanup_failed；5 cleanup_deferred。空/未接入分类不能passed，清理失败高于测试失败；summary分别保留test_status和cleanup_status。

报告含summary.json/md、manifest.json、categories/、environment/（脱敏Compose config/ps/up/down/health/实际DB探测）和logs/（构建、6服务最近2000行）。按run_id保留，恢复清理前另存旧summary。报告收集失败不能passed。未接入分类明确not_ready及空checks，不伪造测试结果。

## 清理与磁盘保留

正常结束/可捕获异常进入finally：终止分类子进程→收集证据→`down --volumes --remove-orphans`→检查project标签容器/网络/卷及捕获的匿名卷→删本次唯一image tag→删本次tmp/runtime。路径解析和link检查防止删除仓库根、开发数据或其他项目。

清理失败时尽可能删tmp、保留最小runtime凭据以便重试，不报告无残留。诊断保留或硬杀进程后：

```powershell
pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -CleanupRunId <输出的run_id>
```

不执行global prune。删除容器释放写层/容器日志，删PG/uploads/Redis匿名卷释放业务数据；本次image tag删除后，共享基础镜像和BuildKit缓存仍可能占空间，这是有意复用缓存，不代表Docker虚拟磁盘物理文件立即缩小。

artifact默认保留。容器日志上限10MiB×2且随容器删除，报告只截末尾；长期仍需人工按run_id管理报告。不要对runtime/artifacts根目录笼统递归删除；不再需要的精确报告目录可移至回收站。Playwright浏览器约数百MiB及node_modules长期供后续测试使用，不计作每次环境残留。

## 已知边界

基础健康和DB探测不证明PRD全通过。lease/retry/deadline/前端恢复等业务缺口未修复；慢Provider、屏障、双owner和具体分类用例仍待准备。硬终止/关机无法执行finally，必须恢复清理；runtime也丢失时按记录project标签只读定位残留，再人工确认精确资源，禁止全局清理。
