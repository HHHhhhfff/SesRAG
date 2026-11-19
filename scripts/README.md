# 应用与监控统一部署入口

本目录是应用拥有者的上层编排，管理本机持久实例`sesrag-live`与独立监控`sesrag-observe-live`。它不把监控下层入口变为业务生命周期管理器。当前应用无生产登录认证，所有公开端口仅回环；本部署不等于公网生产平台。

## 实施顺序与文件职责

- `sesrag.ps1`：PowerShell 7入口；首次创建监控模块专用venv，调用唯一Python编排。
- `deployment/configuration.py`：真实配置准备、独立Secret解析、dotenv保留与受限文件写入。
- `deployment/stack.py`：身份核验、进程互斥、应用构建/数据库备份/迁移和监控串行编排，脱敏操作报告。
- `compose.runtime.yaml`：回环端口、持久重启、运行配置挂载及资源所有者标签；不改根业务Compose。
- `runtime/`：受限部署账本、模型/RAG配置、私有备份，Git/Docker构建忽略。
- 验证统一位于`tests/grafana-observability-test/`，不另建临时Compose环境。

实施按配置安全测试→编排实现→真实部署→三信号和告警验证→Update/Stop/Destroy/Start回归进行。依据见[ADR-005补充](../docs/adr/005-sesrag-local-observability-deployment-plan.md)。

## 快速上手（PowerShell 7.4+）

在仓库根目录执行；也可从其它目录以脚本绝对路径调用。Python3.11+、Docker Desktop Linux Engine与Compose2.27+须可用，Docker内存至少8GiB。首次使用须有本机授权文件`docs/secret/准备的配置信息.md`，分别包含会话、向量化、重排与MinerU凭据。

```powershell
# 首次自动准备真实配置、构建应用、迁移并启动应用与监控。
pwsh -NoProfile -File scripts/sesrag.ps1 Start
# 查看实际服务状态和基础接线检查。
pwsh -NoProfile -File scripts/sesrag.ps1 Status
pwsh -NoProfile -File scripts/sesrag.ps1 Verify
# 更新当前工作区代码对应的应用镜像；不自动pull Git或升级监控digest。
pwsh -NoProfile -File scripts/sesrag.ps1 Update
# 优雅停止；所有历史数据保留。
pwsh -NoProfile -File scripts/sesrag.ps1 Stop
# 销毁容器，仍保留数据卷、应用网络、私有配置与凭据。
pwsh -NoProfile -File scripts/sesrag.ps1 Destroy
# 恢复持久服务。
pwsh -NoProfile -File scripts/sesrag.ps1 Start
```

每个命令完成后检查`$LASTEXITCODE`，非0停止后续操作。动作有互斥锁，失败保留脱敏报告，不靠删除卷修复错误。正常Start会复用原.env和随机所有者，不再次导入Secret文档；只想先准备而不启动可执行`Prepare`。

默认访问：[应用](http://127.0.0.1:5173)、[API就绪](http://127.0.0.1:8000/health/ready)、[Grafana](http://127.0.0.1:3000)。Grafana用户名`admin`，首次密码在`docker/monitoring/runtime/live/secrets/grafana-password`，请仅在本机私下查看。已有Grafana数据库不会随重写密码文件重置密码。监控通知只发本地sink，不会发邮件。

## 真实配置及边界

根`.env`写入独立四类服务凭据、`MOCK_PROVIDER=false`、`MINERU_ENABLED=true`、随机MinerU状态加密密钥和精确存储域白名单。现有数据库密码保留；初始根.env私有副本保存在`scripts/runtime/original.env`。旧`sesrag`与其它project不接管，新实例数据属于`sesrag-live`。`.env`和私有runtime收紧Windows ACL，Git及Docker构建忽略；请勿打印完整环境、备份或原始错误响应。

| 配置 | 要求/默认与含义 |
| --- | --- |
| `OBS_ENVIRONMENT_ID`、`OBS_ENVIRONMENT` | Prepare固定为`live`，显式override把API/Worker身份、日志opt-in及精确Alloy OTLP地址对齐 |
| `SESRAG_DEPLOYMENT_OWNER` | Prepare随机生成，与私有账本和所有容器/卷/网络标签匹配；缺失/冲突拒绝接管 |
| `SESRAG_API_PORT`、`SESRAG_FRONTEND_PORT` | 可选，默认8000/5173，只绑定127.0.0.1；首次启动前可在.env修改，冲突不会杀其它进程 |
| 模型与MinerU Secret | 分别来自授权文件，API/Worker使用相同引用；变更已准备.env需再Update，避免改变已有冻结Run的配置 |
| `MINERU_STATE_ENCRYPTION_KEY` | 首次随机生成后保留，丢失会影响旧解析检查点恢复，必须私下备份 |
| `MINERU_STORAGE_HOST_ALLOWLIST` | 使用既有已核实的两个精确域；云端换域时先核实，再更新.env，不使用通配符 |

运行配置含非Secret ModelProfile、RAG Profile及初始化选择。默认聊天使用真实`live-chat`；预算采用已随镜像离线提供的`cl100k_base`、8192本地窗口和1024安全余量，标记为本地保守配置，**没有供应商精确tokenizer校准证明**。它可用于小规模真实请求，不据此承诺模型完整窗口或生产计费准确。

真实Embedding/rerank凭据已配置，Profile仍保留`INPUT_COUNTER_UNVERIFIED`，不会伪造计数依据或自动回退Mock。默认知识库绑定真实空间而不混入Mock向量；完整真实RAG仍需提供可核实的输入计数/配额依据后用新Profile版本启用。MinerU的已验证办公解析Profile可见，但本次监控部署验证不等于新一轮九格式/检索效果验收。

## 操作的具体含义

- **Start**：先核验project/daemon/随机owner，构建当前源码应用，按既有迁移入口升级，再导入本部署Profile；导出真实部署描述，核监控准入并准备/拉取锁定镜像/校验/启动。下层监控不会反过来启动应用。
- **Update**：先停止业务写入并创建受限`pg_dump`备份、校验`pg_restore --list`，记录旧镜像ID；再构建/迁移并恢复服务。失败停止后续动作，备份保留；不自动downgrade或覆盖数据库。PostgreSQL/Redis镜像主版本、监控组件版本升级不由此动作自动完成。
- **Stop**：先删除监控容器/自有网络而保留五卷/配置，再优雅停止应用容器。应用网络仍保留，下一次Start继续同一网络身份。
- **Destroy**：执行Stop后只移除本部署应用容器；**业务数据和监控历史均保留**。保留的卷和应用网络是有意的持久资源，不是“全数据销毁”。统一入口没有清空业务数据开关。
- **Verify**：只作基本接线检查，既有Tempo纯静态解析或完整验收占位仍如实记not_run/partial。真实模型/告警验证见[本轮验证工程](../tests/grafana-observability-test/README.md)。

本地报告在`tests/grafana-observability-test/artifacts/<run-id>/deployment.json`，监控动作原报告仍在模块artifacts中。数据库备份在`scripts/runtime/backups/<run-id>/database.dump`，含业务数据；这是数据库备份，不等于上传/索引卷完整灾备。私有配置、历史镜像与显式备份不自动删除，也不执行全机prune或VHDX压缩。

即使此前已Destroy容器，只要持久数据库卷仍在，Update也会先恢复且仅恢复PostgreSQL，等待其健康、成功备份后才继续迁移。下层Validate/Verify存在未运行项时，总报告同样保留partial与具体子报告ID；退出码0表示动作执行成功，不能代替逐项验收。

## 失败后处理

同名资源无本部署owner、换Docker daemon、应用网络换ID时拒绝接管；恢复正确的私有账本/配置与原Docker context。不要手改owner/hash“修好”校验。来源指纹变更由显式Update→RefreshBinding核当前真实部署；监控模板/digest变更按独立模块的备份与升级流程处理，不能靠RefreshBinding绕过。

首次应用构建或服务启动失败时，已有运行容器和数据保留；查看脱敏错误码后定位本机服务，修复后重跑Start。已准备.env不会自动跟随Secret文档轮换，请在本机编辑.env中对应独立凭据后执行Update。监控有故障时业务可有界降级，但当前机器停机也会停止本机监控，不能依赖它发自身断电告警。
