# 后端模块

`api/` 保存 HTTP/SSE 路由与公开投影，`application/` 保存应用事务边界，`domain/` 保存稳定对象与协议，`infrastructure/` 实现适配器，`workers/` 编排租约与处理器。正式接口见 [接口文档](../docs/接口文档.md)。

ADR-002 增加的 `domain/ports/__init__.py` 定义纯 Python 的 TaskLease、Parser/位置、IndexedChunk/Evidence DTO，以及非空 Queue/Parser/VectorStore/Embedding/Model 协议，不引入 ORM 或厂商 SDK。

`application/task_execution.py` 统一 Task 身份、租约/截止、取消和最终消息事务；`vector_validation.py` 验证固定 384 维、有限且 float32 可表示数值。Worker Runtime 是组合根：绑定 `queue/adapter.py` 的事务适配器、`providers/factory.py` 的快照 Provider 工厂、`rag/pgvector_store.py` 的向量适配器和 `rag/parsers.py` 的 Parser；handler 实际消费这些注入依赖。

`rag/parser_process.py` 为内部解析子进程入口，不是 HTTP 接口。仅处理经过存储根目录校验的源文件；10 MiB 源、40 MiB ZIP 展开、100000 ZIP 条目/基础位置、64 MiB 序列化输出和 30 秒运行限额。Linux 另有 512 MiB 地址空间/30 秒 CPU 限额；Windows 不提供 RLIMIT。取消或超时回收子进程，不承诺通用沙箱。纯文本模式按 txt/md 行、docx 正文段落提供位置；空白非空文本保留既有字符切分行为，真正空文本永久失败。

索引候选在数据库事务外构建；最终 Task→Document 锁、chunks/active/Task succeeded 一次提交。任何 flush 后跨租约/截止均回滚；失败统一交 Runtime/Queue 结算。`migrations/versions/0003_chunk_locations.py` 为位置字段迁移，降级保留已有证据列；旧历史不补造位置。

运行与配置入口见根 README；测试职责与命令见 [集成测试](../tests/integration/README.md)。上传路由的有界读取不代表 multipart 接收阶段的网络或磁盘总配额。

Worker 六动作 JSON 日志使用持久 Task 的 `task_id`、`run_id`、`document_id` 关联业务对象：Run 任务的 `document_id` 为空，索引任务的 `run_id` 为空；保留 `worker_id/generation/attempt/error_code`，不读取业务内容或输出原始异常。
