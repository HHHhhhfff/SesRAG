from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.api.schemas.v2.context import (
    ContextBudget,
    Identity,
    MessageRange,
    OmittedMessage,
    PositiveInt,
    SummaryMetadata,
)
from backend.api.schemas.v2.context import ContextPlan as ContextPlanV2
from backend.api.schemas.v3 import StrictModel
from backend.api.schemas.v3.sessions import CitationV2


class SelectedBundle(CitationV2):
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LegacyContextPlan(ContextPlanV2):
    schema_version: Literal[2] = 2


class OmittedBundle(StrictModel):
    bundle_id: str
    reason: Literal["budget_trimmed"]


class ContextPlan(ContextBudget):
    schema_version: Literal[3] = 3
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
    trim_policy_version: Identity
    counter_version: Identity
    created_at: datetime
    selected_evidence: list[SelectedBundle] = Field(max_length=100)
    omitted_evidence: list[OmittedBundle] = Field(max_length=100)


class ContextResponse(StrictModel):
    plan: ContextPlan | LegacyContextPlan | None
    reason: str | None
