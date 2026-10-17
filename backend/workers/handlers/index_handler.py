from collections.abc import Callable
from functools import partial
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.errors import PermanentTaskError
from backend.application.task_execution import check_locked_times, guarded_call, lock_execution
from backend.application.vector_validation import validate_vector
from backend.config import Settings
from backend.db.models import DocumentModel
from backend.domain.enums import DocumentState, TaskState
from backend.domain.ports import EmbeddingPort, IndexedChunk, ParserPort, VectorStorePort
from backend.infrastructure.rag.chunker import chunk_text


async def process_index_task(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    task_id: str,
    worker_id: str,
    generation: int,
    provider: EmbeddingPort,
    parser: ParserPort,
    vector_store_factory: Callable[[AsyncSession], VectorStorePort],
) -> None:
    async with session_factory() as session:
        task, _ = await lock_execution(session, task_id, worker_id, generation)
        document = await session.scalar(
            select(DocumentModel)
            .where(DocumentModel.document_id == task.document_id)
            .with_for_update()
        )
        if document is None:
            raise PermanentTaskError("DOCUMENT_NOT_FOUND", "索引任务引用的文档不存在")
        check_locked_times(task.lease_expires_at, task.deadline_at)
        document.status = DocumentState.INDEXING.value
        document_id, storage_key, extension = (
            document.document_id,
            document.storage_key,
            document.extension,
        )
        batch_id = task.progress_json.get("index_batch_id") or str(uuid4())
        lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
        await session.flush()
        check_locked_times(lease_expires_at, deadline_at)
        await session.commit()

    guarded = partial(guarded_call, session_factory, task_id, worker_id, generation)
    parsed = await guarded(partial(parser.parse, storage_key, extension))
    drafts = chunk_text(parsed.text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
    if not drafts or parsed.text == "":
        raise PermanentTaskError("EMPTY_DOCUMENT", "文档没有可索引文本")
    candidates = []
    for draft in drafts:
        vector = validate_vector(await guarded(partial(provider.embed, draft.text)))
        candidates.append(
            IndexedChunk(
                str(uuid4()),
                draft.seq,
                draft.text,
                draft.start_offset,
                draft.end_offset,
                vector,
                tuple(
                    p
                    for p in parsed.locations
                    if p.end_offset > draft.start_offset and p.start_offset < draft.end_offset
                ),
            )
        )

    # 外部解析/Embedding 全部完成后才拿发布锁；失败没有候选持久残留。
    async with session_factory() as session:
        current, _ = await lock_execution(session, task_id, worker_id, generation)
        current_document = await session.scalar(
            select(DocumentModel)
            .where(DocumentModel.document_id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if current_document is None:
            raise PermanentTaskError("DOCUMENT_NOT_FOUND", "索引任务引用的文档不存在")
        lease_expires_at, deadline_at = current.lease_expires_at, current.deadline_at
        check_locked_times(lease_expires_at, deadline_at)
        await vector_store_factory(session).replace(document_id, batch_id, candidates)
        await session.flush()
        # flush/后续锁等待也可能跨越租约；最终事实改变前再次校验。
        check_locked_times(lease_expires_at, deadline_at)
        current.progress_json = {**current.progress_json, "index_batch_id": batch_id}
        current_document.active_index_batch_id = batch_id
        current_document.status = DocumentState.INDEXED.value
        current_document.last_error_code = None
        current.state = TaskState.SUCCEEDED.value
        current.lease_expires_at = None
        await session.flush()
        check_locked_times(lease_expires_at, deadline_at)
        await session.commit()
