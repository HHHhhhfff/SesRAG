import type { RunEvent } from '../types/api'
import { getEvents } from '../api/runs'
import { apiUrl } from '../api/http'

export async function replayEvents(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void) {
  const response = await getEvents(runId, afterSeq)
  for (const event of response.events) onEvent(event)
}

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
      try { onEvent(JSON.parse((event as MessageEvent).data) as RunEvent) }
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
