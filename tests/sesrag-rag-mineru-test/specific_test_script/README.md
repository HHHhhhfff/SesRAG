# 分类测试脚本编写与接入约定

此处只准备接入约定，当前不包含产品自动测试脚本。分类及预计入口见上层`manifest.json`；全部初始为planned，不能算通过。

## 协议

脚本接收`--context /reports/<分类>/context.json --result /reports/<分类>/result.json`。Python脚本在tools容器以`python /suite/specific_test_script/<分类>-tests.py`执行，浏览器脚本以Node执行；不能把任意shell命令写进manifest。工作目录为`/app`，测试工具可从`/suite/helpers`导入，Playwright从`/test-tools/node_modules`加载。每个分类在project报告目录下单独存放，Real共享语料也不覆盖上一分类结果。

输入按`schemas/context.schema.json`验证，含run/category/lane、指纹、内部地址、project引用、预算及允许操作，不含Key或DSN。必要数据库及local控制面权限仅从`/run/secrets/tools-private.json`读取。该文件不得打印、复制到结果或带给浏览器。

结果写`schemas/result.schema.json`规定的JSON，必须逐一覆盖manifest声明的case_id，关联同样的PRD及测试点ID。每例有中文标题、准备/执行阶段、明确预期/实际、安全错误码、耗时、最终状态和至少一项相对证据路径/sha256。编号、run/category/lane不符、重复/遗漏case、退出0但无报告、坏hash/逃逸路径均为工程错误。

状态只用passed/failed/blocked/not_run/harness_error。预期拒绝且断言成立可passed；缺外部前提为blocked，脚本/采证缺失为harness_error。分类所有case通过才退出0；其它结果退出非零。主入口按4清理失败、2工程错误、1产品失败、3受限/范围未执行、0请求范围通过的优先级汇总，不把local通过当完整PRD验收。

## 独立性和数据

- 一个脚本只负责一个分类；多例共享固定输入只读，例间不依赖前例成功。
- 临时文档、库、Thread、键、控制面scope使用独占case前缀。每例finally解除屏障/恢复故障；失败也输出自己的结果，不能提前return漏报后续case。
- 正常业务经正式API建立；`helpers/fixture_admin.py`只允许本project的专属PG及派生case数据库。直接造旧库/性能/越owner夹具须注明证据类型，不能把造好的成功事实当业务通过。
- 代码中文注释标明对应case_id；控制台逐例输出“编号、标题、准备、动作、观察、结论”，详细证据放`/reports`，禁止完整Prompt、Key、DSN、能力URL或宿主路径。
- local用Mock Profile＋受控Port，MinerU保留生产客户端＋MockTransport；真实百炼协议负例可直调带fixture transport的适配器，只标协议模拟。不得把counter改verified以绕守卫。
- 控制面API及scope见[harness说明](../harness/README.md)。禁止开放任意执行代码、URL或宿主Docker socket。
- 图片/ZIP/容量边界等危险数据只在`/inputs/local-only`，不得进入Real计划。真实请求只能使用获准且hash冻结的安全文件与明确预算。
- 真实脚本必须在每次新逻辑操作前调用`helpers/live_budget.LiveBudget.reserve`，上传前调用`approved_input`核hash；共享账本跨三真实分类，不因未知提交退款或重开额度。逻辑预算不代表供应商实际计费。

## ready门槛

先完成正式用例文档与脚本，然后在manifest补显式case/需求/测试点、预算和依赖，审核后改ready。先执行Selected验证；All要求全部12个local分类ready且报告完整。真实Business/Acceptance依计数资料等门禁单独接入；本阶段不预造case编号或结果。
