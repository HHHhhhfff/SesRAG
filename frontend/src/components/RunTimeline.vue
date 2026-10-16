<script setup lang="ts">
import { Square } from 'lucide-vue-next'
import { computed } from 'vue'
import type { RunDetail, RunEvent } from '../types/api'

const props = defineProps<{ run: RunDetail | null; events: RunEvent[]; connection: string; error: string; failureCode: string }>()
// 最近错误是历史事实；当前是否失败仅由 Run 状态决定。
const failureDescription = computed(() => {
  if (props.run?.status === 'failed') return '执行失败'
  if (props.run?.status === 'retry_waiting') return '等待重试'
  if (props.run?.status === 'succeeded') return '上次尝试错误（已恢复）'
  return '上次尝试错误'
})
const emit = defineEmits<{ cancel: []; reconnect: [] }>()
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
      <button
        v-if="run && !['succeeded', 'failed', 'cancelled'].includes(run.status)"
        class="secondary-button"
        @click="emit('cancel')"
      >
        <Square :size="14" /> 停止
      </button>
    </div>
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
    <ol class="event-list">
      <li
        v-for="event in events"
        :key="event.seq"
      >
        <span class="event-seq">{{ event.seq }}</span>
        <span>{{ event.type }}</span>
      </li>
    </ol>
  </section>
</template>

