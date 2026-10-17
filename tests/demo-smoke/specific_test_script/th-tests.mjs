import { runCategory, assert } from '../lib/category-kit.mjs';
import { uuid, isUuid, isTime, increasing, lazy, successful, chainCounts, sqlValue } from './run-test-driver.mjs';

export const coveredCases = ['TH_001', 'TH_002', 'TH_003', 'TH_004'];
await runCategory('th', async s => {
  const ctx = s.ctx;
  // TH_001：身份、列表排序、详情排序各自断言，不以创建成功代替排序通过。
  const creation = lazy(async () => {
    const a = await ctx.request('/api/v1/threads', { method: 'POST', body: {} });
    const b = await ctx.request('/api/v1/threads', { method: 'POST', body: { title: 'TH_001 中文显式标题' } });
    return { a, b };
  });
  await s.check('TH_001', 'TP-TH-001', 'identity', '默认及中文标题创建201；UUID、owner、创建/更新时间完整', async () => {
    const { a, b } = await creation();
    for (const response of [a, b]) {
      assert.equal(response.status, 201);
      assert.ok(isUuid(response.body.thread_id));
      assert.equal(response.body.owner_id, ctx.context.owner_id);
      assert.ok(isTime(response.body.created_at) && isTime(response.body.updated_at));
    }
    assert.equal(a.body.title, '新会话');
    assert.equal(b.body.title, 'TH_001 中文显式标题');
    assert.notEqual(a.body.thread_id, b.body.thread_id);
    return { thread_ids: [a.body.thread_id, b.body.thread_id], owner_matches: true };
  });
  const populated = lazy(async () => {
    const { a, b } = await creation();
    assert.equal(a.status, 201); assert.equal(b.status, 201);
    const submissions = [];
    for (const content of ['TH_001 第一问题', 'TH_001 第二问题']) {
      const submitted = await ctx.submit(a.body.thread_id, content, uuid());
      assert.equal((await ctx.waitRun(submitted.run_id)).status, 'succeeded');
      submissions.push(submitted);
    }
    return { a: a.body, b: b.body, submissions };
  });
  await s.check('TH_001', 'TP-TH-003', 'updated_order', '更新先创建的 A 后列表按 updated_at 倒序，同时间不强制次序', async () => {
    const { a, b } = await populated();
    const response = await ctx.request('/api/v1/threads');
    assert.equal(response.status, 200); assert.ok(Array.isArray(response.body));
    const list = response.body;
    assert.ok(list.some(item => item.thread_id === a.thread_id) && list.some(item => item.thread_id === b.thread_id));
    assert.ok(list.every((item, index) => isTime(item.updated_at) && (index === 0 || Date.parse(list[index - 1].updated_at) >= Date.parse(item.updated_at))));
    const freshA = list.find(item => item.thread_id === a.thread_id);
    assert.ok(Date.parse(freshA.updated_at) >= Date.parse(b.updated_at));
    return { ordered_thread_ids: list.map(item => item.thread_id), updated_a: freshA.updated_at };
  });
  await s.check('TH_001', 'TP-TH-004', 'detail_order', '详情 messages seq 严格升序，runs 创建时间倒序且不混 Thread', async () => {
    const { a, b, submissions } = await populated();
    const detail = await ctx.detail(a.thread_id);
    const control = await ctx.detail(b.thread_id);
    assert.ok(increasing(detail.messages.map(item => item.seq)));
    assert.equal(detail.messages.length, 4);
    assert.ok(detail.messages.every(item => item.thread_id === a.thread_id));
    assert.deepEqual(new Set(detail.runs.map(item => item.run_id)), new Set(submissions.map(item => item.run_id)));
    assert.ok(detail.runs.every((item, index) => isTime(item.created_at) && (index === 0 || Date.parse(detail.runs[index - 1].created_at) >= Date.parse(item.created_at))));
    assert.equal(control.messages.length, 0); assert.equal(control.runs.length, 0);
    return { thread_id: a.thread_id, message_seqs: detail.messages.map(item => item.seq), run_ids: detail.runs.map(item => item.run_id) };
  });

  // TH_002：全空白是质量观察，不追加 PRD 没有承诺的拒绝规则。
  for (const item of [
    { sub: 'empty', title: '', status: 422 },
    { sub: 'one', title: '题', status: 201, saved: '题' },
    { sub: 'two_hundred', title: '题'.repeat(200), status: 201, saved: '题'.repeat(200) },
    { sub: 'two_hundred_one', title: '题'.repeat(201), status: 422 },
    { sub: 'strip', title: '  中文标题  ', status: 201, saved: '中文标题' },
    { sub: 'whitespace_observation', title: '   ', status: 201, saved: '' },
  ]) {
    await s.check('TH_002', 'TP-TH-002', item.sub, `${item.sub}：HTTP ${item.status}，合法标题按 strip 保存，拒绝项无新增 Thread`, async () => {
      const before = ctx.sql(`SELECT count(*)::int AS count FROM threads WHERE owner_id=${sqlValue(ctx.context.owner_id)}`)[0].count;
      const response = await ctx.request('/api/v1/threads', { method: 'POST', body: { title: item.title } });
      const after = ctx.sql(`SELECT count(*)::int AS count FROM threads WHERE owner_id=${sqlValue(ctx.context.owner_id)}`)[0].count;
      assert.equal(response.status, item.status);
      assert.equal(after - before, item.status === 201 ? 1 : 0);
      if (item.status === 201) assert.equal(response.body.title, item.saved);
      return { input_length: item.title.length, http_status: response.status, thread_delta: after - before, saved_length: response.body.title?.length, observation: item.sub === 'whitespace_observation' ? '全空白存为空标题，仅质量观察' : undefined };
    });
  }

  // TH_003：归档只改变归档元数据，不假定列表必须隐藏或者禁止发问。
  await s.check('TH_003', 'TP-TH-005', 'archive_preserves', '归档时间持久有值，已成功问答的 Message/Run/Event 历史完全保留', async () => {
    const data = await successful(ctx, 'TH_003 归档历史');
    const response = await ctx.request(`/api/v1/threads/${data.thread.thread_id}/archive`, { method: 'POST' });
    assert.equal(response.status, 200); assert.equal(response.body.archived, true);
    const after = await ctx.detail(data.thread.thread_id);
    assert.ok(isTime(after.thread.archived_at));
    assert.ok(JSON.stringify(after.messages) === JSON.stringify(data.detail.messages), '归档不可改变Message历史'); assert.deepEqual(after.runs, data.detail.runs);
    assert.ok(JSON.stringify(await ctx.events(data.run.run_id)) === JSON.stringify(data.events), '归档不可改变Event历史');
    const list = await ctx.request('/api/v1/threads'); assert.equal(list.status, 200);
    const listed = list.body.find(item => item.thread_id === data.thread.thread_id);
    if (listed) assert.equal(listed.archived_at, after.thread.archived_at);
    return { thread_id: data.thread.thread_id, run_id: data.run.run_id, archived_at: after.thread.archived_at, history_preserved: true };
  });

  // TH_004：不存在 Thread 的三种正式操作分别检查无副作用及安全错误。
  for (const operation of ['detail', 'archive', 'message']) {
    await s.check('TH_004', 'TP-TH-006', operation, '不存在 Thread 返回404/THREAD_NOT_FOUND，Thread/Message/Run/Task/Event均无新增', async () => {
      const missing = uuid();
      const route = `/api/v1/threads/${missing}${operation === 'archive' ? '/archive' : operation === 'message' ? '/messages' : ''}`;
      const response = await ctx.request(route, { method: operation === 'detail' ? 'GET' : 'POST', ...(operation === 'message' ? { body: { content: 'TH_004 安全测试问题' } } : {}) });
      assert.equal(response.status, 404); assert.equal(response.body.code, 'THREAD_NOT_FOUND');
      assert.ok(!/traceback|[A-Z]:\\|\/app\/|password|postgresql:\/\//i.test(JSON.stringify(response.body)));
      assert.equal(ctx.sql(`SELECT count(*)::int AS count FROM threads WHERE thread_id=${sqlValue(missing)}`)[0].count, 0);
      assert.deepEqual(chainCounts(ctx, missing), { messages: 0, runs: 0, tasks: 0, events: 0 });
      return { missing_thread_id: missing, operation, http_status: response.status, error_code: response.body.code, facts_added: 0 };
    });
  }
});
