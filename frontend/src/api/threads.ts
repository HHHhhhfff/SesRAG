import { apiFetch } from './http'
import type { MessageRunResponse, ThreadDetail, ThreadList, ThreadSummary } from '../types/api'

export function listThreads() {
  return apiFetch<ThreadList>('/api/v1/threads')
}

export function createThread(title: string) {
  return apiFetch<ThreadSummary>('/api/v1/threads', { method: 'POST', body: JSON.stringify({ title }) })
}

export function getThread(threadId: string) {
  return apiFetch<ThreadDetail>(`/api/v1/threads/${threadId}`)
}

export function sendMessage(threadId: string, content: string) {
  return apiFetch<MessageRunResponse>(
    `/api/v1/threads/${threadId}/messages`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({ content }),
    },
  )
}

