import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '../api/v3/rag'
import { ApiError, failureCode } from '../api/http'
import type { KnowledgeBase, RagProfile, RagSelection, RetrievalExecution } from '../types/api-v3'

export const useRagStore = defineStore('rag', () => {
  const bases = ref<KnowledgeBase[]>([]); const profiles = ref<RagProfile[]>([]); const selectedBase = ref(''); const enabled = ref(false)
  const profileKey = ref(''); const topK = ref(5); const rerank = ref(false); const radius = ref(1)
  const tags = ref(''); const documentIds = ref<string[] | null>(null); const extensions = ref<string[] | null>(null)
  const error = ref(''); const diagnostic = ref<RetrievalExecution | null>(null); const diagnosticPending = ref(false); const paused = ref(false)
  let epoch = 0; let timer: ReturnType<typeof setTimeout> | undefined; let pending: { key: string; body: Parameters<typeof api.createDiagnostic>[0] } | null = null
  const retrievalProfiles = computed(() => profiles.value.filter(p => p.kind === 'retrieval' && p.available))
  const embeddingProfiles = computed(() => profiles.value.filter(p => p.kind === 'embedding' && p.available))
  const selectedProfile = computed(() => retrievalProfiles.value.find(p => `${p.profile_id}@${p.version}` === profileKey.value))
  function filters() { return { tags_all: tags.value.split(',').map(s => s.trim()).filter(Boolean), ...(documentIds.value === null ? {} : { document_ids: [...documentIds.value] }), ...(extensions.value === null ? {} : { extensions: [...extensions.value] }) } }
  function validateSettings() {
    const allowed = ['.txt', '.md', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx']
    const currentFilters = filters()
    if (!selectedBase.value || !Number.isInteger(topK.value) || topK.value < 1 || topK.value > 20 || !Number.isInteger(radius.value) || radius.value < 0 || radius.value > 2 || currentFilters.tags_all.length > 20 || currentFilters.tags_all.some(tag => tag.length > 40) || (documentIds.value?.length ?? 0) > 1000 || extensions.value?.some(value => !allowed.includes(value))) {
      error.value = 'INVALID_RAG_PARAMETER：请检查知识库、Top-K（1～20）、邻近半径（0～2）及过滤范围'
      throw new Error('INVALID_RAG_PARAMETER')
    }
  }
  function selection(): RagSelection {
    if (!enabled.value) return { enabled: false }
    validateSettings()
    return { enabled: true, knowledge_base_id: selectedBase.value, retrieval_profile_id: selectedProfile.value?.profile_id, retrieval_profile_version: selectedProfile.value?.version, overrides: { top_k: topK.value, rerank_enabled: rerank.value, neighbor_radius: radius.value }, filters: filters() }
  }
  async function load() {
    error.value = ''
    try {
      const all: KnowledgeBase[] = []; let cursor: string | undefined
      for (let page = 0; page < 50; page++) { const result = await api.listBases(cursor); all.push(...result.items); if (!result.next_cursor) break; cursor = result.next_cursor }
      bases.value = all; profiles.value = (await api.listProfiles()).items
      if (!all.some(p => p.knowledge_base_id === selectedBase.value)) selectedBase.value = all.find(p => p.enabled && p.is_default)?.knowledge_base_id ?? all.find(p => p.enabled)?.knowledge_base_id ?? ''
      if (!selectedProfile.value) profileKey.value = retrievalProfiles.value[0] ? `${retrievalProfiles.value[0].profile_id}@${retrievalProfiles.value[0].version}` : ''
    } catch (cause) { error.value = `${failureCode(cause, 'RAG_CATALOG_READ_FAILED')}：知识库配置读取失败` }
  }
  async function create(name: string, profile: RagProfile) {
    try { const base = await api.createBase({ name, embedding_profile_id: profile.profile_id, embedding_profile_version: profile.version }, crypto.randomUUID()); await load(); selectedBase.value = base.knowledge_base_id }
    catch (cause) { error.value = `${failureCode(cause, 'KNOWLEDGE_BASE_CREATE_FAILED')}：无法创建知识库` }
  }
  async function update(body: { name?: string; enabled?: boolean }) {
    try { await api.patchBase(selectedBase.value, body); await load() } catch (cause) { error.value = `${failureCode(cause, 'KNOWLEDGE_BASE_UPDATE_FAILED')}：无法更新知识库` }
  }
  function stop() { epoch++; clearTimeout(timer); timer = undefined; diagnosticPending.value = false }
  function resetDiagnostic() { stop(); diagnostic.value = null; pending = null; paused.value = false }
  async function poll(expected: number, count = 0) {
    if (!diagnostic.value) return
    try { const result = await api.getExecution(diagnostic.value.execution_id); if (expected !== epoch) return; diagnostic.value = result; if (['succeeded', 'failed', 'cancelled'].includes(result.state)) { diagnosticPending.value = false; return } }
    catch (cause) { if (expected !== epoch) return; error.value = `${failureCode(cause, 'RETRIEVAL_READ_FAILED')}：诊断状态读取失败` }
    if (count >= 59) { paused.value = true; diagnosticPending.value = false; return }
    timer = setTimeout(() => void poll(expected, count + 1), 2000)
  }
  async function diagnose(query: string) {
    if (!pending) {
      try { validateSettings() } catch { return }
      if (!query.trim() || new TextEncoder().encode(query).length > 8192) { error.value = 'RETRIEVAL_QUERY_TOO_LONG：问题不能为空且不能超过8192 UTF-8字节'; return }
    }
    stop(); const expected = epoch; error.value = ''; diagnosticPending.value = true; paused.value = false
    pending ??= { key: crypto.randomUUID(), body: { query, knowledge_base_id: selectedBase.value, retrieval_profile_id: selectedProfile.value?.profile_id, retrieval_profile_version: selectedProfile.value?.version, overrides: { top_k: topK.value, rerank_enabled: rerank.value, neighbor_radius: radius.value }, filters: filters() } }
    try { const result = await api.createDiagnostic(pending.body, pending.key); if (expected !== epoch) return; pending = null; diagnostic.value = result; await poll(expected) }
    catch (cause) { if (expected === epoch) {
      diagnosticPending.value = false
      const rejected = cause instanceof ApiError && cause.status >= 400 && cause.status < 500
      if (rejected) pending = null
      error.value = `${failureCode(cause, 'RETRIEVAL_CREATE_FAILED')}：${rejected ? '诊断被拒绝，请修改参数后重新提交' : '诊断提交未确认；再次提交将重放原参数'}`
    } }
  }
  async function refreshDiagnostic() { stop(); paused.value = false; await poll(epoch) }
  async function cancel() { if (diagnostic.value) { await api.cancelDiagnostic(diagnostic.value.execution_id); await refreshDiagnostic() } }
  return { bases, profiles, selectedBase, enabled, profileKey, topK, rerank, radius, tags, documentIds, extensions, error, diagnostic, diagnosticPending, paused, retrievalProfiles, embeddingProfiles, selection, load, create, update, diagnose, refreshDiagnostic, cancel, stop, resetDiagnostic }
})
