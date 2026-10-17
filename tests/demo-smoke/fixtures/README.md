# Fixture职责

`upload-safe/smoke.txt`、`smoke.md`为UTF-8小文本；`smoke-docx.document.xml`为可审计docx正文源。总入口每次复制到`tmp/<run_id>/fixtures/`并用固定ZIP时间生成`upload-safe/smoke.docx`，分类接收生成后的FixtureDir，结束全部清理。无测试用例使用时不提交二进制docx。

`upload-invalid/unsupported.exe.txt`只是安全文本；后续用例需在本次tmp中复制改名为.exe，不能执行它。大于10MiB、损坏ZIP、路径哨兵均在tmp按需生成，不进入Git或默认报告。

`expected/event-types.json`对应正式Event v1契约，保留task.leased作为应有期望及当前缺口说明；不能删除未实现事件来让测试通过。契约变更时同时维护此文件。

数据只证明格式、流程和证据身份，不证明Mock检索语义质量。禁止放真实知识库、Secret、宿主敏感路径或无用途的大文件。

任务1核查后确认当前无需统一业务SQL/数据库导入脚本：owner是配置，Schema由迁移准备，各用例的可变事实独立经API创建。[data-strategy.md](data-strategy.md)给出逐场景的数据边界与未来确需固定SQL时的接入条件；不要预置成功Task/Run或全局Chunk污染空库/调度测试。
