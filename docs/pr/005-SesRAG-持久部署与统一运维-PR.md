# PR-005补充：真实持久部署与统一运维入口

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | PR-005-DEPLOY／1.0 |
| 日期 | 2026-11-17（America/New_York；机器证据使用UTC） |
| 依据 | [PRD-005](../prd/005-SesRAG-本地Grafana监控告警体系-PRD.md)、[ADR-005 §18](../adr/005-sesrag-local-observability-deployment-plan.md)、用户本轮持久真实部署与一键运维要求 |
| 基线 | `main`，HEAD `b7ffa610e1203820b6fd7e135aa0ea59f86354c5`，包0.3.0；未提交或推送 |
| 范围 | 本机持久真实配置、应用与独立监控接线、统一脚本及同一部署上的真实验证；不重建临时验收环境 |
| 使用入口 | [scripts说明](../../scripts/README.md)、[部署指南](../runbooks/local-grafana-monitoring-setup.md) |

## 1. 已部署结果

实际应用project为`sesrag-live`，监控project为`sesrag-observe-live`，环境身份`live`。PostgreSQL、Redis、API、Worker、前端以及Grafana、Prometheus、Loki、Tempo、Alloy和本地通知sink已启动。迁移容器正常完成退出，不作为常驻服务。验证结束保留这些服务继续运行。

| 用途 | 实际地址／位置 |
| --- | --- |
| 应用工作台 | [http://127.0.0.1:5173](http://127.0.0.1:5173) |
| API就绪 | [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready) |
| Grafana | [http://127.0.0.1:3000](http://127.0.0.1:3000)，用户`admin` |
| Grafana首次密码 | 本机受限`docker/monitoring/runtime/live/secrets/grafana-password`，本报告不保存明文 |
| 应用配置 | 根`.env`；四类服务独立凭据、数据库凭据、MinerU加密密钥，仅本机保存 |
| 监控环境配置 | `docker/monitoring/runtime/live/monitoring.env`及ledger/生成配置，不含业务Key |
| 应用数据 | `sesrag-live`的四个业务卷；既有`sesrag`数据库/上传卷不接管 |
| 监控历史 | `sesrag-observe-live`的五个数据卷；独立于业务数据 |

这里的“生产环境”是本机长期运行且真实调用外部模型的部署。当前产品仍使用固定owner和既有Vite前端，没有公网生产认证、TLS入口或高可用交付；所以公开端口均绑定127.0.0.1，不应直接发布到公网。

## 2. 配置与实际变更

| 文件／目录 | 变动／职责 |
| --- | --- |
| `scripts/sesrag.ps1` | 新增统一PowerShell入口：Prepare/Start/Status/Verify/Update/Stop/Destroy；首次准备专用工具环境 |
| `scripts/deployment/configuration.py` | 新增独立Secret解析、既有dotenv字段保留、随机密钥与受限Profile写入；不回显凭据 |
| `scripts/deployment/stack.py` | 新增project/daemon/owner核验、串行动作与报告；应用更新前停写并备份数据库 |
| `scripts/compose.runtime.yaml` | 新增回环端口、restart策略、运行时Profile挂载、容器/网络/卷owner标签；不改业务镜像源码 |
| `scripts/runtime/` | 受限私有账本、Model/RAG/初始化配置、原.env副本和数据库备份；Git/Docker构建忽略 |
| `docker/monitoring/helpers/lifecycle.py`、`cli.py`、`run-monitoring.ps1` | 增加显式RefreshBinding，限定同project/network ID/targets/信号语义，只更新源码及正式接口来源依据；不绕过模板/镜像漂移 |
| `.env.example` | 补统一部署使用的环境身份、自动owner、回环端口说明；不填真实凭据 |
| `.gitignore`、`.dockerignore` | 排除统一部署私有runtime和本轮证据 |
| `tests/grafana-observability-test/` | 新增配置/归属单测、真实模型三信号、实际Worker告警、统一生命周期与面板查询验证；不新建临时Compose环境 |
| 根README、模块README、scripts README、部署Runbook、ADR-005 | 同步操作入口、编排边界、销毁语义、验证与限制 |

根`.env`已按授权文件填入会话/Embedding/rerank/MinerU独立凭据，`MOCK_PROVIDER=false`、`MINERU_ENABLED=true`。MinerU状态密钥随机生成，原有有效数据库密码保留；首次原.env副本放入受限runtime。监控沿用004指标/安全JSON/OTLP契约及005固定镜像、数据源UID、仪表盘和八规则，不新增业务API或数据库Schema。

Start只在首次生成配置；后续调用不自动扫描Secret文档覆盖.env。更新凭据时在本机编辑.env再Update。默认真实聊天Profile为`live-chat@1`，模型为`gpt-6.1-sol`。RAG Profile不把Mock空间冒充真实空间，不把未验证计数状态伪造为已验证。

## 3. 实际验证与证据

证据位于`tests/grafana-observability-test/artifacts/<run-id>/`；监控子动作另保留模块artifacts原报告。所有模型正文只保存长度/hash，业务事实保留在应用数据库，不回显Secret。

| 核对项 | 结果及证据 |
| --- | --- |
| 配置与准入 | `20261117T122339-933ce790/deployment.json`准备成功；首次完整Start `20261117T122546-bca89447/deployment.json`通过，API/Worker实际源码、网络身份、opt-in及指标绑定经G1～G5检查 |
| 真实模型闭环 | `20261117T122847-9f462a8e/signals.json`：前端同源v3请求→持久Run/Task→Worker→真实模型，Run succeeded，回答58字符且非空；非Mock，不写模型明文报告 |
| 日志与追踪 | 同一signals证据：Loki Worker完成日志与Tempo API/Worker使用同trace；span含http.request、task.enqueue、task.attempt、model.generate及context/generation/publish阶段；正文哨兵未泄漏 |
| 真实指标 | 7个Prometheus目标UP；应用服务/环境身份正确，未替换fixture指标 |
| 真实告警 | `20261117T122946-227612f1/alerts.json`：优雅停止真实Worker，默认TARGET-DOWN等待2分钟后Firing，sink实际接收；恢复Worker后实际收到Resolved，同fingerprint与group hash。未缩短规则或通知窗口 |
| 更新/停止/销毁容器/恢复 | 修复后`20261117T124601-770fdf6c/lifecycle.json`：依次Update→Stop→Destroy→再次Update→Start→Verify通过；业务表行数/行内容摘要、卷创建信息、应用网络ID与原有六个停止容器ID一致。Destroy时应用容器为空，四卷及应用网络保留。原`20261117T123427-3f9507dd`保留为前一轮证据 |
| 更新前备份 | `20261117T124604-4141b9d3/deployment.json`及Destroy后直接Update的`20261117T124829-6fe85668/deployment.json`：两次均先停写/恢复PG、成功pg_dump、pg_restore清单校验和host复制，再继续迁移；私有备份ID各与run-id相同。并非全卷灾备或跨版本回退演练 |
| 数据源/面板/历史 | 基础Verify核三数据源健康、稳定UID、三面板、关联模板；最新`20261117T125225-8c8f16dc/queries.json`核15条实际面板PromQL均成功、历史真实trace仍可查、八规则实际均inactive。与此前完成的生命周期证据联合证明本次重启后数据保留 |
| 单元和静态检查 | 本轮9项安全/配置测试与监控原17项独立单测通过；包括示例空值、Destroy后持久数据库备份和partial聚合。Ruff检查/格式、两份PowerShell入口语法、Python compileall、文档链接及git diff空白检查通过 |

signals报告整体为partial，因为真实Embedding/rerank可用性另记blocked；模型聊天及三信号各自通过。基础Verify也保留完整验收占位not_run，Tempo无纯静态解析器仍记not_run；不把这些原报告整体改写为passed。

总报告聚合已同步保留下层partial：修复后的Start/Update在Validate存在未运行项时仍为partial；Verify在完整验收占位未运行时也为partial，并带子报告ID。动作退出0和生命周期动作试跑通过仅说明对应操作及数据保护检查完成，不意味着所有产品能力验收通过。

首次试跑`20261117T122406-64ca22a6`失败于新配置选择的`o200k_base`不在当前离线资产白名单，已改用镜像已提供的`cl100k_base`，重新导入并完成上述真实验证。失败原证据保留，不计作最终通过项。

主要复现命令：

```powershell
pwsh -NoProfile -File scripts/sesrag.ps1 Start
pwsh -NoProfile -File scripts/sesrag.ps1 Verify
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_live.py signals
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_live.py alerts
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/lifecycle_live.py
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_queries.py
```

signals产生真实模型费用，alerts/lifecycle有维护停机窗口，不能在有用户业务进行时随意重跑。日常只需Start/Status/Verify，具体说明见scripts README。

## 4. 未验证内容与后续处理

1. **完整真实RAG受既有门槛限制**：Embedding/rerank Profile显示`INPUT_COUNTER_UNVERIFIED`，凭据已准备但仍不能选择。后续需取得供应商可复核的输入计数/配额规则、按现有预算策略做边界验证并保存证据，再以新版本Profile启用；不能只改`counter_status`。本次未重新提交MinerU办公解析任务或做九格式/检索效果验收。
2. **生成模型计数仍为本地保守配置**：8192本地窗口、1024安全余量、显式cl100k_base；没有供应商对gpt-6.1-sol精确tokenizer/框架开销校准证明。不把小规模请求成功外推为完整模型窗口或计费计数准确。
3. **告警实测范围**：本部署实际制造并核验TARGET-DOWN的Firing/Resolved；八规则配置/查询与最终inactive均核验，其它规则未在持久环境逐一制造故障。此前005隔离验证保留为原开发证据，不冒充本次实测。
4. **平台和生产安全范围**：Linux可选profile、Windows物理机指标、公网认证/外部通知/高可用未实施或未测。前端沿用既有Vite服务，长期公网生产部署仍需独立安全与服务化方案。
5. **数据保留与销毁**：统一Destroy只销毁容器，保留历史、Secret及应用网络，故后续Start可恢复。明确清监控数据须单独执行监控模块Erase操作；统一入口不提供清业务卷操作。镜像、cache、显式备份和报告不自动删除，VHDX不自动收缩。

## 5. 整体校审

### Standards

规范轴发现3项并已修复：按容器判断备份会漏掉Destroy后的持久数据库；模板显式空白名单未填默认；单凭历史trace存在就把查询命名为“更新/销毁后”会夸大单个检查证据。另同步修复子报告partial聚合。静态复核未发现剩余可行动问题，真实边界回归另见最新运行证据。

### Spec

需求轴发现前两项实质缺陷，修复并补DEP-07/08/09后静态复核未发现剩余实质问题或范围扩张。真实RAG门槛、Linux及公网生产边界保持明确。两轴不把原始问题重复合成新的缺陷数量，也不以静态复核替代实际试跑。

已有`docs/当前任务说明.md`用户修改保留，不自动提交或推送。业务代码、根业务Compose、迁移和业务接口本轮未修改。

最终汇总为`tests/grafana-observability-test/artifacts/delivery-20261117T125421Z/report.json`，实际状态`running`：5个常驻应用服务、6个监控服务，API就绪、前端可访问；最新Status `20261117T125248-6fe3be67`未发现配置漂移。汇总整体保持partial，逐项记录真实RAG及其它未验证边界，没有把运行成功等同于完整产品验收。配置私有文件ACL已核验，源码/文档/脱敏证据未发现原始Key、密码或DSN；150条本地链接及代码块闭合检查通过。
