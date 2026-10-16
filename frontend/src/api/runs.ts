import { apiFetch } from './http'
import type { CancelResponse, EventListResponse, RunDetail } from '../types/api'

export function getRun(runId: string) {
  return apiFetch<RunDetail>(`/api/v1/runs/${runId}`)
}

export function getEvents(runId: string, afterSeq = 0) {
  return apiFetch<EventListResponse>(`/api/v1/runs/${runId}/events?after_seq=${afterSeq}`)
}

export function cancelRun(runId: string) {
  return apiFetch<CancelResponse>(`/api/v1/runs/${runId}/cancel`, { method: 'POST' })
}

