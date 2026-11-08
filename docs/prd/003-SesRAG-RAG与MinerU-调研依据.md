# PRD-003：RAG 与 MinerU 接入调研依据

- 编号：003-RESEARCH；项目版本：v0.3；性质：PRD 编写依据，不是实施方案或验收结果。
- 初次调研日期：2026-10-25（当时客户端时区 America/New_York）；第9节模型协议补充：2026-10-29、第10节文本输入范围复核及第11节办公格式复核：2026-10-30（后两次均为Asia/Shanghai）。
- 研究范围：MinerU 官方云端文档解析 API、其链接的官方输出格式说明、pgvector 官方检索与维度约束、百炼qwen3.7 Embedding／rerank公开协议，以及txt/md本地、七种办公格式云端输入／文本输出的边界；项目代码基线和产品承诺由配套 PRD 确认。
- 验证边界：只执行官方公开页面、官方 GitHub 文件的只读 HTTP GET；未登录、未申请或读取 Token、未上传任何文档、未提交解析任务，也未做带凭证真实调用。下文“已核实”指文档事实，不表示云端接口已在本项目联调成功。
- 配套 PRD：[003-SesRAG-RAG检索增强与MinerU接入-PRD.md](003-SesRAG-RAG检索增强与MinerU接入-PRD.md)；2026-10-29关联[ADR-003实施方案](../adr/003-sesrag-rag-mineru-implementation-plan.md)，方案已接受但待实施。本调研不变更上一轮测试工程。

## 1. 一级来源与证据定位

| 来源 | 本次读取和证据范围 |
| --- | --- |
| [MinerU 文档解析接口文档](https://mineru.net/apiManage/docs) | HTTP 200，页面服务端渲染正文可读。定位：“模式对比”“精准解析 API”“创建解析任务”“获取任务结果”“本地文件批量上传解析”“url 批量上传解析”“批量获取任务结果”“常见错误码”“Agent 轻量解析 API”。本页是动态在线文档，本调研记录日期而不宣称其永久不变。 |
| [MinerU 官方输出格式页面](https://opendatalab.github.io/MinerU/reference/output_files/) | 云端 API 的 `full_zip_url` 字段说明链接至此。定位：“Entrypoint capabilities”“Intermediate JSON”“Saved files, ZIP, and assets”。该页面当前描述开源 MinerU 4.0，不等于云端 v4 API 输出版本。 |
| [官方输出说明固定版本](https://github.com/opendatalab/MinerU/blob/3103e954a46414cc61ab452a6dc3f6a0a61ebe30/docs/en/reference/output_files.md) | 官方仓库 `opendatalab/MinerU`；本次获取到该文件最近一次提交 `3103e954a46414cc61ab452a6dc3f6a0a61ebe30`，提交时间 2026-09-20T14:20:44Z。固定版本便于复查，不代表云端部署使用此提交。 |
| [pgvector 官方仓库](https://github.com/pgvector/pgvector) | 定位README的“Querying”“Indexing”“Filtering”“Reference”部分；核对精确/近似检索、分数、过滤与向量维度限制。未验证本项目部署扩展版本。 |

## 2. 云端 API 的已核实事实

### 2.1 精准 API 与 Agent 轻量 API 不能混用

官方“模式对比”将两种产品明确区分：[API 文档](https://mineru.net/apiManage/docs)。

| 维度 | 精准解析 API（v4） | Agent 轻量解析 API |
| --- | --- | --- |
| 身份 | `Authorization: Bearer <Token>`；Token 在 API 管理页面创建。 | 免登录、无需 Token，按 IP 限频。 |
| 输入上限（文档当前值） | 单文件不超过 200 MB、200 页。 | 不超过 10 MB、20 页。 |
| 提交 | 单 URL、批量 URL，或先申请签名上传 URL 后 PUT 本地文件。 | URL 与文件提交为独立入口，每次单文件。 |
| 输出 | 结果 ZIP，默认 Markdown 与 JSON；可选额外导出格式。 | 仅 Markdown 链接。 |
| 模型 | `pipeline`（默认）、`vlm`（页面推荐）、`MinerU-HTML`。 | 页面概述称固定轻量 pipeline；不承诺获得精准 API 的结构化输出。 |

**对本项目的建议，而非官方保证**：本轮若需要结构化块、页码与证据定位，应以带 Token 的精准 API 为接入基线。不能在 Token 不可用时悄悄切免登录 Agent API，然后仍宣称同等能力。Agent 轻量 API 的开头概述与部分参数表对表格/公式能力也有表述差异，不宜把它当精准版的无成本兼容替代。

### 2.2 已确认的异步接口与步骤

以下地址和行为均来自[官方 API 文档](https://mineru.net/apiManage/docs)对应接口小节；正式实现须核对 HTTP 状态与响应 `code`，不能只判断 HTTP 200。

| 输入方式/阶段 | 官方接口与关键字段 | 说明 |
| --- | --- | --- |
| 单 URL 提交 | `POST https://mineru.net/api/v4/extract/task`；JSON 包含 `url` 和解析选项；成功返回 `data.task_id`。 | 该入口**不支持直接上传文件**。URL 必须能被云端访问；官方特别提示 github、aws 等境外 URL 可能因网络限制超时。 |
| 单任务查询 | `GET https://mineru.net/api/v4/extract/task/{task_id}`。 | 返回状态、进度；完成时给出 `full_zip_url`，失败时给出 `err_msg`。 |
| 本地文件申请上传 | `POST https://mineru.net/api/v4/file-urls/batch`；`files` 中包含 `name`，可选 `data_id`、`is_ocr`、`page_ranges`；公共解析选项在外层。 | 返回 `data.batch_id` 和 `data.file_urls`；示例按输入文件顺序对应 URL。 |
| 上传本地文件 | 对申请得到的 URL 执行 `PUT`，请求体为文件字节。 | 文档说明“无须设置 Content-Type”；该步骤不是往创建任务接口发 multipart，也不应把云端 API Token 转发到签名存储 URL。上传完成后云端自动扫描并提交解析，**不再调用一次创建任务接口**。 |
| 批量 URL 提交 | `POST https://mineru.net/api/v4/extract/task/batch`；`files` 内为 `url`、可选 `data_id` 等。 | 返回 `data.batch_id`。外部 URL 输入是否向用户开放属于 SesRAG 产品安全决策，不由此接口的存在自动授权。 |
| 批量状态查询 | `GET https://mineru.net/api/v4/extract-results/batch/{batch_id}`。 | `data.extract_result` 为文件结果数组，带 `file_name`、`state`、可选 `data_id`、进度、ZIP URL 或错误。批次内文件可能分别处于成功、进行中和失败，不能把一项完成当全批成功。 |

API JSON 包装为 `code`、`msg`、`trace_id`、`data`；文档成功示例 `code=0`、`msg="ok"`。`trace_id` 是上游请求关联信息，不替代本项目的解析任务或索引批次身份。

### 2.3 状态、进度、参数和身份边界

根据[“获取任务结果”“批量获取任务结果”](https://mineru.net/apiManage/docs)：

- 单任务状态：`pending` 排队、`running` 解析中、`converting` 格式转换中、`done` 完成、`failed` 失败；批量本地上传还包括 `waiting-file`（等待上传、排队提交解析）。
- `running` 时可给 `extract_progress.extracted_pages`、`total_pages`、`start_time`；不是所有状态都有进度，不能把无进度解释为零页成功。
- `done` 仅表示上游解析完成，不表示 SesRAG 已安全下载、验包、归一化、切片、向量化并发布检索索引。
- `data_id` 是调用方业务身份回传，允许字母、数字、下划线、短横线、英文句号，最长 128 字符。官方描述**没有承诺同 `data_id` 重复提交自动去重、幂等创建或恰好执行一次**；本项目不能将它当官方 Idempotency-Key。
- `model_version` 必须在本项目提交时显式固定；HTML 要用 `MinerU-HTML`，其他文件选择 `pipeline` 或 `vlm`。不能依赖未传时的默认值永远不变。
- 精准 API 参数表列出 `is_ocr=false`、`enable_table=true`、`enable_formula=true`、`language=ch` 为当前默认；只对 `pipeline`/`vlm` 有效。`vlm` 下 `enable_formula` 特别说明只影响行内公式解析。默认值不等于识别准确率或无损还原保证。
- `page_ranges` 为一基页码输入，支持逗号、闭区间和负索引，例如 `2,4-6`、`2--2`。本项目若不准备完整支持此语法，可限制为明确的安全子集并校验，不默默改变用户范围。
- 默认导出 Markdown、JSON；`extra_formats` 只支持 `docx`、`html`、`latex` 一个或多个，对 HTML 源文件不适用。本轮 RAG 不必为额外导出格式增加产品入口。
- URL 提交参数还有 `no_cache`（默认 false）、`cache_tolerance`（默认 900 秒）；这是云端 URL 内容缓存策略，不等于本项目文档版本或索引一致性保证。不可变上传字节/hash 与本项目候选批次仍需独立记录。

## 3. 限额、有效期和官方文档歧义

| 条件 | 官方页已读事实 | PRD/实施时应如何使用 |
| --- | --- | --- |
| 文件大小/页数 | 精准版说明为 200 MB、200 页。 | 这是上游当前上限，不要求本项目必须开放到上限。MB 与 MiB 不应擅自等价；本项目应另有明确字节限制，取两端允许值中的更严格值。 |
| 批次数量 | 页首对比表写“≤200个”，但“本地文件批量上传解析”和“url批量上传解析”的具体注意事项均写“单次申请链接不能超过50个”。 | 记录官方页内部不一致。未获进一步官方确认前按**最多50个/请求**的保守值设计适配器，并允许更小本地限额；不将200写成验收前提。 |
| 最高优先级页额度 | 每账号每日 1000 页最高优先级解析额度，超过后优先级降低。 | 不能翻译成“每天只能处理1000页”或“1000页以内固定延时”。没有查到固定完成时限或生产SLA。 |
| 其他任务额度 | 错误码列出每日任务上限、HTML额度不足，但该小节没有给出可长期依赖的账户数值。 | 账户权限/配额以真实服务和账户为准；不能把无凭据文档调研当已确认足额可用。 |
| 上传 URL | 申请的文件上传链接有效期24小时。 | 只适用于上传URL；任务身份及已上传字节需持久记录，过期后按阶段处理。 |
| 结果 ZIP URL | 文档给出 `full_zip_url`，本次读取没有查到明确的下载链接有效期或结果保留期限。 | **不能将上传URL的24小时套到下载URL上**；应尽快安全物化所需结果，下载失效要可诊断，未确认前不承诺远端永久可取。 |
| API QPS/轮询频率 | 精准版正文没有给出可确认的固定QPS或统一轮询间隔。Agent轻量版明确IP每分钟有限额、超限HTTP429，但未给可依赖数值。 | 本项目采用可配置、有界退避/轮询与总截止时间；这属于自有控制，不是假称官方推荐固定秒数。 |
| 支持格式 | 精准版概要列PDF、多种图片、Doc/Docx、Ppt/Pptx、Xls/Xlsx；请求参数还列HTML（需专用模型）。错误码说明的扩展名列表比概要短。 | 产品范围以PRD明确白名单为准，不自动把全部上游格式开放；对实际使用的格式、模型和输出样本单独联调。 |

本节事实均来自[官方 API 文档](https://mineru.net/apiManage/docs)“模式对比”和对应具体接口注意事项，均是2026-10-25时点快照，非本项目对未来服务政策的保证。

## 4. 输出结构、定位与版本漂移

### 4.1 云端文档明确说明的结果

在[API 文档](https://mineru.net/apiManage/docs)单任务/批量结果的 `full_zip_url` 描述中：非HTML ZIP 的 `full.md` 为Markdown；`layout.json` 对应中间处理结果（middle.json），`*_model.json` 为模型推理结果，`*_content_list.json` 为内容列表。HTML源文件的结果不同，`full.md`为Markdown，`main.html`为提取正文HTML。

这不等于本项目可以只读 `full.md` 就可靠重建每个Chunk的页码和坐标。Markdown为展示/文本语义，原始页/块身份、标题层级、表格/公式与资产关联应从**已识别并验证的结构化结果**提取。缺失来源定位不能凭Chunk序号补造。

### 4.2 官方输出页与云端说明并非同一稳定契约

[当前官方输出页](https://opendatalab.github.io/MinerU/reference/output_files/)及[固定提交的原文](https://github.com/opendatalab/MinerU/blob/3103e954a46414cc61ab452a6dc3f6a0a61ebe30/docs/en/reference/output_files.md)已描述开源MinerU **4.0**：

- 明确提醒区分入口能力：“Remote output availability is defined by the remote service.” `mineru parse --json`也不是MiddleJson。
- 其MiddleJson/ModelJson使用序列化键 `schema`、`schema_version`，例如 `docvortex.middle`、协议 `2.0`；`pages`内的 `page_idx` 为**零基原始页索引**，与一基CLI页范围不同。
- `ParseResult.save(writer)` 的当前文件为 `markdown.md`、`middle_json.json`、`structured_content.json`、`images/`，有原始模型结果时还有 `model_output.json`。这与云端API小节的命名不完全一致。
- `metadata.producer.version`、解析模式、结构化内容和资产有各自语义；不能只凭一个版本号或文件名判断整个JSON模型。旧 `pdf_info`、`_backend` 等不是当前4.0协议的一部分，历史包不自动迁移。

**本项目需求建议**：ADR应固定真实云端v4结果样本和适配契约，明确接受的文件/结构版本及归一化规则；有版本时按版本识别，无版本的云端包按严格的已确认结构识别；未知结构明确失败，不能把开源4.0文档字段强套云端v4。页码归一化必须保留原始页索引和映射，只在对应输出契约已验证时从零基转产品一基页码；无可靠geometry/页码时明确缺失，不能声称精确页内定位。结构化中间模型、简单内容列表和Markdown不是可互换的同一对象。

图片或表格资产路径应依实际包内引用解析，不拼造文件名或向量化原始二进制。图像语义Embedding/视觉问答是否实施须独立定界；“能解析图片及其OCR”不等于实现多模态RAG。

## 5. 错误、恢复和安全边界

### 5.1 官方已列错误语义

[“常见错误码”](https://mineru.net/apiManage/docs)列出Token错误`A0202`、过期`A0211`；参数错误`-500/-10002`；服务异常`-10001`；文件类型/读取/空文件/大小/页数`-60002～-60006`；模型不可用`-60007`；读取超时`-60008`；队列已满`-60009`；解析失败`-60010`；未上传/任务不存在/越权`-60011～-60013`；运行中任务暂不支持删除`-60014`；转换失败`-60015/-60016`；重试上限`-60017`；每日任务/HTML额度不足`-60018/-60019`等。

这些是上游错误，不应直接成为未经清洗的浏览器响应；本项目需保存稳定分类、安全摘要和可关联trace。文件确定错误、认证和配额问题不能与临时网络故障共用无限重试。官方公开小节未给出请求幂等/提交结果未知时可无副作用重试的承诺；响应丢失时须区分“尚未取得上游身份”和“已有task/batch可继续查询”，不能靠重复提交伪造恢复成功。此处只是产品恢复风险识别，具体策略由ADR确定。

### 5.2 回调事实与本轮推荐

[官方回调参数表](https://mineru.net/apiManage/docs)明确支持HTTP/HTTPS callback，要求POST、UTF-8、application/json、`checksum`和`content`；checksum按`uid + seed + content`计算SHA256，seed由调用方设置，使用callback时必填。接收方返回200视为成功，否则最多重推5次，最终不成功后不再推送。官方示例中的`http://127.0.0.1/callback`不是云端可以访问任意本机localhost的保证。

**本项目建议**：本机Compose初版优先有界轮询，不要求暴露公网回调；若后续启用回调，必须验签、校验上游身份及本地归属、防重放和重复通知。通知不是本地索引已发布的事实来源。本次没有带凭证测试回调真实性或连通性。

### 5.3 SesRAG必须另行实施的控制（不是MinerU文档的保证）

- 开启云端解析前明确文档会离开本机、由何服务处理，取得符合产品用途的用户授权；密钥只在服务端解析，不进入Message、Event、前端、默认日志或普通元数据。调研未确认服务端隐私/数据保留/地域/商用许可条件，不能替服务作此类承诺。
- Token只发往受控MinerU API origin；预签名上传、结果下载和重定向使用独立允许列表、协议/host/IP/端口校验；拒绝本地/私网/metadata等危险目标，不向异域转发Bearer。官方返回URL也不能默认免检。
- ZIP成员检查绝对路径、`..`、符号链接、重复冲突、个数、压缩/解压大小和压缩比；JSON/Markdown/HTML与内嵌资产均是不可信输入。下载超时、截断、畸形、恶意压缩包不能变成“零Chunk索引成功”。
- 上游`done`后还需本地下载/验包/归一化/切片/Embedding与索引事务；失败候选不能污染当前可检索批次。Worker租约变更不等于上游任务取消，外部远程任务与本地Task身份必须区分。
- 现有资料未确认可用于本轮的“取消远端解析”API；不能把用户取消本地处理宣称为撤销云端上传、计费或立即停止远端工作。文档中“运行中任务暂不支持删除”的错误更不能当作已提供取消能力。

## 6. PRD应写明的外部前提与验收口径

1. 精准API真实联调依赖有效Token、账户权限/配额、API与上传/结果存储域网络可达，以及合成且允许上传的真实输入；当前调研未满足或验证这些条件。
2. 使用本机假服务/录制的安全fixture可验证异步状态、重试边界、解包安全、归一化与索引发布；不能替代一次真实MinerU云端端到端调用，也不能证明模型解析质量。
3. 真实联调应覆盖PRD实际开放格式（至少有可复制文本与扫描输入），保存安全的配置身份、任务关联、页/块/文本/资产对照与明确成功或受限原因；不得用本地替代解析器结果记为MinerU通过。
4. 支持上限、外部配额、解析延迟、输出版本是外部可变条件；PRD采用明确本地限制与兼容边界，ADR设计适配和退出条件，不把官方营销准确率或“最高优先级”翻译成无依据的生产指标。
5. 只做本轮独立需求与后续独立验收；不通过扩展上一轮`tests/sesrag-persistent-session-workspace-test`来承担本轮验收。

## 7. 调研自检

已核对本地上传与URL提交的不同接口、异步状态、成功包装、24小时仅属于上传URL、批量50/200歧义、模型与OCR/表格/公式选项、输出页/云端命名差异、未知配额/结果保留/取消能力。未用第三方博客补造事实，未发起带凭据调用或把静态文档阅读写成成功验收。以上技术建议只用于PRD边界确认，不代表本项目已经实施相应安全、状态机或RAG能力。

## 8. pgvector 官方约束补充

本节依据 [pgvector 官方仓库 README](https://github.com/pgvector/pgvector)，核对时页面显示提交身份 `3210babc7667e4742484fb40347b73cc0171272c`。仅核对上游能力和限制，未连接或验证本项目当前数据库中的扩展版本、索引和执行计划。

| 官方事实 | 本轮产品边界建议 |
| --- | --- |
| 默认采用精确最近邻搜索；近似索引以召回损失换取速度，可能改变返回结果。 | 本机初版可先使用有明确范围条件的精确向量查询。官方所说精确搜索的“perfect recall”是算法候选召回口径，不是RAG问答质量或引用正确率保证。 |
| `<->` 为L2距离、`<=>` 为余弦距离、`<#>` 为负内积；余弦相似度可表示为 `1 - cosine distance`。 | 检索结果需保留距离度量、原始分数语义及后续重排分数，不能把不同距离和分数直接混排或统称为相似度。 |
| `vector` 存储最多16000维有限单精度元素；HNSW/IVFFlat 的 `vector` 索引最多2000维，`halfvec` 索引最多4000维。 | 不将存储上限误写成近似索引上限。EmbeddingProfile必须固定模型、版本、维度和距离度量，具体模型维度与部署版本在ADR中确认；旧384维基线不能与新profile向量混查。 |
| 近似索引的过滤通常在索引扫描后应用，可能导致返回数少于所需数量；0.8.0起的迭代扫描可继续扫描，但仍受 `hnsw.max_scan_tuples` / `ivfflat.max_probes` 等边界限制。 | 租户、知识库、文档当前版本/profile等过滤必须成为真实查询条件，不能只在前端过滤。若后续启用共享ANN索引，需独立验收过滤后召回、数量不足和跨租户数据分布的影响，不能把启用索引等同于已保证相同检索结果。 |

保留PostgreSQL/pgvector、初版精确检索、后续再评估近似索引，属于与当前依赖兼容的演进方向；是否采用及其详细迁移、维度存储和索引策略仍由对应PRD/ADR明确，不由本调研附件替代决策。

## 9. 实施前模型协议核对（2026-10-29，Asia/Shanghai）

本节补充本轮已准备的百炼 `qwen3.7-text-embedding` 与 `qwen3.7-text-rerank` 的公开协议依据。仅对下列官方公开页面、同页 Markdown 版本与文档索引执行无凭据 GET；未读取配置中的密钥，未调用模型，未核验账户授权、额度、网络可用性或实际模型响应。配置准备不等于联调完成。

### 9.1 来源和已读范围

| 官方来源 | 本次核对范围 |
| --- | --- |
| [同步接口 API 详情](https://docs.bailian.console.aliyun.com/zh/model-studio/text-embedding-synchronous-api)／[同页 Markdown](https://docs.bailian.console.aliyun.com/zh/model-studio/text-embedding-synchronous-api.md) | HTTP 200；“模型概览”“OpenAI兼容”的请求体／响应、“DashScope”的 text_type／dimension／instruct。 |
| [文本排序 API](https://docs.bailian.console.aliyun.com/zh/model-studio/text-rerank-api)／[同页 Markdown](https://docs.bailian.console.aliyun.com/zh/model-studio/text-rerank-api.md) | HTTP 200；模型能力表、HTTP endpoint、input／parameters、qwen3.7 示例、output.results、输入限制与相对分数说明。 |
| [官方文档索引](https://docs.bailian.console.aliyun.com/llms.txt) | HTTP 200；搜索与本轮两模型相关的 token 计数／tokenizer 资源。未找到足以确认两模型独立计数接口或精确离线 tokenizer 的资料。此结论只是本次检索范围，不能扩张为官方绝无此类能力。 |
| [Embedding 模型控制台](https://bailian.console.aliyun.com/cn-beijing/model/market/detail/qwen3.7-text-embedding)／[Rerank 模型控制台](https://bailian.console.aliyun.com/cn-beijing/model/market/detail/qwen3.7-text-rerank) | 无凭据 GET 为 HTTP 200，但公开正文只提供控制台加载壳；没有从中核实更多模型参数或账户可用性。不将“页面可打开”写成模型已开通。 |

### 9.2 Embedding：明确选择协议，不混入另一协议参数

| 核实项 | 官方事实与本轮使用边界 |
| --- | --- |
| 已列模型 | 上述官方 API 文档已明确列出 `qwen3.7-text-embedding`；北京概览表列最多 20 行、每行最多 128000 Token。它不是仅在用户配置中出现的未知模型名。 |
| OpenAI 兼容入口 | `POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/embeddings`；`{WorkspaceId}` 为受控业务空间配置，不是由浏览器输入的任意 host。请求头为 Bearer API Key；主体 `model`、`input`（本轮只需 string 或 string 数组）、可选 `dimensions`、`encoding_format`。 |
| 本轮可明确选定的维度 | 模型表和参数说明都确认默认 1024；显式发送 `dimensions=1024` 可消除默认值漂移。模型概览表还列 2560、2048、1536、768、512、256，但通用 dimensions 参数说明又把 2048／1536 标作仅 text-embedding-v4，并列 128／64，存在官方页内部表述差异。不能把这些所有值写成已真实验证；本轮先采用两处一致的 1024。2560／2048 还超过本轮 PRD 的 2000 维产品范围。 |
| 返回身份 | `data[]` 包含 `embedding`、`index`、`object`；`index` 为原输入数组位置。应按 index 映射，而非假定返回顺序；数量、唯一性、完整索引范围、维度和有限值均需本地校验。`encoding_format="float"` 避免本轮新增 base64 解码歧义。 |
| 另一套 DashScope HTTP | 入口为 `/api/v1/services/embeddings/text-embedding/text-embedding`，使用嵌套 input／parameters。官方只在这一协议下说明 `parameters.text_type=query/document`、`dimension`（单数）及 `instruct`。`text_type` 默认 document；query 的 instruct 可用于查询说明。 |
| 避免臆造 input_type | 本次 OpenAI 兼容段未列 `input_type` 或 `text_type`。不能因 query/document 是 RAG 逻辑角色，就往兼容请求随意加入 `input_type`，也不能把 DashScope 的 `dimension`、`text_type` 原样塞入兼容请求。若后续改选原生 DashScope 协议，必须建立独立适配／Profile 版本，冻结 query/document 角色和 instruct。 |
| Token 与批次 | 20 是每次请求最大输入行数；128000 是该型号单行限制，不等于可以无界入库或多行总资源无上限。官方 usage 的 total_tokens 按实际模型 tokenizer 统计，明确可能与自行估算字符／词数不一致。本轮可以使用更小的字符／UTF-8 字节配额、批次和请求体上限。 |

### 9.3 Rerank：原生 DashScope HTTP，分数不能跨请求混排

官方为本轮型号给出的 HTTP 入口为：

```text
POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank
Authorization: Bearer <服务端运行时读取的凭据>
Content-Type: application/json
```

请求结构是 `model="qwen3.7-text-rerank"`，`input={"query": "...", "documents": ["..."]}`，`parameters={"top_n": N, "instruct": "Given a web search query, retrieve relevant passages that answer the query."}`。这是官方 qwen3.7 示例的结构；不是 OpenAI embeddings 请求，也不是在准备好的 `/compatible-mode/v1` 后拼接 `/reranks`。若配置文档只准备了兼容 base，实施时须为原生 rerank 单独配置经校验的 endpoint，不能据此判断服务本身缺失或猜测另一个路径。

| 核实项 | 官方事实与本轮使用边界 |
| --- | --- |
| 支持型号 | model 参数明确列出 qwen3.7-text-rerank、qwen3-rerank、gte-rerank-v2、qwen3-vl-rerank；本轮只使用 qwen3.7 文本路线，不自动开放多模态 URL。 |
| 文档数量 | qwen3.7 概览表最多 500 个文档；本轮 PRD candidate_k 最多 100 更严格。`top_n` 默认返回全部，大于输入数时返回全部；本轮可显式设为实际候选数以核验完整候选身份，再本地选 top_k。 |
| 输入 Token | qwen3.7 表列单条最大 30000 Token、请求总量 120000（建议）；通用 query 参数又写查询不超过 4000 Token。保守按 query ≤4000 使用，不把 30000 套到 query 上。单条超限返回 HTTP 400，文档明确“不截断输入内容”。 |
| 请求总量公式 | 官方定义为 `Query Tokens × Document 数量 + Document Tokens 总和`；不能只计算 query 一次。120000 标“建议”与其说明“不得超过请求最大输入”有措辞差异，本轮应采用不高于该值的显式自有硬预算，而不测试外部最大可容忍值。instruct 的实际开销也需校准／留余量。 |
| 输出 | 成功主体有 `request_id`、`output.results[]`、usage；结果项 `index` 指原 documents 位置，`relevance_score` 在 [0,1]，由高到低排列；qwen3.7 还返回 `usage.prompt_tokens`。失败可含 code/message，必须检查而非只看 HTTP 200。 |
| 分数意义 | 官方特别说明该分数是当前请求内的相对分数，不能作为跨请求比较的绝对值。应单次发送本次完整候选集合；资源预算不足时采用显式有界候选文本截取或失败，不能把多批重排分数混排再声称是同一次全局排序。dense cosine 与该分数也不能相加。 |
| return_documents | 文档列此参数默认 false，并把支持型号列为 gte-rerank-v2／qwen3-vl-rerank／qwen3-rerank，没有列 qwen3.7。官方 qwen3.7 请求／响应示例不依赖此参数。本轮不发送它，不要求上游回传文档原文；用本地候选 index 映射来源。 |

### 9.4 输入计数、模型修订与真实验收限制

本次两篇官方协议页未给 qwen3.7 两型号可直接复用的独立 Token 计数端点，也未给足以证明与在线部署相同的离线 tokenizer／词表修订。Embedding 页只解释响应 usage 为模型实际分词结果。因此，不能把现有生成模型的 tiktoken、字符数或 UTF-8 字节数写成这两个模型的精确 Token 计数。

实施方案可以选择更保守的本轮字符／字节配额及带版本的输入计数策略，在启用真实 Profile 前用合成短输入、中文／英文／混合字符及边界样本校准并保留误差／服务返回记录。计数策略、截取规则和服务端硬上限必须冻结，未通过输入安全计数约定的真实 Profile 不启用。对于本地预算而言，实际超限要在请求前明确拆分／截取／拒绝，不能依赖上游静默截断；这里的配额是 SesRAG 自有约束，不是官方 tokenizer 保证。上游 usage 只有请求后才能得到，也不能代替所有前置校验。

官方型号名没有在本次页面中提供可以冻结底层权重的不可变修订标识；本轮应记录受控部署配置修订、适配协议／计数策略版本和调研日期，不伪称上游模型别名永远固定。若实际响应或探测发生不兼容漂移，须停止启用该配置并明确重建／重新校准方向，不能仅凭相同向量维度继续混用。

真实联调仍需有效 API Key、业务空间模型权限／账户额度、网络可达和允许发送的合成查询／片段。本次只核实官方公开协议，没有验证这些外部前提，也没有证明本地准备的 base、具体 workspace 或密钥可调用成功。

## 10. 文本输入范围复核与本轮范围调整依据（2026-10-30，Asia/Shanghai）

本节保留2026-10-30较早一版的公开事实和当时项目建议，非实施／调用证据。**§10.1的官方事实可参考；其“本轮边界”列及§10.2／§10.3的DOCX桥接、本地回退、PDF留后续均为已被取代的v1.1历史建议，不得按此实施。当前决策以§11和PRD／ADR v1.2为准。**当时仅无凭据GET，未读取密钥／提交解析。

### 10.1 官方原生格式支持与模型选择

| 核对项 | 官方来源与已读事实 | 本轮应采用的边界 |
| --- | --- | --- |
| 精准API支持格式 | [API文档](https://mineru.net/apiManage/docs)“精准解析API”限制表列PDF、图片、Doc、Docx、Ppt、PPTx、Xls、Xlsx；创建任务url及本地批量上传`file.name`参数进一步列`.pdf/.doc/.docx/.ppt/.pptx/.xls/.xlsx`、图片和`.html`。 | `.docx`有明确公开依据。该名单没有`.txt`或`.md`，本次没有查到其原生支持承诺；不能将产品希望支持的源格式直接抄成上游格式白名单。 |
| 本地上传文件名 | [“本地文件批量上传解析”](https://mineru.net/apiManage/docs)的`file.name`说明“强烈建议文件名带上正确的后缀名”，后缀列表包括docx、不含txt/md。 | 若产品接受txt/md并选择MinerU，必须先走明确的本地格式适配；不能只把原字节改名为`.docx`骗过扩展名检查。 |
| pipeline／vlm与docx | 同页`model_version`描述：“三个选项:pipeline、vlm、MinerU-HTML，默认pipeline。如果解析的是HTML文件，model_version需明确指定为MinerU-HTML，如果是非HTML文件，可选择pipeline或vlm”。页面推荐vlm。 | docx属于非HTML，可显式选pipeline或vlm；本次未查到docx必须固定某一个模型的特殊规则。项目应冻结所选值，并用真实docx样本联调，不能把未联调组合写成已通过。 |
| 参数适用范围 | 同页OCR／表格／公式／语言选项标为适用于pipeline、vlm；vlm的enable_formula仅影响行内公式解析。 | 这些参数说明不构成“普通文本经云端后必然切得更好”的证据，也不要求本轮引入扫描PDF或OCR验收输入。 |
| 本地文件流程 | 同页先`POST /api/v4/file-urls/batch`申请，按对应签名URL PUT真实文件字节，再查`/api/v4/extract-results/batch/{batch_id}`；上传后自动提交。 | 原生docx与合法转换docx都应沿用该流程、状态与外发安全边界，不额外创建重复解析任务。上传身份及hash必须指向实际上传的派生字节。 |

### 10.2 历史适配建议（v1.1，已由v1.2取代，不得实施）

下列是依据上游docx支持形成的**项目适配建议**，不是官方承诺或本次已经实现／联调的能力：

1. txt/md作为产品源文档仍保留原格式、原始字节／hash和不可变Document身份；选择MinerU时，使用本地受限转换生成真正的OOXML `.docx`，再交给精准API。已有`python-docx`依赖可作为实现候选，但转换器、大小限制、Markdown子集和错误处理应在ADR明确。
2. 转换版本、源hash、派生docx hash、上传文件名、源到派生段落／块映射必须进入解析过程的安全元数据。单纯换后缀不合法；云端返回的是对派生文件的解释，不能把其重新分页后的页码当txt/md原文页码。
3. Markdown转换不得联网加载链接、远端图片或资源，也不能执行内嵌HTML／代码。无损保留原文本、可支持的标题／列表／表格等结构需要明确范围；未支持语法宜以原文保留或给出限制，不能无记录地丢弃内容。转换生成物及解压资源应有明确上限。
4. 云端块回到原txt/md行区间、原docx段落／表格位置的映射应有可靠依据；无法映射时标为缺失／派生位置，或者按已冻结策略本地回退，不能凭块序号、相似文本或派生页码伪造精确源位置。
5. 本次未发现公开协议禁止合法程序生成的docx，但未提交真实文件，不能据此保证所有转换结构／模型组合可用。正式实施须用合成txt、md、docx，分别核对转换字节、上游受理、结构产物、来源映射和本地兜底。
6. “云端结构化可能改善后续Chunk切分”应是对照评测假设；用同一原始源比较本地解析和云端解析的结构保真、文本完整性、Chunk边界、来源身份及检索指标，不因云端返回更多块或格式更复杂就宣布质量提升。

### 10.3 历史本地兜底建议（v1.1，已由v1.2取代，不得实施）

官方页面提供的是当时的API规则，不保证服务长期稳定、账户永远有额度或接口永远无变化。产品可把三种源格式的本地解析设为默认，将“使用MinerU”设为显式选择，并在远端未配置、关闭、不可达或确定失败等情况下按冻结策略回到纯本地解析；这属于SesRAG自己的流程设计。

回退必须记录请求解析方式、实际解析器、原因、原云端尝试及最终产物身份；本地成功不是MinerU成功。已上传文件不会因回退而撤回，远端任务也不因本地继续而必然停止或不再计费。提交结果未知仍保留未知状态且不盲目重新提交；本地兜底不能抹掉这一风险事实。

明确取消、总截止、非法／恶意源文件、安全禁用及产物安全校验失败的处理要由ADR分别限定，不能用泛化“所有错误都忽略后本地成功”掩盖安全事故。无论采用何种回退政策，未勾选／未授权时都不得发送文档。PDF需先确认可靠的纯本地解析／恢复路线，再在未来独立PRD中重新定范围，本轮不因MinerU官方支持PDF而启用入口。

## 11. 办公格式与文本输出复核及已确认决策（2026-10-30，v1.2）

本次按显式设计讨论要求无凭据读取[MinerU官方API文档](https://mineru.net/apiManage/docs)，HTTP 200；未读密钥、上传文件或提交解析。下列是公开文档事实，不能代替真实逐格式验收。

| 核实项 | 官方原文／依据 | 对本轮的约束 |
| --- | --- | --- |
| 原生格式 | 精准API限制列“PDF、图片…、Doc、Docx、Ppt、PPTx、Xls、Xlsx”；url及本地上传file.name列.pdf/.doc/.docx/.ppt/.pptx/.xls/.xlsx。 | 七种办公格式有原生受理依据，不需要项目本地转DOCX或转PDF；图片／HTML虽可能受理但不纳入本轮。 |
| txt/md和输出 | 未列txt/md输入；“markdown、json为默认导出格式，无须设置”，“full.md为MarkDown解析结果”；extra_formats为额外docx/html/latex。 | txt/md直接本地；full.md和JSON作为办公云端结果进行安全归一化，不逆向转换文本去云端。 |
| 模型 | “非HTML文件，可选择pipeline或vlm”，默认pipeline、页面推荐vlm。 | 固定所选Profile并逐格式联调，不宣称任何组合已通过，不在错误后静默换模型。 |
| 失败 | -60002格式识别、-60003读取、-60015/-60016转换、-60010解析失败；官方可能建议手动转PDF。 | 项目不实现转换或本地回退，错误明确结束。安全网络重试只恢复同一工作，未知提交不自动重提。 |
| 位置及质量 | 公开格式支持不能证明工作表／单元格、Word分页或幻灯片身份在真实输出中完整保留。 | 用七格式样本确认协议，只有可靠位置展示；缺失明示。不承诺排版保真、Excel计算／宏或任意OCR质量。 |

已确认产品范围为九格式：txt/md本地；doc/docx/pdf/xls/xlsx/ppt/pptx原件MinerU。办公文件每次上传／重建须确认完整原件外发，MinerU不可用使办公新入库受限／失败，不影响txt/md和旧历史；无本地兜底。单文件10MiB，不新增本地PDF计页或Office转换。旧v1 DOCX写入要求升级，历史仍可读取。上述替代§10的历史项目建议，详细状态、对象、接口、预算和验收以PRD／ADR v1.2为准。
