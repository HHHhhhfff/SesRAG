"""真实事务回执决定尝试结果，回滚/迟到回执均不能制造成功。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.domain.observability import CommitReceipt, ExecutionIdentity
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


@pytest.mark.asyncio
async def test_receipt_commit_rollback_and_generation_fencing():
    runtime = ObservabilityRuntime(load_config("worker", {"OBS_METRICS_ENABLED": "false"}))
    engine = create_async_engine("sqlite+aiosqlite://")
    identity = ExecutionIdentity("task", "index_build", "worker", 2, 1)
    with runtime.attempt(identity, None) as observed:
        async with AsyncSession(engine) as session:
            await session.begin()
            runtime.receipt(session, CommitReceipt(identity, "succeeded"))
            await session.rollback()
        assert observed.result is None
        observed.confirm(
            CommitReceipt(ExecutionIdentity("task", "index_build", "worker", 1, 1), "succeeded")
        )
        assert observed.result is None
        async with AsyncSession(engine) as session:
            await session.begin()
            runtime.receipt(session, CommitReceipt(identity, "yielded"))
            await session.commit()
    assert observed.finish() == "yielded"
    assert runtime.metrics.child("TASK_ATTEMPTS", "index_build", "yielded")._value.get() == 1
    assert runtime.metrics.child("TASK_ATTEMPTS", "index_build", "succeeded")._value.get() == 0
    await runtime.close()
    await engine.dispose()
