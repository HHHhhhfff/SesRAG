from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import MessageModel, RunModel, TaskModel
from backend.domain.enums import RunState, TaskState
from backend.infrastructure.events.journal import append_event, list_events


async def load_run(
    session: AsyncSession, settings: Settings, run_id: str
) -> tuple[RunModel, TaskModel]:
    result = await session.execute(select(RunModel).where(RunModel.run_id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise ApplicationError("RUN_NOT_FOUND", "Run 不存在", 404)
    thread = await session.get(
        __import__("backend.db.models", fromlist=["ThreadModel"]).ThreadModel, run.thread_id
    )
    if thread is None or thread.owner_id != settings.owner_id:
        raise ApplicationError("RUN_NOT_FOUND", "Run 不存在", 404)
    task_result = await session.execute(
        select(TaskModel).where(TaskModel.task_id == run.primary_task_id)
    )
    return run, task_result.scalar_one()


async def cancel_run(session: AsyncSession, settings: Settings, run_id: str) -> RunModel:
    run, task = await load_run(session, settings, run_id)
    if run.status in {RunState.SUCCEEDED.value, RunState.FAILED.value, RunState.CANCELLED.value}:
        return run
    run.cancel_requested_at = datetime.now(timezone.utc)
    run.status = RunState.CANCELLED.value
    if task.state not in {TaskState.SUCCEEDED.value, TaskState.FAILED.value}:
        task.state = TaskState.CANCELLED.value
    await append_event(session, run.run_id, "run.cancelled", {"reason": "user_requested"})
    await session.commit()
    return run


def event_to_dict(event) -> dict:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "run_id": event.run_id,
        "seq": event.seq,
        "type": event.type,
        "occurred_at": event.created_at,
        "data": event.payload_json,
    }


async def get_run_detail(session: AsyncSession, settings: Settings, run_id: str) -> dict:
    run, task = await load_run(session, settings, run_id)
    return {
        "run_id": run.run_id,
        "thread_id": run.thread_id,
        "status": run.status,
        "user_message_id": run.user_message_id,
        "assistant_message_id": run.assistant_message_id,
        "task": {
            "task_id": task.task_id,
            "kind": task.kind,
            "state": task.state,
            "attempt": task.attempt,
            "worker_id": task.worker_id,
            "generation": task.generation,
            "lease_expires_at": task.lease_expires_at,
            "last_error_code": task.last_error_code,
        },
        "last_error_code": run.last_error_code,
    }


async def get_run_events(
    session: AsyncSession, settings: Settings, run_id: str, after_seq: int
) -> list[dict]:
    await load_run(session, settings, run_id)
    return [event_to_dict(event) for event in await list_events(session, run_id, after_seq)]


async def get_thread_detail(session: AsyncSession, settings: Settings, thread_id: str) -> dict:
    from backend.db.models import ThreadModel

    thread = await session.get(ThreadModel, thread_id)
    if thread is None or thread.owner_id != settings.owner_id:
        raise ApplicationError("THREAD_NOT_FOUND", "Thread 不存在", 404)
    messages_result = await session.execute(
        select(MessageModel).where(MessageModel.thread_id == thread_id).order_by(MessageModel.seq)
    )
    runs_result = await session.execute(
        select(RunModel).where(RunModel.thread_id == thread_id).order_by(RunModel.created_at.desc())
    )
    return {
        "thread": thread,
        "messages": [
            {
                "message_id": item.message_id,
                "thread_id": item.thread_id,
                "seq": item.seq,
                "role": item.role,
                "content": item.content,
                "status": item.status,
                "run_id": item.run_id,
                "citations": item.citations_json or [],
            }
            for item in messages_result.scalars()
        ],
        "runs": [
            {"run_id": item.run_id, "status": item.status, "created_at": item.created_at}
            for item in runs_result.scalars()
        ],
    }
