# TEST-002 稳定子集静态初审

- 日期：2026-10-21。
- 工作区：`D:/Agentic_RAG/SesRAG`；分支 `sesrag_v0.2`；brief 基线 HEAD `595eb04`。
- 审批对象：工作区新增 TEST-002 suite 与相关文档/ignore 增量，不是空的 `HEAD..HEAD`。
- 审查依据：`.superpowers/test-002-review-brief.md`、根 `AGENTS.md`、两份通用执行规范、PRD-002/ADR-002 的范围与不变量、正式 TEST-002 方案。
- 本次只创建此报告；未改实现、index 或 branch，未执行 Docker，未派生代理，未重复工具自测。
- 结论：**稳定子集需修正后复核；本报告不作整套环境或产品验收通过结论。** 运行器及 Frozen 实现仍在集成，真 Docker 两轮/失败/强停恢复均未由本审查验证。

## 发现

### Important I-01：setup 在本次未创建临时目录时也会递归删除它，祖先链接未受保护

- 位置：`tests/sesrag-persistent-session-workspace-test/setup-tools.ps1:15`、`:26`、`:49-53`。
- 根因：使用固定 `.cache/setup-tmp`，`finally` 只看目录当前存在与叶目录 `LinkType`，没有记录本次是否创建、独占身份或验证祖先目录。
- 影响：若该目录此前存在，而 Node/依赖前置检查在创建目录之前失败，`finally` 仍删除此前目录；若 `.cache` 是指向 suite 外的链接，叶目录可以是普通目录，递归删除仍会进入外部目标。代码注释“只删除本脚本创建”与实际条件不符。
- 建议：写入前校验 suite/cache 及全部祖先的解析边界与链接；创建随机且独占的临时目录并记录本次创建身份；仅在身份和路径再次确认后删除。补充“前置失败保留旧目录”和“祖先链接拒绝且目标内容不变”反例。
- 处理状态：**静态复核关闭**。修正版采用 GUID 专属目录、创建标志和 owner marker，安装及删除前检查完整祖先 ReparsePoint，删除前还检查目录内链接。`compose-entry.test.mjs:64-81` 新增真实 junction/symlink 外部文件保留反例；根代理转发 5/5 与 setup 再次 exit0。本审查未重复运行。

### Important I-02：源码指纹遗漏正式前端契约生成/检查工具

- 位置：`tests/sesrag-persistent-session-workspace-test/tooling/preflight.mjs:19-20`。
- 根因：`SOURCE_ROOTS` 仅包含 `frontend/src`，`SOURCE_FILES` 未包含 `frontend/scripts/generate-api-types.mjs` 或其目录。
- 影响：`frontend/package.json:7-8` 的 `generate:api` / `check:api` 实际执行该文件，且前端 Dockerfile 会复制整个 frontend。修改它不会改变 `source_digest`，Git `dirty_paths` 的 pathspec 同样漏掉它。后续同源 All/冻结复用可能把改变过的契约门禁工具当成未变。
- 建议：将 `frontend/scripts` 纳入受测/工具指纹，按实际构建与质量命令核对其余输入；添加“文件出现在 manifest 且内容变化改变 digest”的负例。本项针对稳定的指纹输入范围，不评价仍在变更的 Frozen 实现。
- 处理状态：**静态复核关闭**。`SOURCE_ROOTS` 已加入 `frontend/scripts`；`compose-entry.test.mjs:60-62` 断言正式生成工具实际出现在 manifest。根代理转发全套 npm 63/63；本审查未重复运行。

### Important I-03：专库工具分类白名单与八分类协议不一致

- 位置：`tests/sesrag-persistent-session-workspace-test/tooling/db-admin.py:18`、`:53`。
- 根因：`CATEGORIES` 最后一项为 `security`，正式 `manifest.json` / `preflight.mjs` / TEST-002 最后一类是 `quality`。
- 影响：合法 `sesrag-ws-<suffix>-quality` 专库操作在连接前被 `NAMESPACE_REJECTED`；未登记的 security 子 project 反而被白名单接受。Environment 的 env 自检不能发现这处未来分类接入缺口。
- 建议：同步正式分类真源；增加八分类（尤其 quality）正例，以及 security/未知分类反例，避免仅测 env。
- 处理状态：**静态复核关闭**。白名单已改为 quality；Python 自测新增 quality 正例/security 反例。根代理说明先红后绿并转发指定 suite 离线缓存后 26 passed / 1 Windows symlink skipped；首次未指定缓存的素材失败保留为环境输入问题，不抹除。

### Minor M-01：Provider 自测未针对性证明慢流和 stall 上限

- 位置：`tests/sesrag-persistent-session-workspace-test/tooling/provider-selftest.py:217-220`、`:319-322`。
- 根因：超限 stall 测试使用 `kind=normal`，而服务对任意非 stall 的 `stall_timeout_ms` 都会拒绝；slow 检查仅验证分片数，与 normal 等价。
- 影响：若移除 stall 最大时长校验，现有超限测试仍因“参数不适用于 normal”而绿；若移除 slow 的实际片间等待，多片数量断言仍绿。目前实现可见有时长校验和 sleep，因此这是反例覆盖弱点，不是宣称当前响应错误。
- 建议：以 `kind=stall` 测 180001ms 被拒及边界合法值可配置；用流式读取验证首片先到、后片需经受控间隔到达，采用宽容差和足够延迟，避免以整体正文和分片数代替慢流证据。
- 处理状态：**静态复核关闭**。修正版 `provider-selftest.py:88-108` 逐帧读取，slow 配置三片/180ms，并断言前两次间隔各至少120ms；`test_environment_tools.py:31-43` 的 no-wait BufferedResponse 替身必须触发 SelfTestFailure。stall 已改为同 kind 的 180001 拒绝/180000 合法配置正反例（不实际等待180秒）。根代理转发宿主 27 passed / 1 skipped，真实诊断轮 Provider 十组 passed；本审查未重复执行。

## 逐项方案符合性

| 项目 | 静态结论 | 证据或保留条件 |
| --- | --- | --- |
| ENV-01 独立目录/职责/分类 | 稳定部分符合 | suite README、接入计划、manifest 的八类全部 planned、script=null/cases=[]，无产品分类脚本。I-03 须修正。 |
| ENV-02 工具/浏览器/离线词表 | 具备实现和已有工具证据；非环境审批 | setup 使用本 suite Playwright；Node/Python 依赖有锁定；离线词表走当前应用正式离线 loader。I-01 和 M-01 须处理。工具容器真实导入来源仍需集成验证。 |
| ENV-03 隔离与凭据 | Compose 静态边界符合，完整生命周期未验证 | 显式 suite env/file；无 PG/Redis 宿主端口；API/frontend/control 为 127.0.0.1/动态端口；独立具标签网络/卷；不挂根 .env/整个仓库/Docker socket。随机生成、ACL、Engine/账本/回收由后续整体验证。 |
| ENV-04 正式迁移/Profile/就绪 | 部署接线符合；真实运行未验证 | migrate 正式 upgrade head；profile-init 正式同步器；API/Worker 等待完成；Worker readiness 不等于 running；探针只读检查实际迁移 head、vector、四 Profile、Redis、API/Worker、frontend 同源 health。 |
| ENV-05 两次空环境 | 未验证 | 本审查没有真 Docker 证据，不以工具测试代替两次 Environment。 |
| ENV-06 分类协议/空结果不通过 | 契约/接入规范静态符合；运行器最终状态暂缓 | 三份 Schema 已存在，结果要求非空 cases；manifest 为 planned；产品计数与工具探测分离。运行器仍变更，不能据之前自报结果给最终审批。 |
| ENV-07 故障/中断/恢复 | 暂缓 | 真实故障、强停恢复、幂等 cleanup 由根代理完成并追加审批。 |
| ENV-08 残留/既有资源保护 | 暂缓且有 I-01 | Compose 的独占资源定义可见；删除安全/实际残留必须结合稳定运行器和真实资源审计。缓存与 artifacts 保留已在 README 明示。 |
| ENV-09 安全报告/可追溯 | Provider/Python 工具静态质量良好；全链路暂缓 | Provider 分离两个端口/凭据、限额与截断标志、屏障/实例身份；观测仅摘要；Python 工具公开稳定错误码而非异常/凭据。I-02 修正前不能完整声称工具同源。 |
| ENV-10 不偷偷实施产品/质量缺口 | 符合当前范围 | 无产品 API/状态机/迁移修复；GAP-01/02 和八分类后续路线保留；正式 PRD 验收仍 not_run。根导航仍有“环境尚未实施”的旧状态文字，应在最终交付时同步真实阶段，不在当前集成中误写完成。 |

## 质量核查

- Provider：请求/响应/片段/观测容量有界；控制鉴权和推理鉴权分别检查；场景变更与 reset 拒绝 in-flight；release 核验模型/序号/屏障；实例每次启动有随机身份。未发现当前稳定实现的确定性 Critical 问题。
- Python 工具：DSN 主机/库/用户限制、server system_identifier + cluster_name + current identity、数据库 comment 所有权、SQL Identifier、非空 probe 拒绝、无 FORCE/终止连接均可见。技术探针未创建 Thread/Run；fixture 输出确定性 ZIP、hash/token 清单，不生成成功业务事实。
- Compose/ignore：正式迁移和 Profile 依赖正确；复用相同应用 tag；限定源码只读挂载；runtime/artifacts/tmp/node_modules/.cache 及本地 env 均有 Git/Docker ignore。未读取根 .env。
- 契约与文档：接入规范明确上下文、case 集合、非零失败、证据路径和产品/环境分离。Schema 只能提供结构校验；身份、相对路径、case 精确集合和状态一致性仍依赖运行器，留待其稳定后的整套审批。

## 已有运行证据及本次未验证项

以下证据由根代理转发，属于本会话已有运行结果；本审查未重复执行，也未把它们升级为真 Docker 或产品证据：

| 已有证据 | 转发结果 | 限制 |
| --- | --- | --- |
| setup-tools.ps1 主机实跑 | exit0；Node 24.18.0 / Chromium 156.0.8078.4；空页启动关闭成功 | I-01 路径/失败安全未由该正常路径证明。 |
| compose-entry.test.mjs | 3/3 | 配置解析与语法测试，不连接 Engine。 |
| Node preflight | 8类、8required、0case、29需求映射、3 Schema | I-02 的未收集文件不会自动显现。 |
| Provider 独立协议自测 | 10组连续3轮 passed | M-01 所述回归检出能力仍不足。 |
| Python 工具自测 | 24 passed / 1 Windows symlink skipped | Windows 链接拒绝分支没有本机动态证据；专库真实创建/删除由真 Docker 验证。 |
| 运行器自报 npm 全套 | 55 项通过 | 根代理拟重跑；运行器/Frozen 仍变更，本报告不采用为其最终审批。 |

未运行/未验证：真 Docker Environment 两轮；真实迁移/Profile/API/Worker/frontend/Provider 组合启动；工具镜像 `/work` 导入来源；专库真实 create/inspect/drop；真实失败 finally 清理；强停后恢复和重复 Cleanup；容器/网络/卷/tag/宿主进程/私有目录的最终独立残留扫描；最终全套运行器/Frozen 审批；全部产品分类与正式两轮 All。

本报告是第一阶段静态初审。根代理完成修正、集成和真实环境演练后，需要追加最终审批，不能用此报告宣称环境实施完成或 PRD-002 验收通过。

## 第二阶段：运行器及 Frozen 静态复核

根代理要求在运行器/Frozen 稳定后扩大静态范围。原三项 Important 已按修正代码和新增测试源码复核关闭；以下为扩大全套后新增的问题，已逐项反馈根代理。根代理正在补失败测试及修正，因此此节是待闭合清单，不是冻结的最终通过结论。真实 Docker 证据仍未到达本审查。

### Important I-04：正式 All 没有执行质量前置门禁

- 位置（发现时）：`tooling/report.mjs:79-81`、`:111`；`tooling/orchestrator.mjs:413-418`。
- 根因/影响：All 在已有 passed 且 environment passed 时即可 `product_acceptance=passed`；`quality_prerequisites` 默认 pending 且主入口没有 ready 来源。因此会出现产品完整通过与前提 pending 同存，违反 TEST-002 §12。
- 建议/状态：All 必须明确 ready 才可完整通过；pending/blocked 为 incomplete/exit3，保留产品失败与工具失败的原优先级。根代理已新增 `self-tests.test.mjs:383-390` 对 pending/blocked/ready 的正反断言；实现和实际结果待复核。

### Important I-05：公开 PurgeToolCache 仍为始终拒绝的未完成功能

- 位置（发现时）：`run-workspace-tests.ps1:16`；`tooling/orchestrator.mjs:32`、`:41`。
- 根因/影响：PowerShell 暴露开关，TEST-002 §11.3 规定受限清 suite 缓存，但解析器对任何该开关无条件报“尚不支持”。不能以已暴露参数代替方案实现。
- 建议/状态：**转为显式未实施的可选范围差异**。TEST-002 v1.2 §8.1 实施差异/§11.3 及 suite README 已明确未实施、传入退出2、缓存保留及后续安全条件。正常本轮数据清理不依赖此开关，因此不继续作为运行数据清理阻碍；交付必须继续披露，不能声称原方案全部可选能力已完成，也不能说缓存已删除。

### Important I-06：分类清理会把同一轮其它 project 当成非法残留

- 位置（发现时）：`tooling/orchestrator.mjs:285-286`、`:296-298`；`tooling/resources.mjs:73-85`、`:104-107`。
- 根因/影响：分类清理把允许 projects 缩到当前分类，但 discover 仍按 run_id 找整轮全部项目。只要本轮 build project 或其它已登记项目仍有网络/资源，当前分类清理便将其判未登记、跳过 down 并把它算残留。首次冻结的 build-project 工具运行是需验证的实际触发源。
- 建议/状态：分类清理按当前 project+owner 发现及审计；整轮最终清理再按 run+所有登记项目全面发现。增加同 run 的 build/当前分类双 project 替身，确认只清当前分类且不误报另一项目；真实网络情况随后由 Docker 证据确认。已反馈，待复核。

### Important I-07：父进程消失不等于整棵本轮进程树退出

- 位置（发现时）：`tooling/process-registry.mjs:38-49`、`:60`、`:86-97`；`tooling/orchestrator.mjs:237-245`。
- 根因/影响：只登记 spawn 父 PID。父进程生成长活子孙后先退出时，父 PID 不存在会被当作 already_exited；cleanup 随后把父 entry 标 inactive，子孙未登记且 residual.processes 可为空。若子孙继承 pipe，runCommand 可先超时，但最终清理仍可能漏报残留。
- 建议/状态：登记/核验整个本轮树，或使用受控 OS job/process group 并检查其残留；无法证明树为空时不能宣称 cleanup passed。增加“父先退出、子孙持续运行”的反例。此为静态路径推导，本审查没有启动新进程测试；已反馈根代理验证并修正。

### Important I-08：分类日志超限后仍可被计 passed

- 位置（发现时）：`tooling/category-runner.mjs:28-34`；`tooling/process-registry.mjs:63-66`、`:99-103`。
- 根因/影响：process 层超限会丢弃整段 stdout/stderr 并置 truncated；分类层只拒 timedOut，不拒 truncated。分类打印超限日志后提交合法 passed JSON/exit0，仍被计 passed，必须的逐例日志已丢失。
- 建议/状态：超限输出作为 harness_error，保留截断标记；加入“超限日志+合法 passed 报告”负例。已反馈，待修正复核。

### Important I-09：Environment 的运行环境与保留空间记录不完整

- 位置（发现时）：`tooling/orchestrator.mjs:122-136`、`:191-205`、`:285-287`；`tooling/resources.mjs:41-44`、`:65`。
- 根因/影响：仅未来 Selected/Frozen 路径采 tools Python 包；Environment 未保存 app/tools 实际解析依赖、前端运行 Node、Compose/宿主 PowerShell 版本或 `/work` 导入来源。retained 只有类别字符串，没有本轮/累计 artifacts、缓存/冻结归档大小。无法达到方案 §3、§4.1、§11.3 所需的环境可追溯证据。
- 建议/状态：在 Environment 采集无 Secret 的版本/依赖/导入来源和目录容量 JSON，分别标 app/tool/frontend；共享 Docker 缓存不能分摊时明确 unknown。已反馈根代理补充，待复核。

### Important I-10：构建与 Environment 就绪的阶段预算未整体约束

- 位置（发现时）：`tooling/orchestrator.mjs:138-147`、`:149-165`、`:193`，对比 Selected 的 `:313-315`。
- 根因/影响：三个 build 各可用 1800 秒，没有共用阶段 deadline；Environment setup 的 base/migrate/profile/app 各自拥有最长 300 秒，未像 Selected 包整体 deadline。总构建可达约 90 分钟，就绪可达约 20 分钟，超出方案“构建阶段 1800 秒、每子环境就绪 300 秒”。
- 建议/状态：以一个阶段 deadline 包完整 build/setup，继承到每条命令；加入阶段预算耗尽后不再启动下一命令的替身反例。已反馈，待复核。

### Frozen 与其它运行器防护的静态观察

- Frozen 实现验证 manifest 完整键、source/node/依赖/锁文件摘要、镜像 ID/来源、归档 hash/大小；按镜像 ID save，拒归档 RepoTags/repositories/命名 annotation，load 后核验全部 ID/来源才挂本轮 tag。自测归档按 tar 字段独立构造，覆盖缺文件、hash/身份/来源/版本不符、tag 冲突、旧 tag、链接和半成品。尚未由真实 Docker 验证格式及恢复行为，因此只能给静态符合结论。
- 当前进程层具备 UTF-8 分块解码、已中断不启动、输出总量限制、发布前脱敏和父进程创建身份核验；分类层具备精确 case 集、身份/退出码/逐例状态一致性、历史报告拒绝及证据真实路径检查。新增问题 I-07/I-08 仍须闭合。
- 清理层在 down 前核对 owner/run/project、先后核对 Engine、按登记 tag/ID 删除并独立复查；错误 owner/未知 tag/复用 PID/晚出现残留均有针对性自测。I-06 需处理清理的范围层级。
- 所有新增问题及其修正须保留反例和原始失败证据；本审查仅更新报告，不改实现、不执行 Docker、不重复已有命令。后续应追加最终实际结果，而非删除此初审记录。

## 第三阶段：元数据与 Provider 修正复核

### 1. 新增运行清单

已完整审阅 `tooling/runtime-inventory.mjs` 与 `.test.mjs`，并只读核对真实诊断轮 `artifacts/ws-20261021t154615z-02b55225/diagnostics/runtime-inventory.json`。

- 代码先按 project/service 找唯一容器、核对 run/owner/project 后才 exec；仅投影版本、包名/版本和镜像 ID/digest，没有把 inspect Env、pip 配置或环境全集写入清单。三项新自测包含无 Secret 投影、错误归属不 exec、空间汇总不删数据；根代理转发三项 passed，本审查未重跑。
- 真实记录：宿主 Node `24.18.0`，前端 Node `v20.20.2`，Compose `5.1.1`，PowerShell `7.6.5`；app/tools 均 Python `3.12.14`，分别45/60个包，有各自SHA256；app/provider/frontend的实际镜像 ID 和 digest 已记录。
- 真实空间记录：历史 artifacts 合计256853字节、node_modules 20067012字节、.cache 1462709184字节、frozen-builds 0字节；浏览器救援缓存独立记录。共享 Docker cache 的 bytes 为 null，并说明不可安全分摊、不全局清理。
- **I-09 大部已修，尚待完全闭合**：当前只有全部 artifacts 总量，没有本轮 artifacts 单独容量；仍未见正式工具容器将 backend/实际集成探针的导入来源核验为 `/work` 的执行与结果。后者是 TEST-002 §4.1 明确要求，provider 容器的 pip 元数据不能代替带 `/work` 挂载的工具导入证据。已反馈根代理。

### 2. Provider 反例

M-01 已按上述代码及 no-wait 负例关闭。新前端技术探测 Host 处理亦已审阅：仅向固定 Docker DNS frontend 地址发送模拟回环 `Host: 127.0.0.1:5173`，没有关闭 Vite 主机名保护；新增测试明确核对 Host 值。此修正是探测适配，不是产品前端配置变更。

### 3. 诊断轮证据边界

已只读核对 `ws-20261021t154615z-02b55225` 的以下报告：

| 证据 | 观察结果 | 审批含义 |
| --- | --- | --- |
| environment-probe.json | configuration/encoding/database/redis/provider/api/frontend 七项 passed；product not_run | 证明该次技术探测实际通过，不代替产品分类。 |
| provider-selftest.json | 十组 passed；product not_run | 受控协议已在组合环境执行。 |
| probe-database.json | 创建/复查为空、object_count=0、删除后exists=false；business_probe_executed=false | 正确验证专库工具，没有冒充产品竞态探针。 |
| cleanup.json | passed；容器/网络/卷/tag/进程/runtime/tmp全部残留数组为空；preexisting_missing均空；errors=[] | 这是该诊断轮记录的真实清理证据，本审查未自行操作 Docker。 |
| summary.json | environment failed、product not_run、cleanup passed、source_unchanged=false、original/final exit2，原因明确运行期源码变化 | 如实阻止同源声明；**不能计作最终两次成功 Environment 的任一轮**。 |

本阶段复核只闭合 Provider Minor 和 I-09 已完成部分，接受 I-05 的明确可选范围差异；I-04/06/07/08/10 的实现与最终稳定证据待根代理交付后复核。尚未获得最终两次同源空环境闭环、真实故障/强停恢复及最终独立残留对照，不作最终环境审批通过结论。

### 4. 冻结前确认的保守差异与未验证项

根代理已通知最终同源第一轮启动，不再修改受测源码。本审查仅维护此 `.superpowers` 报告。

- 本轮 artifact 单独容量：将由最终独立审计 artifact 补充，并写入环境验证记录；在读到该证据前维持待核对，不能拿历史总量代替本轮大小。
- `/work` 导入来源：现有证据是 Compose 的受控只读挂载、`PYTHONPATH=/work:/suite` 静态接线和真实工具 pytest 执行路径；**专门的动态 import 来源断言未运行**。最终交付应如实说明该验证缺口，不说已完成专测。
- 所有账本完全丢失时：当前代码采用更保守的拒绝策略。仅 runtime 私有账本丢失时可读取 artifact `recovery-ledger.json`；runtime 与全部 artifact 账本均丢失时，没有原 Engine/owner/project 依据，不仅凭资源标签扩大自动删除。原方案“完全缺账本时标签唯一即可降级回收”的能力**未实施**，根代理将校准方案。此差异不会引入误删风险，但操作者需要先恢复可靠账本或人工核对；不能将全账本丢失恢复写成已自动验证/支持。
