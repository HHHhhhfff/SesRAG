<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Send } from 'lucide-vue-next'
import { getHealth } from '../api/health'
import { failureCode } from '../api/http'
import type { HealthReady } from '../types/api'
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
const health = ref<HealthReady | null>(null)
let disposed = false
let healthEpoch = 0
let submissionVersion = 0

const activeId = computed(() => threadStore.active?.thread.thread_id)
const apiStatus = computed(() => health.value?.status === 'ok' ? 'ready' : health.value?.status ?? 'unknown')

// 选中身份先失效旧Run，再读取新详情；已排队回调也不能跨会话写回。
watch(() => threadStore.epoch, () => runStore.reset(), { flush: 'sync' })
watch(activeId, () => {
  const latest = threadStore.active?.runs[0]
  if (latest) void runStore.observe(latest.run_id)
})

async function selectThread(threadId: string) {
  error.value = ''
  try { await threadStore.selectThread(threadId) }
  catch { if (!disposed && threadStore.selectedId === threadId) error.value = 'THREAD_READ_FAILED：无法读取会话' }
}

async function addThread() {
  const epoch = threadStore.epoch
  try { await threadStore.addThread() }
  catch (cause) { if (!disposed && epoch === threadStore.epoch) error.value = `${failureCode(cause, 'THREAD_CREATE_FAILED')}：无法创建会话` }
}

async function ask() {
  if (!input.value.trim() || !threadStore.active) return
  const content = input.value.trim()
  const epoch = threadStore.epoch
  const submission = ++submissionVersion
  input.value = ''
  try {
    const result = await threadStore.ask(content)
    if (!result || disposed || epoch !== threadStore.epoch || submission !== submissionVersion) return
    await runStore.observe(result.run_id)
  } catch (cause) {
    if (!disposed && epoch === threadStore.epoch && submission === submissionVersion) error.value = `${failureCode(cause, 'MESSAGE_SEND_FAILED')}：请求失败，请重试`
  }
}

async function bootstrap() {
  void refreshHealth()
  try {
    await Promise.all([threadStore.loadThreads(), documentStore.load()])
  } catch {
    if (!disposed) error.value = 'WORKSPACE_READ_FAILED：无法连接 API'
  }
}

async function refreshHealth() {
  const epoch = ++healthEpoch
  try {
    const response = await getHealth()
    if (!disposed && epoch === healthEpoch) health.value = response
  } catch { if (!disposed && epoch === healthEpoch) health.value = null }
}

onMounted(bootstrap)
onUnmounted(() => { disposed = true; runStore.reset(); threadStore.invalidate(); documentStore.stop() })
</script>

<template>
  <main class="app-shell">
    <ThreadList
      :threads="threadStore.threads"
      :active-id="activeId"
      @select="selectThread"
      @create="addThread"
    />
    <section class="conversation-column">
      <header class="topbar">
        <div>
          <span class="eyebrow">WORKSPACE</span>
          <h2>{{ threadStore.active?.thread.title ?? '选择会话' }}</h2>
        </div>
        <div
          class="health-panel"
          aria-live="polite"
        >
          <span
            class="connection-dot"
            :class="{ online: apiStatus === 'ready' }"
          >API {{ apiStatus }}</span>
          <span>PG {{ health?.database ?? 'unknown' }}</span>
          <span>Worker {{ health?.worker ?? 'unknown' }}</span>
          <span>Redis {{ health?.redis ?? 'unknown' }}</span>
          <button
            class="secondary-button"
            @click="refreshHealth"
          >
            检查健康
          </button>
        </div>
      </header>
      <div
        v-if="error"
        class="error-banner"
      >
        {{ error }}
      </div>
      <MessageTimeline :messages="runStore.messages" />
      <form
        class="composer"
        @submit.prevent="ask"
      >
        <textarea
          v-model="input"
          :disabled="!threadStore.active"
          placeholder="输入问题，按 Ctrl+Enter 发送"
          @keydown.ctrl.enter.prevent="ask"
        />
        <button
          class="send-button"
          type="submit"
          :disabled="!input.trim() || !threadStore.active"
          title="发送"
          aria-label="发送"
        >
          <Send :size="17" />
        </button>
      </form>
    </section>
    <aside class="detail-column">
      <RunTimeline
        :run="runStore.current"
        :events="runStore.events"
        :connection="runStore.connection"
        :error="runStore.error"
        :failure-code="runStore.failureCode"
        @cancel="runStore.cancel"
        @reconnect="runStore.reconnect"
      />
      <DocumentUploader
        :documents="documentStore.items"
        :loading="documentStore.loading"
        :error="documentStore.error"
        :paused="documentStore.paused"
        @upload="documentStore.upload"
        @refresh="documentStore.load"
      />
    </aside>
  </main>
</template>

