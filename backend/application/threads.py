from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import BranchModel, MessageModel, RunModel, TaskModel, ThreadModel
from backend.domain.enums import MessageRole, MessageStatus, RunState, TaskKind, TaskState
from backend.infrastructure.events.journal import append_event


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def create_thread(
    session: AsyncSession, settings: Settings, title: str, *, conversation_version=1
) -> ThreadModel:
    thread = ThreadModel(
        thread_id=str(uuid4()),
        owner_id=settings.owner_id,
        title=title.strip(),
        conversation_version=conversation_version,
    )
    session.add(thread)
    await session.flush()
    session.add(
        BranchModel(
            branch_id=str(uuid4()),
            thread_id=thread.thread_id,
            name="默认分支",
            is_default=True,
            version=0,
        )
    )
    await session.commit()
    await session.refresh(thread)
    return thread


async def list_threads(session: AsyncSession, settings: Settings) -> list[ThreadModel]:
    result = await session.execute(
        select(ThreadModel)
        .where(ThreadModel.owner_id == settings.owner_id, ThreadModel.conversation_version == 1)
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
    await session.refresh(thread, with_for_update=True)
    require_v1_thread(thread)
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
    # 同线程的幂等复查和 seq 分配必须由同一把行锁保护。
    await session.refresh(thread, with_for_update=True)
    require_v1_thread(thread)
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

    from backend.application.branches import ACTIVE_RUN_STATES, default_branch

    branch = await default_branch(session, thread_id)
    await session.refresh(branch, with_for_update=True)
    if thread.archived_at is not None:
        raise ApplicationError("THREAD_ARCHIVED", "Thread 已归档", 409)
    if await session.scalar(
        select(RunModel.run_id).where(
            RunModel.branch_id == branch.branch_id, RunModel.status.in_(ACTIVE_RUN_STATES)
        )
    ):
        raise ApplicationError("BRANCH_BUSY", "Branch 存在活动 Run", 409)
    thread.next_message_seq += 1
    thread.updated_at = now_utc()
    message = MessageModel(
        message_id=str(uuid4()),
        thread_id=thread_id,
        branch_id=branch.branch_id,
        seq=thread.next_message_seq,
        role=MessageRole.USER.value,
        source="user_input",
        content=content,
        status=MessageStatus.COMPLETED.value,
        idempotency_key=idempotency_key,
    )
    session.add(message)
    await session.flush()
    branch.head_message_id = message.message_id
    branch.version += 1
    run = RunModel(
        run_id=str(uuid4()),
        thread_id=thread_id,
        branch_id=branch.branch_id,
        execution_schema_version=1,
        operation_kind="initial",
        user_message_id=message.message_id,
        status=RunState.QUEUED.value,
        snapshot_json={
            "mock_provider": settings.mock_provider,
            "model": "mock" if settings.mock_provider else settings.model_name,
            "embedding_model": settings.embedding_model_name,
            "base_url": safe_base_url(settings.model_base_url),
            "vector_dimension": settings.vector_dimension,
            "owner_id": settings.owner_id,
            "retrieval": {"top_k": settings.rag_top_k},
            "prompt_version": 1,
        },
    )
    session.add(run)
    await session.flush()
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
    await session.flush()
    await append_event(session, run.run_id, "run.created", {"message_id": message.message_id})
    await append_event(session, run.run_id, "task.queued", {"task_id": task.task_id})
    await session.commit()
    return message, run, task, False


def require_v1_thread(thread):
    if thread.conversation_version != 1:
        raise ApplicationError("API_VERSION_REQUIRED", "此会话需要使用 v2 API", 409)


async def upgrade_for_v2_write(session, thread):
    from backend.application.branches import ACTIVE_RUN_STATES

    if thread.conversation_version == 1:
        active = await session.scalar(
            select(RunModel.run_id).where(
                RunModel.thread_id == thread.thread_id,
                RunModel.execution_schema_version == 1,
                RunModel.status.in_(ACTIVE_RUN_STATES),
            )
        )
        if active:
            raise ApplicationError("LEGACY_RUN_ACTIVE", "请先等待或取消旧 Run", 409)
        thread.conversation_version = 2


def safe_base_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ApplicationError("INVALID_PROVIDER_URL", "Provider URL 配置无效", 422)
    return value.rstrip("/")
