"""schema3会话公开投影；历史消息保留明确引用版本。"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from backend.api.schemas.v2.context import Citation as LegacyCitation
from backend.api.schemas.v2.context import ContextPlanSummary
from backend.api.schemas.v2.models import ModelSelection
from backend.api.schemas.v2.runs import RunOperationCreate, RunStatus, TaskSummary
from backend.api.schemas.v2.threads import Branch, ThreadSummary
from backend.api.schemas.v2.threads import MessageCreate as MessageCreateV2
from backend.api.schemas.v3 import StrictModel
from backend.api.schemas.v3.documents import Location
from backend.api.schemas.v3.retrieval import RagSelection


class CitationV2(StrictModel):
    schema_version: Literal[2] = 2
    bundle_id: str
    document_id: str
    index_batch_id: str
    context_evidence_ids: list[str] = Field(max_length=100)
    locations: list[Location] = Field(max_length=1000)
    dense_score: float = Field(allow_inf_nan=False)
    rerank_score: float | None = Field(default=None, allow_inf_nan=False)


class MessageCreate(MessageCreateV2):
    rag: RagSelection = RagSelection()


class Message(StrictModel):
    message_id: str
    thread_id: str
    branch_id: str
    seq: int
    role: Literal["user", "assistant"]
    source: str
    content: str
    status: str
    run_id: str | None
    citation_schema_version: Literal[1, 2]
    citations: list[CitationV2 | LegacyCitation] = Field(max_length=100)
    created_at: datetime

    @model_validator(mode="after")
    def citation_version_matches(self):
        if any(
            isinstance(item, CitationV2) != (self.citation_schema_version == 2)
            for item in self.citations
        ):
            raise ValueError("引用必须使用消息声明的版本")
        return self


class RunSummary(StrictModel):
    run_id: str
    branch_id: str
    user_message_id: str
    assistant_message_id: str | None
    parent_run_id: str | None
    operation_kind: str
    execution_schema_version: Literal[1, 2, 3]
    status: Literal[
        "queued", "running", "retry_waiting", "cancelling", "succeeded", "failed", "cancelled"
    ]
    created_at: datetime


class ThreadDetail(StrictModel):
    thread: ThreadSummary
    branch: Branch
    branch_path: list[Branch]
    messages: list[Message] = Field(max_length=200)
    runs: list[RunSummary]
    active_run_id: str | None
    recent_run_id: str | None
    next_before_seq: int | None
    has_more: bool


class RagSummary(StrictModel):
    enabled: bool
    execution_state: Literal["not_started", "running", "completed", "failed", "cancelled"]
    result_mode: Literal["off", "ok", "empty", "degraded"] | None
    error_code: str | None = None
    view_id: str | None = None
    knowledge_base_id: str | None = None
    retrieval_profile_id: str | None = None
    top_k: int | None = None
    embedding_dimensions: int | None = None


class SnapshotSummary(StrictModel):
    schema_version: Literal[2, 3]
    context_policy_version: str
    counter_version: str
    context_window_tokens: int = Field(ge=1)
    reserved_output_tokens: int = Field(ge=1)
    safety_margin_tokens: int = Field(ge=0)


class RunDetail(StrictModel):
    run_id: str
    thread_id: str
    branch_id: str
    user_message_id: str
    assistant_message_id: str | None
    parent_run_id: str | None
    operation_kind: str
    execution_schema_version: Literal[1, 2, 3]
    status: RunStatus
    legacy: bool
    snapshot: SnapshotSummary | None
    context_plan: ContextPlanSummary | None
    last_error_code: str | None
    model: ModelSelection | None
    task: TaskSummary
    rag_summary: RagSummary | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "CitationV2",
    "MessageCreate",
    "Message",
    "ThreadDetail",
    "RunDetail",
    "RunOperationCreate",
]
