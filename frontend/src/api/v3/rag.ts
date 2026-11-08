import { apiFetch } from '../http'
import type { BuildCreate, ChunkList, DiagnosticCreate, Document, DocumentList, EvidenceBundle, IndexBuild, KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseList, KnowledgeBasePatch, ParseRequest, RagProfileList, RetrievalExecution } from '../../types/api-v3'

const id = encodeURIComponent
const mutate = (body: unknown, key?: string): RequestInit => ({ method: 'POST', headers: key ? { 'Idempotency-Key': key } : {}, body: JSON.stringify(body) })
export function listBases(cursor?: string) { return apiFetch<KnowledgeBaseList>(`/api/v3/knowledge-bases?limit=200${cursor ? `&cursor=${id(cursor)}` : ''}`) }
export function createBase(body: KnowledgeBaseCreate, key: string) { return apiFetch<KnowledgeBase>('/api/v3/knowledge-bases', mutate(body, key)) }
export function patchBase(key: string, body: KnowledgeBasePatch) { return apiFetch<KnowledgeBase>(`/api/v3/knowledge-bases/${id(key)}`, { ...mutate(body), method: 'PATCH' }) }
export function listProfiles() { return apiFetch<RagProfileList>('/api/v3/rag/profiles') }
export function listDocuments(base: string, cursor?: string) { return apiFetch<DocumentList>(`/api/v3/documents?knowledge_base_id=${id(base)}&limit=200${cursor ? `&cursor=${id(cursor)}` : ''}`) }
export function uploadDocument(base: string, file: File, parse: ParseRequest, tags: string[], key: string) {
  const body = new FormData(); body.set('file', file); body.set('knowledge_base_id', base); body.set('parse', JSON.stringify(parse)); body.set('tags', JSON.stringify(tags))
  return apiFetch<Document>('/api/v3/documents', { method: 'POST', headers: { 'Idempotency-Key': key }, body })
}
export function rebuildDocument(key: string, body: BuildCreate, operationKey: string) { return apiFetch<IndexBuild>(`/api/v3/documents/${id(key)}/index-builds`, mutate(body, operationKey)) }
export function cancelBuild(key: string) { return apiFetch<IndexBuild>(`/api/v3/index-builds/${id(key)}/cancel`, { method: 'POST' }) }
export function patchTags(key: string, tags: string[]) { return apiFetch<Document>(`/api/v3/documents/${id(key)}`, { ...mutate({ tags }), method: 'PATCH' }) }
export function getChunks(key: string, batch: string, cursor?: string) { return apiFetch<ChunkList>(`/api/v3/documents/${id(key)}/chunks?index_batch_id=${id(batch)}${cursor ? `&cursor=${id(cursor)}` : ''}`) }
export function createDiagnostic(body: DiagnosticCreate, key: string) { return apiFetch<RetrievalExecution>('/api/v3/retrieval-executions', mutate(body, key)) }
export function getExecution(key: string) { return apiFetch<RetrievalExecution>(`/api/v3/retrieval-executions/${id(key)}`) }
export function cancelDiagnostic(key: string) { return apiFetch<RetrievalExecution>(`/api/v3/retrieval-executions/${id(key)}/cancel`, { method: 'POST' }) }
export function getBundle(key: string, offset = 0) { return apiFetch<EvidenceBundle>(`/api/v3/evidence-bundles/${id(key)}?offset=${offset}`) }
