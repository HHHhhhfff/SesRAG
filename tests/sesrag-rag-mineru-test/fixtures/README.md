# 固定数据与配置

- `manifest.json`引用`tests/fixtures/rag-v3/manifest.json`的hash；10份源输入为九格式加扫描PDF，原许可/来源保留在真源。`materialize.py`逐份校验大小/hash并复制到本run tmp，源目录只读。
- `baseline.json`声明两个虚假owner及默认Mock选择；没有用户表，不提供共享seed SQL。分段迁移与正式Profile导入已接入，不预填Run/Citation/active成功事实。
- `profiles.local.json`包含Mock空间/重排、本地文本及带已有逐格式协议依据的MinerU配置；`models.local.json`有Mock及local dummy HTTP/SSE生成。它们只用于工程行为。
- `profiles.real.example.json`保留真实Embedding/rerank的unverified门禁；`models.real.example.json`目前沿产品安全示例只含Mock，真实操作者需明确提供自己的合适生成配置，不能凭模板认为真实能力已启用。
- `live-plan.example.json`只有格式和预算示例，authorized=false。私有计划/配置/Secret文件放`runtime-inputs/`，由Real参数明确指定，模板不是授权。
- `counter/evidence.example.json`定义依据/上限/边界校准材料字段，保持unverified。环境不创造官方模型计数依据，也不自动改verified。中英/Unicode边界输入由materialize生成；真实校准需独立补证。
- `counter/inputs.json`提供逐能力边界种子，`evaluation.schema.json`及`helpers/evaluation_data.py`校验25题标注格式、20+5/九格式/语言/跨片段及干扰覆盖；不包含虚构标注或实际效果结论。
- `legacy/baseline.json`明确0006旧库起点；后续compatibility通过专属case库和产品Alembic构造真实旧状态，本阶段不提前编写该类产品测试。
- `materialize.py`生成10MiB±1/空/非法编码/Unicode/跨片段/HTML及逃逸、嵌套、冲突ZIP，均有界且不可执行，输出hash清单。`local-only/`数据禁止外发。

20+5标注集、逐格式内容断言与相关范围映射仍由后续用例/评测任务补齐；10份固定源或包含20条事实不代表已具备25题评测集。
