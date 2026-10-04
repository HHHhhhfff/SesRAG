import pytest
from sqlalchemy import select

from backend.application.documents import create_document
from backend.config import Settings
from backend.db.base import Base
from backend.db.models import ChunkModel, DocumentModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.infrastructure.rag.pgvector_store import search_chunks
from backend.workers.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_worker_indexes_document_and_searches_active_batch(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'document.db'}",
        upload_dir=str(tmp_path / "uploads"),
        auto_create_schema=True,
        redis_enabled=False,
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session:
        document, task = await create_document(
            session,
            settings,
            "guide.md",
            "text/markdown",
            "持久化会话需要保存 Thread、Message 和 Run。".encode("utf-8"),
        )

    runtime = WorkerRuntime(settings, factory, RedisNotifier(settings))
    assert await runtime.run_once() is True

    async with factory() as session:
        saved = await session.get(DocumentModel, document.document_id)
        chunks = list((await session.execute(select(ChunkModel))).scalars())
        evidence = await search_chunks(
            session,
            settings.owner_id,
            MockEmbeddingProvider(settings.vector_dimension).embed("持久化会话"),
            5,
        )
        assert saved.status == "indexed"
        assert saved.active_index_batch_id is not None
        assert chunks
        assert evidence
        assert evidence[0].document_id == document.document_id

    await engine.dispose()
