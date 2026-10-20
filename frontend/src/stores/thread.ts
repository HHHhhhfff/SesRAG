import { defineStore } from 'pinia'
import { ApiError } from '../api/http'
import { createBranch, createIdempotencyKey, createThread, getThread, listBranches, listThreads, patchThread, sendMessage } from '../api/v2/threads'
import type { Branch, ThreadDetail, ThreadSummary } from '../types/api-v2'
import type { BranchCreate, MessageCreate } from '../types/api-v2'

const readIdentity = (key: string) => { try { const value = localStorage.getItem(key); return value || null } catch { return null } }
const writeIdentity = (key: string, value: string | null) => { try { if (value) localStorage.setItem(key, value); else localStorage.removeItem(key) } catch { /* 隐私模式不可用时仅保留内存状态。 */ } }

export const useThreadStore = defineStore('thread', {
  state: () => ({ threads: [] as ThreadSummary[], branches: [] as Branch[], active: null as ThreadDetail | null, loading: false, loadingOlder: false, epoch: 0, submissionVersion: 0, selectedId: readIdentity('sesrag.selectedThreadId'), selectedBranchId: readIdentity('sesrag.selectedBranchId'), nextCursor: null as string | null, hasMore: false, error: '', pendingMessage: null as { key: string; threadId: string; payload: MessageCreate } | null, pendingFork: null as { key: string; threadId: string; payload: BranchCreate } | null }),
  actions: {
    mergeSummary(thread: ThreadSummary) {
      this.threads = [...this.threads.filter(item => item.thread_id !== thread.thread_id), thread]
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at) || b.thread_id.localeCompare(a.thread_id))
    },
    async loadThreads() {
      const epoch = this.epoch
      const page = await listThreads({ limit: 100, include_archived: true })
      if (epoch !== this.epoch) return
      this.threads = page.threads; this.nextCursor = page.next_cursor; this.hasMore = page.has_more
      let preferred = this.threads.find(thread => thread.thread_id === this.selectedId)
      if (!preferred && this.selectedId) {
        try {
          const saved = await getThread(this.selectedId)
          if (epoch !== this.epoch) return
          preferred = saved.thread
          this.threads.push(saved.thread)
        } catch (cause) {
          if (!(cause instanceof ApiError) || cause.code !== 'THREAD_NOT_FOUND') throw cause
        }
      }
      if (epoch !== this.epoch) return
      const next = preferred ?? this.threads.find(thread => !thread.archived_at)
      if (next) await this.selectThread(next.thread_id, this.selectedBranchId ?? undefined)
      else { this.selectedId = null; this.active = null; this.branches = [] }
    },
    async loadMoreThreads() {
      if (!this.hasMore || !this.nextCursor) return
      const epoch = this.epoch; const page = await listThreads({ limit: 100, cursor: this.nextCursor, include_archived: true })
      if (epoch === this.epoch) { this.threads.push(...page.threads.filter(item => !this.threads.some(row => row.thread_id === item.thread_id))); this.nextCursor = page.next_cursor; this.hasMore = page.has_more }
    },
    async selectThread(threadId: string, requestedBranch?: string) {
      const epoch = ++this.epoch
      this.selectedId = threadId; this.active = null; this.branches = []; this.loading = true; this.loadingOlder = false; this.error = ''; this.pendingMessage = null
      writeIdentity('sesrag.selectedThreadId', threadId)
      try {
        let detail = await getThread(threadId)
        if (epoch !== this.epoch) return
        const branches = (await listBranches(threadId)).branches
        if (epoch !== this.epoch) return
        this.branches = branches
        const branch = branches.find(item => item.branch_id === (requestedBranch ?? this.selectedBranchId)) ?? branches.find(item => item.is_default) ?? detail.branch
        if (branch.branch_id !== detail.branch.branch_id) detail = await getThread(threadId, { branch_id: branch.branch_id })
        if (epoch !== this.epoch) return
        this.active = detail; this.selectedBranchId = detail.branch.branch_id
        writeIdentity('sesrag.selectedBranchId', this.selectedBranchId)
      } finally { if (epoch === this.epoch) this.loading = false }
    },
    async selectBranch(branchId: string) { const threadId = this.selectedId; if (threadId) await this.selectThread(threadId, branchId) },
    async refresh(threadId: string, branchId: string, epoch?: number, isCurrent: () => boolean = () => true) {
      const expectedEpoch = epoch ?? this.epoch
      const detail = await getThread(threadId, { branch_id: branchId })
      if (expectedEpoch === this.epoch && threadId === this.selectedId && branchId === this.selectedBranchId && isCurrent()) { this.active = detail; this.mergeSummary(detail.thread) }
    },
    async addThread() {
      const epoch = this.epoch
      const thread = await createThread()
      if (!this.threads.some(item => item.thread_id === thread.thread_id)) this.threads.unshift(thread)
      if (epoch === this.epoch) await this.selectThread(thread.thread_id)
    },
    async rename(title: string) { if (!this.selectedId || !title.trim()) return; const id = this.selectedId; const epoch = this.epoch; const updated = await patchThread(id, { title: title.trim() }); if (epoch !== this.epoch || id !== this.selectedId) return; this.mergeSummary(updated); if (this.active) this.active.thread = updated },
    async setArchived(archived: boolean) { if (!this.selectedId) return; const id = this.selectedId; const epoch = this.epoch; const updated = await patchThread(id, { archived }); if (epoch !== this.epoch || id !== this.selectedId) return; this.mergeSummary(updated); if (this.active) this.active.thread = updated },
    async loadOlder() {
      const detail = this.active
      if (this.loadingOlder || !detail?.has_more || detail.next_before_seq === null) return
      const epoch = this.epoch; const threadId = detail.thread.thread_id; const branchId = detail.branch.branch_id; const beforeSeq = detail.next_before_seq
      this.loadingOlder = true
      try {
        const page = await getThread(threadId, { branch_id: branchId, before_seq: beforeSeq })
        if (epoch !== this.epoch || this.active?.branch.branch_id !== branchId) return
        const current = this.active
        const messages = [...new Map([...page.messages, ...current.messages].map(item => [item.message_id, item])).values()]
        const runs = [...new Map([...page.runs, ...current.runs].map(item => [item.run_id, item])).values()]
        const metadataFresh = current === detail
        this.active = { ...current, messages, runs, ...(metadataFresh ? { has_more: page.has_more, next_before_seq: page.next_before_seq } : {}) }
      } finally { if (epoch === this.epoch) this.loadingOlder = false }
    },
    async forkFrom(messageId: string, name?: string) {
      const detail = this.active; const epoch = this.epoch
      if (!detail || detail.thread.archived_at) return
      const payload = { parent_branch_id: detail.branch.branch_id, fork_message_id: messageId, ...(name ? { name } : {}) }
      const old = this.pendingFork
      const pending = old && old.threadId === detail.thread.thread_id && JSON.stringify(old.payload) === JSON.stringify(payload) ? old : { key: createIdempotencyKey(), threadId: detail.thread.thread_id, payload }
      this.pendingFork = pending
      const branch = await createBranch(pending.threadId, pending.payload, pending.key)
      if (epoch === this.epoch && detail.branch.branch_id === this.selectedBranchId) { this.pendingFork = null; await this.selectThread(detail.thread.thread_id, branch.branch_id) }
    },
    async ask(content: string, profile?: { profile_id: string; version: number }) {
      const detail = this.active; const epoch = this.epoch
      if (!detail || detail.thread.archived_at || !content.trim() || content.trim().length > 20000) return null
      const submission = ++this.submissionVersion; const branchId = detail.branch.branch_id
      const isCurrent = () => epoch === this.epoch && submission === this.submissionVersion && branchId === this.selectedBranchId
      const payload: MessageCreate = { branch_id: branchId, content: content.trim(), expected_version: detail.branch.version, ...(profile ? { model_profile_id: profile.profile_id, model_profile_version: profile.version } : {}) }
      const old = this.pendingMessage
      const pending = old && old.threadId === detail.thread.thread_id && JSON.stringify(old.payload) === JSON.stringify(payload) ? old : { key: createIdempotencyKey(), threadId: detail.thread.thread_id, payload }
      this.pendingMessage = pending
      const result = await sendMessage(pending.threadId, pending.payload, pending.key)
      if (!isCurrent()) return null
      this.pendingMessage = null
      await this.refresh(detail.thread.thread_id, branchId, epoch, isCurrent)
      return isCurrent() ? { ...result, thread_id: detail.thread.thread_id, branch_id: branchId, epoch } : null
    },
    async retryPendingMessage() {
      const pending = this.pendingMessage; if (!pending) return null
      const epoch = this.epoch; const result = await sendMessage(pending.threadId, pending.payload, pending.key)
      if (epoch !== this.epoch || pending.threadId !== this.selectedId || pending.payload.branch_id !== this.selectedBranchId) return null
      this.pendingMessage = null
      await this.refresh(pending.threadId, pending.payload.branch_id, epoch)
      return result
    },
    invalidate() { this.epoch++; this.selectedId = null; this.selectedBranchId = null; this.active = null; this.branches = []; this.nextCursor = null; this.hasMore = false; this.loadingOlder = false },
  },
})
