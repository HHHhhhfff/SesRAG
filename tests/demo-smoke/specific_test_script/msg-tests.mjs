import { runCategory, assert } from '../lib/category-kit.mjs';
import { uuid, isTime, increasing, lazy, ids, chainCounts, sqlValue, runFacts, stoppedWorker } from './run-test-driver.mjs';

export const coveredCases = ['MSG_001', 'MSG_002', 'MSG_003', 'MSG_004', 'MSG_005', 'MSG_006', 'MSG_007', 'MSG_008'];
await runCategory('msg', async s => {
  const ctx = s.ctx;
  // MSG_002/006：整组共享一次停机前提；每项仍独立报告，停机/恢复失败不能吞掉后续用例。
  const stoppedGroup = async (caseId, tpId, items, expected, inspect) => {
    const pending = new Set(items.map(item => item.sub));
    try {
      await stoppedWorker(ctx, async () => {
        for (const item of items) {
          pending.delete(item.sub);
          await s.check(caseId, tpId, item.sub, expected(item), () => inspect(item));
        }
      });
    } catch (error) {
      if (pending.size) {
        for (const item of items.filter(item => pending.has(item.sub))) await s.check(caseId, tpId, item.sub, expected(item), async () => { throw error; });
      } else {
        await s.check(caseId, tpId, 'group_worker_recovery', '该组检查后必须恢复本次Worker并确认ready，失败继续记录后续用例', async () => { throw error; });
      }
    }
  };
  // MSG_001：分别记录 DB 事实、公开时间和来源；API 缺字段按真实预期失败。
  const first = lazy(() => stoppedWorker(ctx, async () => {
    const thread = await ctx.thread('MSG_001 用户事实');
    const content = 'MSG_001 中文正文\n第二行安全测试';
    const key = uuid();
    const submitted = await ctx.submit(thread.thread_id, content, key);
    const detail = await ctx.detail(thread.thread_id);
    const rows = ctx.sql(`SELECT message_id,thread_id,seq,role,content,status,run_id,idempotency_key,created_at FROM messages WHERE message_id=${sqlValue(submitted.message_id)}`);
    return { thread, content, key, submitted, detail, rows, run: runFacts(ctx, submitted.run_id) };
  }));
  await s.check('MSG_001', 'TP-MSG-001', 'persistent_fields', '用户正文、user/completed、Thread/Run关联、正seq、时间、幂等Key持久一致', async () => {
    const data = await first();
    assert.equal(data.rows.length, 1);
    const message = data.rows[0];
    assert.equal(message.thread_id, data.thread.thread_id); assert.equal(message.run_id, data.submitted.run_id);
    assert.equal(message.role, 'user'); assert.equal(message.status, 'completed');
    assert.ok(message.content === data.content, '中文换行正文必须原样保存');
    assert.equal(message.idempotency_key, data.key); assert.equal(message.seq, 1); assert.ok(isTime(message.created_at));
    assert.equal(data.run.user_message_id, message.message_id); assert.equal(data.run.status, 'queued');
    const projected = data.detail.messages.find(item => item.message_id === message.message_id);
    for (const field of ['message_id', 'thread_id', 'seq', 'role', 'status', 'run_id']) assert.equal(projected[field], message[field]);
    assert.ok(projected.content === data.content, '详情必须保留原正文');
    return { ...ids(data.submitted), thread_id: message.thread_id, seq: message.seq, role: message.role, status: message.status, created_at: message.created_at, content_length: message.content.length };
  });
  await s.check('MSG_001', 'TP-MSG-001', 'public_time', '正式 Message 公开契约包含可解析创建时间，与DB事实一致', async () => {
    const data = await first();
    const message = data.detail.messages.find(item => item.message_id === data.submitted.message_id);
    assert.ok(isTime(message.created_at), 'Message 详情缺少公开 created_at');
    assert.equal(Date.parse(message.created_at), Date.parse(data.rows[0].created_at));
    return { message_id: message.message_id, created_at: message.created_at };
  });
  await s.check('MSG_001', 'TP-MSG-001', 'public_source', '公开 Message 事实有独立来源字段/来源对象，不能只用role替代来源', async () => {
    const data = await first();
    const message = data.detail.messages.find(item => item.message_id === data.submitted.message_id);
    assert.ok(Object.hasOwn(message, 'source') && message.source != null, 'Message 详情缺少独立来源 source 契约');
    return { message_id: message.message_id, source_present: true };
  });

  // MSG_002：一次停Worker保护全部边界，每项建立独立Thread并比较自己的完整执行链。
  await stoppedGroup('MSG_002', 'TP-MSG-002', [
    { sub: 'empty', content: '', status: 422 },
    { sub: 'one', content: '问', status: 201 },
    { sub: 'twenty_thousand', content: '问'.repeat(20000), status: 201 },
    { sub: 'twenty_thousand_one', content: '问'.repeat(20001), status: 422 },
    { sub: 'whitespace_observation', content: '   ', status: 201 },
  ], item => `${item.sub}：HTTP ${item.status}；合法输入建1条Message/Run/Task及2条初始Event，拒绝项零副作用`, async item => {
      const thread = await ctx.thread(`MSG_002 ${item.sub}`);
      assert.deepEqual(chainCounts(ctx, thread.thread_id), { messages: 0, runs: 0, tasks: 0, events: 0 });
      const response = await ctx.request(`/api/v1/threads/${thread.thread_id}/messages`, { method: 'POST', body: { content: item.content }, headers: { 'Idempotency-Key': uuid() } });
      assert.equal(response.status, item.status);
      const counts = chainCounts(ctx, thread.thread_id);
      assert.deepEqual(counts, item.status === 201 ? { messages: 1, runs: 1, tasks: 1, events: 2 } : { messages: 0, runs: 0, tasks: 0, events: 0 });
      return { thread_id: thread.thread_id, input_length: item.content.length, http_status: response.status, counts, observation: item.sub === 'whitespace_observation' ? '全空白API接受，仅质量观察' : undefined };
  });

  // MSG_003：每问上传独立单chunk Markdown，问题与证据完全一致以确定 Mock 的首证据。
  const sequence = lazy(async () => {
    const thread = await ctx.thread('MSG_003 连续Markdown');
    const control = await ctx.thread('MSG_003 对照Thread');
    const results = [];
    for (let index = 1; index <= 2; index++) {
      const markdown = `**MSG_003 ${uuid()} 第${index}问**\n\n- Markdown原文保持`;
      const uploaded = await ctx.upload(`MSG_003-${index}.md`, Buffer.from(markdown, 'utf8'), 'text/markdown');
      assert.equal(uploaded.status, 201);
      assert.equal((await ctx.waitDoc(uploaded.body.document_id)).status, 'indexed');
      const submitted = await ctx.submit(thread.thread_id, markdown, uuid());
      const run = await ctx.waitRun(submitted.run_id); assert.equal(run.status, 'succeeded');
      results.push({ submitted, run, markdown, events: await ctx.events(run.run_id) });
    }
    const other = await ctx.submit(control.thread_id, 'MSG_003 对照问题', uuid());
    assert.equal((await ctx.waitRun(other.run_id)).status, 'succeeded');
    return { thread, results, detail: await ctx.detail(thread.thread_id), control: await ctx.detail(control.thread_id) };
  });
  await s.check('MSG_003', 'TP-MSG-003', 'sequence_scope', '同Thread用户/assistant seq严格递增且唯一，对照Thread从1独立开始，游标等于最大seq', async () => {
    const data = await sequence();
    const seqs = data.detail.messages.map(item => item.seq);
    assert.deepEqual(seqs, [1, 2, 3, 4]); assert.ok(increasing(seqs));
    assert.deepEqual(data.detail.messages.map(item => item.role), ['user', 'assistant', 'user', 'assistant']);
    assert.deepEqual(data.control.messages.map(item => item.seq), [1, 2]);
    assert.equal(ctx.sql(`SELECT next_message_seq FROM threads WHERE thread_id=${sqlValue(data.thread.thread_id)}`)[0].next_message_seq, 4);
    return { thread_id: data.thread.thread_id, seqs, control_seqs: data.control.messages.map(item => item.seq) };
  });
  await s.check('MSG_003', 'TP-MSG-008', 'assistant_content_and_links', '每Run恰有1条completed assistant，双向指针一致，正文等于strip增量拼接且保留Markdown', async () => {
    const data = await sequence();
    for (const item of data.results) {
      const messages = data.detail.messages.filter(message => message.role === 'assistant' && message.run_id === item.run.run_id);
      assert.equal(messages.length, 1); const assistant = messages[0];
      assert.equal(assistant.message_id, item.run.assistant_message_id); assert.equal(assistant.status, 'completed');
      const answer = item.events.filter(event => event.type === 'answer.delta').map(event => event.data.text).join('').trim();
      assert.ok(assistant.content === answer, 'assistant 必须等于本Run增量的strip拼接');
      assert.ok(assistant.content.includes(item.markdown), 'Markdown证据原文必须保留');
      assert.ok(!assistant.content.includes('<strong>'), 'Markdown不可提前变为HTML');
    }
    return { run_ids: data.results.map(item => item.run.run_id), assistant_message_ids: data.results.map(item => item.run.assistant_message_id), markdown_preserved: true };
  });

  // MSG_004：同时发起HTTP，排除assistant竞争，核对Thread游标及唯一用户seq。
  await s.check('MSG_004', 'TP-MSG-004', 'different_keys_concurrent', '不同Key并发提交均201，恰有2条用户Message/Run/Task、唯一seq及4条初始Event', () => stoppedWorker(ctx, async () => {
    const thread = await ctx.thread('MSG_004 并发不同问题');
    const responses = await Promise.all([1, 2].map(index => ctx.request(`/api/v1/threads/${thread.thread_id}/messages`, { method: 'POST', body: { content: `MSG_004 第${index}个问题` }, headers: { 'Idempotency-Key': uuid() } })));
    responses.forEach(response => assert.equal(response.status, 201));
    for (const field of ['message_id', 'run_id', 'task_id']) assert.equal(new Set(responses.map(response => response.body[field])).size, 2);
    const detail = await ctx.detail(thread.thread_id); assert.deepEqual(detail.messages.map(item => item.seq), [1, 2]);
    assert.ok(detail.messages.every(item => item.role === 'user'));
    assert.deepEqual(chainCounts(ctx, thread.thread_id), { messages: 2, runs: 2, tasks: 2, events: 4 });
    assert.equal(ctx.sql(`SELECT next_message_seq FROM threads WHERE thread_id=${sqlValue(thread.thread_id)}`)[0].next_message_seq, 2);
    return { thread_id: thread.thread_id, results: responses.map(response => ids(response.body)), seqs: detail.messages.map(item => item.seq) };
  }));

  // MSG_005：同Key换正文仍复用原事实是当前正式约定，不制造409预期。
  const idempotency = lazy(() => stoppedWorker(ctx, async () => {
    const a = await ctx.thread('MSG_005 A'); const b = await ctx.thread('MSG_005 B'); const key = uuid();
    const post = (thread, content, suppliedKey) => ctx.request(`/api/v1/threads/${thread.thread_id}/messages`, { method: 'POST', body: { content }, headers: suppliedKey ? { 'Idempotency-Key': suppliedKey } : {} });
    const first = await post(a, 'MSG_005 原正文', key);
    const repeat = await post(a, 'MSG_005 原正文', key);
    const changed = await post(a, 'MSG_005 改正文仍复用', key);
    const originalCounts = chainCounts(ctx, a.thread_id);
    const originalContent = (await ctx.detail(a.thread_id)).messages[0].content;
    const distinct = await post(a, 'MSG_005 新Key', uuid()); const otherThread = await post(b, 'MSG_005 B同Key', key);
    const noKey1 = await post(a, 'MSG_005 无Key', undefined); const noKey2 = await post(a, 'MSG_005 无Key', undefined);
    return { a, b, first, repeat, changed, originalCounts, originalContent, distinct, otherThread, noKey1, noKey2, aCounts: chainCounts(ctx, a.thread_id), bCounts: chainCounts(ctx, b.thread_id) };
  }));
  await s.check('MSG_005', 'TP-MSG-005', 'sequential_same_key', '首次201、同Key及换正文重复200且三个ID不变，只建一组初始事实', async () => {
    const data = await idempotency(); assert.equal(data.first.status, 201);
    for (const duplicate of [data.repeat, data.changed]) { assert.equal(duplicate.status, 200); assert.deepEqual(ids(duplicate.body), ids(data.first.body)); }
    assert.deepEqual(data.originalCounts, { messages: 1, runs: 1, tasks: 1, events: 2 });
    assert.equal(data.originalContent, 'MSG_005 原正文');
    return { ...ids(data.first.body), duplicate_statuses: [data.repeat.status, data.changed.status], original_counts: data.originalCounts };
  });
  for (const sub of ['different_key', 'different_thread', 'no_key_each_time']) {
    await s.check('MSG_005', 'TP-MSG-007', sub, `${sub}：幂等范围只限同Thread同Key，不同Key/Thread及每次无Key均独立创建`, async () => {
      const data = await idempotency();
      const selected = sub === 'different_key' ? [data.first, data.distinct] : sub === 'different_thread' ? [data.first, data.otherThread] : [data.noKey1, data.noKey2];
      selected.forEach(response => assert.equal(response.status, 201));
      for (const field of ['message_id', 'run_id', 'task_id']) assert.equal(new Set(selected.map(response => response.body[field])).size, 2);
      assert.deepEqual(data.aCounts, { messages: 4, runs: 4, tasks: 4, events: 8 }); assert.deepEqual(data.bCounts, { messages: 1, runs: 1, tasks: 1, events: 2 });
      return { selected: selected.map(response => ids(response.body)), a_counts: data.aCounts, b_counts: data.bCounts };
    });
  }

  // MSG_006：8次试验共享一次停Worker，每次独立Thread/Key/事实；前一项失败不影响后项。
  await stoppedGroup('MSG_006', 'TP-MSG-006', Array.from({ length: 8 }, (_, index) => ({ index, sub: `ordinary_concurrency_trial_${index + 1}` })), () => '独立普通并发只建1条Message/Run/Task及1组创建Event，两响应相同ID或安全冲突', async ({ index }) => {
      const thread = await ctx.thread(`MSG_006 第${index + 1}次`); const key = uuid();
      const responses = await Promise.all([0, 1].map(() => ctx.request(`/api/v1/threads/${thread.thread_id}/messages`, { method: 'POST', body: { content: 'MSG_006 相同Key并发' }, headers: { 'Idempotency-Key': key } })));
      assert.ok(responses.every(response => [200, 201, 409].includes(response.status)), '并发不得返回内部错误');
      const success = responses.filter(response => [200, 201].includes(response.status)); assert.ok(success.length >= 1);
      if (success.length === 2) assert.deepEqual(ids(success[0].body), ids(success[1].body));
      const counts = chainCounts(ctx, thread.thread_id); assert.deepEqual(counts, { messages: 1, runs: 1, tasks: 1, events: 2 });
      return { trial: index + 1, thread_id: thread.thread_id, statuses: responses.map(response => response.status), counts, limitation: '普通交错，不证明首次幂等查询通过后竞争已覆盖' };
  });
  s.block('MSG_006', 'TP-MSG-006', 'first_query_barrier', '两请求首次幂等查询通过后放行，仍只建一组事实', 'E2 首次查询后、取Thread锁前的确定性双请求屏障尚未准备；普通并发结果不能替代');
  s.blockCase('MSG_007', 'E2 同task_id/worker_id/generation重复完成或最终提交重入驱动尚未准备');
  s.blockCase('MSG_008', 'E2 assistant分配seq与新用户Message创建的Thread游标/最终提交屏障尚未准备');
});
