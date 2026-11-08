import { ref } from 'vue'
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
  function stop() { epoch++; clearTimeout(timer); timer = undefined; loading.value = false }
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
  async function load() { stop(); attempts = 0; paused.value = false; inspected.value = null; chunks.value = []; await poll(epoch) }
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
  async function inspect(document: Document, more = false) {
    if (!document.active_index_batch_id) return
    const expected = epoch
    try { const result = await api.getChunks(document.document_id, document.active_index_batch_id, more ? chunkCursor.value ?? undefined : undefined); if (expected !== epoch) return; inspected.value = document; chunks.value = more ? [...chunks.value, ...result.items] : result.items; chunkCursor.value = result.next_cursor ?? null }
    catch (cause) { if (expected === epoch) error.value = `${failureCode(cause, 'CHUNK_READ_FAILED')}：无法读取切片` }
  }
  return { items, loading, error, paused, cursor, chunks, chunkCursor, inspected, pendingUpload, load, more, upload, retryUpload, stop, inspect,
    rebuild: (document: Document, parse: ParseRequest) => { const key = crypto.randomUUID(); return operation(() => api.rebuildDocument(document.document_id, { parse }, key)) },
    cancel: (build: string) => operation(() => api.cancelBuild(build)), tags: (id: string, tags: string[]) => operation(() => api.patchTags(id, tags)) }
})
