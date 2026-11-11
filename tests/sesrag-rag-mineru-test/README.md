# PRD-003：RAG检索增强与MinerU接入测试工程

本目录用于v0.3独立本机验收，不读取开发`.env`，不复用前轮脚本/数据卷/报告。本次准备隔离环境、总入口、工具/数据、接入协议及工程演练；15个产品分类仍为planned，没有具体用例或分类脚本，未执行本轮正式产品测试。

2026-11-11已完成最终同源两轮Environment（各退出0）及启动失败、技术子进程失败/超时、主进程强停恢复与重复Cleanup工程演练。25项宿主工程自测通过；本轮Docker容器/网络/业务卷/tag及runtime/tmp复查为空，既有资源保持。真实Ctrl+C及Linux宿主尚未实测。

实际命令、排错与最终结论见[环境实施与验证记录](环境实施与验证记录.md)。

## 当前文件

| 文件 | 用途与当前状态 |
| --- | --- |
| [测试点设计与需求覆盖矩阵.md](测试点设计与需求覆盖矩阵.md) | 248个原子测试点，分18类，双向映射46项功能需求和12项非功能需求；说明具体目标、代码依据、优先级及可验证条件，供后续用例设计使用。 |
| 本README | 目录入口、文档导航、当前交付状态与后续工作说明。 |
| run-rag-tests.ps1、helpers/orchestrate.py | PS仅包装，Python唯一实现五模式生命周期。 |
| setup-tools.ps1、package/lock、requirements-test.lock | 宿主辅助依赖和独立工具镜像依赖锁定，不复用前轮浏览器。 |
| manifest.json、schemas/ | 12个local及3个real分类planned清单、context/result/manifest严格协议。 |
| compose/ | 独立local/real编排、tools镜像、无Secret环境模板。 |
| [harness/](harness/README.md) | local控制面、跨进程计数/屏障及生产协议受控传输，不放宽产品安全。 |
| [helpers/](helpers/README.md) | 预检、初始化、探针、DB夹具、构建、采证、清理和工程自测。 |
| [fixtures/](fixtures/README.md) | 固定源hash/许可、虚假基线、非Secret配置、边界输入生成及计数/评测协议。 |
| [test-plan.md](test-plan.md)、[分类脚本规范](specific_test_script/README.md) | 环境实施清单及后续用例/分类脚本接入计划。 |

测试点设计时的状态基线：L为214点、K为5点、R为10点、B为5点、D为4点、E为10点。环境工程的本次进展及实际验证另外记录，不能沿用旧E状态认定所有工具始终缺失；也不能因环境通过就将产品点写为通过。具体定义见测试点文档第2、6节。

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

Environment流程：随机凭据→固定输入hash校验/复制→构建三镜像→PG/Redis→分段迁移到0010→显式Profile导入→API/Worker→同源HTTP/SSE、Chromium、离线词表与工程自测→采证→down销毁业务卷→独立残留复查→删除runtime/tmp→保留脱敏报告。SSE用一次Mock/off技术输入确认代理，product仍为not_run，不算产品用例通过。

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

# 分类后续ready后使用；当前两项planned会返回3且不部署。
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories 'ingestion,retrieval'
```

## 模式和报告

| 模式 | 当前行为和结果边界 |
| --- | --- |
| Environment | 可执行技术闭环；0仅表示环境/清理通过，产品not_run。 |
| Selected | 必须指定Categories，只运行ready分类，每分类独占project；planned项not_run并退出3。 |
| All | 需要全部12个local分类ready及完整报告；当前全planned，安全拒绝、不空跑通过。 |
| Real | 需要AllowRealRequests、runtime-inputs内LivePlan和独立能力/计数/授权/hash/预算门禁；默认无外发，Business/Acceptance分别控制范围。 |
| Cleanup | 按可信账本恢复本轮资源；原进程仍活动、Engine不符或账本丢失时拒绝猜删。 |

退出码0为请求范围通过，1产品失败，2工具/参数/报告/运行器错误，3受限或范围未完整执行，4清理失败/无法核验；优先级4＞2＞1＞3＞0。Environment/Selected/All返回0都不等同完整PRD验收通过。

每run保存summary.json/summary.md、environment/preflight、分类及安全日志、指纹、cleanup.json、recovery-ledger.json、证据hash索引。空报告、漏/重复case、错run/lane、坏hash或退出0无证据均为工程错误，不能passed。

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
2. 依据测试点文档编写`test-cases.md`，分类脚本集中到`specific_test_script/`，按已准备协议接入；当前尚无具体产品用例/分类脚本。
3. 对真实Embedding/rerank先补齐计数依据与校准，对效果评估准备完整20+5标注集；真实MinerU/生成等按格式和能力独立核验授权、配置、网络、额度及预算。
4. 接入后执行本地同源复验、真实业务及格式/效果/性能验收，分别收集测试报告、缺陷报告和清理证据。已知差异保留产品目标；未运行、受限和失败分别登记。

本次实施环境工程并执行实际Docker技术验证，不读取真实密钥或发起MinerU/真实模型请求。已有开发探针和历史结果不替代后续产品正式验收。真实配置只从明确runtime-inputs复制必需值，不自动扫描docs/secret或共用宿主Key；计数未校准仍blocked，不能改verified或切Mock掩盖。
