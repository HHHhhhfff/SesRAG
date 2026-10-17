import math
from dataclasses import asdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.errors import PermanentTaskError
from backend.application.vector_validation import validate_vector
from backend.db.models import ChunkModel, DocumentModel
from backend.domain.ports import Evidence, SourceLocation


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


async def search_chunks(
    session: AsyncSession,
    owner_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[Evidence]:
    """读取当前 active batch；Demo 规模下在 Python 排序，列仍使用 pgvector 存储。"""
    if type(top_k) is not int or top_k <= 0:
        raise PermanentTaskError("INVALID_TOP_K", "检索数量必须为正整数")
    query_embedding = validate_vector(query_embedding)
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
                index_batch_id=chunk.index_batch_id,
                filename=document.filename,
                text=chunk.text,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                score=cosine_similarity(query_embedding, validate_vector(list(chunk.embedding))),
                locations=tuple(SourceLocation(**p) for p in chunk.locations_json),
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


class PgVectorStore:
    """由应用事务绑定的向量适配器；发布不自行提交。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, owner_id, vector, top_k):
        return await search_chunks(self.session, owner_id, vector, top_k)

    async def replace(self, document_id, batch_id, chunks):
        await self.session.execute(delete(ChunkModel).where(ChunkModel.document_id == document_id))
        for chunk in chunks:
            self.session.add(
                ChunkModel(
                    chunk_id=chunk.chunk_id,
                    document_id=document_id,
                    index_batch_id=batch_id,
                    seq=chunk.seq,
                    text=chunk.text,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    embedding=validate_vector(chunk.embedding),
                    locations_json=[asdict(p) for p in chunk.locations],
                )
            )
