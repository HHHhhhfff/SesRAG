from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from backend.api.schemas.v3 import StrictModel
from backend.domain.rag import ParseRequest


class ChunkPolicy(StrictModel):
    mode: Literal["structure_v1", "character_v1"] = "structure_v1"
    size: int = Field(default=800, ge=1, le=16000, strict=True)
    overlap: int = Field(default=120, ge=0, le=15999, strict=True)

    max_chunks: int = Field(default=50000, ge=1, le=50000, strict=True)


class BuildCreate(StrictModel):
    parse: ParseRequest = ParseRequest()
    chunker: ChunkPolicy = ChunkPolicy()


class DocumentPatch(StrictModel):
    tags: list[str] = Field(max_length=20)


class ParseOutcome(StrictModel):
    parse_job_id: str
    parser_profile_id: str | None
    parser_profile_version: int | None = Field(ge=1)
    parser_hash: str
    output_protocol: str | None
    parser_kind: Literal["local", "mineru"]
    routing_policy_version: str
    state: Literal["queued", "running", "waiting", "succeeded", "failed", "cancelled"]
    stage: str
    error_code: str | None
    remote_outcome: str | None
    artifact_id: str | None
    poll_count: int = Field(ge=0, le=60)


class IndexBuild(StrictModel):
    index_batch_id: str
    document_id: str
    knowledge_base_id: str
    state: Literal["queued", "building", "waiting", "succeeded", "failed", "cancelled"]
    stage: str
    task_id: str | None
    parse: ParseOutcome | None
    chunk_count: int = Field(ge=0, le=50000)
    error_code: str | None
    operation_status: Literal["cancelling"] | None = None
    created_at: datetime


class Document(StrictModel):
    document_id: str
    knowledge_base_id: str | None
    filename: str
    extension: str
    size_bytes: int
    content_hash: str
    metadata_version: Literal[1] = 1
    tags: list[str] = Field(max_length=20)
    availability: Literal["none", "ready", "reindex_required"]
    active_index_batch_id: str | None
    latest_build: IndexBuild | None
    created_at: datetime


class DocumentList(StrictModel):
    items: list[Document] = Field(max_length=200)
    next_cursor: str | None = None


class Location(StrictModel):
    kind: Literal["line", "paragraph", "table_cell", "page", "slide", "sheet_range", "block"]
    origin: Literal["source", "normalized"]
    quality: Literal["verified", "block_only"]
    number: int | None = Field(default=None, ge=1)
    end_number: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    sheet_name: str | None = Field(default=None, max_length=200)
    cell_range: str | None = Field(default=None, max_length=100)
    table: int | None = Field(default=None, ge=1)
    row: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_location(self):
        if self.end_offset <= self.start_offset:
            raise ValueError("位置必须是非空右端不含区间")
        if self.kind in {"line", "paragraph", "page", "slide"} and self.number is None:
            raise ValueError("来源位置缺少编号")
        if self.end_number is not None and (self.number is None or self.end_number < self.number):
            raise ValueError("来源编号范围无效")
        if self.kind == "block" and (
            not self.block_id or self.quality != "block_only" or self.origin != "normalized"
        ):
            raise ValueError("规范块位置必须标明仅块来源")
        if self.kind == "sheet_range" and (not self.sheet_name or not self.cell_range):
            raise ValueError("工作表位置缺少可靠范围")
        if self.kind == "table_cell" and any(
            value is None for value in (self.table, self.row, self.column)
        ):
            raise ValueError("表格单元格缺少定位")
        return self


class BlockSegment(StrictModel):
    block_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Chunk(StrictModel):
    chunk_id: str
    document_id: str
    index_batch_id: str
    seq: int
    text: str = Field(max_length=16000)
    start_offset: int
    end_offset: int
    locations: list[Location] = Field(max_length=1000)
    content_hash: str | None = None
    space_id: str | None = None
    dimension: int | None = Field(default=None, ge=1, le=2000)
    block_segments: list[BlockSegment] = Field(default=[], max_length=100000)


class ChunkList(StrictModel):
    items: list[Chunk] = Field(max_length=20)
    next_cursor: str | None = None
