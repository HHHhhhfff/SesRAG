import type { RunEvent } from '../types/api-v3'
import { getEvents } from '../api/v3/sessions'
import { apiUrl } from '../api/http'
import { parseSessionEvent } from './run-event-stream'

const kinds = ['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'answer.delta', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled', 'context.planned', 'context.compacted', 'run.cancelling', 'run.retry_created', 'run.regenerated', 'tool.started', 'tool.stage', 'tool.completed', 'tool.failed', 'tool.cancelled']
export function parseV3Event(value: unknown): RunEvent {
  if (!value || typeof value !== 'object') throw new Error('EVENT_SCHEMA_INVALID')
  if (!('schema_version' in value) || value.schema_version !== 3) return parseSessionEvent(value)
  // 类型来自严格契约；边界再校验投影必需的版本、游标、执行身份和载荷。
  const event = value as RunEvent
  if (!kinds.includes(event.type) || !event.run_id || !Number.isSafeInteger(event.seq) || event.seq < 1 || !event.data || typeof event.data !== 'object') throw new Error('EVENT_SCHEMA_INVALID')
  const control = ['run.created', 'task.queued', 'run.failed', 'run.cancelled', 'run.cancelling', 'run.retry_created', 'run.regenerated'].includes(event.type)
  if (!('task_id' in event.data && 'attempt' in event.data && 'generation' in event.data)) throw new Error('EVENT_SCHEMA_INVALID')
  const { task_id, generation, attempt } = event.data
  if (!(control && task_id === null && attempt === null && generation === null) && !(typeof task_id === 'string' && Number.isSafeInteger(attempt) && Number(attempt) > 0 && Number.isSafeInteger(generation) && Number(generation) > 0)) throw new Error('EVENT_SCHEMA_INVALID')
  if (event.type === 'answer.delta' && typeof event.data.text !== 'string') throw new Error('EVENT_SCHEMA_INVALID')
  if (event.type.startsWith('tool.') && !('call_id' in event.data && 'execution_id' in event.data && 'stage' in event.data)) throw new Error('EVENT_SCHEMA_INVALID')
  return event
}
export async function replayV3Events(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void) {
  let cursor = afterSeq
  for (let page = 0; page < 100; page++) {
    const response = await getEvents(runId, cursor)
    for (const raw of response.events) onEvent(parseV3Event(raw))
    if (!response.has_more) return
    if (response.next_after_seq <= cursor) throw new Error('EVENT_CURSOR_INVALID')
    cursor = response.next_after_seq
  }
  throw new Error('EVENT_REPLAY_LIMIT')
}
export function openV3RunStream(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void, onError: (error?: unknown) => void, onReady: () => void) {
  const source = new EventSource(apiUrl(`/api/v3/runs/${encodeURIComponent(runId)}/events/stream?after_seq=${afterSeq}`))
  let closed = false
  const close = () => { closed = true; source.close() }
  for (const kind of kinds) source.addEventListener(kind, event => {
    if (closed) return
    try { onEvent(parseV3Event(JSON.parse((event as MessageEvent).data))) } catch (error) { close(); onError(error) }
  })
  source.onerror = () => { if (!closed) { close(); onError() } }
  void replayV3Events(runId, afterSeq, event => { if (!closed) onEvent(event) }).then(() => { if (!closed) onReady() }).catch(error => { if (!closed) { close(); onError(error) } })
  return { close }
}
