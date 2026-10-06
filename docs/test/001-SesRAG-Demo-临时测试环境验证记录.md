# TEST-ENV-001：Demo 临时测试环境实施与验证记录

**编号**：001

**版本**：v0.1

**日期**：2026-10-06

**状态**：环境基础设施已实施并验证；产品分类脚本未接入，非产品验收结果

**对应 PRD/ADR**：[Demo PRD](../prd/001-SesRAG-项目Demo-PRD.md)、[ADR-001](../adr/001-sesrag-demo-implementation-plan.md)

**依据**：[TEST-001 v0.2](001-SesRAG-项目Demo-test-plan.md)、[测试点矩阵](../../tests/demo-smoke/测试点设计与需求覆盖矩阵.md)

## 1. 范围与环境

本次准备TEST-001阶段1～4所需文件：隔离Compose配置、总入口、接入manifest/Schema/规范、数据准备、报告及清理闭环。没有编写具体产品测试用例或分类脚本，也没有修复backend/frontend/migrations业务代码。

代码分支`sesrag_v0.1`，HEAD `0d7a61cac477874562beed2a58b9f7bdb66e5f72`；工作区保留此前已暂存文档，当前基础设施文件未提交。报告同时记录git_dirty和入口/覆盖文件SHA256，commit不代表未提交代码已经属于提交。

本机Windows、PowerShell7.6.5、Docker Engine29.4.0、Compose5.1.1；容器使用Python3.12/Node20、PostgreSQL16+pgvector、Redis7、固定Mock/单独owner及新卷。本次Docker daemon可用，与测试点设计时的环境阻塞记录不同。

## 2. 文件变动和额外调整

| 变动 | 内容及理由 |
| --- | --- |
| 新增环境入口/辅助 | `tests/demo-smoke/run-demo-smoke.ps1`、`lib/smoke-common.ps1`：参数、端口、随机密码/project、部署、等待、分类进程、报告、销毁和残留检查。 |
| 新增基础设施自检 | `self-tests.ps1`：路径防逃逸/根删除拒绝、脱敏、退出状态优先级、fixture可重复、报告Schema、子进程/超时、端口冲突；不是产品分类脚本。 |
| 新增隔离配置 | `compose/docker-compose.demo-smoke.yml`及`.env.demo-smoke.example`：替换端口、运行密码/owner/image/log，API/frontend仅loopback，不发布DB/Redis。 |
| 新增迁移启动适配 | `compose/run-migrations.py`只读挂载进migrate，将环境URL注入正式Alembic Config，仍跑既有迁移；原因见第4节。 |
| 新增分类接入资源 | `specific_test_script/README.md`、`manifest.json`、`category-result.schema.json`；7类not_implemented，后续脚本按同参数和Schema接入。 |
| 新增接入计划 | `tests/demo-smoke/test-plan.md`：按服务/会话/Worker/文档/SSE/前端/故障顺序接入，E2/E4/双owner前提单列。 |
| 新增fixture | txt/md、docx XML、无害非法后缀文本和event-types；docx生成在tmp，不提交二进制或大文件。 |
| 新增工具依赖 | 本目录package.json/package-lock.json锁定Playwright1.63.0；npm缓存和Chromium/FFmpeg/工具安装在本目录.cache/，没有改前端依赖。 |
| 修改忽略规则 | 根.gitignore/.dockerignore排除runtime/artifacts/tmp、node_modules/.cache和本地测试配置，避免凭据入Git/构建上下文。 |
| 修改/新增导航文档 | 根README、tests/demo-smoke/README、TEST-001实施细化、测试点历史基线备注；新增Runbook及本记录，保持已暂存内容，不更改原PR调研历史。 |

相对原方案的细化：ProjectName为安全前缀+随机ID；runtime改run_id目录；独立构建超时；前端使用合法同源Vite代理；诊断保留新增退出5；清理失败保留最小恢复凭据；额外清理本次镜像tag并核对匿名卷。不是反转事实来源/API/状态机，因此在原测试方案第13节记录，不新增业务ADR。

## 3. 实际执行与证据

原始报告保存在Git忽略的`tests/demo-smoke/artifacts/<run_id>/`，包含summary/cleanup/manifest、分类结果、Compose/健康/实际DB探测及服务日志。下表只表示基础设施执行结果，不是191个产品测试点执行结果。

| 验证 | 命令/方式 | run_id与实际结果 |
| --- | --- | --- |
| 运行器自检 | `pwsh -NoProfile -File tests/demo-smoke/self-tests.ps1` | 通过；运行器实现前观察到缺helper失败，实施后重复通过。 |
| 首次启动失败也清理 | 总入口默认构建 | `20261006t101632-c207e315`：migrate因密码来源不一致失败；报告failed/1，cleanup passed，资源全部回收。 |
| 迁移适配后完整闭环 | 总入口默认构建，SessionSeconds40 | `20261006t101955-8c1ef653`：startup/report/cleanup passed；全7类not_ready、总exit3，无残留。 |
| 浏览器与合法代理 | 总入口SessionSeconds120；一次性Playwright环境探测 | `20261006t102245-aa019d3f`：页面200、main可见、代理health200、pageerror为空，browser-probe.json保存；之后自动销毁。没有提交浏览器分类脚本。 |
| 端口占用/诊断/恢复 | 宿主listener占18000，两个首选端口都18000，启用KeepContainers；随后CleanupRunId | `20261006t102742-eaa47e17`：选择51766/51767，startup passed，保留时cleanup_deferred/5；恢复清理后无残留。此前summary另存，当前summary为not_ready/3和cleanup passed。 |
| docx生成有效 | 同run的生成fixture，用python-docx读取 | 三段中文和SESRAG-SMOKE-DOCX-001读取正确；固定ZIP时间使两次生成hash相同，自检覆盖。 |
| 就绪后异常仍清理 | 总入口`-Category no-such-category` | `20261006t104034-3082bb6d`：启动成功后识别非法分类，failed/1，完整报告及cleanup passed。 |
| 默认7类报告/Schema闭环 | 总入口默认构建 | `20261006t104349-92e35a35`、`20261006t104619-eb349597`及最终校审后的`20261006t105329-52befffd`：startup/report/cleanup passed，exit3；7份not_ready分类JSON全部满足Schema，checks为空且不伪报passed。最终入口也保存清理前的health-final快照。 |
| Docker不可达分支 | 仅子命令临时DOCKER_HOST指向不存在的pipe，结束恢复；不停止真实Docker | `20261006t104612-e32a4c3b`：blocked/2，runtime/tmp清除，没有创建容器。 |
| 外部残留核对 | docker ps/network ls/volume ls/image ls精确筛选sesrag-demo-smoke前缀；检查runtime/tmp | 完成本轮运行后均无本次资源；原sesrag、mall4j、ragflow等既有停止容器仍保留，未全局删除。 |
| 文档/脚本静态校审 | PowerShell AST解析、Markdown链接存在性、改动范围git diff --check、Git忽略核对 | 无脚本语法错误、无断链、无空白格式错误；分类目录具体ps1/mjs脚本数为0，运行目录/依赖/缓存均被忽略。 |

执行报告timestamps使用UTC；本文日期按本机用户时区。由于分类未接入，完整测试报告表示“这些分类未执行”的真实结果，不虚构checks或PRD通过。入口自检和环境探测不替代质量门禁或产品恢复/并发用例。

## 4. 审批中发现的问题与处理

1. 随机测试密码首次启动失败。日志确认migrate仍用alembic.ini固定密码；migrations/env.py没有使用环境URL。已加测试启动适配器注入URL，重复验证成功，产品迁移入口未修改，缺口仍需后续开发处理。
2. 根Compose前端HTTP绝对base与相对SSE不同源。隔离覆盖将base置空，经既有Vite代理同源，真实Chromium安全设置下检查通过。不是给API加CORS，也不声称根开发Compose问题已解决。
3. Redis镜像可创建匿名卷。入口inspect本次容器挂载，保存卷身份并在down后核对；不只检查Compose命名卷。所有本次匿名卷已删除。
4. 如果每run使用唯一镜像tag但不清理，会随run增长。入口删除自己的backend/frontend tag，不删其他项目tag，不做全局prune；共享层/BuildKit缓存有意保留。
5. 空manifest或未接入分类不能passed。入口输出not_ready/3，报告Schema不允许空checks的passed，清理失败优先返回4；诊断保留明确5。
6. shell变量可盖过env-file，端口合并可能保留开发端口。入口显式向Docker子进程传本次SMOKE值，覆盖用!override，解析配置核对仅一个loopback端口，资源必须归属本次project。
7. 系统npm缓存路径不可写。改用项目.cache/npm，没有更改全局npm配置或申请管理员权限；浏览器路径同样固定项目内。

## 5. 清理边界、未验证项与结论

已验证正常/启动失败/就绪后异常/端口冲突/诊断恢复的清理，报告确认本次容器、网络、PG/uploads/匿名卷、临时image tag、runtime/tmp无残留。删除的是本轮专用临时数据，不影响用户开发数据；临时卷数据随销毁不可恢复，脱敏报告保留。

基础镜像、BuildKit缓存、Playwright浏览器和npm/node依赖继续保留；默认artifact也保留，长期须按run_id管理，不承诺占用零空间或Docker虚拟磁盘立即压缩。未执行全局prune。

尚未验证/实施：具体分类脚本、完整PRD验收、慢Provider/步骤屏障、双owner、E4协议替身、交互中Ctrl+C/硬杀/断电实测、真实Docker删除权限失败分支、启用分类的全进程调度验证、Build=false复用路径；状态优先级/子进程超时有自检，但这些不替代上述动态故障。后续接入时按计划补验，不能写成通过。

**整体审批结论**：方案阶段1～4所需环境文件、说明、后续接入约定和计划已准备，真实Docker环境已跑通部署—报告—销毁—无残留闭环；可供后续用例和分类脚本接入。本轮未做产品验收，7类保持not_implemented，正常总入口返回not_ready/3。所有原有修改保留，未自动提交/推送。
