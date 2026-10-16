# SesRAG 前端

Demo 使用 Vue 3、TypeScript、Vite、Pinia 和单页原生组件；无需 Router 或 UI 库。Markdown 由 marked 解析并经 DOMPurify 清洗，不能直接渲染模型原始 HTML。

## 模块职责

- `src/pages/WorkspacePage.vue` 编排会话切换、提交、健康读取和卸载清理。
- `src/stores/thread.ts` 读取 Thread 事实，以 epoch 隔离迟到 HTTP；`run.ts` 管理 Run 事实、事件唯一入口、临时回答投影和连接生命周期；`documents.ts` 管理文档事实和有界刷新。
- `src/api/` 共用安全 base、10 秒请求超时和稳定错误码；`health.ts` 接受 readiness 的 503 依赖事实。
- `src/events/run-event-stream.ts` 连接 SSE 并补放 HTTP，只将事件交给同一去重入口，关闭后丢弃迟到数据。
- `src/components/` 展示消息、状态、引用和文档；引用按钮支持 Enter/Space 展开批次、基础位置与 chunk offset。
- `scripts/generate-api-types.mjs` 从 `../contracts/*_v1.json` 可重复生成 `src/types/api.ts`，仅用项目 Node 标准库；未知 Schema 结构显式报错。

Run 事件只触发 GET，终态和失败以 Run/Thread 返回事实为准；临时 assistant 不写入 Thread 消息。完成消息存在时不追加历史 delta。事件按 `run_id + seq` 去重并按 seq 排序，重连用最后 seq 补放，不取消 Run。自动连接尝试最多重试 3 次，延时 0.5/1/2 秒；耗尽后保留手动重连。切 Thread/Run 和卸载关闭连接、清理 timer 并使旧回调/HTTP 失效。

Document 每 2 秒读取非终态，最多 30 次请求（约 1 分钟，另加请求时间），终态停止；读取失败保留事实并显示稳定错误码，耗尽后提示手动刷新。健康只在初始和用户检查时读取，不用请求成功猜测 PG/Worker/Redis ready。

## 开发与同源配置

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

Vite 代理 `/api` 和 `/health`。宿主默认目标 `http://127.0.0.1:8000`，API 需运行在本机端口；可在 `frontend/.env.local` 或进程环境设置 `API_PROXY_TARGET`。根 Compose 明确使用 `http://api:8000`，浏览器请求同源前端端口。该变量只进入 Vite 服务端，不能以 `VITE_` 前缀公开 Secret。

`VITE_API_BASE_URL` 可选，默认空；HTTP/SSE/health 共用它。一般保持空以经过同源代理；显式配置仅接受无凭据、无路径/query/hash 的 HTTP(S) origin，并要求部署实际允许该 origin 的浏览器请求。不要关闭 CORS 或设置通配 allow-origin 修复代理。

根 `.env.example` 是配置说明模板；宿主运行 Vite 不自动读取仓库根 `.env`，需要前述进程环境或前端局部 env 文件。

## 类型与质量检查

```powershell
npm run generate:api --prefix frontend
npm run check:api --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
npm ci --prefix tests/demo-smoke
npm run unit:frontend --prefix tests/demo-smoke
npm run lint --prefix frontend
```

Lint 与组件测试依赖 `tests/demo-smoke/package-lock.json` 的项目工具，不依赖全局 Vitest/ESLint。`lint` 真正检查前端源文件，不等同于类型检查。Vue 的 `no-v-html` 保留一条提示，因为清洗后的 Markdown 必须渲染 HTML；安全组件回归断言 script/onerror 不进入 DOM。

契约必须先更新再生成。`citation_v1.json` 联合完整新 Evidence 和无批次/位置字段的历史引用；不重写历史 Message/Journal，也不为历史假造批次/基础位置。HTTP 全状态矩阵、Event payload 和漂移负哨兵由 ADR-002 Task5d 验证；组件传输替身通过不等同于真实 Compose/浏览器验收。
