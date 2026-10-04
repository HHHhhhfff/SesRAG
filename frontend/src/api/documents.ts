import { apiFetch } from './http'
import type { DocumentItem } from '../types/api'

export function listDocuments() {
  return apiFetch<{ documents: DocumentItem[] }>('/api/v1/documents')
}

export function uploadDocument(file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<DocumentItem>('/api/v1/documents', { method: 'POST', body })
}

export function reindexDocument(documentId: string) {
  return apiFetch<{ task_id: string; document_id: string; state: string }>(`/api/v1/documents/${documentId}/index`, {
    method: 'POST',
  })
}

