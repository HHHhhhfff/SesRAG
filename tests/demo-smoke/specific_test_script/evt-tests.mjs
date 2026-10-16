import { executionCoverage } from './execution-coverage.mjs';
import { contractValidator } from '../lib/api-contracts.mjs';
import { runCategory, assert, poll } from '../lib/category-kit.mjs';
import { uuid, lazy, increasing, sqlValue, runFacts, stoppedWorker, successful, restartApi, readSSE, eventSummary, sseSummary } from './run-test-driver.mjs';

export const coveredCases = ['EVT_001', 'EVT_002', 'EVT_003', 'EVT_004', 'EVT_005'];
const ajv = contractValidator();
const validateEvent = ajv.getSchema('https://sesrag.local/contracts/run_event_v1.json');

await runCategory('evt', async s => {
  const ctx = s.ctx;
  // EVT_001：契约、领取事件及完整阶段序列独立断言，缺task.leased不能删预期。
  const normal = lazy(async () => {
    const data = await successful(ctx, 'EVT_001 正常事件', 'EVT_001 中文问题');
    return { ...data, stream: await readSSE(ctx, data.run.run_id), facts: runFacts(ctx, data.run.run_id) };
  });
  await s.check('EVT_001', 'TP-EVT-001', 'json_and_sse_v1', '普通events及SSE data逐条符合正式v1 JSON Schema，run_id、event_id和内容相同', async () => {
    const data = await normal(); assert.ok(data.events.length > 0);
    assert.equal(data.stream.status, 200); assert.ok(data.stream.eof); assert.equal(data.stream.frames.length, data.events.length);
    for (const event of [...data.events, ...data.stream.frames.map(frame => frame.data)]) {
      assert.ok(validateEvent(event), `Event ${event.seq} 不符合v1契约：${ajv.errorsText(validateEvent.errors)}`);
      assert.equal(event.run_id, data.run.run_id);
    }
    assert.equal(new Set(data.events.map(event => event.event_id)).size, data.events.length);
    assert.ok(increasing(data.events.map(event => event.seq)));
    assert.ok(data.stream.frames.every((frame, index) => frame.data.event_id === data.events[index].event_id && frame.data.run_id === data.run.run_id));
    assert.ok(data.stream.frames.every((frame, index) => JSON.stringify(frame.data.data) === JSON.stringify(data.events[index].data)));
    return { run_id: data.run.run_id, schema_checked_count: data.events.length + data.stream.frames.length, events: eventSummary(data.events), stream: sseSummary(data.stream) };
  });
  await s.check('EVT_001', 'TP-EVT-004', 'leased_identity', 'task.leased存在且在run.started前，关联真实task_id和领取generation', async () => {
    const data = await normal(); const leased = data.events.find(event => event.type === 'task.leased');
    const trace = ctx.evidence('evt/EVT_001-stage-summary.json', { run_id: data.run.run_id, task_id: data.submitted.task_id, generation: data.facts.generation, events: eventSummary(data.events) }); s.note(`EVT_001 run_id=${data.run.run_id}；阶段证据=${trace}`);
    assert.ok(leased, `Run ${data.run.run_id} 正常Journal缺少task.leased领取事件；证据${trace}`);
    assert.equal(leased.data.task_id, data.submitted.task_id); assert.equal(leased.data.generation, data.facts.generation);
    const started = data.events.find(event => event.type === 'run.started'); assert.ok(started); assert.ok(leased.seq < started.seq);
    return { run_id: data.run.run_id, task_id: leased.data.task_id, generation: leased.data.generation, leased_seq: leased.seq, started_seq: started.seq };
  });
  await s.check('EVT_001', 'TP-EVT-005', 'normal_stage_order', '创建/排队/领取/启动/检索/增量/消息完成/成功按阶段顺序，最终Message指针一致', async () => {
    const data = await normal(); const order = ['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'answer.delta', 'message.completed', 'run.succeeded'];
    const indexes = order.map(type => data.events.findIndex(event => event.type === type));
    order.forEach((type, index) => assert.ok(indexes[index] >= 0, `正常阶段缺少${type}`));
    assert.ok(indexes.every((value, index) => index === 0 || value > indexes[index - 1]), '正常事件阶段必须严格顺序');
    const terminal = data.events.filter(event => ['run.succeeded', 'run.failed', 'run.cancelled'].includes(event.type)); assert.equal(terminal.length, 1); assert.equal(terminal[0].type, 'run.succeeded');
    const completed = data.events.find(event => event.type === 'message.completed'); assert.equal(completed.data.message_id, data.run.assistant_message_id); assert.equal(terminal[0].data.message_id, data.run.assistant_message_id);
    assert.equal(data.events.at(-1).type, 'run.succeeded');
    return { run_id: data.run.run_id, types: data.events.map(event => event.type), assistant_message_id: data.run.assistant_message_id };
  });

  // EVT_003：保存初始事件，完成、重复读取、正式归档和API重启后逐字段比较旧事实。
  const histories = lazy(async () => {
    const initial = await stoppedWorker(ctx, async () => {
      const result = [];
      for (const suffix of ['A', 'B']) {
        const thread = await ctx.thread(`EVT_003 ${suffix}`); const submitted = await ctx.submit(thread.thread_id, `EVT_003 ${suffix}问题`, uuid());
        result.push({ thread, submitted, initial: await ctx.events(submitted.run_id) });
      }
      return result;
    });
    for (const item of initial) { assert.equal((await ctx.waitRun(item.submitted.run_id)).status, 'succeeded'); item.final = await ctx.events(item.submitted.run_id); }
    for (const item of initial) { const archived = await ctx.request(`/api/v1/threads/${item.thread.thread_id}/archive`, { method: 'POST' }); assert.equal(archived.status, 200); }
    await restartApi(ctx);
    for (const item of initial) item.restarted = await ctx.events(item.submitted.run_id);
    return initial;
  });
  await s.check('EVT_003', 'TP-EVT-003', 'history_unchanged_across_restart', '完成/重复重放/归档/API重启不改变已提交Event的event_id、seq、type、时间或payload', async () => {
    const data = await histories();
    for (const item of data) {
      assert.ok(JSON.stringify(item.final.slice(0, item.initial.length)) === JSON.stringify(item.initial), '完成后旧Event内容不可改变');
      assert.ok(JSON.stringify(item.restarted) === JSON.stringify(item.final), 'API重启后Event不可改变'); assert.ok(JSON.stringify(await ctx.events(item.submitted.run_id)) === JSON.stringify(item.final), '重复读取Event不可改变');
      const rows = ctx.sql(`SELECT event_id,run_id,seq,type,payload_json FROM run_events WHERE run_id=${sqlValue(item.submitted.run_id)} ORDER BY seq`);
      assert.equal(rows.length, item.final.length);
      rows.forEach((row, index) => { const event = item.final[index]; assert.equal(row.event_id, event.event_id); assert.equal(row.seq, event.seq); assert.equal(row.type, event.type); assert.ok(JSON.stringify(row.payload_json) === JSON.stringify(event.data), 'API重放payload必须与PG事实一致'); });
    }
    return { runs: data.map(item => ({ run_id: item.submitted.run_id, old_event_ids: item.initial.map(event => event.event_id), after_restart_count: item.restarted.length })), limitation: '未覆盖尚未准备的重试路径，不证明任意SQL篡改防护' };
  });
  await s.check('EVT_003', 'TP-EVT-007', 'run_sequence_independence', '两个Run各从seq1开始，游标独立且所有查询仅包含指定run_id', async () => {
    const data = await histories();
    for (const item of data) {
      assert.deepEqual(item.initial.map(event => event.seq), [1, 2]);
      assert.equal(item.final[0].seq, 1); assert.ok(increasing(item.final.map(event => event.seq)));
      assert.ok(item.final.every(event => event.run_id === item.submitted.run_id));
      const max = item.final.at(-1).seq; assert.equal(runFacts(ctx, item.submitted.run_id).next_event_seq, max);
      const suffix = await ctx.events(item.submitted.run_id, 2); assert.ok(JSON.stringify(suffix) === JSON.stringify(item.final.filter(event => event.seq > 2)), '每Run后缀必须准确');
    }
    assert.notEqual(data[0].submitted.run_id, data[1].submitted.run_id);
    assert.equal(new Set(data.flatMap(item => item.final.map(event => event.event_id))).size, data.reduce((count, item) => count + item.final.length, 0));
    return { runs: data.map(item => ({ run_id: item.submitted.run_id, first_seq: item.final[0].seq, max_seq: item.final.at(-1).seq })) };
  });

  // EVT_004：游标各边界独立report，不把合法后缀掩盖非法输入。
  const replay = lazy(() => successful(ctx, 'EVT_004 游标边界'));
  for (const sub of ['zero', 'middle', 'last', 'beyond', 'negative', 'non_integer']) {
    await s.check('EVT_004', 'TP-EVT-006', sub, `${sub}：合法游标返回严格seq后缀，末尾/超末尾空，负/非整数422且不追加事件`, async () => {
      const data = await replay(); const max = data.events.at(-1).seq;
      const cursor = { zero: 0, middle: Math.floor(max / 2), last: max, beyond: max + 10, negative: -1, non_integer: 'not-an-integer' }[sub];
      const response = await ctx.request(`/api/v1/runs/${data.run.run_id}/events?after_seq=${cursor}`);
      if (['negative', 'non_integer'].includes(sub)) assert.equal(response.status, 422);
      else { assert.equal(response.status, 200); assert.ok(JSON.stringify(response.body.events) === JSON.stringify(data.events.filter(event => event.seq > cursor)), '普通events必须返回精确历史后缀'); assert.ok(increasing(response.body.events.map(event => event.seq))); }
      assert.ok(JSON.stringify(await ctx.events(data.run.run_id)) === JSON.stringify(data.events), '游标请求不得追加或修改Event');
      return { run_id: data.run.run_id, cursor, max_seq: max, http_status: response.status, returned_seqs: response.body.events?.map(event => event.seq), event_count_unchanged: true };
    });
  }

  // EVT_005：索引Task无Run关联，正常及真正空文失败分开证据。
  for (const sub of ['normal_document', 'empty_document']) {
    await s.check('EVT_005', 'TP-EVT-008', sub, 'index_document只写Document/Task，不创建伪Thread/Run/RunEvent；空文明确失败，不要求run.failed', async () => {
      const before = ctx.sql(`SELECT (SELECT count(*)::int FROM threads WHERE owner_id=${sqlValue(ctx.context.owner_id)}) AS threads,(SELECT count(*)::int FROM runs) AS runs,(SELECT count(*)::int FROM run_events) AS events`)[0];
      const response = await ctx.upload(`EVT_005-${sub}.txt`, Buffer.from(sub === 'normal_document' ? 'EVT_005 安全索引正文' : '', 'utf8')); assert.equal(response.status, 201);
      const doc = await ctx.waitDoc(response.body.document_id); assert.equal(doc.status, sub === 'normal_document' ? 'indexed' : 'failed');
      if (sub === 'empty_document') assert.ok(doc.last_error_code);
      const tasks = await poll(() => {
        const rows = ctx.sql(`SELECT task_id,kind,run_id,document_id,state,last_error_code FROM tasks WHERE document_id=${sqlValue(doc.document_id)}`);
        return rows.length && rows.every(task => ['succeeded', 'failed', 'cancelled'].includes(task.state)) ? rows : null;
      }, 5000, 'EVT_005 Document终态后索引Task未在有界时间内结算');
      assert.equal(tasks.length, 1); assert.equal(tasks[0].kind, 'index_document'); assert.equal(tasks[0].run_id, null);
      assert.equal(tasks[0].state, sub === 'normal_document' ? 'succeeded' : 'failed');
      if (sub === 'empty_document') assert.ok(tasks[0].last_error_code);
      const after = ctx.sql(`SELECT (SELECT count(*)::int FROM threads WHERE owner_id=${sqlValue(ctx.context.owner_id)}) AS threads,(SELECT count(*)::int FROM runs) AS runs,(SELECT count(*)::int FROM run_events) AS events`)[0];
      assert.deepEqual(after, before);
      return { document_id: doc.document_id, document_status: doc.status, task: tasks[0], before, after };
    });
  }
  await executionCoverage(s);
});
