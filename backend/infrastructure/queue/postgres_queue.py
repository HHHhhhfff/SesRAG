from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import DocumentModel, RunModel, TaskModel
from backend.infrastructure.events.journal import append_event

TERMINAL = {"succeeded", "failed", "cancelled"}
ACTIVE = {"leased", "running"}


def retry_delay_seconds(attempt: int, base_delay: int) -> int:
    """指数退避有界，避免异常 attempt 引起无界整数增长。"""
    return min(300, base_delay * 2 ** min(20, max(0, attempt - 1)))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def authorization_valid(lease_expires_at: datetime | None, deadline_at: datetime) -> bool:
    """只检查保存的授权时间，不从已清租约/设终态的 ORM 推断授权。"""
    now = utc_now()
    return bool(
        lease_expires_at is not None
        and lease_expires_at.replace(tzinfo=timezone.utc) > now
        and deadline_at.replace(tzinfo=timezone.utc) > now
    )


async def commit_authorized(
    session: AsyncSession, lease_expires_at: datetime | None, deadline_at: datetime
) -> bool:
    """Worker 最后一次写入等待后复查；scheduler 到期结算不使用此入口。"""
    await session.flush()
    if not authorization_valid(lease_expires_at, deadline_at):
        await session.rollback()
        return False
    await session.commit()
    return True


async def lock_task(session: AsyncSession, task_id: str) -> TaskModel | None:
    return (
        await session.execute(
            select(TaskModel)
            .where(TaskModel.task_id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def lock_run(session: AsyncSession, run_id: str) -> RunModel:
    run = (
        await session.execute(
            select(RunModel)
            .where(RunModel.run_id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    session.info.setdefault("locked_runs", {})[run_id] = session.sync_session.get_transaction()
    return run


def lease_valid(task: TaskModel) -> bool:
    now = utc_now()
    return bool(
        task.state in ACTIVE
        and task.lease_expires_at
        and task.lease_expires_at.replace(tzinfo=timezone.utc) > now
        and task.deadline_at.replace(tzinfo=timezone.utc) > now
    )


async def lock_owned_task(
    session: AsyncSession, task_id: str, worker_id: str, generation: int
) -> TaskModel | None:
    # 锁定后重新读取，防止 identity map 中旧状态绕过 generation/租约条件。
    now = utc_now()
    task = (
        await session.execute(
            select(TaskModel)
            .where(
                TaskModel.task_id == task_id,
                TaskModel.worker_id == worker_id,
                TaskModel.generation == generation,
                TaskModel.state.in_(ACTIVE),
                TaskModel.lease_expires_at > now,
                TaskModel.deadline_at > now,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return task if task is not None and lease_valid(task) else None


async def settle_failure(
    session: AsyncSession,
    task: TaskModel,
    error_code: str,
    *,
    retry: bool = False,
    require_active: bool = False,
) -> bool:
    """调用方持有 Task 锁；Run/Document 与 Task 在同事务内结算。"""
    run = None
    document = None
    if task.run_id:
        run = await lock_run(session, task.run_id)
        if run.status in TERMINAL:
            return False
    elif task.document_id:
        document = (
            await session.execute(
                select(DocumentModel)
                .where(DocumentModel.document_id == task.document_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
    if require_active and not lease_valid(task):
        return False
    task.state = "retry_waiting" if retry else "failed"
    task.lease_expires_at = None
    task.last_error_code = error_code
    task.last_error_message = "任务执行失败，可按错误码诊断"
    if run is not None:
        run.status = task.state
        run.last_error_code = error_code
        await append_event(
            session,
            run.run_id,
            "task.retry_scheduled" if retry else "run.failed",
            {"error_code": error_code, "attempt": task.attempt},
        )
    if document is not None:
        document.status = "indexing" if retry else "failed"
        document.last_error_code = error_code
    return True


async def claim_next_task(
    session: AsyncSession, worker_id: str, settings: Settings
) -> TaskModel | None:
    now = utc_now()
    task = (
        await session.execute(
            select(TaskModel)
            .where(
                TaskModel.state == "queued",
                TaskModel.available_at <= now,
                TaskModel.deadline_at > now,
                TaskModel.attempt < TaskModel.max_attempts,
            )
            .order_by(TaskModel.available_at, TaskModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if task is None:
        await session.rollback()
        return None
    # 等待 Run 锁期间不能消耗领取次数；全部锁取得后才建立新租约。
    if task.run_id:
        run = await lock_run(session, task.run_id)
        if run.status in TERMINAL:
            await session.rollback()
            return None
    now = utc_now()
    if task.deadline_at.replace(tzinfo=timezone.utc) <= now:
        await settle_failure(session, task, "TASK_DEADLINE_EXCEEDED")
        await session.commit()
        return None
    task.state = "leased"
    task.worker_id = worker_id
    task.generation += 1
    task.attempt += 1
    task.lease_expires_at = min(
        task.deadline_at.replace(tzinfo=timezone.utc),
        now + timedelta(seconds=settings.task_lease_ttl),
    )
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    if task.run_id:
        await append_event(
            session,
            task.run_id,
            "task.leased",
            {
                "task_id": task.task_id,
                "worker_id": worker_id,
                "generation": task.generation,
                "attempt": task.attempt,
            },
        )
    if not await commit_authorized(session, lease_expires_at, deadline_at):
        return None
    return task


async def renew_lease(
    session: AsyncSession, task_id: str, worker_id: str, generation: int, settings: Settings
) -> bool:
    task = await lock_owned_task(session, task_id, worker_id, generation)
    if task is None:
        await session.rollback()
        return False
    # 新 lease 不能复活等待中已到期的旧授权。
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    task.lease_expires_at = min(
        task.deadline_at.replace(tzinfo=timezone.utc),
        utc_now() + timedelta(seconds=settings.task_lease_ttl),
    )
    return await commit_authorized(session, lease_expires_at, deadline_at)


async def mark_running(
    session: AsyncSession, task_id: str, worker_id: str, generation: int
) -> bool:
    task = await lock_owned_task(session, task_id, worker_id, generation)
    if task is None or task.state != "leased":
        await session.rollback()
        return False
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    task.state = "running"
    return await commit_authorized(session, lease_expires_at, deadline_at)


async def mark_succeeded(
    session: AsyncSession, task_id: str, worker_id: str, generation: int
) -> bool:
    task = await lock_owned_task(session, task_id, worker_id, generation)
    if task is None or task.state != "running" or task.run_id is not None:
        await session.rollback()
        return False
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    task.state = "succeeded"
    task.lease_expires_at = None
    return await commit_authorized(session, lease_expires_at, deadline_at)


async def schedule_retry(
    session: AsyncSession,
    task_id: str,
    worker_id: str,
    generation: int,
    settings: Settings,
    error_code: str,
    error_message: str = "",
    *,
    permanent: bool = False,
) -> bool:
    del error_message  # 原始异常可能含凭证或路径，不持久化。
    task = await lock_owned_task(session, task_id, worker_id, generation)
    if task is None:
        await session.rollback()
        return False
    retry = not permanent and task.attempt < task.max_attempts
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    task.available_at = utc_now() + timedelta(
        seconds=retry_delay_seconds(task.attempt, settings.task_retry_base_delay)
    )
    if not await settle_failure(session, task, error_code, retry=retry, require_active=True):
        await session.rollback()
        return False
    return await commit_authorized(session, lease_expires_at, deadline_at)


async def release_task(
    session: AsyncSession, task_id: str, worker_id: str, generation: int, settings: Settings
) -> bool:
    return await schedule_retry(session, task_id, worker_id, generation, settings, "WORKER_STOPPED")


async def requeue_expired(session: AsyncSession) -> int:
    now = utc_now()
    tasks = list(
        (
            await session.execute(
                select(TaskModel)
                .where(
                    TaskModel.state.not_in(TERMINAL),
                    or_(
                        TaskModel.deadline_at <= now,
                        (TaskModel.state.in_(ACTIVE) & (TaskModel.lease_expires_at <= now)),
                        (TaskModel.state == "retry_waiting") & (TaskModel.available_at <= now),
                        (TaskModel.state == "queued")
                        & (TaskModel.attempt >= TaskModel.max_attempts),
                    ),
                )
                .order_by(TaskModel.task_id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )
    for task in tasks:
        deadline = task.deadline_at.replace(tzinfo=timezone.utc) <= now
        if deadline or task.attempt >= task.max_attempts:
            await settle_failure(
                session, task, "TASK_DEADLINE_EXCEEDED" if deadline else "TASK_ATTEMPTS_EXHAUSTED"
            )
        else:
            task.state = "queued"
            task.worker_id = None
            task.lease_expires_at = None
            task.available_at = now
    await session.commit()
    return len(tasks)
