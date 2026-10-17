import { defineStore } from 'pinia'
import { createThread, getThread, listThreads, sendMessage } from '../api/threads'
import type { ThreadDetail, ThreadSummary } from '../types/api'

export const useThreadStore = defineStore('thread', {
  state: () => ({ threads: [] as ThreadSummary[], active: null as ThreadDetail | null, loading: false, epoch: 0, submissionVersion: 0, selectedId: null as string | null }),
  actions: {
    async loadThreads() {
      const epoch = this.epoch
      const threads = await listThreads()
      if (epoch !== this.epoch) return
      this.threads = threads
      if (!this.selectedId && threads[0]) await this.selectThread(threads[0].thread_id)
    },
    async selectThread(threadId: string) {
      const epoch = ++this.epoch
      this.selectedId = threadId
      this.active = null
      this.loading = true
      try {
        const detail = await getThread(threadId)
        if (epoch === this.epoch) this.active = detail
      } finally {
        if (epoch === this.epoch) this.loading = false
      }
    },
    async refresh(threadId: string, epoch?: number, isCurrent: () => boolean = () => true) {
      const expectedEpoch = epoch ?? this.epoch
      const detail = await getThread(threadId)
      if (expectedEpoch === this.epoch && threadId === this.selectedId && isCurrent()) this.active = detail
    },
    async addThread() {
      const epoch = this.epoch
      const thread = await createThread('新会话')
      this.threads.unshift(thread)
      if (epoch === this.epoch) await this.selectThread(thread.thread_id)
    },
    async ask(content: string) {
      const threadId = this.selectedId
      const epoch = this.epoch
      if (!threadId || !this.active) return null
      // 同Thread可并发提交；只有最新请求能刷新页面和取得Run观察权。
      const submission = ++this.submissionVersion
      const isCurrent = () => epoch === this.epoch && submission === this.submissionVersion
      const result = await sendMessage(threadId, content)
      if (!isCurrent()) return null
      await this.refresh(threadId, epoch, isCurrent)
      return isCurrent() ? result : null
    },
    invalidate() { this.epoch++; this.selectedId = null; this.active = null },
  },
})

