from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from backend.api.schemas.v2 import StrictModel
from backend.api.schemas.v2.context import Citation, Identity, NonNegativeInt
from backend.api.schemas.v2.models import PositiveInt, ProfileSelectionRequest
from backend.api.schemas.v2.runs import RunStatus, RunSummary

Title = Annotated[str, Field(min_length=1, max_length=200)]
BranchName = Annotated[str, Field(min_length=1, max_length=80)]
PageLimit = Annotated[int, Field(ge=1, le=200)]


class ThreadCreate(StrictModel):
    title: Title = "新会话"

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("标题不得为空白")
        return value


class ThreadPatch(StrictModel):
    title: Title | None = None
    archived: StrictBool | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        if value is None:
            raise ValueError("标题不得为空白")
        if not isinstance(value, str):
            return value
        if not value.strip():
            raise ValueError("标题不得为空白")
        return value.strip()

    @model_validator(mode="after")
    def supplied_patch(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("必须提供非空的修改字段")
        return self


class BranchCreate(StrictModel):
    parent_branch_id: Identity
    fork_message_id: Identity
    name: BranchName | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        if value is None:
            raise ValueError("分支名称不得为空白")
        if not isinstance(value, str):
            return value
        if not value.strip():
            raise ValueError("分支名称不得为空白")
        return value.strip()


class MessageCreate(ProfileSelectionRequest):
    branch_id: Identity
    content: str = Field(min_length=1, max_length=20000)
    expected_version: NonNegativeInt

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value):
        if not value.strip():
            raise ValueError("消息不得为空白")
        return value


class ThreadListQuery(StrictModel):
    include_archived: bool = False
    cursor: Identity | None = None
    limit: PageLimit = 50


class ThreadDetailQuery(StrictModel):
    branch_id: Identity | None = None
    before_seq: Annotated[int, Field(ge=1)] | None = None
    limit: PageLimit = 50


class ThreadSummary(StrictModel):
    thread_id: Identity
    owner_id: Identity
    # 响应保留旧标题事实；新建和重命名才使用请求 Title 限制。
    title: str
    default_branch_id: Identity
    conversation_version: Literal[1, 2]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class Branch(StrictModel):
    branch_id: Identity
    thread_id: Identity
    parent_branch_id: Identity | None
    fork_message_id: Identity | None
    name: BranchName
    is_default: bool
    head_message_id: Identity | None
    version: NonNegativeInt
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def fork_pair(self):
        if (self.parent_branch_id is None) != (self.fork_message_id is None):
            raise ValueError("父分支和分叉消息必须同时为空或同时存在")
        return self


class MessageResponse(StrictModel):
    message_id: Identity
    thread_id: Identity
    branch_id: Identity
    seq: PositiveInt
    role: Literal["user", "assistant"]
    source: Literal["user_input", "assistant_generation"]
    content: str
    status: str
    run_id: Identity | None
    citations: list[Citation]
    created_at: datetime


class ThreadList(StrictModel):
    threads: list[ThreadSummary] = Field(max_length=200)
    next_cursor: str | None
    has_more: bool


class ThreadDetail(StrictModel):
    thread: ThreadSummary
    branch: Branch
    branch_path: list[Branch] = Field(min_length=1)
    messages: list[MessageResponse] = Field(max_length=200)
    runs: list[RunSummary]
    active_run_id: str | None
    recent_run_id: str | None
    next_before_seq: PositiveInt | None
    has_more: bool


class BranchListResponse(StrictModel):
    branches: list[Branch]


class MessageRunResponse(StrictModel):
    branch_id: Identity
    message_id: Identity
    run_id: Identity
    task_id: Identity
    status: RunStatus
