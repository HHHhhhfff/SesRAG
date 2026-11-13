<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { getBundle } from '../api/v3/rag'
import { failureCode } from '../api/http'
import type { EvidenceBundle } from '../types/api-v3'
const props = defineProps<{ bundleId: string }>()
const bundle = ref<EvidenceBundle | null>(null); const text = ref(''); const error = ref(''); const loading = ref(false); let epoch = 0
async function load(more = false) {
  const expected = epoch; const id = props.bundleId; loading.value = true
  try { const result = await getBundle(id, more ? bundle.value?.next_offset ?? 0 : 0); if (epoch !== expected) return; bundle.value = result; text.value = more ? text.value + result.text : result.text; error.value = '' }
  catch (cause) { if (epoch === expected) error.value = `${failureCode(cause, 'EVIDENCE_READ_FAILED')}：证据不可读取` }
  finally { if (epoch === expected) loading.value = false }
}
watch(() => props.bundleId, () => { epoch++; bundle.value = null; text.value = ''; void load() }, { immediate: true })
onUnmounted(() => epoch++)
</script>
<template>
  <div class="evidence-viewer">
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="bundle">
      <p>文档 {{ bundle.document_id }} · 批次 {{ bundle.index_batch_id }} · 证据 {{ bundle.bundle_id }}</p>
      <p>向量分数 {{ bundle.dense_score }} · 重排 {{ bundle.rerank_score ?? '未重排' }}</p>
      <pre>{{ text }}</pre>
      <p v-for="location, index in bundle.locations" :key="index">{{ location.origin === 'source' ? '原文' : '归一化文本' }} · {{ location.kind }} {{ location.number ?? location.block_id ?? '' }} · {{ location.start_offset }}–{{ location.end_offset }} · {{ location.quality }}</p>
      <p v-if="!bundle.locations.length || bundle.locations.every(p => p.quality === 'block_only')">未提供可可靠映射的原页、幻灯片或单元格位置。</p>
      <details><summary>来源组件与内容 hash</summary><p v-for="component in bundle.components" :key="component.component_id">{{ component.chunk_id }} · {{ component.start_offset }}–{{ component.end_offset }} · {{ component.content_hash }}</p></details>
      <button v-if="bundle.next_offset !== null" class="secondary-button" :disabled="loading" @click="load(true)">继续读取证据</button>
    </template>
  </div>
</template>
