# 分类测试脚本编写与接入约定

当前已接入14类脚本，逐例范围见[上层README](../README.md#任务34分类脚本与用例映射)和`manifest.json`。历史初始planned状态不代表当前状态；真实评测缺口仍planned，ready也不表示已通过。

## 协议

脚本接收`--context /reports/<分类>/context.json --result /reports/<分类>/result.json`。Python脚本在tools容器以`python /suite/specific_test_script/<分类>-tests.py`执行，浏览器脚本以Node执行；不能把任意shell命令写进manifest。工作目录为`/app`，测试工具可从`/suite/helpers`导入，Playwright从`/test-tools/node_modules`加载。每个分类在project报告目录下单独存放，Real共享语料也不覆盖上一分类结果。

输入按`schemas/context.schema.json`验证，含run/category/lane、指纹、内部地址、project引用、预算及允许操作，不含Key或DSN。必要数据库及local控制面权限仅从`/run/secrets/tools-private.json`读取。该文件不得打印、复制到结果或带给浏览器。

真实context另给`real_capabilities`；私有`/config/live-inputs.json`同步能力、full_business_scope及有效预算。Business可只补证一种能力，未选能力预算为零；需要其它能力的case必须如实blocked/not_run并保留完整报告，不得缩减manifest或宣称完整链成功。完整链及Acceptance要求四能力。tools不接收真实供应商Key；真实业务通过API/Worker请求，不能直调供应商冒充验收。前端源码/依赖和contracts位于`/app/frontend`、`/app/contracts`，后续质量脚本可离线调用；此准备不代表已执行质量用例。

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

先完成正式用例文档与脚本，然后在manifest补显式case/需求/测试点、预算和依赖，审核后改ready。先执行Selected验证；All要求全部12个local分类ready且报告完整。真实Business/Acceptance依计数资料等门禁单独接入；本阶段只使用正式test-cases.md已有编号；不回填任务5结果。


任务3～4统一使用Python分类入口及`helpers.case_runner.run_category(CASES)`；浏览器由workspace-tests.py/quality-tests.py调用`helpers/browser-cases.mjs`。各case中文注释与编号追溯；断言/准备失败均逐例保留，禁止零断言通过。跨例共享的PG模板仅含迁移/Profile，不含业务事实，每例结束销毁派生库，分类finally销毁模板。ENV通过总入口LifecycleAudit在宿主执行，tools没有Docker socket。

## 本次校审后的关键约定

浏览器辅助器经工具容器loopback反代生产前端，核真实安全上下文后操作，不给产品添加crypto替身。UI结果是生产组件/store与受控同源响应的投影证据，后端正式API/PG行为由相应分类独立验证。

真实Profile输出上限必须≤本次计划；配置字节校验/hash冻结/复制后核验保持一致。LiveCase的document_chunks预留是保守上界，办公为50000、txt/md为正文字符数与50000的较小值，预算不足在提交前blocked；不得以固定128片掩盖真实向量请求。未知提交不退款、不自动整轮重跑。

代码审批和试跑已完成，产品失败及真实受限项见[任务3～4记录](../任务3-4实施与试跑记录.md)。任务5才回填正式结果，任务6才形成正式报告。

2026-11-13：performance-tests.py增加EVAL_001独立原源20+5标注审计，当前3例（001/007/008）；EVAL_002/003/006保持真实评测暂缓。当前可验证共240例（230分类函数＋10 ENV），8暂缓；此前239/9统计是历史。

修复后正式结果：完整本机220例及ENV十例通过，真实八个办公目标／预算例通过；248例采用239通过、9受限。上述“任务5才回填／任务6才形成报告”为历史接入计划，现已完成回填和报告，证据与限制见[测试报告](../测试报告.md)及[缺陷报告](../缺陷报告.md)。
