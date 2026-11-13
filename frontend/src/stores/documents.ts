import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '../api/v3/rag'
import { ApiError, failureCode } from '../api/http'
import { useRagStore } from './rag'
import type { Document, ParseRequest, Chunk } from '../types/api-v3'

export const useDocumentStore = defineStore('documents', () => {
  const items = ref<Document[]>([]); const loading = ref(false); const error = ref(''); const paused = ref(false); const cursor = ref<string | null>(null)
  const chunks = ref<Chunk[]>([]); const chunkCursor = ref<string | null>(null); const inspected = ref<Document | null>(null)
  let epoch = 0; let attempts = 0; let timer: ReturnType<typeof setTimeout> | undefined
  let pending: { key: string; base: string; file: File; parse: ParseRequest; tags: string[] } | null = null
  const pendingUpload = ref(false)
  const rebuilding = ref<{ key: string; base: string; documentId: string; parse: ParseRequest; fingerprint: string } | null>(null)
  const pendingRebuild = computed(() => rebuilding.value !== null)
  const canRetryRebuild = computed(() => rebuilding.value?.base === useRagStore().selectedBase)
  let rebuildRequest: Promise<void> | null = null
  let inspectGeneration = 0
  let chunkRequest: { cursor: string; promise: Promise<void> } | null = null
  function resetInspection() { inspectGeneration++; inspected.value = null; chunks.value = []; chunkCursor.value = null; chunkRequest = null }
  function stop() { epoch++; clearTimeout(timer); timer = undefined; loading.value = false; resetInspection() }
  async function poll(expected: number) {
    const base = useRagStore().selectedBase
    if (!base) { items.value = []; return }
    try {
      const result = await api.listDocuments(base)
      if (expected !== epoch || base !== useRagStore().selectedBase) return
      items.value = result.items; cursor.value = result.next_cursor ?? null; error.value = ''
      if (!items.value.some(item => item.latest_build && ['queued', 'building', 'waiting'].includes(item.latest_build.state))) return
    } catch (cause) { if (expected !== epoch) return; error.value = `${failureCode(cause, 'DOCUMENT_REFRESH_FAILED')}：无法读取索引事实` }
    if (++attempts >= 60) { paused.value = true; return }
    timer = setTimeout(() => void poll(expected), 2000)
  }
  async function load() { stop(); attempts = 0; paused.value = false; await poll(epoch) }
  async function more() { if (!cursor.value) return; const expected = epoch; const result = await api.listDocuments(useRagStore().selectedBase, cursor.value); if (expected !== epoch) return; items.value.push(...result.items.filter(d => !items.value.some(i => i.document_id === d.document_id))); cursor.value = result.next_cursor ?? null }
  async function upload(file: File, parse: ParseRequest = {}, tags: string[] = []) {
    pending ??= { key: crypto.randomUUID(), base: useRagStore().selectedBase, file, parse, tags }
    await retryUpload()
  }
  async function retryUpload() {
    if (!pending) return
    const operation = pending; const expected = epoch; loading.value = true; error.value = ''
    try { await api.uploadDocument(operation.base, operation.file, operation.parse, operation.tags, operation.key); pending = null; pendingUpload.value = false; if (expected === epoch) await load() }
    catch (cause) {
      const rejected = cause instanceof ApiError && cause.status >= 400 && cause.status < 500
      if (rejected && pending === operation) { pending = null; pendingUpload.value = false }
      if (expected === epoch) {
        pendingUpload.value = !rejected
        error.value = `${failureCode(cause, 'DOCUMENT_UPLOAD_FAILED')}：${rejected ? '上传被拒绝，请修改输入后重新提交' : '上传未确认，重试会沿用原文件及幂等键'}`
      }
    }
    finally { loading.value = false }
  }
  async function operation(action: () => Promise<unknown>) { error.value = ''; const expected = epoch; try { await action(); if (expected === epoch) await load() } catch (cause) { if (expected === epoch) error.value = `${failureCode(cause, 'DOCUMENT_OPERATION_FAILED')}：文档操作失败` } }
  function rebuild(document: Document, parse: ParseRequest) {
    const base = useRagStore().selectedBase
    const fingerprint = JSON.stringify(Object.entries(parse).filter(([, value]) => value !== undefined).sort(([left], [right]) => left.localeCompare(right)))
    const previous = rebuilding.value
    if (previous && (previous.base !== base || previous.documentId !== document.document_id || previous.fingerprint !== fingerprint)) {
      error.value = 'DOCUMENT_REBUILD_PENDING：请先在原知识库重试并确认原重建，再提交其他操作'
      return Promise.resolve()
    }
    if (!base || document.knowledge_base_id !== base) {
      error.value = 'DOCUMENT_REBUILD_SCOPE_INVALID：请在文档所属知识库操作'
      return Promise.resolve()
    }
    // 至多保存一个未决重建；原参数与授权不随表单修改，未知响应不得换键。
    rebuilding.value ??= { key: crypto.randomUUID(), base, documentId: document.document_id, parse: { ...parse }, fingerprint }
    return retryRebuild()
  }
  function retryRebuild(): Promise<void> {
    const request = rebuilding.value
    if (!request) return Promise.resolve()
    if (request.base !== useRagStore().selectedBase) {
      error.value = 'DOCUMENT_REBUILD_PENDING：请切回原知识库重试原重建'
      return Promise.resolve()
    }
    if (rebuildRequest) return rebuildRequest
    const expected = epoch
    loading.value = true; error.value = ''
    rebuildRequest = (async () => {
      try {
        await api.rebuildDocument(request.documentId, { parse: request.parse }, request.key)
        rebuilding.value = null
        if (expected === epoch && request.base === useRagStore().selectedBase) await load()
      } catch (cause) {
        const rejected = cause instanceof ApiError && cause.status >= 400 && cause.status < 500
        if (rejected) rebuilding.value = null
        if (expected === epoch && request.base === useRagStore().selectedBase) {
          error.value = `${failureCode(cause, 'DOCUMENT_REBUILD_FAILED')}：${rejected ? '重建被拒绝，请修改输入后重新提交' : '重建未确认，重试会沿用原参数、授权及幂等键'}`
        }
      } finally { loading.value = false; rebuildRequest = null }
    })()
    return rebuildRequest
  }
  async function inspect(document: Document, more = false) {
    const base = useRagStore().selectedBase
    const documentId = document.document_id; const batch = document.active_index_batch_id
    const same = inspected.value?.document_id === documentId && inspected.value?.active_index_batch_id === batch
    if (more && (!same || !chunkCursor.value)) return
    if (!more) { resetInspection(); inspected.value = { ...document } }
    if (!batch) return
    const after = more ? chunkCursor.value! : undefined
    if (more && chunkRequest && chunkRequest.cursor === after) return chunkRequest.promise
    const expected = epoch
    const generation = inspectGeneration
    const current = () => expected === epoch && generation === inspectGeneration && base === useRagStore().selectedBase && inspected.value?.document_id === documentId && inspected.value?.active_index_batch_id === batch
    const request = { cursor: after ?? '', promise: Promise.resolve() }
    request.promise = (async () => {
      try {
        const result = await api.getChunks(documentId, batch, after)
        if (!current()) return
        // 重叠分页和重复页均按稳定身份合并，切换文档或批次后旧页不可追加。
        const unique = new Map((more ? chunks.value : []).map(chunk => [chunk.chunk_id, chunk]))
        for (const chunk of result.items) if (!unique.has(chunk.chunk_id)) unique.set(chunk.chunk_id, chunk)
        chunks.value = [...unique.values()]; chunkCursor.value = result.next_cursor ?? null; error.value = ''
      } catch (cause) { if (current()) error.value = `${failureCode(cause, 'CHUNK_READ_FAILED')}：无法读取切片` }
      finally { if (chunkRequest === request) chunkRequest = null }
    })()
    chunkRequest = request
    return request.promise
  }
  return { items, loading, error, paused, cursor, chunks, chunkCursor, inspected, pendingUpload, pendingRebuild, canRetryRebuild, load, more, upload, retryUpload, stop, inspect, rebuild, retryRebuild,
    cancel: (build: string) => operation(() => api.cancelBuild(build)), tags: (id: string, tags: string[]) => operation(() => api.patchTags(id, tags)) }
})
