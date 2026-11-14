"""A04/A05：真实PG只读聚合、未知不伪零与缓存抓取。"""

import asyncio

from evidence import metrics
from prometheus_client import generate_latest

from backend.config import Settings
from backend.infrastructure.observability.metrics import ObservabilityMetrics
from backend.infrastructure.observability.snapshots import SnapshotPoller


async def verify():
    m = ObservabilityMetrics("sesrag-api", "obs-test")
    poller = SnapshotPoller(Settings(), m, lambda *args: None)
    assert "sesrag_queue_ready_tasks{" not in generate_latest(m.registry).decode()
    await poller.refresh("queue")
    assert m.child("SNAPSHOT_VALID", "queue")._value.get() == 1
    before = m.child("QUEUE_LENGTH", "run")._value.get()
    # 观测源断开与真实空队列不同，保留最近成功值。
    original = poller.engine
    from sqlalchemy.ext.asyncio import create_async_engine

    poller.engine = create_async_engine("postgresql+psycopg://invalid:invalid@127.0.0.1:1/no")
    await poller.refresh("queue")
    assert m.child("SNAPSHOT_VALID", "queue")._value.get() == 0
    assert m.child("QUEUE_LENGTH", "run")._value.get() == before
    await poller.engine.dispose()
    poller.engine = original
    await poller.close()
    return {"retains_last_success": True, "unknown_not_zero": True}


def run():
    evidence = asyncio.run(verify())
    output = metrics("api")
    assert "sesrag_snapshot_valid" in output and "sesrag_queue_tasks" in output
    assert "sesrag_queue_ready_tasks" not in metrics("worker")
    return evidence
