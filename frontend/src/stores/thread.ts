import { defineStore } from 'pinia'
import { createThread, getThread, listThreads, sendMessage } from '../api/threads'
import type { Message, ThreadDetail, ThreadSummary } from '../types/api'

export const useThreadStore = defineStore('thread', {
  state: () => ({ threads: [] as ThreadSummary[], active: null as ThreadDetail | null, loading: false }),
  actions: {
    async loadThreads() {
      this.threads = await listThreads()
      if (!this.active && this.threads[0]) await this.selectThread(this.threads[0].thread_id)
    },
    async selectThread(threadId: string) {
      this.loading = true
      try {
        this.active = await getThread(threadId)
      } finally {
        this.loading = false
      }
    },
    async addThread() {
      const thread = await createThread('新会话')
      this.threads.unshift(thread)
      await this.selectThread(thread.thread_id)
    },
    async ask(content: string) {
      if (!this.active) return null
      const result = await sendMessage(this.active.thread.thread_id, content)
      await this.selectThread(this.active.thread.thread_id)
      return result
    },
    appendAssistantDelta(runId: string, delta: string) {
      const message = this.active?.messages.find((item: Message) => item.run_id === runId && item.role === 'assistant')
      if (message) message.content += delta
    },
  },
})

