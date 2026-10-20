<script setup lang="ts">
import type { ModelProfile } from '../types/api-v2'
defineProps<{ models: ModelProfile[]; selected?: { profile_id: string; version: number } | null; disabled?: boolean }>()
const emit = defineEmits<{ change: [{ profile_id: string; version: number }] }>()
function changed(event: Event) {
  const [profile_id, version] = (event.target as HTMLSelectElement).value.split(':')
  emit('change', { profile_id, version: Number(version) })
}
</script>
<template>
  <label class="compact-control">模型
    <select
      :value="selected ? `${selected.profile_id}:${selected.version}` : ''"
      :disabled="disabled"
      @change="changed"
    >
      <option
        v-for="model in models"
        :key="`${model.profile_id}:${model.version}`"
        :value="`${model.profile_id}:${model.version}`"
        :disabled="model.status !== 'enabled'"
      >{{ model.display_name }}{{ model.status !== 'enabled' ? `（${model.reason ?? '不可用'}）` : '' }}</option>
    </select>
  </label>
</template>
