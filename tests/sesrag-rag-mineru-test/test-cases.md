> 2026-11-13修复回归已完成：248例采用239通过、0未通过、9暂不可验证、0工程错误；本机220例完整通过、ENV十例生命周期审计通过、八个真实办公样本及预算检查通过。额度/DNS已实测解除；正式生成与真实检索/重排/效果仍缺适用计数依据。详见测试报告和缺陷报告。

# 003：RAG检索增强与MinerU接入——测试用例设计

| 字段 | 内容 |
| --- | --- |
| 编号／版本 | TC-003／2.0 |
| 状态 | 已完成修复后逐例回填与审批；计数及真实效果仍受限，完整PRD未验收 |
| 日期 | 设计2026-11-11；修复结果更新2026-11-13（America/New_York） |
| 项目／代码基线 | v0.3，分支sesrag_v0.3，HEAD b4c1708e992851a39acad4a4fdc4ec67358410e3；执行时仍需另冻结dirty源码/依赖/配置指纹 |
| 产品／决策依据 | [PRD-003](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)、[ADR-003](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md) |
| 当前实施依据 | [实施结果简要说明](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)、[实施结果调研](../../docs/pr/003-SesRAG-RAG检索增强与MinerU接入-实施结果调研.md)、[正式接口说明](../../docs/接口文档.md#8-v03-rag-与-mineru接口)及本用例逐项代码定位 |
| 测试依据 | [248点矩阵](测试点设计与需求覆盖矩阵.md)、[TEST-003](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)、[环境实施记录](环境实施与验证记录.md)、[分类脚本协议](specific_test_script/README.md)、[接入计划](test-plan.md) |
| 交付范围 | 保留原设计目标，回填修复后的实际证据；产品修复见独立记录，不修改旧PRD正式验收工程；真实受限单列 |

## 1. 用例口径、编号与覆盖边界

本文给出248个用例，按测试点的18类分别使用CAT_001、INP_001等编号，**每个用例对应一个原子测试点**。同一规则下的合法、非法、临界数据放在同用例数据组中，后续逐组输出观察结果；全部必需数据组成立才可判该例通过，不按每个输入枚举新编号。不同故障时点、业务状态、事务边界和前后端投影本已由不同点区分，保留独立用例，不为减少数量合并成模糊“全流程正常”。

248点均有设计，覆盖46项功能和12项非功能需求；覆盖关系见第4节逐点索引及第5节需求映射。已知实现差异不是不可测试的借口，仍按完整产品目标设计断言；尚无证据不能预填通过或失败。正文的“预期结果”是后续判定标准，代码依据说明当前路径，不把当前实现自动当正确答案。

2026-11-13修复回归已完成：248例采用239通过、0未通过、9暂不可验证、0工程错误；本机220例完整通过、ENV十例生命周期审计通过、八个真实办公样本及预算检查通过。额度/DNS已实测解除；正式生成与真实检索/重排/效果仍缺适用计数依据。详见测试报告和缺陷报告。 239个已测例填写复现与稳定性，9个受限例仅填写原因，另外两个字段留空。修复后本机完整回归一次，不与不同源码的修复前两轮拼接稳定性；八个真实格式各一个正确目标作业，扫描另有一次错误场景选择已记录。L/K/R/B/D是设计可验证性标签，K保留原差异追溯但实际已通过；逐例JSON与报告为执行真源。

### 1.1 当前可验证性

| 标记 | 数量 | 本次含义及后续处理 |
| --- | --- | --- |
| L | 225 | 本机可验证，含原E类10点已完成环境工程的状态迁移；独立工程和分类已接入，是否通过见实测，不据L标签推断 |
| K | 5 | 本机可验证的已知实现/契约差异；保留目标并实际复现，不能预先标blocked或采用expected-failure掩盖 |
| R | 10 | 本机存在真实调用路径，逐格式/能力需核授权、配置、网络、额度和计数适用性；本轮已显式准备所需配置并核验，实际失败／受限见逐例结果。当前分能力入口已按第3节补齐；真实材料仍须核验 |
| B | 5 | 暂不可完整验证：真实Embedding/rerank计数依据及校准尚未成立，正常守卫阻断；须先独立补资料/必要代码配置，再导入合适新版本 |
| D | 3 | 真实效果待验：20+5独立原源标注与指标已补，EVAL_001解限并通过；EVAL_002/003/006仍依赖真实计数和正式排名/回答 |

合计240例属于可验证设计范围（L/K为230例，R为10例条件验证），另8例B/D暂缓；R中REAL_009本轮因生成计数未齐而受限，故实际总受限9例。R不等于真实服务前提已齐备；10例ENV是工程验收用例，不能计入产品功能通过率。当前分类入口已接入；普通脚本缺口本轮已修并复验，不作为不可验证理由。

## 2. 公共前置、数据与证据约定

### 2.1 隔离和用例独立性

本机按[目录README](README.md)使用独立Docker Linux环境、真实PG/pgvector、Redis、API/Worker和Playwright。默认local为内部网络、dummy Key及受控Port/transport；MinerU保留生产客户端与安全守卫。涉及PG优化器/外键/触发器/多连接/租约和事务的判定必须在PG执行，SQLite不代替。UI用真实浏览器和同源API/SSE，组件/函数负例仅补充边界证据。

每例自建前置数据，以run_id+case_id+数据组标识命名其库、文档、Thread、key、控制面scope和临时文件，不依赖上一用例通过；公开固定输入只读。需旧active、历史引用或旧协议数据时，本例准备步骤独立通过正式API/迁移构造。直接SQL只用于明确标识的旧库/性能/权限/故障夹具及只读核验，不预写成功Run/Build/引用替代端到端。受约束事实不能直接损坏时，在合法故障边界或回滚事务观察数据库拒绝，不关闭生产触发器来制造“成功”。

多owner是服务端Settings/应用依赖上下文或独立受控API实例，不能靠客户端自报owner字段模拟登录；本轮无生产认证/RBAC验收承诺。并发、进程、网络和磁盘故障只针对可信账本中的本project资源，使用有界屏障/轮询/超时，不能停Docker Desktop或填满宿主磁盘。子例finally恢复配置、释放屏障、回收自建进程/文件，即使失败也继续独立子例并完整报告。

ENV销毁/强停类由现有宿主生命周期/工程演练执行并汇总；tools容器没有Docker socket，不让分类脚本获得任意宿主命令能力。宿主工程驱动已接入故障协调并有自测／演练证据，不给分类脚本任意Docker控制权。迁移和质量命令的只读源码／契约挂载已准备。

### 2.2 数据基线

| 材料 | 当前状态／本用例设计要求 |
| --- | --- |
| 九格式及扫描PDF | [本轮fixture声明](fixtures/manifest.json)校验[10份源manifest](../fixtures/rag-v3/manifest.json)，materialize按run复制；txt/md、DOCX/DOC、文本/扫描PDF、XLSX/XLS、PPTX/PPT各有独立输入，旧Office保留NOTICE和许可 |
| 虚假身份与Profile | [baseline](fixtures/baseline.json)、local Profile/生成配置；没有用户表，不需要虚构统一用户seed SQL。各例不得依赖其它例创建的库或会话 |
| 边界/恶意源及产物 | materialize和受控transport可提供有界基础；分类脚本已按具体阈值补变体并记录hash。危险内容仅local-only，不进真实外发计划 |
| 坐标与数值对照 | 行号1基、规范文本字符0基右开；原PDF页/派生页/规范block区分。score和预算用独立参考算法，不拿被测函数自身输出充当预期 |
| 旧库/并发/性能 | fixture_admin专属case库、0006基线、真实产品Alembic、确定性向量输入；分类已准备合法持久行和竞争屏障。性能≥10000有效Chunk，100次预热后≥100次测量 |
| 真实材料 | 私有runtime-inputs显式输入，逐文件hash/授权及共享预算；真实Profile计数不可假改verified，不从docs/secret自动复制或打印Key |
| 标注 | 20有答案+5无答案、九格式/中英/跨片段/预标干扰已以独立原件hash与投影区间冻结，EVAL_001通过；实际Chunk相关集合仍须按当轮产物绑定及预定义重叠规则映射，真实效果另验 |

### 2.3 判定和记录

每例应记录准备、动作、观测、预期对照及结论。证据按协议保存相对路径/hash，带case/run/category/lane、源码/fixture/Profile指纹和相关Job/Build/Task/generation/View/Context身份；数值、时点及范围可复核。默认日志/结果不带Key、Bearer、完整Prompt、签名URL或宿主私有路径。只有合成内容可在受限断言阶段完整比较，报告保必要摘要。Mock和协议模拟不证明真实效果或DNS/TLS。

预期拒绝得到正确安全码且副作用为零可判通过；缺必需数据组/观察手段为工程错误或未完成，不能按其余组通过填成功。产品缺陷为failed，外部前提缺失为blocked，脚本/采证错误为harness_error，未执行为not_run；类别/证据充分性与清理分别统计。known gap仍应跑出真实结果，不能直接预填失败。自动化“是（含人工复核）”表示操作采证可自动，依据/语义/源样本质量还需人工审核。

## 3. 受限设计、当前入口约束与后续准备

1. **B的5例**：CAT_016、VEC_009、VEC_010、RET_018、REAL_010。定位backend/application/rag_profiles.py::profile_reason和backend/infrastructure/providers/rag_registry.py；真实计数证据/适用模型与边界校准未退出。需官方tokenizer/计数或可证明上界、校准记录及必要独立修复后增版；只配置Key不能解除。影响真实入库、query、rerank及四能力链，不阻碍local Mock协议/状态测试。
2. **D的3例**：EVAL_002、EVAL_003、EVAL_006。独立原源金标已补齐；仍须真实产物绑定、当轮Chunk映射及真实计数/完整链条件。EVAL_001独立原源范围审计已移入performance/local，效果指标不因数据存在判通过。EVAL_004/005使用本例独立合成事实，不依赖整个25题集，可在本机先验证。
3. **R的10例**：REAL_001～009、REAL_011。产品路径支持独立解析/生成核验。用例设计时记录的全能力准入耦合，已在后续任务1～2通过helpers/live_preflight.py修复：LivePlan按capabilities核验所选能力，未选能力不传Key且预算归零；planned分类先拒绝。旧计划仍缺省四能力，Acceptance必须四能力，完整真实链仍需全部配置及三类计数材料。仅MinerU不要求模型counter；仅生成仍需其自身计数依据；部分成功不算完整真实闭环。当时的任务1～2工程修复本身没有执行本例；当前已接入脚本并按所选能力执行，仍须逐能力核验，不能绕守卫直调供应商冒充业务。
4. **K的5例**：MIN_022观测关联/全阶段计时；CTX_006正文编号闭环；UI_007未知重建恢复；CMP_013位置枚举说明；QLT_005前端事件严格性。原缺陷均已修复并经本轮正式目标断言通过，保留K标签追溯原差异，详见逐例结果；未自动xfail或缩小预期。
5. **原E的10点**：环境工程已于上一任务完成，现按L设计ENV_001～010，并同步矩阵当前状态。本次重新执行完整ENV生命周期审计，另最终环境补测验证新资料挂载与19项工程自测；Linux宿主和真实Ctrl+C未实测边界仍保留。

完整PRD仍受真实计数适用依据限制；额度和本机DNS已由本轮真实请求/下载确认恢复，无需为这些已解决条件重复处理。具体剩余材料与后续方向见缺陷报告，不能假填verified。

## 4. 用例目录与详细设计

以下各组索引提供点→用例的完整映射；详细条目同时反向引用测试点。归属分类已按manifest接入14个ready分类，real-evaluation仍planned；设计B/D不冒报ready。ENV用例仅工程层，不新造第16个产品分类；本轮结果整理未修改manifest。

### 4.1 CAT：知识库、配置与能力边界

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-CAT-001` | [CAT_001：知识库名称合法性](#cat_001) | L | catalog／local |
| `TQ-RAG-CAT-002` | [CAT_002：同owner名称唯一](#cat_002) | L | catalog／local |
| `TQ-RAG-CAT-003` | [CAT_003：默认库归属](#cat_003) | L | catalog／local |
| `TQ-RAG-CAT-004` | [CAT_004：知识库读取权限](#cat_004) | L | catalog／local |
| `TQ-RAG-CAT-005` | [CAT_005：库停用后的新操作](#cat_005) | L | catalog／local |
| `TQ-RAG-CAT-006` | [CAT_006：停用后的历史视图读取](#cat_006) | L | catalog／local |
| `TQ-RAG-CAT-007` | [CAT_007：库空间绑定不可变](#cat_007) | L | catalog／local |
| `TQ-RAG-CAT-008` | [CAT_008：同维异空间隔离](#cat_008) | L | catalog／local |
| `TQ-RAG-CAT-009` | [CAT_009：生成模型与向量空间独立](#cat_009) | L | catalog／local |
| `TQ-RAG-CAT-010` | [CAT_010：Profile版本内容不可变](#cat_010) | L | catalog／local |
| `TQ-RAG-CAT-011` | [CAT_011：选择停用的冻结行为](#cat_011) | L | catalog／local |
| `TQ-RAG-CAT-012` | [CAT_012：安全blocked的阶段复查](#cat_012) | L | catalog／local |
| `TQ-RAG-CAT-013` | [CAT_013：Profile安全可用性投影](#cat_013) | L | catalog／local |
| `TQ-RAG-CAT-014` | [CAT_014：真实counter未验证守卫](#cat_014) | L | catalog／local |
| `TQ-RAG-CAT-015` | [CAT_015：Parser与格式配置匹配](#cat_015) | L | catalog／local |
| `TQ-RAG-CAT-016` | [CAT_016：真实计数依据适用性](#cat_016) | B | real-business／real |
| `TQ-RAG-CAT-017` | [CAT_017：生成计数配置可用性](#cat_017) | L | catalog／local |
| `TQ-RAG-CAT-018` | [CAT_018：资源列表分页](#cat_018) | L | catalog／local |

<a id="cat_001"></a>

#### CAT_001：知识库名称合法性

- 用例编号：`CAT_001`
- 对应测试点：`TQ-RAG-CAT-001`：知识库名称合法性。验证目标：名称归一化后可稳定标识库。
- 需求来源：RAG-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；空白虚假owner，导入本地Mock Profile。
- 测试数据要求：名称空串、空白、1/80/81字符及首尾空白。
- 测试流程：
  1. 分别创建及改名。
  2. 读取详情和PG名称，核对去空白长度与拒绝后无新增记录。
- 预期结果：名称去首尾空白后必须为1～80字符；空白、超长拒绝，合法值持久化且读回一致，不以截断代替拒绝。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P1。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；创建名称边界；改名边界；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_002"></a>

#### CAT_002：同owner名称唯一

- 用例编号：`CAT_002`
- 对应测试点：`TQ-RAG-CAT-002`：同owner名称唯一。验证目标：同一owner不存在两个同名库。
- 需求来源：RAG-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个服务端owner上下文，A已有启用/停用库。
- 测试数据要求：同名创建/改名、不同owner同名、两连接同名并发。
- 测试流程：
  1. 先串行验证冲突。
  2. 用PG连接屏障并发首次创建。
  3. 统计成功数、409及最终名称唯一性。
- 预期结果：停用库也占用名称；创建或改名冲突返回409，并发首次创建只能一个成功；不同owner可分别使用相同名称。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：并发/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；停用也保留名称唯一性；服务端不同owner可同名；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_003"></a>

#### CAT_003：默认库归属

- 用例编号：`CAT_003`
- 对应测试点：`TQ-RAG-CAT-003`：默认库归属。验证目标：每owner默认库身份不混淆。
- 需求来源：RAG-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属case库分别有无默认库。
- 测试数据要求：owner-a/owner-b、非默认新库、第二默认标记。
- 测试流程：
  1. 执行产品初始化/首次创建。
  2. 再次创建普通库。
  3. 用事务尝试设置第二默认后回滚，核对每owner唯一默认。
- 预期结果：空owner首次创建/初始化产生唯一默认库，已有默认库不被新库替换；部分唯一约束拒绝第二个默认库，不假设存在未提供的切换默认API。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py)：upgrade。
- 优先级：P1。
- 用例类型：功能/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；唯一初始化默认；第二库不改默认；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_004"></a>

#### CAT_004：知识库读取权限

- 用例编号：`CAT_004`
- 对应测试点：`TQ-RAG-CAT-004`：知识库读取权限。验证目标：越owner与不存在返回同类拒绝。
- 需求来源：RAG-001、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；A/B分别创建库，owner只能由服务端配置决定。
- 测试数据要求：A库、B库及随机不存在ID。
- 测试流程：
  1. A列表并读取/修改B库和不存在ID。
  2. 比较404错误结构及无存在性泄露。
  3. 用B上下文确认其数据未改变。
- 预期结果：列表只返回服务端owner的库，使用其他owner的库ID读取或修改与不存在同为404，不从错误正文泄漏存在性。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P0。
- 用例类型：权限。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；列表仅本owner；越owner和不存在不可区分；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_005"></a>

#### CAT_005：库停用后的新操作

- 用例编号：`CAT_005`
- 对应测试点：`TQ-RAG-CAT-005`：库停用后的新操作。验证目标：停用库拒绝新知识工作。
- 需求来源：RAG-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例库有可检索旧active。
- 测试数据要求：停用、重新启用、新上传/重建/创建检索视图请求。
- 测试流程：
  1. 停库后分别发三类新操作并检查无新增可执行任务。
  2. 启用后重新提交合法新操作并核对旧源hash。
- 预期结果：停用后新上传、重建和冻结新视图明确拒绝，不产生可执行Job；重新启用后合法新操作可恢复，不修改已有源。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：状态/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；23项断言；正式任务完整成功；重新启用可正常发布；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_006"></a>

#### CAT_006：停用后的历史视图读取

- 用例编号：`CAT_006`
- 对应测试点：`TQ-RAG-CAT-006`：停用后的历史视图读取。验证目标：普通库停用不撤销历史知识事实。
- 需求来源：RAG-001、RAG-021。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；停用前已冻结View及产生回答引用。
- 测试数据要求：旧View、原batch及其正文hash。
- 测试流程：
  1. 停库后继续原冻结执行并读旧引用。
  2. 对照原batch和hash，另用新请求确认停用门禁仍生效。
- 预期结果：已有冻结视图及回答引用仍读取原批次，不因enabled改变换成空或最新内容；与安全blocked的后续外发阻断分开验证。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：状态/兼容。
- 是否适合自动化：是。
- 实际测试结果：通过；18项断言；正式任务完整成功；对应原active；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_007"></a>

#### CAT_007：库空间绑定不可变

- 用例编号：`CAT_007`
- 对应测试点：`TQ-RAG-CAT-007`：库空间绑定不可变。验证目标：客户端不能改变已建库空间。
- 需求来源：RAG-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；库绑定空间A且源已入库。
- 测试数据要求：PATCH注入owner/space_id、空间B的构建或query。
- 测试流程：
  1. 分别提交不允许字段。
  2. 尝试异空间调用。
  3. 对照库绑定和原批次仍不变，新空间只能新建库。
- 预期结果：PATCH中注入space或owner字段拒绝；同库构建与查询必须匹配原绑定空间，更换模型空间须新库重新入库。
- 代码依据／主要定位：[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：契约/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_008"></a>

#### CAT_008：同维异空间隔离

- 用例编号：`CAT_008`
- 对应测试点：`TQ-RAG-CAT-008`：同维异空间隔离。验证目标：维度相同不代表向量可比较。
- 需求来源：RAG-002、RAG-018。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可导入两个同维空间和一个异维空间。
- 测试数据要求：384维模型/修订/归一化不同的配置及1024维对照。
- 测试流程：
  1. 逐项创建空间并比对identity。
  2. 向A库写入或查询B空间。
  3. 检查拒绝及PG无混入行。
- 预期结果：模型、修订、归一化或用途约定不同的同维配置生成不同space身份，不能混写混查；不能只比较维度通过。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search。
- 优先级：P0。
- 用例类型：边界/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；不同描述不合并空间；PG保存不同空间身份；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_009"></a>

#### CAT_009：生成模型与向量空间独立

- 用例编号：`CAT_009`
- 对应测试点：`TQ-RAG-CAT-009`：生成模型与向量空间独立。验证目标：换生成模型不改变检索空间。
- 需求来源：RAG-002、RAG-018。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同库有固定向量及两个Mock生成Profile。
- 测试数据要求：同一问题、生成Profile A/B。
- 测试流程：
  1. 分别创建新Run并记录冻结快照。
  2. 比较embedding/space/检索配置不变，生成Profile独立改变。
- 预期结果：切换ModelProfile前后库space及文档/query映射不漂移，检索适配不从生成模型名称推断Embedding或rerank能力。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：功能/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；不隐式重建；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_010"></a>

#### CAT_010：Profile版本内容不可变

- 用例编号：`CAT_010`
- 对应测试点：`TQ-RAG-CAT-010`：Profile版本内容不可变。验证目标：同一版本重导入不能改内容。
- 需求来源：RAG-009、RAG-018、RAG-026、RAG-035。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；四类RAG Profile均有可导入基线。
- 测试数据要求：每类同ID/version同配置、异配置及version+1。
- 测试流程：
  1. 重复导入同内容。
  2. 异内容导入记录409。
  3. 增版导入后读回两版本配置hash，确认启停不改hash。
- 预期结果：相同ID/版本/内容可重放，异内容409；新配置须增版，四类Profile分别校验，不用启停覆盖配置hash。
- 代码依据／主要定位：[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器。
- 优先级：P0。
- 用例类型：契约/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；拒绝原因与约定一致；增版导入成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_011"></a>

#### CAT_011：选择停用的冻结行为

- 用例编号：`CAT_011`
- 对应测试点：`TQ-RAG-CAT-011`：选择停用的冻结行为。验证目标：普通disabled不改冻结配置。
- 需求来源：RAG-035、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；冻结Run/Build后尚未进入外发。
- 测试数据要求：将所选Profile的selection_status设disabled并提供新版。
- 测试流程：
  1. 创建新工作验证拒选旧版本。
  2. 放行已冻结工作，核对仍用旧版本/hash且不自动换新版。
- 预期结果：新工作不能选择已停用版本，已冻结任务仍按原版本运行；读回版本/hash保持，不静默选最新启用版本。
- 代码依据／主要定位：[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：状态。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；正式任务完整成功；冻结仍原版；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_012"></a>

#### CAT_012：安全blocked的阶段复查

- 用例编号：`CAT_012`
- 对应测试点：`TQ-RAG-CAT-012`：安全blocked的阶段复查。验证目标：安全禁用优先于冻结执行。
- 需求来源：RAG-033、RAG-035、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有查询向量完成到rerank前的有界屏障。
- 测试数据要求：安全blocked的Embedding/Rerank/Retrieval版本。
- 测试流程：
  1. 分别在创建后和阶段间设置blocked。
  2. 释放屏障并检查后续调用计数不增加、事实安全失败。
  3. finally恢复配置。
- 预期结果：创建后及Embedding完成到rerank前设置blocked，后续外发须停止并明确失败；不能把普通停用与安全撤权混为一类。
- 代码依据／主要定位：[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：权限/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；24项断言；正式任务完整成功；安全撤权停止外发：retrieval；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_013"></a>

#### CAT_013：Profile安全可用性投影

- 用例编号：`CAT_013`
- 对应测试点：`TQ-RAG-CAT-013`：Profile安全可用性投影。验证目标：前端获得可操作且无Secret的原因。
- 需求来源：RAG-005、RAG-018、RAG-026、NFR-001、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；导入可用、停用、blocked、缺配置的Profile。
- 测试数据要求：可识别dummy Secret及私有配置哨兵。
- 测试流程：
  1. 读取/api/v3/rag/profiles。
  2. 核对kind/version/dimension/formats/原因，扫描无Secret值及私有端点细节。
- 预期结果：配置清单返回kind/版本/维度/支持格式及安全不可用原因，不公开Key、服务私有参数或签名URL，不能把模板导入当实际可用。
- 代码依据／主要定位：[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影；[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason。
- 优先级：P1。
- 用例类型：接口/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；四类安全配置可见；公开响应不含Key或私有配置；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_014"></a>

#### CAT_014：真实counter未验证守卫

- 用例编号：`CAT_014`
- 对应测试点：`TQ-RAG-CAT-014`：真实counter未验证守卫。验证目标：未校准真实模型不被业务启用。
- 需求来源：RAG-016、RAG-018、RAG-026、RAG-044。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；保留生产配置守卫，提供dummy Key但不改counter状态。
- 测试数据要求：真实Embedding/rerank模板unverified、伪占位evidence。
- 测试流程：
  1. 经正式选择和生产工厂构建能力。
  2. 记录INPUT_COUNTER_UNVERIFIED及零真实调用，不允许fallback为Mock。
- 预期结果：只提供Key或counter_evidence占位但状态仍unverified时，业务返回INPUT_COUNTER_UNVERIFIED；不得自动降级Mock或直接改verified绕过。
- 代码依据／主要定位：[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：异常/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；应用启用守卫；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_015"></a>

#### CAT_015：Parser与格式配置匹配

- 用例编号：`CAT_015`
- 对应测试点：`TQ-RAG-CAT-015`：Parser与格式配置匹配。验证目标：配置不能改变固定分流。
- 需求来源：RAG-004、RAG-009、RAG-043。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；正式Profile导入可在case库回滚。
- 测试数据要求：local声明办公格式、MinerU声明txt/md、缺verified_formats或依据。
- 测试流程：
  1. 逐项导入并选择不匹配Profile。
  2. 合法正例和非法项对照，核对非法格式不产生可外发Job。
- 预期结果：local配置仅允许txt/md，MinerU仅七办公；协议、verified_formats和依据要匹配，缺一不可冒充已验证格式。
- 代码依据／主要定位：[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：契约/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_016"></a>

#### CAT_016：真实计数依据适用性

- 用例编号：`CAT_016`
- 对应测试点：`TQ-RAG-CAT-016`：真实计数依据适用性。验证目标：真实输入计数上界有可复核依据。
- 需求来源：RAG-016、RAG-018、RAG-026、RAG-044。
- 当前可验证性：暂不可完整验证·B（真实输入计数依据及校准未完成，生产守卫阻断）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：需要模型官方计数/有依据上界及独立校准材料。
- 测试数据要求：文档/query/批量、rerank组合输入在上限前/等于/超过，以及中英/emoji。
- 测试流程：
  1. 审核材料与冻结model/revision一致。
  2. 用边界集核验算法输出和安全余量。
  3. 依据成立后才增版启用，不能只改verified。
- 预期结果：分别证明Embedding文档/query/批量和rerank组合输入的模型/修订/算法/上界，边界校准成立后增版配置；UTF-8字节数或一次小请求成功不能充当token证明。
- 暂缓标记：真实计数依据/校准未完成，当前正式生产守卫阻断；解除条件见第3节B项，不使用替身凑成真实通过。
- 代码依据／主要定位：[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`docs/adr/003-sesrag-rag-mineru-implementation-plan.md`](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md)：实施决策/不变量。
- 优先级：P0。
- 用例类型：质量/边界。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：qwen3.7真实Embedding/rerank计数策略尚缺在线部署适用依据；未将自有UTF-8字节配额直接标为tokenizer。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="cat_017"></a>

#### CAT_017：生成计数配置可用性

- 用例编号：`CAT_017`
- 对应测试点：`TQ-RAG-CAT-017`：生成计数配置可用性。验证目标：真实生成计数不借Mock绕过预算。
- 需求来源：RAG-030、RAG-044、NFR-004、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立tools可控词表缓存目录，不改共享缓存。
- 测试数据要求：缺encoding/开销/校准版本、缺词表/坏hash、完整配置。
- 测试流程：
  1. 导入并选择各ModelProfile。
  2. 缺缓存时记录无隐式下载并拒绝。
  3. 合法缓存恢复后核对计数版本及快照。
- 预期结果：真实ModelProfile须显式encoding/框架开销/校准版本，缓存缺失或hash不符明确拒绝且普通请求不隐式下载；适用性依据需单独核对。
- 代码依据／主要定位：[`backend/application/model_profiles.py`](../../backend/application/model_profiles.py)：validate_profile_config/resolve_secret；[`backend/infrastructure/providers/context_counter.py`](../../backend/infrastructure/providers/context_counter.py)：token_counter_from_profile/load_encoding_offline。
- 优先级：P0。
- 用例类型：契约/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；拒绝原因与约定一致；显式encoding可离线加载；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cat_018"></a>

#### CAT_018：资源列表分页

- 用例编号：`CAT_018`
- 对应测试点：`TQ-RAG-CAT-018`：资源列表分页。验证目标：分页完整且不越权。
- 需求来源：RAG-001、RAG-005、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：catalog；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例A库/文档数超过两页并含其他owner数据。
- 测试数据要求：limit=1/50/200、0/201、非法/空游标。
- 测试流程：
  1. 按next_cursor读完静态集合并去重对照PG。
  2. 错误参数拒绝，翻页不能突破owner/库范围。
- 预期结果：库/文档列表按合法游标分页，页界无重复遗漏；limit越界、坏游标明确拒绝，不把游标当业务状态或放宽owner过滤。
- 代码依据／主要定位：[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P1。
- 用例类型：接口/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；45项断言；分页前置独立创建；分页无遗漏；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-catalog/catalog/CAT_018.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories catalog -RunId rag-repro-catalog-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.2 INP：文件受理、授权与幂等

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-INP-001` | [INP_001：九格式白名单](#inp_001) | L | ingestion／local |
| `TQ-RAG-INP-002` | [INP_002：文件名安全归一化](#inp_002) | L | ingestion／local |
| `TQ-RAG-INP-003` | [INP_003：源大小边界](#inp_003) | L | ingestion／local |
| `TQ-RAG-INP-004` | [INP_004：扩展名内容MIME一致](#inp_004) | L | ingestion／local |
| `TQ-RAG-INP-005` | [INP_005：文本编码与有效内容](#inp_005) | L | ingestion／local |
| `TQ-RAG-INP-006` | [INP_006：OOXML源容器安全](#inp_006) | L | ingestion／local |
| `TQ-RAG-INP-007` | [INP_007：旧Office源身份](#inp_007) | L | ingestion／local |
| `TQ-RAG-INP-008` | [INP_008：PDF浅预检的边界](#inp_008) | L | ingestion／local |
| `TQ-RAG-INP-009` | [INP_009：txt/md路由不依赖云服务](#inp_009) | L | ingestion／local |
| `TQ-RAG-INP-010` | [INP_010：办公逐次完整原件授权](#inp_010) | L | ingestion／local |
| `TQ-RAG-INP-011` | [INP_011：本地文本拒绝云选项](#inp_011) | L | ingestion／local |
| `TQ-RAG-INP-012` | [INP_012：已知云能力不可用前置拒绝](#inp_012) | L | ingestion／local |
| `TQ-RAG-INP-013` | [INP_013：办公源字节不可变](#inp_013) | L | ingestion／local |
| `TQ-RAG-INP-014` | [INP_014：用户标签合法性](#inp_014) | L | ingestion／local |
| `TQ-RAG-INP-015` | [INP_015：源更新创建新文档](#inp_015) | L | ingestion／local |
| `TQ-RAG-INP-016` | [INP_016：同源独立上传隔离](#inp_016) | L | ingestion／local |
| `TQ-RAG-INP-017` | [INP_017：操作键同请求重放](#inp_017) | L | ingestion／local |
| `TQ-RAG-INP-018` | [INP_018：操作键异请求拒绝](#inp_018) | L | ingestion／local |
| `TQ-RAG-INP-019` | [INP_019：同配置活动构建复用](#inp_019) | L | ingestion／local |
| `TQ-RAG-INP-020` | [INP_020：成功解析产物复用身份](#inp_020) | L | ingestion／local |
| `TQ-RAG-INP-021` | [INP_021：未知提交后新操作确认](#inp_021) | L | ingestion／local |

<a id="inp_001"></a>

#### INP_001：九格式白名单

- 用例编号：`INP_001`
- 对应测试点：`TQ-RAG-INP-001`：九格式白名单。验证目标：只接受本轮支持的输入类型。
- 需求来源：RAG-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；local受控MinerU，固定源hash已校验。
- 测试数据要求：九种合法源、大小写后缀、html/png/exe/docm等负例。
- 测试流程：
  1. 逐格式经v3上传。
  2. 观察路由和受理结果。
  3. 白名单外统计无Document/远端申请，合法办公仅证明受控流程。
- 预期结果：合法txt/md/doc/docx/pdf/xls/xlsx/ppt/pptx按后缀规范处理；图片等九格式之外的类型不因“等”字纳入，HTML/可执行文件/额外类型拒绝。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy。
- 优先级：P0。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；大小写后缀归一化：.txt；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_002"></a>

#### INP_002：文件名安全归一化

- 用例编号：`INP_002`
- 对应测试点：`TQ-RAG-INP-002`：文件名安全归一化。验证目标：原文件名不能影响宿主路径。
- 需求来源：RAG-003、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每组数据使用独立操作键。
- 测试数据要求：目录前缀名、空名、控制符、冒号、超文件名上限。
- 测试流程：
  1. 上传并读取公开名称/私有存储标识。
  2. 确认只保存安全basename，拒绝项无可用源，输入路径不能控制storage key。
- 预期结果：只保存安全basename；目录前缀按现实现剥离，空名、控制符、冒号及超长名拒绝，存储键由服务端生成而非客户端路径。
- 补充判定／证据边界：文件名超长组以生产安全文件名约定的实际阈值构造前/等于/超过，明确记录阈值，不臆造255字符承诺。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：安全/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；安全basename；客户端路径不决定存储键；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_003"></a>

#### INP_003：源大小边界

- 用例编号：`INP_003`
- 对应测试点：`TQ-RAG-INP-003`：源大小边界。验证目标：单文件0与10MiB限制准确。
- 需求来源：RAG-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；文本内容生成器按MiB构造有效UTF-8。
- 测试数据要求：0字节、10485760字节、10485761字节。
- 测试流程：
  1. 逐个上传并记录受理/错误。
  2. 确认等上限不因大小拒绝，超上限无远端申请/可用批次，最后清理大输入。
- 预期结果：校验空文件、恰好10MiB和多1字节，MiB按1024²；超限受理前失败，无可用候选或远端申请。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；恰好10MiB通过源预检；超限无Document或远端Job；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_004"></a>

#### INP_004：扩展名内容MIME一致

- 用例编号：`INP_004`
- 对应测试点：`TQ-RAG-INP-004`：扩展名内容MIME一致。验证目标：伪装类型不进入对应解析链。
- 需求来源：RAG-003、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每种格式都有真实容器正例。
- 测试数据要求：正确MIME、缺省、application/octet-stream、显式错配及改后缀伪源。
- 测试流程：
  1. 通过真实上传接口按表组合。
  2. 核对内容/MIME/后缀共同判定，拒绝项不登记可执行构建。
- 预期结果：扩展名、声明MIME及内容容器共同核对；合法内容在MIME缺省或application/octet-stream时可继续，明确错配拒绝，不能仅改后缀绕过。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source。
- 优先级：P0。
- 用例类型：安全/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；40项断言；合法MIME或未声明；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_005"></a>

#### INP_005：文本编码与有效内容

- 用例编号：`INP_005`
- 对应测试点：`TQ-RAG-INP-005`：文本编码与有效内容。验证目标：本地文本有明确编码条件。
- 需求来源：RAG-003、RAG-015。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属本地文本库。
- 测试数据要求：UTF-8、UTF-8 BOM、中英emoji、非法字节、NUL、全空白。
- 测试流程：
  1. 提交并等待解析事实。
  2. 逐字对照有效正文和来源，坏编码/空内容不能容错丢字后成功。
- 预期结果：UTF-8及受支持BOM可读；非法编码、NUL、全空白和空源拒绝，不静默丢坏字节后当正常正文。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/infrastructure/rag/local_structure.py`](../../backend/infrastructure/rag/local_structure.py)：parse_text。
- 优先级：P0。
- 用例类型：边界/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；有效文本；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_006"></a>

#### INP_006：OOXML源容器安全

- 用例编号：`INP_006`
- 对应测试点：`TQ-RAG-INP-006`：OOXML源容器安全。验证目标：受支持Office ZIP不越过预检。
- 需求来源：RAG-003、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；仅local生成有界恶意OOXML副本。
- 测试数据要求：docx/xlsx/pptx主部件缺失、错ContentTypes、ZipSlip/重复/宏/嵌入/外部关系、合法超链接。
- 测试流程：
  1. 逐项提交预检。
  2. 核对安全拒绝且无云调用。
  3. 合法超链接正例继续但浏览器/解析器无远端访问。
- 预期结果：docx/xlsx/pptx必须有对应主部件及内容类型；危险路径、重复冲突、宏/嵌入对象/非超链接外部关系和展开限额异常拒绝；普通超链接关系可保留但不被本地解析执行或访问。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/infrastructure/rag/isolated_processing.py`](../../backend/infrastructure/rag/isolated_processing.py)：isolated/_isolated/main。
- 优先级：P0。
- 用例类型：安全。
- 是否适合自动化：是。
- 实际测试结果：通过；27项断言；拒绝原因与约定一致；普通超链接可保留但不访问；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_007"></a>

#### INP_007：旧Office源身份

- 用例编号：`INP_007`
- 对应测试点：`TQ-RAG-INP-007`：旧Office源身份。验证目标：OLE文件确实属于声明办公格式。
- 需求来源：RAG-003、RAG-043、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；许可来源明确的真实OLE样本。
- 测试数据要求：doc/xls/ppt原件、缺对应流、损坏头、加密/宏/对象池标记副本。
- 测试流程：
  1. 逐项做上传预检并观察任务登记。
  2. 用真实正例证明格式身份，不能只构造魔数或用ZIP冒充。
- 预期结果：doc/xls/ppt须具备对应OLE流，缺流、加密/宏/对象池危险标记及损坏拒绝；不得用改后缀ZIP替代真实旧格式正例。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：安全/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；真实旧Office容器；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_008"></a>

#### INP_008：PDF浅预检的边界

- 用例编号：`INP_008`
- 对应测试点：`TQ-RAG-INP-008`：PDF浅预检的边界。验证目标：不能将头尾合法误报完整可解析。
- 需求来源：RAG-003、RAG-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；PDF浅校验及受控远端故障均可观察。
- 测试数据要求：缺PDF头/尾、头尾保留但内部损坏、受控加密/解析失败。
- 测试流程：
  1. 先验浅预检拒绝。
  2. 让其余样本走受控远端明确失败，核对无本地PDF正文/页数探测和成功伪装。
- 预期结果：明显无PDF头尾拒绝；保留头尾但内部损坏/加密等用受控远端拒绝观察明确失败，不承诺本地已完成PDF正文/页数/安全鉴定。
- 代码依据／主要定位：[`backend/infrastructure/rag/office_validation.py`](../../backend/infrastructure/rag/office_validation.py)：validate_source；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：异常/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；拒绝原因与约定一致；坏PDF不回退成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_009"></a>

#### INP_009：txt/md路由不依赖云服务

- 用例编号：`INP_009`
- 对应测试点：`TQ-RAG-INP-009`：txt/md路由不依赖云服务。验证目标：关闭MinerU不影响文本链路。
- 需求来源：RAG-004、RAG-015、RAG-043、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；MinerU关闭且不注入其Key，Mock向量可用。
- 测试数据要求：固定txt/md、包含Markdown标题表格。
- 测试流程：
  1. 分别上传到完整active发布。
  2. 记录MinerU申请/健康计数0，确认没有DOCX中间文件。
- 预期结果：禁用MinerU且无其Key时txt/md完成本地解析，云端申请计数为0；不转DOCX，也不调用云健康来阻塞受理。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job。
- 优先级：P0。
- 用例类型：功能/隔离。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；无云申请；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_010"></a>

#### INP_010：办公逐次完整原件授权

- 用例编号：`INP_010`
- 对应测试点：`TQ-RAG-INP-010`：办公逐次完整原件授权。验证目标：每次新办公写入具有有效确认。
- 需求来源：RAG-004、RAG-022、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；合法七办公源且能力可用。
- 测试数据要求：每次上传/重建授权缺失、false、错版本、正确true/v1。
- 测试流程：
  1. 逐数据提交并核查422及零远端申请。
  2. 前一次已授权后再发无授权新请求仍拒绝。
- 预期结果：上传/重建均要求cloud_consent=true与mineru-office-outbound-v1；缺失、false或版本不符422，不以源hash相同或前次同意免授权。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：权限。
- 是否适合自动化：是。
- 实际测试结果：通过；148项断言；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_011"></a>

#### INP_011：本地文本拒绝云选项

- 用例编号：`INP_011`
- 对应测试点：`TQ-RAG-INP-011`：本地文本拒绝云选项。验证目标：本地请求不能隐式切成增强路线。
- 需求来源：RAG-004、RAG-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；txt/md合法源，严格ParseRequest。
- 测试数据要求：附cloud_consent、错误Parser、mode/fallback/converter/url额外字段。
- 测试流程：
  1. 逐项经上传/重建接口送入严格解析参数。
  2. 核对拒绝而非切路由。
  3. 干净本地请求作正例。
- 预期结果：txt/md携带云授权或不匹配Parser配置应拒绝；mode/fallback/converter/URL等未知字段不能改变固定路线。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：契约。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_012"></a>

#### INP_012：已知云能力不可用前置拒绝

- 用例编号：`INP_012`
- 对应测试点：`TQ-RAG-INP-012`：已知云能力不可用前置拒绝。验证目标：不可用时不登记无意义远端工作。
- 需求来源：RAG-004、RAG-013、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每次改变服务端一种能力条件。
- 测试数据要求：MinerU开关false、缺API Key/状态Key/存储域、未验证该格式。
- 测试流程：
  1. 分别提交办公新工作。
  2. 记录明确原因及Job/远端申请不增。
  3. 相同环境txt/md与旧引用仍读取。
- 预期结果：云开关关闭、缺Key/状态加密Key/白名单或该格式未验证时拒绝办公新构建；无远端申请，错误原因明确，不阻断本地文本与旧历史。
- 代码依据／主要定位：[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：异常。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；已知缺配置不可用；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_013"></a>

#### INP_013：办公源字节不可变

- 用例编号：`INP_013`
- 对应测试点：`TQ-RAG-INP-013`：办公源字节不可变。验证目标：实际PUT与登记原件相同。
- 需求来源：RAG-006、RAG-009、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；local真实生产MinerU客户端加受控transport。
- 测试数据要求：固定办公原件hash，恢复前受控篡改本例私有源。
- 测试流程：
  1. 记录PUT实际字节hash并对照源/DB。
  2. 再触发恢复篡改子例，检查SOURCE_HASH_MISMATCH且不上传新字节。
- 预期结果：比对上传源SHA-256、私有源和PUT字节，禁止转格式/去隐藏内容后冒称原件；恢复若源hash变动必须失败，不继续上传替换源。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；篡改源不得解析成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_014"></a>

#### INP_014：用户标签合法性

- 用例编号：`INP_014`
- 对应测试点：`TQ-RAG-INP-014`：用户标签合法性。验证目标：标签可过滤而不覆盖系统元数据。
- 需求来源：RAG-005。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例文档及标签patch入口可用。
- 测试数据要求：0/20/21项，1/40/41字符，空白、重复、非字符串/嵌套、系统键。
- 测试流程：
  1. 上传及修改标签后读回。
  2. 逐项核对去白/去重及拒绝，source/batch/space等系统事实不变。
- 预期结果：最多20项、每项去空白后1～40字符，去重语义一致；非字符串/嵌套和非法补丁拒绝，用户不能覆盖batch/space/source身份。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影；[`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py)：Document/IndexBuild/Location/ChunkPolicy。
- 优先级：P1。
- 用例类型：边界/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；21项断言；标签去空白去重；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_015"></a>

#### INP_015：源更新创建新文档

- 用例编号：`INP_015`
- 对应测试点：`TQ-RAG-INP-015`：源更新创建新文档。验证目标：新内容不覆盖已有引用原源。
- 需求来源：RAG-006、RAG-021。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已有被引用文档A。
- 测试数据要求：同名但修改一字节的新文件、仅改标签。
- 测试流程：
  1. 上传变化源产生B。
  2. 读A旧引用。
  3. 对A改标签并核原源hash未变，探查无原地覆盖源入口。
- 预期结果：变化字节必须产生新Document，标签修改不改source/hash；没有任意覆盖源的接口，历史引用继续指原对象。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影；[`backend/db/models.py`](../../backend/db/models.py)：DocumentModel/ChunkModel/TaskModel/RunModel。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；21项断言；正式任务完整成功；标签不覆盖源；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_016"></a>

#### INP_016：同源独立上传隔离

- 用例编号：`INP_016`
- 对应测试点：`TQ-RAG-INP-016`：同源独立上传隔离。验证目标：源hash不是跨资源共享授权。
- 需求来源：RAG-006、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个owner上下文，固定只读源。
- 测试数据要求：相同字节、不同操作键、相同键跨owner。
- 测试流程：
  1. 分别上传并比较Document/私有源归属。
  2. 同owner独立请求可独立身份，跨owner无可见缓存身份复用。
- 预期结果：同字节但不同操作键独立上传可产生不同Document；跨owner不复用可见身份/源引用，不把去重当权限豁免。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/rag_operations.py`](../../backend/application/rag_operations.py)：replay/record/transaction_lock。
- 优先级：P0。
- 用例类型：权限/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；内容相同不等于身份相同；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_016.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_017"></a>

#### INP_017：操作键同请求重放

- 用例编号：`INP_017`
- 对应测试点：`TQ-RAG-INP-017`：操作键同请求重放。验证目标：重复请求返回同一业务身份。
- 需求来源：RAG-006、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；各操作独立scope，双连接并发能力。
- 测试数据要求：建库/上传/重建/诊断各自相同key及规范请求。
- 测试流程：
  1. 并发首次提交再重放。
  2. 核对首次201或202、重放200及资源身份唯一。
  3. 同逻辑工作不多申请云batch。
- 预期结果：上传/建库/重建/诊断在各自owner及scope中同键同内容返回原资源，首次并发不能创建重复身份或重复云任务；核对201/202与重放200语义。
- 代码依据／主要定位：[`backend/application/rag_operations.py`](../../backend/application/rag_operations.py)：replay/record/transaction_lock；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/knowledge_bases.py`](../../backend/application/knowledge_bases.py)：create_base/patch_base/load_base。
- 优先级：P0。
- 用例类型：幂等/并发。
- 是否适合自动化：是。
- 实际测试结果：通过；23项断言；建库同键重放；诊断重放；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_018"></a>

#### INP_018：操作键异请求拒绝

- 用例编号：`INP_018`
- 对应测试点：`TQ-RAG-INP-018`：操作键异请求拒绝。验证目标：同键不能悄悄承载新业务。
- 需求来源：RAG-006、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每个操作scope已有成功/受理记录。
- 测试数据要求：同key改源/参数、空键/非法/超长键，另一scope同键。
- 测试流程：
  1. 逐组提交。
  2. 异请求409且原记录不变，非法键拒绝，跨scope按自身规则处理不重放他人资源。
- 预期结果：同scope同键更改内容/hash/参数应409，空/非法/超长键拒绝；不同scope不能误碰同一去重记录，不重放他人资源。
- 补充判定／证据边界：v3 RagOperation键的已实现格式约束为字符串长度1～200；分别测缺省/空/201字符/非法类型。不要擅自增加“必须UUID”或“只能ASCII”的验收规则；HTTP库拒绝的非法报文不当作应用层已拒绝的证据。
- 代码依据／主要定位：[`backend/application/rag_operations.py`](../../backend/application/rag_operations.py)：replay/record/transaction_lock；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：幂等/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；21项断言；正式任务完整成功；传输层显式编码非ASCII头字节，不虚构UUID限制；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_018.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_019"></a>

#### INP_019：同配置活动构建复用

- 用例编号：`INP_019`
- 对应测试点：`TQ-RAG-INP-019`：同配置活动构建复用。验证目标：同文档同时至多一个活动候选。
- 需求来源：RAG-020、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例文档有暂停的活动Build。
- 测试数据要求：相同冻结配置、不同chunker/Parser配置的多个新key。
- 测试流程：
  1. 并发重建并查询PG。
  2. 同配置复用活动候选，不同配置INDEX_BUILD_BUSY，无两个同时活动候选。
- 预期结果：对同文档发多个重建，相同冻结配置复用活动候选，不同配置INDEX_BUILD_BUSY；核对DB唯一约束和无双active候选。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：并发。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；只有一个活动候选；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_019.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_020"></a>

#### INP_020：成功解析产物复用身份

- 用例编号：`INP_020`
- 对应测试点：`TQ-RAG-INP-020`：成功解析产物复用身份。验证目标：复用产物条件不放宽。
- 需求来源：RAG-009、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；准备本例成功Artifact及不匹配对照。
- 测试数据要求：同源同Parser/protocol hash、异owner/文档/hash/协议、旧本地DOCX。
- 测试流程：
  1. 依次请求重建。
  2. 记录仅完全匹配产物复用，其他合法请求重解析或安全拒绝。
  3. 办公仍要求新授权。
- 预期结果：只复用同文档/owner、source hash、parser与输出协议hash匹配的成功产物；旧本地DOCX不冒充MinerU，新办公重建仍逐次确认。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：兼容/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；30项断言；正式任务完整成功；跨Document不复用Artifact；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_020.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="inp_021"></a>

#### INP_021：未知提交后新操作确认

- 用例编号：`INP_021`
- 对应测试点：`TQ-RAG-INP-021`：未知提交后新操作确认。验证目标：未知远端结果不会无提示重提。
- 需求来源：RAG-006、RAG-013、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：ingestion；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例Job先制造提交应答未知终态。
- 测试数据要求：新key、同旧key、cloud_consent及acknowledge_duplicate_cost真假。
- 测试流程：
  1. 先无重复成本确认重建观察拒绝。
  2. 明确确认后新操作建新Job。
  3. 旧键重放保持原失败且不再申请。
- 预期结果：先前remote_outcome为unknown_may_continue时，新重建须再次授权且显式acknowledge_duplicate_cost=true确认潜在重复成本；缺确认拒绝，旧Job保持失败，同键重放不变成新申请。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：风险/幂等。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；未知提交持久风险；旧未知终态不复活；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-ingestion/ingestion/INP_021.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories ingestion -RunId rag-repro-ingestion-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.3 MIN：MinerU协议、状态与恢复

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-MIN-001` | [MIN_001：精准API申请协议](#min_001) | L | mineru／local |
| `TQ-RAG-MIN-002` | [MIN_002：原件PUT凭据边界](#min_002) | L | mineru／local |
| `TQ-RAG-MIN-003` | [MIN_003：轮询结果身份验证](#min_003) | L | mineru／local |
| `TQ-RAG-MIN-004` | [MIN_004：远端状态安全映射](#min_004) | L | mineru／local |
| `TQ-RAG-MIN-005` | [MIN_005：远端done不是可检索终态](#min_005) | L | mineru／local |
| `TQ-RAG-MIN-006` | [MIN_006：提交意图先持久化](#min_006) | L | mineru／local |
| `TQ-RAG-MIN-007` | [MIN_007：同Job等待恢复](#min_007) | L | mineru／local |
| `TQ-RAG-MIN-008` | [MIN_008：PUT应答未知恢复](#min_008) | L | mineru／local |
| `TQ-RAG-MIN-009` | [MIN_009：下载断点恢复](#min_009) | L | mineru／local |
| `TQ-RAG-MIN-010` | [MIN_010：正常等待让出执行槽](#min_010) | L | mineru／local |
| `TQ-RAG-MIN-011` | [MIN_011：Job总截止和轮询上限](#min_011) | L | mineru／local |
| `TQ-RAG-MIN-012` | [MIN_012：安全请求有界重试](#min_012) | L | mineru／local |
| `TQ-RAG-MIN-013` | [MIN_013：认证与额度失败分类](#min_013) | L | mineru／local |
| `TQ-RAG-MIN-014` | [MIN_014：明确远端失败不回退](#min_014) | L | mineru／local |
| `TQ-RAG-MIN-015` | [MIN_015：取消尚未提交的工作](#min_015) | L | mineru／local |
| `TQ-RAG-MIN-016` | [MIN_016：取消已提交的工作](#min_016) | L | mineru／local |
| `TQ-RAG-MIN-017` | [MIN_017：取消与发布竞争裁决](#min_017) | L | mineru／local |
| `TQ-RAG-MIN-018` | [MIN_018：Job终态拒绝迟到产物](#min_018) | L | mineru／local |
| `TQ-RAG-MIN-019` | [MIN_019：唯一产物与检查点身份](#min_019) | L | mineru／local |
| `TQ-RAG-MIN-020` | [MIN_020：私有检查点加密](#min_020) | L | mineru／local |
| `TQ-RAG-MIN-021` | [MIN_021：单次外部请求超时](#min_021) | L | mineru／local |
| `TQ-RAG-MIN-022` | [MIN_022：阶段观测关联完整性](#min_022) | K | mineru／local |

<a id="min_001"></a>

#### MIN_001：精准API申请协议

- 用例编号：`MIN_001`
- 对应测试点：`TQ-RAG-MIN-001`：精准API申请协议。验证目标：申请请求和响应身份正确。
- 需求来源：RAG-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生产MinerUClient使用本suite受控HTTP，单文档Job已登记。
- 测试数据要求：HTTP/业务code成功与失败、缺batch/URL、错/重复文件身份。
- 测试流程：
  1. 逐响应组推进申请。
  2. 捕获安全请求摘要。
  3. 只有合法code/data/单文件身份进入PUT，不调用第二提交API。
- 预期结果：使用固定精准API文件URL流程，HTTP成功同时检查业务code/data；当前每Job只申请一个文件，单文档data_id对应Job，缺/重/错文件身份不能继续到PUT，不把上游批量上限误当已实现批量上传。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job。
- 优先级：P0。
- 用例类型：接口/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；保存远端工作身份；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_002"></a>

#### MIN_002：原件PUT凭据边界

- 用例编号：`MIN_002`
- 对应测试点：`TQ-RAG-MIN-002`：原件PUT凭据边界。验证目标：存储上传不携带API Token。
- 需求来源：RAG-007、NFR-001、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；合法已保存handle和原件。
- 测试数据要求：API dummy Bearer、受信签名PUT URL、原字节。
- 测试流程：
  1. 推进上传及poll。
  2. 分别捕获API/存储请求头和body hash。
  3. 核对PUT无Bearer且同batch仅一次申请。
- 预期结果：PUT仅向核实的签名存储目标发送原字节，不附API Bearer；上传完成只查原batch，不额外调用另一解析提交接口。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend。
- 优先级：P0。
- 用例类型：安全/协议。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；原字节PUT；只轮询原batch；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_003"></a>

#### MIN_003：轮询结果身份验证

- 用例编号：`MIN_003`
- 对应测试点：`TQ-RAG-MIN-003`：轮询结果身份验证。验证目标：返回行不能串到其他文件。
- 需求来源：RAG-007、RAG-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Job已保存file_name/data_id/batch。
- 测试数据要求：轮询错名/错ID、多/少条结果、未知状态及匹配正例。
- 测试流程：
  1. 逐组响应后检查Job错误与Build。
  2. 不能为他文件下载/发布，合法状态继续原身份。
- 预期结果：file_name/data_id/结果条数与已保存handle一致，非法状态/错身份明确失败；返回值再像成功也不能为另一文档发布。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：契约/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_004"></a>

#### MIN_004：远端状态安全映射

- 用例编号：`MIN_004`
- 对应测试点：`TQ-RAG-MIN-004`：远端状态安全映射。验证目标：阶段反映真实已知进度。
- 需求来源：RAG-008。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有可控远端状态序列和无进度字段。
- 测试数据要求：waiting-file/pending/running/converting/done/failed，未知页数。
- 测试流程：
  1. 逐阶段暂停读取API和PG。
  2. 核对本地状态、未知值及安全错误。
  3. 不展示原上游正文或伪百分比。
- 预期结果：waiting-file/pending/running/converting/done/failed映射本地阶段，缺页数/进度保持未知，不能填0或假百分比；公开不含原始错误全文。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：功能/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；远端状态不伪造；未知页数不填0且清洗错误正文；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_005"></a>

#### MIN_005：远端done不是可检索终态

- 用例编号：`MIN_005`
- 对应测试点：`TQ-RAG-MIN-005`：远端done不是可检索终态。验证目标：解析完成不会提前切active。
- 需求来源：RAG-008、RAG-020。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已有旧active，候选停在远端done。
- 测试数据要求：下载、chunk、embedding及publish前的多个暂停点。
- 测试流程：
  1. 逐点查询新视图和文档状态。
  2. 确认旧active可用且候选未检索。
  3. 最后放行仅完整发布后切换。
- 预期结果：在远端done到下载/切片/向量化/发布之间挂起，候选仍不可检索，只有完整本地成功才ready；旧active不变。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：状态/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；24项断言；远端done仅到下载阶段；进入目标阶段前未异常终止；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_006"></a>

#### MIN_006：提交意图先持久化

- 用例编号：`MIN_006`
- 对应测试点：`TQ-RAG-MIN-006`：提交意图先持久化。验证目标：申请不明时重启不会再次申请。
- 需求来源：RAG-012、RAG-013、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可在提交前后观察PG检查点并杀本例Worker。
- 测试数据要求：POST可能到达但回包断开/损坏、submitting后崩溃。
- 测试流程：
  1. 确认submitting先于外发提交。
  2. 重启新代。
  3. 核对MINERU_SUBMISSION_UNKNOWN和may_continue，submit总次数不增。
- 预期结果：在发出POST前保存submitting；POST已可能到达但应答丢失/损坏或身份未落盘，恢复写MINERU_SUBMISSION_UNKNOWN，申请次数不增加。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：恢复/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；未知提交明确终态；恢复不知提交结果时不重新申请；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_007"></a>

#### MIN_007：同Job等待恢复

- 用例编号：`MIN_007`
- 对应测试点：`TQ-RAG-MIN-007`：同Job等待恢复。验证目标：重启只继续原远端工作。
- 需求来源：RAG-009、RAG-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已保存batch，两个Worker按租约接管。
- 测试数据要求：pending/running/converting状态、同时导入新版Parser默认。
- 测试流程：
  1. 停止原Worker并待新代接管。
  2. 核对同Job/handle继续poll，旧Parser hash不漂移，申请计数保持1。
- 预期结果：保存batch后在排队/解析/转换中重启Worker，新代使用同Job/handle查询，不重选当前默认Parser、不新建batch。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；跨Worker恢复完成；Job身份不变；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_008"></a>

#### MIN_008：PUT应答未知恢复

- 用例编号：`MIN_008`
- 对应测试点：`TQ-RAG-MIN-008`：PUT应答未知恢复。验证目标：先查询而不是盲目重复提交。
- 需求来源：RAG-012、RAG-013。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；PUT可能已被接受，poll可返回确定状态。
- 测试数据要求：应答丢失后running/done或仍waiting-file两组。
- 测试流程：
  1. 恢复同Job先poll。
  2. 已接受组无重传，waiting-file组仅沿原handle受控PUT，均不重新submit。
- 预期结果：PUT可能成功但返回失败/连接断开，恢复先poll原batch；仅waiting-file按既有协议继续上传，不能重新申请云工作。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：恢复/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；最终已知完成；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_009"></a>

#### MIN_009：下载断点恢复

- 用例编号：`MIN_009`
- 对应测试点：`TQ-RAG-MIN-009`：下载断点恢复。验证目标：结果读取失败不重解析原件。
- 需求来源：RAG-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同batch已done，下载发生短暂失败。
- 测试数据要求：首次连接断开/503，随后合法同hash包。
- 测试流程：
  1. 推进重试或重启Worker。
  2. 核对同batch下载恢复，Artifact唯一，不多创建Job或云申请。
- 预期结果：在已知done后下载临时失败/重启，使用同一batch及受控下载步骤恢复，成功产物唯一；不以新Job消耗另一份解析。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；只有一个成功产物；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_010"></a>

#### MIN_010：正常等待让出执行槽

- 用例编号：`MIN_010`
- 对应测试点：`TQ-RAG-MIN-010`：正常等待让出执行槽。验证目标：等待不占长事务或错误额度。
- 需求来源：RAG-012、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；一个等待办公Job及独立可执行任务。
- 测试数据要求：多次pending轮询，观察attempt/failure_count/lease。
- 测试流程：
  1. 推进多个等待周期。
  2. 查询waiting_external及lease释放。
  3. 让另一任务执行，正常轮询不增加failure_count。
- 预期结果：远端未完成时Task进入waiting_external、释放租约/Worker槽；多次轮询可以增加attempt但不增加failure_count，其他工作可推进。
- 代码依据／主要定位：[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch。
- 优先级：P0。
- 用例类型：状态/容量。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；等待回排；物理尝试增加且槽位释放；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_011"></a>

#### MIN_011：Job总截止和轮询上限

- 用例编号：`MIN_011`
- 对应测试点：`TQ-RAG-MIN-011`：Job总截止和轮询上限。验证目标：云端等待有确定结束条件。
- 需求来源：RAG-013、RAG-014、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可控时钟或本例截止夹具，不改宿主时间。
- 测试数据要求：Job300秒、poll5秒/60次、Task1800秒及更早截止。
- 测试流程：
  1. 分别跨越冻结截止/轮询边界。
  2. 核对安全超时与终态且没有第61次轮询或截止延长。
- 预期结果：默认Job300秒/轮询5秒/最多60次，并不得越Task1800秒截止；长排队触发安全超时，不无限延长或预留解析回退。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：边界/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；Job总截止；轮询上限有界；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_012"></a>

#### MIN_012：安全请求有界重试

- 用例编号：`MIN_012`
- 对应测试点：`TQ-RAG-MIN-012`：安全请求有界重试。验证目标：临时错误恢复有次数和退避。
- 需求来源：RAG-012、RAG-013、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；仅对安全同工作请求注入故障。
- 测试数据要求：poll/download临时网络/5xx，重试耗尽及正常waiting对照。
- 测试流程：
  1. 逐次推进并记录backoff、failure_count。
  2. 恢复可成功，耗尽明确失败，submit应答未知不按此重发。
- 预期结果：仅同工作内安全请求的临时网络/5xx有界重试，failure_count耗尽后明确终态；正常等待与故障回排分别计数。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：异常/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；临时错误不能无限回排；安全请求有限重试；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_013"></a>

#### MIN_013：认证与额度失败分类

- 用例编号：`MIN_013`
- 对应测试点：`TQ-RAG-MIN-013`：认证与额度失败分类。验证目标：认证额度不伪装网络或空成功。
- 需求来源：RAG-013、RAG-020。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已有旧active，准备三类独立失败。
- 测试数据要求：401、403、429、远端明确failed。
- 测试流程：
  1. 逐组推进并读安全码/终态。
  2. 核对原因区分、无换Key/轻量API/转换。
  3. 旧active仍可检索。
- 预期结果：401/403、429与确定解析failed分别产生稳定原因，不自动换Key/轻量API/模型或格式；已有active继续可用。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：异常/可观测。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；拒绝原因与约定一致；确定解析失败独立错误码；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_014"></a>

#### MIN_014：明确远端失败不回退

- 用例编号：`MIN_014`
- 对应测试点：`TQ-RAG-MIN-014`：明确远端失败不回退。验证目标：确定失败不能被另一解析路径覆盖。
- 需求来源：RAG-010、RAG-013。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；不装本地Office/PDF解析及转换工具。
- 测试数据要求：明确failed、空白产物两组，旧active对照。
- 测试流程：
  1. 推进到确定失败。
  2. 记录Job/Build/remote_outcome。
  3. 再次调度同Job不能复活或调用替代路线。
- 预期结果：上游failed或无有效文本后Job/Build失败且remote_outcome保持正确，不调用本地Office解析/转换兜底，不复活失败事实。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：异常/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；无有效文本失败；无本地回退产物；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_015"></a>

#### MIN_015：取消尚未提交的工作

- 用例编号：`MIN_015`
- 对应测试点：`TQ-RAG-MIN-015`：取消尚未提交的工作。验证目标：受理后取消可阻止首次外发。
- 需求来源：RAG-014。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Worker领取前或preparing屏障可控。
- 测试数据要求：queued及尚未submit的building两阶段。
- 测试流程：
  1. 先调用本地取消再放行/调度。
  2. 核对远端submit/PUT为0、没有发布，终态来自PG。
- 预期结果：在排队/准备阶段取消，后续无申请/PUT/发布；queued/waiting任务可直接结算，公开终态只来自服务端事实。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：取消/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；排队取消由服务端结算；取消前未提交则零申请；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_016"></a>

#### MIN_016：取消已提交的工作

- 用例编号：`MIN_016`
- 对应测试点：`TQ-RAG-MIN-016`：取消已提交的工作。验证目标：本地取消不冒称远端撤回。
- 需求来源：RAG-014、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已申请/已PUT的独立Job。
- 测试数据要求：提交后取消、上传后取消、明确已知结果对照。
- 测试流程：
  1. 发取消并释放后续步骤。
  2. 核对不再正常发布，公开提示远端可能继续而非已退款/删除。
- 预期结果：申请/上传后取消停止后续本机步骤和发布，记录unknown_may_continue或真实已知结果；不显示已退款/云文件已删除。
- 代码依据／主要定位：[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：取消/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；本机取消不冒称云端撤回；本机取消事实；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_016.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_017"></a>

#### MIN_017：取消与发布竞争裁决

- 用例编号：`MIN_017`
- 对应测试点：`TQ-RAG-MIN-017`：取消与发布竞争裁决。验证目标：竞争只产生一个合法终态。
- 需求来源：RAG-014、RAG-020、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG双连接、候选到提交边界。
- 测试数据要求：取消先获得锁、发布先获得锁两种确定顺序。
- 测试流程：
  1. 用事务屏障控制获锁顺序并提交。
  2. 读取Build/Task/active，核对只保留胜出的一种终态。
- 预期结果：用两个PG连接在取消与最终提交间竞争：取消先胜不切active，发布先胜保持成功；不能同时出现成功和取消终态或覆盖旧active。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：并发/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；23项断言；进入目标阶段前未异常终止；终态先提交者胜；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_018"></a>

#### MIN_018：Job终态拒绝迟到产物

- 用例编号：`MIN_018`
- 对应测试点：`TQ-RAG-MIN-018`：Job终态拒绝迟到产物。验证目标：迟到返回不能复活失败Job。
- 需求来源：RAG-012、RAG-014。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已失败/取消/超时的Job和旧generation。
- 测试数据要求：迟到done、正常包以及旧代发布调用。
- 测试流程：
  1. 分别放出迟到响应并尝试落库。
  2. 检查终态/active/Event未变，临时产物登记可清理。
- 预期结果：失败/取消/截止后继续返回done或正常包，旧代不能改Job/Build终态、写artifact为新active或追加成功事件；私有迟到文件有清理归属。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：并发/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；迟到done不复活；不发布迟到产物；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_018.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_019"></a>

#### MIN_019：唯一产物与检查点身份

- 用例编号：`MIN_019`
- 对应测试点：`TQ-RAG-MIN-019`：唯一产物与检查点身份。验证目标：一个Job不能生成两份成功事实。
- 需求来源：RAG-009、RAG-012、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；一个Job在恢复或并发写产物边界。
- 测试数据要求：同Job两次合法产物、错误document/source/parser/protocol关联。
- 测试流程：
  1. 受控并发推进并读PG唯一/外键。
  2. 只有一份成功Artifact且所有归属/hash一致。
- 预期结果：同Job恢复或并发写入只有一个成功Artifact，source/parser/protocol/hash关系一致；artifact_id与document归属不能跨串。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_019.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_020"></a>

#### MIN_020：私有检查点加密

- 用例编号：`MIN_020`
- 对应测试点：`TQ-RAG-MIN-020`：私有检查点加密。验证目标：远端能力不以明文事实外泄。
- 需求来源：RAG-011、RAG-012、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；API/Worker共享同一随机状态Key。
- 测试数据要求：正确Key、错误Key、篡改nonce/AAD/密文、handle。
- 测试流程：
  1. 合法保存并重启恢复。
  2. 逐副本解密负例安全失败。
  3. 扫描公开响应/Event无原batch/URL。
- 预期结果：状态用AES-GCM保存；错误Key、篡改nonce/AAD/密文不能解出可用handle；API/Worker同Key可恢复，响应/Event不含原batch和URL。
- 代码依据／主要定位：[`backend/infrastructure/rag/artifact_store.py`](../../backend/infrastructure/rag/artifact_store.py)：ArtifactStore；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：安全/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；相同Key可恢复；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_020.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_021"></a>

#### MIN_021：单次外部请求超时

- 用例编号：`MIN_021`
- 对应测试点：`TQ-RAG-MIN-021`：单次外部请求超时。验证目标：网络挂起不会无限占资源。
- 需求来源：RAG-011、RAG-013、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有界慢连接/慢上传/慢下载传输夹具。
- 测试数据要求：单次timeout前后、取消期间挂起。
- 测试流程：
  1. 逐阶段触发超时及取消。
  2. 核对限定时间返回、安全码/重试语义及无后台请求或解析子进程残留。
- 预期结果：连接/上传/下载各有有界timeout，达到时安全失败或同工作受控重试；取消后不留下后台无界请求/处理进程。
- 代码依据／主要定位：[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/isolated_processing.py`](../../backend/infrastructure/rag/isolated_processing.py)：isolated/_isolated/main。
- 优先级：P0。
- 用例类型：边界/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；单次请求截止；取消后请求已结束；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_021.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="min_022"></a>

#### MIN_022：阶段观测关联完整性

- 用例编号：`MIN_022`
- 对应测试点：`TQ-RAG-MIN-022`：阶段观测关联完整性。验证目标：一个失败可定位具体解析阶段。
- 需求来源：RAG-008、RAG-031、NFR-005。
- 当前可验证性：本机可验证·K（已知实现/契约差异，按完整目标断言，可能失败）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生成一条跨全部解析阶段的成功链和故障链。
- 测试数据要求：document/job/batch/task/worker/generation、阶段开始结束安全观察。
- 测试流程：
  1. 采集默认结构日志和产品持久记录。
  2. 按阶段联接身份/耗时并列缺字段。
  3. 工程补测计时不得冒充产品内置观测。
- 预期结果：按document/Job/batch/Task/worker/generation追踪安全错误和阶段耗时；当前日志/解析全阶段duration不全，必须以完整目标断言并保留缺项，不能补造usage。
- 代码依据／主要定位：[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch。
- 优先级：P1。
- 用例类型：可观测/质量。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；真实Worker必须覆盖解析、切片、向量和发布阶段边界；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/MIN_022.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.4 PAR：产物安全、结构与来源位置

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-PAR-001` | [PAR_001：出站URL白名单](#par_001) | L | mineru／local |
| `TQ-RAG-PAR-002` | [PAR_002：DNS公网绑定](#par_002) | L | mineru／local |
| `TQ-RAG-PAR-003` | [PAR_003：重定向逐跳校验](#par_003) | L | mineru／local |
| `TQ-RAG-PAR-004` | [PAR_004：下载响应体上限](#par_004) | L | mineru／local |
| `TQ-RAG-PAR-005` | [PAR_005：解析ZIP成员安全](#par_005) | L | mineru／local |
| `TQ-RAG-PAR-006` | [PAR_006：解包资源上限](#par_006) | L | mineru／local |
| `TQ-RAG-PAR-007` | [PAR_007：full.md与整体协议](#par_007) | L | mineru／local |
| `TQ-RAG-PAR-008` | [PAR_008：无有效文本失败](#par_008) | L | mineru／local |
| `TQ-RAG-PAR-009` | [PAR_009：表格安全文本化](#par_009) | L | mineru／local |
| `TQ-RAG-PAR-010` | [PAR_010：txt行来源映射](#par_010) | L | chunking／local |
| `TQ-RAG-PAR-011` | [PAR_011：Markdown结构保留](#par_011) | L | chunking／local |
| `TQ-RAG-PAR-012` | [PAR_012：可靠PDF原页映射](#par_012) | L | mineru／local |
| `TQ-RAG-PAR-013` | [PAR_013：缺少原源位置的明示](#par_013) | L | mineru／local |
| `TQ-RAG-PAR-014` | [PAR_014：可选位置文件畸形](#par_014) | L | mineru／local |

<a id="par_001"></a>

#### PAR_001：出站URL白名单

- 用例编号：`PAR_001`
- 对应测试点：`TQ-RAG-PAR-001`：出站URL白名单。验证目标：目标协议与域不可由返回值放宽。
- 需求来源：RAG-011、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；直接调用未放宽的SafeHTTP，受控请求不需真实Key。
- 测试数据要求：http/https、80/443端口、userinfo/fragment、未授权API/存储域、环境代理。
- 测试流程：
  1. 逐URL执行校验和受控请求。
  2. 核对拒绝码及无目的连接。
  3. 合法白名单HTTPS作正例，返回值不能扩大名单。
- 预期结果：非HTTPS/非443/凭据URL/片段/未授权域拒绝；API与存储域分离，不能信任响应自动扩大白名单或用环境代理绕检查。
- 代码依据／主要定位：[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：安全。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；拒绝原因与约定一致；精确HTTPS/443白名单正例；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_002"></a>

#### PAR_002：DNS公网绑定

- 用例编号：`PAR_002`
- 对应测试点：`TQ-RAG-PAR-002`：DNS公网绑定。验证目标：通过域检查也不能连私网。
- 需求来源：RAG-011、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；隔离tools内可替换解析器/连接器观察点，保留生产PublicNetworkBackend。
- 测试数据要求：回环/私网/metadata/IPv6/混合DNS、先公网后私网重绑定。
- 测试流程：
  1. 调用生产连接路径并记录解析与connect_tcp参数。
  2. 不安全地址零连接，合法公网绑定已验证IP且TLS仍原host。
  3. MockTransport不能充当此证据。
- 预期结果：解析出回环/私网/metadata或混合不安全地址拒绝；实际TCP使用已校验公网IP且TLS按原host验证，测试区分transport替身和真实后端路径。
- 补充判定／证据边界：正向公网地址使用文档示例地址仅作为连接器受控返回值，不实际向任意公网主机发业务请求；检查TLS server_hostname和实际IP参数，若只能证明参数绑定，就不得声称完成真实TLS握手。
- 代码依据／主要定位：[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend。
- 优先级：P0。
- 用例类型：安全/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；拒绝私网或混合DNS；不再用host重新DNS连接；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_003"></a>

#### PAR_003：重定向逐跳校验

- 用例编号：`PAR_003`
- 对应测试点：`TQ-RAG-PAR-003`：重定向逐跳校验。验证目标：跳转不能泄漏凭据或绕域。
- 需求来源：RAG-011、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生产SafeHTTP加确定性重定向传输。
- 测试数据要求：GET同域/跨域/私网/循环跳转、PUT/POST 30x。
- 测试流程：
  1. 观察每跳校验与Authorization传播。
  2. 跨origin清凭据，超跳数拒绝，非幂等请求不自动重放。
- 预期结果：GET每跳校验目标，跨origin清凭据且跳数有界；非幂等PUT/POST不自动重放跳转，危险或过多跳转拒绝。
- 代码依据／主要定位：[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend。
- 优先级：P0。
- 用例类型：安全/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；合法跳转；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_004"></a>

#### PAR_004：下载响应体上限

- 用例编号：`PAR_004`
- 对应测试点：`TQ-RAG-PAR-004`：下载响应体上限。验证目标：下载超量或失败不能发布。
- 需求来源：RAG-011、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有界流式响应生成器，无需大文件全部入内存。
- 测试数据要求：100MiB及+1字节、伪小Content-Length、截断、4xx/5xx。
- 测试流程：
  1. 逐组安全下载。
  2. 核对实际累计上限生效、失败包不归一化发布，等上限在其他条件合法时可进入下一步。
- 预期结果：声明长度不可信，流式累计超过产物100MiB等冻结限额立即失败；截断/非成功响应不能当合法完整解析包。
- 代码依据／主要定位：[`backend/infrastructure/rag/download_safety.py`](../../backend/infrastructure/rag/download_safety.py)：SafeHTTP/PublicNetworkBackend；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download。
- 优先级：P0。
- 用例类型：边界/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；等于下载上限允许；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_005"></a>

#### PAR_005：解析ZIP成员安全

- 用例编号：`PAR_005`
- 对应测试点：`TQ-RAG-PAR-005`：解析ZIP成员安全。验证目标：包成员不越过私有根目录。
- 需求来源：RAG-011、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；local-only合成ZIP，含正常full.md对照。
- 测试数据要求：../绝对路径/符号链接/重复冲突/加密/嵌套包。
- 测试流程：
  1. 调用生产normalize_package及隔离物化。
  2. 逐项核拒绝、临时根外文件无变化，安全错误不泄露路径。
- 预期结果：路径逃逸/绝对路径/符号链接/重复冲突/加密或嵌套包拒绝；不执行或读取宿主任意文件，错误不暴露路径。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package。
- 优先级：P0。
- 用例类型：安全。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_006"></a>

#### PAR_006：解包资源上限

- 用例编号：`PAR_006`
- 对应测试点：`TQ-RAG-PAR-006`：解包资源上限。验证目标：压缩炸弹在物化前受限。
- 需求来源：RAG-011、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每次只改变一个资源阈值，其余输入有效。
- 测试数据要求：10000/10001成员、256MiB±1、64MiB±1、压缩比100/超100。
- 测试流程：
  1. 用有界流或稀疏合成ZIP逐项验证。
  2. 等上限不因该项失败，超过时在无限展开前拒绝，清理本例临时文件。
- 预期结果：验证条目≤10000、总展开≤256MiB、单成员≤64MiB、压缩比≤100；其他条件满足时等于上限不因该项拒绝，超过任一项失败，不能先无限解压再清理；子进程超时/内存限制另由隔离点验证。
- 补充判定／证据边界：总展开256MiB正例由多个≤64MiB成员组成，压缩比不超100；不能用单成员超限或高压缩率把另一阈值的正例误判为失败。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/infrastructure/rag/isolated_processing.py`](../../backend/infrastructure/rag/isolated_processing.py)：isolated/_isolated/main。
- 优先级：P0。
- 用例类型：边界/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；条目等于上限允许；总展开等于上限；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_007"></a>

#### PAR_007：full.md与整体协议

- 用例编号：`PAR_007`
- 对应测试点：`TQ-RAG-PAR-007`：full.md与整体协议。验证目标：可识别且唯一的文本产物才归一化。
- 需求来源：RAG-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；合成包语法与正文协议可独立控制。
- 测试数据要求：缺full.md、两个冲突full.md、损坏ZIP/未知整体结构、唯一合法md。
- 测试流程：
  1. 逐包归一化。
  2. 核对只有明确支持且唯一的正文能成功，失败不任选文件/补下载图片。
- 预期结果：缺失/多份冲突full.md、坏ZIP/不支持整体结构明确失败，不以任选一个文件或下载图片补齐文本蒙混成功。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package。
- 优先级：P0。
- 用例类型：契约/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；拒绝原因与约定一致；唯一正文正常；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_008"></a>

#### PAR_008：无有效文本失败

- 用例编号：`PAR_008`
- 对应测试点：`TQ-RAG-PAR-008`：无有效文本失败。验证目标：只有图片或空白不能成功索引。
- 需求来源：RAG-010、RAG-015。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；合法ZIP但正文内容可控。
- 测试数据要求：仅图片引用、空白、无正文；非空正文对照。
- 测试流程：
  1. 归一化并尝试完整索引。
  2. 空产物MINERU_EMPTY_OUTPUT且无active发布，网络观察无隐式OCR/远端资产加载。
- 预期结果：图片Markdown、空白或无可用正文产物返回MINERU_EMPTY_OUTPUT；不加载外链图片/资源做隐式OCR或本地解析回退。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/infrastructure/rag/html_tables.py`](../../backend/infrastructure/rag/html_tables.py)：安全表格文本化。
- 优先级：P0。
- 用例类型：异常/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；拒绝原因与约定一致；真实文本对照；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_009"></a>

#### PAR_009：表格安全文本化

- 用例编号：`PAR_009`
- 对应测试点：`TQ-RAG-PAR-009`：表格安全文本化。验证目标：返回表格可用于文本RAG。
- 需求来源：RAG-010、RAG-015。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；安全表格归一化函数可直接调用。
- 测试数据要求：HTML/Markdown表格含标题/合并文字/数值、script/事件/远程img。
- 测试流程：
  1. 归一化再切片，逐文本/表头和值核对。
  2. 危险标签与资源移除且不执行公式或宏。
- 预期结果：受支持HTML/Markdown表格保留可核对的文本/值和结构边界，去除危险标签/脚本/远程资产；不声称执行Excel公式或宏。
- 代码依据／主要定位：[`backend/infrastructure/rag/html_tables.py`](../../backend/infrastructure/rag/html_tables.py)：安全表格文本化；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package。
- 优先级：P1。
- 用例类型：功能/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；表格文本和值保留；脚本标签移除；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_010"></a>

#### PAR_010：txt行来源映射

- 用例编号：`PAR_010`
- 对应测试点：`TQ-RAG-PAR-010`：txt行来源映射。验证目标：文本规范范围可回溯真实行。
- 需求来源：RAG-015、RAG-017、RAG-043。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例txt源经本地解析。
- 测试数据要求：首尾空行、CRLF、多行中文emoji、无末换行。
- 测试流程：
  1. 核对规范文本与每个block。
  2. 独立计算每段对应行号和0基右开字符交集，确认不是UTF-8字节坐标。
- 预期结果：UTF-8 txt按本地规则成块，行号1起算、规范字符0基右开；空行/多行/Unicode/末行场景映射内容一致，不误作源字节偏移。
- 代码依据／主要定位：[`backend/infrastructure/rag/local_structure.py`](../../backend/infrastructure/rag/local_structure.py)：parse_text；[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations。
- 优先级：P1。
- 用例类型：功能/位置。
- 是否适合自动化：是。
- 实际测试结果：通过；26项断言；块正文区间；所有非空白正文完整覆盖；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/PAR_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_011"></a>

#### PAR_011：Markdown结构保留

- 用例编号：`PAR_011`
- 对应测试点：`TQ-RAG-PAR-011`：Markdown结构保留。验证目标：本地结构化不静默丢正文。
- 需求来源：RAG-015、RAG-016、RAG-043。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本地Markdown结构解析路径。
- 测试数据要求：多级标题/段落/围栏代码/表格/未覆盖非空文本及HTML。
- 测试流程：
  1. 解析并按blocks重建规范文本。
  2. 每段正文覆盖不丢，顺序/区间可对照。
  3. 无脚本或外部请求。
- 预期结果：标题层级/段落/代码/受支持表格及未覆盖的非空文本形成有序块，text与块区间对应；不执行HTML/公式或请求远端资产。
- 代码依据／主要定位：[`backend/infrastructure/rag/local_structure.py`](../../backend/infrastructure/rag/local_structure.py)：parse_text。
- 优先级：P1。
- 用例类型：功能。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；规范正文保留输入；所有非空白正文完整覆盖；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/PAR_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_012"></a>

#### PAR_012：可靠PDF原页映射

- 用例编号：`PAR_012`
- 对应测试点：`TQ-RAG-PAR-012`：可靠PDF原页映射。验证目标：只有可靠唯一映射标原源页。
- 需求来源：RAG-010、RAG-017、RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；受控PDF云包及content-list文本映射。
- 测试数据要求：唯一精确匹配page_idx=0/1；重复文本、无匹配、非法page_idx。
- 测试流程：
  1. 分别归一化读locations。
  2. 可靠唯一匹配页码+1，其余仅规范块并标缺失，不猜页。
- 预期结果：content-list文本唯一精确匹配且page_idx合法时页码+1；重复/无匹配/坏映射不得猜页，规范区间仍对应实际正文。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations。
- 优先级：P0。
- 用例类型：位置/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；可靠/缺失原页映射；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_013"></a>

#### PAR_013：缺少原源位置的明示

- 用例编号：`PAR_013`
- 对应测试点：`TQ-RAG-PAR-013`：缺少原源位置的明示。验证目标：缺坐标不能被猜成精确来源。
- 需求来源：RAG-010、RAG-017、RAG-030、RAG-042。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Office云包及安全来源投影。
- 测试数据要求：Word派生页、PPT/Excel无slide/sheet/cell可靠映射。
- 测试流程：
  1. 归一化再经API读取。
  2. 核对normalized/block_only与block_id，不能输出0页/伪原页，必要正文仍可读。
- 预期结果：Word派生页、PPT/Excel缺幻灯片/工作表/单元格映射时标normalized/block_only；规范block仍能定位实际文本，不能将缺失伪造为0或源页，不把派生版面序号当原源坐标。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations；[`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py)：Document/IndexBuild/Location/ChunkPolicy。
- 优先级：P0。
- 用例类型：位置/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；缺原位置明确规范块：.doc；缺原位置明确规范块：.xlsx；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="par_014"></a>

#### PAR_014：可选位置文件畸形

- 用例编号：`PAR_014`
- 对应测试点：`TQ-RAG-PAR-014`：可选位置文件畸形。验证目标：可选坐标失败不制造错误定位。
- 需求来源：RAG-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：mineru；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；正文始终有效，单独变更可选坐标文件。
- 测试数据要求：坏JSON、超限content-list、未知可选结构、整体协议损坏。
- 测试流程：
  1. 逐包处理。
  2. 核对可选映射不可用与整体不支持分开记录，不能把畸形映射声明为可靠坐标。
- 预期结果：有效正文加畸形/超限/未知content-list时按支持协议处理：可选映射不可用则明确记录，整体协议坏则失败；两者不能一概当成功可靠页。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package。
- 优先级：P1。
- 用例类型：异常/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；可选位置缺失不丢正文；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-mineru/mineru/PAR_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories mineru -RunId rag-repro-mineru-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.5 CHK：切片边界与片段身份

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-CHK-001` | [CHK_001：切片参数边界](#chk_001) | L | chunking／local |
| `TQ-RAG-CHK-002` | [CHK_002：结构优先结束点](#chk_002) | L | chunking／local |
| `TQ-RAG-CHK-003` | [CHK_003：字符兼容模式](#chk_003) | L | chunking／local |
| `TQ-RAG-CHK-004` | [CHK_004：超长块与字节配额](#chk_004) | L | chunking／local |
| `TQ-RAG-CHK-005` | [CHK_005：重叠与前进性](#chk_005) | L | chunking／local |
| `TQ-RAG-CHK-006` | [CHK_006：Chunk总数上限](#chk_006) | L | chunking／local |
| `TQ-RAG-CHK-007` | [CHK_007：Chunk序号与文本hash](#chk_007) | L | chunking／local |
| `TQ-RAG-CHK-008` | [CHK_008：块区间和裁剪来源](#chk_008) | L | chunking／local |
| `TQ-RAG-CHK-009` | [CHK_009：已发布片段不可变](#chk_009) | L | chunking／local |
| `TQ-RAG-CHK-010` | [CHK_010：切片任务子进程隔离](#chk_010) | L | chunking／local |

<a id="chk_001"></a>

#### CHK_001：切片参数边界

- 用例编号：`CHK_001`
- 对应测试点：`TQ-RAG-CHK-001`：切片参数边界。验证目标：非法size/overlap在执行前拒绝。
- 需求来源：RAG-016。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同一规范Artifact及独立Build请求。
- 测试数据要求：默认800/120；size1/16000/0/16001、overlap0/size-1/size/-1、bool与未知mode。
- 测试流程：
  1. 先经接口校验再调用split_artifact。
  2. 合法读回冻结参数，非法拒绝且不发布，不把布尔当整数。
- 预期结果：size为1～16000整数且0≤overlap<size，未知mode拒绝；默认800/120及结构/字符两模式可冻结读回，不接受布尔假整数。
- 补充判定／证据边界：既检查HTTP/DTO也检查切片函数。若DTO先把布尔转换为整数而纯函数能拒绝，按两个边界分别记录；不能仅通过函数测试掩盖入口的参数差异。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact；[`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py)：Document/IndexBuild/Location/ChunkPolicy；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：契约/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；45项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_002"></a>

#### CHK_002：结构优先结束点

- 用例编号：`CHK_002`
- 对应测试点：`TQ-RAG-CHK-002`：结构优先结束点。验证目标：结构边界按冻结算法生效。
- 需求来源：RAG-016。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；含确定结构边界的Artifact。
- 测试数据要求：size=100，块结尾在目标窗后半段与无合适边界两组。
- 测试流程：
  1. 执行structure_v1并独立计算可选末尾边界。
  2. 对照分片覆盖，超长块可拆但不能丢正文。
- 预期结果：构造目标后半段有/无块结尾的文本，结构模式优先合理块边界，仍覆盖正文；不要要求永不拆表格/长块这种未承诺能力。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact；[`backend/infrastructure/rag/local_structure.py`](../../backend/infrastructure/rag/local_structure.py)：parse_text。
- 优先级：P1。
- 用例类型：功能。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；结构模式优先合理块尾；无合理边界按窗结束；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_003"></a>

#### CHK_003：字符兼容模式

- 用例编号：`CHK_003`
- 对应测试点：`TQ-RAG-CHK-003`：字符兼容模式。验证目标：字符窗口产生可对照范围。
- 需求来源：RAG-016。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；与结构模式相同Artifact。
- 测试数据要求：character_v1、size100/overlap20及默认对照。
- 测试流程：
  1. 按冻结字符策略切分。
  2. 逐片核text=规范区间切片、位置有效，不声称等于旧DOCX本地解析。
- 预期结果：同一Artifact用character_v1与显式size/overlap分割，文本等于对应规范范围，保留来源映射，不伪装成旧本地DOCX解析结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact。
- 优先级：P1。
- 用例类型：兼容/功能。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；兼容字符窗；字符模式不丢来源；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_004"></a>

#### CHK_004：超长块与字节配额

- 用例编号：`CHK_004`
- 对应测试点：`TQ-RAG-CHK-004`：超长块与字节配额。验证目标：每片在外发前满足已声明输入限额。
- 需求来源：RAG-016。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Mock向量Profile声明小型max_input_bytes。
- 测试数据要求：长中文/emoji/混排、单字符最多4字节、超长单块。
- 测试流程：
  1. 切片并记录送向量实际字节。
  2. 每片均在冻结字符/字节上限内，无Provider静默截断。
- 预期结果：长中文/emoji/混合文本按字符与UTF-8字节共同拆分，单片不超过冻结预算，不借Provider静默截断；真实token校准另由counter点判断。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；74项断言；每片双预算；所有非空白正文完整覆盖；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_005"></a>

#### CHK_005：重叠与前进性

- 用例编号：`CHK_005`
- 对应测试点：`TQ-RAG-CHK-005`：重叠与前进性。验证目标：重叠不导致丢字或死循环。
- 需求来源：RAG-016。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；避免空白省略影响正文覆盖判断的字符串。
- 测试数据要求：短源、overlap=size-1、字节上限缩窗、空白块。
- 测试流程：
  1. 切分并记录各游标/区间。
  2. 验证持续前进、非空正文覆盖、片数有界，不强求每片固定120重叠。
- 预期结果：短段、临近size的overlap及字节压缩片段下，验证实际重叠/游标持续前进、非空正文覆盖和有界数量；不假设每片必恰好120重叠。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact。
- 优先级：P0。
- 用例类型：边界/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；136项断言；切片数受输入长度界定；所有非空白正文完整覆盖；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_006"></a>

#### CHK_006：Chunk总数上限

- 用例编号：`CHK_006`
- 对应测试点：`TQ-RAG-CHK-006`：Chunk总数上限。验证目标：过多小片段明确失败。
- 需求来源：RAG-016、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有界生成单字符有效源，可只在纯切片层构造。
- 测试数据要求：49999/50000/50001片、空白对照。
- 测试流程：
  1. 分割并检查50000可返回、超过CHUNK_COUNT_LIMIT。
  2. 完整构建负例确认不发布部分候选。
- 预期结果：接近/超过50000片时有稳定CHUNK_COUNT_LIMIT或同义安全错误，不发布部分候选；空白片段不占造假的有效结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；有效片上限前/等于；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_007"></a>

#### CHK_007：Chunk序号与文本hash

- 用例编号：`CHK_007`
- 对应测试点：`TQ-RAG-CHK-007`：Chunk序号与文本hash。验证目标：片段事实身份自洽。
- 需求来源：RAG-017。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两文档同文以及同源两次重建。
- 测试数据要求：每批次chunk_id/seq/text/hash/start/end。
- 测试流程：
  1. 分别构建并读取PG/公开片段。
  2. 验证seq连续、hash独立重算、重建新身份、跨文档不以hash合并。
- 预期结果：同批次seq连续、文本hash等于规范区间内容，新重建产生新身份；相同text跨文档仍不同Chunk，不用hash抹平来源。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/db/models.py`](../../backend/db/models.py)：DocumentModel/ChunkModel/TaskModel/RunModel；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；新批次新片段身份；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_008"></a>

#### CHK_008：块区间和裁剪来源

- 用例编号：`CHK_008`
- 对应测试点：`TQ-RAG-CHK-008`：块区间和裁剪来源。验证目标：切片保留实际覆盖块与位置。
- 需求来源：RAG-017、RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；带多block和可裁剪行来源的Artifact。
- 测试数据要求：跨块、半行、重叠片段、中文字符区间。
- 测试流程：
  1. 逐片将block_segments/locations与独立区间交集比较。
  2. 零长/越界禁止，序号不当页码。
- 预期结果：跨块/半行/重叠时block_segments与locations裁到真实交集，右开区间非空且页/行来源语义一致；不能把Chunk序号当页码。
- 代码依据／主要定位：[`backend/infrastructure/rag/structured_chunker.py`](../../backend/infrastructure/rag/structured_chunker.py)：split_artifact；[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations；[`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py)：Document/IndexBuild/Location/ChunkPolicy。
- 优先级：P0。
- 用例类型：位置/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；块范围裁剪真实交集；来源也裁剪到片内；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_009"></a>

#### CHK_009：已发布片段不可变

- 用例编号：`CHK_009`
- 对应测试点：`TQ-RAG-CHK-009`：已发布片段不可变。验证目标：发布后不能原地修改证据。
- 需求来源：RAG-017、RAG-020、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG上已发布成功批次。
- 测试数据要求：尝试UPDATE text/embedding/range及合法新Build。
- 测试流程：
  1. 在回滚事务中改成功Chunk。
  2. 检查约束拒绝、原内容hash不变。
  3. 新批次可表达新切片。
- 预期结果：直接修改成功批次Chunk文本/向量/范围等核心事实被PG约束拒绝；后续新切片必须新批次，不通过双写掩盖破坏性修改。
- 代码依据／主要定位：[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：一致性/数据库。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="chk_010"></a>

#### CHK_010：切片任务子进程隔离

- 用例编号：`CHK_010`
- 对应测试点：`TQ-RAG-CHK-010`：切片任务子进程隔离。验证目标：取消和超限不留后台处理。
- 需求来源：RAG-011、RAG-016、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：chunking；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Docker Linux内生产isolated调用及进程观察。
- 测试数据要求：解析/解包/切片耗时超时、CPU/内存压力、取消。
- 测试流程：
  1. 分别运行并触发限制。
  2. 核对kill后wait完成、子进程无残留和安全错误，限额只对Linux实测范围作结论。
- 预期结果：本地解析/解包/切片达到timeout或取消后kill并wait，Linux验证CPU/内存限额，Windows直接进程缺等价RLIMIT明确列限制，不能宣称完全沙箱。
- 代码依据／主要定位：[`backend/infrastructure/rag/isolated_processing.py`](../../backend/infrastructure/rag/isolated_processing.py)：isolated/_isolated/main。
- 优先级：P0。
- 用例类型：安全/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；超时稳定拒绝；取消后槽位释放；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-chunking/chunking/CHK_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories chunking -RunId rag-repro-chunking-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.6 VEC：向量协议、空间与输入计数

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-VEC-001` | [VEC_001：维度范围与适配约束](#vec_001) | L | vectors／local |
| `TQ-RAG-VEC-002` | [VEC_002：Embedding批量身份映射](#vec_002) | L | vectors／local |
| `TQ-RAG-VEC-003` | [VEC_003：向量数值有效性](#vec_003) | L | vectors／local |
| `TQ-RAG-VEC-004` | [VEC_004：文档查询归一化一致](#vec_004) | L | vectors／local |
| `TQ-RAG-VEC-005` | [VEC_005：输入批量与长度拒绝](#vec_005) | L | vectors／local |
| `TQ-RAG-VEC-006` | [VEC_006：查询用途与文档用途一致](#vec_006) | L | vectors／local |
| `TQ-RAG-VEC-007` | [VEC_007：Embedding故障不转空成功](#vec_007) | L | vectors／local |
| `TQ-RAG-VEC-008` | [VEC_008：DB空间维度关系约束](#vec_008) | L | vectors／local |
| `TQ-RAG-VEC-009` | [VEC_009：真实文档向量入库](#vec_009) | B | real-business／real |
| `TQ-RAG-VEC-010` | [VEC_010：真实查询向量召回](#vec_010) | B | real-business／real |

<a id="vec_001"></a>

#### VEC_001：维度范围与适配约束

- 用例编号：`VEC_001`
- 对应测试点：`TQ-RAG-VEC-001`：维度范围与适配约束。验证目标：声明维度与支持配置一致。
- 需求来源：RAG-018。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例空间配置与向量验证可独立调用。
- 测试数据要求：维度0/1/384/1024/2000/2001，百炼受支持/不支持配置。
- 测试流程：
  1. 逐配置解析及验证。
  2. 合法通用维度不代表百炼任意模型支持，错误配置在外发前拒绝。
- 预期结果：通用空间接受1～2000，0/2001拒绝；Mock384及不同维度可测，真实百炼当前仅已锁定模型/1024规则，不将通用范围当所有模型都支持。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters；[`backend/application/vector_validation.py`](../../backend/application/vector_validation.py)：validate_vector/normalize_l2_float32。
- 优先级：P0。
- 用例类型：边界/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；通用支持维度；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_002"></a>

#### VEC_002：Embedding批量身份映射

- 用例编号：`VEC_002`
- 对应测试点：`TQ-RAG-VEC-002`：Embedding批量身份映射。验证目标：响应按index还原每条输入。
- 需求来源：RAG-019。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生产百炼Embedding适配器使用fixture transport，仅标协议模拟。
- 测试数据要求：3条输入的乱序正确index；缺/重/多/非整index及数量不符。
- 测试流程：
  1. 送固定文本数组并返回各响应。
  2. 核对输入顺序与向量一一对应，非法集合明确协议错误。
- 预期结果：模拟乱序有效index恢复输入顺序，缺失/重复/多余/index非整数/数量不符失败；不能把向量配给另一Chunk。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：契约。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；乱序恢复原数量；向量输入顺序原样发送；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_003"></a>

#### VEC_003：向量数值有效性

- 用例编号：`VEC_003`
- 对应测试点：`TQ-RAG-VEC-003`：向量数值有效性。验证目标：无效向量进入存储前失败。
- 需求来源：RAG-019。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；向量验证函数和入库/query两入口。
- 测试数据要求：NaN/Inf/超float32范围/字符串/错维/零范数/下溢全零。
- 测试流程：
  1. 分别验证并尝试构建/检索。
  2. 坏向量在存储或距离前失败，无部分发布或假empty。
- 预期结果：NaN/Inf/极大值/非数字/零范数或错维拒绝，float32下溢后全零也失败；不能把坏向量当零分空检索。
- 代码依据／主要定位：[`backend/application/vector_validation.py`](../../backend/application/vector_validation.py)：validate_vector/normalize_l2_float32；[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search。
- 优先级：P0。
- 用例类型：边界/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；拒绝原因与约定一致；有效向量可用；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_004"></a>

#### VEC_004：文档查询归一化一致

- 用例编号：`VEC_004`
- 对应测试点：`TQ-RAG-VEC-004`：文档查询归一化一致。验证目标：写查使用同一空间数值协议。
- 需求来源：RAG-002、RAG-019。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可独立计算float32及L2参考值。
- 测试数据要求：固定非零384/1024向量、document/query同revision。
- 测试流程：
  1. 分别生成两种用途向量并读取实际存储值。
  2. 与独立算法按适当浮点容差核对，归一化约定一致。
- 预期结果：l2_float32_v1在document/query均先校验再归一化到实际存储精度，与独立计算一致；同revision不一边none一边l2。
- 代码依据／主要定位：[`backend/application/vector_validation.py`](../../backend/application/vector_validation.py)：validate_vector/normalize_l2_float32；[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile。
- 优先级：P0。
- 用例类型：功能/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；归一化到实际float32精度；文档/查询相同归一化；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_005"></a>

#### VEC_005：输入批量与长度拒绝

- 用例编号：`VEC_005`
- 对应测试点：`TQ-RAG-VEC-005`：输入批量与长度拒绝。验证目标：向量请求不超冻结本地配额。
- 需求来源：RAG-016、RAG-019、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生产字节预算校验不放宽counter守卫。
- 测试数据要求：batch_size16/17、空文本、max_input_bytes前/等于/+1。
- 测试流程：
  1. 逐输入调用受控Port/适配器。
  2. 非法组统计外发0，合法字节组可受理但不得据此声称token已校准。
- 预期结果：超过batch_size≤16、空文本、超max_input_bytes时外发前失败；明确该字节验证可测，但不替代真实模型token上界证明。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；拒绝原因与约定一致；合法批量/输入边界；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_006"></a>

#### VEC_006：查询用途与文档用途一致

- 用例编号：`VEC_006`
- 对应测试点：`TQ-RAG-VEC-006`：查询用途与文档用途一致。验证目标：同空间用途映射不漂移。
- 需求来源：RAG-002、RAG-018。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实适配协议用受控HTTP记录摘要。
- 测试数据要求：相同原文document/query、冻结model/dimensions/encoding。
- 测试流程：
  1. 分别生成请求并对照生产载荷。
  2. 用途及identity无隐式前缀，生成ModelProfile变更不改变请求空间。
- 预期结果：受控HTTP检查两类请求均使用冻结model/dimensions/encoding格式及identity用途约定，不擅加前缀或跟随生成模型配置。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：协议。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；两用途完全同一冻结映射；不擅加厂商字段；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_007"></a>

#### VEC_007：Embedding故障不转空成功

- 用例编号：`VEC_007`
- 对应测试点：`TQ-RAG-VEC-007`：Embedding故障不转空成功。验证目标：向量依赖失败保持错误身份。
- 需求来源：RAG-019、RAG-020、RAG-028。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已有旧active与独立query失败路径。
- 测试数据要求：认证/网络/429/5xx/坏JSON/坏向量。
- 测试流程：
  1. 逐组触发入库和检索。
  2. 记录有限重试或明确失败，旧active保留，不换Mock、不把基础设施故障写empty。
- 预期结果：注入认证/网络/429/5xx或坏响应，按稳定错误终止/有限重试，不能切Mock、跳向量发布或返回empty掩盖故障。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：异常。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；拒绝原因与约定一致；坏向量无法发布；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_008"></a>

#### VEC_008：DB空间维度关系约束

- 用例编号：`VEC_008`
- 对应测试点：`TQ-RAG-VEC-008`：DB空间维度关系约束。验证目标：持久化不能混入错误空间向量。
- 需求来源：RAG-002、RAG-018、RAG-019。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG及候选专属夹具事务。
- 测试数据要求：错space/dimension/vector_dims、跨库batch、新造legacy_unverified。
- 测试流程：
  1. 逐项INSERT/UPDATE后回滚。
  2. 确认FK/触发器拒绝且合法384/1024对照成立，不能用SQLite替代。
- 预期结果：真实PG拒绝space/dimension/vector_dims不符及跨库批次，兼容旧未知例外受来源约束；直接SQL不能伪造新legacy_unverified数据。
- 代码依据／主要定位：[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器；[`backend/db/models.py`](../../backend/db/models.py)：DocumentModel/ChunkModel/TaskModel/RunModel。
- 优先级：P0。
- 用例类型：数据库/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；进入目标阶段前未异常终止；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/VEC_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="vec_009"></a>

#### VEC_009：真实文档向量入库

- 用例编号：`VEC_009`
- 对应测试点：`TQ-RAG-VEC-009`：真实文档向量入库。验证目标：生产入口实际完成真实Embedding。
- 需求来源：RAG-018、RAG-044。
- 当前可验证性：暂不可完整验证·B（真实输入计数依据及校准未完成，生产守卫阻断）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：计数校准、真实Embedding配置及MinerU原件均满足才执行。
- 测试数据要求：独立真实1024空间、同轮获准办公源、冻结Profile和hash。
- 测试流程：
  1. 正式上传/解析/切片/真实document embedding到active。
  2. 查安全请求关联和PG向量，不能用直调探针或Mock代替。
- 预期结果：校准通过后新库绑定真实1024空间，办公Artifact切片经真实文档Embedding发布active，安全记录模型/版本/计数/维度；直调两条向量探针不能代替。
- 暂缓标记：真实计数依据/校准未完成，当前正式生产守卫阻断；解除条件见第3节B项，不使用替身凑成真实通过。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_embedding.py`](../../backend/infrastructure/providers/bailian_embedding.py)：BailianEmbedding.embed；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是。
- 实际测试结果：暂不可验证：真实Embedding计数门槛未满足，正式真实空间入库仍阻止；有限切片预算已修复，不能再归因为50000片预留。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="vec_010"></a>

#### VEC_010：真实查询向量召回

- 用例编号：`VEC_010`
- 对应测试点：`TQ-RAG-VEC-010`：真实查询向量召回。验证目标：同真实空间完成query向量与检索。
- 需求来源：RAG-018、RAG-023、RAG-044。
- 当前可验证性：暂不可完整验证·B（真实输入计数依据及校准未完成，生产守卫阻断）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：本例独立建立真实库，不依赖VEC_009执行结果。
- 测试数据要求：真实query与已标相关正文、冻结1024空间。
- 测试流程：
  1. 经正式Run或诊断送query。
  2. 核对真实向量请求及PG返回本批次，输入计数/模型身份与文档空间一致。
- 预期结果：从真实已发布库经正式Run/诊断发query，真实适配返回合法向量并在PG召回该批次，不能以Mock384或关闭检索跳过；当前依计数门禁及新入库前置。
- 暂缓标记：真实计数依据/校准未完成，当前正式生产守卫阻断；解除条件见第3节B项，不使用替身凑成真实通过。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是。
- 实际测试结果：暂不可验证：真实Embedding计数门槛未满足，不能用Mock空间或独立协议探针替代生产query向量验证。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

### 4.7 IDX：候选构建、发布与并发

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-IDX-001` | [IDX_001：构建快照冻结](#idx_001) | L | vectors／local |
| `TQ-RAG-IDX-002` | [IDX_002：候选索引不可见](#idx_002) | L | vectors／local |
| `TQ-RAG-IDX-003` | [IDX_003：完整manifest发布](#idx_003) | L | vectors／local |
| `TQ-RAG-IDX-004` | [IDX_004：缺片段或坏hash拒绝发布](#idx_004) | L | vectors／local |
| `TQ-RAG-IDX-005` | [IDX_005：失败与取消保护旧active](#idx_005) | L | vectors／local |
| `TQ-RAG-IDX-006` | [IDX_006：旧代发布权限失效](#idx_006) | L | vectors／local |
| `TQ-RAG-IDX-007` | [IDX_007：锁等待后的授权时间复查](#idx_007) | L | vectors／local |
| `TQ-RAG-IDX-008` | [IDX_008：阶段恢复幂等](#idx_008) | L | vectors／local |
| `TQ-RAG-IDX-009` | [IDX_009：active/latest同文档约束](#idx_009) | L | vectors／local |
| `TQ-RAG-IDX-010` | [IDX_010：跨知识库冻结发布竞争](#idx_010) | L | vectors／local |
| `TQ-RAG-IDX-011` | [IDX_011：已发布构建配置不可改](#idx_011) | L | vectors／local |

<a id="idx_001"></a>

#### IDX_001：构建快照冻结

- 用例编号：`IDX_001`
- 对应测试点：`TQ-RAG-IDX-001`：构建快照冻结。验证目标：执行不读取后改默认配置。
- 需求来源：RAG-009、RAG-017、RAG-020。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例Build/Job已登记但未处理。
- 测试数据要求：修改默认Parser/切片/Embedding版本配置。
- 测试流程：
  1. 读登记快照后改默认并推进。
  2. 核对实际请求/产物manifest始终原版本/hash/source，不能拼入新版结果。
- 预期结果：登记后改Parser/切片/向量默认设置，Build/Job仍使用原hash/版本/source，不能把新配置产物拼进原manifest。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；正式任务完整成功；原快照固定；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_002"></a>

#### IDX_002：候选索引不可见

- 用例编号：`IDX_002`
- 对应测试点：`TQ-RAG-IDX-002`：候选索引不可见。验证目标：未发布内容不参与正常检索。
- 需求来源：RAG-008、RAG-020、RAG-024。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；旧active和独立空库两组，阶段屏障可控。
- 测试数据要求：parse/chunk/embed/publish前分别暂停。
- 测试流程：
  1. 每阶段查询文档及创建新View。
  2. 只见旧active或空集合，候选即使已有部分Chunk也不得检索。
- 预期结果：分别在parse/chunk/embed/publish前屏障查询，候选Chunk或部分向量不可召回，新Run只冻结成功active；空库不能半发布。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：隔离。
- 是否适合自动化：是。
- 实际测试结果：通过；40项断言；候选阶段不切active：parse；候选不进入冻结View：publish；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_003"></a>

#### IDX_003：完整manifest发布

- 用例编号：`IDX_003`
- 对应测试点：`TQ-RAG-IDX-003`：完整manifest发布。验证目标：成功构建一次原子切换。
- 需求来源：RAG-017、RAG-020、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG完整候选，独立读连接。
- 测试数据要求：完整count/seq/hash/space/vector manifest。
- 测试流程：
  1. 屏障停在提交前后持续读取。
  2. 核对Build/active/scope_revision/Task同事务切换，不出现半批次。
- 预期结果：核对Chunk数量/连续seq/hash/空间/向量完整后，在同PG事务更新Build成功、Document.active、scope_revision及Task成功，读者无半批次。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：事务/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；13项断言；正式任务完整成功；发布片数完整；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_004"></a>

#### IDX_004：缺片段或坏hash拒绝发布

- 用例编号：`IDX_004`
- 对应测试点：`TQ-RAG-IDX-004`：缺片段或坏hash拒绝发布。验证目标：不完整候选不能成为active。
- 需求来源：RAG-019、RAG-020。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；仅破坏未发布候选夹具，不触碰不可变成功批次。
- 测试数据要求：缺Chunk、非连续seq、错text hash、缺向量。
- 测试流程：
  1. 逐组尝试发布。
  2. 记录安全拒绝、事务回滚及旧active/hash不变。
- 预期结果：在受控候选数据中破坏数量/seq/text hash/向量完整性，发布失败且旧active保留；不可变成功批次不作为故障注入写坏目标。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：异常/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；53项断言；进入目标阶段前未异常终止；候选损坏拒绝发布：vector；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_005"></a>

#### IDX_005：失败与取消保护旧active

- 用例编号：`IDX_005`
- 对应测试点：`TQ-RAG-IDX-005`：失败与取消保护旧active。验证目标：新尝试失败不清旧索引。
- 需求来源：RAG-020、RAG-022、RAG-040。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例先独立发布旧批次。
- 测试数据要求：parse/chunk/embed失败、取消、deadline各组。
- 测试流程：
  1. 发新重建并注入故障。
  2. 读取Document和检索旧active，latest指本次失败/取消，不被旧成功覆盖。
- 预期结果：解析/切片/Embedding任一步失败、取消或截止，旧active仍ready且可检索，latest显示最新失败/取消而非回指旧成功掩盖原因。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：状态。
- 是否适合自动化：是。
- 实际测试结果：通过；30项断言；正式任务完整成功；旧active保留：deadline；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_006"></a>

#### IDX_006：旧代发布权限失效

- 用例编号：`IDX_006`
- 对应测试点：`TQ-RAG-IDX-006`：旧代发布权限失效。验证目标：换代后旧Worker不得提交。
- 需求来源：RAG-012、RAG-020、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个Worker及外发后有界屏障。
- 测试数据要求：代1失租后代2领取成功，代1迟到产物。
- 测试流程：
  1. 控制代1释放响应时机。
  2. 查worker/generation条件拒绝迟到提交，代2事实/active不受覆盖。
- 预期结果：构造代1外发后失租、代2成功，再放代1迟到；task_id/worker_id/generation不匹配写回被拒，原已发布新代不被覆盖。
- 代码依据／主要定位：[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task。
- 优先级：P0。
- 用例类型：并发/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；进入目标阶段前未异常终止；旧代不能覆盖新代成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_007"></a>

#### IDX_007：锁等待后的授权时间复查

- 用例编号：`IDX_007`
- 对应测试点：`TQ-RAG-IDX-007`：锁等待后的授权时间复查。验证目标：过期租约不能因已拿过锁而提交。
- 需求来源：RAG-020、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG双连接可控锁等待与事务内flush。
- 测试数据要求：有效初始lease，锁等待/flush期间lease或deadline过期。
- 测试流程：
  1. 持锁到截止后再放行发布。
  2. 核对最终提交前重查、回滚及active不变，不只断言首次授权。
- 预期结果：在锁等待/flush期间使lease或deadline到期，最后提交前再次核时，事务回滚且active不变；不能仅首次锁时判断有效。
- 代码依据／主要定位：[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：并发/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；进入目标阶段前未异常终止；成功事实回滚；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_008"></a>

#### IDX_008：阶段恢复幂等

- 用例编号：`IDX_008`
- 对应测试点：`TQ-RAG-IDX-008`：阶段恢复幂等。验证目标：分批写入重试不产生重复Chunk。
- 需求来源：RAG-012、RAG-017、RAG-020。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；分阶段持久检查点和独立Worker重启能力。
- 测试数据要求：chunk完成/embedding检查点、同Build固定输入。
- 测试流程：
  1. 各检查点停止Worker再接管。
  2. 核对继续原Build，Chunk身份/计数/hash符合检查点，不新建Document或重复发布。
- 预期结果：chunk/embed检查点间杀Worker后新代恢复同Build，已完成批次不重复造身份，最终计数与hash一致，不创建新Document。
- 代码依据／主要定位：[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；9项断言；跨Worker续同一Build成功；检查点不重复写片；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_009"></a>

#### IDX_009：active/latest同文档约束

- 用例编号：`IDX_009`
- 对应测试点：`TQ-RAG-IDX-009`：active/latest同文档约束。验证目标：指针不能指另一文档构建。
- 需求来源：RAG-017、RAG-020、RAG-040。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG有两个文档的合法Build。
- 测试数据要求：A.active/latest指B的batch，登记新候选与成功发布对照。
- 测试流程：
  1. 非法关联SQL应FK拒绝。
  2. 分别读取登记后latest和发布后active，确认时点不同。
- 预期结果：直接写错误document/batch组合被FK拒绝；latest在登记时体现尝试，active仅发布时改变，二者不是同一状态。
- 代码依据／主要定位：[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/db/models.py`](../../backend/db/models.py)：DocumentModel/ChunkModel/TaskModel/RunModel；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：数据库/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_010"></a>

#### IDX_010：跨知识库冻结发布竞争

- 用例编号：`IDX_010`
- 对应测试点：`TQ-RAG-IDX-010`：跨知识库冻结发布竞争。验证目标：视图与发布不能读半完成范围。
- 需求来源：RAG-020、RAG-024、RAG-035。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同库多文档，PG发布/标签/冻结三连接屏障。
- 测试数据要求：新batch、标签变化、库外候选。
- 测试流程：
  1. 交错执行竞争并记录获锁顺序。
  2. 核对View manifest及items只来自一个合法完整快照，不含他库或候选。
- 预期结果：库锁下并发冻结View与发布/改标签，视图只取竞争前或后的合法完整集合，manifest与items一致，不混入候选或他库批次。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P0。
- 用例类型：并发。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；视图为竞争前/后完整集合；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="idx_011"></a>

#### IDX_011：已发布构建配置不可改

- 用例编号：`IDX_011`
- 对应测试点：`TQ-RAG-IDX-011`：已发布构建配置不可改。验证目标：历史构建保留原有含义。
- 需求来源：RAG-020、RAG-021、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：vectors；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已成功Build及Artifact，回滚事务。
- 测试数据要求：修改配置/hash/text、合法同源新Build。
- 测试流程：
  1. 逐字段尝试直接UPDATE并读旧证据。
  2. 成功事实被约束保护，新身份才可表达新配置。
- 预期结果：成功Build和Artifact核心配置/hash文本不可原地UPDATE；新版本由新Build表达，不能重写旧引用所依赖的来源。
- 代码依据／主要定位：[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：数据库/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；13项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-vectors/vectors/IDX_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories vectors -RunId rag-repro-vectors-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.8 RET：冻结检索、重排与诊断

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-RET-001` | [RET_001：检索query原文身份](#ret_001) | L | retrieval／local |
| `TQ-RAG-RET-002` | [RET_002：过滤维度组合语义](#ret_002) | L | retrieval／local |
| `TQ-RAG-RET-003` | [RET_003：过滤越权ID拒绝](#ret_003) | L | retrieval／local |
| `TQ-RAG-RET-004` | [RET_004：冻结后的新增批次不可见](#ret_004) | L | retrieval／local |
| `TQ-RAG-RET-005` | [RET_005：损坏视图禁止查最新兜底](#ret_005) | L | retrieval／local |
| `TQ-RAG-RET-006` | [RET_006：空视图合法empty](#ret_006) | L | retrieval／local |
| `TQ-RAG-RET-007` | [RET_007：PG内cosine排序一致](#ret_007) | L | retrieval／local |
| `TQ-RAG-RET-008` | [RET_008：距离计算前范围物化](#ret_008) | L | retrieval／local |
| `TQ-RAG-RET-009` | [RET_009：并列分数稳定顺序](#ret_009) | L | retrieval／local |
| `TQ-RAG-RET-010` | [RET_010：候选与命中数量边界](#ret_010) | L | retrieval／local |
| `TQ-RAG-RET-011` | [RET_011：关闭rerank无调用](#ret_011) | L | retrieval／local |
| `TQ-RAG-RET-012` | [RET_012：rerank同候选身份](#ret_012) | L | retrieval／local |
| `TQ-RAG-RET-013` | [RET_013：rerank分数独立](#ret_013) | L | retrieval／local |
| `TQ-RAG-RET-014` | [RET_014：rerank输入截取范围](#ret_014) | L | retrieval／local |
| `TQ-RAG-RET-015` | [RET_015：重排默认失败](#ret_015) | L | retrieval／local |
| `TQ-RAG-RET-016` | [RET_016：显式dense降级](#ret_016) | L | retrieval／local |
| `TQ-RAG-RET-017` | [RET_017：安全认证错误不得降级](#ret_017) | L | retrieval／local |
| `TQ-RAG-RET-018` | [RET_018：真实原生rerank响应](#ret_018) | B | real-business／real |
| `TQ-RAG-RET-019` | [RET_019：独立诊断不产生聊天事实](#ret_019) | L | retrieval／local |
| `TQ-RAG-RET-020` | [RET_020：诊断取消权限](#ret_020) | L | retrieval／local |
| `TQ-RAG-RET-021` | [RET_021：RAG模式区分](#ret_021) | L | retrieval／local |
| `TQ-RAG-RET-022` | [RET_022：Trace可追溯链](#ret_022) | L | retrieval／local |
| `TQ-RAG-RET-023` | [RET_023：视图规模上限](#ret_023) | L | retrieval／local |

<a id="ret_001"></a>

#### RET_001：检索query原文身份

- 用例编号：`RET_001`
- 对应测试点：`TQ-RAG-RET-001`：检索query原文身份。验证目标：查询不被隐式改写或截断。
- 需求来源：RAG-024、RAG-032。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立Thread锚定Message和诊断query均可控。
- 测试数据要求：原文含首尾空白/多语言/历史干扰；空白和超字节问题。
- 测试流程：
  1. 记录实际query embedding及query hash。
  2. 核对Run只用锚定原文、诊断只用显式原文，非法问题拒绝而非截前缀。
- 预期结果：Run使用锚定Message原文，诊断使用显式query；不拼历史/模型改写/多次查询；超字节上限或全空白明确失败，不静默切前缀。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/api/schemas/v3/retrieval.py`](../../backend/api/schemas/v3/retrieval.py)：RagSelection/DiagnosticCreate/EvidenceBundle。
- 优先级：P0。
- 用例类型：功能/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；空白query明确失败而非empty成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_002"></a>

#### RET_002：过滤维度组合语义

- 用例编号：`RET_002`
- 对应测试点：`TQ-RAG-RET-002`：过滤维度组合语义。验证目标：过滤集合严格按约定缩小范围。
- 需求来源：RAG-005、RAG-024。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同库四文档覆盖扩展名/多标签，固定向量。
- 测试数据要求：document_ids/extensions缺省、显式空、两值；tags_all空/两值。
- 测试流程：
  1. 按组合构建View并列出实际batch集合。
  2. 与独立集合运算对照，OR/AND/None/空集含义不混淆。
- 预期结果：document_ids/extensions内部OR、各维AND、tags_all全部满足；缺省不限、文档/类型显式空集为空、空标签不限；用多标签多类型独立对照。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；60项断言；正式任务完整成功；过滤范围组合：{'document_ids': ['5f44cb9e-4e49-4fc0-bd6f-f7e981ca4dd4', 'a9ff5d07-d3d2-44b4-9009-d951ec8bcced'], 'extensions': ['.md']}；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_003"></a>

#### RET_003：过滤越权ID拒绝

- 用例编号：`RET_003`
- 对应测试点：`TQ-RAG-RET-003`：过滤越权ID拒绝。验证目标：非法文档ID不能被静默忽略。
- 需求来源：RAG-024、RAG-033。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个库和两个owner分别有文档。
- 测试数据要求：同库合法+异库/越owner/不存在ID混合。
- 测试流程：
  1. 提交Run/诊断过滤。
  2. 观察整体拒绝及无外发，不得悄悄去非法项查询合法剩余。
- 预期结果：同库/异库/其他owner/不存在ID混合输入时范围无效明确拒绝，不仅跳过非法项返回其余；集合不能注入SQL或URL。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/domain/rag_profiles.py`](../../backend/domain/rag_profiles.py)：EmbeddingConfig/RerankConfig/ParserConfig/RetrievalFilters。
- 优先级：P0。
- 用例类型：权限。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_004"></a>

#### RET_004：冻结后的新增批次不可见

- 用例编号：`RET_004`
- 对应测试点：`TQ-RAG-RET-004`：冻结后的新增批次不可见。验证目标：旧视图只包含创建时批次。
- 需求来源：RAG-024、RAG-035、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；创建View时固定batch/tag快照。
- 测试数据要求：冻结后新增文档、重建active、修改标签。
- 测试流程：
  1. 在每次变化后用旧View检索并对照原集合。
  2. 新消息另冻结新View，验证只有新View看到变化。
- 预期结果：创建View后新上传/成功重建/改标签，重复检索仍原批次集合；新消息可见新active，不能后台按最新标签重展开旧view。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；34项断言；正式任务完整成功；新view取当前active；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_005"></a>

#### RET_005：损坏视图禁止查最新兜底

- 用例编号：`RET_005`
- 对应测试点：`TQ-RAG-RET-005`：损坏视图禁止查最新兜底。验证目标：视图不可用明确失败。
- 需求来源：RAG-024、RAG-028、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属可损坏视图夹具，PG约束不能伪装绕过。
- 测试数据要求：丢manifest/错hash/缺item依赖等能合法制造的损坏。
- 测试流程：
  1. 调用load_scope和检索。
  2. 能被DB先阻断的变体记录数据库拒绝，其余运行期安全失败，绝不查最新或返回假empty。
- 预期结果：丢失/不匹配manifest或已冻结item依赖损坏，返回稳定错误，不改查最新active、不跨库或返回empty伪装成功。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：异常/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；PG拒绝破坏冻结view；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_006"></a>

#### RET_006：空视图合法empty

- 用例编号：`RET_006`
- 对应测试点：`TQ-RAG-RET-006`：空视图合法empty。验证目标：空范围不制造付费检索。
- 需求来源：RAG-024、RAG-025、RAG-028。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；无成功active的库及合法显式空过滤。
- 测试数据要求：合法query、空白/超限query、blocked依赖对照。
- 测试流程：
  1. 分别执行。
  2. 合法空返回empty且embedding/rerank计数0。
  3. query/依赖验证失败仍明确失败。
- 预期结果：无成功批次或显式空过滤时成功empty，query及依赖仍按约定校验，Embedding/rerank未执行；不假称已查询生成答案相关证据。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：边界/依赖。
- 是否适合自动化：是。
- 实际测试结果：通过；7项断言；正式任务完整成功；空视图零付费能力调用；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_007"></a>

#### RET_007：PG内cosine排序一致

- 用例编号：`RET_007`
- 对应测试点：`TQ-RAG-RET-007`：PG内cosine排序一致。验证目标：数据库Top-K与独立距离相同。
- 需求来源：RAG-023、NFR-007、NFR-008。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG固定非零向量及授权范围。
- 测试数据要求：查询向量、3个已知cosine值、candidate_k、范围外近邻。
- 测试流程：
  1. 执行生产VectorSearch并抓安全SQL/EXPLAIN。
  2. 独立cosine计算对照身份、分数和LIMIT，误差设明确浮点容差。
- 预期结果：真实PG固定有效向量、限定范围，以独立cosine对照身份/分数/顺序，证据含实际SQL/计划及LIMIT；SQLite Python排序不能当正式证明。
- 补充判定／证据边界：分数采用生产cosine与独立参考计算，有限值容差预设为绝对误差≤1e-5；并列值按RET_009的稳定键处理。独立参考不得调用被测cosine帮助函数。
- 代码依据／主要定位：[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search。
- 优先级：P0。
- 用例类型：功能/质量。
- 是否适合自动化：是。
- 实际测试结果：通过；32项断言；正式任务完整成功；实际数据库Top-K SQL；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_008"></a>

#### RET_008：距离计算前范围物化

- 用例编号：`RET_008`
- 对应测试点：`TQ-RAG-RET-008`：距离计算前范围物化。验证目标：混维集合不会先计算后过滤。
- 需求来源：RAG-002、RAG-023、RAG-024。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG同时放384/1024和同维异模型数据。
- 测试数据要求：未授权最相似、候选未发布、外View batch。
- 测试流程：
  1. 执行生产查询并记录物化CTE与计划。
  2. 核对先范围再距离、无混维错误或范围外候选，无全量Python计算。
- 预期结果：混合384/1024与同维异模型数据，实际MATERIALIZED授权/空间集合先形成再算距离；未授权/候选/外视图均不参加排序，不能全量拉Python。
- 代码依据／主要定位：[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：安全/SQL。
- 是否适合自动化：是。
- 实际测试结果：通过；24项断言；正式任务完整成功；授权范围先物化再求距；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_009"></a>

#### RET_009：并列分数稳定顺序

- 用例编号：`RET_009`
- 对应测试点：`TQ-RAG-RET-009`：并列分数稳定顺序。验证目标：重复固定查询候选身份一致。
- 需求来源：RAG-023、RAG-025、NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；多个文档/batch中有同分有效向量。
- 测试数据要求：完全同cosine、不同document/batch/seq/chunk稳定键。
- 测试流程：
  1. 多次执行有限K检索。
  2. 按稳定键独立排序并比较截断边界，不依赖插入顺序。
- 预期结果：同分向量按document/batch/seq/chunk等稳定键排序，有限K截断位置可重现，不靠随机ID生成顺序或DB偶然行序。
- 代码依据／主要定位：[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search。
- 优先级：P1。
- 用例类型：边界/确定性。
- 是否适合自动化：是。
- 实际测试结果：通过；31项断言；正式任务完整成功；稳定键排序；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_010"></a>

#### RET_010：候选与命中数量边界

- 用例编号：`RET_010`
- 对应测试点：`TQ-RAG-RET-010`：候选与命中数量边界。验证目标：candidate_k和top_k分别受限。
- 需求来源：RAG-025。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可导入RetrievalProfile和提交覆盖参数。
- 测试数据要求：默认20/5，top_k1/20/0/21，candidate_k100/101、小于top_k、候选不足。
- 测试流程：
  1. 分组建立/执行策略。
  2. 合法返回实际数，非法拒绝，不能从别库或非View补足。
- 预期结果：默认20/5、top_k1～20且≤candidate_k≤100；非法配置/覆盖拒绝，合法候选不足只返回实际数，不从别库/旧视图补足。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P1。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；默认20/5；候选不足只取实际数；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_011"></a>

#### RET_011：关闭rerank无调用

- 用例编号：`RET_011`
- 对应测试点：`TQ-RAG-RET-011`：关闭rerank无调用。验证目标：关闭时保留dense顺序。
- 需求来源：RAG-027。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；固定dense候选和未提供真实rerank Key。
- 测试数据要求：rerank_enabled=false、top_k=2。
- 测试流程：
  1. 执行检索并记录调用数和结果顺序。
  2. rerank工厂/HTTP零调用，dense分数原样保留。
- 预期结果：关闭重排后服务请求计数为0，top_k来自dense；不要求加载真实rerank Key或用伪重排覆盖dense分数。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P1。
- 用例类型：功能/依赖。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；不伪造重排分数；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_012"></a>

#### RET_012：rerank同候选身份

- 用例编号：`RET_012`
- 对应测试点：`TQ-RAG-RET-012`：rerank同候选身份。验证目标：重排不能引入新来源。
- 需求来源：RAG-026、RAG-027。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；受控ranker对固定dense候选返回index集合。
- 测试数据要求：倒序合法、重复/缺失/越界/非整数index、数量不符。
- 测试流程：
  1. 执行相同View检索。
  2. 合法只重排原候选再取K，非法协议失败，无新Chunk身份。
- 预期结果：受控排序交换只对同一dense候选索引集合重排再取top_k，漏/重/越界index和错误数量失败，不能凭返回文本造新chunk。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：契约。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；原候选交换身份；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_013"></a>

#### RET_013：rerank分数独立

- 用例编号：`RET_013`
- 对应测试点：`TQ-RAG-RET-013`：rerank分数独立。验证目标：两类分数不混写。
- 需求来源：RAG-026、RAG-027。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；固定dense分数与独立rerank分数。
- 测试数据要求：不同分值顺序、NaN/Inf/非法分值。
- 测试流程：
  1. 读取candidates和Bundle。
  2. dense值不被覆盖或与rerank加和，坏分数在契约边界拒绝。
- 预期结果：候选和Bundle保留dense/rerank分数及身份；非有限/越界返回失败，不能加和成无语义score或回写覆盖dense值。
- 补充判定／证据边界：真实适配器的非有限/非法分值按其协议断言，受控Port还需核公开DTO/持久结果；二者证据边界不混写。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence。
- 优先级：P0。
- 用例类型：契约/质量。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；拒绝原因与约定一致；两类分数并存；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_014"></a>

#### RET_014：rerank输入截取范围

- 用例编号：`RET_014`
- 对应测试点：`TQ-RAG-RET-014`：rerank输入截取范围。验证目标：记录真正交给重排的候选前缀。
- 需求来源：RAG-026、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；生产rerank适配器带协议模拟transport。
- 测试数据要求：query边界、中英emoji候选、单项/总输入预算前后。
- 测试流程：
  1. 捕获真实发送字节并独立计算UTF-8前缀。
  2. trace的字符范围吻合发送内容，超长query拒绝。
- 预期结果：query超预算拒绝；文档按UTF-8前缀/组合总预算有界截取，trace字符范围对应实际请求，不能冒称整篇送入或截断半个Unicode字符。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：边界/可观测。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；拒绝原因与约定一致；trace字符范围对应实际请求；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_015"></a>

#### RET_015：重排默认失败

- 用例编号：`RET_015`
- 对应测试点：`TQ-RAG-RET-015`：重排默认失败。验证目标：未声明fallback就不能降级成功。
- 需求来源：RAG-028。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；冻结failure_policy=fail，生成入口有调用计数。
- 测试数据要求：网络/服务/协议/输入预算失败。
- 测试流程：
  1. 分别执行诊断和Run。
  2. 核对Execution/Run失败及错误，不继续生成成功回答，不伪装empty。
- 预期结果：网络/服务/协议/输入预算故障在fail策略下结束Execution/Run，返回failed原因而非empty或继续生成“成功检索”。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank。
- 优先级：P0。
- 用例类型：异常。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；失败策略明确且不伪空；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_016"></a>

#### RET_016：显式dense降级

- 用例编号：`RET_016`
- 对应测试点：`TQ-RAG-RET-016`：显式dense降级。验证目标：只有允许错误可按冻结策略降级。
- 需求来源：RAG-028。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；相同View对照fail与dense_fallback。
- 测试数据要求：名单内临时/服务/协议/预算错误。
- 测试流程：
  1. 取得原dense参考后注入故障。
  2. 验证fallback模式degraded、原因可读、结果保持原dense，无重新query或新造分数。
- 预期结果：dense_fallback且错误在受控名单时返回原dense集合/排序并标degraded、原因和Profile，不能偷偷重新检索或新造分数。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy。
- 优先级：P0。
- 用例类型：异常/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；降级不造分数；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_016.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_017"></a>

#### RET_017：安全认证错误不得降级

- 用例编号：`RET_017`
- 对应测试点：`TQ-RAG-RET-017`：安全认证错误不得降级。验证目标：降级不能绕权限故障。
- 需求来源：RAG-028、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；冻结dense_fallback但安全错误。
- 测试数据要求：rerank401/403、security blocked、坏向量/space/View。
- 测试流程：
  1. 逐组触发。
  2. 核对强制失败且无降级成功，不以名单外安全故障继续生成。
- 预期结果：401/403的RERANK_AUTH_FAILED、安全blocked、空间/向量/视图错误不在fallback名单；即使配置dense_fallback也必须明确失败。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：权限/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；认证不在降级名单；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_018"></a>

#### RET_018：真实原生rerank响应

- 用例编号：`RET_018`
- 对应测试点：`TQ-RAG-RET-018`：真实原生rerank响应。验证目标：生产候选实际交给独立重排服务。
- 需求来源：RAG-026、RAG-044。
- 当前可验证性：暂不可完整验证·B（真实输入计数依据及校准未完成，生产守卫阻断）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：真实rerank计数及相关真实Embedding前提已退出。
- 测试数据要求：真实固定query/候选、Profile版本、原生重排端点。
- 测试流程：
  1. 从正式检索链请求真实ranker。
  2. 记录响应index/score映射及实际输入范围，不用protocol直调小探针冒充业务。
- 预期结果：校准后使用真实Profile/query/候选请求原生端点，返回索引/分数可映射，trace包含真实输入范围；协议小探针不等于业务全链。
- 暂缓标记：真实计数依据/校准未完成，当前正式生产守卫阻断；解除条件见第3节B项，不使用替身凑成真实通过。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：真实/契约。
- 是否适合自动化：是。
- 实际测试结果：暂不可验证：真实rerank计数适用依据未完成，生产真实重排效果尚未验证。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="ret_019"></a>

#### RET_019：独立诊断不产生聊天事实

- 用例编号：`RET_019`
- 对应测试点：`TQ-RAG-RET-019`：独立诊断不产生聊天事实。验证目标：诊断只有检索执行身份。
- 需求来源：RAG-032、RAG-041。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例自建库与固定检索输入。
- 测试数据要求：相同策略/query的diagnostic与正式Run对照。
- 测试流程：
  1. 先后创建并核PG增量。
  2. diagnostic仅Task/View/Execution，无Thread/Message/Run或生成调用，检索规则一致。
- 预期结果：创建diagnostic及Task/View，不创建Thread Message/Run、不调用生成；同条件与Run复用相同检索规则，不要求随机view_id相同。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/api/routes/v3/retrieval.py`](../../backend/api/routes/v3/retrieval.py)：诊断与Bundle端点。
- 优先级：P1。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；正式任务完整成功；诊断不创建runs；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_019.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_020"></a>

#### RET_020：诊断取消权限

- 用例编号：`RET_020`
- 对应测试点：`TQ-RAG-RET-020`：诊断取消权限。验证目标：诊断入口不控制Run内部工具。
- 需求来源：RAG-033、RAG-041。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有活动diagnostic及Run内工具，两个owner。
- 测试数据要求：取消独立诊断、终态诊断、Run工具及越权ID。
- 测试流程：
  1. 经正式取消入口分别请求。
  2. 仅授权诊断合法结算，Run工具需取消Run，不直接改终态。
- 预期结果：仅独立诊断可取消，Run工具须取消Run；活动/已终态响应按事实处理，越owner拒绝，不直接改持久终态。
- 代码依据／主要定位：[`backend/api/routes/v3/retrieval.py`](../../backend/api/routes/v3/retrieval.py)：诊断与Bundle端点；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：权限/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；排队诊断可取消；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_020.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_021"></a>

#### RET_021：RAG模式区分

- 用例编号：`RET_021`
- 对应测试点：`TQ-RAG-RET-021`：RAG模式区分。验证目标：off/未执行/empty/degraded/failed可区分。
- 需求来源：RAG-028、RAG-031、RAG-032。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每种状态独立新建Run/diagnostic。
- 测试数据要求：off、mandatory超预算、空View、fallback、依赖失败。
- 测试流程：
  1. 执行并读rag_summary/ToolCall/Execution/Event。
  2. 逐一核off/not_started/empty/degraded/failed，不用202作成功判据。
- 预期结果：关闭无ToolCall且off；mandatory预算失败not_started；合法空empty；明确降级degraded；依赖故障failed，不能以HTTP202或工具成功推Run成功。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan。
- 优先级：P0。
- 用例类型：状态/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；26项断言；正式任务完整成功；有证据ok；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_021.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_022"></a>

#### RET_022：Trace可追溯链

- 用例编号：`RET_022`
- 对应测试点：`TQ-RAG-RET-022`：Trace可追溯链。验证目标：回答可反查完整执行证据身份。
- 需求来源：RAG-031、RAG-034、NFR-005。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例Run可经历两个generation。
- 测试数据要求：Message/Run/ToolCall/Execution/View/Plan/Citation身份。
- 测试流程：
  1. 分别完成检索和重试后追踪全部外键/公开trace。
  2. 候选/分数/去除/错误与正确代对应，旧事实不覆写。
- 预期结果：由Message/Run追踪ToolCall→Execution→View/batch→ContextPlan及所选范围，记录候选/分数/去除与安全错误；前代事实不可被新代覆盖。
- 代码依据／主要定位：[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算。
- 优先级：P1。
- 用例类型：可观测。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；正式任务完整成功；实际Context范围存在；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_022.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ret_023"></a>

#### RET_023：视图规模上限

- 用例编号：`RET_023`
- 对应测试点：`TQ-RAG-RET-023`：视图规模上限。验证目标：过多文档明确拒绝不静默裁库。
- 需求来源：RAG-024、RAG-025、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立构造合法成功batch集合，明确数据库夹具证据。
- 测试数据要求：1000与1001批次的同库View。
- 测试流程：
  1. 通过冻结服务建立视图。
  2. 1000完整manifest/items可用，1001返回RETRIEVAL_SCOPE_TOO_LARGE，不能截前1000。
- 预期结果：合法成功批次达到1000项可冻结，1001项返回RETRIEVAL_SCOPE_TOO_LARGE；不能只取前1000项导致用户误以为全库已查。
- 代码依据／主要定位：[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；正式任务完整成功；1000批次可冻结；范围夹具不冒充解析/增强成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/RET_023.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.9 ENH：邻近增强、证据与读取

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-ENH-001` | [ENH_001：邻近半径边界](#enh_001) | L | retrieval／local |
| `TQ-RAG-ENH-002` | [ENH_002：重叠区间去重](#enh_002) | L | retrieval／local |
| `TQ-RAG-ENH-003` | [ENH_003：增强总预算截取](#enh_003) | L | retrieval／local |
| `TQ-RAG-ENH-004` | [ENH_004：Bundle组件身份自洽](#enh_004) | L | retrieval／local |
| `TQ-RAG-ENH-005` | [ENH_005：来源范围裁剪](#enh_005) | L | retrieval／local |
| `TQ-RAG-ENH-006` | [ENH_006：证据读取授权](#enh_006) | L | retrieval／local |
| `TQ-RAG-ENH-007` | [ENH_007：证据hash及关系损坏拒绝](#enh_007) | L | retrieval／local |
| `TQ-RAG-ENH-008` | [ENH_008：证据正文分页坐标](#enh_008) | L | retrieval／local |
| `TQ-RAG-ENH-009` | [ENH_009：重建后历史证据保真](#enh_009) | L | retrieval／local |

<a id="enh_001"></a>

#### ENH_001：邻近半径边界

- 用例编号：`ENH_001`
- 对应测试点：`TQ-RAG-ENH-001`：邻近半径边界。验证目标：邻近仅是同批次有界扩展。
- 需求来源：RAG-024、RAG-029。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同文档seq0..4、旧批次及他文档同seq对照。
- 测试数据要求：半径0/1/2，首/中/尾命中。
- 测试流程：
  1. 组装增强并核每个组件。
  2. 仅同文档同batch合法邻居，不越边补齐或误取同seq他来源。
- 预期结果：半径0/1/2对首中尾命中，按seq同文档同批次扩展，不越边补齐，不把其他库/批次相同seq当邻居。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy。
- 优先级：P1。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；邻近范围准确；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_002"></a>

#### ENH_002：重叠区间去重

- 用例编号：`ENH_002`
- 对应测试点：`TQ-RAG-ENH-002`：重叠区间去重。验证目标：重复命中不重复堆正文。
- 需求来源：RAG-029。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；同批次重叠切片及多命中，另文档同文本。
- 测试数据要求：规范区间[0,100)、[80,180)、重复anchor。
- 测试流程：
  1. 组装Bundle并按原Artifact区间并集独立生成参考正文。
  2. 重叠正文不重复，跨文档不合并。
- 预期结果：相邻多命中/重叠切片合并相同规范范围，最终text与Artifact并集对照；组件可重叠但正文不重复，不误合并跨文档同text。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence。
- 优先级：P1。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；正文无重复拼接；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_003"></a>

#### ENH_003：增强总预算截取

- 用例编号：`ENH_003`
- 对应测试点：`TQ-RAG-ENH-003`：增强总预算截取。验证目标：增强有限且丢弃可诊断。
- 需求来源：RAG-029、RAG-030、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可设置max_enhanced_chars，足量组件夹具。
- 测试数据要求：字符预算前/等于/+1，组件99/100/101。
- 测试流程：
  1. 执行增强并读取omitted。
  2. 核对截取后文本/组件不超限且原因明确，不把字符数当生成token预算。
- 预期结果：达到max_enhanced_chars和组件100上限时仅输出可容纳范围/组件，记录enhancement_truncated或omitted原因；字符限额不替代生成token预算。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；删减有原因；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_004"></a>

#### ENH_004：Bundle组件身份自洽

- 用例编号：`ENH_004`
- 对应测试点：`TQ-RAG-ENH-004`：Bundle组件身份自洽。验证目标：每段拼接都可追溯。
- 需求来源：RAG-017、RAG-029、RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；合法hit/Artifact及历史batch。
- 测试数据要求：anchors、component、document/batch/range/hash清单。
- 测试流程：
  1. 逐项读取并重建Bundle文本。
  2. 与Artifact及Chunk关系一致。
  3. 缺正文负例安全EVIDENCE_UNAVAILABLE。
- 预期结果：anchors/组件chunk、document、batch、范围/hash对应实际Artifact文本，旧批次不被最新正文替换；文本缺失明确EVIDENCE_UNAVAILABLE。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；实际区间hash；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_005"></a>

#### ENH_005：来源范围裁剪

- 用例编号：`ENH_005`
- 对应测试点：`TQ-RAG-ENH-005`：来源范围裁剪。验证目标：来源只描述实际增强范围。
- 需求来源：RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有行位置和规范块位置的长Bundle。
- 测试数据要求：增强预算截在半行/Unicode/块中间。
- 测试流程：
  1. 增强后独立计算保留区间。
  2. 核对locations同步裁剪和行号、截外内容不被展示为实际输入来源。
- 预期结果：增强被截取时来源区间同步裁剪，行号更新可核对，原源位置与规范块区分；不能让截掉的内容仍作为实际输入位置显示。
- 代码依据／主要定位：[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations；[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence。
- 优先级：P0。
- 用例类型：位置/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；来源范围不超过实际正文；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_006"></a>

#### ENH_006：证据读取授权

- 用例编号：`ENH_006`
- 对应测试点：`TQ-RAG-ENH-006`：证据读取授权。验证目标：Bundle身份不能绕owner。
- 需求来源：RAG-021、RAG-033、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个owner各有Execution/View/Bundle。
- 测试数据要求：合法ID、越owner、随机不存在ID。
- 测试流程：
  1. 从证据读取入口访问。
  2. 越权与不存在404等价，响应无私有路径/签名URL。
- 预期结果：通过Execution/View校验owner，其他owner/不存在同404；知道Bundle ID不等于有读取权限，响应无私有文件路径/远端URL。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/api/routes/v3/retrieval.py`](../../backend/api/routes/v3/retrieval.py)：诊断与Bundle端点。
- 优先级：P0。
- 用例类型：权限。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_007"></a>

#### ENH_007：证据hash及关系损坏拒绝

- 用例编号：`ENH_007`
- 对应测试点：`TQ-RAG-ENH-007`：证据hash及关系损坏拒绝。验证目标：坏来源不能换最新内容作证据。
- 需求来源：RAG-021、RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；隔离case夹具且有合法Bundle对照。
- 测试数据要求：全文hash、component hash、chunk归属或范围单项损坏。
- 测试流程：
  1. 在可构造边界或回滚事务中制造损坏后读取。
  2. DB先拒绝或读时安全拒绝都明确记录，不替换为新active。
- 预期结果：Artifact全文hash、组件text hash、chunk归属/范围任一不符即拒绝；只能受控测试夹具制造坏数据，不能“修复”为当前active掩盖。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P0。
- 用例类型：异常/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；18项断言；正式任务完整成功；PG不可变约束直接拒绝破坏；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_008"></a>

#### ENH_008：证据正文分页坐标

- 用例编号：`ENH_008`
- 对应测试点：`TQ-RAG-ENH-008`：证据正文分页坐标。验证目标：分页拼回原Bundle且坐标含义清楚。
- 需求来源：RAG-030、RAG-042、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；正文超过4000字符且组件跨页。
- 测试数据要求：offset0/4000/尾部/64000/64001/-1。
- 测试流程：
  1. 逐页读取重拼正文并核无重漏。
  2. 组件位置描述整Bundle且相对Artifact，非法offset拒绝。
- 预期结果：offset0～64000、每页≤4000字符，续读无重漏；offset相对Bundle正文，组件/位置相对Artifact且描述整Bundle，不能错误按当前页平移。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/api/routes/v3/retrieval.py`](../../backend/api/routes/v3/retrieval.py)：诊断与Bundle端点；[`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue)：load/续读/epoch。
- 优先级：P1。
- 用例类型：接口/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；18项断言；正式任务完整成功；续读得到正文；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="enh_009"></a>

#### ENH_009：重建后历史证据保真

- 用例编号：`ENH_009`
- 对应测试点：`TQ-RAG-ENH-009`：重建后历史证据保真。验证目标：旧引用仍读旧版本。
- 需求来源：RAG-021、RAG-030、RAG-042。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例先生成旧回答/引用，再合法新重建。
- 测试数据要求：旧Bundle正文/hash/location，新active不同切片。
- 测试流程：
  1. 发布后重读历史引用并执行普通GC。
  2. 旧引用保持原批次且可读，不按最新正文替换。
- 预期结果：新active发布后读取原Bundle/Citation，文本/hash/位置仍原批次；历史依赖存在时普通GC不能删除，明确区分源已被旧版删掉的不可恢复情形。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/application/legacy_rag.py`](../../backend/application/legacy_rag.py)：materialize_legacy_text/protect_legacy_items。
- 优先级：P0。
- 用例类型：恢复/兼容。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；历史正文/hash/位置不漂移；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/ENH_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.10 CTX：上下文预算、实际输入与引用

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-CTX-001` | [CTX_001：mandatory预算先于检索](#ctx_001) | L | execution／local |
| `TQ-RAG-CTX-002` | [CTX_002：增强后生成预算取舍](#ctx_002) | L | execution／local |
| `TQ-RAG-CTX-003` | [CTX_003：ContextEvidence实际选入范围](#ctx_003) | L | execution／local |
| `TQ-RAG-CTX-004` | [CTX_004：不可信证据角色隔离](#ctx_004) | L | execution／local |
| `TQ-RAG-CTX-005` | [CTX_005：引用关系与终态原子提交](#ctx_005) | L | execution／local |
| `TQ-RAG-CTX-006` | [CTX_006：正文来源编号闭环](#ctx_006) | K | execution／local |
| `TQ-RAG-CTX-007` | [CTX_007：逐句语义支持](#ctx_007) | L | execution／local |
| `TQ-RAG-CTX-008` | [CTX_008：按代上下文事实保留](#ctx_008) | L | execution／local |
| `TQ-RAG-CTX-009` | [CTX_009：生成失败不冒称回答完成](#ctx_009) | L | execution／local |

<a id="ctx_001"></a>

#### CTX_001：mandatory预算先于检索

- 用例编号：`CTX_001`
- 对应测试点：`TQ-RAG-CTX-001`：mandatory预算先于检索。验证目标：必需输入放不下时不付费检索。
- 需求来源：RAG-030、RAG-031、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Run输入可通过合法模型窗口设置制造mandatory不足。
- 测试数据要求：system+问题+输出预留+安全量恰好可用与超1token。
- 测试流程：
  1. 创建Run并记录模型计数及工具状态。
  2. 超限前置失败、Tool not_started、Embedding/rerank计数0，合法对照可继续。
- 预期结果：system/当前问题/输出预留及安全余量超窗口，Run按预算错误结束，Tool保持not_started，Embedding/rerank请求计数0，不能伪造empty。
- 代码依据／主要定位：[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算。
- 优先级：P0。
- 用例类型：边界/费用。
- 是否适合自动化：是。
- 实际测试结果：通过；16项断言；正式任务完整成功；不是empty；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_002"></a>

#### CTX_002：增强后生成预算取舍

- 用例编号：`CTX_002`
- 对应测试点：`TQ-RAG-CTX-002`：增强后生成预算取舍。验证目标：送入模型的证据满足生成窗口。
- 需求来源：RAG-030。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已有多个可增强Bundle、Mock确定计数器。
- 测试数据要求：小窗口/足够窗口、整Bundle不能放入的边界。
- 测试流程：
  1. 分别执行ContextPlan并观察实际ModelRequest。
  2. 独立重算总计数与预留，移除原因可见，不要求Bundle内二次切片。
- 预期结果：增强阶段可截取，生成ContextPlan目前按整Bundle选择/舍弃；实际messages计数+预留+安全量不超窗口，舍弃有原因，不要求未承诺的Bundle内再次部分裁剪。
- 代码依据／主要定位：[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan。
- 优先级：P0。
- 用例类型：边界。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；最终输入总预算；按整Bundle选择不伪称部分裁剪；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_003"></a>

#### CTX_003：ContextEvidence实际选入范围

- 用例编号：`CTX_003`
- 对应测试点：`TQ-RAG-CTX-003`：ContextEvidence实际选入范围。验证目标：持久所选证据等于真实模型输入。
- 需求来源：RAG-030、RAG-031。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；模型输入观察点仅存安全摘要，合成文本可独立重建。
- 测试数据要求：三个Bundle中只有两个进入Plan。
- 测试流程：
  1. 由选中Plan和known text核实际消息hash。
  2. 逐ContextEvidence/Citation比较range/hash，被舍弃者无引用关系。
- 预期结果：记录模型实际收到的Bundle/组件文本范围与hash，只有选入者建ContextEvidence；仅召回但移除的内容不能列入最终Citation。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；33项断言；正式任务完整成功；引用不覆盖被舍弃范围；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_004"></a>

#### CTX_004：不可信证据角色隔离

- 用例编号：`CTX_004`
- 对应测试点：`TQ-RAG-CTX-004`：不可信证据角色隔离。验证目标：文档文本不成为工具授权或系统指令。
- 需求来源：RAG-033、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；不可信文档内含攻击性正文。
- 测试数据要求：忽略规则、改owner/space、访问URL、伪工具调用文本。
- 测试流程：
  1. 完成检索后检查ModelRequest角色与配置。
  2. 不可信段只在普通user证据中，不改变授权或额外执行工具。
- 预期结果：向证据放“忽略规则/访问URL”等，模型收到user角色不可信片段，不能改owner/space/工具配置或执行新工具；不承诺模型文本永不受影响。
- 代码依据／主要定位：[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py)：RAG_BINDING/SearchToolInput/SearchToolResult。
- 优先级：P0。
- 用例类型：安全/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；18项断言；正式任务完整成功；没有动态工具授权；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_005"></a>

#### CTX_005：引用关系与终态原子提交

- 用例编号：`CTX_005`
- 对应测试点：`TQ-RAG-CTX-005`：引用关系与终态原子提交。验证目标：最终引用只能绑定本次输入证据。
- 需求来源：RAG-030、RAG-037、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG最终提交可在事务边界注入异常。
- 测试数据要求：正常成功、assistant/引用/终态提交前异常两组。
- 测试流程：
  1. 执行并在独立连接读Message/CitationLink/Run/Task/Event。
  2. 成功同时可见，注入异常整组回滚，无跨Run或裁外引用。
- 预期结果：assistant/Citation2/MessageCitationLink/Run/Task/终态Event同事务成功，注入事务失败全部回滚；引用不关联其它Run或被裁掉范围。
- 代码依据／主要定位：[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py)：append_event/list_events。
- 优先级：P0。
- 用例类型：事务/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；23项断言；正式任务完整成功；事务失败无成功终态；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_006"></a>

#### CTX_006：正文来源编号闭环

- 用例编号：`CTX_006`
- 对应测试点：`TQ-RAG-CTX-006`：正文来源编号闭环。验证目标：正文标记与展示来源稳定对应。
- 需求来源：RAG-030、RAG-042。
- 当前可验证性：本机可验证·K（已知实现/契约差异，按完整目标断言，可能失败）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；明确已知正文编号缺口，保留目标。
- 测试数据要求：两条证据S1/S2、模型输出合法/未知/错编号。
- 测试流程：
  1. 观察完整合成输入、最终正文与UI来源映射。
  2. 要求编号输入输出展示一致，未知编号不能造来源。
  3. 当前缺失应记失败而非blocked。
- 预期结果：核对模型输入是否含与UI一致的S1等标识，返回未知/错编号不得生成新来源；当前未注入编号，仅关系label不够，应按ADR目标测出差异而非算暂不可测。
- 代码依据／主要定位：[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`frontend/src/components/MessageTimeline.vue`](../../frontend/src/components/MessageTimeline.vue)：引用与消息投影；[`docs/adr/003-sesrag-rag-mineru-implementation-plan.md`](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md)：实施决策/不变量。
- 优先级：P0。
- 用例类型：功能/缺口。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；正式任务完整成功；模型输入须含与UI一致来源编号S1；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_007"></a>

#### CTX_007：逐句语义支持

- 用例编号：`CTX_007`
- 对应测试点：`TQ-RAG-CTX-007`：逐句语义支持。验证目标：引用存在不等于断言被支持。
- 需求来源：RAG-030、RAG-045。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有独立合成事实及已标注支持范围。
- 测试数据要求：正确陈述、带合法引用但事实相反、无证据断言三种固定回答。
- 测试流程：
  1. 通过可控生成返回各答案。
  2. 逐关键断言与证据核对，判定器必须识别错误。
  3. 真实语义质量需另执行真实评测。
- 预期结果：用已标注合成事实对照最终回答的关键断言/错误引用，结构化来源合法但内容不支持仍判相关质量失败；local可控回答验证判定器，真实质量另测。
- 补充判定／证据边界：合成判定样本示例：证据明确“保留期7天”，正确答案7天，错误答案30天但仍挂同一合法引用。此用例校验支持性核对方法，不证明任意自然语言模型永不幻觉。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径。
- 优先级：P1。
- 用例类型：质量/风险。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；3项断言；内容与引用共同判定而非只查引用合法；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_008"></a>

#### CTX_008：按代上下文事实保留

- 用例编号：`CTX_008`
- 对应测试点：`TQ-RAG-CTX-008`：按代上下文事实保留。验证目标：失败重试的计划不覆盖历史代。
- 需求来源：RAG-030、RAG-034。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；允许同Run新代恢复且保留前代Plan。
- 测试数据要求：代1失败/草稿，代2不同实际选入Bundle。
- 测试流程：
  1. 按指定代读取Plan和最终消息。
  2. 旧Plan/hash保留，最终Citation只来自成功代。
- 预期结果：同Run多Task generation产生各自不可变ContextPlan，GET指定代可读且最终Message只用成功代的实际证据，旧代草稿/引用不能混入。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py)：消息/Run/Event/SSE/取消/重试端点。
- 优先级：P0。
- 用例类型：恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；正式任务完整成功；多代计划分别保留；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ctx_009"></a>

#### CTX_009：生成失败不冒称回答完成

- 用例编号：`CTX_009`
- 对应测试点：`TQ-RAG-CTX-009`：生成失败不冒称回答完成。验证目标：工具成功与生成终态分开。
- 需求来源：RAG-031、RAG-034、RAG-037。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；检索已成功且生成transport可控。
- 测试数据要求：生成超时、半流断开、确定错误及成功对照。
- 测试流程：
  1. 分别执行至结算并读Run/Task/Event/Message。
  2. 失败或retry可诊断，无成功最终assistant，工具completed不代表Run成功。
- 预期结果：检索成功后生成超时/断流/错误，Run明确failed/retry状态，不能出现成功最终assistant或用工具completed宣布Run成功。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算。
- 优先级：P0。
- 用例类型：异常/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；16项断言；正式任务完整成功；工具结束不等于Run成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/CTX_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.11 EXE：工具、Run、事件与恢复

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-EXE-001` | [EXE_001：Run创建与视图原子性](#exe_001) | L | execution／local |
| `TQ-RAG-EXE-002` | [EXE_002：完整非Secret快照冻结](#exe_002) | L | execution／local |
| `TQ-RAG-EXE-003` | [EXE_003：RAG关闭零依赖调用](#exe_003) | L | execution／local |
| `TQ-RAG-EXE-004` | [EXE_004：工具定义与输入白名单](#exe_004) | L | execution／local |
| `TQ-RAG-EXE-005` | [EXE_005：每代单逻辑工具调用](#exe_005) | L | execution／local |
| `TQ-RAG-EXE-006` | [EXE_006：自动重试会话身份不变](#exe_006) | L | execution／local |
| `TQ-RAG-EXE-007` | [EXE_007：显式retry保留知识视图](#exe_007) | L | execution／local |
| `TQ-RAG-EXE-008` | [EXE_008：regenerate保留知识视图](#exe_008) | L | execution／local |
| `TQ-RAG-EXE-009` | [EXE_009：新消息获取当前视图](#exe_009) | L | execution／local |
| `TQ-RAG-EXE-010` | [EXE_010：缺失旧视图的v3操作](#exe_010) | L | execution／local |
| `TQ-RAG-EXE-011` | [EXE_011：Journal三代载荷与序号](#exe_011) | L | execution／local |
| `TQ-RAG-EXE-012` | [EXE_012：SSE游标补放](#exe_012) | L | execution／local |
| `TQ-RAG-EXE-013` | [EXE_013：Redis故障不改变终态](#exe_013) | L | execution／local |
| `TQ-RAG-EXE-014` | [EXE_014：工具结束事件不结束Run](#exe_014) | L | execution／local |
| `TQ-RAG-EXE-015` | [EXE_015：Run取消确认](#exe_015) | L | execution／local |
| `TQ-RAG-EXE-016` | [EXE_016：Worker有界停机](#exe_016) | L | execution／local |
| `TQ-RAG-EXE-017` | [EXE_017：专用并发槽实际范围](#exe_017) | L | execution／local |
| `TQ-RAG-EXE-018` | [EXE_018：停用与blocked后的显式重试](#exe_018) | L | execution／local |
| `TQ-RAG-EXE-019` | [EXE_019：回答流资源上限](#exe_019) | L | execution／local |

<a id="exe_001"></a>

#### EXE_001：Run创建与视图原子性

- 用例编号：`EXE_001`
- 对应测试点：`TQ-RAG-EXE-001`：Run创建与视图原子性。验证目标：新输入和冻结事实不部分存在。
- 需求来源：RAG-032、RAG-035、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立Thread/Branch及PG事务观察。
- 测试数据要求：合法请求、expected_version冲突、非法View三组。
- 测试流程：
  1. 创建v3消息。
  2. 读用户Message/Run/Task/View/操作记录增量。
  3. 只有完整合法组同时提交，失败无孤立事实。
- 预期结果：既有Thread/Branch事务中Message/Run/Task/View/幂等结果一起提交，分支版本冲突或View校验失败不留孤立Run/输入，未另造平行聊天入口。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：事务。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；无孤立messages；无孤立retrieval_views；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_002"></a>

#### EXE_002：完整非Secret快照冻结

- 用例编号：`EXE_002`
- 对应测试点：`TQ-RAG-EXE-002`：完整非Secret快照冻结。验证目标：快照足以恢复而不含凭据。
- 需求来源：RAG-035、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Run创建后暂停执行并可更改默认配置。
- 测试数据要求：策略/过滤/工具/空间/模型版本及Secret哨兵。
- 测试流程：
  1. 读取冻结快照，再改默认放行。
  2. 实际依旧原非Secret值，Key/签名能力URL/宿主路径无落库。
- 预期结果：冻结策略/工具/过滤/空间/模型版本与非Secret参数，改默认不漂移；快照只含受信alias而无Key、能力URL和宿主路径。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py)：RAG_BINDING/SearchToolInput/SearchToolResult；[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run。
- 优先级：P0。
- 用例类型：一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；元数据变化不漂移原快照；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_003"></a>

#### EXE_003：RAG关闭零依赖调用

- 用例编号：`EXE_003`
- 对应测试点：`TQ-RAG-EXE-003`：RAG关闭零依赖调用。验证目标：关闭不接触检索服务。
- 需求来源：RAG-032。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；RAG关闭且各检索依赖有计数。
- 测试数据要求：纯off及off附带库/过滤/覆盖参数。
- 测试流程：
  1. 合法off执行完整Run，核零query/vector/rerank/ToolCall。
  2. 矛盾参数拒绝，不能生成伪empty检索。
- 预期结果：关闭时无query Embedding/向量查询/rerank/ToolCall；关闭却附带库/过滤/覆盖参数拒绝，不能创建伪empty执行。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan。
- 优先级：P0。
- 用例类型：功能/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；11项断言；正式任务完整成功；off无工具；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_004"></a>

#### EXE_004：工具定义与输入白名单

- 用例编号：`EXE_004`
- 对应测试点：`TQ-RAG-EXE-004`：工具定义与输入白名单。验证目标：仅固定只读rag.search可装配。
- 需求来源：RAG-032、RAG-033、NFR-006。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；版本化rag.search定义/输入输出Schema可读。
- 测试数据要求：额外owner/space/view/SQL/URL、任意tool名/版本及动态代码。
- 测试流程：
  1. 在契约/绑定入口逐项提交。
  2. 只接受既定只读工具结构，不产生自主循环或越权授权。
- 预期结果：版本化name/version/readonly及输入结果Schema一致；额外owner/space/view/SQL/URL/动态代码/任意工具名不能提交为新授权或自主循环。
- 代码依据／主要定位：[`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py)：RAG_BINDING/SearchToolInput/SearchToolResult；[`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py)：wire_catalog/export --check；[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算。
- 优先级：P0。
- 用例类型：契约/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；固定版本化工具；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_005"></a>

#### EXE_005：每代单逻辑工具调用

- 用例编号：`EXE_005`
- 对应测试点：`TQ-RAG-EXE-005`：每代单逻辑工具调用。验证目标：一个Task/generation最多一次逻辑调用。
- 需求来源：RAG-034。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Task有有效身份并可受控重复dispatch。
- 测试数据要求：同task/generation重复进入、内部网络重试、新generation。
- 测试流程：
  1. 观测ToolCall/Execution唯一约束及历史。
  2. 同代一逻辑调用，不同代独立，旧代迟到不覆盖。
- 预期结果：重复进入同代不造第二个ToolCall，内部网络重试不算新Run或工具；不同代保留独立历史结果，不复用迟到成功覆盖新代。
- 代码依据／主要定位：[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：并发/幂等。
- 是否适合自动化：是。
- 实际测试结果：通过；16项断言；正式任务完整成功；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_006"></a>

#### EXE_006：自动重试会话身份不变

- 用例编号：`EXE_006`
- 对应测试点：`TQ-RAG-EXE-006`：自动重试会话身份不变。验证目标：内部尝试不是新用户操作。
- 需求来源：RAG-034、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；一条固定输入Run及临时故障。
- 测试数据要求：首次临时错误后队列重试成功。
- 测试流程：
  1. 跟踪task/attempt/generation和会话行数。
  2. Thread/用户Message/Run不变，最终assistant至多一条。
- 预期结果：故障回排增加Task代/attempt但Run、用户Message、Thread身份不变；最多一个最终assistant，不能误把物理尝试当新会话。
- 代码依据／主要定位：[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算。
- 优先级：P0。
- 用例类型：恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；最多最终assistant；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_007"></a>

#### EXE_007：显式retry保留知识视图

- 用例编号：`EXE_007`
- 对应测试点：`TQ-RAG-EXE-007`：显式retry保留知识视图。验证目标：失败后显式重试不偷偷换知识。
- 需求来源：RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每例独立产生failed或cancelled schema3 Run。
- 测试数据要求：冻结View后发布新batch，再显式retry与同key重放。
- 测试流程：
  1. 执行新Run并读取parent/input/View/配置。
  2. 复用原视图和输入，可换生成模型但不换向量空间，操作幂等。
- 预期结果：schema3 failed/cancelled源创建关联新Run，复用原输入/RAG配置/View，可显式换生成模型但不改向量空间；新操作键有幂等。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail。
- 优先级：P0。
- 用例类型：恢复/功能。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；关联操作同key重放；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_008"></a>

#### EXE_008：regenerate保留知识视图

- 用例编号：`EXE_008`
- 对应测试点：`TQ-RAG-EXE-008`：regenerate保留知识视图。验证目标：成功后再生成沿用原知识事实。
- 需求来源：RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立已成功schema3源及符合分支规则的头消息。
- 测试数据要求：发布新active后regenerate、并发分支版本冲突对照。
- 测试流程：
  1. 创建关联Run并执行。
  2. 合法沿旧View，冲突按分支规则拒绝，模型输出无需逐字相同。
- 预期结果：schema3 succeeded源按分支规则产生关联Run，沿用来源视图/配置；不把当前active混入，同view不承诺模型逐字相同。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail。
- 优先级：P0。
- 用例类型：功能/兼容。
- 是否适合自动化：是。
- 实际测试结果：通过；24项断言；正式任务完整成功；关联操作同key重放；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_009"></a>

#### EXE_009：新消息获取当前视图

- 用例编号：`EXE_009`
- 对应测试点：`TQ-RAG-EXE-009`：新消息获取当前视图。验证目标：需要新知识须由新输入触发。
- 需求来源：RAG-035、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；原Run已冻结旧batch，随后发布新active。
- 测试数据要求：同Thread再发新的用户Message。
- 测试流程：
  1. 比较两Run的View items及实际候选。
  2. 新Run取当时新active，旧Run不漂移，不能隐式更新旧再生成。
- 预期结果：旧Run创建后发布新batch，再发送新用户Message，新Run取新active集合，旧Run仍旧集合，不提供隐式“最新语料再生成”。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope。
- 优先级：P0。
- 用例类型：功能。
- 是否适合自动化：是。
- 实际测试结果：通过；26项断言；正式任务完整成功；当前新知识可见；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_010"></a>

#### EXE_010：缺失旧视图的v3操作

- 用例编号：`EXE_010`
- 对应测试点：`TQ-RAG-EXE-010`：缺失旧视图的v3操作。验证目标：旧历史不能伪造过去知识。
- 需求来源：RAG-036、RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮自建schema1/2历史Run。
- 测试数据要求：failed/cancelled的retry、成功的regenerate。
- 测试流程：
  1. 从v3操作入口提交。
  2. 返回LEGACY_RETRIEVAL_VIEW_UNAVAILABLE并引导新消息，旧协议历史可读且不补造View。
- 预期结果：schema1/2源经v3 retry/regenerate返回LEGACY_RETRIEVAL_VIEW_UNAVAILABLE并提示新消息，原历史仍可按原协议读，不静默套当前view。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail。
- 优先级：P0。
- 用例类型：兼容/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；旧view不可恢复提示；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_011"></a>

#### EXE_011：Journal三代载荷与序号

- 用例编号：`EXE_011`
- 对应测试点：`TQ-RAG-EXE-011`：Journal三代载荷与序号。验证目标：按版本type解码且Run内seq单调。
- 需求来源：RAG-037、NFR-004、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；三代独立合法事件样本及真实schema3 Run。
- 测试数据要求：seq重复/逆序、终态后追加、UPDATE/DELETE、事件接近上限。
- 测试流程：
  1. 按各代Schema校验并尝试写入。
  2. 拒绝不合法事实，保终态空间及工具真实代身份，历史JSON不重写。
- 预期结果：混合历史按各自Schema验证，工具事件带真实call/execution/代身份，终态后不能再追加或UPDATE/DELETE；普通事件额度保留终态空间。
- 代码依据／主要定位：[`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py)：append_event/list_events；[`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py)：三代事件载荷；[`migrations/rag_guards.py`](../../migrations/rag_guards.py)：PostgreSQL不可变触发器。
- 优先级：P0。
- 用例类型：契约/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；19项断言；正式任务完整成功；新Run事件按3代载荷；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_012"></a>

#### EXE_012：SSE游标补放

- 用例编号：`EXE_012`
- 对应测试点：`TQ-RAG-EXE-012`：SSE游标补放。验证目标：断连可补齐持久事件。
- 需求来源：RAG-037。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Journal包含多页事件并经同源SSE。
- 测试数据要求：after_seq、Last-Event-ID同时给、合法及非法游标、断线重连。
- 测试流程：
  1. 先读一段后断开并重连。
  2. 核头优先及按Journal补放，客户端按seq合并无缺重，不创建新终态。
- 预期结果：Last-Event-ID优先于after_seq，分页/非法游标按正式约定；断线后从Journal补放不缺不重，HTTP/SSE不生成新终态事实。
- 补充判定／证据边界：SSE保持接口原约定：Last-Event-ID优先，负数或不可解析Header归0；普通/events的负数/非整数query返回422。终态之后无新事件时有界关闭空流，不能把两种游标规则混成一条。
- 代码依据／主要定位：[`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py)：消息/Run/Event/SSE/取消/重试端点；[`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py)：append_event/list_events；[`frontend/src/events/rag-event-stream.ts`](../../frontend/src/events/rag-event-stream.ts)：parseV3Event/replayV3Events/openV3RunStream。
- 优先级：P0。
- 用例类型：恢复/接口。
- 是否适合自动化：是。
- 实际测试结果：通过；11项断言；正式任务完整成功；非法Header归0；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_013"></a>

#### EXE_013：Redis故障不改变终态

- 用例编号：`EXE_013`
- 对应测试点：`TQ-RAG-EXE-013`：Redis故障不改变终态。验证目标：通知不可用不丢持久Run事实。
- 需求来源：RAG-037、NFR-003。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG，宿主按账本只断本project Redis。
- 测试数据要求：检索/生成中通知丢失和SSE断线。
- 测试流程：
  1. 执行Run后停通知再恢复。
  2. PG终态/唯一消息存在，GET/SSE补放一致，前端不计时猜终态。
- 预期结果：断Redis/通知或SSE时后台照常写PG，恢复后GET/补放可取唯一消息与终态；页面不可按超时直接宣布失败/成功。
- 代码依据／主要定位：[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch；[`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py)：消息/Run/Event/SSE/取消/重试端点；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重。
- 优先级：P0。
- 用例类型：恢复/事实源。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；恢复SSE仍从PG补放终态；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_014"></a>

#### EXE_014：工具结束事件不结束Run

- 用例编号：`EXE_014`
- 对应测试点：`TQ-RAG-EXE-014`：工具结束事件不结束Run。验证目标：工具完成只代表阶段结果。
- 需求来源：RAG-034、RAG-037。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；tool.completed后暂停生成。
- 测试数据要求：随后成功或失败的两个Run。
- 测试流程：
  1. 读取API并观察真实浏览器。
  2. 工具完成时Run仍非终态，最终只按PG状态更新。
- 预期结果：tool.completed之后延迟/失败生成，API与页面仍按Run事实运行/失败；不得仅根据count或工具状态直接显示回答成功。
- 代码依据／主要定位：[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重；[`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue)：工具阶段展示。
- 优先级：P0。
- 用例类型：状态/投影。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；只有最终事件结束Run；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_015"></a>

#### EXE_015：Run取消确认

- 用例编号：`EXE_015`
- 对应测试点：`TQ-RAG-EXE-015`：Run取消确认。验证目标：cancelling到终态由有效执行者确认。
- 需求来源：RAG-034、RAG-037。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；活动Run检索/生成可暂停。
- 测试数据要求：cancel请求前后、代1迟到delta/引用。
- 测试流程：
  1. 发取消后读请求事实，再由Worker/回收器确认。
  2. 旧代迟到写被拒，页面不把HTTP200当云端停费。
- 预期结果：Run活动时取消先持久请求再由Worker/回收器写cancelled；旧代不能继续delta/引用/终态；请求返回200不等于已远端停计费。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：取消/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；正式任务完整成功；取消后无delta；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_016"></a>

#### EXE_016：Worker有界停机

- 用例编号：`EXE_016`
- 对应测试点：`TQ-RAG-EXE-016`：Worker有界停机。验证目标：停机不静默丢已领取任务。
- 需求来源：RAG-012、RAG-034、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；双Worker与可观察领取记录，宿主只操作本project。
- 测试数据要求：SIGTERM宽限内完成、显式释放、等待外部三组。
- 测试流程：
  1. 发停机信号并同时排入新任务。
  2. 停机Worker不新领，截止内完成/释放或lease回收，重启同工作无重复回答。
- 预期结果：收到信号不再领新Task，在宽限内完成/释放或由lease回收；远端等待让出不阻塞退出，重启可继续同工作且无重复回答。
- 代码依据／主要定位：[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/application/rag_task_execution.py`](../../backend/application/rag_task_execution.py)：lock_build_execution/yield_task/settle_rag_task。
- 优先级：P0。
- 用例类型：恢复/运维。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；停止后不再领取；新Worker续同工作；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_016.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_017"></a>

#### EXE_017：专用并发槽实际范围

- 用例编号：`EXE_017`
- 对应测试点：`TQ-RAG-EXE-017`：专用并发槽实际范围。验证目标：跨Worker门限与实际Task范围一致。
- 需求来源：RAG-012、NFR-004、NFR-008。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专用并发配置及tmp预算受控，多个Worker。
- 测试数据要求：上限配置值与floor(tmp_budget/384MiB)、waiting任务、Run检索。
- 测试流程：
  1. 并发领取构建/诊断并数活动槽。
  2. 全局不按Worker倍增，waiting让槽，Run检索现不计该门限需如实记录。
- 预期结果：多Worker验证构建/诊断全局上限min(配置,临时预算÷384MiB)，waiting不占槽；单Worker仍串行，Run内检索未计此门限需单列，不按每Worker放大吞吐。
- 代码依据／主要定位：[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized；[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch；[`backend/config.py`](../../backend/config.py)：Settings。
- 优先级：P1。
- 用例类型：容量/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；拒绝原因与约定一致；临时预算只允许一个共享槽；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_018"></a>

#### EXE_018：停用与blocked后的显式重试

- 用例编号：`EXE_018`
- 对应测试点：`TQ-RAG-EXE-018`：停用与blocked后的显式重试。验证目标：复用不等于绕过安全限制。
- 需求来源：RAG-035、RAG-036。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立failed/cancelled schema3源及冻结依赖。
- 测试数据要求：普通selection disabled、security blocked、缺View/不可用Profile。
- 测试流程：
  1. 分别显式retry。
  2. 普通停用可沿冻结依赖，安全/依赖异常明确拒绝或失败，无新库/空间兜底。
- 预期结果：普通选择停用可沿原冻结依赖，blocked/缺View/依赖不可用明确拒绝或失败；不能选新模型空间/库为其兜底。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason。
- 优先级：P0。
- 用例类型：权限/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；17项断言；正式任务完整成功；普通停用不换view；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_018.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="exe_019"></a>

#### EXE_019：回答流资源上限

- 用例编号：`EXE_019`
- 对应测试点：`TQ-RAG-EXE-019`：回答流资源上限。验证目标：生成异常流不会无限堆事件。
- 需求来源：RAG-037、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：execution；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Mock生成和受控流输入可参数化。
- 测试数据要求：step/stream timeout、raw delta数/输出字符/flush缓冲在上限前/等于/+1。
- 测试流程：
  1. 按冻结快照读取实际上限并独立生成数据。
  2. 核边界可控、超限安全结算且保终态事件额度，输出无无限增长。
- 预期结果：对有界step/stream timeout、raw delta数、输出字符和flush缓冲上限做边界数据，超限按安全错误结算，不追加无界消息或吞掉终态所需事件额度。
- 补充判定／证据边界：具体上限从RunSnapshot.execution读取并连同Profile/源码版本留证；数据组只超一个维度。增量缓冲字节上限、raw delta数和输出字符数分别观察，不能把字节数当token数。
- 代码依据／主要定位：[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算；[`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py)：append_event/list_events。
- 优先级：P0。
- 用例类型：边界/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-execution/execution/EXE_019.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories execution -RunId rag-repro-execution-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.12 UI：工作台浏览器交互

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-UI-001` | [UI_001：文件选择固定路线提示](#ui_001) | L | workspace／local |
| `TQ-RAG-UI-002` | [UI_002：逐次外发勾选重置](#ui_002) | L | workspace／local |
| `TQ-RAG-UI-003` | [UI_003：云能力不可用禁用提交](#ui_003) | L | workspace／local |
| `TQ-RAG-UI-004` | [UI_004：active与latest并列展示](#ui_004) | L | workspace／local |
| `TQ-RAG-UI-005` | [UI_005：无进度时的中文状态](#ui_005) | L | workspace／local |
| `TQ-RAG-UI-006` | [UI_006：上传未知响应原键重放](#ui_006) | L | workspace／local |
| `TQ-RAG-UI-007` | [UI_007：重建未知响应处理](#ui_007) | K | workspace／local |
| `TQ-RAG-UI-008` | [UI_008：RAG参数前端校验](#ui_008) | L | workspace／local |
| `TQ-RAG-UI-009` | [UI_009：诊断UI与聊天隔离](#ui_009) | L | workspace／local |
| `TQ-RAG-UI-010` | [UI_010：异步响应当前范围隔离](#ui_010) | L | workspace／local |
| `TQ-RAG-UI-011` | [UI_011：有界轮询与手动恢复](#ui_011) | L | workspace／local |
| `TQ-RAG-UI-012` | [UI_012：浏览器事件去重与事实恢复](#ui_012) | L | workspace／local |
| `TQ-RAG-UI-013` | [UI_013：证据来源与缺失提示](#ui_013) | L | workspace／local |
| `TQ-RAG-UI-014` | [UI_014：Markdown外部资产阻断](#ui_014) | L | workspace／local |
| `TQ-RAG-UI-015` | [UI_015：中文安全错误投影](#ui_015) | L | workspace／local |
| `TQ-RAG-UI-016` | [UI_016：页面分页显示完整性](#ui_016) | L | workspace／local |
| `TQ-RAG-UI-017` | [UI_017：阶段展示信息边界](#ui_017) | L | workspace／local |
| `TQ-RAG-UI-018` | [UI_018：构建取消操作事实恢复](#ui_018) | L | workspace／local |

<a id="ui_001"></a>

#### UI_001：文件选择固定路线提示

- 用例编号：`UI_001`
- 对应测试点：`TQ-RAG-UI-001`：文件选择固定路线提示。验证目标：用户明确知道本次解析去向。
- 需求来源：RAG-039。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实Playwright打开本轮同源页面。
- 测试数据要求：九种文件选择、txt/md与办公交替。
- 测试流程：
  1. 逐项选文件并检查中文路线。
  2. 办公完整原件外发/失败不回退提示存在，本地文本不出现可选增强或Office本地兜底。
- 预期结果：九格式选择显示txt/md本地、七办公MinerU完整原件外发且失败不回退；无“可选增强”勾选，不显示本地Office兜底。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互。
- 优先级：P1。
- 用例类型：交互。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_002"></a>

#### UI_002：逐次外发勾选重置

- 用例编号：`UI_002`
- 对应测试点：`TQ-RAG-UI-002`：逐次外发勾选重置。验证目标：前次同意不能沿用到新操作。
- 需求来源：RAG-039、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；办公上传及重建页面均可操作。
- 测试数据要求：选新文件/换文件/撤销勾选/第二次重建。
- 测试流程：
  1. 观察按钮及真实网络载荷。
  2. 每次授权重置，未同意零提交，授权请求cloud_consent/version正确。
- 预期结果：选/换办公文件及每次新重建重置授权，未同意/撤销时不能提交；真实网络请求中确认版本正确，不只看复选框存在。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll。
- 优先级：P0。
- 用例类型：交互/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_003"></a>

#### UI_003：云能力不可用禁用提交

- 用例编号：`UI_003`
- 对应测试点：`TQ-RAG-UI-003`：云能力不可用禁用提交。验证目标：已知不可用不会徒劳外发。
- 需求来源：RAG-039、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；服务端Profile可用性响应可改变。
- 测试数据要求：关闭MinerU/缺配置/格式不可用与txt正例。
- 测试流程：
  1. 加载页面并选办公文件。
  2. 核按钮和原因，随后变更服务状态并提交验证服务端重校验，本地仍可用。
- 预期结果：根据安全配置可用性阻止办公新请求并显示原因，本地文本仍可用；不可用信息变更后的状态由服务端重校验。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts)：selection/validateSettings/diagnose。
- 优先级：P1。
- 用例类型：交互/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_004"></a>

#### UI_004：active与latest并列展示

- 用例编号：`UI_004`
- 对应测试点：`TQ-RAG-UI-004`：active与latest并列展示。验证目标：旧可用与最新失败可同时看见。
- 需求来源：RAG-040、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例文档已有active，新构建可控失败。
- 测试数据要求：旧成功及新解析/向量失败。
- 测试流程：
  1. 浏览器发重建并等待终态。
  2. 核旧ready与latest安全错误并列，刷新后身份及两种状态保持。
- 预期结果：构建新尝试失败后旧active仍ready，页面同时显示最新安全错误/阶段；刷新恢复相同身份，不以一个status覆盖两种事实。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`frontend/src/components/rag-labels.ts`](../../frontend/src/components/rag-labels.ts)：中文标签映射。
- 优先级：P1。
- 用例类型：交互/状态。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_005"></a>

#### UI_005：无进度时的中文状态

- 用例编号：`UI_005`
- 对应测试点：`TQ-RAG-UI-005`：无进度时的中文状态。验证目标：不展示虚假百分比。
- 需求来源：RAG-008、RAG-040、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；远端受控阶段和无进度字段。
- 测试数据要求：排队/解析/转换/向量化/发布/cancelling，未知页数。
- 测试流程：
  1. 逐阶段浏览器截图与网络JSON对照。
  2. 不填伪百分比，取消提示远端可能继续，无退款假承诺。
- 预期结果：排队/解析/转换/向量化/发布/取消分别投影；未知页数不填0/100%，本地取消提示远端可能继续，不显示已退款。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/components/rag-labels.ts`](../../frontend/src/components/rag-labels.ts)：中文标签映射；[`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue)：工具阶段展示。
- 优先级：P1。
- 用例类型：交互/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_006"></a>

#### UI_006：上传未知响应原键重放

- 用例编号：`UI_006`
- 对应测试点：`TQ-RAG-UI-006`：上传未知响应原键重放。验证目标：网络未确认不重复造上传。
- 需求来源：RAG-006、RAG-039。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；网络拦截需先转发实际请求后丢弃响应。
- 测试数据要求：上传已受理断回包、确定4xx、切换库后的迟到响应。
- 测试流程：
  1. 重试观察key/file/参数沿用，PG只一Document/云任务。
  2. 4xx后允许新操作，不串显示旧库响应。
- 预期结果：服务端已登记但应答丢失时保留原文件/参数/key再次提交，确定4xx允许修改后新操作；切库/重试不把旧响应显示为当前文档。
- 代码依据／主要定位：[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll。
- 优先级：P0。
- 用例类型：交互/幂等。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_007"></a>

#### UI_007：重建未知响应处理

- 用例编号：`UI_007`
- 对应测试点：`TQ-RAG-UI-007`：重建未知响应处理。验证目标：用户能安全恢复未确认的重建。
- 需求来源：RAG-006、RAG-022、RAG-040。
- 当前可验证性：本机可验证·K（已知实现/契约差异，按完整目标断言，可能失败）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已知重建未知应答缺口，可先完成后台Build再重试。
- 测试数据要求：已受理重建丢包、活动时重试及完成后重试两组。
- 测试流程：
  1. 记录每次key/Job/batch与提示。
  2. 要求安全恢复不静默创建收费工作，不能只看活动复用就宣称原键恢复已实现。
- 预期结果：丢弃已受理重建应答，再次操作不应无提示创建另一收费工作；当前rebuild每次新UUID，需要按安全恢复目标实测，不能套用上传pending结论。
- 补充判定／证据边界：至少包含“第一次后台任务已完成后再点击”的时序，活动Build复用不能证明未知请求原键保留；只观察到新key而未真实产生新收费任务时，报告潜在重复操作风险，不能虚构已重复收费。
- 代码依据／主要定位：[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：交互/缺口。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_008"></a>

#### UI_008：RAG参数前端校验

- 用例编号：`UI_008`
- 对应测试点：`TQ-RAG-UI-008`：RAG参数前端校验。验证目标：非法设置提交前可理解拒绝。
- 需求来源：RAG-025、RAG-041。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；选择可用库和策略，正在运行的Run作对照。
- 测试数据要求：Top-K0/1/20/21，半径-1/0/2/3，标签/ID边界。
- 测试流程：
  1. 修改UI与绕过UI发非法数据。
  2. 核前端/后端校验、仅后续Run采用新值，无未实现candidate_k控件承诺。
- 预期结果：Top-K1～20/半径0～2/标签及范围边界校验，不出现candidate_k输入这种未实现控件；服务端仍校验，设置只作用后续Run。
- 代码依据／主要定位：[`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts)：selection/validateSettings/diagnose；[`frontend/src/components/RagPanel.vue`](../../frontend/src/components/RagPanel.vue)：配置与诊断投影。
- 优先级：P1。
- 用例类型：交互/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_009"></a>

#### UI_009：诊断UI与聊天隔离

- 用例编号：`UI_009`
- 对应测试点：`TQ-RAG-UI-009`：诊断UI与聊天隔离。验证目标：只检索操作不伪造聊天回答。
- 需求来源：RAG-031、RAG-041。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；浏览器诊断面板及独立检索库。
- 测试数据要求：固定query/策略，候选/分数/去除/degraded。
- 测试流程：
  1. 提交诊断并查看结果。
  2. 比较聊天行数和生成计数不变，不能把全增强内容声称最终模型预算预览。
- 预期结果：显示候选/分数/删减/模式，不创建Message/Run或生成；诊断全部增强内容不等于某生成模型最终预算，页面无预览时不得宣称已有。
- 代码依据／主要定位：[`frontend/src/components/RagPanel.vue`](../../frontend/src/components/RagPanel.vue)：配置与诊断投影；[`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts)：selection/validateSettings/diagnose。
- 优先级：P1。
- 用例类型：交互。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_010"></a>

#### UI_010：异步响应当前范围隔离

- 用例编号：`UI_010`
- 对应测试点：`TQ-RAG-UI-010`：异步响应当前范围隔离。验证目标：迟到响应不污染新选择。
- 需求来源：RAG-035、RAG-041、RAG-042。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可延迟本轮同源接口响应。
- 测试数据要求：库A→B、Bundle A→B、Run A→B快速切换。
- 测试流程：
  1. 先挂起A响应，显示B后放A。
  2. 核当前对象/页/查询身份不被旧响应覆盖，失败也不串错误。
- 预期结果：切换库/Bundle/Run后旧响应不能覆盖新对象，epoch/身份核对生效；查询参数在提交时冻结，不按新界面值解释旧执行。
- 补充判定／证据边界：分别覆盖库列表epoch、同库不同文档/Bundle身份和不同Run事件流；一种切换通过不能代替其余响应范围隔离，若同epoch内仍串响应应据实判失败。
- 代码依据／主要定位：[`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts)：selection/validateSettings/diagnose；[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue)：load/续读/epoch；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重。
- 优先级：P1。
- 用例类型：并发/交互。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_011"></a>

#### UI_011：有界轮询与手动恢复

- 用例编号：`UI_011`
- 对应测试点：`TQ-RAG-UI-011`：有界轮询与手动恢复。验证目标：自动观察暂停不等于业务终止。
- 需求来源：RAG-040、RAG-041、NFR-004。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；浏览器可控计时推进但不改服务端业务事实。
- 测试数据要求：持续pending到60次、提前终态、短时读失败。
- 测试流程：
  1. 观察约2秒间隔和最大轮询次数。
  2. 暂停后手动刷新可恢复，终态停轮询，错误保最后事实。
- 预期结果：文档/诊断最多60次约2秒轮询后暂停可手动刷新，服务端仍可继续；终态停止轮询，读失败保留最后事实和安全错误。
- 代码依据／主要定位：[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`frontend/src/stores/rag.ts`](../../frontend/src/stores/rag.ts)：selection/validateSettings/diagnose。
- 优先级：P1。
- 用例类型：交互/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_012"></a>

#### UI_012：浏览器事件去重与事实恢复

- 用例编号：`UI_012`
- 对应测试点：`TQ-RAG-UI-012`：浏览器事件去重与事实恢复。验证目标：刷新断线重复后展示一致。
- 需求来源：RAG-037。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实页面、EventSource/GET可控网络层。
- 测试数据要求：重复/乱序/缺口/旧Run事件、断线及刷新。
- 测试流程：
  1. 创建真实Run后注入传输序列并恢复Journal。
  2. 核按run_id/seq/有效代去重，有限重连GET恢复，不靠连通宣布成功。
- 预期结果：真实浏览器按run_id+seq和有效代处理重复/乱序/缺口，有限重连及GET恢复同Thread/Run；EventSource成功连接不能自行宣布终态。
- 代码依据／主要定位：[`frontend/src/events/rag-event-stream.ts`](../../frontend/src/events/rag-event-stream.ts)：parseV3Event/replayV3Events/openV3RunStream；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重。
- 优先级：P0。
- 用例类型：交互/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_013"></a>

#### UI_013：证据来源与缺失提示

- 用例编号：`UI_013`
- 对应测试点：`TQ-RAG-UI-013`：证据来源与缺失提示。验证目标：用户可区分原源和规范块。
- 需求来源：RAG-042、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；有可靠页/行与block_only的两类证据。
- 测试数据要求：batch/分数/component/hash及Parser/降级投影。
- 测试流程：
  1. 从回答或诊断打开EvidenceViewer并切换来源。
  2. 核各字段在其实际所属视图可见，缺坐标明确而非猜页。
- 预期结果：EvidenceViewer显示batch/分数/组件/hash与缺失坐标，parser在构建投影、降级在诊断/事件显示；不承诺Viewer直接具有全部字段。
- 代码依据／主要定位：[`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue)：load/续读/epoch；[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/components/RagPanel.vue`](../../frontend/src/components/RagPanel.vue)：配置与诊断投影；[`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue)：工具阶段展示。
- 优先级：P1。
- 用例类型：交互/位置。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_014"></a>

#### UI_014：Markdown外部资产阻断

- 用例编号：`UI_014`
- 对应测试点：`TQ-RAG-UI-014`：Markdown外部资产阻断。验证目标：文档/回答不能主动加载危险资源。
- 需求来源：RAG-042、NFR-002。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；安全Markdown合成响应及浏览器网络监听。
- 测试数据要求：script/onerror/javascript URL/HTML/外链img，正常表格代码。
- 测试流程：
  1. 渲染并检查DOM、脚本哨兵和出站请求。
  2. 危险内容无执行/资产外发，正常Markdown仍可读。
- 预期结果：脚本/事件属性/危险URL/HTML和外链图片等经清洗阻断；浏览器网络记录无外部资产请求，普通Markdown表格/代码仍可读。
- 代码依据／主要定位：[`frontend/src/markdown/render.ts`](../../frontend/src/markdown/render.ts)：Markdown清洗与远程资产阻断；[`frontend/src/components/MessageTimeline.vue`](../../frontend/src/components/MessageTimeline.vue)：引用与消息投影；[`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue)：load/续读/epoch。
- 优先级：P0。
- 用例类型：安全/交互。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_015"></a>

#### UI_015：中文安全错误投影

- 用例编号：`UI_015`
- 对应测试点：`TQ-RAG-UI-015`：中文安全错误投影。验证目标：错误可理解且无内部泄漏。
- 需求来源：RAG-040、RAG-041、RAG-042、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；错误响应仅含安全码，UI字典可读。
- 测试数据要求：未知提交/缺配置/empty/degraded/依赖失败及未知码。
- 测试流程：
  1. 逐组展示并刷新。
  2. 核中文说明与状态区别，未知码安全兜底，无stack/Key/路径/签名URL。
- 预期结果：未知提交/配置受限/empty/degraded/失败按事实区分，稳定错误码和中文说明可见；没有stack、私有路径、Key或签名链接。
- 代码依据／主要定位：[`frontend/src/components/rag-labels.ts`](../../frontend/src/components/rag-labels.ts)：中文标签映射；[`frontend/src/components/RagPanel.vue`](../../frontend/src/components/RagPanel.vue)：配置与诊断投影；[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue)：工具阶段展示。
- 优先级：P1。
- 用例类型：交互/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_015.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_016"></a>

#### UI_016：页面分页显示完整性

- 用例编号：`UI_016`
- 对应测试点：`TQ-RAG-UI-016`：页面分页显示完整性。验证目标：翻页不会混库漏来源。
- 需求来源：RAG-040、RAG-042、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；文档超过一页、批次超过20片、Bundle超过4000字。
- 测试数据要求：连续/重复点加载更多，翻页中切文档/Bundle。
- 测试流程：
  1. 记录cursor/offset及展示ID。
  2. 列表无重复遗漏，切对象清旧页，请求有界。
- 预期结果：文档/切片/证据续读与cursor/offset对应，切对象时清掉旧页，重复点击不堆重复片段；长列表/证据不一次无界拉取。
- 代码依据／主要定位：[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`frontend/src/components/EvidenceViewer.vue`](../../frontend/src/components/EvidenceViewer.vue)：load/续读/epoch；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影。
- 优先级：P1。
- 用例类型：交互/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_016.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_017"></a>

#### UI_017：阶段展示信息边界

- 用例编号：`UI_017`
- 对应测试点：`TQ-RAG-UI-017`：阶段展示信息边界。验证目标：只展示获准的执行阶段事实。
- 需求来源：RAG-037、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；阶段事件真实写入Journal，文档内有伪事件文本。
- 测试数据要求：检索/重排/上下文阶段与伪system事件/隐藏思维链标记。
- 测试流程：
  1. 观察事件时间线与消息正文分层。
  2. 仅真实安全阶段显示为系统阶段，无完整Prompt/私参/隐藏链泄露。
- 预期结果：在事件和页面检查检索/重排/上下文选择等安全阶段可见，模型隐藏思维链、完整Prompt和私有工具参数不被当阶段内容展示；文档文本中的伪造事件说明不能产生额外系统阶段。
- 代码依据／主要定位：[`frontend/src/components/RunTimeline.vue`](../../frontend/src/components/RunTimeline.vue)：工具阶段展示；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重；[`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py)：三代事件载荷。
- 优先级：P0。
- 用例类型：交互/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_017.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="ui_018"></a>

#### UI_018：构建取消操作事实恢复

- 用例编号：`UI_018`
- 对应测试点：`TQ-RAG-UI-018`：构建取消操作事实恢复。验证目标：浏览器取消不自行宣布业务终态。
- 需求来源：RAG-014、RAG-040。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：workspace；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可取消Build与旧active，页面轮询可恢复。
- 测试数据要求：排队/构建/远端等待中取消、终态重复操作。
- 测试流程：
  1. 点击取消后观察返回事实及后续PG投影。
  2. 刷新核最终状态，旧ready仍在，不声称云文件已撤回。
- 预期结果：对可取消构建点击取消，按返回事实显示请求已登记或cancelling，刷新/轮询取得最终状态；终态操作按服务端规则处理，已有ready批次不因本次取消消失，不显示云端已撤回。
- 代码依据／主要定位：[`frontend/src/components/DocumentUploader.vue`](../../frontend/src/components/DocumentUploader.vue)：格式/授权/构建交互；[`frontend/src/stores/documents.ts`](../../frontend/src/stores/documents.ts)：upload/retryUpload/rebuild/poll；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P1。
- 用例类型：交互/取消。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；浏览器执行了具体断言；真实浏览器目标成立；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-workspace/workspace/UI_018.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories workspace -RunId rag-repro-workspace-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.13 CMP：三代兼容、迁移与恢复

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-CMP-001` | [CMP_001：三代协议保持独立](#cmp_001) | L | compatibility／local |
| `TQ-RAG-CMP-002` | [CMP_002：旧DOCX写入明确升级](#cmp_002) | L | compatibility／local |
| `TQ-RAG-CMP-003` | [CMP_003：旧txt/md发布与新读取](#cmp_003) | L | compatibility／local |
| `TQ-RAG-CMP-004` | [CMP_004：旧客户端遇新Thread升级](#cmp_004) | L | compatibility／local |
| `TQ-RAG-CMP-005` | [CMP_005：旧迁移活动租约预检](#cmp_005) | L | compatibility／local |
| `TQ-RAG-CMP-006` | [CMP_006：显式默认库前置](#cmp_006) | L | compatibility／local |
| `TQ-RAG-CMP-007` | [CMP_007：旧未知空间隔离](#cmp_007) | L | compatibility／local |
| `TQ-RAG-CMP-008` | [CMP_008：可信旧空间确认约束](#cmp_008) | L | compatibility／local |
| `TQ-RAG-CMP-009` | [CMP_009：旧引用保护与缺失语义](#cmp_009) | L | compatibility／local |
| `TQ-RAG-CMP-010` | [CMP_010：四段升级可重复](#cmp_010) | L | compatibility／local |
| `TQ-RAG-CMP-011` | [CMP_011：新事实拒绝普通downgrade](#cmp_011) | L | compatibility／local |
| `TQ-RAG-CMP-012` | [CMP_012：一致备份恢复](#cmp_012) | L | compatibility／local |
| `TQ-RAG-CMP-013` | [CMP_013：位置契约允许值一致](#cmp_013) | K | compatibility／local |
| `TQ-RAG-CMP-014` | [CMP_014：旧协议在途Run执行边界](#cmp_014) | L | compatibility／local |

<a id="cmp_001"></a>

#### CMP_001：三代协议保持独立

- 用例编号：`CMP_001`
- 对应测试点：`TQ-RAG-CMP-001`：三代协议保持独立。验证目标：新协议不重写旧事实。
- 需求来源：RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮单独构造三代历史，不调用旧suite。
- 测试数据要求：schema1/2/3 Message/Event/Run、Citation1/2。
- 测试流程：
  1. 分别走相应读取接口并按原Schema验证。
  2. 迁移前后原JSON/hash一致，不把所有版本统一标3。
- 预期结果：用本轮自建schema1/2/3样本分别读/验证，旧Message/Event原JSON及hash不变，新Citation/Evidence各自版本正确，不按产品v0.3猜所有schema=3。
- 代码依据／主要定位：[`backend/api/schemas/v3/sessions.py`](../../backend/api/schemas/v3/sessions.py)：Message/CitationV2/RunDetail；[`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py)：三代事件载荷；[`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py)：wire_catalog/export --check。
- 优先级：P0。
- 用例类型：契约/兼容。
- 是否适合自动化：是。
- 实际测试结果：通过；74项断言；正式任务完整成功；读取未修改旧JSON/hash依据；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_002"></a>

#### CMP_002：旧DOCX写入明确升级

- 用例编号：`CMP_002`
- 对应测试点：`TQ-RAG-CMP-002`：旧DOCX写入明确升级。验证目标：旧客户端不能无授权云上传。
- 需求来源：RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；可信旧DOCX文档及v1上传/重建入口。
- 测试数据要求：合法DOCX、其他新办公格式、旧历史读取。
- 测试流程：
  1. 调用旧写入口。
  2. 核DOCUMENT_WRITE_UPGRADE_REQUIRED或格式拒绝先于新事实，云调用0。
  3. 旧详情/引用仍可读。
- 预期结果：v1 DOCX上传/重建在新事实前返回DOCUMENT_WRITE_UPGRADE_REQUIRED；旧历史可读，其他新办公格式不被旧入口顺带接受，远端计数0。
- 代码依据／主要定位：[`backend/application/documents.py`](../../backend/application/documents.py)：create_document/create_index_task；[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade。
- 优先级：P0。
- 用例类型：兼容/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；8项断言；旧入口明确拒绝办公写入；迁移保留历史文档；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_003"></a>

#### CMP_003：旧txt/md发布与新读取

- 用例编号：`CMP_003`
- 对应测试点：`TQ-RAG-CMP-003`：旧txt/md发布与新读取。验证目标：保留旧写时点且新链可追溯。
- 需求来源：RAG-015、RAG-021、RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮自建可信legacy384库，v1纯文本路径。
- 测试数据要求：txt/md合法及原错误时点负例。
- 测试流程：
  1. 经v1上传到发布。
  2. 核Build/space/Artifact/hash补齐且v3可检索，旧错误契约不被改成云解析。
- 预期结果：可信旧384空间下v1本地文本按原错误时点写入，发布补Build/space/Artifact/hash，v3可检索/读正文；不冒充MinerU或新结构重解析。
- 代码依据／主要定位：[`backend/application/documents.py`](../../backend/application/documents.py)：create_document/create_index_task；[`backend/infrastructure/rag/pgvector_store.py`](../../backend/infrastructure/rag/pgvector_store.py)：PgVectorStore.replace/旧协议检索；[`backend/application/legacy_rag.py`](../../backend/application/legacy_rag.py)：materialize_legacy_text/protect_legacy_items。
- 优先级：P0。
- 用例类型：兼容。
- 是否适合自动化：是。
- 实际测试结果：通过；21项断言；旧文本发布在新协议可用；兼容发布补齐空间与Artifact；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_004"></a>

#### CMP_004：旧客户端遇新Thread升级

- 用例编号：`CMP_004`
- 对应测试点：`TQ-RAG-CMP-004`：旧客户端遇新Thread升级。验证目标：不能用旧响应强装schema3。
- 需求来源：RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；Thread同时含旧历史与新schema3 Run。
- 测试数据要求：v2详情/写入、v2元数据/Branch/Models、v3详情。
- 测试流程：
  1. 分别访问。
  2. 需升级路径明确拒绝，其余仍按原契约复用，旧Run事件版本不改。
- 预期结果：Thread有schema3后v2详情/写入升级，v3读全历史；v2元数据/Branch/Models仍复用，旧Run按原版本读，不因同Thread重标事件。
- 代码依据／主要定位：[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run；[`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py)：消息/Run/Event/SSE/取消/重试端点；[`backend/api/schemas/v3/sessions.py`](../../backend/api/schemas/v3/sessions.py)：Message/CitationV2/RunDetail。
- 优先级：P0。
- 用例类型：兼容/契约。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_005"></a>

#### CMP_005：旧迁移活动租约预检

- 用例编号：`CMP_005`
- 对应测试点：`TQ-RAG-CMP-005`：旧迁移活动租约预检。验证目标：升级不与旧Worker竞跑。
- 需求来源：RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立PG数据库迁至0006，有本例有效活动租约。
- 测试数据要求：0007升级前租约有效/到期、未结束旧DOCX。
- 测试流程：
  1. 运行实际迁移。
  2. 有效租约明确拒绝而不抢停，待停Worker/租约过期后再升级，遗留DOCX按升级要求收尾不外发。
- 预期结果：0007发现有效活动租约就拒绝，要求先停Worker等待，不主动停租约；遗留未结束DOCX按升级要求收尾，不隐式外发。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade；[`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py)：upgrade。
- 优先级：P0。
- 用例类型：迁移/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；拒绝原因与约定一致；遗留DOCX明确升级终止；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_006"></a>

#### CMP_006：显式默认库前置

- 用例编号：`CMP_006`
- 对应测试点：`TQ-RAG-CMP-006`：显式默认库前置。验证目标：旧文档归属有确定来源。
- 需求来源：RAG-001、RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属非空旧库，0007之后可调用正式bootstrap。
- 测试数据要求：缺默认Profile/库与显式导入正例，两owner。
- 测试流程：
  1. 先缺bootstrap尝试0008验证拒绝。
  2. 显式导入再升级核唯一归属，不猜空间或付费重索引。
- 预期结果：0007后显式导入默认Profile/库，0008为每owner确定唯一归属；非空旧库缺bootstrap拒绝，不自动猜空间或付费重索引。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade；[`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py)：upgrade。
- 优先级：P0。
- 用例类型：迁移/一致性。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；拒绝原因与约定一致；旧文档显式归属；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_007"></a>

#### CMP_007：旧未知空间隔离

- 用例编号：`CMP_007`
- 对应测试点：`TQ-RAG-CMP-007`：旧未知空间隔离。验证目标：384维不能默认等于Mock。
- 需求来源：RAG-002、RAG-018、RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；旧向量来源不可信的本轮夹具。
- 测试数据要求：legacy_unknown、reindex_required、可信384/新1024对照。
- 测试流程：
  1. 升级并尝试新检索。
  2. 未知批次隔离，旧向量数值/hash不变，不混进可信空间。
- 预期结果：未知旧批次legacy_unknown/reindex_required，不可混入新1024或可信384查询；只有明确部署来源才显式确认，不改旧向量数值含义。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade；[`backend/tools/confirm_legacy_rag_space.py`](../../backend/tools/confirm_legacy_rag_space.py)：可信旧空间确认入口；[`backend/infrastructure/rag/pgvector_store.py`](../../backend/infrastructure/rag/pgvector_store.py)：PgVectorStore.replace/旧协议检索。
- 优先级：P0。
- 用例类型：迁移/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；旧向量字节含义不变；不自动确认；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_008"></a>

#### CMP_008：可信旧空间确认约束

- 用例编号：`CMP_008`
- 对应测试点：`TQ-RAG-CMP-008`：可信旧空间确认约束。验证目标：显式确认不能改绑库或造向量。
- 需求来源：RAG-002、RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；正式legacy确认工具可在专属库运行。
- 测试数据要求：一致部署来源及原space、混合来源、错误space。
- 测试流程：
  1. 逐组尝试确认。
  2. 合法仅改可信状态且向量未重算，混杂/错空间拒绝。
  3. 标记不作效果证据。
- 预期结果：确认工具要求全库一致可信依据且匹配原绑定空间，来源混杂/异空间拒绝；不重新算向量、不把标记confirmed当语义效果证明。
- 代码依据／主要定位：[`backend/tools/confirm_legacy_rag_space.py`](../../backend/tools/confirm_legacy_rag_space.py)：可信旧空间确认入口；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键。
- 优先级：P0。
- 用例类型：迁移/权限。
- 是否适合自动化：是。
- 实际测试结果：通过；15项断言；拒绝原因与约定一致；不重算旧向量；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_009"></a>

#### CMP_009：旧引用保护与缺失语义

- 用例编号：`CMP_009`
- 对应测试点：`TQ-RAG-CMP-009`：旧引用保护与缺失语义。验证目标：存在引用可保留，丢失不伪造。
- 需求来源：RAG-021、RAG-038。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；升级前旧引用及旧版已缺Chunk两组。
- 测试数据要求：存量引用、旧协议新写引用、已不存在历史片段。
- 测试流程：
  1. 迁移并创建新旧协议引用。
  2. 查LegacyEvidenceRef保护。
  3. 缺片段明确不可恢复，不同text猜补。
- 预期结果：迁移及旧协议新写引用建立LegacyEvidenceRef保护；已被前版删除的Chunk标不可恢复，不能按同text或当前active猜补历史。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade；[`backend/application/legacy_rag.py`](../../backend/application/legacy_rag.py)：materialize_legacy_text/protect_legacy_items；[`backend/infrastructure/rag/pgvector_store.py`](../../backend/infrastructure/rag/pgvector_store.py)：PgVectorStore.replace/旧协议检索。
- 优先级：P0。
- 用例类型：兼容/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；现存与不可恢复分别标识；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_010"></a>

#### CMP_010：四段升级可重复

- 用例编号：`CMP_010`
- 对应测试点：`TQ-RAG-CMP-010`：四段升级可重复。验证目标：空库与旧库升级到正确head。
- 需求来源：RAG-038、NFR-010、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属旧PG及许可夹具，已停止本例Worker。
- 测试数据要求：0007/显式bootstrap/0008/0009/0010。
- 测试流程：
  1. 按产品工具实际顺序升级并重复upgrade。
  2. 核revision、回填数/hash及Profile未被覆盖，不能用create_all替代。
- 预期结果：独立PG实际执行0007→0008→0009→0010及bootstrap，revision长度合法，重复upgrade不覆盖Profile、不重复回填；不是仅create_all模型测试。
- 代码依据／主要定位：[`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py)：upgrade；[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade。
- 优先级：P0。
- 用例类型：迁移/部署。
- 是否适合自动化：是。
- 实际测试结果：通过；3项断言；重复升级无额外回填；Alembic revision长度合法；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_011"></a>

#### CMP_011：新事实拒绝普通downgrade

- 用例编号：`CMP_011`
- 对应测试点：`TQ-RAG-CMP-011`：新事实拒绝普通downgrade。验证目标：回退不能破坏新身份。
- 需求来源：RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；两个独立库：纯结构与含受保护新事实。
- 测试数据要求：ParseJob/View/RagOperation/schema3/多维等分别存在。
- 测试流程：
  1. 尝试实际downgrade。
  2. 有事实RAG_DOWNGRADE_DATA_PRESENT且无丢数据，纯结构按允许路径可回退。
- 预期结果：有ParseJob/View/操作/schema3或多维等受保护事实时RAG_DOWNGRADE_DATA_PRESENT，不能删事实或裁384向量绕过；纯结构合法回退单独核对。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade。
- 优先级：P0。
- 用例类型：迁移/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；12项断言；正式任务完整成功；纯结构回退完成；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_012"></a>

#### CMP_012：一致备份恢复

- 用例编号：`CMP_012`
- 对应测试点：`TQ-RAG-CMP-012`：一致备份恢复。验证目标：回滚恢复原数据库与文件一致性。
- 需求来源：RAG-021、RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；只操作本轮专属PG/源/Artifact卷，停写。
- 测试数据要求：升级前PG dump、源/产物hash及匹配镜像清单。
- 测试流程：
  1. 备份后升级生成受控新事实。
  2. 停写恢复备份和镜像，再核旧消息/引用/hash并重迁移。
  3. 说明升级后新事实未包含。
- 预期结果：在本轮专属旧库/卷保存升级前PG+源/产物+镜像匹配备份，停写恢复后核旧消息/引用/hash及再迁移；不对开发库操作，不承诺无损带回升级后新事实。
- 补充判定／证据边界：恢复只宣称恢复备份时点；升级后产生的新事实不在旧备份，不能写成跨版本无损回退。备份只放本轮私有tmp，释放前保存脱敏hash证据。
- 代码依据／主要定位：[`migrations/rag_checks.py`](../../migrations/rag_checks.py)：drain_legacy_docx/prepare_legacy_documents/backfill_legacy_builds/guard_downgrade；[`backend/tools/upgrade_rag_schema.py`](../../backend/tools/upgrade_rag_schema.py)：upgrade；[`docs/adr/003-sesrag-rag-mineru-implementation-plan.md`](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md)：实施决策/不变量。
- 优先级：P0。
- 用例类型：恢复/运维。
- 是否适合自动化：是。
- 实际测试结果：通过；6项断言；实际pg_dump成功；恢复为旧版本事实；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_013"></a>

#### CMP_013：位置契约允许值一致

- 用例编号：`CMP_013`
- 对应测试点：`TQ-RAG-CMP-013`：位置契约允许值一致。验证目标：接口说明与真实DTO不矛盾。
- 需求来源：RAG-038、RAG-042、NFR-010。
- 当前可验证性：本机可验证·K（已知实现/契约差异，按完整目标断言，可能失败）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；按真实缺位产物读取位置DTO/JSON Schema/接口说明。
- 测试数据要求：quality=verified/block_only/unavailable三枚举对照。
- 测试流程：
  1. 记录实际缺位投影并校验严格Schema。
  2. 与接口说明对比，发现不一致记契约失败，不能杜撰接受unavailable。
- 预期结果：正式说明有quality=unavailable而Location DTO仅verified/block_only；验证缺失位置实际投影与严格Schema，按真源一致目标登记差异，不杜撰已支持的值。
- 代码依据／主要定位：[`backend/api/schemas/v3/documents.py`](../../backend/api/schemas/v3/documents.py)：Document/IndexBuild/Location/ChunkPolicy；[`backend/application/source_locations.py`](../../backend/application/source_locations.py)：clip_locations/public_locations；[`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py)：wire_catalog/export --check。
- 优先级：P1。
- 用例类型：契约/缺口。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；正式说明与Location质量枚举一致；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_013.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="cmp_014"></a>

#### CMP_014：旧协议在途Run执行边界

- 用例编号：`CMP_014`
- 对应测试点：`TQ-RAG-CMP-014`：旧协议在途Run执行边界。验证目标：待执行旧Run不被套用新知识语义。
- 需求来源：RAG-038、NFR-003、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：compatibility；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮独立构造schema1/2待执行Run。
- 测试数据要求：可信旧配置向量与不可恢复/未知空间两组。
- 测试流程：
  1. 在新Worker沿原协议执行。
  2. 合法正常，依赖坏明确失败。
  3. 快照/事件原版本不改、不补View/ToolCall、不换空间。
- 预期结果：本轮自建schema1/2待执行Run，在原冻结配置及可信兼容向量满足时沿原协议执行；原配置无法恢复或空间不可信时明确失败，不换新空间、不为历史Run补造View/ToolCall或改写快照。
- 代码依据／主要定位：[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/infrastructure/rag/pgvector_store.py`](../../backend/infrastructure/rag/pgvector_store.py)：PgVectorStore.replace/旧协议检索；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算。
- 优先级：P0。
- 用例类型：兼容/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；25项断言；正式任务完整成功；不补造View；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-compatibility/compatibility/CMP_014.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories compatibility -RunId rag-repro-compatibility-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.14 LIF：容量、业务GC与保留

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-LIF-001` | [LIF_001：软容量预算拒绝](#lif_001) | L | lifecycle／local |
| `TQ-RAG-LIF-002` | [LIF_002：并发容量预留](#lif_002) | L | lifecycle／local |
| `TQ-RAG-LIF-003` | [LIF_003：引用中批次清理保护](#lif_003) | L | lifecycle／local |
| `TQ-RAG-LIF-004` | [LIF_004：无引用候选清理年龄](#lif_004) | L | lifecycle／local |
| `TQ-RAG-LIF-005` | [LIF_005：GC预览和执行一致性](#lif_005) | L | lifecycle／local |
| `TQ-RAG-LIF-006` | [LIF_006：GC与引用创建竞争](#lif_006) | L | lifecycle／local |
| `TQ-RAG-LIF-007` | [LIF_007：私有临时文件路径清理](#lif_007) | L | lifecycle／local |
| `TQ-RAG-LIF-008` | [LIF_008：诊断七天保留](#lif_008) | L | lifecycle／local |
| `TQ-RAG-LIF-009` | [LIF_009：墓碑与权限响应](#lif_009) | L | lifecycle／local |
| `TQ-RAG-LIF-010` | [LIF_010：清理产物后的重建](#lif_010) | L | lifecycle／local |

<a id="lif_001"></a>

#### LIF_001：软容量预算拒绝

- 用例编号：`LIF_001`
- 对应测试点：`TQ-RAG-LIF-001`：软容量预算拒绝。验证目标：满额拒绝不损已有active。
- 需求来源：RAG-020、RAG-046、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例独占卷和可调软预算，不填满宿主盘。
- 测试数据要求：源/产物/向量估算+活动预留在阈值前/等于/超出，受控disk_usage不足。
- 测试流程：
  1. 分别发新构建/诊断并读容量拒绝。
  2. 比较估算与卷实际，拒绝无可运行工作，不声称宿主硬配额。
- 预期结果：累计源/产物/向量估算+活动构建预留超过配置预算或磁盘不足，新工作安全失败；报告估算与实际占用，不能当宿主硬配额。
- 代码依据／主要定位：[`backend/application/rag_capacity.py`](../../backend/application/rag_capacity.py)：reserve_storage/storage_usage；[`backend/config.py`](../../backend/config.py)：Settings；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P1。
- 用例类型：容量/边界。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；拒绝不遗留可运行任务；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_002"></a>

#### LIF_002：并发容量预留

- 用例编号：`LIF_002`
- 对应测试点：`TQ-RAG-LIF-002`：并发容量预留。验证目标：多个API不能同时超额受理。
- 需求来源：NFR-004、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG多连接及接近上限的容量夹具。
- 测试数据要求：并发两个新请求、终态释放、tmp预算低于384MiB。
- 测试流程：
  1. 同步请求并查锁/活动预留总量。
  2. 不能双放超额或永久保留活动预留，过低tmp明确拒绝。
- 预期结果：近预算边界多个请求在PG锁下序列化预留，失败/终态不留下永远活动预留；tmp低于384MiB配置直接拒绝而不是永远无槽。
- 代码依据／主要定位：[`backend/application/rag_capacity.py`](../../backend/application/rag_capacity.py)：reserve_storage/storage_usage；[`backend/application/rag_operations.py`](../../backend/application/rag_operations.py)：replay/record/transaction_lock；[`backend/config.py`](../../backend/config.py)：Settings；[`backend/infrastructure/queue/postgres_queue.py`](../../backend/infrastructure/queue/postgres_queue.py)：claim_next_task/lock_owned_task/commit_authorized。
- 优先级：P0。
- 用例类型：并发/容量。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；预算不可双放；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_003"></a>

#### LIF_003：引用中批次清理保护

- 用例编号：`LIF_003`
- 对应测试点：`TQ-RAG-LIF-003`：引用中批次清理保护。验证目标：GC不可删历史依赖事实。
- 需求来源：RAG-021、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；每个保护关系均有独立被引用批次及无引用对照。
- 测试数据要求：active/latest/View/Bundle/ContextEvidence/Citation/LegacyRef。
- 测试流程：
  1. 逐种执行业务GC。
  2. 回读依赖正文/hash，保护批次不删，无引用对照按年龄条件可清理。
- 预期结果：active/latest/View/Bundle/ContextEvidence/Citation/LegacyRef依赖的批次、Chunk及必要Artifact保持可读；有无引用的对照不得仅查删除SQL成功。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/db/rag_models.py`](../../backend/db/rag_models.py)：KnowledgeBaseModel/IndexBuildModel/关系外键；[`backend/application/rag_retention.py`](../../backend/application/rag_retention.py)：collect_diagnostics/check_expired。
- 优先级：P0。
- 用例类型：安全/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；29项断言；正式任务完整成功；上下文范围真实落库；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_004"></a>

#### LIF_004：无引用候选清理年龄

- 用例编号：`LIF_004`
- 对应测试点：`TQ-RAG-LIF-004`：无引用候选清理年龄。验证目标：GC按创建时间和终态筛选。
- 需求来源：RAG-021、RAG-046、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；只调整本例夹具created_at，不改宿主时间。
- 测试数据要求：创建不足24h、恰好24h、超过24h、仍活动与无引用终态。
- 测试流程：
  1. 在固定时钟下预览/apply。
  2. 仅严格超过阈值且满足终态无引用者可删，Job错误/hash/unknown摘要仍保存。
- 预期结果：创建时间超过默认24h且终态、无引用才可清理，未满/仍活动保护；保留Job错误/source hash/未知提交摘要，不误按完成后24h。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect。
- 优先级：P1。
- 用例类型：边界/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；保留Job与源hash事实；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_005"></a>

#### LIF_005：GC预览和执行一致性

- 用例编号：`LIF_005`
- 对应测试点：`TQ-RAG-LIF-005`：GC预览和执行一致性。验证目标：dry-run不变更且执行可复查。
- 需求来源：RAG-021、RAG-046、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立可清理和被保护的对象集合。
- 测试数据要求：dry-run默认、apply两次、错误范围/源卷对照。
- 测试流程：
  1. 先拍PG/文件快照再预览。
  2. 预览不变更，执行与规则一致，重复幂等，源文件和外部项目卷不删。
- 预期结果：默认dry-run只报计划，apply按同规则删除并可重复执行，清理后读资源按约定错误；source与非本轮开发卷不属于业务GC删除目标。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/application/rag_capacity.py`](../../backend/application/rag_capacity.py)：reserve_storage/storage_usage。
- 优先级：P1。
- 用例类型：功能/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；上传源未被业务GC删除；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_006"></a>

#### LIF_006：GC与引用创建竞争

- 用例编号：`LIF_006`
- 对应测试点：`TQ-RAG-LIF-006`：GC与引用创建竞争。验证目标：清理不破坏并发新增引用。
- 需求来源：RAG-020、RAG-021、NFR-003、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG多连接和可观测锁序，设置有界lock/statement timeout。
- 测试数据要求：GC对冻结View/发布/取消各两种先后顺序。
- 测试流程：
  1. 受控交错事务并记录等待/错误。
  2. 核无悬空引用，安全回滚可诊断，不能预设代码已有死锁。
- 预期结果：真PG多连接在GC/冻结View/发布/取消间竞争，锁序/外键保护避免引用悬空与不可控死锁；ADR局部锁序差异记录，不预设已有死锁。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/application/retrieval_views.py`](../../backend/application/retrieval_views.py)：freeze_retrieval/load_scope；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`docs/adr/003-sesrag-rag-mineru-implementation-plan.md`](../../docs/adr/003-sesrag-rag-mineru-implementation-plan.md)：实施决策/不变量。
- 优先级：P0。
- 用例类型：并发/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；无悬空组件；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_007"></a>

#### LIF_007：私有临时文件路径清理

- 用例编号：`LIF_007`
- 对应测试点：`TQ-RAG-LIF-007`：私有临时文件路径清理。验证目标：仅删除过期且无活动依赖文件。
- 需求来源：RAG-011、RAG-014、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；专属临时/产物目录及外部哨兵文件。
- 测试数据要求：单层过期普通文件、活动state/query key、symlink、逃逸路径、迟到文件。
- 测试流程：
  1. 运行生产文件清理预览/apply。
  2. 只清明确可回收普通文件，链接/活动文件保护，根外哨兵不变。
- 预期结果：只扫专用目录单层普通文件，活动state/query key及链接保护，路径逃逸拒绝，不递归删源/数据库卷；迟到文件也按归属清理。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/infrastructure/rag/artifact_store.py`](../../backend/infrastructure/rag/artifact_store.py)：ArtifactStore。
- 优先级：P0。
- 用例类型：安全/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；5项断言；仅陈旧普通文件删除；根外哨兵不变；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_008"></a>

#### LIF_008：诊断七天保留

- 用例编号：`LIF_008`
- 对应测试点：`TQ-RAG-LIF-008`：诊断七天保留。验证目标：过期诊断不误删Run证据。
- 需求来源：RAG-021、RAG-041、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；终态diagnostic、活动diagnostic及Run视图。
- 测试数据要求：created_at距今7天±边界，有/无ContextEvidence依赖。
- 测试流程：
  1. 固定时钟运行诊断保留清理。
  2. 仅超7天终态无依赖诊断及其专属对象删除，Run共享视图不删。
- 预期结果：created_at超过7天且终态/无ContextEvidence依赖的独立diagnostic才删其专属View/Bundle，Run视图不按该规则清理；活动/未满/被引用保护。
- 代码依据／主要定位：[`backend/application/rag_retention.py`](../../backend/application/rag_retention.py)：collect_diagnostics/check_expired。
- 优先级：P1。
- 用例类型：边界/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；Run视图不被诊断保留策略清理；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_009"></a>

#### LIF_009：墓碑与权限响应

- 用例编号：`LIF_009`
- 对应测试点：`TQ-RAG-LIF-009`：墓碑与权限响应。验证目标：过期响应有界且不泄漏存在性。
- 需求来源：RAG-021、RAG-041、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已清理资源墓碑，仅本例可调时钟。
- 测试数据要求：原owner在墓碑30天内/边界/之后、其他owner、重复GC。
- 测试流程：
  1. 逐时点读取Execution/Bundle。
  2. 原owner有效墓碑410、超期404，其他owner始终404，重复清理不延墓碑。
- 预期结果：清理后原owner在墓碑创建30天内410，之后404；其他owner始终404；重复清理不扩成永久墓碑或暴露私有ID。
- 补充判定／证据边界：固定时钟验证恰好30天仍在墓碑条件“created_at>=now-30d”内，超过边界才404；不同owner不因墓碑ID存在而获410。
- 代码依据／主要定位：[`backend/application/rag_retention.py`](../../backend/application/rag_retention.py)：collect_diagnostics/check_expired；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P1。
- 用例类型：接口/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；20项断言；正式任务完整成功；墓碑不续期；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="lif_010"></a>

#### LIF_010：清理产物后的重建

- 用例编号：`LIF_010`
- 对应测试点：`TQ-RAG-LIF-010`：清理产物后的重建。验证目标：已删Artifact不能被错误复用。
- 需求来源：RAG-013、RAG-021、RAG-022。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：lifecycle；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例成功Artifact已合法变为无引用可清理对象。
- 测试数据要求：GC清掉产物、旧unknown_may_continue摘要对照。
- 测试流程：
  1. 发新合法重建。
  2. 核不能复用空artifact_id，按原格式路线重新解析/授权，未知历史仍要求重复成本确认。
- 预期结果：无引用产物被GC清除后新构建不因旧Job succeeded而复用空artifact_id，重新走合法路线/授权，未知提交摘要仍能触发重复成本提示。
- 代码依据／主要定位：[`backend/application/rag_gc.py`](../../backend/application/rag_gc.py)：protected/collect；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P0。
- 用例类型：恢复/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；25项断言；正式任务完整成功；不复用空产物，创建新解析；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-lifecycle/lifecycle/LIF_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories lifecycle -RunId rag-repro-lifecycle-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.15 REAL：逐格式与真实业务

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-REAL-001` | [REAL_001：真实DOCX正文表格解析](#real_001) | R | real-formats／real |
| `TQ-RAG-REAL-002` | [REAL_002：真实DOC正文解析](#real_002) | R | real-formats／real |
| `TQ-RAG-REAL-003` | [REAL_003：真实文本PDF解析](#real_003) | R | real-formats／real |
| `TQ-RAG-REAL-004` | [REAL_004：真实扫描PDF文字识别](#real_004) | R | real-formats／real |
| `TQ-RAG-REAL-005` | [REAL_005：真实XLSX表格解析](#real_005) | R | real-formats／real |
| `TQ-RAG-REAL-006` | [REAL_006：真实XLS表格解析](#real_006) | R | real-formats／real |
| `TQ-RAG-REAL-007` | [REAL_007：真实PPTX幻灯文本解析](#real_007) | R | real-formats／real |
| `TQ-RAG-REAL-008` | [REAL_008：真实PPT幻灯文本解析](#real_008) | R | real-formats／real |
| `TQ-RAG-REAL-009` | [REAL_009：真实生成请求与流式返回](#real_009) | R | real-business／real |
| `TQ-RAG-REAL-010` | [REAL_010：四类真实能力业务身份链](#real_010) | B | real-business／real |
| `TQ-RAG-REAL-011` | [REAL_011：真实服务限额和未知成本](#real_011) | R | real-business／real |
| `TQ-RAG-REAL-012` | [REAL_012：真实结果证据分层](#real_012) | L | quality／local |

<a id="real_001"></a>

#### REAL_001：真实DOCX正文表格解析

- 用例编号：`REAL_001`
- 对应测试点：`TQ-RAG-REAL-001`：真实DOCX正文表格解析。验证目标：DOCX取得可核对的实际云产物。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例：明确外发授权/白名单/额度，且当前Real总门禁须满足或后续先按方案修正分能力准入。
- 测试数据要求：本轮hash冻结DOCX、预标标题/正文/表格关键值和可定位范围。
- 测试流程：
  1. 由正式产品上传原件并调用真实MinerU。
  2. 保存同轮解析产物与抽样内容对照，独立解析可用Mock向量但只声明解析真实。
- 预期结果：逐次获准原件经MinerU生产适配，正文/标题/表格和值与原件抽样对照，规范块/hash可追溯；允许独立使用Mock向量仅验解析，但不得叫全链真实。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；19项断言；本轮真实MinerU解析终态；表格样本保留表格结构；[本轮证据](artifacts/rag-repair-20261113-real1/sesrag-rag-repair-20261113-real1-real-formats/real-formats/REAL_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format1.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_002"></a>

#### REAL_002：真实DOC正文解析

- 用例编号：`REAL_002`
- 对应测试点：`TQ-RAG-REAL-002`：真实DOC正文解析。验证目标：旧DOC不是改后缀伪造正例。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，原件许可/NOTICE与外发计划完整。
- 测试数据要求：固定真实二进制DOC、逐项原文摘要/标题/段落预标。
- 测试流程：
  1. 单独正式上传解析。
  2. 逐项核返回文本/结构与位置质量，失败按DOC登记，不借DOCX结果或本地转换。
- 预期结果：使用有许可且hash固定的真实OLE DOC，实际云端返回有效正文/结构，逐项记录遗漏/位置质量，失败不转本地；独立记录该格式受限条件。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/兼容。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；19项断言；本轮真实MinerU解析终态；返回可用于文本RAG的结构块；[本轮证据](artifacts/rag-repair-20261113-real2/sesrag-rag-repair-20261113-real2-real-formats/real-formats/REAL_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format2.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_003"></a>

#### REAL_003：真实文本PDF解析

- 用例编号：`REAL_003`
- 对应测试点：`TQ-RAG-REAL-003`：真实文本PDF解析。验证目标：文本型PDF内容与可靠位置有效。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，生产MinerU配置及外发授权齐备。
- 测试数据要求：固定文本PDF、标题/表格/正文及原页预标。
- 测试流程：
  1. 正式上传并观察真实解析。
  2. 对照关键内容、可靠page映射或明确block_only，done不能代替质量判断。
- 预期结果：真实原件解析正文/标题/表格，页码仅可靠时核验原页，无映射明确规范块；实际内容错误不能因接口done判通过。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；19项断言；本轮真实MinerU解析终态；返回可用于文本RAG的结构块；[本轮证据](artifacts/rag-repair-20261113-real3/sesrag-rag-repair-20261113-real3-real-formats/real-formats/REAL_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format3.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_004"></a>

#### REAL_004：真实扫描PDF文字识别

- 用例编号：`REAL_004`
- 对应测试点：`TQ-RAG-REAL-004`：真实扫描PDF文字识别。验证目标：扫描文字经实际OCR产生有效文本。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，与文本PDF分开登记原件hash。
- 测试数据要求：受控扫描PDF、清晰可读预标文字及所在原页。
- 测试流程：
  1. 正式请求真实解析。
  2. 核预标文字/位置和遗漏，不把单页成功推广为任意OCR/公式质量。
- 预期结果：用受控扫描样本核对预定可读文字及位置质量，独立于文本PDF；不把一页可读样本推广成任意扫描/OCR/公式保真保证。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/边界。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；22项断言；本轮真实MinerU解析终态；返回可用于文本RAG的结构块；[本轮证据](artifacts/rag-repair-20261113-scanfinal/sesrag-rag-repair-20261113-scanfinal-real-formats/real-formats/REAL_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format4.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_005"></a>

#### REAL_005：真实XLSX表格解析

- 用例编号：`REAL_005`
- 对应测试点：`TQ-RAG-REAL-005`：真实XLSX表格解析。验证目标：新Excel表格值可用于文本RAG。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，XLSX原件只读且不执行公式。
- 测试数据要求：固定表头、行列值及可见正文预标。
- 测试流程：
  1. 正式上传并读取安全归一化产物。
  2. 逐项对表头/值/结构，缺sheet/cell坐标明确，保留实际缺项。
- 预期结果：实际云端XLSX输出的表头/行列文本和值经安全归一化后可核对；缺sheet/cell坐标明示，不执行公式/宏或承诺排版。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/infrastructure/rag/html_tables.py`](../../backend/infrastructure/rag/html_tables.py)：安全表格文本化；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；18项断言；本轮真实MinerU解析终态；表格样本保留表格结构；[本轮证据](artifacts/rag-repair-20261113-real5/sesrag-rag-repair-20261113-real5-real-formats/real-formats/REAL_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format5.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_006"></a>

#### REAL_006：真实XLS表格解析

- 用例编号：`REAL_006`
- 对应测试点：`TQ-RAG-REAL-006`：真实XLS表格解析。验证目标：旧Excel表格有独立真实证据。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，合法OLE XLS来源许可明确。
- 测试数据要求：真实XLS中的固定表头/数值及原源区域预标。
- 测试流程：
  1. 独立请求真实解析并逐项对照。
  2. 缺失/失败单列，不能用XLSX返回代替，公式结果仅核可见文本。
- 预期结果：固定合法OLE XLS逐项核正文/表格值与结构，不能用XLSX成功或Mock响应替代；记录真实遗漏及来源可定位范围。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`backend/infrastructure/rag/html_tables.py`](../../backend/infrastructure/rag/html_tables.py)：安全表格文本化；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/兼容。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；20项断言；本轮真实MinerU解析终态；表格样本保留表格结构；[本轮证据](artifacts/rag-repair-20261113-real6/sesrag-rag-repair-20261113-real6-real-formats/real-formats/REAL_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format6.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_007"></a>

#### REAL_007：真实PPTX幻灯文本解析

- 用例编号：`REAL_007`
- 对应测试点：`TQ-RAG-REAL-007`：真实PPTX幻灯文本解析。验证目标：PPTX主要内容结构能被抽取。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，PPTX固定多页子集及预标清单。
- 测试数据要求：已冻结6页样本的标题/正文/表格及所在页对照。
- 测试流程：
  1. 正式上传真实解析。
  2. 逐项标遗漏/可靠坐标，无slide映射只标规范块，不将6页当20题评测集。
- 预期结果：对冻结多页PPTX的标题/正文/表格子集逐项对照，缺幻灯片号标规范块；不从派生分页猜原页，不把六页子集当20题标注集。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/功能。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；17项断言；本轮真实MinerU解析终态；返回可用于文本RAG的结构块；[本轮证据](artifacts/rag-repair-20261113-real7/sesrag-rag-repair-20261113-real7-real-formats/real-formats/REAL_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format7.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_008"></a>

#### REAL_008：真实PPT幻灯文本解析

- 用例编号：`REAL_008`
- 对应测试点：`TQ-RAG-REAL-008`：真实PPT幻灯文本解析。验证目标：旧PPT独立完成真实解析。
- 需求来源：RAG-010、RAG-015、RAG-043。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-formats；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，许可与原件二进制身份已核对。
- 测试数据要求：固定PPT真实样本和预标标题/正文。
- 测试流程：
  1. 独立正式解析并核内容结构。
  2. 缺slide号明示，失败不改名PPTX/本地转换或借其他格式通过。
- 预期结果：使用许可来源清楚的真实二进制PPT，返回正文/标题结构与抽样原件对应，缺精确位置明示；失败不假借PPTX结果。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/infrastructure/rag/mineru_outputs.py`](../../backend/infrastructure/rag/mineru_outputs.py)：normalize_package；[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源。
- 优先级：P0。
- 用例类型：真实/兼容。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；19项断言；本轮真实MinerU解析终态；返回可用于文本RAG的结构块；[本轮证据](artifacts/rag-repair-20261113-real8/sesrag-rag-repair-20261113-real8-real-formats/real-formats/REAL_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format8.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

<a id="real_009"></a>

#### REAL_009：真实生成请求与流式返回

- 用例编号：`REAL_009`
- 对应测试点：`TQ-RAG-REAL-009`：真实生成请求与流式返回。验证目标：正常ModelProfile确实发出并收到回答。
- 需求来源：RAG-032、RAG-037、RAG-044、NFR-012。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例：真实生成配置及生成计数适用性齐备；分能力准入已完成，所选生成能力自身计数仍须满足。
- 测试数据要求：小型合成事实/问题、RAG关闭、明确输出token和费用预算。
- 测试流程：
  1. 经正式Thread/Run发真实生成，核非空SSE增量、唯一assistant及终态。
  2. 不能只直调供应商SDK。
- 预期结果：通过正式Run选择真实生成Profile，固定小型合成事实/问题，验证实际非空SSE增量及唯一持久assistant，不用Mock或只调用供应商SDK作证。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/infrastructure/providers/openai_compatible.py`](../../backend/infrastructure/providers/openai_compatible.py)：stream_request；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/session_runs.py`](../../backend/application/session_runs.py)：insert_run/create_session_message/create_related_run。
- 优先级：P0。
- 用例类型：真实/接口。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：额度已用生产生成适配器的真实短请求核实恢复并收到非空回答；正式Run仍缺gpt-6.1-sol网关实际tokenizer/消息模板适用依据及独立校准，准入守卫正确阻止。适配器连通性不冒充Thread/Run/Worker通过。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="real_010"></a>

#### REAL_010：四类真实能力业务身份链

- 用例编号：`REAL_010`
- 对应测试点：`TQ-RAG-REAL-010`：四类真实能力业务身份链。验证目标：一次新鲜业务所有证据来自同轮真实链。
- 需求来源：RAG-018、RAG-026、RAG-030、RAG-032、RAG-043、RAG-044。
- 当前可验证性：暂不可完整验证·B（真实输入计数依据及校准未完成，生产守卫阻断）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：四能力计数/配置/授权均有效、真实闭环前提已退出。
- 测试数据要求：同轮单获准办公源、真实文档/query向量及rerank/生成Profile、预算。
- 测试流程：
  1. 一条正式业务完成MinerU→真实入库→PG召回→真实rerank→真实流式回答。
  2. 逐身份联接View/ContextEvidence/Citation，无Mock/历史拼接。
- 预期结果：计数门禁退出后关联同轮MinerU→真实文档/query向量→PG候选→真实rerank→真实生成→Context/Citation，四能力均无替身/旁路，不能拼历史探针宣称闭环。
- 暂缓标记：真实计数依据/校准未完成，当前正式生产守卫阻断；解除条件见第3节B项，不使用替身凑成真实通过。
- 代码依据／主要定位：[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/workers/handlers/index_build_handler.py`](../../backend/workers/handlers/index_build_handler.py)：process_index_build_task；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/rag_run_execution.py`](../../backend/application/rag_run_execution.py)：execute_run_retrieval/工具结算；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan。
- 优先级：P0。
- 用例类型：真实/一致性。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：四能力全链需真实Embedding/rerank及生成计数条件共同满足；DNS和额度已解除，剩余计数前提不能伪造。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="real_011"></a>

#### REAL_011：真实服务限额和未知成本

- 用例编号：`REAL_011`
- 对应测试点：`TQ-RAG-REAL-011`：真实服务限额和未知成本。验证目标：真实计划有界且不盲目重提。
- 需求来源：RAG-007、RAG-013、RAG-014、RAG-044、NFR-001、NFR-004。
- 当前可验证性：条件可验证·R（本机存在真实路径；按所选能力核验配置／授权／计数／预算，实际条件见结果）。
- 后续归属：real-business；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；条件真实用例，全部危险限额负例先在local计划工具验证。
- 测试数据要求：获准文件hash、调用预算/时限、模拟未知提交，无授权副本。
- 测试流程：
  1. 先验证预算/hash拒绝的零外发。
  2. 获准后才执行最小真实正例，达到限额停止新逻辑操作，未知提交不自动整轮重跑。
- 预期结果：逐文件hash/授权/预算冻结，只允许合成/获准文件；达到预算/时限停止新请求，未知提交不重跑整轮，本地清理不冒称云撤回或费用归零。
- 受限标记：执行前逐能力核验真实前提，并先处理第3节当前Real全能力准入耦合；本次不预填实际结果。
- 代码依据／主要定位：[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/infrastructure/rag/mineru_client.py`](../../backend/infrastructure/rag/mineru_client.py)：MinerUClient.submit/upload/poll/download；[`backend/tools/check_rag_providers.py`](../../backend/tools/check_rag_providers.py)：真实协议探针，不等于业务验收；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P0。
- 用例类型：真实/风险。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；6项断言；拒绝原因与约定一致；实际获准原件hash仍匹配；[本轮证据](artifacts/rag-repair-20261113-real8/sesrag-rag-repair-20261113-real8-real-formats/real-business/REAL_011.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format8.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：是（八份独立计划的预算断言通过；不证明云端退款）。

<a id="real_012"></a>

#### REAL_012：真实结果证据分层

- 用例编号：`REAL_012`
- 对应测试点：`TQ-RAG-REAL-012`：真实结果证据分层。验证目标：协议成功与业务完成不混写。
- 需求来源：RAG-043、RAG-044、NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本机可验证证据协议，不要求现在真实请求；真实内容子项后续随真实用例核验。
- 测试数据要求：独立构造当前真实/Mock/protocol/历史证据清单及能力身份。
- 测试流程：
  1. 运行报告审核按来源/轮次/transport分层。
  2. 拒绝把HTTP200/旧样本/小探针标为当前真实闭环，真实未执行不得生成passed。
- 预期结果：分别保存每格式/模型的安全结果、配置身份、输入计数及范围；直调protocol_probe、HTTP200、旧8产物或小样本顺序不代表当前业务/效果通过。
- 补充判定／证据边界：本机可先校验证据分类规则；没有当轮真实调用时，报告中对应真实结果必须not_run/blocked。真实材料真实性仍须随相关真实用例审查，合成清单自测不代替它。
- 代码依据／主要定位：[`tests/fixtures/rag-v3/provider-observations.json`](../../tests/fixtures/rag-v3/provider-observations.json)：历史协议安全摘要，仅作参考；[`backend/tools/check_rag_providers.py`](../../backend/tools/check_rag_providers.py)：真实协议探针，不等于业务验收；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P0。
- 用例类型：质量/可追溯。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；2项断言；质量检查本身不是供应商真实测试；拒绝原因与约定一致；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/REAL_012.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Real -Categories real-formats,real-business -AllowRealRequests -LivePlan ./tests/sesrag-rag-mineru-test/runtime-inputs/live-plan-repair-format12.json -RunId rag-repro-real-<新唯一后缀>`；先确认新操作预算及授权，未知旧作业不重提。
- 测试结果是否稳定出现：否（本轮该格式仅一次新逻辑操作，未为稳定性重复收费提交）。

### 4.16 EVAL：效果、规模性能与度量

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-EVAL-001` | [EVAL_001：标注集完整性](#eval_001) | L | performance／local |
| `TQ-RAG-EVAL-002` | [EVAL_002：dense召回率判定](#eval_002) | D | real-evaluation／real |
| `TQ-RAG-EVAL-003` | [EVAL_003：真实rerank收益对照](#eval_003) | D | real-evaluation／real |
| `TQ-RAG-EVAL-004` | [EVAL_004：跨片段答案增强收益](#eval_004) | L | retrieval／local |
| `TQ-RAG-EVAL-005` | [EVAL_005：预算不足效果影响](#eval_005) | L | retrieval／local |
| `TQ-RAG-EVAL-006` | [EVAL_006：真实无答案回答表现](#eval_006) | D | real-evaluation／real |
| `TQ-RAG-EVAL-007` | [EVAL_007：真实PG规模性能](#eval_007) | L | performance／local |
| `TQ-RAG-EVAL-008` | [EVAL_008：全链阶段计时分解](#eval_008) | L | performance／local |

<a id="eval_001"></a>

#### EVAL_001：标注集完整性

- 用例编号：`EVAL_001`
- 对应测试点：`TQ-RAG-EVAL-001`：标注集完整性。验证目标：评测样本足够且来源明确。
- 需求来源：RAG-045、NFR-007。
- 当前可验证性：本机可验证·L（原源20+5标注及原源投影区间可独立核实；效果仍依赖真实链）。
- 后续归属：performance；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；读取冻结source-annotations.json及固定原件，独立核验source/projection hash及Unicode半开区间；不消费MinerU响应或检索结果生成答案。
- 测试数据要求：20有答案+5无答案、九格式/中英/跨片段/预标干扰、来源范围及hash。
- 测试流程：
  1. 逐题人工核原件并冻结答案范围。
  2. 校验唯一ID/计数/格式覆盖，关联当轮View而非硬编码Chunk ID，缺集保持暂缓。
- 预期结果：冻结至少20有答案+5无答案、九格式/中英/跨片段及语义干扰，相关答案用原源或规范文本范围标注，不硬编码随机Chunk ID；当前标注材料未齐。
- 补充判定／证据边界：全部25题必须形成独立问句/预期/答案或无答案依据；固定源文件数、文档事实条数以及六页PPTX均不等于题数。数据校验器通过还需人工审核标注本身正确。
- 当前入口：performance-tests.py::eval001执行原源审计；不更改绑定产物evaluation.schema.json，不伪造artifact hash。EVAL_002/003/006保持暂缓。
- 代码依据／主要定位：[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P1。
- 用例类型：数据/质量。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；4项断言；独立问句及答案/无答案依据共25题；原源标注没有伪造云产物hash；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-performance/performance/EVAL_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories performance -RunId rag-repro-performance-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="eval_002"></a>

#### EVAL_002：dense召回率判定

- 用例编号：`EVAL_002`
- 对应测试点：`TQ-RAG-EVAL-002`：dense召回率判定。验证目标：按完整样本计算平均Recall@20。
- 需求来源：RAG-023、RAG-045。
- 当前可验证性：暂不可完整验证·D（标注/度量数据缺口，真实效果还依赖计数门禁与真实产物）。
- 后续归属：real-evaluation；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：完整标注集、真实办公入库及真实query计数门禁均已退出。
- 测试数据要求：固定View，20有答案题相关范围映射到本轮Chunk，dense candidate_k=20。
- 测试流程：
  1. 每题取Top20计算相关Chunk召回比例。
  2. 按题平均并另算有相关命中题比例，保存各题/各格式失败，平均目标≥0.85。
- 预期结果：每题相关标注Chunk召回比例后按题平均，目标≥0.85，并报告有相关命中题比例；逐格式/全部失败一起报告，少一部分真实办公只能部分评测。
- 补充判定／证据边界：Recall@20(q)=Top20与相关Chunk集合交集数/该题全部相关Chunk数，按20道有答案题平均；无答案题不塞进此分母。范围跨多个Chunk时预先冻结映射规则，不在看到结果后改标注。
- 暂缓标记：标注/数据工具缺口及关联真实前提尚未满足；解除条件见第3节D项，格式检查通过不能代替完整评测。
- 代码依据／主要定位：[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径。
- 优先级：P1。
- 用例类型：质量。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：独立20+5原源标注及指标工程已准备并核验；真实Embedding计数未完成，未产生九格式真实空间的排名，不可计算真实Recall@20。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="eval_003"></a>

#### EVAL_003：真实rerank收益对照

- 用例编号：`EVAL_003`
- 对应测试点：`TQ-RAG-EVAL-003`：真实rerank收益对照。验证目标：同候选语料下可证明真实排序作用。
- 需求来源：RAG-026、RAG-027、RAG-045。
- 当前可验证性：暂不可完整验证·D（标注/度量数据缺口，真实效果还依赖计数门禁与真实产物）。
- 后续归属：real-evaluation；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：标注/真实rerank及输入计数前提满足。
- 测试数据要求：同query/视图/dense候选，预标语义干扰及可能下降样本。
- 测试流程：
  1. 分别dense和真实rerank取Top5。
  2. 计算MRR@5/Recall@5和排名差，至少一预标题提升，保留下降且整体MRR下降不推荐默认开启。
- 预期结果：固定批次/过滤/模型，dense与真实rerank比较MRR@5/Recall@5，至少一个预标干扰样本提升相关名次，保留下降题；整体MRR下降不能推荐默认开启。
- 补充判定／证据边界：MRR@5每题取首个相关名次r≤5的1/r，无相关为0；Recall@5取前5覆盖的相关Chunk比例。两策略同题同dense候选比较，不能只展示提升样本。
- 暂缓标记：标注/数据工具缺口及关联真实前提尚未满足；解除条件见第3节D项，格式检查通过不能代替完整评测。
- 代码依据／主要定位：[`backend/infrastructure/providers/bailian_rerank.py`](../../backend/infrastructure/providers/bailian_rerank.py)：BailianRerank.rank；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径。
- 优先级：P1。
- 用例类型：质量。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：独立标注、固定候选指标对照已准备；真实Embedding/rerank计数未完成，没有同候选真实dense/rerank排名对照。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="eval_004"></a>

#### EVAL_004：跨片段答案增强收益

- 用例编号：`EVAL_004`
- 对应测试点：`TQ-RAG-EVAL-004`：跨片段答案增强收益。验证目标：增强使原缺失答案范围进入Context。
- 需求来源：RAG-029、RAG-030、RAG-045。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；local可用本例合成事实，无需全25题。
- 测试数据要求：答案两个必要条件分在相邻Chunk，半径0与1/2。
- 测试流程：
  1. 固定命中和预算执行两组真实Run编排。
  2. 核实际Context补齐必要答案范围，不只对照Bundle字符数。
- 预期结果：合成确定性答案跨Chunk，半径0与增强对照时实际Context包含补全答案范围；不能仅以文本字符变多或诊断Bundle变长判增强有效。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context。
- 优先级：P1。
- 用例类型：功能/质量。
- 是否适合自动化：是。
- 实际测试结果：通过；31项断言；正式任务完整成功；增强实际进入Context并补齐两个必要条件；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/EVAL_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="eval_005"></a>

#### EVAL_005：预算不足效果影响

- 用例编号：`EVAL_005`
- 对应测试点：`TQ-RAG-EVAL-005`：预算不足效果影响。验证目标：效果评估不能忽略最终舍弃证据。
- 需求来源：RAG-030、RAG-045。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：retrieval；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本例相关证据已召回且答案支持范围预标。
- 测试数据要求：足够/不足增强预算、足够/不足生成窗口四组。
- 测试流程：
  1. 记录各阶段保留/删减及实际模型输入。
  2. 最终引用只支持仍选入范围，召回成功但被移除不算回答可支持。
- 预期结果：对照相关证据已召回但被增强/生成预算移除的场景，记录删减原因与最终范围，回答引用不能覆盖舍弃部分；不将召回成功等同最终回答可支持。
- 代码依据／主要定位：[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`backend/application/context.py`](../../backend/application/context.py)：check_mandatory_budget/plan_context；[`backend/application/task_execution.py`](../../backend/application/task_execution.py)：complete_run/取消与结算。
- 优先级：P0。
- 用例类型：边界/质量。
- 是否适合自动化：是。
- 实际测试结果：通过；54项断言；正式任务完整成功；任一预算移除后不得冒称最终范围仍支持第二条件；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-retrieval/retrieval/EVAL_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories retrieval -RunId rag-repro-retrieval-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="eval_006"></a>

#### EVAL_006：真实无答案回答表现

- 用例编号：`EVAL_006`
- 对应测试点：`TQ-RAG-EVAL-006`：真实无答案回答表现。验证目标：无答案不编造证据或当基础设施故障。
- 需求来源：RAG-028、RAG-030、RAG-045。
- 当前可验证性：暂不可完整验证·D（标注/度量数据缺口，真实效果还依赖计数门禁与真实产物）。
- 后续归属：real-evaluation；通道：real。
- 前置条件：遵守第2节隔离/独立性约定；暂缓：至少5题预标无答案及真实链前提满足。
- 测试数据要求：范围内无答案但有语义近邻的5题、独立服务失败对照。
- 测试流程：
  1. 逐题真实检索生成。
  2. 核无关引用/无证据断言并报告，不能强求零候选，也不能将服务失败算无答案正确。
- 预期结果：标注5个无答案查询，报告无关近邻/错误引用/生成行为；不要求向量零命中，不以服务失败当无答案正确；当前需标注与真实链前置。
- 暂缓标记：标注/数据工具缺口及关联真实前提尚未满足；解除条件见第3节D项，格式检查通过不能代替完整评测。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/application/session_execution.py`](../../backend/application/session_execution.py)：process_session_run/publish_plan；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径。
- 优先级：P1。
- 用例类型：质量/风险。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：暂不可验证：五道无答案金标已核验；真实生成和检索计数前提未齐，未执行正式五题真实回答，不能把服务失败判无答案正确。 详见[计数资料复核](计数资料复核记录.md)及[缺陷报告](缺陷报告.md)。
- 复现步骤：
- 测试结果是否稳定出现：

<a id="eval_007"></a>

#### EVAL_007：真实PG规模性能

- 用例编号：`EVAL_007`
- 对应测试点：`TQ-RAG-EVAL-007`：真实PG规模性能。验证目标：10k Chunk条件下数据库召回达目标。
- 需求来源：RAG-023、NFR-008。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：performance；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；真实PG专属数据库和有界性能夹具，记录Docker分配。
- 测试数据要求：≥10000合法有效Chunk、固定query，100次预热后至少100次测量。
- 测试流程：
  1. 独立装载性能数据并标夹具注入。
  2. 使用生产SQL测DB调用计时，输出全样本/p50/p95/错误率/峰值，p95目标≤1秒，排除外部请求延迟。
- 预期结果：固定≥10000合法有效Chunk，先执行100次预热查询，再测量至少100次查询并保存原始样本；记录PG/扩展/硬件/维度/SQL及p50/p95/错误率/峰值，DB召回p95目标≤1秒，外部延迟排除。
- 补充判定／证据边界：测量点包围实际PG生产召回，不混入query embedding/网络排队。p50/p95用排序样本nearest-rank（ceil(p*n)-1索引）并报告样本数、每次耗时、并发度及错误率；有错误也必须报告，不能删除慢样本。
- 代码依据／主要定位：[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/application/rag_capacity.py`](../../backend/application/rag_capacity.py)：reserve_storage/storage_usage；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P1。
- 用例类型：性能/容量。
- 是否适合自动化：是。
- 实际测试结果：通过；640项断言；正式任务完整成功；测量生产范围物化及数据库Top-K SQL；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-performance/performance/EVAL_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories performance -RunId rag-repro-performance-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="eval_008"></a>

#### EVAL_008：全链阶段计时分解

- 用例编号：`EVAL_008`
- 对应测试点：`TQ-RAG-EVAL-008`：全链阶段计时分解。验证目标：外部等待不被计为数据库开销。
- 需求来源：RAG-031、NFR-005、NFR-008。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：performance；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；local计量工具可先核，真实阶段统计待真实门禁退出。
- 测试数据要求：解析/document embedding/query embedding/DB/rerank/增强/生成各阶段。
- 测试流程：
  1. 用已知延迟验证计量器边界。
  2. 按产品字段和工程观察分别记录整链，缺duration显式说明，Mock计时不作真实SLO证明。
- 预期结果：分别记录解析/文档向量/query向量/DB/rerank/增强/生成及整链统计，缺产品duration注明观察工具来源；Mock仅验证计量器不证明真实服务SLO。
- 补充判定／证据边界：本机部分只验证计量器和已实现阶段；完整真实计时依赖真实前提，产品日志缺字段仍由MIN_022登记，不能借工程补测将产品观测缺口销账。
- 代码依据／主要定位：[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/workers/runtime.py`](../../backend/workers/runtime.py)：WorkerRuntime.run_once/run_forever/_dispatch；[`backend/tools/check_rag_providers.py`](../../backend/tools/check_rag_providers.py)：真实协议探针，不等于业务验收；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P1。
- 用例类型：性能/可观测。
- 是否适合自动化：是。
- 实际测试结果：通过；87项断言；正式任务完整成功；阶段结构可单独对照；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-performance/performance/EVAL_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories performance -RunId rag-repro-performance-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.17 QLT：契约、安全与工程质量

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-QLT-001` | [QLT_001：公开数据秘密泄漏检查](#qlt_001) | L | quality／local |
| `TQ-RAG-QLT-002` | [QLT_002：真实凭据来源隔离](#qlt_002) | L | quality／local |
| `TQ-RAG-QLT-003` | [QLT_003：响应及事件严格契约](#qlt_003) | L | quality／local |
| `TQ-RAG-QLT-004` | [QLT_004：前后端类型无漂移](#qlt_004) | L | quality／local |
| `TQ-RAG-QLT-005` | [QLT_005：前端事件边界拒绝](#qlt_005) | K | quality／local |
| `TQ-RAG-QLT-006` | [QLT_006：模块替换与分层边界](#qlt_006) | L | quality／local |
| `TQ-RAG-QLT-007` | [QLT_007：确定性夹具可复现](#qlt_007) | L | quality／local |
| `TQ-RAG-QLT-008` | [QLT_008：中文可诊断性完整](#qlt_008) | L | quality／local |
| `TQ-RAG-QLT-009` | [QLT_009：非目标入口边界](#qlt_009) | L | quality／local |
| `TQ-RAG-QLT-010` | [QLT_010：外部RAG依赖与全局健康分离](#qlt_010) | L | quality／local |

<a id="qlt_001"></a>

#### QLT_001：公开数据秘密泄漏检查

- 用例编号：`QLT_001`
- 对应测试点：`TQ-RAG-QLT-001`：公开数据秘密泄漏检查。验证目标：所有公开投影无Secret和私有能力。
- 需求来源：RAG-005、RAG-011、RAG-031、RAG-035、NFR-001、NFR-005。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；仅使用可识别dummy凭据及合成Prompt，不读取真实Secret。
- 测试数据要求：假Key/Bearer/签名参数/宿主路径/上游异常全文哨兵。
- 测试流程：
  1. 覆盖成功/失败API/Event/Message/Snapshot/DOM/默认日志/报告。
  2. 逐投影扫描，必要证据身份保留而敏感哨兵不得出现。
- 预期结果：用可识别假Secret覆盖API/Event/Message/Snapshot/前端/默认日志/报告，扫描Key/Authorization/签名URL/宿主路径，错误不回显上游正文或完整Prompt。
- 代码依据／主要定位：[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影；[`backend/api/routes/v3/sessions.py`](../../backend/api/routes/v3/sessions.py)：消息/Run/Event/SSE/取消/重试端点；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle；[`backend/infrastructure/events/journal.py`](../../backend/infrastructure/events/journal.py)：append_event/list_events。
- 优先级：P0。
- 用例类型：安全。
- 是否适合自动化：是。
- 实际测试结果：通过；22项断言；正式任务完整成功；API/事件/快照无敏感URL/Authorization/宿主路径；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_002"></a>

#### QLT_002：真实凭据来源隔离

- 用例编号：`QLT_002`
- 对应测试点：`TQ-RAG-QLT-002`：真实凭据来源隔离。验证目标：测试配置不进入仓库或构建层。
- 需求来源：RAG-044、NFR-001。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮私有配置生成工具与Compose结构可核。
- 测试数据要求：显式env alias、缺某Key、假秘密文档/宿主开发.env哨兵。
- 测试流程：
  1. 生成local/real有效配置但不外发。
  2. 检查只复制明确输入、不扫描Secret文档、不隐式复用，不进模板/build args/镜像history。
- 预期结果：运行Key仅服务端明确别名注入，无自动扫描秘密文档/隐式共用，API/Worker所需存在性可检查；真实值不进JSON模板、build args或镜像历史。
- 补充判定／证据边界：只用本例临时目录中的合成秘密文件及显式private输入做对照，不读取或改写真实docs/secret、根.env或前轮配置；静态检查入口来源和实际生成配置共同作证。
- 代码依据／主要定位：[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/application/model_profiles.py`](../../backend/application/model_profiles.py)：validate_profile_config/resolve_secret；[`backend/config.py`](../../backend/config.py)：Settings；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P0。
- 用例类型：安全/配置。
- 是否适合自动化：是。
- 实际测试结果：通过；4项断言；真实配置来自显式私有输入及授权；JSON模板无真实Key形态；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_003"></a>

#### QLT_003：响应及事件严格契约

- 用例编号：`QLT_003`
- 对应测试点：`TQ-RAG-QLT-003`：响应及事件严格契约。验证目标：版本与未知字段校验一致。
- 需求来源：RAG-032、RAG-037、RAG-038、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；本轮契约文件与DTO加载可用。
- 测试数据要求：每种v3资源及三代Event/Citation/tool合法样本，缺字段/额外字段/版本错配。
- 测试流程：
  1. 以正式JSON Schema/DTO分别验证。
  2. 正例通过负例拒绝，Citation数组与声明版本一致，不把TS类型当运行时校验。
- 预期结果：v3资源、三代Event联合、Citation声明版本与数组分支、工具输入输出按JSON Schema/DTO正负验证；不把生成TS类型当运行期完整验证。
- 代码依据／主要定位：[`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py)：wire_catalog/export --check；[`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py)：三代事件载荷；[`backend/api/schemas/v3/sessions.py`](../../backend/api/schemas/v3/sessions.py)：Message/CitationV2/RunDetail；[`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py)：RAG_BINDING/SearchToolInput/SearchToolResult。
- 优先级：P0。
- 用例类型：契约。
- 是否适合自动化：是。
- 实际测试结果：通过；51项断言；正式任务完整成功；工具任意参数拒绝；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_004"></a>

#### QLT_004：前后端类型无漂移

- 用例编号：`QLT_004`
- 对应测试点：`TQ-RAG-QLT-004`：前后端类型无漂移。验证目标：消费方类型来自相同契约。
- 需求来源：RAG-038、NFR-006、NFR-010。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；后续脚本需挂载本轮只读契约/前端源码或受控宿主执行，不能写产品文件。
- 测试数据要求：export_rag_contracts --check、frontend check:api/typecheck/lint/build。
- 测试流程：
  1. 分别实际运行并保留退出/输出。
  2. 导出类型无漂移，任何检查未执行单列，不复用旧PRD历史数字。
- 预期结果：export_rag_contracts --check与前端check:api一致，禁手写额外字段兜底；类型/lint/build实际结果分别记录，不能沿用历史26项。
- 代码依据／主要定位：[`backend/tools/export_rag_contracts.py`](../../backend/tools/export_rag_contracts.py)：wire_catalog/export --check；[`frontend/scripts/generate-api-types.mjs`](../../frontend/scripts/generate-api-types.mjs)：契约生成与--check。
- 优先级：P1。
- 用例类型：契约/工程。
- 是否适合自动化：是。
- 实际测试结果：通过；1项断言；契约/生成类型/类型检查/Lint/构建全部通过；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_005"></a>

#### QLT_005：前端事件边界拒绝

- 用例编号：`QLT_005`
- 对应测试点：`TQ-RAG-QLT-005`：前端事件边界拒绝。验证目标：畸形事件不污染事实投影。
- 需求来源：RAG-037、NFR-010。
- 当前可验证性：本机可验证·K（已知实现/契约差异，按完整目标断言，可能失败）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；已知运行期事件严格性差异，真实浏览器/边界解析函数可用。
- 测试数据要求：未知version/type、seq为0/负数/非整数、错代身份、缺/错嵌套工具字段。
- 测试流程：
  1. 先按正式JSON Schema标注每份负载是否合法。
  2. 从受控SSE和解析函数分别送入负载。
  3. 核对客户端是否拒绝且不追加，必要字段检查通过不足以声明所有嵌套校验完整。
- 预期结果：未知版本/type/非法seq/执行身份/工具载荷拒绝，不继续追加到当前Run；当前只验证必要字段，须核与完整契约差异，不自动断言所有嵌套字段都严格校验。
- 代码依据／主要定位：[`frontend/src/events/rag-event-stream.ts`](../../frontend/src/events/rag-event-stream.ts)：parseV3Event/replayV3Events/openV3RunStream；[`backend/api/schemas/v3/events.py`](../../backend/api/schemas/v3/events.py)：三代事件载荷；[`frontend/src/stores/run.ts`](../../frontend/src/stores/run.ts)：事件/事实恢复/去重。
- 优先级：P0。
- 用例类型：契约/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；2项断言；真实浏览器有具体拒绝断言；严格契约非法事件在前端全部拒绝；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_006"></a>

#### QLT_006：模块替换与分层边界

- 用例编号：`QLT_006`
- 对应测试点：`TQ-RAG-QLT-006`：模块替换与分层边界。验证目标：厂商协议不散落到业务调用方。
- 需求来源：NFR-006、NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；五个Port及对应应用组合根、源码只读。
- 测试数据要求：ParseGateway/ArtifactNormalizer/EmbeddingPortV2/VectorSearchPort/RerankPort替身及最小共同DTO。
- 测试流程：
  1. 检查领域/路由/Vue导入边界。
  2. 替身运行同契约正负例，切片/增强按独立函数边界记录，不能夸成热插拔Port。
- 预期结果：检查领域/路由/Vue不解释MinerU厂商字段，5个Port可用替身验证共同契约；切片/增强为独立函数非热切换Port，实际能力如实记录。
- 代码依据／主要定位：[`backend/domain/ports/rag.py`](../../backend/domain/ports/rag.py)：5个Protocol边界；[`backend/infrastructure/providers/rag_registry.py`](../../backend/infrastructure/providers/rag_registry.py)：embedding_from_profile/rerank_from_profile；[`backend/application/parse_jobs.py`](../../backend/application/parse_jobs.py)：advance_parse_job；[`backend/application/retrieval.py`](../../backend/application/retrieval.py)：execute_retrieval/create_diagnostic/read_bundle。
- 优先级：P1。
- 用例类型：架构/可测试性。
- 是否适合自动化：是（操作/计算可自动化，依据或内容质量需人工复核）。
- 实际测试结果：通过；16项断言；领域层不依赖厂商/ORM/HTTP；受控替身按共同契约装配完整链；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_007"></a>

#### QLT_007：确定性夹具可复现

- 用例编号：`QLT_007`
- 对应测试点：`TQ-RAG-QLT-007`：确定性夹具可复现。验证目标：固定输入向量视图得到稳定判定。
- 需求来源：NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；相同只读fixture/hash/Profile、独立case数据。
- 测试数据要求：确定向量/固定受控排序、同断点故障，两次独立业务身份。
- 测试流程：
  1. 重复准备与执行并对照语料身份映射/分数/范围/安全码。
  2. 随机资源UUID不要求相等，真实输出不要求逐字相同。
- 预期结果：manifest/hash/配置/向量固定时候选与拼接身份/范围可对照，受控故障可在同断点注入；真实云/生成只要求业务不变量而非逐字恒定。
- 代码依据／主要定位：[`tests/fixtures/rag-v3/manifest.json`](../../tests/fixtures/rag-v3/manifest.json)：10份源文件hash/许可来源；[`backend/infrastructure/rag/vector_search.py`](../../backend/infrastructure/rag/vector_search.py)：VectorSearch.search；[`backend/application/evidence_assembly.py`](../../backend/application/evidence_assembly.py)：assemble_evidence；[`docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md`](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md)：环境/正式接入依据；环境与可验证分类脚本已接入，执行情况见实际结果。
- 优先级：P1。
- 用例类型：可测试性。
- 是否适合自动化：是。
- 实际测试结果：通过；21项断言；正式任务完整成功；拼接内容范围可重复；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_008"></a>

#### QLT_008：中文可诊断性完整

- 用例编号：`QLT_008`
- 对应测试点：`TQ-RAG-QLT-008`：中文可诊断性完整。验证目标：主要错误和操作限制能指导下一步。
- 需求来源：RAG-031、RAG-040、NFR-011。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；安全错误码表和中文展示入口。
- 测试数据要求：已映射错误、未知安全码、empty/blocked/failed/degraded/not_run。
- 测试流程：
  1. 逐码驱动API/页面/报告。
  2. 中文原因与状态可区分，未知码安全兜底而非成功，不回显原堆栈。
- 预期结果：对安全码和未知阶段核中文说明，区分空/受限/失败/降级/未执行，不展示原始堆栈；未映射错误码保安全兜底但不能假称成功。
- 代码依据／主要定位：[`frontend/src/components/rag-labels.ts`](../../frontend/src/components/rag-labels.ts)：中文标签映射；[`backend/application/rag_sessions.py`](../../backend/application/rag_sessions.py)：upgrade_snapshot/generation_snapshot/run_detail；[`backend/application/index_builds.py`](../../backend/application/index_builds.py)：upload_document/start_build/rebuild_document/cancel_build。
- 优先级：P1。
- 用例类型：可用性。
- 是否适合自动化：是。
- 实际测试结果：通过；10项断言；错误响应有中文说明；未知阶段保安全值而非成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_009"></a>

#### QLT_009：非目标入口边界

- 用例编号：`QLT_009`
- 对应测试点：`TQ-RAG-QLT-009`：非目标入口边界。验证目标：未承诺能力不被误认为已交付。
- 需求来源：RAG-032、RAG-033、NFR-006。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；只读核正式路由/工具定义/UI及非目标请求。
- 测试数据要求：任意工具/跨库/硬删/ANN/Hybrid/Office回退/公式计算。
- 测试流程：
  1. 探测公开入口和契约。
  2. 未提供能力明确不支持，避免半成品危险入口。
  3. 不要求实现PRD非目标。
- 预期结果：不因RAG工具扩展而出现任意工具执行、跨库检索、用户硬删除、Office本地回退/转换、ANN/混合检索或公式执行的半成品入口；记录后续路线，不强制实现这些非目标。
- 代码依据／主要定位：[`backend/domain/rag_snapshot.py`](../../backend/domain/rag_snapshot.py)：RAG_BINDING/SearchToolInput/SearchToolResult；[`backend/domain/rag.py`](../../backend/domain/rag.py)：ParseRequest/EmbeddingSpace/RetrievalPolicy；[`backend/api/routes/v3/resources.py`](../../backend/api/routes/v3/resources.py)：资源端点/游标/公开投影；[`docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md`](../../docs/prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)：产品目标/验收口径。
- 优先级：P2。
- 用例类型：边界/风险。
- 是否适合自动化：是。
- 实际测试结果：通过；14项断言；正式任务完整成功；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

<a id="qlt_010"></a>

#### QLT_010：外部RAG依赖与全局健康分离

- 用例编号：`QLT_010`
- 对应测试点：`TQ-RAG-QLT-010`：外部RAG依赖与全局健康分离。验证目标：云服务缺失不使文本应用无法启动。
- 需求来源：RAG-004、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：quality；通道：local。
- 前置条件：遵守第2节隔离/独立性约定；独立配置组，不注入真实Key。
- 测试数据要求：MinerU关闭/不可用、真实模型缺配置、Mock生成及本地文本正例。
- 测试流程：
  1. 启动本轮API/Worker检查基础健康。
  2. 上传txt/md和RAG关闭Run可用路径，办公能力明确不可用，ready不代表外部可用。
- 预期结果：未启用或不可用MinerU/真实模型时PG/API/Worker仍按原健康契约可启动，txt/md本地及关闭RAG的可用生成路径可用；不把健康ready当外部能力可用。
- 代码依据／主要定位：[`backend/config.py`](../../backend/config.py)：Settings；[`backend/application/rag_profiles.py`](../../backend/application/rag_profiles.py)：import_profiles/resolve_profile/profile_reason；[`docker-compose.yml`](../../docker-compose.yml)：当前产品Compose。
- 优先级：P1。
- 用例类型：可用性/异常。
- 是否适合自动化：是。
- 实际测试结果：通过；28项断言；外部关闭不影响存活；办公能力明确不可用；[本轮证据](artifacts/rag-repair-20261113-local2/sesrag-rag-repair-20261113-local2-quality/quality/QLT_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Selected -Categories quality -RunId rag-repro-quality-<新唯一后缀>`；同分类一起执行，修复代码后重新构建。
- 测试结果是否稳定出现：否（修复后本轮一次完整回归；不与不同源码的历史两轮拼接稳定性）。

### 4.18 ENV：临时环境与清理工程

| 测试点 | 用例／标题 | 可验证性 | 后续归属 |
| --- | --- | --- | --- |
| `TQ-RAG-ENV-001` | [ENV_001：正式suite隔离](#env_001) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-002` | [ENV_002：技术就绪顺序](#env_002) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-003` | [ENV_003：local装配不误外发](#env_003) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-004` | [ENV_004：real覆盖清除假服务](#env_004) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-005` | [ENV_005：分类接入覆盖门禁](#env_005) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-006` | [ENV_006：源码与镜像同源性](#env_006) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-007` | [ENV_007：报告与证据真实性](#env_007) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-008` | [ENV_008：正常退出零残留](#env_008) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-009` | [ENV_009：失败中断恢复清理](#env_009) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |
| `TQ-RAG-ENV-010` | [ENV_010：运行数据增长边界](#env_010) | L | 环境工程（主入口/工程自测，独立于产品分类）／environment |

<a id="env_001"></a>

#### ENV_001：正式suite隔离

- 用例编号：`ENV_001`
- 对应测试点：`TQ-RAG-ENV-001`：正式suite隔离。验证目标：本轮环境不接触开发资源。
- 需求来源：RAG-046、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；当前独立Compose/主入口已实施，使用全新run_id。
- 测试数据要求：根.env/旧suite私有输入哨兵、独占project/卷、随机loopback端口。
- 测试流程：
  1. 从Environment入口部署。
  2. 核effective-compose安全投影及内部同源HTTP/SSE，未读开发配置，无固定业务端口。
- 预期结果：按TEST-003独立project/卷/loopback动态端口/私有env启动，根.env和旧suite不读，API/SSE同源；当前正式工程已存在，按本轮原始证据独立验证，不以开发probe替代。
- 补充判定／证据边界：配置哨兵只放本例临时测试根/清洁子进程环境，结合实际Compose参数和生成配置核验；不修改或读取用户真实根.env、前轮suite私有文件，也不把未发现同名哨兵当作独立证明。
- 代码依据／主要定位：[`helpers/orchestrate.py`](helpers/orchestrate.py)：compose_args/inspect_config；[`compose/docker-compose.rag-test.yml`](compose/docker-compose.rag-test.yml)：专属服务/卷/动态端口；[`helpers/prepare_runtime.py`](helpers/prepare_runtime.py)：prepare。
- 优先级：P0。
- 用例类型：工程/部署。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；真实独立Compose/同源代理/SSE安全结构校核；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_001.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_002"></a>

#### ENV_002：技术就绪顺序

- 用例编号：`ENV_002`
- 对应测试点：`TQ-RAG-ENV-002`：技术就绪顺序。验证目标：环境ready有真实依据。
- 需求来源：RAG-046、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；专属空PG，正式迁移与Profile工具已接入。
- 测试数据要求：PG/Redis/迁移/profile-init/API/Worker/frontend时序。
- 测试流程：
  1. 启动环境并核各容器退出/health和PG revision0010/pgvector/Profile。
  2. Worker必须真实ready，不能仅HTTP200。
- 预期结果：PG/Redis→分段迁移/Profile导入→API/Worker→前端，核revision0010/扩展/退出码/Worker事实；HTTP200不是整个环境通过。
- 代码依据／主要定位：[`helpers/environment_probe.py`](helpers/environment_probe.py)：main；[`helpers/initialize.py`](helpers/initialize.py)：main；[`compose/docker-compose.rag-test.yml`](compose/docker-compose.rag-test.yml)：depends_on。
- 优先级：P0。
- 用例类型：工程/部署。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；实际迁移/Profile/PG扩展/Worker就绪事实；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_002.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_003"></a>

#### ENV_003：local装配不误外发

- 用例编号：`ENV_003`
- 对应测试点：`TQ-RAG-ENV-003`：local装配不误外发。验证目标：受控传输不会带真Key访问公网。
- 需求来源：RAG-046、NFR-001、NFR-002、NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；local组合根和control已实现，工厂守卫保持。
- 测试数据要求：dummy Key/internal网络、生产MinerUClient+受控transport、unverified真实模板。
- 测试流程：
  1. 核API/Worker装配身份及实际受控计数。
  2. 合法local路径零公网，真实未校准模板仍拒绝，DNS/TLS证明范围另列。
- 预期结果：独立harness/dummy Key/内部网络，无生产私网开关；真实SafeHTTP与MockTransport证明范围分开，所有工厂绑定自检，不能改verified状态绕守卫。
- 代码依据／主要定位：[`harness/local_entry.py`](harness/local_entry.py)：install；[`harness/transport_fixtures.py`](harness/transport_fixtures.py)：生产守卫与受控工厂；[`compose/docker-compose.rag-test.yml`](compose/docker-compose.rag-test.yml)：internal网络。
- 优先级：P0。
- 用例类型：工程/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；真实local装配自检/受控传输与安全守卫负例；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_003.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_004"></a>

#### ENV_004：real覆盖清除假服务

- 用例编号：`ENV_004`
- 对应测试点：`TQ-RAG-ENV-004`：real覆盖清除假服务。验证目标：完整真实通道不残留替身。
- 需求来源：RAG-043、RAG-044、RAG-046、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；真实Compose覆盖可在不外发下渲染。
- 测试数据要求：local/real合并后入口/挂载/env/网络，缺授权/计数/key的私有计划。
- 测试流程：
  1. 核real清掉harness/control/dummy且使用生产入口。
  2. 前提不足blocked，零业务请求，不以local替换real。
- 预期结果：Compose覆盖显式移除harness/控制面/dummy环境，四能力身份核对及真实counter门禁，缺前提blocked无外发，不自动跑Mock并宣布real通过。
- 代码依据／主要定位：[`helpers/preflight.py`](helpers/preflight.py)：real_gate；[`helpers/orchestrate.py`](helpers/orchestrate.py)：inspect_config；[`compose/docker-compose.rag-real.yml`](compose/docker-compose.rag-real.yml)：覆盖清除。
- 优先级：P0。
- 用例类型：工程/安全。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；real覆盖清除本地装配自测及无授权真实拒绝；没有供应商请求；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_004.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_005"></a>

#### ENV_005：分类接入覆盖门禁

- 用例编号：`ENV_005`
- 对应测试点：`TQ-RAG-ENV-005`：分类接入覆盖门禁。验证目标：planned和空报告不能通过。
- 需求来源：RAG-046、NFR-007。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；context/result/manifest Schema及planned初始清单。
- 测试数据要求：错run/lane、空/重/缺case、坏hash、退出0无结果、Selected/All。
- 测试流程：
  1. 用工程自测隔离负载验证严格拒绝。
  2. planned不能通过，Environment产品not_run，Selected只统计声明范围。
- 预期结果：每分类ready/明确case列表/Schema一致，错run或lane/重复缺case/退出0无证据应工程错误，Environment产品not_run，Selected只认所选范围。
- 补充判定／证据边界：后续manifest仍planned时只做运行器工程自测，不将合成ENGINE_编号或环境用例注册成产品用例来制造All通过。
- 代码依据／主要定位：[`helpers/protocol.py`](helpers/protocol.py)：manifest/validate_result；[`schemas/result.schema.json`](schemas/result.schema.json)；[`helpers/selftest_runner.py`](helpers/selftest_runner.py)：RunnerTests。
- 优先级：P0。
- 用例类型：工程/结果。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；错身份/漏case/证据hash/planned门禁实际工程负例；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_005.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_006"></a>

#### ENV_006：源码与镜像同源性

- 用例编号：`ENV_006`
- 对应测试点：`TQ-RAG-ENV-006`：源码与镜像同源性。验证目标：两轮结果来自同一冻结构建。
- 需求来源：RAG-046、NFR-007、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；一份可归档镜像及明确源码指纹。
- 测试数据要求：dirty/依赖/fixture/config、归档hash；篡改源/包负例。
- 测试流程：
  1. 第一轮保存内容，第二轮FrozenBuild实际load。
  2. 比较两轮指纹，篡改必须拒绝，不能只凭镜像ID无内容宣称同源。
- 预期结果：保存源码含dirty/依赖/fixture/config指纹和镜像归档hash，第二轮显式复用；源变化或只留镜像ID无内容时不得称同源复验。
- 代码依据／主要定位：[`helpers/preflight.py`](helpers/preflight.py)：source_fingerprint；[`helpers/builds.py`](helpers/builds.py)：images/freeze；[`helpers/orchestrate.py`](helpers/orchestrate.py)：main。
- 优先级：P1。
- 用例类型：工程/复现。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；第二轮实际从归档加载且源码/归档hash核验；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_006.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_007"></a>

#### ENV_007：报告与证据真实性

- 用例编号：`ENV_007`
- 对应测试点：`TQ-RAG-ENV-007`：报告与证据真实性。验证目标：分类结果与原始观察可追溯。
- 需求来源：RAG-031、RAG-046、NFR-001、NFR-005。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；结果Schema/脱敏/限额校验可调用。
- 测试数据要求：中文case结果、证据相对路径/hash、Secret哨兵、超限/缺失日志。
- 测试流程：
  1. 生成合成正负报告并校验。
  2. 正常可追溯，缺证据/截断/泄漏明确工程失败，状态分列不互换。
- 预期结果：中文逐case结果、相对证据/hash、模式/受限/失败/未运行分列，日志截断或缺失影响判定不能passed；报告不含原始Key/能力URL/全文Prompt。
- 代码依据／主要定位：[`helpers/evidence.py`](helpers/evidence.py)：redact/scan/index；[`helpers/protocol.py`](helpers/protocol.py)：validate_result；[`helpers/orchestrate.py`](helpers/orchestrate.py)：summarize。
- 优先级：P0。
- 用例类型：工程/可观测。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；坏Schema/路径/hash/泄漏负例与真实采证完整性；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_007.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_008"></a>

#### ENV_008：正常退出零残留

- 用例编号：`ENV_008`
- 对应测试点：`TQ-RAG-ENV-008`：正常退出零残留。验证目标：本轮业务资源全部释放。
- 需求来源：RAG-046、NFR-009、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；宿主生命周期助手有本轮所有权账本，无Docker socket给tools。
- 测试数据要求：正常运行产生的容器/网络/PG上传产物卷/tag/子进程/runtime/tmp。
- 测试流程：
  1. 正常采证down后独立查询所有资源及既有基线。
  2. 本轮全空且旧资源不变，报告/缓存和云端边界明确。
- 预期结果：down --volumes后独立查容器/网络/业务卷/专有tag/子进程/runtime/tmp为空，开发资源不误删；报告/共享缓存和云端可能继续单列，不运行全局prune。
- 代码依据／主要定位：[`helpers/cleanup.py`](helpers/cleanup.py)：cleanup/discover/validate_resource；[`helpers/orchestrate.py`](helpers/orchestrate.py)：finish；[`helpers/common.py`](helpers/common.py)：进程身份/Job回收。
- 优先级：P0。
- 用例类型：工程/生命周期。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；正常结束独立资源复查：容器/卷/网络/tag/runtime/tmp为空，既有资源未丢失；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_008.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_009"></a>

#### ENV_009：失败中断恢复清理

- 用例编号：`ENV_009`
- 对应测试点：`TQ-RAG-ENV-009`：失败中断恢复清理。验证目标：启动失败及硬杀后仍可安全回收。
- 需求来源：RAG-046、NFR-009、NFR-012。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；宿主专属工程演练驱动，可按账本停本轮进程。
- 测试数据要求：真实启动失败、技术子进程失败/超时、主进程强停、错误Engine/丢账本。
- 测试流程：
  1. 逐种演练后同RunId Cleanup两次。
  2. 核成功幂等及拒猜删负例。
  3. 保留首次失败，真实Ctrl+C未执行须另列。
- 预期结果：真实Docker启动半途失败/分类超时/主进程强停后同run Cleanup依可信账本和ID标签回收，重复清理幂等；Engine不可查不假报空，全账本丢失不猜删。
- 补充判定／证据边界：硬杀后恢复通过不代表Ctrl+C/SIGTERM每种信号均已验证；使用真实进程/容器为正向证据，错误Engine/缺账本拒删可用不产生真实删除副作用的工程负例。
- 代码依据／主要定位：[`helpers/lifecycle_exercise.py`](helpers/lifecycle_exercise.py)：main/invoke；[`helpers/cleanup.py`](helpers/cleanup.py)：cleanup；[`helpers/common.py`](helpers/common.py)：process_token/terminate_tree。
- 优先级：P0。
- 用例类型：工程/恢复。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；真实Docker启动失败/子进程失败/超时/主进程强停+重复Cleanup；未用模拟函数替代；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_009.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

<a id="env_010"></a>

#### ENV_010：运行数据增长边界

- 用例编号：`ENV_010`
- 对应测试点：`TQ-RAG-ENV-010`：运行数据增长边界。验证目标：重复执行不累积私有大文件。
- 需求来源：RAG-046、NFR-004、NFR-009。
- 当前可验证性：本机可验证·L（独立环境已准备；执行情况见本条实际结果）。
- 后续归属：环境工程（主入口/工程自测，独立于产品分类）；通道：environment。
- 前置条件：遵守第2节隔离/独立性约定；临时数据和明确保留缓存都有路径/软门限。
- 测试数据要求：两轮上传/ZIP/scratch、runtime-inputs、报告2GiB/轮200MiB、冻结缓存10GiB。
- 测试流程：
  1. 记录执行前后占用与独立残留。
  2. 业务数据随轮销毁，保留项单列且超限阻止新运行，不删唯一恢复账本或全局prune。
- 预期结果：运行凭据/上传/ZIP/scratch随本轮释放，原始runtime-inputs与明确工具/冻结缓存/脱敏报告分列占用和软门限；不删唯一恢复材料或静默清历史证据凑“干净”。
- 代码依据／主要定位：[`helpers/cleanup.py`](helpers/cleanup.py)：erase_run_directory；[`helpers/builds.py`](helpers/builds.py)：freeze预算；[`helpers/evidence.py`](helpers/evidence.py)：scan限额；[`helpers/orchestrate.py`](helpers/orchestrate.py)：artifacts软限。
- 优先级：P1。
- 用例类型：工程/容量。
- 是否适合自动化：是。
- 实际测试结果：通过；工程项断言；运行时源/凭据/scratch已释放；报告/工具/冻结缓存/原始runtime-inputs保留，软门限自测；[本轮证据](artifacts/rag-repair-20261113-engineering-environment-cases/ENV_010.json)。
- 复现步骤：`pwsh -NoProfile -File ./tests/sesrag-rag-mineru-test/run-rag-tests.ps1 -Mode Environment -LifecycleAudit -RunId rag-repro-env-<新唯一后缀>`。
- 测试结果是否稳定出现：是（本轮完整生命周期审计含同源两次正常环境及实际故障恢复；不计产品通过率）。

## 5. 产品需求到用例的覆盖关系

下表由逐点需求关联汇总，仅表示设计覆盖；每项通过仍需对应全部验收内容的真实执行证据。R/B/D受限项不因本地用例通过被免除。完整点号见第4节索引及原矩阵。

| 需求 | 对应测试用例 | 受限／差异提示 |
| --- | --- | --- |
| RAG-001 | [CAT_001](#cat_001)、[CAT_002](#cat_002)、[CAT_003](#cat_003)、[CAT_004](#cat_004)、[CAT_005](#cat_005)、[CAT_006](#cat_006)、[CAT_018](#cat_018)、[CMP_006](#cmp_006) | 局部实测：通过8／未通过0／受限0；完整需求判定见测试报告 |
| RAG-002 | [CAT_007](#cat_007)、[CAT_008](#cat_008)、[CAT_009](#cat_009)、[VEC_004](#vec_004)、[VEC_006](#vec_006)、[VEC_008](#vec_008)、[RET_008](#ret_008)、[CMP_007](#cmp_007)、[CMP_008](#cmp_008) | 局部实测：通过7／未通过2／受限0；完整需求判定见测试报告 |
| RAG-003 | [INP_001](#inp_001)、[INP_002](#inp_002)、[INP_003](#inp_003)、[INP_004](#inp_004)、[INP_005](#inp_005)、[INP_006](#inp_006)、[INP_007](#inp_007)、[INP_008](#inp_008) | 局部实测：通过8／未通过0／受限0；完整需求判定见测试报告 |
| RAG-004 | [CAT_015](#cat_015)、[INP_009](#inp_009)、[INP_010](#inp_010)、[INP_011](#inp_011)、[INP_012](#inp_012)、[QLT_010](#qlt_010) | 局部实测：通过6／未通过0／受限0；完整需求判定见测试报告 |
| RAG-005 | [CAT_013](#cat_013)、[CAT_018](#cat_018)、[INP_014](#inp_014)、[RET_002](#ret_002)、[QLT_001](#qlt_001) | 局部实测：通过5／未通过0／受限0；完整需求判定见测试报告 |
| RAG-006 | [INP_013](#inp_013)、[INP_015](#inp_015)、[INP_016](#inp_016)、[INP_017](#inp_017)、[INP_018](#inp_018)、[INP_021](#inp_021)、[UI_006](#ui_006)、[UI_007](#ui_007) | 局部实测：通过7／未通过1／受限0；完整需求判定见测试报告 |
| RAG-007 | [MIN_001](#min_001)、[MIN_002](#min_002)、[MIN_003](#min_003)、[REAL_011](#real_011) | 局部实测：通过4／未通过0／受限0；完整需求判定见测试报告 |
| RAG-008 | [MIN_004](#min_004)、[MIN_005](#min_005)、[MIN_022](#min_022)、[IDX_002](#idx_002)、[UI_005](#ui_005) | 局部实测：通过4／未通过1／受限0；完整需求判定见测试报告 |
| RAG-009 | [CAT_010](#cat_010)、[CAT_015](#cat_015)、[INP_011](#inp_011)、[INP_013](#inp_013)、[INP_020](#inp_020)、[MIN_007](#min_007)、[MIN_019](#min_019)、[IDX_001](#idx_001) | 局部实测：通过8／未通过0／受限0；完整需求判定见测试报告 |
| RAG-010 | [INP_008](#inp_008)、[MIN_003](#min_003)、[MIN_014](#min_014)、[PAR_007](#par_007)、[PAR_008](#par_008)、[PAR_009](#par_009)、[PAR_012](#par_012)、[PAR_013](#par_013)、[PAR_014](#par_014)、[REAL_001](#real_001)、[REAL_002](#real_002)、[REAL_003](#real_003)、[REAL_004](#real_004)、[REAL_005](#real_005)、[REAL_006](#real_006)、[REAL_007](#real_007)、[REAL_008](#real_008) | 局部实测：通过8／未通过4／受限5；完整需求判定见测试报告 |
| RAG-011 | [MIN_020](#min_020)、[MIN_021](#min_021)、[PAR_001](#par_001)、[PAR_002](#par_002)、[PAR_003](#par_003)、[PAR_004](#par_004)、[PAR_005](#par_005)、[PAR_006](#par_006)、[CHK_010](#chk_010)、[LIF_007](#lif_007)、[QLT_001](#qlt_001) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| RAG-012 | [MIN_006](#min_006)、[MIN_007](#min_007)、[MIN_008](#min_008)、[MIN_009](#min_009)、[MIN_010](#min_010)、[MIN_012](#min_012)、[MIN_018](#min_018)、[MIN_019](#min_019)、[MIN_020](#min_020)、[IDX_006](#idx_006)、[IDX_008](#idx_008)、[EXE_016](#exe_016)、[EXE_017](#exe_017) | 局部实测：通过13／未通过0／受限0；完整需求判定见测试报告 |
| RAG-013 | [INP_012](#inp_012)、[INP_021](#inp_021)、[MIN_006](#min_006)、[MIN_008](#min_008)、[MIN_011](#min_011)、[MIN_012](#min_012)、[MIN_013](#min_013)、[MIN_014](#min_014)、[MIN_021](#min_021)、[LIF_010](#lif_010)、[REAL_011](#real_011) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| RAG-014 | [MIN_011](#min_011)、[MIN_015](#min_015)、[MIN_016](#min_016)、[MIN_017](#min_017)、[MIN_018](#min_018)、[UI_018](#ui_018)、[LIF_007](#lif_007)、[REAL_011](#real_011) | 局部实测：通过8／未通过0／受限0；完整需求判定见测试报告 |
| RAG-015 | [INP_005](#inp_005)、[INP_009](#inp_009)、[PAR_008](#par_008)、[PAR_009](#par_009)、[PAR_010](#par_010)、[PAR_011](#par_011)、[CMP_003](#cmp_003)、[REAL_001](#real_001)、[REAL_002](#real_002)、[REAL_003](#real_003)、[REAL_004](#real_004)、[REAL_005](#real_005)、[REAL_006](#real_006)、[REAL_007](#real_007)、[REAL_008](#real_008) | 局部实测：通过6／未通过4／受限5；完整需求判定见测试报告 |
| RAG-016 | [CAT_014](#cat_014)、[CAT_016](#cat_016)、[PAR_011](#par_011)、[CHK_001](#chk_001)、[CHK_002](#chk_002)、[CHK_003](#chk_003)、[CHK_004](#chk_004)、[CHK_005](#chk_005)、[CHK_006](#chk_006)、[CHK_010](#chk_010)、[VEC_005](#vec_005) | 局部实测：通过9／未通过1／受限1；完整需求判定见测试报告 |
| RAG-017 | [PAR_010](#par_010)、[PAR_012](#par_012)、[PAR_013](#par_013)、[CHK_007](#chk_007)、[CHK_008](#chk_008)、[CHK_009](#chk_009)、[IDX_001](#idx_001)、[IDX_003](#idx_003)、[IDX_008](#idx_008)、[IDX_009](#idx_009)、[ENH_004](#enh_004) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| RAG-018 | [CAT_008](#cat_008)、[CAT_009](#cat_009)、[CAT_010](#cat_010)、[CAT_013](#cat_013)、[CAT_014](#cat_014)、[CAT_016](#cat_016)、[VEC_001](#vec_001)、[VEC_006](#vec_006)、[VEC_008](#vec_008)、[VEC_009](#vec_009)、[VEC_010](#vec_010)、[CMP_007](#cmp_007)、[REAL_010](#real_010) | 局部实测：通过8／未通过1／受限4；完整需求判定见测试报告 |
| RAG-019 | [VEC_002](#vec_002)、[VEC_003](#vec_003)、[VEC_004](#vec_004)、[VEC_005](#vec_005)、[VEC_007](#vec_007)、[VEC_008](#vec_008)、[IDX_004](#idx_004) | 局部实测：通过6／未通过1／受限0；完整需求判定见测试报告 |
| RAG-020 | [INP_019](#inp_019)、[MIN_005](#min_005)、[MIN_013](#min_013)、[MIN_017](#min_017)、[CHK_009](#chk_009)、[VEC_007](#vec_007)、[IDX_001](#idx_001)、[IDX_002](#idx_002)、[IDX_003](#idx_003)、[IDX_004](#idx_004)、[IDX_005](#idx_005)、[IDX_006](#idx_006)、[IDX_007](#idx_007)、[IDX_008](#idx_008)、[IDX_009](#idx_009)、[IDX_010](#idx_010)、[IDX_011](#idx_011)、[LIF_001](#lif_001)、[LIF_006](#lif_006) | 局部实测：通过19／未通过0／受限0；完整需求判定见测试报告 |
| RAG-021 | [CAT_006](#cat_006)、[INP_015](#inp_015)、[IDX_011](#idx_011)、[ENH_006](#enh_006)、[ENH_007](#enh_007)、[ENH_009](#enh_009)、[CMP_003](#cmp_003)、[CMP_009](#cmp_009)、[CMP_012](#cmp_012)、[LIF_003](#lif_003)、[LIF_004](#lif_004)、[LIF_005](#lif_005)、[LIF_006](#lif_006)、[LIF_008](#lif_008)、[LIF_009](#lif_009)、[LIF_010](#lif_010) | 局部实测：通过16／未通过0／受限0；完整需求判定见测试报告 |
| RAG-022 | [INP_010](#inp_010)、[INP_017](#inp_017)、[INP_018](#inp_018)、[INP_019](#inp_019)、[INP_020](#inp_020)、[INP_021](#inp_021)、[IDX_005](#idx_005)、[UI_007](#ui_007)、[LIF_010](#lif_010) | 局部实测：通过8／未通过1／受限0；完整需求判定见测试报告 |
| RAG-023 | [VEC_010](#vec_010)、[RET_007](#ret_007)、[RET_008](#ret_008)、[RET_009](#ret_009)、[EVAL_002](#eval_002)、[EVAL_007](#eval_007) | 局部实测：通过4／未通过0／受限2；完整需求判定见测试报告 |
| RAG-024 | [IDX_002](#idx_002)、[IDX_010](#idx_010)、[RET_001](#ret_001)、[RET_002](#ret_002)、[RET_003](#ret_003)、[RET_004](#ret_004)、[RET_005](#ret_005)、[RET_006](#ret_006)、[RET_008](#ret_008)、[RET_023](#ret_023)、[ENH_001](#enh_001) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| RAG-025 | [RET_006](#ret_006)、[RET_009](#ret_009)、[RET_010](#ret_010)、[RET_023](#ret_023)、[UI_008](#ui_008) | 局部实测：通过5／未通过0／受限0；完整需求判定见测试报告 |
| RAG-026 | [CAT_010](#cat_010)、[CAT_013](#cat_013)、[CAT_014](#cat_014)、[CAT_016](#cat_016)、[RET_012](#ret_012)、[RET_013](#ret_013)、[RET_014](#ret_014)、[RET_018](#ret_018)、[REAL_010](#real_010)、[EVAL_003](#eval_003) | 局部实测：通过6／未通过0／受限4；完整需求判定见测试报告 |
| RAG-027 | [RET_011](#ret_011)、[RET_012](#ret_012)、[RET_013](#ret_013)、[EVAL_003](#eval_003) | 局部实测：通过3／未通过0／受限1；完整需求判定见测试报告 |
| RAG-028 | [VEC_007](#vec_007)、[RET_005](#ret_005)、[RET_006](#ret_006)、[RET_015](#ret_015)、[RET_016](#ret_016)、[RET_017](#ret_017)、[RET_021](#ret_021)、[EVAL_006](#eval_006) | 局部实测：通过7／未通过0／受限1；完整需求判定见测试报告 |
| RAG-029 | [ENH_001](#enh_001)、[ENH_002](#enh_002)、[ENH_003](#enh_003)、[ENH_004](#enh_004)、[EVAL_004](#eval_004) | 局部实测：通过5／未通过0／受限0；完整需求判定见测试报告 |
| RAG-030 | [CAT_017](#cat_017)、[PAR_012](#par_012)、[PAR_013](#par_013)、[CHK_008](#chk_008)、[ENH_003](#enh_003)、[ENH_004](#enh_004)、[ENH_005](#enh_005)、[ENH_007](#enh_007)、[ENH_008](#enh_008)、[ENH_009](#enh_009)、[CTX_001](#ctx_001)、[CTX_002](#ctx_002)、[CTX_003](#ctx_003)、[CTX_005](#ctx_005)、[CTX_006](#ctx_006)、[CTX_007](#ctx_007)、[CTX_008](#ctx_008)、[REAL_010](#real_010)、[EVAL_004](#eval_004)、[EVAL_005](#eval_005)、[EVAL_006](#eval_006) | 局部实测：通过18／未通过1／受限2；完整需求判定见测试报告 |
| RAG-031 | [MIN_022](#min_022)、[RET_021](#ret_021)、[RET_022](#ret_022)、[CTX_001](#ctx_001)、[CTX_003](#ctx_003)、[CTX_009](#ctx_009)、[UI_009](#ui_009)、[EVAL_008](#eval_008)、[QLT_001](#qlt_001)、[QLT_008](#qlt_008)、[ENV_007](#env_007) | 局部实测：通过10／未通过1／受限0；完整需求判定见测试报告 |
| RAG-032 | [RET_001](#ret_001)、[RET_019](#ret_019)、[RET_021](#ret_021)、[EXE_001](#exe_001)、[EXE_003](#exe_003)、[EXE_004](#exe_004)、[REAL_009](#real_009)、[REAL_010](#real_010)、[QLT_003](#qlt_003)、[QLT_009](#qlt_009) | 局部实测：通过8／未通过0／受限2；完整需求判定见测试报告 |
| RAG-033 | [CAT_012](#cat_012)、[RET_003](#ret_003)、[RET_020](#ret_020)、[ENH_006](#enh_006)、[CTX_004](#ctx_004)、[EXE_004](#exe_004)、[QLT_009](#qlt_009) | 局部实测：通过7／未通过0／受限0；完整需求判定见测试报告 |
| RAG-034 | [RET_022](#ret_022)、[CTX_008](#ctx_008)、[CTX_009](#ctx_009)、[EXE_005](#exe_005)、[EXE_006](#exe_006)、[EXE_014](#exe_014)、[EXE_015](#exe_015)、[EXE_016](#exe_016) | 局部实测：通过8／未通过0／受限0；完整需求判定见测试报告 |
| RAG-035 | [CAT_010](#cat_010)、[CAT_011](#cat_011)、[CAT_012](#cat_012)、[IDX_010](#idx_010)、[RET_004](#ret_004)、[EXE_001](#exe_001)、[EXE_002](#exe_002)、[EXE_009](#exe_009)、[EXE_018](#exe_018)、[UI_010](#ui_010)、[QLT_001](#qlt_001) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| RAG-036 | [CAT_011](#cat_011)、[CAT_012](#cat_012)、[RET_004](#ret_004)、[RET_005](#ret_005)、[EXE_007](#exe_007)、[EXE_008](#exe_008)、[EXE_009](#exe_009)、[EXE_010](#exe_010)、[EXE_018](#exe_018) | 局部实测：通过9／未通过0／受限0；完整需求判定见测试报告 |
| RAG-037 | [CTX_005](#ctx_005)、[CTX_009](#ctx_009)、[EXE_011](#exe_011)、[EXE_012](#exe_012)、[EXE_013](#exe_013)、[EXE_014](#exe_014)、[EXE_015](#exe_015)、[EXE_019](#exe_019)、[UI_012](#ui_012)、[UI_017](#ui_017)、[REAL_009](#real_009)、[QLT_003](#qlt_003)、[QLT_005](#qlt_005) | 局部实测：通过11／未通过1／受限1；完整需求判定见测试报告 |
| RAG-038 | [EXE_010](#exe_010)、[CMP_001](#cmp_001)、[CMP_002](#cmp_002)、[CMP_003](#cmp_003)、[CMP_004](#cmp_004)、[CMP_005](#cmp_005)、[CMP_006](#cmp_006)、[CMP_007](#cmp_007)、[CMP_008](#cmp_008)、[CMP_009](#cmp_009)、[CMP_010](#cmp_010)、[CMP_011](#cmp_011)、[CMP_012](#cmp_012)、[CMP_013](#cmp_013)、[CMP_014](#cmp_014)、[QLT_003](#qlt_003)、[QLT_004](#qlt_004) | 局部实测：通过15／未通过2／受限0；完整需求判定见测试报告 |
| RAG-039 | [UI_001](#ui_001)、[UI_002](#ui_002)、[UI_003](#ui_003)、[UI_006](#ui_006) | 局部实测：通过4／未通过0／受限0；完整需求判定见测试报告 |
| RAG-040 | [IDX_005](#idx_005)、[IDX_009](#idx_009)、[UI_004](#ui_004)、[UI_005](#ui_005)、[UI_007](#ui_007)、[UI_011](#ui_011)、[UI_015](#ui_015)、[UI_016](#ui_016)、[UI_018](#ui_018)、[QLT_008](#qlt_008) | 局部实测：通过8／未通过2／受限0；完整需求判定见测试报告 |
| RAG-041 | [RET_019](#ret_019)、[RET_020](#ret_020)、[UI_008](#ui_008)、[UI_009](#ui_009)、[UI_010](#ui_010)、[UI_011](#ui_011)、[UI_015](#ui_015)、[LIF_008](#lif_008)、[LIF_009](#lif_009) | 局部实测：通过9／未通过0／受限0；完整需求判定见测试报告 |
| RAG-042 | [PAR_013](#par_013)、[ENH_008](#enh_008)、[ENH_009](#enh_009)、[CTX_006](#ctx_006)、[UI_010](#ui_010)、[UI_013](#ui_013)、[UI_014](#ui_014)、[UI_015](#ui_015)、[UI_016](#ui_016)、[CMP_013](#cmp_013) | 局部实测：通过7／未通过3／受限0；完整需求判定见测试报告 |
| RAG-043 | [CAT_015](#cat_015)、[INP_007](#inp_007)、[INP_009](#inp_009)、[PAR_010](#par_010)、[PAR_011](#par_011)、[REAL_001](#real_001)、[REAL_002](#real_002)、[REAL_003](#real_003)、[REAL_004](#real_004)、[REAL_005](#real_005)、[REAL_006](#real_006)、[REAL_007](#real_007)、[REAL_008](#real_008)、[REAL_010](#real_010)、[REAL_012](#real_012)、[ENV_004](#env_004) | 局部实测：通过7／未通过3／受限6；完整需求判定见测试报告 |
| RAG-044 | [CAT_014](#cat_014)、[CAT_016](#cat_016)、[CAT_017](#cat_017)、[VEC_009](#vec_009)、[VEC_010](#vec_010)、[RET_018](#ret_018)、[REAL_009](#real_009)、[REAL_010](#real_010)、[REAL_011](#real_011)、[REAL_012](#real_012)、[QLT_002](#qlt_002)、[ENV_004](#env_004) | 局部实测：通过6／未通过0／受限6；完整需求判定见测试报告 |
| RAG-045 | [CTX_007](#ctx_007)、[EVAL_001](#eval_001)、[EVAL_002](#eval_002)、[EVAL_003](#eval_003)、[EVAL_004](#eval_004)、[EVAL_005](#eval_005)、[EVAL_006](#eval_006) | 局部实测：通过3／未通过0／受限4；完整需求判定见测试报告 |
| RAG-046 | [LIF_001](#lif_001)、[LIF_004](#lif_004)、[LIF_005](#lif_005)、[ENV_001](#env_001)、[ENV_002](#env_002)、[ENV_003](#env_003)、[ENV_004](#env_004)、[ENV_005](#env_005)、[ENV_006](#env_006)、[ENV_007](#env_007)、[ENV_008](#env_008)、[ENV_009](#env_009)、[ENV_010](#env_010) | 局部实测：通过13／未通过0／受限0；完整需求判定见测试报告 |
| NFR-001 | [CAT_004](#cat_004)、[CAT_013](#cat_013)、[INP_010](#inp_010)、[INP_013](#inp_013)、[INP_016](#inp_016)、[MIN_002](#min_002)、[MIN_016](#min_016)、[MIN_020](#min_020)、[RET_017](#ret_017)、[ENH_006](#enh_006)、[EXE_002](#exe_002)、[UI_002](#ui_002)、[UI_017](#ui_017)、[REAL_011](#real_011)、[QLT_001](#qlt_001)、[QLT_002](#qlt_002)、[ENV_003](#env_003)、[ENV_007](#env_007) | 局部实测：通过18／未通过0／受限0；完整需求判定见测试报告 |
| NFR-002 | [INP_002](#inp_002)、[INP_004](#inp_004)、[INP_006](#inp_006)、[INP_007](#inp_007)、[MIN_002](#min_002)、[PAR_001](#par_001)、[PAR_002](#par_002)、[PAR_003](#par_003)、[PAR_005](#par_005)、[CTX_004](#ctx_004)、[UI_014](#ui_014)、[ENV_003](#env_003) | 局部实测：通过12／未通过0／受限0；完整需求判定见测试报告 |
| NFR-003 | [MIN_006](#min_006)、[MIN_017](#min_017)、[MIN_019](#min_019)、[CHK_009](#chk_009)、[IDX_003](#idx_003)、[IDX_006](#idx_006)、[IDX_007](#idx_007)、[IDX_011](#idx_011)、[CTX_005](#ctx_005)、[EXE_001](#exe_001)、[EXE_006](#exe_006)、[EXE_013](#exe_013)、[CMP_014](#cmp_014)、[LIF_006](#lif_006) | 局部实测：通过14／未通过0／受限0；完整需求判定见测试报告 |
| NFR-004 | [CAT_017](#cat_017)、[MIN_010](#min_010)、[MIN_011](#min_011)、[MIN_012](#min_012)、[MIN_021](#min_021)、[PAR_004](#par_004)、[PAR_006](#par_006)、[CHK_006](#chk_006)、[CHK_010](#chk_010)、[VEC_005](#vec_005)、[RET_014](#ret_014)、[RET_023](#ret_023)、[ENH_003](#enh_003)、[CTX_001](#ctx_001)、[EXE_011](#exe_011)、[EXE_016](#exe_016)、[EXE_017](#exe_017)、[EXE_019](#exe_019)、[UI_011](#ui_011)、[LIF_002](#lif_002)、[REAL_011](#real_011)、[ENV_010](#env_010) | 局部实测：通过22／未通过0／受限0；完整需求判定见测试报告 |
| NFR-005 | [MIN_022](#min_022)、[RET_022](#ret_022)、[EVAL_008](#eval_008)、[QLT_001](#qlt_001)、[ENV_007](#env_007) | 局部实测：通过4／未通过1／受限0；完整需求判定见测试报告 |
| NFR-006 | [EXE_004](#exe_004)、[QLT_004](#qlt_004)、[QLT_006](#qlt_006)、[QLT_009](#qlt_009) | 局部实测：通过4／未通过0／受限0；完整需求判定见测试报告 |
| NFR-007 | [RET_007](#ret_007)、[RET_009](#ret_009)、[REAL_012](#real_012)、[EVAL_001](#eval_001)、[QLT_006](#qlt_006)、[QLT_007](#qlt_007)、[ENV_003](#env_003)、[ENV_005](#env_005)、[ENV_006](#env_006) | 局部实测：通过8／未通过0／受限1；完整需求判定见测试报告 |
| NFR-008 | [RET_007](#ret_007)、[EXE_017](#exe_017)、[EVAL_007](#eval_007)、[EVAL_008](#eval_008) | 局部实测：通过4／未通过0／受限0；完整需求判定见测试报告 |
| NFR-009 | [LIF_001](#lif_001)、[LIF_002](#lif_002)、[LIF_003](#lif_003)、[LIF_004](#lif_004)、[LIF_005](#lif_005)、[LIF_006](#lif_006)、[LIF_007](#lif_007)、[LIF_008](#lif_008)、[ENV_008](#env_008)、[ENV_009](#env_009)、[ENV_010](#env_010) | 局部实测：通过11／未通过0／受限0；完整需求判定见测试报告 |
| NFR-010 | [EXE_011](#exe_011)、[CMP_001](#cmp_001)、[CMP_005](#cmp_005)、[CMP_006](#cmp_006)、[CMP_010](#cmp_010)、[CMP_011](#cmp_011)、[CMP_012](#cmp_012)、[CMP_013](#cmp_013)、[CMP_014](#cmp_014)、[LIF_009](#lif_009)、[QLT_003](#qlt_003)、[QLT_004](#qlt_004)、[QLT_005](#qlt_005) | 局部实测：通过11／未通过2／受限0；完整需求判定见测试报告 |
| NFR-011 | [CAT_013](#cat_013)、[CAT_018](#cat_018)、[ENH_008](#enh_008)、[UI_004](#ui_004)、[UI_005](#ui_005)、[UI_013](#ui_013)、[UI_015](#ui_015)、[UI_016](#ui_016)、[QLT_008](#qlt_008) | 局部实测：通过8／未通过1／受限0；完整需求判定见测试报告 |
| NFR-012 | [CAT_017](#cat_017)、[INP_009](#inp_009)、[INP_012](#inp_012)、[UI_003](#ui_003)、[CMP_010](#cmp_010)、[REAL_009](#real_009)、[QLT_010](#qlt_010)、[ENV_001](#env_001)、[ENV_002](#env_002)、[ENV_004](#env_004)、[ENV_006](#env_006)、[ENV_008](#env_008)、[ENV_009](#env_009) | 局部实测：通过12／未通过0／受限1；完整需求判定见测试报告 |

## 6. 设计阶段整体校审与接入记录（2026-11-11历史）

本节保留设计交付时的检查和文件清单；当前任务5～6执行状态以第7节及各例实际结果为准。

已逐点检查248个设计目标：ID与测试点一一对应、各例有独立前置/明确数据组/动作/可判断预期、代码定位和需求来源；序号连续且无重复，58项需求均有用例。L/K/R/B/D分别224/5/10/5/4，优先级P0/P1/P2分别193/54/1。239例可验证设计（含10例真实条件），9例明确暂缓，原环境E状态已按当前实现更新。编号仅用于设计覆盖，不是通过数。

校审重点包括：同Job未知提交不重提；等待与故障重试分开；候选不污染active；本地文本不外发；办公不回退；空间/owner/View前置过滤；原文query；actual ContextEvidence与Citation一致；增强截取与生成整Bundle取舍区分；SSE游标兼容规则；本轮独立旧库迁移；GC年龄起点/墓碑边界；真实与Mock证据分层；真实入口全能力门禁耦合及未实施分类不产生假通过。

后续先按[specific_test_script/README](specific_test_script/README.md)准备分类脚本和每例必需夹具/只读挂载/宿主故障协调，核验脚本结果覆盖全部声明case，再把manifest对应项改ready；此为设计交付时的历史状态；当前manifest及脚本接入状态见README。按Selected排错、本机同源两轮、真实各能力/格式与效果分别执行。每例填写真实结果/实际命令/稳定性；未执行或暂缓有明确原因，不复制历史Environment或开发probe结果。

本次只执行文档/代码只读核对、结构/链接/映射与空结果字段校验；没有启动环境、执行产品用例、运行前后端全量质量门禁、调用真实服务或读取Key。机械校审材料在本机忽略目录data/rag-implementation/test-case-design-20261111/，不属于正式产品测试报告。不自动提交或推送。

### 6.1 本任务文件变动与校核

| 文件 | 本次变动 |
| --- | --- |
| [test-cases.md](test-cases.md) | 新增248例详细设计、逐点/逐需求覆盖、受限项、接入与判定边界 |
| [目录README](README.md)、[接入计划](test-plan.md) | 修改用例导航、当前状态、后续脚本和准入准备顺序 |
| [测试点矩阵](测试点设计与需求覆盖矩阵.md) | 保留248点及目标，ENV10点E转L、补工程依据，历史/当前状态分开 |
| [根README](../../README.md)、[测试文档目录](../../docs/test/README.md) | 修改本轮用例入口与完成状态导航 |
| [TEST-003](../../docs/test/003-SesRAG-RAG检索增强与MinerU接入-test-plan.md) | 同步F阶段用例设计已完成、脚本待接入及Real准入衔接；保留环境历史证据 |

用户任务说明已有修改予以保留，本任务不改写。上述共新增1份、修改6份正式文档；辅助整理/审计材料仅在忽略的data目录，不是具体自动测试脚本。

实际文档校核：`python data/rag-implementation/test-case-design-20261111/audit.py`（本机一次性辅助）检查ID/字段/顺序/双向需求映射/状态/链接/空执行字段/manifest未ready；`git diff --check -- README.md docs/test/ tests/sesrag-rag-mineru-test/`检查本次文档差异格式。两者均通过；另人工对照当前代码的固定格式路线、Profile守卫、PG排序、原子提交、SSE游标、GC时间和前端未知重建机制。不把这些文档检查写成产品用例通过。

## 7. 任务5～6执行与结果复核（2026-11-12）

248例采用结果：220通过、13未通过、15暂不可验证；本机219例最终同源两轮各209通过/10失败/0工程错误，清理通过。ENV十例复用任务4最终工程审计；真实格式已执行DOCX/DOC/文本PDF，其余5例因已证实CDN本机DNS异常受限，真实生成另缺计数依据且网关额度不足。完整PRD验收未通过。

最终本地配对为rag-task56-20261112-local2／local3，冻结归档`354e19f32512184fc1ee950a`；初始local1因日志观测需要修正仅作排错。真实三格式各一次新逻辑操作，不为稳定性重提未知云作业；REAL_011在三个计划下均通过。ENV证据来源及未单独实测Linux宿主／键盘Ctrl+C的边界明确保留。

248×3＝744个执行字段：实际结果248条，已测233例的复现及稳定性466条，合计714条已填写；15个受限项的复现／稳定性30条按要求留空。结果、证据hash、采用规则及完整需求映射见[采用结果索引](artifacts/rag-task56-20261112-results/adopted-results.json)和[测试报告](测试报告.md)。全部未通过／受限见[缺陷报告](缺陷报告.md)，不把本轮报告交付当作产品缺陷已修。

### 7.1 最终校审补测

EVAL_008原断言经最终校审发现不充分；已在performance-tests.py补8阶段透明观测、已知20ms延迟、每阶段≥3样本及三组聚合统计。最终采用perf2／perf3两次同源定向补测，均退出0、清理通过；原完整两轮的弱断言passed不作本例充分证据。产品代码不变，其余本机用例仍采用local2／local3。 源码／构建指纹和逐例证据见测试报告第8.3节及采用结果索引。
