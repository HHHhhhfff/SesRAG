# PRD-003 实施检查与中断恢复记录

- 日期：2026-10-30（Asia/Shanghai）。
- 依据：[PRD-003](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)、[ADR-003](003-sesrag-rag-mineru-implementation-plan.md)。
- 状态：工程主体和开发检查已完成；真实计数／效果等门槛仍有缺口，不表示全量验收通过。
- 正式结果：[PR-003](../pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)；本文件仅保留执行与恢复索引，不替代ADR决策。

## 阶段结果

| 阶段 | 当前产出与未退出项 |
| --- | --- |
| P0真实协议 | 固定九格式输入、七办公加扫描PDF真实产物、Embedding1024及原生rerank协议成功；真实模型输入计数仍unverified。 |
| P1契约／迁移 | 版本化DTO／Schema／类型、四迁移、Profile／空间、默认库与旧空间确认工具；真实PG升级至0010。 |
| P2/P3解析 | 固定授权／路由、幂等、单Job同batch恢复、有界等待和未知停止；安全出站／ZIP／HTML表格、纯文本独立。 |
| P4/P5索引／检索 | 不可变批次、租约原子发布、多维PG Top-K、重排／邻近／诊断、引用保护GC；真实模型全链路受计数门槛阻断。 |
| P6会话 | schema3复用原会话事务，冻结view、固定工具、实际证据与三代兼容；旧入口新引用也有FK保护。 |
| P7前端 | 库／策略／授权／active/latest／诊断／证据与中文投影；26项前端检查通过，未做全面真实浏览器验收。 |
| P8开发检查／交付 | 316后端通过，静态／类型／构建通过，三轮独立Compose通过且清理为空；20+5效果、10k性能及正式TEST-003未完成。 |

## Docker异常后的恢复

用户恢复Docker Desktop后，继续使用随机专用项目，不使用根.env／开发数据库。早期依赖下载网络超时已收日志清理；修复真实PG暴露的Alembic revision过长及模拟浏览器Host探针，不关闭Vite保护。构建分离依赖缓存，pip网络超时120秒且有界重试。

成功证据目录：data/rag-implementation/sesrag-rag-check-aab4c943f7/、审查补修前sesrag-rag-check-bdce4c5ca1/、最终sesrag-rag-check-15e869a51b/。最终probe true、cleanup 0，container/volume/network/images全空。真实服务既有批次仅只读补证，没有因恢复重新上传。

后端全量一次因离线tokenizer缓存缺失失败，准备阶段显式预热并校验后重跑最终316通过；普通请求仍不下载。其余实际修复、代码位置及差异见PR-003。

保留用户已有暂存内容，不自动提交／推送；不维护前轮正式验收套件，不执行全局Docker prune。后续工作为输入计数依据／校准和独立TEST-003，不能把本文状态误读为正式上线批准。
