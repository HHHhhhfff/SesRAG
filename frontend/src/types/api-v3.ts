// 自动生成自 contracts/*_v3.json；请运行 npm run generate:api，勿手工修改。

export type BlockSegment = { "block_id": string; "start": number; "end": number }

export type Branch = { "branch_id": string; "thread_id": string; "parent_branch_id": (string) | (null); "fork_message_id": (string) | (null); "name": string; "is_default": boolean; "head_message_id": (string) | (null); "version": number; "created_at": string; "updated_at": string }

export type BuildCreate = { "parse"?: ParseRequest; "chunker"?: ChunkPolicy }

export type CancelledData = { "reason": "user_requested" }

export type CancelledDataV2 = { "reason": "user_requested"; "task_id": (string) | (null); "attempt": (number) | (null); "generation": (number) | (null) }

export type Candidate = { "chunk_id": string; "document_id": string; "index_batch_id": string; "dense_score": number; "rerank_score"?: (number) | (null); "rerank_input_start"?: (number) | (null); "rerank_input_end"?: (number) | (null) }

export type Chunk = { "chunk_id": string; "document_id": string; "index_batch_id": string; "seq": number; "text": string; "start_offset": number; "end_offset": number; "locations": Array<Location>; "content_hash"?: (string) | (null); "space_id"?: (string) | (null); "dimension"?: (number) | (null); "block_segments"?: Array<BlockSegment> }

export type ChunkList = { "items": Array<Chunk>; "next_cursor"?: (string) | (null) }

export type ChunkPolicy = { "mode"?: "structure_v1" | "character_v1"; "size"?: number; "overlap"?: number; "max_chunks"?: number }

export type CitationV2 = { "schema_version"?: 2; "bundle_id": string; "document_id": string; "index_batch_id": string; "context_evidence_ids": Array<string>; "locations": Array<Location>; "dense_score": number; "rerank_score"?: (number) | (null) }

export type CompactedDataV2 = { "task_id": string; "attempt": number; "generation": number; "summary": SummaryMetadata }

export type CompletedData = { "message_id": string; "citations": Array<(EvidenceCitation) | (LegacyCitation)> }

export type CompletedDataV2 = { "message_id": string; "citations": Array<(EvidenceCitation) | (LegacyCitation)>; "task_id": string; "attempt": number; "generation": number }

export type CompletedDataV3 = { "task_id": string; "attempt": number; "generation": number; "message_id": string; "citations": Array<CitationV2> }

export type ContextPlan = { "estimated_input_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "context_window_tokens": number; "status": "ready" | "budget_exceeded"; "schema_version"?: 3; "context_plan_id": string; "run_id": string; "task_id": string; "generation": number; "attempt": number; "thread_id": string; "branch_id": string; "anchor_message_id": string; "selected_message_ids": Array<string>; "omitted_messages": Array<OmittedMessage>; "omitted_ranges": Array<MessageRange>; "summaries": Array<SummaryMetadata>; "trim_policy_version": string; "counter_version": string; "created_at": string; "selected_evidence": Array<SelectedBundle>; "omitted_evidence": Array<OmittedBundle> }

export type ContextPlanSummary = { "estimated_input_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "context_window_tokens": number; "status": "ready" | "budget_exceeded"; "context_plan_id": string; "generation": number; "attempt": number; "selected_message_count": number; "omitted_message_count": number; "summary_count": number }

export type ContextResponse = { "plan": (ContextPlan) | (LegacyContextPlan) | (null); "reason": (string) | (null) }

export type ControlIdentity = { "task_id": (string) | (null); "attempt": (number) | (null); "generation": (number) | (null) }

export type CreatedDataV2 = { "message_id": string; "task_id": (string) | (null); "attempt": (number) | (null); "generation": (number) | (null); "branch_id": string; "operation_kind": "initial" | "user_retry" | "regenerate" | "branch_continue" }

export type DeltaData = { "text": string }

export type DeltaDataV2 = { "text": string; "task_id": string; "attempt": number; "generation": number }

export type DiagnosticCreate = { "query": string; "knowledge_base_id": string; "retrieval_profile_id"?: string; "retrieval_profile_version"?: number; "overrides"?: RetrievalOverrides; "filters"?: RetrievalFilters }

export type Document = { "document_id": string; "knowledge_base_id": (string) | (null); "filename": string; "extension": string; "size_bytes": number; "content_hash": string; "metadata_version"?: 1; "tags": Array<string>; "availability": "none" | "ready" | "reindex_required"; "active_index_batch_id": (string) | (null); "latest_build": (IndexBuild) | (null); "created_at": string }

export type DocumentList = { "items": Array<Document>; "next_cursor"?: (string) | (null) }

export type DocumentPatch = { "tags": Array<string> }

export type ErrorAttemptData = { "error_code": string; "attempt": number }

export type EventList = { "events": Array<(EventV1RunCreated) | (EventV1TaskQueued) | (EventV1TaskLeased) | (EventV1RunStarted) | (EventV1RetrievalCompleted) | (EventV1AnswerDelta) | (EventV1TaskRetryScheduled) | (EventV1MessageCompleted) | (EventV1RunSucceeded) | (EventV1RunFailed) | (EventV1RunCancelled) | (EventV2RunCreated) | (EventV2TaskQueued) | (EventV2TaskLeased) | (EventV2RunStarted) | (EventV2RetrievalCompleted) | (EventV2AnswerDelta) | (EventV2TaskRetryScheduled) | (EventV2MessageCompleted) | (EventV2RunSucceeded) | (EventV2RunFailed) | (EventV2RunCancelled) | (EventV2ContextPlanned) | (EventV2ContextCompacted) | (EventV2RunCancelling) | (EventV2RunRetryCreated) | (EventV2RunRegenerated) | (EventV3RunCreated) | (EventV3TaskQueued) | (EventV3TaskLeased) | (EventV3RunStarted) | (EventV3RetrievalCompleted) | (EventV3AnswerDelta) | (EventV3TaskRetryScheduled) | (EventV3MessageCompleted) | (EventV3RunSucceeded) | (EventV3RunFailed) | (EventV3RunCancelled) | (EventV3ContextPlanned) | (EventV3ContextCompacted) | (EventV3RunCancelling) | (EventV3RunRetryCreated) | (EventV3RunRegenerated) | (EventV3ToolStarted) | (EventV3ToolStage) | (EventV3ToolCompleted) | (EventV3ToolFailed) | (EventV3ToolCancelled)>; "next_after_seq": number; "has_more": boolean }

export type EventV1AnswerDelta = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "answer.delta"; "occurred_at": string; "data": DeltaData }

export type EventV1MessageCompleted = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "message.completed"; "occurred_at": string; "data": CompletedData }

export type EventV1RetrievalCompleted = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "retrieval.completed"; "occurred_at": string; "data": RetrievalData }

export type EventV1RunCancelled = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.cancelled"; "occurred_at": string; "data": CancelledData }

export type EventV1RunCreated = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.created"; "occurred_at": string; "data": MessageIdData }

export type EventV1RunFailed = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.failed"; "occurred_at": string; "data": ErrorAttemptData }

export type EventV1RunStarted = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.started"; "occurred_at": string; "data": TaskIdData }

export type EventV1RunSucceeded = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "run.succeeded"; "occurred_at": string; "data": MessageIdData }

export type EventV1TaskLeased = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "task.leased"; "occurred_at": string; "data": LeasedData }

export type EventV1TaskQueued = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "task.queued"; "occurred_at": string; "data": TaskIdData }

export type EventV1TaskRetryScheduled = { "schema_version": 1; "event_id": string; "run_id": string; "seq": number; "type": "task.retry_scheduled"; "occurred_at": string; "data": ErrorAttemptData }

export type EventV2AnswerDelta = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "answer.delta"; "occurred_at": string; "data": DeltaDataV2 }

export type EventV2ContextCompacted = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "context.compacted"; "occurred_at": string; "data": CompactedDataV2 }

export type EventV2ContextPlanned = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "context.planned"; "occurred_at": string; "data": PlannedDataV2 }

export type EventV2MessageCompleted = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "message.completed"; "occurred_at": string; "data": CompletedDataV2 }

export type EventV2RetrievalCompleted = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "retrieval.completed"; "occurred_at": string; "data": RetrievalDataV2 }

export type EventV2RunCancelled = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.cancelled"; "occurred_at": string; "data": CancelledDataV2 }

export type EventV2RunCancelling = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.cancelling"; "occurred_at": string; "data": CancelledDataV2 }

export type EventV2RunCreated = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.created"; "occurred_at": string; "data": CreatedDataV2 }

export type EventV2RunFailed = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.failed"; "occurred_at": string; "data": FailedDataV2 }

export type EventV2RunRegenerated = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.regenerated"; "occurred_at": string; "data": RelatedRunDataV2 }

export type EventV2RunRetryCreated = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.retry_created"; "occurred_at": string; "data": RelatedRunDataV2 }

export type EventV2RunStarted = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.started"; "occurred_at": string; "data": ExecutionIdentity }

export type EventV2RunSucceeded = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.succeeded"; "occurred_at": string; "data": SucceededDataV2 }

export type EventV2TaskLeased = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "task.leased"; "occurred_at": string; "data": LeasedDataV2 }

export type EventV2TaskQueued = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "task.queued"; "occurred_at": string; "data": ControlIdentity }

export type EventV2TaskRetryScheduled = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "task.retry_scheduled"; "occurred_at": string; "data": RetryDataV2 }

export type EventV3AnswerDelta = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "answer.delta"; "occurred_at": string; "data": DeltaDataV2 }

export type EventV3ContextCompacted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "context.compacted"; "occurred_at": string; "data": CompactedDataV2 }

export type EventV3ContextPlanned = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "context.planned"; "occurred_at": string; "data": PlannedDataV2 }

export type EventV3MessageCompleted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "message.completed"; "occurred_at": string; "data": CompletedDataV3 }

export type EventV3RetrievalCompleted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "retrieval.completed"; "occurred_at": string; "data": RetrievalDataV3 }

export type EventV3RunCancelled = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.cancelled"; "occurred_at": string; "data": CancelledDataV2 }

export type EventV3RunCancelling = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.cancelling"; "occurred_at": string; "data": CancelledDataV2 }

export type EventV3RunCreated = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.created"; "occurred_at": string; "data": CreatedDataV2 }

export type EventV3RunFailed = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.failed"; "occurred_at": string; "data": FailedDataV2 }

export type EventV3RunRegenerated = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.regenerated"; "occurred_at": string; "data": RelatedRunDataV2 }

export type EventV3RunRetryCreated = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.retry_created"; "occurred_at": string; "data": RelatedRunDataV2 }

export type EventV3RunStarted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.started"; "occurred_at": string; "data": ExecutionIdentity }

export type EventV3RunSucceeded = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "run.succeeded"; "occurred_at": string; "data": SucceededDataV2 }

export type EventV3TaskLeased = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "task.leased"; "occurred_at": string; "data": LeasedDataV2 }

export type EventV3TaskQueued = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "task.queued"; "occurred_at": string; "data": ControlIdentity }

export type EventV3TaskRetryScheduled = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "task.retry_scheduled"; "occurred_at": string; "data": RetryDataV2 }

export type EventV3ToolCancelled = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "tool.cancelled"; "occurred_at": string; "data": ToolEvent }

export type EventV3ToolCompleted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "tool.completed"; "occurred_at": string; "data": ToolEvent }

export type EventV3ToolFailed = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "tool.failed"; "occurred_at": string; "data": ToolEvent }

export type EventV3ToolStage = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "tool.stage"; "occurred_at": string; "data": ToolEvent }

export type EventV3ToolStarted = { "schema_version": 3; "event_id": string; "run_id": string; "seq": number; "type": "tool.started"; "occurred_at": string; "data": ToolEvent }

export type EvidenceBundle = { "schema_version"?: 2; "bundle_id": string; "document_id": string; "index_batch_id": string; "text": string; "components": Array<EvidenceComponent>; "locations": Array<Location>; "dense_score": number; "rerank_score"?: (number) | (null); "next_offset": (number) | (null) }

export type EvidenceCitation = { "document_id": string; "chunk_id": string; "filename": string; "start_offset": number; "end_offset": number; "score": number; "index_batch_id": string; "locations": Array<EvidenceLocation> }

export type EvidenceComponent = { "component_id": string; "chunk_id": string; "start_offset": number; "end_offset": number; "content_hash": string }

export type EvidenceLocation = { "kind": "line" | "paragraph"; "number": number; "start_offset": number; "end_offset": number }

export type ExecutionIdentity = { "task_id": string; "attempt": number; "generation": number }

export type FailedDataV2 = { "task_id": (string) | (null); "attempt": (number) | (null); "generation": (number) | (null); "error_code": string }

export type IndexBuild = { "index_batch_id": string; "document_id": string; "knowledge_base_id": string; "state": "queued" | "building" | "waiting" | "succeeded" | "failed" | "cancelled"; "stage": string; "task_id": (string) | (null); "parse": (ParseOutcome) | (null); "chunk_count": number; "error_code": (string) | (null); "operation_status"?: ("cancelling") | (null); "created_at": string }

export type KnowledgeBase = { "knowledge_base_id": string; "name": string; "enabled": boolean; "is_default": boolean; "embedding_space_id": string; "embedding_profile_id": string; "embedding_profile_version": number; "created_at": string; "updated_at": string }

export type KnowledgeBaseCreate = { "name": string; "embedding_profile_id": string; "embedding_profile_version": number }

export type KnowledgeBaseList = { "items": Array<KnowledgeBase>; "next_cursor"?: (string) | (null) }

export type KnowledgeBasePatch = { "name"?: (string) | (null); "enabled"?: (boolean) | (null) }

export type LeasedData = { "task_id": string; "worker_id": string; "attempt": number; "generation": number }

export type LeasedDataV2 = { "task_id": string; "attempt": number; "generation": number; "worker_id": string }

export type LegacyCitation = { "document_id": string; "chunk_id": string; "filename": string; "start_offset": number; "end_offset": number; "score": number }

export type LegacyContextPlan = { "estimated_input_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "context_window_tokens": number; "status": "ready" | "budget_exceeded"; "context_plan_id": string; "run_id": string; "task_id": string; "generation": number; "attempt": number; "thread_id": string; "branch_id": string; "anchor_message_id": string; "selected_message_ids": Array<string>; "omitted_messages": Array<OmittedMessage>; "omitted_ranges": Array<MessageRange>; "summaries": Array<SummaryMetadata>; "selected_evidence": Array<SelectedEvidence>; "trim_policy_version": string; "counter_version": string; "created_at": string; "schema_version"?: 2 }

export type Location = { "kind": "line" | "paragraph" | "table_cell" | "page" | "slide" | "sheet_range" | "block"; "origin": "source" | "normalized"; "quality": "verified" | "block_only"; "number"?: (number) | (null); "end_number"?: (number) | (null); "block_id"?: (string) | (null); "sheet_name"?: (string) | (null); "cell_range"?: (string) | (null); "table"?: (number) | (null); "row"?: (number) | (null); "column"?: (number) | (null); "start_offset": number; "end_offset": number }

export type Message = { "message_id": string; "thread_id": string; "branch_id": string; "seq": number; "role": "user" | "assistant"; "source": string; "content": string; "status": string; "run_id": (string) | (null); "citation_schema_version": 1 | 2; "citations": Array<(CitationV2) | (EvidenceCitation) | (LegacyCitation)>; "created_at": string }

export type MessageCreate = { "model_profile_id"?: (string) | (null); "model_profile_version"?: (number) | (null); "branch_id": string; "content": string; "expected_version": number; "rag"?: RagSelection }

export type MessageIdData = { "message_id": string }

export type MessageRange = { "from_seq": number; "to_seq": number; "count": number; "reason": "outside_candidate_window" | "budget_trimmed" | "summarized" }

export type MessageRunResponse = { "branch_id": string; "message_id": string; "run_id": string; "task_id": string; "status": "queued" | "running" | "retry_waiting" | "cancelling" | "succeeded" | "failed" | "cancelled" }

export type ModelSelection = { "profile_id": string; "version": number; "display_name": string; "provider_kind": "mock" | "openai_compatible"; "model_name": string; "context_window_tokens": number; "max_output_tokens": number }

export type Omission = { "chunk_id": string; "reason": string }

export type OmittedBundle = { "bundle_id": string; "reason": "budget_trimmed" }

export type OmittedMessage = { "message_id": string; "reason": "budget_trimmed" | "summarized" | "incomplete_turn" }

export type ParseOutcome = { "parse_job_id": string; "parser_profile_id": (string) | (null); "parser_profile_version": (number) | (null); "parser_hash": string; "output_protocol": (string) | (null); "parser_kind": "local" | "mineru"; "routing_policy_version": string; "state": "queued" | "running" | "waiting" | "succeeded" | "failed" | "cancelled"; "stage": string; "error_code": (string) | (null); "remote_outcome": (string) | (null); "artifact_id": (string) | (null); "poll_count": number }

export type ParseRequest = { "parser_profile_id"?: (string) | (null); "parser_profile_version"?: (number) | (null); "cloud_consent"?: (boolean) | (null); "consent_version"?: (string) | (null); "acknowledge_duplicate_cost"?: boolean }

export type PlannedDataV2 = { "task_id": string; "attempt": number; "generation": number; "plan": ContextPlanSummary; "omitted_ranges": Array<MessageRange>; "summary_ids": Array<string> }

export type RagProfile = { "kind": "embedding" | "rerank" | "parser" | "retrieval"; "profile_id": string; "version": number; "available": boolean; "unavailable_reason": (string) | (null); "formats"?: Array<string>; "verified_formats"?: Array<string>; "space_id"?: (string) | (null); "dimension"?: (number) | (null) }

export type RagProfileList = { "items": Array<RagProfile> }

export type RagSelection = { "enabled"?: boolean; "knowledge_base_id"?: (string) | (null); "retrieval_profile_id"?: (string) | (null); "retrieval_profile_version"?: (number) | (null); "overrides"?: RetrievalOverrides; "filters"?: RetrievalFilters }

export type RagSummary = { "enabled": boolean; "execution_state": "not_started" | "running" | "completed" | "failed" | "cancelled"; "result_mode": ("off" | "ok" | "empty" | "degraded") | (null); "error_code"?: (string) | (null); "view_id"?: (string) | (null); "knowledge_base_id"?: (string) | (null); "retrieval_profile_id"?: (string) | (null); "top_k"?: (number) | (null); "embedding_dimensions"?: (number) | (null) }

export type RelatedRunDataV2 = { "task_id": (string) | (null); "attempt": (number) | (null); "generation": (number) | (null); "parent_run_id": string; "branch_id": string; "user_message_id": string }

export type RetrievalData = { "count": number; "items": Array<RetrievalItem> }

export type RetrievalDataV2 = { "count": number; "items": Array<RetrievalItem>; "task_id": string; "attempt": number; "generation": number }

export type RetrievalDataV3 = { "task_id": string; "attempt": number; "generation": number; "count": number; "execution_id": (string) | (null); "mode": "off" | "ok" | "empty" | "degraded"; "bundle_ids": Array<string> }

export type RetrievalExecution = { "execution_id": string; "view_id": string; "origin": "run" | "diagnostic"; "state": "queued" | "running" | "succeeded" | "failed" | "cancelled" | "interrupted"; "stage": string; "mode": ("ok" | "empty" | "degraded") | (null); "candidates": Array<Candidate>; "bundle_ids": Array<string>; "omitted": Array<Omission>; "error_code": (string) | (null); "timings_ms": { [key: string]: unknown }; "profile": RetrievalTraceProfile }

export type RetrievalFilters = { "document_ids"?: (Array<string>) | (null); "extensions"?: (Array<string>) | (null); "tags_all"?: Array<string> }

export type RetrievalItem = { "document_id": string; "chunk_id": string; "index_batch_id": string; "locations": Array<EvidenceLocation>; "start_offset": number; "end_offset": number; "score": number }

export type RetrievalOverrides = { "top_k"?: (number) | (null); "rerank_enabled"?: (boolean) | (null); "neighbor_radius"?: (number) | (null) }

export type RetrievalTraceProfile = { "retrieval_profile_id": string; "retrieval_profile_version": number; "candidate_k": number; "top_k": number }

export type RetryDataV2 = { "task_id": string; "attempt": number; "generation": number; "error_code": string }

export type RunDetail = { "run_id": string; "thread_id": string; "branch_id": string; "user_message_id": string; "assistant_message_id": (string) | (null); "parent_run_id": (string) | (null); "operation_kind": string; "execution_schema_version": 1 | 2 | 3; "status": "queued" | "running" | "retry_waiting" | "cancelling" | "succeeded" | "failed" | "cancelled"; "legacy": boolean; "snapshot": (SnapshotSummary) | (null); "context_plan": (ContextPlanSummary) | (null); "last_error_code": (string) | (null); "model": (ModelSelection) | (null); "task": TaskSummary; "rag_summary": (RagSummary) | (null); "created_at": string; "updated_at": string }

export type RunOperationCreate = { "model_profile_id"?: (string) | (null); "model_profile_version"?: (number) | (null) }

export type RunSummary = { "run_id": string; "branch_id": string; "user_message_id": string; "assistant_message_id": (string) | (null); "parent_run_id": (string) | (null); "operation_kind": string; "execution_schema_version": 1 | 2 | 3; "status": "queued" | "running" | "retry_waiting" | "cancelling" | "succeeded" | "failed" | "cancelled"; "created_at": string }

export type SelectedBundle = { "schema_version"?: 2; "bundle_id": string; "document_id": string; "index_batch_id": string; "context_evidence_ids": Array<string>; "locations": Array<Location>; "dense_score": number; "rerank_score"?: (number) | (null); "content_hash": string }

export type SelectedEvidence = { "document_id": string; "chunk_id": string; "index_batch_id": string; "locations": Array<EvidenceLocation>; "start_offset": number; "end_offset": number; "score": number; "content_hash": string }

export type SnapshotSummary = { "schema_version": 2 | 3; "context_policy_version": string; "counter_version": string; "context_window_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number }

export type SourceSegment = { "message_id": string; "start_offset": number; "end_offset": number }

export type SucceededDataV2 = { "message_id": string; "task_id": string; "attempt": number; "generation": number }

export type SummaryMetadata = { "summary_id": string; "thread_id": string; "branch_id": string; "covered_message_ids": Array<string>; "from_seq": number; "to_seq": number; "source_hash": string; "source_segments": Array<SourceSegment>; "summary_policy_version": string; "source_run_id": string; "created_at": string }

export type TaskIdData = { "task_id": string }

export type TaskSummary = { "task_id": string; "kind": "run"; "state": "queued" | "leased" | "running" | "retry_waiting" | "succeeded" | "failed" | "cancelled"; "attempt": number; "worker_id": (string) | (null); "generation": number; "lease_expires_at": (string) | (null); "last_error_code": (string) | (null) }

export type ThreadDetail = { "thread": ThreadSummary; "branch": Branch; "branch_path": Array<Branch>; "messages": Array<Message>; "runs": Array<RunSummary>; "active_run_id": (string) | (null); "recent_run_id": (string) | (null); "next_before_seq": (number) | (null); "has_more": boolean }

export type ThreadSummary = { "thread_id": string; "owner_id": string; "title": string; "default_branch_id": string; "conversation_version": 1 | 2; "archived_at": (string) | (null); "created_at": string; "updated_at": string }

export type ToolEvent = { "task_id": string; "attempt": number; "generation": number; "call_id": string; "execution_id": string; "tool_version"?: 1; "stage": string; "mode"?: ("ok" | "empty" | "degraded") | (null); "count"?: (number) | (null); "error_code"?: (string) | (null) }

export type RunEvent = (EventV1RunCreated) | (EventV1TaskQueued) | (EventV1TaskLeased) | (EventV1RunStarted) | (EventV1RetrievalCompleted) | (EventV1AnswerDelta) | (EventV1TaskRetryScheduled) | (EventV1MessageCompleted) | (EventV1RunSucceeded) | (EventV1RunFailed) | (EventV1RunCancelled) | (EventV2RunCreated) | (EventV2TaskQueued) | (EventV2TaskLeased) | (EventV2RunStarted) | (EventV2RetrievalCompleted) | (EventV2AnswerDelta) | (EventV2TaskRetryScheduled) | (EventV2MessageCompleted) | (EventV2RunSucceeded) | (EventV2RunFailed) | (EventV2RunCancelled) | (EventV2ContextPlanned) | (EventV2ContextCompacted) | (EventV2RunCancelling) | (EventV2RunRetryCreated) | (EventV2RunRegenerated) | (EventV3RunCreated) | (EventV3TaskQueued) | (EventV3TaskLeased) | (EventV3RunStarted) | (EventV3RetrievalCompleted) | (EventV3AnswerDelta) | (EventV3TaskRetryScheduled) | (EventV3MessageCompleted) | (EventV3RunSucceeded) | (EventV3RunFailed) | (EventV3RunCancelled) | (EventV3ContextPlanned) | (EventV3ContextCompacted) | (EventV3RunCancelling) | (EventV3RunRetryCreated) | (EventV3RunRegenerated) | (EventV3ToolStarted) | (EventV3ToolStage) | (EventV3ToolCompleted) | (EventV3ToolFailed) | (EventV3ToolCancelled)
