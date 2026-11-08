# v0.3 RAG 与 MinerU 部署、升级和检查

- 版本：v0.3／PRD-003；日期：2026-10-30。
- 依据：[PRD-003](../prd/003-SesRAG-RAG检索增强与MinerU接入-PRD.md)、[ADR-003](../adr/003-sesrag-rag-mineru-implementation-plan.md)。
- 本文补充[本机基础部署流程](demo-development.md)。数据库密码、DSN 的生成、Windows/Linux 安装及备份恢复继续使用该文档；所有命令从仓库根执行。不要覆盖已有 `.env` 或重新初始化已有数据卷。
- 当前能力与验证限制见[实施记录](../pr/003-SesRAG-RAG检索增强与MinerU接入-PR.md)；接口字段只维护在[接口文档](../接口文档.md#8-v03-rag-与-mineru接口)。

## 1. 空库启动与本地文本

准备好基础 `.env` 的数据库配置后，保持 `MOCK_PROVIDER=true`、`MINERU_ENABLED=false`。首次空库启动不需要模型或 MinerU Key：

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps -a
docker compose exec -T api python -m alembic current
```

Linux Bash 使用相同 Docker 命令。迁移入口改为 `backend.tools.upgrade_rag_schema`：先升到 0007，显式初始化 catalog 和默认库，再升到 0010；空库采用明确的 Mock 空间。重复启动不会覆盖已导入的配置。预期 `migrate` 退出 0、API/Worker 正常运行，最终 revision 为 `0010_rag_task_and_run_protocol`。

打开前端 `http://localhost:5173`。默认知识库绑定 `mock-embedding@1`，可以上传 UTF-8 txt/md，查看最新构建、已发布切片并执行检索诊断；聊天勾选“后续新消息启用 RAG”后使用所选库。关闭 RAG 的聊天不访问检索依赖。Mock 只用于工程流程，不证明语义效果。

## 2. 显式导入 RAG 配置

根 Compose 将两份无 Secret 模板只读挂入容器；它们是导入输入，数据库为运行时配置真源：

```powershell
docker compose exec -T api python -m backend.tools.sync_rag_profiles /app/config/rag-profiles.example.json
```

`docker/rag-profiles.example.json` 包含本地／Mock、已用真实办公样本核实的 `mineru-office@2`、真实百炼模板和独立检索策略。导入模板不启用云端开关，不写入凭据，也不会把真实模型的 `counter_status=unverified` 改为 verified。可在工作台“可用配置及原因”或 `GET /api/v3/rag/profiles` 查看不可用原因。

相同 ID/version、相同内容允许重放；改配置须增加 version。`enabled=false` 阻止新选择；`blocked=true` 为安全阻断，冻结中的工作也会在受控检查点失败。同版本不能借重导入改变模型或空间。自定义文件可先复制至容器后显式导入：

```powershell
docker compose cp ./data/rag-profiles.local.json api:/tmp/rag-profiles.local.json
docker compose exec -T api python -m backend.tools.sync_rag_profiles /tmp/rag-profiles.local.json
```

该文件不得含 Key。工作区 `data/` 已忽略；不要将非 Secret 文件的 `config_ref` 改成真实凭据。

## 3. 启用办公文件解析

九格式固定分流：txt/md 永远本地；doc/docx/pdf/xls/xlsx/ppt/pptx 原件只使用 MinerU 精准 API。办公每次上传或重建均需在页面明确授权完整原件外发；失败不转换文件、不切本地解析。启用前确认上游的数据政策适合所上传文件。

在现有 `.env` 中配置：

```dotenv
MINERU_ENABLED=true
MINERU_API_KEY=<从MinerU账户获取的精准API令牌>
MINERU_STATE_ENCRYPTION_KEY=<32字节随机值的base64>
MINERU_STORAGE_HOST_ALLOWLIST=mineru.oss-cn-shanghai.aliyuncs.com,cdn-mineru.openxlab.org.cn
```

以上两个域是 2026-10-30 真实调用观察到的上传／结果域，分别核实后使用，不代表可自动信任后续返回的任意域。新域被阻断时先核实上游来源再调整精确白名单，禁止使用 `*`。`OUTBOUND_TARGET_UNSAFE` 是安全失败，不能据此自动扩大白名单或重新上传已提交原件。

生成加密 Key 的命令（Windows 使用项目 Python；Linux 改为 `.venv/bin/python`）：

```powershell
.venv/Scripts/python.exe -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

仅首次生成，把结果安全填入 `.env`，API/Worker 使用同一值并单独备份。存在活动云端 Job 时不要随意换 Key，否则旧检查点无法解密。该命令会在本机终端显示 Key，不能把输出放进报告或聊天。

导入上一节的 Profile 后同步更新两个服务的环境：

```powershell
docker compose up -d --force-recreate api worker
```

页面选办公文件时应显示原件外发确认；未授权不能提交。`done` 只是远端完成，只有本地 `IndexBuild=succeeded` 并切换 active 才可检索。`submission_unknown` 表示云端可能已受理，本地不会自动重提；手动新建重建操作必须再次授权并确认可能重复计费。取消只终止本地工作，不保证远端撤回或退款。

当前真实样本的 PDF 页码部分可可靠映射；Word、PPT、Excel 主要提供规范文本块。缺少真实页／幻灯片／单元格映射会明确展示，不能把转换后的页号当原位置。

## 4. 真实 Embedding 和 rerank

两类 Key 分开注入 `RAG_EMBEDDING_API_KEY`、`RAG_RERANK_API_KEY`，不自动复用生成模型 Key。修改后同时重建 API/Worker。

真实模板使用 `qwen3.7-text-embedding`、显式 1024 维、`l2_float32_v1` 和百炼兼容 `/compatible-mode/v1/embeddings`；rerank 使用独立原生 `/api/v1/services/rerank/text-rerank/text-rerank`。如账户使用专属 workspace origin，修改非 Secret 地址并增加配置版本。

真实协议调用已经成功，但本轮尚无充分证据证明模型专用输入计数。模板因此返回 `INPUT_COUNTER_UNVERIFIED`，保持不可用。不得仅填一个字符串就宣称完成校准；需要官方计数能力／tokenizer 或有依据的配额上界及边界校准证据，完成后增版导入。UTF-8 字节限制是本地配额，不是精确模型 token 数。

真实空间创建后不可改绑；切换生成模型不会改变向量空间。旧 384 维空间与新 1024 维空间通过身份、维度和模型修订隔离。待计数前提完成后，应新建绑定真实 Profile 的知识库并重新入库，不能把 Mock 向量改标签为真实向量。

## 5. 已有 v0.2 数据库升级

先按基础 Runbook 停写、排空 Worker、备份 PostgreSQL 和 uploads；新增的 `rag_artifacts` 私有卷及加密 Key 也须一并保护。不要在有数据的旧库裸跑 `alembic upgrade head`。

```powershell
docker compose stop api worker frontend
```

确认无有效旧租约后，在 `.env` 设置：

```dotenv
RAG_BOOTSTRAP_CONFIG=/app/config/rag-bootstrap.example.json
```

示例选择 Mock 空间只表示给 owner 建立默认库，不证明旧向量来自 Mock。真实旧配置应依据历史部署记录准备非 Secret bootstrap 文件，并在 migrate 服务只读挂载该文件。

```powershell
docker compose build migrate api worker
docker compose run --rm migrate
docker compose up -d api worker frontend
docker compose exec -T api python -m alembic current
```

迁移给旧文档填归属，旧向量标记为 `legacy_unverified`；已有历史消息／事件／引用 JSON 不改写，已经丢失的 Chunk 不补造。未领取的旧 DOCX 索引任务结束为 `DOCUMENT_WRITE_UPGRADE_REQUIRED`，必须改用 v3 并授权，不会自动外发。

只有有可复核的旧 Mock-384 部署来源时才使用确认工具。清单结构如下；先填真实 document/batch 身份和记录引用，再复制到容器：

```json
{"space_id":"<由可信旧空间计算得到的hash>","provenance_reference":"<历史部署记录引用>","batches":[{"document_id":"<uuid>","index_batch_id":"<uuid>","source_hash":"<原源sha256>"}]}
```

```powershell
docker compose cp ./data/legacy-confirmation.json api:/tmp/legacy-confirmation.json
docker compose exec -T api python -m backend.tools.confirm_legacy_rag_space /tmp/legacy-confirmation.json
docker compose exec -T api python -m backend.tools.confirm_legacy_rag_space /tmp/legacy-confirmation.json --apply
```

缺来源、混空间、原文缺失或与默认库绑定不符时拒绝；保留不可检索提示，原件另建新库重新入库。不能仅凭“384维”确认。

出现本轮业务事实后 downgrade 明确拒绝；安全回退使用升级前一致备份及对应旧镜像，步骤参考基础 Runbook。不要删新事实来绕过降级检查，不使用 `down -v` 进行升级。

## 6. 有界清理与容量

```powershell
docker compose exec -T api python -m backend.tools.cleanup_rag_artifacts
docker compose exec -T api python -m backend.tools.cleanup_rag_artifacts --apply
```

默认 dry run；`--apply` 清超过 24 小时、无 active/latest、视图或证据引用的批次及无活动依赖的私有临时文件。保留 ParseJob 的错误／hash及未知提交摘要。独立诊断保留七天，清理后保留三十天安全墓碑并返回 `410 RAG_RESOURCE_EXPIRED`；Run 视图和回答证据不按七天规则清除。

总预算默认10GiB、临时预算1GiB，属于应用软配额。`RAG_TMP_BUDGET_BYTES`至少402653184（384MiB）容纳一个执行槽，低于此值启动明确拒绝，不让任务受理后永远排队。源、规范文本、候选和历史依赖占用可能长期增长；不能删除引用中数据腾空间。独立检查只销毁其带项目标签的容器／卷／网络，不做全局prune，不动其他项目镜像。

## 7. 本轮独立检查与复现

安装项目 dev 依赖后：

```powershell
.venv/Scripts/python.exe -m pytest tests/unit tests/api tests/integration -q
.venv/Scripts/python.exe -m backend.tools.export_rag_contracts --check
npm run check:api --prefix frontend
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm run test:unit --prefix frontend
npm run build --prefix frontend
.venv/Scripts/python.exe tests/integration/run_rag_v3_check.py
```

Linux 将 Python 路径替换为 `.venv/bin/python`。独立 Compose 检查不读取根 `.env`，不映射宿主端口，使用随机项目和随机数据库凭据。证据在 `data/rag-implementation/sesrag-rag-check-*/`：启动、模型导入、probe、容器日志、清理和 summary。`finally` 销毁该项目容器／卷／网络及自动命名的本次应用镜像，保留共享基础镜像和构建缓存，summary 的 remaining 必须全部为空。镜像构建失败时同样收证清理，不能将清理成功写成产品验证通过。

真实服务探针只用于显式批准的固定公开／合成样本，不自动读取 `docs/secret`：

```powershell
.venv/Scripts/python.exe -m backend.tools.check_rag_providers --mode models --allow-synthetic-outbound --output data/rag-implementation/model-probe.json
.venv/Scripts/python.exe -m backend.tools.check_rag_providers --mode office --allow-synthetic-outbound --output data/rag-implementation/office-probe.json
```

调用前安全注入所需凭据、加密 Key 和核实的域；office 探针会上传 manifest 中七种办公样本，不能用它处理个人文档。重跑同一 output 的终态项会跳过，不自动重提未知结果。若仅补取已提交批次的结果，使用同 output 目录下 private 检查点和 `--mode office-results`，不新建上传；这是 P0 只读补证工具，不会复活产品中已终态的 Job。
