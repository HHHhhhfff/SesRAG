import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import DocumentUploader from '../src/components/DocumentUploader.vue'
import { useDocumentStore } from '../src/stores/documents'
import { useRagStore } from '../src/stores/rag'
import { ApiError } from '../src/api/http'
import * as api from '../src/api/v3/rag'
import type { Chunk, ChunkList, Document, IndexBuild, ParseRequest } from '../src/types/api-v3'

vi.mock('../src/api/v3/rag', () => ({ listDocuments: vi.fn(), rebuildDocument: vi.fn(), getChunks: vi.fn() }))

const documentRow: Document = {
  document_id: 'doc-a', knowledge_base_id: 'base-a', filename: 'a.txt', extension: '.txt',
  size_bytes: 1, content_hash: 'a'.repeat(64), tags: [], availability: 'ready',
  active_index_batch_id: 'batch-a', latest_build: null, created_at: '2026-11-12T00:00:00Z',
}
const build: IndexBuild = {
  index_batch_id: 'new-batch', document_id: 'doc-a', knowledge_base_id: 'base-a', state: 'queued',
  stage: 'queued', task_id: null, parse: null, chunk_count: 0, error_code: null,
  created_at: '2026-11-12T00:00:00Z',
}
const chunk = (id: string): Chunk => ({
  chunk_id: id, document_id: 'doc-a', index_batch_id: 'batch-a', seq: 1,
  text: id, start_offset: 0, end_offset: 1, locations: [],
})
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (cause: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  useRagStore().selectedBase = 'base-a'
  vi.mocked(api.listDocuments).mockResolvedValue({ items: [], next_cursor: null })
  vi.mocked(api.rebuildDocument).mockResolvedValue(build)
})

describe('RAG-DEF-006 未确认重建恢复', () => {
  it('网络未知后冻结原授权，参数属性顺序变化仍复用同一幂等键', async () => {
    vi.mocked(api.rebuildDocument).mockRejectedValueOnce(new TypeError('network'))
    const store = useDocumentStore()
    const parse: ParseRequest = { cloud_consent: true, consent_version: 'consent-v1' }
    await store.rebuild(documentRow, parse)
    parse.cloud_consent = false
    await store.rebuild(documentRow, { consent_version: 'consent-v1', cloud_consent: true })
    const calls = vi.mocked(api.rebuildDocument).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[1]).toEqual(['doc-a', { parse: { cloud_consent: true, consent_version: 'consent-v1' } }, calls[0]![2]])
    expect(calls[0]![1].parse?.cloud_consent).toBe(true)
    expect(store.error).toBe('')
  })

  it('不同文档、参数或知识库不得覆盖未决操作，切回后仍恢复原键', async () => {
    vi.mocked(api.rebuildDocument).mockRejectedValueOnce(new TypeError('network'))
    const store = useDocumentStore()
    await store.rebuild(documentRow, {})
    await store.rebuild(documentRow, { acknowledge_duplicate_cost: true })
    await store.rebuild({ ...documentRow, document_id: 'doc-b' }, {})
    useRagStore().selectedBase = 'base-b'
    await store.rebuild({ ...documentRow, knowledge_base_id: 'base-b' }, {})
    expect(api.rebuildDocument).toHaveBeenCalledTimes(1)
    expect(store.error).toContain('DOCUMENT_REBUILD_PENDING')
    useRagStore().selectedBase = 'base-a'
    await store.rebuild(documentRow, {})
    expect(api.rebuildDocument).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.rebuildDocument).mock.calls[1]![2]).toBe(vi.mocked(api.rebuildDocument).mock.calls[0]![2])
  })

  it('明确4xx拒绝后允许修正参数并创建新操作', async () => {
    vi.mocked(api.rebuildDocument).mockRejectedValueOnce(new ApiError('INVALID_RAG_PARAMETER', 422))
    const store = useDocumentStore()
    await store.rebuild(documentRow, {})
    await store.rebuild(documentRow, { acknowledge_duplicate_cost: true })
    const calls = vi.mocked(api.rebuildDocument).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[1]![2]).not.toBe(calls[0]![2])
  })

  it('同一未决操作并发提交只发送一次，迟到确认不刷新别的知识库', async () => {
    const response = deferred<IndexBuild>()
    vi.mocked(api.rebuildDocument).mockReturnValue(response.promise)
    const store = useDocumentStore()
    const first = store.rebuild(documentRow, {})
    const second = store.rebuild(documentRow, {})
    expect(api.rebuildDocument).toHaveBeenCalledTimes(1)
    useRagStore().selectedBase = 'base-b'
    response.resolve(build)
    await Promise.all([first, second])
    expect(api.listDocuments).not.toHaveBeenCalled()
  })

  it('界面可重试原重建，跨库时禁止重放', async () => {
    vi.mocked(api.rebuildDocument).mockRejectedValueOnce(new TypeError('network'))
    const store = useDocumentStore()
    const wrapper = mount(DocumentUploader)
    await store.rebuild(documentRow, {})
    await flushPromises()
    const retry = wrapper.findAll('button').find(button => button.text() === '重试原重建（同一幂等键）')
    expect(retry).toBeDefined()
    useRagStore().selectedBase = 'base-b'
    await flushPromises()
    expect(retry!.attributes('disabled')).toBeDefined()
    await retry!.trigger('click')
    expect(api.rebuildDocument).toHaveBeenCalledTimes(1)
    useRagStore().selectedBase = 'base-a'
    await flushPromises()
    await retry!.trigger('click')
    await flushPromises()
    expect(api.rebuildDocument).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('重试原重建（同一幂等键）')
    wrapper.unmount()
  })
})

describe('RAG-DEF-007 已发布切片分页', () => {
  it('同游标并发只发一次请求，页面重叠按chunk身份去重且末页停止', async () => {
    const page = deferred<ChunkList>()
    vi.mocked(api.getChunks).mockResolvedValueOnce({ items: [chunk('one'), chunk('one')], next_cursor: 'page2' }).mockReturnValueOnce(page.promise)
    const store = useDocumentStore()
    await store.inspect(documentRow)
    const first = store.inspect(documentRow, true)
    const second = store.inspect(documentRow, true)
    expect(api.getChunks).toHaveBeenCalledTimes(2)
    page.resolve({ items: [chunk('one'), chunk('two'), chunk('two')], next_cursor: null })
    await Promise.all([first, second])
    expect(store.chunks.map(row => row.chunk_id)).toEqual(['one', 'two'])
    await store.inspect(documentRow, true)
    expect(api.getChunks).toHaveBeenCalledTimes(2)
  })

  it.each(['document', 'batch', 'refresh'] as const)('%s切换后的迟到初页不能覆盖当前身份', async kind => {
    const old = deferred<ChunkList>()
    vi.mocked(api.getChunks).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ items: [chunk('current')], next_cursor: 'current-page' })
    const store = useDocumentStore()
    const first = store.inspect(documentRow)
    const current = { ...documentRow, ...(kind === 'document' ? { document_id: 'doc-b' } : kind === 'batch' ? { active_index_batch_id: 'batch-b' } : {}) }
    await store.inspect(current)
    old.resolve({ items: [chunk('late')], next_cursor: 'old-page' })
    await first
    expect(store.inspected?.document_id).toBe(current.document_id)
    expect(store.inspected?.active_index_batch_id).toBe(current.active_index_batch_id)
    expect(store.chunks.map(row => row.chunk_id)).toEqual(['current'])
    expect(store.chunkCursor).toBe('current-page')
  })

  it('切换文档后迟到分页错误和结果不污染新文档', async () => {
    const old = deferred<ChunkList>()
    vi.mocked(api.getChunks).mockResolvedValueOnce({ items: [chunk('one')], next_cursor: 'page2' }).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ items: [chunk('new')], next_cursor: null })
    const store = useDocumentStore()
    await store.inspect(documentRow)
    const first = store.inspect(documentRow, true)
    await store.inspect({ ...documentRow, document_id: 'doc-b' })
    old.reject(new ApiError('CHUNK_READ_FAILED', 503))
    await first
    expect(store.error).toBe('')
    expect(store.chunks.map(row => row.chunk_id)).toEqual(['new'])
    expect(store.chunkCursor).toBeNull()
  })

  it('切换知识库后丢弃旧切片响应，load清空游标', async () => {
    const old = deferred<ChunkList>()
    vi.mocked(api.getChunks).mockReturnValue(old.promise)
    const store = useDocumentStore()
    const first = store.inspect(documentRow)
    useRagStore().selectedBase = 'base-b'
    await store.load()
    old.resolve({ items: [chunk('late')], next_cursor: 'old-page' })
    await first
    expect(store.inspected).toBeNull()
    expect(store.chunks).toEqual([])
    expect(store.chunkCursor).toBeNull()
  })
})
