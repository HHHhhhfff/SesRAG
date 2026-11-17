# PRD-005：SesRAG本地Grafana监控告警体系

| 字段 | 内容 |
| --- | --- |
| 编号 | PRD-005 |
| 版本 | 1.1 |
| 状态 | **已确认，已实施**；Windows Docker Desktop范围已交付并验证，Linux可选profile未验收 |
| 日期 | 2026-11-16（Asia/Shanghai） |
| 产品／适用范围 | SesRAG仓库内独立的本地监控模块`docker/monitoring/`；首要平台为Windows Docker Desktop Linux容器，也兼容原生Linux Docker Engine |
| 当前项目基线 | 工作区分支`main`，HEAD `8876a66141a7e237fe45cc10b4b6f87178953e77`，包版本0.3.0；005是需求编号，不自行升级产品/API版本 |
| 依据 | [ADR-005：Grafana监控体系本地搭建与部署方案](../adr/005-sesrag-local-observability-deployment-plan.md)；[本地可观测体系调研](../runbooks/local-observability-compose-research.md) |
| 关联交付 | [PRD-004应用可观测性](004-SesRAG-应用可观测性与追踪上下文-PRD.md)、[PR-004实施结果](../pr/004-SesRAG-应用可观测性与追踪上下文-PR.md)、[正式接口文档](../接口文档.md) |
| 后续方案 | ADR-005作为本PRD的实施基线；完成实施后新增`docs/pr/005-SesRAG-本地监控部署-PR.md`记录实际差异与验证结果 |
| 阶段／依赖 | 004应用能力已交付；005实施结果见[PR-005](../pr/005-SesRAG-本地监控部署-PR.md)。每个新部署接线仍须核G1～G5，不依赖本轮临时环境继续存活 |

## 1. 需求定位与预期结果

本轮拟把PRD-004已经具备的指标、日志和追踪能力接入一套可重复启动、查询、告警、备份、恢复和销毁的本地监控体系。使用者是本地运行SesRAG的开发者或维护者：日常查看健康与积压，异常时从指标定位到日志/追踪，再通过受控故障确认告警有效。

P0表示接入、安全或核心闭环必需项；P1表示完整交付所需的展示、维护或质量能力，不能在完整验收时默认跳过。默认Desktop与可选Linux的结果分开记录。

本轮交付的是**本地开发与排障能力**。它不提供生产级高可用、外部独立宕机监测、生产SLO或零丢失保证；电脑休眠、Docker Desktop停止或本机资源耗尽时，监控会随本机一起停止。

| 目标 | 预期结果 | 完成判定 |
| --- | --- | --- |
| O5-G1 独立可重复部署 | 监控由独立Compose project管理，可预检、拉取锁定镜像、启动、停止、重启和销毁 | 同一环境重复执行不会接管或删除应用project；失败只回收本轮自有资源 |
| O5-G2 三信号可查询 | 真实应用metrics进入Prometheus，获准stdout进入Loki，应用OTLP traces经Alloy进入Tempo | Grafana可查询三类信号，并使用真实service/environment/trace身份关联 |
| O5-G3 版本化展示与告警 | 数据源、面板、告警规则、联系点和路由由provisioning恢复 | 重建后UID稳定；告警经历Pending、Firing、通知、恢复和Resolved |
| O5-G4 资源与数据有界 | 组件内存、CPU、卷预算、保留期、队列和丢弃边界明确 | 报告实际资源、写入错误、拒绝和丢弃；不把配置值当作实测或零丢失证明 |
| O5-G5 保留与销毁可区分 | Stop保留监控历史，Destroy只清理监控模块资源 | Stop后可恢复查询；Destroy后监控资源清单为空，应用数据库、上传、索引和其它Compose不变 |
| O5-G6 失败可诊断可恢复 | 配置、网络、端口、权限、镜像、磁盘和依赖失败有明确诊断 | 启动失败、Ctrl+C、主进程硬停和恢复流程都不破坏已有环境 |

## 2. 实施前基线与本轮差距（需求确认时点）

| 当前代码／文档 | 已有能力 | 本轮差距 |
| --- | --- | --- |
| `docker-compose.yml` | 已有PostgreSQL、Redis、API、Worker、前端及业务卷 | 没有独立监控Compose、监控网络、监控卷和生命周期入口 |
| `backend/infrastructure/observability/`、`contracts/observability/` | PRD-004已提供安全指标、JSON日志、OTLP traces及版本化契约 | 本轮只消费这些契约，需增加应用契约输入、Prometheus/Alloy/Loki/Tempo/Grafana配置和验证工具 |
| `docs/接口文档.md`§9 | 已冻结API `9101/metrics`、Worker `9102/metrics`、指标语义和日志/追踪边界 | 需要把真实实例、应用网络、环境标签和目标列表渲染为监控接入描述 |
| `docs/pr/004-SesRAG-应用可观测性与追踪上下文-PR.md` | 已验证28类指标、真实OTLP捕获、四类Task关联和安全日志 | 监控模块仍需验证信号实际抵达Prometheus、Loki、Tempo，并建立Grafana关联 |
| `backend/app.py`、`backend/workers/main.py`、`backend/infrastructure/observability/config.py` | API/Worker装配独立registry/日志/SDK；指标和日志默认开启，traces默认关闭，需显式内网endpoint与主机白名单 | 仅配置已有OBS开关，不新增应用插桩；先在目标应用启用后再验证Tempo到达 |
| `docker-compose.yml`、`.env.example` | API/Worker端口只expose；日志采集标签`collect=false`，traces默认false，服务身份固定 | 需交付`application.override.yaml`、合并检查与显式应用步骤；不能把代码支持解释为已开始采集 |
| `backend/tools/export_observability_contract.py` | 可导出源码ref/指纹及观测能力；不证明任何当前Docker网络归属或目标在线 | 005部署描述在引用导出结果之外另核实际容器、网络、别名和目标列表 |
| `docs/runbooks/local-observability-compose-research.md` | 已完成组件职责、版本候选、存储和清理研究 | 需要形成可执行的固定版本、配置、告警、备份/恢复和资源边界 |
| 仓库当前目录 | 尚无`docker/monitoring/` | 新增独立模块；不把业务代码、数据库迁移、Task传播或前轮测试工程纳入本轮 |

这些实现事实来自源码核对，PR-004中的验证只代表其记载的版本和环境，不能外推为005验收通过。PRD-004负责“产生正确且安全的遥测”，本PRD负责“接收、存储、查询、展示、告警和生命周期管理”。监控采集失败不能写回Run/Task/Event终态、改变租约或触发业务重试。

### 2.1 实际部署接入门槛

| 门槛 | 接线前须核对的内容 | 不满足时的行为 |
| --- | --- | --- |
| G1 来源与契约 | 正式接口/能力字典引用、源码ref与相关dirty指纹、应用project和环境身份 | 输出实际差异，不生成假绑定 |
| G2 指标 | API/逐实例Worker真实端点、类型/单位/有限labels、初始化条件、快照有效性与唯一统计来源 | 缺必需绑定或实际语义冲突则拒绝接线 |
| G3 日志 | stdout字段、service/environment、适用业务身份与有效trace字段，源端无敏感正文 | 拒绝把不安全来源直接接入；非JSON受控负例按专门策略验证 |
| G4 traces | 已有OTLP HTTP/protobuf开关、精确白名单、服务身份、Task兄弟attempt拓扑与来源采样约定 | 先报告来源/配置缺口，不在005补SDK或任务传播 |
| G5 实例与权限 | 已运行的专用开发应用、容器/网络实际归属、唯一别名及部署override的允许步骤 | 不接管同名网络、不自动启动或重建应用 |

准备输入须引用全部门槛；正式应用信号接线验证在已明确应用override后完成。Status和清理不能因应用离线或契约漂移被阻断；这些动作仍要核验自有资源和路径。

## 3. 实施边界

### 3.1 本轮范围

1. 在`docker/monitoring/`提供独立Compose、固定镜像版本、配置模板、专用运行输入、宿主工具和验证入口。
2. 部署Grafana、Prometheus、Loki、Tempo、Alloy五个核心组件，以及只用于本地告警验证的`webhook-sink`和按需验证工具。
3. 只读核验并接入已经运行的应用API/Worker指标端点；通过Docker stdout采集获准应用日志；通过OTLP HTTP/gRPC接收应用追踪。
4. 提供Grafana三数据源、版本化仪表盘、Grafana-managed Alerting、内置告警路由和本地Webhook通知闭环。
5. 提供Prepare、Pull、Validate、Start、Verify、Status、Stop、Backup、Restore、Destroy等生命周期动作及脱敏报告。
6. 提供Docker Desktop默认profile和原生Linux可选profile；Linux profile可以加载Node Exporter，但不属于Windows平台能力。

### 3.2 明确不实施

- 不修改`backend/`、`frontend/`、数据库Schema、Task传播、应用指标语义、业务接口或PRD-004契约。
- 不实施`windows_exporter`、Windows物理CPU/内存/磁盘指标、cAdvisor、PostgreSQL/Redis Exporter。
- 不把Linux容器指标伪装为Windows宿主指标；Docker Desktop默认不加载Linux主机面板。
- 不部署独立Alertmanager，不在Prometheus或Loki重复定义告警规则；只使用Grafana-managed Alerting及其内置路由。
- 不接入SMTP、企业Webhook、云托管监控、CI工作流、云资源或外部账号。
- 不启用Tempo metrics-generator/service graph、profiling、eBPF、tail sampling、OTLP logs/metrics、remote-write或持久遥测队列。
- 不执行全机`docker prune`、Desktop reset、宿主VHDX压缩、应用数据库/上传/索引清理或前轮正式验收目录修改。
- 前轮`tests/sesrag-persistent-session-workspace-test/`、`tests/sesrag-rag-mineru-test/`、`tests/sesrag-observability-test/`均不纳入本轮修改或运行依赖；005另建自身验证文件。

## 4. 用户可见能力与关键工程设计

### 4.1 组件与网络

默认监控Compose project为`sesrag-observe-<environment-id>`，默认环境为`local`；environment_id只允许1～32位小写字母/数字/短横线。监控组件连接自有`monitoring` bridge网络；Prometheus和Alloy额外连接已经由应用project拥有、并通过实际资源ID/labels核验的应用网络，不创建、删除或接管它。网络连接本身不是只读权限隔离。

Alloy在应用网络使用唯一别名`sesrag-obs-<environment-id>-alloy`。Prometheus抓取应用目标，Alloy采集获准stdout并接收OTLP，Loki保存日志，Tempo保存追踪，Grafana查询三类数据并管理告警。

| 组件 | 容器端口与用途 | 默认宿主暴露 |
| --- | --- | --- |
| Grafana | 3000，UI/查询/告警 | `127.0.0.1:3000` |
| Prometheus | 9090，查询/抓取状态 | 不暴露 |
| Loki | 3100，日志写入/查询/ready | 不暴露 |
| Tempo | 3200查询/ready，4317/4318 OTLP | 不暴露 |
| Alloy | 4317/4318 OTLP，12345管理 | 不暴露；host-otlp为可选回环profile |
| webhook-sink | 8080，本地告警接收 | 不暴露 |
| Node Exporter | 9100，仅Linux可选profile | 不暴露 |

Grafana匿名访问、自动更新检查和启动时插件下载默认关闭。OTLP接收器绑定容器接口不等于发布到宿主公网；普通bridge不构成主机防火墙隔离保证。

Alloy默认需访问开发Docker daemon的Unix socket读取日志；socket挂载`:ro`不限制Docker API写权限，project/label过滤也不是权限隔离。该组件仅限可信本地配置，不开放TCP2375、不默认privileged。原生Linux可选Node Exporter需要另外核准受限主机挂载，不能与Desktop默认权限混用。

### 4.2 核心对象与关系

| 对象 | 含义与主要职责 | 关键字段/约束 |
| --- | --- | --- |
| `MonitoringEnvironment` | 一个可独立启动、停止、保留或销毁的监控实例 | `environment_id`、Compose project、监控网络、五类卷、平台profile；资源只属于一个环境 |
| `ApplicationContract` | 监控模块接入某个已运行应用实例的版本化描述 | 应用project/network、API/Worker targets、指标绑定、日志字段、OTLP配置、源码/契约指纹；禁止Secret、公网URL和未核验网络 |
| `SignalSource` | 进入监控存储的指标、日志或追踪来源 | service/environment、来源容器、协议、采集路径、有效性与错误状态；是业务事实的投影 |
| `Datasource` | Grafana查询后端的固定连接身份 | UID固定为`sesrag-prometheus`、`sesrag-loki`、`sesrag-tempo`；URL只使用监控网络DNS |
| `Dashboard` | 版本化的查询和展示定义 | `overview`、`application`、`pipeline`、可选`linux-host`；禁止把缺失信号填成常数0 |
| `AlertRule` | Grafana-managed的诊断规则 | `obs005-<rule-id>`、folder `sesrag-observe`、environment/service分组、warning/critical级别；Prometheus/Loki不另设重复规则 |
| `LifecycleRun` | 一次Prepare/Pull/Validate/Start/Verify/Stop/Backup/Restore/Destroy操作及其证据 | run-id、源码/配置/镜像/契约hash、资源账本、状态、脱敏artifacts；不记录Secret或业务正文 |
| `MonitoringBackup` | 监控卷和配置的受控备份 | environment、backup-id、卷清单、manifest、完整性校验、目标路径；Restore只写核验为空的监控卷 |

对象名称用于描述职责，具体字段、代码类型及持久方式由ADR-005细化；稳定术语以[CONTEXT.md](../../CONTEXT.md)为准。`ApplicationContract`引用004能力导出和正式接口，另加实际部署身份，不是直接把004样例复制成实例，也不新增业务数据库对象。

关系为：`ApplicationContract`描述已运行应用，`MonitoringEnvironment`按契约连接应用网络；`SignalSource`分别进入Prometheus/Loki/Tempo；Grafana的`Datasource`查询这些存储，`Dashboard`和`AlertRule`引用固定UID；`LifecycleRun`记录整个操作但不改变应用事实。

### 4.3 三类信号与关联

- **指标**：Prometheus以15秒抓取、5秒timeout拉取API `9101/metrics`、Worker `9102/metrics`及监控组件自身指标；应用job使用`honor_labels=true`保持源service/environment，Prometheus补job/instance。不通过Alloy重复抓取同一metrics，不把run/task/trace身份放入时序标签。多个Worker须逐实例唯一目标，counter先逐实例rate再sum；API全局快照不跨实例sum。
- **日志**：Alloy只采集同时满足应用Compose project、环境标签和显式opt-in标签的API/Worker stdout，不采自身发送失败日志造成反馈。默认按004的JSON字段解析timestamp/level/trace_id；Loki索引标签仅使用environment、service和有限level。非JSON受控日志必须有明确安全处理与错误诊断，不静默丢弃，也不默认透传可能含Secret的原始异常。
- **追踪**：Alloy接收器支持受控HTTP/gRPC，SesRAG现有应用使用HTTP/protobuf `/v1/traces`，不要求005给应用增加gRPC出口。处理后经有界batch/重试发送Tempo，不重设来源采样，不增加OTLP logs/metrics支持。
- **关联**：Grafana pipeline面板按真实trace_id连接Loki与Tempo。缺失span必须区分采样、源端未产生、传输丢弃、查询窗口和过期，不能直接判断业务失败。

队列和Worker聚合健康使用004的initialized/valid/last_success guard，默认有效期30秒；初次成功前缺少业务值，不填0。队列积压只取有效且到时待领queued，retry_backoff和waiting_external另行显示；指标抓取成功不等于业务ready。Alloy持久positions仅保存读取位置，发送缓冲仍是有界内存，崩溃、下游断开或Docker日志轮转可导致丢失，不承诺exactly-once。

### 4.4 展示与告警行为

默认仪表盘至少包含：

1. `overview`：抓取状态、组件写入/导出错误、丢弃、进程资源和数据路径状态。
2. `application`：API短请求量/5xx/耗时、Worker readiness、队列长度/最老等待、Task尝试结果和阶段耗时；SSE和后台Run不混为短请求耗时。
3. `pipeline`：环境/service过滤、Loki检索、Tempo查询及双向trace关联。
4. `linux-host`：仅Linux profile显示真实CPU、内存、文件系统和loadavg；Desktop不显示伪造宿主指标。

默认规则由Grafana统一管理。下表阈值是本地排障默认值，不是产品SLO；调整时有界配置、重新渲染并记录版本。规则必须使用真实指标绑定，绑定缺失时拒绝生成，不能用空查询或`or vector(0)`掩盖缺口。

| 规则 | 判定目标 | 持续等待／级别 |
| --- | --- | --- |
| TARGET-DOWN | 预期API/逐实例Worker或监控组件目标up=0，或固定预期目标序列缺失 | 2分钟／critical |
| METRIC-MISSING | up=1，但承诺always必需序列缺失，或已首次成功source的条件必需序列缺失；不要求尚未知的业务快照初始化为0 | 2分钟／critical |
| OBSERVATION-INVALID | 目标可抓取，但队列/Worker聚合来源未知、valid=0或快照超过30秒有效期 | 2分钟／warning |
| WORKER-NOT-READY | 来源已知且新鲜、对应目标可抓取，但聚合worker_ready不为1 | 2分钟／critical |
| QUEUE-WAIT | 同task_kind的可信到时待领数>0且最老等待>120秒 | 5分钟／warning |
| API-ERROR | 最近5分钟普通短请求样本≥20且5xx比例>5%；排除SSE/probe和客户端错误 | 2分钟／warning |
| TASK-FAILURES | 最近10分钟failed attempt增量≥3；不把yielded/cancelled/lease_lost/released混作失败 | 2分钟／warning |
| PIPELINE-ERROR | 最近5分钟Alloy导出失败/拒绝或Loki/Tempo写入错误counter有增量；具体自指标在固定版本核验后绑定 | 1分钟／warning |

正常空闲查询须产出带环境/服务身份的数值0；目标失联、必需序列缺失、来源失效、数据源查询错误分别诊断，业务阈值规则不可因guard失效额外宣布业务失败。规则统一`noDataState=NoData`、`execErrState=Error`；DatasourceNoData/DatasourceError有专门通知策略，不能设为OK或永久保留上次状态。无请求不报API错误，但不能掩盖up失败；不为长SSE/生成默认设置短HTTP延迟告警。

默认通知路由为本地`webhook-sink`，按environment/service分组，发送Firing和Resolved；group_wait 30秒、group_interval 1分钟、repeat_interval 4小时。sink同时满足最近100条及最长24小时的保留上限，字段白名单过滤、重建即清空，不新增持久卷或外部目的端。验收须核通知分组、去重与重复；隔离测试可缩短重复窗口，结束恢复4小时默认并留差异记录。

provisioning为正式配置入口，面板禁止直接UI覆盖；探索另存临时副本。撤销数据源/规则必须显式删除或prune UID，并实际确认数据库内对象消失，不能只删本地YAML。已有Grafana卷重启不能通过覆盖首次启动密码文件假称已重置密码。

### 4.5 生命周期与数据状态

| 动作 | 行为要求 |
| --- | --- |
| Prepare | 校验Docker/Compose、平台、契约、应用project/network归属、端口、磁盘和输入路径；生成本环境配置与首次凭据，重复执行不覆盖既有Secret/数据，不启动服务 |
| Pull | 只拉取显式锁定版本，记录tag、digest、架构和退出结果；不使用`latest` |
| Validate | 用固定版本可用的解析工具及Schema检查配置/provisioning引用；不启动应用或存储。Tempo等若无纯解析入口，明确记录并在独立临时环境受限启动验证后清理，不把YAML可读当兼容通过 |
| Start | 只启动监控project，按ready状态轮询；应用未运行或准入不满足时拒绝接线，不替用户启动应用 |
| Verify | 依次检查真实/合成信号、数据源、面板、告警Firing/Resolved、关联和资源，报告状态为passed/failed/blocked/not_run |
| Status | 只读报告组件、卷、保留期、空间、抓取和写入状态；不要求应用在线即可读取监控自身状态 |
| Stop | 停止监控容器但保留监控卷、配置和历史；不删除应用网络或业务卷 |
| Backup | 停止监控写入后备份五卷、配置、必要Secret和manifest；权限受限，公共报告只含安全索引/hash；完成后恢复原运行状态。应用可离线，取消/半份备份不得标记完整 |
| Restore | 校验同版本manifest、hash、归档路径/链接/展开预算及权限；只写已核验为空且属于目标环境的监控卷，拒绝覆盖已有历史；后续Start/Verify仍须过接入门槛 |
| Destroy | 明确选择`EraseMonitoringData`后，仅删除本环境监控project容器、named volumes、自有network和runtime临时副本；保留并列明显式备份、报告、镜像、BuildKit cache及应用资源 |

环境状态按`absent→prepared→starting→running→stopped→destroyed`记录，异常保留`failed`、阶段和资源清单；状态不等于应用Run状态。单环境互斥、跨环境资源隔离；每次操作新run-id，不覆盖报告。Start失败/中断只撤销本次新增资源，保留已有卷及健康环境；硬停后靠账本和实际labels复核恢复，不能只凭锁不存在判断无资源。

Stop/Destroy在应用离线或契约变化时仍应可清理，只需Docker可用及自有资源/路径核验。停止监控不会自动撤销应用OTLP配置，源端可有有界导出失败，恢复后继续发送；需要撤销时按文档显式操作。删除named volume只释放Docker内部空间，不保证Windows VHDX文件立即缩小。

### 4.6 技术基线

实施默认采用ADR-005冻结的版本基线；正式实施时仍需复核官方镜像可用性、安全通告、目标架构并记录digest，不能用`latest`替代版本锁定。

| 组件／工具 | 版本基线 | 主要职责 |
| --- | --- | --- |
| Grafana | `grafana/grafana:13.3.1` | UI、数据源、provisioning和Grafana-managed Alerting |
| Prometheus | `prom/prometheus:v3.16.0` | 唯一指标存储、抓取和promtool配置校验 |
| Loki | `grafana/loki:3.7.10` | 单体TSDB日志存储与查询 |
| Tempo | `grafana/tempo:3.1.1` | 单体本地trace WAL/blocks与查询 |
| Alloy | `grafana/alloy:v1.21.3` | Docker stdout采集、OTLP接收/处理/转发 |
| Node Exporter | `quay.io/prometheus/node-exporter:v1.12.1` | 仅原生Linux可选profile，不是Windows替代 |
| Docker／Compose | Docker Engine 26+、Compose 2.27+ | 容器编排与生命周期操作 |
| 宿主工具 | Python 3.11+专属venv、PowerShell 7.4+ | Schema校验、预检、渲染、报告和生命周期包装 |

Prometheus默认全局抓取间隔15秒、timeout 5秒；Grafana规则组默认30秒评估。版本、digest、目标架构和工具依赖hash必须写入运行报告。

## 5. 功能需求清单

| ID | 功能需求 | 验收标准 | 优先级 |
| --- | --- | --- | --- |
| OBS5-001 | 监控接入必须使用版本化`ApplicationContract`，绑定应用project、网络、API/Worker目标、指标/日志/OTLP真源和源码指纹 | 缺失G1～G5任一门槛、契约版本不匹配、应用网络归属不符时停止接线且不创建业务假数据 | P0 |
| OBS5-002 | 监控必须由独立Compose project运行，使用自有监控网络和自有数据卷 | 重复Start可识别同一环境；应用project、业务卷和应用网络不被纳入监控清理 | P0 |
| OBS5-003 | 镜像、宿主工具和配置必须有固定版本、digest/依赖锁和显式Pull动作 | `latest`、digest不符、架构不符或配置漂移时拒绝启动；记录版本和来源 | P0 |
| OBS5-004 | 提供有界生命周期入口，覆盖Prepare/Pull/Validate/Start/Verify/Status/Stop/Backup/Restore/Destroy | 命令输入和输出为结构化状态；Docker命令、启动、验证、备份和清理有截止时间和中文诊断 | P0 |
| OBS5-005 | Prometheus必须抓取API、Worker和监控自身指标，并保留固定service/environment身份 | API/Worker实际指标可查询；抓取间隔、timeout、label上限符合契约；不新增高基数业务标签 | P0 |
| OBS5-006 | Alloy必须只采集获准应用stdout，并将安全JSON日志转发Loki | project、环境和opt-in过滤生效；其它project或未授权服务日志不可进入默认Loki；解析/脱敏错误可诊断 | P0 |
| OBS5-007 | Alloy必须接收受控OTLP并将应用追踪发送Tempo | 真实应用trace可按trace_id查询；接收端、batch、重试、memory limiter和丢弃可观察，不改变业务结果 | P0 |
| OBS5-008 | Grafana必须自动配置Prometheus、Loki、Tempo三个固定UID数据源 | 重建后UID、URL、访问权限和健康状态一致；不启匿名Admin或联网下载未知插件 | P0 |
| OBS5-009 | Grafana必须提供overview/application/pipeline面板，并按契约显示未知、缺失和无数据状态 | 面板查询使用真实指标单位/标签；缺少来源时显示不可用，不填伪造0；Loki↔Tempo关联使用真实trace_id | P1 |
| OBS5-010 | 告警规则必须由Grafana-managed Alerting统一管理 | 规则UID、folder、阈值、NoData/Error语义和环境分组稳定；Prometheus/Loki不重复告警 | P0 |
| OBS5-011 | 告警必须覆盖目标失联、必需指标缺失、观测无效、Worker未就绪、队列等待、API错误、Task失败和流水线错误 | idle不误报；受控故障产生正确Firing并在恢复后Resolved；规则绑定缺失时拒绝渲染 | P0 |
| OBS5-012 | 默认通知必须闭环到本地Webhook sink，外部通知保持关闭 | Verify实际捕获Pending→Firing→Webhook→恢复→Resolved；sink只保存有限、脱敏通知 | P1 |
| OBS5-013 | 监控数据必须按组件和信号设置保留期、卷预算和空间预警 | Grafana约0.5GiB、Prometheus约3GiB/7天、Loki约3GiB/72小时、Tempo约3GiB/24小时、Alloy约0.5GiB；70%提示、85%警告可报告 | P1 |
| OBS5-014 | 停止、重启、销毁必须区分数据保留和资源销毁 | Stop后历史可查；Destroy后监控资源为空且应用DB/上传/索引、其它project和外部网络保持不变 | P0 |
| OBS5-015 | 必须支持监控卷和配置的受控备份/恢复 | manifest完整性可校验；半份备份拒绝；Restore不得覆盖非空或非本环境卷，恢复后可再次Verify | P1 |
| OBS5-016 | Docker Desktop与原生Linux平台行为必须明确区分 | Desktop不安装/加载windows_exporter和Linux宿主面板；linux-host仅显式选择Node Exporter profile | P0 |
| OBS5-017 | 所有运行、验证、告警和清理结果必须生成脱敏报告 | 报告含run-id、源码/配置/镜像/契约hash、资源清单、状态和未运行项；不含Secret、Prompt、文档原文和通知凭据 | P0 |
| OBS5-018 | 采集端和存储故障时必须有界降级，并能恢复采集；监控不得自动操作业务状态 | 分别中断Alloy/Loki/Tempo并恢复，观察失败/拒绝/丢弃、重试与恢复结果；受控应用仍按原语义完成，不伪称零丢失 | P0 |
| OBS5-019 | 必须验证遥测保留策略的实际过期删除，并交付同版本升级和回退操作说明 | 通过足够观察时间或符合固定版本时间约束的隔离旧时间夹具证明log/trace过期；未实际验证则not_run。升级前备份，失败后原版本加一致备份恢复到空环境 | P1 |

## 6. 非功能需求清单

| ID | 非功能需求 | 验收标准 | 优先级 |
| --- | --- | --- | --- |
| NFR5-001 安全 | Secret只通过受控secret文件/运行输入注入，日志、配置展开、报告和Grafana面板不得泄露 | 敏感哨兵扫描通过；Grafana仅回环访问；不开放2375、不默认privileged、不挂Windows整盘；Linux可选受限挂载与Docker socket高权限需明确记录 | P0 |
| NFR5-002 资源 | 五核心初始容器上限约6GiB/3.75核；五核心+sink上限6.125GiB，单验证工具运行时6.5GiB，Linux可选再加0.125GiB | 资源合计需实际检查，Docker总容量低于8GiB拒绝完整栈；建议Docker10～12GiB/宿主24GiB以上，应用另计。记录CPU/RSS/OOM/采样间隔，离散最大值不称连续峰值 | P1 |
| NFR5-003 存储 | 五卷规划合计约10GiB，Prometheus另设2GB block保留上限（不含head/WAL），保留期不是卷硬配额 | 70%提示、85%警告来自Status/Verify离线检查，不冒充连续Grafana磁盘告警；报告Docker文件系统余量，备份/镜像/应用数据另计，满盘须如实报写入失败 | P1 |
| NFR5-004 可恢复性 | 组件重启、监控Stop/Start、入口硬停和受控失败应能按账本恢复 | 不误删其它环境；旧锁、部分资源和失败备份均有明确处理；监控故障不改应用readiness、终态或租约 | P0 |
| NFR5-005 可观测性 | 监控自身抓取、写入、导出、拒绝、丢弃和数据源错误必须可见 | overview或Status区分up、NoData、Error、invalid和丢弃；缺指标不填常数0；停止Grafana/本机时不承诺自发通知 | P0 |
| NFR5-006 可测试性 | 配置测试、Compose smoke、真实接入、告警闭环、备份恢复和清理均有独立入口 | 状态为passed/failed/blocked/not_run并说明原因、缺陷/脚本/环境归类；受控应用业务确实执行、Mock不证明外部服务可用性，不读取docs/secret或默认付费请求 | P0 |
| NFR5-007 兼容性 | 固定版本配置分别适配Desktop及Linux可选profile，固定镜像兼容性必须实际核验 | Desktop为首要必验平台；Linux环境缺失可明确not_run但不能宣称跨平台通过。不自动升级/reset Docker或切换版本/profile | P1 |
| NFR5-008 网络边界 | 只有Prometheus/Alloy可加入已核验应用网络，其余组件留在监控网络 | external网络归应用且不能删除；主机、端口、project实际归属核验；shell覆盖关键值拒绝，不把:ro当Docker API安全隔离 | P0 |
| NFR5-009 配置一致性 | 数据源/仪表盘/告警UID及配置可从版本化文件重建，数据历史独立存卷 | UI探索不覆盖源码；撤销旧UID实际删除并验证。独立monitoring.env不扫描/改写根.env或docs/secret，Start/Validate不隐含Pull | P1 |
| NFR5-010 通知边界 | 本轮仅本地Webhook验证，无SMTP/公网Webhook入口 | Firing/Resolved、分组去重/重复可验证；默认零外部通知，sink保留量/时间上限有效 | P0 |
| NFR5-011 有界运行 | 命令、ready等待、验证、队列、导出重试和停机均有预算；长任务有中文进度 | 沿用ADR：常规Docker60秒、Pull20分钟、Start180秒、停机30秒、基础Verify300秒、完整3600秒/单告警1200秒；长操作每30秒进度。保留删除和备份另有显式截止，不把超时当成功 | P0 |

## 7. 验收标准与需求覆盖

实施完成后至少完成以下验收组；每组应关联独立run-id和脱敏证据：

| 验收组 | 覆盖需求 | 必须证明 |
| --- | --- | --- |
| A01 准入与配置 | OBS5-001、OBS5-002、OBS5-003、OBS5-004；NFR5-001、NFR5-007、NFR5-008、NFR5-011 | 坏契约、坏host、端口冲突、digest漂移、平台错误、shell覆盖和Secret泄露均被拒绝；不创建业务资源 |
| A02 基础组件 | OBS5-002、OBS5-003、OBS5-004、OBS5-005、OBS5-006、OBS5-007、OBS5-008；NFR5-002、NFR5-003、NFR5-008、NFR5-009 | 五组件ready、固定UID/权限、私网端口、卷和配置验证通过；合成三信号可查询并标记fixture |
| A03 真实指标 | OBS5-005、OBS5-009、OBS5-011；NFR5-005 | API/Worker真实metrics抓取、低基数、队列/readiness有效性和面板单位正确；缺失/过期不伪造健康 |
| A04 真实日志与追踪 | OBS5-006、OBS5-007、OBS5-009；NFR5-001、NFR5-005 | 获准stdout经Alloy入Loki，未获准容器不入库；安全非JSON负例处理可见；HTTP→Task→Worker及重试代际按004实际拓扑到达Tempo，trace_id双向跳转；不泄漏敏感内容 |
| A05 告警闭环 | OBS5-010、OBS5-011、OBS5-012；NFR5-010、NFR5-011 | 八类规则、idle、NoData和Error分别核验；sink收到Firing/Resolved；短测试缩短重复间隔后核去重/重复并恢复默认配置 |
| A06 生命周期与数据 | OBS5-013、OBS5-014、OBS5-015；NFR5-003、NFR5-004、NFR5-009、NFR5-011 | Stop后Start历史可查；启动失败/Ctrl+C/入口硬停与重入清理安全；Backup/Restore同版本可查三信号，半份/恶意归档/非空覆盖拒绝；Destroy仅清自有资源，前后保护清单/指纹证明应用与其它project不被删除 |
| A07 平台与资源 | OBS5-016、OBS5-017；NFR5-002、NFR5-006、NFR5-007 | Desktop排除Windows宿主指标；Linux profile边界明确；资源、丢弃、OOM、未运行项和清理结果完整入报告 |
| A08 故障降级与恢复 | OBS5-018；NFR5-004、NFR5-005、NFR5-011 | 分别断开Loki/Tempo/Alloy，观察有限缓冲/重试/拒绝与恢复；应用真实受控业务仍执行；磁盘满等故障有具体来源，不降低阈值或关闭必要信号冒充通过 |
| A09 保留与维护 | OBS5-019；NFR5-003、NFR5-006、NFR5-009 | 用足够时间或固定版本合法旧时间夹具验证log/trace实际删除；未测标not_run并阻止完整验收通过。升级/回退说明与同版本空环境恢复路径一致，未执行新版升级不写成通过 |

测试须使用本轮专用隔离应用实例和安全业务数据，不对日常开发环境做断连/故障/清理演练。模型和MinerU可用受控替身，但真实API请求、持久Task和Worker执行以及OTLP HTTP/protobuf到Tempo的路径必须实际发生；只发合成信号不能证明应用接入。无隔离应用则应用保护/接线项明确blocked或not_run，不能算完整通过。

默认Desktop完整验收要求全部必需项有实际passed结果；任何failed/blocked/not_run均需说明具体原因、影响及处理方向。原生Linux可选profile缺环境允许单列not_run，并将通过范围限定Desktop。保留期删除不能因等待长而隐式跳过；Linux选项之外的未测必需项不得转为通过。

| ADR-005既有验收 | 本PRD对应验收组 | 关系 |
| --- | --- | --- |
| V01～V02 | A01 | 准入/配置拒绝路径 |
| V03～V04 | A02 | 固定组件、配置与合成信号 |
| V05 | A03 | 真实应用指标 |
| V06～V08 | A04及A02 | stdout、真实trace与Grafana关联/UID |
| V09～V10 | A05 | 规则状态、通知及恢复 |
| V11 | A07 | 实测资源及证据 |
| V12 | A08 | 下游故障、丢弃和恢复 |
| V13 | A09 | 保留删除真实验证 |
| V14～V16 | A06及A09 | 保留/销毁、异常恢复、备份恢复与维护说明 |
| V17 | A07 | 平台边界 |

目标O5-G1由A01/A02验证，G2由A03/A04验证，G3由A02/A04/A05验证，G4由A07/A08/A09验证，G5由A06验证，G6由A01/A06/A08验证；功能与非功能编号在以上矩阵逐项可追溯。文档校审只证明设计及覆盖，不替代未来运行结果。

## 8. 实施路线与交付文件

实施按ADR-005的P0～P6推进：

1. **P0准入**：核对PRD-004交付指纹、API/Worker端点、指标/日志/OTLP契约、应用网络和部署许可；不满足则停止。
2. **P1工具与身份**：新增模块模板、镜像/依赖锁、主入口、Schema、预检、渲染和资源账本；先验证拒绝路径。
3. **P2基础组件**：新增Compose、Prometheus/Alloy/Loki/Tempo/Grafana配置和验证工具，完成ready与合成信号检查。
4. **P3展示**：新增Grafana provisioning、固定UID数据源、仪表盘、联系点和策略树，验证重建一致性。
5. **P4真实接线**：应用拥有者显式应用已批准的override；接入真实metrics、stdout和OTLP，监控入口不自动重建或停止应用。
6. **P5告警**：验证idle、NoData、Error、目标失联、队列/API/Task故障、Firing、Webhook和Resolved，恢复默认通知配置。
7. **P6交付**：完成Stop/Start、Destroy、硬停恢复、磁盘/导出故障、备份恢复、资源报告和整体校审。

预期新增文件集中于`docker/monitoring/`：`compose.yaml`、`application.override.yaml`、`README.md`、`.env.example`、`images.lock.json`、`requirements-host.lock`、`run-monitoring.ps1`、`integration/`契约、Prometheus/Alloy/Loki/Tempo配置、Grafana provisioning/面板、Linux profile、`helpers/`工具、`tools/`验证镜像、`validation/`测试、`runtime/`、`artifacts/`、`backups/`和`.cache/`。其中runtime、artifacts、backups和.cache必须Git/Docker构建上下文忽略；新增职责、运行方式和清理边界必须在模块README说明。

后续实施还须更新`.gitignore`/`.dockerignore`排除监控运行数据和备份，根README补使用导航，CONTEXT保持术语状态；仅向`docs/接口文档.md`补运行交付资源的必要链接，不复制第二套应用指标语义。业务代码和既往验收工程不属于修改范围，部署override仅覆盖已支持的观测环境变量、采集标签和有界日志轮转。

需求确认阶段只新增本PRD及导航，未部署监控。后续005模块、运行工具、独立场景验证及实际差异现已实施，见PR-005；不把该历史文档阶段的检查当运行结果。

## 9. 后续路线与整体审批口径

后续可独立考虑windows_exporter、真实Linux网络namespace采集、cAdvisor/数据库Exporter、多机/对象存储/高可用、持久发送队列、外部SMTP/企业Webhook、生产身份认证和外部可用性探测；这些能力不在本PRD默认实施范围内。

整体校审重点：应用能力已存在但默认未开启外发/采集；004能力导出与005实例描述分工；普通网络连接和Docker socket权限不被称为只读隔离；后台等待不算积压、未知快照不填0；数据保留不等于硬配额；Stop/Destroy不因应用离线失去清理能力；Validate不假定所有组件存在纯配置检查入口；长期删除验证不能被短smoke替代。

本PRD包含19项功能、11项非功能和A01～A09验收矩阵，并覆盖ADR-005的V01～V17。校审中修正了上述歧义和旧前置描述，保留固定工程版本与运行核验边界。需求确认时状态为“已确认，待实施”，当时仅做文档核验；现Desktop范围已完成独立实施/开发验证，具体命令、证据、清理和未测边界见PR-005。

本次文档核验：需求编号连续/唯一、30项需求均有验收映射、9组验收与ADR的17项对应完整；PRD、ADR、README和CONTEXT的本地链接、表格列数和代码块检查通过，`git diff --check`通过。代码只读核对了应用Compose、配置默认值、观测装配、能力导出、指标字典与PR-004边界；未修改用户已有任务说明或运行历史验收脚本。


### 9.1 实施状态更新（2026-11-16）

需求边界保持不变。Windows Docker Desktop已交付独立模块并完成真实应用三信号/代际、八类告警、异常通知、组件故障、保留物理删除、备份恢复、入口中断及清理验证；范围与结果以[PR-005](../pr/005-SesRAG-本地监控部署-PR.md)为准。Linux可选profile未运行，未来正式测试调研另行编制；本PRD不将旧版本测试或文档检查当本轮通过证明。
