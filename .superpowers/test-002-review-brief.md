# TEST-002 静态审批任务

工作区 D:/Agentic_RAG/SesRAG，分支sesrag_v0.2，HEAD595eb04。全部本轮代码未提交（AGENTS禁止自动提交）；评审对象是工作区新增suite与其文档/ignore，而不是HEAD..HEAD空差异。先读AGENTS与tests/实施测试文件时的通用规范。

必须只读，不修改任何工作区/index/branch、不操作Docker、不派子代理。不重复执行实现者相同代码已跑的工具自测；审查测试是否真的能判错以及边界是否按方案实现。所有发现写 `.superpowers/test-002-static-review.md`（仅该报告可新建）并返回精简清单。

依据：docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md 和当前用户任务只准备环境，禁止实现产品分类。稳定范围优先审查：suite内compose/、fixtures/、tooling/provider-selftest.py、environment_probe.py、prepare-fixtures.py、db-admin.py、test_environment_tools.py、compose-entry.test.mjs、preflight.mjs、setup-tools.ps1、run-workspace-tests.ps1、schemas/、manifest、README接入规则，以及根ignore修改。

运行器orchestrator/resources/process/category/report和frozen-builds正在独立子任务修改；本轮先不下动态闭环结论，根代理会在它们稳定及真Docker验证后让你追加全套最终审批。你可先记录跨模块接口疑点反馈给根代理。

约束：root .env/开发库/其他Docker资源不碰；临时环境独立run/project/owner/卷/回环动态端口；secret先脱敏再artifact；PG正式迁移/Profile非业务seed；工具探测不算产品case；计划8类保持planned；环境passed不能冒充PRD验收；成功/异常/强停后资源按身份精准回收；工具缓存/报告明确保留。

提供逐项spec compliance与quality结论。Issues按Critical/Important/Minor标级，附真实文件行号、根因/影响、建议。不能因动态Docker未跑而虚称通过；未验证项明确列出。
