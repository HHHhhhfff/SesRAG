from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RunEventModel, RunModel

RESERVED_EVENTS = {
    "run.failed",
    "run.cancelled",
    "run.cancelling",
    "message.completed",
    "run.succeeded",
}


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    data: dict[str, Any],
) -> RunEventModel:
    """锁定 Run 后分配 seq，保证同一 Run 的事件严格递增。"""
    # 只有当前事务已持有 Run 锁才允许保留本事务修改；旧 identity 必须刷新。
    locked = session.info.get("locked_runs", {}).get(run_id)
    if locked is not None and locked is session.sync_session.get_transaction():
        await session.flush()
    result = await session.execute(
        select(RunModel)
        .where(RunModel.run_id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    run = result.scalar_one()
    session.info.setdefault("locked_runs", {})[run_id] = session.sync_session.get_transaction()
    if run.status in {"succeeded", "failed", "cancelled"}:
        # 允许当前结算事务写事实事件，但终态提交后禁止任何追加。
        terminal = await session.scalar(
            select(RunEventModel.event_id)
            .where(
                RunEventModel.run_id == run_id,
                RunEventModel.type.in_(["run.succeeded", "run.failed", "run.cancelled"]),
            )
            .limit(1)
        )
        if terminal or event_type not in {f"run.{run.status}", "message.completed"}:
            raise ValueError("RUN_TERMINAL")
    if run.execution_schema_version == 2:
        from backend.api.schemas.v2.runs import EVENT_DATA_V2
        from backend.application.errors import PermanentTaskError
        from backend.db.models import TaskModel

        if event_type not in RESERVED_EVENTS:
            count = await session.scalar(
                select(func.count())
                .select_from(RunEventModel)
                .where(RunEventModel.run_id == run_id, RunEventModel.type.not_in(RESERVED_EVENTS))
            )
            if count >= run.snapshot_json["execution"]["max_regular_events"]:
                raise PermanentTaskError("RUN_EVENT_LIMIT", "Run 事件数量超过上限")
        control = event_type in {
            "run.created",
            "task.queued",
            "run.retry_created",
            "run.regenerated",
            "run.cancelling",
            "run.cancelled",
        }
        task = await session.get(TaskModel, run.primary_task_id)
        execution = (
            {"task_id": task.task_id, "attempt": task.attempt, "generation": task.generation}
            if task and task.attempt
            else {"task_id": None, "attempt": None, "generation": None}
        )
        data = {
            **data,
            **({"task_id": None, "attempt": None, "generation": None} if control else execution),
        }
        data = EVENT_DATA_V2[event_type].model_validate(data).model_dump(mode="json")
    run.next_event_seq += 1
    event = RunEventModel(
        event_id=str(uuid4()),
        run_id=run_id,
        seq=run.next_event_seq,
        schema_version=run.execution_schema_version,
        type=event_type,
        payload_json=data,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event


async def list_events(
    session: AsyncSession, run_id: str, after_seq: int = 0
) -> list[RunEventModel]:
    result = await session.execute(
        select(RunEventModel)
        .where(RunEventModel.run_id == run_id, RunEventModel.seq > after_seq)
        .order_by(RunEventModel.seq)
    )
    return list(result.scalars())
