# 应用观测启用、验证与回退

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | RUNBOOK-004／1.0 |
| 日期 | 2026-11-14（Asia/Shanghai） |
| 适用 | 应用API/Worker，包版本0.3.0；单API、单或显式逐实例采集Worker |
| 依据 | [PRD-004](../prd/004-SesRAG-应用可观测性与追踪上下文-PRD.md)、[ADR-004](../adr/004-sesrag-observability-implementation-plan.md) |
| 正式真源 | [应用观测接口](../接口文档.md)、[指标字典](../../contracts/observability/metrics_v1.json) |

## 1. 默认部署与开关

使用根Compose的既有数据库凭据启动应用；004没有监控服务依赖。默认安全JSON日志与内网指标启用，traces关闭。API和Worker只在容器网监听9101/9102，不映射宿主，也不经过前端代理。原业务8000/health及API响应保持原协议。

| 配置 | 必填／默认 | 作用及边界 |
| --- | --- | --- |
| `OBS_METRICS_ENABLED` | 否／true | false同时关闭监听和API快照，JSON日志仍开启 |
| `OBS_METRICS_HOST` | 否／0.0.0.0 | 根Compose固定容器内监听；宿主直接运行须设127.0.0.1 |
| `OBS_METRICS_PORT` | 否／API9101、Worker9102 | 根Compose按角色固定，不自动寻找空闲端口；直接运行可显式设置1～65535 |
| `OBS_SERVICE_NAME` | 否／sesrag-api或sesrag-worker | 必须与进程角色一致，禁止任意动态身份 |
| `OBS_ENVIRONMENT` | 否／local | 有限小写环境名；与005部署environment一致 |
| `OBS_TRACES_ENABLED` | 否／false | endpoint存在也不会自动启用 |
| `OBS_OTLP_TRACES_ENDPOINT` | traces启用时必填 | 受控内网HTTP(S)绝对地址，路径固定/v1/traces，无凭据/query/fragment |
| `OBS_OTLP_ALLOWED_HOSTS` | traces启用时必填 | 精确主机名，不允许通配；发送时DNS全部结果必须是loopback、RFC1918或IPv6 ULA，绑定已核验IP，拒绝公网/link-local |
| `OBS_TRACE_SAMPLE_RATIO` | 否／1.0 | 有限0～1；本地100%，验收固定1.0；ParentBased保留来源采样 |

只支持本模块的OBS配置，traces启用时存在`OTEL_*`自动配置会停用traces并记录降级；移除冲突变量后重建应用。不要用模型/MinerU Key给观测接收端认证。本轮不支持公网认证OTLP网关。

## 2. 迁移与启动

1. 备份开发/正式数据库，安排写入和领取暂停窗口。先升级镜像，再运行migrate服务；新迁移0012接0011，增加可空来源列和不可变触发器，不回填历史Task。
2. 根`backend.tools.upgrade_rag_schema`读取实际head，旧0010/0011只前进；重复运行不回退catalog。未知或较新revision报`DATABASE_REVISION_UNSUPPORTED`，先更新正确代码镜像。
3. DDL锁等待1秒／语句30秒。拿不到锁即退出；排查持锁事务后重试，不提高到无限等待。
4. 启动API与Worker，从其所在内网验证监听。不要为了查看指标临时发布到0.0.0.0宿主端口。

在已授权的应用Compose项目中，可通过API容器读取自身指标（输出为公开的有限指标，无凭据）：

```powershell
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9101/metrics').read().decode())"
docker compose exec -T worker python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9102/metrics').read().decode())"
```

默认不需要真实模型或MinerU请求即可验证。开发独立验证见[本轮测试入口](../../tests/sesrag-observability-test/README.md)。

## 3. traces接收与005交接

004独立验证使用collector，正式后续005使用该部署的唯一Alloy内网别名。005 override显式将Prometheus/Alloy连接已核验的应用网络，并把该Alloy别名加入API/Worker白名单、配置`http://<alias>:4318/v1/traces`、设置`OBS_TRACES_ENABLED=true`。004不自动创建这个网络或Alloy。

导出能力描述并记录源码ref/dirty指纹；核对源service/environment与005静态目标一致。Prometheus应用job使用`honor_labels: true`。全局队列和聚合Worker存在性只采API；多个Worker分别提供唯一目标，counter先逐实例rate再sum，不sum多个API的全局快照。

快照四来源为queue、worker_presence、postgres、redis；业务告警仅在initialized/valid为1、last_success距采集时刻小于30秒时判断。缺失/过期另行告警。日志trace字段为JSON字段，高基数业务ID不作为Loki索引label。未采样/导出失败的日志可能没有可查询trace；Run ID不是trace_id。

## 4. 降级诊断

| 信号 | 排查与处理 |
| --- | --- |
| `config/invalid_config` | 核对角色、环境名、端口、采样、白名单和OTEL冲突；不打印整个env |
| `metrics/bind_failed` | 确认同容器无重复进程占用端口；修复部署后重启，不偷偷换端口 |
| `snapshot/source_error`或valid=0 | 核对PG/Redis连接、只读查询预算和心跳；保留旧值不能解释为当前健康 |
| `traces/export_failure` | 从应用网络核对接收别名、端口、allowlist、DNS和HTTP协议；接收端恢复后下一batch自然恢复 |
| `context/origin_missing|origin_invalid` | 旧Task无来源或数据不合法；保留业务身份，不能回填来源伪造原trace |
| `traces/span_limit` | scope超过128子span，指标仍累计；检查是否意外逐token/逐chunk创建无界span |
| `logs/queue_full`或`traces/flush_timeout` | 接收/输出故障可能丢遥测；业务事实仍查询PG。SDK队列精确丢失数未知，不当作审计账本 |

API/Worker业务readiness不依赖观测接收端。Worker收到停止信号先按原20秒宽限执行/释放，再给观测总计3秒收尾；Compose关闭宽限30秒。OS DNS系统调用永久阻塞无法由Python强杀，进程退出会丢弃内存队列，本轮不承诺零丢失。

## 5. 关闭与回退

临时停用traces可设false后重建应用；指标也可关闭，JSON日志仍启用。回退Schema前停止API/Worker并备份，再显式执行：

```powershell
alembic -x allow_observability_loss=true downgrade 0011_rag_source_integrity
```

该命令永久丢弃Task追踪来源，保留业务字段；未带参数会拒绝。不得在新代码仍运行时删列。仅回退旧镜像并保留0012时，须使用理解0012的迁移入口或跳过旧migrate服务，原0011工具不能识别较新head。005监控卷本轮未创建，无需清理。
