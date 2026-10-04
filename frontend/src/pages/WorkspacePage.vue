<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Send } from 'lucide-vue-next'
import { openRunStream } from '../events/run-event-stream'
import { useDocumentStore } from '../stores/documents'
import { useRunStore } from '../stores/run'
import { useThreadStore } from '../stores/thread'
import DocumentUploader from '../components/DocumentUploader.vue'
import MessageTimeline from '../components/MessageTimeline.vue'
import RunTimeline from '../components/RunTimeline.vue'
import ThreadList from '../components/ThreadList.vue'

const threadStore = useThreadStore()
const runStore = useRunStore()
const documentStore = useDocumentStore()
const input = ref('')
const error = ref('')
let stream: EventSource | null = null

const activeId = computed(() => threadStore.active?.thread.thread_id)

async function selectThread(threadId: string) {
  error.value = ''
  await threadStore.selectThread(threadId)
}

async function ask() {
  if (!input.value.trim() || !threadStore.active) return
  const content = input.value.trim()
  input.value = ''
  try {
    const result = await threadStore.ask(content)
    if (!result) return
    await runStore.observe(result.run_id)
    stream?.close()
    stream = openRunStream(result.run_id, runStore.events.at(-1)?.seq ?? 0, (event) => {
      runStore.append(event)
      if (event.type === 'answer.delta') threadStore.appendAssistantDelta(result.run_id, String(event.data.text ?? ''))
    })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '请求失败'
  }
}

async function bootstrap() {
  try {
    await Promise.all([threadStore.loadThreads(), documentStore.load()])
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法连接 API'
  }
}

onMounted(bootstrap)
onUnmounted(() => stream?.close())
</script>

<template>
  <main class="app-shell">
    <ThreadList :threads="threadStore.threads" :active-id="activeId" @select="selectThread" @create="threadStore.addThread" />
    <section class="conversation-column">
      <header class="topbar">
        <div>
          <span class="eyebrow">WORKSPACE</span>
          <h2>{{ threadStore.active?.thread.title ?? '选择会话' }}</h2>
        </div>
        <span class="connection-dot" :class="{ online: !error }">API</span>
      </header>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <MessageTimeline :messages="threadStore.active?.messages ?? []" />
      <form class="composer" @submit.prevent="ask">
        <textarea v-model="input" :disabled="!threadStore.active" placeholder="输入问题，按 Ctrl+Enter 发送" @keydown.ctrl.enter.prevent="ask" />
        <button class="send-button" type="submit" :disabled="!input.trim() || !threadStore.active" title="发送" aria-label="发送"><Send :size="17" /></button>
      </form>
    </section>
    <aside class="detail-column">
      <RunTimeline :run="runStore.current" :events="runStore.events" @cancel="runStore.cancel" />
      <DocumentUploader :documents="documentStore.items" :loading="documentStore.loading" @upload="documentStore.upload" />
    </aside>
  </main>
</template>

