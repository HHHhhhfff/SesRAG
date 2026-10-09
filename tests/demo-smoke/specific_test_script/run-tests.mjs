import { runCategory, assert } from '../lib/category-kit.mjs';
import { uuid, lazy, isUuid, isTime, ids, chainCounts, sqlValue, runFacts, stoppedWorker, successful } from './run-test-driver.mjs';

export const coveredCases = ['RUN_001', 'RUN_002', 'RUN_003', 'RUN_004', 'RUN_005', 'RUN_006', 'RUN_007'];
await runCategory('run', async s => {
  const ctx = s.ctx;
  // RUN_001：无Worker提交时完整读取持久链，恢复后继续同一身份。
  const queuedChain = lazy(() => stoppedWorker(ctx, async () => {
    const thread = await ctx.thread('RUN_001 PostgreSQL排队');
    const response = await ctx.request(`/api/v1/threads/${thread.thread_id}/messages`, { method: 'POST', body: { content: 'RUN_001 原子创建执行链' }, headers: { 'Idempotency-Key': uuid() } });
    assert.equal(response.status, 201);
    const submitted = response.body;
    return { thread, response, submitted, detail: await ctx.detail(thread.thread_id), api: await ctx.run(submitted.run_id), facts: runFacts(ctx, submitted.run_id), counts: chainCounts(ctx, thread.thread_id), events: await ctx.events(submitted.run_id) };
  }));
  await s.check('RUN_001', 'TP-RUN-001', 'queued_full_chain', 'HTTP201即有用户Message、唯一queued Run/主Task和两个初始Event，无同步assistant', async () => {
    const data = await queuedChain();
    for (const id of Object.values(ids(data.submitted))) assert.ok(isUuid(id));
    assert.equal(data.submitted.status, 'queued'); assert.equal(data.api.status, 'queued'); assert.equal(data.api.task.state, 'queued');
    assert.equal(data.facts.user_message_id, data.submitted.message_id); assert.equal(data.facts.primary_task_id, data.submitted.task_id);
    assert.equal(data.facts.thread_id, data.thread.thread_id); assert.equal(data.facts.assistant_message_id, null);
    assert.equal(data.facts.status, 'queued'); assert.equal(data.facts.task_state, 'queued'); assert.equal(data.facts.kind, 'run');
    assert.deepEqual(data.counts, { messages: 1, runs: 1, tasks: 1, events: 2 });
    assert.deepEqual(data.events.map(event => [event.seq, event.type]), [[1, 'run.created'], [2, 'task.queued']]);
    assert.equal(data.events[0].data.message_id, data.submitted.message_id); assert.equal(data.events[1].data.task_id, data.submitted.task_id);
    assert.equal(data.detail.messages[0].run_id, data.submitted.run_id); assert.equal(data.detail.messages[0].role, 'user');
    return { ...ids(data.submitted), thread_id: data.thread.thread_id, counts: data.counts, run_status: data.facts.status, task_state: data.facts.task_state };
  });
  await s.check('RUN_001', 'TP-WK-001', 'restart_claims_original', '停Worker期间Task真实留在PG queued，恢复后原Run/Task身份被领取且完成', async () => {
    const data = await queuedChain(); assert.equal(data.facts.task_state, 'queued'); assert.equal(data.facts.attempt, 0); assert.equal(data.facts.generation, 0);
    const done = await ctx.waitRun(data.submitted.run_id); assert.equal(done.status, 'succeeded'); assert.equal(done.run_id, data.submitted.run_id);
    assert.equal(done.task.task_id, data.submitted.task_id); assert.ok(done.task.attempt >= 1 && done.task.generation >= 1);
    const counts = chainCounts(ctx, data.thread.thread_id); assert.equal(counts.runs, 1); assert.equal(counts.tasks, 1); assert.equal(counts.messages, 2);
    return { run_id: done.run_id, task_id: done.task.task_id, generation: done.task.generation, attempt: done.task.attempt, persisted_identity_preserved: true };
  });
  for (const sub of ['first_flush_failure', 'event_commit_failure']) s.block('RUN_002', 'TP-RUN-002', sub, '创建事务失败时Message/Run/Task/Event和Thread游标整组回滚，恢复后可创建', `E2 仅作用本用例连接的${sub}注入驱动尚未准备`);

  // RUN_003：默认快照有可验证字段；跨配置真实执行单独保留解锁条件。
  const snapshot = lazy(() => stoppedWorker(ctx, async () => {
    const settings = ctx.python("import json\nfrom backend.config import Settings\ns=Settings()\nprint('SMOKE_JSON:'+json.dumps({'mock_provider':s.mock_provider,'model_name':s.model_name,'rag_top_k':s.rag_top_k},ensure_ascii=False))");
    const thread = await ctx.thread('RUN_003 默认快照'); const submitted = await ctx.submit(thread.thread_id, 'RUN_003 配置冻结', uuid());
    return { thread, submitted, settings, facts: runFacts(ctx, submitted.run_id) };
  }));
  await s.check('RUN_003', 'TP-RUN-003', 'creation_model', 'snapshot.model准确等于创建时配置解析的Mock或模型名称', async () => {
    const data = await snapshot();
    const model = data.settings.mock_provider ? 'mock' : data.settings.model_name;
    assert.ok(model); assert.equal(data.facts.snapshot_json.model, model);
    return { run_id: data.submitted.run_id, creation_model: model, snapshot_model: data.facts.snapshot_json.model };
  });
  await s.check('RUN_003', 'TP-RUN-003', 'retrieval_prompt_time', '快照top_k等于API创建配置、prompt_version=1，Run创建时间持久有效', async () => {
    const data = await snapshot(); const value = data.facts.snapshot_json;
    assert.equal(value.retrieval.top_k, data.settings.rag_top_k); assert.equal(value.prompt_version, 1); assert.ok(isTime(data.facts.created_at));
    return { run_id: data.submitted.run_id, top_k: value.retrieval.top_k, prompt_version: value.prompt_version, created_at: data.facts.created_at };
  });
  await s.check('RUN_003', 'TP-RUN-003', 'safe_immutable_snapshot', '快照不含Key/凭据/宿主路径，正常执行后内容仍与创建时完全相同', async () => {
    const data = await snapshot(); const before = data.facts.snapshot_json;
    const containsSensitive = value => Object.entries(value).some(([key, item]) => /api.?key|password|secret|credential|upload.?dir|database.?url/i.test(key) || (item && typeof item === 'object' && containsSensitive(item)) || (typeof item === 'string' && /[A-Z]:\\|postgresql:\/\//i.test(item)));
    assert.ok(!containsSensitive(before), '快照不得保存凭据或宿主路径');
    assert.equal((await ctx.waitRun(data.submitted.run_id)).status, 'succeeded');
    assert.deepEqual(runFacts(ctx, data.submitted.run_id).snapshot_json, before);
    return { run_id: data.submitted.run_id, immutable_after_normal_execution: true, sensitive_fields: false };
  });
  await s.check('RUN_003', 'TP-RUN-004', 'default_execution_limit', '默认配置执行召回数量不超过冻结top_k，快照在完成后不改写；只给默认配置局部证据', async () => {
    const data = await snapshot(); assert.equal((await ctx.waitRun(data.submitted.run_id)).status, 'succeeded');
    const retrieval = (await ctx.events(data.submitted.run_id)).find(event => event.type === 'retrieval.completed');
    assert.ok(retrieval); assert.ok(retrieval.data.count <= data.facts.snapshot_json.retrieval.top_k);
    assert.deepEqual(runFacts(ctx, data.submitted.run_id).snapshot_json, data.facts.snapshot_json);
    return { run_id: data.submitted.run_id, retrieval_count: retrieval.data.count, frozen_top_k: data.facts.snapshot_json.retrieval.top_k, limitation: 'API和Worker配置相同，未证明配置改变后的遵从性' };
  });
  s.block('RUN_003', 'TP-RUN-003', 'non_mock_model_snapshot', '非Mock创建快照准确记录指定模型且不含Key', 'E2/E4/C 非Mock、不同模型名称的创建与执行配置驱动尚未准备；默认Mock不证明硬编码模型正确');
  s.block('RUN_003', 'TP-RUN-004', 'changed_worker_configuration', 'API top_k=1/模型A创建Run，Worker top_k=3/模型B执行仍遵从原快照', 'E2/E4/C API/Worker不同配置及Provider调用参数证据驱动尚未准备');

  // RUN_004：各状态用独立Run；不存在的状态入口不能由成功状态替代。
  for (const state of ['queued', 'succeeded', 'cancelled']) {
    await s.check('RUN_004', 'TP-RUN-005', state, `${state}：重复API读取与真实PG Run/Task持久状态及关联字段一致`, async () => {
      let data;
      if (state === 'succeeded') {
        const prepared = await successful(ctx, `RUN_004 ${state}`);
        data = { submitted: prepared.submitted, api1: await ctx.run(prepared.run.run_id), api2: await ctx.run(prepared.run.run_id), facts: runFacts(ctx, prepared.run.run_id) };
      } else {
        data = await stoppedWorker(ctx, async () => {
          const thread = await ctx.thread(`RUN_004 ${state}`); const submitted = await ctx.submit(thread.thread_id, `RUN_004 ${state}问题`, uuid());
          if (state === 'cancelled') { const cancelled = await ctx.request(`/api/v1/runs/${submitted.run_id}/cancel`, { method: 'POST' }); assert.equal(cancelled.status, 200); }
          return { submitted, api1: await ctx.run(submitted.run_id), api2: await ctx.run(submitted.run_id), facts: runFacts(ctx, submitted.run_id) };
        });
      }
      for (const api of [data.api1, data.api2]) {
        assert.equal(api.status, state); assert.equal(api.status, data.facts.status); assert.equal(api.task.state, state); assert.equal(api.task.state, data.facts.task_state);
        for (const field of ['run_id', 'thread_id', 'user_message_id', 'assistant_message_id', 'last_error_code']) assert.equal(api[field], data.facts[field]);
        for (const field of ['task_id', 'attempt', 'generation', 'worker_id']) assert.equal(api.task[field], data.facts[field]);
        assert.equal(api.task.last_error_code, data.facts.task_error_code);
      }
      return { ...ids(data.submitted), run_status: data.facts.status, task_state: data.facts.task_state, repeated_reads_consistent: true };
    });
  }
  for (const state of ['running', 'retry_waiting', 'failed']) s.block('RUN_004', 'TP-RUN-005', state, `${state}状态的API与PG事实一致、对应Task状态正确`, `E2 可控${state}阶段的真实Run驱动尚未准备；不使用Index失败或SQL修改状态替代`);

  // RUN_005：单条只读SELECT看到成功全组，最终commit故障另报条件不足。
  await s.check('RUN_005', 'TP-RUN-006', 'normal_committed_group', '正常完成从独立PG连接同次读取可见assistant正文/引用、Run/Task succeeded及两个终态事件', async () => {
    const data = await successful(ctx, 'RUN_005 正常成功事务');
    const rows = ctx.sql(`SELECT r.run_id,r.status,r.assistant_message_id,t.state AS task_state,m.message_id,m.role,m.status AS message_status,m.content,m.citations_json,(SELECT count(*)::int FROM messages x WHERE x.run_id=r.run_id AND x.role='assistant') AS assistant_count,(SELECT json_agg(json_build_object('seq',e.seq,'type',e.type,'data',e.payload_json) ORDER BY e.seq) FROM run_events e WHERE e.run_id=r.run_id AND e.type IN ('message.completed','run.succeeded')) AS terminal_group FROM runs r JOIN tasks t ON t.task_id=r.primary_task_id LEFT JOIN messages m ON m.message_id=r.assistant_message_id WHERE r.run_id=${sqlValue(data.run.run_id)}`);
    assert.equal(rows.length, 1); const row = rows[0]; assert.equal(row.status, 'succeeded'); assert.equal(row.task_state, 'succeeded');
    assert.equal(row.assistant_count, 1); assert.equal(row.message_id, row.assistant_message_id); assert.equal(row.role, 'assistant'); assert.equal(row.message_status, 'completed');
    const deltas = data.events.filter(event => event.type === 'answer.delta').map(event => event.data.text).join('').trim();
    assert.ok(row.content === deltas, '同事务可见的最终正文必须等于增量strip拼接');
    assert.ok(Array.isArray(row.citations_json)); assert.deepEqual(row.terminal_group.map(event => event.type), ['message.completed', 'run.succeeded']);
    row.terminal_group.forEach(event => assert.equal(event.data.message_id, row.message_id));
    assert.deepEqual(row.terminal_group[0].data.citations, row.citations_json); assert.equal(row.terminal_group[1].seq, row.terminal_group[0].seq + 1);
    return { run_id: row.run_id, assistant_message_id: row.message_id, assistant_count: row.assistant_count, citation_count: row.citations_json.length, terminal_group: row.terminal_group.map(event => ({ seq: event.seq, type: event.type })), limitation: '正常提交全组可见；未覆盖commit失败' };
  });
  s.block('RUN_005', 'TP-RUN-006', 'final_commit_failure', '新增assistant和两个终态Event后commit失败整组回滚，不出现成功残片', 'E2 本用例最终commit失败、另一连接前后读取屏障尚未准备');
  s.blockCase('RUN_006', 'E2 成功/永久失败Run的handler终态重入及旧attempt迟到失败驱动尚未准备；纯状态机不替代生产路径');

  // RUN_007：缺失对象的普通读取、补放、取消分别核对，不借SSE结果。
  for (const operation of ['detail', 'events', 'cancel']) {
    await s.check('RUN_007', 'TP-RUN-008', operation, '未创建Run的详情/events/cancel均404/RUN_NOT_FOUND，无Run/Event/Task副作用', async () => {
      const missing = uuid();
      const route = `/api/v1/runs/${missing}${operation === 'events' ? '/events' : operation === 'cancel' ? '/cancel' : ''}`;
      const response = await ctx.request(route, { method: operation === 'cancel' ? 'POST' : 'GET' });
      assert.equal(response.status, 404); assert.equal(response.body.code, 'RUN_NOT_FOUND');
      assert.ok(!/traceback|[A-Z]:\\|\/app\/|postgresql:\/\//i.test(JSON.stringify(response.body)));
      const counts = ctx.sql(`SELECT (SELECT count(*)::int FROM runs WHERE run_id=${sqlValue(missing)}) AS runs,(SELECT count(*)::int FROM run_events WHERE run_id=${sqlValue(missing)}) AS events,(SELECT count(*)::int FROM tasks WHERE run_id=${sqlValue(missing)}) AS tasks`)[0];
      assert.deepEqual(counts, { runs: 0, events: 0, tasks: 0 });
      return { missing_run_id: missing, operation, http_status: response.status, code: response.body.code, counts };
    });
  }
});
