# SesRAG 契约

`run_event_v1.json` 是前后端 Event envelope 的首版 JSON Schema。后端写入 PostgreSQL 的 `RunEvent`、SSE 输出和前端 `RunEvent` 类型都必须保持该契约的字段语义。

修改 Event 类型时，先更新 Schema 和契约测试，再同步后端事件生成和前端类型。`seq` 是同一 Run 内单调递增的事实序号，SSE 的 `id` 使用该序号；Redis 只传唤醒通知，不是契约事实来源。

