import fs from 'node:fs';
import path from 'node:path';
import { helper, atomicJson } from '../tooling/product-category.mjs';
import { assert, key, thread, send, answer, done, run, events, scenario, observations, barrier, release, request, detail, until, cancelledSource } from './support.mjs';
import { validate, upload } from './compatibility-runtime.mjs';
import { openBrowser, openPage } from './browser-support.mjs';

export const nextChatSequence = async (c) => Math.max(0, ...(await observations(c)).requests.map((item) => item.request_seq)) + 2;

// RUN_009/UI_007共用实际故障输入，不共用任何成功结果或预置终态。
export async function terminalSamples(c, prefix) {
  const results = [];
  for (const kind of ['success', 'retry', 'failure', 'cancel']) {
    const t = await thread(c, `${prefix}-${kind}-${key().slice(0, 8)}`); let created;
    if (kind === 'cancel') created = await cancelledSource(c, t, `${prefix}取消`);
    else {
      await scenario(c, kind === 'failure' ? { kind: 'http-error', http_status: 401 }
        : kind === 'retry' ? { kind: 'http-error', http_status: 503, request_seq: await nextChatSequence(c) } : { chunks: ['阶段成功回答'] });
      created = await send(c, t, `${prefix}真实阶段${kind}`, 'ws-http-a');
    }
    const finished = await done(c, created.run_id, 90000); const expected = { success: 'succeeded', retry: 'succeeded', failure: 'failed', cancel: 'cancelled' }[kind];
    assert.equal(finished.status, expected, `${prefix}/${kind}前提失败`);
    assert.equal(finished.task.attempt, kind === 'retry' ? 2 : 1, `${prefix}/${kind}尝试数错误`);
    results.push({ kind, thread: t, created, finished, journal: await events(c, created.run_id) });
  }
  await scenario(c); return results;
}

async function pgFacts(suite, rid) {
  atomicJson(path.join(suite.tmp, 'run-facts-input.json'), { run_id: rid });
  await helper(suite.context, 'observe-run-facts');
  const facts = JSON.parse(fs.readFileSync(path.join(suite.tmp, 'run-facts.json'), 'utf8'));
  assert.equal(facts.run_id, rid); assert.equal(facts.isolation, 'read committed'); return facts;
}
const projection = (items) => items.map(({ event_id, seq, type, data, schema_version }) => ({ event_id, seq, type, data, schema_version }));

// 读取真正SSE数据帧；活动流达到目标便断开观察，不取消业务Run。
export async function readSse(c, rid, { after = 0, header, stop, timeout = 15000 } = {}) {
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), timeout); const packets = [];
  try {
    const response = await fetch(`${c.api_base_url}/api/v2/runs/${rid}/events/stream?after_seq=${after}`, { headers: header === undefined ? {} : { 'Last-Event-ID': String(header) }, signal: controller.signal });
    assert.equal(response.status, 200); const reader = response.body.getReader(); const decoder = new TextDecoder(); let pending = '';
    while (true) {
      const part = await reader.read(); if (part.done) break; pending += decoder.decode(part.value, { stream: true });
      let end;
      while ((end = pending.indexOf('\n\n')) >= 0) {
        const frame = pending.slice(0, end); pending = pending.slice(end + 2);
        for (const line of frame.split('\n')) if (line.startsWith('data: ')) {
          const item = JSON.parse(line.slice(6)); validate('run_event_v2.json', item); packets.push(item);
          if (stop?.(item)) { await reader.cancel(); return packets; }
        }
      }
    }
    return packets;
  } finally { clearTimeout(timer); controller.abort(); }
}

// RUN_009：四条真实Worker路径，同时核验PG、REST、SSE与白名单契约。
async function stageEvents(suite) {
  const c = suite.context; await upload(c, 'RUN_009-evidence.txt', 'EVIDENCE-RUN-STAGES 本机虚构的阶段检索证据。');
  const samples = await terminalSamples(c, 'RUN_009'); const results = [];
  for (const sample of samples) {
    const pg = await pgFacts(suite, sample.created.run_id); const sse = await readSse(c, sample.created.run_id);
    assert.deepEqual(projection(sample.journal), pg.events); assert.deepEqual(projection(sse), pg.events);
    assert.equal(pg.status, sample.finished.status); assert.equal(pg.task.state, sample.finished.status);
    assert.deepEqual(pg.events.map((item) => item.seq), Array.from({ length: pg.events.length }, (_, index) => index + 1));
    const types = pg.events.map((item) => item.type);
    for (const type of ['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'context.planned', `run.${pg.status}`]) assert.ok(types.includes(type), `${sample.kind}缺真实阶段${type}`);
    if (sample.kind === 'retry') assert.equal(types.filter((type) => type === 'task.retry_scheduled').length, 1);
    else assert.ok(!types.includes('task.retry_scheduled'));
    assert.equal(pg.assistant_ids.length, pg.status === 'succeeded' ? 1 : 0);
    for (const event of sample.journal) {
      validate('run_event_v2.json', event);
      assert.throws(() => validate('run_event_v2.json', { ...event, data: { ...event.data, hidden_prompt: 'NEGATIVE_SECRET' } }), '嵌套额外敏感字段必须拒绝');
      if (event.data.attempt > 0) assert.equal(event.data.task_id, sample.created.task_id);
    }
    const retrieval = pg.events.find((item) => item.type === 'retrieval.completed'); assert.ok(retrieval.data.count > 0);
    results.push({ kind: sample.kind, pg, sse_count: sse.length });
  }
  return { actual: '成功检索、自动重试、永久失败、取消四组真实Run：独立PG只读事务、REST、SSE事件身份/payload逐项一致；终态/assistant与Task事实一致，额外敏感字段契约拒绝。', results };
}

// RUN_010：Provider未发第二片/结束标记，两个独立观察通道已看到第一片。
async function firstDelta(suite) {
  const c = suite.context; const t = await thread(c, 'RUN_010-real-PG');
  await scenario(c, { kind: 'stall', chunks: ['FIRST_CHUNK', 'FINAL_TAIL'] }); const created = await send(c, t, '首片独立发布', 'ws-http-a'); const held = await barrier(c);
  let pg; let packets;
  try {
    await until(() => events(c, created.run_id), (journal) => journal.some((event) => event.type === 'answer.delta' && event.data.text.includes('FIRST_CHUNK')), '未结束时首片REST可见');
    pg = await pgFacts(suite, created.run_id); assert.equal(pg.status, 'running'); assert.equal(pg.assistant_ids.length, 0);
    assert.ok(pg.events.some((event) => event.type === 'answer.delta' && event.data.text === 'FIRST_CHUNK'));
    packets = await readSse(c, created.run_id, { stop: (event) => event.type === 'answer.delta' });
    assert.equal(packets.at(-1).data.text, 'FIRST_CHUNK');
    const record = (await observations(c)).requests.find((item) => item.request_seq === held.request_seq); assert.equal(record.finished, false); assert.equal(record.waiting_release, true);
  } finally { await release(c, held); }
  assert.equal((await done(c, created.run_id)).status, 'succeeded'); assert.equal((await detail(c, t.thread_id)).messages.at(-1).content, 'FIRST_CHUNKFINAL_TAIL');
  return { actual: 'Provider真实屏障仍挂起时，独立PG READ COMMITTED事务及SSE均已见FIRST_CHUNK，Run running且无最终assistant；释放后正文顺序正确。', pg, sse_first: packets.at(-1) };
}

// RUN_011/012：实际终态流分页/游标/有限尾页，额外复用真实客户端归并器。
async function replay(suite, boundary = false) {
  const c = suite.context; await scenario(c, { kind: 'slow', chunks: Array.from({ length: 20 }, (_, index) => `DELTA_${index};`), chunk_delay_ms: 150 });
  const t = await thread(c, boundary ? 'RUN_012-cursors' : 'RUN_011-replay'); const created = await send(c, t, '事件分页', 'ws-http-a');
  const early = await until(() => events(c, created.run_id), (journal) => journal.filter((item) => item.type === 'answer.delta').length >= 2, '流式断点');
  const k = early.at(-1).seq; const observed = await readSse(c, created.run_id, { after: k }); await done(c, created.run_id); const journal = await events(c, created.run_id);
  assert.deepEqual(projection(observed), projection(journal.filter((item) => item.seq > k)));
  for (const limit of [1, 2]) {
    let after = 0; const pages = [];
    while (true) { const page = (await request(c, `/api/v2/runs/${created.run_id}/events?after_seq=${after}&limit=${limit}`)).data; pages.push(...page.events); if (!page.has_more) break; assert.ok(page.next_after_seq > after); after = page.next_after_seq; }
    assert.deepEqual(projection(pages), projection(journal));
  }
  for (const after of [0, k, journal.at(-1).seq, journal.at(-1).seq + 100]) assert.deepEqual(projection(await readSse(c, created.run_id, { after })), projection(journal.filter((item) => item.seq > after)));
  if (boundary) {
    for (const query of ['after_seq=-1', 'after_seq=bad', 'limit=0', 'limit=1001']) await request(c, `/api/v2/runs/${created.run_id}/events?${query}`, { expected: 422 });
    const defaults = (await request(c, `/api/v2/runs/${created.run_id}/events`)).data; assert.ok(defaults.events.length <= 200);
    for (const header of ['', '-1', 'invalid']) assert.deepEqual(projection(await readSse(c, created.run_id, { after: k, header })), projection(journal));
    assert.deepEqual(projection(await readSse(c, created.run_id, { after: 0, header: k })), projection(journal.filter((item) => item.seq > k)));
  } else {
    const browser = await openBrowser(); let opened;
    try {
      opened = await openPage(browser, c, t); const seq = await opened.page.evaluate(async (raw) => {
        const { useRunStore } = await import('/src/stores/run.ts'); const store = useRunStore();
        await store.observe(raw[0].run_id); store.events = [];
        for (const event of [...raw].reverse().concat(raw, raw.slice(0, 3))) store.append(event, false);
        return store.events.map((event) => event.seq);
      }, journal); assert.deepEqual(seq, journal.map((item) => item.seq));
    } finally { await opened?.session.close(); await browser.close(); }
  }
  return { actual: boundary ? 'REST非法参数422；SSE独立Header优先级/坏值回0；默认上限与末尾有限关闭均经实际请求验证。' : '持续Run真实断点后SSE补放与REST小页一致；从0/断点/末尾/越界完整补放，真实客户端归并器对重排和重复事件只保留原始唯一seq。', run_id: created.run_id, k, event_count: journal.length };
}

// RUN_029：正常、自动attempt、新会话层Run三种身份分别沿PG/API/Context/Event/日志追溯。
async function correlations(suite) {
  const c = suite.context; await scenario(c); const t = await thread(c, 'RUN_029-normal'); const normal = await answer(c, t, '关联正常输入', 'ws-http-a');
  await scenario(c, { kind: 'http-error', http_status: 503, request_seq: await nextChatSequence(c) }); const retryThread = await thread(c, 'RUN_029-retry'); const retried = await send(c, retryThread, '关联自动尝试', 'ws-http-a');
  assert.equal((await done(c, retried.run_id)).task.attempt, 2); await scenario(c);
  const related = (await request(c, `/api/v2/runs/${normal.run_id}/regenerate`, { method: 'POST', headers: { 'Idempotency-Key': key() }, body: {}, expected: 201 })).data; await done(c, related.run_id);
  const results = [];
  for (const created of [normal, retried, related]) {
    const api = await run(c, created.run_id); const pg = await pgFacts(suite, created.run_id); const context = (await request(c, `/api/v2/runs/${created.run_id}/context`)).data.plan;
    assert.equal(pg.task.task_id, created.task_id); assert.equal(pg.user_message_id, api.user_message_id);
    assert.equal(context.run_id, api.run_id); assert.equal(context.thread_id, api.thread_id); assert.equal(context.branch_id, api.branch_id); assert.equal(context.task_id, created.task_id); assert.equal(context.generation, api.task.generation);
    for (const event of pg.events) if (event.data.task_id) assert.equal(event.data.task_id, created.task_id);
    assert.equal(pg.input_creator_run_id, created === related ? normal.run_id : created.run_id);
    if (created === related) { assert.equal(api.parent_run_id, normal.run_id); assert.equal(api.operation_kind, 'regenerate'); }
    results.push({ api, pg, context });
  }
  const { records } = (await helper(c, 'correlation-logs')).result;
  const selected = records.filter((record) => results.some(({ api }) => api.run_id === record.run_id));
  for (const { api } of results) assert.ok(selected.some((record) => record.run_id === api.run_id && record.task_id === api.task.task_id && record.generation === api.task.generation), '默认结构化日志缺实际执行身份');
  return { actual: '正常、自动retry、用户regenerate三组PG/API/计划/Event/结构化日志身份完整关联；自动代数不新建Run，用户新Run复用输入但Message.run_id仍为原创建者。', results, log_records: selected };
}

export const runEvidenceRuntime = { RUN_009: stageEvents, RUN_010: firstDelta, RUN_011: (suite) => replay(suite), RUN_012: (suite) => replay(suite, true), RUN_029: correlations };
