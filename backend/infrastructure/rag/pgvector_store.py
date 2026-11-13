import hashlib
import math
from dataclasses import asdict

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.application.errors import PermanentTaskError
from backend.application.legacy_rag import LEGACY_SPACE, materialize_legacy_text
from backend.application.vector_validation import validate_vector
from backend.db.models import ChunkModel, DocumentModel, utc_now
from backend.db.rag_models import IndexBuildModel, KnowledgeBaseModel
from backend.domain.ports import Evidence, SourceLocation
from backend.domain.rag import digest


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
    """旧协议仅检索可信Mock-384；PostgreSQL内完成精确排序和LIMIT。"""
    if type(top_k) is not int or top_k <= 0:
        raise PermanentTaskError("INVALID_TOP_K", "检索数量必须为正整数")
    query_embedding = validate_vector(query_embedding)
    base = await session.scalar(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.owner_id == owner_id, KnowledgeBaseModel.is_default.is_(True)
        )
    )
    if base is not None and base.embedding_space_id != LEGACY_SPACE.space_id:
        raise PermanentTaskError("LEGACY_RAG_SPACE_UNAVAILABLE", "旧协议不能检索新的向量空间")
    query = (
        select(ChunkModel, DocumentModel)
        .join(DocumentModel, DocumentModel.document_id == ChunkModel.document_id)
        .where(
            DocumentModel.owner_id == owner_id,
            DocumentModel.active_index_batch_id == ChunkModel.index_batch_id,
            ChunkModel.legacy_unverified.is_(False),
            (ChunkModel.space_id.is_(None) | (ChunkModel.space_id == LEGACY_SPACE.space_id)),
            (DocumentModel.knowledge_base_id == base.knowledge_base_id)
            if base
            else DocumentModel.knowledge_base_id.is_(None),
        )
    )
    distances = None
    if session.get_bind().dialect.name == "postgresql":
        scoped = (
            query.with_only_columns(ChunkModel)
            .where(ChunkModel.embedding.is_not(None))
            .cte("legacy_scoped")
            .prefix_with("MATERIALIZED")
        )
        chunk = aliased(ChunkModel, scoped)
        distance = cast(chunk.embedding, Vector()).cosine_distance(query_embedding)
        rows = (
            await session.execute(
                select(chunk, DocumentModel, distance)
                .join(DocumentModel, DocumentModel.document_id == chunk.document_id)
                .order_by(distance, chunk.document_id, chunk.seq, chunk.chunk_id)
                .limit(top_k)
            )
        ).all()
        distances = {row[0].chunk_id: 1 - float(row[2]) for row in rows}
        pairs = [(row[0], row[1]) for row in rows]
    else:
        pairs = [(row[0], row[1]) for row in (await session.execute(query)).all()]
    scored: list[Evidence] = []
    for chunk, document in pairs:
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
                score=distances[chunk.chunk_id]
                if distances is not None
                else cosine_similarity(query_embedding, validate_vector(list(chunk.embedding))),
                locations=tuple(
                    SourceLocation(
                        **{key: p[key] for key in ("kind", "number", "start_offset", "end_offset")}
                    )
                    for p in chunk.locations_json
                    if p.get("kind") in {"line", "paragraph"}
                ),
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
        # 重建不得删除历史引用中的批次；这里只替换本次尚未发布的候选身份。
        document = await self.session.get(DocumentModel, document_id)
        base = await self.session.get(KnowledgeBaseModel, document.knowledge_base_id)
        if base is None or not base.enabled or base.embedding_space_id != LEGACY_SPACE.space_id:
            raise PermanentTaskError("LEGACY_RAG_SPACE_UNAVAILABLE", "旧写入口缺少可信空间")
        if await self.session.get(IndexBuildModel, batch_id):
            raise PermanentTaskError("INDEX_BUILD_IMMUTABLE", "不能覆写已发布的批次")
        job_id, artifact_id = await materialize_legacy_text(self.session, document, chunks)
        # 旧解析/切片语义继续兼容，发布同样登记不可变身份，供v3视图/引用/GC使用。
        self.session.add(
            IndexBuildModel(
                index_batch_id=batch_id,
                document_id=document_id,
                knowledge_base_id=base.knowledge_base_id,
                space_id=LEGACY_SPACE.space_id,
                parse_job_id=job_id,
                artifact_id=artifact_id,
                state="succeeded",
                stage="completed",
                provenance="legacy_verified",
                embedding_snapshot={
                    "profile_id": base.embedding_profile_id,
                    "version": base.embedding_profile_version,
                },
                chunker_snapshot={"kind": "legacy_character_window_v1"},
                manifest_hash=digest([{"seq": c.seq, "text": c.text} for c in chunks]),
                chunk_count=len(chunks),
                published_at=utc_now(),
            )
        )
        await self.session.flush()
        await self.session.execute(
            delete(ChunkModel).where(
                ChunkModel.document_id == document_id, ChunkModel.index_batch_id == batch_id
            )
        )
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
                    space_id=LEGACY_SPACE.space_id,
                    dimension=LEGACY_SPACE.dimension,
                    content_hash=hashlib.sha256(chunk.text.encode()).hexdigest(),
                    locations_json=[asdict(p) for p in chunk.locations],
                )
            )
        document.latest_index_batch_id = batch_id
