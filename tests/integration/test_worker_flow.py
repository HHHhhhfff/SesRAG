import pytest
from sqlalchemy import select

from backend.application.threads import create_message_run, create_thread
from backend.config import Settings
from backend.db.base import Base
from backend.db.models import MessageModel, RunModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.workers.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_worker_completes_run_and_persists_assistant_message(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}",
        upload_dir=str(tmp_path / "uploads"),
        auto_create_schema=True,
        redis_enabled=False,
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session:
        thread = await create_thread(session, settings, "Worker 测试")
        _message, run, _task, _duplicate = await create_message_run(
            session, settings, thread.thread_id, "没有资料时应该明确说明", "worker-test"
        )

    runtime = WorkerRuntime(settings, factory, RedisNotifier(settings))
    assert await runtime.run_once() is True

    async with factory() as session:
        saved_run = await session.get(RunModel, run.run_id)
        messages = list(
            (
                await session.execute(select(MessageModel).where(MessageModel.run_id == run.run_id))
            ).scalars()
        )
        assert saved_run.status == "succeeded"
        assert len(messages) == 2
        assert messages[-1].role == "assistant"

    await engine.dispose()
