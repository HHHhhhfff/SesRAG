import { ref } from 'vue'
import { defineStore } from 'pinia'
import { listDocuments, uploadDocument } from '../api/documents'
import { failureCode } from '../api/http'
import type { DocumentItem } from '../types/api'

export const useDocumentStore = defineStore('documents', () => {
  const items = ref<DocumentItem[]>([])
  const loading = ref(false)
  const error = ref('')
  const paused = ref(false)
  let epoch = 0
  let attempts = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  function stop() { epoch++; clearTimeout(timer); timer = undefined; loading.value = false }
  async function poll(expectedEpoch: number) {
    try {
      const response = await listDocuments()
      if (epoch !== expectedEpoch) return
      items.value = response.documents; error.value = ''
      if (!items.value.some(item => !['indexed', 'failed', 'cancelled'].includes(item.status))) return
    } catch (cause) {
      if (epoch !== expectedEpoch) return
      error.value = `${failureCode(cause, 'DOCUMENT_REFRESH_FAILED')}：无法读取索引事实`
    }
    if (++attempts >= 30) { paused.value = true; return }
    timer = setTimeout(() => { void poll(expectedEpoch) }, 2000)
  }
  async function load() {
    stop(); attempts = 0; paused.value = false
    await poll(epoch)
  }
  async function upload(file: File) {
    loading.value = true; error.value = ''
    const expectedEpoch = epoch
    try {
      await uploadDocument(file)
      if (epoch === expectedEpoch) await load()
    } catch (cause) {
      if (epoch === expectedEpoch) error.value = `${failureCode(cause, 'DOCUMENT_UPLOAD_FAILED')}：文档上传失败，请重试`
    } finally { if (epoch === expectedEpoch || epoch === expectedEpoch + 1) loading.value = false }
  }
  return { items, loading, error, paused, load, upload, stop }
})

