# 分类测试接入约定

本目录目前只含manifest及报告Schema，没有任何产品分类自动测试脚本。7类都为`not_implemented`，总入口仍部署、报告和清理，但返回`not_ready/3`。不得提交空断言脚本改为enabled。

## 接入步骤

1. 根据[测试点矩阵](../测试点设计与需求覆盖矩阵.md)及后续用例确定主测试点ID和单一验证目标。
2. 按manifest路径新增`.ps1`或`.mjs`，完成正常/异常输入、证据、退出码和清理自有客户端。
3. 生成满足[category-result.schema.json](category-result.schema.json)的JSON，验证真正失败能返回非零；不得把已知缺陷自动跳过后报passed。
4. 在[manifest.json](manifest.json)中将该项改为`enabled`，设置合理有界timeout_seconds，再通过总入口指定`-Category <name>`验证接入。
5. 正式验收选择all并检查所有必测分类完成。子集通过不等于全部PRD通过，summary会记录category_selection。

## 统一参数与进程边界

PowerShell使用同名param，Node从process.argv解析下列参数（拼写和大小写固定）：

```text
-BaseUrl <http://127.0.0.1:api-port>
-FrontendUrl <http://127.0.0.1:frontend-port>
-RunId <本次run_id>
-ArtifactDir <本次报告绝对目录>
-RuntimeDir <本次运行绝对目录>
-FixtureDir <本次tmp中生成的fixture目录>
```

`FixtureDir/upload-safe/`有txt/md及生成的smoke.docx，稳定源位于仓库fixtures；不得从宿主任意目录搜资料。大文件/损坏文档写到RuntimeDir同级的本次tmp/run_id内，不进Git，不留artifact原文。

总入口为每类创建独立子进程，超时/可捕获中断终止进程树。退出0且Schema合法、run_id/category一致、非空checks全部passed才通过。没有报告、错误报告、空checks的passed、子进程非零或超时均失败。未接入项由入口生成not_ready/空checks；分类可以记录blocked/skipped/not_ready，但这些不构成通过。

每类写`<ArtifactDir>/categories/<manifest.name>.json`，至少包含：schema_version=1、run_id、category、status、UTC started_at/finished_at、非空checks、evidence。每个check包含id（用例ID）、test_point_id、status、自然语言expected/actual、evidence路径数组；关联Thread/Run/Task/document/generation/seq可作为扩展字段。

证据路径应相对ArtifactDir且不能逃逸，失败记录可复现输入摘要/状态码/关联日志；不得记录真实Key、数据库密码、完整Prompt或无必要原文。运行器会再次脱敏主报告和stdout，但分类自己的截图/附加文件必须自行脱敏。

## 不可越过的边界

- 业务操作经正式HTTP/SSE；必要容器内DB诊断只读，不改生产状态伪造结果。
- RuntimeDir/context.json可获取本次project和地址；compose.env含临时凭据，只供必要容器诊断，不打印/复制到报告。
- 禁止自行Compose down/global prune，禁止碰开发project、删除其他分类报告或改变本次owner/project；环境销毁仅由总入口负责。
- 浏览器、SSE、HTTP客户端及其他自建进程须在分类finally关闭，禁止启动逃逸的后台服务；不得禁用浏览器CORS策略掩盖产品缺陷。
- 当前同源Vite代理为合法测试部署配置，但不代表根Compose跨域缺口已修复；慢Provider/双owner/屏障尚未准备，需明确另补条件。
- Node可import项目本目录安装的playwright；运行器设置`PLAYWRIGHT_BROWSERS_PATH=tests/demo-smoke/.cache/ms-playwright`，浏览器只下载到该项目目录。

总入口默认镜像构建、全新随机project、Mock且384维，开始前做真实DB和基础服务检查。这些仅是环境前提，不替代本目录后续产品断言。
