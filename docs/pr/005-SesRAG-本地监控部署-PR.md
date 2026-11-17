# PR-005：SesRAG本地Grafana监控告警体系实施结果

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | PR-005／1.0 |
| 日期 | 2026-11-16（Asia/Shanghai；运行报告时间为UTC） |
| 对应需求／方案 | [PRD-005](../prd/005-SesRAG-本地Grafana监控告警体系-PRD.md)、[ADR-005](../adr/005-sesrag-local-observability-deployment-plan.md) |
| 项目基线 | `main`，HEAD `8876a66141a7e237fe45cc10b4b6f87178953e77`，产品包0.3.0；未提交或推送 |
| 实施范围 | 独立`docker/monitoring/`模块；Windows Docker Desktop为本轮实际验证平台，Linux可选profile单列未验证 |
| 结果定位 | 记录本轮工程交付、开发验证及差异；不替代后续实施结果调研或独立正式测试方案 |

## 1. 实际交付与边界

已落地Grafana＋Prometheus＋Loki＋Tempo＋Alloy独立Compose，附本地Webhook接收器、固定镜像/宿主依赖、部署绑定Schema、配置渲染、仪表盘/告警、生命周期与本轮验证工程。监控停止、销毁和恢复均独立于应用；应用PostgreSQL仍是业务事实来源。

没有修改`backend/`、`frontend/`、`contracts/`、`migrations/`、根应用Compose或业务环境模板，没有给业务API增加字段。未修改、依赖或运行前轮PRD正式验收目录。应用接线只通过独立override配置004已经提供的能力。

## 2. 文件与模块变动

| 文件／目录 | 变动与实际职责 |
| --- | --- |
| `docker/monitoring/compose.yaml` | 新增六服务、五named volumes、监控bridge、应用external网络、内存/CPU/日志轮转/权限和回环端口 |
| `application.override.yaml` | 新增显式应用接线：004指标/traces开关、精确OTLP host、采集opt-in和环境标签；监控入口不运行应用up/down |
| `images.lock.json`、`requirements-host.lock` | 新增linux/amd64镜像digest及hash锁定宿主依赖；工具镜像从锁定Python构建，运行账本锁ImageID |
| `.env.example`、`run-monitoring.ps1` | 新增输入说明与PowerShell7入口；仅使用模块venv和受控子进程环境，拒绝shell关键变量覆盖 |
| `integration/application-contract.schema.json`、样例、`export_binding.py` | 新增部署描述及只读导出：源码/ref/正式接口hash、真实容器/网络身份、端点、28类指标、日志/追踪模式；不取代004契约 |
| `integration/component-metrics.json` | 新增固定版本组件自指标初始化/条件产生语义，必需缺失纳入METRIC-MISSING |
| `helpers/preflight.py` | 新增Schema、镜像digest、版本/容量、实际源代码指纹、应用opt-in、指标、网络/别名归属、归档安全门禁 |
| `helpers/render.py` | 新增有限Prometheus/Alloy/Grafana规则渲染；全局快照唯一API来源，多Worker逐实例统计；无任意PromQL输入 |
| `helpers/lifecycle.py`、`cli.py` | 新增Prepare/Pull/Validate/Start/Status/Verify/Stop/Backup/Restore/Destroy，互斥、账本、进程树/CID回收、五卷一致备份与空环境恢复 |
| `helpers/verify.py` | 新增真实目标/数据源/面板/规则/关联模板/合成信号的基础检查；明确不把基础Verify算作完整验收 |
| `prometheus/`、`alloy/`、`loki/`、`tempo/` | 新增有限采集和存储配置；15s抓取、72h日志、24h追踪、7d/2GB指标blocks；日志positions持久，发送队列有界 |
| `grafana/grafana.ini`、`provisioning/`、四份dashboard JSON | 新增安全运行设置、三数据源固定UID、同一目录UID、三默认面板和八类告警、本地通知策略；Linux面板只在Linux profile加载 |
| `platform/compose.linux-host.yaml` | 新增可选Node Exporter，只启用CPU/内存/文件系统/负载等；Desktop拒绝选择，不宣称Windows物理宿主监控 |
| `tools/` | 新增标准库工具镜像、内网HTTP/OTLP JSON夹具、环形Webhook接收器、卷统计/安全归档、fixture指标服务 |
| `validation/` | 新增本轮专用配置/安全单测、隔离应用准备/清理、真实Task重试、告警、故障、保留删除、备份恢复、入口中断、配置撤销/空闲和失败回滚验证 |
| `README.md`、`runtime/`、`artifacts/`、`backups/`、`.cache/` | 新增模块使用/职责说明；运行数据、凭据、备份、工具缓存均Git及Docker构建忽略 |
| 根`.gitignore`／`.dockerignore` | 修改：排除上述005运行目录，防止Secret/备份进入Git或应用镜像上下文 |
| 根`README.md`、`CONTEXT.md`、PRD/ADR及调研文档 | 修改：同步005导航、术语/状态、实际工程差异和验证边界；保留原研究时点 |
| `docs/接口文档.md` | 仅补005运行交付链接；应用端点/业务响应/指标语义未变 |

更细的目录说明及全部命令见[模块README](../../docker/monitoring/README.md)。新增`application_fixture.py`等验证入口用于把本轮开发验证变为可复现操作，不是主入口自动管理日常应用。

## 3. 端点、网络及契约交付

| 消费／用途 | 地址和行为 |
| --- | --- |
| Grafana UI | 默认`http://127.0.0.1:3000`，本轮隔离验证用3005；`admin`密码来自私有secret文件，匿名关闭 |
| 应用指标 | 已有API `http://api:9101/metrics`、Worker `http://worker:9102/metrics`；Prometheus每15s主动抓取、timeout5s、honor_labels保留service/environment；应用指标真源仍在[正式接口§9](../接口文档.md#9-应用观测接口与交付契约004) |
| 应用OTLP | 显式override指向`http://sesrag-obs-<env>-alloy:4318/v1/traces`；精确host白名单，应用实际发送HTTP/protobuf；Alloy内部另提供4317gRPC，未给应用新增gRPC出口 |
| Prometheus／Loki／Tempo | 内网9090／3100／3200，不发布宿主；Grafana数据源UID `sesrag-prometheus`／`sesrag-loki`／`sesrag-tempo` |
| Alloy管理／本地通知 | 内网12345和`http://webhook-sink:8080/alerts`；sink只保留白名单最近100条/24h，内存状态，不新增卷或外部通知 |

独立project为`sesrag-observe-<env>`。仅Prometheus/Alloy加入经ID和labels核验的应用网络；其它组件只在监控网络。外部应用网络不由本模块创建或删除。Docker socket只限可信本机daemon；`:ro`不是Docker API权限隔离，Alloy为访问镜像数据目录增加了受限`DAC_OVERRIDE`，没有privileged或TCP2375。

新`ApplicationContract`采用schema_version=1，记录实际部署身份、唯一API统计来源、逐实例Worker targets、完整004字典、正式接口hash和traces/logs引用。004业务API/Event/Tool、Task传播与数据库Schema没有升级。应用错误、任务重试和租约不由监控写回。

## 4. 实际适配与校审修复

- 官方候选镜像版本均取得，按架构digest锁定；Node Exporter使用官方Docker Hub `prom/node-exporter:v1.12.1`同版本镜像，未在Desktop拉取/运行Linux profile。首次tag拉取部分遭遇镜像源referrers错误，按官方tag manifest确认的架构digest重试成功，没有降版本或使用latest。
- 应用镜像不含Git目录/宿主Dockerfile，不能直接调用004完整capability函数作为容器探针；005比较真实镜像内业务/契约/迁移/包文件指纹，并在宿主另核004来源与正式接口hash。
- Alloy1.21.3使用`stage.label_keep`，exporter timeout位于组件根部；原生检查器发现后修正。日志level有限化，非JSON原文替换成固定诊断。
- Grafana13首启可能按标题另建随机告警folder；现先建立固定dashboard目录UID，再加载rules。provisioning中的`$`须转义，实际API核验跳转模板未被环境展开为空；日志正则实际匹配真实trace_id。
- 校审修复了资源ID漂移阻断清理、孤立Secret被覆盖、无界进程等待、临时容器缺CID回收、公开stderr泄漏、卷根权限遗漏、实际容器未停写、多Worker旧窗口聚合、快照freshness不足等问题。另补恢复绑定校验：环境文件须与当前受控目录/固定镜像相等，生成配置须等于可信模板重渲染，不能只靠归档中可被同步改写的hash；归档展开预算按六份总量12GiB计算。回归包含真实恢复、硬杀/受控KeyboardInterrupt和低层安全测试。
- 组件必需零序列登记并核验；按up和initialized/valid/last_success分离失联/缺失/未知与业务失败。正常空闲不是NoData，未知也不填假0。

## 5. 验证与证据

平台为Windows Docker Desktop Linux容器：Engine29.9.2、Compose5.6.1、20CPU、Docker可见内存12,396,097,536 bytes（约11.5GiB），PowerShell7.6.9、宿主Python3.11.6。真实应用使用独立`sesrag-obs005-app`、Mock Provider与专用PG/Redis，未请求付费模型/MinerU。

每条证据位于`docker/monitoring/artifacts/<run-id>/report.json`，Git忽略；报告保留配置/来源/镜像/契约hash和脱敏身份。历史失败试跑也保留，不将其与最新通过项混算。

| 验收组／主要内容 | 最新采用证据与结果 |
| --- | --- |
| A01 契约/安全/工具准入 | 配置及生命周期单测：17项通过；覆盖Schema、身份/host/path、指标字典、坏digest/latest、shell覆盖、归档路径/链接/展开预算、备份篡改、孤立Secret、Webhook100条/24h等；实际Prepare通过G1～G5；`20261116T135145-77ac46d9`实际坏源码/公网host/其它project网络/网络ID/错误平台拒绝，`20261116T135323-a7b7bbff`真实端口冲突拒绝且无残留 |
| A02 基础组件/三合成信号 | 六服务ready、7个Prometheus目标up；`20261116T140237-7ec0b9e5`固定镜像原生promtool/Loki/Alloy检查通过；`20261116T140628-b6593521`恢复后基础探测通过（Tempo纯静态解析及完整验收占位明确not_run，由各独立运行场景补齐） |
| A03 真实指标/空闲 | API/Worker实际metrics与源身份通过；`20261116T133940-a74c0eff`确认八类真实表达式非空且全0、规则inactive；数据源prune实际删除、规则目录UID一致 |
| A04 真实日志/追踪 | `20261116T135006-2ce93201`全新应用复跑：真实HTTP→producer→Task→两个兄弟consumer，generation1→2；Run成功，API/Worker同trace可查；正文哨兵无泄露；其它project/无opt-in日志不入库，非JSON原文屏蔽有诊断 |
| A05 八规则/通知 | `20261116T124725-ac89fd83`七应用规则Firing/Resolved；`20261116T131006-d5d1d54e`真实Loki中断触发PIPELINE及通知分组/去重/重复，恢复默认配置；`20261116T133955-53faf956`按特定rulename和独立时间边界归档NoData/Error的Firing/Resolved |
| A06 数据/恢复 | `20261116T140310-a46fe8f9`：恢复绑定安全加固后，重新验证Stop/Start历史可查、五卷一致备份、非空恢复拒绝、Destroy→空环境Restore→Start后历史/配置可查；应用及其它project清单/事实计数不变 |
| A06 入口中断 | `20261116T132413-ad2cf08f`：真实Start后硬杀主进程，重入清理自有资源；等待子进程时受控KeyboardInterrupt回收CLI/CID容器，五卷保留 |
| A07 平台/资源 | `resource-20261116T131053`：12次离散样本、约45.56s，六服务内存示例约614MiB（docker stats口径）；五核心上限6144MiB/3.75CPU，sink128MiB/.1CPU，端口和双网边界正确，无OOM；不是连续峰值或容量压测 |
| A08 断开/满盘 | `20261116T132648-b00cb3be`：分别中断Loki/Tempo/Alloy，实际错误counter增加，业务Run仍成功且恢复后新Run成功；`20261116T133359-3844bf9c`：64KiB隔离tmpfs真实ENOSPC，不填宿主盘，清理通过 |
| A09 保留删除 | `20261116T133017-af18ae20`：73h日志chunk/25htrace block先持久化并可查，再以默认72h/24h阈值物理删除；仅维护周期加速，文件前后清单入报告，演练资源清理通过 |

告警fixture使用单独fixture005身份，pending/评估加速并将重复窗口缩短为30s；5m/10m统计窗口保留并等到自然恢复，结束恢复默认pending与30s/1m/4h通知策略。合成信号不计真实业务通过，实际错误counter/业务结果与合成规则证据分开。

主要命令：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 -m unittest discover -s docker/monitoring/validation -p "test_*.py"
& .venv/Scripts/ruff.exe check docker/monitoring
& .venv/Scripts/ruff.exe format --check docker/monitoring
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Validate -EnvironmentId verify005
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Verify -EnvironmentId verify005
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py business
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py alerts
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py alerts-extra
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/lifecycle_validation.py
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/recovery_validation.py
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/fault_validation.py
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/retention_validation.py --tool-image <本轮工具ImageID> --timeout 1200
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/disk_validation.py
```

真实/故障验证只能对005专用隔离实例执行；普通使用者按模块README从已运行的应用接线，不对日常应用执行这些故障脚本。Validate中Tempo没有纯解析器的项仍记not_run，其同版本实际ready/写入/查询/删除已在运行验证覆盖，不伪造“配置静态解析通过”。

## 6. 限制和维护

原生Linux/Node Exporter未运行，不宣称该平台通过；Linux文件Secret的宿主UID/组读取权限需另外核准。未实施Windows exporter、外部通知、高可用、生产SLO、tail sampling、持久发送队列或真实模型效果测试。没有升级到另一个监控版本，不将同版本恢复称为跨版本升级成功。

五卷预算10GiB、70/85%提示来自Status/Verify，保留期不是磁盘硬配额；Docker镜像/缓存、备份和应用数据另计。离散资源样本不等于连续峰值，未做生产容量保证。监控与电脑同机停止时不能自发可靠通知。

备份按backup-id保留，包含Secret，仅在受限`backups/verify005/`保存，Git/Docker构建忽略。镜像、工具缓存、脱敏证据和显式备份按方案保留；不全机prune、不压缩VHDX。新版本更新/回退、密码与数据维护步骤见模块README。

本轮未运行前轮正式验收、前端构建/类型检查或全仓库业务回归；没有相应业务改动，不把这些未运行检查写成通过。最终失败启动与全新环境复跑及清理已完成，见下节。


## 7. 最终校审与收尾

整体校审分别核对仓库规范及PRD/ADR覆盖，修复发现后完成相关回归。`20261116T134430-cc0c2ffd`证明：既有健康环境遭就绪探测失败时容器ID不变；从Stop状态新建资源失败时仅回收本轮容器/网络，原五卷ID保留，随后Start成功。

新交付的`validation/application_fixture.py`从空白专用project完成Start/来源绑定，证据`20261116T134900-5db3c6d8`；之后Prepare/Pull/Validate/Start分别为`134922-74859f92`、`134927-f1843540`、`134933-95fed21c`、`134938-f2adcdd0`（日期前缀均为20261116T）。全新业务/代际复跑`20261116T135006-2ce93201`通过，基础Verify `20261116T135036-28675f4a`通过其范围内全部实际检查，明确完整验收另据各独立场景，不改写占位项为假通过。

恢复绑定安全加固后再次从空环境准备应用，`20261116T140158-7542abd3`通过；Prepare/Pull/Validate/Start依次为`20261116T140227-ead69c7a`、`20261116T140232-6a93dbbd`、`20261116T140237-7ec0b9e5`、`20261116T140243-63f73325`。真实备份恢复`20261116T140310-a46fe8f9`与恢复后基础Verify `20261116T140628-b6593521`通过各自实际运行检查；Validate和Verify保留其未运行项及partial状态，未覆盖为整体验收通过。

最终监控Destroy `20261116T140650-37441dcc`、带本轮标记的应用夹具Stop `20261116T140724-da8a8fe6`均通过；端口拒绝证据仍为`20261116T135323-a7b7bbff`。最终汇总为`docker/monitoring/artifacts/delivery-20261116T140749/report.json`：A01～A09有上述对应证据并记录最终源码指纹；verify005、retention005、disk005及sesrag-obs005-app的容器/卷/网络均为空，三个监控runtime目录不存在。原有六个历史停止容器保持原状态，未清理其数据。原`delivery-20261116T135450`保留为加固前历史快照。

最终`ruff check`、`ruff format --check`、17项独立单元测试、Compose配置检查与`git diff --check`通过。交付文件链接/编号/状态另做机械核对。镜像/缓存、脱敏报告和私有显式备份按方案保留；不把这些保留项视为容器残留，也不声称VHDX已收缩。

结论：005独立监控模块已完成本轮Windows Docker Desktop实施与整体校审，关键运行闭环有真实证据；Linux可选profile不计通过。后续实施结果调研/正式验收可基于本模块和证据继续组织，无需借用前轮测试文件。
