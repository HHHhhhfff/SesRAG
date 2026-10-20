<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Send, Archive, ArchiveRestore } from 'lucide-vue-next'
import { getHealth } from '../api/health'
import { failureCode } from '../api/http'
import type { HealthReady } from '../types/api'
import { useDocumentStore } from '../stores/documents'
import { useModelStore } from '../stores/model'
import { useRunStore } from '../stores/run'
import { useThreadStore } from '../stores/thread'
import DocumentUploader from '../components/DocumentUploader.vue'
import MessageTimeline from '../components/MessageTimeline.vue'
import RunTimeline from '../components/RunTimeline.vue'
import ThreadList from '../components/ThreadList.vue'
import BranchSelector from '../components/BranchSelector.vue'
import ModelSelector from '../components/ModelSelector.vue'

const threadStore = useThreadStore(); const runStore = useRunStore(); const documentStore = useDocumentStore(); const modelStore = useModelStore()
const input = ref(''); const error = ref(''); const health = ref<HealthReady | null>(null); let disposed = false; let healthEpoch = 0; let submissionVersion = 0
const editingTitle = ref(false); const titleDraft = ref('')
const activeId = computed(() => threadStore.active?.thread.thread_id); const apiStatus = computed(() => health.value?.status === 'ok' ? 'ready' : health.value?.status ?? 'unknown'); const archived = computed(() => Boolean(threadStore.active?.thread.archived_at))
watch(() => threadStore.epoch, () => runStore.reset(), { flush: 'sync' })
watch(() => threadStore.active?.runs, runs => { const detail = threadStore.active; const ownRuns = runs?.filter(item => item.branch_id === detail?.branch.branch_id); const latest = ownRuns?.find(item => item.run_id === detail?.active_run_id) ?? ownRuns?.find(item => item.run_id === detail?.recent_run_id) ?? ownRuns?.[0]; if (latest && !runStore.current) void runStore.observe(latest.run_id) }, { deep: true })
async function selectThread(threadId: string) { error.value = ''; try { await threadStore.selectThread(threadId) } catch (cause) { if (!disposed && threadStore.selectedId === threadId) error.value = `${failureCode(cause, 'THREAD_READ_FAILED')}：无法读取会话` } }
async function addThread() {
  const epoch = threadStore.epoch
  try { await threadStore.addThread() }
  catch (cause) { if (!disposed && epoch === threadStore.epoch) error.value = `${failureCode(cause, 'THREAD_CREATE_FAILED')}：无法创建会话` }
}
async function action(operation: () => Promise<unknown>) { const epoch = threadStore.epoch; try { await operation() } catch (cause) { if (!disposed && epoch === threadStore.epoch) error.value = `${failureCode(cause, 'WORKSPACE_OPERATION_FAILED')}：操作失败，请重试` } }
async function renameThread() { await action(() => threadStore.rename(titleDraft.value)); editingTitle.value = false }
async function retryMessage() { await action(async () => { const result = await threadStore.retryPendingMessage(); if (result) await runStore.observe(result.run_id) }) }
async function ask() { const content = input.value.trim(); if (!content || !threadStore.active || archived.value) return; const epoch = threadStore.epoch; const submission = ++submissionVersion; input.value = ''; try { const result = await threadStore.ask(content, modelStore.selected ?? undefined); if (!result || disposed || epoch !== threadStore.epoch || submission !== submissionVersion) return; await runStore.observe(result.run_id) } catch (cause) { if (!disposed && epoch === threadStore.epoch && submission === submissionVersion) error.value = `${failureCode(cause, 'MESSAGE_SEND_FAILED')}：请求失败，请重试` } }
async function bootstrap() { void refreshHealth(); await modelStore.load(); try { await Promise.all([threadStore.loadThreads(), documentStore.load()]) } catch { if (!disposed) error.value = 'WORKSPACE_READ_FAILED：无法连接 API' } }
async function refreshHealth() { const epoch = ++healthEpoch; try { const response = await getHealth(); if (!disposed && epoch === healthEpoch) health.value = response } catch { if (!disposed && epoch === healthEpoch) health.value = null } }
onMounted(bootstrap); onUnmounted(() => { disposed = true; runStore.reset(); threadStore.invalidate(); documentStore.stop() })
</script>

<template>
  <main class="app-shell">
    <ThreadList
      :threads="threadStore.threads"
      :active-id="activeId"
      :has-more="threadStore.hasMore"
      @select="selectThread"
      @create="addThread"
      @more="threadStore.loadMoreThreads"
    />
    <section class="conversation-column">
      <header class="topbar">
        <div>
          <span class="eyebrow">WORKSPACE</span><form
            v-if="editingTitle"
            class="title-edit"
            @submit.prevent="renameThread"
          >
            <input
              v-model="titleDraft"
              maxlength="200"
              aria-label="会话标题"
            ><button
              class="secondary-button"
              type="submit"
            >
              保存
            </button><button
              class="secondary-button"
              type="button"
              @click="editingTitle = false"
            >
              取消
            </button>
          </form><div
            v-else
            class="title-line"
          >
            <h2>{{ threadStore.active?.thread.title ?? '选择会话' }}</h2><button
              v-if="threadStore.active"
              class="text-action"
              type="button"
              @click="titleDraft = threadStore.active.thread.title; editingTitle = true"
            >
              重命名
            </button>
          </div>
        </div>
        <div
          class="health-panel"
          aria-live="polite"
        >
          <span
            class="connection-dot"
            :class="{ online: apiStatus === 'ready' }"
          >API {{ apiStatus }}</span><span>PG {{ health?.database ?? 'unknown' }}</span><span>Worker {{ health?.worker ?? 'unknown' }}</span><span>Redis {{ health?.redis ?? 'unknown' }}</span><button
            class="secondary-button"
            @click="refreshHealth"
          >
            检查健康
          </button>
        </div>
      </header>
      <div
        v-if="threadStore.active"
        class="workspace-controls"
      >
        <BranchSelector
          :branches="threadStore.branches"
          :model-value="threadStore.selectedBranchId"
          @change="id => action(() => threadStore.selectBranch(id))"
        />
        <ModelSelector
          :models="modelStore.models"
          :selected="modelStore.selected"
          :disabled="Boolean(runStore.current && !['succeeded', 'failed', 'cancelled'].includes(runStore.current.status))"
          @change="modelStore.select"
        />
        <span class="model-operation-hint">重试和重新生成默认沿用原模型；手动切换后使用所选模型。</span>
        <button
          class="icon-button"
          :title="archived ? '取消归档' : '归档会话'"
          :aria-label="archived ? '取消归档' : '归档会话'"
          @click="action(() => threadStore.setArchived(!archived))"
        >
          <ArchiveRestore
            v-if="archived"
            :size="16"
          /><Archive
            v-else
            :size="16"
          />
        </button>
      </div>
      <div
        v-if="error"
        class="error-banner"
      >
        {{ error }}
      </div>
      <p
        v-if="threadStore.pendingMessage"
        class="pending-operation"
        role="status"
      >
        上次提交结果未确认，重试会使用原正文和同一幂等键。<button
          class="secondary-button"
          @click="retryMessage"
        >
          重试原提交
        </button>
      </p>
      <MessageTimeline
        :messages="runStore.messages"
        :readonly="archived"
        :has-more="threadStore.active?.has_more"
        @older="action(() => threadStore.loadOlder())"
        @fork="id => action(() => threadStore.forkFrom(id))"
      />
      <form
        class="composer"
        @submit.prevent="ask"
      >
        <textarea
          v-model="input"
          :disabled="!threadStore.active || archived"
          minlength="1"
          maxlength="20000"
          placeholder="输入问题，按 Ctrl+Enter 发送"
          @keydown.ctrl.enter.prevent="ask"
        /><button
          class="send-button"
          type="submit"
          :disabled="!input.trim() || !threadStore.active || archived"
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
        :context-detail="runStore.contextDetail"
        :readonly="archived"
        :has-profile="Boolean(modelStore.selected)"
        :operation-pending="runStore.operationPending"
        :has-pending-operation="Boolean(runStore.pendingOperation)"
        @cancel="runStore.cancel"
        @retry="runStore.retry"
        @regenerate="runStore.regenerate"
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
