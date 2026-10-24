import { helper } from '../tooling/product-category.mjs';
import { assert, thread, send, answer, done, run, events, scenario, barrier, release, releaseThenRestore, request, detail, observations, until } from './support.mjs';
import { runEvidenceRuntime, nextChatSequence } from './run-evidence-runtime.mjs';

async function ready(suite) {
  return until(async () => { try { return (await request(suite.context, '/health/ready')).data; } catch { return null; } },
    (data) => data?.database === 'ready' && data?.worker_count >= 1, '服务恢复就绪', 60000);
}

// RUN_013：中断的只是SSE观察连接；PG/Worker中的同一Run继续执行。
async function observerDisconnect(suite) {
  const c = suite.context; const t = await thread(c, `RUN_013-${c.run_id}`);
  await scenario(c, { kind: 'stall', chunks: ['断线前', '断线后'] });
  const created = await send(c, t, 'HISTORY-OBSERVER-001', 'ws-http-a');
  const held = await barrier(c);
  try {
    const controller = new AbortController();
    const response = await fetch(`${c.api_base_url}/api/v2/runs/${created.run_id}/events/stream`, { signal: controller.signal });
    const reader = response.body.getReader(); await reader.read(); controller.abort();
    assert.equal((await run(c, created.run_id)).run_id, created.run_id);
  } finally { await release(c, held); }
  assert.equal((await done(c, created.run_id)).status, 'succeeded');
  const received = (await observations(c)).requests.filter((item) => item.model === 'ws-http-a' && item.input?.sentinel_matches?.includes('HISTORY-OBSERVER-001'));
  assert.equal(received.length, 1);
  return { actual: 'SSE读取后主动断开；同一Run继续成功结算，未发出cancel/retry请求。', run_id: created.run_id, provider_observation_count: received.length };
}

// RUN_014：真实重启API容器，比较持久Message/Event/Run身份及原文。
async function apiRestart(suite) {
  const c = suite.context; const t = await thread(c, `RUN_014-${c.run_id}`);
  const created = await answer(c, t, 'API重启持久历史');
  const before = await detail(c, t.thread_id); const journal = await events(c, created.run_id);
  const restarted = await helper(c, 'restart', 'api'); c.api_base_url = restarted.result.api_base_url; await ready(suite);
  const after = await detail(c, t.thread_id);
  assert.deepEqual(after.messages, before.messages); assert.deepEqual(await events(c, created.run_id), journal);
  assert.equal((await run(c, created.run_id)).status, 'succeeded');
  await scenario(c, { kind: 'stall', chunks: ['API_ACTIVE_HEAD', 'API_ACTIVE_TAIL'] });
  const activeThread = await thread(c, `RUN_014-active-${c.run_id}`); const active = await send(c, activeThread, 'API重启活动输入', 'ws-http-a'); const held = await barrier(c);
  let prefix;
  try {
    const frozen = (await run(c, active.run_id)).snapshot; prefix = await events(c, active.run_id);
    const restartedActive = await helper(c, 'restart', 'api'); c.api_base_url = restartedActive.result.api_base_url; await ready(suite);
    const recovered = await run(c, active.run_id); assert.deepEqual(recovered.snapshot, frozen); assert.equal(recovered.task.task_id, active.task_id);
    assert.deepEqual((await events(c, active.run_id)).slice(0, prefix.length), prefix);
  } finally { await release(c, held); }
  assert.equal((await done(c, active.run_id)).status, 'succeeded'); assert.ok((await events(c, active.run_id, prefix.at(-1).seq)).some((item) => item.type === 'run.succeeded'));
  return { actual: '完成态/运行态两组API真实重启均重新就绪；历史、Snapshot、Run/Task身份和Journal前缀保持，断点后可补齐终态。', run_id: created.run_id, active_run_id: active.run_id, event_count: journal.length };
}

// RUN_015：Worker强制停止/重启后的租约回收，不伪造DB成功终态。
async function workerRestart(suite) {
  const c = suite.context; const results = [];
  for (const action of ['stop', 'kill-worker']) {
    const t = await thread(c, `RUN_015-${action}-${c.run_id}`);
    await scenario(c, { kind: 'stall', chunks: ['旧执行片段', '旧执行后缀'] });
    const created = await send(c, t, 'Worker停止恢复输入', 'ws-http-a'); const held = await barrier(c); const original = await run(c, created.run_id);
    let queued; let released = false;
    try {
      await helper(c, action, action === 'stop' ? 'worker' : undefined);
      await release(c, held); released = true;
      const pending = await thread(c, `RUN_015-down-${action}`); queued = await send(c, pending, '停止后不得领取新任务'); assert.equal((await run(c, queued.run_id)).task.state, 'queued');
      await scenario(c, { chunks: ['新执行完整回答'] });
    } finally {
      // 从停服意图起覆盖整个故障窗口；即使release失败也必须恢复，且不掩盖原始失败。
      await releaseThenRestore(async () => { if (!released) await release(c, held); },
        async () => { await helper(c, 'start', 'worker'); await ready(suite); });
    }
    const finished = await done(c, created.run_id, 90000); assert.equal(finished.status, 'succeeded'); await done(c, queued.run_id);
    const page = await detail(c, t.thread_id);
    assert.equal(page.messages.filter((item) => item.role === 'user').length, 1); assert.equal(page.messages.filter((item) => item.role === 'assistant').length, 1);
    assert.equal(finished.task.task_id, created.task_id); assert.ok(finished.task.generation > original.task.generation); assert.deepEqual(finished.snapshot, original.snapshot);
    results.push({ action, run_id: created.run_id, task: finished.task });
  }
  return { actual: '优雅stop和SIGKILL失租两组真实恢复：停服期间新Task保持queued，恢复沿用Run/Task/input/Snapshot，generation递增且唯一最终回答。', results };
}

// RUN_022：HTTP状态经过真实适配器和完整Worker重试到终态，不仅检查错误类。
async function httpErrors(suite) {
  const c = suite.context; const results = [];
  for (const status of [401, 403, 400, 404, 408, 429, 500, 503]) {
    await scenario(c, { kind: 'http-error', http_status: status });
    const t = await thread(c, `RUN_022-${status}`); const created = await send(c, t, 'HTTP故障映射', 'ws-http-a'); const finished = await done(c, created.run_id, 90000);
    assert.equal(finished.status, 'failed'); assert.equal(finished.task.attempt, [408, 429, 500, 503].includes(status) ? 3 : 1);
    assert.equal(finished.assistant_message_id, null); const journal = await events(c, created.run_id);
    assert.equal(journal.filter((item) => item.type === 'run.failed').length, 1); assert.ok(!JSON.stringify(finished).includes('fixture_http_error'));
    results.push({ http_status: status, run_id: created.run_id, attempts: finished.task.attempt, error_code: finished.last_error_code });
  }
  await scenario(c);
  return { actual: '8组真实HTTP错误分别结算：401/403/400/404仅1尝试，408/429/500/503有界3尝试；无最终assistant或上游正文泄露。网络/超时的适配器断言另附JUnit。', results };
}

// RUN_024：仅操作本分类受标签保护的PG/Redis；finally恢复并等待真实就绪。
async function infrastructure(suite) {
  const c = suite.context; const results = [];
  await helper(c, 'stop', 'redis');
  try {
    const health = await request(c, '/health/ready', { expected: [200, 503] });
    assert.notEqual(health.data.redis, 'ready');
    const t = await thread(c, `RUN_024-redis-${c.run_id}`); const created = await answer(c, t, 'Redis通知降级仍使用PG事实');
    results.push({ service: 'redis', readiness_status: health.status, run_id: created.run_id, status: created.finished.status });
  } finally { await helper(c, 'start', 'redis'); await ready(suite); }
  await helper(c, 'stop', 'postgres');
  try {
    const health = await request(c, '/health/ready', { expected: 503 });
    assert.notEqual(health.data.database, 'ready');
    const response = await request(c, '/api/v2/threads', { expected: 503 });
    assert.ok(response.data.code); results.push({ service: 'postgres', readiness_status: health.status, code: response.data.code });
  } finally { await helper(c, 'start', 'postgres'); await ready(suite); }
  // RUN_024提交阶段：PG已停时消息创建安全失败，恢复后原请求只产生一套事实。
  const pending = await thread(c, 'RUN_024-submit'); const token = crypto.randomUUID();
  const body = { branch_id: pending.default_branch_id, expected_version: 0, content: 'PG_SUBMIT_RECOVERY' };
  await helper(c, 'stop', 'postgres');
  try { const response = await request(c, `/api/v2/threads/${pending.thread_id}/messages`, { method: 'POST', headers: { 'Idempotency-Key': token }, body, expected: 503 }); assert.equal(response.data.code, 'DATABASE_UNAVAILABLE'); }
  finally { await helper(c, 'start', 'postgres'); await ready(suite); }
  assert.equal((await detail(c, pending.thread_id)).messages.length, 0);
  const submitted = (await request(c, `/api/v2/threads/${pending.thread_id}/messages`, { method: 'POST', headers: { 'Idempotency-Key': token }, body, expected: 201 })).data;
  assert.equal((await done(c, submitted.run_id)).status, 'succeeded'); results.push({ stage: 'submit', run_id: submitted.run_id, status: 'succeeded', input_count: (await detail(c, pending.thread_id)).messages.filter((item) => item.role === 'user').length });
  // RUN_024执行阶段：首片已提交后断PG，Provider继续返回；恢复只能依据PG的旧Run/Task回收。
  await scenario(c, { kind: 'stall', chunks: ['PG_EXEC_HEAD', 'PG_EXEC_TAIL'], request_seq: await nextChatSequence(c) }); const activeThread = await thread(c, 'RUN_024-execution'); const active = await send(c, activeThread, '执行中数据库故障', 'ws-http-a'); const held = await barrier(c);
  const before = await run(c, active.run_id); let released = false;
  try {
    await helper(c, 'stop', 'postgres'); await request(c, `/api/v2/runs/${active.run_id}`, { expected: 503 });
    await release(c, held); released = true; await new Promise((resolve) => setTimeout(resolve, 500));
  } finally {
    await releaseThenRestore(async () => { if (!released) await release(c, held); },
      async () => { await helper(c, 'start', 'postgres'); await ready(suite); });
  }
  const finished = await done(c, active.run_id, 120000); assert.equal(finished.task.task_id, active.task_id); assert.deepEqual(finished.snapshot, before.snapshot);
  const page = await detail(c, activeThread.thread_id); const assistants = page.messages.filter((item) => item.role === 'assistant');
  assert.ok(assistants.length <= 1); assert.equal(page.messages.filter((item) => item.role === 'user').length, 1);
  // 场景只停第一次chat；数据库恢复后自动尝试使用Provider明确的正常默认响应，不能再次停死。
  if (finished.status === 'succeeded') assert.equal(assistants[0].content, finished.task.generation === before.task.generation ? 'PG_EXEC_HEADPG_EXEC_TAIL' : '受控 Provider 返回合成结果。');
  else { assert.equal(finished.status, 'failed'); assert.equal(assistants.length, 0); assert.ok(finished.last_error_code); }
  results.push({ stage: 'execution', run_id: active.run_id, status: finished.status, error_code: finished.last_error_code, generation: finished.task.generation }); await scenario(c);
  return { actual: 'Redis通知降级仍按PG执行；PG读取/提交/执行三阶段真实中断均无假成功，恢复后原输入/Run/Task/Snapshot可追溯且无重复最终回答。服务均已恢复。', results };
}

export const runtimeCases = { ...runEvidenceRuntime, RUN_013: observerDisconnect, RUN_014: apiRestart, RUN_015: workerRestart, RUN_022: httpErrors, RUN_024: infrastructure };
