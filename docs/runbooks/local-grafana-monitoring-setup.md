# 本地 Grafana 监控模块配置、部署与启动

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | RUNBOOK-005／1.0 |
| 日期 | 2026-11-17（Asia/Shanghai） |
| 状态 | 已实施；Windows Docker Desktop平台及隔离环境部署流程已验证 |
| 适用范围 | 仓库内独立 `docker/monitoring/` 模块；Docker Desktop Linux 容器 |
| 依据 | [PRD-005](../prd/005-SesRAG-本地Grafana监控告警体系-PRD.md)、[ADR-005](../adr/005-sesrag-local-observability-deployment-plan.md)、[PR-005实施结果](../pr/005-SesRAG-本地监控部署-PR.md) |
| 详细操作参考 | [监控模块 README](../../docker/monitoring/README.md) |

## 1. 部署结构与边界

需要同时启动应用与监控时，优先使用已交付的[统一部署脚本](../../scripts/README.md)：在仓库根目录运行`pwsh -NoProfile -File scripts/sesrag.ps1 Start`即可准备本机真实配置并部署持久`live`实例。本文后续保留独立模块的手工接线流程，适用于由其他入口管理的应用；不要将手工`local`环境与脚本的`live`环境混用。

监控栈由独立 Compose project 管理，包含 Grafana、Prometheus、Loki、Tempo、Alloy 和仅用于本地告警的 webhook-sink。Prometheus 与 Alloy 额外加入已核验的应用网络，用于抓取 API/Worker 指标及接收应用日志和追踪；其他监控组件只加入监控网络。应用服务仍由应用自身的 Compose project 管理。

本文主流程面向 Windows PowerShell 7.4+ 与 Docker Desktop Linux Engine。原生 Linux 配置虽已交付，但本轮未实测，不能按本文将其视为已验收平台。资源建议至少为 Docker 可用内存 8 GiB（推荐 10～12 GiB）及模块所在盘 12 GiB 可用空间；镜像、Docker 数据盘、应用数据和显式备份另计。

PR-005 的独立验证使用 `verify005` 环境、回环端口 `3005` 和专用隔离应用；它证明平台和同一部署流程，不表示当前机器的 `local` 环境已经启动。

操作约束：

- 所有命令从仓库根目录 `D:\Agentic_RAG\SesRAG` 执行。
- `docker/monitoring/.env.example` 仅供查看，不会被入口自动读取。环境、项目、镜像等有效配置由入口校验并写入对应 `runtime/<环境>/`。
- 应用凭据继续留在应用自己的受限 env-file；不要复制到监控配置或命令行。监控 Secret 位于受限 runtime 文件中，不要粘贴到工单、截图或报告。
- 监控入口不会启动、停止或重建应用。应用配置变更须由应用所有者审核并显式部署。
- 首次启动 Grafana 默认只绑定 `127.0.0.1:3000`；Prometheus、Loki、Tempo、Alloy 和通知接收器不发布宿主端口。`-HostOtlp` 是可选配置，仅绑定回环地址 `4318`。
- 默认联系点只发往本地 webhook-sink；没有 SMTP 或外部 Webhook 通知。

## 2. 前置检查与工具准备

打开 PowerShell，进入仓库根目录并检查工具与 Docker Engine：

```powershell
Set-Location D:\Agentic_RAG\SesRAG
pwsh --version
python --version
docker version
docker compose version
```

要求 PowerShell 7.4+、Python 3.11+、Docker Engine 26+、Compose 2.27+。`docker version` 必须能成功读取 Server 信息。准备模块专用 Python 虚拟环境并安装 hash 锁定依赖；不修改系统 Python、项目 `.venv` 或业务依赖：

```powershell
python -m venv docker/monitoring/.cache/venv
& docker/monitoring/.cache/venv/Scripts/python.exe -m pip install --require-hashes -r docker/monitoring/requirements-host.lock
if ($LASTEXITCODE -ne 0) { throw '监控模块依赖安装失败，停止部署' }
```

如果专用虚拟环境已经存在，不需要重复创建；依赖锁变更后再按上面的命令更新。

## 3. 显式接入正在运行的应用

确认应用 Compose project 中 PostgreSQL、Redis、API、Worker 等依赖已正常运行，且应用私有 env-file 使用的是该数据库当前有效凭据。以下变量请按实际应用替换：

```powershell
$appEnvFile = (Resolve-Path -LiteralPath '<应用私有env-file>').Path
$appProject = '<应用Compose项目名>'
$appNetwork = '<该应用project拥有的Docker网络名>'
```

在应用 env-file 中设置 `OBS_ENVIRONMENT_ID=local`，并确认该值与本监控环境一致。先查看并审核合并配置；`config --quiet` 不输出展开后的凭据：

```powershell
docker compose --env-file $appEnvFile -p $appProject -f docker-compose.yml -f docker/monitoring/application.override.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw '应用与观测配置合并校验失败；不要继续' }
```

`application.override.yaml` 会启用已有的 API/Worker metrics 和 traces，将 OTLP traces 指向当前环境的 Alloy，并为 API/Worker 设置日志采集 opt-in。应用本来运行但尚未应用该配置时，由应用拥有者执行：

```powershell
docker compose --env-file $appEnvFile -p $appProject -f docker-compose.yml -f docker/monitoring/application.override.yaml up -d --no-deps api worker
if ($LASTEXITCODE -ne 0) { throw '应用观测配置部署失败；先检查应用容器状态和日志' }
```

确认容器已按新配置重建并健康。监控接入工具不会猜测网络归属；用 Docker 实际资源标签和网络信息确定 `$appNetwork`。若有多个 Worker，须为每个 Worker 配置唯一网络别名，并在导出参数中逐个列出，不能用会负载均衡到多个实例的同一服务别名代替。

从实际运行的应用容器与网络导出部署绑定描述。默认单 API/单 Worker 使用 `api` 与 `worker` 网络别名：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/integration/export_binding.py --environment local --project $appProject --network $appNetwork --output docker/monitoring/.cache/application-contract.json
if ($LASTEXITCODE -ne 0) { throw '应用绑定导出或准入检查失败；不要启动监控栈' }
```

多 Worker 示例：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 docker/monitoring/integration/export_binding.py --environment local --project $appProject --network $appNetwork --worker-hosts worker-1,worker-2 --output docker/monitoring/.cache/application-contract.json
if ($LASTEXITCODE -ne 0) { throw '应用绑定导出或准入检查失败；不要启动监控栈' }
```

导出过程是只读准入核验，不包含 Secret，也不会启动或重建应用。若契约、源码版本、容器标签、网络身份或指标绑定不符合要求，入口应拒绝继续；先按报错修正真实部署或重新导出，不要手工改造导出的 hash。

## 4. 准备并启动监控栈

选定与应用一致的环境 ID。首次使用 `local`；Grafana 默认端口为 `3000`。依次运行 Prepare、Pull、Validate、Start，每一步失败都应停止，不要越过失败继续：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Prepare -EnvironmentId local -ApplicationContract docker/monitoring/.cache/application-contract.json
if ($LASTEXITCODE -ne 0) { throw 'Prepare 失败；查看本机脱敏报告后处理' }

pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Pull -EnvironmentId local
if ($LASTEXITCODE -ne 0) { throw 'Pull 失败；检查 Docker 网络和锁定镜像来源' }

pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Validate -EnvironmentId local
if ($LASTEXITCODE -ne 0) { throw 'Validate 失败；修复配置后重新校验' }

pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Start -EnvironmentId local
if ($LASTEXITCODE -ne 0) { throw 'Start 失败；检查本次脱敏报告和资源状态' }
```

Grafana 端口冲突时，在首次 Prepare 前选择空闲的本机端口；例如首次 Prepare 使用 `-GrafanaPort 3005`，访问地址相应改为 `http://127.0.0.1:3005`，之后各动作继续使用该环境配置。已有环境的端口属于已准备配置，不能直接重跑 Prepare 覆盖；按模块 README 的备份、配置更新和回归流程处理。Start 不会隐式 Pull 镜像。父 PowerShell 若设置了 `OBS_*`、`GF_*` 或 `IMAGE_*` 变量，入口会拒绝运行；清理冲突变量或在干净的 PowerShell 窗口重试。

## 5. 登录并验证数据

查看实际运行状态，再执行基础 Verify：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Status -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Verify -EnvironmentId local
```

打开 [Grafana](http://127.0.0.1:3000)，用户名为 `admin`。首次密码在 `docker/monitoring/runtime/local/secrets/grafana-password`；仅在本机受限终端中查看：

```powershell
Get-Content -LiteralPath docker/monitoring/runtime/local/secrets/grafana-password
```

不要将密码保存到脚本、共享终端记录、截图或报告。若该环境已初始化过 Grafana 数据卷，Prepare 不会覆盖 Secret 文件，重写首次密码文件也不会重置 Grafana 数据库中已有的密码。

基础 Verify 检查组件、数据源、面板、目标和合成信号等基础状态；它本身不等于 PR-005 的完整验收。新部署应重点确认：

- Grafana 的 overview、application、pipeline 仪表盘可打开；数据源 UID 为 `sesrag-prometheus`、`sesrag-loki`、`sesrag-tempo`。
- Prometheus 中 API/Worker 目标为 UP，真实指标带有预期 service/environment 身份。
- Loki 可查到被 opt-in 的 API/Worker 日志；其他 Compose project 或未 opt-in 服务不应被采集。
- 有请求产生追踪后，可在 Tempo 查询 trace，并从 pipeline 仪表盘按 trace ID 关联 Loki 日志。
- 告警健康状态需结合实际规则及通知场景验证。PR-005 的完整运行验证由独立场景组成，具体证据和通过范围见[实施结果](../pr/005-SesRAG-本地监控部署-PR.md)。

应用日志采集和追踪导出失败仅产生有界观测降级，不应改变业务 Run/Task 结果；但停止监控期间应用可能记录导出失败。若暂时不需要观测，应按模块 README 的应用拥有者流程撤销 override 后重建 API/Worker。

## 6. 日常停止、重启与销毁

短暂停止监控并保留历史数据、配置和 Secret：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Stop -EnvironmentId local
```

重新启动已有监控环境：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Start -EnvironmentId local
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Verify -EnvironmentId local
```

需要一致备份时先运行 Backup，并在受限位置保护备份：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Backup -EnvironmentId local
```

确认不再需要该环境及其监控历史后，才执行销毁。执行前再次核对环境 ID；此操作会删除该监控环境的容器、五个监控数据卷、网络及 runtime 配置/Secret，但保留应用数据库、上传文件、索引、应用网络、共享镜像、验证报告和显式备份：

```powershell
pwsh -NoProfile -File docker/monitoring/run-monitoring.ps1 -Action Destroy -EnvironmentId local -EraseMonitoringData
```

销毁不会删除应用服务，也不会删除外部应用网络。Docker 内部数据被删除不代表 Windows Docker Desktop 的 VHDX 文件会立即缩小；本模块不会执行全局 `docker prune`、Desktop reset 或磁盘压缩。恢复备份只允许相同镜像锁的空目标环境，完整流程见[模块 README](../../docker/monitoring/README.md#生命周期)。

## 7. 常见问题

| 现象 | 处理方向 |
| --- | --- |
| Docker daemon 不可用 | 启动 Docker Desktop，确认 Linux Engine 正常后重试 `docker version`。 |
| 合并配置或导出被拒绝 | 核对应用 env-file 中的 `OBS_ENVIRONMENT_ID`、project/network 所属标签、唯一 Worker 别名、应用是否已使用 override，以及当前代码和指标契约是否匹配。 |
| Grafana 端口占用 | 选定回环空闲端口，并在 Prepare 和后续动作中保持该端口；不要停止或占用其他应用。 |
| 镜像缺失 | 单独运行 Pull 并检查其报告；Start 不下载镜像。 |
| 配置校验失败 | 先查看模块生成的脱敏 `artifacts/<run-id>/report.json` 和稳定错误码；不要把 Secret 或完整 inspect/env 输出贴到工单。 |
| 同环境配置或代码已漂移 | 不手改 runtime 生成文件；按模块 README 的备份、更新和回退流程处理。 |
| Linux 主机指标或 Secret 权限不工作 | Linux 可选 profile 未在本轮验收，先按 ADR-005 和模块 README 完成该平台权限核验，不要将 Desktop 结果外推。 |

组件版本、资源限制、告警规则、数据保留、恢复限制和完整验证命令以[监控模块 README](../../docker/monitoring/README.md)及[PR-005实施结果](../pr/005-SesRAG-本地监控部署-PR.md)为准；本指南只提供日常配置、部署和启动顺序。
