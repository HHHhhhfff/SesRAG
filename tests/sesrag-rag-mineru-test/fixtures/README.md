# 固定数据与配置

- `manifest.json`引用`tests/fixtures/rag-v3/manifest.json`的hash；10份源输入为九格式加扫描PDF，原许可/来源保留在真源。`materialize.py`逐份校验大小/hash并复制到本run tmp，源目录只读。
- `baseline.json`声明两个虚假owner及默认Mock选择；没有用户表，不提供共享seed SQL。`helpers/baseline.py`校验声明，prepare_runtime复制到私有`/config/baseline.json`并给Compose同一owner，initialize与environment_probe再次核对；分段迁移与正式Profile导入已接入，不预填Run/Citation/active成功事实。other_owner是后续服务端权限夹具的身份参数，不代表导入了用户账号。
- `profiles.local.json`包含Mock空间/重排、本地文本及带已有逐格式协议依据的MinerU配置；`models.local.json`有Mock及local dummy HTTP/SSE生成。它们只用于工程行为。
- `profiles.real.example.json`保留真实Embedding/rerank的unverified门禁；`models.real.example.json`目前沿产品安全示例只含Mock，真实操作者需明确提供自己的合适生成配置，不能凭模板认为真实能力已启用。
- `live-plan.example.json`只有格式和预算示例，authorized=false；capabilities缺省为四能力，也可显式选择独立补证能力，Acceptance禁止缩减。未选能力不传Key且有效预算归零。私有计划/配置/Secret文件放`runtime-inputs/`，由Real参数明确指定，模板不是授权；无ready脚本不读取Secret或部署。
- `counter/evidence.example.json`定义依据/上限/边界校准材料字段，保持unverified。环境不创造官方模型计数依据，也不自动改verified。中英/Unicode边界输入由materialize生成；真实校准需独立补证。
- `counter/inputs.json`提供逐能力边界种子，`evaluation.schema.json`及`helpers/evaluation_data.py`校验25题标注格式、20+5/九格式/语言/跨片段及干扰覆盖；不包含虚构标注或实际效果结论。
- `legacy/baseline.json`明确0006旧库起点；后续compatibility通过专属case库和产品Alembic构造真实旧状态，本阶段不提前编写该类产品测试。
- `materialize.py`生成10MiB±1/空/非法编码/Unicode/跨片段/HTML及逃逸、嵌套、冲突ZIP，均有界且不可执行，输出hash清单。`local-only/`数据禁止外发。

20+5标注集、逐格式内容断言与相关范围映射仍由后续用例/评测任务补齐；10份固定源或包含20条事实不代表已具备25题评测集。


任务3～4补齐`case-catalog.json`（248例设计的身份/目标快照，不含执行结果）、`real-expectations.json`（八份固定办公输入按hash绑定的独立文本/结构预期，不从MinerU响应生成）。兼容/性能/边界专属数据由分类脚本在独立PG和scratch准备，不共享可变成功事实。20+5语义标注与真实输入计数仍须独立补齐。

2026-11-13当前补齐：`source-annotations.json`为独立20+5原源金标，`source-annotations.schema.json`为原源协议。范围是独立投影Unicode半开坐标，source/projection hash均可重算；未填任何云artifact hash。原evaluation.schema.json保持已绑定区间协议；EVAL_001原源审计可本机执行，EVAL_002/003/006仍须真实绑定与计数门禁。以上“仍待补齐”段落属于此前任务历史。
