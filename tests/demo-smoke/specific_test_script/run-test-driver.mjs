import { randomUUID } from 'node:crypto';
import { assert } from '../lib/category-kit.mjs';

// TH/MSG/RUN/CAN/EVT/SSE：只复用客户端及准备方式，每条用例仍创建自己的业务身份。
export const uuid = () => randomUUID();
export const sqlValue = value => `'${String(value).replaceAll("'", "''")}'`;
export function lazy(prepare) {
  let result;
  return () => result ??= Promise.resolve().then(prepare);
}
export function isUuid(value) {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}
export function isTime(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value));
}
export function assertMessageSource(projected, persisted, role) {
  const expected = role === 'user' ? 'user_input' : 'assistant_generation';
  assert.equal(projected.role, role); assert.equal(persisted.role, role);
  assert.equal(projected.source, expected, '公开来源必须表达事实来源，不能复制role');
  assert.equal(persisted.source, expected, 'PG来源必须表达事实来源，不能复制role');
  assert.ok(isTime(projected.created_at) && isTime(persisted.created_at));
  assert.equal(Date.parse(projected.created_at), Date.parse(persisted.created_at), '公开时间必须对应同一持久Message');
  assert.equal(projected.message_id, persisted.message_id);
}
export function increasing(values) {
  return values.every((value, index) => Number.isInteger(value) && value > 0 && (index === 0 || value > values[index - 1]));
}
export function ids(body) {
  return { message_id: body.message_id, run_id: body.run_id, task_id: body.task_id };
}
export async function successful(ctx, title, content = '说明本次测试的会话事实。') {
  const thread = await ctx.thread(title);
  const submitted = await ctx.submit(thread.thread_id, content, uuid());
  const run = await ctx.waitRun(submitted.run_id);
  assert.equal(run.status, 'succeeded', '准备的正常 Run 必须真实成功');
  return { thread, submitted, run, detail: await ctx.detail(thread.thread_id), events: await ctx.events(run.run_id) };
}
export function chainCounts(ctx, threadId) {
  const id = sqlValue(threadId);
  return ctx.sql(`SELECT (SELECT count(*)::int FROM messages WHERE thread_id=${id}) AS messages, (SELECT count(*)::int FROM runs WHERE thread_id=${id}) AS runs, (SELECT count(*)::int FROM tasks WHERE run_id IN (SELECT run_id FROM runs WHERE thread_id=${id})) AS tasks, (SELECT count(*)::int FROM run_events WHERE run_id IN (SELECT run_id FROM runs WHERE thread_id=${id})) AS events`)[0];
}
export function runFacts(ctx, runId) {
  return ctx.sql(`SELECT r.run_id,r.thread_id,r.user_message_id,r.assistant_message_id,r.primary_task_id,r.status,r.snapshot_json,r.next_event_seq,r.cancel_requested_at,r.last_error_code,r.created_at,t.task_id,t.kind,t.state AS task_state,t.attempt,t.generation,t.worker_id,t.lease_expires_at,t.last_error_code AS task_error_code FROM runs r JOIN tasks t ON t.task_id=r.primary_task_id WHERE r.run_id=${sqlValue(runId)}`)[0];
}
export async function stoppedWorker(ctx, operation) {
  // MSG_001/002/004/005/006、RUN_001/003/004、CAN_001、SSE_003/004：仅停止本次 project。
  try {
    const result = ctx.compose(['stop', '-t', '25', 'worker']);
    assert.equal(result.code, 0, '本次 Worker 必须停止，才能建立 queued 前提');
    return await operation();
  } finally {
    const restored = ctx.compose(['start', 'worker']);
    assert.equal(restored.code, 0, '必须恢复本次 Worker');
    await ctx.ready(20000);
  }
}
export async function restartApi(ctx) {
  // EVT_003：重启不会创建新 project；恢复等待有界，失败仍保留分类报告。
  try {
    assert.equal(ctx.compose(['restart', 'api']).code, 0, '重启本次 API 失败');
  } finally {
    await ctx.ready(20000);
  }
}
export function eventSummary(events) {
  return events.map(event => ({ event_id: event.event_id, run_id: event.run_id, seq: event.seq, type: event.type }));
}
export async function readSSE(ctx, runId, { after = 0, header, timeoutMs = 4500, maxFrames = Infinity, onFrame } = {}) {
  // SSE_001～005、EVT_001：所有连接有截止时间，并在 finally 释放 reader 和 HTTP 连接。
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let reader;
  const result = { status: null, content_type: null, frames: [], eof: false, timed_out: false, stream_error: null };
  try {
    const response = await fetch(new URL(`/api/v1/runs/${runId}/events/stream?after_seq=${after}`, ctx.args.BaseUrl), {
      headers: { Accept: 'text/event-stream', ...(header === undefined ? {} : { 'Last-Event-ID': String(header) }) },
      signal: controller.signal,
    });
    result.status = response.status;
    result.content_type = response.headers.get('content-type');
    if (response.status !== 200) {
      const body = await response.text();
      try { result.error_body = JSON.parse(body); } catch { result.error_body = '响应不是 JSON'; }
      return result;
    }
    reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let pending = '';
    while (true) {
      const item = await reader.read();
      if (item.done) { result.eof = true; break; }
      pending += decoder.decode(item.value, { stream: true });
      let boundary;
      while ((boundary = /\r?\n\r?\n/.exec(pending))) {
        const block = pending.slice(0, boundary.index);
        pending = pending.slice(boundary.index + boundary[0].length);
        const fields = {};
        for (const line of block.split(/\r?\n/)) {
          if (line.startsWith(':')) continue;
          const colon = line.indexOf(':');
          if (colon < 0) continue;
          const name = line.slice(0, colon);
          const value = line.slice(colon + 1).replace(/^ /, '');
          fields[name] = name === 'data' && fields.data !== undefined ? `${fields.data}\n${value}` : value;
        }
        if (fields.data !== undefined) {
          const frame = { id: fields.id, event: fields.event, data: JSON.parse(fields.data) };
          result.frames.push(frame);
          if (onFrame) await onFrame(frame);
          if (result.frames.length >= maxFrames) return result;
        }
      }
    }
  } catch (error) {
    result.timed_out = controller.signal.aborted;
    result.stream_error = result.timed_out ? '客户端有界超时' : error.name;
  } finally {
    clearTimeout(timer);
    controller.abort();
    if (reader) { try { await reader.cancel(); } catch { /* SSE：服务端异常断流也必须释放本地 reader。 */ } }
  }
  return result;
}
export function sseSummary(stream) {
  return { status: stream.status, content_type: stream.content_type, eof: stream.eof, timed_out: stream.timed_out, stream_error: stream.stream_error, frames: stream.frames.map(frame => ({ id: frame.id, event: frame.event, event_id: frame.data.event_id, run_id: frame.data.run_id, seq: frame.data.seq })) };
}
