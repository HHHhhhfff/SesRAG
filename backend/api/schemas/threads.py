from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ThreadCreate(BaseModel):
    title: str = Field(default="新会话", min_length=1, max_length=200)


class ThreadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    owner_id: str
    title: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class MessageRunResponse(BaseModel):
    message_id: str
    run_id: str
    task_id: str
    status: str


class MessageResponse(BaseModel):
    message_id: str
    thread_id: str
    seq: int
    role: str
    content: str
    status: str
    run_id: str | None
    citations: list[dict]


class ThreadDetail(BaseModel):
    thread: ThreadSummary
    messages: list[MessageResponse]
    runs: list[dict]
