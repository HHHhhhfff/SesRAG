# API 回归验证

`test_document_limits.py` 验证上传只请求10MiB+1字节且413无文档/文件残留。该测试不代表multipart解析前的网络或spool磁盘配额。

`test_core_api.py` 覆盖会话/消息/Run创建、幂等与上传拒绝；`test_foundation_health.py` 验证健康探测与安全错误；`test_foundation_public_fields.py` 验证公开source/created_at投影。

`test_validation_safety.py` 直接检查未经脱敏的 ASGI 原始 422 响应：长标题/消息、错误类型、畸形 JSON、非法 query 和缺失 file 不回显 input/ctx/原值，仅公开安全 type/loc 与固定摘要；同时验证正常创建和业务 422/404 错误仍保持原契约。

`test_execution_stream.py` 验证 SSE 在握手前拒绝不存在的 Run、Header优先及非法游标归零补放、终态空后缀关闭。普通事件查询与 SSE 的游标规则分别遵循正式接口文档。

```powershell
.venv/Scripts/python.exe -m pytest tests/api -q
```
