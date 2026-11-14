from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.base import Base
from backend.db.models import DocumentModel, TaskModel
from backend.infrastructure.observability.snapshots import read_queue


@pytest.mark.asyncio
async def test_queue_groups_are_disjoint_and_active_last_attempt_is_valid():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = datetime.now(timezone.utc)
    async with async_sessionmaker(engine)() as session:
        session.add(
            DocumentModel(
                document_id="doc",
                owner_id="test",
                filename="x.txt",
                extension=".txt",
                size_bytes=1,
                content_hash="0" * 64,
                storage_key="file",
                status="indexing",
            )
        )
        for name, state, available, attempt, lease in [
            ("ready", "queued", -20, 0, None),
            ("future", "queued", 30, 0, None),
            ("last", "running", 0, 3, now + timedelta(seconds=30)),
            ("expired", "running", 0, 1, now - timedelta(seconds=1)),
        ]:
            session.add(
                TaskModel(
                    task_id=name,
                    kind="index_document",
                    document_id="doc",
                    state=state,
                    attempt=attempt,
                    max_attempts=3,
                    available_at=now + timedelta(seconds=available),
                    deadline_at=now + timedelta(minutes=2),
                    lease_expires_at=lease,
                )
            )
        await session.commit()
    async with engine.connect() as connection:
        values, groups = await read_queue(connection, now)
    assert values["index_document"][0] == 1
    assert values["index_document"][1] == pytest.approx(20, abs=0.01)
    assert groups["index_document", "running"] == 1
    assert groups["index_document", "expired"] == 1
    assert groups["index_document", "queued_future"] == 1
    assert sum(groups.values()) == 4
    await engine.dispose()
