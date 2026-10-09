# 固定隔离子场景与运行器故障哨兵

这些文件由总入口的固定 `-HarnessScenario` 白名单选择，不进入正式21分类manifest。正式产品用例及映射见[分类README](../../specific_test_script/README.md)。不接受任意manifest路径，不把本目录故意构造的passed报告算作产品通过。

| 场景/文件 | 用途及使用阶段 |
| --- | --- |
| `not-ready.json` | 两个未接入占位分类，LIFE_001/002/003验证全新环境、all/subset未就绪和正常释放。 |
| `disabled.json` | 无可执行分类，验证not_ready，LIFE_004/008诊断KeepContainers及恢复。 |
| `protocol.json`、`life-*.mjs` | LIFE_004故意生成合法、无报告、空passed、错run/category、非零、blocked、超时/子进程树；最终缺脚本用于安全失败。 |
| `missing-script.json` | enabled但目标文件故意不存在，验证失败不误通过。不存在的`life-absent.mjs`不是漏交。 |
| `life-probe-core.mjs` | 上述工具哨兵共享参数/报告适配，不调用业务API。 |
| `nested-recovery.json`、`life-nested-deferred.mjs` | LIFE_006部署deferred子环境并登记，再故意超时；父运行器须按精确身份回收，不能依赖被杀分类的finally。 |
| `doc-limit.json`、`doc-limit-probe.mjs` | 薄入口调用正式分类目录的DOC_003真实HTTP10MiB边界，独立新PG/卷，停止Worker避免大索引，环境由同一入口销毁。 |
| `rag-empty.json`、`rag-empty-probe.mjs` | 薄入口调用RAG_003真实空库正式Run，独立PG/owner；不删除主环境文档伪造空库。 |

disabled的不存在脚本不会执行。子环境复用本轮源码镜像但不复用数据库/上传卷；所有nested身份登记父runtime，分类finally及父清理精确恢复。主入口硬杀仍需按保存run_id手动恢复，不承诺自动finally。真实过程、原报告和清理记录都按新run_id保留。
