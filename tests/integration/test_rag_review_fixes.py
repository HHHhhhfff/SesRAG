"""ADR-002 中期审查的兼容性及异常收尾回归。"""

import asyncio
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select

from backend.application.documents import create_document
from backend.application.errors import ApplicationError, PermanentTaskError
from backend.application.vector_validation import validate_vector
from backend.db.models import ChunkModel, DocumentModel, TaskModel
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.rag import parsers
from backend.infrastructure.storage.local_files import LocalFileStorage
from backend.workers.runtime import WorkerRuntime


async def test_nonempty_whitespace_indexes_unchanged(document_db):
    settings, factory = document_db
    async with factory() as session:
        document, task = await create_document(session, settings, "space.txt", "text/plain", b" \n")
    await WorkerRuntime(settings, factory, RedisNotifier(settings)).run_once()
    async with factory() as session:
        assert (await session.get(TaskModel, task.task_id)).state == "succeeded"
        assert (await session.get(DocumentModel, document.document_id)).status == "indexed"
        assert (await session.scalar(select(ChunkModel))).text == " \n"


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_commit_and_rollback_fail_still_attempt_cleanup(
    document_db, monkeypatch, cleanup_fails
):
    settings, factory = document_db
    cleaned = []
    original = LocalFileStorage.remove

    def remove(storage, key):
        cleaned.append(key)
        original(storage, key)
        if cleanup_fails:
            raise OSError("private cleanup path")

    monkeypatch.setattr(LocalFileStorage, "remove", remove)
    async with factory() as session:

        async def fail():
            raise OSError("private database path")

        monkeypatch.setattr(session, "commit", fail)
        monkeypatch.setattr(session, "rollback", fail)
        with pytest.raises(ApplicationError) as error:
            await create_document(session, settings, "new.txt", "text/plain", b"new")
        assert error.value.code == (
            "DOCUMENT_CLEANUP_FAILED" if cleanup_fails else "DOCUMENT_PERSIST_FAILED"
        )
        assert "private" not in str(error.value)
    assert len(cleaned) == 1
    assert list((settings.upload_path / "documents").iterdir()) == []
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(DocumentModel)) == 0
        assert await session.scalar(select(func.count()).select_from(TaskModel)) == 0


def test_save_cleanup_attempts_all_owned_files_when_first_unlink_fails(tmp_path, monkeypatch):
    storage = LocalFileStorage(tmp_path)
    original_unlink = Path.unlink
    attempts = []

    def replace(path, target):
        # 模拟发布步骤在目标已产生后报错；两个拥有文件均需尝试清理。
        target.write_bytes(b"partial")
        raise OSError("publish failed")

    def unlink(path, *args, **kwargs):
        attempts.append(path.name)
        if path.name.endswith(".tmp"):
            raise OSError("unlink denied")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(OSError):
        storage.save("owned", ".txt", b"data")
    assert attempts == ["source.txt.tmp", "source.txt"]
    assert not (tmp_path / "documents/owned/source.txt").exists()


def test_huge_json_integer_is_permanent_vector_error():
    with pytest.raises(PermanentTaskError) as error:
        validate_vector([10**400] + [1] * 383)
    assert error.value.code == "EMBEDDING_INVALID"
    assert validate_vector([1] * 384) == [1.0] * 384


async def test_parser_spawn_error_is_safe_and_retryable(tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("private executable path")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    with pytest.raises(ApplicationError) as error:
        await parsers.SubprocessParser(tmp_path).parse("source.txt", ".txt")
    assert error.value.code == "DOCUMENT_PARSER_UNAVAILABLE" and error.value.retryable
    assert "private" not in str(error.value)


async def test_parser_output_limit_kills_actual_child(tmp_path, monkeypatch):
    import sys

    original = asyncio.create_subprocess_exec
    children = []

    async def spawn(*args, **kwargs):
        child = await original(
            sys.executable,
            "-c",
            "import sys,time; sys.stdout.write('x'*4096); sys.stdout.flush(); time.sleep(1)",
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(parsers, "MAX_OUTPUT_BYTES", 100, raising=False)
    with pytest.raises(PermanentTaskError) as error:
        await parsers.SubprocessParser(tmp_path).parse("source.txt", ".txt")
    assert error.value.code == "DOCUMENT_PARSE_LIMIT"
    assert children[0].returncode is not None


async def test_parser_explicit_cancel_reaps_actual_child(tmp_path, monkeypatch):
    import sys

    original = asyncio.create_subprocess_exec
    children = []
    started = asyncio.Event()

    async def spawn(*args, **kwargs):
        child = await original(sys.executable, "-c", "import time; time.sleep(10)", **kwargs)
        children.append(child)
        started.set()
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(parsers.SubprocessParser(tmp_path).parse("source.txt", ".txt"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert children[0].returncode is not None


def test_zip_entry_limit_precedes_document_parsing(tmp_path, monkeypatch):
    path = tmp_path / "many.docx"
    with ZipFile(path, "w") as archive:
        for index in range(4):
            archive.writestr(str(index), "small")
    monkeypatch.setattr(parsers, "MAX_ZIP_ENTRIES", 3, raising=False)
    with pytest.raises(PermanentTaskError) as error:
        parsers.parse_document(path, ".docx")
    assert error.value.code == "DOCUMENT_PARSE_LIMIT"
