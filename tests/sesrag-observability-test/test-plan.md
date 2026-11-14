# 004独立开发验证接入计划

版本1.0，2026-11-14（Asia/Shanghai）。依据[ADR-004](../../docs/adr/004-sesrag-observability-implementation-plan.md)，此处只维护可执行工程接线，不替代PRD或后续正式测试点/用例设计。

| 顺序 | 条件与输入 | 执行与退出证据 |
| --- | --- | --- |
| 1 环境预检 | Docker、Python3.12、固定观测依赖、当前源码 | 能力/路由漂移检查，随机run-id、凭据、锁和资源账本先建立 |
| 2 部署 | 本轮专属Compose，不复用开发卷/外部付费服务 | PG/Redis健康、根迁移到0012、API与Worker实际运行 |
| 3 功能 | 各组独立数据；Recovery显式准备四类链路 | Http→Trace→Metrics→Recovery→Security→Handoff；记录真实失败而继续独立组 |
| 4 恢复与长连接 | 专门慢生成Worker入口与原Task来源 | 重建前收集日志；硬杀后租约回收、停机释放后重试；generation前进且来源不变；10个SSE连接保持30s后断连与补放 |
| 5 持续质量 | 真实PG历史/非终态夹具、缓存与受控接收端 | 高频抓取不提高查询频率；故障/队列压力期间业务正常，线程/内存/关闭有界 |
| 6 开销 | 固定实施前Git基点与当前候选；同依赖层/资源/50ms夹具 | B→C/C→B交替3对，暖机60s+测量300s；每对完整分布/1秒资源数据与固定门槛结果 |
| 7 交付/清理 | 安全Schema/哨兵校验通过后才保存证据 | report/logs/application/budget，最后down当前project并核查三类label资源与runtime目录 |

Budget为耗时分组，失败/中断的探索轮次保留诊断，不进入有效三对。脚本故障与产品故障分别定位；不以修改业务返回或降低采样/删指标使脚本通过。Environment不计完整验收；未运行或依赖缺失明确标记，不能填passed。
