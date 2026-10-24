<script setup lang="ts">
import { ref } from 'vue'
import { renderMarkdown } from '../markdown/render'
import type { Message } from '../types/api-v2'

defineProps<{ messages: Message[]; readonly?: boolean; hasMore?: boolean }>()
const expanded = ref(new Set<string>())
const emit = defineEmits<{ fork: [string]; older: [] }>()

function toggle(key: string) {
  if (expanded.value.has(key)) expanded.value.delete(key)
  else expanded.value.add(key)
}

</script>

<template>
  <div class="message-list">
    <button
      v-if="hasMore"
      class="secondary-button"
      type="button"
      @click="emit('older')"
    >
      加载更早消息
    </button>
    <article
      v-for="message in messages"
      :key="message.message_id"
      class="message"
      :class="message.role"
    >
      <div class="message-meta">
        {{ message.role === 'user' ? '你' : 'SesRAG' }}
        <button
          v-if="!readonly && !message.message_id.startsWith('projection-')"
          class="text-action"
          type="button"
          @click="emit('fork', message.message_id)"
        >
          从此处分支
        </button>
      </div>
      <div
        class="message-content"
        v-html="renderMarkdown(message.content)"
      />
      <div
        v-if="message.citations.length"
        class="citation-list"
      >
        <div
          v-for="(citation, index) in message.citations"
          :key="citation.chunk_id"
        >
          <button
            class="citation"
            :aria-expanded="expanded.has(`${message.message_id}-${index}`)"
            :aria-controls="`citation-${message.seq}-${index}`"
            @click="toggle(`${message.message_id}-${index}`)"
            @keydown.enter.prevent="toggle(`${message.message_id}-${index}`)"
            @keydown.space.prevent="toggle(`${message.message_id}-${index}`)"
          >
            {{ citation.filename }} · {{ citation.start_offset }}-{{ citation.end_offset }}
          </button>
          <div
            v-if="expanded.has(`${message.message_id}-${index}`)"
            :id="`citation-${message.seq}-${index}`"
            class="citation-detail"
          >
            <p>文档 {{ citation.document_id }} · Chunk {{ citation.chunk_id }}</p>
            <p>字符 {{ citation.start_offset }}-{{ citation.end_offset }} · 分数 {{ citation.score }}</p>
            <template v-if="'index_batch_id' in citation">
              <p>批次 {{ citation.index_batch_id }}</p>
              <p
                v-for="(location, locationIndex) in citation.locations"
                :key="locationIndex"
              >
                第 {{ location.number }} {{ location.kind === 'line' ? '行' : '段' }} · 字符 {{ location.start_offset }}-{{ location.end_offset }}
              </p>
              <p v-if="!citation.locations.length">
                此索引未保存基础位置
              </p>
            </template>
            <p v-else>
              历史引用未保存批次和基础位置
            </p>
          </div>
        </div>
      </div>
    </article>
    <div
      v-if="!messages.length"
      class="empty-main"
    >
      选择一个会话，开始提问。
    </div>
  </div>
</template>

