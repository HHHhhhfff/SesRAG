<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { ContextPlan, RunDetail, RunEvent } from '../types/api-v2'
import RunActions from './RunActions.vue'
import ContextNotice from './ContextNotice.vue'

const props = defineProps<{ run: RunDetail | null; events: RunEvent[]; connection: string; error: string; failureCode: string; contextDetail?: ContextPlan | null; readonly?: boolean; hasProfile?: boolean; operationPending?: boolean; hasPendingOperation?: boolean }>()
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 1000) })
onUnmounted(() => clearInterval(timer))
const elapsed = computed(() => props.run ? Math.max(0, Math.floor(((['succeeded', 'failed', 'cancelled'].includes(props.run.status) ? Date.parse(props.run.updated_at) : now.value) - Date.parse(props.run.created_at)) / 1000)) : 0)
// 最近错误是历史事实；当前是否失败仅由 Run 状态决定。
const failureDescription = computed(() => {
  if (props.run?.status === 'failed') return '执行失败'
  if (props.run?.status === 'retry_waiting') return '等待重试'
  if (props.run?.status === 'succeeded') return '上次尝试错误（已恢复）'
  return '上次尝试错误'
})
const emit = defineEmits<{ cancel: []; retry: []; regenerate: []; reconnect: [] }>()
const publicEvents = new Set(['run.created', 'task.queued', 'task.leased', 'run.started', 'retrieval.completed', 'answer.delta', 'task.retry_scheduled', 'message.completed', 'run.succeeded', 'run.failed', 'run.cancelled', 'context.planned', 'context.compacted', 'run.cancelling', 'run.retry_created', 'run.regenerated'])
</script>

<template>
  <section
    v-if="run || error"
    class="run-panel"
  >
    <div class="section-heading">
      <div>
        <span class="eyebrow">RUN</span>
        <strong>{{ run?.status ?? 'unknown' }}</strong>
      </div>
      <RunActions
        :run="run"
        :readonly="readonly"
        :has-profile="hasProfile"
        :loading="operationPending"
        :has-pending-operation="hasPendingOperation"
        @cancel="emit('cancel')"
        @retry="emit('retry')"
        @regenerate="emit('regenerate')"
      />
    </div>
    <p
      v-if="hasPendingOperation"
      class="pending-run-operation"
      role="status"
    >
      原操作结果未确认，重试将沿用原模型参数和同一幂等键。
    </p>
    <p
      v-if="failureCode"
      class="failure-summary"
      role="status"
    >
      {{ failureCode }}：{{ failureDescription }}
    </p>
    <p
      v-if="error"
      role="alert"
    >
      {{ error }}
    </p>
    <p
      v-if="['connecting', 'reconnecting', 'disconnected'].includes(connection)"
      class="stream-status"
      role="status"
    >
      {{ connection === 'disconnected' ? '连接中断' : '连接中' }}，执行仍由服务端管理
    </p>
    <button
      v-if="['reconnecting', 'disconnected'].includes(connection) || error"
      class="secondary-button"
      @click="emit('reconnect')"
    >
      重新连接
    </button>
    <p
      v-if="run"
      class="run-progress"
    >
      耗时 {{ elapsed }} 秒 · 第 {{ run.task.attempt }} 次尝试 · generation {{ run.task.generation }} · {{ run.task.state }}
    </p>
    <p
      v-if="run?.legacy"
      class="legacy-hint"
    >
      历史运行未保存模型 Profile；重试或重新生成前请选择可用模型。
    </p>
    <details
      v-if="run"
      class="run-detail"
    >
      <summary>执行详情</summary><p>{{ run.model?.display_name ?? '历史模型未知' }} · {{ run.model?.model_name ?? 'legacy' }}</p><p>操作 {{ run.operation_kind }} · Run {{ run.run_id }}</p><p v-if="run.snapshot">
        上下文窗口 {{ run.snapshot.context_window_tokens }} · 输出上限 {{ run.snapshot.reserved_output_tokens }} · {{ run.snapshot.context_policy_version }}
      </p>
    </details>
    <ContextNotice
      :plan="run?.context_plan ?? null"
      :detail="contextDetail"
    />
    <ol class="event-list">
      <li
        v-for="event in events.filter(item => publicEvents.has(item.type))"
        :key="event.seq"
      >
        <span class="event-seq">{{ event.seq }}</span>
        <span>{{ event.type }}</span>
      </li>
    </ol>
  </section>
</template>

