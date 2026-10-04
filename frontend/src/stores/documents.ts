import { defineStore } from 'pinia'
import { listDocuments, uploadDocument } from '../api/documents'
import type { DocumentItem } from '../types/api'

export const useDocumentStore = defineStore('documents', {
  state: () => ({ items: [] as DocumentItem[], loading: false }),
  actions: {
    async load() {
      this.items = (await listDocuments()).documents
    },
    async upload(file: File) {
      this.loading = true
      try {
        const item = await uploadDocument(file)
        this.items.unshift(item)
      } finally {
        this.loading = false
      }
    },
  },
})

