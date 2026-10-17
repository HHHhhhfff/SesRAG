import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import WorkspacePage from '../../../frontend/src/pages/WorkspacePage.vue'
import RunTimeline from '../../../frontend/src/components/RunTimeline.vue'
import { useRunStore } from '../../../frontend/src/stores/run'
import { useThreadStore } from '../../../frontend/src/stores/thread'
import type { Message, RunDetail, RunEvent, ThreadDetail } from '../../../frontend/src/types/api'
import { useDocumentStore } from '../../../frontend/src/stores/documents'
import { componentChecks, componentTitle } from './fe-component-checks.mjs'

// FE_003/005/008/009/011/015：仅替换HTTP和SSE传输，挂载真实页面、组件、store、API client与事件回调。
// 这些精确时序证明前端投影；慢Provider/真实持久化竞态由分类报告独立记为未完整验收。
const timestamp = '2026-10-07T00:00:00Z'
type RecordedRequest = { path: string; method: string; body?: string }
let wrapper: VueWrapper | undefined
let requests: RecordedRequest[]
let threads: Map<string, ThreadDetail>
let runs: Map<string, RunDetail>
let events: Map<string, RunEvent[]>
let replayGate: { promise: Promise<void>; release: () => void } | undefined
let replayCalls = 0
let nextSubmission = 'A'
let readsAfterTerminal = 0
let documentRows: unknown[] = []
let healthBody: unknown
let healthStatus = 200
let threadGates: Map<string, ReturnType<typeof deferred>>

function deferred() {
  let release!: () => void
  const promise = new Promise<void>((resolve) => { release = resolve })
  return { promise, release }
}

function thread(label: string): ThreadDetail {
  return {
    thread: { thread_id: `thread-${label}`, owner_id: 'safe-test-owner', title: `独立会话${label}`, archived_at: null, created_at: timestamp, updated_at: timestamp },
    messages: [], runs: [],
  }
}

function run(label: string, status: RunDetail['status'] = 'running'): RunDetail {
  return {
    run_id: `run-${label}`, thread_id: `thread-${label}`, status, user_message_id: `user-${label}`, assistant_message_id: null,
    task: { task_id: `task-${label}`, kind: 'run', state: status, attempt: 1, generation: 1, worker_id: 'safe-worker', lease_expires_at: null, last_error_code: null }, last_error_code: null,
  }
}

function message(label: string, role: Message['role'], content: string): Message {
  return { message_id: `${role}-${label}`, thread_id: `thread-${label}`, seq: role === 'user' ? 1 : 2, role, source: role === 'user' ? 'user_input' : 'assistant_generation', created_at: timestamp, content, status: 'completed', run_id: `run-${label}`, citations: [] }
}

function event(label: string, seq: number, type: string, data: Record<string, unknown> = {}): RunEvent {
  return { schema_version: 1, event_id: `event-${label}-${seq}`, run_id: `run-${label}`, seq, type, occurred_at: timestamp, data }
}

class TransportEventSource {
  static instances: TransportEventSource[] = []
  listeners = new Map<string, ((event: MessageEvent) => void)[]>()
  onerror: (() => void) | null = null
  closed = false
  constructor(public url: string) { TransportEventSource.instances.push(this) }
  addEventListener(type: string, callback: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), callback])
  }
  close() { this.closed = true }
  emit(value: RunEvent) {
    if (this.closed) return
    for (const callback of this.listeners.get(value.type) ?? []) callback(new MessageEvent(value.type, { data: JSON.stringify(value) }))
  }
}

async function settle() { await flushPromises(); await nextTick(); await flushPromises() }
const checkName = (sub: string) => componentTitle(componentChecks.find((entry) => entry[2] === sub)!)

test(checkName('component-retry-history'), async () => {
  const current = run('A', 'succeeded')
  current.last_error_code = 'PROVIDER_HTTP_503'
  current.task.last_error_code = 'PROVIDER_HTTP_503'
  current.task.attempt = 2
  wrapper = mount(RunTimeline, { props: { run: current, events: [], connection: 'closed', error: '', failureCode: current.last_error_code } })
  expect(wrapper.find('.failure-summary').text()).toContain('上次尝试错误（已恢复）')
  expect(wrapper.find('.failure-summary').text()).not.toContain('执行失败')
  expect(wrapper.text()).toContain('PROVIDER_HTTP_503')
  await wrapper.setProps({ run: { ...current, status: 'retry_waiting' } })
  expect(wrapper.find('.failure-summary').text()).toContain('等待重试')
  await wrapper.setProps({ run: { ...current, status: 'failed' } })
  expect(wrapper.find('.failure-summary').text()).toContain('执行失败')
})

beforeEach(() => {
  requests = []; threads = new Map([['thread-A', thread('A')], ['thread-B', thread('B')]])
  runs = new Map([['run-A', run('A')], ['run-B', run('B')]])
  events = new Map([['run-A', []], ['run-B', []]])
  replayGate = undefined; replayCalls = 0; nextSubmission = 'A'; readsAfterTerminal = 0
  documentRows = []; healthStatus = 200
  healthBody = { status: 'ok', database: 'ready', redis: 'ready', worker: 'ready', worker_count: 1 }
  threadGates = new Map()
  TransportEventSource.instances = []
  vi.stubGlobal('EventSource', TransportEventSource)
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, 'http://localhost')
    const method = init?.method ?? 'GET'
    requests.push({ path: url.pathname + url.search, method, body: typeof init?.body === 'string' ? init.body : undefined })
    let body: unknown
    let status = 200
    if (url.pathname === '/api/v1/threads') body = [...threads.values()].map((detail) => detail.thread)
    else if (url.pathname === '/api/v1/documents') body = { documents: documentRows }
    else if (url.pathname === '/health/ready') { body = healthBody; status = healthStatus }
    else if (/\/threads\/[^/]+\/messages$/.test(url.pathname) && method === 'POST') {
      const label = nextSubmission
      const detail = threads.get(`thread-${label}`)!
      const content = JSON.parse(String(init?.body)).content
      if (!detail.messages.some((item) => item.role === 'user')) detail.messages.unshift(message(label, 'user', content))
      if (!detail.runs.length) detail.runs.push({ run_id: `run-${label}`, status: runs.get(`run-${label}`)!.status, created_at: timestamp })
      body = { message_id: `user-${label}`, run_id: `run-${label}`, task_id: `task-${label}`, status: runs.get(`run-${label}`)!.status }
      status = 201
    } else if (/\/threads\/[^/]+$/.test(url.pathname)) {
      await threadGates.get(url.pathname.split('/').at(-1)!)?.promise
      body = threads.get(url.pathname.split('/').at(-1)!)
      const current = body as ThreadDetail
      if (current?.runs.some((item) => ['succeeded', 'failed', 'cancelled'].includes(item.status))) readsAfterTerminal++
    } else if (/\/runs\/[^/]+\/cancel$/.test(url.pathname)) {
      const selected = runs.get(url.pathname.split('/').at(-2)!)!
      selected.status = 'cancelled'
      body = { run_id: selected.run_id, status: selected.status }
    } else if (/\/runs\/[^/]+\/events$/.test(url.pathname)) {
      replayCalls++
      // FE_008：observe的第一次补放完成，openRunStream的第二次补放停在传输屏障。
      if (replayGate && replayCalls === 2) await replayGate.promise
      const after = Number(url.searchParams.get('after_seq') ?? '0')
      body = { events: (events.get(url.pathname.split('/').at(-2)!) ?? []).filter((item) => item.seq > after) }
    } else if (/\/runs\/[^/]+$/.test(url.pathname)) body = runs.get(url.pathname.split('/').at(-1)!)
    else throw new Error(`FE传输驱动遇到未声明路径：${url.pathname}`)
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  }))
  setActivePinia(createPinia())
})

afterEach(() => {
  replayGate?.release()
  for (const gate of threadGates.values()) gate.release()
  wrapper?.unmount(); wrapper = undefined
  for (const source of TransportEventSource.instances) source.close()
  vi.unstubAllGlobals(); vi.useRealTimers(); setActivePinia(undefined)
})

async function boot() {
  wrapper = mount(WorkspacePage)
  await settle()
  expect(wrapper.find('textarea').attributes('disabled')).toBeUndefined()
  return wrapper
}

async function ask() {
  const page = await boot()
  await page.find('textarea').setValue('中文安全测试问题')
  await page.find('form').trigger('submit')
  await settle()
  expect(TransportEventSource.instances).toHaveLength(1)
  return { page, source: TransportEventSource.instances[0] }
}

// FE_003：无最终Message的首片到达，不能把空白或预存assistant当作流式回答。
test(checkName('component-partial-answer'), async () => {
  const { page, source } = await ask()
  expect(threads.get('thread-A')!.messages.filter((item) => item.role === 'assistant')).toHaveLength(0)
  source.emit(event('A', 1, 'answer.delta', { text: '首片可见' }))
  await settle()
  expect(useRunStore().events.map((item) => item.seq)).toEqual([1])
  expect(page.findAll('.message.assistant').map((item) => item.find('.message-content').text())).toEqual(['首片可见'])
  expect(threads.get('thread-A')!.messages.filter((item) => item.role === 'assistant')).toHaveLength(0)
  expect(page.find('.run-panel strong').text()).toBe('running')
})

// FE_004：terminal之前客户端只有user；terminal之后接口事实已有最终正文和引用。
test(checkName('component-terminal-refresh'), async () => {
  const { page, source } = await ask()
  const final = message('A', 'assistant', '安全最终回答')
  final.citations = [{ document_id: 'doc-A', chunk_id: 'chunk-A', filename: '安全证据.txt', start_offset: 0, end_offset: 8, score: 0.9 }]
  threads.get('thread-A')!.messages.push(final)
  threads.get('thread-A')!.runs[0].status = 'succeeded'
  runs.get('run-A')!.status = 'succeeded'
  runs.get('run-A')!.assistant_message_id = final.message_id
  source.emit(event('A', 1, 'message.completed', { message_id: final.message_id, citations: final.citations }))
  source.emit(event('A', 2, 'run.succeeded', { status: 'succeeded' }))
  await settle()
  expect(readsAfterTerminal, '终态到达后应重新读取服务器最终Message').toBeGreaterThan(0)
  expect(page.findAll('.message.assistant')).toHaveLength(1)
  expect(page.find('.message.assistant .message-content').text()).toBe(final.content)
  expect(page.find('.citation').text()).toBe('安全证据.txt · 0-8')
})

test(checkName('component-running'), async () => {
  runs.get('run-A')!.status = 'queued'
  const { page, source } = await ask()
  expect(page.find('.run-panel strong').text()).toBe('queued')
  runs.get('run-A')!.status = 'running'
  source.emit(event('A', 1, 'run.started', { status: 'running' }))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('running')
})

test(checkName('component-succeeded'), async () => {
  const { page, source } = await ask()
  runs.get('run-A')!.status = 'succeeded'
  source.emit(event('A', 1, 'run.succeeded', { status: 'succeeded' }))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('succeeded')
  expect(page.find('.run-panel button').exists()).toBe(false)
})

test(checkName('component-cancel'), async () => {
  const { page, source } = await ask()
  await page.find('.run-panel button').trigger('click')
  await settle()
  expect(requests.filter((item) => item.method === 'POST' && item.path.endsWith('/cancel')).map((item) => item.path)).toEqual(['/api/v1/runs/run-A/cancel'])
  source.emit(event('A', 1, 'run.cancelled', { status: 'cancelled' }))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('cancelled')
  expect(page.find('.run-panel button').exists()).toBe(false)
  source.emit(event('A', 2, 'run.succeeded', { status: 'succeeded' }))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('cancelled')
})

test(checkName('component-async-failure'), async () => {
  const { page, source } = await ask()
  runs.get('run-A')!.status = 'failed'; runs.get('run-A')!.last_error_code = 'PROVIDER_UNAVAILABLE'
  source.emit(event('A', 1, 'run.failed', { error_code: 'PROVIDER_UNAVAILABLE', status: 'failed' }))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('failed')
  expect(page.find('.detail-column').text()).toContain('PROVIDER_UNAVAILABLE')
})

test(checkName('component-failure-reason'), async () => {
  runs.get('run-A')!.status = 'failed'; runs.get('run-A')!.last_error_code = 'PROVIDER_UNAVAILABLE'
  const { page } = await ask()
  expect(page.find('.run-panel strong').text()).toBe('failed')
  expect(page.find('.detail-column').text()).toContain('PROVIDER_UNAVAILABLE')
})

test(checkName('component-seq-order'), async () => {
  const { page, source } = await ask()
  for (const seq of [3, 1, 2, 2]) source.emit(event('A', seq, 'task.queued'))
  await settle()
  expect(useRunStore().events.map((item) => item.seq)).toEqual([1, 2, 3])
  expect(page.findAll('.event-seq').map((item) => item.text())).toEqual(['1', '2', '3'])
})

test(checkName('component-run-scope'), async () => {
  const { source } = await ask()
  source.emit(event('A', 1, 'task.queued'))
  events.set('run-B', [event('B', 1, 'run.created')])
  await useRunStore().observe('run-B')
  await settle()
  expect(useRunStore().events.map((item) => [item.run_id, item.seq])).toEqual([['run-B', 1]])
  expect(wrapper!.findAll('.event-seq').map((item) => item.text())).toEqual(['1'])
})

test(checkName('component-replay-stream-overlap'), async () => {
  // FE_008：预存临时assistant使断言专注重复投影，不借FE_003空白错误蒙混通过。
  threads.get('thread-A')!.messages.push({ ...message('A', 'assistant', '已有首片'), status: 'generating' })
  replayGate = deferred()
  const { page, source } = await ask()
  const delta = event('A', 1, 'answer.delta', { text: '唯一片段' })
  events.set('run-A', [delta])
  source.emit(delta)
  replayGate.release()
  await settle()
  expect(useRunStore().events.filter((item) => item.seq === 1)).toHaveLength(1)
  expect(page.find('.message.assistant .message-content').text()).toBe('已有首片唯一片段')
})

test(checkName('component-final-history'), async () => {
  threads.get('thread-A')!.messages.push(message('A', 'assistant', '已持久最终正文'))
  runs.get('run-A')!.status = 'succeeded'
  replayGate = deferred()
  const { page } = await ask()
  // FE_008：第二次HTTP补放才返回历史增量，游标仍为0；不是注入小于请求游标的非法SSE。
  events.set('run-A', [event('A', 1, 'answer.delta', { text: '已持久最终正文' }), event('A', 2, 'run.succeeded')])
  replayGate.release()
  await settle()
  expect(useRunStore().events).toHaveLength(2)
  expect(page.find('.message.assistant .message-content').text()).toBe('已持久最终正文')
})

test(checkName('component-stream-after-replay'), async () => {
  threads.get('thread-A')!.messages.push({ ...message('A', 'assistant', '已有首片'), status: 'generating' })
  replayGate = deferred()
  const { page, source } = await ask()
  const delta = event('A', 1, 'answer.delta', { text: '唯一片段' })
  events.set('run-A', [delta])
  replayGate.release()
  await settle()
  source.emit(delta)
  await settle()
  expect(useRunStore().events.filter((item) => item.seq === 1)).toHaveLength(1)
  expect(page.find('.message.assistant .message-content').text()).toBe('已有首片唯一片段')
})

test(checkName('component-reconnect-cursor'), async () => {
  const { page, source } = await ask()
  source.emit(event('A', 1, 'task.queued'))
  source.emit(event('A', 2, 'answer.delta', { text: '片一' }))
  await settle()
  source.onerror?.()
  events.set('run-A', [event('A', 1, 'task.queued'), event('A', 2, 'answer.delta', { text: '片一' }), event('A', 3, 'answer.delta', { text: '片二' })])
  // 真实重连入口若存在，点击后仍使用生产stream逻辑；否则允许自动重连在有界窗口内触发。
  const reconnect = page.findAll('button').find((item) => /重新连接|重连/.test(item.text()))
  if (reconnect) await reconnect.trigger('click')
  await new Promise((resolve) => setTimeout(resolve, 1250))
  await settle()
  const resumed = TransportEventSource.instances.find((item) => item !== source && !item.closed)
  expect(resumed, 'SSE错误后应存在自动重连或可用的手动重连入口').toBeDefined()
  expect(new URL(resumed!.url, 'http://localhost').searchParams.get('after_seq')).toBe('2')
  resumed!.emit(event('A', 3, 'answer.delta', { text: '片二' }))
  await settle()
  expect(useRunStore().events.map((item) => item.seq)).toEqual([1, 2, 3])
  expect(requests.some((item) => item.path.endsWith('/cancel'))).toBe(false)
})

test(checkName('component-disconnect-no-cancel'), async () => {
  const { source } = await ask()
  source.onerror?.()
  await settle()
  expect(requests.filter((item) => item.path.endsWith('/cancel'))).toEqual([])
  expect(runs.get('run-A')!.status).toBe('running')
})

test(checkName('component-active-restore'), async () => {
  threads.get('thread-A')!.messages.push(message('A', 'user', '已提交活动问题'))
  threads.get('thread-A')!.runs.push({ run_id: 'run-A', status: 'running', created_at: timestamp })
  events.set('run-A', [event('A', 1, 'run.created'), event('A', 2, 'run.started')])
  const page = await boot()
  expect(useThreadStore().active!.messages).toHaveLength(1)
  expect(useRunStore().current?.run_id).toBe('run-A')
  expect(page.findAll('.event-seq').map((item) => item.text())).toEqual(['1', '2'])
  expect(TransportEventSource.instances.some((item) => item.url.includes('/run-A/'))).toBe(true)
  runs.get('run-A')!.status = 'succeeded'
  TransportEventSource.instances.at(-1)!.emit(event('A', 3, 'run.succeeded'))
  await settle()
  expect(page.find('.run-panel strong').text()).toBe('succeeded')
  expect(requests.some((item) => item.method === 'POST')).toBe(false)
})

test(checkName('component-switch-isolation'), async () => {
  threads.get('thread-B')!.messages.push(message('B', 'user', 'B独立历史'))
  const { page, source } = await ask()
  source.emit(event('A', 1, 'answer.delta', { text: 'A首片' }))
  await settle()
  await page.findAll('.thread-item')[1].trigger('click')
  await settle()
  expect(useThreadStore().active!.thread.thread_id).toBe('thread-B')
  // FE_015：先尝试迟到事件，再一起核对关闭/面板/正文，保留真实组件行为。
  source.emit(event('A', 2, 'answer.delta', { text: 'A迟到片' }))
  await settle()
  expect({ old_stream_closed: source.closed, run_in_b: useRunStore().current?.run_id ?? null, b_content: page.find('.message.user .message-content').text() }).toEqual({ old_stream_closed: true, run_in_b: null, b_content: 'B独立历史' })
  threads.get('thread-A')!.messages.push(message('A', 'assistant', 'A持久最终答案'))
  threads.get('thread-A')!.runs[0].status = 'succeeded'
  await page.findAll('.thread-item')[0].trigger('click')
  await settle()
  expect(page.find('.message.assistant .message-content').text()).toBe('A持久最终答案')
})

test(checkName('component-switch-back-history'), async () => {
  threads.get('thread-B')!.messages.push(message('B', 'user', 'B独立历史'))
  const { page, source } = await ask()
  source.emit(event('A', 1, 'answer.delta', { text: 'A首片' }))
  await settle()
  await page.findAll('.thread-item')[1].trigger('click')
  await settle()
  expect(useThreadStore().active!.thread.thread_id).toBe('thread-B')
  source.emit(event('A', 2, 'answer.delta', { text: 'A迟到片' }))
  threads.get('thread-A')!.messages.push(message('A', 'assistant', 'A持久最终答案'))
  threads.get('thread-A')!.runs[0].status = 'succeeded'
  await page.findAll('.thread-item')[0].trigger('click')
  await settle()
  expect(page.find('.message.assistant .message-content').text()).toBe('A持久最终答案')
  expect(page.findAll('.message.assistant')).toHaveLength(1)
})

// 删除健康读取/固定绿灯时失败：503依赖事实与网络失败必须可见。
test('健康503显示PG不可用、Redis降级和Worker未知', async () => {
  healthBody = { status: 'unavailable', database: 'unavailable', redis: 'degraded', worker: 'unknown', worker_count: 0, code: 'DATABASE_UNAVAILABLE' }
  healthStatus = 503
  const page = await boot()
  expect(page.find('.health-panel').text()).toContain('PG unavailable')
  expect(page.find('.health-panel').text()).toContain('Redis degraded')
  expect(page.find('.health-panel').text()).toContain('Worker unknown')
  expect(page.find('.connection-dot').classes()).not.toContain('online')
})

test('健康网络失败不固定绿灯', async () => {
  healthBody = undefined
  const fetcher = globalThis.fetch
  vi.stubGlobal('fetch', (input: string, init?: RequestInit) => input === '/health/ready' ? Promise.reject(new Error('network')) : fetcher(input, init))
  const page = await boot()
  expect(page.find('.connection-dot').classes()).not.toContain('online')
  expect(page.find('.health-panel').text()).toContain('API unknown')
})

// 删除Thread epoch检查时失败：A较慢HTTP不能覆盖已切换的B。
test('切Thread丢弃迟到详情HTTP', async () => {
  const page = await boot()
  const gate = deferred(); threadGates.set('thread-A', gate)
  const slow = useThreadStore().selectThread('thread-A')
  await page.findAll('.thread-item')[1].trigger('click'); await settle()
  gate.release(); await slow; await settle()
  expect(useThreadStore().active!.thread.thread_id).toBe('thread-B')
})

// 移除source回调epoch检查时失败：主动绕过close双重验证迟到callback隔离。
test('切Thread后已排队的旧SSE回调不污染新会话', async () => {
  const { page, source } = await ask()
  const callback = source.listeners.get('answer.delta')![0]
  await page.findAll('.thread-item')[1].trigger('click'); await settle()
  callback(new MessageEvent('answer.delta', { data: JSON.stringify(event('A', 1, 'answer.delta', { text: '旧回答' })) }))
  await settle()
  expect(useRunStore().events).toEqual([])
  expect(page.text()).not.toContain('旧回答')
})

// 取消DOMPurify或仅给鼠标span时失败：引用可键盘展开，正文XSS仍被清洗。
test('引用展开显示真实批次和基础位置且Markdown保持安全', async () => {
  const answer = message('A', 'assistant', '<img src=x onerror="alert(1)"><script>alert(1)</script>安全正文')
  answer.citations = [{ document_id: 'doc-A', chunk_id: 'chunk-A', index_batch_id: 'batch-A', filename: '证据.txt', start_offset: 4, end_offset: 9, score: 0.8, locations: [{ kind: 'line', number: 2, start_offset: 3, end_offset: 12 }] }]
  threads.get('thread-A')!.messages.push(answer)
  const page = await boot()
  const citation = page.find('button.citation')
  expect(citation.attributes('aria-expanded')).toBe('false')
  await citation.trigger('keydown', { key: 'Enter' })
  expect(citation.attributes('aria-expanded')).toBe('true')
  expect(page.find('.citation-detail').text()).toContain('doc-A')
  expect(page.find('.citation-detail').text()).toContain('chunk-A')
  expect(page.find('.citation-detail').text()).toContain('batch-A')
  expect(page.find('.citation-detail').text()).toContain('第 2 行')
  expect(page.find('.citation-detail').text()).toContain('4-9')
  expect(page.find('.message-content').html()).not.toMatch(/onerror|<script/)
  await citation.trigger('keydown', { key: ' ' })
  expect(citation.attributes('aria-expanded')).toBe('false')
})

// 去掉Document轮询/终态停止会失败；真实store读取通过HTTP边界驱动。
test('Document非终态刷新到失败展示错误并停止轮询', async () => {
  vi.useFakeTimers()
  documentRows = [{ document_id: 'doc-A', filename: '文档.txt', status: 'indexing', last_error_code: null }]
  const page = await boot()
  documentRows = [{ document_id: 'doc-A', filename: '文档.txt', status: 'failed', last_error_code: 'DOCUMENT_PARSE_FAILED' }]
  await vi.advanceTimersByTimeAsync(2000); await settle()
  expect(page.find('.document-panel').text()).toContain('DOCUMENT_PARSE_FAILED')
  const count = requests.filter((item) => item.path === '/api/v1/documents').length
  await vi.advanceTimersByTimeAsync(120000); await settle()
  expect(requests.filter((item) => item.path === '/api/v1/documents')).toHaveLength(count)
})

test('Document长期非终态自动刷新有上限并可手动恢复', async () => {
  vi.useFakeTimers()
  documentRows = [{ document_id: 'doc-A', filename: '文档.txt', status: 'indexing', last_error_code: null }]
  const page = await boot()
  await vi.advanceTimersByTimeAsync(180000); await settle()
  const count = requests.filter((item) => item.path === '/api/v1/documents').length
  expect(count).toBeGreaterThan(1)
  await vi.advanceTimersByTimeAsync(180000); await settle()
  expect(requests.filter((item) => item.path === '/api/v1/documents')).toHaveLength(count)
  const refresh = page.findAll('.document-panel button').find((item) => /刷新/.test(item.text()))!
  await refresh.trigger('click'); await settle()
  expect(requests.filter((item) => item.path === '/api/v1/documents').length).toBeGreaterThan(count)
})

// 事件payload伪造terminal不能直接改变Run事实或隐藏停止按钮。
test('terminal事件仅触发GET不本地宣布终态', async () => {
  const { page, source } = await ask()
  source.emit(event('A', 1, 'run.succeeded', { status: 'succeeded' })); await settle()
  expect(page.find('.run-panel strong').text()).toBe('running')
  expect(page.find('.run-panel button').text()).toContain('停止')
})

test('message.completed触发终态GET后补齐未送达的terminal Journal', async () => {
  const { source } = await ask()
  runs.get('run-A')!.status = 'succeeded'
  events.set('run-A', [event('A', 1, 'message.completed'), event('A', 2, 'run.succeeded')])
  source.emit(event('A', 1, 'message.completed')); await settle()
  expect(source.closed).toBe(true)
  expect(useRunStore().events.map(item => item.seq)).toEqual([1, 2])
})

test('乱序增量按seq投影且外来Run同seq不污染', async () => {
  const { page, source } = await ask()
  source.emit(event('A', 2, 'answer.delta', { text: '二' }))
  source.emit(event('B', 1, 'answer.delta', { text: '外来' }))
  source.emit(event('A', 1, 'answer.delta', { text: '一' })); await settle()
  expect(page.find('.message.assistant .message-content').text()).toBe('一二')
  expect(useRunStore().events.map(item => item.run_id)).toEqual(['run-A', 'run-A'])
})

test('连续断线自动重连有界且卸载清理timer和stream', async () => {
  vi.useFakeTimers()
  const { page, source } = await ask()
  source.onerror?.(); await vi.advanceTimersByTimeAsync(500); await settle()
  TransportEventSource.instances.at(-1)!.onerror?.(); await vi.advanceTimersByTimeAsync(1000); await settle()
  TransportEventSource.instances.at(-1)!.onerror?.(); await vi.advanceTimersByTimeAsync(2000); await settle()
  TransportEventSource.instances.at(-1)!.onerror?.(); await vi.advanceTimersByTimeAsync(60000); await settle()
  expect(TransportEventSource.instances).toHaveLength(4)
  expect(page.text()).toContain('重新连接')
  const reconnect = page.findAll('button').find(item => item.text() === '重新连接')!
  await reconnect.trigger('click'); await settle()
  const current = TransportEventSource.instances.at(-1)!
  page.unmount(); wrapper = undefined
  current.onerror?.(); await vi.advanceTimersByTimeAsync(60000)
  expect(current.closed).toBe(true)
  expect(TransportEventSource.instances).toHaveLength(5)
})

test('上传失败展示服务端稳定错误码且不回显路径', async () => {
  const fetcher = globalThis.fetch
  vi.stubGlobal('fetch', (input: string, init?: RequestInit) => input === '/api/v1/documents' && init?.method === 'POST'
    ? Promise.resolve(new Response(JSON.stringify({ code: 'DOCUMENT_TOO_LARGE', message: 'C:/secret/password' }), { status: 413 }))
    : fetcher(input, init))
  const page = await boot()
  const file = page.find('input[type=file]')
  Object.defineProperty(file.element, 'files', { value: [new File(['text'], '文档.txt')], configurable: true })
  await file.trigger('change'); await settle()
  expect(page.find('.document-panel').text()).toContain('DOCUMENT_TOO_LARGE')
  expect(page.text()).not.toContain('secret')
})

test('切Run丢弃旧GET返回且旧连接关闭', async () => {
  const { source } = await ask()
  const fetcher = globalThis.fetch
  const gate = deferred()
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    if (input === '/api/v1/runs/run-A') await gate.promise
    return fetcher(input, init)
  })
  const old = useRunStore().observe('run-A')
  await useRunStore().observe('run-B'); await settle()
  gate.release(); await old; await settle()
  expect(source.closed).toBe(true)
  expect(useRunStore().current?.run_id).toBe('run-B')
  expect(TransportEventSource.instances.filter(item => !item.closed).map(item => item.url)).toEqual(['/api/v1/runs/run-B/events/stream?after_seq=0'])
})

test('卸载使迟到健康Document HTTP失效并停止刷新', async () => {
  vi.useFakeTimers()
  const fetcher = globalThis.fetch
  const gate = deferred()
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    if (input === '/api/v1/documents' || input === '/health/ready') await gate.promise
    return fetcher(input, init)
  })
  wrapper = mount(WorkspacePage); await settle()
  wrapper.unmount(); wrapper = undefined
  documentRows = [{ document_id: 'late', filename: '迟到.txt', status: 'indexing', last_error_code: null }]
  gate.release(); await settle(); await vi.advanceTimersByTimeAsync(120000)
  expect(useDocumentStore().items).toEqual([])
  expect(requests.filter(item => item.path === '/api/v1/documents')).toHaveLength(1)
})

// I1：重试保留Journal，但当前草稿只含最新run.started之后的增量。
test('I1 实时重试不拼接不同attempt草稿', async () => {
  const { page, source } = await ask()
  source.emit(event('A', 1, 'run.started', { attempt: 1 }))
  source.emit(event('A', 2, 'answer.delta', { text: '旧草稿' }))
  await settle()
  expect(page.find('.message.assistant .message-content').text()).toBe('旧草稿')
  source.emit(event('A', 3, 'task.retry_scheduled', { attempt: 1 }))
  source.emit(event('A', 4, 'run.started', { attempt: 2 }))
  source.emit(event('A', 5, 'answer.delta', { text: '新答案' })); await settle()
  expect(page.find('.message.assistant .message-content').text()).toBe('新答案')
  expect(useRunStore().events.map(item => item.seq)).toEqual([1, 2, 3, 4, 5])
})

test('I1 刷新replay只投影最新attempt草稿并保留完整Journal', async () => {
  threads.get('thread-A')!.messages.push(message('A', 'user', '重试中的问题'))
  threads.get('thread-A')!.runs.push({ run_id: 'run-A', status: 'running', created_at: timestamp })
  events.set('run-A', [event('A', 1, 'run.started', { attempt: 1 }), event('A', 2, 'answer.delta', { text: '旧草稿' }), event('A', 3, 'task.retry_scheduled'), event('A', 4, 'run.started', { attempt: 2 }), event('A', 5, 'answer.delta', { text: '新答案' })])
  const page = await boot()
  expect(page.find('.message.assistant .message-content').text()).toBe('新答案')
  expect(useRunStore().events.map(item => item.seq)).toEqual([1, 2, 3, 4, 5])
})

// I2：旧取消POST晚于B终态GET开始返回，不能让B刷新version失效。
test('I2 旧cancel返回不能使新Run终态GET和最终Message失效', async () => {
  const { page, source } = await ask()
  const fetcher = globalThis.fetch
  const cancelGate = deferred(); const terminalGate = deferred()
  let holdTerminal = false
  let terminalReadStarted = false
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    if (input === '/api/v1/runs/run-A/cancel') await cancelGate.promise
    if (input === '/api/v1/runs/run-B' && holdTerminal) { terminalReadStarted = true; await terminalGate.promise }
    return fetcher(input, init)
  })
  const cancelling = useRunStore().cancel()
  threads.get('thread-B')!.messages.push(message('B', 'user', 'B问题'))
  threads.get('thread-B')!.runs.push({ run_id: 'run-B', status: 'running', created_at: timestamp })
  await page.findAll('.thread-item')[1].trigger('click'); await settle()
  expect(source.closed).toBe(true)
  const final = message('B', 'assistant', 'B最终答案')
  runs.get('run-B')!.status = 'succeeded'; runs.get('run-B')!.assistant_message_id = final.message_id
  threads.get('thread-B')!.messages.push(final); threads.get('thread-B')!.runs[0].status = 'succeeded'
  holdTerminal = true
  TransportEventSource.instances.at(-1)!.emit(event('B', 1, 'run.succeeded')); await settle()
  expect(terminalReadStarted).toBe(true)
  cancelGate.release(); await cancelling; await settle()
  terminalGate.release(); await settle()
  expect(page.find('.run-panel strong').text()).toBe('succeeded')
  expect(page.find('.run-panel button').exists()).toBe(false)
  expect(page.find('.message.assistant .message-content').text()).toBe('B最终答案')
})

// I3：同Thread允许并发创建Run；迟到A响应不得抢回已由B取得的观察权。
test('I3 同Thread连续提交A B反序响应保持B观察权和事实历史', async () => {
  const page = await boot()
  const fetcher = globalThis.fetch
  const firstGate = deferred()
  let submissions = 0
  runs.get('run-B')!.thread_id = 'thread-A'
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    if (input === '/api/v1/threads/thread-A/messages' && init?.method === 'POST') {
      const label = ++submissions === 1 ? 'A' : 'B'
      const detail = threads.get('thread-A')!
      const user = { ...message(label, 'user', JSON.parse(String(init.body)).content), thread_id: 'thread-A', seq: submissions }
      detail.messages.push(user)
      detail.runs.unshift({ run_id: `run-${label}`, status: 'running', created_at: timestamp })
      if (label === 'A') await firstGate.promise
      return new Response(JSON.stringify({ message_id: user.message_id, run_id: `run-${label}`, task_id: `task-${label}`, status: 'running' }), { status: 201 })
    }
    return fetcher(input, init)
  })
  await page.find('textarea').setValue('问题A'); await page.find('form').trigger('submit'); await settle()
  await page.find('textarea').setValue('问题B'); await page.find('form').trigger('submit'); await settle()
  expect(useRunStore().current?.run_id).toBe('run-B')
  const bSource = TransportEventSource.instances.at(-1)!
  firstGate.release(); await settle()
  expect(useRunStore().current?.run_id).toBe('run-B')
  expect(bSource.closed).toBe(false)
  expect(TransportEventSource.instances.filter(item => !item.closed).map(item => item.url)).toEqual(['/api/v1/runs/run-B/events/stream?after_seq=0'])
  expect(page.findAll('.message.user').map(item => item.find('.message-content').text())).toEqual(['问题A', '问题B'])
})
