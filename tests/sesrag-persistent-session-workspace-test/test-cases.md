# PRD-002 持久化会话与对话工作台测试用例

- **编号**：TEST-CASE-002
- **版本**：v1.3（任务5～6同源两轮正式All及104例执行记录回填）
- **状态**：8类104例已完成两轮正式执行，两轮各104通过、0失败/受限/未运行/工程错误，清理通过；归档呈现等补充问题另见缺陷报告，不宣称PRD零差异
- **日期**：2026-10-23
- **适用范围**：v0.2 / `sesrag_v0.2`；本机 Docker Compose 隔离环境
- **产品依据**：[PRD-002](../../docs/prd/002-SesRAG-持久化会话与对话工作台-PRD.md)
- **实施依据**：[会话工作台实施方案](../../docs/adr/002-sesrag-persistent-session-workspace-implementation-plan.md)（文件编号 002，正文沿用 ADR-003）
- **调研依据**：[实施结果调研](../../docs/pr/002-SesRAG-持久化会话与对话工作台-实施结果调研.md)、[实施摘要](../../docs/pr/002-SesRAG-持久化会话与对话工作台-PR.md)
- **验收工程依据**：[TEST-002](../../docs/test/002-SesRAG-持久化会话与对话工作台-test-plan.md)、[测试点矩阵](测试点设计与需求覆盖矩阵.md)、[分类接入计划](test-plan.md)、[脚本接入规范](specific_test_script/README.md)
- **接口依据**：[接口文档第 7 节](../../docs/接口文档.md)、`contracts/*_v2.json`、实际路由与 DTO
- **环境完成证据**：[环境实施与验证记录](环境实施与验证记录.md)；只证明环境闭环，不证明本文用例通过

## 1. 目的、边界与判定

本文将测试点转为自动化实现的流程、数据和判据，覆盖全部84个测试点及接口兼容、关键UI交互补充。任务1～2的工具前置见[准备核验记录](测试准备与总入口核验记录.md)，任务3～4的脚本与调试见[脚本校审记录](测试脚本实施与试跑校审记录.md)。任务5～6现已完成同源码/依赖/镜像的两轮All，并据真实逐例结果回填三个执行字段；汇总见[测试报告](测试报告.md)，实现差异与补充问题见[缺陷报告](缺陷报告.md)。下文“设计可验证状态”、前置和设计交接中的“待脚本/执行”等表述保留设计历史，不是当前执行结论；当前状态以本段、§1.3和每例执行字段为准。没有为通过而修改产品或降低预期。

不以 Mock/受控 Provider 证明真实模型效果、生产性能、知识库多租户隔离或隐藏思维。当前单 owner 场景的归属校验不是生产认证/RBAC。真实工具执行、跨会话语义记忆和知识库发布生命周期不在本轮范围。

### 1.1 可验证状态校准

原矩阵日期为 2026-10-21，定义了 65 个可验证点、19 个暂不可验证点。随后环境框架已实施；本文保留原始状态用于溯源，不继续把“没有 Compose/PG/浏览器”当作当前事实。

| 设计标记 | 当前含义 | 后续执行处理 |
| --- | --- | --- |
| V | 原矩阵可验证；当前已接入并完成两轮真实执行。 | 本批对应用例两轮通过；依据为逐例断言和证据，不是“可验证”标记本身。 |
| E | 原矩阵受限；ENV-01/02/03及QGAP-01/02前置已解除，故障/屏障/浏览器与质量编排已实施。 | 对应用例已在本机正式执行并取得两轮通过证据；保留原受限标记便于追溯，不继续按历史标记记blocked。 |
| B | 若执行前又发现未满足的环境或测试工程条件，重新按当次事实标受限。 | 当前没有仍为B的设计用例；发生阻碍须保留原因、影响和解除条件，不静默跳过、记通过或降级为仅源码检查。 |

原19个受限点目前均属于E：17个环境前置已备，TP-TEST-02/03对应的两项质量工具缺口在任务1～2中补齐。TP-MIG-01～04等原本同时注明SQLite可验、PG受限的点，现应按真实PG设计执行，不用SQLite结果冒充正式并发/迁移证据。各例的“原受限”信息只陈述矩阵历史，不是当前运行结论。

### 1.2 执行字段与证据边界

每个用例的“实际测试结果”“复现步骤”“测试结果是否稳定出现”现已依据§1.3两轮真实执行填写。设计流程仍是自动脚本的行为参考，不能替代执行记录；“稳定”仅表示两轮同源判定一致，不意味着随机身份、耗时和长期运行结果恒定。本批没有最终blocked用例；后续如条件不足，应只写真实受限原因，不补造结果。

报告区分 passed、failed、blocked、not_run及harness_error；缺依赖、缺脚本、取证失败和测量不足不得算通过。失败还须区分产品实现、测试工程/观测、外部环境及其他原因。一个用例含参数子场景时，每个子场景均需结果；任一必需子场景失败或阻塞，整例不能passed。QLT_005分类中间的等待清理状态已由总入口在最终清理后结算，两轮最终均passed。

### 1.3 正式执行轮次、真实命令与复现

| 轮次 | run_id | UTC开始～结束 | 最终结果 |
| --- | --- | --- | --- |
| R1 | `ws-20261023t020902z-9fa22610` | 2026-10-23 02:09:02.693～03:06:44.334 | 104 passed，其余0；环境/清理passed，退出0。 |
| R2 | `ws-20261023t030707z-c936fff7` | 2026-10-23 03:07:07.316～04:03:33.402 | 104 passed，其余0；环境/清理passed，退出0。 |

本次从仓库根`D:\Agentic_RAG\SesRAG`实际依次执行以下命令；R1清理通过并退出后才启动R2：

```powershell
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode All
pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode All -FrozenBuild 66fb4ce36c160d213a2541fb6120fea708df8e0007158e7c85dc07940f3c18b2
```

两轮源码摘要均为`684a5e22b94598517bcaeb25fe8a4ab750c758e34acdf0c6b70f97faafec3de7`，运行前后均未变化。逐例R1/R2链接指向当轮原始单例观察，完整状态/关联节点和证据路径见同目录result.json；QLT_005最终判定还须看outer_finalization及cleanup。UI_001通过仍保留归档列表呈现差异；QLT_006计数名称按报告解释，未覆写原始日志。

各例的Selected命令是后续定向复现方式，运行整类，不表示本次曾单独逐例运行Selected。执行后按新run_id读取对应case/result，等待总入口清理结束。**本文回填使当前工作区源码指纹变化**：当前树复测应不带旧FrozenBuild重新冻结；原验收输入（含空结果版用例文档）及镜像归档已保留，精确复现条件见[测试报告§2](测试报告.md#2-两轮执行基线与证据)，不得跳过指纹校验或覆盖开发工作区。

## 2. 公共前置、数据与隔离

### 2.1 公共前置 P0-ENV

1. 从当前源码和锁文件构建本套件的独立Compose，不加载根`.env`、不接开发数据库、不复用旧`tests/demo-smoke/`。总入口为`run-workspace-tests.ps1`；Environment仅技术探测，Selected/All执行已ready的产品分类。
2. 核对 PostgreSQL/pgvector、Redis、受控 Provider、migrate、Profile 导入、API、Worker、前端 readiness 和实际迁移 head。不能以容器 running 或 HTTP 200 单独替代就绪。
3. 每例以 `run_id/category/case_id` 分配数据命名空间。常规数据经正式 API/Worker 创建；不预造 succeeded Run、租约、Event 或 assistant。旧版本事实只在迁移专库按旧 revision schema 构造。并发/时钟测试调用现有真实应用、队列和 PG 探针边界，不直接 UPDATE 伪造成功。
4. 每例自行建立所需 Thread、Branch、模型场景和文档；不得依赖另一个用例通过。可在本例复用前一步产生的事实。故障/Worker停启/Profile变更用例独占分类子环境；finally 恢复配置并验证 readiness，恢复失败停止受污染子环境。
5. 正常执行、超时、异常均交给总入口收集报告并清理本轮容器（含 one-off/已停止）、网络、命名卷、专有镜像 tag、runtime 和 tmp，再独立审计残留。保留 artifacts 和明示依赖缓存，不全局 prune。

### 2.2 数据约定

| 数据 | 具体设计与使用边界 |
| --- | --- |
| 身份哨兵 | 每例独立 `CASE/<case_id>/<run_id>`；两个 Thread 用 A_ONLY/B_ONLY、分支用 ROOT/SIB_A/SIB_B/NEST_ONLY，回答使用不同哨兵。它们是合成文本，不含真实个人信息。 |
| Profile 基线 | `fixtures/model-profiles.json`：mock-default@1=8192/1024、mock-small@1=2048/256、ws-http-a@1=8192/1024、ws-http-b@1=2048/256；安全余量128、摘要上限512。真实 HTTP Profile 固定 tiktoken/cl100k_base 和离线资产。测试变体以新ID/version导入专环境，不改基线同版本生成配置。 |
| Provider 场景 | `fixtures/provider/server.py` 提供 normal/slow/stall/empty/malformed/disconnect/context-limit/http-error 等；使用控制端口和屏障，按请求序号定向。以请求收到/首片/等待释放/完成信号同步，不用固定 sleep 猜状态。若某输入无法由现有服务表达，后续只扩展测试夹具/探针，不增加产品调试路由。 |
| 长历史与预算 | 使用 `tooling/prepare-fixtures.py` 的可重建文本，并按冻结计数器生成恰好边界与边界+1数据；记录字符/字节/token/hash。用户消息每条≤20000字符；超长候选历史由多条合法消息构成，不能用非法输入绕过 API。 |
| RAG | 只导入本例合成文档，保留 document/chunk/batch/location/hash/score 身份。知识库是单 owner 共享的；测试隔离的是会话上下文，不要求同 owner 不同 Thread 看不见同一合法文档。 |
| Secret哨兵 | 分别随机生成虚假模型 Key、PG 密码、Provider 控制 token；与正文哨兵分离。原始值仅在私有 runtime/进程内使用；公开证据只记录命中面和数量，不发布值、完整 Prompt 或全量环境。 |
| 迁移/竞态 | `tooling/db-admin.py` 管理本轮白名单专库；核验实例身份和所有权。迁移库从0003起，正式 head=`0006_v2_run_guards`；禁止 downgrade base、手工 stamp 或删除开发库。PG竞态用独立连接/事务锁屏障，SQLite不替代。 |

### 2.3 公共证据与判据

每例至少保存 case ID、输入摘要/hash、对象ID、关键步骤的安全观察、断言和相对证据路径；记录版本、源码/镜像指纹和时间。PG新会话读取已提交事实，SSE/浏览器只作投影观察。Provider实收用 roles、顺序、长度、hash和哨兵匹配证明，不公开完整请求。普通业务不变量不可只用“接口200”或“页面有文字”判通过。

Thread全局 Message.seq 在分支上可有间隙；Event.seq 属于同一Run，跨attempt/generation不重置。用户输入执行身份看 Run.user_message_id，不要求旧 user Message.run_id 被重写。数据库当前没有被本文假定存在的不可变触发器；历史不变以公开写路径前后hash/身份校验。

后续自动化按下文8类主归属接入；跨需求复用证据，不重复实现同一断言。跨层用例可使用 API、PG、Provider、浏览器联合观察，分类仅决定主脚本归属。

### 2.4 本批用例的源码定位与观察层

以下文件均为仓库根相对路径；点级完整定位沿用测试点矩阵“代码依据”列。本表保留设计时的实现/测试路由；当前分类及探针已接入，实际执行范围由每轮逐例JSON、节点清单和日志共同证明，不将普通SQLite开发节点冒充PG并发证据。

| 分类/行为 | 主要实现定位 | 已有验证入口与本批补充 |
| --- | --- | --- |
| Thread/Branch/幂等 | `backend/application/session_threads.py`：`list_session_threads/session_thread_detail/patch_session_thread`；`backend/application/branches.py`：`resolve_scope/create_branch`；`backend/application/session_operations.py`；`backend/application/session_runs.py`：`create_session_message/create_related_run` | `tests/api/test_v2_session_api.py`、`tests/api/test_v2_run_api.py`、`tests/unit/test_branch_paths.py`；本批增加PG及DOM证据，不将SQLite等同PG。 |
| Context/summary/Evidence | `backend/application/context.py`：`check_mandatory_budget/load_context_candidates/plan_context/_extract_summary`；`backend/application/session_execution.py`：`publish_plan/process_session_run`；`backend/infrastructure/session/context.py` | `tests/unit/test_context_planning.py`、`tests/integration/test_v2_run_execution.py`；本批要求实收hash/哨兵与计划一致。 |
| Profile/Snapshot/Tokenizer | `backend/application/model_profiles.py`：`validate_profile_config`；`backend/infrastructure/session/model_profiles.py`：`SQLModelProfileRepository.import_profiles`；`backend/infrastructure/providers/registry.py`；`backend/infrastructure/providers/context_counter.py` | `tests/unit/test_model_profiles.py`、HTTP执行集成；本批分别验证停用、撤销凭据、同版本冲突和检索空间冻结。 |
| Run/队列/最终发布 | `backend/application/session_execution.py`：`_bounded_stream`；`backend/application/task_execution.py`：`check_execution/lock_execution/complete_run`；`backend/infrastructure/queue/postgres_queue.py`；`backend/workers/runtime.py` | `tests/integration/session_pg_probe.py`：`creation_probe/cancel_success_probe/stale_and_publication_probe/cancellation_reclaim_probe`；新交错需后续追加受控编排，不直接伪造状态。 |
| Journal/SSE/错误 | `backend/infrastructure/events/journal.py`；`backend/api/routes/v2/runs.py`；`backend/infrastructure/providers/openai_compatible.py`；`backend/api/routes/health.py`；`backend/app.py` | `tests/api/test_execution_stream.py`、`tests/integration/test_provider_http.py`、`tests/api/test_validation_safety.py`；本批区分REST/SSE游标与Redis降级。 |
| 浏览器投影 | `frontend/src/stores/thread.ts`、`frontend/src/stores/run.ts`、`frontend/src/events/run-event-stream.ts`；`frontend/src/pages/WorkspacePage.vue`；`frontend/src/components/ThreadList.vue`、`MessageTimeline.vue`、`RunTimeline.vue`、`ContextNotice.vue`、`ModelSelector.vue`、`RunActions.vue`；`frontend/src/markdown/render.ts` | 当前suite提供Playwright/Chromium；产品浏览器分类脚本尚待实现。只能用真实DOM证明刷新、迟到响应与XSS结果。 |
| 兼容/迁移/契约 | `backend/api/routes/threads.py`、`backend/api/routes/runs.py`及`backend/api/routes/v2/`；`backend/api/schemas/v2/`；`contracts/`；`migrations/versions/0004_v2_session_branches.py`、`0005_v2_profiles_context.py`、`0006_v2_run_guards.py`；`migrations/v2_session_checks.py` | `tests/unit/test_v2_session_migrations.py`及独立PG迁移库；v2新接口验证与旧样本工程门禁分别判定。 |
| 本机环境/工具/资源 | `docker-compose.yml`、`docker/`、`pyproject.toml`、`frontend/package.json`及锁文件；本suite的`compose/fixtures/tooling/schemas/` | 已有环境记录仅作准备依据；正式产品分类、性能测量和全门禁需后续真实执行。 |

## 3. 测试用例

### 3.1 session：会话、分支和输入事实

#### SES_001 创建会话并原子初始化默认分支

- 用例编号：SES_001
- 对应测试点：TP-THR-01：创建 Thread 并初始化默认 Branch
- 用例标题：创建会话并原子初始化默认分支
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立空白用例命名空间。
- 测试数据要求：省略标题、显式中文标题各一条，两个独立创建请求。
- 测试流程：1）调用v2创建Thread；2）读取详情与Branch列表；3）用返回的默认Branch提交首条合法消息。
- 预期结果：返回201和唯一Thread身份；省略标题为“新会话”；owner为服务端值，只有一个默认根Branch且parent/fork为空；首条消息可提交，不出现孤立Thread或跨Thread默认Branch。
- 优先级：P0
- 用例类型：功能/契约/原子性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。正式创建得到唯一Thread与唯一默认Branch，归属/版本/空历史一致。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_002 列表在稳定快照下排序分页不重不漏

- 用例编号：SES_002
- 对应测试点：TP-THR-02：Thread 列表排序与游标分页
- 用例标题：列表在稳定快照下排序分页不重不漏
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；在用例独占库创建至少5个Thread，提供受控应用时钟制造更新时间并列。
- 测试数据要求：更新时间不同和相同的Thread；limit=1、2、200以及省略limit。
- 测试流程：1）记录预期(updated_at,thread_id)降序；2）在不再写入的窗口遍历全部游标页；3）更新其中一个Thread后重新从首页遍历。
- 预期结果：默认limit=50；每轮完整遍历的身份集合与基线一致、无重复遗漏，并列按thread_id倒序；更新后位于对应新排序位置。跨页期间新增/改序不承诺数据库快照，本例不将这种自然变化误判分页缺陷。
- 优先级：P1
- 用例类型：功能/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。正式列表每页2项读取6个Thread，排序稳定且无重漏；快照期间未并发更新。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_003 Thread列表拒绝非法游标和越界分页

- 用例编号：SES_003
- 对应测试点：TP-THR-02：Thread 列表排序与游标分页
- 用例标题：Thread列表拒绝非法游标和越界分页
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；准备两个合法Thread及一个有效游标。
- 测试数据要求：损坏base64、非预期JSON/时间/身份结构；limit=0、201、非整数；合法游标到达末尾。
- 测试流程：1）逐项请求列表并保留安全响应；2）用有效游标请求空尾页；3）重读合法列表和业务计数。
- 预期结果：非法业务游标为422 INVALID_CURSOR；参数范围/类型错误为安全422校验体；合法尾页返回空集合且无下一游标；不回显原始异常输入，不产生业务写入。
- 优先级：P1
- 用例类型：异常/边界/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。非法/损坏游标及分页边界共7组均安全422。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_004 详情和历史分页返回指定分支的持久事实

- 用例编号：SES_004
- 对应测试点：TP-THR-03：Thread 详情与消息历史读取
- 用例标题：详情和历史分页返回指定分支的持久事实
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例经正式链路完成≥3轮问答，再创建一个后缀不同的子Branch。
- 测试数据要求：limit=1、2、200，before_seq为合法正序号；另测0/负数/limit201。
- 测试流程：1）清空客户端缓存并读取Thread详情；2）按next_before_seq向前遍历父/子路径；3）将各页拼成升序并对照PG身份与原文。
- 预期结果：Branch、默认身份、最近Run与PG一致；页内升序，下一游标为本页最小seq；拼接去分页重叠后不重不漏、不含兄弟后缀；分支seq间隙合法；非法参数422，读取不改历史。
- 优先级：P0
- 用例类型：功能/恢复/分页
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。两轮真实Worker问答按历史分页重建，身份/角色/正文/seq与完整服务端历史一致。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_005 新建和重命名使用相同标题边界

- 用例编号：SES_005
- 对应测试点：TP-THR-04：Thread 新标题输入边界校验
- 用例标题：新建和重命名使用相同标题边界
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；已建有历史的Thread，记录原标题和历史hash。
- 测试数据要求：trim后长度1/200/201、纯空白、空字符串、首尾空白、null；PATCH空对象与额外字段。
- 测试流程：1）分别参数化v2创建与显式改名；2）合法改名后重读列表和详情；3）非法请求后比较原值与历史。
- 预期结果：合法标题trim后保存；1/200接受，空白/空/201/null和无字段PATCH拒绝安全422；额外字段拒绝；失败不改标题、Message或Run，显式改名只影响指定Thread元数据。
- 优先级：P1
- 用例类型：功能/边界/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。新建/重命名1与200字符及trim合法；空白/201字符均422，失败后旧标题不变。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_006 归档只改变可用性且历史可读

- 用例编号：SES_006
- 对应测试点：TP-THR-05：归档不删除历史且仍可读取
- 用例标题：归档只改变可用性且历史可读
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例有成功、失败Run及消息/Event，归档前记录各事实ID/hash。
- 测试数据要求：含历史Thread；include_archived省略、false、true。
- 测试流程：1）归档Thread；2）读取普通列表与包含归档列表；3）通过详情、Run、事件接口读取原记录并比对PG。
- 预期结果：archived_at非空；默认列表排除，include_archived=true可找到；历史身份、原文、角色、终态与Event不变，无物理删除。UI展示差异另由UI_001判断。
- 优先级：P0
- 用例类型：功能/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。归档仅改变归档标记，已完成Message/Run仍保持原身份原文可读。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_007 归档后拒绝新操作但重放既有幂等结果

- 用例编号：SES_007
- 对应测试点：TP-THR-06：归档 Thread 的新写操作受拒绝
- 用例标题：归档后拒绝新操作但重放既有幂等结果
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例先产生一组已成功的幂等写请求，另有可retry失败源及可regenerate成功源。
- 测试数据要求：归档后以新键提交消息、分支、retry、regenerate；用归档前原键原请求重放。
- 测试流程：1）归档并记录对象计数；2）独立执行各新写操作；3）重放原操作；4）检查所有表及Branch Head。
- 预期结果：新操作409 THREAD_ARCHIVED且无部分事实；既有同键同规范请求优先重放原身份（200），不因归档误拒；旧结果可读，重放也不创造新对象。
- 优先级：P0
- 用例类型：状态边界/幂等/异常
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。归档后新消息/分支/retry/regenerate均拒绝；既有同键同体优先返回原身份，无新消息。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_008 取消归档恢复继续对话资格

- 用例编号：SES_008
- 对应测试点：TP-THR-07：取消归档恢复活跃列表资格
- 用例标题：取消归档恢复继续对话资格
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例自行创建、完成问答并归档Thread。
- 测试数据要求：archived=false；独立新幂等键和合法expected_version。
- 测试流程：1）取消归档；2）读取普通列表/详情；3）在原Branch发起新消息并完成；4）对照旧历史。
- 预期结果：archived_at为空，Thread回普通集合且身份不变；原Branch可继续写；旧消息和Run不被重建或改写，新增序号在同Thread持续递增。
- 优先级：P1
- 用例类型：功能/状态转换
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。取消归档后普通列表资格及继续写入恢复，旧Run/历史仍可读。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_009 从合法用户或assistant锚点创建子分支

- 用例编号：SES_009
- 对应测试点：TP-BR-01：从有效历史消息位置创建 Branch
- 用例标题：从合法用户或assistant锚点创建子分支
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；父Branch完成两轮问答。
- 测试数据要求：分别选择父路径中的用户消息和assistant消息；独立键，可省略/指定分支名。
- 测试流程：1）对每类锚点创建子Branch；2）读取Branch元数据和路径；3）在子路径提交独立后缀。
- 预期结果：首次201；父Branch/fork_message_id/thread_id精确指向所选锚点，子Head初值为锚点；默认关系合法、原Branch不变；分叉只引用旧消息、不复制祖先事实。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。持久用户/assistant两种锚点均建立独立子Branch，父子归属及锚点正确，未复制祖先消息。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_009.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_009.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_009.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_010 子分支共同前缀共享事实而不复制

- 用例编号：SES_010
- 对应测试点：TP-BR-02：Branch 读取包含共同祖先且不复制祖先事实
- 用例标题：子分支共同前缀共享事实而不复制
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例父路径含至少两轮成功问答，记录Message数量/hash。
- 测试数据要求：在第一轮回答处分叉，父子各增加不同后缀。
- 测试流程：1）分叉前后记录PG Message计数；2）分别读取父子路径；3）比较共有前缀的message_id/seq/正文和创建branch_id。
- 预期结果：单独分叉不增加Message；共同前缀按同一身份出现一次；两个后缀各只在自己的路径；不可为了路径连续重新分配seq或改写祖先创建Branch。
- 优先级：P0
- 用例类型：事实可靠性/隔离
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。分叉前后共同前缀身份保持，父子新后缀互不进入另一条路径且祖先不复制。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_010.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_010.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_010.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_011 兄弟及嵌套分支路径和执行上下文隔离

- 用例编号：SES_011
- 对应测试点：TP-BR-03：同一Thread兄弟与嵌套Branch路径隔离
- 用例标题：兄弟及嵌套分支路径和执行上下文隔离
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；受控HTTP Provider记录安全哨兵；本例从ROOT创建A/B，再从A创建N。
- 测试数据要求：ROOT/SIB_A/SIB_B/NEST_ONLY唯一消息和回答哨兵，均在预算内。
- 测试流程：1）分别完成A/B/N自己的对话；2）读取三条路径；3）各提交新问题并核对Provider实收顺序/hash/哨兵。
- 预期结果：共同祖先只出现一次；A不含B/N后缀，B不含A/N，N只含合法祖先前缀及自身后缀；模型实收与路径一致，无兄弟消息或摘要串用。摘要复用深测见CTX_006。
- 优先级：P0
- 用例类型：隔离/功能
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。同Thread兄弟与嵌套路径分别读取，祖先只一份且兄弟/未来后缀隔离；执行实收隔离另由指定Worker断言共同核验。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_011.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_011.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_011.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_012 非法锚点和跨Thread归属安全拒绝

- 用例编号：SES_012
- 对应测试点：TP-BR-05：非法/越权分叉锚点与路径约束拒绝
- 用例标题：非法锚点和跨Thread归属安全拒绝
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；建立两个Thread和一个不在当前父路径上的兄弟后缀。
- 测试数据要求：不存在Message/Branch、另一Thread锚点、兄弟非祖先消息；分支名null/空白/81字符。
- 测试流程：1）分别请求创建Branch；2）捕获安全错误；3）对照父Head、Branch/Message/操作记录计数。
- 预期结果：归属/对象不存在先按404；同Thread不在父路径按业务契约拒绝，名称校验422；无部分Branch和幂等操作事实；不得泄露其他Thread内容或创建越路径引用。
- 优先级：P0
- 用例类型：权限/异常/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。不存在/跨Thread对象404；null/空白/81字符名称422；无部分Branch。不可见同Thread锚点由指定路径断言覆盖。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_012.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_012.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_012.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_013 分支数量和嵌套深度到限后拒绝

- 用例编号：SES_013
- 对应测试点：TP-BR-05：非法/越权分叉锚点与路径约束拒绝
- 用例标题：分支数量和嵌套深度到限后拒绝
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独占用例库，使用正式分叉API建立结构；不影响其他case。
- 测试数据要求：分支总数99→100→101（含根）；深度31→32→33（含根），名称1/80字符。
- 测试流程：1）在数量和深度两个独立Thread构造边界；2）尝试恰好到限及超限操作；3）重读路径及对象计数。
- 预期结果：总数100与深度32可达；下一次422 BRANCH_LIMIT_EXCEEDED，无部分事实/Head改变；合法名称边界接受；不能通过修改测试上限掩盖默认产品限制。
- 优先级：P0
- 用例类型：边界/容量
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。正式API达到100个Branch/32层深度并接受80字符名；下一项均BRANCH_LIMIT_EXCEEDED且不产生部分分支。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_013.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_013.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_013.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_014 过期Head版本不能推进分支

- 用例编号：SES_014
- 对应测试点：TP-BR-06：使用过期expected_version提交时拒绝推进Branch Head
- 用例标题：过期Head版本不能推进分支
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；记录Branch版本v，以合法请求推进到v+1。
- 测试数据要求：旧expected_version=v、新独立键；对照新请求使用当前版本。
- 测试流程：1）用旧版本提交新消息；2）读取Branch及Run/Task/Message计数；3）用当前版本再次合法提交。
- 预期结果：旧版本409稳定版本冲突且无部分写入；当前版本正常创建并推进；已接受用户输入、Head与全局seq不被回滚或覆盖。
- 优先级：P0
- 用例类型：边界/并发前置
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。过期expected_version安全409且原Head/Message不变；当前版本请求成功推进。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_014.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_014.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_014.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_015 活动分支拒绝冲突写入且不阻塞独立分支

- 用例编号：SES_015
- 对应测试点：TP-BR-08：活动Run期间拒绝禁止的Branch写操作
- 用例标题：活动分支拒绝冲突写入且不阻塞独立分支
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；Provider屏障保持A有活动Run，B为同Thread独立子Branch。
- 测试数据要求：A上的新消息、从活动Run.user_message_id锚点分叉、从更早已完成历史锚点分叉；B上的合法新消息；相同键重放已接受操作。
- 测试流程：1）确认A活动事实和两类锚点；2）分别发新消息与两类分叉；3）向B提交；4）重放A原请求后释放Provider。
- 预期结果：A新消息409 BRANCH_BUSY，活动输入锚点分叉422 INVALID_BRANCH_PATH，无部分写入；更早合法历史锚点分叉可接受，不能误判“活动分支禁止所有分叉”；已接受同键请求仍重放；B可独立推进，A既有Run/Head不被非法修改。
- 优先级：P0
- 用例类型：状态边界/隔离
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。活动Branch新消息BRANCH_BUSY，活动输入锚点INVALID_BRANCH_PATH；早期合法分叉与同Thread独立Branch正常推进。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_015.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_015.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_015.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_016 真实PG多连接创建遵循Head锁序

- 用例编号：SES_016
- 对应测试点：TP-BR-09：并发消息和分支创建遵守PostgreSQL Head锁序
- 用例标题：真实PG多连接创建遵循Head锁序
- 设计可验证状态：E：原矩阵暂不可验证（TP-BR-09）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实PG专库及独立连接屏障，可调用session_pg_probe.creation_probe；不以SQLite替代。
- 测试数据要求：同Branch同版本不同键、同键同体、消息提交与合法已完成历史锚点建Branch交错、同Thread不同Branch四组独立数据。
- 测试流程：1）按每组屏障安排两个事务在Thread/Head锁前后竞争并有界释放；2）两种顺序分别观察消息与历史分叉；3）查唯一约束、Head、seq及相关身份。
- 预期结果：同Branch不同键同版本至多一个消息接受，另一方稳定冲突；同键同体归并一套事实；历史分叉本身不推进父Head，可与消息按合法串行顺序均成功；独立Branch可各自推进；无死锁/重复seq/半套对象或越路径引用。活动输入非法分叉拒绝另见SES_015，不误套全分支忙限制。
- 优先级：P0
- 用例类型：并发/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：0个pytest节点及2组真实PG场景；@pg::creation_probe；@pg::creation_edges。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_016.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_016.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_016.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_017 对象归属校验先于版本或状态提示

- 用例编号：SES_017
- 对应测试点：TP-BR-05：非法/越权分叉锚点与路径约束拒绝；TP-SEC-02：异常响应和默认日志不泄露Prompt/堆栈/宿主路径
- 用例标题：对象归属校验先于版本或状态提示
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；专库内通过合法测试仓储准备另一owner对象，应用仍以固定owner运行。
- 测试数据要求：外owner和随机不存在的Thread/Branch/Run；包括v2对象、归档对象。
- 测试流程：1）调用详情/消息/分支/Run/Event/context/取消及关联操作；2）比较外owner与不存在对象响应；3）检查无写入。
- 预期结果：均按安全404隐藏身份；不先泄露API_VERSION_REQUIRED、归档、模型或Run状态；不把固定OWNER_ID当成生产登录权限证明。
- 优先级：P0
- 用例类型：权限/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：3个pytest节点；@case::test_SES_017_owner_all_v2_endpoints；api/test_v2_session_api.py::test_v1_all_run_endpoints_guard_schema_after_owner_before_sse；api/test_v2_run_api.py::test_canonical_omitted_profile_and_owner_first_and_stale_head。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_017.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_017.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_017.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### SES_018 新消息输入和幂等头严格校验

- 用例编号：SES_018
- 对应测试点：TP-RUN-01：新消息Run原子创建与幂等重放
- 用例标题：新消息输入和幂等头严格校验
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；有效Thread/Branch和Profile对；独立键，记录初始计数。
- 测试数据要求：正文长度1/20000/20001、全空白、合法首尾空白；缺/空/201字符Key；缺branch/version、负version、Profile只填一半/null、额外受控字段。
- 测试流程：1）逐项向v2提交；2）对合法正文重读Message；3）对非法项检查安全422及零部分写入。
- 预期结果：后端保存合法正文原始空白；非法长度/类型/缺键或Key>200拒绝；Profile身份成对且不能注入owner/状态/parent_run_id；错误不回显正文，合法请求只产生一套事实。
- 优先级：P0
- 用例类型：边界/契约/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。输入/幂等头11组非法边界均安全422且无消息；1/20000字符及合法原始空白按原文保存。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/session/SES_018.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/session/SES_018.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'session'`；等待入口退出，再查新run_id的`categories/session/SES_018.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.2 context：历史、预算、摘要和证据

#### CTX_001 后续模型请求实际接收当前分支历史

- 用例编号：CTX_001
- 对应测试点：TP-RUN-09：同一Branch的既有对话进入后续Run上下文
- 用例标题：后续模型请求实际接收当前分支历史
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；使用受控HTTP Profile；本例两轮回答均经真实Worker完成。
- 测试数据要求：首轮用户USER_OLD和回答ASSISTANT_OLD哨兵，后续USER_NEW；窗口充足、不触发裁剪。
- 测试流程：1）完成首轮；2）提交第二轮；3）将Provider实收角色/顺序/hash与Message及ContextPlan选中身份对照。
- 预期结果：当前请求中按历史顺序包含首轮用户和assistant，最后是当前用户输入；只出现一次，不从测试端预拼请求或前端缓存冒充历史；Run锚点与实际user_message_id一致。
- 优先级：P0
- 用例类型：功能/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。第二轮实际HTTP请求末三条依次为旧用户/旧assistant/当前用户，角色与原文hash一一对应，锚点和选中Message身份正确。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_002 两个Thread交替执行不串历史或摘要

- 用例编号：CTX_002
- 对应测试点：TP-BR-04：Thread 间消息、摘要与运行上下文隔离
- 用例标题：两个Thread交替执行不串历史或摘要
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；两个独立Thread各建立历史及可触发摘要的数据；HTTP Provider安全观测可用。
- 测试数据要求：A_ONLY/B_ONLY、不同回答和摘要来源；知识库可为同owner共享，但不把另一Thread的上下文Evidence缓存当当前结果。
- 测试流程：1）A/B交替发起各自后续问题；2）分别核对实收哨兵/hash、计划和summary来源；3）再次切回A重复观察。
- 预期结果：每个ModelRequest只含本Thread当前路径允许的历史/摘要；无另一Thread消息、临时回答或缓存证据身份；同owner共享知识库合法召回不算跨Thread污染。
- 优先级：P0
- 用例类型：隔离/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_real_worker_model_request_history_isolation_selected_evidence；@case::test_CTX_002_007_summary_scope_and_reuse。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_003 mandatory预算到界和超界在检索前判定

- 用例编号：CTX_003
- 对应测试点：TP-CTX-01：Mandatory输入、系统指令和输出预留预算边界；TP-CAP-01：Token输入预算和输出预留有限且按Profile冻结
- 用例标题：mandatory预算到界和超界在检索前判定
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；固定Mock/真实tiktoken两种计数条件，运行Profile和限额均冻结。
- 测试数据要求：按计数器构造系统指令+当前输入+协议开销+输出预留+128余量恰好等于窗口及多1 token的合法长度输入。
- 测试流程：1）记录预算各项；2）分别执行到界/超界Run；3）核对计划、最终错误及Embedding/检索/生成调用计数。
- 预期结果：到界可继续，超界以CONTEXT_TOO_LARGE类安全错误结算；保留完整当前输入和系统规则，不截断换通过；超界不调用Embedding、检索或生成；窗口/输出额度为冻结值且有限。
- 优先级：P0
- 用例类型：边界/容量/异常
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：5个pytest节点；unit/test_context_planning.py::test_mandatory_budget_check_counts_only_system_and_current_input；unit/test_context_planning.py::test_mandatory_over_budget_fails_before_candidate_or_evidence_use；integration/test_v2_run_execution.py::test_mandatory_budget_fails_before_embedding_and_publishes_plan；@case::test_CTX_003_exact_mandatory_boundary。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_004 预算收缩按最旧完整轮次裁剪

- 用例编号：CTX_004
- 对应测试点：TP-CTX-02：超预算时按完整旧轮次顺序裁剪
- 用例标题：预算收缩按最旧完整轮次裁剪
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；小窗口Profile；在独立分支构造多轮完整问答及一个合法孤立输入。
- 测试数据要求：各轮独立哨兵，长度使移除最旧轮后恰好满足预算；另含不能再容纳的变体。
- 测试流程：1）规划并执行当前问题；2）对照被选/被省略ID和角色顺序；3）重读原历史与模型实收。
- 预期结果：先按策略减少最旧完整轮，不能只留半条消息或混入兄弟路径；当前输入不截断；仍超界明确失败；原事实不删，遗漏范围可追溯。摘要分支按既定策略另由CTX_006验证。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；unit/test_context_planning.py::test_history_trimming_removes_whole_old_turns_and_prunes_low_score_evidence_first。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_005 不可变计划与最终发送请求逐项一致

- 用例编号：CTX_005
- 对应测试点：TP-CTX-03：ContextPlan来源和计数与实际ModelRequest一致
- 用例标题：不可变计划与最终发送请求逐项一致
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；分别准备无裁剪、有裁剪、摘要、内部重试四组独立Run。
- 测试数据要求：消息ID/hash、选中Evidence身份/hash、Profile、counter版本和四项预算；同Run不同generation。
- 测试流程：1）执行至计划发布及Provider收到请求；2）按安全hash/哨兵重建所选顺序并复算冻结计数；3）读取指定generation及不存在generation。
- 预期结果：每task/generation只有对应计划，来源与实收一致、预算不超冻结窗口；重试新计划可追溯，旧计划不变；未规划返回plan=null/reason=not_planned，不存在generation返回404。
- 优先级：P0
- 用例类型：事实可靠性/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：8个pytest节点；@case::test_CTX_005_006_plan_variants；integration/test_v2_run_execution.py::test_worker_real_http_uses_frozen_model_and_planned_history；integration/test_v2_run_execution.py::test_plan_publication_after_last_flush_lease_expiry_rolls_back；integration/test_v2_run_execution.py::test_automatic_retry_keeps_run_task_input_and_attempt_plans；integration/test_v2_run_execution.py::test_persisted_summary_has_exact_sources_safe_projection_and_compacted_event。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_006 摘要保留来源切片并可在同路径复用

- 用例编号：CTX_006
- 对应测试点：TP-CTX-04：ConversationSummary来源范围、哈希与分支限制
- 用例标题：摘要保留来源切片并可在同路径复用
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；配置trim_then_extract_v1，准备足够旧历史触发压缩；原文带中英文和多字节字符。
- 测试数据要求：摘要来源message_id、字符偏移、hash、from/to seq、策略版本和创建时间；每段提取≤128 Unicode字符。
- 测试流程：1）触发摘要；2）比对私有摘要与来源切片和公开安全元数据；3）同Branch兼容后续Run再次规划；4）重读原Message。
- 预期结果：摘要是确定性摘取而非伪称LLM总结；来源完整可校验，偏移右端不含、hash稳定；仅在来源/策略兼容时复用；原Message不变、不丢全文；公开API不返回summary_text。
- 优先级：P1
- 用例类型：功能/派生事实
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：6个pytest节点；@case::test_CTX_005_006_plan_variants；integration/test_v2_run_execution.py::test_persisted_summary_has_exact_sources_safe_projection_and_compacted_event；unit/test_context_planning.py::test_summary_records_only_extracted_source_segments_and_hash。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_007 摘要不跨兄弟或父子分支直接复用

- 用例编号：CTX_007
- 对应测试点：TP-CTX-04：ConversationSummary来源范围、哈希与分支限制；TP-BR-03：同一Thread兄弟与嵌套Branch路径隔离
- 用例标题：摘要不跨兄弟或父子分支直接复用
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；A已生成摘要，再建同Thread兄弟B、子N及另一ThreadC。
- 测试数据要求：A独有来源哨兵和共同祖先；B/N/C各自问题、同策略。
- 测试流程：1）分别在B/N/C触发规划；2）检查summary_id、thread_id、branch_id、covered_message_ids和实收；3）比较A摘要原记录。
- 预期结果：A摘要不得直接作为B/N/C的可复用记录；即使共同祖先文本相同，也必须在当前路径/归属内重新构造合法派生记录；不存在未来或兄弟后缀，A摘要不被改写。
- 优先级：P0
- 用例类型：隔离/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_real_worker_model_request_history_isolation_selected_evidence；@case::test_CTX_002_007_summary_scope_and_reuse。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_008 摘要构造失败明确回退而不吞计数器错误

- 用例编号：CTX_008
- 对应测试点：TP-CTX-05：摘要失败回退和Tokenizer故障语义可区分
- 用例标题：摘要构造失败明确回退而不吞计数器错误
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立工具进程可向现有摘要/计数Port注入受控异常，不新增产品路由。
- 测试数据要求：摘要提取抛错、摘要放不进预算、Tokenizer抛错三组；输入带唯一但不敏感哨兵。
- 测试流程：1）在不同Run触发三种条件；2）观察ContextPlan策略、Run结果与日志；3）对照Provider调用和原Message。
- 预期结果：仅可回退摘要故障使用trim_only_v1并记安全SUMMARY_EXTRACTION_FAILED；摘要超预算按确定规则减少/不用摘要；Tokenizer失败必须明确失败，不能被摘要回退吞掉、字符估算或联网兜底；原文不变。
- 优先级：P0
- 用例类型：异常/恢复
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_summary_extraction_failure_publishes_trim_only_and_safe_log；unit/test_context_planning.py::test_summary_counter_failure_is_not_hidden_as_extraction_fallback。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_009 候选消息数和字符上限不丢当前输入

- 用例编号：CTX_009
- 对应测试点：TP-CTX-06：上下文候选窗口上限不静默遗漏当前问题
- 用例标题：候选消息数和字符上限不丢当前输入
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；通过多条合法消息构造长历史，必要时调用现有load_context_candidates代码级入口复核精确边界。
- 测试数据要求：候选消息199/200/201（含锚点）；总字符199999/200000/200001；独立分支尾部当前问题。
- 测试流程：1）按两组阈值分别加载与规划；2）对照所选最近候选及窗口外范围/数量；3）检查输入原文与后续请求。
- 预期结果：200条和200000字符边界按实现接受，超界只省略更旧候选并标明范围；当前问题始终保留，原始历史不删；分支seq间隙不能被误记为真实消息数量；不把有限窗口称为完整历史。
- 优先级：P1
- 用例类型：容量/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：3个pytest节点；unit/test_context_planning.py::test_candidate_message_window_keeps_exactly_latest_200_facts；unit/test_context_planning.py::test_candidate_character_limit_accepts_200000_and_trims_at_200001；unit/test_context_planning.py::test_candidate_window_omissions_are_reported_as_compact_ranges。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_009.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_009.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_009.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_010 Evidence先按低分和确定身份顺序淘汰

- 用例编号：CTX_010
- 对应测试点：TP-CTX-07：低优先级Evidence先于必要历史被移除
- 用例标题：Evidence先按低分和确定身份顺序淘汰
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；使用现有检索Port的受控Evidence集合做确定性规划，并在真实链路核对选中身份。
- 测试数据要求：多条Evidence有不同score及最低同分项，document/chunk身份不同；预算仅允许保留部分。
- 测试流程：1）在相同预算重复规划；2）逐步收缩预算；3）比对保留集合、被淘汰次序、历史和mandatory内容。
- 预期结果：最低分先移除，同分按document/chunk确定顺序处理；尽可能先移Evidence再裁旧轮；不删除mandatory；重复输入结果确定，ContextPlan安全身份反映最终集合。
- 优先级：P0
- 用例类型：功能/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；unit/test_context_planning.py::test_tied_lowest_evidence_eviction_uses_ascending_document_chunk_identity；unit/test_context_planning.py::test_low_score_evidence_is_removed_before_higher_score_evidence。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_010.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_010.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_010.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_011 最终引用仅来自本Run选中证据

- 用例编号：CTX_011
- 对应测试点：TP-RAG-01：最终Citation只引用该Run实际选择的Evidence
- 用例标题：最终引用仅来自本Run选中证据
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；经正式上传/索引建立多个合成文档；用小窗口产生召回后裁剪；另设确定性Port测试精确子集。
- 测试数据要求：不同document/chunk/batch/location/hash的证据；另一Run的证据作为负对照。
- 测试流程：1）发起有召回Run；2）读取计划、证据身份与最终Message citations；3）将每个引用反查本Run选中集合及真实索引批次。
- 预期结果：引用只来自实际选中Evidence，所有身份/位置/hash可对应；被裁掉或其他Run证据不能引用；不能仅凭回答含文档标题判定引用正确。受控向量结果不证明检索效果。
- 优先级：P1
- 用例类型：功能/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。三个合成文档经正式上传/真实PG向量索引；最终每个引用均精确对应本Run选中Evidence的document/chunk/批次/位置/hash身份，不包含未选证据。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_011.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_011.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_011.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_012 空召回和检索链故障有不同语义

- 用例编号：CTX_012
- 对应测试点：TP-RAG-02：无Evidence与检索基础设施失败表现不同
- 用例标题：空召回和检索链故障有不同语义
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；空知识库与已索引合成库两个独立场景，Embedding/检索Port支持定向故障。
- 测试数据要求：真实空结果、Embedding不可用、向量查询异常；每组独立Run。
- 测试流程：1）先验证空库正常请求；2）分别注入非空库Embedding/查询故障；3）对照计划、事件、Run错误和模型请求计数。
- 预期结果：真实空召回可按无证据流程生成且citations为空；Embedding/检索故障必须安全失败/有界重试，不伪装“无相关资料”成功或普通取消；错误层级以契约区分。DB/Redis容器故障另见RUN_025。
- 优先级：P0
- 用例类型：异常/错误语义
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：4个pytest节点；integration/test_v2_run_execution.py::test_real_worker_model_request_history_isolation_selected_evidence；@case::test_CTX_012_empty_vs_infrastructure。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_012.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_012.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_012.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### CTX_013 Context公开摘要有预算身份而无正文

- 用例编号：CTX_013
- 对应测试点：TP-OBS-03：上下文裁剪/摘要范围和模型Profile可观察但无正文泄露
- 用例标题：Context公开摘要有预算身份而无正文
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例准备有裁剪/摘要/模型标识的Run，记录私有Prompt与文档哨兵。
- 测试数据要求：模型ID/version、四预算、summary来源范围、hash；系统指令和证据原文负哨兵。
- 测试流程：1）读取context详情、Run DTO、Context事件和默认日志；2）检查安全关联/范围；3）扫描不应公开字段。
- 预期结果：可关联Profile/策略/预算及被影响历史范围，summary/证据仅安全身份和hash；不含Prompt、summary_text、证据全文、凭据/宿主路径；日志不以全文替代安全诊断。UI提示单独在UI_006验收。
- 优先级：P1
- 用例类型：可观察性/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；integration/test_v2_run_execution.py::test_persisted_summary_has_exact_sources_safe_projection_and_compacted_event。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/context/CTX_013.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/context/CTX_013.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'context'`；等待入口退出，再查新run_id的`categories/context/CTX_013.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.3 model：模型选择、快照和凭据

#### MOD_001 模型列表可区分配置并提供唯一安全默认项

- 用例编号：MOD_001
- 对应测试点：TP-MOD-01：Profile列表展示多个可用项和唯一默认选择
- 用例标题：模型列表可区分配置并提供唯一安全默认项
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；已导入四项Profile基线，尚未修改状态。
- 测试数据要求：mock-default/mock-small/ws-http-a/ws-http-b各@1；默认、启用/可用状态和展示名。
- 测试流程：1）读取models列表；2）对照元数据安全字段和唯一默认对；3）分别显式选择两个HTTP Profile创建独立Run。
- 预期结果：默认仅一对且完整启用；前端/API能区分ID/version/model/display_name；新Run反映所选身份并到达对应受控模型，不用名称猜模型；列表不返回Secret或完整配置。UI选择交互另见UI_010。
- 优先级：P0
- 用例类型：功能/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。四Profile均可区分且唯一默认；HTTP A/B各自真实成功执行，快照ID/version与显式选择一致。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_002 禁用或配置不完整Profile拒绝用于新Run

- 用例编号：MOD_002
- 对应测试点：TP-MOD-02：禁用或不完整Profile不得用于新Run且不静默回退
- 用例标题：禁用或配置不完整Profile拒绝用于新Run
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独占Profile变体环境；通过正式导入/配置路径设置禁用及不完整项。
- 测试数据要求：禁用Profile、缺运行Key、缺真实encoding/必需配置、无效ID/version；不改baseline同版本生成字段。
- 测试流程：1）读取availability；2）逐项请求新Run；3）比较对象计数、Provider请求数和响应。
- 预期结果：配置缺口在可预检处安全拒绝/标不可用，无部分Run；新Run不接受禁用项；仅运行时才能发现的缺凭据应以MODEL_CREDENTIAL_UNAVAILABLE失败而不伪装创建成功执行；任何情况都不回退Mock/其他模型。
- 优先级：P0
- 用例类型：异常/安全/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：4个pytest节点；@case::test_MOD_002_unavailable_profiles；unit/test_model_profiles.py::test_model_list_exposes_no_secret_fields_and_marks_missing_credential；api/test_v2_run_api.py::test_retry_optional_body_and_profile_replay_before_unavailable；unit/test_model_profiles.py::test_real_provider_cannot_use_mock_token_counter。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_003 旧Run执行与恢复使用冻结模型而非当前默认

- 用例编号：MOD_003
- 对应测试点：TP-MOD-03：RunSnapshot冻结Profile版本与执行配置
- 用例标题：旧Run执行与恢复使用冻结模型而非当前默认
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；暂停Worker领取，创建HTTP A Run；独占配置环境可导入A新版本并切换默认。
- 测试数据要求：A@1与新A@2具有不同model/生成参数/预算；原A@1随后停用；自动retry和恢复子场景。
- 测试流程：1）创建并记录原Snapshot；2）改默认/停用旧项；3）恢复Worker执行或重试原Run；4）新建Run对照。
- 预期结果：旧Run保持A@1及原参数/预算；停用元数据不撤销已冻结可解析配置；新Run使用新默认或显式启用项；按旧Snapshot重建，旧事实不被回写当前值。
- 优先级：P0
- 用例类型：功能/恢复/快照
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：3个pytest节点；@case::test_MOD_003_default_change_between_attempts；integration/test_v2_run_execution.py::test_worker_real_http_uses_frozen_model_and_planned_history；unit/test_model_profiles.py::test_snapshot_profile_freezes_nonsecret_version_and_registry_rebuilds_mock。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_004 同ID版本生成配置不可覆盖

- 用例编号：MOD_004
- 对应测试点：TP-MOD-03：RunSnapshot冻结Profile版本与执行配置
- 用例标题：同ID版本生成配置不可覆盖
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；Profile导入入口在专环境运行并保存基线hash。
- 测试数据要求：同ID/version改变model_name、base_url、generation_params、token预算或tokenizer；另测只改启用/默认和新version。
- 测试流程：1）分别导入冲突和允许变体；2）核对错误及持久配置；3）读取已创建Run快照。
- 预期结果：同版本生成配置冲突安全拒绝且旧值不变；启禁用/默认的允许变更不改旧Snapshot；新生成配置必须新版本，历史Run仍能解析其冻结版本。
- 优先级：P0
- 用例类型：边界/配置不变量
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：7个pytest节点；unit/test_model_profiles.py::test_same_version_profile_model_change_is_rejected；@case::test_MOD_004_immutable_fields。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_005 运行凭据撤销使旧Run明确失败而不切换

- 用例编号：MOD_005
- 对应测试点：TP-MOD-02：禁用或不完整Profile不得用于新Run且不静默回退
- 用例标题：运行凭据撤销使旧Run明确失败而不切换
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；先有有效Key创建HTTP Run，再在领取前重建服务环境移除该运行Key，保持数据库。
- 测试数据要求：与正文不同的虚假Key；同一原Run、原Snapshot、其他仍可用Mock作为负对照。
- 测试流程：1）冻结Run后撤销Key；2）恢复处理；3）查错误、attempt、Snapshot及所有Provider调用。
- 预期结果：原Run安全MODEL_CREDENTIAL_UNAVAILABLE结算，不改Profile身份，不用Mock补答案；无假成功assistant；不把“旧Profile停用但Key仍可解析”与“实际Key缺失”混为同一错误。
- 优先级：P0
- 用例类型：异常/恢复
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；unit/test_model_profiles.py::test_missing_runtime_credential_is_reported_without_disclosing_secret；@case::test_MOD_005_revoked_runtime_key。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_006 运行凭据在事实和所有公开面均不泄露

- 用例编号：MOD_006
- 对应测试点：TP-MOD-04：Secret不进入Snapshot、Profile响应和模型调用观测公开面；TP-SEC-01：Secret不进入消息、Snapshot、Event和API前端响应
- 用例标题：运行凭据在事实和所有公开面均不泄露
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立模型Key/DSN密码/控制token虚假哨兵；正常、认证失败、重试三组本例数据。
- 测试数据要求：合成凭据仅私有注入；Profile/Run/Event/Message/错误体、浏览器网络与存储、默认日志为检查面。
- 测试流程：1）执行三组场景；2）扫描业务事实字段与公开DTO/SSE/页面/日志；3）仅发布各面命中计数和安全定位。
- 预期结果：各面均不含凭据值；Profile只保存安全config_ref，Snapshot仅必要无秘密配置；浏览器只偏好身份，不存Key/DSN；报告不导出inspect Env/完整Prompt。镜像层与Git检查归QLT_006。
- 优先级：P0
- 用例类型：安全/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。实际认证HTTP执行后，6类PG事实字段、原始默认服务日志、API公开响应及真实浏览器20项网络观察/Storage均未发现运行凭据。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_007 Profile拒绝藏凭据的URL及未支持参数

- 用例编号：MOD_007
- 对应测试点：TP-SEC-03：Profile URL/参数输入拒绝凭据及未支持配置
- 用例标题：Profile拒绝藏凭据的URL及未支持参数
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；正式Profile导入入口，记录导入前数据hash。
- 测试数据要求：URL含userinfo/query/fragment；未知生成参数、非法tokenizer、窗口/输出非正或关系越界；一条合法对照。
- 测试流程：1）分别导入非法Profile；2）检查安全错误与数据库；3）导入合法对照并发起受控请求。
- 预期结果：非法项不持久化，不原样回显带凭据URL；未知参数/计数器配置明确拒绝；合法项可用，不通过清洗后悄悄改用户配置来掩盖非法输入。
- 优先级：P0
- 用例类型：安全/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：7个pytest节点；unit/test_model_profiles.py::test_profile_rejects_url_credentials_and_unknown_generation_parameters；unit/test_model_profiles.py::test_snapshot_rejects_incomplete_or_out_of_bounds_nested_policy；unit/test_model_profiles.py::test_profile_requires_explicit_tiktoken_framing_and_calibration_settings。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### MOD_008 恢复检索沿用冻结Embedding空间

- 用例编号：MOD_008
- 对应测试点：TP-MOD-03：RunSnapshot冻结Profile版本与执行配置；TP-RAG-01：最终Citation只引用该Run实际选择的Evidence
- 用例标题：恢复检索沿用冻结Embedding空间
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；已索引384维合成文档；冻结Run后可改变当前服务Embedding配置，旧端点仍由Provider观测。
- 测试数据要求：原kind/model/base_url/secret alias/top_k与新配置不同；生成Profile也独立切换。
- 测试流程：1）创建启用检索Run并暂停；2）变更当前Embedding设置；3）恢复并观察Embedding/检索调用和引用身份。
- 预期结果：旧Run按retrieval快照重建原kind/端点/模型/384维/top_k；新生成模型不改变向量空间；凭据仅运行期解析；故障不静默改空间或伪空召回，最终引用仍来自本Run证据。
- 优先级：P0
- 用例类型：快照/恢复/检索边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_worker_embedding_rebuild_uses_frozen_endpoint_and_kind；integration/test_v2_run_execution.py::test_mock_embedding_mode_does_not_depend_on_embedding_model_label。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/model/MOD_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/model/MOD_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'model'`；等待入口退出，再查新run_id的`categories/model/MOD_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.4 run：执行、事件、恢复、取消和错误

#### RUN_001 新消息原子创建且幂等重放不重复事实

- 用例编号：RUN_001
- 对应测试点：TP-RUN-01：新消息Run原子创建与幂等重放
- 用例标题：新消息原子创建且幂等重放不重复事实
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；新Thread/默认Branch；Worker在接受后可受控暂停。
- 测试数据要求：一个有效Key、规范请求及只改变正文/Profile/Branch的冲突请求。
- 测试流程：1）首次提交并记录身份；2）同键同规范请求重放；3）同键异体请求；4）从PG核对Message、Run、Snapshot、Task、操作及初始事件。
- 预期结果：首次201、重放200且返回原身份；异体409 IDEMPOTENCY_CONFLICT；仅一套事实并相互归属一致，Head原子推进；任何创建失败不留孤立用户消息或无Task的Run。
- 优先级：P0
- 用例类型：功能/幂等/原子性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；api/test_v2_run_api.py::test_create_snapshot_replay_before_archive_and_no_external_calls。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_002 运行中delta仅为草稿而非最终Message

- 用例编号：RUN_002
- 对应测试点：TP-RUN-03：流式delta在完成前不构成最终assistant Message
- 用例标题：运行中delta仅为草稿而非最终Message
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；受控HTTP Provider首片后暂停，Worker保持有效租约。
- 测试数据要求：首片DRAFT_ONLY、后续FINAL_ONLY及正常结束标记。
- 测试流程：1）等待首delta已提交；2）查询Run、Event、Message及页面；3）释放Provider正常结束再查询。
- 预期结果：暂停时有answer.delta但无该Run最终assistant，Run非终态；完成才发布最终Message，投影替换而非重复追加；最终正文按产品strip规则规范化，失败草稿不能冒充完成事实。
- 优先级：P0
- 用例类型：功能/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_first_delta_flushes_while_provider_stalls；@case::test_RUN_002_draft_is_not_message。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_003 最终发布事务全部提交或全部回滚

- 用例编号：RUN_003
- 对应测试点：TP-RUN-04：最终assistant Message与Run成功终态共同提交
- 用例标题：最终发布事务全部提交或全部回滚
- 设计可验证状态：E：原矩阵暂不可验证（TP-RUN-04）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实PG专库，现有stale_and_publication_probe/执行集成入口可控制最终flush前的租约/提交边界。
- 测试数据要求：正常成功、最终flush租约过期、提交前受控数据库错误三组独立任务。
- 测试流程：1）在最终发布前建立屏障；2）分别放行成功或注入故障；3）用新连接比较Task/Run状态、assistant、Branch Head及message.completed/run.succeeded。
- 预期结果：成功时唯一assistant、Head、Run/Task成功及配套终态事件同事务可见；失败时整组回滚，不留成功无消息/失败有完成消息；不能把分步查询时不同快照的正常变化当部分提交。
- 优先级：P0
- 用例类型：原子性/异常/并发
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点及2组真实PG场景；@pg::stale_and_publication_probe；@pg::commit_failure；integration/test_v2_run_execution.py::test_v2_final_publication_expiry_rolls_back_message_events_and_head。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_004 自动重试沿用同一身份并隔离失败增量

- 用例编号：RUN_004
- 对应测试点：TP-RUN-05：Worker自动重试沿用同一Run/输入且不拼接尝试增量
- 用例标题：自动重试沿用同一身份并隔离失败增量
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；定向Provider第一尝试可重试失败、第二尝试正常，期间有失败草稿。
- 测试数据要求：OLD_ATTEMPT_DELTA与NEW_ATTEMPT_ANSWER；同一输入/Run/Task。
- 测试流程：1）执行第一尝试并记录Event/计划；2）经队列backoff重新领取；3）完成第二尝试并比较身份、attempt/generation与最终回答。
- 预期结果：Run/Task/user_message_id不变，attempt/generation递增且受限；各代计划不可变且可关联；Event.seq不重置，最终回答不拼接旧代草稿；不产生第二条用户输入或会话层新Run。
- 优先级：P0
- 用例类型：异常/恢复/事实语义
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；integration/test_v2_run_execution.py::test_automatic_retry_keeps_run_task_input_and_attempt_plans。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_005 用户retry新建Run并按来源Head选择分支

- 用例编号：RUN_005
- 对应测试点：TP-RUN-06：用户显式retry创建可追溯的新Run并保留旧结果
- 用例标题：用户retry新建Run并按来源Head选择分支
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；在本例分别建立failed/cancelled源；一组源Head仍是输入且空闲，另一组已推进或忙。
- 测试数据要求：每次独立幂等键；原输入正文/hash、旧事件集合。
- 测试流程：1）请求retry；2）比较新Run/Task/parent_run_id/operation_kind与输入；3）分别验证复用空闲原Branch和新子Branch路径；4）令新尝试失败。
- 预期结果：新Run/Task且parent指向源，operation_kind=user_retry，复用原user_message_id，不改原Message.run_id；满足原Head空闲条件才复用，否则子路径；旧失败/取消与事件不被改写，新失败不污染旧可读结果。
- 优先级：P0
- 用例类型：功能/恢复/分支
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；api/test_v2_run_api.py::test_retry_reuses_input_and_immutable_creator_and_head_version；integration/test_v2_run_execution.py::test_successful_explicit_retry_turn_survives_failed_creator_context。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_006 regenerate始终新建路径且排除旧答及未来历史

- 用例编号：RUN_006
- 对应测试点：TP-RUN-07：已成功回答重新生成进入独立路径且保留旧回答
- 用例标题：regenerate始终新建路径且排除旧答及未来历史
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例成功源后父路径继续一轮；受控Provider可观测输入。
- 测试数据要求：原输入、旧回答OLD_ANSWER、之后FUTURE_ONLY；两个不同重生成键。
- 测试流程：1）针对原成功Run重生成两次；2）读取两个新Branch和关联Run；3）比较实收上下文和原路径。
- 预期结果：每个新键独立新子Branch/Run，复用原输入并关联源Run；请求不含旧答案及父路径未来消息；旧成功回答/Run原样可读，新答案不覆盖旧事实。
- 优先级：P0
- 用例类型：功能/隔离/历史保留
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_regenerate_distinct_children_exclude_old_answer_reuse_input；integration/test_v2_run_execution.py::test_regenerate_worker_sees_input_prefix_without_old_answer_or_future。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_007 关联操作重放与状态限制不改变来源

- 用例编号：RUN_007
- 对应测试点：TP-RUN-08：显式retry/regenerate操作幂等且来源身份不变
- 用例标题：关联操作重放与状态限制不改变来源
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立failed/cancelled/succeeded/活动Run；记录来源和对象计数。
- 测试数据要求：retry/regenerate同键同体、同键改Profile；非法来源状态；归档/禁用前已接受的原请求。
- 测试流程：1）首次操作后重放及冲突请求；2）对不允许状态发新操作；3）状态条件变化后重放原请求。
- 预期结果：同键同体200同结果，新键首次201；冲突409且无重复Branch；retry仅failed/cancelled、regenerate仅succeeded，新操作错误可诊断；已接受请求先重放，不因新增归档/禁用状态改变旧来源关系或补写旧Journal。
- 优先级：P0
- 用例类型：幂等/状态边界/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；api/test_v2_run_api.py::test_retry_reuses_input_and_immutable_creator_and_head_version；api/test_v2_run_api.py::test_retry_optional_body_and_profile_replay_before_unavailable。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_008 Run Journal跨重试单调追加且历史不改写

- 用例编号：RUN_008
- 对应测试点：TP-EVT-01：同一Run事件seq严格递增且历史不可重排
- 用例标题：Run Journal跨重试单调追加且历史不改写
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；单个Run经历计划、流式增量、一次自动重试和最终结算。
- 测试数据要求：事件event_id/seq/type/data的安全hash；REST每页limit=1/2与SSE观察。
- 测试流程：1）按阶段记录已提交事件；2）继续执行后重新读旧范围；3）对照PG、REST分页、SSE顺序。
- 预期结果：同Run seq从起点持续递增且不复用/重置，event_id唯一；旧事件hash不变；连接重放不改Journal；schema2执行事件带真实task/attempt/generation，不用测试方重编号。
- 优先级：P0
- 用例类型：契约/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；integration/test_v2_run_execution.py::test_automatic_retry_keeps_run_task_input_and_attempt_plans。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_009 阶段事件来自真实状态且只投影安全白名单

- 用例编号：RUN_009
- 对应测试点：TP-EVT-02：状态事件和回答增量按持久事实投影；TP-OBS-01：公开运行时间线仅含白名单阶段与安全摘要
- 用例标题：阶段事件来自真实状态且只投影安全白名单
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；正常检索成功、自动重试、永久失败、取消四组独立Run。
- 测试数据要求：queued/leased/started/retrieval/delta/retry/终态与context事件；负对照隐藏思维/工具轨迹字段。
- 测试流程：1）在各场景记录PG事实及REST/SSE；2）按schema版本校验每类payload；3）比对事件与真实阶段。
- 预期结果：每组只出现实际经历的阶段；终态由持久提交确认；不存在本地定时器伪造完成、CoT/完整Prompt/Secret、未实现工具事件；额外嵌套敏感字段被契约拒绝。页面顺序另见UI_007。
- 优先级：P0
- 用例类型：功能/安全/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。成功检索、自动重试、永久失败、取消四组真实Run：独立PG只读事务、REST、SSE事件身份/payload逐项一致；终态/assistant与Task事实一致，额外敏感字段契约拒绝。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_009.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_009.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_009.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_010 首delta在Provider继续停顿时独立可见

- 用例编号：RUN_010
- 对应测试点：TP-EVT-03：Provider暂停期间首个delta已持久化可查询
- 用例标题：首delta在Provider继续停顿时独立可见
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；PG独立READ COMMITTED观察连接，Provider首片后无限下一片前设有界屏障。
- 测试数据要求：首段哨兵FIRST_CHUNK；流结束被屏障阻挡。
- 测试流程：1）确认收到首片且Provider仍等待；2）在有界轮询内用新快照查Journal并消费SSE；3）释放后检查最终顺序。
- 预期结果：无需第二token或结束标记就可见已提交首delta；正常flush约100ms机制实际生效；释放后正文顺序正确；此功能用例不代替PERF_002的1秒精确延迟判定。
- 优先级：P0
- 用例类型：时序/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。Provider真实屏障仍挂起时，独立PG READ COMMITTED事务及SSE均已见FIRST_CHUNK，Run running且无最终assistant；释放后正文顺序正确。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_010.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_010.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_010.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_011 REST与SSE交叠补放不丢事件

- 用例编号：RUN_011
- 对应测试点：TP-EVT-04：指定after_seq重连可补齐缺失事件且不重复展示
- 用例标题：REST与SSE交叠补放不丢事件
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；长流产生可跨多页事件；保持同一Run不重建。
- 测试数据要求：断点k、从0、末seq及超出末seq；REST页大小1/2，SSE交叠块。
- 测试流程：1）读到k断开；2）期间继续执行；3）REST补页与SSE从k恢复，保存原始seq并通过真实客户端归并器投影。
- 预期结果：所有k后已提交事件可补齐，run+seq去重；乱序到达只推进连续游标，缺口必须补齐；终态尾页排完后关闭；从终态重连不重执行Provider。DOM交互另见UI_003。
- 优先级：P0
- 用例类型：恢复/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。持续Run真实断点后SSE补放与REST小页一致；从0/断点/末尾/越界完整补放，真实客户端归并器对重排和重复事件只保留原始唯一seq。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_011.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_011.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_011.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_012 REST和SSE分别遵守自身游标规则

- 用例编号：RUN_012
- 对应测试点：TP-EVT-05：Event分页游标非法、优先级和上限符合接口契约
- 用例标题：REST和SSE分别遵守自身游标规则
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；固定已完成Run包含多条事件，可建立新SSE连接。
- 测试数据要求：REST after_seq=-1/非整数、limit0/1001/省略；SSE Header/query冲突、负数/坏值/空值、合法末尾。
- 测试流程：1）逐项调用REST与SSE；2）记录首个返回seq和尾页结束；3）核对数据上限和错误体。
- 预期结果：REST非法参数安全422，默认limit200最大1000；SSE优先Last-Event-ID，负数/不可解析归0而非套用REST422；合法cursor只返回其后事件，终态空尾页有限关闭，无无限返回。
- 优先级：P1
- 用例类型：边界/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。REST非法参数422；SSE独立Header优先级/坏值回0；默认上限与末尾有限关闭均经实际请求验证。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_012.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_012.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_012.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_013 断开观察不取消或重启业务执行

- 用例编号：RUN_013
- 对应测试点：TP-EVT-06：SSE观察者断开不取消、不重启业务Run
- 用例标题：断开观察不取消或重启业务执行
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；Provider慢流/阻塞，已有SSE观察者；抓取API调用和Provider计数。
- 测试数据要求：同一Run的两次连接、一次中途断开。
- 测试流程：1）观察首片后主动关闭连接；2）在无观察者时释放Provider直至终态；3）重新连接/读取结果。
- 预期结果：Run/Task/attempt不因断连改变，无cancel请求、无重复用户输入/Run/模型请求；原Run仍可独立成功/失败；重连仅读Journal。刷新与组件卸载由UI_002补证。
- 优先级：P0
- 用例类型：恢复/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。SSE读取后主动断开；同一Run继续成功结算，未发出cancel/retry请求。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_013.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_013.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_013.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_014 API容器重启后持久历史和运行观察恢复

- 用例编号：RUN_014
- 对应测试点：TP-RUN-02：持久历史在服务重建后保持原文和顺序；TP-REC-03：API/Worker重启后同一Run/Task按Snapshot恢复
- 用例标题：API容器重启后持久历史和运行观察恢复
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；一组已完成多轮Thread，另一组Run正由独立Worker执行；真实PG保持运行。
- 测试数据要求：重启前ID/角色/正文hash/seq/终态与Snapshot；运行中事件断点。
- 测试流程：1）只重启本轮API；2）等待readiness；3）清空客户端连接后读历史和补放运行中Run。
- 预期结果：完成历史原文/顺序/身份保持；正在执行Run不被重建或取消，Worker可继续；事件断点后可补齐；Provider配置来自原Snapshot，不依赖API内存。
- 优先级：P0
- 用例类型：恢复/部署
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。完成态/运行态两组API真实重启均重新就绪；历史、Snapshot、Run/Task身份和Journal前缀保持，断点后可补齐终态。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_014.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_014.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_014.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_015 Worker停止及失租恢复不重复创建Run

- 用例编号：RUN_015
- 对应测试点：TP-REC-03：API/Worker重启后同一Run/Task按Snapshot恢复
- 用例标题：Worker停止及失租恢复不重复创建Run
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；本轮独占Worker/API环境；支持优雅停止和强停两组独立Run并用Provider屏障同步。
- 测试数据要求：原Run/Task/input及Snapshot；一组先完成/释放，另一组让租约过期后新Worker领取。
- 测试流程：1）确认已领取再分别停止；2）记录截止/释放/过期路径；3）重启Worker并观察重领和结算。
- 预期结果：停止后不领新任务；已领任务在有界时间完成/释放或等待回收，不能静默丢失；恢复沿用Run/Task/input，generation提高，事件可补放；可重做模型调用但不承诺token位置续算。
- 优先级：P0
- 用例类型：恢复/异常/租约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。优雅stop和SIGKILL失租两组真实恢复：停服期间新Task保持queued，恢复沿用Run/Task/input/Snapshot，generation递增且唯一最终回答。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_015.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_015.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_015.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_016 旧generation迟到计划或写回全部被拒绝

- 用例编号：RUN_016
- 对应测试点：TP-REC-04：旧Worker租约代写回被拒绝
- 用例标题：旧generation迟到计划或写回全部被拒绝
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-04）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实PG多连接屏障及现有stale_and_publication_probe；A失租、B更高代有效。
- 测试数据要求：分别延迟A的计划发布、delta flush、进度/完成写回；B有已提交事实。
- 测试流程：1）A领取后阻塞；2）通过真实队列回收/重领产生B；3）释放A各写入边界；4）新连接对照B和历史hash。
- 预期结果：所有写回以task_id+worker_id+generation及有效时间判定；A不能覆盖B计划、事件、assistant、Head或终态，整组失败回滚；不只验证最终Run状态而漏查迟到delta。
- 优先级：P0
- 用例类型：并发/恢复/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点及2组真实PG场景；@pg::stale_and_publication_probe；@pg::stale_all_writes；integration/test_v2_run_execution.py::test_plan_publication_after_last_flush_lease_expiry_rolls_back。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_016.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_016.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_016.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_017 无执行者queued和retry_waiting可直接取消

- 用例编号：RUN_017
- 对应测试点：TP-CAN-01：queued/retry_waiting Run取消并停止后续执行
- 用例标题：无执行者queued和retry_waiting可直接取消
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；暂停Worker建立queued；另Run经真实可重试故障进入retry_waiting并暂停领取。
- 测试数据要求：两种Task真实状态，独立取消请求及重复取消。
- 测试流程：1）确认无有效执行者；2）取消后读Run/Task/Event；3）恢复Worker并观察Provider计数。
- 预期结果：直接cancelled，取消终态唯一；不再领取/调用模型；重复取消返回现状不重复追加终态；失败/成功等已有终态也不因cancel改写。
- 优先级：P0
- 用例类型：功能/状态边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：4个pytest节点；integration/test_v2_run_execution.py::test_cancellation_task_state_ack_and_reclaim_priority。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_017.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_017.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_017.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_018 leased或running取消先cancelling后确认

- 用例编号：RUN_018
- 对应测试点：TP-CAN-02：running取消保持cancelling直到Worker确认
- 用例标题：leased或running取消先cancelling后确认
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；分别在已领取未run.started与运行中检索/流阻塞处建立屏障。
- 测试数据要求：Task leased但Run可能queued，以及运行中已出delta两个独立样本。
- 测试流程：1）以Task事实确认执行者；2）发cancel并暂不放行Worker；3）读cancelling后释放到可中断边界；4）查最终事实。
- 预期结果：有执行者时不能因Run表面queued直接报已取消；先持久取消请求/cancelling，Worker确认才cancelled；Task不引入cancelling新状态；已有delta只留事件，无成功assistant；UI不能倒计时推终态。
- 优先级：P0
- 用例类型：状态机/恢复
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：5个pytest节点；integration/test_v2_run_execution.py::test_worker_observes_cancel_and_acknowledges_without_requeue；integration/test_v2_run_execution.py::test_cancellation_task_state_ack_and_reclaim_priority。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_018.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_018.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_018.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_019 取消先提交时成功事务不能反向获胜

- 用例编号：RUN_019
- 对应测试点：TP-CAN-03：取消与成功提交竞争只有一个终态获胜
- 用例标题：取消先提交时成功事务不能反向获胜
- 设计可验证状态：E：原矩阵暂不可验证（TP-CAN-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实PG cancel_success_probe/锁屏障，确认取消事务先于最终发布持锁并提交。
- 测试数据要求：同一有效执行任务、完整Provider答案在最终发布前被阻挡。
- 测试流程：1）先提交取消请求/确认路径；2）释放成功发布事务；3）查询Run/Task、assistant、Head和全部终态。
- 预期结果：最终cancelled且唯一终态，成功发布被拒绝/回滚；没有message.completed/run.succeeded或最终assistant，Head不被推进到失败发布的答案；竞争次序证据真实，不用sleep猜测。
- 优先级：P0
- 用例类型：并发/原子性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：0个pytest节点及1组真实PG场景；@pg::cancel_success_probe。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_019.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_019.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_019.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_020 成功先提交时后续取消仅读成功事实

- 用例编号：RUN_020
- 对应测试点：TP-CAN-03：取消与成功提交竞争只有一个终态获胜
- 用例标题：成功先提交时后续取消仅读成功事实
- 设计可验证状态：E：原矩阵暂不可验证（TP-CAN-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；独立PG竞争数据，屏障确保成功事务全部提交后才让取消获锁。
- 测试数据要求：一个成功Run及其唯一最终assistant。
- 测试流程：1）成功发布并由新连接确认；2）释放cancel；3）再次重复cancel和读取事件。
- 预期结果：cancel返回succeeded现状，不追加cancelling/cancelled，不删除成功消息或改Head；始终只有一套成功事实，终态不可逆。
- 优先级：P0
- 用例类型：并发/状态边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：0个pytest节点及1组真实PG场景；@pg::cancel_success_probe。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_020.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_020.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_020.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_021 取消后迟到结果或过期回收不能翻转终态

- 用例编号：RUN_021
- 对应测试点：TP-CAN-04：取消后迟到Provider结果或租约回收不能翻转终态
- 用例标题：取消后迟到结果或过期回收不能翻转终态
- 设计可验证状态：E：原矩阵暂不可验证（TP-CAN-04）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；Provider延迟响应，另组任务取消请求后让lease/deadline过期；真实PG cancellation_reclaim_probe。
- 测试数据要求：晚到delta/完整答案；取消与普通失败/重试回收竞争；含被其他事务锁住的任务。
- 测试流程：1）先使取消事实生效；2）释放迟到Provider或运行回收器；3）按新快照查事件、消息、租约和其他未锁任务。
- 预期结果：取消优先结算而非被当普通可重试任务；旧执行者不续写终态后答案/成功；回收skip locked不全局阻塞；没有成功assistant、终态翻转或长期活租约。
- 优先级：P0
- 用例类型：并发/异常/恢复
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点及2组真实PG场景；@pg::cancellation_reclaim_probe；@pg::cancellation_skip_locked；integration/test_v2_run_execution.py::test_expired_cancellation_ack_rejected_reclaimer_cancels_not_fails。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_021.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_021.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_021.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_022 HTTP故障映射区分永久与可重试

- 用例编号：RUN_022
- 对应测试点：TP-ERR-01：Provider HTTP状态按可重试性映射
- 用例标题：HTTP故障映射区分永久与可重试
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；受控HTTP Provider按请求序号返回指定状态，独立Run避免attempt污染。
- 测试数据要求：401/403/400/404/408/429/500/503、网络断连和超时；响应体含合成敏感哨兵。
- 测试流程：1）逐项执行到稳定终态；2）查Provider底层分类、Run安全码、Task尝试与事件；3）扫描公开错误。
- 预期结果：401/403及普通4xx为永久失败；408/429/5xx/网络/超时按有界策略重试；区分Provider底层码和会话包装码，不误要求它们相同；响应正文不回显、无静默成功。
- 优先级：P0
- 用例类型：异常/错误语义
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。8组真实HTTP错误分别结算：401/403/400/404仅1尝试，408/429/500/503有界3尝试；无最终assistant或上游正文泄露。网络/超时的适配器断言另附JUnit。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_022.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_022.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_022.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_023 空流和破损协议不产生成功回答

- 用例编号：RUN_023
- 对应测试点：TP-ERR-02：空流、坏JSON、断流或缺少结束标记不能伪成功
- 用例标题：空流和破损协议不产生成功回答
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；受控Provider或现有协议fixture能分别表达每个原始协议故障。
- 测试数据要求：空流、只有空白delta、坏JSON、非字符串delta、中途断流、无[DONE]、超时；独立请求。
- 测试流程：1）逐场景返回原始协议；2）观察调用次数、事件及最终消息；3）保存故障类型和安全错误码。
- 预期结果：各故障明确失败或有界重试，不能凭部分输出成功；MODEL_EMPTY_OUTPUT/MODEL_STREAM_INVALID等按实际层级区分；无最终assistant或伪造完整答案；部分delta可审计但不算完成。
- 优先级：P0
- 用例类型：异常/协议
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：24个pytest节点；@case::test_RUN_023_protocol_worker_terminal；integration/test_v2_run_execution.py::test_empty_or_invalid_provider_stream_cannot_succeed；integration/test_provider_http.py。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_023.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_023.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_023.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_024 PG不可用和Redis通知降级不伪装空知识

- 用例编号：RUN_024
- 对应测试点：TP-ERR-03：Database、Redis、检索故障与空召回区分
- 用例标题：PG不可用和Redis通知降级不伪装空知识
- 设计可验证状态：E：原矩阵暂不可验证（TP-ERR-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；独占分类子环境，可停止/恢复本轮PG或Redis；采证不导出凭据。
- 测试数据要求：PG中断在提交/读取/执行阶段分别触发；Redis中断时保持PG健康；各组独立Run。
- 测试流程：1）依次注入故障并读health/Run/SSE；2）记录失败或通知丢失；3）恢复依赖/readiness后读持久事实和回收结果。
- 预期结果：PG不可用readiness503 DATABASE_UNAVAILABLE，不能出现假成功或空召回答复；恢复后按持久事实处理。Redis不就绪可HTTP200 status=degraded、Worker数量不可得/0；PG轮询可继续补放，不要求Run必须失败；通知不是事实源。
- 优先级：P0
- 用例类型：异常/恢复/事实来源
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。Redis通知降级仍按PG执行；PG读取/提交/执行三阶段真实中断均无假成功，恢复后原输入/Run/Task/Snapshot可追溯且无重复最终回答。服务均已恢复。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_024.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_024.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_024.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_025 持续错误耗尽重试预算后有界结算

- 用例编号：RUN_025
- 对应测试点：TP-ERR-04：自动重试、deadline和资源失败有界且可结算
- 用例标题：持续错误耗尽重试预算后有界结算
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；故障Provider持续返回可重试错误；使用创建时冻结的max_attempts及真实backoff。
- 测试数据要求：默认max_attempts=3；持久记录各attempt/generation、时间与错误。
- 测试流程：1）连续执行至预算耗尽；2）再等待一次有界回收窗口；3）查询Task/Run终态、租约、事件和Provider次数。
- 预期结果：尝试不超过冻结预算；末次明确failed，唯一安全终态且不留下有效租约/永续retry_waiting；之后不再调用Provider，不通过无限延长测试超时换通过。
- 优先级：P0
- 用例类型：异常/容量
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；integration/test_v2_run_execution.py::test_automatic_retry_keeps_run_task_input_and_attempt_plans；@case::test_RUN_025_exhaustion。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_025.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_025.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_025.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_026 输出字符、原始增量和缓冲字节到限受控

- 用例编号：RUN_026
- 对应测试点：TP-CAP-02：流式答案长度和增量速率受限
- 用例标题：输出字符、原始增量和缓冲字节到限受控
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；Provider可定向输出分片；精确阈值测试可用现有冻结执行配置测试入口，不能修改已创建Snapshot。
- 测试数据要求：分别达到/超过max_output_chars=1000000、max_raw_deltas=4096、delta_buffer_bytes=65536；覆盖多字节文本。
- 测试流程：1）为三种限制建立独立Run/核心执行子场景；2）使其他限制不先触发；3）查询终态与实际已提交增量数量/字节。
- 预期结果：到界按配置可处理，越界ANSWER_LIMIT_EXCEEDED或DELTA_BUFFER_LIMIT并停止；原始delta数不同于flush后的Event数；字节按UTF-8而非字符；失败草稿不成为完成消息，内存/事件不无界增长。
- 优先级：P0
- 用例类型：容量/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：12个pytest节点；integration/test_v2_run_execution.py::test_frozen_resource_limits_fail_with_reserved_terminal；@case::test_RUN_026_frozen_boundaries。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_026.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_026.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_026.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_027 常规事件预算耗尽仍保留失败结算能力

- 用例编号：RUN_027
- 对应测试点：TP-CAP-03：Event数量达到上限时仍可写入终态
- 用例标题：常规事件预算耗尽仍保留失败结算能力
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；在现有应用执行测试入口按真实追加路径逼近冻结max_regular_events，不批量SQL伪造Journal。
- 测试数据要求：默认15000常规Event；独立成功末尾、重试调度、失败结算边界；可用合法较小冻结限额提高重复性。
- 测试流程：1）按真实追加逼近/达到限额；2）继续正常/异常路径；3）查最后事件、Run/Task及租约。
- 预期结果：常规Event有限；超过预算明确RUN_EVENT_LIMIT，终态保留额度可提交唯一run.failed；不留下running/有效租约，不能靠跳过终态断言判通过；已正常成功结算的合法边界仍一致。
- 优先级：P0
- 用例类型：容量/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：3个pytest节点；@case::test_RUN_027_regular_events_boundary；integration/test_v2_run_execution.py::test_event_limit_during_retry_becomes_failure_not_stuck_lease。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_027.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_027.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_027.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_028 deadline及步骤/流超时阻止无限执行

- 用例编号：RUN_028
- 对应测试点：TP-CAP-04：Run执行时长受deadline限制并最终结算；TP-ERR-04：自动重试、deadline和资源失败有界且可结算
- 用例标题：deadline及步骤/流超时阻止无限执行
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；可控时钟的真实应用/queue探针与慢Provider；lease与deadline分开建样本。
- 测试数据要求：冻结deadline600s、step60s、stream120s；边界前/到界/越界与取消请求同时存在的变体。
- 测试流程：1）在受控边界前执行；2）推进时钟或保持Provider阻塞至超时；3）查停止调用、回收和结算，不改Run原deadline。
- 预期结果：各限时按冻结值生效，越界不继续写入或无限重试；deadline耗尽按失败策略结算，有取消请求则按取消优先；失租不能靠延长lease补成功；异步回收在有界等待内完成。
- 优先级：P0
- 用例类型：异常/时间边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：5个pytest节点；@case::test_RUN_028_deadline_exact_and_cancel_priority；integration/test_v2_run_execution.py::test_frozen_timeout_closes_stream_and_never_publishes_success；integration/test_lease_recovery.py。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_028.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_028.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_028.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_029 对象关联可追溯且不混淆输入创建者

- 用例编号：RUN_029
- 对应测试点：TP-OBS-02：Run、Thread、Branch、Task与Event身份可关联
- 用例标题：对象关联可追溯且不混淆输入创建者
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例产生一次正常Run、一次自动重试和一次用户关联操作。
- 测试数据要求：thread_id/branch_id/run_id/task_id/user_message_id/assistant_message_id、event seq/attempt/generation。
- 测试流程：1）遍历API、Context、PG、Event及结构化日志安全关联字段；2）沿Run输入反查Message与Branch路径；3）比较各代身份。
- 预期结果：每条事实能归属唯一Run/Task及合法Thread/Branch；自动attempt与用户新Run可区分；Message.run_id保留创建者而Run.user_message_id为执行输入；UI投影身份不反写PG，不因seq同值跨Run混淆。
- 优先级：P0
- 用例类型：可观察性/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。正常、自动retry、用户regenerate三组PG/API/计划/Event/结构化日志身份完整关联；自动代数不新建Run，用户新Run复用输入但Message.run_id仍为原创建者。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_029.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_029.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_029.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### RUN_030 校验和运行错误只返回安全诊断

- 用例编号：RUN_030
- 对应测试点：TP-SEC-02：异常响应和默认日志不泄露Prompt/堆栈/宿主路径
- 用例标题：校验和运行错误只返回安全诊断
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；日志级别为默认；正文、未知字段名、宿主路径、Provider错误体各有独立合成哨兵。
- 测试数据要求：非法请求、Provider认证/解析错误、数据库不可用三组；不使用真实隐私或凭据。
- 测试流程：1）触发校验与业务/基础设施错误；2）扫描原始响应和默认日志；3）核对安全loc/type/msg或code/message及关联ID。
- 预期结果：校验detail只含安全类型/位置和固定说明，未知字段名归一为field；不含input/ctx/url或原始值；业务错误可诊断但无完整Prompt/堆栈/宿主路径/凭据。记录有意认证Key扫描复用MOD_006证据，不重复输出秘密。
- 优先级：P0
- 用例类型：安全/异常
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：10个pytest节点；api/test_validation_safety.py。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/run/RUN_030.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/run/RUN_030.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'run'`；等待入口退出，再查新run_id的`categories/run/RUN_030.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.5 workspace：浏览器恢复、投影和Markdown

#### UI_001 归档会话可发现、只读且不默认抢占新选择

- 用例编号：UI_001
- 对应测试点：TP-THR-05：归档不删除历史且仍可读取；TP-THR-07：取消归档恢复活跃列表资格；TP-REC-01：工作台刷新后以服务端恢复Thread/Branch/消息和Run
- 用例标题：归档会话可发现、只读且不默认抢占新选择
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-01）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实Chromium同源页；本例有一个归档和一个普通会话，均含历史。
- 测试数据要求：无已存选择偏好、已存有效归档选择两组；独立浏览器context。
- 测试流程：1）从页面归档并查看列表/历史/输入状态；2）无偏好重开；3）带归档偏好重开后取消归档。
- 预期结果：归档可辨识和打开、历史可读且禁止新写；无偏好默认不选归档项；有效已存归档选择可恢复只读，取消归档后可继续。当前代码是混排并标“已归档”，无独立归档页；必须对照PRD“归档列表”记录呈现差异，不捏造筛选控件或直接宣称完全一致。
- 优先级：P0
- 用例类型：功能/恢复/产品差异
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。页面归档保留历史并禁写；无偏好未选归档项，有效归档偏好恢复只读；取消归档可继续。界面为混排标识，未提供独立归档筛选页；PRD归档列表呈现差异见[缺陷报告WS-DEF-001](缺陷报告.md#2-ws-def-001归档会话呈现未完全符合prd)，本例通过不表示该差异已修复。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_002 刷新按服务端重建已完成会话并处理失效偏好

- 用例编号：UI_002
- 对应测试点：TP-REC-01：工作台刷新后以服务端恢复Thread/Branch/消息和Run
- 用例标题：刷新按服务端重建已完成会话并处理失效偏好
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-01）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实浏览器；本例创建父子分支和不同终态Run，保存已提交身份。
- 测试数据要求：有效Thread/Branch、已删除或不存在ID、损坏localStorage、不可写storage变体。
- 测试流程：1）选中分支后整页刷新/关闭重开；2）比对列表、消息、最近Run与服务端；3）注入失效身份偏好再打开。
- 预期结果：有效偏好只提示选择，正文/顺序/终态从服务端恢复；失效偏好回落到有效服务端结果且不串数据；storage失败不阻断会话。当前只展示active/recent Run，不要求不存在的任意历史Run选择器，旧Run由API核对。
- 优先级：P0
- 用例类型：恢复/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。刷新后正文/Run来自服务端；不存在的Thread偏好回落有效会话；损坏模型偏好和不可写Storage未阻断页面。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_003 刷新活动Run补建草稿但不重复写入或取消

- 用例编号：UI_003
- 对应测试点：TP-REC-02：刷新非终态Run恢复观察而非重复提交或取消
- 用例标题：刷新活动Run补建草稿但不重复写入或取消
- 设计可验证状态：E：原矩阵暂不可验证（TP-REC-02）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实浏览器及定向慢Provider；独立queued/running/retry_waiting样本。
- 测试数据要求：已提交delta含REFRESH_DRAFT；浏览器清除内存状态但保留身份偏好。
- 测试流程：1）各状态整页刷新；2）捕获请求并补放持久事件；3）释放Provider至终态，比较PG计数与页面。
- 预期结果：不发重复message/retry/cancel；Run/Task/input身份稳定；整页刷新需从0或等价完整持久重建草稿，不能只从丢失的内存seq之后显示半段；自动新attempt草稿与旧代分离，最终消息只显示一次。
- 优先级：P0
- 用例类型：恢复/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。queued/running/retry_waiting三个独立样本刷新均沿用原Run/Task/input；running草稿由Journal完整重建，无重复业务POST，每组最终唯一assistant。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_004 短断线重连按连续序去重并有人工恢复入口

- 用例编号：UI_004
- 对应测试点：TP-EVT-04：指定after_seq重连可补齐缺失事件且不重复展示；TP-EVT-06：SSE观察者断开不取消、不重启业务Run
- 用例标题：短断线重连按连续序去重并有人工恢复入口
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；真实页面观察持续Run；浏览器可定向阻断/交叠流响应，不重启业务进程。
- 测试数据要求：重复/乱序块、缺口、短断线和连续三次失败；同run+seq不同attempt。
- 测试流程：1）先应用若干事件；2）中断并恢复自动连接，注入合法交叠；3）持续失败后使用现有手动重连入口。
- 预期结果：内存连续游标不越过缺口、重连补齐且无重复可见字符；最多按0.5/1/2秒策略自动重连后提供人工恢复，不无限忙循环；断开/卸载不cancel，终态不重执行；Provider原始业务请求数不因重连增加。
- 优先级：P0
- 用例类型：恢复/异步边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。真实Journal重排/重复/缺seq2的传输注入后游标停1并重连补齐；另组三次失败后人工恢复，seq/字符无重复；同一Run/Task仅执行一次。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_005 切换后旧HTTP和SSE迟到结果不污染新作用域

- 用例编号：UI_005
- 对应测试点：TP-BR-07：会话切换后迟到响应不能污染当前工作台
- 用例标题：切换后旧HTTP和SSE迟到结果不污染新作用域
- 设计可验证状态：E：原矩阵暂不可验证（TP-BR-07）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；两个Thread及同Thread兄弟分支，各有不同消息/错误/Context；浏览器网络屏障。
- 测试数据要求：A的详情/Run/context/events响应延迟，切到B再释放；分别制造成功与失败旧响应。
- 测试流程：1）选A并挂起响应；2）切Thread或Branch到B；3）释放A并对照B的消息、错误、草稿、引用与选中身份。
- 预期结果：scope/epoch丢弃旧作用域结果；B不显示A的任何投影或错误，不改变B选择；A业务仍可后台完成；旧响应不能触发B的cancel/补写或清空B最新结果。
- 优先级：P0
- 用例类型：隔离/异步竞态
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。跨Thread及同Thread兄弟路径两种作用域、五层接口、迟到成功/失败共20组网络屏障；B选择、消息、错误和身份均不被旧A响应覆盖。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_006 上下文处理提示与安全计划范围一致

- 用例编号：UI_006
- 对应测试点：TP-CTX-08：裁剪/摘要提示面向用户且不暴露Prompt全文
- 用例标题：上下文处理提示与安全计划范围一致
- 设计可验证状态：E：原矩阵暂不可验证（TP-CTX-08）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实页面；本例三组Run分别无裁剪、裁剪、摘要，并有预算超限变体。
- 测试数据要求：四预算、omitted_ranges、summary来源范围/策略；Prompt全文负哨兵。
- 测试流程：1）触发规划并等待context事件；2）读取页面ContextNotice及服务端详情；3）刷新和切换后再核对。
- 预期结果：显示实际预算、裁剪/摘要数量及受影响范围，超限明确；每项来自当前Run计划而非本地猜测；不显示Prompt/summary_text/证据全文或原始凭据；旧Run提示不残留到新作用域。
- 优先级：P0
- 用例类型：可观察性/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。无裁剪/只裁剪/摘要/预算超限四组实际规划与刷新DOM逐项对应四预算、数量、来源范围和策略；提示未暴露历史/摘要/证据全文。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_007 时间线展示可追溯的真实阶段和操作状态

- 用例编号：UI_007
- 对应测试点：TP-UI-01：时间线按Run和Event序展示真实执行阶段
- 用例标题：时间线展示可追溯的真实阶段和操作状态
- 设计可验证状态：E：原矩阵暂不可验证（TP-UI-01）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实浏览器；成功/失败/自动重试/取消四组独立Run，以现有active/recent展示。
- 测试数据要求：服务端真实Journal序列；queued、started、检索、delta、retry、cancelling和终态。
- 测试流程：1）逐场景观察时间线与状态控件；2）对照REST事件run_id/seq；3）切换到另一会话再回读。
- 预期结果：事件按真实Run和seq展示，能区分自动重试、停止中和终态；不得定时器伪完结或显示CoT/虚假工具轨迹；没有历史Run选择器不借假控件覆盖，历史事实由API验收并记录UI能力边界。
- 优先级：P0
- 用例类型：功能/可观察性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。成功/永久失败/自动重试/取消四组真实时间线全部按Run/seq对应Journal，attempt/generation和终态明确，切换后恢复正确；无隐藏思维或虚构工具。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_008 Markdown原文与流式及最终DOM分离

- 用例编号：UI_008
- 对应测试点：TP-MD-01：常见Markdown语法渲染且保存原文
- 用例标题：Markdown原文与流式及最终DOM分离
- 设计可验证状态：E：原矩阵暂不可验证（TP-MD-01）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实页面，受控Provider可返回分段Markdown；用户与assistant分别覆盖。
- 测试数据要求：标题、段落、列表、合法链接、行内码、代码块、中英文/换行；代码围栏跨delta，首尾空白。
- 测试流程：1）提交用户Markdown并流式输出另一段；2）在未闭合/闭合围栏时观察DOM；3）完成后与API/PG正文比对。
- 预期结果：结构可读、代码块不误执行；持久原文不被HTML替换；后端合法用户原文保留但普通页面发送按trim行为，assistant最终strip规范化可与草稿边缘空白不同；最终内容不重复且与保存正文对应。
- 优先级：P0
- 用例类型：功能/边界/渲染
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。用户及assistant Markdown在真实DOM呈现标题/列表/链接/行内码/跨delta代码块；最终只有一条回答，持久层保留Markdown原文。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_009 不可信Markdown在真实DOM中不能执行

- 用例编号：UI_009
- 对应测试点：TP-MD-02：恶意Markdown不能执行脚本或危险链接
- 用例标题：不可信Markdown在真实DOM中不能执行
- 设计可验证状态：E：原矩阵暂不可验证（TP-MD-02）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；隔离浏览器context，不访问公网；捕获执行哨兵/导航/网络请求/弹窗。
- 测试数据要求：用户与模型两方向script、onerror/onclick、SVG、javascript:及data:text/html/HTML注入载荷；合法代码展示作对照。
- 测试流程：1）在流式和完成态分别渲染载荷；2）等待实际事件触发并尝试危险链接操作；3）检查DOM属性/协议与执行哨兵。
- 预期结果：脚本、危险属性/协议不能执行，DOMPurify安全规则生效；允许的普通Markdown仍可读；不是只做字符串contains断言；原始载荷仅作为合成文本事实，不反写为可信HTML。
- 优先级：P0
- 用例类型：安全/XSS
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。用户及assistant两方向恶意文本持久原文不变；真实流式/最终DOM无脚本、事件属性或危险协议，执行哨兵/弹窗均未触发。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_009.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_009.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_009.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_010 切换后不显示旧引用或旧草稿

- 用例编号：UI_010
- 对应测试点：TP-RAG-03：Thread/Branch切换不显示旧Citation或旧增量
- 用例标题：切换后不显示旧引用或旧草稿
- 设计可验证状态：E：原矩阵暂不可验证（TP-RAG-03）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实页面；A有合法Citation，B无证据，C有不同Evidence；可延迟旧Run详情和流。
- 测试数据要求：A/B/C的document/chunk/batch身份及唯一回答哨兵。
- 测试流程：1）A流中切到B/C并延迟释放A；2）展开当前引用；3）再切回A核对各自事实。
- 预期结果：B没有A引用，C仅显示C实际证据/位置，旧delta/错误不串线；展开详情可追溯当前Message和Run；返回A可恢复A自己的事实，不通过全局清空旧历史掩盖污染。
- 优先级：P0
- 用例类型：隔离/异步竞态
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。A真实草稿/引用切到无引用B后均不残留，再切C仅显示其实际Message引用集合；同owner合法共享检索不误判为缓存串线。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_010.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_010.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_010.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_011 页面模型选择、运行禁用和恢复偏好真实有效

- 用例编号：UI_011
- 对应测试点：TP-MOD-01：Profile列表展示多个可用项和唯一默认选择；TP-MOD-02：禁用或不完整Profile不得用于新Run且不静默回退
- 用例标题：页面模型选择、运行禁用和恢复偏好真实有效
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；真实页面四Profile，另有一个不可用项；可控制Run停顿。
- 测试数据要求：选择HTTP A/B、有效/失效模型偏好、运行时选择控件状态。
- 测试流程：1）新Run前选择B并发问；2）运行中查看控件禁用；3）终态后切A再发；4）带无效偏好重开。
- 预期结果：页面显示实际选项与请求中的成对ID/version一致；不可用项不能用于新Run且安全说明可见；活动Run选择受限且不改其Snapshot；无效偏好回默认，密钥不进入localStorage。
- 优先级：P0
- 用例类型：功能/状态边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。B实际执行与运行禁用、终态换A新Run、有效/失效模型偏好及真实PG禁用Profile的页面不可选说明均已验证；未存凭据。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_011.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_011.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_011.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_012 Run动作按钮按真实状态发出唯一业务操作

- 用例编号：UI_012
- 对应测试点：TP-RUN-06：用户显式retry创建可追溯的新Run并保留旧结果；TP-RUN-07：已成功回答重新生成进入独立路径且保留旧回答；TP-CAN-02：running取消保持cancelling直到Worker确认
- 用例标题：Run动作按钮按真实状态发出唯一业务操作
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例独立建立failed/cancelled/succeeded/running来源；各有可用Profile。
- 测试数据要求：重试/重新生成/停止、连续点击和操作请求延迟；来源模型与手动新选择。
- 测试流程：1）按各状态操作现有按钮；2）观察请求、pending禁用和随后返回的Run/Branch；3）停止中等待服务端确认。
- 预期结果：只显示状态允许动作；重复点击不能创建额外操作；retry/regenerate默认沿来源Profile，手动切换按选择，且保留旧结果；停止先显示cancelling而非伪终态；归档只读不露可写关联动作。
- 优先级：P0
- 用例类型：功能/状态边界/幂等
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。succeeded/failed/cancelled/running四来源按钮实际执行；响应挂起时pending禁用阻止重复操作，默认沿源模型/手动切换生效；停止先cancelling，归档隐藏关联写动作。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_012.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_012.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_012.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_013 页面分叉与历史加载保留正确路径

- 用例编号：UI_013
- 对应测试点：TP-BR-01：从有效历史消息位置创建 Branch；TP-BR-02：Branch 读取包含共同祖先且不复制祖先事实；TP-THR-03：Thread 详情与消息历史读取
- 用例标题：页面分叉与历史加载保留正确路径
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；真实页面；足够历史触发“加载更早消息”，父子有不同后缀。
- 测试数据要求：选择一个持久用户/assistant消息分叉，临时projection消息作负对照。
- 测试流程：1）加载更早消息并点击“从此处分支”；2）通过现有分支选择器切父/子；3）刷新后再读。
- 预期结果：旧页与新页合并无重复，所选锚点身份正确，共同前缀只呈现一次；临时projection不能分叉；父后缀不进入子路径，选中分支刷新可恢复；归档不能分叉。
- 优先级：P0
- 用例类型：功能/分支/分页
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。真实页面以持久用户消息分叉，共同祖先只呈现一次，父未来后缀未进入子路径；刷新恢复所选分支。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_013.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_013.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_013.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### UI_014 提交结果未知时在当前页面重放原操作

- 用例编号：UI_014
- 对应测试点：TP-RUN-01：新消息Run原子创建与幂等重放；TP-RUN-08：显式retry/regenerate操作幂等且来源身份不变
- 用例标题：提交结果未知时在当前页面重放原操作
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；真实页面；网络屏障在服务端接受消息或关联操作后丢弃响应，页面不整页刷新。
- 测试数据要求：原正文/模型/幂等键和随后被修改的输入或选择；分别测消息和retry/regenerate。
- 测试流程：1）使已接受响应丢失；2）观察“重试原提交/原操作”；3）使用恢复入口并查PG对象计数。
- 预期结果：重放保留原键和原规范请求，不用新正文/模型制造冲突或重复Run；返回原身份并恢复观察；pending仅内存，整页刷新不承诺跨页保存未知写入原键，不能写出当前未实现的持久待提交保证。
- 优先级：P0
- 用例类型：异常/幂等/交互恢复
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。message及retry/regenerate三类已接受响应丢失后均重放原键/规范请求；编辑正文或改模型不替换原操作，不重复创建业务身份。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/workspace/UI_014.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/workspace/UI_014.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'workspace'`；等待入口退出，再查新run_id的`categories/workspace/UI_014.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.6 compatibility：契约、旧数据和迁移

#### COMP_001 v2十五个正式入口与契约包装一致

- 用例编号：COMP_001
- 对应测试点：TP-THR-03：Thread 详情与消息历史读取；TP-EVT-02：状态事件和回答增量按持久事实投影；TP-OBS-02：Run、Thread、Branch、Task与Event身份可关联
- 用例标题：v2十五个正式入口与契约包装一致
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例分别产生合法对象与各状态源；契约直接从当前contracts加载，不用已删除样本文件。
- 测试数据要求：接口文档§7.1所列15个方法/路径的成功、业务错误与安全422样本；SSE按版本校验。
- 测试流程：1）逐个调用models、Thread列表/创建/详情/PATCH、Branch列表/创建、消息、Run详情/Event/SSE/cancel/retry/regenerate/context；2）验证实际JSON和生成类型约定；3）负测额外字段。
- 预期结果：15入口均使用正式流程及精确包装，不多套data；状态码/分页字段和nullable边界正确；Request拒绝额外字段，Event选正确schema分支；接口集合审计不代替各功能例，旧字面样本工程缺口仍由QLT_002单列。
- 优先级：P0
- 用例类型：契约/兼容/补充验收
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。v2十五类正式方法/路径均实际调用并通过当前JSON Schema；SSE逐事件校验版本，额外字段422。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_002 v1九个会话入口保留旧成功契约

- 用例编号：COMP_002
- 对应测试点：TP-RUN-01：新消息Run原子创建与幂等重放；TP-EVT-01：同一Run事件seq严格递增且历史不可重排
- 用例标题：v1九个会话入口保留旧成功契约
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例仅用v1创建legacy Thread/消息并执行；默认Branch为内部事实。
- 测试数据要求：v1 Thread创建/列表/详情/重命名/消息及Run详情/Event/SSE/cancel，共九入口；原可选幂等键。
- 测试流程：1）按旧客户端请求形式逐入口执行；2）以v1 Schema核对成功payload；3）对新消息做重复键及归档/忙分支保护负测。
- 预期结果：原路径/请求/成功结构不增加必填v2字段；仅列conversation_version=1；默认Branch存在但不泄露为新旧混合契约；忙/归档拒绝新写且已成功原键优先重放；旧事件不被改写。
- 优先级：P0
- 用例类型：兼容/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。v1 Thread/消息/Run/Event/SSE/cancel/archive旧响应逐项校验，无新增必填v2字段；归档后的原键返回旧身份。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_003 v1拒绝v2对象但不误封旧Run

- 用例编号：COMP_003
- 对应测试点：TP-THR-03：Thread 详情与消息历史读取；TP-SEC-02：异常响应和默认日志不泄露Prompt/堆栈/宿主路径
- 用例标题：v1拒绝v2对象但不误封旧Run
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；v2 Thread/schema2 Run，另有Thread升级后仍保留的schema1旧Run及外owner对象。
- 测试数据要求：同owner version2 Thread/schema2 Run、升级Thread上的旧Run、不可访问身份。
- 测试流程：1）从v1读/写v2对象；2）对升级Thread的旧Run读Event/SSE/cancel；3）对外owner调用相同入口。
- 预期结果：v2 Thread或schema2 Run返回409 API_VERSION_REQUIRED；旧Run按execution_schema独立守卫，仍可从v1读/取消；owner不符先404，不泄露版本；不得单凭Thread版本重标旧Run/Event。
- 优先级：P0
- 用例类型：兼容/权限/版本
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；api/test_v2_session_api.py::test_v1_all_run_endpoints_guard_schema_after_owner_before_sse。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_004 v2读取和取消legacy不虚构新模型计划

- 用例编号：COMP_004
- 对应测试点：TP-EVT-01：同一Run事件seq严格递增且历史不可重排；TP-RUN-02：持久历史在服务重建后保持原文和顺序
- 用例标题：v2读取和取消legacy不虚构新模型计划
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；迁移后legacy Thread内分别有已完成和可取消schema1 Run。
- 测试数据要求：记录原Thread版本、Snapshot、Event JSON/hash及旧模型信息缺省。
- 测试流程：1）经v2 GET详情/Run/Event/SSE/context读取；2）取消旧活动Run；3）重读Thread和旧Event。
- 预期结果：单纯读和cancel不升级Thread；Run legacy=true，model/Profile/snapshot/context_plan按契约为空，不填当前默认假历史；旧Event原schema1原样补放，不添加schema2任务字段；旧状态不投影不存在的cancelling。
- 优先级：P0
- 用例类型：兼容/事实保留
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。v2只读/取消legacy不升级Thread，模型快照/计划按契约为空，schema1事件原样补放且不改写。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_005 首次v2写旧Thread原子升级且失败不升级

- 用例编号：COMP_005
- 对应测试点：TP-RUN-01：新消息Run原子创建与幂等重放；TP-BR-08：活动Run期间拒绝禁止的Branch写操作；TP-THR-08：升级后的合法旧标题按原值兼容读取
- 用例标题：首次v2写旧Thread原子升级且失败不升级
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；每个子场景独立legacy Thread，分别无活动legacy和有活动legacy。
- 测试数据要求：PATCH元数据、Branch、新消息、retry、regenerate五种首次写；旧空/空白/首尾空白标题。
- 测试流程：1）在各自对象发首次v2写；2）用活动legacy和非法请求使写入失败；3）检查conversation_version、对象计数和原文。
- 预期结果：无活动legacy且写入成功时同事务升2；有活动legacy409 LEGACY_RUN_ACTIVE、失败全部回滚，不出现只升级无操作；无关元数据操作不重写旧标题；之后不自动降1。
- 优先级：P0
- 用例类型：兼容/原子性/异常
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：7个pytest节点；@case::test_COMP_005_007_first_write_upgrade；api/test_v2_session_api.py::test_legacy_read_no_upgrade_active_write_guard_and_title_preservation；api/test_v2_session_api.py::test_fork_identity_replay_before_archive_and_inherited_path。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_006 迁移旧标题读取与无关更新不做新写校验

- 用例编号：COMP_006
- 对应测试点：TP-THR-08：升级后的合法旧标题按原值兼容读取
- 用例标题：迁移旧标题读取与无关更新不做新写校验
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立旧revision数据含空字符串、纯空白及首尾空白title，完成正式升级。
- 测试数据要求：title三类旧合法值；归档/取消归档及显式新重命名作对照。
- 测试流程：1）读v2列表和详情；2）做无关PATCH并再读；3）显式重命名为新合法值。
- 预期结果：前两步响应和数据库保留旧字符串原值，包括Thread升2时也不trim/fallback；仅显式新重命名适用trim后1～200规则；不能为通过新Schema静默修历史。
- 优先级：P1
- 用例类型：兼容/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：10个pytest节点；@case::test_COMP_006_legacy_titles；api/test_v2_session_api.py::test_legacy_read_no_upgrade_active_write_guard_and_title_preservation；api/test_v2_schemas.py::test_thread_response_preserves_legacy_title_after_metadata_upgrade。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_007 legacy关联操作必须显式提供Profile

- 用例编号：COMP_007
- 对应测试点：TP-RUN-06：用户显式retry创建可追溯的新Run并保留旧结果；TP-RUN-07：已成功回答重新生成进入独立路径且保留旧回答；TP-MOD-02：禁用或不完整Profile不得用于新Run且不静默回退
- 用例标题：legacy关联操作必须显式提供Profile
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立legacy失败/取消/成功源，无活动冲突。
- 测试数据要求：retry/regenerate省略模型、只一半、显式启用ID/version；同键同体重放。
- 测试流程：1）先缺模型请求；2）再显式合法Profile创建关联Run；3）比较新旧schema/Thread版本与来源身份。
- 预期结果：省略为422 MODEL_PROFILE_REQUIRED，半对为安全校验错误；显式后新Run schema2且冻结所选配置，复用输入、保留schema1源；首次写成功升级Thread，同键重放不重复创建，不把旧Run伪装有新Snapshot。
- 优先级：P0
- 用例类型：兼容/契约
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：6个pytest节点；@case::test_COMP_005_007_first_write_upgrade；api/test_v2_run_api.py::test_legacy_projection_cancel_never_upgrade_and_explicit_profile。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_007.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_007.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_007.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_008 旧Demo全状态事实升级至当前head不丢失

- 用例编号：COMP_008
- 对应测试点：TP-MIG-01：旧Demo事实升级至v2迁移head后内容不丢失
- 用例标题：旧Demo全状态事实升级至当前head不丢失
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；db-admin管理独立迁移专库，从0003正式Schema准备数据，不接开发库。
- 测试数据要求：legacy不同Run/Task状态、消息/引用/Event/幂等、空标题、合成Document/Chunk及索引批次；升级前计数/稳定hash。
- 测试流程：1）完成旧库基线并导出安全清单；2）正式升级0004→0005→0006；3）逐表/字段比较并读旧API。
- 预期结果：revision为0006_v2_run_guards；源ID/原文/状态/Event/文档身份不丢失改写；默认Branch及迁移Profile仅按策略回填一次，旧Snapshot/事件不伪造升级；冲突必须停止而非取消/删除旧事实。
- 优先级：P0
- 用例类型：迁移/事实可靠性
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：2个pytest节点；@migration::test_COMP_008_documents_chunks_roundtrip；unit/test_v2_session_migrations.py::test_mixed_legacy_states_preserve_full_fact_hash_and_counts。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_008.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_008.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_008.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_009 不兼容旧数据在迁移写入前被拒绝

- 用例编号：COMP_009
- 对应测试点：TP-MIG-04：迁移冲突预检失败时不改动源业务事实
- 用例标题：不兼容旧数据在迁移写入前被拒绝
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立0003冲突库，逐类复用migrations/v2_session_checks.preflight规则与现有测试数据。
- 测试数据要求：重复工作/重复操作、活动状态冲突、不兼容关联等每种可识别冲突，分别建库。
- 测试流程：1）记录revision/结构/事实hash；2）执行正式升级至首个v2 revision；3）读错误与新快照。
- 预期结果：安全诊断明确冲突类型；失败前后revision、原结构及源事实不变，无静默cancel、删除或半回填；不能绕过预检用stamp制造可升级结论。
- 优先级：P0
- 用例类型：迁移/异常/风险
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：11个pytest节点；unit/test_v2_session_migrations.py::test_preflight_identifies_conflicts_without_rewriting_facts；unit/test_v2_session_migrations.py::test_preflight_rejects_duplicate_work_without_cancel_or_delete；unit/test_v2_session_migrations.py::test_upgrade_preflight_preserves_revision_and_original_facts。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_009.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_009.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_009.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_010 重复upgrade head不重复回填

- 用例编号：COMP_010
- 对应测试点：TP-MIG-03：重复执行升级保持迁移revision和业务事实不变
- 用例标题：重复upgrade head不重复回填
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本例独立旧库完成首次正式升级，记录全业务与迁移回填hash。
- 测试数据要求：同库连续两次upgrade head；含默认Branch/Profile和legacy事实。
- 测试流程：1）再次运行正式升级；2）比较revision及各表身份/计数/hash；3）以API重新读取原会话。
- 预期结果：head保持不变，无重复Branch/Profile/业务事实或旧内容变化；重复操作成功不代表可任意重写迁移历史；两次结果留独立命令证据。
- 优先级：P0
- 用例类型：迁移/幂等
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：1个pytest节点；unit/test_v2_session_migrations.py::test_legacy_backfill_repeat_and_safe_roundtrip。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_010.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_010.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_010.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_011 无v2业务事实时受保护回退可安全往返

- 用例编号：COMP_011
- 对应测试点：TP-MIG-02：v2事实存在时降级预检在删结构前拒绝
- 用例标题：无v2业务事实时受保护回退可安全往返
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立升级后的legacy专库，未引入任何v2业务事实；只有迁移默认Branch/Mock基线。
- 测试数据要求：目标0003；另备仅有人工Profile但无其他v2事实的独立样本。
- 测试流程：1）先验证降级预检；2）对支持样本回退0003并再升级head；3）对人工Profile样本先观察拒绝，再按显式导出管理流程处理。
- 预期结果：支持路径源事实与hash往返保持；人工Profile未显式导出/处理前以CUSTOM_PROFILE_EXPORT_REQUIRED拒绝自动删配置；不降base、不手工stamp、不以恢复空库代替回退验证。
- 优先级：P0
- 用例类型：迁移/回退/风险
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：3个pytest节点；unit/test_v2_session_migrations.py::test_legacy_backfill_repeat_and_safe_roundtrip；unit/test_v2_session_migrations.py::test_custom_profile_downgrade_requires_explicit_export。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_011.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_011.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_011.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_012 存在任何v2事实时拒绝有损回退

- 用例编号：COMP_012
- 对应测试点：TP-MIG-02：v2事实存在时降级预检在删结构前拒绝
- 用例标题：存在任何v2事实时拒绝有损回退
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；每类阻止条件独立专库，记录降级前revision/结构/hash。
- 测试数据要求：子Branch、version2 Thread、schema2 Run、ContextPlan/Summary、SessionOperation、多Run共享输入等；禁止base请求作额外负例。
- 测试流程：1）逐库请求降级至0003；2）核对guard_downgrade诊断；3）再次读取所有业务及结构。
- 预期结果：在删结构前拒绝V2_BUSINESS_FACTS等对应错误；数据/表/revision不变；base明确禁止。真实存在v2事实只允许向前修复或经批准恢复备份，不能为测试强删事实骗过guard。
- 优先级：P0
- 用例类型：迁移/数据安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。已执行：8个pytest节点；@migration::test_COMP_012_independent_context_facts_guard；unit/test_v2_session_migrations.py::test_downgrade_rejects_every_session_business_fact；unit/test_v2_session_migrations.py::test_v2_migration_chain_refuses_base_downgrade_even_empty。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_012.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_012.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_012.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### COMP_013 保留文档索引与健康入口而不新增平行聊天

- 用例编号：COMP_013
- 对应测试点：TP-RAG-01：最终Citation只引用该Run实际选择的Evidence；TP-DEP-01：正式Compose服务迁移/健康/Worker readiness顺序正确
- 用例标题：保留文档索引与健康入口而不新增平行聊天
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；API路由注册表可审计，含文本上传/索引正常基线。
- 测试数据要求：v1 documents上传/列表/index三入口及health live/ready；v2会话工作台请求轨迹。
- 测试流程：1）上传/索引合成txt/md/docx并查询；2）读健康；3）审计v2路由和前端请求。
- 预期结果：文档与健康旧入口继续可用且契约保留；没有v2同义documents/index/health/archive或绕开Thread/Run的新chat接口；工作台会话走v2，文档/健康仍走约定入口；本例只做本轮兼容回归，不恢复旧PRD全验收套件。
- 优先级：P1
- 用例类型：兼容/部署/范围
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。txt/md/docx经正式v1上传与Worker索引成功；旧index/health继续可用，路由未新增平行v2 documents/chat/health/archive。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/compatibility/COMP_013.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/compatibility/COMP_013.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'compatibility'`；等待入口退出，再查新run_id的`categories/compatibility/COMP_013.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.7 performance：本机响应性

#### PERF_001 单用户提交API的完整样本p95不超过1秒

- 用例编号：PERF_001
- 对应测试点：TP-PERF-01：单用户Run提交API p95≤1秒
- 用例标题：单用户提交API的完整样本p95不超过1秒
- 设计可验证状态：E：原矩阵暂不可验证（TP-PERF-01）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；单用户/单Worker，DB健康，预热结束，无索引或其他压测；源码/镜像/资源配置冻结。
- 测试数据要求：至少30个独立合法提交，分别使用新Thread/当前空闲Branch及独立键；逐条记录单调开始/结束时刻、状态码、身份。
- 测试流程：1）记录资源/预热和健康证据；2）依次提交，前一Run离开活动状态后再下一次；3）按全部N样本排序取第ceil(0.95×N)项，保存原始样本。
- 预期结果：每次提交返回正确Run身份；p95≤1000ms。慢/失败样本不能删除、重试替换或只保成功样本；有失败必须单独判功能/环境问题，不能以低p95宣布验收通过。测量不包含等模型答案的时间。
- 优先级：P1
- 用例类型：性能/边界
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。完整30样本提交API p95=31.65ms；所有提交均返回合法身份；未删除慢样本；R1输出：完整30样本提交API p95=29.62ms；所有提交均返回合法身份；未删除慢样本。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/performance/PERF_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/performance/PERF_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'performance'`；等待入口退出，再查新run_id的`categories/performance/PERF_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### PERF_002 首个持久delta到DOM延迟按保守区间判断

- 用例编号：PERF_002
- 对应测试点：TP-PERF-02：已提交首个delta到DOM可见≤1秒
- 用例标题：首个持久delta到DOM延迟按保守区间判断
- 设计可验证状态：E：原矩阵暂不可验证（TP-PERF-02）；当前本机具备基础条件，专门编排待实施。
- 前置条件：P0-ENV；真实PG READ COMMITTED新快照、浏览器同源页、受控Provider屏障；已订阅且时钟校准；单用户/Worker。
- 测试数据要求：至少30个独立首delta样本；每样本L取PG最后未见查询的开始时刻、U取首次可见查询的结束时刻（均映射到宿主单调时钟），另记录DOM首次显示区间[D低,D高]及校准误差。
- 测试流程：1）确认订阅就绪后释放首片；2）每次查询新快照并保留发起/结束时间以保守夹住提交，浏览器连续观察DOM并校准到同一时基；3）逐样本算延迟区间[max(0,D低−U),max(0,D高−L)]，不能以最后未见查询的结束或首次可见查询的开始缩窄区间。
- 预期结果：每个有效样本上界≤1000ms才满足目标，下界>1000ms判失败，交叠为测量不足需改善测量而非通过；保留所有样本和误差。不能用Event.occurred_at/事务开始时间替commit，不复用旧快照，不把上游首token等待计入或拿平均数替代阈值。
- 优先级：P1
- 用例类型：性能/时序/测量风险
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。保留30个独立首delta区间：通过30、失败0、测量交叠受限0。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/performance/PERF_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/performance/PERF_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'performance'`；等待入口退出，再查新run_id的`categories/performance/PERF_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

### 3.8 quality：可测试性、部署和门禁

#### QLT_001 受控Provider按场景与屏障记录安全实收

- 用例编号：QLT_001
- 对应测试点：TP-TEST-01：本地受控Provider能按场景输出并记录安全请求摘要
- 用例标题：受控Provider按场景与屏障记录安全实收
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；独立推理/控制端口和虚假认证；浏览器无控制token权限。
- 测试数据要求：normal/slow/stall/empty/malformed/disconnect/context-limit/http-error；按请求序号定向两条不同模型请求。
- 测试流程：1）逐场景设置并发起真实产品请求；2）在收到/首片/等待释放/完成屏障观测；3）检查角色/长度/hash/哨兵和观察容量标志。
- 预期结果：可重复控制而不串请求场景；实收可追溯Run输入，观测无Key/完整Prompt；超容量明确截断不能被当完整证明；测试侧协议失败需单列，不算产品失败。Provider自测通过也不替代其余产品用例。
- 优先级：P1
- 用例类型：可测试性/功能
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。8种场景均通过正式API/Worker实际调用并核对终态；stall屏障定向释放，安全实收观测未截断或泄露凭据。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_001.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_001.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_001.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### QLT_002 后端与契约质量门禁脱离旧验收目录

- 用例编号：QLT_002
- 对应测试点：TP-TEST-02：API契约字面样本测试不依赖已移除旧验收目录
- 用例标题：后端与契约质量门禁脱离旧验收目录
- 设计可验证状态：E：原QGAP-01受限；任务1～2已补稳定样本和依赖，当前本机可验证，尚未执行本例。
- 前置条件：使用tests/api/fixtures/v2-contract-samples.json及已改引用的tests/api/test_v2_schemas.py；安装jsonschema[format-nongpl]，确保日期格式检查生效。不恢复旧验收目录；仍须后续quality分类执行本例完整质量命令与坏样本反例。
- 测试数据要求：合法/非法字面样本及与backend DTO对应样本；当前源码和锁定Python测试依赖；Ruff/mypy/pytest与契约漂移检查范围。
- 测试流程：1）解除缺口后在干净工具环境运行后端质量命令及固定样本测试；2）验证所有文件来自现仓库；3）注入一个坏样本确认门禁真实失败后恢复。
- 预期结果：样本测试必须到达DTO/JSON Schema断言且不读取旧目录；全量质量命令结果逐项报告，缺fixture/依赖/命令是工程blocked或failed，不是产品通过；退出0空报告不能通过。工具准备阶段的契约测试通过不替代本例完整质量验收。
- 优先级：P1
- 用例类型：可测试性/契约/质量门禁
- 是否适合自动化：是（工具前置已补，待接入完整断言）
- 实际测试结果：通过（R1/R2均passed）。ruff退出0；mypy退出0；pytest退出0；bad-contract-rejected退出0。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_002.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_002.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_002.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### QLT_003 前端独立质量命令真实检查当前源码

- 用例编号：QLT_003
- 对应测试点：TP-TEST-03：前端Lint/组件质量门禁有本模块独立入口
- 用例标题：前端独立质量命令真实检查当前源码
- 设计可验证状态：E：原QGAP-02受限；任务1～2已补前端独立工具链，当前本机可验证，尚未执行本例。
- 前置条件：frontend自身的ESLint/Vitest/Vue Test Utils/jsdom与锁文件、独立eslint.config.mjs/vitest.config.ts及lint/test:unit入口已准备；不读取旧验收目录。后续quality分类仍须执行完整质量门禁及临时错误负例；三项toolchain探针不是产品组件用例。
- 测试数据要求：typecheck、build、check:api、独立lint、组件测试的锁文件工具；可被检测的类型/规则/组件错误临时变体。
- 测试流程：1）解除缺口后独立安装前端开发依赖；2）逐项运行实际命令并保存检查范围/输出；3）用临时错误确认非零退出和有效诊断后恢复。
- 预期结果：类型/生成契约无漂移，Lint/组件命令确实覆盖当前源码；缺入口不能视为通过，也不能仅用Vite build替Lint/组件测试；suite Playwright不自动补齐前端质量门禁。各子检查独立报告，工具探针通过不替代真实产品组件验证。
- 优先级：P1
- 用例类型：可测试性/质量门禁
- 是否适合自动化：是（工具前置已补，待接入完整断言）
- 实际测试结果：通过（R1/R2均passed）。check:api退出0；typecheck退出0；lint退出0；test:unit退出0；build:types退出0；build:vite退出0；negative-type-rejected退出0；negative-lint-rejected退出0；negative-component-rejected退出0。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_003.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_003.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_003.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### QLT_004 离线计数器版本及词表损坏可重复诊断

- 用例编号：QLT_004
- 对应测试点：TP-TEST-04：TokenCounter固定版本且离线可重复加载；TP-CTX-05：摘要失败回退和Tokenizer故障语义可区分
- 用例标题：离线计数器版本及词表损坏可重复诊断
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；固定tiktoken 0.8.0/cl100k_base预热资产；只在独立工具容器副本删除/损坏词表，禁止破坏共享缓存。
- 测试数据要求：相同Profile/输入重复计数、已知hash词表；缓存缺失/损坏、消息/请求overhead变体。
- 测试流程：1）断公网保留私网后重复计数；2）核对counter身份及预算；3）在独立副本制造缺损并观察网络尝试和错误。
- 预期结果：相同配置计数稳定且包含冻结协议开销；缺损明确失败，不运行时联网下载、不用字符数或Mock替代真实Profile计数；不被摘要回退吞没，公开响应不泄露资产宿主路径。
- 优先级：P0
- 用例类型：可测试性/边界/离线
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。离线TokenCounter/上下文固定节点退出0；缺失/损坏缓存负例包含禁止网络访问断言。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_004.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_004.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_004.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### QLT_005 干净部署至采证清理形成独立闭环

- 用例编号：QLT_005
- 对应测试点：TP-DEP-01：正式Compose服务迁移/健康/Worker readiness顺序正确
- 用例标题：干净部署至采证清理形成独立闭环
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV的前置准备工具已就绪；生命周期由总入口控制，不触碰开发项目；本例分类侧只观察本轮资源/报告，不自行递归启动或销毁Compose。
- 测试数据要求：全新卷、四Profile、唯一run_id/owner；正常结束、主动分类失败/超时两组生命周期。
- 测试流程：1）总入口部署，分类侧核验migrate/Profile/API/Worker/前端和health并写只读观察；2）分别完成正常/受控失败运行；3）总入口finally清理后，由生命周期外层校验器汇总cleanup与独立资源扫描证据。
- 预期结果：正式迁移head正确、worker_count≥1且依赖真实就绪；完整闭环判定必须等总入口最终报告和残留审计，不能由尚未清理的分类进程提前宣布通过；正常和异常路径均采脱敏报告，清理失败非零并留恢复账本。只保留明示artifacts/依赖缓存/共享基础层，不全局prune。
- 优先级：P1
- 用例类型：部署/恢复/资源
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。正常分类、全新环境分类主动失败、全新环境分类超时三条路径均采证并在finally清理；分类及全轮独立审计通过，容器/网络/卷/专有tag/runtime/tmp无残留，源码未变。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_005.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_005.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_005.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

#### QLT_006 Secret仅运行时注入而不进镜像或版本文件

- 用例编号：QLT_006
- 对应测试点：TP-DEP-02：Profile Secret不进入镜像、前端构建产物或版本控制
- 用例标题：Secret仅运行时注入而不进镜像或版本文件
- 设计可验证状态：V：当前本机可验证，脚本/执行待后续完成。
- 前置条件：P0-ENV；本轮独立构建/运行；不同虚假Secret哨兵和镜像ID可追溯，构建前后仓库清单可核对。
- 测试数据要求：Dockerfile/构建上下文/层与history、前端dist、Git跟踪文件、受版本控制Compose/模板、公开报告。
- 测试流程：1）按正常入口构建并注入运行Key；2）扫描以上持久/公开面；3）检查运行时仅服务端获得必要值。
- 预期结果：Secret不在镜像层/构建参数/dist/Git/公开报告中；不公开含环境值的inspect或resolved Compose。私有runtime插值和后端运行环境按需要含虚假值不是失败，但必须受控并清理；不能为扫描删掉必要注入导致产品根本没运行。
- 优先级：P0
- 用例类型：部署/安全
- 是否适合自动化：是
- 实际测试结果：通过（R1/R2均passed）。镜像归档扫描25288个成员、Git跟踪文件311份，frontend/dist及公开artifact亦纳入扫描，凭据命中0；helper合计扫描504次（artifact+Git+dist，非504份公开证据）；R1输出：相同扫描边界的helper合计507次、凭据命中0；原日志计数标签问题见[WS-DEF-004](缺陷报告.md#5-ws-def-004秘密扫描日志的统计名称不准确)。证据：[R1](artifacts/ws-20261023t020902z-9fa22610/categories/quality/QLT_006.json)、[R2](artifacts/ws-20261023t030707z-c936fff7/categories/quality/QLT_006.json)，完整断言/关联日志见各轮同目录result.json。
- 复现步骤：本次实际执行§1.3两条All命令；定向复现：`pwsh -NoProfile -File tests/sesrag-persistent-session-workspace-test/run-workspace-tests.ps1 -Mode Selected -Categories 'quality'`；等待入口退出，再查新run_id的`categories/quality/QLT_006.json`及result.json（执行整类，包含本例）。
- 测试结果是否稳定出现：是：两轮同源均passed；表示判定一致，不要求身份、时间或性能数值相同。

## 4. 覆盖矩阵

### 4.1 分类规模和用例主归属

| 分类 | 用例范围 | 数量 |
| --- | --- | --- |
| session | SES_001～SES_018 | 18 |
| context | CTX_001～CTX_013 | 13 |
| model | MOD_001～MOD_008 | 8 |
| run | RUN_001～RUN_030 | 30 |
| workspace | UI_001～UI_014 | 14 |
| compatibility | COMP_001～COMP_013 | 13 |
| performance | PERF_001、PERF_002 | 2 |
| quality | QLT_001～QLT_006 | 6 |

合计104个唯一用例；前置/流程中提到其他用例只用于解释断言分工，不形成执行先后依赖。以下覆盖表是设计追溯，不是通过率或执行证据。

### 4.2 全部84个测试点到用例

原矩阵状态保留为历史快照；V/E/B按§1.1解释。一个测试点可能需要数据/事务层与DOM层不同用例共同取证，不因已有一个断言就省略另一层。

| 测试点 | 测试目标 | 覆盖用例 | 状态校准 |
| --- | --- | --- | --- |
| TP-THR-01 | 创建 Thread 并初始化默认 Branch | SES_001 | V：原可验证，现仍可设计本机验证 |
| TP-THR-02 | Thread 列表排序与游标分页 | SES_002、SES_003 | V：原可验证，现仍可设计本机验证 |
| TP-THR-03 | Thread 详情与消息历史读取 | SES_004；UI_013；COMP_001、COMP_003 | V：原可验证，现仍可设计本机验证 |
| TP-THR-04 | Thread 新标题输入边界校验 | SES_005 | V：原可验证，现仍可设计本机验证 |
| TP-THR-08 | 升级后的合法旧标题按原值兼容读取 | COMP_005、COMP_006 | V：原可验证，现仍可设计本机验证 |
| TP-THR-05 | 归档不删除历史且仍可读取 | SES_006；UI_001 | V：原可验证，现仍可设计本机验证 |
| TP-THR-06 | 归档 Thread 的新写操作受拒绝 | SES_007 | V：原可验证，现仍可设计本机验证 |
| TP-THR-07 | 取消归档恢复活跃列表资格 | SES_008；UI_001 | V：原可验证，现仍可设计本机验证 |
| TP-BR-01 | 从有效历史消息位置创建 Branch | SES_009；UI_013 | V：原可验证，现仍可设计本机验证 |
| TP-BR-02 | Branch 读取包含共同祖先且不复制祖先事实 | SES_010；UI_013 | V：原可验证，现仍可设计本机验证 |
| TP-BR-03 | 同一Thread兄弟与嵌套Branch路径隔离 | SES_011；CTX_007 | V：原可验证，现仍可设计本机验证 |
| TP-BR-04 | Thread 间消息、摘要与运行上下文隔离 | CTX_002 | V：原可验证，现仍可设计本机验证 |
| TP-BR-05 | 非法/越权分叉锚点与路径约束拒绝 | SES_012、SES_013、SES_017 | V：原可验证，现仍可设计本机验证 |
| TP-BR-06 | 使用过期expected_version提交时拒绝推进Branch Head | SES_014 | V：原可验证，现仍可设计本机验证 |
| TP-BR-07 | 会话切换后迟到响应不能污染当前工作台 | UI_005 | E：原ENV受限，现具备基础条件 |
| TP-BR-08 | 活动Run期间拒绝禁止的Branch写操作 | SES_015；COMP_005 | V：原可验证，现仍可设计本机验证 |
| TP-BR-09 | 并发消息和分支创建遵守PostgreSQL Head锁序 | SES_016 | E：原ENV受限，现具备基础条件 |
| TP-RUN-01 | 新消息Run原子创建与幂等重放 | SES_018；RUN_001；UI_014；COMP_002、COMP_005 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-02 | 持久历史在服务重建后保持原文和顺序 | RUN_014；COMP_004 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-03 | 流式delta在完成前不构成最终assistant Message | RUN_002 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-04 | 最终assistant Message与Run成功终态共同提交 | RUN_003 | E：原ENV受限，现具备基础条件 |
| TP-RUN-05 | Worker自动重试沿用同一Run/输入且不拼接尝试增量 | RUN_004 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-06 | 用户显式retry创建可追溯的新Run并保留旧结果 | RUN_005；UI_012；COMP_007 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-07 | 已成功回答重新生成进入独立路径且保留旧回答 | RUN_006；UI_012；COMP_007 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-08 | 显式retry/regenerate操作幂等且来源身份不变 | RUN_007；UI_014 | V：原可验证，现仍可设计本机验证 |
| TP-RUN-09 | 同一Branch的既有对话进入后续Run上下文 | CTX_001 | V：原可验证，现仍可设计本机验证 |
| TP-MOD-01 | Profile列表展示多个可用项和唯一默认选择 | MOD_001；UI_011 | V：原可验证，现仍可设计本机验证 |
| TP-MOD-02 | 禁用或不完整Profile不得用于新Run且不静默回退 | MOD_002、MOD_005；UI_011；COMP_007 | V：原可验证，现仍可设计本机验证 |
| TP-MOD-03 | RunSnapshot冻结Profile版本与执行配置 | MOD_003、MOD_004、MOD_008 | V：原可验证，现仍可设计本机验证 |
| TP-MOD-04 | Secret不进入Snapshot、Profile响应和模型调用观测公开面 | MOD_006 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-01 | 同一Run事件seq严格递增且历史不可重排 | RUN_008；COMP_002、COMP_004 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-02 | 状态事件和回答增量按持久事实投影 | RUN_009；COMP_001 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-03 | Provider暂停期间首个delta已持久化可查询 | RUN_010 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-04 | 指定after_seq重连可补齐缺失事件且不重复展示 | RUN_011；UI_004 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-05 | Event分页游标非法、优先级和上限符合接口契约 | RUN_012 | V：原可验证，现仍可设计本机验证 |
| TP-EVT-06 | SSE观察者断开不取消、不重启业务Run | RUN_013；UI_004 | V：原可验证，现仍可设计本机验证 |
| TP-REC-01 | 工作台刷新后以服务端恢复Thread/Branch/消息和Run | UI_001、UI_002 | E：原ENV受限，现具备基础条件 |
| TP-REC-02 | 刷新非终态Run恢复观察而非重复提交或取消 | UI_003 | E：原ENV受限，现具备基础条件 |
| TP-REC-03 | API/Worker重启后同一Run/Task按Snapshot恢复 | RUN_014、RUN_015 | E：原ENV受限，现具备基础条件 |
| TP-REC-04 | 旧Worker租约代写回被拒绝 | RUN_016 | E：原ENV受限，现具备基础条件 |
| TP-CAN-01 | queued/retry_waiting Run取消并停止后续执行 | RUN_017 | V：原可验证，现仍可设计本机验证 |
| TP-CAN-02 | running取消保持cancelling直到Worker确认 | RUN_018；UI_012 | V：原可验证，现仍可设计本机验证 |
| TP-CAN-03 | 取消与成功提交竞争只有一个终态获胜 | RUN_019、RUN_020 | E：原ENV受限，现具备基础条件 |
| TP-CAN-04 | 取消后迟到Provider结果或租约回收不能翻转终态 | RUN_021 | E：原ENV受限，现具备基础条件 |
| TP-CTX-01 | Mandatory输入、系统指令和输出预留预算边界 | CTX_003 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-02 | 超预算时按完整旧轮次顺序裁剪 | CTX_004 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-03 | ContextPlan来源和计数与实际ModelRequest一致 | CTX_005 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-04 | ConversationSummary来源范围、哈希与分支限制 | CTX_006、CTX_007 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-05 | 摘要失败回退和Tokenizer故障语义可区分 | CTX_008；QLT_004 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-06 | 上下文候选窗口上限不静默遗漏当前问题 | CTX_009 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-07 | 低优先级Evidence先于必要历史被移除 | CTX_010 | V：原可验证，现仍可设计本机验证 |
| TP-CTX-08 | 裁剪/摘要提示面向用户且不暴露Prompt全文 | UI_006 | E：原ENV受限，现具备基础条件 |
| TP-UI-01 | 时间线按Run和Event序展示真实执行阶段 | UI_007 | E：原ENV受限，现具备基础条件 |
| TP-MD-01 | 常见Markdown语法渲染且保存原文 | UI_008 | E：原ENV受限，现具备基础条件 |
| TP-MD-02 | 恶意Markdown不能执行脚本或危险链接 | UI_009 | E：原ENV受限，现具备基础条件 |
| TP-RAG-01 | 最终Citation只引用该Run实际选择的Evidence | CTX_011；MOD_008；COMP_013 | V：原可验证，现仍可设计本机验证 |
| TP-RAG-02 | 无Evidence与检索基础设施失败表现不同 | CTX_012 | V：原可验证，现仍可设计本机验证 |
| TP-RAG-03 | Thread/Branch切换不显示旧Citation或旧增量 | UI_010 | E：原ENV受限，现具备基础条件 |
| TP-ERR-01 | Provider HTTP状态按可重试性映射 | RUN_022 | V：原可验证，现仍可设计本机验证 |
| TP-ERR-02 | 空流、坏JSON、断流或缺少结束标记不能伪成功 | RUN_023 | V：原可验证，现仍可设计本机验证 |
| TP-ERR-03 | Database、Redis、检索故障与空召回区分 | RUN_024 | E：原ENV受限，现具备基础条件 |
| TP-ERR-04 | 自动重试、deadline和资源失败有界且可结算 | RUN_025、RUN_028 | V：原可验证，现仍可设计本机验证 |
| TP-SEC-01 | Secret不进入消息、Snapshot、Event和API前端响应 | MOD_006 | V：原可验证，现仍可设计本机验证 |
| TP-SEC-02 | 异常响应和默认日志不泄露Prompt/堆栈/宿主路径 | SES_017；RUN_030；COMP_003 | V：原可验证，现仍可设计本机验证 |
| TP-SEC-03 | Profile URL/参数输入拒绝凭据及未支持配置 | MOD_007 | V：原可验证，现仍可设计本机验证 |
| TP-OBS-01 | 公开运行时间线仅含白名单阶段与安全摘要 | RUN_009 | V：原可验证，现仍可设计本机验证 |
| TP-OBS-02 | Run、Thread、Branch、Task与Event身份可关联 | RUN_029；COMP_001 | V：原可验证，现仍可设计本机验证 |
| TP-OBS-03 | 上下文裁剪/摘要范围和模型Profile可观察但无正文泄露 | CTX_013 | V：原可验证，现仍可设计本机验证 |
| TP-PERF-01 | 单用户Run提交API p95≤1秒 | PERF_001 | E：原ENV受限，现具备基础条件 |
| TP-PERF-02 | 已提交首个delta到DOM可见≤1秒 | PERF_002 | E：原ENV受限，现具备基础条件 |
| TP-CAP-01 | Token输入预算和输出预留有限且按Profile冻结 | CTX_003 | V：原可验证，现仍可设计本机验证 |
| TP-CAP-02 | 流式答案长度和增量速率受限 | RUN_026 | V：原可验证，现仍可设计本机验证 |
| TP-CAP-03 | Event数量达到上限时仍可写入终态 | RUN_027 | V：原可验证，现仍可设计本机验证 |
| TP-CAP-04 | Run执行时长受deadline限制并最终结算 | RUN_028 | V：原可验证，现仍可设计本机验证 |
| TP-MIG-01 | 旧Demo事实升级至v2迁移head后内容不丢失 | COMP_008 | V：原可验证，现仍可设计本机验证 |
| TP-MIG-02 | v2事实存在时降级预检在删结构前拒绝 | COMP_011、COMP_012 | V：原可验证，现仍可设计本机验证 |
| TP-MIG-03 | 重复执行升级保持迁移revision和业务事实不变 | COMP_010 | V：原可验证，现仍可设计本机验证 |
| TP-MIG-04 | 迁移冲突预检失败时不改动源业务事实 | COMP_009 | V：原可验证，现仍可设计本机验证 |
| TP-TEST-01 | 本地受控Provider能按场景输出并记录安全请求摘要 | QLT_001 | V：原可验证，现仍可设计本机验证 |
| TP-TEST-02 | API契约字面样本测试不依赖已移除旧验收目录 | QLT_002 | E：原QGAP-01，工具前置已补，待正式执行 |
| TP-TEST-03 | 前端Lint/组件质量门禁有本模块独立入口 | QLT_003 | E：原QGAP-02，工具前置已补，待正式执行 |
| TP-TEST-04 | TokenCounter固定版本且离线可重复加载 | QLT_004 | V：原可验证，现仍可设计本机验证 |
| TP-DEP-01 | 正式Compose服务迁移/健康/Worker readiness顺序正确 | COMP_013；QLT_005 | V：原可验证，现仍可设计本机验证 |
| TP-DEP-02 | Profile Secret不进入镜像、前端构建产物或版本控制 | QLT_006 | V：原可验证，现仍可设计本机验证 |

### 4.3 产品需求到用例

覆盖PRD第6节18项FR、第8节11项NFR。对应需求的测试点范围取自矩阵§5，追溯到本文件用例；兼容补充COMP组用于防止接口更新或旧事实迁移断层。完整验收须取得各需求涉及层面的证据，不以表内任一单例通过代替整项需求。

| PRD需求 | 覆盖用例 | 验收关注 |
| --- | --- | --- |
| FR-TH-01 | SES_001～SES_008；UI_001、UI_013；COMP_001、COMP_003、COMP_005、COMP_006 | Thread创建/列表/详情/重命名及新标题边界/归档/取消归档、更新时间排序、旧标题兼容读取、历史保留与归档后写入边界。 |
| FR-TH-02 | SES_011～SES_014、SES_016、SES_017；CTX_001、CTX_002、CTX_006、CTX_007；UI_005、UI_010 | 当前Thread/Branch历史进入后续请求；两Thread/多Branch的消息、摘要、Evidence、Prompt和异步前端投影互不串用。 |
| FR-MEM-01 | SES_018；CTX_001；RUN_001～RUN_003、RUN_014、RUN_015；UI_001～UI_003、UI_014；COMP_002、COMP_004、COMP_005 | 持久事实可恢复，已完成历史实际进入后续Run上下文；delta非完成事实；最终assistant与成功终态原子一致。 |
| FR-BR-01 | SES_009～SES_017；CTX_002、CTX_007；UI_013；COMP_005 | 从历史锚点分叉、共享祖先不复制、路径正确、原分支不被覆盖、非法/过期锚点与并发边界。 |
| FR-BR-02 | RUN_004～RUN_007；UI_012、UI_014；COMP_007 | 自动attempt沿用同Run；用户重试/重生成新建关联Run；旧消息保留且操作幂等。 |
| FR-MOD-01 | MOD_001、MOD_002、MOD_005、MOD_006；UI_011；COMP_007 | 多Profile列表/选择、默认/禁用/缺配置行为、API和浏览器无Secret。 |
| FR-MOD-02 | MOD_002～MOD_006、MOD_008；UI_011；COMP_007 | RunSnapshot固定Profile版本及模型配置；Profile不可用时明确失败而不静默切换。 |
| FR-STR-01 | RUN_008～RUN_010；COMP_001、COMP_002、COMP_004 | 持久Event单调追加、状态语义真实，Provider未结束时delta已可读，终态与Message一致。 |
| FR-STR-02 | RUN_011～RUN_013；UI_003、UI_004 | 断线补放、游标分页/去重；断开只停止观察，不取消或重复执行Run。 |
| FR-REC-01 | SES_004；UI_001～UI_003、UI_007、UI_013；COMP_001、COMP_003 | 刷新从服务端恢复Thread/Branch/Message/Run；非终态Run续接观察，浏览器偏好非事实源。 |
| FR-REC-02 | RUN_014～RUN_016、RUN_021 | API/Worker重启及租约回收保留同一业务身份，旧generation写回被拒绝。 |
| FR-RUN-01 | RUN_013、RUN_017～RUN_021；UI_004、UI_012 | queued/running/retry_waiting取消状态、Worker确认、迟到结果和取消/成功竞争只有一个终态。 |
| FR-OBS-01 | SES_017；CTX_013；RUN_009、RUN_029、RUN_030；UI_007；COMP_001、COMP_003 | 页面展示可读关键状态、唯一Run与安全错误/上下文摘要，不展示隐藏思维、工具伪事件或敏感内容。 |
| FR-CTX-01 | CTX_003～CTX_005、CTX_009、CTX_010；UI_006 | Profile预算、输出预留、完整轮次裁剪、当前输入保留、超限不调用Provider、计划和界面提示范围正确。 |
| FR-CTX-02 | SES_011；CTX_006～CTX_008；QLT_004 | 摘要记录来源范围/策略且限Thread/Branch；原文保留；失败按既定回退或明确报错。 |
| FR-MD-01 | UI_008、UI_009 | 常用Markdown展示、持久原文与渲染分离、危险脚本/属性/协议在真实DOM中不执行。 |
| FR-RAG-01 | CTX_004、CTX_011、CTX_012；MOD_008；UI_010；COMP_013 | Citation来源于本Run实际Evidence，过滤后不引用未选证据，空召回与基础设施故障区别。 |
| FR-ERR-01 | CTX_008、CTX_012；MOD_002、MOD_005；RUN_022～RUN_025、RUN_028；UI_011；COMP_007；QLT_004 | Provider/上下文/取消/检索/数据库故障安全区分，可重试范围有界，不伪装空召回或成功。 |
| NFR-SEC-01 | SES_017；MOD_006、MOD_007；RUN_030；COMP_003；QLT_006 | 凭据只在服务端受控使用；数据库公开面、Event、响应、前端、日志、镜像与配置无Secret。 |
| NFR-SEC-02 | UI_009 | 真实浏览器DOM执行检查危险输入。 |
| NFR-ISO-01 | SES_011～SES_017；CTX_002、CTX_006、CTX_007；UI_003、UI_005、UI_010；COMP_005 | Branch/Thread路径和摘要范围正确，迟到响应/引用不能跨会话投影。 |
| NFR-REL-01 | SES_018；CTX_011；MOD_008；RUN_001～RUN_003、RUN_008、RUN_019、RUN_020；UI_014；COMP_002、COMP_004、COMP_005、COMP_013 | PostgreSQL是事实源；事件有序；终态和最终Message原子提交；取消竞争不产生双重结果。 |
| NFR-REL-02 | RUN_014～RUN_016、RUN_021；UI_001～UI_003；COMP_004 | 浏览器/API/Worker恢复和generation条件写回满足可恢复性。 |
| NFR-PERF-01 | PERF_001、PERF_002 | 至少30样本p95算法正确；持久delta到DOM延迟仅在保守误差上界满足时通过。 |
| NFR-CAP-01 | CTX_003、CTX_004、CTX_009、CTX_010；RUN_026～RUN_028 | 上下文/输出/事件/执行有界，留有终态结算能力，不丢当前输入。 |
| NFR-OBS-01 | CTX_005、CTX_013；RUN_008、RUN_009、RUN_029；UI_006；COMP_001、COMP_002、COMP_004 | Run/Thread/Branch/Task/seq关联可追溯；时间线区分持久事实和临时投影并安全说明Profile/上下文处理。 |
| NFR-TEST-01 | RUN_014～RUN_016；COMP_013；PERF_001；QLT_001～QLT_005 | 可控Provider/计数器、真PG/Compose/浏览器和完整质量门禁具备可靠、可重复入口。 |
| NFR-MIG-01 | COMP_008～COMP_012 | 旧事实升级保留、重复迁移与冲突预检可验证；不安全降级在破坏数据前拒绝。 |
| NFR-DEP-01 | COMP_013；QLT_005、QLT_006 | 正式Compose服务/migration/readiness路径可验证，Secret不进入镜像/前端/版本控制。 |

### 4.4 十项整体验收到用例

AC编号是测试点矩阵对PRD第9节十条验收的追溯别名，不是新增PRD需求或产品接口编号。

| 整体验收 | 覆盖用例 | 必需证据 |
| --- | --- | --- |
| AC-01 持久恢复与会话/分支隔离 | SES_004、SES_010～SES_017；CTX_002、CTX_007；RUN_014～RUN_016；UI_001～UI_003、UI_005、UI_010、UI_013；COMP_001、COMP_003～COMP_005 | 持久层身份对照、两个Thread/多Branch哨兵、页面/API/Worker恢复与迟到写回证据。 |
| AC-02 历史实际进入Provider且预算/来源正确 | CTX_001～CTX_010、CTX_013；UI_006；QLT_004 | 捕获同一Branch历史在后续Run中的ModelRequest内容身份、Token计数、ContextPlan/summary来源和不调用Provider负例。 |
| AC-03 多Profile选择、快照固定与凭据隔离 | MOD_001～MOD_006、MOD_008；UI_011；COMP_007；QLT_006 | Profile列表和新Run选择、Snapshot前后对照及各公开面的Secret扫描。 |
| AC-04 持久流式、断线补放和终态一致 | RUN_002、RUN_003、RUN_008～RUN_013；UI_003、UI_004；COMP_001、COMP_002、COMP_004；PERF_002 | DB Event、SSE游标、浏览器呈现时序和事务终态证据。 |
| AC-05 中断、迟到Provider/Worker与租约失效保护 | RUN_016～RUN_021、RUN_025、RUN_028；UI_012 | 两种取消竞争顺序、Worker generation/屏障和PG事实回滚证据。 |
| AC-06 自动重试与用户操作不混淆且保留历史 | RUN_004～RUN_007、RUN_009、RUN_017；UI_012、UI_014；COMP_007 | Run/Task/Message/Branch身份计数、尝试增量隔离和旧结果仍可读。 |
| AC-07 分支路径及分支摘要隔离 | SES_009～SES_017；CTX_002、CTX_006～CTX_008；UI_013；COMP_005；QLT_004 | 多级父子路径、摘要源消息/哈希与原始Message保持不变。 |
| AC-08 Markdown安全和RAG证据身份 | CTX_011、CTX_012；MOD_008；UI_008～UI_010；COMP_013 | 真实浏览器DOM安全结果、最终Citation对应本次Run证据和空结果/故障差异。 |
| AC-09 故障分型与无静默成功 | SES_017；CTX_003、CTX_008、CTX_012；MOD_002、MOD_005；RUN_022～RUN_025、RUN_028、RUN_030；UI_011；COMP_003、COMP_007；QLT_004 | 受控Provider/DB/RAG故障的状态、错误码、调用次数、重试和安全响应。 |
| AC-10 开发质量、契约/迁移、前端与Compose验收报告 | COMP_008～COMP_013；PERF_001、PERF_002；QLT_001～QLT_006 | 工具缺口解除、所有质量命令真实运行、PG迁移及两轮同源完整环境报告；blocked/failed/not_run均不得写成passed。 |

### 4.5 原受限点的去向和前置解除

下表保留设计及准备阶段状态；任务3～4已完成分类编排，任务5～6正式两轮已实际验证对应内容，两轮最终均无blocked。ENV及QGAP不再是当前未决前置，不能把下表历史“待执行”语态当成本轮结果。

| 原矩阵限制 | 测试点/用例 | 当前结论与后续处理 |
| --- | --- | --- |
| ENV-01/02/03（17点） | 上表原ENV受限的E行 | 环境闭环已有记录；本机可设计验证。PG/浏览器/故障控制具体编排、用例断言与证据收集仍需后续实现；若执行时发现缺失屏障或夹具，报告测试工程blocked，不能当产品通过。 |
| QGAP-01 | TP-TEST-02 / QLT_002 | 任务1～2已迁入tests/api/fixtures稳定字面样本、修引用、补格式校验依赖并运行契约断言；工程前置解除，待quality分类完整执行。原缺口为测试工程问题，不是机器配置不足或产品接口必然错误。 |
| QGAP-02 | TP-TEST-03 / QLT_003 | 任务1～2已补前端独立Lint/Vitest工具、配置、入口和锁文件并做工具核验；工程前置解除，待quality分类完整执行。类型/构建和三项工具探针不得代替实际产品组件回归。 |
| 原矩阵部分可验点中的PG子限制 | TP-MIG-01～04、TP-RUN-01/03/05等 | 代码级验证仍可使用既有测试，但正式事务/并发/迁移/重启结论必须来自当前隔离PG与真实进程；不使用SQLite充当PG证据。 |

本机Linux宿主、真实外部模型效果、生产负载与上游token续算不在本批验收承诺内；不为它们填通过。本文件没有要求用户手动准备真实凭据或公网服务；后续工程缺口明确可在仓库内处理，不需要为了完成设计而扩大产品范围。

## 5. 后续接入与整体校审

### 5.1 从设计到执行的交接（原设计路线）

以下为原设计任务的实施顺序，现均已有对应工程与正式执行；不是当前未完成事项。当前命令、结果和未修复差异分别见§1.3及测试/缺陷报告。

1. 按8类主归属在`specific_test_script/`逐类实现，动态数据/屏障归该类，公共稳定输入复用fixtures；用例不得直接操作开发库、创建平行产品路由或删除非本轮资源。
2. QGAP-01/02的工具前置已补；已有PG探针、Provider自测、环境自测只能复用其真实能力，不能把其已有通过数填成104个用例结果。新增的消息/分叉交错与故障边界需要后续实际实现。
3. 分类脚本须输出中文case ID、参数子场景、过程观察和证据；任何必需子场景失败/阻塞均影响本例结论。分类报告遵守已有Schema，再登记manifest的script/case_ids/status。本文不预填manifest，更不把planned改ready。
4. Selected调试完成后，以同源码/依赖/冻结镜像基线执行至少两轮All；完整环境与清理报告由总入口产生。QLT_005闭环结论在总入口清理后由外层校验，分类进程不得提前自证“清理通过”。
5. 真实执行后逐例填写实际测试结果、可复现的命令/操作及稳定性，给出run_id/证据路径；暂不可验证须写当次原因及解除条件。保留失败历史并形成独立测试/缺陷报告，不以最终重跑覆盖问题。

### 5.2 原设计任务文档变动（历史）

| 文件 | 变动与用途 |
| --- | --- |
| `tests/sesrag-persistent-session-workspace-test/test-cases.md` | 新增104例、公共数据/隔离/证据规则、源码定位、全量覆盖表和设计校审记录，供后续脚本实现。 |
| `tests/sesrag-persistent-session-workspace-test/README.md` | 增加用例入口/分类规模和未执行边界。 |
| `tests/sesrag-persistent-session-workspace-test/test-plan.md` | 将“用例待设计”更新为已设计；分类实现/门禁/正式验收仍未执行。 |
| `tests/sesrag-persistent-session-workspace-test/测试点设计与需求覆盖矩阵.md` | 不删改84点目标和原始点级状态；补充日期校准，将旧环境受限说明明确为历史快照，链接当前用例。 |

以上仅为原用例设计轮的变动清单：该轮未修改产品代码、接口、契约、迁移、测试工具/锁文件或manifest，未安装依赖、启动产品验收或自动提交。随后任务1～2的工具/总入口调整另见[准备核验记录](测试准备与总入口核验记录.md)，不混入该轮历史结论。

### 5.3 整体校审记录（2026-10-22）

| 校审项 | 结论与处理 |
| --- | --- |
| 测试点完整性 | 104个唯一用例覆盖84/84点；原65个可验证点无遗漏，原19个受限点均额外标记并保留原因/解除条件。 |
| 需求追溯 | 已核对18项FR、11项NFR、10项整体验收；测试点→用例与需求→用例双向可查，AC仅为验收追溯别名。 |
| 用例字段 | 每例14个设计/记录字段完整；执行结果、复现步骤、稳定性共312个字段留空，不把设计或旧环境记录当新执行结果。 |
| 独立性与原子判据 | 常规用例自行建事实；同目标输入边界参数化，不按每个字符重复建例。PG事务、取消先后、UI投影分层取证；包含多个必需子场景时必须分别记录。 |
| 源码一致性修正 | 校审纠正活动Branch“一律禁止分叉”的错误推断：新消息忙为BRANCH_BUSY，活动输入锚点分叉为INVALID_BRANCH_PATH，合法历史锚点仍可分叉；补足消息/分叉交错。 |
| 时间与清理判据修正 | 首delta测量明确L用最后不可见查询开始、U用首次可见查询结束；不把Event时间当commit。闭环清理必须由总入口最终证据判定，分类不得递归部署/自行清理或提前报通过。 |
| 已知差异与限制 | 原设计轮保留归档混排/无任意历史Run选择器的UI边界，当时QGAP-01/02未修复、QLT_002/003为B；任务1～2已补工具前置，当前状态以§1.1/§4.5为准。Profile停用、Key撤销、Redis降级、用户重试与自动attempt分开判断。 |
| 文档治理 | 原矩阵环境状态与新环境事实已显式分期，未改历史结果；README/接入计划同步。未恢复旧PRD验收目录，未扩大产品范围。 |
| 验证方法 | Node只读审计确认104个唯一ID、84点、29项需求、10项验收、14字段/例、312个空执行字段、34条有效本地链接，以及4份文档无尾空白/占位/失效源码路径；manifest仍8类planned。另执行限定范围git diff --check；因这4份文档目前均未跟踪，空白结论以Node逐文件检查为依据，不依赖Git忽略未跟踪文件的空结果。人工复核关键源码；未运行产品测试。 |

**原设计交付结论（2026-10-22历史）**：本文可作为后续分类测试脚本的设计基线。上述结论只针对当时的用例设计和文档完整性；当时尚未进行本批产品正式执行，不以设计替代取证。

## 6. 任务5～6正式执行与整体校审（2026-10-23）

§1.3两轮All均已结束并清理，各104 passed，其余状态计数为0；两个轮次的104个唯一ID、84点和29项FR/NFR映射一致。全部实际结果、复现和稳定性312字段均已填写，执行记录链接到正确分类/用例的两轮原始证据，不使用任务3～4的不同源码调试结果代替。机器可读完整校审见[任务5～6最终校审](artifacts/任务5-6最终校审.json)。

校审保留并说明UI_001的归档呈现差异、QLT_006的日志计数口径问题；另登记OpenAPI版本及文档残留，详见[缺陷报告](缺陷报告.md)。本批没有最终失败或暂不可验证用例，故没有因空缺前置而保留未填的执行字段。测试集通过不代表这些补充问题已修复。

本次只修改结果文档及必要导航/状态，未修改受测产品、脚本、夹具、契约、迁移或锁文件；test-cases的回填发生在两轮结束之后。运行时资源已清理，原始artifact、源码归档与冻结工具缓存保留，重放边界见测试报告。未自动提交或推送。
