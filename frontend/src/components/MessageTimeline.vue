<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { Message } from '../types/api'

defineProps<{ messages: Message[] }>()

function renderMarkdown(value: string) {
  return DOMPurify.sanitize(marked.parse(value) as string)
}
</script>

<template>
  <div class="message-list">
    <article v-for="message in messages" :key="message.message_id" class="message" :class="message.role">
      <div class="message-meta">{{ message.role === 'user' ? '你' : 'SesRAG' }}</div>
      <div class="message-content" v-html="renderMarkdown(message.content)" />
      <div v-if="message.citations.length" class="citation-list">
        <span v-for="citation in message.citations" :key="citation.chunk_id" class="citation">
          {{ citation.filename }} · {{ citation.start_offset }}-{{ citation.end_offset }}
        </span>
      </div>
    </article>
    <div v-if="!messages.length" class="empty-main">选择一个会话，开始提问。</div>
  </div>
</template>

