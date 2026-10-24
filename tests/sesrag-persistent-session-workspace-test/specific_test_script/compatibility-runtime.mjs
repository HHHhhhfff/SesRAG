import fs from 'node:fs';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { repoRoot } from '../tooling/product-category.mjs';
import { assert, key, thread, detail, request, send, answer, run, events, done, until, cancelledSource } from './support.mjs';

const ajv = new Ajv2020({ strict: false, allErrors: true }); addFormats(ajv);
for (const file of fs.readdirSync(path.join(repoRoot, 'contracts')).filter((name) => name.endsWith('.json'))) {
  const schema = JSON.parse(fs.readFileSync(path.join(repoRoot, 'contracts', file), 'utf8'));
  // 部分v1契约使用相对$id，按契约目录URI解析，保留其正式字段/约束。
  schema.$id = new URL(schema.$id ?? file, 'https://sesrag.local/contracts/').href; ajv.addSchema(schema);
}
export function validate(name, data) {
  const validator = ajv.getSchema(`https://sesrag.local/contracts/${name}`); assert.ok(validator, `缺少契约${name}`);
  assert.ok(validator(data), `契约${name}拒绝实际响应：${JSON.stringify(validator.errors)}`);
}
async function sse(c, rid, version = 2) {
  const response = await fetch(`${c.api_base_url}/api/v${version}/runs/${rid}/events/stream`, { signal: AbortSignal.timeout(15000) }); assert.equal(response.status, 200);
  const text = await response.text(); const packets = text.split(/\r?\n/).filter((line) => line.startsWith('data: ')).map((line) => JSON.parse(line.slice(6)));
  for (const packet of packets) validate(`run_event_v${version}.json`, packet);
  return packets;
}
export async function upload(c, name, data, mime = 'text/plain') {
  const body = new FormData(); body.set('file', new Blob([data], { type: mime }), name);
  const response = await fetch(`${c.api_base_url}/api/v1/documents`, { method: 'POST', body, signal: AbortSignal.timeout(20000) }); assert.equal(response.status, 201);
  const document = await response.json(); validate('document_v1.json', document);
  const ready = await until(async () => (await request(c, '/api/v1/documents')).data.documents.find((item) => item.document_id === document.document_id), (item) => ['indexed', 'failed'].includes(item?.status), '文档索引', 60000);
  assert.equal(ready.status, 'indexed', `文档索引失败：${ready.last_error_code}`); return ready;
}

export const compatibilityRuntime = {
  // COMP_001：15个正式v2入口逐项真实调用并验证精确响应契约。
  async COMP_001({ context: c }) {
    const t = await thread(c, `COMP_001-${key().slice(0, 8)}`); validate('thread_v2.json', t);
    const observed = ['POST threads'];
    async function get(url, schema, options) { const response = await request(c, url, options); validate(schema, response.data); observed.push(`${options?.method ?? 'GET'} ${url.replace(/[0-9a-f-]{36}/g, ':id')}`); return response.data; }
    await get('/api/v2/models', 'api_responses_v2.json#/$defs/ModelListResponse');
    await get('/api/v2/threads', 'api_responses_v2.json#/$defs/ThreadList');
    const d = await get(`/api/v2/threads/${t.thread_id}`, 'api_responses_v2.json#/$defs/ThreadDetail');
    await get(`/api/v2/threads/${t.thread_id}`, 'thread_v2.json', { method: 'PATCH', body: { title: t.title + '改名' } });
    await get(`/api/v2/threads/${t.thread_id}/branches`, 'api_responses_v2.json#/$defs/BranchListResponse');
    const first = await get(`/api/v2/threads/${t.thread_id}/messages`, 'api_responses_v2.json#/$defs/MessageRunResponse', { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { branch_id: d.branch.branch_id, expected_version: 0, content: 'v2契约问题' }, expected: 201 });
    await done(c, first.run_id);
    await get(`/api/v2/runs/${first.run_id}`, 'run_v2.json');
    await get(`/api/v2/runs/${first.run_id}/events`, 'api_responses_v2.json#/$defs/EventListResponse');
    const packets = await sse(c, first.run_id); assert.ok(packets.length); observed.push('GET Run events/stream');
    await get(`/api/v2/runs/${first.run_id}/context`, 'api_responses_v2.json#/$defs/ContextResponse');
    await get(`/api/v2/runs/${first.run_id}/cancel`, 'api_responses_v2.json#/$defs/CancelResponse', { method: 'POST' });
    const child = await get(`/api/v2/threads/${t.thread_id}/branches`, 'branch_v2.json', { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { parent_branch_id: d.branch.branch_id, fork_message_id: first.message_id }, expected: 201 }); assert.ok(child.branch_id);
    const regenerated = await get(`/api/v2/runs/${first.run_id}/regenerate`, 'api_responses_v2.json#/$defs/MessageRunResponse', { method: 'POST', headers: { 'Idempotency-Key': key() }, body: {}, expected: 201 }); await done(c, regenerated.run_id);
    const cancelSource = await thread(c, 'COMP_001-cancel-source'); const source = await cancelledSource(c, cancelSource, '取消再重试');
    const retried = await get(`/api/v2/runs/${source.run_id}/retry`, 'api_responses_v2.json#/$defs/MessageRunResponse', { method: 'POST', headers: { 'Idempotency-Key': key() }, body: {}, expected: 201 }); await done(c, retried.run_id);
    const invalid = await request(c, '/api/v2/threads', { method: 'POST', body: { title: 'x', owner_id: 'forbidden' }, expected: 422 }); validate('api_responses_v2.json#/$defs/ValidationErrorResponse', invalid.data);
    return { actual: 'v2十五类正式方法/路径均实际调用并通过当前JSON Schema；SSE逐事件校验版本，额外字段422。', observed };
  },
  // COMP_002：v1成功契约仍不需要v2必填字段，旧对象不能误变v2。
  async COMP_002({ context: c }) {
    const created = await request(c, '/api/v1/threads', { method: 'POST', body: { title: 'COMP_002 legacy' }, expected: 201 }); const t = created.data; validate('thread_v1.json', t);
    validate('api_responses_v1.json#/$defs/ThreadList', (await request(c, '/api/v1/threads')).data);
    validate('api_responses_v1.json#/$defs/ThreadDetail', (await request(c, `/api/v1/threads/${t.thread_id}`)).data);
    const token = key(); const first = (await request(c, `/api/v1/threads/${t.thread_id}/messages`, { method: 'POST', body: { content: '旧客户端输入' }, headers: { 'Idempotency-Key': token }, expected: 201 })).data; validate('api_responses_v1.json#/$defs/MessageRunResponse', first);
    await done(c, first.run_id); validate('run_v1.json', (await request(c, `/api/v1/runs/${first.run_id}`)).data);
    validate('api_responses_v1.json#/$defs/EventListResponse', (await request(c, `/api/v1/runs/${first.run_id}/events`)).data); await sse(c, first.run_id, 1);
    validate('api_responses_v1.json#/$defs/CancelResponse', (await request(c, `/api/v1/runs/${first.run_id}/cancel`, { method: 'POST' })).data);
    validate('api_responses_v1.json#/$defs/ArchiveResponse', (await request(c, `/api/v1/threads/${t.thread_id}/archive`, { method: 'POST' })).data);
    const replay = await request(c, `/api/v1/threads/${t.thread_id}/messages`, { method: 'POST', body: { content: '旧客户端输入' }, headers: { 'Idempotency-Key': token }, expected: 200 }); assert.equal(replay.data.run_id, first.run_id);
    return { actual: 'v1 Thread/消息/Run/Event/SSE/cancel/archive旧响应逐项校验，无新增必填v2字段；归档后的原键返回旧身份。', run_id: first.run_id };
  },
  async COMP_004({ context: c }) {
    const t = (await request(c, '/api/v1/threads', { method: 'POST', body: { title: 'COMP_004' }, expected: 201 })).data;
    const created = (await request(c, `/api/v1/threads/${t.thread_id}/messages`, { method: 'POST', body: { content: 'legacy事实' }, expected: 201 })).data; await done(c, created.run_id);
    const journal = await events(c, created.run_id); const projected = await run(c, created.run_id);
    assert.equal(projected.legacy, true); assert.equal(projected.model, null); assert.equal(projected.snapshot, null); assert.equal(projected.context_plan, null);
    await sse(c, created.run_id); await request(c, `/api/v2/runs/${created.run_id}/cancel`, { method: 'POST' });
    assert.equal((await detail(c, t.thread_id)).thread.conversation_version, 1); assert.deepEqual(await events(c, created.run_id), journal);
    return { actual: 'v2只读/取消legacy不升级Thread，模型快照/计划按契约为空，schema1事件原样补放且不改写。', run_id: created.run_id };
  },
  // COMP_013：真实txt/md/docx上传、索引和路由审计，保持旧文档与health边界。
  async COMP_013(suite) {
    const c = suite.context; const indexed = [];
    for (const [name, file, mime] of [['evidence.txt', path.join(repoRoot, 'tests/sesrag-persistent-session-workspace-test/fixtures/documents/evidence.txt'), 'text/plain'], ['history.md', path.join(repoRoot, 'tests/sesrag-persistent-session-workspace-test/fixtures/documents/history-sentinel.md'), 'text/markdown'], ['minimal.docx', path.join(suite.tmp, 'inputs/minimal.docx'), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']]) indexed.push(await upload(c, name, fs.readFileSync(file), mime));
    for (const document of indexed) validate('api_responses_v1.json#/$defs/IndexResponse', (await request(c, `/api/v1/documents/${document.document_id}/index`, { method: 'POST' })).data);
    assert.equal((await request(c, '/health/live')).data.status, 'ok'); assert.ok((await request(c, '/health/ready')).data.worker_count >= 1);
    const spec = (await request(c, '/openapi.json')).data; const paths = Object.keys(spec.paths);
    assert.equal(paths.filter((p) => p.startsWith('/api/v2/') && /documents|\/chat|\/health|\/archive/.test(p)).length, 0);
    return { actual: 'txt/md/docx经正式v1上传与Worker索引成功；旧index/health继续可用，路由未新增平行v2 documents/chat/health/archive。', documents: indexed.map((item) => ({ document_id: item.document_id, batch: item.active_index_batch_id })) };
  },
};
