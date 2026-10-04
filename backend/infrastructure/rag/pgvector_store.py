import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ChunkModel, DocumentModel


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


@dataclass(frozen=True, slots=True)
class Evidence:
    document_id: str
    chunk_id: str
    filename: str
    text: str
    start_offset: int
    end_offset: int
    score: float


async def search_chunks(
    session: AsyncSession,
    owner_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[Evidence]:
    """读取当前 active batch；Demo 规模下在 Python 排序，列仍使用 pgvector 存储。"""
    result = await session.execute(
        select(ChunkModel, DocumentModel)
        .join(DocumentModel, DocumentModel.document_id == ChunkModel.document_id)
        .where(
            DocumentModel.owner_id == owner_id,
            DocumentModel.active_index_batch_id == ChunkModel.index_batch_id,
        )
    )
    scored: list[Evidence] = []
    for chunk, document in result.all():
        if chunk.embedding is None:
            continue
        scored.append(
            Evidence(
                document_id=document.document_id,
                chunk_id=chunk.chunk_id,
                filename=document.filename,
                text=chunk.text,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                score=cosine_similarity(query_embedding, list(chunk.embedding)),
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]
