<script setup lang="ts">
import { Upload } from 'lucide-vue-next'
import { safeErrorCode } from '../api/http'
import type { DocumentItem } from '../types/api'

defineProps<{ documents: DocumentItem[]; loading: boolean; error: string; paused: boolean }>()
const emit = defineEmits<{ upload: [File]; refresh: [] }>()

function onChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('upload', file)
}
</script>

<template>
  <section class="document-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">KNOWLEDGE</span>
        <strong>文档索引</strong>
      </div>
      <label
        class="secondary-button"
        :class="{ disabled: loading }"
      >
        <Upload :size="14" /> 上传
        <input
          type="file"
          accept=".txt,.md,.docx"
          hidden
          :disabled="loading"
          @change="onChange"
        >
      </label>
    </div>
    <p
      v-if="error"
      role="alert"
    >
      {{ error }}
    </p>
    <p
      v-if="paused"
      role="status"
    >
      自动刷新已暂停，可手动继续检查。
    </p>
    <button
      class="secondary-button"
      @click="emit('refresh')"
    >
      刷新索引状态
    </button>
    <div
      v-for="document in documents"
      :key="document.document_id"
      class="document-item"
    >
      <span>{{ document.filename }}</span>
      <small :class="`status-${document.status}`">{{ document.status }}</small>
      <span
        v-if="document.last_error_code"
        class="failure-summary"
      >{{ safeErrorCode(document.last_error_code) }}：索引失败</span>
    </div>
    <div
      v-if="!documents.length"
      class="empty-state"
    >
      还没有文档
    </div>
  </section>
</template>

