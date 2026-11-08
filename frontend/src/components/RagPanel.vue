<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRagStore } from '../stores/rag'
import EvidenceViewer from './EvidenceViewer.vue'
import { ragLabel } from './rag-labels'
const rag = useRagStore(); const name = ref(''); const embedding = ref(''); const query = ref(''); const rename = ref('')
watch(() => rag.selectedBase, () => { rag.documentIds = null; rag.extensions = null; rag.resetDiagnostic(); rename.value = rag.bases.find(p => p.knowledge_base_id === rag.selectedBase)?.name ?? '' })
function create() { const profile = rag.embeddingProfiles.find(p => `${p.profile_id}@${p.version}` === embedding.value); if (profile && name.value.trim()) void rag.create(name.value, profile) }
</script>
<template>
  <section class="rag-panel">
    <h3>知识库与 RAG</h3>
    <p v-if="rag.error" role="alert">{{ rag.error }}</p>
    <label>当前知识库<select v-model="rag.selectedBase" aria-label="当前知识库"><option value="">请选择</option><option v-for="base in rag.bases" :key="base.knowledge_base_id" :value="base.knowledge_base_id">{{ base.name }}{{ base.enabled ? '' : '（停用）' }}</option></select></label>
    <p v-if="rag.selectedBase">空间 {{ rag.bases.find(p => p.knowledge_base_id === rag.selectedBase)?.embedding_space_id }}</p>
    <details><summary>管理知识库</summary>
      <form class="rag-form" @submit.prevent="create"><input v-model="name" aria-label="新知识库名称" placeholder="新知识库名称" maxlength="80" required><select v-model="embedding" aria-label="向量配置" required><option value="">选择独立向量空间</option><option v-for="profile in rag.embeddingProfiles" :key="`${profile.profile_id}@${profile.version}`" :value="`${profile.profile_id}@${profile.version}`">{{ profile.profile_id }} v{{ profile.version }} · {{ profile.dimension }}维</option></select><button class="secondary-button">创建知识库</button></form>
      <form v-if="rag.selectedBase" class="rag-form" @submit.prevent="rag.update({name:rename})"><input v-model="rename" aria-label="知识库新名称" maxlength="80" required><button class="secondary-button">重命名</button><button type="button" class="secondary-button" @click="rag.update({enabled: !rag.bases.find(p => p.knowledge_base_id === rag.selectedBase)?.enabled})">切换启停</button></form>
    </details>
    <label><input v-model="rag.enabled" type="checkbox">后续新消息启用 RAG</label>
    <label>检索策略<select v-model="rag.profileKey"><option v-for="profile in rag.retrievalProfiles" :key="`${profile.profile_id}@${profile.version}`" :value="`${profile.profile_id}@${profile.version}`">{{ profile.profile_id }} v{{ profile.version }}</option></select></label>
    <div class="rag-form"><label>Top-K<input v-model.number="rag.topK" type="number" min="1" max="20"></label><label><input v-model="rag.rerank" type="checkbox">重排</label><label>邻近半径<input v-model.number="rag.radius" type="number" min="0" max="2"></label><label>必须同时含标签（逗号分隔）<input v-model="rag.tags" maxlength="819"></label></div>
    <p>以上设置只影响后续新 Run；重试和重新生成沿用原配置与语料视图。关闭 RAG 时不调用检索依赖。</p>
    <details><summary>过滤范围</summary><label>文档 ID（留空表示不限；勾选空范围表示没有文档）<input :value="rag.documentIds?.join(',') ?? ''" @change="rag.documentIds = ($event.target as HTMLInputElement).value.trim() ? ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()) : null"></label><label><input :checked="rag.documentIds?.length === 0" type="checkbox" @change="rag.documentIds = ($event.target as HTMLInputElement).checked ? [] : null">显式空文档范围</label><label>类型（如 .md,.pdf，留空不限）<input :value="rag.extensions?.join(',') ?? ''" @change="rag.extensions = ($event.target as HTMLInputElement).value.trim() ? ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()) : null"></label></details>
    <details><summary>可用配置及原因</summary><p v-for="profile in rag.profiles" :key="`${profile.kind}:${profile.profile_id}@${profile.version}`">{{ profile.kind }} · {{ profile.profile_id }} v{{ profile.version }} · {{ profile.available ? '可用' : profile.unavailable_reason }}</p></details>
    <h4>只检索诊断</h4><form class="rag-form" @submit.prevent="rag.diagnose(query)"><input v-model="query" aria-label="诊断查询" maxlength="8192" required placeholder="不创建聊天消息或调用生成模型"><button class="secondary-button" :disabled="!rag.selectedBase || rag.diagnosticPending">执行诊断</button></form>
    <template v-if="rag.diagnostic"><p>{{ ragLabel(rag.diagnostic.state) }} / {{ ragLabel(rag.diagnostic.stage) }} · {{ rag.diagnostic.mode ? ragLabel(rag.diagnostic.mode) : '执行中' }}</p><p v-if="rag.diagnostic.error_code" role="alert">{{ rag.diagnostic.error_code }}</p><p v-if="rag.diagnostic.mode === 'empty'">当前范围无可用证据。</p><p v-if="rag.diagnostic.mode === 'degraded'">重排失败，按已冻结的降级策略使用向量排序。</p><button class="secondary-button" @click="rag.refreshDiagnostic">刷新诊断</button><button v-if="!['succeeded','failed','cancelled'].includes(rag.diagnostic.state)" class="secondary-button" @click="rag.cancel">请求取消</button><p v-if="rag.paused">自动轮询已暂停，可手动刷新。</p>
      <p v-for="candidate in rag.diagnostic.candidates" :key="candidate.chunk_id">{{ candidate.chunk_id }} · dense {{ candidate.dense_score }} · rerank {{ candidate.rerank_score ?? '无' }}</p><p v-for="item in rag.diagnostic.omitted" :key="item.chunk_id">移除 {{ item.chunk_id }}：{{ item.reason }}</p>
      <details v-for="bundle in rag.diagnostic.bundle_ids" :key="bundle"><summary>证据 {{ bundle }}</summary><EvidenceViewer :bundle-id="bundle" /></details>
    </template>
  </section>
</template>
