import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createThread, getThread, listBranches, listThreads, patchThread } from '../src/api/v2/threads'
import { useThreadStore } from '../src/stores/thread'
import ThreadList from '../src/components/ThreadList.vue'
import WorkspacePage from '../src/pages/WorkspacePage.vue'
import type { ThreadDetail, ThreadList as ThreadPage, ThreadSummary } from '../src/types/api-v2'

vi.mock('../src/api/v2/threads', () => ({
  createThread: vi.fn(), getThread: vi.fn(), listBranches: vi.fn(), listThreads: vi.fn(),
  patchThread: vi.fn(), createBranch: vi.fn(), createIdempotencyKey: vi.fn(), sendMessage: vi.fn(),
}))
vi.mock('../src/api/health', () => ({ getHealth: vi.fn().mockResolvedValue({ status: 'ok' }) }))
vi.mock('../src/stores/model', () => ({ useModelStore: () => ({ models: [], selected: null, load: async () => {}, select: vi.fn() }) }))
vi.mock('../src/stores/documents', () => ({ useDocumentStore: () => ({ items: [], loading: false, error: '', paused: false, load: async () => {}, stop: vi.fn() }) }))
vi.mock('../src/stores/run', () => ({ useRunStore: () => ({ current: null, messages: [], events: [], connection: 'closed', error: '', failureCode: '', reset: vi.fn() }) }))

const stamp = '2026-10-24T00:00:00Z'
function summary(id: string, archived = false): ThreadSummary {
  return { thread_id: id, title: id, owner_id: 'local-user', default_branch_id: `${id}-b`, conversation_version: 2, archived_at: archived ? stamp : null, created_at: stamp, updated_at: stamp }
}
function detail(thread: ThreadSummary): ThreadDetail {
  const branch = { branch_id: thread.default_branch_id, thread_id: thread.thread_id, parent_branch_id: null, fork_message_id: null, name: '主分支', is_default: true, head_message_id: null, version: 0, created_at: stamp, updated_at: stamp }
  return { thread, branch, branch_path: [branch], messages: [], runs: [], active_run_id: null, recent_run_id: null, next_before_seq: null, has_more: false }
}
const page = (threads: ThreadSummary[], next_cursor: string | null = null): ThreadPage => ({ threads, next_cursor, has_more: next_cursor !== null })

beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); setActivePinia(createPinia())
  vi.mocked(getThread).mockImplementation(async id => detail(summary(id, id.startsWith('archived'))))
  vi.mocked(listBranches).mockImplementation(async id => ({ branches: [detail(summary(id)).branch] }))
})

// WS-DEF-001 / UI_015～018：经真实store动作验证视图、游标和身份恢复，HTTP仅替换传输。
describe('普通与归档会话视图', () => {
  it('无偏好时默认普通视图，普通与归档集合互不混排', async () => {
    vi.mocked(listThreads).mockResolvedValue(page([summary('archived-a', true), summary('normal')]))
    const store = useThreadStore(); await store.loadThreads()
    expect(store.listView).toBe('active'); expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['normal'])
    await store.setListView('archived')
    expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['archived-a']); expect(store.selectedId).toBe('archived-a')
  })
  it('归档和取消归档切到目标视图，保持当前会话及分支身份', async () => {
    vi.mocked(listThreads).mockResolvedValue(page([summary('normal')]))
    const store = useThreadStore(); await store.loadThreads(); const branch = store.selectedBranchId
    vi.mocked(patchThread).mockResolvedValue(summary('normal', true)); await store.setArchived(true)
    expect(store.listView).toBe('archived'); expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['normal'])
    expect(store.active?.thread.archived_at).toBe(stamp); expect(store.selectedBranchId).toBe(branch)
    vi.mocked(patchThread).mockResolvedValue(summary('normal')); await store.setArchived(false)
    expect(store.listView).toBe('active'); expect(store.active?.thread.archived_at).toBeNull(); expect(store.selectedBranchId).toBe(branch)
  })
  it('有效归档偏好在首屏以外仍恢复到归档视图', async () => {
    localStorage.setItem('sesrag.selectedThreadId', 'archived-saved')
    vi.mocked(listThreads).mockResolvedValue(page([summary('normal')], 'next'))
    const store = useThreadStore(); await store.loadThreads()
    expect(store.listView).toBe('archived'); expect(store.active?.thread.thread_id).toBe('archived-saved')
    expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['archived-saved']); expect(store.nextCursor).toBe('next')
  })
  it('空归档视图清空活动详情，新建会话回普通视图', async () => {
    vi.mocked(listThreads).mockResolvedValue(page([summary('normal')]))
    const store = useThreadStore(); await store.loadThreads(); await store.setListView('archived')
    expect(store.active).toBeNull(); expect(store.selectedId).toBeNull()
    expect(localStorage.getItem('sesrag.selectedThreadId')).toBeNull()
    vi.mocked(createThread).mockResolvedValue(summary('new')); await store.addThread()
    expect(store.listView).toBe('active'); expect(store.selectedId).toBe('new')
  })
  it('共享游标分页按当前视图过滤并按身份去重', async () => {
    vi.mocked(listThreads).mockResolvedValueOnce(page([summary('normal')], 'p2')).mockResolvedValueOnce(page([summary('normal'), summary('archived-b', true)]))
    const store = useThreadStore(); await store.loadThreads(); await store.setListView('archived'); await store.loadMoreThreads()
    expect(vi.mocked(listThreads).mock.calls[1]?.[0]).toEqual({ limit: 100, cursor: 'p2', include_archived: true })
    expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['archived-b']); expect(store.active?.thread.thread_id).toBe('archived-b')
    await store.setListView('active'); expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['normal']); expect(store.hasMore).toBe(false)
  })
  it('切换视图丢弃迟到分页，不覆盖新视图游标，重新加载可成功', async () => {
    let resolvePage!: (value: ThreadPage) => void
    vi.mocked(listThreads).mockResolvedValueOnce(page([summary('normal')], 'p2')).mockImplementationOnce(() => new Promise(resolve => { resolvePage = resolve }))
    const store = useThreadStore(); await store.loadThreads(); const pending = store.loadMoreThreads(); await store.setListView('archived')
    resolvePage(page([summary('archived-late', true)])); await pending
    expect(store.nextCursor).toBe('p2'); expect(store.visibleThreads).toEqual([])
    vi.mocked(listThreads).mockResolvedValue(page([summary('archived-current', true)])); await store.loadMoreThreads()
    expect(store.visibleThreads.map(t => t.thread_id)).toEqual(['archived-current'])
  })
  it('侧栏提供可访问的双视图与精确空页提示', async () => {
    const wrapper = mount(ThreadList, { props: { threads: [], view: 'archived', hasMore: true } })
    try {
      expect(wrapper.get('button[aria-pressed="true"]').text()).toBe('已归档')
      await wrapper.get('button[aria-pressed="false"]').trigger('click'); expect(wrapper.emitted('view')).toEqual([['active']])
      expect(wrapper.text()).toContain('已加载会话中暂无归档项，可加载更多')
    } finally { wrapper.unmount() }
  })
  it('切视图后的当前详情失败必须显示错误，恢复后可继续选择', async () => {
    vi.mocked(listThreads).mockResolvedValue(page([summary('normal'), summary('archived-a', true)]))
    const wrapper = mount(WorkspacePage, { global: { stubs: { RunTimeline: true, MessageTimeline: true, DocumentUploader: true, BranchSelector: true, ModelSelector: true } } })
    try {
      await flushPromises()
      vi.mocked(getThread).mockRejectedValueOnce(new Error('synthetic-read-failure'))
      const archived = wrapper.findAll('.thread-views button')[1]!
      await archived.trigger('click'); await flushPromises()
      expect(wrapper.get('.error-banner').text()).toContain('THREAD_READ_FAILED')
      expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
      await wrapper.findAll('.thread-views button')[0]!.trigger('click'); await flushPromises()
      expect(wrapper.find('.error-banner').exists()).toBe(false)
      expect(wrapper.get('.topbar h2').text()).toBe('normal')
    } finally { wrapper.unmount() }
  })
})
