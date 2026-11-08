"""RAG 的格式、配置、不可变输入输出；不依赖 ORM 或厂商协议。"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.application.errors import ApplicationError

TEXT_FORMATS = frozenset({".txt", ".md"})
OFFICE_FORMATS = frozenset({".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"})
FORMATS = TEXT_FORMATS | OFFICE_FORMATS
ROUTING_VERSION = "format_router_v1"
CONSENT_VERSION = "mineru-office-outbound-v1"


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def parser_for(extension: str) -> str:
    if extension in TEXT_FORMATS:
        return "local"
    if extension in OFFICE_FORMATS:
        return "mineru"
    raise ApplicationError("UNSUPPORTED_DOCUMENT_TYPE", "文件格式不在九格式白名单内", 415)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ParseRequest(StrictModel):
    parser_profile_id: str | None = Field(default=None, min_length=1, max_length=80)
    parser_profile_version: int | None = Field(default=None, ge=1)
    cloud_consent: bool | None = None
    consent_version: str | None = Field(default=None, max_length=80)
    acknowledge_duplicate_cost: bool = False

    @model_validator(mode="after")
    def paired_profile(self):
        if (self.parser_profile_id is None) != (self.parser_profile_version is None):
            raise ValueError("解析配置身份和版本必须成对")
        return self

    def resolve(self, extension: str) -> str:
        route = parser_for(extension)
        if route == "local":
            if self.cloud_consent is not None or self.consent_version is not None:
                raise ApplicationError("INVALID_PARSE_SELECTION", "本地文本不接受云端授权字段", 422)
        elif self.cloud_consent is not True or self.consent_version != CONSENT_VERSION:
            raise ApplicationError(
                "CLOUD_CONSENT_REQUIRED", "本次办公文件操作需要确认完整原件外发", 422
            )
        return route


class EmbeddingSpace(StrictModel):
    provider: str = "mock"
    model: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=120)
    dimension: int = Field(ge=1, le=2000)
    normalization: Literal["none", "l2_float32_v1"] = "none"
    metric: Literal["cosine"] = "cosine"
    purpose_mapping: Literal["identity_v1"] = "identity_v1"

    @property
    def space_id(self) -> str:
        return digest(self.model_dump())


class RetrievalPolicy(StrictModel):
    candidate_k: int = Field(default=20, ge=1, le=100)
    top_k: int = Field(default=5, ge=1, le=20)
    rerank_enabled: bool = False
    failure_policy: Literal["fail", "dense_fallback"] = "fail"
    neighbor_radius: int = Field(default=1, ge=0, le=2)
    max_enhanced_chars: int = Field(default=16000, ge=1, le=64000)

    @model_validator(mode="after")
    def candidate_bound(self):
        if self.top_k > self.candidate_k:
            raise ValueError("最终命中数不能大于候选数")
        return self


@dataclass(frozen=True)
class ParsedBlock:
    block_id: str
    kind: str
    text: str
    start: int
    end: int
    heading_path: tuple[str, ...] = ()
    locations: tuple[dict, ...] = ()


@dataclass(frozen=True)
class NormalizedArtifact:
    text: str
    blocks: tuple[ParsedBlock, ...]
    protocol: str
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChunkDraftV2:
    seq: int
    text: str
    start: int
    end: int
    block_segments: tuple[dict, ...]
    locations: tuple[dict, ...]


@dataclass(frozen=True)
class DenseHit:
    chunk_id: str
    document_id: str
    index_batch_id: str
    seq: int
    filename: str
    text: str
    start: int
    end: int
    dense_score: float
    locations: tuple[dict, ...] = ()
    rerank_score: float | None = None
    rerank_input_start: int | None = None
    rerank_input_end: int | None = None


@dataclass(frozen=True)
class FrozenScope:
    view_id: str
    owner_id: str
    knowledge_base_id: str
    space_id: str
    batches: tuple[str, ...]
    manifest_hash: str


@dataclass(frozen=True)
class RetrievalResult:
    mode: str
    bundles: tuple[dict, ...]
    candidates: tuple[DenseHit, ...]
    omitted: tuple[dict, ...] = ()
    error_code: str | None = None
    timings: dict = field(default_factory=dict)
