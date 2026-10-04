from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    schema_version: int
    event_id: str
    run_id: str
    seq: int
    type: str
    occurred_at: datetime
    data: dict


class RunResponse(BaseModel):
    run_id: str
    thread_id: str
    status: str
    user_message_id: str
    assistant_message_id: str | None
    task: dict
    last_error_code: str | None


class EventListResponse(BaseModel):
    events: list[EventResponse]
