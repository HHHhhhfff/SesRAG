import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { cancelRun, getContext, getRun, regenerateRun, retryRun } from '../api/v2/runs'
import { createIdempotencyKey } from '../api/v2/threads'
import { failureCode as requestFailureCode, safeErrorCode } from '../api/http'
import { openV2RunStream, replayV2Events } from '../events/run-event-stream'
import { useThreadStore } from './thread'
import { useModelStore } from './model'
import type { ContextPlan, Message, RunDetail, RunEvent, RunOperationCreate } from '../types/api-v2'

const terminal = (status: string) => ['succeeded', 'failed', 'cancelled'].includes(status)
export const useRunStore = defineStore('run', () => {
  const current = ref<RunDetail | null>(null)
  const events = ref<RunEvent[]>([])
  const connected = ref(false)
  const connection = ref('idle')
  const error = ref('')
  const context = ref<RunDetail['context_plan']>(null)
  const contextDetail = ref<ContextPlan | null>(null)
  const operationPending = ref(false)
  const pendingOperation = ref<{ key: string; kind: 'retry' | 'regenerate'; runId: string; threadId: string; branchId: string; payload: RunOperationCreate } | null>(null)
  let epoch = 0; let activeRunId: string | null = null; let activeThreadId: string | null = null; let activeBranchId: string | null = null
  let stream: ReturnType<typeof openV2RunStream> | null = null; let retryTimer: ReturnType<typeof setTimeout> | undefined; let retries = 0; let refreshVersion = 0; let attemptKey = ''; let draftStartSeq = 0
  let observedModelRevision = 0
  const threadStore = () => useThreadStore()
  const messages = computed<Message[]>(() => {
    const detail = threadStore().active
    if (!detail || !current.value || detail.thread.thread_id !== current.value.thread_id || detail.branch.branch_id !== current.value.branch_id) return detail?.messages ?? []
    const runId = current.value.run_id; const answer = detail.messages.find(item => item.run_id === runId && item.role === 'assistant')
    const delta = events.value.filter(item => item.run_id === runId && item.seq > draftStartSeq && item.type === 'answer.delta' && typeof item.data.text === 'string' && (!attemptKey || item.data.generation === undefined || `${item.data.task_id}:${item.data.generation}:${item.data.attempt}` === attemptKey)).map(item => item.data.text).join('')
    if (answer?.status === 'completed' || current.value.status === 'succeeded') return detail.messages
    if (!delta) return detail.messages
    if (answer) return detail.messages.map(item => item.message_id === answer.message_id ? { ...item, content: (answer.status === 'generating' ? answer.content : '') + delta, status: 'generating' } : item)
    return [...detail.messages, { message_id: `projection-${runId}`, thread_id: detail.thread.thread_id, branch_id: detail.branch.branch_id, seq: (detail.messages.at(-1)?.seq ?? 0) + 1, role: 'assistant', source: 'assistant_generation', created_at: events.value[0]?.occurred_at ?? '', content: delta, status: 'generating', run_id: runId, citations: [] }]
  })
  function stopTransport() { stream?.close(); stream = null; clearTimeout(retryTimer); retryTimer = undefined; connected.value = false }
  function reset() { epoch++; refreshVersion++; activeRunId = null; activeThreadId = null; activeBranchId = null; stopTransport(); current.value = null; events.value = []; context.value = null; contextDetail.value = null; connection.value = 'idle'; error.value = ''; retries = 0; attemptKey = ''; draftStartSeq = 0; operationPending.value = false; pendingOperation.value = null }
  function contiguousCursor() {
    let cursor = 0
    for (const event of events.value) { if (event.seq !== cursor + 1) break; cursor = event.seq }
    return cursor
  }
  function append(event: RunEvent, refreshFacts = true) {
    if (!activeRunId || event.run_id !== activeRunId || !Number.isSafeInteger(event.seq) || event.seq < 1 || events.value.some(item => item.run_id === event.run_id && item.seq === event.seq)) return false
    if (current.value && event.schema_version !== current.value.execution_schema_version) { error.value = 'EVENT_SCHEMA_UNSUPPORTED：运行与事件版本不一致'; return false }
    events.value.push(event); events.value.sort((a, b) => a.seq - b.seq)
    if ((event.type === 'task.leased' || event.type === 'run.started') && event.seq >= draftStartSeq) {
      if (event.data.generation !== undefined) attemptKey = `${event.data.task_id}:${event.data.generation}:${event.data.attempt}`
      else attemptKey = ''
      draftStartSeq = event.seq
    }
    if (refreshFacts && ['run.started', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled', 'run.cancelling', 'context.planned', 'context.compacted'].includes(event.type)) void refresh(activeRunId, epoch)
    return true
  }
  async function refresh(runId: string, expectedEpoch: number) {
    if (expectedEpoch !== epoch || runId !== activeRunId) return
    const version = ++refreshVersion
    try {
      const detail = await getRun(runId)
      if (expectedEpoch !== epoch || version !== refreshVersion || detail.thread_id !== activeThreadId || detail.branch_id !== activeBranchId) return
      current.value = detail; context.value = detail.context_plan
      if (detail.context_plan) void loadContext(runId, expectedEpoch)
      if (terminal(detail.status)) {
        stopTransport(); connection.value = 'complete'
        await replayV2Events(runId, contiguousCursor(), event => { if (expectedEpoch === epoch && version === refreshVersion) append(event, false) })
        if (expectedEpoch === epoch && version === refreshVersion && activeThreadId && activeBranchId) await threadStore().refresh(activeThreadId, activeBranchId, threadStore().epoch, () => expectedEpoch === epoch && version === refreshVersion)
      }
    } catch (cause) { if (expectedEpoch === epoch && version === refreshVersion) error.value = `${requestFailureCode(cause, 'RUN_REFRESH_FAILED')}：无法刷新执行事实，请重新连接` }
  }
  async function loadContext(runId: string, expectedEpoch: number) {
    try { const response = await getContext(runId); if (expectedEpoch === epoch && runId === activeRunId) contextDetail.value = response.plan }
    catch (cause) { if (expectedEpoch === epoch && runId === activeRunId) error.value = `${requestFailureCode(cause, 'CONTEXT_READ_FAILED')}：无法读取上下文计划` }
  }
  function connect(runId: string, expectedEpoch: number) {
    if (epoch !== expectedEpoch) return
    stopTransport(); connection.value = 'connecting'; const afterSeq = contiguousCursor()
    stream = openV2RunStream(runId, afterSeq, event => { if (epoch === expectedEpoch && event.run_id === activeRunId) append(event) }, cause => {
      if (epoch !== expectedEpoch) return
      if (cause) error.value = `${requestFailureCode(cause, 'EVENT_SCHEMA_INVALID')}：无法解析事件，请重新连接`
      connected.value = false; if (current.value && terminal(current.value.status)) { connection.value = 'complete'; return }
      connection.value = retries < 3 ? 'reconnecting' : 'disconnected'; if (retries < 3) { const delay = 500 * 2 ** retries++; retryTimer = setTimeout(() => connect(runId, expectedEpoch), delay) }
    }, () => { if (epoch === expectedEpoch) { connected.value = true; connection.value = 'connected'; if (current.value && terminal(current.value.status)) void refresh(runId, expectedEpoch) } })
  }
  async function observe(runId: string) {
    reset(); const expectedEpoch = epoch; activeRunId = runId
    observedModelRevision = useModelStore().selectionRevision
    const selectedThread = threadStore().selectedId; const selectedBranch = threadStore().selectedBranchId; const threadEpoch = threadStore().epoch
    try {
      const detail = await getRun(runId)
      if (epoch !== expectedEpoch || threadEpoch !== threadStore().epoch) return
      if (detail.thread_id !== selectedThread || detail.branch_id !== selectedBranch) { error.value = 'RUN_SCOPE_MISMATCH：执行不属于所选会话分支'; connection.value = 'disconnected'; return }
      activeThreadId = detail.thread_id; activeBranchId = detail.branch_id; current.value = detail; context.value = detail.context_plan
      if (detail.context_plan) void loadContext(runId, expectedEpoch)
      await replayV2Events(runId, 0, event => { if (epoch === expectedEpoch) append(event, false) })
      if (epoch === expectedEpoch) connect(runId, expectedEpoch)
    } catch (cause) { if (epoch === expectedEpoch) { connection.value = 'disconnected'; error.value = `${requestFailureCode(cause, 'RUN_READ_FAILED')}：无法读取执行事实，请重新连接` } }
  }
  async function reconnect() { if (!activeRunId) return; error.value = ''; retries = 0; const expectedEpoch = epoch; await refresh(activeRunId, expectedEpoch); if (epoch === expectedEpoch && current.value && !terminal(current.value.status)) connect(activeRunId, expectedEpoch) }
  async function cancel() { if (!current.value || terminal(current.value.status)) return; const runId = current.value.run_id; const expectedEpoch = epoch; try { await cancelRun(runId); if (expectedEpoch === epoch && runId === activeRunId) await refresh(runId, expectedEpoch) } catch (cause) { if (expectedEpoch === epoch) error.value = `${requestFailureCode(cause, 'RUN_CANCEL_FAILED')}：取消请求失败，请重试` } }
  async function related(kind: 'retry' | 'regenerate') {
    if (!current.value || operationPending.value || threadStore().active?.thread.archived_at || (kind === 'retry' ? !['failed', 'cancelled'].includes(current.value.status) : current.value.status !== 'succeeded')) return null
    const expectedEpoch = epoch; const threadEpoch = threadStore().epoch
    const old = pendingOperation.value
    if (old && (old.kind !== kind || old.runId !== current.value.run_id || old.threadId !== current.value.thread_id || old.branchId !== current.value.branch_id)) { error.value = 'RUN_OPERATION_PENDING：请先重试已提交的原操作'; return null }
    const model = useModelStore().selected
    if (!old && current.value.legacy && !model) { error.value = 'MODEL_PROFILE_REQUIRED：旧运行需要先选择模型'; return null }
    // 默认交由服务端复制来源快照；只有查看该Run后明确换模或legacy选择才覆盖。
    const overrideModel = current.value.legacy || useModelStore().selectionRevision !== observedModelRevision
    const payload = model && overrideModel ? { model_profile_id: model.profile_id, model_profile_version: model.version } : {}
    const pending = old ?? { key: createIdempotencyKey(), kind, runId: current.value.run_id, threadId: current.value.thread_id, branchId: current.value.branch_id, payload }
    pendingOperation.value = pending; operationPending.value = true; error.value = ''
    try {
      const result = kind === 'retry' ? await retryRun(pending.runId, pending.payload, pending.key) : await regenerateRun(pending.runId, pending.payload, pending.key)
      if (expectedEpoch !== epoch || threadEpoch !== threadStore().epoch || pending.threadId !== threadStore().selectedId || pending.branchId !== threadStore().selectedBranchId) return null
      pendingOperation.value = null
      await threadStore().selectThread(pending.threadId, result.branch_id)
      if (threadStore().selectedId === pending.threadId && threadStore().selectedBranchId === result.branch_id) await observe(result.run_id)
      return result
    } catch (cause) { if (expectedEpoch === epoch) error.value = `${requestFailureCode(cause, 'RUN_OPERATION_FAILED')}：操作结果未确认，请重试同一操作`; return null }
    finally { if (expectedEpoch === epoch) operationPending.value = false }
  }
  const failureCode = computed(() => current.value?.last_error_code ? safeErrorCode(current.value.last_error_code) : '')
  return { current, events, connected, connection, error, context, contextDetail, operationPending, pendingOperation, messages, failureCode, observe, append, cancel, reconnect, reset, retry: () => related('retry'), regenerate: () => related('regenerate') }
})
