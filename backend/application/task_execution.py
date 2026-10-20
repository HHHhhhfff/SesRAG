import asyncio
import inspect
from datetime import timezone
from uuid import uuid4

from sqlalchemy import select

from backend.db.models import BranchModel, MessageModel, ThreadModel
from backend.infrastructure.events.journal import append_event
from backend.infrastructure.queue import postgres_queue as queue


class ExecutionStopped(Exception):
    """取消、丢租或截止后停止执行，不把旧执行者的结果写回。"""


def check_locked_times(lease_expires_at, deadline_at):
    """持有执行锁的发布事务，在最后一次数据库等待后检查原租约时间。"""
    now = queue.utc_now()
    if (
        lease_expires_at is None
        or lease_expires_at.replace(tzinfo=timezone.utc) <= now
        or deadline_at.replace(tzinfo=timezone.utc) <= now
    ):
        raise ExecutionStopped()


async def lock_execution(session, task_id, worker_id, generation):
    task = await queue.lock_owned_task(session, task_id, worker_id, generation)
    if task is None:
        raise ExecutionStopped()
    run = await queue.lock_run(session, task.run_id) if task.run_id else None
    if not queue.lease_valid(task) or (
        run is not None and (run.status in queue.TERMINAL or run.cancel_requested_at)
    ):
        raise ExecutionStopped()
    return task, run


async def check_execution(factory, task_id, worker_id, generation):
    async with factory() as session:
        task, _ = await lock_execution(session, task_id, worker_id, generation)
        return max(
            0.0, (task.deadline_at.replace(tzinfo=timezone.utc) - queue.utc_now()).total_seconds()
        )


async def guarded_call(factory, task_id, worker_id, generation, operation, *, timeout=60):
    """付费调用期间短周期复查租约/取消，并有整步超时。"""
    remaining = await check_execution(factory, task_id, worker_id, generation)

    async def invoke():
        if inspect.iscoroutinefunction(operation):
            return await operation()
        value = await asyncio.to_thread(operation)
        return await value if inspect.isawaitable(value) else value

    pending = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(min(timeout, remaining)):
            while True:
                done, _ = await asyncio.wait({pending}, timeout=0.2)
                await check_execution(factory, task_id, worker_id, generation)
                if done:
                    return pending.result()
    finally:
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


async def append_execution_event(session, task_id, worker_id, generation, event_type, data):
    task, run = await lock_execution(session, task_id, worker_id, generation)
    if run is None:
        raise ExecutionStopped()
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    event = await append_event(session, run.run_id, event_type, data)
    await session.flush()
    check_locked_times(lease_expires_at, deadline_at)
    return event


async def complete_run(session, task_id, worker_id, generation, answer, citations):
    task, run = await lock_execution(session, task_id, worker_id, generation)
    if run is None:
        raise ExecutionStopped()
    thread = (
        await session.execute(
            select(ThreadModel)
            .where(ThreadModel.thread_id == run.thread_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    branch = (
        await session.scalars(
            select(BranchModel)
            .where(BranchModel.branch_id == run.branch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()
    # 等待 Thread 锁期间租约也可能到期，所有锁获得后再次检查。
    if not queue.lease_valid(task):
        raise ExecutionStopped()
    # 终态写入会清空 Task 租约，保留本代原时间用于发布前校验。
    lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
    thread.next_message_seq += 1
    assistant = MessageModel(
        message_id=str(uuid4()),
        thread_id=thread.thread_id,
        branch_id=branch.branch_id,
        seq=thread.next_message_seq,
        role="assistant",
        source="assistant_generation",
        content=answer,
        status="completed",
        run_id=run.run_id,
        citations_json=citations,
    )
    session.add(assistant)
    await session.flush()
    branch.head_message_id = assistant.message_id
    branch.version += 1
    run.assistant_message_id = assistant.message_id
    run.status = "succeeded"
    task.state = "succeeded"
    task.lease_expires_at = None
    await append_event(
        session,
        run.run_id,
        "message.completed",
        {"message_id": assistant.message_id, "citations": citations},
    )
    await append_event(session, run.run_id, "run.succeeded", {"message_id": assistant.message_id})
    await session.flush()
    # 所有最终事实已 flush 后再定发布边界；失效由 session 整组回滚。
    # commit 的网络往返仍有耗时，不将此检查声称为物理时间零延迟提交。
    check_locked_times(lease_expires_at, deadline_at)
    await session.commit()
