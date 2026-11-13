import { apiFetch } from '../http'
import type { ContextResponse, EventList, MessageCreate, MessageRunResponse, RunDetail, RunOperationCreate, ThreadDetail } from '../../types/api-v3'
import { createIdempotencyKey, getThread as readThread } from '../v2/threads'

const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined) search.set(key, String(value))
  return search.size ? `?${search}` : ''
}
const runPath = (id: string) => `/api/v3/runs/${encodeURIComponent(id)}`
export function getThread(id: string, params: { branch_id?: string; before_seq?: number; limit?: number } = {}): Promise<ThreadDetail> { return readThread(id, params, 3) }
export function sendMessage(id: string, body: MessageCreate, key: string = createIdempotencyKey()) { return apiFetch<MessageRunResponse>(`/api/v3/threads/${encodeURIComponent(id)}/messages`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(body) }) }
export function getRun(id: string) { return apiFetch<RunDetail>(runPath(id)) }
export function getContext(id: string, generation?: number) { return apiFetch<ContextResponse>(`${runPath(id)}/context${query({ generation })}`) }
export function getEvents(id: string, after_seq = 0) { return apiFetch<EventList>(`${runPath(id)}/events${query({ after_seq, limit: 200 })}`) }
export function cancelRun(id: string) { return apiFetch<{ run_id: string; status: RunDetail['status'] }>(`${runPath(id)}/cancel`, { method: 'POST' }) }
export function retryRun(id: string, body: RunOperationCreate = {}, key: string = createIdempotencyKey()) { return related(id, 'retry', body, key) }
export function regenerateRun(id: string, body: RunOperationCreate = {}, key: string = createIdempotencyKey()) { return related(id, 'regenerate', body, key) }
function related(id: string, kind: string, body: RunOperationCreate, key: string) { return apiFetch<MessageRunResponse>(`${runPath(id)}/${kind}`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(body) }) }
