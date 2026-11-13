import type { RunEvent } from '../types/api-v3'
import { getEvents } from '../api/v3/sessions'
import { apiUrl } from '../api/http'
import validateRunEvent, { eventKinds } from './generated/run-event-validator.js'

export function parseV3Event(value: unknown): RunEvent {
  // HTTP补放与SSE共享正式Schema生成的运行时边界，不回显不可信载荷。
  if (!validateRunEvent(value)) throw new Error('EVENT_SCHEMA_INVALID')
  return value
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
  for (const kind of eventKinds) source.addEventListener(kind, event => {
    if (closed) return
    try { onEvent(parseV3Event(JSON.parse((event as MessageEvent).data))) } catch (error) { close(); onError(error) }
  })
  source.onerror = () => { if (!closed) { close(); onError() } }
  void replayV3Events(runId, afterSeq, event => { if (!closed) onEvent(event) }).then(() => { if (!closed) onReady() }).catch(error => { if (!closed) { close(); onError(error) } })
  return { close }
}
