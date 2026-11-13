"""PRD-003 的可替换解析、检索和模型能力。"""

from typing import Protocol

from backend.domain.rag import DenseHit, FrozenScope, NormalizedArtifact


class ParseGateway(Protocol):
    async def submit(self, job: dict) -> dict: ...
    async def upload(self, content: bytes, handle: dict) -> None: ...
    async def poll(self, handle: dict) -> dict: ...
    async def download(self, handle: dict) -> bytes: ...


class ArtifactNormalizer(Protocol):
    def normalize(self, package: bytes, extension: str) -> NormalizedArtifact: ...


class EmbeddingPortV2(Protocol):
    async def embed(self, texts: tuple[str, ...], *, purpose: str) -> tuple[list[float], ...]: ...


class VectorSearchPort(Protocol):
    async def search(
        self, scope: FrozenScope, vector: list[float], limit: int
    ) -> tuple[DenseHit, ...]: ...


class RerankPort(Protocol):
    async def rank(self, query: str, texts: tuple[str, ...]) -> tuple[tuple[int, float], ...]: ...
