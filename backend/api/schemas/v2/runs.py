from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator

from backend.api.schemas.v2 import StrictModel
from backend.api.schemas.v2.context import (
    Citation,
    ContextPlanSummary,
    Identity,
    MessageRange,
    NonNegativeInt,
    RetrievalItem,
    SummaryMetadata,
)
from backend.api.schemas.v2.models import ModelSelection, PositiveInt, ProfileSelectionRequest

RunStatus = Literal[
    "queued", "running", "retry_waiting", "cancelling", "succeeded", "failed", "cancelled"
]
OperationKind = Literal["initial", "user_retry", "regenerate", "branch_continue"]


class RunOperationCreate(ProfileSelectionRequest):
    pass


class EventListQuery(StrictModel):
    after_seq: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=1000)] = 200


class TaskSummary(StrictModel):
    task_id: str
    kind: Literal["run"]
    state: Literal[
        "queued", "leased", "running", "retry_waiting", "succeeded", "failed", "cancelled"
    ]
    attempt: NonNegativeInt
    worker_id: str | None
    generation: NonNegativeInt
    lease_expires_at: datetime | None
    last_error_code: str | None


class SnapshotSummary(StrictModel):
    schema_version: Literal[2]
    prompt_version: Identity
    context_policy_version: Identity
    summary_policy_version: Identity
    counter_version: Identity
    context_window_tokens: PositiveInt
    reserved_output_tokens: PositiveInt
    safety_margin_tokens: NonNegativeInt
    retrieval_enabled: bool
    retrieval_top_k: PositiveInt
    embedding_dimensions: Literal[384]


class RunSummary(StrictModel):
    run_id: Identity
    branch_id: Identity
    user_message_id: Identity
    assistant_message_id: Identity | None
    parent_run_id: Identity | None
    operation_kind: OperationKind
    execution_schema_version: Literal[1, 2]
    status: RunStatus
    created_at: datetime


class RunResponse(RunSummary):
    thread_id: Identity
    legacy: bool
    model_profile_id: Identity | None
    model_profile_version: PositiveInt | None
    model: ModelSelection | None
    snapshot: SnapshotSummary | None
    context_plan: ContextPlanSummary | None
    task: TaskSummary
    last_error_code: str | None
    cancel_requested_at: datetime | None
    updated_at: datetime

    @model_validator(mode="after")
    def execution_projection(self):
        # HTTP v2 读取旧 Run 不得补造模型、计划或新状态。
        if self.execution_schema_version == 1:
            if (
                not self.legacy
                or self.status == "cancelling"
                or any(
                    value is not None
                    for value in (
                        self.model_profile_id,
                        self.model_profile_version,
                        self.model,
                        self.snapshot,
                        self.context_plan,
                    )
                )
            ):
                raise ValueError("旧 Run 只能返回明确的空模型和上下文投影")
        elif self.legacy or any(
            value is None
            for value in (
                self.model_profile_id,
                self.model_profile_version,
                self.model,
                self.snapshot,
            )
        ):
            raise ValueError("新 Run 必须返回安全模型和快照摘要")
        return self


class CancelResponse(StrictModel):
    run_id: Identity
    status: RunStatus


class MessageIdData(StrictModel):
    message_id: Identity


class TaskIdData(StrictModel):
    task_id: Identity


class LeasedData(TaskIdData):
    worker_id: Identity
    attempt: PositiveInt
    generation: PositiveInt


class RetrievalData(StrictModel):
    count: NonNegativeInt
    items: list[RetrievalItem]


class DeltaData(StrictModel):
    text: str


class ErrorAttemptData(StrictModel):
    error_code: str
    attempt: NonNegativeInt


class CompletedData(MessageIdData):
    citations: list[Citation]


class CancelledData(StrictModel):
    reason: Literal["user_requested"]


class ControlIdentity(StrictModel):
    task_id: Identity | None
    attempt: NonNegativeInt | None
    generation: NonNegativeInt | None


class ExecutionIdentity(StrictModel):
    task_id: Identity
    attempt: PositiveInt
    generation: PositiveInt


class CreatedDataV2(ControlIdentity, MessageIdData):
    branch_id: Identity
    operation_kind: OperationKind


class LeasedDataV2(ExecutionIdentity):
    worker_id: Identity


class RetrievalDataV2(ExecutionIdentity, RetrievalData):
    pass


class DeltaDataV2(ExecutionIdentity, DeltaData):
    pass


class RetryDataV2(ExecutionIdentity):
    error_code: Identity


class CompletedDataV2(ExecutionIdentity, CompletedData):
    pass


class SucceededDataV2(ExecutionIdentity, MessageIdData):
    pass


class FailedDataV2(ControlIdentity):
    error_code: Identity


class CancelledDataV2(ControlIdentity, CancelledData):
    pass


class PlannedDataV2(ExecutionIdentity):
    plan: ContextPlanSummary
    omitted_ranges: list[MessageRange] = Field(max_length=200)
    summary_ids: list[Identity] = Field(max_length=200)


class CompactedDataV2(ExecutionIdentity):
    summary: SummaryMetadata


class RelatedRunDataV2(ControlIdentity):
    parent_run_id: Identity
    branch_id: Identity
    user_message_id: Identity


LEGACY_EVENT_DATA: dict[str, type[StrictModel]] = {
    "run.created": MessageIdData,
    "task.queued": TaskIdData,
    "task.leased": LeasedData,
    "run.started": TaskIdData,
    "retrieval.completed": RetrievalData,
    "answer.delta": DeltaData,
    "task.retry_scheduled": ErrorAttemptData,
    "message.completed": CompletedData,
    "run.succeeded": MessageIdData,
    "run.failed": ErrorAttemptData,
    "run.cancelled": CancelledData,
}
EVENT_DATA_V2: dict[str, type[StrictModel]] = {
    "run.created": CreatedDataV2,
    "task.queued": ControlIdentity,
    "task.leased": LeasedDataV2,
    "run.started": ExecutionIdentity,
    "retrieval.completed": RetrievalDataV2,
    "answer.delta": DeltaDataV2,
    "task.retry_scheduled": RetryDataV2,
    "message.completed": CompletedDataV2,
    "run.succeeded": SucceededDataV2,
    "run.failed": FailedDataV2,
    "run.cancelled": CancelledDataV2,
    "context.planned": PlannedDataV2,
    "context.compacted": CompactedDataV2,
    "run.cancelling": CancelledDataV2,
    "run.retry_created": RelatedRunDataV2,
    "run.regenerated": RelatedRunDataV2,
}


class EventResponse(StrictModel):
    schema_version: Literal[1, 2]
    event_id: Identity
    run_id: Identity
    seq: PositiveInt
    type: str
    occurred_at: datetime
    data: dict

    @field_validator("data")
    @classmethod
    def exact_versioned_data(cls, value, info: ValidationInfo):
        # 旧 Journal 必须使用旧 payload，不能按事件同名补造新执行身份。
        version = info.data.get("schema_version")
        types = LEGACY_EVENT_DATA if version == 1 else EVENT_DATA_V2 if version == 2 else {}
        payload = types.get(info.data.get("type", ""))
        if payload is None:
            raise ValueError("不支持的事件版本或类型")
        return payload.model_validate(value).model_dump(mode="json")


class EventListResponse(StrictModel):
    events: list[EventResponse] = Field(max_length=1000)
    next_after_seq: NonNegativeInt
    has_more: bool
