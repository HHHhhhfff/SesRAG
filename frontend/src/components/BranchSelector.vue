<script setup lang="ts">
import type { Branch } from '../types/api-v2'
defineProps<{ branches: Branch[]; modelValue?: string | null; readonly?: boolean }>()
const emit = defineEmits<{ change: [string] }>()
</script>
<template>
  <label class="compact-control">分支
    <select
      :value="modelValue ?? ''"
      :disabled="readonly"
      @change="emit('change', ($event.target as HTMLSelectElement).value)"
    >
      <option
        v-for="branch in branches"
        :key="branch.branch_id"
        :value="branch.branch_id"
      >{{ branch.name }}{{ branch.is_default ? '（默认）' : '' }}</option>
    </select>
  </label>
</template>
