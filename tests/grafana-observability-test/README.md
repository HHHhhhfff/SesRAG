# 本机持久应用与Grafana部署验证

本目录只对`scripts/`管理的`sesrag-live`和`sesrag-observe-live`做验证，不另搭临时环境，不借用前轮正式验收脚本。入口会核验随机资源身份。报告在被Git/Docker构建忽略的`artifacts/`，只有状态、关联ID、hash和白名单通知字段；Secret和完整模型回答不写报告。

| 文件 | 用途 |
| --- | --- |
| `test_deployment.py` | dotenv安全/独立凭据/归属拒绝/RefreshBinding目标不变的离线回归，不启动容器 |
| `verify_live.py signals` | 从实际前端同源API发真实模型聊天，核持久Run/Task结果、Loki/Tempo同trace、正文不泄漏和真实Prometheus targets；另记真实RAG既有限制 |
| `verify_live.py alerts` | 优雅停止该持久Worker，用默认TARGET-DOWN窗口验证真实Firing/Resolved与sink接收，finally恢复Worker；不修改告警规则/阈值 |
| `lifecycle_live.py` | 顺序试跑Update、Stop、Destroy、再次Update、Start及Verify；包括无容器但有数据库卷的更新备份，对照业务事实计数、应用网络/卷、非本部署资源，结束保持运行 |
| `verify_queries.py` | 执行实际Grafana面板15条PromQL，核重启后历史trace和八类规则inactive |

在仓库根目录执行：

```powershell
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/grafana-observability-test -p 'test_*.py'
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_live.py signals
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_live.py alerts
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/lifecycle_live.py
& docker/monitoring/.cache/venv/Scripts/python.exe -X utf8 tests/grafana-observability-test/verify_queries.py
```

signals会创建一个命名清楚的验证Thread/Run并产生真实模型费用，保留业务事实；alerts会造成约数分钟Worker维护窗口，不在有用户任务执行时运行。lifecycle会构建镜像、停止和删除本部署容器，但保留数据；显式数据库备份仍含业务数据且要私下保护。不要对日常访问高峰运行这些验证。执行失败看报告错误码与未完成项，不能以进程退出0替代每个检查状态；signals的RAG计数门槛仍会记录blocked，不等于监控失败。

本轮实际结果、证据ID和未测项见[持久部署与统一运维结果](../../docs/pr/005-SesRAG-持久部署与统一运维-PR.md)。
