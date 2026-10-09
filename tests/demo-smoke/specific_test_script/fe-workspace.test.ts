import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import WorkspacePage from '../../../frontend/src/pages/WorkspacePage.vue'
import { useRunStore } from '../../../frontend/src/stores/run'
import { useThreadStore } from '../../../frontend/src/stores/thread'
import type { Message, RunDetail, RunEvent, ThreadDetail } from '../../../frontend/src/types/api'
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
    task: { task_id: `task-${label}`, state: status, attempt: 1, generation: 1, worker_id: 'safe-worker' }, last_error_code: null,
  }
}

function message(label: string, role: Message['role'], content: string): Message {
  return { message_id: `${role}-${label}`, thread_id: `thread-${label}`, seq: role === 'user' ? 1 : 2, role, content, status: 'completed', run_id: `run-${label}`, citations: [] }
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

beforeEach(() => {
  requests = []; threads = new Map([['thread-A', thread('A')], ['thread-B', thread('B')]])
  runs = new Map([['run-A', run('A')], ['run-B', run('B')]])
  events = new Map([['run-A', []], ['run-B', []]])
  replayGate = undefined; replayCalls = 0; nextSubmission = 'A'; readsAfterTerminal = 0
  TransportEventSource.instances = []
  vi.stubGlobal('EventSource', TransportEventSource)
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, 'http://localhost')
    const method = init?.method ?? 'GET'
    requests.push({ path: url.pathname + url.search, method, body: typeof init?.body === 'string' ? init.body : undefined })
    let body: unknown
    let status = 200
    if (url.pathname === '/api/v1/threads') body = [...threads.values()].map((detail) => detail.thread)
    else if (url.pathname === '/api/v1/documents') body = { documents: [] }
    else if (/\/threads\/[^/]+\/messages$/.test(url.pathname) && method === 'POST') {
      const label = nextSubmission
      const detail = threads.get(`thread-${label}`)!
      const content = JSON.parse(String(init?.body)).content
      if (!detail.messages.some((item) => item.role === 'user')) detail.messages.unshift(message(label, 'user', content))
      if (!detail.runs.length) detail.runs.push({ run_id: `run-${label}`, status: runs.get(`run-${label}`)!.status, created_at: timestamp })
      body = { message_id: `user-${label}`, run_id: `run-${label}`, task_id: `task-${label}`, status: runs.get(`run-${label}`)!.status }
      status = 201
    } else if (/\/threads\/[^/]+$/.test(url.pathname)) {
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
