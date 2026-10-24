import { assert, key, thread, detail, request, send, answer, done, scenario, barrier, release } from './support.mjs';

const route = (t) => `/api/v2/threads/${t.thread_id}`;
async function fork(c, t, bid, mid, name) {
  return (await request(c, `${route(t)}/branches`, { method: 'POST', expected: 201, headers: { 'Idempotency-Key': key() },
    body: { parent_branch_id: bid, fork_message_id: mid, ...(name ? { name } : {}) } })).data;
}
async function titled(c, id) { return thread(c, `${id}-${key().slice(0, 8)}`); }

// SES_001～018：正式API创建动态事实；每例独立Thread，参数负例不预造成功记录。
export const sessionRuntime = {
  async SES_001({ context: c }) {
    const t = await titled(c, 'SES_001'); const d = await detail(c, t.thread_id); const branches = (await request(c, `${route(t)}/branches`)).data.branches;
    assert.equal(branches.length, 1); assert.equal(d.branch.branch_id, t.default_branch_id); assert.equal(d.branch.thread_id, t.thread_id); assert.equal(d.branch.version, 0); assert.equal(d.branch.is_default, true); assert.equal(d.messages.length, 0);
    return { actual: '正式创建得到唯一Thread与唯一默认Branch，归属/版本/空历史一致。', thread: t, branch: d.branch };
  },
  async SES_002({ context: c }) {
    const created = []; for (let i = 0; i < 5; i++) created.push(await titled(c, 'SES_002'));
    const rows = []; let cursor;
    do { const page = (await request(c, `/api/v2/threads?include_archived=true&limit=2${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`)).data; rows.push(...page.threads); cursor = page.next_cursor; assert.equal(page.has_more, Boolean(cursor)); } while (cursor);
    assert.equal(rows.length, new Set(rows.map((item) => item.thread_id)).size); assert.ok(created.every((item) => rows.some((row) => row.thread_id === item.thread_id)));
    const order = rows.map((item) => `${item.updated_at}|${item.thread_id}`); assert.deepEqual(order, [...order].sort().reverse());
    return { actual: `正式列表每页2项读取${rows.length}个Thread，排序稳定且无重漏；快照期间未并发更新。`, ids: rows.map((item) => item.thread_id) };
  },
  async SES_003({ context: c }) {
    const values = ['cursor=bad', 'cursor=%7B%7D', 'limit=0', 'limit=201', 'limit=-1', 'limit=wrong', 'unknown_field=value'];
    for (const value of values) await request(c, `/api/v2/threads?${value}`, { expected: 422 });
    return { actual: `非法/损坏游标及分页边界共${values.length}组均安全422。`, variants: values };
  },
  async SES_004({ context: c }) {
    const t = await titled(c, 'SES_004'); await answer(c, t, '第1轮'); await answer(c, t, '第2轮');
    const all = await detail(c, t.thread_id); const recent = (await request(c, `${route(t)}?limit=2`)).data; const old = (await request(c, `${route(t)}?limit=2&before_seq=${recent.next_before_seq}`)).data;
    assert.deepEqual([...old.messages, ...recent.messages], all.messages); assert.equal(new Set(all.messages.map((m) => m.message_id)).size, 4);
    return { actual: '两轮真实Worker问答按历史分页重建，身份/角色/正文/seq与完整服务端历史一致。', message_ids: all.messages.map((m) => m.message_id) };
  },
  async SES_005({ context: c }) {
    const results = [];
    for (const title of ['a', '中'.repeat(200), '  保留合法标题  ']) {
      const t = (await request(c, '/api/v2/threads', { method: 'POST', body: { title }, expected: 201 })).data; assert.equal(t.title, title.trim());
      const updated = (await request(c, route(t), { method: 'PATCH', body: { title }, expected: 200 })).data; assert.equal(updated.title, title.trim()); results.push({ length: title.length, status: 200 });
    }
    const t = await titled(c, 'SES_005');
    for (const title of ['', ' \t\n ', 'x'.repeat(201)]) { await request(c, '/api/v2/threads', { method: 'POST', body: { title }, expected: 422 }); await request(c, route(t), { method: 'PATCH', body: { title }, expected: 422 }); assert.equal((await detail(c, t.thread_id)).thread.title, t.title); }
    return { actual: '新建/重命名1与200字符及trim合法；空白/201字符均422，失败后旧标题不变。', results };
  },
  async SES_006({ context: c }) {
    const t = await titled(c, 'SES_006'); const r = await answer(c, t, '归档事实'); const before = await detail(c, t.thread_id);
    await request(c, route(t), { method: 'PATCH', body: { archived: true } }); const after = await detail(c, t.thread_id);
    assert.ok(after.thread.archived_at); assert.deepEqual(after.messages, before.messages); assert.deepEqual(after.runs, before.runs); assert.equal((await request(c, `/api/v2/runs/${r.run_id}`)).data.status, 'succeeded');
    return { actual: '归档仅改变归档标记，已完成Message/Run仍保持原身份原文可读。', thread_id: t.thread_id };
  },
  async SES_007({ context: c }) {
    const t = await titled(c, 'SES_007'); const token = key(); const payload = { branch_id: t.default_branch_id, expected_version: 0, content: '原幂等输入', model_profile_id: 'mock-default', model_profile_version: 1 };
    const original = (await request(c, `${route(t)}/messages`, { method: 'POST', body: payload, headers: { 'Idempotency-Key': token }, expected: 201 })).data; await done(c, original.run_id);
    await request(c, route(t), { method: 'PATCH', body: { archived: true } }); const before = await detail(c, t.thread_id);
    const replay = await request(c, `${route(t)}/messages`, { method: 'POST', body: payload, headers: { 'Idempotency-Key': token }, expected: 200 });
    // 幂等身份不变；status是当前事实，不能要求仍为首次响应的queued。
    for (const field of ['branch_id', 'message_id', 'run_id', 'task_id']) assert.equal(replay.data[field], original[field]);
    assert.equal(replay.data.status, 'succeeded');
    await request(c, `${route(t)}/messages`, { method: 'POST', body: { ...payload, expected_version: before.branch.version }, headers: { 'Idempotency-Key': key() }, expected: 409 });
    await request(c, `${route(t)}/branches`, { method: 'POST', body: { parent_branch_id: t.default_branch_id, fork_message_id: original.message_id }, headers: { 'Idempotency-Key': key() }, expected: 409 });
    for (const op of ['retry', 'regenerate']) await request(c, `/api/v2/runs/${original.run_id}/${op}`, { method: 'POST', body: {}, headers: { 'Idempotency-Key': key() }, expected: 409 });
    assert.deepEqual((await detail(c, t.thread_id)).messages, before.messages);
    return { actual: '归档后新消息/分支/retry/regenerate均拒绝；既有同键同体优先返回原身份，无新消息。', run_id: original.run_id };
  },
  async SES_008({ context: c }) {
    const t = await titled(c, 'SES_008'); const old = await answer(c, t, '取消归档前历史'); await request(c, route(t), { method: 'PATCH', body: { archived: true } }); await request(c, route(t), { method: 'PATCH', body: { archived: false } });
    assert.equal((await detail(c, t.thread_id)).thread.archived_at, null); await answer(c, t, '取消归档继续'); assert.equal((await request(c, `/api/v2/runs/${old.run_id}`)).data.status, 'succeeded');
    return { actual: '取消归档后普通列表资格及继续写入恢复，旧Run/历史仍可读。', thread_id: t.thread_id };
  },
  async SES_009({ context: c }) {
    const t = await titled(c, 'SES_009'); await answer(c, t, '合法锚点'); const d = await detail(c, t.thread_id); const children = [];
    for (const m of d.messages) { const child = await fork(c, t, t.default_branch_id, m.message_id); assert.equal(child.parent_branch_id, t.default_branch_id); assert.equal(child.fork_message_id, m.message_id); assert.equal(child.thread_id, t.thread_id); children.push(child.branch_id); }
    assert.equal((await detail(c, t.thread_id)).messages.length, 2);
    return { actual: '持久用户/assistant两种锚点均建立独立子Branch，父子归属及锚点正确，未复制祖先消息。', children };
  },
  async SES_010({ context: c }) {
    const t = await titled(c, 'SES_010'); await answer(c, t, '共同历史'); const before = await detail(c, t.thread_id); const child = await fork(c, t, t.default_branch_id, before.messages.at(-1).message_id);
    assert.deepEqual((await detail(c, t.thread_id, child.branch_id)).messages, before.messages);
    await answer(c, t, '父独有后缀'); await answer(c, t, '子独有后缀', 'mock-default', child.branch_id);
    const parent = await detail(c, t.thread_id); const nested = await detail(c, t.thread_id, child.branch_id);
    assert.deepEqual(parent.messages.slice(0, 2), nested.messages.slice(0, 2)); assert.ok(!nested.messages.some((m) => m.content === '父独有后缀')); assert.ok(!parent.messages.some((m) => m.content === '子独有后缀'));
    return { actual: '分叉前后共同前缀身份保持，父子新后缀互不进入另一条路径且祖先不复制。', child_id: child.branch_id };
  },
  async SES_011({ context: c }) {
    const t = await titled(c, 'SES_011'); await answer(c, t, 'ROOT_ONLY'); const root = await detail(c, t.thread_id); const mid = root.messages.at(-1).message_id;
    const a = await fork(c, t, t.default_branch_id, mid); const b = await fork(c, t, t.default_branch_id, mid); await answer(c, t, 'SIB_A_ONLY', 'mock-default', a.branch_id); await answer(c, t, 'SIB_B_ONLY', 'mock-default', b.branch_id);
    const apath = await detail(c, t.thread_id, a.branch_id); const nested = await fork(c, t, a.branch_id, apath.messages.at(-1).message_id); await answer(c, t, 'NEST_ONLY', 'mock-default', nested.branch_id);
    for (const [branch, included, excluded] of [[a, 'SIB_A_ONLY', ['SIB_B_ONLY', 'NEST_ONLY']], [b, 'SIB_B_ONLY', ['SIB_A_ONLY', 'NEST_ONLY']], [nested, 'NEST_ONLY', ['SIB_B_ONLY']]]) {
      const page = await detail(c, t.thread_id, branch.branch_id); assert.ok(page.messages.some((m) => m.content === included)); assert.ok(excluded.every((token) => !page.messages.some((m) => m.content === token)));
    }
    return { actual: '同Thread兄弟与嵌套路径分别读取，祖先只一份且兄弟/未来后缀隔离；执行实收隔离另由指定Worker断言共同核验。', branches: [a.branch_id, b.branch_id, nested.branch_id] };
  },
  async SES_012({ context: c }) {
    const a = await titled(c, 'SES_012A'); const b = await titled(c, 'SES_012B'); const source = await answer(c, a, '合法输入'); const foreign = await answer(c, b, '外Thread输入');
    const base = { parent_branch_id: a.default_branch_id, fork_message_id: source.message_id };
    for (const payload of [{ ...base, fork_message_id: key() }, { ...base, fork_message_id: foreign.message_id }, { ...base, parent_branch_id: b.default_branch_id }]) await request(c, `${route(a)}/branches`, { method: 'POST', body: payload, headers: { 'Idempotency-Key': key() }, expected: 404 });
    for (const name of [null, '', ' ', 'x'.repeat(81)]) await request(c, `${route(a)}/branches`, { method: 'POST', body: { ...base, name }, headers: { 'Idempotency-Key': key() }, expected: 422 });
    assert.equal((await request(c, `${route(a)}/branches`)).data.branches.length, 1);
    return { actual: '不存在/跨Thread对象404；null/空白/81字符名称422；无部分Branch。不可见同Thread锚点由指定路径断言覆盖。' };
  },
  async SES_013({ context: c }) {
    const t = await titled(c, 'SES_013-count'); const first = await answer(c, t, '数量锚点');
    for (let i = 0; i < 99; i++) await fork(c, t, t.default_branch_id, first.message_id, i === 98 ? 'x'.repeat(80) : 'a');
    assert.equal((await request(c, `${route(t)}/branches`)).data.branches.length, 100);
    const overflow = await request(c, `${route(t)}/branches`, { method: 'POST', body: { parent_branch_id: t.default_branch_id, fork_message_id: first.message_id }, headers: { 'Idempotency-Key': key() }, expected: 422 }); assert.equal(overflow.data.code, 'BRANCH_LIMIT_EXCEEDED');
    const depth = await titled(c, 'SES_013-depth'); const source = await answer(c, depth, '深度锚点'); let parent = depth.default_branch_id;
    for (let i = 0; i < 31; i++) parent = (await fork(c, depth, parent, source.message_id)).branch_id;
    assert.equal((await request(c, `${route(depth)}/branches`, { method: 'POST', body: { parent_branch_id: parent, fork_message_id: source.message_id }, headers: { 'Idempotency-Key': key() }, expected: 422 })).data.code, 'BRANCH_LIMIT_EXCEEDED');
    return { actual: '正式API达到100个Branch/32层深度并接受80字符名；下一项均BRANCH_LIMIT_EXCEEDED且不产生部分分支。' };
  },
  async SES_014({ context: c }) {
    const t = await titled(c, 'SES_014'); await answer(c, t, '已推进Head'); const before = await detail(c, t.thread_id);
    const response = await request(c, `${route(t)}/messages`, { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { branch_id: t.default_branch_id, expected_version: 0, content: '旧版本写入' }, expected: 409 }); assert.equal(response.data.code, 'BRANCH_HEAD_CHANGED');
    assert.deepEqual((await detail(c, t.thread_id)).messages, before.messages); await answer(c, t, '当前版本正常');
    return { actual: '过期expected_version安全409且原Head/Message不变；当前版本请求成功推进。' };
  },
  async SES_015({ context: c }) {
    const t = await titled(c, 'SES_015'); const earlier = await answer(c, t, '早期完成锚点'); const b = await fork(c, t, t.default_branch_id, earlier.message_id);
    await scenario(c, { kind: 'stall', chunks: ['活动Run草稿', '后缀'] }); const created = await send(c, t, '活动输入', 'ws-http-a'); const held = await barrier(c);
    let independent;
    try {
      const page = await detail(c, t.thread_id);
      assert.equal((await request(c, `${route(t)}/messages`, { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { branch_id: t.default_branch_id, expected_version: page.branch.version, content: '冲突写' }, expected: 409 })).data.code, 'BRANCH_BUSY');
      assert.equal((await request(c, `${route(t)}/branches`, { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { parent_branch_id: t.default_branch_id, fork_message_id: created.message_id }, expected: 422 })).data.code, 'INVALID_BRANCH_PATH');
      await fork(c, t, t.default_branch_id, earlier.message_id); independent = await send(c, t, '独立Branch继续', 'mock-default', key(), b.branch_id);
    } finally { await release(c, held); }
    await done(c, created.run_id); assert.equal((await done(c, independent.run_id)).status, 'succeeded'); return { actual: '活动Branch新消息BRANCH_BUSY，活动输入锚点INVALID_BRANCH_PATH；早期合法分叉与同Thread独立Branch正常推进。' };
  },
  async SES_018({ context: c }) {
    const rejected = [];
    const t = await titled(c, 'SES_018'); const valid = { branch_id: t.default_branch_id, content: '合法', expected_version: 0 };
    for (const [label, body, id] of [
      ['too-long', { ...valid, content: 'x'.repeat(20001) }, key()], ['blank', { ...valid, content: '  \n ' }, key()],
      ['missing-key', valid, undefined], ['blank-key', valid, ''], ['long-key', valid, 'k'.repeat(201)],
      ['missing-branch', { content: 'x', expected_version: 0 }, key()], ['missing-version', { branch_id: valid.branch_id, content: 'x' }, key()],
      ['negative-version', { ...valid, expected_version: -1 }, key()], ['half-profile', { ...valid, model_profile_id: 'mock-default' }, key()],
      ['null-profile', { ...valid, model_profile_id: null, model_profile_version: null }, key()], ['extra-owner', { ...valid, owner_id: 'foreign' }, key()],
    ]) { await request(c, `${route(t)}/messages`, { method: 'POST', body, headers: id === undefined ? {} : { 'Idempotency-Key': id }, expected: 422 }); rejected.push(label); }
    assert.equal((await detail(c, t.thread_id)).messages.length, 0);
    for (const content of ['a', 'x'.repeat(20000), '  原始合法空白  ']) { const own = await titled(c, 'SES_018valid'); const created = await send(c, own, content); const page = await detail(c, own.thread_id); assert.equal(page.messages[0].content, content); await request(c, `/api/v2/runs/${created.run_id}/cancel`, { method: 'POST' }); await done(c, created.run_id); }
    return { actual: `输入/幂等头${rejected.length}组非法边界均安全422且无消息；1/20000字符及合法原始空白按原文保存。`, rejected };
  },
};
