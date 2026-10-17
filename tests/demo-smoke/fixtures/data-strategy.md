# Demo测试数据准备边界（任务1）

**编号**：001

**版本**：v0.1

**日期**：2026-10-07

**状态**：已确认不需要全局SQL种子；分类独立数据准备已在任务3接入，受限驱动另列blocked

**依据**：[测试用例](../test-cases.md)、[分类协议](../specific_test_script/README.md)、[Demo PRD](../../../docs/prd/001-SesRAG-项目Demo-PRD.md)、当前ORM及应用入口。

## 1. 结论

当前没有跨用例共享且必须先写入数据库的稳定身份/字典基线。Demo没有User/Tenant/权限账号表；owner_id为配置字符串，入口每次生成专属owner，写入runtime/context.json并透传API/Worker。业务七表初始为空，Alembic负责Schema和vector扩展，不是虚假业务数据导入。

因此本轮**不新增seed.sql或数据库导入脚本，也不挂接虚假的“数据已导入”阶段**。这不是漏做：DEP_001、RAG_003等需要全新/空库起点；全局预置Document/Task/Run会干扰数量、领取顺序、空召回和故障验收。稳定的是输入fixture和字段语义，不是所有用例复用一组可变业务记录。

## 2. 各类数据由谁准备

| 场景/用例组 | 数据与生成方式 | 本轮准备情况/后续职责 |
| --- | --- | --- |
| DEP/HLT/LIFE | 新PG卷、Schema、随机owner/project/密码 | 总入口已接入迁移和context生成，实际新库七表计数均0；不执行业务seed。 |
| TH/MSG/RUN/CAN/EVT/SSE | 各用例独立Thread/Message/Run/Task/Event | 任务3通过正式API创建；记录关联ID，不从别的用例结果借状态。Event由生产路径生成，不能直接INSERT已成功Run/Event。 |
| DOC/PAR/CHK/IDX/RAG | 固定txt/md/docx文本输入及临时边界文件 | safe fixture已接入总入口生成与FixtureDir参数，docx只在tmp生成；Document/Chunk/向量通过上传及真实Worker索引产生。 |
| RAG_003空库 | 无active Chunk的独立环境/owner数据范围 | 已通过固定rag-empty总入口场景启动全新PG，正式API/Worker完整Run；主分类关联嵌套报告，不删除其他用例文档。 |
| OWN_001双owner | A/B配置身份及独立会话/知识 | 当前无用户表可导入；O双配置API/执行者驱动尚未实现。后续真实创建，不写SQL伪装认证/RBAC，避免A任务被B owner Worker处理。 |
| WK/事务/取消竞态 | 真领取的Task、可控Provider/屏障 | E2驱动在任务3按需要实现；正常写入经生产函数。只读SQL可核对lease/generation，不能SQL更改state/seq/generation使断言通过。 |
| SEC/大小/解析错误 | 非真实敏感哨兵、精确大小/损坏编码/ZIP/XSS | 小安全输入已有；大/攻击边界数据任务3在本次tmp按需生成，不进入Git或默认原文报告。 |

任务3可抽取复用的“创建数据”函数，但每个用例返回自己专属的ID集，失败不得污染下一用例。故障/重启/删除源文件只能作用本次资源，finally恢复自己的客户连接并交由总入口销毁环境。

任务3补充：10MiB接受边界使用固定doc-limit独立新库，HTTP接受后保持Worker停止直至总入口销毁，避免普通文本生成约15420块；原文不保留artifact。生产函数保存点辅助测试采用外层事务finally rollback与容器TemporaryDirectory，不伪造业务状态；只证明登记函数，不取代上述完整HTTP目标。真实函数/配置/损坏数据驱动见specific_test_script中的同类文件，E2/O/E4完整场景仍有未满足条件。

## 3. 未来确需固定SQL时的接入条件

仅当后续新增真实稳定字典/身份表且确有跨用例固定基线时，再新增可审计小SQL及导入步骤。先说明对应PRD/Schema、固定值用途、幂等性和owner边界；由总入口在迁移成功后、相关用例执行前导入本次PG并记录结果/失败退出。若启动Worker会消费基线，必须调整本次启动顺序，不能无条件边运行边灌Task。

导入要校验project/run_id和目标库，不连接宿主开发库，不包含Secret/宿主路径，不批量预置“已测试成功”的事实；失败阻断分类、仍收证据和清理。本轮没有这种数据需求，导入脚本状态明确为“不需要/未设置”，不是“已成功导入”。
