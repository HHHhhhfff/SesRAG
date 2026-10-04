import { apiFetch } from './http'
import type { ThreadDetail, ThreadSummary } from '../types/api'

export function listThreads() {
  return apiFetch<ThreadSummary[]>('/api/v1/threads')
}

export function createThread(title: string) {
  return apiFetch<ThreadSummary>('/api/v1/threads', { method: 'POST', body: JSON.stringify({ title }) })
}

export function getThread(threadId: string) {
  return apiFetch<ThreadDetail>(`/api/v1/threads/${threadId}`)
}

export function sendMessage(threadId: string, content: string) {
  return apiFetch<{ message_id: string; run_id: string; task_id: string; status: string }>(
    `/api/v1/threads/${threadId}/messages`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({ content }),
    },
  )
}

