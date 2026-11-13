# 测试环境共用工具

| 文件 | 职责 |
| --- | --- |
| orchestrate.py | 唯一生命周期，五模式、每分类独占project、启动/调用/结果核对/采证/销毁和汇总。 |
| common.py | 路径/原子JSON、清洁子进程环境、有界命令、进程身份与Engine身份。 |
| protocol.py | manifest完整性、ready门槛、分类结果/需求/证据hash核对。 |
| preflight.py | 工具/空间/源码指纹和无付费Real门禁，不读取秘密文档。 |
| live_preflight.py | Real离线分能力准入：授权/hash/配置/独立alias/计数材料/预算；未选能力不转发凭据与额度；完整链和Acceptance不降低要求。 |
| baseline.py | 读取并校验固定虚假owner/Profile声明，初始化与探针使用同一基线；没有用户表，不提供虚构seed SQL。 |
| prepare_runtime.py | 每project生成随机凭据，复制非Secret配置，准备私有env/tools文件。 |
| initialize.py | 显式调用产品Profile导入，不代写业务成功状态。 |
| environment_probe.py | 真PG迁移/扩展、Profile、Worker、同源HTTP/SSE、离线词表及Chromium技术探针；产品not_run。 |
| browser.mjs | 独立Chromium启动、同源页面/health技术检查，finally关闭context/browser。 |
| download_browser.py | 构建期按锁定Playwright清单续传官方Headless Shell/FFmpeg包，核验大小/CRC及服务端校验和，再交官方安装器解包；只保留无头浏览器，运行期不下载。 |
| fixture_admin.py | 限定专属PG和hash派生case库的创建/销毁，提供有界确定性性能输入，具体旧状态/持久化由后续用例准备。 |
| live_budget.py、evaluation_data.py | 共享逻辑预算/获准输入校验及20+5数据格式/覆盖校验，不是实际付费执行或效果评测。 |
| builds.py | 三镜像构建/ID登记、镜像内容归档hash、冻结复用及缓存软门限。 |
| evidence.py | 脱敏、有界采证、秘密扫描与相对路径/hash索引。 |
| cleanup.py | Engine/进程/资源所有权核验，精确回收及独立残留复查，允许重复Cleanup。 |
| selftest_runner.py | 工程正负自测：空/错/重复报告、路径/hash、counter守卫、控制面持久/拒绝、命令超时、错误Engine拒删；非产品用例。 |
| selftest_preparation.py | 任务1～2的基线、独立真实能力、无必要Secret拒读、授权/预算/计数守卫回归；仅合成输入，不调用供应商。 |
| lifecycle_exercise.py | 实际Docker正常/失败/超时/强停恢复演练驱动，产品not_run，不进入产品分类清单。 |

只使用本轮入口，不调用前轮suite。错误信息只保安全码，原始stdout暂存本轮tmp后脱敏入artifacts；每命令输出和时限有界。恢复账本保留在artifacts，运行凭据在runtime独立存放，成功清理不删除唯一恢复账本。


任务3～4新增：`case_runner.py`（中文逐例/异常分类/安全JSON证据/模板finally清理）、`case_environment.py`（专属PG+正式API/Worker）、`legacy_database.py`（0006旧库/真实迁移/备份夹具）、`synthetic_rows.py`（明确标识的范围规模持久化）、`live_cases.py`（正式真实业务/逐操作共享预算）、`browser-cases.mjs`（生产Vue/store的真实Chromium交互）、`environment_cases.py`（本次真实生命周期十例结果）、`audit_cases.py`（当前240可验证设计目标的函数/manifest/需求追溯门禁，EVAL_001解限前为239）。这些工具不作为产品能力或历史验收结果。PostgreSQL客户端只用于本轮专属库dump/restore。

校审后补充：common原子账本遇短时PermissionError有界重试；live_preflight以同一次有界字节读取校验/冻结配置，prepare_runtime核最终复制hash及真实输出上限；live_cases在正式上传前预留保守片数预算并采集终态安全阶段/错误码。浏览器辅助器使用loopback反代提供安全上下文，finally关闭；lifecycle_exercise只有ENV逐例审计成功才发布工程passed，失败写failed。详细验证见[任务3～4记录](../任务3-4实施与试跑记录.md)。

2026-11-13新增`source_annotations.py`（原源金标审计／真实产物唯一quote绑定）、`evaluation_metrics.py`（范围到Chunk映射与Recall/MRR计算）、`resource_observation.py`（宿主有界owned容器资源采样及局部性能汇总）、`selftest_engineering.py`（离线工程正负回归）。只读原源投影不接产品解析或本地Office/PDF回退；真实计数门禁不变，金标存在不表示真实效果通过。

`evidence_capture.py`严格识别独立不可信证据消息的可选来源编号前缀，供CTX/EVAL捕获实际模型请求；正则锚定，不从历史消息内contains推断证据。`synthetic_rows.values`只复制非Computed持久列，生成列由PG计算。
