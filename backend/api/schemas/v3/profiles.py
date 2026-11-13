from typing import Literal

from pydantic import Field

from backend.api.schemas.v3 import StrictModel


class RagProfile(StrictModel):
    kind: Literal["embedding", "rerank", "parser", "retrieval"]
    profile_id: str
    version: int
    available: bool
    unavailable_reason: str | None
    formats: list[str] = Field(default=[], max_length=9)
    verified_formats: list[str] = Field(default=[], max_length=9)
    space_id: str | None = None
    dimension: int | None = None


class RagProfileList(StrictModel):
    items: list[RagProfile] = Field(max_length=200)
