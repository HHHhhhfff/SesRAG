import inspect
from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.errors import PermanentTaskError
from backend.config import Settings
from backend.db.models import ChunkModel, DocumentModel, TaskModel
from backend.domain.enums import DocumentState, TaskState
from backend.infrastructure.queue.postgres_queue import mark_succeeded, schedule_retry
from backend.infrastructure.rag.chunker import chunk_text
from backend.infrastructure.rag.parsers import parse_document
from backend.infrastructure.storage.local_files import LocalFileStorage


async def process_index_task(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    task_id: str,
    worker_id: str,
    generation: int,
    embed: Callable[[str], list[float]],
) -> None:
    async with session_factory() as session:
        task = await session.get(TaskModel, task_id)
        if task is None or task.generation != generation or task.worker_id != worker_id:
            return
        document = await session.get(DocumentModel, task.document_id)
        if document is None:
            raise PermanentTaskError("DOCUMENT_NOT_FOUND", "索引任务引用的文档不存在")
        document.status = DocumentState.INDEXING.value
        await session.commit()

    storage = LocalFileStorage(settings.upload_path)
    try:
        storage.read(document.storage_key)
        parsed = parse_document(settings.upload_path / document.storage_key, document.extension)
        chunks = chunk_text(
            parsed.text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
        )
        if not chunks:
            raise PermanentTaskError("EMPTY_DOCUMENT", "文档解析后没有可索引文本")
        batch_id = task.progress_json.get("index_batch_id") or str(uuid4())
        async with session_factory() as session:
            current = await session.get(TaskModel, task_id)
            current_document = await session.get(DocumentModel, document.document_id)
            if current is None or current_document is None:
                return
            if current.generation != generation or current.worker_id != worker_id:
                return
            current.progress_json = {**(current.progress_json or {}), "index_batch_id": batch_id}
            await session.execute(
                delete(ChunkModel).where(
                    ChunkModel.document_id == document.document_id,
                    ChunkModel.index_batch_id == batch_id,
                )
            )
            for draft in chunks:
                vector = embed(draft.text)
                if inspect.isawaitable(vector):
                    vector = await vector
                if len(vector) != settings.vector_dimension:
                    raise PermanentTaskError(
                        "EMBEDDING_DIMENSION_MISMATCH", "Embedding 维度与配置不一致"
                    )
                session.add(
                    ChunkModel(
                        chunk_id=str(uuid4()),
                        document_id=document.document_id,
                        index_batch_id=batch_id,
                        seq=draft.seq,
                        text=draft.text,
                        start_offset=draft.start_offset,
                        end_offset=draft.end_offset,
                        embedding=vector,
                    )
                )
            current_document.active_index_batch_id = batch_id
            current_document.status = DocumentState.INDEXED.value
            current_document.last_error_code = None
            await session.execute(
                delete(ChunkModel).where(
                    ChunkModel.document_id == document.document_id,
                    ChunkModel.index_batch_id != batch_id,
                )
            )
            await session.commit()
        async with session_factory() as session:
            await mark_succeeded(session, task_id, worker_id, generation)
    except PermanentTaskError as exc:
        async with session_factory() as session:
            current = await session.get(TaskModel, task_id)
            current_document = await session.get(DocumentModel, document.document_id)
            if current is not None and current_document is not None:
                current.state = TaskState.FAILED.value
                current.last_error_code = exc.code
                current.last_error_message = exc.message
                current_document.status = DocumentState.FAILED.value
                current_document.last_error_code = exc.code
                await session.commit()
        raise
    except Exception as exc:
        async with session_factory() as session:
            await schedule_retry(
                session,
                task_id,
                worker_id,
                generation,
                settings,
                "INDEX_FAILED",
                str(exc),
            )
        raise
