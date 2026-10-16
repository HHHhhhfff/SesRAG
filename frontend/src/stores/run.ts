import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { cancelRun, getRun } from '../api/runs'
import { failureCode as requestFailureCode, safeErrorCode } from '../api/http'
import { openRunStream, replayEvents } from '../events/run-event-stream'
import { useThreadStore } from './thread'
import type { Message, RunDetail, RunEvent } from '../types/api'

const terminal = (status: string) => ['succeeded', 'failed', 'cancelled'].includes(status)

export const useRunStore = defineStore('run', () => {
  const current = ref<RunDetail | null>(null)
  const events = ref<RunEvent[]>([])
  const connected = ref(false)
  const connection = ref('idle')
  const error = ref('')
  let epoch = 0
  let activeRunId: string | null = null
  let stream: ReturnType<typeof openRunStream> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | undefined
  let retries = 0
  let refreshVersion = 0

  const messages = computed<Message[]>(() => {
    const detail = useThreadStore().active
    if (!detail) return []
    if (!current.value || current.value.thread_id !== detail.thread.thread_id) return detail.messages
    const runId = current.value.run_id
    // 每次执行从空正文开始；完整Journal保留，草稿只投影最新执行边界之后的片段。
    const startSeq = events.value.filter(item => item.type === 'run.started').at(-1)?.seq ?? 0
    const delta = events.value.filter(item => item.seq > startSeq && item.type === 'answer.delta' && typeof item.data.text === 'string').map(item => item.data.text).join('')
    const assistant = detail.messages.find(item => item.run_id === runId && item.role === 'assistant')
    // 完成Message是事实，历史delta不可追加到其正文。临时投影不写入Thread事实。
    if (assistant?.status === 'completed') return detail.messages
    if (!delta) return startSeq && assistant ? detail.messages.filter(item => item !== assistant) : detail.messages
    if (assistant) return detail.messages.map(item => item === assistant ? { ...item, content: (startSeq ? '' : item.content) + delta } : item)
    return [...detail.messages, {
      message_id: `projection-${runId}`, thread_id: detail.thread.thread_id,
      seq: (detail.messages.at(-1)?.seq ?? 0) + 1, role: 'assistant', source: 'assistant_generation',
      created_at: events.value[0]?.occurred_at ?? '', content: delta, status: 'generating', run_id: runId, citations: [],
    }]
  })

  function stopTransport() {
    stream?.close(); stream = null
    clearTimeout(retryTimer); retryTimer = undefined
    connected.value = false
  }

  function reset() {
    epoch++; refreshVersion++; activeRunId = null
    stopTransport(); current.value = null; events.value = []; connection.value = 'idle'; error.value = ''; retries = 0
  }

  async function refresh(runId: string, expectedEpoch: number) {
    // 旧scope不能递增当前刷新版本，否则会使新Run已经发出的GET失效。
    if (expectedEpoch !== epoch || runId !== activeRunId) return
    const version = ++refreshVersion
    const threadStore = useThreadStore()
    const threadEpoch = threadStore.epoch
    try {
      const detail = await getRun(runId)
      if (expectedEpoch !== epoch || version !== refreshVersion) return
      current.value = detail
      if (terminal(detail.status)) {
        stopTransport(); connection.value = 'complete'
        // message.completed与终态同事务；GET先确认终态时仍补齐尚未送达的Journal后缀。
        await replayEvents(runId, events.value.at(-1)?.seq ?? 0, event => {
          if (expectedEpoch === epoch && version === refreshVersion) append(event, false)
        })
        if (expectedEpoch !== epoch || version !== refreshVersion) return
        await threadStore.refresh(detail.thread_id, threadEpoch, () => expectedEpoch === epoch && version === refreshVersion)
      }
    } catch (cause) {
      if (expectedEpoch === epoch && version === refreshVersion) error.value = `${requestFailureCode(cause, 'RUN_REFRESH_FAILED')}：无法刷新执行事实，请重新连接`
    }
  }

  function append(event: RunEvent, refreshFacts = true): boolean {
    if (!activeRunId || event.run_id !== activeRunId || !Number.isSafeInteger(event.seq) || event.seq < 1 || events.value.some(item => item.seq === event.seq)) return false
    events.value.push(event)
    events.value.sort((left, right) => left.seq - right.seq)
    // Journal只触发重新GET，不能由事件payload本地宣布Run状态。
    if (refreshFacts && ['run.started', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled'].includes(event.type)) void refresh(activeRunId, epoch)
    return true
  }

  function connect(runId: string, expectedEpoch: number) {
    if (epoch !== expectedEpoch) return
    stopTransport(); connection.value = 'connecting'
    const afterSeq = events.value.at(-1)?.seq ?? 0
    stream = openRunStream(runId, afterSeq,
      event => { if (epoch === expectedEpoch) append(event) },
      () => {
        if (epoch !== expectedEpoch) return
        connected.value = false
        if (current.value && terminal(current.value.status)) { connection.value = 'complete'; return }
        connection.value = retries < 3 ? 'reconnecting' : 'disconnected'
        if (retries < 3) {
          const delay = 500 * 2 ** retries++
          retryTimer = setTimeout(() => connect(runId, expectedEpoch), delay)
        }
      },
      () => {
        if (epoch !== expectedEpoch) return
        connected.value = true; connection.value = 'connected'
        if (current.value && terminal(current.value.status)) { stopTransport(); connection.value = 'complete' }
      })
  }

  async function observe(runId: string) {
    reset()
    const expectedEpoch = epoch
    activeRunId = runId
    try {
      const detail = await getRun(runId)
      if (epoch !== expectedEpoch) return
      current.value = detail
      await replayEvents(runId, 0, event => { if (epoch === expectedEpoch) append(event) })
      if (epoch !== expectedEpoch) return
      // 建立连接后再次补放，覆盖GET结束与SSE订阅建立之间的窗口。
      connect(runId, expectedEpoch)
    } catch (cause) {
      if (epoch === expectedEpoch) { connection.value = 'disconnected'; error.value = `${requestFailureCode(cause, 'RUN_READ_FAILED')}：无法读取执行事实，请重新连接` }
    }
  }

  async function reconnect() {
    if (!activeRunId) return
    error.value = ''; retries = 0
    const runId = activeRunId; const expectedEpoch = epoch
    await refresh(runId, expectedEpoch)
    if (epoch === expectedEpoch && current.value && !terminal(current.value.status)) connect(runId, expectedEpoch)
  }

  async function cancel() {
    if (!current.value || terminal(current.value.status)) return
    const runId = current.value.run_id; const expectedEpoch = epoch
    try {
      await cancelRun(runId)
      if (expectedEpoch === epoch && runId === activeRunId) await refresh(runId, expectedEpoch)
    }
    catch (cause) { if (epoch === expectedEpoch) error.value = `${requestFailureCode(cause, 'RUN_CANCEL_FAILED')}：取消请求失败，请重试` }
  }

  const failureCode = computed(() => current.value?.last_error_code ? safeErrorCode(current.value.last_error_code) : '')
  return { current, events, connected, connection, error, messages, failureCode, observe, append, cancel, reset, reconnect }
})

