# 后端单元验证

状态机、Task策略、切分/解析、Mock Provider、余弦排序与配置验证在本目录按模块命名。foundation_* 验证初始化契约、迁移历史/回退和完整性约束；foundation_pg_probe.py 仅在控制者指定的新隔离 PG 库使用。

`test_rag_boundaries.py` 验证基础位置、真实空输入与损坏文档安全错误、向量/TopK、httpx 协议响应和解析进程超时回收；MockTransport 用于协议错误注入，不证明真实网络效果。真实本地 HTTP/SSE 和 PostgreSQL 竞争见 integration 目录。

`test_v2_session_migrations.py` 真实执行 0003→0006 SQLite DDL/DML，覆盖混合旧 Run 状态、全历史 hash/计数、不安全数据预检、可恢复0003回退和v2事实/自定义Profile/base拒绝。`test_branch_paths.py` 覆盖有效 fork 区间、祖先不复制、限额/环检测、请求省略语义与有界历史加载；SQLite 不证明 PostgreSQL 行锁与多连接竞争。

`test_context_planning.py` 验证 mandatory 预检、完整轮次裁剪、紧凑范围、摘要来源及证据同分时按 document/chunk 升序淘汰；摘要构造失败可回退，但计数器失败必须传播，不能被摘要故障语义吞掉。v2 实际发布/模型链路见 integration 测试。

```powershell
.venv/Scripts/python.exe -m pytest tests/unit -q
```
# PRD-003 补充说明

`test_rag_profiles_v3.py`、`test_rag_migrations_v3.py`、`test_rag_chunking_v3.py`、`test_rag_office_inputs_v3.py`、`test_rag_mineru_tables_v3.py`、`test_rag_vector_normalization_v3.py`、`test_rag_sql_scope_v3.py`分别覆盖固定路由／空间、元数据及实际迁移、结构与字节预算、九格式和恶意包、云端表格／图片空文本、查询／入库归一化、PG物化查询编译。SQL编译与SQLite不等于PG执行证明。旧v2迁移测试固定到0006，防止本轮head变化使历史hash口径漂移。
