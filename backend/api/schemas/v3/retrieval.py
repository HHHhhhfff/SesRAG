from typing import Literal

from pydantic import Field, model_validator

from backend.api.schemas.v3 import StrictModel
from backend.api.schemas.v3.documents import Location
from backend.domain.rag_profiles import RetrievalFilters


class RetrievalOverrides(StrictModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    rerank_enabled: bool | None = None
    neighbor_radius: int | None = Field(default=None, ge=0, le=2)


class RagSelection(StrictModel):
    enabled: bool = False
    knowledge_base_id: str | None = None
    retrieval_profile_id: str | None = Field(default=None, max_length=80)
    retrieval_profile_version: int | None = Field(default=None, ge=1)
    overrides: RetrievalOverrides = RetrievalOverrides()
    filters: RetrievalFilters = RetrievalFilters()

    @model_validator(mode="after")
    def paired_profile(self):
        if (self.retrieval_profile_id is None) != (self.retrieval_profile_version is None):
            raise ValueError("检索配置身份及版本必须成对")
        return self


class DiagnosticCreate(StrictModel):
    query: str = Field(min_length=1, max_length=8192)
    knowledge_base_id: str
    retrieval_profile_id: str = "default-retrieval"
    retrieval_profile_version: int = Field(default=1, ge=1)
    overrides: RetrievalOverrides = RetrievalOverrides()
    filters: RetrievalFilters = RetrievalFilters()


class Candidate(StrictModel):
    chunk_id: str
    document_id: str
    index_batch_id: str
    dense_score: float = Field(allow_inf_nan=False)
    rerank_score: float | None = Field(default=None, allow_inf_nan=False)
    rerank_input_start: int | None = Field(default=None, ge=0)
    rerank_input_end: int | None = Field(default=None, ge=0)


class Omission(StrictModel):
    chunk_id: str
    reason: str = Field(max_length=100)


class RetrievalExecution(StrictModel):
    execution_id: str
    view_id: str
    origin: Literal["run", "diagnostic"]
    state: Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
    stage: str
    mode: Literal["ok", "empty", "degraded"] | None
    candidates: list[Candidate] = Field(max_length=100)
    bundle_ids: list[str] = Field(max_length=100)
    omitted: list[Omission] = Field(max_length=100)
    error_code: str | None
    timings_ms: dict[str, float] = Field(max_length=10)
    profile: "RetrievalTraceProfile"


class RetrievalTraceProfile(StrictModel):
    retrieval_profile_id: str
    retrieval_profile_version: int = Field(ge=1)
    candidate_k: int = Field(ge=1, le=100)
    top_k: int = Field(ge=1, le=20)


class EvidenceComponent(StrictModel):
    component_id: str
    chunk_id: str
    start_offset: int
    end_offset: int
    content_hash: str


class EvidenceBundle(StrictModel):
    schema_version: Literal[2] = 2
    bundle_id: str
    document_id: str
    index_batch_id: str
    text: str = Field(max_length=4000)
    components: list[EvidenceComponent] = Field(max_length=100)
    locations: list[Location] = Field(max_length=1000)
    dense_score: float = Field(allow_inf_nan=False)
    rerank_score: float | None = Field(default=None, allow_inf_nan=False)
    next_offset: int | None
