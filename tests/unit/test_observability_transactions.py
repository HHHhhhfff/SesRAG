"""只有业务事务真正提交后才能确认观测回执。"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.infrastructure.observability.transactions import after_transaction


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [True, False])
async def test_callback_only_reports_success_after_commit(commit):
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine)
    result = []
    async with factory() as session:
        await session.execute(text("SELECT 1"))
        after_transaction(
            session, lambda: result.append("committed"), lambda: result.append("rolled_back")
        )
        if commit:
            await session.commit()
        else:
            await session.rollback()
    assert result == (["committed"] if commit else ["rolled_back"])
    await engine.dispose()


@pytest.mark.asyncio
async def test_observer_exception_does_not_abort_commit():
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine)
    async with factory() as session:
        await session.execute(text("SELECT 1"))
        after_transaction(session, lambda: 1 / 0, lambda: None)
        await session.commit()
    await engine.dispose()
