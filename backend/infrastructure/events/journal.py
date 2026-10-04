from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RunEventModel, RunModel


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    data: dict[str, Any],
) -> RunEventModel:
    """锁定 Run 后分配 seq，保证同一 Run 的事件严格递增。"""
    result = await session.execute(
        select(RunModel).where(RunModel.run_id == run_id).with_for_update()
    )
    run = result.scalar_one()
    run.next_event_seq += 1
    event = RunEventModel(
        event_id=str(uuid4()),
        run_id=run_id,
        seq=run.next_event_seq,
        schema_version=1,
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
