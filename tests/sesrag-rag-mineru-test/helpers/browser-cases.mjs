// UI_001～018/QLT_005：真实Chromium、生产组件/store及同源HTTP；无产品源码测试后门。
import { createRequire } from 'node:module';
import { createServer, request as proxyRequest } from 'node:http';
const require = createRequire('/test-tools/package.json');
const { chromium } = require('playwright');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => i % 2 ? a : [...a, [v.slice(2), all[i + 1]]], []));
const observations = []; let assertions = 0;
function note(phase, detail) { observations.push({ phase, detail }); }
function check(value, target, actual) { assertions++; note('观察', { target, value: Boolean(value), actual }); if (!value) throw new Error(target); }
// 工具容器内loopback反代保留生产Vite/API同源链路，提供真实localhost安全上下文。
// 不修改crypto或放宽产品Host白名单；仅监听本容器loopback，结束时关闭连接。
const upstream = new URL(args.origin);
const proxy = createServer((incoming, outgoing) => {
  const request = proxyRequest(new URL(incoming.url, upstream), { method: incoming.method, headers: { ...incoming.headers, host: upstream.host } }, response => {
    outgoing.writeHead(response.statusCode, response.headers); response.pipe(outgoing);
  });
  request.on('error', () => { if (!outgoing.headersSent) outgoing.writeHead(502); outgoing.end(); });
  incoming.pipe(request);
});
await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve));
args.origin = `http://127.0.0.1:${proxy.address().port}`;
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const context = await browser.newContext();
const page = await context.newPage();
page.on('pageerror', error => note('浏览器错误', String(error.message).slice(0, 300)));
const calls = [];
const base = '00000000-0000-4000-8000-000000000001';
const docId = '00000000-0000-4000-8000-000000000002';
const batch = '00000000-0000-4000-8000-000000000003';
const doc = (extra = {}) => ({ document_id: docId, knowledge_base_id: base, filename: 'fact.txt', extension: '.txt', size_bytes: 12, content_hash: 'a'.repeat(64), tags: [], availability: 'ready', active_index_batch_id: batch, latest_build: { index_batch_id: batch, state: 'succeeded', stage: 'completed', chunk_count: 1, parse: { parser_kind: 'local', stage: 'completed' } }, ...extra });
const diagnostic = (extra = {}) => ({ execution_id: 'diag-1', view_id: 'view-1', state: 'succeeded', stage: 'completed', mode: 'ok', candidates: [], omitted: [], bundle_ids: [], error_code: null, ...extra });
const bundle = (id = 'bundle-A', extra = {}) => ({ bundle_id: id, document_id: docId, index_batch_id: batch, dense_score: .8, rerank_score: null, text: 'ALPHA 37', locations: [], components: [{ component_id: 'component-1', chunk_id: 'chunk-1', start_offset: 0, end_offset: 8, content_hash: 'b'.repeat(64) }], next_offset: null, ...extra });
let documents = [], result = diagnostic(), bundleResult = bundle(), profileAvailable = true;
let handler = null;
async function route(route) {
  const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
  calls.push({ path, method: request.method(), key: request.headers()['idempotency-key'], body: request.postDataBuffer()?.toString('utf8') ?? '', query: url.search });
  if (handler && await handler(route, path, request)) return;
  let value = {};
  if (path === '/api/v3/documents') value = request.method() === 'GET' ? { items: documents, next_cursor: null } : doc();
  else if (path.includes('/index-builds') && request.method() === 'POST') value = { index_batch_id: batch, state: 'queued' };
  else if (path.startsWith('/api/v3/retrieval-executions')) value = result;
  else if (path.startsWith('/api/v3/evidence-bundles/')) value = bundleResult;
  else if (path === '/api/v3/knowledge-bases') value = { items: [{ knowledge_base_id: base, name: '本例库', enabled: true, is_default: true }], next_cursor: null };
  else if (path.endsWith('/chunks')) value = { items: [], next_cursor: null };
  else if (path === '/api/v3/rag/profiles') value = { items: [] };
  else return route.continue();
  await route.fulfill({ status: request.method() === 'POST' ? 202 : 200, contentType: 'application/json', body: JSON.stringify(value) });
}
async function setup(component = 'DocumentUploader') {
  // 完成真实工作台初次加载后才卸载，避免bootstrap的迟到响应污染独立组件夹具。
  await page.goto(args.origin, { waitUntil: 'networkidle' });
  const secure = await page.evaluate(() => isSecureContext && typeof crypto.randomUUID === 'function');
  if (!secure) throw new Error('BROWSER_SECURE_CONTEXT_UNAVAILABLE');
  await page.route('**/api/**', route);
  await page.evaluate(async ({ component, base, profileAvailable }) => {
    const { createApp, reactive, h } = await import('/node_modules/.vite/deps/vue.js');
    const { createPinia, setActivePinia } = await import('/node_modules/.vite/deps/pinia.js');
    document.querySelector('#app').__vue_app__?.unmount();
    const pinia = createPinia(); setActivePinia(pinia);
    const { useRagStore } = await import('/src/stores/rag.ts');
    const { useDocumentStore } = await import('/src/stores/documents.ts');
    const { useRunStore } = await import('/src/stores/run.ts');
    const rag = useRagStore(); const docs = useDocumentStore(); const run = useRunStore();
    rag.selectedBase = base;
    rag.bases = [{ knowledge_base_id: base, name: '本例库', enabled: true, is_default: true }];
    rag.profiles = [{ kind: 'parser', available: profileAvailable, verified_formats: ['.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx'] }];
    const module = await import(`/src/components/${component}.vue`);
    const root = document.createElement('div'); root.id = 'case-root'; document.body.append(root);
    const props = reactive(component === 'EvidenceViewer' ? { bundleId: 'bundle-A' } : {});
    const app = createApp({ render: () => h(module.default, props) }); app.use(pinia); const vm = app.mount(root);
    window.__case = { rag, docs, run, app, vm, pinia, props };
  }, { component, base, profileAvailable });
}
async function setFile(extension) {
  await page.getByLabel('选择文档', { exact: true }).setInputFiles({ name: `sample.${extension}`, mimeType: 'application/octet-stream', buffer: Buffer.from('safe input') });
}
async function rendered() { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => resolve()))); }
async function setDocs(rows) { documents = rows; await page.evaluate(rows => { window.__case.docs.items = rows; }, rows); await rendered(); }
async function state(fn, value) { return page.evaluate(fn, value); }
const cases = {
  async UI_001() { // UI_001：九格式逐个实际选择，验证固定路线和无可选增强。
    await setup();
    for (const ext of ['txt', 'md', 'doc', 'docx', 'pdf', 'xls', 'xlsx', 'ppt', 'pptx']) {
      await setFile(ext); await rendered();
      check(await page.getByText(['txt', 'md'].includes(ext) ? '此文本仅在本地解析，不发送到 MinerU。' : '我同意本次将完整原件', { exact: false }).isVisible(), '按格式显示固定路线', ext);
    }
    check(await page.getByText('可选增强', { exact: false }).count() === 0, '没有可选增强开关');
  },
  async UI_002() { // UI_002：新文件/撤销/新重建逐次确认，捕获实际multipart parse。
    await setup(); await setFile('docx');
    const consent = page.getByRole('checkbox').first(); const submit = page.getByRole('button', { name: '提交本次操作' });
    check(await submit.isDisabled(), '未授权不能提交'); await consent.check(); await consent.uncheck();
    check(await submit.isDisabled(), '撤销后不能提交'); await consent.check(); await setFile('pdf');
    check(!(await consent.isChecked()), '更换文件重置授权'); await consent.check();
    const completed = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v3/documents' && r.request().method() === 'POST');
    await submit.click(); await completed;
    const sent = calls.find(r => r.method === 'POST' && r.path === '/api/v3/documents');
    check(sent?.body.includes('mineru-office-outbound-v1') && sent.body.includes('cloud_consent'), '网络请求含本次明确授权', sent);
    await setDocs([doc({ filename: 'office.docx', extension: '.docx' })]);
    await page.getByRole('button', { name: '重建索引' }).click();
    check(!(await page.getByRole('checkbox').first().isChecked()), '每次重建授权重新开始');
  },
  async UI_003() { // UI_003：不可用只阻止办公，txt仍可提交。
    profileAvailable = false; await setup(); await setFile('docx');
    await page.getByRole('checkbox').first().check();
    check(await page.getByRole('button', { name: '提交本次操作' }).isDisabled(), '云能力不可用即使勾选仍阻止');
    check(await page.getByText('当前无法提交', { exact: false }).isVisible(), '中文受限原因可见');
    await setFile('txt'); check(await page.getByRole('button', { name: '提交本次操作' }).isEnabled(), '本地文本可用');
  },
  async UI_004() { // UI_004：active与latest失败同时展示，load后仍一致。
    await setup(); const row = doc({ latest_build: { index_batch_id: 'new-failed', state: 'failed', stage: 'embedding', chunk_count: 0, error_code: 'EMBEDDING_SERVICE_FAILED' } });
    await setDocs([row]); await page.getByRole('button', { name: '刷新索引状态' }).click();
    check((await page.locator('.document-panel').innerText()).includes(batch), '旧active身份仍显示');
    check(await page.getByText('EMBEDDING_SERVICE_FAILED', { exact: false }).isVisible(), '最新失败同时可见');
    check(await page.getByText('当前批次可检索', { exact: false }).isVisible(), '旧ready不被最新失败覆盖');
  },
  async UI_005() { // UI_005：阶段中文及未知进度；不产生伪百分比或退款承诺。
    await setup();
    for (const stage of ['preparing', 'remote_running', 'remote_converting', 'embedding', 'publish', 'stopped']) {
      await setDocs([doc({ latest_build: { state: 'waiting', stage, chunk_count: 0, parse: { parser_kind: 'mineru', stage, remote_outcome: 'unknown_may_continue' } } })]);
      const text = await page.locator('.document-panel').innerText();
      check(text.includes('进度未提供时为未知') && text.includes('远端可能继续处理'), '未知进度及本地停止边界', stage);
      check(!text.includes('100%') && !text.includes('已退款'), '不伪造完成比例或退款');
    }
  },
  async UI_006() { // UI_006：已受理丢包后真实store重放同key/原文件参数。
    let posts = 0;
    handler = async (r, path, req) => { if (path === '/api/v3/documents' && req.method() === 'POST' && ++posts === 1) { await r.abort('connectionreset'); return true; } return false; };
    await setup(); await setFile('txt'); await page.getByRole('button', { name: '提交本次操作' }).click();
    await page.getByRole('button', { name: '重试原上传（同一幂等键）' }).waitFor();
    await page.getByRole('button', { name: '重试原上传（同一幂等键）' }).click(); await page.waitForTimeout(80);
    const sent = calls.filter(r => r.method === 'POST' && r.path === '/api/v3/documents');
    check(sent.length === 2 && sent[0].key === sent[1].key, '未知上传沿用同幂等键', sent.map(r => r.key));
    check(sent.every(r => r.body.includes('sample.txt') && r.body.includes('safe input')), '原文件与参数重放');
  },
  async UI_007() { // UI_007：保留安全恢复目标；每次新UUID应实测失败，不能expected-failure。
    let count = 0; handler = async (r, path, req) => { if (path.includes('/index-builds') && req.method() === 'POST' && ++count === 1) { await r.abort(); return true; } return false; };
    await setup(); await setDocs([doc()]);
    await state(async row => { await window.__case.docs.rebuild(row, {}); await window.__case.docs.rebuild(row, {}); }, doc());
    const sent = calls.filter(r => r.path.includes('/index-builds') && r.method === 'POST');
    check(sent.length === 2 && sent[0].key === sent[1].key, '未知重建必须安全恢复原操作，不能无提示生成新键', sent.map(r => r.key));
  },
  async UI_008() { // UI_008：实际RAG store边界，不存在candidate_k控件。
    await setup('RagPanel');
    for (const [key, values] of [['topK', [0, 1, 20, 21]], ['radius', [-1, 0, 2, 3]]]) {
      for (const value of values) {
        const ok = await state(({ key, value }) => { const r = window.__case.rag; r.enabled = true; r.topK = 5; r.radius = 1; r[key] = value; try { r.selection(); return true; } catch { return false; } }, { key, value });
        check(ok === (key === 'topK' ? value >= 1 && value <= 20 : value >= 0 && value <= 2), '参数合法区间', { key, value });
      }
    }
    check(await page.getByText('candidate_k', { exact: false }).count() === 0, '不虚构候选数控件');
  },
  async UI_009() { // UI_009：实际诊断表单只调用诊断、不生成聊天。
    result = diagnostic({ mode: 'degraded', candidates: [{ chunk_id: 'c1', dense_score: .7, rerank_score: null }], omitted: [{ chunk_id: 'c2', reason: 'budget' }] });
    await setup('RagPanel'); await page.getByLabel('诊断查询').fill('ALPHA?'); await page.getByRole('button', { name: '执行诊断' }).click();
    await page.getByText('已明确降级', { exact: false }).waitFor();
    check((await page.locator('.rag-panel').innerText()).includes('dense 0.7'), '候选分数可见');
    check(await page.getByText('移除 c2：budget').isVisible(), '删减原因可见');
    check(calls.filter(r => r.method === 'POST').every(r => r.path === '/api/v3/retrieval-executions'), '诊断UI不创建Message或Run');
  },
  async UI_010() { // UI_010：文档迟到响应不能覆盖新库；Bundle迟到响应不能覆盖新组件。
    let release; const gate = new Promise(resolve => { release = resolve; });
    handler = async (r, path, req) => { if (path === '/api/v3/documents' && req.url().includes('knowledge_base_id=' + base)) { await gate; await r.fulfill({ json: { items: [doc({ filename: 'old-A.txt' })], next_cursor: null } }); return true; } return false; };
    await setup(); await state(() => { void window.__case.docs.load(); }); await page.waitForTimeout(50);
    await state(() => { window.__case.rag.selectedBase = 'base-B'; void window.__case.docs.load(); }); release(); await page.waitForTimeout(100);
    check(!(await page.locator('.document-panel').innerText()).includes('old-A.txt'), '旧库迟到响应被epoch丢弃');
    await state(() => { window.__case.rag.resetDiagnostic(); });
    check(await state(() => window.__case.rag.diagnostic === null), '切换诊断范围清旧事实');
    // 同一真实Viewer先挂起A，再切到B；A随后失败也不得污染B的正文或错误。
    let releaseBundle; const bundleGate = new Promise(resolve => { releaseBundle = resolve; });
    handler = async (r, path) => {
      if (path === '/api/v3/evidence-bundles/bundle-A') { await bundleGate; await r.fulfill({ status: 404, json: { code: 'OLD_BUNDLE_MISSING' } }); return true; }
      if (path === '/api/v3/evidence-bundles/bundle-B') { await r.fulfill({ json: bundle('bundle-B', { text: 'B current evidence' }) }); return true; }
      return false;
    };
    await setup('EvidenceViewer');
    await state(() => { window.__case.props.bundleId = 'bundle-B'; });
    await page.getByText('B current evidence', { exact: true }).waitFor(); releaseBundle(); await page.waitForTimeout(80);
    check(!(await page.locator('.evidence-viewer').innerText()).includes('OLD_BUNDLE_MISSING'), '旧Bundle失败不能污染新身份');
    // 正式Run store的两个observe交错，旧Run响应与事件均不能覆盖当前Run。
    let releaseRun; const runGate = new Promise(resolve => { releaseRun = resolve; });
    handler = async (r, path) => {
      if (path === '/api/v3/runs/run-A') { await runGate; await r.fulfill({ json: { run_id: 'run-A', thread_id: 't', branch_id: 'b', execution_schema_version: 3, status: 'running' } }); return true; }
      if (path === '/api/v3/runs/run-B') { await r.fulfill({ json: { run_id: 'run-B', thread_id: 't', branch_id: 'b', execution_schema_version: 3, status: 'running' } }); return true; }
      if (path.endsWith('/events')) { await r.fulfill({ json: { events: [], has_more: false, next_after_seq: 0 } }); return true; }
      if (path.endsWith('/events/stream')) { await r.fulfill({ contentType: 'text/event-stream', body: ': bounded stream\n\n' }); return true; }
      return false;
    };
    const oldRequest = page.waitForRequest(r => new URL(r.url()).pathname === '/api/v3/runs/run-A');
    await state(async () => { const { useThreadStore } = await import('/src/stores/thread.ts'); const t = useThreadStore(); t.selectedId = 't'; t.selectedBranchId = 'b'; window.__oldObserve = window.__case.run.observe('run-A'); });
    await oldRequest;
    await state(() => window.__case.run.observe('run-B')); releaseRun(); await state(() => window.__oldObserve);
    const scoped = await state(() => { const s = window.__case.run; s.append({ run_id: 'run-A', seq: 1, schema_version: 3, type: 'answer.delta', data: { text: 'old' } }, false); return { run: s.current.run_id, events: s.events.length }; });
    check(scoped.run === 'run-B' && scoped.events === 0, '迟到Run与旧事件均被当前身份隔离', scoped);
  },
  async UI_011() { // UI_011：Playwright时钟推进实际60次轮询，然后手动恢复。
    documents = [doc({ latest_build: { state: 'waiting', stage: 'parse', chunk_count: 0 } })];
    await setup(); await page.clock.install(); await state(() => window.__case.docs.load());
    for (let i = 0; i < 61; i++) { await page.clock.runFor(2100); await page.waitForTimeout(5); }
    check(await state(() => window.__case.docs.paused), '60次后暂停');
    const count = calls.filter(r => r.path === '/api/v3/documents').length;
    await page.clock.runFor(10000); check(calls.filter(r => r.path === '/api/v3/documents').length === count, '暂停不无限请求', count);
    documents = [doc()]; await page.getByRole('button', { name: '刷新索引状态' }).click();
    check(!(await state(() => window.__case.docs.paused)), '手动刷新恢复事实');
  },
  async UI_012() { // UI_012：实际store按run/seq去重、乱序排序且连接不宣布终态。
    await setup();
    const result = await state(async () => {
      const run = window.__case.run;
      const { useThreadStore } = await import('/src/stores/thread.ts'); const threads = useThreadStore();
      threads.selectedId = 't'; threads.selectedBranchId = 'b';
      return { terminalBefore: run.current?.status, empty: run.events.length };
    });
    check(result.empty === 0 && result.terminalBefore === undefined, '无Journal时不造终态');
    // 通过observe正式读取接口初始化activeRun，传输顺序由同源路由控制。
    handler = async (r, path) => {
      if (path === '/api/v3/runs/r') { await r.fulfill({ json: { run_id: 'r', thread_id: 't', branch_id: 'b', execution_schema_version: 3, status: 'running', context_plan: null } }); return true; }
      if (path.includes('/events')) { await r.fulfill({ json: { events: [], has_more: false, next_after_seq: 0 } }); return true; } return false;
    };
    await state(() => window.__case.run.observe('r'));
    const value = await state(() => {
      const s = window.__case.run; const make = (seq, run_id = 'r') => ({ schema_version: 3, run_id, seq, type: 'answer.delta', data: { task_id: 'task', generation: 1, attempt: 1, text: String(seq) } });
      s.append(make(2), false); s.append(make(1), false); s.append(make(1), false); s.append(make(3, 'other'), false);
      return { seq: s.events.map(e => e.seq), status: s.current.status };
    });
    check(JSON.stringify(value.seq) === '[1,2]', '乱序排序、重复与旧Run拒绝', value);
    check(value.status === 'running', 'EventSource连接不代替PG终态');
  },
  async UI_013() { // UI_013：实际Viewer显示身份/分数/组件hash及缺坐标提示。
    await setup('EvidenceViewer'); await page.getByText('未提供可可靠映射', { exact: false }).waitFor();
    const text = await page.locator('.evidence-viewer').innerText();
    check(text.includes(batch) && text.includes('0.8') && text.includes('未重排'), '证据身份及分数可见');
    await page.getByText('来源组件与内容 hash').click();
    check(await page.getByText('b'.repeat(64), { exact: false }).isVisible(), '组件hash可追溯');
  },
  async UI_014() { // UI_014：真实DOM清洗及网络观察，普通表格/代码保留。
    await setup(); const outgoing = []; page.on('request', r => { if (r.url().includes('evil.example')) outgoing.push(r.url()); });
    const result = await state(async () => {
      const { renderMarkdown } = await import('/src/markdown/render.ts');
      const root = document.createElement('div'); root.innerHTML = renderMarkdown('<script>window.bad=1</script>\n<img src="https://evil.example/x" onerror="window.bad=2">\n<a href="javascript:alert(1)">bad</a>\n\n|A|B|\n|---|---|\n|1|2|\n\n```txt\nsafe\n```'); document.body.append(root);
      return { unsafe: root.querySelectorAll('script,img,[onerror],[href^="javascript:"]').length, table: !!root.querySelector('table'), code: !!root.querySelector('code'), executed: window.bad };
    });
    await page.waitForTimeout(50);
    check(result.unsafe === 0 && !result.executed, '危险节点/属性/协议不执行', result);
    check(result.table && result.code && outgoing.length === 0, '普通Markdown可读且无外部资产请求', outgoing);
  },
  async UI_015() { // UI_015：安全状态中文分辨，未知码不伪成功。
    await setup('RagPanel');
    for (const mode of ['empty', 'degraded']) { await state(value => { window.__case.rag.diagnostic = value; }, diagnostic({ mode })); await rendered(); check((await page.locator('.rag-panel').innerText()).includes(mode === 'empty' ? '无可用证据' : '已明确降级'), '中文模式区别', mode); }
    await state(() => { window.__case.rag.error = 'UNKNOWN_SAFE_CODE：诊断状态读取失败'; });
    const text = await page.locator('.rag-panel').innerText();
    check(text.includes('UNKNOWN_SAFE_CODE') && text.includes('诊断状态读取失败') && !text.includes('Traceback'), '未知错误安全兜底');
  },
  async UI_016() { // UI_016：重复文档页去重；证据offset续读与对象切换。
    await setup();
    handler = async (r, path) => { if (path === '/api/v3/documents') { await r.fulfill({ json: { items: [doc()], next_cursor: null } }); return true; } return false; };
    await state(async row => { const d = window.__case.docs; d.items = [row]; d.cursor = 'page2'; await Promise.all([d.more(), d.more()]); }, doc());
    check(await state(() => window.__case.docs.items.length) === 1, '重复分页不重复文档');
    await state(() => { window.__case.docs.inspected = { document_id: 'old' }; window.__case.docs.chunks = [{ chunk_id: 'old' }]; });
    await state(() => window.__case.docs.load());
    check(await state(() => window.__case.docs.inspected === null && window.__case.docs.chunks.length === 0), '重新加载清理旧切片范围');
    const chunks = Array.from({ length: 21 }, (_, i) => ({ chunk_id: 'chunk-' + i, text: 'page-' + i, start_offset: i, end_offset: i + 1, locations: [] }));
    handler = async (r, path, req) => {
      if (path.endsWith('/chunks')) { const more = new URL(req.url()).searchParams.has('cursor'); await r.fulfill({ json: { items: more ? chunks.slice(20) : chunks.slice(0, 20), next_cursor: more ? null : 'page2' } }); return true; }
      return false;
    };
    await state(row => window.__case.docs.inspect(row), doc());
    check(await state(() => window.__case.docs.chunks.length) === 20, '切片初页有界20片');
    await state(async row => { await Promise.all([window.__case.docs.inspect(row, true), window.__case.docs.inspect(row, true)]); }, doc());
    const ids = await state(() => window.__case.docs.chunks.map(c => c.chunk_id));
    const duplicateChunks = ids.length !== 21 || new Set(ids).size !== 21;
    // 先采证证据翻页，再统一判断重复切片，避免前一个失败漏掉独立投影层。
    handler = async (r, path, req) => {
      if (path.includes('/evidence-bundles/')) { const offset = Number(new URL(req.url()).searchParams.get('offset')); await r.fulfill({ json: bundle(path.split('/').at(-1), { text: offset === 0 ? 'A'.repeat(4000) : 'TAIL', next_offset: offset === 0 ? 4000 : null }) }); return true; }
      return false;
    };
    await setup('EvidenceViewer'); await page.getByRole('button', { name: '继续读取证据' }).waitFor();
    await page.getByRole('button', { name: '继续读取证据' }).click();
    await page.getByRole('button', { name: '继续读取证据' }).waitFor({ state: 'detached' });
    check((await page.locator('.evidence-viewer pre').innerText()) === 'A'.repeat(4000) + 'TAIL', '证据按offset=4000拼接且末页停止');
    check(!duplicateChunks, '重复加载更多切片不得重复或遗漏', ids);
  },
  async UI_017() { // UI_017：真实阶段只来自事件，文档中的伪造阶段不注入系统timeline。
    await setup();
    const result = await state(async () => {
      const { createApp } = await import('/node_modules/.vite/deps/vue.js'); const { default: Timeline } = await import('/src/components/RunTimeline.vue');
      const root = document.createElement('div'); document.body.append(root);
      const events = [{ seq: 1, type: 'tool.stage', data: { stage: 'dense_search' } }, { seq: 2, type: 'context.planned', data: {} }, { seq: 3, type: 'PRIVATE_CHAIN', data: { text: 'hidden chain sentinel' } }];
      createApp(Timeline, { run: { status: 'running', task: { attempt: 1, generation: 1, state: 'running' }, created_at: new Date().toISOString() }, events, connection: 'connected', error: '', failureCode: '' }).use(window.__case.pinia).mount(root);
      await new Promise(resolve => requestAnimationFrame(resolve)); return root.innerText;
    });
    check(result.includes('tool.stage') && result.includes('context.planned'), '公开阶段可见');
    check(!result.includes('hidden chain sentinel') && !result.includes('PRIVATE_CHAIN'), '非公开事件及隐藏内容不展示');
  },
  async UI_018() { // UI_018：取消按钮调用服务端，刷新恢复事实且旧active保留。
    await setup(); await setDocs([doc({ latest_build: { index_batch_id: 'pending-build', state: 'waiting', stage: 'parse', chunk_count: 0 } })]);
    documents = [doc({ latest_build: { index_batch_id: 'pending-build', state: 'cancelled', stage: 'completed', chunk_count: 0 } })];
    await page.getByRole('button', { name: '请求取消构建' }).click(); await page.getByText('已取消', { exact: false }).waitFor();
    check(calls.some(r => r.path === '/api/v3/index-builds/pending-build/cancel'), '取消经正式HTTP入口');
    check((await page.locator('.document-panel').innerText()).includes(batch), '取消候选保留旧active');
    check(!(await page.locator('.document-panel').innerText()).includes('云端已撤回'), '不声称撤回云端');
  },
  async QLT_005() { // QLT_005：运行时事件解析对严格Schema负例的拒绝边界。
    await setup();
    const result = await state(async () => {
      const { parseV3Event } = await import('/src/events/rag-event-stream.ts');
      const valid = { schema_version: 3, event_id: 'e', run_id: 'r', seq: 1, type: 'tool.stage', occurred_at: new Date().toISOString(), data: { task_id: 't', attempt: 1, generation: 1, call_id: 'c', execution_id: 'x', tool_version: 1, stage: 'dense' } };
      const bad = [ { ...valid, schema_version: 99 }, { ...valid, seq: 0 }, { ...valid, type: 'unknown' }, { ...valid, data: { ...valid.data, generation: 0 } }, { ...valid, data: { ...valid.data, tool_version: 99 } }, { ...valid, data: { ...valid.data, count: -1 } } ];
      return bad.map((value, index) => { try { parseV3Event(value); return { index, rejected: false }; } catch { return { index, rejected: true }; } });
    });
    check(result.every(r => r.rejected), '严格契约非法事件不得追加到当前Run', result);
  },
};
let output;
try {
  note('准备', { case_id: args.case, browser: browser.version(), evidence: '真实Chromium+生产Vue/Pinia；受控同源HTTP仅证明投影语义' });
  if (!cases[args.case]) throw new Error('BROWSER_CASE_NOT_IMPLEMENTED');
  await cases[args.case](); output = { passed: true, assertions, observations };
} catch (error) {
  output = { passed: false, assertions, observations, error: String(error.message).slice(0, 300), ...(assertions === 0 ? { harness_error: error.name + ':' + String(error.message).slice(0, 200) } : {}) };
} finally { await context.close(); await browser.close(); proxy.closeAllConnections(); await new Promise(resolve => proxy.close(resolve)); }
console.log(JSON.stringify(output));
process.exitCode = output.passed ? 0 : 1;
