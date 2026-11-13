> 2026-11-13修复回归已完成：248例采用239通过、0未通过、9暂不可验证、0工程错误；本机220例完整通过、ENV十例生命周期审计通过、八个真实办公样本及预算检查通过。额度/DNS已实测解除；正式生成与真实检索/重排/效果仍缺适用计数依据。详见测试报告和缺陷报告。

# PRD-003：RAG检索增强与MinerU接入测试工程

本次修复过程与剩余计数门槛见[修复计划](缺陷修复实施与回归计划.md)、[计数资料复核](计数资料复核记录.md)及[产品变动记录](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-缺陷修复记录.md)。下列任务5～6章节保留修复前历史；本段与最新报告／逐例结果为当前结论，不将历史网络问题继续视为当前阻碍。

本目录用于v0.3独立本机验收，不读取开发`.env`，不复用前轮验收脚本／数据卷。14类脚本及240个可验证设计目标已接入；2026-11-13修复回归已完成：248例采用239通过、0未通过、9暂不可验证、0工程错误；本机220例完整通过、ENV十例生命周期审计通过、八个真实办公样本及预算检查通过。额度/DNS已实测解除；正式生成与真实检索/重排/效果仍缺适用计数依据。详见测试报告和缺陷报告。 见[测试报告](测试报告.md)、[缺陷报告](缺陷报告.md)及[248例实测](test-cases.md)。

2026-11-11原环境实施已完成同源两轮Environment（各退出0）及启动失败、技术子进程失败/超时、主进程强停恢复与重复Cleanup工程演练，25项宿主工程自测通过。随后任务1～2补齐准备工程，41项宿主自测及更新后一次Environment通过，三个planned拒绝路径与重复Cleanup符合预期。本轮Docker容器/网络/业务卷/tag及runtime/tmp复查为空，既有资源保持。真实Ctrl+C及Linux宿主尚未实测。

实际命令、排错与最终结论见[环境实施与验证记录](环境实施与验证记录.md)。

## 当前文件

| 文件 | 用途与当前状态 |
| --- | --- |
| [测试点设计与需求覆盖矩阵.md](测试点设计与需求覆盖矩阵.md) | 248个原子测试点，分18类，双向映射46项功能需求和12项非功能需求；说明目标、代码依据、优先级及可验证条件，作为用例和脚本的追溯依据。 |
| [test-cases.md](test-cases.md) | 248例中文设计，逐例给前置/数据组/流程/预期/代码依据及需求映射；修复后L/K/R为225/5/10例（R为真实条件验证），B/D为5/3例暂缓。已按实际证据回填；受限项仅填原因，ENV来源明确，不以环境通过替代产品通过。 |
| [测试报告.md](测试报告.md) | 修复后完整本机回归、ENV审计、真实逐格式联调、性能／质量、命令、清理和限制；修复前两轮单独归档。 |
| [缺陷报告.md](缺陷报告.md) | 任务6逐项解释所有失败／受限、定位、影响、复现及整改建议；额外工程观测缺口单列。 |
| 本README | 目录入口、文档导航、当前交付状态与后续工作说明。 |
| run-rag-tests.ps1、helpers/orchestrate.py | PS仅包装，Python唯一实现五模式生命周期。 |
| setup-tools.ps1、package/lock、requirements-test.lock | 宿主辅助依赖和独立工具镜像依赖锁定，不复用前轮浏览器。 |
| manifest.json、schemas/ | 12个local及3个real分类的状态与逐例追溯清单、context/result/manifest严格协议。 |
| compose/ | 独立local/real编排、tools镜像、无Secret环境模板。 |
| [harness/](harness/README.md) | local控制面、跨进程计数/屏障及生产协议受控传输，不放宽产品安全。 |
| [helpers/](helpers/README.md) | 预检、初始化、探针、DB夹具、构建、采证、清理和工程自测。 |
| [fixtures/](fixtures/README.md) | 固定源hash/许可、虚假基线、非Secret配置、边界输入生成及计数/评测协议。 |
| [test-plan.md](test-plan.md)、[分类脚本规范](specific_test_script/README.md) | 环境实施清单及后续用例/分类脚本接入计划。 |

测试点设计时的历史基线为L/K/R/B/D/E=214/5/10/5/4/10；原E的10点转L后为224/5/10/5/4/0，本次修复再将EVAL_001从D移至L，现为225/5/10/5/3/0。环境结果另记，不能因环境通过就将产品点写为通过。具体定义见测试点文档第2、6节与用例文档第1、3节。

任务1～2复核已修复用例设计时记录的真实准入耦合：`helpers/live_preflight.py`按LivePlan的`capabilities`核验所选能力，`preflight.real_gate`保留原入口。缺省仍是完整四能力；Acceptance禁止缩减范围。仅MinerU不要求模型计数，仅生成要求自己的计数材料；完整真实链仍要求全部配置、三份计数依据及校准。部分范围成功汇总为`real=partial_passed`，不得写成完整真实业务通过。planned分类先拒绝，不读取无必要Secret。

本次新增`helpers/baseline.py`（固定虚假身份/配置声明校验）、`helpers/live_preflight.py`（离线分能力门禁）、`helpers/selftest_preparation.py`（准备工程正负自测）；补齐tools的mypy、前端源码/独立npm依赖和契约。实际验证与剩余条件见[任务1～2准备与验证记录](任务1-2准备与验证记录.md)。该历史阶段没有接入产品分类或发真实请求；后续任务3～4进展见下文。

## 部署与闭环执行

宿主需要PowerShell 7.4+、Python 3.11+、Docker Linux Engine、Compose 2.24.4+及Git。Windows使用Docker Desktop Linux容器，Linux使用Docker Engine。setup使用项目解释器或系统Python创建专属`.cache/host-python`，只在该环境安装辅助依赖，不修改项目`.venv`。tools镜像使用产品Python 3.12、独立Node 22.13.1、锁定Playwright 1.58.2及配套Chromium；前端仍用原生产Dockerfile，不改变产品技术栈。

Windows在项目根目录执行：

```powershell
pwsh -NoProfile -File .\tests\sesrag-rag-mineru-test\setup-tools.ps1
pwsh -NoProfile -File .\tests\sesrag-rag-mineru-test\run-rag-tests.ps1 -Mode Environment
```

Linux在项目根目录执行（系统Docker/PowerShell/Python先按发行版安装，本脚本不提升权限）：

```bash
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/setup-tools.ps1
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment
```

无需手动up/down。首次构建联网下载公开依赖，运行阶段local网络internal、只带dummy凭据。建议Docker分配4核/8GiB、宿主至少20GiB可用；预检最低5GiB不等于性能达标。

Environment流程：随机凭据→固定输入hash校验/复制→构建三镜像→PG/Redis→分段迁移到0011→固定owner基线核验与显式Profile导入→API/Worker→同源HTTP/SSE、Chromium、离线词表、质量工具可用性与工程自测→采证→down销毁业务卷→独立残留复查→删除runtime/tmp→保留脱敏报告。SSE用一次Mock/off技术输入确认代理，product仍为not_run，不算产品用例通过。

tools只安装Playwright配套的Headless Shell及FFmpeg；首次构建按官方清单有界续传、核验包后交官方安装器解包。系统库、浏览器及应用层分开缓存，运行期不下载。测试API地址使用本轮前端容器IP走同源代理，保留Vite原有Host防护。

主入口打印run_id。需要短时观察可加`-HoldSeconds 60`，上限300秒，没有永久保留或跳过清理开关。前端只映射127.0.0.1随机端口，地址写本轮project的addresses.json；API/PG/Redis不映射宿主。

```powershell
# 明确指定尚未使用的ID；重复ID拒绝覆盖。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -RunId rag-local-manual-0001

# 中断或Docker恢复后，对同一ID恢复清理；可重复执行。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Cleanup -RunId rag-local-manual-0001
```

Linux使用相同pwsh参数。成功Environment的summary.json记录`frozen_build`，后续可将该值作为`-FrozenBuild`参数复用归档；源/依赖/配置不符会拒绝。归档保留镜像内容及hash，不只保留image ID。

```powershell
# 后续同源复验：先读取实际首轮构建标识，不传build.json路径。
$taskFirstRun = Get-Content -Raw ./tests/sesrag-rag-mineru-test/artifacts/<首轮run_id>/summary.json | ConvertFrom-Json
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -FrozenBuild $taskFirstRun.frozen_build

# 只执行所选ready分类；每例独立PG、中文过程与证据。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories 'ingestion,retrieval'
```

## 模式和报告

| 模式 | 当前行为和结果边界 |
| --- | --- |
| Environment | 可执行技术闭环；0仅表示环境/清理通过，产品not_run。 |
| Selected | 必须指定Categories，只运行ready分类，每分类独占project；planned项not_run并退出3。 |
| All | 全部12个local分类已ready；逐类独立部署/采证/销毁，覆盖220个本地产品用例。 |
| Real | 需要AllowRealRequests、runtime-inputs内LivePlan和独立能力/计数/授权/hash/预算门禁；默认无外发，Business/Acceptance分别控制范围；Business可用Categories显式选择real-formats或real-business，未满足的条件如实受限。 |
| Cleanup | 按可信账本恢复本轮资源；原进程仍活动、Engine不符或账本丢失时拒绝猜删。 |

退出码0为请求范围通过，1产品失败，2工具/参数/报告/运行器错误，3受限或范围未完整执行，4清理失败/无法核验；优先级4＞2＞1＞3＞0。Environment/Selected/All返回0都不等同完整PRD验收通过。

每run保存summary.json/summary.md、environment/preflight、分类及安全日志、指纹、cleanup.json、recovery-ledger.json、证据hash索引。空报告、漏/重复case、错run/lane、坏hash或退出0无证据均为工程错误，不能passed。

### 后续真实计划准备约定

`fixtures/live-plan.example.json`新增`capabilities`：`mineru/embedding/rerank/generation`的非空无重复子集；旧计划省略字段仍要求四项。Business允许独立能力补证，Acceptance必须四项。`counter_evidence`每条需`capability/file/sha256`，文件内容须与声明能力、模型相符，具备revision、算法、来源、日期、适用上限及通过的输入hash校准记录；资料存在性校验不能替代真实性审核或产品正式counter守卫。

MinerU需要自己的Key、32字节Base64状态加密Key、明确存储域白名单及获准原件；Embedding/rerank各需自己的Key/Profile/计数依据；生成需自己的Key、openai_compatible+tiktoken配置和生成计数依据。只选择生成时可不提供外发文件；有文件仍须hash核验。未选能力的逻辑预算置零、凭据不转发。真实Key只注入API/Worker，迁移、Profile导入和tools不接收供应商Key。后续真实业务必须走正式API，不能在tools拿Key直接请求来冒充业务闭环。

用户指定的`docs/secret/准备的配置信息.md`为后续显式准备来源；常驻运行器不自动读取它。私有计划/配置/独立别名放`runtime-inputs/`，授权与样本hash逐次确认。本次只检查准备工程，没有发真实请求、校准真实计数或确认服务额度；不能将Key存在当作服务可用。

后续分类读取`context.real_capabilities`和`/config/live-inputs.json`中的能力/有效预算。需要未选能力的用例必须如实blocked或not_run并说明；不能遗漏manifest case、伪造通过或将部分计划计为完整真实链。`helpers.live_budget`仍逐操作预留，未知提交不退款。

## 清理与空间管理

runtime和tmp按run_id隔离，包含随机DB密码、完整有效Compose、tools权限及原始临时输出，成功清理必须删除。artifacts保留脱敏报告和恢复账本，累计2GiB软门限/单轮200MiB；`.cache/frozen-builds`保留镜像归档，10GiB软门限；runtime-inputs保留操作者原始私有输入，不随单轮删除。上述目录均被Git和Docker构建忽略。

正常先down/volumes，再按Engine、suite/run/随机owner完整标签及真实ID复查容器/网络/业务卷/专有镜像tag/子进程/runtime/tmp。Windows用Job回收CLI进程树。只删本轮tag，不按共享image ID强制删除；不执行全局prune，不碰其它项目。Docker无法核验/所有权不符时cleanup失败、保留材料；强停后Cleanup补恢复摘要，不补造通过。

报告、明确依赖/浏览器/构建缓存、冻结归档及runtime-inputs属于有意保留项，需单列占用；业务卷和运行凭据不属于保留项。Docker共享基础镜像与BuildKit缓存可能占空间，本工程不擅自清除其它项目共用内容；删除冻结归档前需确认无活跃/同源复验依赖。本机销毁不保证云端撤回或费用归零。

## 依据与导航

- [PRD-003](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：需求边界、功能/非功能要求及完整验收标准。
- [ADR-003](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md)：实现决策、不变量及实际实施差异。
- [实施结果简要说明](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)、[实施结果调研](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-实施结果调研.md)：当前实现及后续测试关注点。
- [TEST-003测试实施方案](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：后续Compose、总入口、工具、数据、报告协议及资源销毁闭环的实施依据。
- [正式接口说明](../../docs/接口文档.md)、[通用测试规范](../实施测试文件时的通用规范.md)：契约真源与测试实施约束。

## 后续准备顺序

1. 按环境实施记录确认专属环境、总入口、工具/数据/受控transport、证据和清理结果，不将环境技术探针当产品验收。
2. 按已完成的248例`test-cases.md`准备专属数据/观测和分类脚本，集中到`specific_test_script/`，按协议接入；每点一例，同一规则的边界数据合组。分类脚本/manifest已接入，逐例覆盖关系见下表；试跑工程错误须先修复，产品断言失败保留证据。
3. 对真实Embedding/rerank与生成补齐计数依据与校准；20+5独立原源标注及指标工程已准备，真实效果仍待前提满足后执行。真实MinerU已逐格式复验，后续复测仍需独立核验授权、配置、网络及预算。
4. 接入后执行本地同源复验、真实业务及格式/效果/性能验收，分别收集测试报告、缺陷报告和清理证据。已知差异保留产品目标；未运行、受限和失败分别登记。

本轮环境工程及任务1～2验证均不发起MinerU/真实模型请求。已有开发探针和历史结果不替代后续产品正式验收。真实配置只从明确runtime-inputs复制所选能力必需值，不自动扫描docs/secret或共用宿主Key；计数未校准仍blocked，不能改verified或切Mock掩盖。


## 任务3～4分类脚本与用例映射

以下脚本均位于`specific_test_script/`。每例输出准备、执行、观察、结论及断言数，结果/过程证据在`artifacts/<run_id>/<project>/<category>/`。普通用例由正式API/Worker建立前置，使用每例专属PG派生数据库；纯函数/协议负例与性能直接注入均明确证据类型。

| 分类脚本 | 用例范围（数量） | 主要验证方式 |
| --- | --- | --- |
| catalog-tests.py | CAT_001～015、017～018（17） | 知识库、Profile、固定向量空间、owner/分页/版本约束 |
| ingestion-tests.py | INP_001～021（21） | 九格式/授权、源完整性、标签、幂等与未知提交 |
| mineru-tests.py | MIN_001～022、PAR_001～009、012～014（34） | 生产客户端受控HTTP、真PG状态恢复、安全下载/解包/位置 |
| chunking-tests.py | PAR_010～011、CHK_001～010（12） | 本地结构/独立区间oracle、参数HTTP边界及候选不可变 |
| vectors-tests.py | VEC_001～008、IDX_001～011（19） | 数值协议、真实PG关系/事务/代际/发布 |
| retrieval-tests.py | RET_001～017、019～023、ENH_001～009、EVAL_004～005（33） | 独立cosine参考、SQL过滤/排序、冻结View、重排/增强/范围 |
| execution-tests.py | CTX_001～009、EXE_001～019（28） | Run/ContextEvidence/Citation/Journal、重试取消与有效代 |
| workspace-tests.py | UI_001～018（18） | helpers/browser-cases.mjs在真实Chromium执行生产Vue组件/store；受控同源响应测试投影与异常 |
| compatibility-tests.py | CMP_001～014（14） | 本轮自建旧库、真实四迁移、旧协议、pg_dump/pg_restore、严格契约 |
| lifecycle-tests.py | LIF_001～010（10） | 实际生产GC/PG锁与引用、容量、文件/墓碑/时间边界 |
| performance-tests.py | EVAL_001、007～008（3） | 10000正式有效Chunk；100预热+100实测生产PG SQL；工程与产品计时分列 |
| quality-tests.py | REAL_012、QLT_001～010（11） | 公开安全/严格Schema/真实前端质量命令/浏览器非法事件/边界 |
| real-formats-tests.py | REAL_001～008（8） | 真实MinerU原件上传、独立源hash内容/结构断言；外部前提不足逐例blocked |
| real-business-tests.py | REAL_009、011（2） | 正式API/Worker真实生成；共享预算/未知成本边界；不冒称四能力完整链 |
| helpers/lifecycle_exercise.py、environment_cases.py | ENV_001～010（10，工程结果） | 两轮同源Environment、真实启动/超时/强停恢复和零残留；不注册第16个产品分类 |

CAT_016、VEC_009～010、RET_018、REAL_010（真实计数B）及EVAL_002～003、006（真实效果D）保留正式目标，未用Mock或空脚本填ready。EVAL_001已补原源金标并纳入local通过。10个R类已有脚本，本轮8个格式目标及预算例通过、生成仍缺计数依据；脚本存在不表示完整真实链已通过。

```powershell
# 当前全部220个local产品用例，失败仍采证并清理。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode All -RunId rag-task34-local-0001

# ENV十例工程审计：两轮Environment及真实失败/超时/强停演练，可能耗时数分钟。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-task34-engineering-0001

# 真实解析单能力补证示例；必须先提供明确私有计划/授权/hash/预算，不读取开发env。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/plan.json
```

新增辅助文件：`fixtures/case-catalog.json`保存设计追溯；`fixtures/real-expectations.json`保存独立源内容断言；`case_runner.py`统一执行/报告；`case_environment.py`隔离PG/正式调用；`legacy_database.py`仅旧库迁移夹具；`synthetic_rows.py`仅范围规模夹具；`live_cases.py`真实正式API/预算；`audit_cases.py`机械覆盖门禁。工具镜像使用与服务端匹配的PostgreSQL 16客户端，仅供CMP_012真实备份恢复。任务3～4当时未修改产品代码、契约、迁移；本次缺陷修复的产品变化见修复记录，前轮验收工程仍不变。

试跑和审批证据见[任务3～4实施与试跑记录](任务3-4实施与试跑记录.md)。上述为任务3～4试跑时的历史状态；任务5～6最新结果见文首和末节，试跑不冒充正式同源两轮。

## 任务3～4最终状态（2026-11-12历史）

分类脚本和239个可验证目标的追溯已落地，完整All及受影响分类已试跑。最新逐例联合结果为本地209通过、10失败、0工程错误；这是排错证据，不能拼作正式同源两轮。48项宿主工程自测通过；ENV十例及真实启动失败/子进程失败和超时/主进程强停恢复/重复Cleanup通过。所有本轮运行资源清理通过。产品失败、实际命令、文件职责、保留缓存和逐项审批见[任务3～4实施与试跑记录](任务3-4实施与试跑记录.md)。

真实单作业DOCX试跑最终为UPSTREAM_TEMPORARY_UNAVAILABLE，未重建云作业重跑；其余格式未纳入本次单作业计划，生成缺计数校准依据。真实10例为1通过/1失败/8受限，不能认定真实完整链通过。后续模型输出上限须不超过LivePlan预算；配置校验和hash来自同一份有界字节，复制后再次核验。真实文档向量预留采用保守片数上界：txt/md为正文字符数与50000取小，办公为50000；当前预算不足即上传前受限，不能预留128后无限处理。办公独立MinerU验证可用Mock向量，但只证明解析路径。

覆盖审计需产品依赖环境（tools内运行，或已安装仓库依赖的项目`.venv`），轻量宿主环境只负责生命周期。在项目根目录可执行：

```powershell
$env:PYTHONPATH = '.;tests/sesrag-rag-mineru-test'
& .venv/Scripts/python.exe ./tests/sesrag-rag-mineru-test/helpers/audit_cases.py
& .venv/Scripts/python.exe -m unittest helpers.selftest_runner helpers.selftest_preparation
```

以上为任务3～4交付时状态；任务5～6结果已更新见下，脚本ready仍不表示产品通过。

## 任务5～6正式执行与报告（2026-11-12历史）

248例采用结果：220通过、13未通过、15暂不可验证；本机219例最终同源两轮各209通过/10失败/0工程错误，清理通过。ENV十例复用任务4最终工程审计；真实格式已执行DOCX/DOC/文本PDF，其余5例因已证实CDN本机DNS异常受限，真实生成另缺计数依据且网关额度不足。完整PRD验收未通过。

新增文件职责已在“当前文件”表登记。`test-cases.md`保留248个设计目标并更新714个执行字段，15个受限项的30个复现／稳定性字段按要求为空。`specific_test_script/mineru-tests.py::min022`仅临时恢复被同进程Alembic禁用的logger，结束后还原；产品缺完整阶段字段的失败仍保留。未修改产品、契约、迁移或前轮测试。

本轮已明确调用用户指定配置文档，仅将所需别名放入Git忽略的`runtime-inputs`；总入口仍不自动读取secret文档。三个真实计划各一个新逻辑云作业；生成两个有界补充诊断均403且不作为正式Run通过。实际命令、完整指纹、计数／标注／DNS／额度限制和清理证据见两份报告。私有临时整理脚本不是分类入口，不影响manifest。

最终阶段计时复核：EVAL_008原断言经最终校审发现不充分；已在performance-tests.py补8阶段透明观测、已知20ms延迟、每阶段≥3样本及三组聚合统计。最终采用perf2／perf3两次同源定向补测，均退出0、清理通过；原完整两轮的弱断言passed不作本例充分证据。产品代码不变，其余本机用例仍采用local2／local3。

## 本轮测试工程修复（2026-11-13）

- `fixtures/source-annotations.json`和`source-annotations.schema.json`：20有答案＋5无答案的独立问句、答案／无答案依据与九格式原源投影坐标；金标冻结于检索前，来自固定原件及generate_fixtures.FACTS，不由MinerU返回或命中生成。跨片段题的两个必要范围分别保存；当轮实际Chunk用预冻结正重叠规则映射。
- `helpers/source_annotations.py`：只读固定原件的独立投影审计和唯一quote绑定。DOC使用FIB正文，PPT读取OLE文本记录，OOXML按节点文本、XLS按单元格、PDF按页文本投影，坐标均为投影内0起算Unicode右端不含范围。此工具仅验金标，不接产品Parser、不构成PDF／Office本地回退，不外发或改原件。tools新增锁定`xlrd==2.0.2`、`pypdf==6.11.0`；OLE使用产品基线`olefile==0.47`。只读真实产物可输出无全文绑定文件，缺quote／重复明确报错；不填假artifact hash，不改变现有evaluation.schema绑定协议。
- `helpers/evaluation_metrics.py`：同源同产物正重叠映射相关Chunk集合；Recall@20按有答案题平均，另报命中题比例；Top5 MRR／Recall配对保留下降题。离线计算器验证不代表EVAL_002/003/006已执行，summary.effects保持not_run。
- `helpers/resource_observation.py`：宿主仅对账本验证的当前project容器ID执行docker stats，每2秒、每次5秒超时、最多900轮／64容器，finally停止线程。保存resource-samples.json原样本、单容器采样CPU／内存最大值、漏采／失败／窗口耗尽。离散样本不证明连续真实峰值，亦非project并发总内存峰值；不向tools挂Docker socket。
- `summary.performance`按实际performance分类及资源证据归并，区分本机PG／受控计时、真实分类期间资源采样与未执行四能力全链。未执行评测不会由金标存在变成通过。
- `helpers/live_cases.py`真实文档向量操作默认预留最多128片，并将同一max_chunks随正式上传冻结；本地小文本可收紧，预算不足先于上传拒绝，无Embedding能力不预留文档向量额度。共享账本未知不退、真实计数门禁保持不变。
- `helpers/selftest_engineering.py`为本轮预算、金标绑定、指标及观测工程正负回归，接入正式tools工程自测。

离线命令：`$env:PYTHONPATH='tests/sesrag-rag-mineru-test'; python -m helpers.selftest_engineering`。实际变更、红绿证据与未运行检查见[修复记录](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-缺陷修复记录.md)；此命令无Docker／云请求。

### local1工程适配修复（2026-11-13）

完整All `rag-repair-20261113-local1`实际220例＝215通过／3失败／2工程错误，退出2且清理通过；本次只修测试适配，不改产品或原目标。RET_023规模夹具复制SQLAlchemy Computed列导致PG428C9，现`synthetic_rows.values`排除computed列；EVAL_004/005及CTX_004模型请求采集尚按旧无编号前缀识别，现`helpers/evidence_capture.py`用锚定正则识别可选`[S正整数] `与不可信证据标签，并在实际用例保留非空、user角色及来源编号断言；不是泛用contains。CMP_013工具环境缺正式接口文档，local/real Compose的tools均只读挂载唯一正式文档到`/app/docs/接口文档.md`，不挂其它文档、开发配置或Secret。

新helper仅测试采集，原引用／范围／两个条件断言全部保留。自测增至17项（computed排除、前缀正负例与来源号、两lane只读挂载），另48项基线通过；正式All复跑须新建FrozenBuild并重建镜像，不能复用local1旧指纹。

## 缺陷修复后最终回归（2026-11-13）

本机`rag-repair-20261113-local2`完整220例通过、退出0、清理通过；ENV完整生命周期审计10例通过。八个真实格式目标通过；扫描样本初次错分消耗1job，修复hash元数据筛选后以`scanfinal`补测通过，原结果保留。真实计划共享预算用例重复通过，生成计数门禁仍阻止正式Run。采用239通过/9受限，已回填248例。

新增工程文件：`helpers/evidence_capture.py`严格识别带S号的不可信证据；`helpers/synthetic_rows.py::values`排除Computed列；tools只读挂载正式接口文档及两份Compose YAML，不挂目录／环境文件。18项工程回归后补PDF筛选至19项，最终tools实测通过。

构建输入：本机完整回归及七格式使用`7ac937b6738a375690b417cc`，最后仅真实PDF选择器/其离线测试改变，`53534717c92a35f6739ad4ad`用于扫描补测。产品源码未再变化，不把不同完整source称为同源两轮。当前复现应重新构建，历史冻结包只用于相应基线。
