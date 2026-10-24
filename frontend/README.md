# SesRAG 前端

重试/重新生成默认沿用来源Run的模型快照；只有查看该Run后在模型控件手动切换，才发送显式覆盖。全局保存的模型偏好只用于新消息选择，不自动覆盖旧Run。工作台自动观察只选当前Branch的Run，继承祖先Run保留为历史；侧栏摘要由服务端事实刷新并按最近更新时间排序。

Demo 使用 Vue 3、TypeScript、Vite、Pinia 和单页原生组件；无需 Router 或 UI 库。Markdown 由 marked 解析并经 DOMPurify 清洗，不能直接渲染模型原始 HTML。

## 模块职责

- `src/pages/WorkspacePage.vue` 编排会话切换、提交、健康读取和卸载清理。
- `src/stores/thread.ts` 读取 Thread 事实，以 epoch 隔离迟到 HTTP；`run.ts` 管理 Run 事实、事件唯一入口、临时回答投影和连接生命周期；`documents.ts` 管理文档事实和有界刷新。
- `src/api/` 共用安全 base、10 秒请求超时和稳定错误码；`health.ts` 接受 readiness 的 503 依赖事实。
- `src/api/v2/`、`stores/model.ts`、`stores/branch.ts` 和新增选择/控制组件组成持久会话工作台；Thread/Branch/Run/Model 会话请求只走 `/api/v2`，文档 client 继续使用 `/api/v1`，旧 v1 会话 client 保留用于 legacy 回归。
- `src/markdown/render.ts` 是保存正文与流式草稿的唯一清洗入口；每次 marked 渲染后均使用 DOMPurify，原文与清洗后的 DOM 保持分离。
- `src/events/run-event-stream.ts` 连接 SSE 并补放 HTTP，只将事件交给同一去重入口，关闭后丢弃迟到数据。
- `src/components/` 展示消息、状态、引用和文档；引用按钮支持 Enter/Space 展开批次、基础位置与 chunk offset。
- `scripts/generate-api-types.mjs` 从 `../contracts/*_v1.json` 与 `*_v2.json` 可重复生成 v1 `src/types/api.ts` 和独立 v2 `src/types/api-v2.ts`；默认同时检查两代漂移，显式临时 `--output` 保留 v1 兼容，可指定 `--version v2` 检查 v2。仅使用项目 Node 标准库；未知 Schema 结构显式报错。

Run 事件只触发 GET，终态和失败以 Run/Thread 返回事实为准；临时 assistant 不写入 Thread 消息。完成消息存在时不追加历史 delta。事件按 `run_id + seq` 去重并按 seq 排序，重连和终态补放使用已连续收到的 seq 游标，不取消 Run。自动连接尝试最多重试 3 次，延时 0.5/1/2 秒；耗尽后保留手动重连。切 Thread/Run 和卸载关闭连接、清理 timer 并使旧回调/HTTP 失效。

会话列表分为“普通会话”和“已归档”视图，默认普通；归档/取消归档切到目标视图并保持当前身份，归档仍只读。两个视图共享服务端 `include_archived=true` 的全量游标和摘要缓存，仅过滤当前视图；空页而仍有后续页时提示加载更多，不等于服务器无归档记录。切视图清空旧选择/Run投影并选择该视图首项；空视图清空偏好，新建会话回普通视图。已保存的 Thread/Branch 即使不在列表首屏也会独立读取校验，有效归档偏好恢复到归档只读视图。待确认的重试/重新生成操作保留原模型参数与幂等键，模型选择变化不会替换原请求；界面提供“重试原操作”。更早消息按身份去重合并，不能覆盖当前分支的新事实。

Document 每 2 秒读取非终态，最多 30 次请求（约 1 分钟，另加请求时间），终态停止；读取失败保留事实并显示稳定错误码，耗尽后提示手动刷新。健康只在初始和用户检查时读取，不用请求成功猜测 PG/Worker/Redis ready。

## 开发与同源配置

Node 支持 `^20.19.0 || ^22.13.0 || >=24`；本机验收工具使用 Node 24。依赖由本模块 `package-lock.json` 锁定。以下命令均从仓库根执行；npm 缓存限定在测试工程，避免使用不可写的全局缓存。

`docker/frontend/Dockerfile`使用BuildKit缓存公开npm tarball并执行`npm ci`，锁文件不一致即失败；下载限制5个连接、每请求120秒并最多重试3次，不无限重试、不换包源。该缓存不会进入镜像，也不包含数据库/模型凭据；属于Docker共享构建缓存，测试资源清理不做全局prune。首次下载受网络影响仍可能失败，须保留失败报告并按总入口重试。

```powershell
npm ci --prefix frontend --cache tests/sesrag-persistent-session-workspace-test/.cache/npm
npm run dev --prefix frontend
```

Vite 代理 `/api` 和 `/health`。宿主默认目标 `http://127.0.0.1:8000`，API 需运行在本机端口；可在 `frontend/.env.local` 或进程环境设置 `API_PROXY_TARGET`。根 Compose 明确使用 `http://api:8000`，浏览器请求同源前端端口。该变量只进入 Vite 服务端，不能以 `VITE_` 前缀公开 Secret。

`VITE_API_BASE_URL` 可选，默认空；HTTP/SSE/health 共用它。一般保持空以经过同源代理；显式配置仅接受无凭据、无路径/query/hash 的 HTTP(S) origin，并要求部署实际允许该 origin 的浏览器请求。不要关闭 CORS 或设置通配 allow-origin 修复代理。

根 `.env.example` 是配置说明模板；宿主运行 Vite 不自动读取仓库根 `.env`，需要前述进程环境或前端局部 env 文件。

## 类型与质量检查

`tests/thread-store.test.ts` 是 WS-DEF-001 的8项store/侧栏/页面回归，覆盖互斥视图、归档移动、首屏外偏好、空视图、新建、共享游标去重、迟到响应及当前视图读取失败的可见错误与恢复；正式浏览器验收由 PRD-002 独立套件UI_015～018执行。

```powershell
npm run generate:api --prefix frontend
npm run check:api --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
npm run lint --prefix frontend
npm run test:toolchain --prefix frontend
npm run test:unit --prefix frontend
```

Lint 与组件测试由前端自有 ESLint、Vitest、Vue Test Utils、jsdom 及锁文件提供，不读取旧验收目录或全局工具。`eslint.config.mjs` 检查 `src/`、`scripts/`、`tests/` 和配置文件；`vitest.config.ts` 使用独立 Vue/jsdom 环境，不加载开发代理配置。没有测试文件时命令失败。

`tests/toolchain.test.ts` 与 `tests/fixtures/ToolchainProbe.vue` 是三项工具能力自检：Vue/TypeScript SFC、DOM 事件/MutationObserver、可控定时器。它们只证明后续组件脚本的工具前置，不能作为工作台产品验收；实际产品组件用例留待后续增加。`test:unit` 运行本模块全部 `tests/**/*.test.ts`，`test:toolchain` 仅运行工具探针。Vue 的 `no-v-html` 保留一条警告，因为清洗后的 Markdown 必须渲染 HTML；警告不等于 XSS 验证通过，后续仍需真实恶意输入与 DOM 断言。

契约必须先更新再生成。`citation_v1.json` 联合完整新 Evidence 和无批次/位置字段的历史引用；不重写历史 Message/Journal，也不为历史假造批次/基础位置。HTTP 全状态矩阵、Event payload 和漂移负哨兵由 ADR-002 Task5d 验证；组件传输替身通过不等同于真实 Compose/浏览器验收。
