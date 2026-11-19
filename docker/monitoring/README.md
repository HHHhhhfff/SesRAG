# SesRAG 本地监控模块（005）

独立Compose：Grafana、Prometheus、Loki、Tempo、Alloy及本地Webhook接收器。首次部署请按[配置、部署与启动指南](../../docs/runbooks/local-grafana-monitoring-setup.md)操作；本页记录详细文件职责、数据口径、生命周期和故障处理。应用指标/日志/trace真源见[接口文档](../../docs/接口文档.md#9-应用观测接口与交付契约004)，产品边界见[PRD-005](../../docs/prd/005-SesRAG-本地Grafana监控告警体系-PRD.md)，设计见[ADR-005](../../docs/adr/005-sesrag-local-observability-deployment-plan.md)，实际结果见[PR-005](../../docs/pr/005-SesRAG-本地监控部署-PR.md)。运行检查的通过范围以结果文档为准。

## 前提与安全边界

- Windows PowerShell7.4+、Python3.11+、Docker Engine26+/Compose2.27+，Linux容器；Docker可用内存至少8GiB，推荐10～12GiB，模块所在盘至少12GiB空闲，Docker数据盘、镜像/备份/应用另计。
- 用户先运行专用开发应用，明确部署下面的观测override，再导出实际部署描述。主入口不会自动启动、停止或重建应用，不读取根`.env`或`docs/secret`。
- 全局队列/readiness快照只用一个API统计来源；Worker支持多个唯一网络别名，不能用负载均衡别名代替逐实例目标。
- Grafana只绑定`127.0.0.1:3000`，可通过入口改回环端口；其它服务默认不发布宿主端口。`-HostOtlp`仅额外发布`127.0.0.1:4318`，不发布4317。
- Alloy读取Docker Unix socket，`:ro`不限制Docker API权限；配置和daemon必须可信。该镜像目录需要`DAC_OVERRIDE`，仍不privileged、不开放2375、不挂Windows整盘。卷工具仅挂已核验监控卷，按需root+CHOWN/DAC_OVERRIDE/FOWNER，无socket。
- 默认无SMTP/公网Webhook、Windows exporter、数据库exporter、metrics-generator、tail sampling或业务代码修改。停止监控时应用可能有有界导出失败，不改变业务事实。
- 本地明文Secret只保存在ACL受限runtime/备份。Linux可选profile尚须独立平台验证；Linux宿主创建0600 Secret后需显式使Grafana UID472可受限读取（例如专用组0440），不能全局可读，未完成该平台准入不得宣称Linux通过。

## 文件职责

| 文件/目录 | 用途 |
| --- | --- |
| `compose.yaml` | 独立project六服务、五named volumes、资源上限、回环端口与双网边界 |
| `application.override.yaml` | 应用拥有者显式启用004已有观测开关、精确OTLP白名单和日志opt-in；不新增SDK |
| `.env.example` | 输入说明；不是自动读取配置，所有派生值由Prepare/Pull写入专属monitoring.env |
| `images.lock.json` | 官方registry核实的linux/amd64 digest，版本不使用latest；工具镜像本地构建后锁Image ID |
| `requirements-host.lock` | 模块专属venv依赖和完整hash；不修改业务依赖 |
| `run-monitoring.ps1` | Windows主入口；Linux直接同一Python CLI |
| `integration/` | 实例描述Schema/无Secret样例、只读绑定导出、固定版本组件指标初始化登记 |
| `helpers/preflight.py` | Schema/源码指纹/实际容器网络/指标/受控环境/归档安全校验 |
| `helpers/render.py` | 有限Prometheus/告警/Alloy模板生成，不接受任意PromQL注入 |
| `helpers/lifecycle.py` | 有界子进程、环境互斥、持久资源账本、生命周期、备份恢复与清理 |
| `helpers/verify.py`、`cli.py` | 基础真实查询与动作分派，报告不把未运行验收算通过 |
| `prometheus/`、`alloy/`、`loki/`、`tempo/` | 抓取/日志/OTLP有限处理、固定版本本地存储及保留配置 |
| `grafana/` | 固定UID三数据源/目录/仪表盘/八类规则/本地联系点和通知树 |
| `platform/` | 原生Linux受限Node Exporter配置；Desktop拒绝加载 |
| `tools/` | 标准库工具镜像、HTTP/OTLP JSON夹具、本地告警环形缓存、卷归档检查器、合成告警服务 |
| `validation/` | 本轮离线配置/生命周期测试、专用隔离应用override、一次受控Worker失败、真实业务/告警/保留验证；不依赖旧验收工程 |
| `runtime/<env>/` | 受限输入/Secret/生成配置/账本；Stop保留，Destroy删除该环境 |
| `artifacts/<run-id>/` | 不覆盖的脱敏报告；每动作独立ID，包含hash、资源清单、结果与限制 |
| `backups/<env>/<backup-id>/` | 私有一致备份，含Secret，Destroy保留；自行按保留计划清理 |
| `.cache/` | 专用venv、受限验证输入和缓存，Git/Docker构建忽略；不自动清理共享镜像/BuildKit |

## 首次准备与显式应用接线

在仓库根目录执行：

```powershell
python -m venv docker/monitoring/.cache/venv
& docker/monitoring/.cache/venv/Scripts/python.exe -m pip install --require-hashes -r docker/monitoring/requirements-host.lock
```

应用拥有者先在自己的受限env-file中补`OBS_ENVIRONMENT_ID=local`，确认应用project与真实网络。不要把业务凭据复制到monitoring.env。显式审核合并配置并部署**已有**应用（示例中的应用env-file由拥有者提供，不属于本模块生成）：

```powershell
docker compose --env-file <应用私有env-file> -p <应用project> -f docker-compose.yml -f docker/monitoring/application.override.yaml config --quiet
docker compose --env-file <应用私有env-file> -p <应用project> -f docker-compose.yml -f docker/monitoring/application.override.yaml up -d --no-deps api worker
```

路径以第一个Compose文件为基准。变更仅为已有OBS开关和opt-in标签；应用原先traces/日志采集默认关闭。监控入口不执行上面应用命令。多Worker先为每个实例配置唯一网络别名。

导出并实际核验G1～G5：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/integration/export_binding.py --environment local --project <应用project> --network <应用真实网络> --output docker/monitoring/.cache/application-contract.json
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Prepare -EnvironmentId local -ApplicationContract docker/monitoring/.cache/application-contract.json
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Pull -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Validate -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Start -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Verify -EnvironmentId local
```

Linux使用`.cache/venv/bin/python helpers/cli.py <Action> --environment local ...`；权限和可选profile另验。默认project `sesrag-observe-local`，Alloy应用网络别名`sesrag-obs-local-alloy`。仅Prometheus和Alloy加入真实应用external网络。Schema样例的零hash不能用于真实接线，正式输入应由导出工具产生。

Grafana用户名`admin`，首次密码在`runtime/local/secrets/grafana-password`，用户本地打开查看即可，勿复制进工单/截图/报告。已有Grafana卷不会因重写密码文件而重置数据库密码，Prepare不覆盖Secret。父shell中若存在`OBS_*`、`GF_*`、`IMAGE_*`入口明确拒绝，避免Compose环境优先级污染；退出当前临时shell或清除相应变量后重试。

## 生命周期

已运行应用需要统一编排时，可使用[应用所有者入口](../../scripts/README.md)；监控独立入口仍不操作应用。应用代码更新并已重新部署后，可显式`-Action RefreshBinding -ApplicationContract <新导出描述>`刷新同一project/network ID/targets/信号语义的来源指纹；该动作拒绝换采集目标、模板漂移或镜像变更，不替代配置升级与备份。

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Status -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Stop -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Start -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Backup -EnvironmentId local
# 明确丢弃此监控环境数据；应用/其它环境/共享镜像/报告/备份均保留。
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Destroy -EnvironmentId local -EraseMonitoringData
# 空目标同版本恢复：backup-id从Backup脱敏报告读取，恢复完再显式Start/Verify。
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Restore -EnvironmentId local -BackupId <backup-id>
```

Stop删除监控容器/网络而保留五卷、Secret和配置。Destroy还删除五卷及该环境runtime，按project+module+environment+随机owner核验，不因应用离线或接入漂移阻断清理。账本记录资源ID/daemon身份，入口硬停后按标签补账。异常Start只清理本次新增容器/网络，不删除已有卷或原有健康环境。备份根据实际运行状态停写，备份五卷与私有配置/Secret/hash manifest，再恢复运行；恢复只允许空环境及相同镜像锁，拒绝半份/篡改/绝对路径/链接/越界/总计超12GiB展开。恢复还会将环境绑定与当前路径/固定镜像重新比较、按可信模板重渲染核对完整配置集合；自行改写归档及hash仍不能改向其它宿主路径或外部采集目的端。

常规子进程60秒、Pull单镜像20分钟、Start整体180秒、停机30秒宽限、Verify基础300秒；每30秒输出进度。Start/Validate不隐式Pull。独立告警长验证按统计窗口有更长显式预算。长保留/备份另设预算，超时必须失败或not_run。Docker内部空间释放不保证Windows VHDX立即缩小，不执行prune/reset/压缩磁盘。

## 数据与诊断口径

Prometheus15秒抓取/5秒超时；应用honor_labels，原环境/service不被改写。全局快照只来自API；queued只含到时有效待领，外部等待/退避另列，未知/过期不能补0。28类应用指标仍以004机器字典为真源。组件自指标必须登记初始化；其必需缺失由METRIC-MISSING发现。

Loki72h，Tempo24h，Prometheus7d/2GB blocks；五卷规划10GiB，70%提示/85%警告由Status/Verify报告，不是硬配额或连续Windows磁盘告警。Alloy positions持久，日志buffer/OTLP queue内存有界，断开/崩溃/轮转可丢失，不承诺零丢失。日志仅获准应用project+环境+opt-in的API/Worker，非JSON替换为固定诊断，level限制INFO/WARNING/ERROR；trace_id留JSON字段。追踪仅OTLP traces，安全属性白名单保留004关联，不向第三方转发。

三个数据源UID `sesrag-prometheus`/`sesrag-loki`/`sesrag-tempo`；目录`sesrag-observe`，面板overview/application/pipeline，Linux另加linux-host。Loki日志使用`| json`提取trace_id；Tempo按同一trace查询，跳转时间扩大±5分钟。缺span要区分源端采样、未产生、传输、查询窗口和过期。

八类Grafana规则：TARGET-DOWN、METRIC-MISSING、OBSERVATION-INVALID、WORKER-NOT-READY、QUEUE-WAIT、API-ERROR、TASK-FAILURES、PIPELINE-ERROR。默认NoData/Error独立通知，非健康0。联系点仅本地sink，30s分组等待/1m间隔/4h重复，Firing及Resolved都发送。sink只留最近100条且最多24h，字段白名单，容器重建清空，无第六卷。Grafana/电脑自身停机时无法自发可靠宕机告警。

## 独立验证与故障处理

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 -m unittest discover -s docker/monitoring/validation -p "test_*.py"
```

`Verify`仅基础探测，完整通过必须结合本轮`validation/`真实业务代际、八类告警、NoData/Error、故障/资源、备份恢复、保留物理删除、清理证据。合成环境为fixture005，不计真实应用通过。005真实验证只允许`verify005`及`sesrag-obs005-app`专用实例/回环18005；`worker_fault_entry.py`只在测试挂载，首次模型调用抛一次受控异常，不修改业务源码或访问付费服务。

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py business
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py alerts
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/live_validation.py alerts-extra
```

完整可复现的本轮专用环境准备与清理（会创建/构建专用应用，不属于监控日常主入口）：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/application_fixture.py Start
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Prepare -EnvironmentId verify005 -ApplicationContract docker/monitoring/.cache/application/contract.json -GrafanaPort 3005
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Pull -EnvironmentId verify005
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Validate -EnvironmentId verify005
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Start -EnvironmentId verify005
# 运行所需validation场景；首次business会消费一次故障夹具，重跑先重启该专用Worker。
# 清理先监控，再应用；应用夹具只接受本轮测试标记，拒绝同名外来资源。
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Destroy -EnvironmentId verify005 -EraseMonitoringData
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/validation/application_fixture.py Stop
```

`application_fixture.py`先要求Docker本机已有应用基线PG/Redis镜像，按根应用Dockerfile显式构建；如镜像缺失，先按应用部署规范准备，不把应用构建归入监控Start隐式下载。`lifecycle_validation.py`检查历史/备份恢复及受保护资源；`recovery_validation.py`检查主进程硬杀与受控KeyboardInterrupt；`start_failure_validation.py`注入就绪失败验证回收范围；`fault_validation.py`验证三组件故障下业务继续；`diagnostic_validation.py`按特定rulename捕获NoData/Error恢复；`provisioning_validation.py`检查UID撤销与正式idle；`disk_validation.py`只填64KiB隔离tmpfs，不填宿主盘。

`alerts`使用fixture指标，保留5m/10m统计窗口但pending10s/评估10s/重复30s；finally恢复默认，配置差异入报告。硬杀时`runtime/verify005/validation-recovery/`保留原文件，必须先还原三份配置并reload，不能继续日常接线或把漂移Status当正常。`retention_validation.py --tool-image <本轮工具ImageID> --timeout 1200`在独立retention005环境用73h日志/25htrace验证旧文件实际消失，72h/24h阈值不变，维护周期加速；结束清本次资源。该演练期间应Stop默认监控，避免超出资源/单工具预算。

常见诊断：源码/字典漂移重新导出并审核目标部署；端口冲突只改本模块端口；坏配置先Validate；镜像缺失显式Pull；owner不符拒绝接管；孤立Secret/账本禁止重写，先恢复完整备份。存储满先Status/备份并按明确Destroy处理，不自动删业务数据。公开报告只留稳定错误码，原始解析器输出需在本机受控环境定位，勿把Secret/宿主路径贴入报告。

## 更新与回退

先Stop/Backup并保留原`images.lock.json`、源码配置和受限Secret；审核官方release、安全公告/Schema兼容，再修改digest和模板，在空隔离环境跑Validate、三信号、告警与恢复验证。已有环境拒绝配置/hash漂移，不支持直接热改绕过。升级失败使用原源码/镜像锁及一致备份恢复到空环境；不承诺旧二进制直接读新版数据库。撤销datasource使用provisioning prune；告警使用显式deleteRules并核数据库UID实际消失。版本化面板`allowUiUpdates=false`，探索另存临时副本，审核导出后纳入源码。
