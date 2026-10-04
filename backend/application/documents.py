from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import DocumentModel, TaskModel
from backend.domain.enums import DocumentState, TaskKind, TaskState
from backend.infrastructure.storage.local_files import LocalFileStorage

ALLOWED_EXTENSIONS = {".txt", ".md", ".docx"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_document(
    session: AsyncSession,
    settings: Settings,
    filename: str,
    content_type: str | None,
    content: bytes,
) -> tuple[DocumentModel, TaskModel]:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ApplicationError("UNSUPPORTED_DOCUMENT_TYPE", "仅支持 txt、md、docx 文档", 415)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ApplicationError("DOCUMENT_TOO_LARGE", "文档大小不能超过 10 MiB", 413)
    allowed_mime = {
        ".txt": {"text/plain", "application/octet-stream", None},
        ".md": {"text/markdown", "text/plain", "application/octet-stream", None},
        ".docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
            None,
        },
    }
    if content_type not in allowed_mime[extension]:
        raise ApplicationError("DOCUMENT_MIME_MISMATCH", "文档 MIME 类型与扩展名不匹配", 415)

    document_id = str(uuid4())
    storage = LocalFileStorage(settings.upload_path)
    storage_key, content_hash = storage.save(document_id, extension, content)
    batch_id = str(uuid4())
    task_id = str(uuid4())
    try:
        document = DocumentModel(
            document_id=document_id,
            owner_id=settings.owner_id,
            filename=filename,
            extension=extension,
            size_bytes=len(content),
            content_hash=content_hash,
            storage_key=storage_key,
            status=DocumentState.UPLOADED.value,
        )
        task = TaskModel(
            task_id=task_id,
            kind=TaskKind.INDEX_DOCUMENT.value,
            document_id=document_id,
            state=TaskState.QUEUED.value,
            max_attempts=settings.task_max_attempts,
            available_at=utc_now(),
            deadline_at=datetime.fromtimestamp(
                utc_now().timestamp() + settings.task_deadline, tz=timezone.utc
            ),
            progress_json={"index_batch_id": batch_id},
        )
        session.add_all([document, task])
        await session.commit()
    except Exception:
        await session.rollback()
        target = settings.upload_path / storage_key
        if target.exists():
            target.unlink()
        raise
    return document, task


async def list_documents(session: AsyncSession, settings: Settings) -> list[DocumentModel]:
    result = await session.execute(
        select(DocumentModel)
        .where(DocumentModel.owner_id == settings.owner_id)
        .order_by(DocumentModel.created_at.desc())
    )
    return list(result.scalars())


async def create_index_task(
    session: AsyncSession, settings: Settings, document_id: str
) -> TaskModel:
    document = await session.get(DocumentModel, document_id)
    if document is None or document.owner_id != settings.owner_id:
        raise ApplicationError("DOCUMENT_NOT_FOUND", "文档不存在", 404)
    active = await session.execute(
        select(TaskModel).where(
            TaskModel.document_id == document_id,
            TaskModel.kind == TaskKind.INDEX_DOCUMENT.value,
            TaskModel.state.in_(
                [
                    TaskState.QUEUED.value,
                    TaskState.LEASED.value,
                    TaskState.RUNNING.value,
                    TaskState.RETRY_WAITING.value,
                ]
            ),
        )
    )
    existing = active.scalar_one_or_none()
    if existing is not None:
        return existing
    task = TaskModel(
        task_id=str(uuid4()),
        kind=TaskKind.INDEX_DOCUMENT.value,
        document_id=document_id,
        state=TaskState.QUEUED.value,
        max_attempts=settings.task_max_attempts,
        available_at=utc_now(),
        deadline_at=datetime.fromtimestamp(
            utc_now().timestamp() + settings.task_deadline, tz=timezone.utc
        ),
        progress_json={"index_batch_id": str(uuid4())},
    )
    document.status = DocumentState.UPLOADED.value
    session.add(task)
    await session.commit()
    return task
