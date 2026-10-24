# TEST-002 接续账本

计划：docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md

## 已完成/进行中

- 已核对当前任务、仓库规则、测试规范、现有未提交增量及 Docker 既有资源。未自动提交/推送。
- 已新增 Compose 配置自测并观察失败后修复：动态分类标签、迁移/Profile/API/Worker依赖、Worker readiness、PG cluster_name。解析自测2/2通过。
- 已新增PowerShell唯一入口/setup。语法自测3/3通过。实际setup暴露多Node可执行路径集合问题，已改取首个匹配，Chromium安装执行中。
- Provider子任务：仅server.py/provider-selftest.py；报告10组协议检查连续3轮通过。待根代理整体验证。
- Python子任务：environment_probe/prepare-fixtures/db-admin，进行中。
- 运行器收尾子任务：workspace_runner_finish，要求见test-002-resume-brief.md；进行中，未启动Docker。

## 决策记录

- Ruling: 保留当前sesrag_v0.2工作目录接续，不创建新worktree——用户明确当前工作区继续且已有大量未提交增量；若判断错误需人工移动修改，但不会静默丢失工作。
- Ruling: Compose/资源helper使用Node模块，PowerShell只保留公开入口——避免维护双份生命周期；方案允许单一职责拆分，文档将同步真实文件路径。
- Ruling: 不给冻结镜像加入动态run标签，采用稳定suite/source指纹标签，tag+已记录imageID核验；构建完成但imageID未回填时仅以本轮tag和稳定标签恢复身份——满足冻结复用且能覆盖强停窗口；若标签不符必须拒绝删除并保留账本。

## 待执行

- setup/preflight完整验证；整合运行器和Python工具。
- 真Docker两次Environment完整闭环；部署半途故障清理；强停后Cleanup恢复及重复幂等扫描。
- All/Selected planned退出3、路径/owner/Engine/缺报告/采证故障等框架负例。
- README/测试方案/接入计划/环境实施与验证记录回填；逐项审核ENV-01～10和Git差异、秘密忽略/残留。
