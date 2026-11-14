# PRD-004应用观测独立开发验证

依据[PRD-004](../../docs/prd/004-SesRAG-应用可观测性与追踪上下文-PRD.md)、[ADR-004](../../docs/adr/004-sesrag-observability-implementation-plan.md)。本目录只验证004应用能力，不调用前轮正式验收入口，不部署ADR-005监控组件，不读取`docs/secret`，不调用付费模型/MinerU。

## 1. 目录与职责

| 路径 | 职责 |
| --- | --- |
| `run-observability-tests.ps1` | PowerShell参数包装，使用项目Python3.12环境 |
| `tooling/runner.py` | Python唯一编排、专属project/凭据、中文结果、报告及finally销毁核验 |
| `tooling/evidence.py`、`probe.py` | 容器内分组调用、接口等待、安全结果投影，不把异常正文存档 |
| `tooling/recovery.py` | 运行锁和旧账本恢复；不会回收锁仍被持有的活动运行 |
| `tooling/restart.py` | 真实Worker硬杀/租约回收与正常停机释放的宿主编排 |
| `tooling/budget.py` | 只读Git归档构建实施前B，与当前C共享相同依赖层，交替三对采样 |
| `compose/compose.yaml`、`.env.example` | 独立PG/Redis/迁移/API/Worker/collector/probe；不发布宿主端口，不复用开发数据卷 |
| `compose/recovery.yaml` | 仅恢复分组临时覆盖Worker测试入口 |
| `fixtures/collector.py` | 真正解码OTLP HTTP/protobuf，保存有界安全span投影 |
| `fixtures/provider.py`、`recovery_worker.py` | 测试进程注入的MinerU传输替身、固定50ms业务延迟和受控慢生成；不修改生产SafeHTTP允许范围 |
| `fixtures/seed.sql` | 固定Schema门禁；账号基线用OWNER_ID=obs-test，动态对象各组独立创建 |
| `specific_test_script/` | 各分组的具体检查，见下表 |
| `runtime/<run-id>/` | 随机测试凭据、账本、锁、临时Git基线；Git/Docker上下文忽略，成功清理时删除 |
| `artifacts/<run-id>/` | 脱敏报告、有限JSON日志、005实例输入及资源比较；不覆盖既往证据 |

| 脚本／入口 | 验证目标与PRD验收组 |
| --- | --- |
| `test_http.py` | A01～A03：v1/v2实际请求、终态SSE补放、随机404和内网端点方法限制 |
| `test_metrics.py` | A04～A05：真实只读PG聚合，首次未知和失败保留旧值，API/Worker统计归属 |
| `test_trace.py` | A07～A08、A10、A12：四类持久Task、txt/md与受控办公文件、检索/重排/模型、幂等producer、真实protobuf和兄弟拓扑 |
| `test_recovery.py`＋`tooling/restart.py` | A06、A09～A10：PG触发器、降级授权、原事务yield，以及真实硬杀／停机释放后的来源保持 |
| `test_sse.py` | A03/A14：在All/Recovery的受控慢Worker中，10个真实SSE连接持续30秒，断连后active归零、Run继续成功及游标补放无重复 |
| `test_security.py` | A12：真实模型适配边界无W3C头，公网OTLP拒绝，敏感哨兵不出现在指标/捕获span |
| `test_quality.py` | A13～A14：11000条真实队列夹具、双目标10req/s持续120s、接收端故障120s及队列压力60s、业务继续、线程/内存/关闭预算 |
| `test_budget.py`＋`tooling/budget.py` | A14：相同依赖/资源/夹具，B→C/C→B交替3对，每目标暖机60s、测量300s，600短请求及至少200个四类任务 |
| `test_handoff.py` | A15：角色、单位、标签、条件初始化、序列≤12000及实际路由字典 |
| `tooling/runner.py` | A16：启动、迁移、受控执行、脱敏证据、销毁、卷/网络残留检查 |

以上是每组的验证职责，不能仅因某个脚本通过就代表该A组全部边界都通过；底层补充回归在`tests/unit/test_observability_*.py`及`tests/api/test_observability_http.py`，覆盖七种结果、源事务回滚、采样、异步流、记录器故障与SDK实际传输。实际结果以本轮报告为准。

## 2. 依赖与运行

需要Docker Desktop Linux容器、Compose v2、项目`.venv` Python3.12和`.[dev]`。镜像固定004观测依赖版本与hash，业务依赖沿用项目约束；首次构建需网络，运行验证无需外部服务。Docker可用内存建议≥8GiB；同一时刻只测一个开销环境，其他开发负载应停止。

```powershell
pwsh -NoProfile -File .\tests\sesrag-observability-test\run-observability-tests.ps1 -Group Environment
pwsh -NoProfile -File .\tests\sesrag-observability-test\run-observability-tests.ps1 -Group Trace
pwsh -NoProfile -File .\tests\sesrag-observability-test\run-observability-tests.ps1 -Group All
```

参数：`-Group Environment|Http|Metrics|Trace|Recovery|Security|Budget|Handoff|All`，可选`-RunId`。`-SkipBuild`仅在已明确构建当前源码镜像时使用；不得用旧镜像配新源码指纹形成验收。Budget/All完整三对约需40分钟，加上持续故障、重启与构建时间；不缩短窗口或只挑最优轮次。

Environment只证明部署与清理，不算产品通过。Recovery会先独立准备Trace业务夹具，再核验恢复。主入口在每次启动先检查旧账本与进程锁，恢复被硬停运行的自有资源；所有资源操作限定当前记录的Compose project，不做全机prune。

## 3. 结果与清理

每条结果包含case、passed/failed/blocked/not_run、中文说明与安全evidence。`report.json`记录源码ref/dirty指纹、配置与契约hash、各组结果、清理清单；`logs.json`只保存通过Schema/敏感哨兵检查的最近有限日志。Worker重建前先收集日志，重建后合并核对四类任务的适用身份，避免容器销毁造成证据缺失。旧文本候选批次在handler选定后才关联，领取时不伪造尚未知的批次。`application.json`是005可消费的安全实例输入，仍须在005实施时重新核验网络归属。

finally执行本project的`down --volumes --remove-orphans`，分别查询容器/卷/网络label确认无残留；成功后删除本运行凭据、锁、账本和Git归档。报告、构建镜像与BuildKit缓存按说明保留。构建缓存不是数据库/上传业务数据，按需用Docker Desktop管理，不自动全局清除。

本次实施验证结论与校审修正见[开发实施验证记录](开发实施验证记录.md)；最终`impl-final-05`13条结果全部通过、三对开销均通过、清理无残留。此记录不替代后续正式测试设计。

替身只能证明请求适配、返回处理、指标/日志/来源/错误语义及恢复，不证明真实MinerU或模型可用性、RAG效果或生产SLO。Grafana面板、Loki/Tempo持久化与告警通知在005另外验证。
