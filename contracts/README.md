# SesRAG 契约

`evidence_v1.json` 约束新增引用的文档、chunk、不可变批次、分数和基础位置；旧历史记录不重写。

`run_event_v1.json` 同时约束 Event envelope 和11种 type/data 联合。领取身份、重试错误/attempt、检索身份/位置、增量text、终态message/citations各自严格校验；retrieval不含filename，与完整Citation不同。后端写入 PostgreSQL 的 `RunEvent`、SSE 输出和前端 `RunEvent` 类型都必须保持该契约的字段语义。

`message_v1.json` 和 `document_v1.json` 约束公开投影：Message 必须提供安全逻辑来源（`user_input`/`assistant_generation`）及 `created_at`；上传 Document 的来源固定为 `local_upload`，不得泄露宿主路径或 storage key。

修改 Event 类型时，先更新 Schema 和契约测试，再同步后端事件生成和前端类型。`seq` 是同一 Run 内单调递增的事实序号，SSE 的 `id` 使用该序号；Redis 只传唤醒通知，不是契约事实来源。

`thread_v1.json`、`run_v1.json`、`health_v1.json` 约束当前完整 Thread/Run/Task 和 readiness 200/503 投影；`api_responses_v1.json` 的 `$defs` 保存列表、详情、提交、取消、归档、索引、live 与错误响应包装。`citation_v1.json` 严格区分完整新 Evidence 和不含批次/位置的历史引用；新的 Worker 输出必须直接验证 `evidence_v1.json`，不能以 legacy 分支掩盖新协议缺失。

前端类型生成入口为 `frontend/scripts/generate-api-types.mjs`，使用项目 Node 标准库：`npm run generate:api --prefix frontend` 生成，`npm run check:api --prefix frontend` 只读比较并在漂移时非零退出。不得手工维护 `frontend/src/types/api.ts` 第二套字段。生成器支持仓库使用的引用、定义、联合、对象、数组与标量，未知结构失败；数值范围、format 等运行时约束仍由 JSON Schema 动态验证，TypeScript 不替代该门禁。

ADR-002 Task5d 接入所有 HTTP route/status 动态矩阵、Event payload 联合和生成漂移负哨兵；retrieval 的身份 DTO 不等于完整带 filename 的 Citation。请求校验 422 保留 detail 数组，每项仅允许安全 type/loc 和固定 msg="请求参数校验失败"，禁止 input/ctx/url 和原始输入值；前端只展示稳定错误码和固定摘要。业务 ApplicationError 保留 ErrorResponse。

ADR-003 Task1 新增八份独立 v2 契约：`thread_v2`（协议代际和默认分支）、`branch_v2`（父/分叉/head/version）、`message_v2`（不可变创建分支/Run）、`run_v2`（输入复用/来源/安全快照与计划摘要）、`model_profile_v2`（安全模型选项/版本）、`context_plan_v2`（有界上下文和摘要来源元数据）、`run_event_v2`（schema1直接引用+严格schema2联合）、`api_responses_v2`（请求、分页包装及复用的错误）。完整字段、15条计划路由与状态见 [正式接口文档 §7](../docs/接口文档.md#7-adr-003-v2-契约基线)。契约就绪不表示业务路由已上线。

默认 generate/check 同时维护 `frontend/src/types/api.ts` 和 `api-v2.ts`。原 `--output <path>` 仍只生成 v1 临时产物；`--version v2 --output <path>` 生成 v2，`--version v1|v2 --check` 可分代只读检查。CRLF/LF归一化后比较，真实字段差异失败。v2 显式 import/别名复用 v1 Citation、RetrievalItem、TaskSummary和LegacyRunEvent；v1 JSON及公开导出冻结。

聚焦验证：`node --test tests/demo-smoke/tooling/contracts-v2.test.mjs tests/demo-smoke/tooling/contracts.test.mjs`。独立字面样本 `tests/demo-smoke/tooling/v2-contract-samples.json` 覆盖全部16类schema2事件、完整安全投影与legacy空值；负样本拒绝缺字段、错误type/version/payload、任意对象及嵌套Secret。后端请求/投影消费测试见 `tests/api/test_v2_schemas.py`。

