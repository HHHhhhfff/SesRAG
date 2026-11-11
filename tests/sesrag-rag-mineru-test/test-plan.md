# TEST-003环境实施与后续接入计划

日期：2026-11-11；依据：[正式测试方案](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)。当前任务只实施环境工程，产品用例与分类脚本另行准备。

## 实施顺序

- [x] A：先冻结manifest、context/result Schema、虚假身份和Profile、目录说明。
- [x] B：准备锁定工具、独立无头Chromium、固定源校验/安全边界输入、local控制面和工厂装配、自测负例。
- [x] C：独立Compose、随机凭据和动态回环端口、分段迁移至0010、显式Profile导入、API/Worker/同源与浏览器技术探针。
- [x] D：五模式总入口、分类隔离、结果核对、脱敏/指纹/采证、所有权账本与恢复清理。
- [x] E：两轮Environment，以及真实Docker启动失败、技术子进程失败/超时、主进程强停后的真实清理演练；结果见环境记录。尚无产品分类脚本，技术子进程是生命周期演练，不能称已经执行产品分类。

技术路线：PowerShell 7仅包装Python生命周期；产品镜像使用原Dockerfile；tools镜像添加独立Node/Playwright及环境依赖。local网络internal，MinerU保持生产URL和安全检查，通过测试入口装配受控transport；真实配置使用Compose覆盖清除全部local装配，计数依据不足时无付费拒绝。PG是实际数据库，控制面只保存计划/计数/屏障，不写产品成功事实。

文件职责：`schemas/`为接入协议；`compose/`定义隔离部署；`harness/`提供local假传输及跨进程控制面；`helpers/`承接预检、初始化、探针、总编排、采证、清理和工程自测；`fixtures/`存固定数据声明、非Secret配置和有界生成器；`specific_test_script/`只提供编写规范，暂不放产品脚本。`runtime/tmp/artifacts/.cache/runtime-inputs`的保留与清理规则见README。

## 后续分类接入

manifest的12个local分类按catalog、ingestion、mineru、chunking、vectors、retrieval、execution、workspace、compatibility、lifecycle、performance、quality登记；real三个分类为real-formats、real-business、real-evaluation。本阶段全部planned、case列表为空，不能执行为passed。

1. 依据[248点矩阵](测试点设计与需求覆盖矩阵.md)设计正式用例，不沿用前轮编号。
2. 每分类单独脚本，按`specific_test_script/README.md`读取context并输出结果；共享数据只读，用例数据独占。
3. 增补manifest的case/测试点/需求关联，审核后改ready；执行Selected排错，All只能在全部local分类ready后通过。
4. 真实Embedding/rerank先独立补计数依据/校准及必要产品修复；20+5标注另行补齐。不得用测试工厂绕真实门禁。
5. 冻结同源镜像后执行本地两轮、至少一次真实业务及完整格式/效果/性能验收；产品测试、环境工程和清理分别判定。

验收记录写入`环境实施与验证记录.md`；运行原始证据在`artifacts/<run_id>/`，不把环境通过记为产品验收通过。不自动提交或推送。
