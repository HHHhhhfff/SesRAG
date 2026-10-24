<script setup lang="ts">
import { Plus, MessageSquare } from 'lucide-vue-next'
import type { ThreadSummary } from '../types/api-v2'

defineProps<{ threads: ThreadSummary[]; activeId?: string; hasMore?: boolean; loadingMore?: boolean; view: 'active' | 'archived' }>()
const emit = defineEmits<{ select: [string]; create: []; more: []; view: ['active' | 'archived'] }>()
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
    <div class="thread-views" role="group" aria-label="会话列表视图">
      <button class="secondary-button" type="button" :aria-pressed="view === 'active'" @click="emit('view', 'active')">普通会话</button>
      <button class="secondary-button" type="button" :aria-pressed="view === 'archived'" @click="emit('view', 'archived')">已归档</button>
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
      :disabled="loadingMore"
      @click="emit('more')"
    >
      加载更多
    </button>
    <div
      v-if="!threads.length"
      class="empty-state"
    >
      {{ hasMore ? (view === 'archived' ? '已加载会话中暂无归档项，可加载更多' : '已加载会话中暂无普通项，可加载更多') : (view === 'archived' ? '暂无归档会话' : '暂无普通会话') }}
    </div>
  </aside>
</template>

