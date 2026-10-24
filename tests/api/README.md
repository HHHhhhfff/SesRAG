# API 回归验证

`test_document_limits.py` 验证上传只请求10MiB+1字节且413无文档/文件残留。该测试不代表multipart解析前的网络或spool磁盘配额。

`test_core_api.py` 覆盖会话/消息/Run创建、幂等与上传拒绝；`test_foundation_health.py` 验证健康探测与安全错误；`test_foundation_public_fields.py` 验证公开source/created_at投影。

`test_validation_safety.py` 直接检查未经脱敏的 ASGI 原始 422 响应：长标题/消息、错误类型、畸形 JSON、非法 query 和缺失 file 不回显 input/ctx/原值，仅公开安全 type/loc 与固定摘要；同时验证正常创建和业务 422/404 错误仍保持原契约。

`test_execution_stream.py` 验证 SSE 在握手前拒绝不存在的 Run、Header优先及非法游标归零补放、终态空后缀关闭。普通事件查询与 SSE 的游标规则分别遵循正式接口文档。

`test_v2_schemas.py` 为 ADR-003 契约阶段的纯 DTO 消费测试：Profile 成对/显式null拒绝、标题名称修剪边界、空白消息与服务端字段拒绝、分页默认上限、legacy/v2事件精确payload，以及独立JSON字面样本的后端投影校验。

固定字面样本归属 [fixtures/README.md](fixtures/README.md)，数据为 `fixtures/v2-contract-samples.json`，独立于各轮验收套件。样本覆盖 v2 核心对象、legacy Run 与全部16类 v2 Event；同时经后端 DTO 与本地 JSON Schema 正/负断言，不联网解析 Schema。安装开发依赖时须包含 `jsonschema[format-nongpl]`，避免缺少格式检查器时非法 `date-time` 被静默接受。它们是契约输入，不是数据库 seed，也不代表真实业务结果。

`test_v2_session_api.py` 使用真实 SQLite/TestClient 验证已挂载的六条 v2 Thread/Branch 路由、旧标题保存、首次写升级/活动旧Run拒绝、keyset/历史分页、跨Thread404、分叉幂等、v1/schema2守卫及SSE握手前拒绝。Worker成功推进Branch沿用真实领取/完成服务。不代替后续v2执行、真实PostgreSQL竞争或Compose验收。

`test_v2_run_api.py` 验证 v2 消息原子创建、幂等省略语义与归档/禁用后重放、Run 安全投影、Context 未规划/代数404、输入创建者保持、legacy 读取取消不升级、可省略操作 body 及 SSE Header 优先/终态空尾关闭。

```powershell
.venv/Scripts/python.exe -m pytest tests/api -q
```
