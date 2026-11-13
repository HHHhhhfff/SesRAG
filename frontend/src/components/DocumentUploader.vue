<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDocumentStore } from '../stores/documents'
import { useRagStore } from '../stores/rag'
import type { Document, ParseRequest } from '../types/api-v3'
import { ragLabel } from './rag-labels'
const documents = useDocumentStore(); const rag = useRagStore()
const file = ref<File | null>(null); const rebuilding = ref<Document | null>(null); const consent = ref(false); const duplicate = ref(false); const tags = ref(''); const localError = ref('')
const extension = computed(() => (file.value?.name ?? rebuilding.value?.filename ?? '').slice((file.value?.name ?? rebuilding.value?.filename ?? '').lastIndexOf('.')).toLowerCase())
const office = computed(() => !['.txt', '.md'].includes(extension.value))
const cloudReady = computed(() => rag.profiles.some(p => p.kind === 'parser' && p.available && p.verified_formats?.includes(extension.value)))
function reset() { file.value = null; rebuilding.value = null; consent.value = false; duplicate.value = false; localError.value = '' }
watch(() => rag.selectedBase, reset)
function select(event: Event) {
  reset(); const input = event.target as HTMLInputElement; file.value = input.files?.[0] ?? null; input.value = ''
  if (file.value && (!file.value.size || file.value.size > 10 * 1024 * 1024)) { localError.value = '文件必须大于 0 且不超过 10 MiB'; file.value = null }
}
async function submit() {
  if (office.value && (!consent.value || !cloudReady.value)) return
  const parse: ParseRequest = office.value ? { cloud_consent: true, consent_version: 'mineru-office-outbound-v1', acknowledge_duplicate_cost: duplicate.value } : {}
  if (rebuilding.value) await documents.rebuild(rebuilding.value, parse)
  else if (file.value) await documents.upload(file.value, parse, tags.value.split(',').map(s => s.trim()).filter(Boolean))
  reset()
}
</script>
<template>
  <section class="document-panel">
    <h3>文档与索引</h3>
    <p>txt/md 本地解析；doc/docx/pdf/xls/xlsx/ppt/pptx 使用 MinerU，失败不回退。单文件 ≤10 MiB。</p>
    <input type="file" aria-label="选择文档" accept=".txt,.md,.doc,.docx,.pdf,.xls,.xlsx,.ppt,.pptx" :disabled="documents.loading || !rag.selectedBase || documents.pendingUpload" @change="select">
    <p v-if="documents.error || localError" role="alert">{{ documents.error || localError }}</p>
    <button v-if="documents.pendingUpload" class="secondary-button" @click="documents.retryUpload">重试原上传（同一幂等键）</button>
    <template v-if="documents.pendingRebuild">
      <p>重建尚未确认；请先恢复原操作。{{ documents.canRetryRebuild ? '' : '请切回原知识库。' }}</p>
      <button class="secondary-button" :disabled="documents.loading || !documents.canRetryRebuild" @click="documents.retryRebuild">重试原重建（同一幂等键）</button>
    </template>
    <form v-if="file || rebuilding" class="rag-form" @submit.prevent="submit">
      <strong>{{ rebuilding ? '重建' : '上传' }}：{{ file?.name ?? rebuilding?.filename }}</strong>
      <label v-if="file">标签（英文逗号分隔）<input v-model="tags" maxlength="819"></label>
      <template v-if="office">
        <p v-if="!cloudReady" role="alert">该格式的 MinerU 能力尚未配置或验证，当前无法提交。</p>
        <label><input v-model="consent" type="checkbox">我同意本次将完整原件（含隐藏内容、元数据及图片）发送到 MinerU。失败不回退。</label>
        <label v-if="rebuilding?.latest_build?.parse?.remote_outcome === 'unknown_may_continue'"><input v-model="duplicate" type="checkbox">前次云端任务可能仍在处理，我接受本次新操作可能重复计费。</label>
      </template>
      <p v-else>此文本仅在本地解析，不发送到 MinerU。</p>
      <button class="secondary-button" :disabled="documents.loading || (office && (!consent || !cloudReady))">提交本次操作</button>
      <button type="button" class="secondary-button" @click="reset">取消</button>
    </form>
    <p v-if="documents.paused">自动刷新已暂停；服务端任务仍由其自身状态控制。</p>
    <button class="secondary-button" @click="documents.load">刷新索引状态</button>
    <article v-for="document in documents.items" :key="document.document_id" class="document-item">
      <strong>{{ document.filename }}</strong><p>可用性：{{ ragLabel(document.availability) }} · 当前批次 {{ document.active_index_batch_id ?? '无' }}</p>
      <p v-if="document.latest_build">最新构建：{{ ragLabel(document.latest_build.state) }} / {{ ragLabel(document.latest_build.stage) }} · 切片 {{ document.latest_build.chunk_count }}</p>
      <p v-if="document.latest_build?.parse">解析：{{ document.latest_build.parse.parser_kind === 'local' ? '本地文本' : 'MinerU云端' }} / {{ ragLabel(document.latest_build.parse.stage) }} · 进度未提供时为未知</p>
      <p v-if="document.latest_build?.error_code" role="alert">{{ document.latest_build.error_code }}：构建失败，已有可用批次保留。</p>
      <p v-if="document.latest_build?.parse?.remote_outcome === 'unknown_may_continue'">本地已停止；远端可能继续处理。取消不保证撤回文件或计费。</p>
      <p>标签：{{ document.tags.join('，') || '无' }}</p>
      <label>更新标签<input :value="document.tags.join(',')" maxlength="819" @change="documents.tags(document.document_id, ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean))"></label>
      <button class="secondary-button" :disabled="documents.loading || documents.pendingRebuild" @click="reset(); rebuilding = document">重建索引</button>
      <button v-if="document.latest_build && ['queued','building','waiting'].includes(document.latest_build.state)" class="secondary-button" @click="documents.cancel(document.latest_build!.index_batch_id)">请求取消构建</button>
      <button v-if="document.active_index_batch_id" class="secondary-button" @click="documents.inspect(document)">查看已发布切片</button>
    </article>
    <button v-if="documents.cursor" class="secondary-button" @click="documents.more">加载更多文档</button>
    <details v-if="documents.inspected" open>
      <summary>{{ documents.inspected.filename }} · 已发布切片</summary>
      <article v-for="chunk in documents.chunks" :key="chunk.chunk_id"><p>{{ chunk.chunk_id }} · {{ chunk.start_offset }}–{{ chunk.end_offset }}</p><pre>{{ chunk.text }}</pre><p>来源位置 {{ chunk.locations.length ? JSON.stringify(chunk.locations) : '未提供' }}</p></article>
      <button v-if="documents.chunkCursor" class="secondary-button" @click="documents.inspect(documents.inspected!, true)">更多切片</button>
    </details>
  </section>
</template>
