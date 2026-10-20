import { apiFetch } from '../http'
import type { Branch, BranchCreate, MessageCreate, MessageRunResponse, ThreadDetail, ThreadList, ThreadListQuery, ThreadPatch, ThreadSummary } from '../../types/api-v2'

export const createIdempotencyKey = () => crypto.randomUUID()

const query = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== undefined) search.set(key, String(value))
  return search.toString() ? `?${search}` : ''
}

export function listThreads(params: ThreadListQuery = {}) {
  return apiFetch<ThreadList>(`/api/v2/threads${query(params)}`)
}
export function createThread(title = '新会话') {
  return apiFetch<ThreadSummary>('/api/v2/threads', { method: 'POST', body: JSON.stringify({ title }) })
}
export function getThread(threadId: string, params: { branch_id?: string; before_seq?: number; limit?: number } = {}) {
  return apiFetch<ThreadDetail>(`/api/v2/threads/${encodeURIComponent(threadId)}${query(params)}`)
}
export function patchThread(threadId: string, payload: ThreadPatch) {
  return apiFetch<ThreadSummary>(`/api/v2/threads/${encodeURIComponent(threadId)}`, { method: 'PATCH', body: JSON.stringify(payload) })
}
export function listBranches(threadId: string) {
  return apiFetch<{ branches: Branch[] }>(`/api/v2/threads/${encodeURIComponent(threadId)}/branches`)
}
export function createBranch(threadId: string, payload: BranchCreate, idempotencyKey: string = createIdempotencyKey()) {
  return apiFetch<Branch>(`/api/v2/threads/${encodeURIComponent(threadId)}/branches`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) })
}
export function sendMessage(threadId: string, payload: MessageCreate, idempotencyKey: string = createIdempotencyKey()) {
  return apiFetch<MessageRunResponse>(`/api/v2/threads/${encodeURIComponent(threadId)}/messages`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) })
}
