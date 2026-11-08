from datetime import datetime

from pydantic import Field

from backend.api.schemas.v3 import StrictModel


class KnowledgeBaseCreate(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    embedding_profile_id: str = Field(min_length=1, max_length=80)
    embedding_profile_version: int = Field(ge=1)


class KnowledgeBasePatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None


class KnowledgeBase(StrictModel):
    knowledge_base_id: str
    name: str
    enabled: bool
    is_default: bool
    embedding_space_id: str
    embedding_profile_id: str
    embedding_profile_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseList(StrictModel):
    items: list[KnowledgeBase] = Field(max_length=200)
    next_cursor: str | None = None
