// 自动生成自 contracts/*_v2.json；请运行 npm run generate:api，勿手工修改。

import type { Citation as LegacyCitation, TaskSummary as LegacyTaskSummary, RunEvent as LegacyRunEvent, RetrievalItem as LegacyRetrievalItem, ErrorResponse as LegacyErrorResponse, ValidationErrorResponse as LegacyValidationErrorResponse } from './api'

export type ThreadSummary = { "thread_id": string; "owner_id": string; "title": string; "default_branch_id": string; "conversation_version": 1 | 2; "archived_at": string | null; "created_at": string; "updated_at": string }

export type Branch = { "branch_id": string; "thread_id": string; "parent_branch_id": string | null; "fork_message_id": string | null; "name": string; "is_default": boolean; "head_message_id": string | null; "version": number; "created_at": string; "updated_at": string }

export type Message = { "message_id": string; "thread_id": string; "branch_id": string; "seq": number; "role": "user" | "assistant"; "source": "user_input" | "assistant_generation"; "content": string; "status": string; "run_id": string | null; "citations": Array<LegacyCitation>; "created_at": string }

export type RunDetail = { "run_id": string; "thread_id": string; "branch_id": string; "status": RunStatus; "user_message_id": string; "assistant_message_id": string | null; "parent_run_id": string | null; "operation_kind": OperationKind; "execution_schema_version": 1 | 2; "legacy": boolean; "model_profile_id": string | null; "model_profile_version": number | null; "model": (ModelSelection) | (null); "snapshot": (SnapshotSummary) | (null); "context_plan": (ContextPlanSummary) | (null); "task": LegacyTaskSummary; "last_error_code": string | null; "cancel_requested_at": string | null; "created_at": string; "updated_at": string }

export type RunStatus = "queued" | "running" | "retry_waiting" | "cancelling" | "succeeded" | "failed" | "cancelled"

export type OperationKind = "initial" | "user_retry" | "regenerate" | "branch_continue"

export type SnapshotSummary = { "schema_version": 2; "prompt_version": string; "context_policy_version": string; "summary_policy_version": string; "counter_version": string; "context_window_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "retrieval_enabled": boolean; "retrieval_top_k": number; "embedding_dimensions": 384 }

export type RunSummary = { "run_id": string; "branch_id": string; "user_message_id": string; "assistant_message_id": string | null; "parent_run_id": string | null; "operation_kind": OperationKind; "execution_schema_version": 1 | 2; "status": RunStatus; "created_at": string }

export type ModelProfile = { "profile_id": string; "version": number; "display_name": string; "provider_kind": "mock" | "openai_compatible"; "model_name": string; "context_window_tokens": number; "max_output_tokens": number; "status": "enabled" | "disabled" | "invalid"; "reason": null | "MODEL_PROFILE_DISABLED" | "MODEL_PROFILE_INVALID" | "MODEL_CREDENTIAL_UNAVAILABLE"; "is_default": boolean }

export type ModelProfileKey = { "profile_id": string; "version": number }

export type ModelSelection = { "profile_id": string; "version": number; "display_name": string; "provider_kind": "mock" | "openai_compatible"; "model_name": string; "context_window_tokens": number; "max_output_tokens": number }

export type ProfileSelectionRequest = { "model_profile_id"?: string; "model_profile_version"?: number }

export type ContextPlan = { "context_plan_id": string; "run_id": string; "task_id": string; "generation": number; "attempt": number; "thread_id": string; "branch_id": string; "anchor_message_id": string; "selected_message_ids": Array<string>; "omitted_messages": Array<OmittedMessage>; "omitted_ranges": Array<MessageRange>; "summaries": Array<SummaryMetadata>; "selected_evidence": Array<SelectedEvidence>; "trim_policy_version": string; "counter_version": string; "estimated_input_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "context_window_tokens": number; "status": "ready" | "budget_exceeded"; "created_at": string }

export type MessageRange = { "from_seq": number; "to_seq": number; "count": number; "reason": "outside_candidate_window" | "budget_trimmed" | "summarized" }

export type OmittedMessage = { "message_id": string; "reason": "budget_trimmed" | "summarized" | "incomplete_turn" }

export type SourceSegment = { "message_id": string; "start_offset": number; "end_offset": number }

export type SummaryMetadata = { "summary_id": string; "thread_id": string; "branch_id": string; "covered_message_ids": Array<string>; "from_seq": number; "to_seq": number; "source_hash": string; "source_segments": Array<SourceSegment>; "summary_policy_version": string; "source_run_id": string; "created_at": string }

export type SelectedEvidence = { "document_id": string; "chunk_id": string; "index_batch_id": string; "locations": Array<{ "kind": "line" | "paragraph"; "number": number; "start_offset": number; "end_offset": number }>; "start_offset": number; "end_offset": number; "score": number; "content_hash": string }

export type ContextPlanSummary = { "context_plan_id": string; "generation": number; "attempt": number; "status": "ready" | "budget_exceeded"; "estimated_input_tokens": number; "reserved_output_tokens": number; "safety_margin_tokens": number; "context_window_tokens": number; "selected_message_count": number; "omitted_message_count": number; "summary_count": number }

export type RunEvent = (LegacyRunEvent) | (RunEventV2)

export type ExecutionTaskId = string

export type ExecutionAttempt = number

export type ExecutionGeneration = number

export type ControlTaskId = string | null

export type ControlAttempt = number | null

export type ControlGeneration = number | null

export type EventEnvelopeV2 = { "schema_version": 2; "event_id": string; "run_id": string; "seq": number; "type": "run.created" | "task.queued" | "task.leased" | "run.started" | "retrieval.completed" | "answer.delta" | "task.retry_scheduled" | "message.completed" | "run.succeeded" | "run.failed" | "run.cancelled" | "context.planned" | "context.compacted" | "run.cancelling" | "run.retry_created" | "run.regenerated"; "occurred_at": string; "data": { [key: string]: unknown } }

export type RunEventV2 = (EventEnvelopeV2) & (({ "type": "run.created"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "message_id": string; "branch_id": string; "operation_kind": OperationKind }; [key: string]: unknown }) | ({ "type": "task.queued"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration }; [key: string]: unknown }) | ({ "type": "task.leased"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "worker_id": string }; [key: string]: unknown }) | ({ "type": "run.started"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration }; [key: string]: unknown }) | ({ "type": "retrieval.completed"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "count": number; "items": Array<LegacyRetrievalItem> }; [key: string]: unknown }) | ({ "type": "answer.delta"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "text": string }; [key: string]: unknown }) | ({ "type": "task.retry_scheduled"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "error_code": string }; [key: string]: unknown }) | ({ "type": "message.completed"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "message_id": string; "citations": Array<LegacyCitation> }; [key: string]: unknown }) | ({ "type": "run.succeeded"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "message_id": string }; [key: string]: unknown }) | ({ "type": "run.failed"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "error_code": string }; [key: string]: unknown }) | ({ "type": "run.cancelled"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "reason": "user_requested" }; [key: string]: unknown }) | ({ "type": "context.planned"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "plan": ContextPlanSummary; "omitted_ranges": Array<MessageRange>; "summary_ids": Array<string> }; [key: string]: unknown }) | ({ "type": "context.compacted"; "data": { "task_id": ExecutionTaskId; "attempt": ExecutionAttempt; "generation": ExecutionGeneration; "summary": SummaryMetadata }; [key: string]: unknown }) | ({ "type": "run.cancelling"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "reason": "user_requested" }; [key: string]: unknown }) | ({ "type": "run.retry_created"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "parent_run_id": string; "branch_id": string; "user_message_id": string }; [key: string]: unknown }) | ({ "type": "run.regenerated"; "data": { "task_id": ControlTaskId; "attempt": ControlAttempt; "generation": ControlGeneration; "parent_run_id": string; "branch_id": string; "user_message_id": string }; [key: string]: unknown }))

export type ThreadCreate = { "title"?: string }

export type ThreadPatch = { "title"?: string; "archived"?: boolean }

export type BranchCreate = { "parent_branch_id": string; "fork_message_id": string; "name"?: string }

export type MessageCreate = { "branch_id": string; "content": string; "expected_version": number; "model_profile_id"?: string; "model_profile_version"?: number }

export type RunOperationCreate = ProfileSelectionRequest

export type ThreadListQuery = { "include_archived"?: boolean; "cursor"?: string; "limit"?: number }

export type ThreadDetailQuery = { "branch_id"?: string; "before_seq"?: number; "limit"?: number }

export type EventListQuery = { "after_seq"?: number; "limit"?: number }

export type ContextQuery = { "generation"?: number }

export type ThreadList = { "threads": Array<ThreadSummary>; "next_cursor": string | null; "has_more": boolean }

export type ThreadDetail = { "thread": ThreadSummary; "branch": Branch; "branch_path": Array<Branch>; "messages": Array<Message>; "runs": Array<RunSummary>; "active_run_id": string | null; "recent_run_id": string | null; "next_before_seq": number | null; "has_more": boolean }

export type BranchListResponse = { "branches": Array<Branch> }

export type MessageRunResponse = { "branch_id": string; "message_id": string; "run_id": string; "task_id": string; "status": RunStatus }

export type CancelResponse = { "run_id": string; "status": RunStatus }

export type EventListResponse = { "events": Array<RunEvent>; "next_after_seq": number; "has_more": boolean }

export type ModelListResponse = { "models": Array<ModelProfile>; "default_profile": ModelProfileKey }

export type ContextResponse = ({ "plan": null; "reason": "not_planned" }) | ({ "plan": ContextPlan; "reason": null })

export type ErrorResponse = LegacyErrorResponse

export type ValidationErrorResponse = LegacyValidationErrorResponse

export type UnprocessableResponse = (LegacyErrorResponse) | (LegacyValidationErrorResponse)
