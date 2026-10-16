import { executionCoverage } from './execution-coverage.mjs';
import { runCategory, assert } from '../lib/category-kit.mjs';
import { uuid, lazy, sqlValue, runFacts, stoppedWorker, successful, readSSE, sseSummary } from './run-test-driver.mjs';

export const coveredCases = ['SSE_001', 'SSE_002', 'SSE_003', 'SSE_004', 'SSE_005'];
await runCategory('sse', async s => {
  const ctx = s.ctx;
  // SSE_001：独立中文单chunk证据保证JSON内容含中文，格式和各游标优先级分别检查。
  const normal = lazy(async () => {
    const text = `SSE_001 ${uuid()} 中文流式证据`;
    const uploaded = await ctx.upload('SSE_001-中文.txt', Buffer.from(text, 'utf8')); assert.equal(uploaded.status, 201);
    assert.equal((await ctx.waitDoc(uploaded.body.document_id)).status, 'indexed');
    return successful(ctx, 'SSE_001 中文格式', text);
  });
  await s.check('SSE_001', 'TP-SSE-001', 'wire_format', 'text/event-stream；每帧id=seq、event=type、JSON envelope与DB相同，中文保真且收到终态后EOF', async () => {
    const data = await normal(); const stream = await readSSE(ctx, data.run.run_id);
    const trace = ctx.evidence('sse/SSE_001-wire.json', sseSummary(stream)); s.note(`SSE_001 run_id=${data.run.run_id}；流证据=${trace}`);
    assert.equal(stream.status, 200); assert.match(stream.content_type, /^text\/event-stream/i); assert.ok(stream.eof && !stream.timed_out);
    assert.equal(stream.frames.length, data.events.length);
    for (let index = 0; index < stream.frames.length; index++) {
      const frame = stream.frames[index]; const event = data.events[index];
      assert.equal(frame.id, String(event.seq)); assert.equal(frame.event, event.type); assert.equal(frame.data.schema_version, 1);
      assert.equal(frame.data.event_id, event.event_id); assert.equal(frame.data.run_id, event.run_id); assert.equal(frame.data.seq, event.seq);
      assert.equal(frame.data.type, event.type); assert.ok(JSON.stringify(frame.data.data) === JSON.stringify(event.data), 'SSE payload必须与DB事件相同'); assert.equal(Date.parse(frame.data.occurred_at), Date.parse(event.occurred_at));
    }
    const deltas = stream.frames.filter(frame => frame.event === 'answer.delta').map(frame => frame.data.data.text).join('');
    assert.ok(deltas.includes('中文流式证据'), 'SSE JSON必须保留中文证据');
    assert.equal(stream.frames.at(-1).event, 'run.succeeded');
    return { run_id: data.run.run_id, stream: sseSummary(stream), chinese_preserved: true, trace };
  });
  for (const item of [
    { sub: 'valid_header_wins', after: 1, header: '3', effective: 3 },
    { sub: 'zero_header_wins', after: 3, header: '0', effective: 0 },
    { sub: 'negative_header_zero', after: 3, header: '-1', effective: 0 },
    { sub: 'invalid_header_zero', after: 3, header: 'bad-cursor', effective: 0 },
    { sub: 'absent_header_query', after: 2, effective: 2 },
  ]) {
    await s.check('SSE_001', 'TP-SSE-003', item.sub, `${item.sub}：Header优先，负/非法Header归0，无Header用query；收到精确DB后缀`, async () => {
      const data = await normal(); const stream = await readSSE(ctx, data.run.run_id, item);
      assert.equal(stream.status, 200); assert.ok(stream.eof && !stream.timed_out);
      const expected = data.events.filter(event => event.seq > item.effective);
      assert.equal(stream.frames.length, expected.length);
      assert.deepEqual(stream.frames.map(frame => [frame.data.event_id, frame.data.seq]), expected.map(event => [event.event_id, event.seq]));
      assert.ok(stream.frames.every((frame, index) => JSON.stringify(frame.data.data) === JSON.stringify(expected[index].data)));
      return { run_id: data.run.run_id, query: item.after, header: item.header ?? '未发送', effective_cursor: item.effective, stream: sseSummary(stream) };
    });
  }

  // SSE_002：已有历史后缀可验证；真正读取/新追加竞争交界的屏障仍独立blocked。
  await s.check('SSE_002', 'TP-SSE-002', 'historical_suffix', '独立完成Run从中间游标连接，补齐完整DB历史后缀且无其它Run事件', async () => {
    const data = await successful(ctx, 'SSE_002 历史补放'); const after = Math.floor(data.events.at(-1).seq / 2);
    const stream = await readSSE(ctx, data.run.run_id, { after }); assert.equal(stream.status, 200); assert.ok(stream.eof);
    const expected = data.events.filter(event => event.seq > after);
    assert.deepEqual(stream.frames.map(frame => [frame.data.seq, frame.data.event_id]), expected.map(event => [event.seq, event.event_id]));
    assert.ok(stream.frames.every(frame => frame.data.run_id === data.run.run_id));
    return { run_id: data.run.run_id, after_seq: after, stream: sseSummary(stream), limitation: '历史后缀，不含读取/追加竞争屏障' };
  });
  await s.check('SSE_002', 'TP-SSE-002', 'history_then_worker_events', 'queued初始历史已接收后启动Worker，原连接继续接收新事件至终态，最终序列等于DB完整后缀', () => stoppedWorker(ctx, async () => {
    const thread = await ctx.thread('SSE_002 历史衔接实时'); const submitted = await ctx.submit(thread.thread_id, 'SSE_002 实时续接问题', uuid());
    const initial = await ctx.events(submitted.run_id); assert.deepEqual(initial.map(event => event.seq), [1, 2]);
    let started = false;
    const stream = await readSSE(ctx, submitted.run_id, { after: 1, timeoutMs: 20000, onFrame: async frame => {
      if (!started && frame.data.seq === 2) {
        started = true; assert.equal(ctx.compose(['start', 'worker']).code, 0); await ctx.ready(15000);
      }
    } });
    const trace = ctx.evidence('sse/SSE_002-live.json', sseSummary(stream)); s.note(`SSE_002 run_id=${submitted.run_id}；证据=${trace}`);
    assert.ok(started, '必须先收到初始历史再启动Worker'); assert.equal(stream.status, 200); assert.ok(stream.eof && !stream.timed_out);
    assert.equal((await ctx.waitRun(submitted.run_id)).status, 'succeeded');
    const events = await ctx.events(submitted.run_id, 1);
    assert.deepEqual(stream.frames.map(frame => [frame.data.seq, frame.data.event_id]), events.map(event => [event.seq, event.event_id]));
    assert.ok(stream.frames.every(frame => frame.data.run_id === submitted.run_id));
    assert.ok(stream.frames.some(frame => frame.data.seq > 2));
    return { run_id: submitted.run_id, stream: sseSummary(stream), trace, limitation: 'Worker在历史已交付后启动；没有历史读取瞬间的竞争屏障' };
  }));

  // SSE_003：queued仍未完成时真实关闭连接，恢复后同Run完成；首delta执行中屏障另记录。
  await s.check('SSE_003', 'TP-SSE-004', 'disconnect_while_queued', 'Run尚queued时断开SSE不写取消，恢复Worker后原身份成功且从最后seq完整补放', async () => {
    let prepared;
    await stoppedWorker(ctx, async () => {
      const thread = await ctx.thread('SSE_003 断开不取消'); const submitted = await ctx.submit(thread.thread_id, 'SSE_003 排队时断流问题', uuid());
      const stream = await readSSE(ctx, submitted.run_id, { maxFrames: 1 }); assert.equal(stream.status, 200); assert.equal(stream.frames.length, 1);
      const facts = runFacts(ctx, submitted.run_id); assert.equal(facts.status, 'queued'); assert.equal(facts.cancel_requested_at, null);
      assert.ok(!(await ctx.events(submitted.run_id)).some(event => event.type === 'run.cancelled'));
      prepared = { thread, submitted, lastSeq: stream.frames.at(-1).data.seq, disconnected: sseSummary(stream) };
    });
    const done = await ctx.waitRun(prepared.submitted.run_id); assert.equal(done.status, 'succeeded'); assert.equal(done.task.task_id, prepared.submitted.task_id);
    const facts = runFacts(ctx, done.run_id); assert.equal(facts.cancel_requested_at, null); assert.ok(facts.assistant_message_id);
    const events = await ctx.events(done.run_id); assert.ok(!events.some(event => event.type === 'run.cancelled'));
    const reconnect = await readSSE(ctx, done.run_id, { after: prepared.lastSeq }); assert.ok(reconnect.eof);
    assert.deepEqual(reconnect.frames.map(frame => frame.data.seq), events.filter(event => event.seq > prepared.lastSeq).map(event => event.seq));
    assert.equal((await ctx.detail(prepared.thread.thread_id)).messages.filter(message => message.role === 'assistant').length, 1);
    return { run_id: done.run_id, task_id: done.task.task_id, last_seq: prepared.lastSeq, disconnected: prepared.disconnected, reconnect: sseSummary(reconnect), limitation: '断开时queued，未覆盖首delta后running屏障' };
  });

  // SSE_004：成功、取消各真实终态发送后EOF；空后缀无限轮询风险按正确预期失败。
  for (const state of ['succeeded', 'cancelled']) {
    await s.check('SSE_004', 'TP-SSE-006', state, `${state}：从0发送且只发送一个terminal，服务端有界正常EOF`, async () => {
      let runId;
      if (state === 'succeeded') runId = (await successful(ctx, 'SSE_004 成功关闭')).run.run_id;
      else await stoppedWorker(ctx, async () => {
        const thread = await ctx.thread('SSE_004 取消关闭'); const submitted = await ctx.submit(thread.thread_id, 'SSE_004 取消问题', uuid()); runId = submitted.run_id;
        const response = await ctx.request(`/api/v1/runs/${runId}/cancel`, { method: 'POST' }); assert.equal(response.status, 200); assert.equal(response.body.status, 'cancelled');
      });
      const stream = await readSSE(ctx, runId); assert.equal(stream.status, 200); assert.ok(stream.eof && !stream.timed_out, '发送终态后流必须正常EOF');
      const terminal = stream.frames.filter(frame => ['run.succeeded', 'run.failed', 'run.cancelled'].includes(frame.event));
      assert.equal(terminal.length, 1); assert.equal(terminal[0].event, `run.${state}`); assert.equal(stream.frames.at(-1).event, terminal[0].event);
      assert.deepEqual(stream.frames.map(frame => frame.data.seq), (await ctx.events(runId)).map(event => event.seq));
      return { run_id: runId, terminal: state, stream: sseSummary(stream) };
    });
  }
  const complete = lazy(() => successful(ctx, 'SSE_004 空后缀资源边界'));
  for (const sub of ['at_terminal', 'beyond_terminal']) {
    await s.check('SSE_004', 'TP-SSE-007', sub, '已终态且游标在终态或超过终态时无新事件，连接应有界EOF而非无限空轮询（补充资源风险）', async () => {
      const data = await complete(); const max = data.events.at(-1).seq; const after = sub === 'at_terminal' ? max : max + 10;
      const stream = await readSSE(ctx, data.run.run_id, { after, timeoutMs: 3500 });
      const trace = ctx.evidence(`sse/SSE_004-${sub}.json`, { run_id: data.run.run_id, after_seq: after, stream: sseSummary(stream) }); s.note(`SSE_004 run_id=${data.run.run_id}；资源观察证据=${trace}`);
      assert.equal(stream.status, 200); assert.equal(stream.frames.length, 0);
      assert.ok(stream.eof && !stream.timed_out, `Run ${data.run.run_id} 已终态空后缀未在3500ms内EOF，仍占用轮询连接；证据${trace}`);
      return { run_id: data.run.run_id, after_seq: after, stream: sseSummary(stream), trace };
    });
  }

  // SSE_005：记录初始HTTP，缺失Run必须在StreamingResponse前拒绝；200后断流不算404。
  await s.check('SSE_005', 'TP-SSE-008', 'missing_run_handshake', '不存在Run在SSE握手前404/RUN_NOT_FOUND，无200后异常断流及路径泄漏', async () => {
    const missing = uuid(); const stream = await readSSE(ctx, missing, { timeoutMs: 3500 });
    const trace = ctx.evidence('sse/SSE_005-handshake.json', { missing_run_id: missing, ...sseSummary(stream), error_body: stream.error_body }); s.note(`SSE_005 missing_run_id=${missing}；握手证据=${trace}`);
    assert.equal(stream.status, 404, `不存在Run SSE握手HTTP应404，实际${stream.status}；证据${trace}`);
    assert.equal(stream.error_body.code, 'RUN_NOT_FOUND'); assert.equal(stream.frames.length, 0);
    assert.ok(!/traceback|[A-Z]:\\|\/app\/|postgresql:\/\//i.test(JSON.stringify(stream.error_body)));
    const facts = ctx.sql(`SELECT (SELECT count(*)::int FROM runs WHERE run_id=${sqlValue(missing)}) AS runs,(SELECT count(*)::int FROM run_events WHERE run_id=${sqlValue(missing)}) AS events`)[0];
    assert.deepEqual(facts, { runs: 0, events: 0 });
    return { missing_run_id: missing, http_status: stream.status, error_code: stream.error_body.code, facts, trace };
  });
  await executionCoverage(s);
});
