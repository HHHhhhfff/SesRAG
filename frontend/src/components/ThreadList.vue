<script setup lang="ts">
import { Plus, MessageSquare } from 'lucide-vue-next'
import type { ThreadSummary } from '../types/api-v2'

defineProps<{ threads: ThreadSummary[]; activeId?: string; hasMore?: boolean }>()
const emit = defineEmits<{ select: [string]; create: []; more: [] }>()
</script>

<template>
  <aside class="thread-panel">
    <div class="panel-heading">
      <div>
        <span class="eyebrow">SESRAG</span>
        <h1>持久会话</h1>
      </div>
      <button
        class="icon-button"
        title="新建会话"
        aria-label="新建会话"
        @click="emit('create')"
      >
        <Plus :size="18" />
      </button>
    </div>
    <button
      v-for="thread in threads"
      :key="thread.thread_id"
      class="thread-item"
      :class="{ active: thread.thread_id === activeId }"
      @click="emit('select', thread.thread_id)"
    >
      <MessageSquare :size="16" />
      <span>{{ thread.title }}</span>
      <small v-if="thread.archived_at">已归档</small>
    </button>
    <button
      v-if="hasMore"
      class="secondary-button thread-more"
      type="button"
      @click="emit('more')"
    >
      加载更多
    </button>
    <div
      v-if="!threads.length"
      class="empty-state"
    >
      暂无会话
    </div>
  </aside>
</template>

