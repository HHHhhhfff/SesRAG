import { openCategory } from '../tooling/product-category.mjs';
import { assert, key, thread, request, answer, done, send, events, scenario, barrier, release, delay, until } from './support.mjs';
import { openBrowser, openPage, pageRunId } from './browser-support.mjs';

export const nearestRank = (values, quantile = 0.95) => [...values].sort((a, b) => a - b)[Math.ceil(quantile * values.length) - 1];
export function latencyInterval({ L, U, D_low, D_high }) {
  assert.ok(L <= U && D_low <= D_high, '测量区间顺序非法');
  const lower = Math.max(0, D_low - U); const upper = Math.max(0, D_high - L);
  return { lower_ms: lower, upper_ms: upper, status: upper <= 1000 ? 'passed' : lower > 1000 ? 'failed' : 'blocked' };
}

async function main(contextFile) {
  const suite = openCategory('performance', contextFile); const c = suite.context;
  const health = (await request(c, '/health/ready')).data; assert.equal(health.worker_count, 1, '性能基线必须只有一个Worker');
  // PERF_001：预热不混入正式30样本；慢样本/失败样本不删除或自动重试替换。
  await suite.test('PERF_001', async () => {
    const warm = await thread(c, 'PERF_001预热'); await answer(c, warm, '预热');
    const samples = [];
    for (let index = 0; index < 30; index++) {
      const item = await thread(c, `PERF_001-${index}-${key().slice(0, 8)}`);
      const started = performance.now(); let observed;
      try {
        observed = await request(c, `/api/v2/threads/${item.thread_id}/messages`, { method: 'POST', expected: 201,
          headers: { 'Idempotency-Key': key() }, body: { branch_id: item.default_branch_id, content: `性能样本${index}`, expected_version: 0, model_profile_id: 'mock-default', model_profile_version: 1 } });
        samples.push({ index, start_ms: started, end_ms: performance.now(), status: observed.status, run_id: observed.data.run_id });
        assert.ok(observed.data.run_id && observed.data.task_id); await done(c, observed.data.run_id);
      } catch (error) { samples.push({ index, start_ms: started, end_ms: performance.now(), error: error.message }); }
    }
    for (const sample of samples) sample.duration_ms = sample.end_ms - sample.start_ms;
    const p95 = nearestRank(samples.map((sample) => sample.duration_ms));
    const evidence = suite.evidence('PERF_001-samples.json', { clock: 'host performance.now monotonic', warmup_count: 1, algorithm: 'nearest-rank ceil(0.95*N)', health, samples, p95_ms: p95 });
    assert.equal(samples.length, 30); assert.equal(samples.filter((sample) => sample.error).length, 0, '提交样本存在功能/环境失败，禁止据低p95通过'); assert.ok(p95 <= 1000, `提交p95=${p95.toFixed(2)}ms超过1000ms`);
    return { actual: `完整30样本提交API p95=${p95.toFixed(2)}ms；所有提交均返回合法身份；未删除慢样本。`, evidence_paths: [evidence] };
  });
  // PERF_002：PG可见性通过每次新请求的新READ COMMITTED快照查询；DOM也由宿主单调时钟夹定。
  await suite.test('PERF_002', async () => {
    const browser = await openBrowser(); const samples = [];
    try {
      for (let index = 0; index < 30; index++) {
        const token = `PERF_DELTA_${index}_${key().slice(0, 8)}`; const item = await thread(c, `PERF_002-${index}`);
        await scenario(c, { kind: 'stall', chunks: ['', token], stall_after_chunk: 1 });
        const created = await send(c, item, '首delta到DOM测量', 'ws-http-a'); const held = await barrier(c);
        let session;
        try {
          session = await openPage(browser, c, item); const page = session.page;
          assert.equal(await pageRunId(page), created.run_id);
          await until(() => page.evaluate(async () => { const { useRunStore } = await import('/src/stores/run.ts'); return useRunStore().connection; }), (value) => value === 'connected', '首片释放前SSE已订阅');
          const checks = []; const initialStart = performance.now(); const beforeEvents = await events(c, created.run_id); const initialEnd = performance.now();
          assert.ok(!beforeEvents.some((event) => event.type === 'answer.delta' && event.data.text?.includes(token)));
          const domStart = performance.now(); assert.ok(!(await page.locator('.message-list').innerText()).includes(token)); const domEnd = performance.now();
          let L = initialStart; let U; let D_low = domStart; let D_high;
          await release(c, held);
          const deadline = performance.now() + 15000;
          const pgPoll = async () => {
            while (performance.now() < deadline) {
              const start = performance.now(); const journal = await events(c, created.run_id); const end = performance.now();
              const seen = journal.some((event) => event.type === 'answer.delta' && event.data.text?.includes(token)); checks.push({ source: 'PG via REST fresh request', start_ms: start, end_ms: end, seen });
              if (seen) { U = end; return; } L = start; await delay(10);
            }
            throw new Error('未观察到持久首delta');
          };
          const domPoll = async () => {
            while (performance.now() < deadline) {
              const start = performance.now(); const seen = (await page.locator('.message-list').innerText()).includes(token); const end = performance.now();
              checks.push({ source: 'Chromium DOM', start_ms: start, end_ms: end, seen });
              if (seen) { D_high = end; return; } D_low = start; await delay(10);
            }
            throw new Error('未观察到首delta DOM');
          };
          await Promise.all([pgPoll(), domPoll()]);
          const interval = latencyInterval({ L, U, D_low, D_high });
          samples.push({ index, run_id: created.run_id, L, U, D_low, D_high, initial_query_end_ms: initialEnd, initial_dom_end_ms: domEnd,
            ...interval, checks, clock_error_ms: 0, clock_mapping: 'PG请求和DOM观测均用同一宿主performance.now前后包围，无跨时钟换算' });
          await done(c, created.run_id);
        } catch (error) { samples.push({ index, run_id: created.run_id, status: 'failed', error: error.message }); try { await release(c, held); } catch { /* 已释放或已结束，不改写原始观察。 */ } }
        finally { await session?.session.close(); }
      }
    } finally { await browser.close(); }
    const evidence = suite.evidence('PERF_002-samples.json', { query_isolation: 'fresh HTTP request -> new SQLAlchemy session -> PostgreSQL READ COMMITTED', clock: 'host monotonic bracketing for both channels', samples });
    assert.equal(samples.length, 30);
    const status = samples.some((sample) => sample.status === 'failed') ? 'failed' : samples.some((sample) => sample.status === 'blocked') ? 'blocked' : 'passed';
    return { status, actual: `保留30个独立首delta区间：通过${samples.filter((item) => item.status === 'passed').length}、失败${samples.filter((item) => item.status === 'failed').length}、测量交叠受限${samples.filter((item) => item.status === 'blocked').length}。`,
      reason_code: status === 'passed' ? null : 'DELTA_LATENCY_INTERVAL', reason: '仅区间上界≤1000ms通过；下界>1000ms失败；交叠为测量不足。', evidence_paths: [evidence] };
  });
  return suite.finish();
}
if (process.argv.includes('--context')) main(process.argv[process.argv.indexOf('--context') + 1]).then((code) => { process.exitCode = code; }).catch((error) => { console.error(`【performance】工程错误：${error.message}`); process.exitCode = 2; });
