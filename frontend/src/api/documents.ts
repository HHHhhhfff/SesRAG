import { apiFetch } from './http'
import type { DocumentItem, DocumentListResponse, IndexResponse } from '../types/api'

export function listDocuments() {
  return apiFetch<DocumentListResponse>('/api/v1/documents')
}

export function uploadDocument(file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<DocumentItem>('/api/v1/documents', { method: 'POST', body })
}

export function reindexDocument(documentId: string) {
  return apiFetch<IndexResponse>(`/api/v1/documents/${documentId}/index`, {
    method: 'POST',
  })
}

