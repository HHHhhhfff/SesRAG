# CASE-001：SesRAG 项目 Demo 测试用例

**编号**：001

**版本**：v0.2

**日期**：2026-10-07

**状态**：任务5两轮正式all已执行、结果已回填；产品验收不通过，受限子项未完成

**适用范围**：本机 Docker Compose 隔离环境中的 Demo 需求验收、实现差异复现，以及后续分类脚本设计

**代码基线**：`sesrag_v0.1`，`e40b1055abe8e4263817ff12dda881a7c158c26b`。此提交新增了测试环境基础设施，业务代码仍为 `0d7a61c` 的实现；本轮不修复代码。实际执行时须记录运行时 commit 和工作区是否有修改。

**后续工具更新（2026-10-07）**：任务1～任务2已另行准备项目Python3.12开发环境及独立ESLint/Vitest/Ajv/组件工具，并复核总入口，见[准备与审批记录](任务1-2准备与审批记录.md)。本文件用例目标和可验证层级统计保持；QLT_007所述通用工具缺口已解除，但正式产品门禁/分类脚本未接入，E2/E4/O/C条件仍待准备。工具探针/环境验证不回填本文件实际结果，仍不是任务5正式执行。

**后续脚本更新（2026-10-07）**：任务3～4已按本文件目标接入21分类和局部/受限子项，开展真实Docker试跑并校审，见[实施与审批记录](任务3-4实施与审批记录.md)及[脚本映射](README.md#分类脚本与用例映射)。下文“脚本尚未接入”、环境条件统计和卡片状态为设计时历史基线，不能继续据此判断当前脚本是否存在；正确预期不因产品失败而改写。这是任务3～4的历史记录；任务5～6已完成下列正式结果登记。

**依据**：

- [Demo PRD](../../docs/prd/001-SesRAG-项目Demo-PRD.md)、[ADR-001](../../docs/adr/001-sesrag-demo-implementation-plan.md)：需求与正确预期；不是以当前错误行为作为通过标准。
- [测试点及需求覆盖矩阵](测试点设计与需求覆盖矩阵.md)：191 个测试点、需求来源与代码依据。
- [实施结果调研](../../docs/pr/001-SesRAG-项目Demo-PR.md)、[接口文档](../../docs/接口文档.md)：实现与正式接口核对。
- [正式测试方案](../../docs/test/001-SesRAG-项目Demo-test-plan.md)、[环境 README](README.md)、[环境验证记录](../../docs/test/001-SesRAG-Demo-临时测试环境验证记录.md)。
- [分类接入协议](specific_test_script/README.md)、[接入计划](test-plan.md)、[Fixture 说明](fixtures/README.md)。

## 1. 设计范围和使用方式

本文件保留测试用例设计并附任务5正式执行结果，不交付分类脚本或产品修复，也不宣布产品验收通过。共设计 **149 个用例**，逐项关联全部 **191 个测试点**；既覆盖可验证部分，也保留额外标记的局部/待补用例。第 5 节给出逐测试点反向映射；PRD 的需求覆盖关系继续以测试点矩阵第 5 节为真源，通过本文件映射落到用例，不复制第二套需求定义。

采用场景合并和参数化控制数量：同一幂等作用域、三格式正常解析、同一错误协议族可以在一个用例中列数据子项，但每个关联目标必须独立断言；不同取消步骤、租约竞态、前后端事实投影不会因名称相似而合并成笼统的“运行正常”。跨用例不继承执行结果；每个用例自行准备数据，能复用 fixture/准备函数而非依赖其他用例先通过。

任务5实际结果见卡片：149项均填写“实际测试结果”；104项可验证/部分用例补复现与稳定性，45项暂不可完整动态用例按要求仅填实际结果，后两栏保留空。正式证据为第一轮`20261007t072506-2fc5b075`、第二轮`20261007t075158-2907bbdf`，同一dirty工作区164个产品/脚本/契约/锁/fixture文件冻结哈希不变；HEAD仍为上述提交。两轮结果按子项判断，不因记录齐全宣布全面通过。详见[测试报告](测试报告.md)、[缺陷报告](缺陷报告.md)及[执行审批记录](任务5-6执行与审批记录.md)。测试流程和预期保持设计目标，未执行分支没有制造复现命令。

## 2. 可验证状态、环境条件和判定

### 2.1 设计时状态基线与本轮衔接

本节统计及卡片“目前未接入”的自动化说明保留设计阶段基线，不作为当前脚本交付状态。设计时7类占位`not_implemented`已在任务3改为21分类enabled，本轮两次全部调用；隔离Compose、总入口、报告/清理、Playwright/Chromium已准备，不能再用“入口/浏览器未交付”解释受限。当前未完成条件以卡片实际结果及缺陷报告为准。**脚本记录存在不等于完整目标已验证，设计时未编写脚本也不等于功能原本不可在本机验证。**

| 本文件状态 | 含义 | 用例数量 |
| --- | --- | --- |
| 可验证·本机动态 | 当前 API/UI/工具入口和本机条件足以进行所述动态核对，设计的自动化尚未接入；已知差异可能使预期失败。 | 53 |
| 可验证·本机静态 | 当前可审查代码、配置、依赖和契约；架构判断需人工，静态通过不等于动态正确。 | 9 |
| 部分可验证·子项有明确限制 | 已有正常/静态/局部入口，但完整字段、状态、故障分支、配置驱动或实现不足；逐子项分开记录。 | 42 |
| 暂不可完整动态验证 | 完整时序/协议/隔离场景需要当前尚未准备的条件或实现；用例仍写明输入、流程、正确预期和解锁条件。 | 45 |

上表只统计用例设计状态，不是执行状态。标记“可验证”不表示通过，标记“待补”也不等于已证明产品失败。即使缺少机制，仍可做静态缺失确认；不能把缺失机制的完整动态验收写成通过。

### 2.2 环境和数据公共约定

| 条件 | 当前可用范围或需补内容 |
| --- | --- |
| E0 | 仓库源码、契约、配置及现有质量工具。纯函数/现有单测可在本机调用；静态审查不启动产品容器。 |
| E1 | 已实施的 `run-demo-smoke.ps1`：独立随机 project/owner/密码/端口、临时 PG/Redis/uploads 卷，固定 Mock/384 维，真实 PostgreSQL，合法 Vite 同源代理。Docker daemon 须可用；入口正常未接入分类仍返回 not_ready/3。 |
| E2 | 待补慢 Embedding/模型、逐片输出、步骤/事务屏障、受控时钟/提交故障及双 Worker 驱动。须基于真实生产函数和临时 PG，不直接改事实状态伪造成功，不用固定 sleep 碰竞态。 |
| E3 | Playwright/Chromium 已在本目录安装，正常浏览器安全策略可用；分类脚本/特定网络或投影交错驱动尚未编写。普通页面验证不再因安装工具缺失阻塞。 |
| E4 | 待补本机隔离 OpenAI-compatible HTTP 替身，覆盖超时/HTTP 状态/畸形 JSON/流协议。默认 Mock 不能证明真实协议，不访问外部服务或使用真实 Key。 |
| O | 待补同一临时 PG 的 A/B owner 应用配置及各自执行者。身份仍来自服务端配置，不新增生产登录/RBAC；保证检索任务由相应 owner Worker 处理。 |
| C | 特殊配置/环境故障覆盖或函数驱动：当前环境模板仅有 4 个整数选项，不能直接用它配置 deadline/top_k/非 Mock/维度等。所需覆盖必须在测试目录独立准备并纳入资源清理，不悄悄修改根配置。 |

所有 E1 用例默认：先确认服务真正就绪；只使用输出的 BaseUrl/FrontendUrl；经正式 HTTP/SSE 操作；只读查询本次容器内 PG 补足 API 未公开的 lease/generation/snapshot/Chunk/约束等证据；不发布 PG/Redis 宿主端口。不同 Worker 显式不同 ID，不能由这个前提反推默认 ID 生成已修复。

数据用本次 FixtureDir 中的 safe txt/md/生成 docx。新边界、损坏、表格、XSS、哨兵和大文件只在 `tmp/<run_id>/` 按需生成；没有真实个人资料/凭据，不进入 Git 或默认原文报告。安全文件名、symlink、源文件移动等操作须先验证精确目标属于本次临时资源，不读取真实敏感文件，不填满本机磁盘/内存。

动态用例失败/阻塞也须进入总入口报告和清理。分类关闭自己的 SSE、浏览器、HTTP 客户端和子进程；只有总入口销毁环境。运行器专项的临时 manifest/故障替身目前没有独立接入参数，不能擅自把正式七分类改为伪产品脚本；先扩展明确隔离的自检驱动再执行这些子项。

### 2.3 子项判定、优先级与结果协议

- P0：持久事实、唯一身份、终态、租约、取消、索引隔离、安全和验收关键路径；P1：主要交互、诊断、配置与性能；P2：补充架构/非目标边界。
- 功能预期以 PRD/ADR 为准。能复现代码不符合需求就记 failed，不因“已知问题”自动 skipped/passed；未满足前置条件记 blocked，未接脚本记 not_ready。
- 参数化组合逐项报告，任何必测子项失败则该用例不能整体 passed；局部可验证与待补条件分别给结论，不把部分通过包装成全覆盖。
- 当前运行器对 enabled 分类，只有整体 passed 协议满足才判 passed，子项 blocked/skipped/not_ready 或报告无效均使该分类归为 failed；具体子项原因保留在分类原报告。启动前环境不足的顶层 blocked/2 与此不同。
- 联合用例在分类 Schema 中仍需为每个测试点写独立 check：`id=<用例ID>__<测试点ID>__<子项>`，`test_point_id` 为单个 TP ID，附自然语言 expected/actual 和 evidence。不能把多个 TP ID 塞进该单值字段；每个 ID 必须能回溯用例卡片和子项。
- 记录状态码、正文摘要、关联 thread/run/task/document、generation/attempt/seq、UTC 时间和脱敏证据。故障/并发还需步骤屏障与事务提交顺序；不得只写“表现正常”。
- 同用例混合静态/动态时分别报告；SQLite 不证明真实 PG 锁或 pgvector。索引失败核对 Document/Task，不虚构索引 Run 的 run.failed。
- 正式产品分类成功与清理成功分开：passed/0、failed/1、blocked/2、not_ready/3；cleanup_failed/4、cleanup_deferred/5 不可正式验收通过。共享缓存/artifacts 有意保留不等于业务残留。
- 重试 Run 采用 ADR 的 retry_waiting→running，Task 必须回 queued 再领取；本文件不新增另一套状态兼容。纯空白输入、docx 非段落区域、终态空后缀连接等补充观察项按用例注明的性质登记，不擅自上升为新的 P0 产品承诺。

## 3. 后续实施路线和证据边界

1. 优先接入当前 E1 主路径：部署/迁移/会话事实/正常索引检索/事件补放/queued 取消，再接入 E3 页面与安全清洗；代码差异如实失败。
2. 独立补 E2/O/C 驱动并明确生命周期、配置来源、调用权限和退出清理约定后，再实施租约/终态/索引事务/截止/停机/前端异步竞争用例。驱动不得变成生产测试后门。
3. 再补 E4 本地协议替身；静态缺口确认与真实 HTTP 动态证据分别记录，不依赖真实 Key。
4. 架构/质量和运行器专项独立校审；QLT 系列检查是否有实际门禁覆盖，不能凭本用例文档宣布自动化交付。LIFE 系列是测试基础设施验收，不计成新产品能力。
5. 各类脚本完成后依[分类协议](specific_test_script/README.md)接入 manifest；最终 all 完整运行并复核第 5 节全部必测子项及清理报告。任何未执行、失败、blocked 或 not_ready 的必要目标都不能被平均覆盖率掩盖。

### 3.1 当前环境实现的定位入口

LIFE用例使用当前实现而非旧测试点中的待实施路径；以下路径均相对本目录。

| 目标 | 实现文件与职责 |
| --- | --- |
| 生命周期/就绪/分类/证据/清理 | [run-demo-smoke.ps1](run-demo-smoke.ps1)的Wait-Environment、Collect-Evidence、Cleanup-Environment及主流程。 |
| 路径/端口/子进程/脱敏/退出码 | [smoke-common.ps1](lib/smoke-common.ps1)的Get-SmokeChildPath、Remove-SmokeChild、Get-SmokePort、Invoke-SmokeProcess、Protect-SmokeText、Get-SmokeOutcome；[self-tests.ps1](self-tests.ps1)为辅助机制自检。 |
| 部署与迁移覆盖 | [测试Compose](compose/docker-compose.demo-smoke.yml)、[迁移适配](compose/run-migrations.py)，不替代根Compose或生产迁移。 |
| 分类调度及报告 | [manifest](specific_test_script/manifest.json)、[分类报告Schema](specific_test_script/category-result.schema.json)；目前没有产品分类脚本。 |

## 4. 用例卡片

卡片中的代码简称、方法和文件全路径来自测试点矩阵第 3.1 节；它们用于后续定位实现，实际编脚本时必须再次核对当前提交。以下前置条件均继承第 2 节，单独写出的故障/配置驱动未准备时不能假装已有开关。

### 4.1 部署、迁移、配置与健康

主归属：service-health（故障证据复用于 fault-safety）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### DEP_001：全新隔离部署和首次迁移

- 用例编号：`DEP_001`
- 对应测试点：`TP-DEP-001`：全新编排服务拓扑；`TP-DEP-002`：首次迁移结果
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；新 run_id、空卷，未复用镜像
- 测试数据要求：当前源码镜像、默认384维、无模型Key
- 测试流程：启动完整编排；观察六服务状态和 migrate 退出；只读查 Alembic版本、扩展及表。
- 预期结果：frontend/api/worker/postgres/redis 就绪，migrate 退出0；Alembic=head，vector扩展及threads/messages/runs/run_events/tasks/documents/chunks七表存在；没有用宿主机业务进程替代容器。
- 优先级：P0
- 用例类型：运维/契约
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Compose：services；两个 Dockerfile；迁移：upgrade；ORM；migrations/env.py
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-DEP-001__topology`：通过，输出："[6项，明细见证据]"；`TP-DEP-002__schema`：通过，输出：{"version":[{"version_num":"0001_initial_demo"}],"tables":"[8项，明细见证据]"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_002：重复迁移保留既有事实

- 用例编号：`DEP_002`
- 对应测试点：`TP-DEP-003`：已完成迁移重复执行
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例自建Thread、已索引Document并记下ID
- 测试数据要求：一条已完成问答和三格式中任一文档
- 测试流程：对同一临时库再次执行生产迁移的 upgrade head；比较迁移前后记录及约束。
- 预期结果：迁移不报重复表错误；版本仍为head；Thread/Message/Run/Event/Document/Chunk的ID、内容、计数和约束均不改变。
- 优先级：P1
- 用例类型：恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：迁移；Compose：migrate.command
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-DEP-003__repeat-migration`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","document_id":"[关联ID见证据]","repeat":"不变"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_003：迁移失败阻断API和Worker

- 用例编号：`DEP_003`
- 对应测试点：`TP-DEP-004`：迁移失败阻断业务启动
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；需测试专用失败迁移覆盖，环境方案已有失败验证记录但当前无可选故障参数
- 测试数据要求：仅本次migrate的安全非零退出，不能破坏真实迁移文件
- 测试流程：让本次migrate确定性失败；观察依赖服务是否启动业务和分类是否运行；收集报告后清理。
- 预期结果：migrate非零、API/Worker不能进入处理状态；分类被阻断，报告保存安全错误及退出码；仍进入清理，不能伪报环境就绪。
- 优先级：P0
- 用例类型：异常/运维
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Compose：service_completed_successfully
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-DEP-004__declared-migration-gate`：通过，输出：{"root":{"api":"service_completed_successfully","worker":"service_completed_successfully"},"merged":{"api":"service_completed_successfully","worker":"service_completed_successfully"},"scope":"静态依赖声明；不代表首次迁移故障已实测"}；`TP-DEP-004__full-scenario`：受限未执行，输出：首次迁移失败独立驱动尚未完成；已有静态依赖声明不等于动态失败阻断/清理验收。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### DEP_004：API与Worker共享上传及重启存储

- 用例编号：`DEP_004`
- 对应测试点：`TP-DEP-005`：上传卷共享
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；正常上传卷和Worker
- 测试数据要求：smoke.txt，另含中文标识的文档
- 测试流程：API上传后等待Worker索引；重启API/Worker但不删除卷；只读比对storage_key对应文件与Chunk。
- 预期结果：Worker读取的是API保存的同一原始字节；索引完成，重启后文件/hash/Document/Chunk均保留，不依赖单进程临时目录。
- 优先级：P0
- 用例类型：功能/恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Compose：uploads；Storage.save/read；Index Handler
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-DEP-005__shared-restart`：通过，输出：{"document_id":"[关联ID见证据]","hash":"07ec155ad96b4c14a4fb5fa53ffc31ea628e5b1f1d9ff15be5307f77e34fde19","chunk_ids":["[关联ID见证据]"],"restart":"持久事实不变"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_005：Secret运行时注入与构建边界

- 用例编号：`DEP_005`
- 对应测试点：`TP-DEP-006`：Secret 配置注入边界
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；读根与测试Compose、模板、Dockerfile和前端构建路径
- 测试数据要求：数据库密码/模型Key字段名称及非真实哨兵，禁止输出真实值
- 测试流程：追踪Secret从配置到API/Worker，检查镜像COPY/ARG/ENV及前端变量；分别记录根部署和测试覆盖。
- 预期结果：Secret只由运行环境供后端使用，不提交、不烘焙、不进前端；逐字段明确哪些未透传或写死。测试随机密码覆盖不能消除根Compose硬编码差异。
- 优先级：P0
- 用例类型：安全/配置
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：Compose：environment；Dockerfile；Settings；.env.example
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-DEP-006__root-secret-review`：失败，输出：根Compose数据库密码/连接串仍为固定字面值；不是运行时Secret注入。原因：类型1（已测/审查确认）：根Compose凭据为固定字面值；隔离覆盖随机密码没有改变根部署。 定位：`docker-compose.yml:7/29/40/65（各服务environment）`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_006：调度参数非法值拒绝

- 用例编号：`DEP_006`
- 对应测试点：`TP-DEP-007`：调度参数有效性
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；核查Settings及Runtime消费；动态需独立配置驱动
- 测试数据要求：TTL/heartbeat/attempt/deadline分别0、负值；heartbeat等于或大于TTL；有效TTL30/heartbeat10
- 测试流程：逐组追踪配置校验与使用；有效组合核对续租周期；记录拒绝层及安全诊断。
- 预期结果：有效正值可用；非法组合在启动或使用前明确拒绝，不能零周期运行或接受无效队列。当前Settings缺校验应记设计差异，不以构造成功为通过。
- 优先级：P1
- 用例类型：边界/配置
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：Settings 字段；Runtime._lease_heartbeat；Queue
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-DEP-007__invalid-settings`：失败，输出：Settings接受无效周期/期限/次数组合。原因：类型1（已测/审查确认）：配置没有正值与heartbeat<TTL组合校验，真实Settings驱动接受非法组合。 定位：`backend/config.py:18 Settings；backend/workers/runtime.py:138 _lease_heartbeat`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_007：向量维度配置与真实PG一致

- 用例编号：`DEP_007`
- 对应测试点：`TP-DEP-008`：运行向量维度与数据库一致
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；同时审查迁移/ORM/Settings；完整PG动态需专用配置覆盖
- 测试数据要求：dimension=384及128；Mock输出同配置长度
- 测试流程：比较Embedding输出、设置和PG Vector列定义；识别非默认配置拒绝或匹配迁移是否存在。
- 预期结果：384三者一致；128须明确拒绝或存在匹配Schema，不能无声写入固定384列；SQLite JSON通过不证明PG支持非默认维度。
- 优先级：P0
- 用例类型：边界/契约
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：ORM：EmbeddingType.load_dialect_impl 固定 Vector(384)；Settings
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-DEP-008__vector-config`：失败，输出：Settings接受128，数据库固定384且无启动拒绝。原因：类型1（已测/审查确认）：配置接受128维而真实PG列固定Vector(384)，无启动一致性检查。 定位：`backend/config.py:17 Settings.vector_dimension；backend/db/models.py:34 EmbeddingType.load_dialect_impl`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_007__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_008：数据库实际约束完整性

- 用例编号：`DEP_008`
- 对应测试点：`TP-DEP-009`：迁移约束与模型一致
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；已迁移全新PG；只读系统目录
- 测试数据要求：外键、Message/Event/Chunk seq唯一、Run.user_message_id唯一、幂等复合唯一、Task kind关联检查清单
- 测试流程：从pg_catalog读取实际约束并与ORM和ADR逐项对比，不执行破坏性SQL。
- 预期结果：外键及声明的唯一性保护真实存在；ADR约定的(thread_id,idempotency_key)和Task kind关联CHECK不能遗漏。当前缺失应报告失败/差异；约束审查不替代并发功能用例。
- 优先级：P0
- 用例类型：契约
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：迁移upgrade；ORM.__table_args__/mapped_column；ADR §6.1
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-DEP-009__constraints`：失败，输出：用例规定约束缺失/不完整 + actual - expected + [ + 'messages(thread_id,idempotency_key) unique', + 'tasks kind/run_id/document_id CHECK语义不完整' + ] - [] 。原因：类型1（已测/审查确认）：真实PG缺Message(thread_id,idempotency_key)唯一与Task kind/关联对象互斥CHECK。 定位：`backend/db/models.py:56 MessageModel.__table_args__、:91 TaskModel；migrations/versions/0001_initial_demo.py:14 upgrade`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_008__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DEP_009：Redis不可达时冷启动降级

- 用例编号：`DEP_009`
- 对应测试点：`TP-DEP-010`：Redis冷启动降级边界
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；需仅本次Compose的Redis失败启动覆盖
- 测试数据要求：Redis冷启动不可达，PG正常
- 测试流程：在首次业务启动前令Redis不可达；核对API/Worker启动、ready及DB链路；恢复并清理。
- 预期结果：按ADR通知故障应降级，不阻断PG权威业务；不得丢事实。根Compose Redis healthy依赖阻断启动是当前差异；此项不同于运行后重启Redis。
- 优先级：P1
- 用例类型：异常/恢复
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Compose：api/worker depends_on.redis；Notifier.connect；ADR §3.2/5.7
- 实际测试结果：不通过；第一轮通过0/失败1/受限1，第二轮通过0/失败1/受限1。子项记录：`TP-DEP-010__cold-start-dependency-review`：失败，输出：根编排仍硬依赖Redis healthy，冷启动无法执行通知降级；`TP-DEP-010__full-scenario`：受限未执行，输出：冷启动Redis不可达场景需独立Compose覆盖，不能以运行后停Redis代替；静态冲突已单独实际解析，完整冷启动动态待补。。原因：类型1（已测/审查确认）：根编排硬要求Redis healthy，与应用允许通知降级矛盾；仅确认声明冲突，冷启动故障未实测。 定位：`docker-compose.yml:50/75 depends_on.redis；backend/infrastructure/events/redis_notifier.py:14 connect`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/dep.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/dep.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category dep`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-dep.log`及`categories/dep.json`，按`DEP_009__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### HLT_001：live只表示API进程存活

- 用例编号：`HLT_001`
- 对应测试点：`TP-HLT-001`：API 存活语义
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；正常及本次PG停机两个分支
- 测试数据要求：/health/live；安全响应扫描
- 测试流程：请求live；停止本次PG但保留API进程再请求；恢复PG。
- 预期结果：两分支API仍存活时live为200/status=ok，无凭据；结果不能作为DB/Worker就绪证明。
- 优先级：P1
- 用例类型：功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：health.py：live
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-HLT-001__normal`：通过，输出：{"status":200,"headers":{"date":"Wed, 07 Oct 2026 07:52:35 GMT","server":"uvicorn"}}；`TP-HLT-001__pg-down`：通过，输出：{"status":200,"headers":{"date":"Wed, 07 Oct 2026 07:52:35 GMT","server":"uvicorn"}}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/hlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/hlt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category hlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-hlt.log`及`categories/hlt.json`，按`HLT_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### HLT_002：PG故障下ready与业务错误

- 用例编号：`HLT_002`
- 对应测试点：`TP-HLT-002`：数据库就绪真实性；`TP-WK-027`：DB中断API错误语义
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；记录故障前事实，精确停止本次PG
- 测试数据要求：ready、创建Thread、读取已有Thread
- 测试流程：确认PG已不可达后分别请求ready与业务；比对HTTP/正文及无新事实；恢复。
- 预期结果：ready不再声明database=ready，明确硬依赖未就绪；业务返回稳定503及安全错误，不能成功/无证据或泄漏堆栈。当前固定ready及未映射DB异常分别记失败。
- 优先级：P0
- 用例类型：异常/安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：health.py：ready；App.state.engine；App.exception_handler；应用服务DB调用
- 实际测试结果：不通过；第一轮通过1/失败3/受限0，第二轮通过1/失败3/受限0。子项记录：`TP-HLT-002__ready`：失败，输出：ready固定宣告database=ready；`TP-WK-027__create`：失败，输出：未映射依赖故障，实际HTTP 500 500 !== 503 ；`TP-WK-027__read`：失败，输出：未映射依赖故障，实际HTTP 500 500 !== 503 ；`TP-WK-027__no-phantom-facts`：通过，输出：{"thread_count_unchanged":true,"original_thread_id":"[关联ID见证据]"}。原因：类型1（已测/审查确认）：真实停PG仍返回database=ready；数据库异常未映射为稳定503，业务创建/读取返回500。 定位：`backend/api/routes/health.py:12 ready；backend/app.py:37 application_error_handler`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/hlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/hlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category hlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-hlt.log`及`categories/hlt.json`，按`HLT_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### HLT_003：运行后Redis故障不丢事实

- 用例编号：`HLT_003`
- 对应测试点：`TP-HLT-003`：Redis 降级真实性；`TP-HLT-006`：Redis 重启事实恢复；`TP-SSE-005`：Redis不可用仍补放
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；API/Worker已启动，有历史Run；本用例准备新问答
- 测试数据要求：正常Redis、断连、恢复三阶段
- 测试流程：停止本次Redis；读ready及历史；提交新问题并读取SSE；重启Redis再比较事件/状态。
- 预期结果：断连时redis明确degraded而非旧client假ready；DB历史/新任务仍可处理，SSE完整补放、终态不丢。Redis恢复不新建业务身份；允许通知降级和轮询延迟。
- 优先级：P0
- 用例类型：恢复/异常
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Notifier.connect/ready_worker_count；health.py：ready；Queue；Notifier.publish_run；runs.py：stream_events；runs.py：generator/del notifier；Notifier
- 实际测试结果：不通过；第一轮通过3/失败1/受限0，第二轮通过3/失败1/受限0。子项记录：`TP-HLT-003__ready`：失败，输出：client非null导致假ready + actual - expected + 'ready' - 'degraded' ；`TP-HLT-006__facts`：通过，输出：{"old_thread":"[关联ID见证据]","new_thread":"[关联ID见证据]","run_id":"[关联ID见证据]","status":"succeeded"}；`TP-SSE-005__redis-down-replay`：通过，输出：{"run_id":"[关联ID见证据]","event_seqs":"[7项，明细见证据]"}；`TP-HLT-006__redis-restart-compare`：通过，输出：{"run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","events":7,"persistent_facts_unchanged":true}。原因：类型1（已测/审查确认）：健康判断使用client非null而非实际连通性；停Redis仍ready。 定位：`backend/api/routes/health.py:12 ready；backend/infrastructure/events/redis_notifier.py:34 ready_worker_count`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/hlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/hlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category hlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-hlt.log`及`categories/hlt.json`，按`HLT_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### HLT_004：长任务期间Worker readiness不误离线

- 用例编号：`HLT_004`
- 对应测试点：`TP-HLT-004`：Worker readiness 连续性
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补慢Provider，不是缺浏览器或Docker
- 测试数据要求：任务持续超过readiness TTL，lease正常续租
- 测试流程：保持可控任务活跃，跨TTL多次读取ready、Redis readiness与Task lease；任务结束复查。
- 预期结果：活跃Worker持续ready且计数准确；不能只在每轮开始刷新后任TTL过期；readiness与任务lease两个心跳分开判定。
- 优先级：P1
- 用例类型：边界/运维
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime.heartbeat/run_forever；Notifier.ready_worker_count
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-HLT-004__full-scenario`：受限未执行，输出：长任务超过readiness TTL的Provider/lease屏障未准备；普通短Mock任务不能证明长任务readiness连续性。。静态风险（非本用例动态失败）：readiness仅循环头刷新，stop停止租约心跳，当前handler没有真实grace有界等待。 定位：`backend/workers/runtime.py:136/191/203`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/hlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/hlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### HLT_005：API重启恢复全部持久事实

- 用例编号：`HLT_005`
- 对应测试点：`TP-HLT-005`：API 重启事实恢复
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；用例自身创建已完成会话和已索引文档
- 测试数据要求：记录Thread/Message/Run/Task/Event/Document/Chunk ID及摘要
- 测试流程：重启本次API；重新读取正式API和必要只读DB信息；比较重启前后。
- 预期结果：全部已提交ID、正文、seq、引用和状态一致；API不创建替代身份；Redis/前端缓存不是恢复来源。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：App.lifespan；Run服务读取函数；ORM；Compose卷
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-HLT-005__restart`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","document_id":"[关联ID见证据]","persistent":"全部不变"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/hlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/hlt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category hlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-hlt.log`及`categories/hlt.json`，按`HLT_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

### 4.2 会话、消息和Run事实

主归属：thread-run-api。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### TH_001：创建、列表排序和会话详情

- 用例编号：`TH_001`
- 对应测试点：`TP-TH-001`：创建会话身份；`TP-TH-003`：列表更新时间倒序；`TP-TH-004`：会话详情事实排序
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例独立创建A、B两Thread
- 测试数据要求：默认标题及显式中文标题；给先创建的A再追加消息
- 测试流程：创建并记录返回；更新A；读列表与A/B详情，按服务端时间和seq比较。
- 预期结果：创建201、UUID/owner/时间完整；默认新会话；更新后的列表按updated_at倒序（同时间不强制次序）；messages按seq升序、runs按创建倒序且不混Thread。
- 优先级：P0
- 用例类型：功能/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：create_thread；ThreadCreate/ThreadSummary；ThreadModel；会话服务：list_threads/create_message_run；Run服务：get_thread_detail
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-TH-001__identity`：通过，输出：{"thread_ids":["[关联ID见证据]","[关联ID见证据]"],"owner_matches":true}；`TP-TH-003__updated_order`：通过，输出：{"ordered_thread_ids":"[6项，明细见证据]","updated_a":"2026-10-07T07:53:20.636048Z"}；`TP-TH-004__detail_order`：通过，输出：{"thread_id":"[关联ID见证据]","message_seqs":[1,2,3,4],"run_ids":["[关联ID见证据]","[关联ID见证据]"]}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/th.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/th.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category th`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-th.log`及`categories/th.json`，按`TH_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### TH_002：标题长度与strip边界

- 用例编号：`TH_002`
- 对应测试点：`TP-TH-002`：标题长度校验
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；每个数据项独立提交
- 测试数据要求：空串、1/200/201字符、前后空格、全空白
- 测试流程：逐项创建并记录状态、保存标题及是否产生Thread。
- 预期结果：空串/201字符422无记录，1/200接受，标题按strip归一；全空白按补充质量建议单列观察空标题风险，不擅自认定已确认的P0拒绝规则。
- 优先级：P1
- 用例类型：边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：ThreadCreate；会话服务：create_thread
- 实际测试结果：已执行子项通过；第一轮通过6/失败0/受限0，第二轮通过6/失败0/受限0。子项记录：`TP-TH-002__empty`：通过，输出：{"input_length":0,"http_status":422,"thread_delta":0}；`TP-TH-002__one`：通过，输出：{"input_length":1,"http_status":201,"thread_delta":1,"saved_length":1}；`TP-TH-002__two_hundred`：通过，输出：{"input_length":200,"http_status":201,"thread_delta":1,"saved_length":200}；`TP-TH-002__two_hundred_one`：通过，输出：{"input_length":201,"http_status":422,"thread_delta":0}；`TP-TH-002__strip`：通过，输出：{"input_length":8,"http_status":201,"thread_delta":1,"saved_length":4}；`TP-TH-002__whitespace_observation`：通过，输出：{"input_length":3,"http_status":201,"thread_delta":1,"saved_length":0,"observation":"全空白存为空标题，仅质量观察"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/th.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/th.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category th`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-th.log`及`categories/th.json`，按`TH_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### TH_003：归档保留事实历史

- 用例编号：`TH_003`
- 对应测试点：`TP-TH-005`：归档保留历史
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；自建已成功问答的Thread
- 测试数据要求：归档前Thread、Message、Run、Event摘要
- 测试流程：归档后读取列表/详情/事件，比较archived_at及历史。
- 预期结果：archived_at有值，原历史不删改；不将隐藏归档列表或禁发问题作为PRD未要求的通过条件。
- 优先级：P1
- 用例类型：功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：archive_thread；threads.py：post_archive
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-TH-005__archive_preserves`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","archived_at":"2026-10-07T07:53:26.925154Z","history_preserved":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/th.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/th.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category th`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-th.log`及`categories/th.json`，按`TH_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### TH_004：不存在Thread拒绝且无副作用

- 用例编号：`TH_004`
- 对应测试点：`TP-TH-006`：缺失会话错误
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；生成从未创建的UUID
- 测试数据要求：详情、归档、发送三操作
- 测试流程：分别请求；只读核对该ID没有新增Thread/Message/Run/Task。
- 预期结果：均404/THREAD_NOT_FOUND，无隐式建会话或消息执行链，错误无内部路径。
- 优先级：P1
- 用例类型：异常/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：get_thread；Run服务：get_thread_detail
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-TH-006__detail`：通过，输出：{"missing_thread_id":"[关联ID见证据]","operation":"detail","http_status":404,"error_code":"THREAD_NOT_FOUND","facts_added":0}；`TP-TH-006__archive`：通过，输出：{"missing_thread_id":"[关联ID见证据]","operation":"archive","http_status":404,"error_code":"THREAD_NOT_FOUND","facts_added":0}；`TP-TH-006__message`：通过，输出：{"missing_thread_id":"[关联ID见证据]","operation":"message","http_status":404,"error_code":"THREAD_NOT_FOUND","facts_added":0}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/th.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/th.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category th`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-th.log`及`categories/th.json`，按`TH_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### OWN_001：双owner会话、文档与执行访问隔离

- 用例编号：`OWN_001`
- 对应测试点：`TP-TH-007`：owner列表隔离；`TP-TH-008`：owner对象访问拒绝；`TP-RUN-008`：Run对象访问隔离；`TP-DOC-009`：文档列表与owner；`TP-DOC-012`：index对象访问拒绝；`TP-RAG-002`：owner召回隔离；`TP-SSE-008`：SSE握手前对象校验
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+O；待补同一临时PG的双配置API及各自Worker；A/B数据经应用创建
- 测试数据要求：A/B各一Thread/已索引Document/成功Run，含独特标记
- 测试流程：A/B各查列表和召回；A访问B的详情/归档/消息/Run/events/SSE/cancel/index；反向重复；比对副作用。
- 预期结果：列表/证据只含本owner；跨owner读写和SSE握手均404、不暴露存在性，无状态/Event/Task副作用；Run/Document/召回逐项断言。不是生产认证或RBAC验收。
- 优先级：P0
- 用例类型：权限/安全
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：会话服务：list_threads；Settings.owner_id；会话服务：get_thread；Run服务：get_thread_detail；Run服务：load_run/get_run_events/cancel_run；文档服务：list_documents；DocumentResponse；文档服务：create_index_task owner校验；Vector.search_chunks：owner_id；Run Handler：settings.owner_id；runs.py：stream_events；Run服务：get_run_events
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限15，第二轮通过0/失败0/受限15。子项记录：`TP-TH-007__a_list`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-TH-007__b_list`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-TH-008__detail`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-TH-008__archive`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-TH-008__message`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-RUN-008__detail`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-RUN-008__events`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-RUN-008__cancel`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-DOC-009__a_list`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-DOC-009__b_list`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-DOC-012__index`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-RAG-002__a_retrieval`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-RAG-002__b_retrieval`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-SSE-008__a_to_b`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner；`TP-SSE-008__b_to_a`：受限未执行，输出：O条件尚未准备：需要同一临时PG的A/B配置API及各自owner Worker；服务端身份来自Settings.owner_id，当前单API不能模拟双owner。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/own.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/own.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### MSG_001：用户Message持久字段与公开契约

- 用例编号：`MSG_001`
- 对应测试点：`TP-MSG-001`：用户消息持久字段
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；Worker先停，避免快速终态干扰
- 测试数据要求：含中文换行的正文和唯一幂等Key
- 测试流程：创建后读Thread详情及Message/Run DB；核对每个字段与PRD，区分DB字段和API公开字段。
- 预期结果：user/completed、原正文、Thread/Run关联、正seq和创建时间持久一致；时间及来源语义须有明确契约。当前DB有created_at但API缺时间/独立来源，局部通过不能验收完整公开事实。
- 优先级：P0
- 用例类型：功能/契约
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：MessageModel；会话服务：create_message_run；MessageResponse
- 实际测试结果：不通过；第一轮通过1/失败2/受限0，第二轮通过1/失败2/受限0。子项记录：`TP-MSG-001__persistent_fields`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","thread_id":"[关联ID见证据]","seq":1,"role":"user","status":"completed","created_at":"2026-10-07T07:53:31.611334+00:00"}；`TP-MSG-001__public_time`：失败，输出：Message 详情缺少公开 created_at；`TP-MSG-001__public_source`：失败，输出：Message 详情缺少独立来源 source 契约。原因：类型1（已测/审查确认）：Message公开投影缺created_at及独立来源语义；DB时间存在。source字段名是用例约定，PRD未固定此拼写。 定位：`backend/api/schemas/threads.py:32 MessageResponse；backend/application/runs.py:100 get_thread_detail`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### MSG_002：正文长度校验不产生执行副作用

- 用例编号：`MSG_002`
- 对应测试点：`TP-MSG-002`：消息正文长度限制
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；停Worker，记录各请求前计数
- 测试数据要求：空串、1/20000/20001字符、纯空白（API直接提交）
- 测试流程：逐项提交；检查HTTP和对应Message/Run/Task/Event计数。
- 预期结果：空串和20001为422且不建执行链；1与20000可接受。纯空白当前可接受单列质量观察，不能擅自将前端trim等同API拒绝需求。
- 优先级：P1
- 用例类型：边界/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：MessageCreate；threads.py：post_message
- 实际测试结果：已执行子项通过；第一轮通过5/失败0/受限0，第二轮通过5/失败0/受限0。子项记录：`TP-MSG-002__empty`：通过，输出：{"thread_id":"[关联ID见证据]","input_length":0,"http_status":422,"counts":{"runs":0,"tasks":0,"events":0}}；`TP-MSG-002__one`：通过，输出：{"thread_id":"[关联ID见证据]","input_length":1,"http_status":201,"counts":{"runs":1,"tasks":1,"events":2}}；`TP-MSG-002__twenty_thousand`：通过，输出：{"thread_id":"[关联ID见证据]","input_length":20000,"http_status":201,"counts":{"runs":1,"tasks":1,"events":2}}；`TP-MSG-002__twenty_thousand_one`：通过，输出：{"thread_id":"[关联ID见证据]","input_length":20001,"http_status":422,"counts":{"runs":0,"tasks":0,"events":0}}；`TP-MSG-002__whitespace_observation`：通过，输出：{"thread_id":"[关联ID见证据]","input_length":3,"http_status":201,"counts":{"runs":1,"tasks":1,"events":2},"observation":"全空白API接受，仅质量观察"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### MSG_003：连续问题和最终Message序号与关联

- 用例编号：`MSG_003`
- 对应测试点：`TP-MSG-003`：连续消息序号；`TP-MSG-008`：最终assistant关联与内容
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；一Thread逐个等待Run完成；另建对照Thread
- 测试数据要求：两条不同问题，Markdown证据文本
- 测试流程：逐条提交并完成；读全部Message、Run、Event，比较seq、游标和最终文本。
- 预期结果：同Thread用户/assistant seq严格递增且唯一，其他Thread独立；每个assistant为completed，run_id及assistant_message_id互相对应，正文等于该Run生成增量的strip拼接，Markdown原文保留。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：create_message_run；Run Handler；uq_messages_thread_seq；Run Handler：answer_parts/assistant；MessageModel
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-MSG-003__sequence_scope`：通过，输出：{"thread_id":"[关联ID见证据]","seqs":[1,2,3,4],"control_seqs":[1,2]}；`TP-MSG-008__assistant_content_and_links`：通过，输出：{"run_ids":["[关联ID见证据]","[关联ID见证据]"],"assistant_message_ids":["[关联ID见证据]","[关联ID见证据]"],"markdown_preserved":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### MSG_004：并发不同问题各获唯一消息序号

- 用例编号：`MSG_004`
- 对应测试点：`TP-MSG-004`：不同消息并发序号
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；真实PG，停Worker以排除最终回写竞争
- 测试数据要求：同Thread两个不同Key/正文
- 测试流程：并行提交两个请求；读取事实计数、seq和游标。
- 预期结果：两用户Message、两Run和两Task均成功持久化，用户seq不重复，无误复用Key；Thread游标一致。不同于assistant回写竞争。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：session.refresh(with_for_update=True)
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-MSG-004__different_keys_concurrent`：通过，输出：{"thread_id":"[关联ID见证据]","results":[{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"},{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"}],"seqs":[1,2]}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### MSG_005：顺序幂等和作用域

- 用例编号：`MSG_005`
- 对应测试点：`TP-MSG-005`：顺序重复幂等键；`TP-MSG-007`：幂等作用域
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；独立Thread A/B；停Worker
- 测试数据要求：A同Key重复/改变正文；A不同Key；B同Key；A无Key两次
- 测试流程：逐项提交并比较状态码、返回ID及初始事件计数。
- 预期结果：A首次201、同Key重复200且ID不变、一组初始事实；当前同Key不同正文复用原结果，不要求未约定409。A不同Key/B同Key/无Key每次均独立，不能跨Thread复用。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：create_message_run 幂等查询；threads.py：duplicate；会话服务：create_message_run 查询条件
- 实际测试结果：已执行子项通过；第一轮通过4/失败0/受限0，第二轮通过4/失败0/受限0。子项记录：`TP-MSG-005__sequential_same_key`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","duplicate_statuses":[200,200],"original_counts":{"runs":1,"tasks":1,"events":2}}；`TP-MSG-007__different_key`：通过，输出：{"selected":[{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"},{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"}],"a_counts":{"runs":4,"tasks":4,"events":8},"b_counts":{"runs":1,"tasks":1,"events":2}}；`TP-MSG-007__different_thread`：通过，输出：{"selected":[{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"},{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"}],"a_counts":{"runs":4,"tasks":4,"events":8},"b_counts":{"runs":1,"tasks":1,"events":2}}；`TP-MSG-007__no_key_each_time`：通过，输出：{"selected":[{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"},{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]"}],"a_counts":{"runs":4,"tasks":4,"events":8},"b_counts":{"runs":1,"tasks":1,"events":2}}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### MSG_006：同Key竞争提交只建一次

- 用例编号：`MSG_006`
- 对应测试点：`TP-MSG-006`：同Key并发提交
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；普通并发可测，确定性两请求首次查询后屏障待E2
- 测试数据要求：同Thread/Key/正文两请求及反复试验次数
- 测试流程：并发提交并记每次计数；补驱动后把两请求置于首次幂等查询通过、取锁前，再放行。
- 预期结果：任一交错只一Message/Run/Task和一组创建事件，两请求返回相同ID或安全冲突；零次偶然复现不能证明通过。当前缺锁后复查/唯一约束记录风险。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：会话服务：create_message_run；MessageModel.__table_args__
- 实际测试结果：不通过；第一轮通过0/失败8/受限1，第二轮通过0/失败8/受限1。子项记录：`TP-MSG-006__ordinary_concurrency_trial_1`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_2`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_3`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_4`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_5`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_6`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_7`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__ordinary_concurrency_trial_8`：失败，输出：Expected values to be strictly deep-equal: + actual - expected { + message_id: '[关联ID见证据]', + run_id: '[关联ID见证据]', + task_id: '[关联ID见证据]' - message_id: '[关联ID见证据]', - run_id: '[关联ID见证据]', - task_id: '[关联ID见证据]' } ；`TP-MSG-006__first_query_barrier`：受限未执行，输出：E2 首次查询后、取Thread锁前的确定性双请求屏障尚未准备；普通并发结果不能替代。原因：类型1（已测/审查确认）：幂等查询在Thread锁前，锁内未复查且缺唯一保护；每轮8次普通并发均返回不同执行身份。 定位：`backend/application/threads.py:57/74 create_message_run；backend/db/models.py:56 MessageModel`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category msg`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-msg.log`及`categories/msg.json`，按`MSG_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### MSG_007：重复完成不产生第二assistant

- 用例编号：`MSG_007`
- 对应测试点：`TP-MSG-009`：assistant重复完成防护
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补同一身份重复handler完成驱动
- 测试数据要求：同task_id/run_id，两个合法/重复完成调用
- 测试流程：让第一次完成持久成功；再次交付相同身份或重入最终提交；读assistant与终态Event。
- 预期结果：同Run最终assistant至多一条、指针不变，不重复正文/终态；不能凭首次成功推断具备重复完成保护。
- 优先级：P0
- 用例类型：并发/恢复
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：最终事务；MessageModel；RunModel
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-MSG-009__full-scenario`：受限未执行，输出：E2 同task_id/worker_id/generation重复完成或最终提交重入驱动尚未准备。静态风险（非本用例动态失败）：只拒cancelled，缺其它终态重入及已有最终assistant保护。 定位：`backend/workers/handlers/run_handler.py:40/99；backend/db/models.py:76 RunModel`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### MSG_008：最终回写与新问题并发seq

- 用例编号：`MSG_008`
- 对应测试点：`TP-MSG-010`：用户与assistant并发seq
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补Thread游标读取/最终提交屏障
- 测试数据要求：同Thread旧Run即将完成、新Key问题
- 测试流程：在旧assistant分配seq与新用户创建交错处放行两事务；比较完整Message与游标。
- 预期结果：两条事实都保存，seq唯一无回退、无丢失更新/唯一冲突导致回答失败；仅用户创建有锁不足以证明此项。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：thread.next_message_seq；会话服务：create_message_run
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-MSG-010__full-scenario`：受限未执行，输出：E2 assistant分配seq与新用户Message创建的Thread游标/最终提交屏障尚未准备。静态风险（非本用例动态失败）：用户与assistant的Thread seq分配未用相同锁协议。 定位：`backend/application/threads.py:74 Thread锁；backend/workers/handlers/run_handler.py:107`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/msg.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/msg.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RUN_001：无Worker时原子创建持久执行链

- 用例编号：`RUN_001`
- 对应测试点：`TP-RUN-001`：初始事实原子创建；`TP-WK-001`：PostgreSQL权威排队
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；先停Worker，PG正常；本用例独立Thread
- 测试数据要求：一条问题和Key
- 测试流程：提交后立即读Run/Thread/events及Task；重启Worker再等同一Run完成。
- 预期结果：201返回稳定ID；用户Message、唯一Run、主Task、run.created/task.queued同提交且初始queued；不在HTTP同步生成答案；重启从PG领取原身份。
- 优先级：P0
- 用例类型：功能/契约
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：会话服务：create_message_run；Journal.append_event；会话服务；TaskModel；Queue；Runtime
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-RUN-001__queued_full_chain`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","thread_id":"[关联ID见证据]","counts":{"runs":1,"tasks":1,"events":2},"run_status":"queued","task_state":"queued"}；`TP-WK-001__restart_claims_original`：通过，输出：{"run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","generation":1,"attempt":1,"persisted_identity_preserved":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category run`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-run.log`及`categories/run.json`，按`RUN_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### RUN_002：初始事务故障整组回滚

- 用例编号：`RUN_002`
- 对应测试点：`TP-RUN-002`：创建事务失败回滚
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补flush/commit失败注入，只作用本用例连接
- 测试数据要求：Message/Run/Task加入后首次flush失败、追加事件后commit失败两个分支
- 测试流程：调用真实创建用例并在目标提交点失败；从另一连接读取；恢复后再提交新问题。
- 预期结果：失败请求不返回已创建成功；Message/Run/Task/Event及Thread游标全部回滚，无半链路；恢复后可正常创建，不手删事实伪造回滚。
- 优先级：P0
- 用例类型：异常/事务
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：会话服务：create_message_run；DB session
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-RUN-002__first_flush_failure`：受限未执行，输出：E2 仅作用本用例连接的first_flush_failure注入驱动尚未准备；`TP-RUN-002__event_commit_failure`：受限未执行，输出：E2 仅作用本用例连接的event_commit_failure注入驱动尚未准备。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RUN_003：配置快照准确并约束后续执行

- 用例编号：`RUN_003`
- 对应测试点：`TP-RUN-003`：快照字段准确性；`TP-RUN-004`：执行遵从冻结快照
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；默认快照可读；非Mock/配置变更完整执行待E2/E4覆盖
- 测试数据要求：API top_k=1创建queued Run；Worker top_k=3；不同模型标识，不用真实Key
- 测试流程：读取创建快照；用改变后的Worker配置执行原Run；比较Provider实际参数/证据数并重读snapshot。
- 预期结果：快照准确记录创建时模型、top_k、prompt_version和创建时间，不含Key且不被改写；执行仍遵循top_k=1/创建模型。当前硬编码mock且handler读新Settings应记差异，不以JSON存在为通过。
- 优先级：P0
- 用例类型：契约/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：会话服务：snapshot_json；RunModel.created_at；Run Handler：settings.rag_top_k/providers；会话服务
- 实际测试结果：局部通过，完整受限；第一轮通过4/失败0/受限2，第二轮通过4/失败0/受限2。子项记录：`TP-RUN-003__creation_model`：通过，输出：{"run_id":"[关联ID见证据]","creation_model":"mock"}；`TP-RUN-003__retrieval_prompt_time`：通过，输出：{"run_id":"[关联ID见证据]","top_k":5,"created_at":"2026-10-07T07:55:40.631104+00:00"}；`TP-RUN-003__safe_immutable_snapshot`：通过，输出：{"run_id":"[关联ID见证据]","immutable_after_normal_execution":true,"sensitive_fields":false}；`TP-RUN-004__default_execution_limit`：通过，输出：{"run_id":"[关联ID见证据]","retrieval_count":5,"frozen_top_k":5,"limitation":"API和Worker配置相同，未证明配置改变后的遵从性"}；`TP-RUN-003__non_mock_model_snapshot`：受限未执行，输出：E2/E4/C 非Mock、不同模型名称的创建与执行配置驱动尚未准备；默认Mock不证明硬编码模型正确；`TP-RUN-004__changed_worker_configuration`：受限未执行，输出：E2/E4/C API/Worker不同配置及Provider调用参数证据驱动尚未准备。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category run`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-run.log`及`categories/run.json`，按`RUN_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### RUN_004：Run与Task全部持久状态读取一致

- 用例编号：`RUN_004`
- 对应测试点：`TP-RUN-005`：状态读取持久一致
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；queued/成功/取消可测；running/retry_waiting/failed全覆盖待E2
- 测试数据要求：各独立Run覆盖queued/running/retry_waiting/succeeded/failed/cancelled
- 测试流程：分别使Run进入真实阶段，重复读API/DB；观察Redis/前端不参与终态写入。
- 预期结果：API与DB事实一致、对应Task状态符合阶段；终态来自后端事务，状态不由观察者推断。补E2前只对已观察状态给局部结论。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Run服务：get_run_detail；Runtime._record_run_failure；ORM
- 实际测试结果：局部通过，完整受限；第一轮通过3/失败0/受限3，第二轮通过3/失败0/受限3。子项记录：`TP-RUN-005__queued`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","run_status":"queued","task_state":"queued","repeated_reads_consistent":true}；`TP-RUN-005__succeeded`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","run_status":"succeeded","task_state":"succeeded","repeated_reads_consistent":true}；`TP-RUN-005__cancelled`：通过，输出：{"message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","run_status":"cancelled","task_state":"cancelled","repeated_reads_consistent":true}；`TP-RUN-005__running`：受限未执行，输出：E2 可控running阶段的真实Run驱动尚未准备；不使用Index失败或SQL修改状态替代；`TP-RUN-005__retry_waiting`：受限未执行，输出：E2 可控retry_waiting阶段的真实Run驱动尚未准备；不使用Index失败或SQL修改状态替代；`TP-RUN-005__failed`：受限未执行，输出：E2 可控failed阶段的真实Run驱动尚未准备；不使用Index失败或SQL修改状态替代。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category run`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-run.log`及`categories/run.json`，按`RUN_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### RUN_005：成功结果事务原子可见与故障回滚

- 用例编号：`RUN_005`
- 对应测试点：`TP-RUN-006`：成功终态原子提交
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；正常成功可测；最终commit故障待E2
- 测试数据要求：完整问答；在新增assistant和两个终态Event后commit失败
- 测试流程：正常完成从另一连接读全组；故障分支读取提交前后并检查回滚。
- 预期结果：assistant正文/引用、Run/Task succeeded、message.completed/run.succeeded同时可见；提交失败则该整组不可见、不存在半成功；允许后续失败结算，但不能把成功残片当终态。
- 优先级：P0
- 用例类型：功能/异常/事务
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Run Handler：最终commit；Journal
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-RUN-006__normal_committed_group`：通过，输出：{"run_id":"[关联ID见证据]","assistant_message_id":"[关联ID见证据]","assistant_count":1,"citation_count":5,"terminal_group":[{"seq":9,"type":"message.completed"},{"seq":10,"type":"run.succeeded"}],"limitation":"正常提交全组可见；未覆盖commit失败"}；`TP-RUN-006__final_commit_failure`：受限未执行，输出：E2 本用例最终commit失败、另一连接前后读取屏障尚未准备。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category run`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-run.log`及`categories/run.json`，按`RUN_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### RUN_006：succeeded/failed不能被重执行逆转

- 用例编号：`RUN_006`
- 对应测试点：`TP-RUN-007`：非取消终态不可逆
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补终态重入和迟到失败驱动
- 测试数据要求：成功Run、永久失败Run各独立；旧attempt异常
- 测试流程：对终态重复开始handler并投递迟到失败回写；比较状态、Message、seq和错误。
- 预期结果：成功/失败终态不回running/retry_waiting，无冲突终态或第二assistant；纯状态机测试不能替代生产直接赋值路径。
- 优先级：P0
- 用例类型：并发/状态机
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：状态机：transition_run/task；Run Handler；Runtime._record_run_failure
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-RUN-007__full-scenario`：受限未执行，输出：E2 成功/永久失败Run的handler终态重入及旧attempt迟到失败驱动尚未准备；纯状态机不替代生产路径。静态风险（非本用例动态失败）：只拒cancelled，缺其它终态重入及已有最终assistant保护。 定位：`backend/workers/handlers/run_handler.py:40/99；backend/db/models.py:76 RunModel`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RUN_007：缺失Run的读取/事件/取消错误

- 用例编号：`RUN_007`
- 对应测试点：`TP-RUN-008`：Run对象访问隔离
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；不存在UUID；跨owner由OWN_001覆盖
- 测试数据要求：详情、events、cancel
- 测试流程：分别请求并核对DB无新Run/Event或其他对象改变。
- 预期结果：全部404/RUN_NOT_FOUND，无取消副作用；SSE握手另有SSE_005，不以普通events通过替代。
- 优先级：P0
- 用例类型：异常/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Run服务：load_run/get_run_events/cancel_run
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-RUN-008__detail`：通过，输出：{"missing_run_id":"[关联ID见证据]","operation":"detail","http_status":404,"code":"RUN_NOT_FOUND","counts":{"runs":0,"events":0,"tasks":0}}；`TP-RUN-008__events`：通过，输出：{"missing_run_id":"[关联ID见证据]","operation":"events","http_status":404,"code":"RUN_NOT_FOUND","counts":{"runs":0,"events":0,"tasks":0}}；`TP-RUN-008__cancel`：通过，输出：{"missing_run_id":"[关联ID见证据]","operation":"cancel","http_status":404,"code":"RUN_NOT_FOUND","counts":{"runs":0,"events":0,"tasks":0}}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/run.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/run.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category run`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-run.log`及`categories/run.json`，按`RUN_007__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

### 4.3 Worker租约、重试、截止和停机

主归属：worker-lease-recovery（DB故障归 fault-safety）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### WK_001：可领取任务资格与租约初值

- 用例编号：`WK_001`
- 对应测试点：`TP-WK-002`：领取资格筛选；`TP-WK-003`：领取身份与代数
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；普通领取可读；精确状态/时钟边界需E2驱动
- 测试数据要求：queued且available<=now/deadline>now；未来available、到期deadline、各非queued；确定排序时间
- 测试流程：创建业务任务并让驱动调用真实claim；分别检查不合格组、排序及一次领取后的身份。
- 预期结果：仅可用queued被领取；按available_at/created_at排序；成功写leased、worker_id、generation和attempt各+1、now+TTL租约，提交后才执行；deadline=now不得领取。边界驱动未备时不宣称全组通过。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Queue.claim_next_task；Queue.claim_next_task；TaskModel
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限1，第二轮通过2/失败0/受限1。子项记录：`TP-WK-003__claim`：通过，输出：{"task_id":"[关联ID见证据]","state":"leased","worker_id":"wk-driver","attempt":1,"generation":1,"lease":"2026-10-07T07:56:29.432179+00:00","ttl_seconds":30,"lease_in_server_bounds":true}；`TP-WK-002__queued-qualification`：通过，输出：[{"state":"cancelled","worker_id":"wk-driver","generation":1,"attempt":1}]；`TP-WK-002__time-and-state-boundaries`：受限未执行，输出：未准备逐状态/受控时钟及隔离队列驱动；已有正常领取不代表完整筛选组合。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### WK_002：双Worker排他与SKIP LOCKED

- 用例编号：`WK_002`
- 对应测试点：`TP-WK-004`：多Worker排他领取
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补双Worker/领取事务屏障驱动，两Worker不同稳定ID，真实PG两连接
- 测试数据要求：两个可用任务，第一条在连接A领取事务未提交
- 测试流程：A锁首任务，B尝试claim；再同时竞争同一单任务；读generation/attempt。
- 预期结果：被锁任务不阻塞B领取另一任务；同Task只一claim成功、代数与attempt各增一次；不得用SQLite模拟锁结论。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue：with_for_update(skip_locked=True)
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-004__full-scenario`：受限未执行，输出：E1+E2；待补双Worker/领取事务屏障驱动，两Worker不同稳定ID，真实PG两连接。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_003：默认Worker实例身份唯一

- 用例编号：`WK_003`
- 对应测试点：`TP-WK-005`：Worker身份唯一性
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；核查默认身份；动态需两个未设置WORKER_ID的隔离实例
- 测试数据要求：两个同PID容器；显式不同ID对照
- 测试流程：追踪默认worker_id生成、存续稳定性及readiness键；比较同PID实例结果。
- 预期结果：同一进程稳定、不同实例不同身份；默认worker-PID可能碰撞须记录失败/差异。harness显式唯一ID是测试前提，不能替产品默认实现背书。
- 优先级：P0
- 用例类型：边界/架构
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：Runtime.__init__；heartbeat；TaskModel.worker_id
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-WK-005__default-identity`：失败，输出：两个同PID实例默认worker_id碰撞，显式测试ID并未修复默认生成。原因：类型1（已测/审查确认）：默认worker-PID在跨容器同PID时碰撞；harness显式WORKER_ID未修产品默认行为。 定位：`backend/workers/runtime.py:35 WorkerRuntime.__init__`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### WK_004：长任务正常续租保护

- 用例编号：`WK_004`
- 对应测试点：`TP-WK-006`：正常心跳持续续租
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补慢任务，heartbeat<TTL，另一Worker观察
- 测试数据要求：持续超过2×TTL的任务
- 测试流程：执行中定时只读lease；其他Worker轮询；正常释放Provider后完成。
- 预期结果：lease按心跳延长、task/worker/generation不变；无到期回收或第二执行者；最后原子成功。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime._lease_heartbeat；Queue.renew_lease
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-006__full-scenario`：受限未执行，输出：E1+E2；待补慢任务，heartbeat<TTL，另一Worker观察。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_005：错误身份及过期边界续租拒绝

- 用例编号：`WK_005`
- 对应测试点：`TP-WK-007`：不匹配身份续租拒绝；`TP-WK-008`：已到期lease续租拒绝
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补真实claim后的Queue驱动/时间边界
- 测试数据要求：wrong task/worker/generation；非leased/running；lease=now及<now；有效lease对照
- 测试流程：分别调用真实renew_lease；比对调用前后lease/state，过期组保留同worker/generation。
- 预期结果：无效组false且不改lease/state，有效组三元组匹配且未过期才延长；过期持有者不能自续复活。
- 优先级：P0
- 用例类型：安全/边界
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.renew_lease；Queue.renew_lease：lease_expires_at > utc_now
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-WK-007__full-scenario`：受限未执行，输出：E1+E2；待补真实claim后的Queue驱动/时间边界。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。；`TP-WK-008__full-scenario`：受限未执行，输出：E1+E2；待补真实claim后的Queue驱动/时间边界。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_006：崩溃后到期回收和原身份接管

- 用例编号：`WK_006`
- 对应测试点：`TP-WK-009`：未超限租约回收
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补领取后/完成前屏障；新Worker不同ID
- 测试数据要求：未达max_attempts的run任务
- 测试流程：确认已领取后kill旧Worker；先在TTL内观察，再到期回收/新claim；放行新任务完成。
- 预期结果：TTL内不抢租；到期清旧worker/lease并queued，新claim代数/attempt增长；task/run/user Message身份不变，唯一assistant；crash不等于SIGTERM优雅停机。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.requeue_expired/claim_next_task；Runtime.run_once
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-009__full-scenario`：受限未执行，输出：E1+E2；待补领取后/完成前屏障；新Worker不同ID。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_007：接管后普通旧状态写回拒绝及审计

- 用例编号：`WK_007`
- 对应测试点：`TP-WK-010`：旧代数普通写回拒绝；`TP-WK-030`：stale拒绝诊断
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补新代数已提交后的旧Queue调用
- 测试数据要求：旧身份mark_running/mark_succeeded/schedule_retry/renew；适用合法前态
- 测试流程：调用每个旧写回；比较新执行事实和关联事件/日志。
- 预期结果：全部拒绝不污染新状态/期限/错误；有安全可关联task_id/worker_id/generation拒绝诊断，false或静默return不能满足审计要求。
- 优先级：P0
- 用例类型：并发/运维
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue对应函数的筛选条件；Queue；Runtime._lease_heartbeat；Run Handler
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-WK-010__full-scenario`：受限未执行，输出：E1+E2；待补新代数已提交后的旧Queue调用。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。；`TP-WK-030__full-scenario`：受限未执行，输出：E1+E2；待补新代数已提交后的旧Queue调用。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：条件SELECT后ORM更新不是提交时三元组CAS，成功分支缺有效lease条件，拒绝多为静默返回。 定位：`backend/infrastructure/queue/postgres_queue.py:48/93/114；backend/workers/handlers/run_handler.py:99`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_008：多次崩溃达到attempt上限

- 用例编号：`WK_008`
- 对应测试点：`TP-WK-011`：回收达到最大attempt
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补每次领取后kill和有界lease；run/index两任务分别自建
- 测试数据要求：max_attempts=3，连续3次崩溃
- 测试流程：每轮确认已领取再kill、等待到期回收；最后读Task及关联Run或Document。
- 预期结果：上限后Task和关联对象一致failed，稳定错误码与适用Run终态事件齐全，后续不claim；不能只Task failed而Run running/Document indexing。
- 优先级：P0
- 用例类型：异常/恢复
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.requeue_expired；RunModel/DocumentModel；Runtime
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-011__full-scenario`：受限未执行，输出：E1+E2；待补每次领取后kill和有界lease；run/index两任务分别自建。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：回收耗尽只改Task failed，没有关联Run/Document终态和Event。 定位：`backend/infrastructure/queue/postgres_queue.py:161 requeue_expired`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_009：SELECT后接管不被旧commit覆盖

- 用例编号：`WK_009`
- 对应测试点：`TP-WK-012`：查询后接管的竞态防护
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补两连接在查询后/commit前屏障
- 测试数据要求：renew、success、retry三写回，各独立Task
- 测试流程：旧连接条件查询通过后暂停；新连接完成到期回收/claim并提交；旧连接继续提交。
- 预期结果：每种交错均保留新generation/worker及状态，旧commit拒绝/回滚；静态WHERE存在不能证明CAS安全。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue：SELECT后ORM赋值commit；requeue_expired
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-012__full-scenario`：受限未执行，输出：E1+E2；待补两连接在查询后/commit前屏障。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：条件SELECT后ORM更新不是提交时三元组CAS，成功分支缺有效lease条件，拒绝多为静默返回。 定位：`backend/infrastructure/queue/postgres_queue.py:48/93/114；backend/workers/handlers/run_handler.py:99`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_010：旧attempt不能追加执行事件

- 用例编号：`WK_010`
- 对应测试点：`TP-WK-013`：旧Worker事件写回隔离
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补检索/增量返回屏障和接管
- 测试数据要求：旧attempt在query embedding或delta前暂停；新attempt完成接管
- 测试流程：新代数提交后放行旧retrieval/delta或重复开始；只读Journal序列并关联调用时间。
- 预期结果：接管后旧attempt不追加run.started/retrieval.completed/answer.delta污染事件，seq正常；不能仅最终成功检查三元组而忽略中途事实。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：各append_event前条件；Journal
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-013__full-scenario`：受限未执行，输出：E1+E2；待补检索/增量返回屏障和接管。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：中途Event、失败分支保护不足；心跳失租只返回不停止handler。 定位：`backend/workers/handlers/run_handler.py:53/78；backend/workers/runtime.py:147/162；backend/workers/handlers/index_handler.py:92`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_011：旧异常不能覆盖新Run或Document

- 用例编号：`WK_011`
- 对应测试点：`TP-WK-014`：旧Worker失败回写隔离
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补旧attempt延迟错误，分别run及index
- 测试数据要求：旧Run普通异常/旧Index PermanentTaskError，新代数正常执行
- 测试流程：新claim提交后抛出旧异常；读Run/Document/Task及事件。
- 预期结果：新事实不被置failed/retry_waiting或写旧错误；失败分支同样校验持有者，不能只保护成功分支。
- 优先级：P0
- 用例类型：并发/异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime._record_run_failure；Index Handler：PermanentTaskError分支
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-014__full-scenario`：受限未执行，输出：E1+E2；待补旧attempt延迟错误，分别run及index。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：中途Event、失败分支保护不足；心跳失租只返回不停止handler。 定位：`backend/workers/handlers/run_handler.py:53/78；backend/workers/runtime.py:147/162；backend/workers/handlers/index_handler.py:92`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_012：心跳失租后停止昂贵步骤

- 用例编号：`WK_012`
- 对应测试点：`TP-WK-015`：失租后停止工作
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补续租false和步骤计数
- 测试数据要求：Run检索/模型、Index embedding两类handler
- 测试流程：在步骤屏障处令renew失租，放行当前调用；观察后续Provider/索引调用数及事实。
- 预期结果：旧handler停止后续昂贵步骤与持久写回，有安全诊断；heartbeat返回而handler继续执行视为失败。
- 优先级：P0
- 用例类型：异常/安全
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime._lease_heartbeat/run_once；两个Handler
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-015__full-scenario`：受限未执行，输出：E1+E2；待补续租false和步骤计数。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：中途Event、失败分支保护不足；心跳失租只返回不停止handler。 定位：`backend/workers/handlers/run_handler.py:53/78；backend/workers/runtime.py:147/162；backend/workers/handlers/index_handler.py:92`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_013：指数退避计算与持久availability

- 用例编号：`WK_013`
- 对应测试点：`TP-WK-016`：退避时间计算
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0；现有函数可执行；PG schedule_retry动态需E2
- 测试数据要求：base=2，attempt1/2/3；时钟前后界
- 测试流程：核对纯函数为2/4/8；补驱动后真实schedule_retry并比较available_at与调用前后时间区间。
- 预期结果：available_at为故障时间加2/4/8且未到不执行；最大attempt限制次数，不要求未承诺jitter或额外时间封顶；纯数值通过不是完整重试通过。
- 优先级：P1
- 用例类型：边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Queue.retry_delay_seconds/schedule_retry
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-WK-016__backoff-values`：通过，输出：[2,4,8]；`TP-WK-016__persisted-availability`：受限未执行，输出：真实schedule_retry与时间边界驱动尚未完成；纯数值不算完整回排。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_013__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### WK_014：临时错误到期真实重试保持身份

- 用例编号：`WK_014`
- 对应测试点：`TP-WK-017`：retry_waiting回排；`TP-WK-018`：重试身份保持
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补首次失败后成功Provider；当前代码缺retry_waiting回排
- 测试数据要求：同Run一次临时异常，base2/max3
- 测试流程：首次失败读Task/Run等待与错误；不手动改状态，等退避到期再次领取并成功；比对身份和事件。
- 预期结果：等待前不执行，到期Task回queued并重新running；Run按ADR等待后继续running（不强制PRD示意中的中间queued）；同task/run/user Message、代数/attempt增加且最终Message唯一。当前停滞应failed，不用直接SQL回queued制造通过。
- 优先级：P0
- 用例类型：恢复/功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.claim_next_task/requeue_expired/schedule_retry；Runtime；TaskModel；Queue；会话服务；Run Handler
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-WK-017__full-scenario`：受限未执行，输出：E1+E2；待补首次失败后成功Provider；当前代码缺retry_waiting回排。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。；`TP-WK-018__full-scenario`：受限未执行，输出：E1+E2；待补首次失败后成功Provider；当前代码缺retry_waiting回排。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_015：持续临时错误耗尽重试一致失败

- 用例编号：`WK_015`
- 对应测试点：`TP-WK-019`：重试次数耗尽终态
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补每次失败驱动；回排实现缺口同WK_014
- 测试数据要求：run/index各max_attempts3，连续故障
- 测试流程：通过真实队列推进到第3次失败；只读终态、错误及有界等待后的是否再次领取。
- 预期结果：最多3attempt后Task及Run/Document failed，稳定错误码，不再领取/生成成功；索引Document同步失败也必须成立，单步最后分支不足以证明全回路。
- 优先级：P0
- 用例类型：异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.schedule_retry；Runtime._record_run_failure；Index Handler
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-019__full-scenario`：受限未执行，输出：E1+E2；待补每次失败驱动；回排实现缺口同WK_014。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_016：queued超过总deadline明确失败

- 用例编号：`WK_016`
- 对应测试点：`TP-WK-020`：排队过deadline
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；需测试专用API deadline配置，现有4项模板不包含；短配置驱动待补
- 测试数据要求：deadline5秒；停Worker保持queued
- 测试流程：提交后等待真实deadline再启动Worker，读Task/Run/Event，观察两个poll周期以上。
- 预期结果：到期Task/Run failed且TASK_DEADLINE_EXCEEDED，不永久queued、不当用户cancelled，无后续执行；当前只领取过滤可静态确认，完整动态需覆盖配置。
- 优先级：P0
- 用例类型：边界/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Queue.claim_next_task；Runtime；TaskModel
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-WK-020__expired-queued`：失败，输出：截止后仍未结算failed。原因：类型1（已测/审查确认）：claim排除已deadline任务却没有queued到期结算，回收只覆盖leased/running；短deadline生产函数驱动任务仍queued。 定位：`backend/infrastructure/queue/postgres_queue.py:20 claim_next_task、:149 requeue_expired；backend/workers/runtime.py:79 run_once`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_016__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### WK_017：运行任务跨deadline停止

- 用例编号：`WK_017`
- 对应测试点：`TP-WK-021`：执行中过deadline
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补慢任务和短deadline覆盖
- 测试数据要求：当前任务在deadline后才返回结果
- 测试流程：观察到期限及后续调用，放行迟到回答，读取最终持久事实。
- 预期结果：硬期限后停止后续步骤，Task/Run失败且截止码，不允许迟到succeeded；Index分支同样无迟到发布。
- 优先级：P0
- 用例类型：边界
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler/Index Handler；Runtime
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-021__full-scenario`：受限未执行，输出：E1+E2；待补慢任务和短deadline覆盖。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：运行步骤和最终提交缺硬deadline检查，退避越deadline缺结算。 定位：`backend/workers/handlers/run_handler.py:30/99；backend/infrastructure/queue/postgres_queue.py:139`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_018：退避不能越过总deadline

- 用例编号：`WK_018`
- 对应测试点：`TP-WK-022`：retry_waiting过deadline
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补第一次错误、短deadline和长退避
- 测试数据要求：available_at晚于deadline_at
- 测试流程：失败后保持retry_waiting；跨deadline观察，再跨available_at观察。
- 预期结果：截止时Task/Run失败并保留原身份/截止错误，不继续等待或再次执行；当前回排/结算均缺时应报告差异。
- 优先级：P0
- 用例类型：边界/异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Queue.schedule_retry/claim_next_task；Runtime
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-022__full-scenario`：受限未执行，输出：E1+E2；待补第一次错误、短deadline和长退避。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`；静态风险（非本用例动态失败）：运行步骤和最终提交缺硬deadline检查，退避越deadline缺结算。 定位：`backend/workers/handlers/run_handler.py:30/99；backend/infrastructure/queue/postgres_queue.py:139`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_019：SIGTERM后不领取新任务

- 用例编号：`WK_019`
- 对应测试点：`TP-WK-023`：SIGTERM停止新领取
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补慢任务和信号观察驱动；Linux容器内任务A运行、B排队
- 测试数据要求：A已running/B已queued，Provider屏障
- 测试流程：对精确Worker发SIGTERM并记录收到信号时间；放行A；读B是否被该实例claim；重启领取B。
- 预期结果：停止标志后旧Worker不claim B；B保留queued供重启/他者，不能靠强制kill伪证停领。
- 优先级：P0
- 用例类型：运维
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：install_signal_handlers；Runtime.request_stop/run_forever
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-023__full-scenario`：受限未执行，输出：E1+E2；待补慢任务和信号观察驱动；Linux容器内任务A运行、B排队。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_020：宽限内完成仍有有效lease

- 用例编号：`WK_020`
- 对应测试点：`TP-WK-024`：SIGTERM宽限内完成
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补剩余执行时间小于grace且大于剩余TTL的任务
- 测试数据要求：设置grace/TTL/heartbeat有效；另一Worker可观察
- 测试流程：A运行中SIGTERM，宽限内放行完成；监测心跳/lease与竞争者。
- 预期结果：当前任务在grace内完成且必要续租继续，有效租约内原子成功，无他者接管；stop_event终止续租的风险须判明。
- 优先级：P0
- 用例类型：运维/恢复
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime._lease_heartbeat/run_forever；Run Handler
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-024__full-scenario`：受限未执行，输出：E1+E2；待补剩余执行时间小于grace且大于剩余TTL的任务。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：readiness仅循环头刷新，stop停止租约心跳，当前handler没有真实grace有界等待。 定位：`backend/workers/runtime.py:136/191/203`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_021：超宽限有界退出并可回收

- 用例编号：`WK_021`
- 对应测试点：`TP-WK-025`：SIGTERM超宽限退出
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补阻塞超过grace任务；区分Docker stop超时
- 测试数据要求：grace20秒，处理耗时>grace；测试stop_grace_period应大于应用grace
- 测试流程：SIGTERM后测应用退出时间/原因；观察显式释放或有效回收；重启执行。
- 预期结果：应用在配置grace加事先限定调度误差内安全退出，当前任务完成/释放/可回收；Docker SIGKILL不能记优雅通过；无无限await，也不静默丢失任务。
- 优先级：P0
- 用例类型：运维/边界
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Runtime.run_forever；Compose未设stop_grace_period
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-025__full-scenario`：受限未执行，输出：E1+E2；待补阻塞超过grace任务；区分Docker stop超时。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：readiness仅循环头刷新，stop停止租约心跳，当前handler没有真实grace有界等待。 定位：`backend/workers/runtime.py:136/191/203`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### WK_022：正常Worker重启继续queued任务

- 用例编号：`WK_022`
- 对应测试点：`TP-WK-026`：正常重启续跑队列
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；无运行中长任务，先停Worker
- 测试数据要求：停机期间新建两个Run
- 测试流程：重启Worker并观察队列完成，比较创建时ID。
- 预期结果：两任务继续原身份执行、事实保留，无重复用户/Run/assistant；遗留leased任务路径另由WK_006验证，不在快速重启中夸大覆盖。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Worker入口；Runtime；Queue
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-WK-026__queued-restart`：通过，输出：[{"thread_id":"[关联ID见证据]","message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","status":"succeeded"},{"thread_id":"[关联ID见证据]","message_id":"[关联ID见证据]","run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","status":"succeeded"}]。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_022__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### WK_023：DB中断后Worker有界退避恢复

- 用例编号：`WK_023`
- 对应测试点：`TP-WK-028`：DB中断Worker退避恢复
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；空闲Worker；精确停止和恢复本次PG
- 测试数据要求：领取/回收周期内PG不可达，恢复后新queued任务
- 测试流程：等待Worker下一轮访问失败；检查进程、日志/重连频率；恢复PG、提交任务。
- 预期结果：Worker不静默退出，不无限热循环，安全有界退避；恢复后无需丢状态继续领取，不靠手动重启掩盖恢复缺陷。
- 优先级：P0
- 用例类型：恢复/异常
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Runtime.run_forever/run_once；Worker入口finally
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过1/失败0/受限0。状态波动：`WK_023__TP-WK-028__db-recovery` 第一轮失败（Run [关联ID见证据]未进入终态），第二轮通过（{"worker":"running","run_id":"[关联ID见证据]"}）。子项记录：`TP-WK-028__db-recovery`：通过，输出：{"worker":"running","run_id":"[关联ID见证据]"}。原因：类型3（未定位/测试观测不足）：第一轮恢复后新Run15秒未终态，第二轮成功；具体差异根因未定位。故障快照均running、RestartCount0，专属4秒日志为空，缺实际查询命中故障屏障；空日志不能证明退避。 定位：`tests/demo-smoke/specific_test_script/wk-tests.mjs:49/50/53/54 db-recovery`；类型1（静态风险，非已定位该次失败根因）：领取/回收异常在handler catch之外，run_forever无DB异常捕获或重连退避；最终日志有同路径异常，但混有HLT阶段。 定位：`backend/workers/runtime.py:79 run_once、:191 run_forever；backend/workers/main.py:20 main`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_023__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：否；WK_023同一恢复子项一轮失败、一轮通过，根因未定位，不能只取第二轮。

#### WK_024：六类调度动作日志可关联

- 用例编号：`WK_024`
- 对应测试点：`TP-WK-029`：Worker生命周期关联日志
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0/E1；claim/success可直接观察；renew/release/retry/failure全链待E2且release实现不足
- 测试数据要求：六动作×run/index适用场景
- 测试流程：逐动作触发或审查缺失生产路径；读取默认实际日志输出而非logger.extra源代码。
- 预期结果：日志含task_id、适用run_id或document_id、worker_id、generation；无secret；动作缺日志/无release机制/formatter未输出均明示，不以部分动作日志作为全部通过。
- 优先级：P1
- 用例类型：运维
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Runtime logger调用；Worker入口logging.basicConfig；Queue
- 实际测试结果：不通过；第一轮通过0/失败2/受限1，第二轮通过0/失败2/受限1。子项记录：`TP-WK-029__claim-log`：失败，输出：默认claim行未输出task_id/run_id等关联字段；`TP-WK-029__success-log`：失败，输出：实际success动作缺关联日志；`TP-WK-029__all-actions`：受限未执行，输出：尚未准备六动作×两handler驱动；release正式机制不足；claim日志断言不能覆盖所有动作。。原因：类型1（已测/审查确认）：formatter不展示extra，claim extra亦缺run_id；成功动作无对应关联日志。 定位：`backend/workers/main.py:9 logging.basicConfig；backend/workers/runtime.py:88 run_once；backend/workers/handlers/run_handler.py:123 process_run_task`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category wk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-wk.log`及`categories/wk.json`，按`WK_024__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### WK_025：未被接管的过期lease也不得完成

- 用例编号：`WK_025`
- 对应测试点：`TP-WK-031`：到期未接管的完成拒绝
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补续租停止及最终提交屏障；不启动回收者
- 测试数据要求：worker/generation不变但lease真实过期
- 测试流程：到期后放行旧handler最终提交；另组直接调用真实mark_succeeded；读Task/Run/Message/Event。
- 预期结果：两路径均拒绝过期持有者，不写assistant或成功终态；三元组相同不能替代租约仍有效。
- 优先级：P0
- 用例类型：边界/并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler最终条件；Queue.mark_succeeded；TaskModel.lease_expires_at
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-WK-031__full-scenario`：受限未执行，输出：E1+E2；待补续租停止及最终提交屏障；不启动回收者。需要真实PG事务/Provider屏障或受控时间及信号驱动；本轮尚未实现完整驱动，不把快速Mock任务/SQLite单测冒充该时序。。静态风险（非本用例动态失败）：条件SELECT后ORM更新不是提交时三元组CAS，成功分支缺有效lease条件，拒绝多为静默返回。 定位：`backend/infrastructure/queue/postgres_queue.py:48/93/114；backend/workers/handlers/run_handler.py:99`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/wk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/wk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.4 取消行为

主归属：thread-run-api（步骤竞态复用 worker-lease-recovery 驱动）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### CAN_001：queued取消及终态重复取消

- 用例编号：`CAN_001`
- 对应测试点：`TP-CAN-001`：queued取消；`TP-CAN-002`：终态重复取消
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；停Worker创建queued；另自建成功及空文失败以外的Run失败需E2
- 测试数据要求：queued、cancelled、succeeded；failed分支待确定性失败驱动
- 测试流程：取消queued后读Run/Task/Event；重启Worker观察不执行；重复取消各已获得终态。
- 预期结果：queued取消原子写Run/Task cancelled和cancel_requested_at/唯一run.cancelled；不生成assistant；重复终态取消不逆转、不新增事件，保留原错误/正文。failed未准备时记子项blocked，不借用Index失败冒充Run失败。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Run服务：cancel_run；Queue.claim_next_task；Run服务：cancel_run终态判断
- 实际测试结果：局部通过，完整受限；第一轮通过4/失败0/受限1，第二轮通过4/失败0/受限1。子项记录：`TP-CAN-001__queued_cancel_transaction`：通过，输出：{"run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","cancel_requested_at":"2026-10-07T07:56:36.623129+00:00","events":[{"event_id":"[关联ID见证据]","run_id":"[关联ID见证据]","seq":1,"type":"run.created"},{"event_id":"[关联ID见证据]","run_id":"[关联ID见证据]","seq":2,"type":"task.queued"}…（完整输出见原证据）；`TP-CAN-001__restart_does_not_claim_cancelled`：通过，输出：{"run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","attempt":0,"generation":0,"worker_cycle_observed":"[关联ID见证据]"}；`TP-CAN-002__cancelled_repeat`：通过，输出：{"run_id":"[关联ID见证据]","terminal_status":"cancelled","event_count":3,"unchanged":true}；`TP-CAN-002__succeeded_repeat`：通过，输出：{"run_id":"[关联ID见证据]","terminal_status":"succeeded","assistant_message_id":"[关联ID见证据]","unchanged":true}；`TP-CAN-002__failed_repeat`：受限未执行，输出：E2 真实Run永久失败驱动尚未准备；空文Index失败不是Run失败。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category can`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-can.log`及`categories/can.json`，按`CAN_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### CAN_002：embedding期间取消阻止检索

- 用例编号：`CAN_002`
- 对应测试点：`TP-CAN-003`：检索前步骤取消检查
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补query embedding返回前屏障
- 测试数据要求：调用计数search=0的Run
- 测试流程：embedding期间经正式cancel取消，等提交后放行embedding；观察search/检索事件。
- 预期结果：不调用search、不写retrieval.completed，Run保持cancelled；只无最终Message不足以证明步骤检查。
- 优先级：P0
- 用例类型：功能/异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：初始判断/query_embedding/search_chunks
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-CAN-003__full-scenario`：受限未执行，输出：E2 query embedding返回前屏障及search调用计数驱动尚未准备。静态风险（非本用例动态失败）：步骤间取消检查及最终取消/成功事务竞争保护不足。 定位：`backend/workers/handlers/run_handler.py:48/75/98；backend/application/runs.py:31`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### CAN_003：检索后取消阻止模型调用

- 用例编号：`CAN_003`
- 对应测试点：`TP-CAN-004`：模型前步骤取消检查
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补search完成/模型前屏障
- 测试数据要求：Provider stream_answer调用计数
- 测试流程：暂停模型前，经API取消并确认提交再放行。
- 预期结果：模型调用次数0，无answer.delta或成功，保留取消前已提交事实。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：retrieval.completed后stream_answer
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-CAN-004__full-scenario`：受限未执行，输出：E2 search完成后、model.stream_answer调用前屏障及调用计数驱动尚未准备。静态风险（非本用例动态失败）：步骤间取消检查及最终取消/成功事务竞争保护不足。 定位：`backend/workers/handlers/run_handler.py:48/75/98；backend/application/runs.py:31`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### CAN_004：生成中取消不发布后续增量

- 用例编号：`CAN_004`
- 对应测试点：`TP-CAN-005`：流式中取消抑制增量
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补至少3片增量慢Provider
- 测试数据要求：片1先提交，片2/3在取消后返回
- 测试流程：收到首delta后取消，再放行后两片；读Journal/Message/Run。
- 预期结果：首片可保留，取消后不新增delta/最终assistant，状态不成功；不能把前端断开代替cancel。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：answer.delta前current.status检查
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-CAN-005__full-scenario`：受限未执行，输出：E2 首片已提交、后两片在取消后返回的慢Provider逐片屏障尚未准备。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### CAN_005：取消与最终成功交错终态

- 用例编号：`CAN_005`
- 对应测试点：`TP-CAN-006`：迟到成功与取消竞态
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补最终SELECT/commit屏障
- 测试数据要求：取消先commit；成功先commit两独立分支
- 测试流程：控制两事务顺序并放行另一方；比较终态、assistant和终态Event。
- 预期结果：取消先提交则无迟到成功/assistant覆盖；成功先提交则cancel不逆转成功；每Run只一个有效终态，无冲突事实。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run服务：cancel_run；Run Handler：最终事务
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-CAN-006__cancel_commits_first`：受限未执行，输出：E2 cancel_commits_first最终SELECT/commit双事务屏障尚未准备；`TP-CAN-006__success_commits_first`：受限未执行，输出：E2 success_commits_first最终SELECT/commit双事务屏障尚未准备。静态风险（非本用例动态失败）：步骤间取消检查及最终取消/成功事务竞争保护不足。 定位：`backend/workers/handlers/run_handler.py:48/75/98；backend/application/runs.py:31`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### CAN_006：retry_waiting取消不被重排复活

- 用例编号：`CAN_006`
- 对应测试点：`TP-CAN-007`：retry_waiting取消
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补真实临时失败驱动，自动回排当前缺失
- 测试数据要求：处于退避的Run，取消与到期回排交错
- 测试流程：失败后cancel；跨available_at并启动/保持Worker；补回排后再测竞争。
- 预期结果：原Task/Run cancelled，不重新claim/回答；等待态cancel函数局部效果不替代完整回排竞争验收。
- 优先级：P0
- 用例类型：功能/并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run服务：cancel_run；Queue.schedule_retry
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-CAN-007__full-scenario`：受限未执行，输出：E2 真实临时失败、到期回排与取消交错驱动尚未准备；不得SQL写retry_waiting伪造前提。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/can.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/can.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.5 文档登记、解析与切分

主归属：document-rag（安全故障归 fault-safety）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### DOC_001：三格式登记元数据、hash和列表

- 用例编号：`DOC_001`
- 对应测试点：`TP-DOC-001`：上传元数据与索引任务；`TP-DOC-006`：内容哈希准确；`TP-DOC-009`：文档列表与owner
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；同owner，Worker先停；跨owner另OWN_001
- 测试数据要求：txt/md/docx，同字节不同文件名及改变一字节对照
- 测试流程：依次上传；读返回/列表和Document/Task；比对原字节hash和列表时间。
- 预期结果：201、UUID、原名/扩展/字节数/hash/owner/storage_key/状态/时间及index Task持久准确；同内容同hash但独立Document，不虚构去重；列表时间倒序无路径。独立source字段缺失单独记局部差异。
- 优先级：P0
- 用例类型：功能/契约
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：文档服务：create_document；DocumentModel；documents.py：to_response；Storage.save；DocumentModel.content_hash；文档服务：list_documents；DocumentResponse
- 实际测试结果：不通过；第一轮通过5/失败1/受限0，第二轮通过5/失败1/受限0。子项记录：`TP-DOC-001__txt`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","format":"txt","bytes":40,"status":"uploaded"}；`TP-DOC-001__md`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","format":"md","bytes":28,"status":"uploaded"}；`TP-DOC-001__docx`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","format":"docx","bytes":1082,"status":"uploaded"}；`TP-DOC-006__equal-and-changed-bytes`：通过，输出：{"documents":["[关联ID见证据]","[关联ID见证据]","[关联ID见证据]"],"same_hash":true,"changed_hash":true}；`TP-DOC-009__owner-list-order`：通过，输出：{"count":11,"registered":3,"owner_matches":true}；`TP-DOC-001__source-field`：失败，输出：当前DocumentResponse缺少独立source字段。原因：类型1（已测/审查确认）：Document公开契约没有独立来源语义；source是测试字段约定，不能仅按字段拼写作PRD唯一解释。 定位：`backend/api/schemas/documents.py:6 DocumentResponse；backend/api/routes/documents.py:12 to_response`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_002：扩展名白名单与大小写

- 用例编号：`DOC_002`
- 对应测试点：`TP-DOC-002`：扩展名白名单
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；停Worker；每项单独请求
- 测试数据要求：txt/md/docx及TXT/MD/DOCX；doc/pdf/exe/无后缀，内容均安全文本
- 测试流程：逐项上传；比对HTTP、文件/Document/Task增量。
- 预期结果：支持后缀大小写归一接受；其他415/UNSUPPORTED_DOCUMENT_TYPE，无文件/记录/Task；.doc不能被当已支持。
- 优先级：P1
- 用例类型：边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：文档服务：ALLOWED_EXTENSIONS；Path.suffix.lower
- 实际测试结果：已执行子项通过；第一轮通过10/失败0/受限0，第二轮通过10/失败0/受限0。子项记录：`TP-DOC-002__txt`：通过，输出：{"extension":"txt","status":201,"error_code":null}；`TP-DOC-002__md`：通过，输出：{"extension":"md","status":201,"error_code":null}；`TP-DOC-002__docx`：通过，输出：{"extension":"docx","status":201,"error_code":null}；`TP-DOC-002__TXT`：通过，输出：{"extension":"TXT","status":201,"error_code":null}；`TP-DOC-002__MD`：通过，输出：{"extension":"MD","status":201,"error_code":null}；`TP-DOC-002__DOCX`：通过，输出：{"extension":"DOCX","status":201,"error_code":null}；`TP-DOC-002__doc`：通过，输出：{"extension":"doc","status":415,"error_code":"UNSUPPORTED_DOCUMENT_TYPE"}；`TP-DOC-002__pdf`：通过，输出：{"extension":"pdf","status":415,"error_code":"UNSUPPORTED_DOCUMENT_TYPE"}；`TP-DOC-002__exe`：通过，输出：{"extension":"exe","status":415,"error_code":"UNSUPPORTED_DOCUMENT_TYPE"}；`TP-DOC-002__none`：通过，输出：{"extension":"none","status":415,"error_code":"UNSUPPORTED_DOCUMENT_TYPE"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_003：10MiB精确边界

- 用例编号：`DOC_003`
- 对应测试点：`TP-DOC-003`：文件大小阈值
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；仅在本次tmp生成，不提交大fixture，停Worker
- 测试数据要求：有效UTF8 txt恰10×1024×1024字节及+1
- 测试流程：上传两项；核对状态、size和上传卷/DB；结束清生成文件。
- 预期结果：恰10MiB登记201，+1拒413/DOCUMENT_TOO_LARGE且无文件/Task；索引结果不混入上传大小通过标准。
- 优先级：P0
- 用例类型：边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：MAX_DOCUMENT_BYTES；create_document
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-DOC-003__production-exact-10mib`：通过，输出：{"size":10485760,"hash":"b5eec3f68ef64d15e82dad91ff908582c5f081e61a62e22427af9bec2cd35f8d","expected_hash":"b5eec3f68ef64d15e82dad91ff908582c5f081e61a62e22427af9bec2cd35f8d","stored_size":10485760,"document_status":"uploaded","task_state":"queued","task_kind":…（完整输出见原证据）；`TP-DOC-003__http-plus-one`：通过，输出：{"bytes":10485761,"status":413,"error_code":"DOCUMENT_TOO_LARGE"}；`TP-DOC-003__http-exact-10mib`：通过，输出：{"scenario":"doc-limit","nested_run_id":"20261007t075714-e25fa0ad","checks":[{"id":"DOC_003__TP-DOC-003__http-exact-10mib","status":"passed"}],"bytes":10485760,"status":201,"cleanup":"passed","evidence":"evidence/nested/doc-limit-summary.json"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_004：MIME与扩展名匹配

- 用例编号：`DOC_004`
- 对应测试点：`TP-DOC-004`：MIME与扩展名匹配
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；停Worker，具备可控multipart客户端
- 测试数据要求：每支持格式×允许MIME、application/octet-stream、无MIME、明显错误MIME
- 测试流程：按组合上传并核对实际请求头、状态及DB/存储副作用。
- 预期结果：匹配、octet-stream、未指定兼容接受；不匹配415/DOCUMENT_MIME_MISMATCH无副作用；不将此检查称内容魔数识别。
- 优先级：P1
- 用例类型：安全/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：文档服务：allowed_mime
- 实际测试结果：已执行子项通过；第一轮通过13/失败0/受限0，第二轮通过13/失败0/受限0。子项记录：`TP-DOC-004__txt-text-plain`：通过，输出：{"format":"txt","mime":"text/plain","status":201,"error_code":null}；`TP-DOC-004__txt-application-octet-stream`：通过，输出：{"format":"txt","mime":"application/octet-stream","status":201,"error_code":null}；`TP-DOC-004__txt-none`：通过，输出：{"format":"txt","mime":null,"status":201,"error_code":null}；`TP-DOC-004__txt-image-png`：通过，输出：{"format":"txt","mime":"image/png","status":415,"error_code":"DOCUMENT_MIME_MISMATCH"}；`TP-DOC-004__md-text-markdown`：通过，输出：{"format":"md","mime":"text/markdown","status":201,"error_code":null}；`TP-DOC-004__md-text-plain`：通过，输出：{"format":"md","mime":"text/plain","status":201,"error_code":null}；`TP-DOC-004__md-application-octet-stream`：通过，输出：{"format":"md","mime":"application/octet-stream","status":201,"error_code":null}；`TP-DOC-004__md-none`：通过，输出：{"format":"md","mime":null,"status":201,"error_code":null}；`TP-DOC-004__md-image-png`：通过，输出：{"format":"md","mime":"image/png","status":415,"error_code":"DOCUMENT_MIME_MISMATCH"}；`TP-DOC-004__docx-application-vnd.openxmlformats-officedocument.wordprocessingml.document`：通过，输出：{"format":"docx","mime":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","status":201,"error_code":null}；`TP-DOC-004__docx-application-octet-stream`：通过，输出：{"format":"docx","mime":"application/octet-stream","status":201,"error_code":null}；`TP-DOC-004__docx-none`：通过，输出：{"format":"docx","mime":null,"status":201,"error_code":null}；`TP-DOC-004__docx-image-png`：通过，输出：{"format":"docx","mime":"image/png","status":415,"error_code":"DOCUMENT_MIME_MISMATCH"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_005：原文件名不控制落盘路径

- 用例编号：`DOC_005`
- 对应测试点：`TP-DOC-005`：文件名路径隔离
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；只用上传卷内部和测试哨兵，不碰宿主真文件
- 测试数据要求：../sentinel.txt、绝对样式文件名、Unicode/特殊符号；超长名单列观察
- 测试流程：上传后只读定位实际storage_key和文件；核对旁路哨兵未变及浏览器显示。
- 预期结果：文件仅服务端UUID路径下存储，不覆盖外部哨兵；原名安全显示；超长错误可诊断不泄路径，未约定最大长度不强加精确边界。
- 优先级：P0
- 用例类型：安全/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Storage.save；create_document；DocumentModel.filename
- 实际测试结果：不通过；第一轮通过6/失败1/受限0，第二轮通过6/失败1/受限0。子项记录：`TP-DOC-005__production-sentinel`：通过，输出：{"variants":3,"sentinel_unchanged":true,"scope":"本用例独立临时上传范围和PG保存点"}；`TP-DOC-005__5cbebb93`：通过，输出：{"document_id":"[关联ID见证据]","status":201,"under_uuid_path":true}；`TP-DOC-005__7752c3b0`：通过，输出：{"document_id":"[关联ID见证据]","status":201,"under_uuid_path":true}；`TP-DOC-005__78615a17`：通过，输出：{"document_id":"[关联ID见证据]","status":201,"under_uuid_path":true}；`TP-DOC-005__c5e9c725`：通过，输出：{"document_id":"[关联ID见证据]","status":201,"under_uuid_path":true}；`TP-DOC-005__browser-filename-text`：通过，输出：{"documents":["[关联ID见证据]","[关联ID见证据]"],"displayed_exactly":true,"html_elements_created":0,"events_executed":false}；`TP-DOC-005__long-name-observation`：失败，输出：超长名拒绝仅通用错误，缺少可诊断稳定错误码/安全说明。原因：类型1（已测/审查确认）：超长文件名被拒绝，但只有通用错误而无稳定安全诊断码；未声称发生文件路径越界。 定位：`backend/application/documents.py:22 create_document；backend/db/models.py:132 DocumentModel；backend/app.py:37 application_error_handler`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_006：DB登记失败删除已保存原文件

- 用例编号：`DOC_006`
- 对应测试点：`TP-DOC-007`：登记DB失败清理文件
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补保存成功后DB commit故障
- 测试数据要求：独立小txt，记录本次storage_key
- 测试流程：触发登记提交失败；另一连接查Document/Task、检查源文件和临时文件。
- 预期结果：DB全回滚、source删除，无无主原始文件或成功响应；空父目录可单独记录而非业务事实。
- 优先级：P0
- 用例类型：异常/事务
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：文档服务：create_document except/target.unlink
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-DOC-007__full-scenario`：受限未执行，输出：尚无保存成功后精确DB commit故障驱动；不能伪造SQL登记失败或删除他人文件。。静态风险（非本用例动态失败）：storage.save在登记try外，temporary写入/replace缺失败清理包围。 定位：`backend/application/documents.py:48/76；backend/infrastructure/storage/local_files.py:12 save`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### DOC_007：存储不可写时安全失败

- 用例编号：`DOC_007`
- 对应测试点：`TP-DOC-008`：上传磁盘故障
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补本次受限上传卷/精确写失败，不填满宿主磁盘
- 测试数据要求：只读目录或受控write错误
- 测试流程：API上传触发save失败；检查响应、DB、临时文件及错误脱敏。
- 预期结果：无成功Document/Task，安全诊断并清理本次未完成文件；当前save在try外的映射/清理风险不能忽略。
- 优先级：P0
- 用例类型：异常/安全
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Storage.save temporary；create_document try边界；App
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-DOC-008__full-scenario`：受限未执行，输出：尚无限定本次上传卷的可控write失败/API脱敏驱动；不填满磁盘或修改共享上传目录权限。。静态风险（非本用例动态失败）：storage.save在登记try外，temporary写入/replace缺失败清理包围。 定位：`backend/application/documents.py:48/76；backend/infrastructure/storage/local_files.py:12 save`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### DOC_008：活动index请求复用

- 用例编号：`DOC_008`
- 对应测试点：`TP-DOC-010`：活动索引任务复用
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；queued可测；leased/running/retry_waiting需E2
- 测试数据要求：每状态独立Document和一个真实活动index Task
- 测试流程：重复POST index两次；读返回ID、活动Task数及batch标识。
- 预期结果：每状态同task_id、无新活动Task/batch；queued通过不等于全部中间态通过。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：文档服务：create_index_task
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限3，第二轮通过1/失败0/受限3。子项记录：`TP-DOC-010__queued`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","state":"queued"}；`TP-DOC-010__leased`：受限未执行，输出：缺少E2确定阶段屏障；queued结果不代表该状态。；`TP-DOC-010__running`：受限未执行，输出：缺少E2确定阶段屏障；queued结果不代表该状态。；`TP-DOC-010__retry_waiting`：受限未执行，输出：缺少E2确定阶段屏障；queued结果不代表该状态。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_008__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### DOC_009：并发重建只一个活动Task

- 用例编号：`DOC_009`
- 对应测试点：`TP-DOC-011`：并发index请求幂等
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；已有终态无活动Task；确定性查询后屏障需E2
- 测试数据要求：两并发index请求，同Document
- 测试流程：普通并发记录多轮；补屏障后同时通过无活动任务查询再commit；再顺序请求检查。
- 预期结果：只一个未终态Task，返回复用/安全冲突，无重复batch或后续scalar多行错误；偶然无冲突不证明幂等安全。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：create_index_task查询/commit；TaskModel约束
- 实际测试结果：不通过；第一轮通过0/失败3/受限1，第二轮通过0/失败3/受限1。子项记录：`TP-DOC-011__ordinary-concurrency-1`：失败，输出：普通并发创建了重复活动索引Task 2 !== 1 ；`TP-DOC-011__ordinary-concurrency-2`：失败，输出：普通并发创建了重复活动索引Task 2 !== 1 ；`TP-DOC-011__ordinary-concurrency-3`：失败，输出：普通并发创建了重复活动索引Task 2 !== 1 ；`TP-DOC-011__deterministic-query-barrier`：受限未执行，输出：缺少E2查询后屏障；普通并发偶然成功不证明并发幂等安全。。原因：类型1（已测/审查确认）：活动Task查询后新增之间无锁/唯一保护；每轮3次普通并发创建2个活动索引Task。 定位：`backend/application/documents.py:94 create_index_task；backend/db/models.py:91 TaskModel`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_009__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### DOC_010：不存在Document索引拒绝

- 用例编号：`DOC_010`
- 对应测试点：`TP-DOC-012`：index对象访问拒绝
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；未使用UUID；跨owner另OWN_001
- 测试数据要求：POST documents/{id}/index
- 测试流程：提交并核对Task计数/文件访问。
- 预期结果：404/DOCUMENT_NOT_FOUND，无Task或文件读取副作用；输入ID不是宿主路径。
- 优先级：P0
- 用例类型：异常/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：文档服务：create_index_task owner校验
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-DOC-012__missing-document`：通过，输出：{"document_id":"[关联ID见证据]","status":404,"error_code":"DOCUMENT_NOT_FOUND"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_010__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### DOC_011：终态重建与成功批次替换

- 用例编号：`DOC_011`
- 对应测试点：`TP-DOC-013`：终态文档重新索引；`TP-IDX-007`：成功替换清理旧批次
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例已indexed文档，另空文failed文档；先停Worker
- 测试数据要求：两终态Document；为成功文档先完成一条有引用回答
- 测试流程：请求重建并观察queued时旧active；重启完成；比对新task/batch、旧Chunk及历史引用。
- 预期结果：终态不复用旧Task；新Task/batch，Document回uploaded；候选前旧active保留。成功后只新active、旧Chunk清除/seq唯一；历史Message原引用不删改，不要求旧chunk预览。失败文档可创建新尝试但仍按其内容失败。
- 优先级：P1
- 用例类型：功能/恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：文档服务：create_index_task；DocumentModel.active_index_batch_id；Index Handler：delete旧batch；uq_chunks_batch_seq
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-DOC-013__terminal-rebuild`：通过，输出：{"documents":[{"document_id":"[关联ID见证据]","prior_status":"indexed"},{"document_id":"[关联ID见证据]","prior_status":"failed"}],"new_tasks":true}；`TP-IDX-007__replace-and-preserve-history`：通过，输出：{"documents":["[关联ID见证据]","[关联ID见证据]"],"historical_message":"[关联ID见证据]","history_unchanged":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/doc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/doc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category doc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-doc.log`及`categories/doc.json`，按`DOC_011__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### PAR_001：三格式正文解析及位置语义

- 用例编号：`PAR_001`
- 对应测试点：`TP-PAR-001`：UTF-8 txt解析；`TP-PAR-002`：Markdown解析；`TP-PAR-003`：docx段落解析；`TP-PAR-007`：解析位置契约
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；现有safe fixture可用；段落位置可比对
- 测试数据要求：含中英/换行txt、标题与标记md、两段落docx
- 测试流程：分别上传索引；按parser参考文本比对Chunk切片和source_name/offset。
- 预期结果：txt UTF8字符保真，md保留原标记，docx顶层段落以换行拼接；Chunk offset是解析文本字符而非字节/页码。Parser独立位置字段缺失须记局部契约差异，不假称完整位置接口。
- 优先级：P0
- 用例类型：功能/契约
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Parser.parse_document：.txt；Chunker；Parser：path.read_text；tests/unit/test_parsers.py；Parser：Document(...)/document.paragraphs；ParsedDocument；ChunkDraft；ChunkModel
- 实际测试结果：不通过；第一轮通过5/失败1/受限0，第二轮通过5/失败1/受限0。子项记录：`TP-PAR-001__production-fixtures`：通过，输出：{"formats":["txt","md","docx"],"txt_characters":24}；`TP-PAR-001__txt-indexed-text`：通过，输出：{"document_id":"[关联ID见证据]","format":"txt","chunks":1,"parsed_characters":24}；`TP-PAR-002__md-indexed-text`：通过，输出：{"document_id":"[关联ID见证据]","format":"md","chunks":1,"parsed_characters":29}；`TP-PAR-003__docx-indexed-text`：通过，输出：{"document_id":"[关联ID见证据]","format":"docx","chunks":1,"parsed_characters":23}；`TP-PAR-007__character-offset`：通过，输出：{"documents":["[关联ID见证据]","[关联ID见证据]","[关联ID见证据]"],"offset_unit":"Unicode字符"}；`TP-PAR-007__parser-position-contract`：失败，输出：ParsedDocument仅source_name/text，缺少独立基础位置字段。原因：类型1（已测/审查确认）：解析结构只有source_name/text，没有ADR所述独立基础位置字段；chunk字符offset不等同解析位置语义。 定位：`backend/infrastructure/rag/parsers.py:6 ParsedDocument、:11 parse_document`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/par.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/par.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category par`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-par.log`及`categories/par.json`，按`PAR_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### PAR_002：错误编码与损坏docx失败语义

- 用例编号：`PAR_002`
- 对应测试点：`TP-PAR-004`：编码损坏失败语义；`TP-PAR-005`：docx结构损坏
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本次tmp生成，允许必要有界观察，已知retry停滞可能复现
- 测试数据要求：非UTF8 txt/md；非ZIP或损坏ZIP的docx
- 测试流程：通过上传入口登记，等待索引失败结算；读Document/Task错误、attempt和active。
- 预期结果：最终Document/Task failed且稳定解析错误，无错误成功或发布空知识；普通异常停retry_waiting/indexing视为失败，不以等待更多时间掩盖缺回排。
- 优先级：P0
- 用例类型：异常
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Parser.read_text(encoding='utf-8')；Index Handler except；Parser：python-docx；Index Handler
- 实际测试结果：不通过；第一轮通过0/失败4/受限0，第二轮通过0/失败4/受限0。子项记录：`TP-PAR-004__bad-txt`：失败，输出：解析错误未结算：{"document_id":"[关联ID见证据]","document_status":"indexing","task_state":"retry_waiting","attempt":1,"max_attempts":3,"error_code":"INDEX_FAILED","timeout":true} + actual - expected + 'indexing' - 'failed' ；`TP-PAR-004__bad-md`：失败，输出：解析错误未结算：{"document_id":"[关联ID见证据]","document_status":"indexing","task_state":"retry_waiting","attempt":1,"max_attempts":3,"error_code":"INDEX_FAILED","timeout":true} + actual - expected + 'indexing' - 'failed' ；`TP-PAR-005__nonzip-docx`：失败，输出：解析错误未结算：{"document_id":"[关联ID见证据]","document_status":"indexing","task_state":"retry_waiting","attempt":1,"max_attempts":3,"error_code":"INDEX_FAILED","timeout":true} + actual - expected + 'indexing' - 'failed' ；`TP-PAR-005__damaged-zip-docx`：失败，输出：解析错误未结算：{"document_id":"[关联ID见证据]","document_status":"indexing","task_state":"retry_waiting","attempt":1,"max_attempts":3,"error_code":"INDEX_FAILED","timeout":true} + actual - expected + 'indexing' - 'failed' 。原因：类型1（已测/审查确认）：坏编码/docx或源丢失进入通用INDEX_FAILED，Task写retry_waiting；没有到期回queued路径，Document保持indexing，attempt=1/max_attempts=3。 定位：`backend/infrastructure/rag/parsers.py:11 parse_document；backend/workers/handlers/index_handler.py:103 通用异常分支；backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:20 claim_next_task`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/par.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/par.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category par`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-par.log`及`categories/par.json`，按`PAR_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### PAR_003：真正空解析不发布索引

- 用例编号：`PAR_003`
- 对应测试点：`TP-PAR-006`：空解析文本；`TP-IDX-008`：索引终态错误一致性
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；EMPTY_DOCUMENT分支可测；IDX普通异常耗尽另IDX_005
- 测试数据要求：零字节txt/md、无段落正文docx；仅空白文本观察对照
- 测试流程：逐项索引并读Task/Document/Chunk/active。
- 预期结果：真正空文本Task/Document failed、EMPTY_DOCUMENT，active不切换，无空候选；仅空白按当前字符行为记录，不强加strip规则。本用例只覆盖IDX_008永久空文分支。
- 优先级：P0
- 用例类型：边界/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Index Handler：if not chunks；PermanentTaskError；Index Handler except；Queue.schedule_retry
- 实际测试结果：局部通过，完整受限；第一轮通过7/失败0/受限1，第二轮通过7/失败0/受限1。子项记录：`TP-PAR-006__zero-txt`：通过，输出：{"document_id":"[关联ID见证据]","status":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-IDX-008__zero-txt-task`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","task_state":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-PAR-006__zero-md`：通过，输出：{"document_id":"[关联ID见证据]","status":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-IDX-008__zero-md-task`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","task_state":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-PAR-006__empty-docx`：通过，输出：{"document_id":"[关联ID见证据]","status":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-IDX-008__empty-docx-task`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","task_state":"failed","error_code":"EMPTY_DOCUMENT"}；`TP-PAR-006__whitespace-observation`：通过，输出：{"document_id":"[关联ID见证据]","status":"indexed","whitespace_characters":4}；`TP-IDX-008__ordinary-error-exhaustion`：受限未执行，输出：本例仅真实验证EMPTY_DOCUMENT永久错误；普通错误耗尽及回排闭环归IDX_005，尚缺E2驱动。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/par.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/par.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category par`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-par.log`及`categories/par.json`，按`PAR_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### PAR_004：docx非段落内容支持边界

- 用例编号：`PAR_004`
- 对应测试点：`TP-PAR-008`：docx非段落文字覆盖
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；需本次tmp按设计生成无敏感内容docx
- 测试数据要求：仅表格文字；正文+页眉/文本框各独立哨兵
- 测试流程：上传解析并对照可见文字与解析/Chunk；区分只有非段落和混合文件。
- 预期结果：明确列出区域是否保留；当前顶层paragraphs遗漏是覆盖限制，不宣称已完整支持。PRD未细化区域，作为限制/待决事项而非擅自扩大P0承诺；仅表格触发空文时按EMPTY_DOCUMENT判断。
- 优先级：P1
- 用例类型：边界/观察
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Parser：document.paragraphs
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限1，第二轮通过2/失败0/受限1。子项记录：`TP-PAR-008__table_only`：通过，输出：{"document_id":"[关联ID见证据]","status":"failed","retained_regions":{"header":false,"table":false},"scope":"当前顶层paragraphs覆盖观察"}；`TP-PAR-008__mixed_regions`：通过，输出：{"document_id":"[关联ID见证据]","status":"indexed","retained_regions":{"header":false,"table":false},"scope":"当前顶层paragraphs覆盖观察"}；`TP-PAR-008__full-region-support`：受限未执行，输出：已动态记录各区域是否保留；PRD尚未细化区域范围，当前顶层paragraphs遗漏需需求确认，不能称完整docx区域支持。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/par.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/par.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category par`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-par.log`及`categories/par.json`，按`PAR_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### CHK_001：字符切分覆盖与overlap

- 用例编号：`CHK_001`
- 对应测试点：`TP-CHK-001`：切片覆盖与offset；`TP-CHK-002`：overlap交界
- 当前可验证状态：可验证·本机动态
- 前置条件：E0可调用纯函数；E1保存身份，默认配置无需变更
- 测试数据要求：size4/overlap0或1；文本长1/4/8/10，含中文；另默认800/120文档
- 测试流程：比对每块seq/start/end/text与输入；索引默认长文读document/batch身份。
- 预期结果：seq从0、无空尾块、首尾完整，text=原文[start:end]；start步长=size-overlap，尾块正确；每块父document/batch正确。字符近似不等于精确tokenizer。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Chunker.chunk_text；Index Handler：ChunkModel；Chunker.chunk_text
- 实际测试结果：已执行子项通过；第一轮通过4/失败0/受限0，第二轮通过4/失败0/受限0。子项记录：`TP-CHK-001__pure-character-coverage`：通过，输出：{"parameter_groups":8,"empty_chunks":0}；`TP-CHK-002__pure-overlap`：通过，输出：{"parameter_groups":8,"overlaps":[0,1]}；`TP-CHK-001__persisted-default-identity`：通过，输出：{"document_id":"[关联ID见证据]","batch_id":"[关联ID见证据]","chunks":3,"characters":2100}；`TP-CHK-002__persisted-default-overlap`：通过，输出：{"document_id":"[关联ID见证据]","pairs":2,"overlap":120}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/chk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/chk.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category chk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-chk.log`及`categories/chk.json`，按`CHK_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### CHK_002：非法切分参数拒绝与Worker结算

- 用例编号：`CHK_002`
- 对应测试点：`TP-CHK-003`：非法切分参数
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0函数可测；Worker配置驱动/最终失败需E2且重试闭环缺失
- 测试数据要求：size0/-1；overlap-1/size/size+1；有效对照
- 测试流程：纯函数逐组调用；补驱动后经index Task使用非法配置观察终态。
- 预期结果：函数明确ValueError、不无限循环；Worker配置错误须安全有界失败，不永久重试或indexing；纯函数通过只算局部。
- 优先级：P1
- 用例类型：边界/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Chunker参数判断；Settings；Index Handler
- 实际测试结果：局部通过，完整受限；第一轮通过5/失败0/受限1，第二轮通过5/失败0/受限1。子项记录：`TP-CHK-003__size-0-overlap-0`：通过，输出：{"size":0,"overlap":0,"error":"ValueError"}；`TP-CHK-003__size--1-overlap-0`：通过，输出：{"size":-1,"overlap":0,"error":"ValueError"}；`TP-CHK-003__size-4-overlap--1`：通过，输出：{"size":4,"overlap":-1,"error":"ValueError"}；`TP-CHK-003__size-4-overlap-4`：通过，输出：{"size":4,"overlap":4,"error":"ValueError"}；`TP-CHK-003__size-4-overlap-5`：通过，输出：{"size":4,"overlap":5,"error":"ValueError"}；`TP-CHK-003__worker-config-settlement`：受限未执行，输出：缺少E2独立Worker配置驱动；函数ValueError已动态验证，不能替代Worker失败/重试闭环。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/chk.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/chk.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category chk`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-chk.log`及`categories/chk.json`，按`CHK_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

### 4.6 索引候选与最小RAG

主归属：document-rag（Provider协议归 fault-safety）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### IDX_001：离线Mock向量确定性

- 用例编号：`IDX_001`
- 对应测试点：`TP-IDX-001`：确定性Mock Embedding
- 当前可验证状态：可验证·本机动态
- 前置条件：E0；当前Mock可直接调用；不需要网络
- 测试数据要求：相同中英文本重复、不同文本，默认384维
- 测试流程：多次embed并比较向量长度、数值有限性和同输入稳定性。
- 预期结果：同输入同配置完全相同、长度384且有限；不要求不同文本一定正交或哈希体现真实语义。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：MockEmbeddingProvider.embed；tests/unit/test_mock_provider.py
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-IDX-001__mock-repeat-finite`：通过，输出：{"equal_repeated":true,"dimensions":[384,384,384],"all_finite":true,"norms":[0.9999999999999999,0.9999999999999999,1]}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category idx`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-idx.log`及`categories/idx.json`，按`IDX_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### IDX_002：三格式首次索引全组结果

- 用例编号：`IDX_002`
- 对应测试点：`TP-IDX-003`：初次索引完整结果
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1；正常结果可测；indexing阶段确定采样需E2
- 测试数据要求：本用例分别safe txt/md/docx
- 测试流程：上传后轮询API/只读DB；记录各状态、Task、active、Chunk及错误字段。
- 预期结果：终态Document indexed和Task succeeded；Chunk非空且向量/seq/offset/document/batch完整，active指本批次、错误清除；uploaded→indexing→indexed需步骤证据，不以快速终态倒推中间态。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Index Handler；ChunkModel；Queue.mark_succeeded
- 实际测试结果：局部通过，完整受限；第一轮通过3/失败0/受限1，第二轮通过3/失败0/受限1。子项记录：`TP-IDX-003__txt-first-index`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","status":"indexed","task_state":"succeeded","batch_id":"[关联ID见证据]","chunks":1,"format":"txt"}；`TP-IDX-003__md-first-index`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","status":"indexed","task_state":"succeeded","batch_id":"[关联ID见证据]","chunks":1,"format":"md"}；`TP-IDX-003__docx-first-index`：通过，输出：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","status":"indexed","task_state":"succeeded","batch_id":"[关联ID见证据]","chunks":1,"format":"docx"}；`TP-IDX-003__indexing-phase`：受限未执行，输出：上传与终态已真实验证；缺少E2慢Embedding/步骤屏障，快速终态不能倒推indexing阶段。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category idx`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-idx.log`及`categories/idx.json`，按`IDX_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### IDX_003：错维Embedding禁止发布

- 用例编号：`IDX_003`
- 对应测试点：`TP-IDX-002`：Embedding长度不符
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补短/长向量Provider，本次配置固定384
- 测试数据要求：输出383/385长度各Document，384对照
- 测试流程：执行真实index handler，读失败事实与候选/active。
- 预期结果：错维Task/Document failed、EMBEDDING_DIMENSION_MISMATCH，无截断填充/候选切换/错误PG写入；有效对照成功。
- 优先级：P0
- 用例类型：异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Index Handler：len(vector)；PermanentTaskError
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-IDX-002__full-scenario`：受限未执行，输出：缺少E2真实领取Task与383/385维Provider受控驱动；默认384向量成功不能证明错维禁止发布。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### IDX_004：候选隔离与失败保留旧active

- 用例编号：`IDX_004`
- 对应测试点：`TP-IDX-004`：候选批次检索隔离；`TP-IDX-006`：重建失败保留旧索引
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补多块慢Embedding及第N块失败；真实PG查询
- 测试数据要求：首次构建无active；重建已有active；至少3块
- 测试流程：构建暂停时另连接检索；失败后再检索；独立成功分支完成后复核切换。
- 预期结果：首次候选不可召回；重建仅旧active；失败回滚候选、不抹旧active，即使Document failed旧知识仍可检索；全部成功才切新batch。
- 优先级：P0
- 用例类型：并发/恢复
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Index Handler候选事务；Vector.search_chunks active条件；Index Handler回滚；Vector.search_chunks
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-IDX-004__candidate-inflight`：受限未执行，输出：缺少E2多块慢Embedding屏障与独立PG检索采样；不SQL伪造候选状态。；`TP-IDX-006__failed-rebuild-old-active`：受限未执行，输出：缺少E2第N块失败Provider与构建期间检索驱动，正常重建成功另DOC_011独立验证。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### IDX_005：索引发布原子性及普通错误耗尽

- 用例编号：`IDX_005`
- 对应测试点：`TP-IDX-005`：索引发布与Task原子性；`TP-IDX-008`：索引终态错误一致性
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补两commit间故障和重复普通异常；回排缺失
- 测试数据要求：active提交与mark_succeeded之间断点；max_attempts耗尽分支
- 测试流程：在发布窗口中断；另一连接读Document/Task；另例普通失败至上限。
- 预期结果：按ADR不允许indexed而Task running/retry/failed的半发布；耗尽时Document/Task一致failed、有错误码且无候选污染。当前两事务及Document同步缺口分别记录，不只看永久错误分支。
- 优先级：P0
- 用例类型：事务/异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Index Handler两段session/commit；Index Handler except；Queue.schedule_retry
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-IDX-005__commit-window`：受限未执行，输出：缺少E2两commit之间精确故障驱动；当前两事务风险保留，不能用普通成功终态证明原子性。；`TP-IDX-008__ordinary-exhaustion`：受限未执行，输出：缺少E2重复普通异常驱动，当前retry_waiting回排缺口；PAR_003永久错误不能代替此分支。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`；静态风险（非本用例动态失败）：Document/Chunk发布与Task成功是两个事务。 定位：`backend/workers/handlers/index_handler.py:80/89/90/91；backend/infrastructure/queue/postgres_queue.py:93`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### IDX_006：源文件丢失重建明确失败

- 用例编号：`IDX_006`
- 对应测试点：`TP-IDX-009`：原始文件丢失
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；只删除本次临时文档精确source，需验证路径归属；不删除宿主文件
- 测试数据要求：已索引Document，其storage_key从本次DB诊断获得
- 测试流程：停Worker，移走本次source到本次tmp可恢复位置；请求重建并重启；读终态/错误与旧active。
- 预期结果：明确存储/索引失败、Task/Document一致、旧active不被污染；不能空正文成功或永久retry_waiting；保留可诊断安全错误。
- 优先级：P0
- 用例类型：异常/恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Storage.read；Index Handler except
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-IDX-009__missing-own-source`：失败，输出：源丢失未有界结算：{"document_id":"[关联ID见证据]","task_id":"[关联ID见证据]","document_status":"indexing","task_state":"retry_waiting","attempt":1,"max_attempts":3,"error_code":"INDEX_FAILED","timed_out":true} + actual - expected + 'indexing' - 'failed' 。原因：类型1（已测/审查确认）：坏编码/docx或源丢失进入通用INDEX_FAILED，Task写retry_waiting；没有到期回queued路径，Document保持indexing，attempt=1/max_attempts=3。 定位：`backend/infrastructure/rag/parsers.py:11 parse_document；backend/workers/handlers/index_handler.py:103 通用异常分支；backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:20 claim_next_task`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category idx`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-idx.log`及`categories/idx.json`，按`IDX_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### IDX_007：慢Embedding不能持长数据库事务

- 用例编号：`IDX_007`
- 对应测试点：`TP-IDX-010`：外部调用不持长事务
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补慢Provider，PG只读pg_stat_activity诊断
- 测试数据要求：多chunk每次调用持续多个秒，有限总时长
- 测试流程：Provider暂停时多次观察事务开始时间/连接占用；核对handler事务边界。
- 预期结果：外部调用不在长期持久事务内；观察无跨整个慢循环长事务。当前session循环可静态确认差异，动态指标不能用固定阈值冒充未约定SLO。
- 优先级：P1
- 用例类型：架构/性能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Index Handler：for draft嵌入session块
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-IDX-010__full-scenario`：受限未执行，输出：缺少E2多块慢Provider与pg_stat_activity确定采样；源码session位置不足以代替长事务实际指标，不擅自增加固定SLO阈值。。静态风险（非本用例动态失败）：候选事务内逐块await外部Embedding。 定位：`backend/workers/handlers/index_handler.py:46/47/54/60/61/89`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/idx.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/idx.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RAG_001：Top-K排序、证据字段与相似度边界

- 用例编号：`RAG_001`
- 对应测试点：`TP-RAG-001`：Top-K与排序；`TP-RAG-008`：相似度边界语义；`TP-RAG-014`：Top-K配置边界
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1默认K可测；K=1/超过N/<=0专用配置驱动待补，静态可核查
- 测试数据要求：多chunk；计算Mock query向量余弦；空库和有库无关问题；K1、N+2、0、-1
- 测试流程：按每组查询/正式Run或真实search函数，独立计算得分，比对证据、数量、排序和配置拒绝。
- 预期结果：有效K返回min(K,N)、余弦降序，平分不强制次序；Evidence文档/chunk/text/filename/offset/score完整；K<=0明确拒绝/有正式约定，不负切片。无阈值Mock有库无关问答可Top-K，不据此宣称语义拒答。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Vector.search_chunks/cosine_similarity；Evidence；Vector：scored[:top_k]；MockEmbeddingProvider；Settings.rag_top_k；Vector：scored[:top_k]
- 实际测试结果：不通过；第一轮通过5/失败2/受限1，第二轮通过5/失败2/受限1。子项记录：`TP-RAG-001__top-k-sort`：通过，输出：{"document_id":"[关联ID见证据]","n":55,"groups":[{"k":5,"count":5},{"k":1,"count":1},{"k":57,"count":55}]}；`TP-RAG-001__evidence-fields`：通过，输出：{"count":5,"evidence":[{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.8397348277053578},{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.7934122786589615},{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.7842023853046921},{"d…（完整输出见原证据）；`TP-RAG-008__cosine-and-no-threshold`：通过，输出：{"cosine_scores":[1,0,-1,0],"unrelated_count":5,"semantic_limit":"Mock无相关性阈值，不证明语义拒答"}；`TP-RAG-014__k-1`：通过，输出：{"k":1,"count":1,"error":null}；`TP-RAG-014__k-over-n`：通过，输出：{"k":57,"count":55,"error":null}；`TP-RAG-014__k-0`：失败，输出：当前search_chunks未拒绝K<=0，使用Python切片产生未约定行为；`TP-RAG-014__k--1`：失败，输出：当前search_chunks未拒绝K<=0，使用Python切片产生未约定行为；`TP-RAG-014__runtime-top-k-config`：受限未执行，输出：真实search函数边界已动态断言；缺少独立Worker配置驱动，不把函数调用等同正式Run配置验收。。原因：类型1（已测/审查确认）：K=0/-1未拒绝，直接Python切片产生未约定结果。 定位：`backend/infrastructure/rag/pgvector_store.py:31 search_chunks；backend/config.py:26 rag_top_k`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category rag`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-rag.log`及`categories/rag.json`，按`RAG_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### RAG_002：向量和检索故障不能冒充空证据

- 用例编号：`RAG_002`
- 对应测试点：`TP-RAG-003`：向量异常不是无证据
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补查询向量错维/真实search故障驱动
- 测试数据要求：错query/chunk维度、查询异常；零向量为对照非维度错误
- 测试流程：触发真实问答检索错误；读Task/Run/Event/Message和有界重试。
- 预期结果：稳定错误与失败或有限重试，没有成功无证据回答/伪citations；零向量当前cosine=0语义单独记录；完整结算受重试缺口不能假通过。
- 优先级：P0
- 用例类型：异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Vector.cosine_similarity/search_chunks；Run Handler except
- 实际测试结果：暂不可完整动态验证；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-RAG-003__real-search-wrong-dimension`：通过，输出：{"document_id":"[关联ID见证据]","query_dimensions":383,"error":"ValueError"}；`TP-RAG-003__task-run-settlement`：受限未执行，输出：真实search错维拒绝已验证；缺少E2错误Provider/真实search异常的正式Run驱动，且回排闭环缺口待验证。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RAG_003：真正空知识库回答

- 用例编号：`RAG_003`
- 对应测试点：`TP-RAG-004`：空召回答案
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例独立空文档集合/环境，非通过删除他人文档
- 测试数据要求：正常问题，无active Chunk
- 测试流程：提交Run并读retrieval、全部delta、最终Message及状态。
- 预期结果：检索count0/items空，正常succeeded、明确没有足够证据且citations空；无基础设施异常，不混淆低相似度。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：MockModelProvider.stream_answer；Run Handler
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-RAG-004__isolated-empty-owner`：通过，输出：{"count":0,"items":[],"answer":"当前知识库没有足够证据回答这个问题。","scope":"真实search+生产Mock空证据分支，随机独立空owner"}；`TP-RAG-004__formal-run-empty-range`：通过，输出：{"scenario":"rag-empty","nested_run_id":"20261007t080040-c8191fc1","checks":[{"id":"RAG_003__TP-RAG-004__formal-empty-run","status":"passed"}],"run_status":"succeeded","task_state":"succeeded","retrieval_count":0,"citations":[],"cleanup":"passed","evidence":"e…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category rag`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-rag.log`及`categories/rag.json`，按`RAG_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### RAG_004：非空证据、增量正文和引用身份

- 用例编号：`RAG_004`
- 对应测试点：`TP-RAG-005`：非空证据回答；`TP-RAG-006`：增量与最终正文一致；`TP-RAG-007`：引用证据身份真实性
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；自建三格式已索引资料，固定Mock且无Key
- 测试数据要求：含中英文/Markdown证据的问句
- 测试流程：执行问答；读retrieval和delta；只读核对本次Evidence/Chunk与最终citations/content。
- 预期结果：query向量→检索→Provider顺序，答案基于实际证据；按seq拼接delta再strip等于最终正文。每citation属于本次召回document/chunk/offset/score、filename正确，无他Run/owner/候选伪引用；中文仅一delta不失败。Mock不证明效果。
- 优先级：P0
- 用例类型：功能/安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Run Handler；Mock Provider；Vector；Run Handler：answer_parts/answer；MockModelProvider；Run Handler：evidence/citations；MessageModel.citations_json；Vector
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-RAG-005__nonempty-evidence-answer`：通过，输出：{"run_id":"[关联ID见证据]","documents":["[关联ID见证据]","[关联ID见证据]","[关联ID见证据]"],"retrieval_count":5,"assistant_message_id":"[关联ID见证据]"}；`TP-RAG-006__deltas-final`：通过，输出：{"run_id":"[关联ID见证据]","deltas":4,"characters":51,"message_id":"[关联ID见证据]"}；`TP-RAG-007__actual-citation-identities`：通过，输出：{"run_id":"[关联ID见证据]","citations":[{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.9999999999999998},{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.8391393602460557},{"document_id":"[关联ID见证据]","chunk_id":"[关联ID见证据]","score":0.839139360…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category rag`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-rag.log`及`categories/rag.json`，按`RAG_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### RAG_005：真实模式缺配置明确拒启动

- 用例编号：`RAG_005`
- 对应测试点：`TP-RAG-009`：Provider初始化配置
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0 Runtime初始化可安全审查；容器动态需诊断覆盖，默认harness固定Mock
- 测试数据要求：MOCK_PROVIDER=false；base/key/model/embedding_model任一缺失及全部缺失；默认Mock对照
- 测试流程：逐组初始化真实Runtime，不访问外部URL；核对启动结果和安全错误。
- 预期结果：缺字段明确拒绝，无静默Mock回退、不泄Key；Mock无外部配置可启动。现有.env四整数不能当已支持真实模式覆盖。
- 优先级：P1
- 用例类型：配置/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Runtime.__init__；Settings
- 实际测试结果：局部通过，完整受限；第一轮通过6/失败0/受限1，第二轮通过6/失败0/受限1。子项记录：`TP-RAG-009__missing-model_base_url`：通过，输出：{"missing":["model_base_url"],"error":"ValueError"}；`TP-RAG-009__missing-model_api_key`：通过，输出：{"missing":["model_api_key"],"error":"ValueError"}；`TP-RAG-009__missing-model_name`：通过，输出：{"missing":["model_name"],"error":"ValueError"}；`TP-RAG-009__missing-embedding_model_name`：通过，输出：{"missing":["embedding_model_name"],"error":"ValueError"}；`TP-RAG-009__missing-all`：通过，输出：{"missing":["model_base_url","model_api_key","model_name","embedding_model_name"],"error":"ValueError"}；`TP-RAG-009__mock-and-configured-real`：通过，输出：{"mock":true,"real_provider":"OpenAICompatibleProvider","external_requests":0}；`TP-RAG-009__container-startup-config`：受限未执行，输出：已调用真实Runtime初始化；harness固定Mock且不重配生产服务，容器启动配置覆盖待独立驱动。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category rag`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-rag.log`及`categories/rag.json`，按`RAG_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### RAG_006：Provider临时与永久错误分类

- 用例编号：`RAG_006`
- 对应测试点：`TP-RAG-010`：临时Provider错误分类；`TP-RAG-011`：永久Provider错误分类
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E4（结构化异常另E2）；待补隔离本地HTTP替身，非真实服务
- 测试数据要求：embed/chat分别超时/连接失败/500；401/403/400/不支持模型；PermanentTaskError
- 测试流程：通过生产HTTP adapter触发各错误；观察Task/Run或Document、错误码、attempt及事件。
- 预期结果：临时错误稳定分类、有限退避到上限失败；永久错误直接一致failed、不盲重试；不伪无资料、不多层无限重试。HTTP协议与注入Python异常分开给证据，当前RUN_FAILED/INDEX_FAILED及Task不一致按差异判定。
- 优先级：P0
- 用例类型：异常
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：真实Provider httpx调用；Run/Index Handler；Queue；backend/application/errors.py；Handler except；Runtime._record_run_failure
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-RAG-010__temporary-http-errors`：受限未执行，输出：缺少E4隔离本地HTTP协议服务及E2正式Task/Run结算驱动；Python注入异常不能替代真实HTTP协议。；`TP-RAG-011__permanent-http-errors`：受限未执行，输出：缺少E4隔离本地HTTP协议服务及正式永久异常结算驱动，当前通用RUN_FAILED/INDEX_FAILED不能按静态源码冒充正确分类。。静态风险（非本用例动态失败）：没有到期retry_waiting→queued路径；PAR_002/IDX_006已有动态同根证据，本用例完整错误分支仍受限。 定位：`backend/infrastructure/queue/postgres_queue.py:114 schedule_retry、:149 requeue_expired、:27 queued筛选`；静态风险（非本用例动态失败）：HTTP/网络错误未转换临时/永久结构化类型，普通异常统一重试。 定位：`backend/infrastructure/providers/openai_compatible.py:22/42；backend/workers/handlers/run_handler.py:139/142；index_handler.py:104`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RAG_007：Provider畸形JSON安全失败

- 用例编号：`RAG_007`
- 对应测试点：`TP-RAG-012`：Provider异常响应结构
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E4；待补本地协议服务
- 测试数据要求：embed缺data/空data/无embedding/错误类型；chat缺choices/content/空或错误类型
- 测试流程：逐组请求生产adapter，经handler观测结果；扫描响应/持久错误/日志。
- 预期结果：明确稳定失败，无无意义成功正文、无原始响应泄漏/无限等待；空/错误类型不能未经校验当合法回答。
- 优先级：P1
- 用例类型：异常/契约
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：真实Provider：response.json字段访问
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-RAG-012__full-scenario`：受限未执行，输出：缺少E4本地协议服务：逐组畸形JSON/类型/空字段必须通过生产HTTP adapter及handler观察，不能仅检查字段访问源码。。静态风险（非本用例动态失败）：直接访问未验证JSON并yield content，缺显式结构/非空校验。 定位：`backend/infrastructure/providers/openai_compatible.py:23/43`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### RAG_008：真实HTTP流协议逐增量交付

- 用例编号：`RAG_008`
- 对应测试点：`TP-RAG-013`：真实生成流协议
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E4；待补本地SSE模型替身；当前token流实现缺失
- 测试数据要求：分时返回3片不同文字，最终完成标记
- 测试流程：捕获adapter发送的请求stream字段；替身分片返回并观察每片进入Journal的时间。
- 预期结果：按流协议请求并逐增量交付，不等全HTTP响应一次yield；当前stream:false可静态记缺口，不用Mock多delta宣称真实token流。
- 优先级：P1
- 用例类型：契约
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：真实Provider.stream_answer
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-RAG-013__full-scenario`：受限未执行，输出：缺少E4分时三片SSE模型替身和Journal时间采样；当前真实adapter请求stream:false风险明确，Mock多delta不是HTTP流协议证据。。静态风险（非本用例动态失败）：真实请求stream:false且一次yield完整正文。 定位：`backend/infrastructure/providers/openai_compatible.py:35/43`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/rag.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/rag.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.7 Event Journal和SSE

主归属：event-sse-recovery。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### EVT_001：v1契约与正常阶段事件序列

- 用例编号：`EVT_001`
- 对应测试点：`TP-EVT-001`：Event envelope契约；`TP-EVT-004`：领取事件存在；`TP-EVT-005`：正常执行事件顺序
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；自建正常Run；JSON Schema可校验
- 测试数据要求：含中文数据的全部正常事件
- 测试流程：读events和SSE，以v1 Schema逐条验证；比对阶段顺序、Task身份与最终Message指针。
- 预期结果：schema_version1、UUID/run_id/正seq/type/ISO时间/data符合Schema；创建/排队后task.leased应关联真实task/generation且在run.started前，再检索/增量/消息完成/成功；当前无领取事件应单独failed，不删契约使通过。
- 优先级：P0
- 用例类型：契约/功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Event契约；Run服务：event_to_dict；RunEventModel；Queue.claim_next_task；Runtime.run_once；Event契约；会话服务；Run Handler；Journal
- 实际测试结果：不通过；第一轮通过1/失败2/受限0，第二轮通过1/失败2/受限0。子项记录：`TP-EVT-001__json_and_sse_v1`：通过，输出：{"run_id":"[关联ID见证据]","schema_checked_count":94,"events":"[47项，明细见证据]","stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[47项]"}}；`TP-EVT-004__leased_identity`：失败，输出：Run [关联ID见证据] 正常Journal缺少task.leased领取事件；证据evidence/evt/EVT_001-stage-summary.json；`TP-EVT-005__normal_stage_order`：失败，输出：正常阶段缺少task.leased。原因：类型1（已测/审查确认）：领取仅修改Task，没有task.leased，Journal从task.queued直接到run.started。 定位：`backend/infrastructure/queue/postgres_queue.py:38 claim_next_task；backend/workers/runtime.py:79 run_once；backend/workers/handlers/run_handler.py:44 process_run_task；contracts/run_event_v1.json:17`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/evt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/evt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category evt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-evt.log`及`categories/evt.json`，按`EVT_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### EVT_002：并发追加与回滚序号正确

- 用例编号：`EVT_002`
- 对应测试点：`TP-EVT-002`：同Run并发分配seq
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补真实append_event双连接及commit失败驱动
- 测试数据要求：同Run两并发追加，一个独立事务回滚
- 测试流程：控制追加竞争并提交；再触发回滚后继续追加；读游标及Journal。
- 预期结果：已提交seq唯一严格递增，游标与记录对应，回滚不永久占序号；真实PG，不手写Event SQL模拟生产分配。
- 优先级：P0
- 用例类型：并发/事务
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Journal.append_event；uq_run_events_run_seq
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限2，第二轮通过0/失败0/受限2。子项记录：`TP-EVT-002__two_connection_append`：受限未执行，输出：E2 two_connection_append真实生产append_event双连接/提交失败屏障尚未准备，不手写Event SQL代替；`TP-EVT-002__rollback_then_append`：受限未执行，输出：E2 rollback_then_append真实生产append_event双连接/提交失败屏障尚未准备，不手写Event SQL代替。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/evt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/evt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### EVT_003：旧事件不变及Run序号独立

- 用例编号：`EVT_003`
- 对应测试点：`TP-EVT-003`：事件追加不可改写；`TP-EVT-007`：Run之间序号独立
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；自建两Run并记首次事件摘要
- 测试数据要求：两Run各从1开始；重复读取/重放/API重启
- 测试流程：多次按各自游标读取，重启后对比旧event_id/seq/type/data；静态查更新删除路径。
- 预期结果：同Run历史内容不变、seq不跨Run共享；请求始终只含指定run_id；应用仅追加，不宣称DB能抵御任意SQL篡改。重试路径不可用时不声称覆盖重试后不变。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：Journal；RunEventModel；Run Handler/Runtime；Journal.append_event/list_events
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-EVT-003__history_unchanged_across_restart`：通过，输出：{"runs":[{"run_id":"[关联ID见证据]","old_event_ids":"[2项]","after_restart_count":7},{"run_id":"[关联ID见证据]","old_event_ids":"[2项]","after_restart_count":10}],"limitation":"未覆盖尚未准备的重试路径，不证明任意SQL篡改防护"}；`TP-EVT-007__run_sequence_independence`：通过，输出：{"runs":[{"run_id":"[关联ID见证据]","first_seq":1,"max_seq":7},{"run_id":"[关联ID见证据]","first_seq":1,"max_seq":10}]}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/evt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/evt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category evt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-evt.log`及`categories/evt.json`，按`EVT_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### EVT_004：events after_seq精确边界

- 用例编号：`EVT_004`
- 对应测试点：`TP-EVT-006`：after_seq补放边界
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；一完整Run已知最大seq=N
- 测试数据要求：0、中间m、N、N+10、-1、非法字符串
- 测试流程：分别GET事件，比较完整序列后缀、顺序和错误。
- 预期结果：只返回seq>游标的升序后缀；末尾及超末尾空；负/非整数422，无新Event。
- 优先级：P0
- 用例类型：边界/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：runs.py：get_events Query(ge=0)；Journal.list_events
- 实际测试结果：已执行子项通过；第一轮通过6/失败0/受限0，第二轮通过6/失败0/受限0。子项记录：`TP-EVT-006__zero`：通过，输出：{"run_id":"[关联ID见证据]","cursor":0,"max_seq":9,"http_status":200,"returned_seqs":"[9项，明细见证据]","event_count_unchanged":true}；`TP-EVT-006__middle`：通过，输出：{"run_id":"[关联ID见证据]","cursor":4,"max_seq":9,"http_status":200,"returned_seqs":[5,6,7,8,9],"event_count_unchanged":true}；`TP-EVT-006__last`：通过，输出：{"run_id":"[关联ID见证据]","cursor":9,"max_seq":9,"http_status":200,"returned_seqs":[],"event_count_unchanged":true}；`TP-EVT-006__beyond`：通过，输出：{"run_id":"[关联ID见证据]","cursor":19,"max_seq":9,"http_status":200,"returned_seqs":[],"event_count_unchanged":true}；`TP-EVT-006__negative`：通过，输出：{"run_id":"[关联ID见证据]","cursor":-1,"max_seq":9,"http_status":422,"event_count_unchanged":true}；`TP-EVT-006__non_integer`：通过，输出：{"run_id":"[关联ID见证据]","cursor":"not-an-integer","max_seq":9,"http_status":422,"event_count_unchanged":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/evt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/evt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category evt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-evt.log`及`categories/evt.json`，按`EVT_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### EVT_005：index Task不用伪会话事件

- 用例编号：`EVT_005`
- 对应测试点：`TP-EVT-008`：索引任务不伪造RunEvent
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例上传正常与空文各一个
- 测试数据要求：index_document Task
- 测试流程：读Task/Document及全库相关Run/Event（只读）；检查索引错误观测。
- 预期结果：index有Document/Task状态和日志，不创建虚假Thread/Run/RunEvent；空文失败不要求不存在的run.failed。
- 优先级：P1
- 用例类型：契约
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：TaskKind；文档服务；Index Handler；ORM
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-EVT-008__normal_document`：通过，输出：{"document_id":"[关联ID见证据]","document_status":"indexed","task":{"task_id":"[关联ID见证据]","kind":"index_document","run_id":null,"document_id":"[关联ID见证据]","state":"succeeded","last_error_code":null},"before":{"threads":52,"runs":59,"events":487},"after":{"threads":5…（完整输出见原证据）；`TP-EVT-008__empty_document`：通过，输出：{"document_id":"[关联ID见证据]","document_status":"failed","task":{"task_id":"[关联ID见证据]","kind":"index_document","run_id":null,"document_id":"[关联ID见证据]","state":"failed","last_error_code":"EMPTY_DOCUMENT"},"before":{"threads":52,"runs":59,"events":487},"after":{"th…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/evt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/evt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category evt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-evt.log`及`categories/evt.json`，按`EVT_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### SSE_001：SSE格式及Header游标优先级

- 用例编号：`SSE_001`
- 对应测试点：`TP-SSE-001`：SSE消息格式；`TP-SSE-003`：Last-Event-ID优先级
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；已完成有中文Event的Run，客户端限时并finally关闭
- 测试数据要求：query游标q/Header h不同；有效h、负h、非法h；无Header
- 测试流程：逐组连接，解析id/event/data并对比普通events对应后缀。
- 预期结果：Content-Type text/event-stream，id=seq/event=type/data完整v1 JSON中文保真，event_id/内容同DB；Header优先，负/非法Header归0；无Header用query。普通events非法422不强加给SSE归0规则。
- 优先级：P1
- 用例类型：契约/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：runs.py：stream_events.generator；event_to_dict；runs.py：last_event_id/max/int
- 实际测试结果：已执行子项通过；第一轮通过6/失败0/受限0，第二轮通过6/失败0/受限0。子项记录：`TP-SSE-001__wire_format`：通过，输出：{"run_id":"[关联ID见证据]","stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[9项]"},"chinese_preserved":true,"trace":"evidence/sse/SSE_001-wire.json"}；`TP-SSE-003__valid_header_wins`：通过，输出：{"run_id":"[关联ID见证据]","query":1,"header":"3","effective_cursor":3,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[6项]"}}；`TP-SSE-003__zero_header_wins`：通过，输出：{"run_id":"[关联ID见证据]","query":3,"header":"0","effective_cursor":0,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[9项]"}}；`TP-SSE-003__negative_header_zero`：通过，输出：{"run_id":"[关联ID见证据]","query":3,"header":"-1","effective_cursor":0,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[9项]"}}；`TP-SSE-003__invalid_header_zero`：通过，输出：{"run_id":"[关联ID见证据]","query":3,"header":"bad-cursor","effective_cursor":0,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[9项]"}}；`TP-SSE-003__absent_header_query`：通过，输出：{"run_id":"[关联ID见证据]","query":2,"header":"未发送","effective_cursor":2,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[7项]"}}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sse.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sse.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sse`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sse.log`及`categories/sse.json`，按`SSE_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### SSE_002：补历史衔接实时事件无缺口

- 用例编号：`SSE_002`
- 对应测试点：`TP-SSE-002`：首连补历史后观察新事件
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1历史可测；历史读取/新追加交界需E2屏障
- 测试数据要求：连接前有事件、连接建立中追加、建立后再追加
- 测试流程：从中间游标订阅；控制三时段真实append/执行；与最终DB序列比对。
- 预期结果：历史后缀后继续完整交付新事件，无交界缺口、只来自DB；局部历史通过不证明竞争交界已验证。
- 优先级：P0
- 用例类型：功能/并发
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：runs.py：generator；Journal.list_events
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限1，第二轮通过2/失败0/受限1。子项记录：`TP-SSE-002__historical_suffix`：通过，输出：{"run_id":"[关联ID见证据]","after_seq":4,"stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[5项]"},"limitation":"历史后缀，不含读取/追加竞争屏障"}；`TP-SSE-002__history_then_worker_events`：通过，输出：{"run_id":"[关联ID见证据]","stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[6项]"},"trace":"evidence/sse/SSE_002-live.json","limitation":"Worker在历史已交付后启动；没有历史读取瞬间的竞争屏障"}；`TP-SSE-002__read_append_boundary`：受限未执行，输出：E2 历史SELECT/新append/交付边界的确定性屏障尚未准备；历史后再启动Worker不替代该竞态。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sse.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sse.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sse`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sse.log`及`categories/sse.json`，按`SSE_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### SSE_003：SSE断开不能取消执行

- 用例编号：`SSE_003`
- 对应测试点：`TP-SSE-004`：客户端断开不取消
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1可查断流无取消；需E2阻塞以确保断开时仍执行中
- 测试数据要求：可控未完成Run、首片后断开客户端
- 测试流程：断开后不调用cancel；放行任务并查询最终；新客户端从最后seq补放。
- 预期结果：Run继续原身份成功、无cancel_requested_at/run.cancelled；最终Message/事件完整。快速Mock完成后才断开只给局部证据。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：runs.py：request.is_disconnected；cancel_run仅由cancel路由调用
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-SSE-004__disconnect_while_queued`：通过，输出：{"run_id":"[关联ID见证据]","task_id":"[关联ID见证据]","last_seq":1,"disconnected":{"status":200,"eof":false,"timed_out":false,"stream_error":null,"frames":"[1项]"},"reconnect":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[7项]"},"limitation":"断…（完整输出见原证据）；`TP-SSE-004__disconnect_after_first_delta_running`：受限未执行，输出：E2 首delta后可控未完成Run及慢Provider屏障尚未准备；queued断流证据不替代生成中断开。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sse.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sse.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sse`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sse.log`及`categories/sse.json`，按`SSE_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### SSE_004：终态流正常关闭与空后缀资源边界

- 用例编号：`SSE_004`
- 对应测试点：`TP-SSE-006`：发送终态后关闭；`TP-SSE-007`：游标已越过终态
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1成功/取消可测；failed需E2真实Run失败
- 测试数据要求：各terminal从0；成功Run从N及N+10
- 测试流程：有界订阅并等待EOF；末尾游标无新事件分支记录连接是否仍轮询；关闭客户端。
- 预期结果：实际发送terminal后结束、无第二终态；已终态空后缀也应有界结束，不无限占连接。后者为补充资源风险，当前while空轮询记差异；failed缺条件单列blocked。
- 优先级：P1
- 用例类型：功能/边界
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：runs.py：terminal类型判断；runs.py：generator while True
- 实际测试结果：不通过；第一轮通过2/失败2/受限1，第二轮通过2/失败2/受限1。子项记录：`TP-SSE-006__succeeded`：通过，输出：{"run_id":"[关联ID见证据]","terminal":"succeeded","stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[9项]"}}；`TP-SSE-006__cancelled`：通过，输出：{"run_id":"[关联ID见证据]","terminal":"cancelled","stream":{"status":200,"eof":true,"timed_out":false,"stream_error":null,"frames":"[3项]"}}；`TP-SSE-006__failed`：受限未执行，输出：E2 真实Run永久失败驱动尚未准备；Index失败无RunEvent；`TP-SSE-007__at_terminal`：失败，输出：Run [关联ID见证据] 已终态空后缀未在3500ms内EOF，仍占用轮询连接；证据evidence/sse/SSE_004-at_terminal.json；`TP-SSE-007__beyond_terminal`：失败，输出：Run [关联ID见证据] 已终态空后缀未在3500ms内EOF，仍占用轮询连接；证据evidence/sse/SSE_004-beyond_terminal.json。原因：类型1（已测/审查确认）：仅实际yield终态事件才关闭；终态后空后缀仍轮询，N/N+10游标3500ms不EOF。 定位：`backend/api/routes/runs.py:65 stream_events.generator`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sse.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sse.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sse`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sse.log`及`categories/sse.json`，按`SSE_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### SSE_005：不存在Run在SSE握手前拒绝

- 用例编号：`SSE_005`
- 对应测试点：`TP-SSE-008`：SSE握手前对象校验
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；未创建UUID，普通客户端记录HTTP headers
- 测试数据要求：不存在Run；跨owner另OWN_001
- 测试流程：请求流并记录初始HTTP及正文/关闭原因。
- 预期结果：开始StreamingResponse前404/RUN_NOT_FOUND，无200后抛错断流、数据/堆栈/路径泄漏；与普通事件404分别断言。
- 优先级：P0
- 用例类型：权限/异常
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：runs.py：stream_events；Run服务：get_run_events
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-SSE-008__missing_run_handshake`：失败，输出：不存在Run SSE握手HTTP应404，实际200；证据evidence/sse/SSE_005-handshake.json 200 !== 404 。原因：类型1（已测/审查确认）：Run/owner校验推迟至generator，StreamingResponse已200握手。 定位：`backend/api/routes/runs.py:51 stream_events、:71 generator；backend/application/runs.py:78 get_run_events`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sse.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sse.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sse`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sse.log`及`categories/sse.json`，按`SSE_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

### 4.8 浏览器工作台

主归属：frontend-workspace。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### FE_001：合法同源路由与会话创建选择

- 用例编号：`FE_001`
- 对应测试点：`TP-FE-001`：浏览器API与SSE路由一致；`TP-FE-002`：创建与选择会话
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3现有Chromium；普通浏览器安全策略
- 测试数据要求：两Thread和一个安全txt；本次实际FrontendUrl/BaseUrl
- 测试流程：打开页面创建/选择会话，上传和订阅；记录请求目标及所见历史。
- 预期结果：HTTP/上传/SSE抵达同project，Thread列表出现服务端ID、选择历史正确；采用测试Vite同源代理合法，不禁用CORS。根Compose跨域缺口另DEP_005静态及可选隔离配置诊断，不能称根部署已修复。
- 优先级：P0
- 用例类型：功能/接口
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：前端HTTP：baseUrl；事件流：EventSource；vite.config；Compose；App无CORSMiddleware；ThreadList；thread store：addThread/loadThreads/selectThread；前端页面
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-FE-001__browser-http-upload-sse`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","document_id":"[关联ID见证据]","request_targets":"[12项，明细见证据]"}；`TP-FE-002__browser-create-select`：通过，输出：{"created_thread_id":"[关联ID见证据]","selected_thread_ids":["[关联ID见证据]","[关联ID见证据]"],"server_titles_visible":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_002：按钮与Ctrl+Enter各只提交一次

- 用例编号：`FE_002`
- 对应测试点：`TP-FE-003`：发送与用户消息呈现
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3；本用例会话；监测网络请求
- 测试数据要求：空输入、未选会话、中文问题；按钮和Ctrl+Enter独立分支
- 测试流程：检查禁用；输入后各发送一次并读用户Message/请求数。
- 预期结果：空/未选不能提交；每操作一个消息请求与一条用户消息，角色和正文与服务端一致，不重复提交。
- 优先级：P1
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：前端页面：ask/composer；thread store：ask
- 实际测试结果：已执行子项通过；第一轮通过4/失败0/受限0，第二轮通过4/失败0/受限0。子项记录：`TP-FE-003__browser-no-thread`：通过，输出：{"submit_count":0,"active_thread":null}；`TP-FE-003__browser-empty-input`：通过，输出：{"thread_id":"[关联ID见证据]","submit_count":0}；`TP-FE-003__browser-button`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","user_message_id":"[关联ID见证据]","submit_count":1,"visible_user_count":1}；`TP-FE-003__browser-ctrl-enter`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","user_message_id":"[关联ID见证据]","submit_count":1,"visible_user_count":1}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_003：未完成assistant增量可见

- 用例编号：`FE_003`
- 对应测试点：`TP-FE-004`：执行中回答投影
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2+E3；待补分片慢Run，无预存assistant
- 测试数据要求：片1已持久、片2等待
- 测试流程：发送后在terminal前观察消息区域，比较Event与显示内容。
- 预期结果：片1到达即显示运行中回答而非等已有最终assistant；不保存临时投影为终态事实。当前只查已有assistant的代码差异应失败。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：thread store：appendAssistantDelta；前端页面：onEvent；MessageTimeline
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败1/受限1，第二轮通过0/失败1/受限1。子项记录：`TP-FE-004__component-partial-answer`：失败，输出：真实生产组件断言failed：AssertionError: expected [] to deeply equal [ '首片可见' ] 'failed' !== 'passed' ；`TP-FE-004__persistent-slow-stream`：受限未执行，输出：未接入真实慢Provider/Worker持久化分片屏障；已有真实组件断言验证前端缺失。原因：类型1（已测/审查确认）：只追加已存在assistant，最终Message未建时丢弃delta，没有Run临时回答投影。 定位：`frontend/src/stores/thread.ts:31 appendAssistantDelta；frontend/src/components/MessageTimeline.vue:15`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### FE_004：不刷新获取最终答案与引用

- 用例编号：`FE_004`
- 对应测试点：`TP-FE-005`：terminal后最终消息恢复
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3；本用例已有证据文档
- 测试数据要求：正常问答
- 测试流程：等待API持久成功但不刷新页面；观察最终正文/引用和assistant数量。
- 预期结果：自动显示服务端最终正文与引用、恰一assistant，不只时间线出现terminal；当前缺终态重新读取不能被手工刷新掩盖。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：前端页面：事件回调；thread store；MessageTimeline
- 实际测试结果：不通过；第一轮通过0/失败2/受限0，第二轮通过0/失败2/受限0。子项记录：`TP-FE-005__browser-no-refresh`：失败，输出：无刷新页面未自动显示持久最终答案，或重放增量污染最终正文；`TP-FE-005__component-terminal-refresh`：失败，输出：真实生产组件断言failed：AssertionError: 终态到达后应重新读取服务器最终Message: expected 0 to be greater than 0 'failed' !== 'passed' 。原因：类型1（已测/审查确认）：提交后只即时读Thread一次，终态事件后不读取最终答案/引用。 定位：`frontend/src/pages/WorkspacePage.vue:36 ask回调；frontend/src/stores/thread.ts:25 ask`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_005：实时状态和页面取消正确Run

- 用例编号：`FE_005`
- 对应测试点：`TP-FE-006`：实时Run状态投影；`TP-FE-015`：页面取消操作
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2+E3；待补运行中屏障；分别成功/取消Run
- 测试数据要求：queued/running/terminal及停止按钮
- 测试流程：发送后按阶段比较API与面板；独立分支点击停止并观察cancel请求/按钮。
- 预期结果：面板从持久事实更新，非终态可停止且调用当前run_id；cancelled后按钮移除，无迟到成功。仅按钮存在或Run store收事件不算状态更新通过。
- 优先级：P0
- 用例类型：功能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：run store：observe/append；RunTimeline；RunTimeline：emit(cancel)；run store：cancel；api/runs.ts
- 实际测试结果：暂不可完整动态验证；第一轮通过1/失败2/受限2，第二轮通过1/失败2/受限2。子项记录：`TP-FE-006__component-running`：失败，输出：真实生产组件断言failed：AssertionError: expected 'queued' to be 'running' // Object.is equality 'failed' !== 'passed' ；`TP-FE-006__component-succeeded`：失败，输出：真实生产组件断言failed：AssertionError: expected 'running' to be 'succeeded' // Object.is equality 'failed' !== 'passed' ；`TP-FE-015__component-cancel`：通过，输出：{"vitest_title":"FE_005__TP-FE-015__component-cancel","status":"passed","duration_ms":10.854800000000068,"scope":"真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收"}；`TP-FE-006__persistent-state-stages`：受限未执行，输出：无真实运行中屏障，Mock运行过快无法可靠抓取所有阶段；受控真实组件阶段已逐项执行；`TP-FE-015__persistent-running-cancel-race`：受限未执行，输出：无Worker模型/最终提交竞争屏障，组件取消请求不证明后端竞态。原因：类型1（已测/审查确认）：append仅更新events，不刷新current状态；RunTimeline不显示last_error_code。 定位：`frontend/src/stores/run.ts:9 observe、:15 append；frontend/src/components/RunTimeline.vue:10`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### FE_006：请求和异步执行失败可诊断

- 用例编号：`FE_006`
- 对应测试点：`TP-FE-007`：失败交互可诊断
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1+E3；请求错误可测；Run异步失败待E2
- 测试数据要求：不存在会话请求；可控永久失败Run
- 测试流程：分别触发请求失败及异步失败；观察提示、面板、时间线。
- 预期结果：安全稳定错误提示，异步failed和原因可见，不一直running或误成功；不能仅catch HTTP错误宣称异步失败交互完成。
- 优先级：P1
- 用例类型：异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：前端页面：error；RunTimeline；run store；前端HTTP
- 实际测试结果：不通过；第一轮通过1/失败2/受限1，第二轮通过1/失败2/受限1。子项记录：`TP-FE-007__browser-request-failure`：通过，输出：{"thread_id":"[关联ID见证据]","status":404,"safe_message":"Thread 不存在","submitted_run_count":0}；`TP-FE-007__component-async-failure`：失败，输出：真实生产组件断言failed：AssertionError: expected 'running' to be 'failed' // Object.is equality 'failed' !== 'passed' ；`TP-FE-007__component-failure-reason`：失败，输出：真实生产组件断言failed：AssertionError: expected 'RUNfailedKNOWLEDGE文档索引 上传 还没有文档' to contain 'PROVIDER_UNAVAILABLE' 'failed' !== 'passed' ；`TP-FE-007__persistent-permanent-failure`：受限未执行，输出：未提供本次隔离Worker永久失败Provider驱动；真实组件异步failed投影已独立断言。原因：类型1（已测/审查确认）：append仅更新events，不刷新current状态；RunTimeline不显示last_error_code。 定位：`frontend/src/stores/run.ts:9 observe、:15 append；frontend/src/components/RunTimeline.vue:10`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### FE_007：时间线seq去重排序作用域

- 用例编号：`FE_007`
- 对应测试点：`TP-FE-008`：Event时间线去重排序
- 当前可验证状态：可验证·本机动态
- 前置条件：E0现有store可驱动；浏览器E3；无需新产品接口
- 测试数据要求：同Run seq3/1/2/2；另Run seq1
- 测试流程：隔离前端驱动调用真实store append，不改生产API；比对events顺序；浏览器正常时间线对照。
- 预期结果：同Run按1/2/3且seq2一次，切换Run不误删另seq1；此结果仅证明事件去重，不证明正文去重。驱动文件后续编写，本轮不执行。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：run store：append/events；RunTimeline
- 实际测试结果：已执行子项通过；第一轮通过3/失败0/受限0，第二轮通过3/失败0/受限0。子项记录：`TP-FE-008__browser-normal-timeline`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","seq":"[7项，明细见证据]"}；`TP-FE-008__component-seq-order`：通过，输出：{"vitest_title":"FE_007__TP-FE-008__component-seq-order","status":"passed","duration_ms":7.833300000000008,"scope":"真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收"}；`TP-FE-008__component-run-scope`：通过，输出：{"vitest_title":"FE_007__TP-FE-008__component-run-scope","status":"passed","duration_ms":8.286200000000008,"scope":"真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_007__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_008：重放与SSE同delta只投影一次

- 用例编号：`FE_008`
- 对应测试点：`TP-FE-009`：答案重复投影防护
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2+E3；待补replay/SSE交错驱动
- 测试数据要求：同seq delta重复；已含最终正文Thread重放
- 测试流程：控制两来源同事件同时/倒序交付；读取可见正文与服务端最终原文。
- 预期结果：每seq delta只应用一次，最终正文不翻倍；已有最终Message不追加历史增量；Run store去重不能替Message投影作保证。
- 优先级：P0
- 用例类型：并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：前端事件流：replay+EventSource；前端页面：回调；thread store
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败3/受限1，第二轮通过0/失败3/受限1。子项记录：`TP-FE-009__component-replay-stream-overlap`：失败，输出：真实生产组件断言failed：AssertionError: expected '已有首片唯一片段唯一片段' to be '已有首片唯一片段' // Object.is equality 'failed' !== 'passed' ；`TP-FE-009__component-stream-after-replay`：失败，输出：真实生产组件断言failed：AssertionError: expected '已有首片唯一片段唯一片段' to be '已有首片唯一片段' // Object.is equality 'failed' !== 'passed' ；`TP-FE-009__component-final-history`：失败，输出：真实生产组件断言failed：AssertionError: expected '已持久最终正文已持久最终正文' to be '已持久最终正文' // Object.is equality 'failed' !== 'passed' ；`TP-FE-009__persistent-replay-overlap`：受限未执行，输出：未提供真实Worker分片与replay/SSE屏障；真实组件同seq重叠与历史最终Message已独立断言。原因：类型1（已测/审查确认）：时间线去重没有阻止页面无条件追加delta；completed Message也允许叠加历史delta。 定位：`frontend/src/pages/WorkspacePage.vue:37 ask回调；frontend/src/stores/run.ts:15 append；frontend/src/stores/thread.ts:31 appendAssistantDelta`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

#### FE_009：断网后补放与不取消

- 用例编号：`FE_009`
- 对应测试点：`TP-FE-010`：断线重连补放
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1+E3终态重放重连入口可检查；活跃断网需E2
- 测试数据要求：最后处理seq=m后网络中断；离线期间新增事件
- 测试流程：正常浏览器网络断开/恢复；观察自动或明确重连入口、游标、时间线和正文；读Run未取消。
- 预期结果：从m继续、补齐遗漏、无重复正文/事件且不cancel；当前onerror close无重连应失败。terminal路径只能验证入口缺失，不能证明活跃续流。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：前端事件流：openRunStream/source.onerror；run store
- 实际测试结果：不通过；第一轮通过2/失败2/受限2，第二轮通过2/失败2/受限2。子项记录：`TP-FE-010__browser-disconnect-no-cancel`：通过，输出：{"run_id":"[关联ID见证据]","before_status":"queued","after_status":"queued","cancel_requests":0,"last_processed_seq":2,"native_disconnect":{"severed_socket_count":1,"native_streams":"[1项]"},"transport_connections":[{"path":"/api/v1/runs/[关联ID见证据]/events/stream","af…（完整输出见原证据）；`TP-FE-010__browser-reconnect-entry`：失败，输出：真实活动SSE error后没有自动重连或可用的手动重连入口；真实断线证据：evidence/fe/FE_009-reconnect-native-disconnect.json；`TP-FE-010__component-reconnect-cursor`：失败，输出：真实生产组件断言failed：AssertionError: SSE错误后应存在自动重连或可用的手动重连入口: expected undefined to be defined 'failed' !== 'passed' ；`TP-FE-010__component-disconnect-no-cancel`：通过，输出：{"vitest_title":"FE_009__TP-FE-010__component-disconnect-no-cancel","status":"passed","duration_ms":6.944299999999657,"scope":"真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收"}；`TP-FE-010__persistent-active-network-resume`：受限未执行，输出：缺真实慢Run分片屏障；queued受控传输服务断开与组件检查不能代替running分片完整续流；`TP-FE-010__ordinary-browser-offline`：受限未执行，输出：Chromium setOffline对已建立空闲SSE未触发原生error，普通离线前置不足；受控透传socket断开子项不能代替此场景。原因：类型1（已测/审查确认）：error即close终止浏览器自动重试，页面没有重连入口/编排；受控真实socket断开及组件子项均失败。 定位：`frontend/src/events/run-event-stream.ts:27 openRunStream.onerror；frontend/src/components/RunTimeline.vue:10`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_009__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### FE_010：刷新及frontend重启恢复历史

- 用例编号：`FE_010`
- 对应测试点：`TP-FE-011`：刷新历史恢复；`TP-FE-018`：前端进程重启恢复
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3；自建已完成会话/文档，记录服务端事实
- 测试数据要求：清内存/浏览器存储后新上下文；frontend重启
- 测试流程：新上下文打开并选择Thread；重启本次frontend后重新打开选择；比对正文/引用/文档。
- 预期结果：API恢复相同ID/事实，不依Pinia/local缓存、无重复提交；Run时间线恢复另FE_011，不把消息历史通过当全部恢复。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：前端页面：bootstrap；thread store：loadThreads/selectThread；Compose：frontend；前端页面bootstrap；stores
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-FE-011__fresh-context`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","message_ids":["[关联ID见证据]","[关联ID见证据]"],"citation_count":5,"document_id":"[关联ID见证据]","document_status":"indexed","new_submission_count":0,"frontend_restarted":false}；`TP-FE-018__frontend-restart`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","message_ids":["[关联ID见证据]","[关联ID见证据]"],"citation_count":5,"document_id":"[关联ID见证据]","document_status":"indexed","new_submission_count":0,"frontend_restarted":true}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_010__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_011：刷新恢复Run时间线与继续订阅

- 用例编号：`FE_011`
- 对应测试点：`TP-FE-012`：刷新运行时间线恢复
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1+E3已terminal路径可测；queued/running刷新续订需E2
- 测试数据要求：成功历史Run及活动Run各会话
- 测试流程：刷新后选择会话；检查状态/Event/replay/订阅；活跃分支放行后观察终态。
- 预期结果：自动恢复相应Run及历史Event，活跃继续订阅，不需发送新问题；当前bootstrap未observe缺失单独failed，未有慢任务时活跃子项blocked。
- 优先级：P0
- 用例类型：恢复
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：前端页面：bootstrap；run store：observe
- 实际测试结果：不通过；第一轮通过0/失败2/受限1，第二轮通过0/失败2/受限1。子项记录：`TP-FE-012__browser-terminal-restore`：失败，输出：刷新仅恢复Message，未恢复Run状态/事件时间线；`TP-FE-012__component-active-restore`：失败，输出：真实生产组件断言failed：AssertionError: expected undefined to be 'run-A' // Object.is equality 'failed' !== 'passed' ；`TP-FE-012__persistent-active-reload`：受限未执行，输出：无真实活动Run屏障；terminal恢复与真实组件活动恢复已独立断言。原因：类型1（已测/审查确认）：恢复仅读Thread/Document，不observe对应Run、补Journal或续订活动流。 定位：`frontend/src/pages/WorkspacePage.vue:45 bootstrap、:22 selectThread；frontend/src/stores/thread.ts:12 selectThread`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_011__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### FE_012：上传后自动更新索引状态

- 用例编号：`FE_012`
- 对应测试点：`TP-FE-013`：文档上传状态更新
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3；正常txt与空文各自上传
- 测试数据要求：文件原名、上传初始状态、终态indexed/failed
- 测试流程：上传后不刷新浏览器，API独立观察终态，再比页面。
- 预期结果：页面原名/初始状态正确，自动显示indexed或failed及安全原因；请求loading结束不等于索引完成，当前无轮询应记差异。
- 优先级：P1
- 用例类型：功能/异常
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：documents store：upload/load；DocumentUploader
- 实际测试结果：不通过；第一轮通过2/失败2/受限0，第二轮通过2/失败2/受限0。子项记录：`TP-FE-013__browser-indexed-initial`：通过，输出：{"document_id":"[关联ID见证据]","initial_status":"uploaded"}；`TP-FE-013__browser-indexed-automatic-terminal`：失败，输出：文档页面仍为uploaded，未自动更新为indexed；`TP-FE-013__browser-failed-initial`：通过，输出：{"document_id":"[关联ID见证据]","initial_status":"uploaded"}；`TP-FE-013__browser-failed-automatic-terminal`：失败，输出：文档页面仍为uploaded，未自动更新为failed。原因：类型1（已测/审查确认）：upload只保留初始响应，没有通知或有界刷新。 定位：`frontend/src/stores/documents.ts:8 load、:11 upload；frontend/src/components/DocumentUploader.vue:26`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_012__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_013：引用可读且可展开

- 用例编号：`FE_013`
- 对应测试点：`TP-FE-014`：引用展示与展开
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1+E3；选择由API准备的已成功有引用会话
- 测试数据要求：citation filename/offset和真实证据
- 测试流程：读最终Message引用，观察标签并尝试展开信息，对照身份/位置。
- 预期结果：标签与真实citation一致，并有可用展开信息；当前仅span无展开是实现缺口，不能算完整通过；不要求完整本地文档预览工具。
- 优先级：P1
- 用例类型：功能
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：MessageTimeline：citation-list；Message.citations类型
- 实际测试结果：不通过；第一轮通过1/失败1/受限0，第二轮通过1/失败1/受限0。子项记录：`TP-FE-014__browser-citation-label`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","message_ids":["[关联ID见证据]","[关联ID见证据]"],"citation_count":5}；`TP-FE-014__browser-citation-expand`：失败，输出：引用只有静态标签，没有可展开入口 false !== true 。原因：类型1（已测/审查确认）：引用只有静态标签无可展开入口；可读标签通过。 定位：`frontend/src/components/MessageTimeline.vue:18 citation-list`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_013__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### FE_014：健康面板实现与安全展示

- 用例编号：`FE_014`
- 对应测试点：`TP-FE-016`：健康状态展示
- 当前可验证状态：可验证·本机静态
- 前置条件：E0+E3；当前没有Worker/DB组件，可浏览器观察缺失
- 测试数据要求：健康响应的API/Worker/DB三对象
- 测试流程：审查client与页面并打开当前UI；核对是否存在三个独立事实展示。
- 预期结果：应区分ready/degraded/unknown且不含secret；当前只error关联API点须记未实现。组件缺失可本机确认，但故障状态动态完整验收暂不可做。
- 优先级：P1
- 用例类型：功能/架构
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：前端页面：connection-dot；frontend/src/api/无health client
- 实际测试结果：不通过；第一轮通过0/失败1/受限1，第二轮通过0/失败1/受限1。子项记录：`TP-FE-016__browser-health-panels`：失败，输出：健康面板缺少独立事实展示：API/Worker/DB + actual - expected + [ + 'API', + 'Worker', + 'DB' + ] - [] ；`TP-FE-016__health-fault-states`：受限未执行，输出：页面健康组件缺失；完整故障态动态展示待产品补齐后准备对应服务故障条件。原因：类型1（已测/审查确认）：没有health client和API/Worker/DB独立事实展示，点颜色只依error是否为空。 定位：`frontend/src/pages/WorkspacePage.vue:66 connection-dot、:45 bootstrap`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category fe`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-fe.log`及`categories/fe.json`，按`FE_014__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### FE_015：切换Thread不串旧Run投影

- 用例编号：`FE_015`
- 对应测试点：`TP-FE-017`：会话切换观察隔离
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2+E3；待补A慢Run；B独立历史
- 测试数据要求：A首delta后暂停，B已选，A迟到事件
- 测试流程：运行A后切B，再放行A；检查当前面板/正文/网络订阅，切回A核对历史。
- 预期结果：B不挂A Run或正文，旧流及时关闭/隔离、B面板对应B事实；切回能读A实际结果，无污染或遗漏。
- 优先级：P1
- 用例类型：边界/并发
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：前端页面：selectThread/stream；thread/run store
- 实际测试结果：暂不可完整动态验证；第一轮通过1/失败1/受限1，第二轮通过1/失败1/受限1。子项记录：`TP-FE-017__component-switch-isolation`：失败，输出：真实生产组件断言failed：AssertionError: expected { old_stream_closed: false, …(2) } to deeply equal { old_stream_closed: true, …(2) } 'failed' !== 'passed' ；`TP-FE-017__component-switch-back-history`：通过，输出：{"vitest_title":"FE_015__TP-FE-017__component-switch-back-history","status":"passed","duration_ms":10.999899999999798,"scope":"真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收"}；`TP-FE-017__persistent-delayed-thread-switch`：受限未执行，输出：无真实持久慢Run屏障；真实Workspace组件旧流关闭与B投影隔离已独立断言。原因：类型1（已测/审查确认）：切Thread未关旧stream或重建观察，回调缺Run/Thread作用域隔离。 定位：`frontend/src/pages/WorkspacePage.vue:22 selectThread、:36 ask回调；frontend/src/stores/run.ts:15 append`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/fe.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/fe.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.9 安全与性能补充

主归属：fault-safety（XSS归 frontend-workspace，提交性能归 thread-run-api）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### SEC_001：上传原文件不被静态HTTP暴露

- 用例编号：`SEC_001`
- 对应测试点：`TP-SEC-001`：上传目录非静态暴露
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；本用例独立上传含安全哨兵文档
- 测试数据要求：/data/uploads、/uploads、已知测试storage_key猜测路径
- 测试流程：对API/frontend请求候选直链；检查状态/响应内容，不枚举宿主任意路径。
- 预期结果：不能得到原始字节或哨兵正文，非公开文件接口；卷共享不等于StaticFiles暴露。
- 优先级：P0
- 用例类型：安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：App.include_router无静态上传路由；Compose volumes
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-SEC-001__static-paths`：通过，输出："[6项，明细见证据]"。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sec.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sec.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sec`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sec.log`及`categories/sec.json`，按`SEC_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### SEC_002：Storage拒绝路径及symlink逃逸

- 用例编号：`SEC_002`
- 对应测试点：`TP-SEC-002`：Storage读路径防逃逸
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0安全函数驱动可准备，当前未备；Linux容器临时哨兵，不访问真实宿主敏感文件
- 测试数据要求：../、绝对key、上传根外symlink及正常key
- 测试流程：仅本次tmp建立外部哨兵/链接；调用真实Storage.read比较拒绝/返回；删本次fixture。
- 预期结果：逃逸均拒绝不返回哨兵，正常key可读；resolve后仍限定upload根，不能只字面检查../。
- 优先级：P0
- 用例类型：安全
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Storage.read：resolve/parents校验
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-SEC-002__traversal-symlink`：通过，输出：{"normal":true,"rows":[{"kind":"../outside.txt","rejected":true},{"kind":"absolute","rejected":true},{"kind":"link.txt","rejected":true}]}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sec.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sec.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sec`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sec.log`及`categories/sec.json`，按`SEC_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### SEC_003：Markdown清洗阻止XSS

- 用例编号：`SEC_003`
- 对应测试点：`TP-SEC-003`：Markdown XSS清洗
- 当前可验证状态：可验证·本机动态
- 前置条件：E1+E3；正常浏览器，安全测试哨兵，无外网
- 测试数据要求：用户Markdown与可显示的Mock证据回答含script/onerror/javascript链接；正常标题/代码/链接对照
- 测试流程：经真实输入生成用户消息及含攻击字符串的Mock证据回答，API先确认原Markdown确含样例；选择/刷新该持久会话使两角色都经过真实组件渲染；监听哨兵变量/请求/弹窗并检查DOM。
- 预期结果：两角色攻击都不执行、危险属性/URL删除，正常内容显示；不只检查DOMPurify调用。必要刷新只为读取已持久正文，不当成FE_004无需刷新能力通过；样例未进入assistant原文或未渲染则记该子项未覆盖，不将空白判清洗通过。
- 优先级：P0
- 用例类型：安全/浏览器
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：MessageTimeline：renderMarkdown/v-html
- 实际测试结果：已执行子项通过；第一轮通过4/失败0/受限0，第二轮通过4/失败0/受限0。子项记录：`TP-SEC-003__user-safety`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","role":"user","part":"safety","attack_original_confirmed":true,"actual":"安全哨兵未执行或对应正常格式保留，按本子项独立判断"}；`TP-SEC-003__user-normal-format`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","role":"user","part":"normal-format","attack_original_confirmed":true,"actual":"安全哨兵未执行或对应正常格式保留，按本子项独立判断"}；`TP-SEC-003__assistant-safety`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","role":"assistant","part":"safety","attack_original_confirmed":true,"actual":"安全哨兵未执行或对应正常格式保留，按本子项独立判断"}；`TP-SEC-003__assistant-normal-format`：通过，输出：{"thread_id":"[关联ID见证据]","run_id":"[关联ID见证据]","role":"assistant","part":"normal-format","attack_original_confirmed":true,"actual":"安全哨兵未执行或对应正常格式保留，按本子项独立判断"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sec.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sec.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sec`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sec.log`及`categories/sec.json`，按`SEC_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### SEC_004：错误响应、事实与日志不含敏感哨兵

- 用例编号：`SEC_004`
- 对应测试点：`TP-SEC-004`：API错误输出脱敏；`TP-SEC-005`：持久事实与日志脱敏
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1缺对象/DB错误可测；Provider/存储哨兵异常待E2/E4
- 测试数据要求：仅非真实KEY_SENTINEL及测试路径/连接串哨兵，分请求与异常源
- 测试流程：触发缺对象/DB/解析/存储/Provider错误；扫描响应、snapshot、Event、Message、默认日志/前端。
- 预期结果：无Secret/堆栈/宿主路径/凭证原文；422与ApplicationError分别记录格式，不声称都envelope。允许用户正文/证据不误作secret；截断str(exc)不等于脱敏，未触发分支不能通过。
- 优先级：P0
- 用例类型：安全/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：App.exception_handler；HTTP Schema；应用errors.py；Runtime._record_run_failure/logger.exception；Handler schedule_retry；snapshot_json
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限2，第二轮通过2/失败0/受限2。子项记录：`TP-SEC-004__safe-errors`：通过，输出：{"missing":{"status":404,"headers":{"date":"Wed, 07 Oct 2026 08:03:33 GMT","server":"uvicorn"}},"invalid":{"status":422,"headers":{"date":"Wed, 07 Oct 2026 08:03:33 GMT","server":"uvicorn"}}}；`TP-SEC-005__normal-facts`：通过，输出：{"run_id":"[关联ID见证据]","normal_secret_leak":false}；`TP-SEC-004__exception-sentinel`：受限未执行，输出：E2/E4异常驱动尚未完成；正常事实无密码不代表异常str(exc)已脱敏。DB故障响应另HLT_002真实执行。；`TP-SEC-005__exception-sentinel`：受限未执行，输出：E2/E4异常驱动尚未完成；正常事实无密码不代表异常str(exc)已脱敏。DB故障响应另HLT_002真实执行。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sec.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sec.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sec`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sec.log`及`categories/sec.json`，按`SEC_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### SEC_005：全量读取上传风险审查

- 用例编号：`SEC_005`
- 对应测试点：`TP-SEC-006`：超大上传内存风险
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；不实施宿主内存耗尽，动态资源测量待E2受控限额
- 测试数据要求：HTTP读取到大小检查的代码路径，10MiB与超限逻辑
- 测试流程：追踪await file.read、请求体限制与存储校验先后，检查是否存在读前上限/有界读取。
- 预期结果：应有有界读取/请求体拒绝；当前全量读后检查须记风险，DOC_003阈值通过不能替代内存边界安全。
- 优先级：P1
- 用例类型：边界/安全
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：documents.py：await file.read；create_document大小检查
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-SEC-006__bounded-upload-review`：失败，输出：上传函数仍无参数全量read，在大小校验前分配内存 1 !== 0 。原因：类型1（已测/审查确认）：大小检查之前await file.read()无界全量读，AST与源码确认；未开展真实OOM破坏测试。 定位：`backend/api/routes/documents.py:38 upload_document；backend/application/documents.py:34 大小校验`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/sec.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/sec.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category sec`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-sec.log`及`categories/sec.json`，按`SEC_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### PERF_001：消息提交小规模端到端延迟

- 用例编号：`PERF_001`
- 对应测试点：`TP-PERF-001`：提交问题响应时间
- 当前可验证状态：可验证·本机动态
- 前置条件：E1已就绪/单Worker/少量文档；独立会话，避免故障用例并行
- 测试数据要求：预热3次、测量20次非重复Key；冷启动另记录不混样本
- 测试流程：用客户端单调计时从发送到完整201；记录每个Run ID、是否等模型和样本耗时。
- 预期结果：每个有效测量<1秒、成功返回Run ID且不等模型；报告样本、硬件/负载、最小/中位/p95/最大和超标次数，不只平均、不推导生产SLO。
- 优先级：P1
- 用例类型：性能
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：threads.py：post_message；create_message_run
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-PERF-001__20-samples`：通过，输出：{"environment":{"cpus":20,"memory_gib":23.73033905029297,"platform":"win32","mock":true,"worker_count":1,"load":"[3项]"},"samples":"[20项，明细见证据]","stats":{"min":10.889100000000326,"median":16.678100000000995,"p95":23.657599999998638,"max":23.671400000000176,"ove…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/perf.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/perf.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category perf`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-perf.log`及`categories/perf.json`，按`PERF_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### PERF_002：run.started到客户端首执行事件延迟

- 用例编号：`PERF_002`
- 对应测试点：`TP-PERF-002`：开始后首执行事件可见
- 当前可验证状态：暂不可完整动态验证
- 前置条件：E1+E2；待补暂停领取以先连SSE；确认两端时钟误差
- 测试数据要求：预热3次/20个Run，订阅均在启动前
- 测试流程：Worker暂停，提交并先连接SSE；放行领取，以持久run.started时间记录该事件到达延迟。
- 预期结果：每个样本在开始后<2秒可见；不以run.created当执行首包；记录时钟误差/轮询/负载，误差不足判阈值时blocked，不用不同机时钟盲减。
- 优先级：P1
- 用例类型：性能
- 是否适合自动化：是（补齐注明条件后；当前不能完整动态验收）
- 代码依据：Run Handler：run.started；runs.py：generator；Settings.sse_poll_interval
- 实际测试结果：暂不可完整动态验证；第一轮通过0/失败0/受限1，第二轮通过0/失败0/受限1。子项记录：`TP-PERF-002__full-scenario`：受限未执行，输出：需任务启动前SSE订阅屏障、跨容器时钟误差确认及20样本驱动；本輪没有准备，不能以run.created或终态补放冒充首执行事件延迟。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/perf.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/perf.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.10 工程架构与自动化门禁

主归属：静态/质量审查（后续明确门禁接入，不伪装已有manifest分类）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### ARC_001：目录分层与Demo非目标边界

- 用例编号：`ARC_001`
- 对应测试点：`TP-ARC-001`：分层与目录职责；`TP-ARC-004`：Demo非目标入口边界
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；当前目录、路由/页面/依赖可读
- 测试数据要求：仓库职责清单及PRD非目标清单
- 测试流程：追踪路由到application、domain到依赖、前端page/store/client/event；检查是否暴露误导的未完成高级入口。
- 预期结果：前后端分离、业务不在适配入口堆积，domain不依FastAPI/厂商SDK；明确具体耦合差异；无伪生产认证/HITL/任意工具/审核发布等半成品入口，不要求实现非目标。
- 优先级：P2
- 用例类型：架构
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：backend及frontend/src目录；AGENTS目录职责；App注册路由；前端页面；PRD §2.2
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-ARC-001__layer-review`：通过，输出：{"layering":"已审阅路由→application→ORM、Worker直接调用adapter、domain枚举/状态机无FastAPI/厂商依赖；前端page编排/store/API/event/Markdown组件各有边界。Run状态直接赋值绕过状态机、Port缺失在ARC_002及Run并发子项单独记录。","non_goals":"实际仅Thread/Run/Document/health路由及单一Workspace，无HITL/生产登录RBAC/任意工具/审核发布入口。","imports":[…（完整输出见原证据）；`TP-ARC-004__public-scope`：通过，输出：{"paths":"[12项，明细见证据]","review":"实际仅Thread/Run/Document/health路由及单一Workspace，无HITL/生产登录RBAC/任意工具/审核发布入口。"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/arc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/arc.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category arc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-arc.log`及`categories/arc.json`，按`ARC_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### ARC_002：Provider及基础设施替换边界

- 用例编号：`ARC_002`
- 对应测试点：`TP-ARC-002`：Provider可替换接口；`TP-ARC-003`：Queue/Vector/Parser稳定Port
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0；Mock/真实调用签名可核查；完整替换Port尚缺
- 测试数据要求：embed/stream_answer、Queue/Vector/Parser接口和Evidence
- 测试流程：比较同步/异步适配、错误契约和引用身份；追踪handler/application具体adapter imports，查正式Port定义。
- 预期结果：稳定语义和身份贯穿替换；当前duck typing可调用不等于正式Port齐备，Queue/Vector/Parser Port缺失明确记未实现。静态确认缺失可做，完整替换动态暂不可验收；异常协议另RAG用例。
- 优先级：P1
- 用例类型：架构/契约
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：Runtime.__init__；Run Handler._maybe_await；Provider类；Handler imports；backend/domain无ports模块；Vector.Evidence
- 实际测试结果：不通过；第一轮通过1/失败1/受限1，第二轮通过1/失败1/受限1。子项记录：`TP-ARC-002__provider-signatures`：通过，输出：{"mock_embed":"(self, text: str) -> list[float]","real_embed":"(self, text: str) -> list[float]","mock_stream":"(self, question: str, evidence: list[dict[str, str]]) -> collections.abc.AsyncIterator[str]","real_stream":"(self, question: str, evidence: list[dic…（完整输出见原证据）；`TP-ARC-003__ports-review`：失败，输出：QueuePort正式Port缺失；`TP-ARC-003__replacement-integration`：受限未执行，输出：当前正式Port缺失，完整替换适配器及动态验收未准备；缺失确认与完整替换分别记录。。原因：类型1（已测/审查确认）：domain/ports.py及QueuePort等正式Port未落地，编排直接调用具体函数；Provider签名相容不证明完整替换边界。 定位：`backend/workers/runtime.py:12 具体适配器依赖；backend/workers/handlers/run_handler.py:10、index_handler.py:12；docs/adr/001-sesrag-demo-implementation-plan.md:402`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/arc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/arc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category arc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-arc.log`及`categories/arc.json`，按`ARC_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### ARC_003：迁移历史不随ORM隐式漂移

- 用例编号：`ARC_003`
- 对应测试点：`TP-ARC-005`：初始迁移历史稳定性
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；迁移与模型完整可读，不修改文件做实验
- 测试数据要求：0001初始迁移的Schema定义来源
- 测试流程：追踪upgrade/downgrade是否固定历史定义或调用现行Base.metadata。
- 预期结果：历史Schema应稳定自包含；当前create_all/drop_all绑定现行ORM记风险/差异，不假称表存在即迁移演进安全。
- 优先级：P1
- 用例类型：架构/迁移
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：0001_initial_demo.py：Base.metadata.create_all/drop_all
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-ARC-005__migration-history-review`：失败，输出：历史迁移仍依现行Base.metadata.create_all/drop_all。原因：类型1（已测/审查确认）：历史revision使用现行Base.metadata.create_all/drop_all。 定位：`migrations/versions/0001_initial_demo.py:14 upgrade、:20 downgrade`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/arc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/arc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category arc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-arc.log`及`categories/arc.json`，按`ARC_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### ARC_004：技术栈声明与实际使用一致

- 用例编号：`ARC_004`
- 对应测试点：`TP-ARC-006`：声明技术栈与实际依赖
- 当前可验证状态：可验证·本机静态
- 前置条件：E0；依赖锁/镜像/配置及入口
- 测试数据要求：PRD列出的技术栈逐项清单
- 测试流程：对比安装版本和代码实际调用/注册；尤其Naive UI、Vue Router、markdown清洗。
- 预期结果：逐项区分已安装、已使用和未实现；Naive UI缺失/Router未注册明示，包存在不当功能证据，不扩写生产技术承诺。
- 优先级：P2
- 用例类型：架构
- 是否适合自动化：否（人工静态校审为主，可用扫描工具辅助）
- 代码依据：pyproject.toml；frontend/package.json/main.ts；Compose；Dockerfile
- 实际测试结果：不通过；第一轮通过0/失败1/受限0，第二轮通过0/失败1/受限0。子项记录：`TP-ARC-006__stack-review`：失败，输出：承诺技术栈安装/实际消费不一致 + actual - expected + [ + 'Naive UI未安装', + 'Naive UI没有真实消费', + 'Vue Router未注册' + ] - [] 。原因：类型1（已测/审查确认）：Naive UI未安装/消费；Vue Router虽安装未注册，与PRD/ADR声明不符。 定位：`frontend/package.json:12 dependencies；frontend/src/main.ts:6 插件注册；frontend/src/App.vue:5`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/arc.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/arc.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category arc`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-arc.log`及`categories/arc.json`，按`ARC_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### QLT_001：状态机合法非法转移全覆盖

- 用例编号：`QLT_001`
- 对应测试点：`TP-QLT-001`：状态机自动化覆盖
- 当前可验证状态：可验证·本机动态
- 前置条件：E0；现有pytest依赖可用；本轮不执行
- 测试数据要求：Run/Task全部允许边和终态到各非终态非法边
- 测试流程：核查并执行纯状态机测试；记录断言矩阵、命令与退出码；与handler赋值路径区分。
- 预期结果：所有合法转移成功、非法包括全部终态回退拒绝；现有测试不够全则失败/缺口，不能由纯函数通过推断RUN_006/CAN_005生产并发正确。
- 优先级：P0
- 用例类型：契约/质量
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：tests/unit/test_state_machine.py；状态机
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-QLT-001__all-state-edges`：通过，输出：{"edges":85,"scope":"领域纯函数；不代表handler直接赋值或并发写回正确"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### QLT_002：Journal和SSE自动化断言门禁覆盖

- 用例编号：`QLT_002`
- 对应测试点：`TP-QLT-002`：Journal自动化覆盖
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0检查现有测试可做；完整专项脚本尚未接入
- 测试数据要求：EVT_002/EVT_004/SSE_001/SSE_002对应断言
- 测试流程：逐项找实际可执行测试及门禁入口；有条件执行，核对seq并发/回滚/游标/SSE报告。
- 预期结果：每目标有真实断言及失败退出码，初始两事件断言不能替代全面覆盖；本用例设计文档不是已具备自动化。缺脚本记录not_ready/实现缺口。
- 优先级：P0
- 用例类型：质量/契约
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：tests/api/test_core_api.py；Journal；tests目录
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-QLT-002__existing-executable-gate`：通过，输出：{"files":["tests/api/test_core_api.py"],"exit_code":0,"summary":"2 passed, 1 warning in 1.36s"}；`TP-QLT-002__complete-regression-gate`：受限未执行，输出：本轮EVT/SSE常规检查已接，但并发seq和事务回滚屏障完整门禁未备。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### QLT_003：真实PG租约自动化覆盖

- 用例编号：`QLT_003`
- 对应测试点：`TP-QLT-003`：租约恢复自动化覆盖
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0现有测试可查；真实PG专项和E2未准备
- 测试数据要求：代数/回收/旧续租与完成/多Worker领取
- 测试流程：审查现有SQLite测试与正式PG用例的差别；后续运行专项并查看DB类型与证据。
- 预期结果：关键目标在PG受可运行门禁保护；SQLite少量回收拒续租不能覆盖SKIP LOCKED和并发，未准备部分不能passed。
- 优先级：P0
- 用例类型：质量/并发
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：tests/integration/test_lease_recovery.py；Queue
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-QLT-003__existing-executable-gate`：通过，输出：{"files":["tests/integration/test_lease_recovery.py"],"exit_code":0,"summary":"1 passed in 0.64s"}；`TP-QLT-003__complete-regression-gate`：受限未执行，输出：现有pytest是SQLite，WK真实PG正常领取已补，但多Worker/过期回收/旧写回完整PG门禁未备。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### QLT_004：重试与取消回路自动化覆盖

- 用例编号：`QLT_004`
- 对应测试点：`TP-QLT-004`：重试取消自动化覆盖
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0可查；完整脚本/回排/E2不足
- 测试数据要求：退避、回排、耗尽、running/retry取消和迟到写回清单
- 测试流程：逐项核对现有断言/脚本与执行报告，后续复用WK/CAN证据。
- 预期结果：完整回路和步骤竞争均有自动化失败断言，不只数值退避/queued取消；产品回排缺失和脚本缺失分别记，不重复定义功能流程。
- 优先级：P0
- 用例类型：质量
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：tests/unit/test_task_policy.py；tests/api/test_core_api.py
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-QLT-004__existing-executable-gate`：通过，输出：{"files":["tests/unit/test_task_policy.py"],"exit_code":0,"summary":"1 passed in 0.55s"}；`TP-QLT-004__complete-regression-gate`：受限未执行，输出：本轮queued取消与退避已补，retry_waiting回排/耗尽及running取消竞态尚未完整落地。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### QLT_005：解析召回引用自动化覆盖

- 用例编号：`QLT_005`
- 对应测试点：`TP-QLT-005`：解析召回自动化覆盖
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0可查；三格式完整专项与屏障未全部具备
- 测试数据要求：三格式正常/损坏/空文、active隔离、Top-K、引用身份
- 测试流程：找逐项断言对应文件，核对环境和已有报告是否真实执行。
- 预期结果：各目标都有可执行断言；md/Mock/SQLite简单流不能替代全覆盖，不以设计用例数当执行门禁完成。
- 优先级：P0
- 用例类型：质量
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：tests/unit/test_parsers.py/test_chunker.py/test_vector_store.py；tests/integration/test_document_flow.py
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-QLT-005__existing-executable-gate`：通过，输出：{"files":["tests/unit/test_parsers.py","tests/unit/test_chunker.py","tests/unit/test_vector_store.py","tests/integration/test_document_flow.py"],"exit_code":0,"summary":"6 passed in 0.77s"}；`TP-QLT-005__complete-regression-gate`：受限未执行，输出：本轮三格式/切分/召回引用已补，candidate构建/事务发布屏障及真实Provider故障完整门禁未备。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### QLT_006：正式API和Event契约同步门禁

- 用例编号：`QLT_006`
- 对应测试点：`TP-QLT-006`：API/Event契约门禁
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0路由/Schema/前端类型可查；全路由自动校验未接入
- 测试数据要求：所有正式方法路径/HTTP状态/错误、Event v1/前端字段
- 测试流程：从接口文档枚举与实际路由对照；比较Schema及api.ts；检查实际契约运行校验和失败退出。
- 预期结果：全链路一致、有真实契约门禁；422和业务envelope按实际约定分别判断；手写类型/JSON文件存在不算Schema已测，缺全面断言明示。
- 优先级：P0
- 用例类型：契约/质量
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：tests/api/test_core_api.py；Event契约；frontend/src/types/api.ts；HTTP路由
- 实际测试结果：局部通过，完整受限；第一轮通过1/失败0/受限1，第二轮通过1/失败0/受限1。子项记录：`TP-QLT-006__route-event-contract`：通过，输出：{"paths":12,"events":7,"run_id":"[关联ID见证据]"}；`TP-QLT-006__full-http-field-contract`：受限未执行，输出：本轮路径方法/Event动态Schema已测；完整HTTP响应JSON Schema与自动前端类型生成仍未实施，不能用OpenAPI存在替代全部响应检查。。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### QLT_007：后前端质量命令与浏览器门禁

- 用例编号：`QLT_007`
- 对应测试点：`TP-QLT-007`：后端质量命令；`TP-QLT-008`：前端质量及浏览器门禁
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0；依赖按项目路径就绪，ESLint/Vitest独立配置与工具已补齐；产品门禁/浏览器分类脚本和真实组件断言仍未接入
- 测试数据要求：pytest、ruff check/format --check、mypy；前端typecheck/build/独立lint/Vitest；Playwright分类
- 测试流程：按现有配置分别运行可用命令并记录原输出/退出；审查缺失命令与lint真实执行内容。
- 预期结果：每可用门禁真实执行且结果可追溯；缺失门禁not_ready不假通过；npm lint=vue-tsc不称ESLint，浏览器安装不称Playwright产品用例通过，构建不代替交互。
- 优先级：P1
- 用例类型：运维/质量
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：pyproject.toml；tests；migrations；backend；frontend/package.json；tests无浏览器用例
- 实际测试结果：不通过；第一轮通过5/失败4/受限0，第二轮通过5/失败4/受限0。子项记录：`TP-QLT-007__pytest`：通过，输出：{"command":"python -m pytest -q tests/unit tests/api tests/integration","exit_code":0,"summary":"16 passed, 1 warning in 1.66s"}；`TP-QLT-007__ruff-check`：失败，输出：ruff-check退出1，见原输出 1 !== 0 ；`TP-QLT-007__ruff-format`：失败，输出：ruff-format退出1，见原输出 1 !== 0 ；`TP-QLT-007__mypy`：通过，输出：{"command":"python -m mypy backend","exit_code":0,"summary":"Success: no issues found in 46 source files"}；`TP-QLT-008__typecheck`：通过，输出：{"name":"typecheck","exit_code":0,"summary":"> vue-tsc --noEmit"}；`TP-QLT-008__build`：通过，输出：{"name":"build","exit_code":0,"summary":"✓ built in 1.90s"}；`TP-QLT-008__eslint`：通过，输出：{"name":"eslint","exit_code":0,"summary":" 0 errors and 37 warnings potentially fixable with the '--fix' option."}；`TP-QLT-008__vitest`：失败，输出：vitest退出1，见原输出；组件真实失败不能伪报门禁通过 1 !== 0 ；`TP-QLT-008__browser-category-gate`：失败，输出：Playwright 7真实失败、0受阻，不能宣称门禁全通过。原因：类型1（已测/审查确认）：Ruff3错误/2待格式文件；Vitest12产品组件失败、Playwright7浏览器失败；后两复用FE缺陷，不重复计新业务缺陷。 定位：`migrations/env.py:1 导入、:18 长行；migrations/versions/0001_initial_demo.py:3 导入；tests/demo-smoke/specific_test_script/qlt-tests.mjs:34/49`。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/qlt.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/qlt.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category qlt`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-qlt.log`及`categories/qlt.json`，按`QLT_007__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

### 4.11 临时测试环境与报告清理闭环

主归属：运行器专项审查/自检（不把哨兵当产品分类，不默认新增manifest项）。以下用例可以复用数据准备函数，不复用其他用例的通过结果。

#### LIFE_001：两次运行隔离且不污染开发资源

- 用例编号：`LIFE_001`
- 对应测试点：`TP-LIFE-001`：隔离资源归属
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；记录既有开发project只读资源摘要；不操作开发资源
- 测试数据要求：相同project前缀两次运行；同首选端口；不同run_id
- 测试流程：分别启动/结束本次环境；比较owner/project/端口/镜像/卷/网络及开发资源摘要。
- 预期结果：每次随机独立run_id/project/owner/卷网络；仅127.0.0.1发布API/frontend、DB/Redis无发布；无开发固定端口残留；原开发资源不变，历史报告不覆盖。
- 优先级：P0
- 用例类型：运维/安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：run-demo-smoke.ps1：project/owner/端口生成、启动和标签资源核查；compose/docker-compose.demo-smoke.yml：端口/卷覆盖；lib/smoke-common.ps1：端口选择。
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-LIFE-001__two_fresh_isolated_runs`：通过，输出：{"nested_runs":[{"run_id":"20261007t080426-63cdc107","project":"sesrag-demo-smoke-life-63cdc107","owner_id":"demo-smoke-20261007t080426-63cdc107","api_port":51988,"frontend_port":51989,"network_ids":"[1项]","volume_names":"[2项]","image_tags":"[2项]","trace":"evi…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_001__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### LIFE_002：启动门禁有界且真实依赖失败阻断

- 用例编号：`LIFE_002`
- 对应测试点：`TP-LIFE-002`：启动就绪门禁
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1正常和daemon不可达可测；精确config/migrate/DB/Redis/frontend故障需独立harness驱动
- 测试数据要求：正常；docker/config失败；迁移失败；真实DB探测/Worker/frontend超时
- 测试流程：逐独立run触发指定门禁，记录截止时间/分类是否启动及报告清理。
- 预期结果：全部必要门禁成功才进入分类；失败在配置限时内结束，真实DB探测不能只信ready常量；安全报告明确阶段且finally清理。故障驱动未准备子项blocked，不填历史环境结果。
- 优先级：P0
- 用例类型：运维/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：run-demo-smoke.ps1：预检、Wait-Environment、启动超时、finally；compose/docker-compose.demo-smoke.yml；compose/run-migrations.py；backend/api/routes/health.py。
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限6，第二轮通过2/失败0/受限6。子项记录：`TP-LIFE-002__normal_real_dependency_gates`：通过，输出：{"run_id":"20261007t080426-63cdc107","stages":{"sesrag-demo-smoke-life-63cdc107-frontend:local":{"reused_image_id":"sha256:b4e95005f64724672b0a0f3ea6a5edcd57e27b78dcbc84a109463ce1938e932d"},"cleanup":"passed","tests":"not_ready","preflight":"passed","report_co…（完整输出见原证据）；`TP-LIFE-002__daemon_unavailable`：通过，输出：{"run_id":"20261007t080530-fa8ecc87","status":"blocked","exit_code":2,"duration_ms":1627,"classification_started":false,"trace":"evidence/life/nested-20261007t080530-fa8ecc87.json"}；`TP-LIFE-002__compose_config_failure`：受限未执行，输出：compose_config_failure的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代；`TP-LIFE-002__migration_failure`：受限未执行，输出：migration_failure的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代；`TP-LIFE-002__real_db_probe_failure`：受限未执行，输出：real_db_probe_failure的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代；`TP-LIFE-002__redis_gate_failure`：受限未执行，输出：redis_gate_failure的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代；`TP-LIFE-002__worker_readiness_timeout`：受限未执行，输出：worker_readiness_timeout的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代；`TP-LIFE-002__frontend_timeout`：受限未执行，输出：frontend_timeout的独立Compose/依赖故障harness尚未准备；正常门禁和daemon故障不能替代。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_002__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### LIFE_003：默认未接入分类不假passed

- 用例编号：`LIFE_003`
- 对应测试点：`TP-LIFE-003`：未接入分类不报通过
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；当前manifest七项not_implemented
- 测试数据要求：all及一个未实现分类；无产品脚本；disabled/空选择分支需独立harness驱动另由LIFE_004覆盖
- 测试流程：运行默认和子集选择，读summary、manifest快照及分类报告。
- 预期结果：not_ready/3、空checks，不以空可执行集/环境就绪改为passed；子集不代表全PRD；清理状态单独成功。
- 优先级：P0
- 用例类型：运维/契约
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：run-demo-smoke.ps1：manifest调度、Schema/身份/退出码校验；specific_test_script/manifest.json、category-result.schema.json；lib/smoke-common.ps1：Invoke-SmokeProcess。
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-LIFE-003__all`：通过，输出：{"run_id":"20261007t080426-63cdc107","selection":"all","status":"not_ready","exit_code":3,"categories":[{"status":"not_ready","name":"life-unimplemented-a"},{"status":"not_ready","name":"life-unimplemented-b"}],"trace":"evidence/life/nested-20261007t080426-63c…（完整输出见原证据）；`TP-LIFE-003__subset`：通过，输出：{"run_id":"20261007t080456-e0696884","selection":"life-unimplemented-a","status":"not_ready","exit_code":3,"categories":[{"name":"life-unimplemented-a","status":"not_ready"}],"trace":"evidence/life/nested-20261007t080456-e0696884.json"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_003__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### LIFE_004：分类报告、退出码和超时协议

- 用例编号：`LIFE_004`
- 对应测试点：`TP-LIFE-003`：未接入分类不报通过
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E0运行器逻辑可审查；动态待补独立harness测试替身，不改正式七分类为假产品脚本
- 测试数据要求：6固定参数；合法非空checks；enabled脚本不存在/缺报告/空passed/错run/category/非零/超时；disabled或空可执行集
- 测试流程：用独立临时manifest及哨兵子进程验证各协议分支；观察进程树终止与分类状态。
- 预期结果：只有0+Schema合法+匹配身份+非空checks全passed才分类passed；enabled脚本缺失/非passed协议时均不得通过，原子项保留具体原因；disabled/空可执行集为not_ready而非passed；超时kill自有树。当前入口无独立manifest参数，先补harness自检驱动再动态，不污染正式manifest。
- 优先级：P0
- 用例类型：契约/异常
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：run-demo-smoke.ps1：manifest调度、Schema/身份/退出码校验；specific_test_script/manifest.json、category-result.schema.json；lib/smoke-common.ps1：Invoke-SmokeProcess。
- 实际测试结果：已执行子项通过；第一轮通过10/失败0/受限0，第二轮通过10/失败0/受限0。子项记录：`TP-LIFE-003__valid`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"valid","category_state":{"name":"life-valid","status":"passed","script_sha256":"D18A4CE8F0C26BA3518CFB81127A601F2E7345B6D02F5794C0E8E9D0961F24BB","exit_code":0},"overall":"failed","trace":"evidence/life/nested-2…（完整输出见原证据）；`TP-LIFE-003__missing-report`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"missing-report","category_state":{"name":"life-missing-report","status":"failed","script_sha256":"5920C70341CCC37DE9C0E61F394AD1CE6CCA71FC38B2890239ADC853B117EDAD","exit_code":0},"overall":"failed","trace":"evid…（完整输出见原证据）；`TP-LIFE-003__empty-passed`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"empty-passed","category_state":{"name":"life-empty-passed","status":"failed","script_sha256":"744522E2B8896217115E0B09526A64BAC4AB07693A5C6AC3E48B97DCB724502E","exit_code":0},"overall":"failed","trace":"evidence…（完整输出见原证据）；`TP-LIFE-003__wrong-run`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"wrong-run","category_state":{"name":"life-wrong-run","status":"failed","script_sha256":"77057E9BDC4D8200554858C24E0FE8A02A0E7253B2436BE19D706E08C2E73941","exit_code":0},"overall":"failed","trace":"evidence/life/…（完整输出见原证据）；`TP-LIFE-003__wrong-category`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"wrong-category","category_state":{"name":"life-wrong-category","status":"failed","script_sha256":"6ED93DAEC8CB62B2A338BB6BDED5F74619C466345CD8727986E297782DCF596B","exit_code":0},"overall":"failed","trace":"evid…（完整输出见原证据）；`TP-LIFE-003__nonzero`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"nonzero","category_state":{"name":"life-nonzero","status":"failed","script_sha256":"E744CAC3F145BFAC64B25792E6B43C638BDC07D3F06A1836D712EFAA4E6994C4","exit_code":7},"overall":"failed","trace":"evidence/life/nest…（完整输出见原证据）；`TP-LIFE-003__blocked`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"blocked","category_state":{"name":"life-blocked","status":"failed","script_sha256":"799E279CA6A1A372C7F11DDB98454A6E13343EBD742CFA358CA1ABB90C85FF89","exit_code":0},"overall":"failed","trace":"evidence/life/nest…（完整输出见原证据）；`TP-LIFE-003__timeout`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"timeout","category_state":{"name":"life-timeout","status":"failed","script_sha256":"1F30B0A0A467914EBDBCC9972D9B84C5D151C7073AA5B27B12E5F0B5E2A37910","exit_code":124},"overall":"failed","trace":"evidence/life/ne…（完整输出见原证据）；`TP-LIFE-003__missing-script`：通过，输出：{"run_id":"20261007t080533-660d44da","scenario":"missing-script","category_state":"缺脚本触发安全失败","overall":"failed","trace":"evidence/life/nested-20261007t080533-660d44da.json"}；`TP-LIFE-003__disabled_empty_executable_set`：通过，输出：{"run_id":"20261007t080602-c1ddc804","test_status":"not_ready","categories":[{"name":"life-disabled-only","status":"skipped"}],"limitation":"诊断保留总体cleanup_deferred，不能当正式通过","trace":"evidence/life/nested-20261007t080602-c1ddc804.json"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_004__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### LIFE_005：报告完整、脱敏及版本可追溯

- 用例编号：`LIFE_005`
- 对应测试点：`TP-LIFE-004`：报告证据可追溯
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；连续两个默认run，本轮结果不引用旧记录
- 测试数据要求：本次commit、run_id/project、UTC时间；安全配置哨兵
- 测试流程：读artifacts的summary/json/md/manifest/categories/environment/logs/cleanup；比较清理前后证据和历史目录。
- 预期结果：关联实际commit/config/时间/ID，缺分类如实not_ready；日志/健康/编排/迁移/残留证据可追溯且无密码；两报告不覆盖。失败原因/复现证据可登记，清理前ps不当清理后证据；报告收集失败不能passed。
- 优先级：P1
- 用例类型：运维/安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：run-demo-smoke.ps1：git_commit/git_dirty、Write-Evidence、Collect-Evidence、summary/cleanup输出；lib/smoke-common.ps1：Protect-SmokeText。
- 实际测试结果：已执行子项通过；第一轮通过2/失败0/受限0，第二轮通过2/失败0/受限0。子项记录：`TP-LIFE-004__report_identity_evidence_and_redaction`：通过，输出：{"nested_run_ids":["20261007t080426-63cdc107","20261007t080456-e0696884"],"git_commit":"e40b1055abe8e4263817ff12dda881a7c158c26b","runner_sha256":"267944192B31E982AA590FE857BFFFE5B744B7586750153EA430BE993758475E","report_collection":"passed","generated_passwor…（完整输出见原证据）；`TP-LIFE-004__historical_artifact_unchanged`：通过，输出：{"preserved_run_id":"20261007t080426-63cdc107","other_run_id":"20261007t080456-e0696884","historical_sha256":{"summary.json":"82ada99fcd6beb2681e75aa8a3695382bd26f43b9e9a45fc797744056c149912","summary.md":"d68eb44f2674864547b251bed548cc97bdc89ae010a872f3e870c0…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_005__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### LIFE_006：失败、可捕获中断及硬杀恢复清理

- 用例编号：`LIFE_006`
- 对应测试点：`TP-LIFE-005`：失败或中断仍清理
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1正常/启动失败可测；分类失败、Ctrl+C/异常及硬杀驱动待补；只作用本次入口
- 测试数据要求：正常；启动失败；子进程失败/超时；可捕获中断；硬杀
- 测试流程：各独立run测试finally，检查自有浏览器/SSE/进程关闭；硬杀保留runtime后用CleanupRunId恢复，不承诺立即清理。
- 预期结果：可捕获路径收证据→关闭子进程→销毁/残留核对→删除runtime/tmp；硬杀无法finally必须明确恢复清理且无遗漏，不能伪自动清理；客户端闭合需后续分类实现的finally证据。
- 优先级：P0
- 用例类型：运维/恢复
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：run-demo-smoke.ps1：finally、Cleanup-Environment、CleanupRunId、Collect-Evidence；lib/smoke-common.ps1：Get-SmokeOutcome、Remove-SmokeChild、Invoke-SmokeProcess；self-tests.ps1。
- 实际测试结果：局部通过，完整受限；第一轮通过4/失败0/受限3，第二轮通过4/失败0/受限3。子项记录：`TP-LIFE-005__normal`：通过，输出：{"run_id":"20261007t080426-63cdc107","original_exit":3,"cleanup":"passed","trace":"evidence/life/nested-20261007t080426-63cdc107.json"}；`TP-LIFE-005__startup_failure`：通过，输出：{"run_id":"20261007t080530-fa8ecc87","original_exit":2,"cleanup":"passed","trace":"evidence/life/nested-20261007t080530-fa8ecc87.json"}；`TP-LIFE-005__category_failure_and_timeout`：通过，输出：{"run_id":"20261007t080533-660d44da","original_exit":1,"cleanup":"passed","trace":"evidence/life/nested-20261007t080533-660d44da.json"}；`TP-LIFE-005__killed_category_parent_registry_fallback`：通过，输出：{"harness_parent_run_id":"20261007t080633-73fcd8bc","registered_child_run_id":"20261007t080651-50e125dd","category_timeout_exit":124,"child_deferred_exit":5,"parent_fallback":{"cleaned":true,"run_id":"20261007t080651-50e125dd","exit_code":3,"project":"sesrag-d…（完整输出见原证据）；`TP-LIFE-005__capturable_interrupt`：受限未执行，输出：capturable_interrupt独立受控故障或运行器客户端生命周期观测驱动尚未准备；正常/失败路径及超时树终止是已有局部证据；`TP-LIFE-005__hard_kill_recovery`：受限未执行，输出：hard_kill_recovery独立受控故障或运行器客户端生命周期观测驱动尚未准备；正常/失败路径及超时树终止是已有局部证据；`TP-LIFE-005__browser_sse_client_closure`：受限未执行，输出：browser_sse_client_closure独立受控故障或运行器客户端生命周期观测驱动尚未准备；正常/失败路径及超时树终止是已有局部证据。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_006__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### LIFE_007：精确资源释放与保留范围

- 用例编号：`LIFE_007`
- 对应测试点：`TP-LIFE-006`：清理残留核对与退出码
- 当前可验证状态：可验证·本机动态
- 前置条件：E1；默认运行完成，能查询本次Docker标签/资源清单
- 测试数据要求：本次PG/uploads/Redis匿名卷、网络、镜像tag、tmp/runtime；artifacts和共享缓存对照
- 测试流程：正常结束后按project标签/捕获卷ID/唯一tag只读查残留；核对cleanup.json及本地精确run目录。
- 预期结果：容器/网络/业务卷/本次tag/tmp/runtime无残留，退出与清理证据一致；artifacts/浏览器/共享基础镜像/BuildKit缓存有意保留，不global prune、不要求Docker虚拟盘立即物理缩小。
- 优先级：P0
- 用例类型：运维/安全
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：run-demo-smoke.ps1：finally、Cleanup-Environment、CleanupRunId、Collect-Evidence；lib/smoke-common.ps1：Get-SmokeOutcome、Remove-SmokeChild、Invoke-SmokeProcess；self-tests.ps1。
- 实际测试结果：已执行子项通过；第一轮通过1/失败0/受限0，第二轮通过1/失败0/受限0。子项记录：`TP-LIFE-006__zero_exact_residuals_and_preserved_cache`：通过，输出：{"nested_cleanup":[{"nested_run_id":"20261007t080426-63cdc107","project":"sesrag-demo-smoke-life-63cdc107","zero_container_network_volume_tag_runtime_tmp":true,"artifact_preserved":true},{"nested_run_id":"20261007t080456-e0696884","project":"sesrag-demo-smoke-…（完整输出见原证据）。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_007__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

#### LIFE_008：诊断保留和清理失败不能passed

- 用例编号：`LIFE_008`
- 对应测试点：`TP-LIFE-006`：清理残留核对与退出码
- 当前可验证状态：部分可验证·子项有明确限制
- 前置条件：E1 KeepContainers可测；删除失败驱动待补，不改全局Docker配置
- 测试数据要求：KeepContainers=true；仅本次down/文件清理失败；CleanupRunId重试
- 测试流程：观察诊断结束及失败后状态/最小runtime；恢复障碍按run_id清理；保存原报告后比较新cleanup。
- 预期结果：诊断cleanup_deferred/5且资源明示保留；清理失败cleanup_failed/4优先不被产品passed覆盖，最小runtime留作恢复并尽量删tmp；重试只清本次、成功核对无残留。
- 优先级：P0
- 用例类型：异常/运维
- 是否适合自动化：是（可用子项可接入，受限子项独立记录）
- 代码依据：run-demo-smoke.ps1：finally、Cleanup-Environment、CleanupRunId、Collect-Evidence；lib/smoke-common.ps1：Get-SmokeOutcome、Remove-SmokeChild、Invoke-SmokeProcess；self-tests.ps1。
- 实际测试结果：局部通过，完整受限；第一轮通过2/失败0/受限1，第二轮通过2/失败0/受限1。子项记录：`TP-LIFE-006__diagnostic_deferred_then_recovery`：通过，输出：{"run_id":"20261007t080602-c1ddc804","original_status":"cleanup_deferred","original_exit":5,"recovery_exit":3,"recovered_cleanup":"passed","original_summary_preserved":true}；`TP-LIFE-006__cleanup_failure_status_precedence_function`：通过，输出：{"function":"Get-SmokeOutcome","tested_product_statuses":["passed","failed","not_ready"],"expected_cleanup_status":"cleanup_failed","exit_code":4,"limitation":"未制造真实down或文件删除失败"}；`TP-LIFE-006__real_down_or_file_cleanup_failure`：受限未执行，输出：仅本次down/文件删除失败的独立故障驱动尚未准备；状态函数通过不能替代真实删除失败。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。不得把局部检查或记录覆盖解释为完整需求验收通过。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_008__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（仅已执行子项状态在两轮一致）；受限记录一致不证明完整场景稳定，完整稳定性未判定。

#### LIFE_009：生成及删除路径不越界

- 用例编号：`LIFE_009`
- 对应测试点：`TP-LIFE-007`：临时文件安全边界
- 当前可验证状态：可验证·本机动态
- 前置条件：E0；现有self-tests可执行；E1只读忽略规则；不删除真实仓库目录
- 测试数据要求：合法run_id；../、绝对路径、根目录、symlink/reparse、误project等危险输入
- 测试流程：检查Git忽略后才生成；运行辅助安全自检/读取删除目标解析；确认危险目标拒绝。
- 预期结果：runtime/artifacts/tmp/cache/node_modules等不入Git/构建；清理仅精确本次子目录和project，拒绝根/逃逸/link；分类无自发down/prune权，不以广泛glob删开发数据。
- 优先级：P0
- 用例类型：安全/边界
- 是否适合自动化：是（后续按分类协议编写脚本；目前未接入）
- 代码依据：lib/smoke-common.ps1：路径解析与Remove-SmokeChild；self-tests.ps1：路径/状态安全检查；run-demo-smoke.ps1：run_id目录生成与资源归属核查；根.gitignore/.dockerignore。
- 实际测试结果：已执行子项通过；第一轮通过4/失败0/受限0，第二轮通过4/失败0/受限0。子项记录：`TP-LIFE-007__production_path_rejections`：通过，输出：{"checks":"[11项，明细见证据]","actual_production_functions":["Get-SmokeChildPath","Remove-SmokeChild"],"exact_tmp_sandbox_removed":true}；`TP-LIFE-007__git_and_build_context_exclusions`：通过，输出：{"ignored_paths":"[6项，明细见证据]","actual_git_check_ignore":true}；`TP-LIFE-007__mismatched_saved_project_recovery`：通过，输出：{"invalid_run_id":"life-invalid-bb965c74","rejected_before_deployment":true,"exit_code":2,"prior_resources_unchanged":true}；`TP-LIFE-007__category_has_no_destroy_permission`：通过，输出：{"denied_before_docker_execution":["down","rm","prune"],"lifecycle_owner":"run-demo-smoke.ps1"}。证据：[第一轮](artifacts/20261007t072506-2fc5b075/categories/life.json)、[第二轮](artifacts/20261007t075158-2907bbdf/categories/life.json)及各check.evidence/中文分类日志。
- 复现步骤：从仓库根目录执行 `pwsh -NoProfile -File tests/demo-smoke/run-demo-smoke.ps1 -Category life`；该入口运行整个分类并准备独立数据，不支持只选单个用例。正式两轮实际使用不带-Category的all入口。查看新run的`logs/category-life.log`及`categories/life.json`，按`LIFE_009__`定位子项；受限项须先补前置驱动，当前命令不会自动解除限制。
- 测试结果是否稳定出现：是（两轮相同检查ID的断言状态一致；失败稳定也不等于通过；不外推生产可靠性）。

## 5. 覆盖关系与完整验收

### 5.1 逐测试点反向映射

每个测试点至少对应一个用例；多用例只是同目标不同子场景的证据，不能重复计为多个需求。状态为用例中实际可做的层级，局部/待补原因及正确预期见相应卡片；原表的旧状态不作为本轮结果。

| 测试点 | 目标 | 对应用例 | 当前验证层级 |
| --- | --- | --- | --- |
| TP-DEP-001 | 全新编排服务拓扑 | `DEP_001` | 当前入口可验证（不等于通过） |
| TP-DEP-002 | 首次迁移结果 | `DEP_001` | 当前入口可验证（不等于通过） |
| TP-DEP-003 | 已完成迁移重复执行 | `DEP_002` | 当前入口可验证（不等于通过） |
| TP-DEP-004 | 迁移失败阻断业务启动 | `DEP_003` | 部分可验证，见用例缺口 |
| TP-DEP-005 | 上传卷共享 | `DEP_004` | 当前入口可验证（不等于通过） |
| TP-DEP-006 | Secret 配置注入边界 | `DEP_005` | 静态可验证（不替代动态） |
| TP-DEP-007 | 调度参数有效性 | `DEP_006` | 静态可验证（不替代动态） |
| TP-DEP-008 | 运行向量维度与数据库一致 | `DEP_007` | 静态可验证（不替代动态） |
| TP-DEP-009 | 迁移约束与模型一致 | `DEP_008` | 当前入口可验证（不等于通过） |
| TP-DEP-010 | Redis冷启动降级边界 | `DEP_009` | 部分可验证，见用例缺口 |
| TP-HLT-001 | API 存活语义 | `HLT_001` | 当前入口可验证（不等于通过） |
| TP-HLT-002 | 数据库就绪真实性 | `HLT_002` | 当前入口可验证（不等于通过） |
| TP-HLT-003 | Redis 降级真实性 | `HLT_003` | 当前入口可验证（不等于通过） |
| TP-HLT-004 | Worker readiness 连续性 | `HLT_004` | 待补条件/实现，见用例前置 |
| TP-HLT-005 | API 重启事实恢复 | `HLT_005` | 当前入口可验证（不等于通过） |
| TP-HLT-006 | Redis 重启事实恢复 | `HLT_003` | 当前入口可验证（不等于通过） |
| TP-TH-001 | 创建会话身份 | `TH_001` | 当前入口可验证（不等于通过） |
| TP-TH-002 | 标题长度校验 | `TH_002` | 当前入口可验证（不等于通过） |
| TP-TH-003 | 列表更新时间倒序 | `TH_001` | 当前入口可验证（不等于通过） |
| TP-TH-004 | 会话详情事实排序 | `TH_001` | 当前入口可验证（不等于通过） |
| TP-TH-005 | 归档保留历史 | `TH_003` | 当前入口可验证（不等于通过） |
| TP-TH-006 | 缺失会话错误 | `TH_004` | 当前入口可验证（不等于通过） |
| TP-TH-007 | owner列表隔离 | `OWN_001` | 待补条件/实现，见用例前置 |
| TP-TH-008 | owner对象访问拒绝 | `OWN_001` | 待补条件/实现，见用例前置 |
| TP-MSG-001 | 用户消息持久字段 | `MSG_001` | 部分可验证，见用例缺口 |
| TP-MSG-002 | 消息正文长度限制 | `MSG_002` | 当前入口可验证（不等于通过） |
| TP-MSG-003 | 连续消息序号 | `MSG_003` | 当前入口可验证（不等于通过） |
| TP-MSG-004 | 不同消息并发序号 | `MSG_004` | 当前入口可验证（不等于通过） |
| TP-MSG-005 | 顺序重复幂等键 | `MSG_005` | 当前入口可验证（不等于通过） |
| TP-MSG-006 | 同Key并发提交 | `MSG_006` | 部分可验证，见用例缺口 |
| TP-MSG-007 | 幂等作用域 | `MSG_005` | 当前入口可验证（不等于通过） |
| TP-MSG-008 | 最终assistant关联与内容 | `MSG_003` | 当前入口可验证（不等于通过） |
| TP-MSG-009 | assistant重复完成防护 | `MSG_007` | 待补条件/实现，见用例前置 |
| TP-MSG-010 | 用户与assistant并发seq | `MSG_008` | 待补条件/实现，见用例前置 |
| TP-RUN-001 | 初始事实原子创建 | `RUN_001` | 当前入口可验证（不等于通过） |
| TP-RUN-002 | 创建事务失败回滚 | `RUN_002` | 待补条件/实现，见用例前置 |
| TP-RUN-003 | 快照字段准确性 | `RUN_003` | 部分可验证，见用例缺口 |
| TP-RUN-004 | 执行遵从冻结快照 | `RUN_003` | 部分可验证，见用例缺口 |
| TP-RUN-005 | 状态读取持久一致 | `RUN_004` | 部分可验证，见用例缺口 |
| TP-RUN-006 | 成功终态原子提交 | `RUN_005` | 部分可验证，见用例缺口 |
| TP-RUN-007 | 非取消终态不可逆 | `RUN_006` | 待补条件/实现，见用例前置 |
| TP-RUN-008 | Run对象访问隔离 | `OWN_001`、`RUN_007` | 待补条件/实现，见用例前置；当前入口可验证（不等于通过） |
| TP-EVT-001 | Event envelope契约 | `EVT_001` | 当前入口可验证（不等于通过） |
| TP-EVT-002 | 同Run并发分配seq | `EVT_002` | 待补条件/实现，见用例前置 |
| TP-EVT-003 | 事件追加不可改写 | `EVT_003` | 当前入口可验证（不等于通过） |
| TP-EVT-004 | 领取事件存在 | `EVT_001` | 当前入口可验证（不等于通过） |
| TP-EVT-005 | 正常执行事件顺序 | `EVT_001` | 当前入口可验证（不等于通过） |
| TP-EVT-006 | after_seq补放边界 | `EVT_004` | 当前入口可验证（不等于通过） |
| TP-EVT-007 | Run之间序号独立 | `EVT_003` | 当前入口可验证（不等于通过） |
| TP-EVT-008 | 索引任务不伪造RunEvent | `EVT_005` | 当前入口可验证（不等于通过） |
| TP-SSE-001 | SSE消息格式 | `SSE_001` | 当前入口可验证（不等于通过） |
| TP-SSE-002 | 首连补历史后观察新事件 | `SSE_002` | 部分可验证，见用例缺口 |
| TP-SSE-003 | Last-Event-ID优先级 | `SSE_001` | 当前入口可验证（不等于通过） |
| TP-SSE-004 | 客户端断开不取消 | `SSE_003` | 部分可验证，见用例缺口 |
| TP-SSE-005 | Redis不可用仍补放 | `HLT_003` | 当前入口可验证（不等于通过） |
| TP-SSE-006 | 发送终态后关闭 | `SSE_004` | 部分可验证，见用例缺口 |
| TP-SSE-007 | 游标已越过终态 | `SSE_004` | 部分可验证，见用例缺口 |
| TP-SSE-008 | SSE握手前对象校验 | `OWN_001`、`SSE_005` | 待补条件/实现，见用例前置；当前入口可验证（不等于通过） |
| TP-WK-001 | PostgreSQL权威排队 | `RUN_001` | 当前入口可验证（不等于通过） |
| TP-WK-002 | 领取资格筛选 | `WK_001` | 部分可验证，见用例缺口 |
| TP-WK-003 | 领取身份与代数 | `WK_001` | 部分可验证，见用例缺口 |
| TP-WK-004 | 多Worker排他领取 | `WK_002` | 待补条件/实现，见用例前置 |
| TP-WK-005 | Worker身份唯一性 | `WK_003` | 静态可验证（不替代动态） |
| TP-WK-006 | 正常心跳持续续租 | `WK_004` | 待补条件/实现，见用例前置 |
| TP-WK-007 | 不匹配身份续租拒绝 | `WK_005` | 待补条件/实现，见用例前置 |
| TP-WK-008 | 已到期lease续租拒绝 | `WK_005` | 待补条件/实现，见用例前置 |
| TP-WK-009 | 未超限租约回收 | `WK_006` | 待补条件/实现，见用例前置 |
| TP-WK-010 | 旧代数普通写回拒绝 | `WK_007` | 待补条件/实现，见用例前置 |
| TP-WK-011 | 回收达到最大attempt | `WK_008` | 待补条件/实现，见用例前置 |
| TP-WK-012 | 查询后接管的竞态防护 | `WK_009` | 待补条件/实现，见用例前置 |
| TP-WK-013 | 旧Worker事件写回隔离 | `WK_010` | 待补条件/实现，见用例前置 |
| TP-WK-014 | 旧Worker失败回写隔离 | `WK_011` | 待补条件/实现，见用例前置 |
| TP-WK-015 | 失租后停止工作 | `WK_012` | 待补条件/实现，见用例前置 |
| TP-WK-016 | 退避时间计算 | `WK_013` | 部分可验证，见用例缺口 |
| TP-WK-017 | retry_waiting回排 | `WK_014` | 待补条件/实现，见用例前置 |
| TP-WK-018 | 重试身份保持 | `WK_014` | 待补条件/实现，见用例前置 |
| TP-WK-019 | 重试次数耗尽终态 | `WK_015` | 待补条件/实现，见用例前置 |
| TP-WK-020 | 排队过deadline | `WK_016` | 部分可验证，见用例缺口 |
| TP-WK-021 | 执行中过deadline | `WK_017` | 待补条件/实现，见用例前置 |
| TP-WK-022 | retry_waiting过deadline | `WK_018` | 待补条件/实现，见用例前置 |
| TP-WK-023 | SIGTERM停止新领取 | `WK_019` | 待补条件/实现，见用例前置 |
| TP-WK-024 | SIGTERM宽限内完成 | `WK_020` | 待补条件/实现，见用例前置 |
| TP-WK-025 | SIGTERM超宽限退出 | `WK_021` | 待补条件/实现，见用例前置 |
| TP-WK-026 | 正常重启续跑队列 | `WK_022` | 当前入口可验证（不等于通过） |
| TP-WK-027 | DB中断API错误语义 | `HLT_002` | 当前入口可验证（不等于通过） |
| TP-WK-028 | DB中断Worker退避恢复 | `WK_023` | 当前入口可验证（不等于通过） |
| TP-WK-029 | Worker生命周期关联日志 | `WK_024` | 部分可验证，见用例缺口 |
| TP-WK-030 | stale拒绝诊断 | `WK_007` | 待补条件/实现，见用例前置 |
| TP-WK-031 | 到期未接管的完成拒绝 | `WK_025` | 待补条件/实现，见用例前置 |
| TP-CAN-001 | queued取消 | `CAN_001` | 部分可验证，见用例缺口 |
| TP-CAN-002 | 终态重复取消 | `CAN_001` | 部分可验证，见用例缺口 |
| TP-CAN-003 | 检索前步骤取消检查 | `CAN_002` | 待补条件/实现，见用例前置 |
| TP-CAN-004 | 模型前步骤取消检查 | `CAN_003` | 待补条件/实现，见用例前置 |
| TP-CAN-005 | 流式中取消抑制增量 | `CAN_004` | 待补条件/实现，见用例前置 |
| TP-CAN-006 | 迟到成功与取消竞态 | `CAN_005` | 待补条件/实现，见用例前置 |
| TP-CAN-007 | retry_waiting取消 | `CAN_006` | 待补条件/实现，见用例前置 |
| TP-DOC-001 | 上传元数据与索引任务 | `DOC_001` | 部分可验证，见用例缺口 |
| TP-DOC-002 | 扩展名白名单 | `DOC_002` | 当前入口可验证（不等于通过） |
| TP-DOC-003 | 文件大小阈值 | `DOC_003` | 当前入口可验证（不等于通过） |
| TP-DOC-004 | MIME与扩展名匹配 | `DOC_004` | 当前入口可验证（不等于通过） |
| TP-DOC-005 | 文件名路径隔离 | `DOC_005` | 当前入口可验证（不等于通过） |
| TP-DOC-006 | 内容哈希准确 | `DOC_001` | 部分可验证，见用例缺口 |
| TP-DOC-007 | 登记DB失败清理文件 | `DOC_006` | 待补条件/实现，见用例前置 |
| TP-DOC-008 | 上传磁盘故障 | `DOC_007` | 待补条件/实现，见用例前置 |
| TP-DOC-009 | 文档列表与owner | `OWN_001`、`DOC_001` | 待补条件/实现，见用例前置；部分可验证，见用例缺口 |
| TP-DOC-010 | 活动索引任务复用 | `DOC_008` | 部分可验证，见用例缺口 |
| TP-DOC-011 | 并发index请求幂等 | `DOC_009` | 部分可验证，见用例缺口 |
| TP-DOC-012 | index对象访问拒绝 | `OWN_001`、`DOC_010` | 待补条件/实现，见用例前置；当前入口可验证（不等于通过） |
| TP-DOC-013 | 终态文档重新索引 | `DOC_011` | 当前入口可验证（不等于通过） |
| TP-PAR-001 | UTF-8 txt解析 | `PAR_001` | 部分可验证，见用例缺口 |
| TP-PAR-002 | Markdown解析 | `PAR_001` | 部分可验证，见用例缺口 |
| TP-PAR-003 | docx段落解析 | `PAR_001` | 部分可验证，见用例缺口 |
| TP-PAR-004 | 编码损坏失败语义 | `PAR_002` | 当前入口可验证（不等于通过） |
| TP-PAR-005 | docx结构损坏 | `PAR_002` | 当前入口可验证（不等于通过） |
| TP-PAR-006 | 空解析文本 | `PAR_003` | 部分可验证，见用例缺口 |
| TP-PAR-007 | 解析位置契约 | `PAR_001` | 部分可验证，见用例缺口 |
| TP-PAR-008 | docx非段落文字覆盖 | `PAR_004` | 部分可验证，见用例缺口 |
| TP-CHK-001 | 切片覆盖与offset | `CHK_001` | 当前入口可验证（不等于通过） |
| TP-CHK-002 | overlap交界 | `CHK_001` | 当前入口可验证（不等于通过） |
| TP-CHK-003 | 非法切分参数 | `CHK_002` | 部分可验证，见用例缺口 |
| TP-IDX-001 | 确定性Mock Embedding | `IDX_001` | 当前入口可验证（不等于通过） |
| TP-IDX-002 | Embedding长度不符 | `IDX_003` | 待补条件/实现，见用例前置 |
| TP-IDX-003 | 初次索引完整结果 | `IDX_002` | 部分可验证，见用例缺口 |
| TP-IDX-004 | 候选批次检索隔离 | `IDX_004` | 待补条件/实现，见用例前置 |
| TP-IDX-005 | 索引发布与Task原子性 | `IDX_005` | 待补条件/实现，见用例前置 |
| TP-IDX-006 | 重建失败保留旧索引 | `IDX_004` | 待补条件/实现，见用例前置 |
| TP-IDX-007 | 成功替换清理旧批次 | `DOC_011` | 当前入口可验证（不等于通过） |
| TP-IDX-008 | 索引终态错误一致性 | `PAR_003`、`IDX_005` | 部分可验证，见用例缺口；待补条件/实现，见用例前置 |
| TP-IDX-009 | 原始文件丢失 | `IDX_006` | 当前入口可验证（不等于通过） |
| TP-IDX-010 | 外部调用不持长事务 | `IDX_007` | 待补条件/实现，见用例前置 |
| TP-RAG-001 | Top-K与排序 | `RAG_001` | 部分可验证，见用例缺口 |
| TP-RAG-002 | owner召回隔离 | `OWN_001` | 待补条件/实现，见用例前置 |
| TP-RAG-003 | 向量异常不是无证据 | `RAG_002` | 待补条件/实现，见用例前置 |
| TP-RAG-004 | 空召回答案 | `RAG_003` | 当前入口可验证（不等于通过） |
| TP-RAG-005 | 非空证据回答 | `RAG_004` | 当前入口可验证（不等于通过） |
| TP-RAG-006 | 增量与最终正文一致 | `RAG_004` | 当前入口可验证（不等于通过） |
| TP-RAG-007 | 引用证据身份真实性 | `RAG_004` | 当前入口可验证（不等于通过） |
| TP-RAG-008 | 相似度边界语义 | `RAG_001` | 部分可验证，见用例缺口 |
| TP-RAG-009 | Provider初始化配置 | `RAG_005` | 部分可验证，见用例缺口 |
| TP-RAG-010 | 临时Provider错误分类 | `RAG_006` | 待补条件/实现，见用例前置 |
| TP-RAG-011 | 永久Provider错误分类 | `RAG_006` | 待补条件/实现，见用例前置 |
| TP-RAG-012 | Provider异常响应结构 | `RAG_007` | 待补条件/实现，见用例前置 |
| TP-RAG-013 | 真实生成流协议 | `RAG_008` | 待补条件/实现，见用例前置 |
| TP-RAG-014 | Top-K配置边界 | `RAG_001` | 部分可验证，见用例缺口 |
| TP-FE-001 | 浏览器API与SSE路由一致 | `FE_001` | 当前入口可验证（不等于通过） |
| TP-FE-002 | 创建与选择会话 | `FE_001` | 当前入口可验证（不等于通过） |
| TP-FE-003 | 发送与用户消息呈现 | `FE_002` | 当前入口可验证（不等于通过） |
| TP-FE-004 | 执行中回答投影 | `FE_003` | 待补条件/实现，见用例前置 |
| TP-FE-005 | terminal后最终消息恢复 | `FE_004` | 当前入口可验证（不等于通过） |
| TP-FE-006 | 实时Run状态投影 | `FE_005` | 待补条件/实现，见用例前置 |
| TP-FE-007 | 失败交互可诊断 | `FE_006` | 部分可验证，见用例缺口 |
| TP-FE-008 | Event时间线去重排序 | `FE_007` | 当前入口可验证（不等于通过） |
| TP-FE-009 | 答案重复投影防护 | `FE_008` | 待补条件/实现，见用例前置 |
| TP-FE-010 | 断线重连补放 | `FE_009` | 部分可验证，见用例缺口 |
| TP-FE-011 | 刷新历史恢复 | `FE_010` | 当前入口可验证（不等于通过） |
| TP-FE-012 | 刷新运行时间线恢复 | `FE_011` | 部分可验证，见用例缺口 |
| TP-FE-013 | 文档上传状态更新 | `FE_012` | 当前入口可验证（不等于通过） |
| TP-FE-014 | 引用展示与展开 | `FE_013` | 部分可验证，见用例缺口 |
| TP-FE-015 | 页面取消操作 | `FE_005` | 待补条件/实现，见用例前置 |
| TP-FE-016 | 健康状态展示 | `FE_014` | 静态可验证（不替代动态） |
| TP-FE-017 | 会话切换观察隔离 | `FE_015` | 待补条件/实现，见用例前置 |
| TP-FE-018 | 前端进程重启恢复 | `FE_010` | 当前入口可验证（不等于通过） |
| TP-SEC-001 | 上传目录非静态暴露 | `SEC_001` | 当前入口可验证（不等于通过） |
| TP-SEC-002 | Storage读路径防逃逸 | `SEC_002` | 部分可验证，见用例缺口 |
| TP-SEC-003 | Markdown XSS清洗 | `SEC_003` | 当前入口可验证（不等于通过） |
| TP-SEC-004 | API错误输出脱敏 | `SEC_004` | 部分可验证，见用例缺口 |
| TP-SEC-005 | 持久事实与日志脱敏 | `SEC_004` | 部分可验证，见用例缺口 |
| TP-SEC-006 | 超大上传内存风险 | `SEC_005` | 静态可验证（不替代动态） |
| TP-PERF-001 | 提交问题响应时间 | `PERF_001` | 当前入口可验证（不等于通过） |
| TP-PERF-002 | 开始后首执行事件可见 | `PERF_002` | 待补条件/实现，见用例前置 |
| TP-ARC-001 | 分层与目录职责 | `ARC_001` | 静态可验证（不替代动态） |
| TP-ARC-002 | Provider可替换接口 | `ARC_002` | 部分可验证，见用例缺口 |
| TP-ARC-003 | Queue/Vector/Parser稳定Port | `ARC_002` | 部分可验证，见用例缺口 |
| TP-ARC-004 | Demo非目标入口边界 | `ARC_001` | 静态可验证（不替代动态） |
| TP-ARC-005 | 初始迁移历史稳定性 | `ARC_003` | 静态可验证（不替代动态） |
| TP-ARC-006 | 声明技术栈与实际依赖 | `ARC_004` | 静态可验证（不替代动态） |
| TP-QLT-001 | 状态机自动化覆盖 | `QLT_001` | 当前入口可验证（不等于通过） |
| TP-QLT-002 | Journal自动化覆盖 | `QLT_002` | 部分可验证，见用例缺口 |
| TP-QLT-003 | 租约恢复自动化覆盖 | `QLT_003` | 部分可验证，见用例缺口 |
| TP-QLT-004 | 重试取消自动化覆盖 | `QLT_004` | 部分可验证，见用例缺口 |
| TP-QLT-005 | 解析召回自动化覆盖 | `QLT_005` | 部分可验证，见用例缺口 |
| TP-QLT-006 | API/Event契约门禁 | `QLT_006` | 部分可验证，见用例缺口 |
| TP-QLT-007 | 后端质量命令 | `QLT_007` | 部分可验证，见用例缺口 |
| TP-QLT-008 | 前端质量及浏览器门禁 | `QLT_007` | 部分可验证，见用例缺口 |
| TP-LIFE-001 | 隔离资源归属 | `LIFE_001` | 当前入口可验证（不等于通过） |
| TP-LIFE-002 | 启动就绪门禁 | `LIFE_002` | 部分可验证，见用例缺口 |
| TP-LIFE-003 | 未接入分类不报通过 | `LIFE_003`、`LIFE_004` | 当前入口可验证（不等于通过）；部分可验证，见用例缺口 |
| TP-LIFE-004 | 报告证据可追溯 | `LIFE_005` | 当前入口可验证（不等于通过） |
| TP-LIFE-005 | 失败或中断仍清理 | `LIFE_006` | 部分可验证，见用例缺口 |
| TP-LIFE-006 | 清理残留核对与退出码 | `LIFE_007`、`LIFE_008` | 当前入口可验证（不等于通过）；部分可验证，见用例缺口 |
| TP-LIFE-007 | 临时文件安全边界 | `LIFE_009` | 当前入口可验证（不等于通过） |

### 5.2 八条产品验收的联合证据

| PRD §9 | 联合用例（详细子项以逐点映射为准） | 不可省略的证据/限制 |
| --- | --- | --- |
| 1 全新服务启动健康 | DEP_001～DEP_004、HLT_001～HLT_004、FE_001、LIFE_001/002 | 真迁移/DB探测、实际依赖健康、浏览器可达；ready常量不能证明就绪，长Worker健康仍需E2。 |
| 2 完整会话事实与回答 | RUN_001/005、MSG_001/003、EVT_001、RAG_003/004、FE_002～FE_005 | DB关联及原子终态、真实Message/引用、前端显示均需满足；字段/API或前端缺口不得跳过。 |
| 3 崩溃lease恢复且无重复assistant | WK_006～WK_012/025、MSG_007/008、RUN_006、IDX_004/005 | 确定故障阶段、新代数、旧写回/事件/失败隔离、唯一assistant与候选隔离；默认快速Mock不能证明。 |
| 4 SIGTERM安全停机与重启 | WK_019～WK_022、WK_004/006 | 停领、有效lease下宽限内完成、有界超宽限和恢复分别验证；Docker强杀不当优雅通过。 |
| 5 三格式索引与真实引用/无证据 | PAR_001/003、CHK_001、IDX_002/004、RAG_003/004、FE_012/013 | 实际三格式和chunk身份，失败不是无知识；基础引用标签不是展开完成。 |
| 6 SSE补放和前端无重复 | EVT_004、SSE_001～SSE_004、FE_007～FE_011 | 后端游标、交界无缺口、浏览器断线/刷新/正文去重联合证据；仅事件store去重不够。 |
| 7 取消停止步骤且无迟到成功 | CAN_001～CAN_006、FE_005 | 检索/模型/增量/最终提交逐步骤；queued取消不能替代running与竞争。 |
| 8 自动化关键域全覆盖 | QLT_001～QLT_007、LIFE_003～LIFE_009及对应功能用例 | 真正可执行断言、分类报告、失败退出与清理；149个设计用例和浏览器安装不表示自动化已实现。 |

## 6. 校审记录与交付边界

本轮新增本文件，并同步根README、环境README、分类接入计划、分类协议和测试点文档的状态/导航说明；不变更产品代码、API、迁移、Compose、fixture、manifest 或运行器，不安装新依赖，不新增产品测试脚本，不启动产品验收。用户修改的 `docs/当前任务说明.md` 保留。

校审重点：

- 测试点原表与环境更新分开理解：LIFE 已有入口，普通浏览器已有工具；E2/E4/O/C 缺口仍逐用例明示。
- 全部 191 个测试点逐项映射，待补目标也写流程和正确预期，没有删掉实现差异以追求通过。
- 149 个用例均有编号、标题、关联测试点、前置/数据/流程/预期、优先级/类型/自动化适用性，三个实际结果字段留空。
- 区分 Run 与 Task、lease 与 readiness、事件去重与正文去重、空检索与故障、真实 Provider 流与 Mock、应用SIGTERM与Docker强杀、产品结果与资源清理。
- 合并用例保留独立子项断言和报告 ID；不以共享场景造成跨用例执行依赖。
- 对补充建议/区域支持限制不擅自修改PRD，正确目标仍按权威需求；代码缺陷不改成“当前行为符合预期”。

2026-10-07完成只读PowerShell字段/引用/链接校验及Git空白检查，实际结果如下；这是设计校审证据，不是产品执行结果。检查读取本文件全部卡片、测试点ID和反向映射，并验证字段唯一/非空、结果栏为空及本地链接目标存在。

| 设计检查 | 结果 |
| --- | --- |
| 用例ID、必需字段及空结果栏 | 149个唯一用例；字段缺失/重复/错误为0；447个实际结果/复现/稳定性字段全部为空。 |
| 191个测试点引用和反向覆盖 | 191个点均有用例，191行反向映射与卡片一致；未知引用/未覆盖点为0。 |
| 可验证层级计数与卡片一致 | 动态53、静态9、部分42、待补45，合计149；暂不可完整动态项均有明确前置缺口。 |
| 文档相对链接 | 本轮修改文档的本地链接目标均存在，无失效目标。 |
| 本轮改动空白检查 | git diff --check限定本轮既有文档无错误；新增文档no-index --check无错误诊断，行尾空白为0。no-index的差异退出1不等于格式失败。 |
| 全工作区空白检查 | docs/当前任务说明.md第26行存在用户原有行尾空格，保留，未越界处理；不将全工作区宣称为无警告。 |
| 产品单测/构建/Compose/浏览器验收 | 本轮未执行；结果字段全部留空。 |

**结论边界**：本文件用于后续编写分类测试脚本及实施验收。设计覆盖不等于需求已正确实现或测试已通过；完整验收必须补齐明确条件、执行必要子项、保存可追溯证据并确认清理成功。
