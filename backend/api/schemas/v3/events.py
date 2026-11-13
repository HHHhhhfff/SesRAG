"""三代Journal读取及schema3严格载荷；旧事件不转写。"""

from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from backend.api.schemas.v2.runs import EVENT_DATA_V2, LEGACY_EVENT_DATA, ExecutionIdentity
from backend.api.schemas.v3 import StrictModel
from backend.api.schemas.v3.sessions import CitationV2


class ToolEvent(ExecutionIdentity):
    call_id: str
    execution_id: str
    tool_version: Literal[1] = 1
    stage: str
    mode: Literal["ok", "empty", "degraded"] | None = None
    count: int | None = Field(default=None, ge=0, le=100)
    error_code: str | None = None


class RetrievalDataV3(ExecutionIdentity):
    count: int = Field(ge=0, le=100)
    execution_id: str | None
    mode: Literal["off", "ok", "empty", "degraded"]
    bundle_ids: list[str] = Field(max_length=100)


class CompletedDataV3(ExecutionIdentity):
    message_id: str
    citations: list[CitationV2] = Field(max_length=100)


EVENT_DATA_V3: dict[str, type[BaseModel]] = {
    **EVENT_DATA_V2,
    "retrieval.completed": RetrievalDataV3,
    "message.completed": CompletedDataV3,
    **{
        kind: ToolEvent
        for kind in (
            "tool.started",
            "tool.stage",
            "tool.completed",
            "tool.failed",
            "tool.cancelled",
        )
    },
}


class Event(StrictModel):
    schema_version: Literal[1, 2, 3]
    event_id: str
    run_id: str
    seq: int = Field(ge=1)
    type: str
    occurred_at: datetime
    data: dict

    @field_validator("data")
    @classmethod
    def payload(cls, value, info: ValidationInfo):
        mapping: Mapping[str, type[BaseModel]]
        if info.data.get("schema_version") == 1:
            mapping = LEGACY_EVENT_DATA
        elif info.data.get("schema_version") == 2:
            mapping = EVENT_DATA_V2
        else:
            mapping = EVENT_DATA_V3
        schema = mapping.get(info.data.get("type", ""))
        if schema is None:
            raise ValueError("事件版本／类型不受支持")
        return schema.model_validate(value).model_dump(mode="json")


class EventList(StrictModel):
    events: list[Event] = Field(max_length=1000)
    next_after_seq: int = Field(ge=0)
    has_more: bool
