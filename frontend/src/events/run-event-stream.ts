import type { RunEvent } from '../types/api'
import { getEvents } from '../api/runs'

export async function replayEvents(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void) {
  const response = await getEvents(runId, afterSeq)
  for (const event of response.events) onEvent(event)
}

export function openRunStream(runId: string, afterSeq: number, onEvent: (event: RunEvent) => void) {
  const source = new EventSource(`/api/v1/runs/${runId}/events/stream?after_seq=${afterSeq}`, { withCredentials: false })
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
    source.addEventListener(eventType, (event) => onEvent(JSON.parse((event as MessageEvent).data) as RunEvent))
  }
  source.onerror = () => source.close()
  void replayEvents(runId, afterSeq, onEvent)
  return source
}
