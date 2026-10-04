import { apiFetch } from './http'
import type { RunDetail, RunEvent } from '../types/api'

export function getRun(runId: string) {
  return apiFetch<RunDetail>(`/api/v1/runs/${runId}`)
}

export function getEvents(runId: string, afterSeq = 0) {
  return apiFetch<{ events: RunEvent[] }>(`/api/v1/runs/${runId}/events?after_seq=${afterSeq}`)
}

export function cancelRun(runId: string) {
  return apiFetch<{ run_id: string; status: string }>(`/api/v1/runs/${runId}/cancel`, { method: 'POST' })
}

