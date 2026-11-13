"""schema3的严格RAG冻结子契约；生成字段仍按原schema2验证。"""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from backend.domain.rag import RetrievalPolicy, StrictModel
from backend.domain.rag_profiles import EmbeddingConfig, RerankConfig

Identity = Annotated[str, Field(min_length=1, max_length=200)]


class FrozenEmbedding(StrictModel):
    profile_id: Identity
    version: int = Field(ge=1)
    config: EmbeddingConfig


class FrozenRerank(StrictModel):
    profile_id: Identity
    version: int = Field(ge=1)
    config: RerankConfig


class FrozenRetrievalProfile(StrictModel):
    profile_id: Identity
    version: int = Field(ge=1)
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class RagToolBinding(StrictModel):
    name: Literal["rag.search"]
    version: Literal[1]


class FrozenRetrievalConfig(StrictModel):
    policy: RetrievalPolicy
    retrieval_profile: FrozenRetrievalProfile
    embedding: FrozenEmbedding
    rerank: FrozenRerank | None
    tool: RagToolBinding
    view_id: Identity


class RagOff(StrictModel):
    enabled: Literal[False]


class RagOn(StrictModel):
    enabled: Literal[True]
    view_id: Identity
    config: FrozenRetrievalConfig


RAG_BINDING: TypeAdapter[RagOn | RagOff] = TypeAdapter(
    Annotated[RagOn | RagOff, Field(discriminator="enabled")]
)


class SearchToolInput(StrictModel):
    schema_version: Literal[1] = 1
    query: str = Field(min_length=1, max_length=8192)
    binding: RagOn


class SearchToolResult(StrictModel):
    schema_version: Literal[2] = 2
    execution_id: Identity
    mode: Literal["ok", "empty", "degraded"]
    bundle_ids: list[Identity] = Field(max_length=100)
