<script setup lang="ts">
import { Square } from 'lucide-vue-next'
import type { RunDetail, RunEvent } from '../types/api'

defineProps<{ run: RunDetail | null; events: RunEvent[] }>()
const emit = defineEmits<{ cancel: [] }>()
</script>

<template>
  <section v-if="run" class="run-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">RUN</span>
        <strong>{{ run.status }}</strong>
      </div>
      <button v-if="!['succeeded', 'failed', 'cancelled'].includes(run.status)" class="secondary-button" @click="emit('cancel')">
        <Square :size="14" /> 停止
      </button>
    </div>
    <ol class="event-list">
      <li v-for="event in events" :key="event.seq">
        <span class="event-seq">{{ event.seq }}</span>
        <span>{{ event.type }}</span>
      </li>
    </ol>
  </section>
</template>

