export type RunStatus = 'queued' | 'running' | 'retry_waiting' | 'succeeded' | 'failed' | 'cancelled'

export interface ThreadSummary {
  thread_id: string
  owner_id: string
  title: string
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  message_id: string
  thread_id: string
  seq: number
  role: 'user' | 'assistant'
  content: string
  status: string
  run_id: string | null
  citations: Citation[]
}

export interface Citation {
  document_id: string
  chunk_id: string
  filename: string
  start_offset: number
  end_offset: number
  score: number
}

export interface ThreadDetail {
  thread: ThreadSummary
  messages: Message[]
  runs: { run_id: string; status: RunStatus; created_at: string }[]
}

export interface RunDetail {
  run_id: string
  thread_id: string
  status: RunStatus
  user_message_id: string
  assistant_message_id: string | null
  task: { task_id: string; state: string; attempt: number; generation: number; worker_id: string | null }
  last_error_code: string | null
}

export interface RunEvent {
  schema_version: number
  event_id: string
  run_id: string
  seq: number
  type: string
  occurred_at: string
  data: Record<string, unknown>
}

export interface DocumentItem {
  document_id: string
  filename: string
  extension: string
  size_bytes: number
  content_hash: string
  status: string
  active_index_batch_id: string | null
  last_error_code: string | null
  created_at: string
  updated_at: string
}

