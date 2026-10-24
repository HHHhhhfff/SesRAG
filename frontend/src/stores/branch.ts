import { computed } from 'vue'
import { defineStore } from 'pinia'
import { useThreadStore } from './thread'

export const useBranchStore = defineStore('branch', () => {
  const thread = useThreadStore()
  const branches = computed(() => thread.branches)
  const selectedId = computed(() => thread.selectedBranchId)
  async function select(branchId: string) { if (branches.value.some(item => item.branch_id === branchId)) await thread.selectBranch(branchId) }
  return { branches, selectedId, select }
})
