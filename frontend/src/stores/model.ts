import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { listModels } from '../api/v2/models'
import type { ModelProfile, ModelProfileKey } from '../types/api-v2'

export const useModelStore = defineStore('model', () => {
  const models = ref<ModelProfile[]>([])
  const defaultProfile = ref<ModelProfileKey | null>(null)
  const selected = ref<ModelProfileKey | null>(null)
  const selectionRevision = ref(0)
  const loading = ref(false)
  const error = ref('')
  const available = computed(() => models.value.filter(item => item.status === 'enabled'))
  async function load() {
    loading.value = true; error.value = ''
    try {
      const result = await listModels(); models.value = result.models; defaultProfile.value = result.default_profile
      const saved = (() => { try { return JSON.parse(localStorage.getItem('sesrag.selectedModel') ?? 'null') as ModelProfileKey | null } catch { return null } })()
      const wanted = saved ?? result.default_profile
      selected.value = result.models.some(item => item.profile_id === wanted.profile_id && item.version === wanted.version && item.status === 'enabled') ? wanted : result.default_profile
    } catch { error.value = 'MODEL_LIST_FAILED：无法读取模型列表' } finally { loading.value = false }
  }
  function select(profile: ModelProfileKey) {
    if (!models.value.some(item => item.profile_id === profile.profile_id && item.version === profile.version && item.status === 'enabled')) return false
    selected.value = profile
    selectionRevision.value++
    try { localStorage.setItem('sesrag.selectedModel', JSON.stringify(profile)) } catch { /* 偏好不可持久化时不影响提交。 */ }
    return true
  }
  return { models, available, defaultProfile, selected, selectionRevision, loading, error, load, select }
})
