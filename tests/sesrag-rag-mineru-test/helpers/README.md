# 测试环境共用工具

| 文件 | 职责 |
| --- | --- |
| orchestrate.py | 唯一生命周期，五模式、每分类独占project、启动/调用/结果核对/采证/销毁和汇总。 |
| common.py | 路径/原子JSON、清洁子进程环境、有界命令、进程身份与Engine身份。 |
| protocol.py | manifest完整性、ready门槛、分类结果/需求/证据hash核对。 |
| preflight.py | 工具/空间/源码指纹和无付费Real门禁，不读取秘密文档。 |
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
| lifecycle_exercise.py | 实际Docker正常/失败/超时/强停恢复演练驱动，产品not_run，不进入产品分类清单。 |

只使用本轮入口，不调用前轮suite。错误信息只保安全码，原始stdout暂存本轮tmp后脱敏入artifacts；每命令输出和时限有界。恢复账本保留在artifacts，运行凭据在runtime独立存放，成功清理不删除唯一恢复账本。
