import { apiFetch } from '../http'
import type { ContextResponse, EventListResponse, MessageRunResponse, RunDetail, RunEvent, RunOperationCreate } from '../../types/api-v2'
import { createIdempotencyKey } from './threads'

const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined) search.set(key, String(value))
  return search.toString() ? `?${search}` : ''
}
export function getRun(runId: string) { return apiFetch<RunDetail>(`/api/v2/runs/${encodeURIComponent(runId)}`) }
export function getEvents(runId: string, afterSeq = 0, limit = 200) { return apiFetch<EventListResponse>(`/api/v2/runs/${encodeURIComponent(runId)}/events${query({ after_seq: afterSeq, limit })}`) }
export function cancelRun(runId: string) { return apiFetch<{ run_id: string; status: RunDetail['status'] }>(`/api/v2/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' }) }
export function retryRun(runId: string, payload: RunOperationCreate = {}, idempotencyKey: string = createIdempotencyKey()) { return apiFetch<MessageRunResponse>(`/api/v2/runs/${encodeURIComponent(runId)}/retry`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) }) }
export function regenerateRun(runId: string, payload: RunOperationCreate = {}, idempotencyKey: string = createIdempotencyKey()) { return apiFetch<MessageRunResponse>(`/api/v2/runs/${encodeURIComponent(runId)}/regenerate`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) }) }
export function getContext(runId: string, generation?: number) { return apiFetch<ContextResponse>(`/api/v2/runs/${encodeURIComponent(runId)}/context${query({ generation })}`) }
export type V2EventHandler = (event: RunEvent) => void
