// 自动生成自 contracts/*_v1.json；请运行 npm run generate:api，勿手工修改。

export type ThreadSummary = { "thread_id": string; "owner_id": string; "title": string; "archived_at": string | null; "created_at": string; "updated_at": string }

export type Message = { "message_id": string; "thread_id": string; "seq": number; "role": "user" | "assistant"; "source": "user_input" | "assistant_generation"; "content": string; "status": string; "run_id": string | null; "citations": Array<Citation>; "created_at": string }

export type Citation = (Evidence) | ({ "document_id": string; "chunk_id": string; "filename": string; "start_offset": number; "end_offset": number; "score": number })

export type Evidence = { "document_id": string; "chunk_id": string; "index_batch_id": string; "filename": string; "start_offset": number; "end_offset": number; "score": number; "locations": Array<{ "kind": "line" | "paragraph"; "number": number; "start_offset": number; "end_offset": number }> }

export type DocumentItem = { "document_id": string; "filename": string; "source": "local_upload"; "extension": string; "size_bytes": number; "content_hash": string; "status": string; "active_index_batch_id": string | null; "last_error_code": string | null; "created_at": string; "updated_at": string }

export type RunDetail = { "run_id": string; "thread_id": string; "status": RunStatus; "user_message_id": string; "assistant_message_id": string | null; "task": TaskSummary; "last_error_code": string | null }

export type RunStatus = "queued" | "running" | "retry_waiting" | "succeeded" | "failed" | "cancelled"

export type TaskSummary = { "task_id": string; "kind": "run"; "state": "queued" | "leased" | "running" | "retry_waiting" | "succeeded" | "failed" | "cancelled"; "attempt": number; "worker_id": string | null; "generation": number; "lease_expires_at": string | null; "last_error_code": string | null }

export type RunEvent = (EventEnvelope) & (({ "type": "run.created"; "data": { "message_id": string }; [key: string]: unknown }) | ({ "type": "task.queued"; "data": { "task_id": string }; [key: string]: unknown }) | ({ "type": "task.leased"; "data": { "task_id": string; "worker_id": string; "generation": number; "attempt": number }; [key: string]: unknown }) | ({ "type": "run.started"; "data": { "task_id": string }; [key: string]: unknown }) | ({ "type": "retrieval.completed"; "data": { "count": number; "items": Array<RetrievalItem> }; [key: string]: unknown }) | ({ "type": "answer.delta"; "data": { "text": string }; [key: string]: unknown }) | ({ "type": "task.retry_scheduled"; "data": { "error_code": string; "attempt": number }; [key: string]: unknown }) | ({ "type": "message.completed"; "data": { "message_id": string; "citations": Array<Citation> }; [key: string]: unknown }) | ({ "type": "run.succeeded"; "data": { "message_id": string }; [key: string]: unknown }) | ({ "type": "run.failed"; "data": { "error_code": string; "attempt": number }; [key: string]: unknown }) | ({ "type": "run.cancelled"; "data": { "reason": "user_requested" }; [key: string]: unknown }))

export type EventEnvelope = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.created" | "task.queued" | "task.leased" | "run.started" | "retrieval.completed" | "answer.delta" | "task.retry_scheduled" | "message.completed" | "run.succeeded" | "run.failed" | "run.cancelled"; "occurred_at": string; "data": { [key: string]: unknown } }

export type RetrievalItem = { "document_id": string; "chunk_id": string; "index_batch_id": string; "locations": Array<{ "kind": "line" | "paragraph"; "number": number; "start_offset": number; "end_offset": number }>; "start_offset": number; "end_offset": number; "score": number }

export type HealthReady = { "status": "ok" | "degraded" | "unavailable"; "database": "ready" | "unavailable"; "redis": "ready" | "degraded"; "worker": "ready" | "unknown"; "worker_count": number; "code"?: "DATABASE_UNAVAILABLE" }

export type ThreadList = Array<ThreadSummary>

export type ThreadDetail = { "thread": ThreadSummary; "messages": Array<Message>; "runs": Array<{ "run_id": string; "status": RunStatus; "created_at": string }> }

export type MessageRunResponse = { "message_id": string; "run_id": string; "task_id": string; "status": RunStatus }

export type ArchiveResponse = { "thread_id": string; "archived": true }

export type CancelResponse = { "run_id": string; "status": RunStatus }

export type EventListResponse = { "events": Array<RunEvent> }

export type DocumentListResponse = { "documents": Array<DocumentItem> }

export type IndexResponse = { "task_id": string; "document_id": string; "state": string }

export type HealthLive = { "status": "ok" }

export type ErrorResponse = { "code": string; "message": string }

export type ValidationErrorResponse = { "detail": Array<{ "type": string; "loc": Array<string | number>; "msg": "请求参数校验失败" }> }
