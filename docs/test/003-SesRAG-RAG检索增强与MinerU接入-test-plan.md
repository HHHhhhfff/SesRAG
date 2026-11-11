# 003：RAG检索增强与MinerU接入测试实施方案

| 字段 | 内容 |
| --- | --- |
| 编号／方案版本 | TEST-003／1.0 |
| 状态 | 已确认；A～E环境工程已实施并演练通过，F/G产品用例接入与正式验收待后续执行 |
| 日期 | 2026-11-11（America/New_York） |
| 对应项目 | v0.3／`sesrag_v0.3`；执行时另记实际commit、dirty源码指纹和镜像ID |
| 产品依据 | [PRD-003](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)，46项RAG功能需求、12项NFR非功能需求 |
| 实施依据 | [ADR-003](../adr/003-sesrag-rag-mineru-implementation-plan.md)、[实施结果简要说明](../pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)、[实施结果调研](../pr/003-SesRAG-RAG检索增强与MinerU接入-实施结果调研.md) |
| 接口与运维真源 | [接口文档第8节](../接口文档.md#8-v03-rag-与-mineru接口)、[RAG运行手册](../runbooks/rag-v3-development.md)、[通用执行规范](../项目开发和修改的通用执行规范.md)、[测试文件实施规范](../../tests/实施测试文件时的通用规范.md) |
| 独立测试目录 | `tests/sesrag-rag-mineru-test/`，下文简称suite；不接入前两轮正式验收目录 |
| 实施结果 | [环境实施与验证记录](../../tests/sesrag-rag-mineru-test/环境实施与验证记录.md)记录同源两轮与故障/恢复证据；产品结果后续另写`测试报告.md`、`缺陷报告.md` |

> 第1～15节保留已确认方案的设计和历史校审口径；2026-11-11环境工程实施后的实际状态、差异和证据以第16节及环境实施记录为准。环境完成不代表正式产品测试通过。

## 1. 决策摘要、目标和实施边界

本轮正式验收采用**本机Docker Compose、真实PostgreSQL/pgvector、独立临时业务数据和统一生命周期入口**。本地可控测试负责准确验证故障、状态、空间、引用与清理；另外安排至少一轮从真实MinerU原件解析，经真实Embedding入库和query向量化、真实rerank，到真实生成模型回答与持久引用的业务闭环。四类外部能力分别判定，任一被Mock替代都不能称“真实业务闭环通过”。

本方案定义两条执行通道：`local`为可控工程通道，`real`为真实服务通道。正式验收汇总必须同时展示两者；`local`全部通过不免除真实办公格式和模型要求。效果与性能按PRD独立判定，不能把一次真实闭环成功扩展为质量或SLO达标。

方案制定阶段只编写并校审本方案和文档导航，没有创建运行工程、读取真实密钥值或执行付费请求。下表是已确认的环境实施范围；本次环境交付结果见第16节，真实请求仍未执行。

| 范围 | 本方案后续负责准备 | 不在环境实施阶段直接完成 |
| --- | --- | --- |
| 环境与工具 | 独立Compose、工具镜像、私有运行配置、迁移/Profile初始化、假服务/传输夹具、浏览器、故障屏障、环境探针 | 产品缺陷修复、放松安全白名单、改业务状态机或迁移规则 |
| 总入口与结果 | 启动/调用/超时/采证/销毁/恢复清理；分类协议、planned清单、结果Schema、中文汇总 | 编写各分类产品断言并把未接入分类标为通过 |
| 共享数据 | 九格式及扫描PDF固定输入校验、非Secret Profile模板、数据生成工具、真实调用计划与预算、计数校准材料协议 | 直接注入成功Run/引用/active以代替业务流程；伪造真实counter依据 |
| 衔接文档 | suite README、`test-plan.md`、分类编写规范、环境实施记录 | 原子测试点矩阵、`test-cases.md`、分类自动测试脚本、正式执行及结果回填；这些另行设计实施 |

环境探针和运行器自测允许在环境阶段实施，但只验证技术条件与生命周期。例如检查API就绪不能算文档入库用例通过。真实Profile校准和产品缺口需要单独的可追溯前置处理；不能为了环境“能跑”在测试入口中临时修产品。

## 2. 当前实现基线与必须正视的前提

源码基线来自当前v0.3实现及调研。执行前复核实际分支和工作区；若代码已改变，先更新指纹与受影响的测试设计，不沿用旧结论。

| 已确认事实 | 对测试设计的约束／定位 |
| --- | --- |
| 九格式固定路线 | `txt/md`仅本地；`doc/docx/pdf/xls/xlsx/ppt/pptx`仅MinerU原件。每次办公上传/重建须确认外发，无转格式或本地回退。见[domain/rag.py](../../backend/domain/rag.py)、[index_builds.py](../../backend/application/index_builds.py)。 |
| 向量事实在PG/pgvector | 使用范围先MATERIALIZED再cosine排序/LIMIT；SQLite分支不证明PG优化器、混维或多连接。见[vector_search.py](../../backend/infrastructure/rag/vector_search.py)。 |
| 真实模型计数仍未校准 | 模板`bailian-embedding`、`bailian-rerank`为unverified；[profile_reason](../../backend/application/rag_profiles.py)和[rag_registry](../../backend/infrastructure/providers/rag_registry.py)阻断`INPUT_COUNTER_UNVERIFIED`。只有Key可用不足以启用真实业务。 |
| 生成模型计数另有契约 | 真实ModelProfile需要显式tiktoken encoding、框架开销及校准版本；当前仅缓存的encoding可离线加载。不能以该计数替代Embedding/rerank计数。见[model_profiles.py](../../backend/application/model_profiles.py)、[context_counter.py](../../backend/infrastructure/providers/context_counter.py)。 |
| 发布、冻结和终态有持久约束 | ParseJob/IndexBuild/View/ContextEvidence及Journal由PG维护；`latest`登记时更新，`active`成功发布时更新；自动重试不创建新会话Run。 |
| 有已知目标差异 | 正文引用编号未注入、部分观测/计时不足、未知重建前端未保留原操作键；生成预算整Bundle取舍，增强阶段可截取。按预期目标设计负例，不能因代码这样做就改为成功标准。 |
| 并发/清理口径有细节 | 新构建/诊断并发实际为跨Worker共享上限，单Worker主循环串行；Run内检索不进该专用计数。GC按created_at与引用保护，且实际锁序与ADR局部文字有差异。按调研记录分别验证。 |
| 既有检查不是本轮正式结果 | 历史316后端、26前端、三轮Compose及真实协议安全统计仅为参考；本次调研26项也不替代正式用例。见[调研第9～10节](../pr/003-SesRAG-RAG检索增强与MinerU接入-实施结果调研.md)。 |

目前没有理由在“方案编写”阶段要求用户手工处理。后续真实通道若缺有效凭据、额度或可核实的模型计数依据，需精确列出缺什么、影响哪个阶段、操作者应补什么；保留本地通道的可执行工作，不假装完整真实验收已完成。

## 3. 验收分层、测试矩阵与判定

### 3.1 证据层次

| 层次／通道 | 主要内容 | 成功标准与证据边界 |
| --- | --- | --- |
| E：环境工程 | 部署、配置、迁移、工具、同源代理、生命周期与恢复清理 | 环境状态和cleanup均通过；product为not_run，不生成虚假产品case通过数。 |
| A：local工程链路 | 真实PG/Redis/API/Worker/前端＋确定性Mock或受控传输；真实本地txt/md | 协议、权限、状态、故障和确定性断言；不证明真实外部解析/语义效果。 |
| B：real办公格式 | 七办公格式加额外扫描PDF，共8份真实外发，txt/md另验不外发 | 每格式正文/标题或表格及位置质量分别记录；失败不回退；8份输入不是8种办公格式。 |
| C：real完整业务 | 真实MinerU＋真实文档/查询Embedding＋PG召回＋真实rerank＋真实流式生成 | 至少一个办公原件完成正式业务链，数据库持久证据和实际响应可追溯；不能只运行供应商SDK或直调协议探针。 |
| D：效果／性能 | 九格式20+5标注，同语料视图排序/增强对照；10k Chunk/100次查询 | 按PRD指标实报；可在local验证性能/度量工具，但Mock效果不得代替真实质量。 |

### 3.2 拟接入分类及需求覆盖

分类是后续脚本的职责范围，不是本次已经编写的测试点/用例。以下`RAG-*`、`NFR-*`均来自PRD-003；同一需求涉及不同投影或故障时允许跨分类覆盖，但后续测试点须避免相同判定重复计数。

| 分类ID／通道 | 后续要覆盖的内容 | PRD覆盖 | 关键证据与条件 |
| --- | --- | --- | --- |
| catalog／local | 库创建/默认/启停/owner、Profile不可变与安全禁用、空间绑定 | RAG-001～002、RAG-005；NFR-006、NFR-010 | API/DB、同维异模型/异维、两个服务端owner上下文；不假设已有生产登录/RBAC。 |
| ingestion／local | 文件名/大小/MIME/容器、固定路线、外发确认、源不可变及幂等 | RAG-003～006、RAG-009、RAG-015、RAG-022；NFR-001～002 | 10MiB边界、九格式真假输入、操作键冲突、云端调用计数为零的拒绝证据。 |
| mineru／local | 申请/PUT/poll/download/归一化、恢复/未知/取消/截止、恶意输出 | RAG-007～014、RAG-015、RAG-022；NFR-001～005、NFR-007 | 单batch次数、PUT无Bearer、真实PG双Worker、断点、SSRF与ZIP限制；假产物不冒充云端通过。 |
| chunking／local | 结构/字符窗口、长块/Unicode/重叠、块位置/hash | RAG-015～017；NFR-004、NFR-007 | Artifact与Chunk独立区间对照；真实输入计数仍另验。 |
| vectors／local | 版本化向量配置、384/1024与同维异空间、坏返回、候选原子发布 | RAG-002、RAG-018～020；NFR-003、NFR-006～007 | 真PG维度/FK/触发器、失败/失租不切active、SQL独立距离对照；真实模型另见real。 |
| retrieval／local | 过滤/冻结范围、候选/Top-K、重排/降级、邻近合并、上下文实际范围与trace | RAG-023～031；NFR-001～002、NFR-005～007 | None/空集合、tags AND、并列顺序、认证错误不得降级、enhancement截取与生成取舍分开。 |
| execution／local | 固定工具、按代调用、Run冻结/重试/再生成、Journal/SSE/终态事务 | RAG-030～037；NFR-003～005、NFR-007 | 多连接屏障/停机、旧代拒写、mandatory预算先于付费、实际ContextEvidence、正文编号缺口。 |
| workspace／local | 浏览器上传授权、构建状态、诊断、配置、证据/Markdown与事件恢复 | RAG-039～042；NFR-011 | Playwright真实浏览器同源HTTP/SSE；组件测试是补充，不代替页面交互。 |
| compatibility／local | 三代契约/历史、旧DOCX写入升级、旧空间/引用、分段迁移/回退 | RAG-021～022、RAG-038；NFR-010、NFR-012 | 自建旧库fixture、0006→0010、旧Message/Event hash不变、备份恢复；不调用旧suite。 |
| lifecycle／local | 历史依赖保护、容量预算、取消/磁盘压力、业务GC/诊断保留 | RAG-020～022、RAG-046；NFR-004、NFR-009、NFR-012 | 创建时间24h/7d与墓碑30d边界、dry-run/apply、竞争锁序与实际清理结果。 |
| performance／local | 数据库精确检索规模、延迟分位数、资源和全链阶段拆分 | RAG-023、RAG-025；NFR-008～009 | 真实PG≥10000有效Chunk、100次测量，硬件/扩展/维度/执行计划/峰值；不以构建耗时或Mock延迟代替。 |
| quality／local | Schema/类型/工具链、分层边界、证据/报告正确性与泄漏检查 | RAG-032、RAG-038、RAG-046；NFR-001～002、NFR-005～007、NFR-010～012 | 新旧契约校验、前端类型/lint/构建、运行器负例；不得把旧报告数字填入本轮。 |
| real-business／real | 一轮真实办公→索引→对话→引用→清理闭环 | RAG-004、RAG-007～010、RAG-015～020、RAG-023～037、RAG-043～044；NFR-001、NFR-003～005、NFR-012 | 四类真实依赖均不可Mock，必须满足第6节门禁；引用来源正确不等于答案每句话有语义支持。 |
| real-formats／real | 九格式各自内容与结构、PDF文本/扫描，入库及安全证据 | RAG-003～004、RAG-010、RAG-015～017、RAG-039～040、RAG-042～044；NFR-011～012 | 本地2格式＋办公7格式/8份，逐项真实结果和可靠/缺失位置。 |
| real-evaluation／real | 同语料视图dense/rerank及增强的效果评估 | RAG-026～030、RAG-043～045；NFR-007 | 至少20有答案/5无答案及预标语义干扰，全部失败/下降样本留存；真实格式不足只能部分评测。 |

此矩阵覆盖46项功能、12项非功能，但不直接替代原子测试点与用例。后续须把各条验收标准展开到具体case，尤其PRD §10.3：dense平均Recall@20≥0.85、MRR@5/Recall@5对照、至少一个真实重排提升相关名次的场景、跨片段增强、范围/引用100%一致、无答案与基础设施失败分开，以及分格式质量。

## 4. 专属目录、预计文件与职责

以下为方案制定时的拟新增清单；环境资源现已按第16节落地，正式产品用例和分类脚本仍未新增。实际命令与增补模块见suite README。不复制上一轮套件来维持隐式依赖。

```text
tests/sesrag-rag-mineru-test/
├── README.md
├── test-plan.md                         # 分类接入计划、planned/ready清单及顺序
├── run-rag-tests.ps1                    # Windows/Linux统一pwsh入口
├── 环境实施与验证记录.md                # 环境实施后的真实记录
├── setup-tools.ps1
├── package.json / package-lock.json     # 独立Playwright/报告工具锁定
├── requirements-test.lock              # 补充Python工具依赖精确锁定
├── manifest.json                       # 分类、case声明、依赖、预算；初始planned
├── schemas/
│   ├── context.schema.json
│   ├── result.schema.json
│   └── manifest.schema.json
├── compose/
│   ├── docker-compose.rag-test.yml
│   ├── docker-compose.rag-real.yml      # 真实通道覆盖，移除local harness
│   ├── Dockerfile.tools
│   └── .env.rag-test.example            # 仅占位/默认，不含Secret
├── harness/
│   ├── local_entry.py                  # 仅local镜像的API/Worker入口
│   ├── transport_fixtures.py           # HTTP受控响应、请求身份检查
│   ├── scenario_control.py             # 屏障/计数/重启后可读控制面
│   └── README.md
├── helpers/
│   ├── orchestrate.py                  # 生命周期、子project及分类执行
│   ├── preflight.py                    # 依赖、fixture、配置和真实门禁
│   ├── environment_probe.py            # 环境技术探针，不是产品分类
│   ├── prepare_runtime.py              # 凭据/别名/配置分离及安全生成
│   ├── fixture_admin.py                # 专属测试库、旧库/性能数据和资源登记
│   ├── evidence.py                     # 脱敏、限量、索引/hash、泄漏检查
│   ├── cleanup.py                      # 所有权校验、删除及独立残留复查
│   ├── selftest_runner.py              # 运行器/控制面/清理的正负自测
│   ├── browser.mjs                     # 浏览器启动/上下文/进程回收共用能力
│   └── README.md
├── fixtures/
│   ├── README.md
│   ├── baseline.json                   # 虚假owner/Profile选择及稳定身份声明
│   ├── profiles.local.json
│   ├── profiles.real.example.json      # 未满足计数时保持unverified
│   ├── models.local.json
│   ├── models.real.example.json
│   ├── live-plan.example.json          # 外发hash/格式、真实能力、预算和结果范围
│   ├── manifest.json                  # 引用固定输入hash及来源许可
│   ├── materialize.py                  # 校验并复制固定输入/生成边界输入
│   ├── legacy/                        # 本轮自行定义的旧库数据/预期摘要
│   └── counter/                       # 计数测试输入和非Secret依据模板
├── specific_test_script/
│   └── README.md                      # 分类脚本协议；实际脚本后续另写
├── runtime/<run_id>/                   # Secret/恢复控制账本，Git忽略
├── runtime-inputs/                     # 操作者私有live计划/配置来源，默认不随单轮删除
├── tmp/<run_id>/                       # 下载包、浏览器、原始诊断等，结束删除
├── artifacts/<run_id>/                 # 保留脱敏证据和报告，默认Git忽略
└── .cache/                            # 依赖/浏览器/词表；frozen-builds保存冻结构建账本
```

测试点矩阵、`test-cases.md`、分类脚本、`测试报告.md`和`缺陷报告.md`在后续任务新增。初始manifest不得引用不存在的脚本并标ready；planned保留预计脚本路径但不可执行。

### 4.1 文件用途与使用阶段

| 新增资源 | 主要职责与使用时机 | 阶段 |
| --- | --- | --- |
| suite README、`test-plan.md`、`specific_test_script/README.md` | 操作、结果/清理说明、分类接入顺序、数据边界、中文日志和独立性规则；后续每个脚本关联哪些用例需维护 | A及后续接入 |
| `manifest.json`、`schemas/`三文件 | 冻结模式/分类/case/预算、运行上下文、结果协议；先定义后实现调用方 | A |
| `setup-tools.ps1`、package/lock、Python lock | 准备PS7、Python辅助依赖、浏览器/Node、hash校验的离线词表；开发宿主与容器版本分列 | B |
| `compose/`四文件 | 真实PG/Redis及应用/前端/工具服务，local/real差异、动态端口、资源标签/卷、无Secret配置模板 | C |
| `harness/`及README | local控制面/传输和屏障，覆盖慢响应、坏协议、应答未知、按Task/generation阻塞；不进入真实通道 | B～C |
| `helpers/orchestrate.py`、`run-rag-tests.ps1` | 主入口参数验证、全程账本、按分类部署/执行/采证/清理、信号与恢复；PS仅包装，不复制第二套生命周期 | D |
| preflight、prepare_runtime、environment_probe | 无付费的依赖/门禁判断、私有配置和环境就绪验证；各模式均执行必要就绪检查，Environment只执行这些技术检查 | B～C |
| fixture_admin、fixtures目录及materialize | 共享固定输入/虚假身份/Profile、专属旧库/性能库生成、计数材料和live计划；不代写产品终态 | B～C |
| evidence、cleanup、browser | 有界脱敏采证、路径/所有权保护、浏览器回收、清理审计与恢复账本 | D |
| selftest_runner | 退出0但无报告、错误run_id、重复case、超时/强停、错误标签/路径等自测，不能计产品用例 | B～D |
| `环境实施与验证记录.md` | 实施完成后记录真实Environment两轮及异常/恢复演练、工具版本、限制、清理证据 | E |
| runtime/runtime-inputs/tmp/artifacts/.cache | runtime/tmp/artifacts按run_id隔离；运行凭据和大临时文件不累计，脱敏报告/明确缓存有意保留；runtime-inputs是原始私有配置来源，由操作者单独管理，不是运行副本 | C～E |

### 4.2 已有文件的预计修改

| 文件 | 修改内容与目的 | 边界 |
| --- | --- | --- |
| `.gitignore` | 新suite的runtime/runtime-inputs/tmp/artifacts/.cache/node_modules、实际私有配置文件忽略 | 不影响固定fixture、Schema和脚本入库 |
| `.dockerignore` | 排除同类运行数据、Secret源目录和suite凭据，防止进入根构建上下文 | 验证tools镜像仍能COPY必要受控测试文件；不把私有文件排除只寄望.gitignore |
| 根`README.md`、`docs/test/README.md` | 本方案导航；实施后加入独立suite入口和“已实施/待验收”状态 | 不在README复制正式接口表 |
| `tests/integration/README.md` | 必要时链接正式TEST-003并说明既有开发probe只作补充 | 不改变原probe断言，不把历史日志转换为新结果 |
| 本方案 | 仅在实施后追加实际路径/命令/环境结果/设计差异，保留历史口径 | 未执行的阶段保持待实施 |

正常环境准备不需要修改backend/frontend业务、contracts、生产Compose或历史验收目录。发现测试工具确需公共依赖变更时，先记录具体缺口、影响文件、验证方式再作最小调整；产品修复必须单独留变更记录和回归依据。制定方案时仅修改本方案与导航；环境实施后的实际文件与增补项见第16节。

## 5. 本机临时环境与local控制能力

### 5.1 工具、资源与构建

目标为Windows Docker Desktop的Linux容器或Linux Docker Engine，Compose v2.24.4+，PowerShell 7.4+作为两平台统一入口；工具镜像采用与项目相容的Python 3.11+和Node 22.13+，实际patch与依赖锁定。浏览器用独立Playwright Chromium；不复用前轮node_modules或浏览器profile。Docker/PS不自动以管理员权限安装，缺少时列出确切版本要求和可执行安装依据。

建议起始资源为Docker分配4核/8GiB、宿主可用20GiB以上空间；这是执行建议而非达标证明。记录实际CPU/内存/磁盘、Engine/context、pgvector/PG/浏览器版本和各服务峰值；不足时按类别安排串行或将具体容量/性能项标受限。预检不能只检查磁盘阈值后声称满足NFR-008。

构建三类本轮tag：app、frontend、tools，标签带suite/run/source指纹。local与real使用相同产品源码和生产Dockerfile构建，local仅以只读测试挂载/专用入口装配受控适配器；real使用正常产品入口、不挂载local harness。禁止运行器改源码或重写生产镜像中的业务文件。第二轮local复用冻结构建与依赖，启动前后均核对指纹。

首次正式All在销毁运行tag前，保存无凭据的镜像归档及`build.json`到`.cache/frozen-builds/<指纹>/`，包含归档SHA-256、image ID、源码/依赖指纹；后续`-FrozenBuild`校验后加载并创建新run专有tag。不能仅留镜像ID却删掉唯一镜像内容后声称可复用。加载过程新建的tag也登记；归档有意保留并单列空间，不含业务卷/runtime。冻结缓存默认10GiB软门限，磁盘不足不静默改为重建另一组依赖；清缓存由操作者在无活跃引用时按明确指纹处理。

### 5.2 Compose服务与隔离

独立基础Compose定义`postgres/redis/migrate/profile-init/api/worker/frontend/tools/scenario-control`；worker可按分类启动两实例。real覆盖只启用PG/Redis/迁移/配置/API/Worker/前端/工具，禁止scenario-control或fake transport进入真实链路。

real覆盖必须使用支持的`!reset/!override`清空local的harness挂载、场景依赖、dummy环境和入口，再显式列出真实配置；不能依赖普通数组合并来“移除”它们。scenario-control仅处于local profile，real网络允许按正式出站策略访问公网。准备后将完整有效配置存runtime私有文件，并作安全结构校验：无local服务/挂载/假工厂、正常产品入口、正确卷/动态端口/真实alias；报告仅输出校验结论和非Secret身份。版本不支持覆盖标签或结构检查不满足时停止，不降级成混合配置。

- project名使用`sesrag-rag-<时间与随机串>-<分类短名>`，run_id另有`rag-...`身份。每分类独占PG、uploads、rag_artifacts、rag_tmp及控制面卷；无固定container_name、external卷或开发端口。
- 前端仅映射`127.0.0.1`动态宿主端口，由Docker查询实际地址；API/PG/Redis不映射宿主。API与SSE统一由前端反向代理；tools/browser走内部服务名与同源代理。浏览器服务只供本轮工具，不暴露公网。
- 所有Compose调用显式file、project、project-directory、私有env-file，清除继承的COMPOSE_FILE/PROJECT_NAME、开发DSN及服务Key等无关变量；不读取根`.env`，不以根Compose覆盖拼接隐式继承开发卷。
- 网络/卷/容器/镜像与one-off容器同时记录Compose project及自定义suite/run/owner标签。创建前写意图账本，创建后登记真实ID；Engine context和daemon身份贯穿恢复清理。
- 默认local不注入任何真实Key，不挂载`docs/secret/`、宿主home或Docker socket到产品容器。Docker故障注入由受控宿主编排助手按账本操作，不开放给测试页面/工具输入。
- PG/Redis就绪 → 分段迁移 → Profile导入 → API/Worker就绪 → 前端同源探测 → 分类执行。检查migrate/profile-init实际退出0，revision为`0010_rag_task_and_run_protocol`，扩展可查询，Worker readiness不靠API返回200猜测。

### 5.3 local假服务与真实安全路径分离

MinerU客户端固定HTTPS公共API，SafeHTTP拒绝私网且不信任环境代理；不能简单把URL换成`http://fake-mineru`就期待正式适配可用，更不能增加生产“允许私网”开关来方便测试。

local采用独立`harness/local_entry.py`在应用启动前装配测试工厂：现有MinerU/Embedding/rerank适配器接受的`transport`参数接入`httpx.MockTransport`类受控传输，保留协议解析、URL白名单、状态编排和错误映射。控制面通过专有网络/令牌/场景白名单提供响应计划及跨进程调用计数，延迟/屏障有截止，不接受任意代码或目标URL。生成适配可使用本suite固定HTTP/SSE假服务及有效非Secret测试Profile。

该方式证明的是**受控传输下的产品编排/协议**，没有经过真实DNS/TLS/公网连接；真实出站安全另用未替换的SafeHTTP/PublicNetworkBackend和明确安全负样本验收，正向真实公网由real通道验证。测试记录必须标注transport类型，不混写。现有测试以参数注入为设计参考；若工厂需装配多个模块引用，必须在启动自测确认全部生效、无旁路真请求。默认local网络隔离为internal，mock路径无真实凭据；构建/装依赖阶段联网单列。

local控制面至少具备：固定成功/空/坏向量/坏索引；401/403/429/5xx；慢流/断流；申请应答丢失；PUT未知后原batch查询；等待/转换/下载故障；恶意ZIP/HTML；发布前屏障；一代迟到；生成前记录实际输入范围摘要。禁止控制面直接把Task/Build/Run写成成功。控制台只输出case、阶段、调用类型/次数、hash与错误码；完整请求只限明确非Secret合成断言且有界，不能采集真实Authorization。

装配还须区分三种能力：主业务向量/重排使用明确Mock Profile及受控Port来注入结果/故障；MinerU使用生产客户端＋受控transport及合成产物；百炼真实适配器的HTTP解析/坏索引协议可在tools进程直接带fixture transport校验，结果标protocol模拟。不能把真实Profile标成verified来开启local测试，更不能让替换工厂绕过本该拒绝的unverified/blocked用例。假生成HTTP/SSE由scenario-control服务提供固定路径，使用dummy Key和本地可校验的计数配置，绝不绑定真实服务凭据。local启动后须报告这些装配身份，不能只记录一个模糊的“mock=true”。

### 5.4 数据库和故障工具

主业务通过正式API创建；fixture_admin仅对本project登记的测试数据库/卷工作，拒绝开发DSN、未知库名和无法确认所有权的路径。迁移/旧库/性能/越owner数据允许专门造数，需记录“数据库夹具注入”的证据类型，不能把这种数据当端到端成功入库。

并发/恢复测试使用真实PG多连接与两个Worker，以可观察屏障控制领取、外发后、写回前、发布前时点。测试时可终止指定Worker容器、断开本project的Redis、注入指定卷容量/受控文件错误；禁止停止Docker Desktop或删全局网络来模拟故障。需要改时间时仅操纵该case夹具/受控时钟，不改宿主系统时间或任意更新已发布事实。

## 6. 真实MinerU与模型业务闭环

### 6.1 真实通道准入门禁

真实业务是本轮必须安排的验收项目，但执行必须使用可核实前提。以下GATE编号仅为本方案工程门禁，不是PRD编号或用例编号。

| 门禁 | 核对内容 | 不满足时的处理 |
| --- | --- | --- |
| GATE-REAL-01：来源与外发 | live计划声明合成/获准公共文件、逐文件SHA-256、格式、用途、最大调用量；办公请求逐次`cloud_consent`及授权版本 | 缺授权或hash变化不外发；不扩大到宿主任意文件 |
| GATE-REAL-02：独立能力配置 | MinerU精准API、真实Embedding、rerank、生成模型四项分别检查别名/存在性/端点/模型身份；Key仅在API/Worker必要环境注入 | 逐能力列缺项；不隐式复用Key，不因MODEL可用认定其他能力可用 |
| GATE-REAL-03：计数与版本 | Embedding/rerank官方计数/tokenizer或有依据保守上界及边界校准材料；生成encoding/框架开销适用性；不可变Profile版本/hash和证据摘要 | 当前此门禁未退出。标blocked，停止完整真实链路，不改unverified为假verified、不调用适配器绕守卫冒充业务 |
| GATE-REAL-04：网络与格式 | 精确API/存储域白名单、公网TLS可达；MinerU Profile verified_formats/协议依据；配置缺失可无付费判定 | 未知域先安全拒绝，核实后增版/重新准备；不自动扩大白名单、转换文件或重申batch |
| GATE-REAL-05：资源与预算 | 干净的真实专属project/真实空间、磁盘和时限、live预算；同一时刻只跑一个真实计划 | 不满足则禁止新业务提交；已有可能受理的远端工作单列 |

`docs/secret/准备的配置信息.md`是操作者准备来源，不是常驻服务的数据源。后续准备工具只把指定能力需要的值送入私有runtime，输出“已配置/缺失”和非Secret模型/端点身份；不得把整份文件、Key或能力URL写进模板/报告、屏幕日志和构建上下文。API/Worker必须使用同一MinerU状态加密Key。

计数材料在环境阶段定义格式并准备固定边界输入，**不承诺本方案写完就已获得校准依据**。若官方适配需要新计数实现或修正现有模型支持，列为独立产品前置修复并验证后再冻结测试版本。无依据时仍可运行受控local和可用的独立真实协议补证，但完整业务仍blocked；不能将“小输入这次返回了”当全输入上界证明。

### 6.2 一轮真实业务的明确流程

默认`Real -RealPlan Business`至少执行以下闭环；具体产品脚本后续实现为`real-business-tests.py`。

1. 创建独占真实project，经过正常迁移与显式Profile导入；真实服务使用正常产品API/Worker入口。检查未挂载local harness、未注入MockTransport，真实生成选择为openai_compatible，Embedding/rerank为真实适配，办公为MinerU。配置/镜像/样本指纹写入safe metadata。
2. 新建绑定真实1024维空间的知识库；保留独立384 Mock库作空间对照，不能将Mock向量改标签为真实。选一份小型DOCX合成正文与表格作为默认办公输入，包含可独立核对的独特事实；另备一个语义干扰片段，避免只验证非空回答。
3. 经`POST /api/v3/documents`上传原件，带本次外发授权和幂等键。通过API及受权数据库采证确认ParseJob→MinerU申请/原字节PUT/同batch轮询→真实产物→ParsedArtifact/Block→切片→真实文档Embedding→IndexBuild成功/active。只见远端done或直调协议成功不算通过。
4. 通过既有Thread创建入口及v3消息入口发送预定问题，显式启用该库、真实rerank及真实生成ModelProfile。冻结本次view/config；真实query Embedding、PG候选、rerank和增强必须实际执行，不能通过空视图、关闭RAG或dense_fallback避开依赖。
5. 经正式SSE读取工具阶段和回答增量，GET事实确认Run成功、唯一最终assistant、ContextPlan与Citation关系。回答须包含预期事实，引用只能关联本次实际输入；逐句语义及正文编号另作判断，不能由Citation非空代替。存安全必要回答片段/比对结果、响应字节数/hash、事件序号和耗时，不保存完整Prompt或签名URL。
6. 验证旧/其他库文档不进入候选，读取本次Bundle分页并比对源hash/规范范围；刷新读取持久结果。真实rerank须返回有效索引/分数、执行模式为ok；它这次不改变顺序不直接判协议失败，但不能据此宣称效果提升。
7. 收集脱敏证据/配置身份/四类能力结果，停止新请求，销毁本project容器/卷/网络/私有文件并复查。若任一实际依赖失败，业务闭环失败或blocked，按第10节定位，不将已成功部分抹除。

真实请求/响应的最低证明由“无假适配的运行配置＋生产代码路径＋实际返回的产物/向量/分数/流＋持久身份链”共同构成。供应商trace/request ID若可安全取得则保存摘要；当前代码未提供的全量上游计时/usage注明缺失，不能为报告方便伪造字段。`check_rag_providers.py`直调只可标`protocol_probe`，既有8份历史产物也不能替代本轮新鲜业务闭环。

### 6.3 真实格式与效果计划、费用控制

`RealPlan Acceptance`在同一次真实环境中依次执行`real-formats → real-business → real-evaluation`，复用本次已经成功发布的相同输入与批次，避免重复上传和切片；Business选其中一个办公文档完成回答，仍是新鲜完整链路。txt/md本地解析与七办公真实解析逐项检查，PDF额外扫描输入；各失败、内容遗漏和位置缺失单列。

效果对照期间停止语料写入，冻结source/Artifact/Chunk/Profile和空间。不同诊断请求可能生成不同view_id，必须核对批次清单、过滤和scope/hash等价，并对同一dense候选集合比较重排；不能只因两个请求都“当前库”就认定同视图。计量程序按标准答案范围映射本次Chunk，不硬编码随机ID。凡提升/下降/无答案/跨片段样本均保留；MRR@5整体下降不可推荐默认开启。

| real计划 | 默认逻辑业务预算与时限 | 结果边界 |
| --- | --- | --- |
| Business | 1份DOCX≤2MiB、最多1个新云端解析工作；固定小语料≤128个文档Chunk、最多2个查询、1次回答、输出≤512 tokens；全轮20分钟 | 证明一次四依赖真实业务闭环；不等于全部格式、质量和性能通过 |
| Acceptance | 七办公＋额外扫描PDF共8次新云工作、另2个本地文本输入；≤2048个文档Chunk、≤60次query、≤32次rerank、≤3次回答、每回答≤512 tokens；全轮60分钟 | 覆盖真实格式及20+5效果对照；超量需要修改明确的live计划并记录新范围，不自动扩额 |

上述为测试编排的**逻辑操作上限**，不是供应商最终费用承诺；同一Task内部有界重试/轮询另受冻结的产品上限控制。计划应按批量16、失败最多3次等估算最坏外部请求量并展示安全摘要。若无法观测真实计费token、实际HTTP总次数或远端工作是否已结束，报告写unknown，不能把逻辑次数当账单。

真实通道串行执行。已明确失败或提交未知不自动换Key/格式/模型或重新跑整轮；本机超时取消也不保证云端停计费。达到本轮预算/截止后停止新逻辑操作、请求取消并回收本地Worker，记录在途可能继续。仅对同一已知batch安全恢复，不把新的run_id当上游去重机制。真实费用相关故障注入主要放local验证，不重复付费制造失败。

## 7. 数据、配置和初始导入

### 7.1 共享基线与case数据边界

共享基线是虚假owner标识、库/Profile选择、固定输入与版本约定。当前没有用户表，不应为了“统一SQL种子”虚构账户数据库。空库使用正式分段迁移和显式`sync_model_profiles/sync_rag_profiles`；库和文档优先经API建立，baseline.json记录选择而不写死随机生成的资源ID。

本轮默认**不新增共享seed SQL**：不预填业务成功状态、Run、Citation或真实向量。若后续某组确需稳定旧库/性能夹具，由fixture_admin在专属库中生成，有manifest、生成器版本、行数与hash及清理登记。case临时文档/线程/操作键/故障场景均独占前缀，每例自行准备/恢复；一例失败不能使其他例依赖其成功结果。

### 7.2 文档与异常输入

复用[tests/fixtures/rag-v3](../../tests/fixtures/rag-v3/README.md)这一本轮开发输入真源，环境准备时按hash复制到本run私有输入目录，suite manifest记录来源，不硬链接可变运行文件回源目录。两个Apache POI公共doc/ppt保留NOTICE/许可；不需要联网重新下载就可用已有合法固定字节。

`materialize.py`另生成必要的边界/安全包，不执行宏或载荷：10MiB±1、空文件、MIME/容器伪装、长Unicode/长表格、重复/逃逸/嵌套ZIP、HTML不可信内容、相邻/跨Chunk答案和语义干扰。全部为合成数据且有规模上限。真实计划只允许manifest列出的安全输入，危险样本只走local。

20+5问题/答案/相关范围标注最终由后续用例/评测任务补齐；环境阶段只定义数据格式/加载校验，不能把包含20条事实的单个文档直接当“20道标注题已完成”。七办公格式需独立正文/标题或表格核对，PPTX现样本只有六页子集。扫描PDF与文本PDF分开，原页/幻灯片/工作表映射缺失时以冻结规范块并人工核对，不能编造坐标。

### 7.3 旧库、性能与校准输入

- compatibility使用本suite的legacy生成器从0006构造最小真实旧状态、停止Worker、显式默认库/空间后升级；覆盖未知384来源、遗留DOCX任务、存在/已丢旧引用及一致备份恢复。不导入开发数据库，也不复用前轮验收SQL/脚本。
- performance可注入固定算法的≥10000个合法Chunk与有效Build/空间/FK、同时建立384/1024隔离数据，明确仅证明数据库召回，不证明全部经过真实模型入库。预热后测100次并保存原始样本；外部阶段需另计时，不能借Mock延迟推真实全链性能。
- counter输入覆盖中英/混合/Unicode、文档/query、单条/批量/请求组合边界。依据须标模型/修订/算法/适用上限/来源/日期/校准结果；Embedding、rerank、生成三份适用性独立。验证证据不含Key，修改Profile须增版。

### 7.4 配置准备与初始化顺序

`prepare_runtime.py`先读取明确允许的输入，再创建本run私有env/config；不透传整个宿主环境。下面均是本轮运行副本，不修改根`.env`或生产模板。

| 配置组 | local | real | 使用服务及边界 |
| --- | --- | --- | --- |
| DB密码/DSN/project | 每project生成随机32字节hex密码和独占库DSN | 同样随机隔离，绝不复用开发DSN | migrate/profile-init/API/Worker/tools按需；密码不输出，DSN仅容器私有配置 |
| owner与目录 | 服务端虚假owner；专属uploads/artifact/tmp卷 | 真实业务仍用虚假测试owner，非真实用户资料 | API/Worker一致；owner-b越权场景另起显式服务上下文/夹具，不信任客户端owner参数 |
| `MOCK_PROVIDER`及Profile选择 | 保留旧路径Mock默认，schema3明确使用local配置 | 逐项显式选择真实ModelProfile/RAG Profile；不能只看这个旧开关断定全链真实 | 该开关不替代新版Profile适配身份核对 |
| `MINERU_ENABLED/API_KEY/STATE_ENCRYPTION_KEY/STORAGE_HOST_ALLOWLIST` | 默认关闭；mineru分类可启用受控transport、dummy Key及专属加密Key | 精准API有效Key、同run API/Worker共用32字节base64加密Key、核实的精确域 | local启用不代表公网调用；real不注入假传输，加密Key保留到同Job恢复结束 |
| `RAG_EMBEDDING_API_KEY/RAG_RERANK_API_KEY/MODEL_API_KEY` | 只需假生成的dummy Key；不带真实服务Key | 按各自受信alias分别显式映射，非SecretProfile仅保存alias | API作可用性核对，Worker实际调用；tools不默认获取全部Key |
| Profile与计数 | mock空间/本地策略、假生成有效计数；unverified拒绝场景保持原状态 | 独立新版本Profile、真实1024空间、专用计数证据和生成计数适用依据 | 显式导入数据库；配置文件存在不等于已经启用或生效 |
| 容量/时间 | 默认存储10GiB、临时1GiB、专用并发1；case可声明变体 | 同默认起点并按live计划限量/有界截止 | 保留生产Settings校验；配置变体与并发实际口径一并归档 |

私有live计划至少声明schema_version、Business/Acceptance、文件列表及hash、解析授权版本、四类真实能力/Profile版本、非Secret配置文件引用、计数依据摘要、凭据来源的alias、逻辑预算/时限。凭据值仅从显式进程环境白名单或`runtime-inputs`内单独私有Secret文件读取，不写进live计划或命令行。准备工具先将必需值复制到本run runtime，再清理子进程继承变量；原始私有输入不随单轮删除。

配置初始化按实际产品工具执行：空库`backend.tools.upgrade_rag_schema`到0010 → 显式`sync_rag_profiles`及`sync_model_profiles`导入本模式配置 → 查询安全Profile清单/默认库 → 经API创建case知识库。默认Mock库可以共存，但真实case必须绑定并核验自己的真实空间，不能依赖默认选择。升级旧库则按compatibility夹具/Runbook分段执行，不在新空库上假称已完成旧库升级验证。

## 8. 总入口、生命周期和调用协议

### 8.1 模式与参数

总入口`run-rag-tests.ps1`使用PS7包装Python orchestrator，工作目录不影响定位。参数必须有明确枚举和冲突校验，不依赖用户手工启动/关闭容器。

| 模式 | 行为 | 默认外发与成功含义 |
| --- | --- | --- |
| Environment | local部署→技术探针/工具自检→采证→清理，可在尚无分类脚本时运行 | 无真实请求；environment passed、product not_run |
| Selected | 运行`-Categories`列出的local已ready分类，每分类新project；不自动满足其它分类覆盖 | 无真实请求；只声明所选范围 |
| All | 运行全部12个local分类；planned/漏case不能通过 | 无真实请求；local轮次完成，完整acceptance仍待real/效果等证据 |
| Real | `-RealPlan Business`或`Acceptance`；必须同时`-AllowRealRequests -LivePlan <path>`并通过第6节门禁 | 缺开关不外发；真实缺前提标blocked，不能自动改跑Mock并判real通过 |
| Cleanup | 只恢复指定run_id的账本资源，幂等，不构建/不测试/不调用远端 | 只声明清理，不产生产品passed |

共同参数拟包括RunId（新运行自动生成，重复拒绝）、Categories、HoldSeconds（Environment可选0～300）、StartupTimeoutSeconds、FrozenBuild（复用已登记镜像/锁定集）。artifacts固定在suite下按run_id输出，避免第二套清理范围。敏感凭据不接受命令行字面量，用受限私有文件/进程环境注入。Real的LivePlan路径先解析到本suite受控目录，结果只存非Secret指纹。

不提供跳过清理或永久KeepEnvironment。Cleanup不能仅凭用户给的容器名或project前缀删除；路径/标签/Engine不匹配明确拒绝。

### 8.2 单轮和分类生命周期

1. 创建run_id和私有目录；写初始账本/源码与依赖指纹、现存资源快照，建立总入口try/finally。无Docker可用也落中文失败摘要，不假定零残留。
2. 验证manifest/Schema/fixture hash/工具/磁盘/权限。准备模式对应配置；real门禁在任何付费业务前执行，敏感配置不进入构建层。
3. 显式构建并登记本轮tag/镜像ID，或核验FrozenBuild；local每分类独立子project串行启动，real Acceptance三子分类共享本轮真实语料project以复用批次。
4. 启动PG/Redis、迁移及Profile初始化，读取真实revision/服务事实。等Worker就绪和同源HTTP/SSE可观察；启动超时即转采证与清理。
5. 写安全context与分类范围；分类进程有deadline。每case记录独立准备/动作/观察/结论；通过finally撤销屏障和临时故障，失败不伪造后续成功。
6. 收集分类结果/日志/安全DB投影/浏览器与资源信息。JSON结果通过Schema与manifest覆盖核对才可汇总；空报告、退出0无报告等为harness_error。
7. 每个local分类采证后销毁子project并复查，前一分类失败仍可在干净环境执行其它独立分类。基础工具/清理不可信时停止新部署，剩余分类not_run并说明原因。real共享语料若基础阶段失败，依赖的后续子类标blocked，不继续制造费用。
8. 最后释放本run所有资源/私有目录，独立残留扫描，更新cleanup和最终summary；摘要只在清理结束后定稿。总进程中断时恢复入口使用同一账本。

超时默认：构建/工具准备另给有界预算，启动≤300秒；local分类默认≤900秒，performance/迁移可声明≤1800秒；real计划20/60分钟；单次日志命令≤30秒，清理总预算默认180秒，必要一次有界复查。分类预算应在case设计后校准，不因超时自动无限延长或自动重跑。主流程须可处理Ctrl+C/子进程崩溃；硬杀和Docker异常依赖Cleanup恢复，不能承诺finally必然执行。

### 8.3 分类脚本协议

local预计脚本为`<分类ID>-tests.py`，workspace为`workspace-tests.mjs`；real对应`real-business-tests.py`、`real-formats-tests.py`、`real-evaluation-tests.py`，统一置于`specific_test_script/`。后续是否拆同类脚本由独立性决定，不把不同分类的产品断言塞进共用helper。

manifest每项声明category、lane、planned/ready、entrypoint、显式case_id列表/需求关联、超时、资源/依赖和是否可能付费。执行仅允许suite内已登记入口；不执行manifest任意shell字符串。产品case编号由后续用例文档定义，此处不预造SES类或旧PRD用例编号。

context包含schema_version、run_id/category/lane、source/fixture/config指纹、内部服务地址、资源引用、报告目录、预算与允许操作；不含Key/DSN/签名URL。数据库工具和控制面凭据经独立私有文件，只给必要进程。API响应安全身份和DB观察权限分开，脚本不能借测试工具任意切到开发库。

每case输出中文“编号＋标题＋准备＋执行阶段＋预期/实际＋结论”，以及结构化case_id、PRD/测试点关联、状态、耗时、stable error_code、预期/实际安全摘要、证据相对路径和hash。脚本中文注释标明对应case。用例前置失败独立记录，不能用return提前跳出却不报结果。

分类结果只允许`passed/failed/blocked/not_run/harness_error`。预期业务拒绝在断言正确时仍是case passed；实际受依赖限制为blocked，不是failed空结果；脚本缺文件/无法采证属harness_error。未ready分类为not_run且产品执行门禁不满足，不能用它们凑通过率。结果数量、case_id集合、重复、run_id/lane和证据路径均与manifest核对；一case只能有一个最终状态，失败重跑另存attempt历史。

总退出码：0为所请求范围实际完成且均通过/清理通过；1产品断言失败；2参数/工具/运行器/报告错误；3前置受限或请求范围未完整执行；4清理失败或无法核验。优先级4＞2＞1＞3＞0；summary保存全部原因，不因优先级丢其它失败。Environment和Selected返回0只针对其范围；All返回0也不自动把全PRD acceptance标通过。

## 9. 报告、证据和真实结果回填

每run输出`summary.json/summary.md`、`evidence-index.json`、`cleanup.json`、`recovery-ledger.json`、environment/preflight结果、分类case JSON/中文记录及指纹。需要时生成JUnit，不能只靠JUnit丢失blocked/工程错误含义。

summary分开列environment、local产品范围、real四依赖/格式/闭环、效果、性能、cleanup；每项明确passed/failed/blocked/not_run及原因。完整acceptance仅在对应必需分类/case、真实业务/格式/模型、指标和清理均满足且无未解决验收失败时通过；Business成功但Acceptance未执行时只写“真实业务smoke通过，完整PRD验收未完成”。

- 运行事实包括时间/平台/资源、执行命令的脱敏参数、HEAD与dirty文件hash、构建镜像ID/依赖锁/Schema/fixture/Profile/view批次指纹；源码运行前后变动则整轮标同源性无效，不能继续称两轮同版本。
- 业务证据包括Document/ParseJob/Build/Task/View/Execution/ToolCall/ContextPlan/ContextEvidence/Message和Event安全关联；远端batch仅留不可逆摘要或私有受限记录，公开产物不保存原能力。
- 日志采集默认每服务5MiB、单轮总200MiB，超限保存截断标记及证据不充分状态；截图/视频默认仅失败必需项，视频可关闭。核心断言所需证据被截断时不得passed。
- 私有原日志先写tmp，白名单投影/脱敏后写artifacts；不输出`docker inspect`完整environment或`compose config`正文。缺失服务日志逐项报告，不用空文件声称采集成功。
- 对Secret、Authorization、签名URL、私有路径作已知值与模式扫描；已知Secret匹配只输出字段/文件及命中数，不输出匹配内容。合成查询/答案只保必要断言摘要，完整Prompt默认不归档。证据泄漏属于工程失败，隔离原件并阻止公开汇总。
- artifacts保留以便回填和复现，不自动覆盖历史。每run记录新增和累计占用；默认累计2GiB软门限，达到时停止新轮并提示按run_id归档，不能静默删除旧报告。

后续正式执行将已测case的实际结果、真实命令/run_id/证据、稳定性回填`test-cases.md`；真实只执行一轮的条目标“仅一轮，稳定性未充分验证”，不能把两个不同语料/历史协议探针拼为稳定两轮。最终测试/缺陷报告列全部失败/blocked/not_run，区分产品代码、测试工程、外部依赖/性能条件，并定位文件与函数；调研已知缺口不能因暂未实现观测就消失。

## 10. 已知缺口和受限场景的测试处理

| 项目 | 当前类型与影响 | 正式测试处理 |
| --- | --- | --- |
| 真实输入计数 | 工程/配置依据缺口，影响真实Embedding/rerank及RAG-016/018/026/044完整业务 | 首先准备校准材料和必要独立修复，不绕门禁。未满足时真实闭环blocked，已可测本地照常，协议补证单列。 |
| 正文引用编号 | 代码闭环缺口，结构化Citation有事实范围而Prompt缺S1等一致编号 | 分开测“引用范围来自实际输入”和“正文标记对应”，预期按PRD/ADR；后者失败列代码缺陷，不改成受限或允许模型乱标。 |
| 观测、日志和计时 | 代码/观测缺口，新身份可能需DB追溯，全阶段duration/上游usage不全 | 测试工程补安全DB观察与外部计时，不补造产品字段；能否满足NFR-005另判。 |
| 未知重建操作键 | 前端潜在缺陷，失败应答可能未保存原key | local复现“已创建但应答丢失”；按事实判是否重复/误导，不预先宣布通过或已发生缺陷。 |
| 并发/GC/保留时间 | 文档与当前实现的口径差异 | 对全局槽、Run内检索、锁序和created_at边界明确断言；必要先同步决策说明，不能用每Worker假设构造无效预期。 |
| 格式位置或云端质量 | 服务能力/返回事实，Word/PPT/Excel常只有规范块 | 可靠位置缺失如实展示是预期；正文/表格遗漏导致目标未达仍列失败或外部差异，不能把全部内容错误归为“没页码”。 |
| Key/网络/额度/上游变化 | 非代码外部前提，逐能力/格式限制 | 给出缺失配置名、错误码、发生阶段及需要操作者补充的事项；不打印Key、不自动换账号和扩大域。 |
| 测试工具/条件缺口 | 本机可通过文件/工具修复的工程问题 | 先修环境/观测再测；不能把缺脚本/假上游能力不足当长期外部受限。 |
| 10k性能/效果未测 | 需要独立数据/指标执行 | 不从短probe/四依赖成功推达标；依资源真实执行，实际不足实报并定位。 |

## 11. 销毁、零残留审计与恢复

### 11.1 正常及失败清理顺序

1. 停止发新业务请求，撤销控制面屏障/临时网络或容量故障，停止本轮浏览器和分类子进程。进程按PID＋创建时间＋父子/可执行身份核对，不按node/python全局名称杀进程。
2. 有界采集证据，随后对明确file/env/project调用`docker compose down --volumes --remove-orphans --timeout 30`；登记的one-off/额外Worker也按标签/ID核对后删除。不调用根默认Compose。
3. 扫描本run所有子project和owner标签的停止/运行容器、网络、命名/意外匿名卷。标签/所有权不一致拒删并记失败。只有down退出0不算通过；命令失败不能解释成列表为空。
4. 按账本移除本轮app/frontend/tools专有tag，先核镜像ID及所有权；若FrozenBuild复用其它轮tag，只删除本轮登记别名，原冻结资产作为明确缓存保留。禁全局system/volume/image/builder prune，禁强制删共享image ID。
5. 保存非Secret恢复账本/清理报告后，删除本run的runtime/tmp、浏览器profile、下载ZIP和私有原日志。Windows使用LiteralPath，Linux核实真实路径/符号链接；目标必须是suite下当前run_id子目录，拒空/`..`/盘符根/home/仓库根。
6. 独立复查后更新最终summary。若Engine不可达或仍有卷，cleanup为unknown/failed，退出4；保留最小恢复账本/私有配置，明确残留和占用，不先删唯一恢复材料来声称干净。

### 11.2 零残留的可观察定义

| 资源 | 通过条件 |
| --- | --- |
| 容器 | ps -a按所有登记project/owner/run查询为空，包括migrate/profile-init/tools/额外Worker |
| 网络与业务卷 | 本轮网络、PG数据、上传、产物、scratch、控制面卷及任何匿名业务卷均不存在 |
| 镜像tag | 本轮专有tag清除；共享基础镜像/冻结归档/构建缓存有意保留且列明 |
| 宿主进程/端口 | 本轮子进程树退出、映射消失；不杀随后复用端口的无关进程 |
| runtime/tmp | 当前run_id私有目录无残留；失败保留的最小材料明确说明且cleanup不得通过 |
| 既有资源 | 开发容器/网络/卷不被本轮删除；启动前后对比记录，外部并发变更不强行归因 |

报告和工具缓存不计业务残留，但必须披露大小/保留原因。连续运行不能积累数据库卷、上传/云端包和私有Key；报告/缓存也有上限和按run_id归档说明。Docker共享缓存无法精确分摊时记未知，不声称释放了所有磁盘空间。

### 11.3 强停与恢复清理

主入口创建资源前即写runtime私有账本及artifacts安全恢复账本，持续原子更新；Cleanup依次读取两者，核对daemon/context、suite/run/owner、资源ID、标签和本地路径，只删除可确认归属的对象。重复运行Cleanup应幂等通过，不能再建环境或请求远端。

全部可信账本丢失时，不凭相似project名前缀猜删；明确人工需恢复账本或核对原Engine与资源归属，并报告仍有未知残留。Docker恢复后继续同run_id Cleanup，不重新执行产品分类。真实远端工作可能继续/产物可能保留，报告单列“本机清理完成、云端结果/保留未知”；不宣称本地down能撤回MinerU文件、取消远端费用或证明供应商数据删除。

## 12. 后续实施路线与阶段退出条件

| 阶段 | 实施任务 | 退出条件／证据 |
| --- | --- | --- |
| A：目录/协议冻结 | 新suite、README/接入计划/Schema/15类planned manifest，更新忽略及导航 | 路径用途明确、无旧工程依赖；58项需求在未来分类有归属；planned/空case不能pass |
| B：工具/数据/控制面 | 锁定工具/浏览器/词表，校验10固定输入，准备Profile/legacy/perf/counter协议及local transport/屏障 | 无真实Key的local不会公网外发；工具启动关闭、自测负例、fixture hash/许可一致；计数真实状态不伪造 |
| C：部署/初始化/真实门禁 | 专有Compose、标签/账本、动态端口、PG扩展/迁移/Profile、同源就绪；real配置预检 | 空库到0010可重复；开发资源共存；真实缺前提输出blocked且没有付费提交；ready不是一条HTTP200 |
| D：总调用/报告/清理 | 五模式、超时、分类协议/Schema验证、脱敏限额/指纹、恢复Cleanup | 退出0无报告/错case/重复/超时不pass；清理失败优先退出4；planned All不能成功 |
| E：环境实施复核 | 两轮新Environment、真实Docker启动失败、分类进程失败/超时、强停恢复清理演练；填写环境记录 | 每轮environment passed、product not_run、cleanup passed；失败演练的预期退出/残留复核有真实证据。真实Ctrl+C若未测单列，不能以替身证明 |
| F：后续测试设计/接入 | 原子测试点、用例、各分类脚本；登记case与ready | 不在A～E直接实施；覆盖PRD及调研差异，逐例独立、中文输出、缺口先补后测 |
| G：正式执行/报告 | Selected排错后冻结源码/镜像，本地至少两轮All；至少一轮Real Business，完整验收还需Real Acceptance及性能/效果 | 分通道/轮次/case保留结果，不用真实历史探针替代。完整通过门槛见第9节；受限/失败全部定位、复现、后续动作清楚 |

G中的“一轮真实业务”是最低必需安排，不表示Business可代替七办公格式或20+5效果验收。为控制费用，Acceptance可在同轮复用新鲜业务产物，不要求所有付费场景再整体重复两次；稳定性结论按实际轮次限定。任何产品修复改变源码后，冻结新版本重新执行受影响及关键回归，旧失败证据保留，不拼成虚假的同源两轮通过。

## 13. 实施后的参考命令与复现约定

以下命令接口现已由环境入口实现，但Selected/All/Real仍受planned及真实前提门禁约束；本节示例不当作实际执行记录，实际历史命令见第16节链接。Windows PowerShell及Linux Bash均从仓库根调用`pwsh`，Docker/Linux宿主安装与真实服务运行前提见[Runbook](../runbooks/rag-v3-development.md)。

```powershell
# 安装/检查本suite工具，不调用真实服务。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/setup-tools.ps1

# 仅技术闭环，可在产品分类未接入时运行。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment

# 后续分类ready后，先专项排错，再完整local；第二轮显式加载首轮冻结构建账本。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories 'ingestion,retrieval'
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode All
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode All -FrozenBuild '<首轮summary.json的frozen_build标识>'

# 满足真实计数、凭据及预算前提后才执行，live文件由准备工具生成且被忽略。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -RealPlan Business -AllowRealRequests -LivePlan tests/sesrag-rag-mineru-test/runtime-inputs/live-plan.json

# 完整真实格式/业务/效果同环境复用语料；不能在不需重提时自动再跑整轮。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -RealPlan Acceptance -AllowRealRequests -LivePlan tests/sesrag-rag-mineru-test/runtime-inputs/live-plan.json

# 将run_id替换为实际summary/console中的值，只恢复清理。
pwsh -NoProfile -File tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Cleanup -RunId rag-20261111t120000z-a1b2c3d4
```

`runtime-inputs/`是操作者私有输入目录，实际实施时同样新增Git/Docker忽略，不随单轮清理误删原始凭据来源；复制到runtime的本轮凭据必须删除。实际入口的FrozenBuild参数接收首轮summary.json中的24字符构建标识，内部定位`.cache/frozen-builds/<标识>/build.json`，不接收任意归档路径；live计划示例路径需替换为真实已准备文件。不存在时入口拒绝，不自动生成“已校准”配置。Linux使用相同命令，路径大小写、权限与PS可用性分别预检；未在Linux宿主实际演练就明确未测，不能从Linux容器推断宿主跨平台已验。

复现记录必须给实际命令、run_id、lane/plan/category/case、源码/镜像/fixture/Profile指纹、退出码及证据路径；真实重放还需说明是否可能重新外发/计费。日志或报告中不回显私有配置正文和Secret参数。

## 14. 方案实施验收清单

本表验收环境工程，不是预先设计全部产品用例。

| 编号 | 必须满足的要求 | 实施后应提交的证据 |
| --- | --- | --- |
| ENV-003-01 | 专属目录、README、接入计划、planned清单及协议完整，无前轮依赖 | 实际文件清单、链接/Schema/范围校审 |
| ENV-003-02 | 工具与固定输入可复现、无静默运行时下载 | 工具/锁定版本、Chromium/词表探针、10份hash和许可核验 |
| ENV-003-03 | 环境不读开发.env、不混开发卷/端口/凭据 | 安全Compose投影、动态地址、Engine及资源账本、忽略/构建上下文检查 |
| ENV-003-04 | 迁移/Profile/数据库扩展/Worker/前端均按顺序就绪 | 0010 revision、扩展版本、migrate/import退出0、Worker事实及同源HTTP/SSE探针 |
| ENV-003-05 | local可控传输与真实网络边界明确 | 启动绑定自检、无真Key/外网、协议与屏障负例；未声称已验证真实DNS/TLS |
| ENV-003-06 | Real门禁真实有效，不绕counter守卫 | 缺授权/Key/counter/域/预算的无外发拒绝自测；真实前提状态及尚未退出项 |
| ENV-003-07 | 模式/分类/case/退出码不产生假通过 | planned、空报告、重复case、错run/lane、退出0无证据等自测 |
| ENV-003-08 | 两次干净Environment完整闭环 | 两个新run_id、environment passed/product not_run/cleanup passed及相同源码指纹 |
| ENV-003-09 | 失败/超时/中断可回收，强停可恢复幂等 | 真实Docker失败演练、主进程强停后Cleanup、再次Cleanup，替身证据另列 |
| ENV-003-10 | 无本轮容器/网络/业务卷/tag/进程/私有目录残留 | 独立查询结果及占用变化；缓存/报告和云端未知状态单列 |
| ENV-003-11 | 报告中文、脱敏、有界、指纹/证据可追溯 | summary/清理/证据索引、Secret扫描和截断负例，不隐藏采集错误 |
| ENV-003-12 | 产品与工程缺口不被环境“修好”掩盖，真实业务后续可接入 | 修改清单、门禁/剩余事项、F/G路线与live预算，未运行产品项明确not_run |

## 15. 本次方案整体校审结论

本方案按九格式固定路线、无解析回退、真实/Mock分列、PG事实源、候选与active隔离、冻结视图、实际证据范围、统一主入口和所有权清理统一设计。覆盖矩阵包含PRD的46项功能和12项非功能；环境/正式用例的边界、真实计数前提、三份真实分类和12份local分类职责均已明确。

本次校审重点避免以下冲突：把协议探针当真实业务；把unverified配置直接启用；用local All宣称全PRD通过；让假MinerU依靠放松生产SSRF守卫；混淆增强截取与生成预算、latest与active；只执行down却不查卷；为了零残留删除恢复账本；因复制旧suite引入跨轮数据/脚本依赖。真实未知提交和本机清理不等于云端撤回/费用归零，已在流程和报告口径中一致说明。

已执行文档机械校核：需求矩阵覆盖全部58项，12个local与3个real分类无重复，5项真实门禁与12项环境实施验收条目齐全；15章和15张表的结构一致，本方案及两份导航的109个本地链接有效，UTF-8/尾部空白和本次导航diff格式检查通过。Compose覆盖的最低版本与冻结镜像恢复方式已补明确。校核摘要保存在本机忽略目录`data/rag-implementation/test-plan-20261111/document-audit.json`，该路径不是产品测试结果。

方案制定阶段交付为方案文档和导航，当时环境和产品测试均未执行；上述文字保留其时间边界。环境实施后的状态如下，正式case、真实业务请求、效果与性能仍未执行，不能以设计或环境校审结论宣称这些结果通过。

## 16. 2026-11-11环境工程实施结果

A～E环境工程现已在[独立suite](../../tests/sesrag-rag-mineru-test/README.md)完成：两份Compose、三镜像构建、PowerShell包装/Python唯一生命周期、独立宿主工具环境、Chromium/离线词表、固定输入校验、分段迁移/Profile初始化、local控制面、15分类planned清单及三份Schema、报告/指纹/证据hash、所有权清理和中断恢复均已准备。没有改产品业务、正式契约、生产Compose或前轮验收目录。

实际补充的模块包括`helpers/common.py`、`protocol.py`、`builds.py`、`initialize.py`、`live_budget.py`、`evaluation_data.py`、`download_browser.py`、`lifecycle_exercise.py`与评测Schema，职责分别见[helpers说明](../../tests/sesrag-rag-mineru-test/helpers/README.md)和[fixtures说明](../../tests/sesrag-rag-mineru-test/fixtures/README.md)。Windows真实试跑发现并修正插件系统环境缺项、SQLite句柄、Profile Path适配、Vite内部Host、pwsh分类列表、慢下载/续传、归档强停登记和已退出进程误判；详细原因与失败证据在[环境实施记录第2～3节](../../tests/sesrag-rag-mineru-test/环境实施与验证记录.md#2-试跑中发现与修正)。

实现与原设计的明确差异：

| 项目 | 实际实现及理由 | 验证边界 |
| --- | --- | --- |
| 宿主依赖 | `.cache/host-python`独立venv；tools复制产品运行依赖并增加精确测试工具锁 | 不再向项目venv安装本suite锁；项目依赖检查已恢复正常 |
| 浏览器 | Playwright 1.58.2的Chromium Headless Shell及FFmpeg，官方清单/有界续传/包校验/官方安装器 | 只需无头浏览器；未配置有头GUI，不影响后续Playwright页面测试 |
| 同源地址 | tools解析本轮frontend容器IP再走前端代理；宿主仍127.0.0.1动态端口 | 避免Vite拒绝frontend域名，不扩大产品Host白名单 |
| 冻结构建 | Environment成功也保存归档，FrozenBuild接收构建标识而非任意文件路径 | 两轮实际archive load已验证；源/依赖不一致拒绝 |
| 真实分类 | Real Acceptance在一个专属real project内按分类串行复用语料，共享预算账本，分类报告分目录 | 不按分类重新创建付费语料；所有real分类仍planned，本次只验拒绝门禁，未外发 |
| 账本 | runtime存完整有效配置及凭据，artifacts持久安全恢复账本；load前登记临时原tag及预期ID | runtime删除后仍能恢复清理；无账本不猜删，恢复只按可信账本/Engine/标签/ID |
| 旧库及性能 | 提供专属case数据库工具、0006基线、确定性数据生成与标注格式协议 | 具体旧状态、性能持久数据及20+5标注由后续用例准备，不预写产品成功 |
| 异常演练 | 实际Docker API启动失败、tools技术子进程失败/超时、主进程强停及两次Cleanup | 尚无产品分类，技术演练不冒充产品case；真实Ctrl+C未测 |

最终驱动命令：

```powershell
pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/setup-tools.ps1
& ./tests/sesrag-rag-mineru-test/.cache/host-python/Scripts/python.exe ./tests/sesrag-rag-mineru-test/helpers/lifecycle_exercise.py --prefix rag-env-20261111-v4
```

prefix为历史实测值，重演换新prefix；两轮Environment分别为`rag-env-20261111-v4-env1/env2`，源码/构建指纹一致，均environment passed/product not_run/cleanup passed/exit0。冻结标识为`d863280ae44f39da8693d941`。启动失败、子进程失败/超时预期并实际退出2；强停后Cleanup两次0；All全planned与Real无授权各退出3，无产品/付费调用。工程驱动最终退出0，完整矩阵、原始证据链接、排错及资源占用见[环境实施记录](../../tests/sesrag-rag-mineru-test/环境实施与验证记录.md)。

最终独立复查本suite容器/网络/业务卷/专有tag、活动子进程及runtime/tmp均为空，既有6个外部容器及原网络/卷集合不变。报告、工具及归档缓存明确保留，Docker全机BuildKit缓存不做全局prune；另有约0.53MiB的pip旧临时目录清理被自动审批拒绝，已单列，未声称释放。25项宿主工程自测通过，容器自测24通过/1宿主专用Compose项跳过（宿主该项通过）；静态及文档/Schema检查通过。

ENV-003-01～12已按环境工程口径完成校审。F/G仍待后续：设计正式用例、接入分类脚本、真实计数校准及配置/授权/额度、20+5标注、逐格式/真实业务/效果/性能正式执行和报告。Linux宿主及真实Ctrl+C尚未实测，前后端产品全量质量门禁本次未运行。环境交付不替代PRD-003正式验收。
