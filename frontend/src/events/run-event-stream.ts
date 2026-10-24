import type { RunEvent } from '../types/api'
import { getEvents } from '../api/runs'
import { apiUrl } from '../api/http'
import { getEvents as getV2Events } from '../api/v2/runs'
import type { RunEvent as V2RunEvent } from '../types/api-v2'

export async function replayEvents(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void) {
  const response = await getEvents(runId, afterSeq)
  for (const event of response.events) onEvent(parseLegacyEvent(event))
}

export function parseLegacyEvent(value: unknown): RunEvent {
  if (!value || typeof value !== 'object' || (value as { schema_version?: unknown }).schema_version !== 1) throw new Error('EVENT_SCHEMA_UNSUPPORTED')
  const event = value as RunEvent
  if (!event.run_id || !Number.isSafeInteger(event.seq) || event.seq < 1 || !legacyTypes.includes(event.type) || !event.data || typeof event.data !== 'object') throw new Error('EVENT_SCHEMA_INVALID')
  if (event.type !== 'task.leased' && ('generation' in event.data || 'branch_id' in event.data || 'operation_kind' in event.data)) throw new Error('EVENT_SCHEMA_INVALID')
  return event
}
const legacyTypes = ['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'answer.delta', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled']

export function openRunStream(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void, onError: () => void, onReady: () => void) {
  const source = new EventSource(apiUrl(`/api/v1/runs/${runId}/events/stream?after_seq=${afterSeq}`), { withCredentials: false })
  let closed = false
  const eventTypes = [
    'run.created',
    'task.queued',
    'task.leased',
    'run.started',
    'retrieval.completed',
    'answer.delta',
    'task.retry_scheduled',
    'message.completed',
    'run.succeeded',
    'run.failed',
    'run.cancelled',
  ]
  for (const eventType of eventTypes) {
    source.addEventListener(eventType, (event) => {
      if (closed) return
      try { onEvent(parseLegacyEvent(JSON.parse((event as MessageEvent).data))) }
      catch { close(); onError() }
    })
  }
  function close() { closed = true; source.close() }
  source.addEventListener('open', () => { if (!closed) onReady() })
  source.onerror = () => { if (!closed) { close(); onError() } }
  // HTTP补放和SSE只调用同一去重入口；关闭后迟到HTTP不得再投影。
  void replayEvents(runId, afterSeq, event => { if (!closed) onEvent(event) }).then(() => {
    if (!closed) onReady()
  }).catch(() => { if (!closed) { close(); onError() } })
  return { close }
}

const v2Types = ['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'answer.delta', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled', 'context.planned', 'context.compacted', 'run.cancelling', 'run.retry_created', 'run.regenerated']
export function parseV2(value: unknown): V2RunEvent {
  if (!value || typeof value !== 'object' || (value as { schema_version?: unknown }).schema_version !== 2) throw new Error('未知或不支持的事件协议版本')
  const event = value as V2RunEvent
  if (!v2Types.includes(event.type) || !event.run_id || !Number.isSafeInteger(event.seq) || event.seq < 1) throw new Error('事件结构不完整')
  if (!event.data || typeof event.data !== 'object' || !('task_id' in event.data) || !('attempt' in event.data) || !('generation' in event.data)) throw new Error('EVENT_SCHEMA_INVALID')
  const { task_id, attempt, generation } = event.data
  const control = ['run.created', 'task.queued', 'run.failed', 'run.cancelled', 'run.cancelling', 'run.retry_created', 'run.regenerated'].includes(event.type)
  if (!(control && task_id === null && attempt === null && generation === null) && !(typeof task_id === 'string' && Number.isSafeInteger(attempt) && Number(attempt) >= 1 && Number.isSafeInteger(generation) && Number(generation) >= 1)) throw new Error('EVENT_SCHEMA_INVALID')
  if (event.type === 'answer.delta' && typeof event.data.text !== 'string') throw new Error('EVENT_SCHEMA_INVALID')
  return event
}
export async function replayV2Events(runId: string, afterSeq: number, onEvent: (event: V2RunEvent) => void) {
  let cursor = afterSeq
  // 分页到尾，不把首个200条误认为完整Journal。
  for (let page = 0; page < 100; page++) {
    const response = await getV2Events(runId, cursor)
    for (const raw of response.events) onEvent(parseSessionEvent(raw))
    if (!response.has_more) return
    if (response.next_after_seq <= cursor) throw new Error('EVENT_CURSOR_INVALID')
    cursor = response.next_after_seq
  }
  throw new Error('EVENT_REPLAY_LIMIT')
}
export function parseSessionEvent(value: unknown): V2RunEvent {
  return value && typeof value === 'object' && (value as { schema_version?: unknown }).schema_version === 1 ? parseLegacyEvent(value) : parseV2(value)
}
export function openV2RunStream(runId: string, afterSeq: number, onEvent: (event: V2RunEvent) => void, onError: (error?: unknown) => void, onReady: () => void) {
  const source = new EventSource(apiUrl(`/api/v2/runs/${encodeURIComponent(runId)}/events/stream?after_seq=${afterSeq}`), { withCredentials: false })
  let closed = false
  let replayed = false; let ready = false
  const maybeReady = () => { if (!closed && replayed && !ready) { ready = true; onReady() } }
  for (const eventType of v2Types) source.addEventListener(eventType, event => {
    if (closed) return
    try { onEvent(parseSessionEvent(JSON.parse((event as MessageEvent).data))) } catch (error) { close(); onError(error) }
  })
  function close() { closed = true; source.close() }
  source.addEventListener('open', maybeReady)
  source.onerror = () => { if (!closed) { close(); onError() } }
  void replayV2Events(runId, afterSeq, event => { if (!closed) onEvent(event) }).then(() => { if (!closed) { replayed = true; maybeReady() } }).catch(error => { if (!closed) { close(); onError(error) } })
  return { close }
}
