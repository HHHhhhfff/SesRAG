<script setup lang="ts">
import { RefreshCw, Square } from 'lucide-vue-next'
import type { RunDetail } from '../types/api-v2'
defineProps<{ run: RunDetail | null; loading?: boolean; readonly?: boolean; hasProfile?: boolean; hasPendingOperation?: boolean }>()
const emit = defineEmits<{ cancel: []; retry: []; regenerate: [] }>()
</script>
<template>
  <div
    v-if="run"
    class="run-actions"
  >
    <button
      v-if="['queued', 'running', 'retry_waiting', 'cancelling'].includes(run.status)"
      class="secondary-button"
      :disabled="loading || run.status === 'cancelling'"
      @click="emit('cancel')"
    >
      <Square :size="14" /> {{ run.status === 'cancelling' ? '停止中' : '停止' }}
    </button>
    <button
      v-if="!readonly && ['failed', 'cancelled'].includes(run.status)"
      class="secondary-button"
      :disabled="loading || (run.legacy && !hasProfile && !hasPendingOperation)"
      @click="emit('retry')"
    >
      <RefreshCw :size="14" /> {{ hasPendingOperation ? '重试原操作' : '重试' }}
    </button>
    <button
      v-if="!readonly && run.status === 'succeeded'"
      class="secondary-button"
      :disabled="loading || (run.legacy && !hasProfile && !hasPendingOperation)"
      @click="emit('regenerate')"
    >
      <RefreshCw :size="14" /> {{ hasPendingOperation ? '重试原操作' : '重新生成' }}
    </button>
  </div>
</template>
