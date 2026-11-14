# 应用观测模块

实现依据：[PRD-004](../../../docs/prd/004-SesRAG-应用可观测性与追踪上下文-PRD.md)、[ADR-004](../../../docs/adr/004-sesrag-observability-implementation-plan.md)。正式端点及字段以[接口文档](../../../docs/接口文档.md)和[版本化字典](../../../contracts/observability/metrics_v1.json)为准。

`runtime.py`在API lifespan／Worker main中装配独立registry、日志队列、SDK和监听；import不启动端口或注册全局provider。`config.py`把OBS原始字符串转换为分功能配置，错误以安全诊断降级。`metrics.py`消费同一指标字典，只接受声明的标签元组；`metrics_http.py`独立线程缓存编码并提供只读抓取。`snapshots.py`只在API启动专用只读连接池与5秒快照，Worker不重复提供全局队列。

`tracing.py`使用显式OTel provider和手动span；`exporter.py`使用固定端点Session和标准库HTTP连接，将DNS核验结果绑定到socket，不信任环境代理、不重定向或转发业务凭据。`sanitization.py`先投影有限字段／固定中文消息，`logging.py`再非阻塞排队写stdout，第三方原始日志不输出。`transactions.py`仅在指定Session实例订阅原事务提交/回滚，回调不执行SQL或网络。

应用层通过`backend/application/observation.py`接线；领域DTO在`backend/domain/observability.py`。来源创建与结算回执都不改变业务授权、租约、预算和事实。新Task在首次flush前保存producer来源，旧NULL不回填；每代attempt消费同一来源。handler正常返回不能宣布成功。

本地启动与迁移／故障排查见[Runbook](../../../docs/runbooks/application-observability.md)。005消费端需保持源`service/environment`、设置`honor_labels: true`并对快照做有效性guard。本模块不部署Grafana、Alloy或其它监控存储。
