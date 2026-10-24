# TEST-002 运行器收尾任务

依据：`docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md`；需求边界以当前 `docs/当前任务说明.md` 为准。只实现隔离临时环境，不实现产品分类脚本、不改产品代码、不提交/推送。现有未提交文件必须保留。

当前运行器已初写，需完成根因核查、失败测试、安全修复和自测。所属文件：`tooling/orchestrator.mjs`、`resources.mjs`、`process-registry.mjs`、`category-runner.mjs`、`report.mjs`、`self-tests.test.mjs`（均在 `tests/sesrag-persistent-session-workspace-test/`）。不要改 Compose、Python、Provider、PS入口或文档，由根代理处理。

明确要求：
- Environment: 真实 build→deploy→正式迁移/Profile→技术探测→采证→finally清理→独立残留审计；product_acceptance 固定 not_run。
- 每轮安全生成run_id/owner、runtime私有ACL、原子账本和进程身份。初始化、preflight、Docker失败也须报告并释放锁及自身临时目录，不能发生在finally之外。锁要校验活跃主进程身份；Cleanup拒绝仍活跃运行，允许强停后恢复，幂等复核不能仅信旧cleanup.json。
- runCommand 的创建身份/终止必须保守，运行期登记进程；中断后停止后续部署，清理有界，清理失败优先4，参数/工具/协议错误2，环境前提受限3，捕获中断130。
- Windows/Linux兼容磁盘空间检查（Node fs.statfs），本suite固定PLAYWRIGHT_BROWSERS_PATH，子进程不继承开发WS/COMPOSE/DSN/模型Secret。日志先脱敏再发布、UTF8流解码、有界；采证失败不能环境passed/exit0。报告输出目录先准备。
- tools容器每次run显式唯一name/owner标签并记入账本，防止强停遗留；新增资源创建前登记意图。资源扫描核验Engine/context、run_id+owner+登记project。标签错误拒绝删除，镜像tag与ID对应，不能全局prune。清理报告包括runtime/tmp/进程/既有资源，清理成功后再删除私有凭据。
- runTools/Provider selftest仅一次；Python探测接口预计 `environment_probe.py --json --api-url http://api:8000 --frontend-url http://frontend:5173`（以实际--help确认）；fixture接口 `prepare-fixtures.py --output /outputs/inputs --manifest /outputs/fixture-manifest.json`。Provider协议脚本 `provider-selftest.py --base-url http://provider:8080 --control-url http://provider:8081`。
- PG专库验证：从已核验postgres容器读 `SELECT system_identifier FROM pg_control_system()`，传 `db-admin.py create|inspect|drop --database sesrag_session_probe_<run后8位> --expected-server-id <id> --expected-namespace <project>`。Postgres cluster_name将由根代理设为WS_TEST_PROJECT。真实创建空probe库再删除，只是环境工具检查，不执行业务probe。
- 目前八分类都planned。All/Selected planned必须退出3并产报告，不部署；未来ready分类必须真正经过独立project/context/schema/runner，不允许ready时静默跑Environment。若未来接入部分本次无法完备，明确阻止ready未支持功能而不伪通过，并报告给根代理。
- 负例自测：缺报告、非零码、超时、重复/漏/错身份case、路径越界、错误owner/Engine、采证失败仍finally、初始化失败释放锁/目录；用框架替身而非产品脚本。

不得启动Docker资源（根代理统一演练）。不要派生子代理。先写失败的最小测试、观察失败再修实现。中文简短注释。报告写 `.superpowers/test-002-runner-report.md`，说明逐项改动、真实命令/结果、未实现项/风险；最终回报简短状态与报告路径，不提交。
