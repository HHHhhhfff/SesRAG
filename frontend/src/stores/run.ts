import { defineStore } from 'pinia'
import { cancelRun, getRun } from '../api/runs'
import { replayEvents } from '../events/run-event-stream'
import type { RunDetail, RunEvent } from '../types/api'

export const useRunStore = defineStore('run', {
  state: () => ({ current: null as RunDetail | null, events: [] as RunEvent[], connected: false }),
  actions: {
    async observe(runId: string) {
      this.current = await getRun(runId)
      this.events = []
      await replayEvents(runId, 0, (event) => this.append(event))
      this.current = await getRun(runId)
    },
    append(event: RunEvent) {
      if (this.events.some((item) => item.seq === event.seq)) return
      this.events.push(event)
      this.events.sort((left, right) => left.seq - right.seq)
    },
    async cancel() {
      if (this.current) this.current.status = (await cancelRun(this.current.run_id)).status as RunDetail['status']
    },
  },
})

