"""可替换基础设施协议；DTO 仅依赖 Python 标准库。"""

from collections.abc import AsyncGenerator, Awaitable, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourceLocation:
    kind: str
    number: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source_name: str
    text: str
    locations: tuple[SourceLocation, ...]


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    chunk_id: str
    seq: int
    text: str
    start_offset: int
    end_offset: int
    embedding: list[float]
    locations: tuple[SourceLocation, ...]


@dataclass(frozen=True, slots=True)
class Evidence:
    document_id: str
    chunk_id: str
    index_batch_id: str
    filename: str
    text: str
    start_offset: int
    end_offset: int
    score: float
    locations: tuple[SourceLocation, ...]


@dataclass(frozen=True, slots=True)
class TaskLease:
    task_id: str
    kind: str
    run_id: str | None
    document_id: str | None
    worker_id: str
    generation: int
    attempt: int


class QueuePort(Protocol):
    async def reclaim(self) -> int: ...
    async def claim(self, worker_id: str) -> TaskLease | None: ...
    async def start(self, task: TaskLease) -> bool: ...
    async def renew(self, task: TaskLease) -> bool: ...
    async def release(self, task: TaskLease) -> bool: ...
    async def fail(self, task: TaskLease, code: str, *, permanent: bool) -> str: ...


class ParserPort(Protocol):
    async def parse(self, storage_key: str, extension: str) -> ParsedDocument: ...


class VectorStorePort(Protocol):
    async def search(self, owner_id: str, vector: list[float], top_k: int) -> list[Evidence]: ...
    async def replace(
        self, document_id: str, batch_id: str, chunks: Sequence[IndexedChunk]
    ) -> None: ...


class EmbeddingPort(Protocol):
    def embed(self, text: str) -> list[float] | Awaitable[list[float]]: ...


class ModelProvider(Protocol):
    def stream_answer(
        self, question: str, evidence: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]: ...


@dataclass(frozen=True, slots=True)
class ModelRequestMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[ModelRequestMessage, ...]
    max_output_tokens: int
    selected_evidence: tuple[tuple[str, str], ...]
    generation_params: dict


class ModelRequestProvider(Protocol):
    def stream_request(self, request: ModelRequest) -> AsyncGenerator[str, None]: ...
