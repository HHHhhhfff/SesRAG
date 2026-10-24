import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

export { assert, delay };
export const key = () => crypto.randomUUID();
export const terminal = (status) => ['succeeded', 'failed', 'cancelled'].includes(status);

// 每个请求有界；只返回业务DTO，不记录认证头或运行凭据。
export async function request(context, route, { method = 'GET', body, expected, headers = {} } = {}) {
  const response = await fetch(context.api_base_url + route, { method, headers: { 'Content-Type': 'application/json', ...headers },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(15000) });
  const text = await response.text(); let data; try { data = JSON.parse(text); } catch { data = text; }
  if (expected !== undefined) assert.ok((Array.isArray(expected) ? expected : [expected]).includes(response.status), `${method} ${route} 状态${response.status}，预期${expected}；code=${data?.code ?? '无'}`);
  else assert.ok(response.ok, `${method} ${route} 失败：${response.status}；code=${data?.code ?? '无'}`);
  return { status: response.status, data };
}

export async function until(action, predicate, label, timeout = 45000) {
  const end = performance.now() + timeout; let value;
  do { value = await action(); if (await predicate(value)) return value; await delay(100); } while (performance.now() < end);
  throw new Error(`${label} 超时；最后状态=${typeof value === 'object' ? value?.status ?? value?.code ?? '对象' : value}`);
}

export async function thread(context, title) {
  return (await request(context, '/api/v2/threads', { method: 'POST', body: { title }, expected: 201 })).data;
}
export async function detail(context, tid, bid) {
  return (await request(context, `/api/v2/threads/${tid}${bid ? `?branch_id=${bid}` : ''}`)).data;
}
export async function send(context, item, content, profile = 'mock-default', idempotencyKey = key(), bid = item.default_branch_id) {
  const page = await detail(context, item.thread_id, bid);
  return (await request(context, `/api/v2/threads/${item.thread_id}/messages`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey },
    body: { branch_id: bid, expected_version: page.branch.version, content, model_profile_id: profile, model_profile_version: 1 }, expected: [200, 201] })).data;
}
export async function run(context, rid) { return (await request(context, `/api/v2/runs/${rid}`)).data; }
export async function events(context, rid, after = 0) { return (await request(context, `/api/v2/runs/${rid}/events?after_seq=${after}&limit=1000`)).data.events; }
export async function done(context, rid, timeout = 45000) { return until(() => run(context, rid), (value) => terminal(value.status), `Run ${rid}结算`, timeout); }
export async function answer(context, item, content, profile = 'mock-default', bid) {
  const created = await send(context, item, content, profile, key(), bid); const finished = await done(context, created.run_id);
  assert.equal(finished.status, 'succeeded', `问答未成功：${finished.status}/${finished.last_error_code}`);
  return { ...created, finished };
}
export async function control(context, endpoint, body, method = 'POST') {
  const response = await fetch(context.provider_control_url + endpoint, { method,
    headers: { Authorization: `Bearer ${process.env.PROVIDER_CONTROL_TOKEN}`, 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(20000) });
  assert.equal(response.status, 200, `Provider控制协议失败：${endpoint}/${response.status}`);
  return response.json();
}
export async function scenario(context, overrides = {}) {
  // 终态事务可早于Provider连接finally；等待实收处理真正退出，避免污染下一用例。
  await until(async () => (await observations(context)).active_requests, (value) => value === 0, '前一Provider请求退出', 20000);
  const before = await observations(context);
  const model = overrides.model ?? 'ws-http-a';
  const configured = await control(context, '/control/scenario', { schema_version: 1, model, kind: 'normal', chunks: ['测试回答'], ...overrides }, 'PUT');
  const scopes = barrierScopes.get(context) ?? new Map();
  scopes.set(model, Math.max(0, ...before.requests.map((item) => item.request_seq)));
  barrierScopes.set(context, scopes);
  return configured;
}
export async function observations(context) { return control(context, '/control/observations', undefined, 'GET'); }
const barrierScopes = new WeakMap();
export const isCurrentBarrier = (item, model, after) => item?.model === model && item.request_seq > after && item.waiting_release === true && item.finished === false;
export async function barrier(context, model = 'ws-http-a') {
  // waiting_release是历史阶段标识，不会在finished时清除；必须同时核验本次配置之后的请求身份。
  const after = barrierScopes.get(context)?.get(model) ?? 0;
  return until(async () => (await observations(context)).requests.findLast((item) => isCurrentBarrier(item, model, after)),
    Boolean, `Provider ${model}本次请求停顿屏障`);
}
export async function release(context, record) {
  return control(context, '/control/release', { schema_version: 1, model: record.model, request_seq: record.request_seq });
}

// RUN_015/024：Provider释放失败也不能跳过已停止服务的恢复；失败继续向外传播。
export async function releaseThenRestore(releasePending, restoreService) {
  try { await releasePending(); }
  finally { await restoreService(); }
}

// UI_014/COMP_001：建立真实cancelled来源，避免快速Mock先成功导致retry前提失效。
export async function cancelledSource(context, item, content) {
  await scenario(context, { kind: 'stall', chunks: ['CANCEL_SOURCE_HEAD', 'CANCEL_SOURCE_TAIL'] });
  const created = await send(context, item, content, 'ws-http-a'); const held = await barrier(context);
  try { await request(context, `/api/v2/runs/${created.run_id}/cancel`, { method: 'POST' }); }
  finally { await release(context, held); }
  assert.equal((await done(context, created.run_id)).status, 'cancelled', 'retry来源必须先被真实取消');
  await scenario(context); return created;
}
