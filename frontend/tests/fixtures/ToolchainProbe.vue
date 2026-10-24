<script setup lang="ts">
defineProps<{ label: string }>()
const emit = defineEmits<{ action: [string] }>()
</script>

<template>
  <button type="button" @click="emit('action', label)">{{ label }}</button>
</template>
