"""RAG_001/RAG_002/RAG_003/RAG_005：真实PG召回和生产Provider/Runtime驱动。"""

import asyncio
import base64
import dataclasses
import io
import json
import math
from uuid import uuid4

from docx import Document
from sqlalchemy import select

from backend.config import Settings
from backend.db.models import ChunkModel, DocumentModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.factory import providers_for_snapshot
from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider
from backend.infrastructure.rag.pgvector_store import cosine_similarity, search_chunks
from backend.workers.runtime import WorkerRuntime

arguments = globals().get("SMOKE_INPUT", {})


async def main():
    settings = Settings()
    mode = arguments.get("mode", "fixtures")
    result = {}
    if mode == "fixtures":
        document = Document()
        document.add_paragraph("RAG_004第三格式资料")
        stream = io.BytesIO()
        document.save(stream)
        result = {"docx": base64.b64encode(stream.getvalue()).decode()}
    elif mode == "config":
        # RAG_005：只初始化真实Runtime，不发外部请求，测试Key不进入结果。
        configured = {
            "mock_provider": False,
            "model_base_url": "http://127.0.0.1:9",
            "model_api_key": "safe-test-key-not-a-secret",
            "model_name": "local-test-model",
            "embedding_model_name": "local-test-embedding",
        }
        checks = []
        for missing in (
            ["model_base_url"],
            ["model_api_key"],
            ["model_name"],
            ["embedding_model_name"],
            ["model_base_url", "model_api_key", "model_name", "embedding_model_name"],
        ):
            error = None
            try:
                local = Settings(
                    _env_file=None,
                    **{**settings.model_dump(), **configured, **{key: None for key in missing}},
                )
                WorkerRuntime(local, None, RedisNotifier(local))
            except Exception as exc:
                error = type(exc).__name__
            checks.append({"missing": missing, "error": error})
        mock_embedding, mock_model = providers_for_snapshot({"mock_provider": True}, None)
        real = Settings(_env_file=None, **{**settings.model_dump(), **configured})
        ready, _ = providers_for_snapshot(
            {
                "mock_provider": False,
                "base_url": real.model_base_url,
                "model": real.model_name,
                "embedding_model": real.embedding_model_name,
            },
            real.model_api_key,
        )
        result = {
            "missing": checks,
            "mock_embedding": type(mock_embedding).__name__,
            "mock_model": type(mock_model).__name__,
            "real_configured": type(ready).__name__,
        }
    elif mode == "cosine":
        checks = []
        for left, right in (
            ([1, 0], [1, 0]),
            ([1, 0], [0, 1]),
            ([1, 0], [-1, 0]),
            ([0, 0], [1, 0]),
        ):
            checks.append({"left": left, "right": right, "score": cosine_similarity(left, right)})
        try:
            cosine_similarity([1], [1, 0])
            error = None
        except Exception as exc:
            error = type(exc).__name__
        result = {"checks": checks, "dimension_error": error}
    else:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        embedding = MockEmbeddingProvider(settings.vector_dimension)
        query = embedding.embed(arguments.get("question", "RAG独立问题"))
        try:
            async with factory() as session:
                if mode == "empty":
                    # RAG_003：随机空owner读取真实PG active过滤，不删除其他用例事实。
                    owner = "rag-empty-" + str(uuid4())
                    evidence = await search_chunks(session, owner, query, settings.rag_top_k)
                    deltas = [
                        delta
                        async for delta in MockModelProvider().stream_answer(
                            "RAG_003独立空知识库问题",
                            [dataclasses.asdict(item) for item in evidence],
                        )
                    ]
                    result = {
                        "count": len(evidence),
                        "items": [
                            {"document_id": item.document_id, "chunk_id": item.chunk_id}
                            for item in evidence
                        ],
                        "answer": "".join(deltas).strip(),
                        "deltas": deltas,
                    }
                elif mode == "dimension-error":
                    try:
                        await search_chunks(
                            session, settings.owner_id, query[:-1], settings.rag_top_k
                        )
                        error = None
                    except Exception as exc:
                        error = getattr(exc, "code", type(exc).__name__)
                    result = {"query_dimensions": len(query) - 1, "error": error}
                else:
                    active = list(
                        (
                            await session.execute(
                                select(ChunkModel, DocumentModel)
                                .join(
                                    DocumentModel,
                                    DocumentModel.document_id == ChunkModel.document_id,
                                )
                                .where(
                                    DocumentModel.owner_id == settings.owner_id,
                                    DocumentModel.active_index_batch_id
                                    == ChunkModel.index_batch_id,
                                )
                            )
                        ).all()
                    )
                    # RAG_001：独立数学计算预期得分，不复制生产排序结果作为真值。
                    scores = {}
                    for chunk, _document in active:
                        vector = [float(value) for value in chunk.embedding]
                        denominator = math.sqrt(sum(value * value for value in query)) * math.sqrt(
                            sum(value * value for value in vector)
                        )
                        scores[chunk.chunk_id] = (
                            sum(left * right for left, right in zip(query, vector, strict=True))
                            / denominator
                            if denominator
                            else 0.0
                        )
                    count = len(scores)
                    groups = []
                    for top_k in (settings.rag_top_k, 1, count + 2, 0, -1):
                        try:
                            evidence = await search_chunks(session, settings.owner_id, query, top_k)
                            current = []
                            for item in evidence:
                                source = next(
                                    (chunk, doc)
                                    for chunk, doc in active
                                    if chunk.chunk_id == item.chunk_id
                                )
                                chunk, document = source
                                current.append(
                                    {
                                        "document_id": item.document_id,
                                        "chunk_id": item.chunk_id,
                                        "filename": item.filename,
                                        "start_offset": item.start_offset,
                                        "end_offset": item.end_offset,
                                        "score": float(item.score),
                                        "score_matches": abs(
                                            float(item.score) - scores[item.chunk_id]
                                        )
                                        < 1e-6,
                                        "identity_matches": item.document_id == chunk.document_id
                                        and item.filename == document.filename
                                        and item.text == chunk.text
                                        and item.start_offset == chunk.start_offset
                                        and item.end_offset == chunk.end_offset,
                                        "active_matches": chunk.index_batch_id
                                        == document.active_index_batch_id,
                                    }
                                )
                            groups.append({"k": top_k, "items": current, "error": None})
                        except Exception as exc:
                            groups.append({"k": top_k, "items": [], "error": type(exc).__name__})
                    result = {"n": count, "default_k": settings.rag_top_k, "groups": groups}
        finally:
            await engine.dispose()
    print("SMOKE_JSON:" + json.dumps(result, ensure_ascii=False))


asyncio.run(main())
