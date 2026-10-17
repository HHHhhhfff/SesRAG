import pytest
from sqlalchemy import func, select

from backend.application.documents import create_document
from backend.application.errors import ApplicationError
from backend.db.models import DocumentModel, TaskModel
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.workers.runtime import WorkerRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["x" * 256 + ".txt", "bad\x00.txt"])
async def test_upload_rejects_unsafe_filename_without_facts(document_db, filename):
    settings, factory = document_db
    async with factory() as session:
        with pytest.raises(ApplicationError) as error:
            await create_document(session, settings, filename, "text/plain", b"hello")
        assert error.value.code == "INVALID_DOCUMENT_FILENAME"
        assert await session.scalar(select(func.count()).select_from(DocumentModel)) == 0
    assert not list(settings.upload_path.rglob("source*"))


async def test_storage_replace_failure_removes_partial_and_preserves_unrelated(
    document_db, monkeypatch
):
    from pathlib import Path

    settings, factory = document_db
    original = Path.replace

    def fail(path, target):
        if str(path).endswith(".tmp"):
            raise OSError("private path")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail)
    async with factory() as session:
        with pytest.raises(ApplicationError) as error:
            await create_document(session, settings, "source.txt", "text/plain", b"hello")
        assert error.value.code == "DOCUMENT_STORAGE_FAILED"
        assert await session.scalar(select(func.count()).select_from(TaskModel)) == 0
    assert list((settings.upload_path / "documents").iterdir()) == []


@pytest.mark.parametrize(
    "content,code", [(b"\xff", "DOCUMENT_ENCODING_INVALID"), (b"", "EMPTY_DOCUMENT")]
)
async def test_parser_failure_settles_task_document_permanently(document_db, content, code):
    settings, factory = document_db
    async with factory() as session:
        document, task = await create_document(
            session, settings, "source.txt", "text/plain", content
        )
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    await worker.run_once()
    async with factory() as session:
        saved = await session.get(TaskModel, task.task_id)
        assert saved.state == "failed" and saved.last_error_code == code and saved.attempt == 1
        doc = await session.get(DocumentModel, document.document_id)
        assert doc.status == "failed" and doc.active_index_batch_id is None


@pytest.mark.parametrize("filename", ["../private.txt", "C:\\private.txt", "/host/private.txt"])
async def test_upload_normalizes_host_paths_to_safe_logical_basename(document_db, filename):
    settings, factory = document_db
    async with factory() as session:
        document, _ = await create_document(session, settings, filename, "text/plain", b"hello")
        assert document.filename == "private.txt"
        assert document.storage_key == f"documents/{document.document_id}/source.txt"


@pytest.mark.asyncio
async def test_slow_embedding_has_no_open_transaction_and_location_survives(document_db):
    from sqlalchemy import event

    from backend.db.models import ChunkModel

    settings, factory = document_db
    async with factory() as session:
        document, task = await create_document(
            session, settings, "note.txt", "text/plain", b"one\ntwo"
        )
    engine = factory.kw["bind"].sync_engine
    transactions = set()

    def begin(connection):
        transactions.add(id(connection))

    def end(connection):
        transactions.discard(id(connection))

    event.listen(engine, "begin", begin)
    event.listen(engine, "commit", end)
    event.listen(engine, "rollback", end)
    observed = []

    class Provider:
        async def embed(self, text):
            observed.append(len(transactions))
            return MockEmbeddingProvider().embed(text)

    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    worker.embedding_provider = Provider()
    await worker.run_once()
    assert observed == [0]
    async with factory() as session:
        saved = await session.get(TaskModel, task.task_id)
        assert saved.state == "succeeded"
        chunk = await session.scalar(select(ChunkModel))
        assert chunk.locations_json == [
            {"kind": "line", "number": 1, "start_offset": 0, "end_offset": 3},
            {"kind": "line", "number": 2, "start_offset": 4, "end_offset": 7},
        ]


@pytest.mark.asyncio
async def test_upload_commit_failure_cleans_only_new_file(document_db, monkeypatch):
    settings, factory = document_db
    settings.upload_path.mkdir(parents=True)
    existing = settings.upload_path / "keep.txt"
    existing.write_bytes(b"old")
    async with factory() as session:

        async def fail():
            raise RuntimeError("secret /host/path")

        monkeypatch.setattr(session, "commit", fail)
        with pytest.raises(ApplicationError) as error:
            await create_document(session, settings, "new.txt", "text/plain", b"hello")
        assert error.value.code == "DOCUMENT_PERSIST_FAILED"
        assert "secret" not in str(error.value)
        assert await session.scalar(select(func.count()).select_from(TaskModel)) == 0
    assert existing.read_bytes() == b"old"
    assert not list(settings.upload_path.rglob("source*"))
