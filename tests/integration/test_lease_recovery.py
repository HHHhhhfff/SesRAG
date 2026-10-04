from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.config import Settings
from backend.db.base import Base
from backend.db.models import TaskModel
from backend.db.session import create_engine, create_session_factory
from backend.domain.enums import TaskKind, TaskState
from backend.infrastructure.queue.postgres_queue import (
    claim_next_task,
    renew_lease,
    requeue_expired,
)


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimed_and_old_generation_cannot_renew(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'lease.db'}",
        upload_dir=str(tmp_path / "uploads"),
        auto_create_schema=True,
        redis_enabled=False,
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    task_id = str(uuid4())
    async with factory() as session:
        session.add(
            TaskModel(
                task_id=task_id,
                kind=TaskKind.RUN.value,
                state=TaskState.QUEUED.value,
                max_attempts=3,
                available_at=datetime.now(timezone.utc),
                deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await session.commit()

    async with factory() as session:
        first = await claim_next_task(session, "worker-a", settings)
        assert first.generation == 1
        first.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()
        await requeue_expired(session)
        second = await claim_next_task(session, "worker-b", settings)
        assert second.generation == 2

    async with factory() as session:
        assert await renew_lease(session, task_id, "worker-a", 1, settings) is False

    await engine.dispose()
