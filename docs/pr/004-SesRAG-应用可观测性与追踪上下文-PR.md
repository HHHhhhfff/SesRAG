# PR-004：应用可观测性与追踪上下文实施简要说明

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | PR-004／1.0 |
| 日期 | 2026-11-14（Asia/Shanghai） |
| 项目基线 | main，HEAD `1779e968332285bd524275270838bdec2b845d66`；包版本仍为0.3.0，本轮未提交 |
| 状态 | 已实施；开发验证与整体校审通过，详见§6；不替代后续独立实施结果调研与正式测试设计 |
| 对应需求／方案 | [PRD-004](../prd/004-SesRAG-应用可观测性与追踪上下文-PRD.md)、[ADR-004](../adr/004-sesrag-observability-implementation-plan.md) |
| 正式接口真源 | [接口文档§9](../接口文档.md)、[版本化观测契约](../../contracts/observability/README.md) |
| 后续消费方 | [ADR-005](../adr/005-sesrag-local-observability-deployment-plan.md)，本轮不部署docker/monitoring |

## 1. 已实施的能力与边界

API/Worker现在各有独立Prometheus registry及内网监听、安全JSON stdout、显式OTel SDK与OTLP HTTP/protobuf。安全日志和指标默认启用，traces默认关闭；受控接收端配置齐备后显式启用，本地默认100%采样。观测故障允许丢遥测，但不改变Run/Task/Event事实、租约代数、取消/重试预算或业务readiness。

Task新增可空`trace_origin_json`，在创建事务首次flush前写入，之后由数据库触发器保护不可改变。可信HTTP根→短入队producer→后续各代独立兄弟consumer，拓扑为`task_sibling_spans_v1`。等待外部/自动重试/Worker重启仍消费原来源；幂等重放不重建producer。旧/坏来源按missing/invalid建立本地attempt根，不回填历史。

尝试结算以原授权事务commit回执确认，正常handler return不宣布成功。succeeded/failed/yielded/cancelled/lease_lost/released/unknown互斥，每次有效领取只计一次；retry_scheduled为附加属性。原最终Message/Event/active批次的事务边界保持不变。

## 2. 文件与模块变动

| 新增文件/目录 | 职责与调用位置 |
| --- | --- |
| `backend/domain/observability.py` | TraceOrigin、ExecutionIdentity、CommitReceipt普通DTO，无SDK/ORM依赖 |
| `backend/application/observation.py` | ContextVar旁路、创建/回执/控制/下游调用facade；同步、协程和异步生成流分别适配 |
| `backend/infrastructure/observability/{__init__,config,runtime}.py` | 分功能原始配置解析、独立装配/关闭、attempt和下游作用域 |
| 同目录`metrics.py`、`metrics_http.py`、`snapshots.py` | 唯一字典驱动指标、缓存只读监听、API专属只读PG/Redis快照及有效性 |
| 同目录`tracing.py`、`exporter.py` | 显式provider、有限span属性/采样、真实SDK固定端点Session与统一读取截止 |
| 同目录`logging.py`、`sanitization.py`、`transactions.py`、`README.md` | 编码后入队的白名单JSON；指定Session的commit/rollback回调；模块职责与限制 |
| `migrations/versions/0012_task_trace_origin.py` | 0011之后可空来源列、PG/SQLite不可变触发器、显式授权降级 |
| `contracts/observability/` | 四份严格Schema、指标字典、实例样例、README；额外增加固定错误码字典`error_codes_v1.json`统一日志投影 |
| `backend/tools/export_observability_contract.py` | 只读检查路由/指标漂移，导出版本/源码指纹/005安全输入 |
| `docker/observability-requirements.in`、`.lock` | 固定004直接及传递依赖/hash，Docker先hash安装，再给业务依赖派生相同精确constraints |
| `tests/unit/test_observability_*.py`、`tests/api/test_observability_{http,sse}.py` | 真实scope/事务/SDK协议、快照、配置、日志、安全和旁路故障底层回归 |
| `tests/sesrag-observability-test/` | 独立Compose、OTLP捕获器/Provider替身、总入口、恢复/持续故障/开销脚本、资源账本和脱敏报告；详见其README |
| `docs/runbooks/application-observability.md` | 应用启停、配置、迁移/回退、故障、005交接操作 |

| 修改已有路径 | 实际调整与目的 |
| --- | --- |
| `backend/config.py`、`.env.example` | OBS字段保留原始字符串，配置错误分功能降级；补默认/必填/安全边界 |
| `backend/app.py`、`backend/workers/main.py` | 生命周期接线；去除Worker import时basicConfig；原健康接口不变 |
| `backend/db/models.py`、`backend/domain/ports/__init__.py` | 可空来源映射，TaskLease末尾兼容追加来源及来源状态 |
| `backend/infrastructure/queue/adapter.py` | 来源只读解码与有限claim/renew/reclaim/release观测，不改QueuePort业务返回含义 |
| `backend/tools/upgrade_rag_schema.py` | 实际head识别、0010/0011向前升级、head重复无操作、未知版本拒绝 |
| `backend/application/{threads,session_runs,documents,index_builds,retrieval}.py` | 六处真实新Task分支挂接producer，重放分支不覆盖来源 |
| `backend/application/{task_execution,rag_task_execution}.py`、`backend/infrastructure/queue/postgres_queue.py` | 在原成功/yield/失败/取消/回排事务登记回执；yield清worker前捕获身份 |
| `backend/workers/runtime.py`及四类`handlers/` | 领取后scope、七类结果、阶段及终态提交接线；新runtime不再重复旧全dispatch计时/观测查库 |
| `backend/application/{stage_observation,session_execution,parse_jobs,retrieval,rag_run_execution}.py` | 阶段outcome handle、原三参callback兼容、检索empty/degraded、生成流上下文和本地解析边界；检索事务commit后补充当前尝试的真实execution身份 |
| `backend/infrastructure/providers/{openai_compatible,bailian_embedding,bailian_rerank,mock,rag_registry}.py`、`backend/infrastructure/rag/{mineru_client,parsers}.py` | 实际下游方法手动安全span，不采正文/URL、不注入追踪头，Mock明确backend属性 |
| `backend/api/routes/{runs,v2/runs,v3/sessions}.py` | SSE终态补放完成标记，原分页/游标/Event协议不变 |
| `pyproject.toml`、`docker/api/Dockerfile`、`docker-compose.yml` | 固定观测依赖、复制契约、关闭原始访问日志；角色指标端口仅expose、30s停机宽限、日志轮转和005标签预留 |
| `tests/unit/{test_foundation_migrations,test_rag_migrations_v3}.py`、`tests/integration/rag_v3_pg_probe.py` | 共用迁移测试同步0012及显式降级授权；未修改前轮正式验收目录 |
| `.gitignore`、`.dockerignore`、README、backend/README、CONTEXT、接口文档、PRD/ADR引用 | 运行凭据/产物不进入Git或构建上下文，维护用途/契约导航及状态 |

实施时增加了恢复Worker夹具、资源锁/恢复脚本、独立SDK传输和SSE负例等文件，目的是让关键边界可直接验证。PG迁移底层验证放在本轮`test_recovery.py`中，未额外创建同内容的`tests/integration/test_observability_migration.py`，避免重复维护两套环境。没有改动前轮正式专项目录，没有自动提交或推送。

## 3. 应用端点、指标及005拉取入口

| 应用 | 内网抓取地址 | 暴露内容 |
| --- | --- | --- |
| API | `http://api:9101/metrics` | HTTP/SSE、全局队列、PG/Redis/Worker聚合快照、下游及观测自身 |
| Worker | `http://worker:9102/metrics` | 本进程attempt/stage/control/downstream、观测自身；不重复全局队列 |
| 业务健康 | 原`/health/live`、`/health/ready` | 原响应/状态语义；不依赖观测接收端成功 |

这两类指标端口在根Compose只expose，不发布到宿主，也不经前端。多个Worker须逐实例唯一DNS目标。005把Prometheus/Alloy显式连接已核验的应用网络，再配置真实目标；004不创建该监控网络。

主要指标包括`sesrag_http_requests_total`、`sesrag_http_request_duration_seconds`、四个SSE系列、`sesrag_worker_ready`、`sesrag_ready_workers`、`sesrag_dependency_ready`、`sesrag_queue_ready_tasks`、`sesrag_queue_oldest_wait_seconds`、`sesrag_queue_tasks`、五个snapshot控制/刷新系列、三种task_attempt系列、worker_accepting/control、stage_duration、downstream_calls/duration及observation_events/trace_export_spans。完整28项名称、单位、labels、合法元组和桶以[接口文档§9](../接口文档.md)及机器字典为准，本表不建立第二份可漂移契约。

所有指标由源端固定提供service/environment，005须`honor_labels: true`。队列及聚合readiness只使用API单一来源；Worker counter先逐实例rate再sum。快照每5秒刷新、30秒有效，来源固定queue/worker_presence/postgres/redis；初始未知缺少业务样本，失败保留旧值但valid=0。告警必须同时guard有效性和last_success，不能把未知补零。

通过`OBS_TRACES_ENABLED=true`、合法`OBS_OTLP_TRACES_ENDPOINT`及精确`OBS_OTLP_ALLOWED_HOSTS`启用后，应用以HTTP/protobuf发往受控内网/v1/traces；后续005配置其唯一Alloy别名。日志按JSON字段trace_id关联，不把Task/Run ID当trace_id；未采样或发送失败可能查不到已保存trace。

## 4. 接口、契约和数据变化

唯一数据库新增为Task的可空来源列。0012不改旧Message/RunSnapshot/Event payload，不回填旧Task；PG比较JSON时转jsonb，NULL→对象等任何UPDATE改变均拒绝。降级必须停止应用并使用`-x allow_observability_loss=true`授权丢来源，原0011迁移入口不能误用于较新head。

公网traceparent/tracestate/baggage不被extract，第三方请求无W3C头。只手动插桩，不启用FastAPI/httpx/SQL自动插桩，不采SQL/Prompt/文档/签名URL/异常正文。安全日志先同步投影/编码，再进入1024容量队列，单行≤4096bytes；观测失败不暴露原始异常。

SDK独立provider，resource仅service.name/service.version/deployment.environment.name，ParentBased采样保留来源决定，禁自动异常event/status description及atexit。导出端点复核精确目标及DNS，将核验IP绑定socket；统一截止覆盖状态行、header、chunk及body，拒绝慢滴无限延长，禁代理/重定向/公网，单请求1MiB、响应64KiB。

## 5. 审批中发现并修正的问题

1. 恢复来源的TraceFlags原为整数，SDK ParentBased要求对象；改为显式TraceFlags，并用有效producer来源的真实consumer及protobuf验证。
2. SDK调用Session.request，原先只覆盖post会绕过限制；改为覆盖真实SDK路径，加入真实HTTP/protobuf捕获回归。
3. 单socket读超时不能约束持续慢滴响应；加入保留socket与统一deadline reader，覆盖status/header/chunk/body，并补慢滴header负例。
4. HTTP指标/attempt结束异常可能改变业务或遗留ContextVar；记录器失败降级，清理放入独立finally。结束日志改在实际attempt/stage span激活时产生。
5. dependency指标必须按postgres/redis分别guard；修正字典及秒/布尔单位，能力Schema嵌套字段严格校验并加入缺字段/未知字段/错误拓扑负例。
6. 共用降级测试必须显式授权丢来源；修正测试输入，保留线上无授权拒绝降级门禁。根Compose角色端口键通过结构化config核验纠正。
7. 独立测试的v3文档状态路径、挂载脚本导入路径、测试加密Key编码、暖机/测量数据隔离和finally临时归档清理均已修正；探索失败保留诊断，不计产品通过。
8. 最终Spec复核发现新日志分支遗漏部分已有安全业务身份；补齐Task身份与有界Thread查询，当前attempt独享correlation供阶段/续租/结束日志复用。旧文本批次在handler选定后才关联，检索execution在原事务提交后关联，不伪造领取时未知信息；四类红→绿回归及跨任务隔离已加入。
9. Worker重建使先前容器stdout丢失，测试主入口改为重建前后分别收集并合并校验；补齐10个真实SSE连接持续30秒的断连/补放，以及开销窗口内候选双指标端点每5秒抓取。

规范/需求双轴审查及其轻量复验已执行；发现的阻断项已修复并按最终候选重跑。以下结果是本次开发交付依据，不凭静态源码或早先探索轮次宣告通过。

## 6. 验证记录与剩余限制

最终候选`impl-final-05`的13条分组/工程结果全部passed，源码指纹为`929ed24997002a9e36ff0c5b2e4609f4447b5ff59cd64687ffff092762f4b2b3`。最终报告、能力实例、日志和三对资源采样分别在`tests/sesrag-observability-test/artifacts/impl-final-05/{report,application,logs,budget}.json`（Git忽略，本机保留）。配置hash为`b2f8f5af478e6d05437d62ba25ad913d6ff62c9dedafd34321cbc33c598c01ce`，指标字典hash为`7c6636a649ea703643e981d1dd96d9cb92eae8b1b390777444ccb10933184b6a`。

| 已执行命令／检查 | 结果与边界 |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/unit tests/api -q` | 最终302项通过（76.42秒），包括补充部分采样来源决定回归 |
| `.venv/Scripts/python.exe -m mypy backend` | 147个源文件通过 |
| `.venv/Scripts/python.exe -m ruff check backend tests/unit tests/api tests/integration tests/sesrag-observability-test` | 通过；新增观测模块及本轮脚本格式检查通过 |
| `.venv/Scripts/python.exe -m backend.tools.export_observability_contract --check` | 能力Schema、实际路由与28项指标字典一致 |
| `docker compose config --quiet`、容器`pip check` | 根部署配置及固定SDK依赖检查通过 |
| `.venv/Scripts/python.exe -u tests/sesrag-observability-test/tooling/runner.py --group All --run-id impl-final-05 --skip-build` | 候选镜像已在`impl-final-02`按修正源码构建；之后仅修验证脚本，应用源码指纹一致。最终All包含恢复、10连接SSE、持续质量与三对开销；退出码0 |

关键证据：真实HTTP/protobuf捕获197个安全span，四类Task均消费原producer；硬杀/正常停机释放后generation均到2、来源不变并成功；10个SSE连接保持30秒后active归零、后台Run成功、游标补放无重复。重建前后合并校验573条JSON日志，适用Thread/文档/批次/解析/检索身份得到保留；日志原文直接来自核验过的容器，排除Compose渲染信息。

11000条真实PG队列夹具查询耗时30.70ms；两个指标目标各1200次抓取且240次并行业务读取成功，抓取阶段和并行业务收尾期间共26次队列刷新，保持约5秒的原刷新频率。接收端慢故障持续120秒、前60秒施加队列压力，18个业务Run仍成功，额外关闭2.006秒；SDK精确drop数仍报告unknown。

三对均保留完整数据，顺序B→C、C→B、B→C；每环境暖机60秒、测量约300秒，600个短请求、200个四类Task（run125，其余各25），错误率0。候选同时每5秒抓取双指标端点，traces100%，未关闭安全日志。下表为B→C，CPU/RSS列为候选相对基线增量。

| 对次 | HTTP p95（ms） | Task attempt p95（ms） | API／Worker CPU增量（核） | API／Worker RSS增量（MiB） | 固定负载完成吞吐C/B | 门槛 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 36.25→37.88 | 190.72→187.96 | 0.0313／0.0357 | 15.69／16.70 | 100% | 全通过 |
| 2 | 36.60→39.99 | 189.85→185.55 | 0.0300／0.0339 | 15.49／15.58 | 100% | 全通过 |
| 3 | 38.36→37.92 | 183.61→196.40 | 0.0307／0.0373 | 14.86／15.59 | 100% | 全通过 |

固定负载完成吞吐均为200/300=0.667 Task/s，用于本地对比，不是饱和容量测试或生产SLO。资源采样每环境286～291点，保留CPU秒、RSS与cgroup可见内存。容器、卷、网络清单均为空，runtime凭据、锁、账本、Git基线归档已删除；镜像/BuildKit缓存与脱敏报告按说明保留。

未计通过的探索轮次保留在artifacts：早期接口/夹具/预算编排错误、`impl-final-01`因最终日志修复而主动终止、`impl-final-02/03/04`分别暴露重建丢日志或采集渲染问题；均已定位修正，不能用其局部结果代替最终All。详细复验与校审记录见[开发验证记录](../../tests/sesrag-observability-test/开发实施验证记录.md)。

本轮没有前端代码/业务API JSON/Event变动，因此未额外执行前端构建/类型检查；没有调用真实付费模型/MinerU，也不以受控替身证明真实服务可用性。Grafana/Loki/Tempo展示、存储与告警通知闭环属于005，尚未实施。

OS级DNS永久阻塞不能被Python强杀，关闭调用方按预算返回，进程退出可能丢遥测；本轮不提供持久发送队列、零丢失、跨崩溃精确审计或生产SLO。当前按单API部署，全局快照不可在多个API间相加；多Worker需显式逐目标采集。

详细事实、调研及后续测试点/正式验收仍可单独设计；本文是实施结果简要说明，不替代后续实施结果调研文档。
