from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import TaskModel
from backend.domain.enums import TaskState


def retry_delay_seconds(attempt: int, base_delay: int) -> int:
    """计算第 attempt 次失败后的指数退避秒数。"""
    return base_delay * (2 ** max(0, attempt - 1))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_next_task(
    session: AsyncSession, worker_id: str, settings: Settings
) -> TaskModel | None:
    now = utc_now()
    result = await session.execute(
        select(TaskModel)
        .where(
            TaskModel.state == TaskState.QUEUED.value,
            TaskModel.available_at <= now,
            TaskModel.deadline_at > now,
        )
        .order_by(TaskModel.available_at, TaskModel.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None
    task.state = TaskState.LEASED.value
    task.worker_id = worker_id
    task.generation += 1
    task.attempt += 1
    task.lease_expires_at = now + timedelta(seconds=settings.task_lease_ttl)
    await session.commit()
    await session.refresh(task)
    return task


async def renew_lease(
    session: AsyncSession,
    task_id: str,
    worker_id: str,
    generation: int,
    settings: Settings,
) -> bool:
    result = await session.execute(
        select(TaskModel).where(
            TaskModel.task_id == task_id,
            TaskModel.worker_id == worker_id,
            TaskModel.generation == generation,
            TaskModel.state.in_([TaskState.LEASED.value, TaskState.RUNNING.value]),
            TaskModel.lease_expires_at > utc_now(),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        await session.rollback()
        return False
    task.lease_expires_at = utc_now() + timedelta(seconds=settings.task_lease_ttl)
    await session.commit()
    return True


async def mark_running(
    session: AsyncSession, task_id: str, worker_id: str, generation: int
) -> bool:
    result = await session.execute(
        select(TaskModel).where(
            TaskModel.task_id == task_id,
            TaskModel.worker_id == worker_id,
            TaskModel.generation == generation,
            TaskModel.state == TaskState.LEASED.value,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        await session.rollback()
        return False
    task.state = TaskState.RUNNING.value
    await session.commit()
    return True


async def mark_succeeded(
    session: AsyncSession, task_id: str, worker_id: str, generation: int
) -> bool:
    result = await session.execute(
        select(TaskModel).where(
            TaskModel.task_id == task_id,
            TaskModel.worker_id == worker_id,
            TaskModel.generation == generation,
            TaskModel.state == TaskState.RUNNING.value,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        await session.rollback()
        return False
    task.state = TaskState.SUCCEEDED.value
    task.lease_expires_at = None
    await session.commit()
    return True


async def schedule_retry(
    session: AsyncSession,
    task_id: str,
    worker_id: str,
    generation: int,
    settings: Settings,
    error_code: str,
    error_message: str,
) -> bool:
    result = await session.execute(
        select(TaskModel).where(
            TaskModel.task_id == task_id,
            TaskModel.worker_id == worker_id,
            TaskModel.generation == generation,
            TaskModel.state.in_([TaskState.LEASED.value, TaskState.RUNNING.value]),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        await session.rollback()
        return False
    if task.attempt >= task.max_attempts:
        task.state = TaskState.FAILED.value
    else:
        task.state = TaskState.RETRY_WAITING.value
        task.available_at = utc_now() + timedelta(
            seconds=retry_delay_seconds(task.attempt, settings.task_retry_base_delay)
        )
    task.lease_expires_at = None
    task.last_error_code = error_code
    task.last_error_message = error_message[:500]
    await session.commit()
    return True


async def requeue_expired(session: AsyncSession) -> int:
    now = utc_now()
    result = await session.execute(
        select(TaskModel).where(
            TaskModel.state.in_([TaskState.LEASED.value, TaskState.RUNNING.value]),
            TaskModel.lease_expires_at < now,
        )
    )
    tasks = list(result.scalars())
    for task in tasks:
        task.worker_id = None
        task.lease_expires_at = None
        if task.attempt >= task.max_attempts:
            task.state = TaskState.FAILED.value
        else:
            task.state = TaskState.QUEUED.value
            task.available_at = now
    await session.commit()
    return len(tasks)
