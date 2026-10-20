from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from backend.api.schemas.v2 import StrictModel
from backend.api.schemas.v2.models import PositiveInt

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Identity = Annotated[str, Field(min_length=1)]
ContentHash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ContextQuery(StrictModel):
    generation: Annotated[int, Field(ge=1)] | None = None


class EvidenceLocation(StrictModel):
    kind: Literal["line", "paragraph"]
    number: PositiveInt
    start_offset: NonNegativeInt
    end_offset: NonNegativeInt


class RetrievalItem(StrictModel):
    document_id: str
    chunk_id: str
    index_batch_id: str
    locations: list[EvidenceLocation]
    start_offset: NonNegativeInt
    end_offset: NonNegativeInt
    score: float


class LegacyCitation(StrictModel):
    document_id: str
    chunk_id: str
    filename: str
    start_offset: NonNegativeInt
    end_offset: NonNegativeInt
    score: float


class EvidenceCitation(LegacyCitation):
    index_batch_id: str
    locations: list[EvidenceLocation]


Citation = EvidenceCitation | LegacyCitation


class SelectedEvidence(RetrievalItem):
    content_hash: ContentHash


class MessageRange(StrictModel):
    from_seq: PositiveInt
    to_seq: PositiveInt
    count: PositiveInt
    reason: Literal["outside_candidate_window", "budget_trimmed", "summarized"]


class OmittedMessage(StrictModel):
    message_id: Identity
    reason: Literal["budget_trimmed", "summarized", "incomplete_turn"]


class SourceSegment(StrictModel):
    message_id: Identity
    start_offset: NonNegativeInt
    end_offset: NonNegativeInt


class SummaryMetadata(StrictModel):
    summary_id: Identity
    thread_id: Identity
    branch_id: Identity
    covered_message_ids: list[Identity] = Field(max_length=200)
    from_seq: PositiveInt
    to_seq: PositiveInt
    source_hash: ContentHash
    source_segments: list[SourceSegment] = Field(max_length=200)
    summary_policy_version: Identity
    source_run_id: Identity
    created_at: datetime


class ContextBudget(StrictModel):
    estimated_input_tokens: NonNegativeInt
    reserved_output_tokens: PositiveInt
    safety_margin_tokens: NonNegativeInt
    context_window_tokens: PositiveInt
    status: Literal["ready", "budget_exceeded"]


class ContextPlanSummary(ContextBudget):
    context_plan_id: Identity
    generation: PositiveInt
    attempt: PositiveInt
    selected_message_count: NonNegativeInt
    omitted_message_count: NonNegativeInt
    summary_count: NonNegativeInt


class ContextPlan(ContextBudget):
    context_plan_id: Identity
    run_id: Identity
    task_id: Identity
    generation: PositiveInt
    attempt: PositiveInt
    thread_id: Identity
    branch_id: Identity
    anchor_message_id: Identity
    selected_message_ids: list[Identity] = Field(max_length=200)
    omitted_messages: list[OmittedMessage] = Field(max_length=200)
    omitted_ranges: list[MessageRange] = Field(max_length=200)
    summaries: list[SummaryMetadata] = Field(max_length=200)
    selected_evidence: list[SelectedEvidence] = Field(max_length=200)
    trim_policy_version: Identity
    counter_version: Identity
    created_at: datetime


class ContextResponse(StrictModel):
    plan: ContextPlan | None
    reason: Literal["not_planned"] | None

    @model_validator(mode="after")
    def plan_reason(self):
        if (self.plan is None) != (self.reason == "not_planned"):
            raise ValueError("未规划时必须明确原因，已规划时原因必须为空")
        return self
