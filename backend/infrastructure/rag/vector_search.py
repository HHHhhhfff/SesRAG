"""带冻结范围的精确召回；PostgreSQL只返回数据库排序后的Top-K。"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, select
from sqlalchemy.orm import aliased

from backend.application.errors import PermanentTaskError
from backend.application.vector_validation import validate_vector
from backend.db.models import ChunkModel, DocumentModel
from backend.db.rag_models import EmbeddingSpaceModel, IndexBuildModel
from backend.domain.rag import DenseHit
from backend.infrastructure.rag.pgvector_store import cosine_similarity


class VectorSearch:
    def __init__(self, session):
        self.session = session

    async def search(self, scope, vector, limit):
        if not scope.batches:
            return ()
        space = await self.session.get(EmbeddingSpaceModel, scope.space_id)
        if space is None or not 1 <= limit <= 100:
            raise PermanentTaskError("INVALID_RAG_PARAMETER", "检索空间或数量无效")
        vector = validate_vector(vector, dimension=space.dimension)
        query = (
            select(ChunkModel, DocumentModel)
            .join(DocumentModel, DocumentModel.document_id == ChunkModel.document_id)
            .join(IndexBuildModel, IndexBuildModel.index_batch_id == ChunkModel.index_batch_id)
            .where(
                DocumentModel.owner_id == scope.owner_id,
                DocumentModel.knowledge_base_id == scope.knowledge_base_id,
                IndexBuildModel.state == "succeeded",
                IndexBuildModel.space_id == scope.space_id,
                ChunkModel.index_batch_id.in_(scope.batches),
                ChunkModel.space_id == scope.space_id,
                ChunkModel.dimension == space.dimension,
                ChunkModel.embedding.is_not(None),
            )
        )
        if self.session.bind.dialect.name == "postgresql":
            # 先物化授权及同空间集合，再执行距离函数，避免优化器跨混维数据求值。
            scoped = query.with_only_columns(ChunkModel).cte("scoped").prefix_with("MATERIALIZED")
            chunk = aliased(ChunkModel, scoped)
            distance = cast(chunk.embedding, Vector()).cosine_distance(vector)
            rows = (
                await self.session.execute(
                    select(chunk, DocumentModel, distance.label("distance"))
                    .join(DocumentModel, DocumentModel.document_id == chunk.document_id)
                    .order_by(
                        distance,
                        chunk.document_id,
                        chunk.index_batch_id,
                        chunk.seq,
                        chunk.chunk_id,
                    )
                    .limit(limit)
                )
            ).all()
            return tuple(self.hit(chunk, doc, 1 - float(distance)) for chunk, doc, distance in rows)
        # SQLite仅供工程测试；正式性能与SQL排序结论必须来自真实PG探针。
        rows = (await self.session.execute(query)).all()
        hits = [
            self.hit(
                chunk,
                doc,
                cosine_similarity(
                    vector, validate_vector(list(chunk.embedding), dimension=space.dimension)
                ),
            )
            for chunk, doc in rows
        ]
        hits.sort(
            key=lambda h: (-h.dense_score, h.document_id, h.index_batch_id, h.seq, h.chunk_id)
        )
        return tuple(hits[:limit])

    @staticmethod
    def hit(chunk, document, score):
        return DenseHit(
            chunk.chunk_id,
            chunk.document_id,
            chunk.index_batch_id,
            chunk.seq,
            document.filename,
            chunk.text,
            chunk.start_offset,
            chunk.end_offset,
            score,
            tuple(chunk.locations_json),
        )
