# 后端单元验证

状态机、Task策略、切分/解析、Mock Provider、余弦排序与配置验证在本目录按模块命名。foundation_* 验证初始化契约、迁移历史/回退和完整性约束；foundation_pg_probe.py 仅在控制者指定的新隔离 PG 库使用。

`test_rag_boundaries.py` 验证基础位置、真实空输入与损坏文档安全错误、向量/TopK、httpx 协议响应和解析进程超时回收；MockTransport 用于协议错误注入，不证明真实网络效果。真实本地 HTTP/SSE 和 PostgreSQL 竞争见 integration 目录。

```powershell
.venv/Scripts/python.exe -m pytest tests/unit -q
```
