from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import MessageModel, RunModel, TaskModel, ThreadModel
from backend.domain.enums import MessageRole, MessageStatus, RunState, TaskKind, TaskState
from backend.infrastructure.events.journal import append_event


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def create_thread(session: AsyncSession, settings: Settings, title: str) -> ThreadModel:
    thread = ThreadModel(thread_id=str(uuid4()), owner_id=settings.owner_id, title=title.strip())
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread


async def list_threads(session: AsyncSession, settings: Settings) -> list[ThreadModel]:
    result = await session.execute(
        select(ThreadModel)
        .where(ThreadModel.owner_id == settings.owner_id)
        .order_by(ThreadModel.updated_at.desc())
    )
    return list(result.scalars())


async def get_thread(session: AsyncSession, settings: Settings, thread_id: str) -> ThreadModel:
    thread = await session.get(ThreadModel, thread_id)
    if thread is None or thread.owner_id != settings.owner_id:
        raise ApplicationError("THREAD_NOT_FOUND", "Thread 不存在", 404)
    return thread


async def archive_thread(session: AsyncSession, settings: Settings, thread_id: str) -> ThreadModel:
    thread = await get_thread(session, settings, thread_id)
    thread.archived_at = now_utc()
    await session.commit()
    return thread


async def create_message_run(
    session: AsyncSession,
    settings: Settings,
    thread_id: str,
    content: str,
    idempotency_key: str | None,
) -> tuple[MessageModel, RunModel, TaskModel, bool]:
    thread = await get_thread(session, settings, thread_id)
    if idempotency_key:
        existing = await session.execute(
            select(MessageModel).where(
                MessageModel.thread_id == thread_id,
                MessageModel.idempotency_key == idempotency_key,
            )
        )
        message = existing.scalar_one_or_none()
        if message is not None and message.run_id:
            run = await session.get(RunModel, message.run_id)
            if run is None:
                raise ApplicationError("RUN_NOT_FOUND", "幂等消息关联的 Run 不存在", 500)
            task_result = await session.execute(
                select(TaskModel).where(TaskModel.run_id == run.run_id)
            )
            return message, run, task_result.scalar_one(), True

    await session.refresh(thread, with_for_update=True)
    thread.next_message_seq += 1
    thread.updated_at = now_utc()
    message = MessageModel(
        message_id=str(uuid4()),
        thread_id=thread_id,
        seq=thread.next_message_seq,
        role=MessageRole.USER.value,
        content=content,
        status=MessageStatus.COMPLETED.value,
        idempotency_key=idempotency_key,
    )
    session.add(message)
    run = RunModel(
        run_id=str(uuid4()),
        thread_id=thread_id,
        user_message_id=message.message_id,
        status=RunState.QUEUED.value,
        snapshot_json={
            "model": "mock",
            "retrieval": {"top_k": settings.rag_top_k},
            "prompt_version": 1,
        },
    )
    session.add(run)
    task = TaskModel(
        task_id=str(uuid4()),
        kind=TaskKind.RUN.value,
        run_id=run.run_id,
        state=TaskState.QUEUED.value,
        max_attempts=settings.task_max_attempts,
        available_at=now_utc(),
        deadline_at=datetime.fromtimestamp(
            now_utc().timestamp() + settings.task_deadline,
            tz=timezone.utc,
        ),
    )
    session.add(task)
    await session.flush()
    run.primary_task_id = task.task_id
    message.run_id = run.run_id
    await append_event(session, run.run_id, "run.created", {"message_id": message.message_id})
    await append_event(session, run.run_id, "task.queued", {"task_id": task.task_id})
    await session.commit()
    return message, run, task, False
