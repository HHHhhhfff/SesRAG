"""A13/A14持续故障和抓取压力；只通过有界配置/真实网络观测业务不变。"""

import asyncio
import io
import resource
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from evidence import client, metrics, request, wait
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import delete, insert

from backend.config import Settings
from backend.db.models import DocumentModel, TaskModel
from backend.db.session import create_engine
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.metrics import ObservabilityMetrics
from backend.infrastructure.observability.runtime import ObservabilityRuntime
from backend.infrastructure.observability.snapshots import SnapshotPoller


def refresh_count(output):
    return sum(
        sample.value
        for f in text_string_to_metric_families(output)
        for sample in f.samples
        if sample.name == "sesrag_snapshot_refresh_total" and sample.labels.get("source") == "queue"
    )


async def frequent_scrapes():
    before = refresh_count(metrics("api"))
    counts = {"api": 0, "worker": 0, "business": 0}
    async with httpx.AsyncClient(trust_env=False, timeout=3) as c:

        async def load(role, port):
            begin = time.monotonic()
            for n in range(1200):
                await asyncio.sleep(max(0, begin + n * 0.1 - time.monotonic()))
                response = await c.get(f"http://{role}:{port}/metrics")
                assert response.status_code == 200
                counts[role] += 1

        async def business():
            for _ in range(240):
                response = await c.get("http://api:8000/api/v1/threads")
                assert response.status_code == 200
                counts["business"] += 1
                await asyncio.sleep(0.5)

        await asyncio.gather(load("api", 9101), load("worker", 9102), business())
    after = refresh_count(metrics("api"))
    assert 22 <= after - before <= 26, "高频抓取改变了队列查询频率"
    return dict(scrapes=counts, queue_refresh_delta=after - before)


async def historical_queue():
    settings = Settings()
    engine = create_engine(settings)
    document = str(uuid4())
    now = datetime.now(timezone.utc)
    async with engine.begin() as connection:
        await connection.execute(
            insert(DocumentModel),
            dict(
                document_id=document,
                owner_id="obs-test",
                filename="load.txt",
                extension=".txt",
                size_bytes=1,
                content_hash="0" * 64,
                storage_key="load-" + document,
                status="indexing",
            ),
        )
        rows = []
        for n in range(11000):
            state = (
                "succeeded"
                if n < 10000
                else ["queued", "retry_waiting", "leased", "running"][n % 4]
            )
            rows.append(
                dict(
                    task_id="o4t-" + uuid4().hex,
                    kind="index_document",
                    document_id=document,
                    state=state,
                    available_at=now + timedelta(days=1),
                    deadline_at=now + timedelta(days=2),
                    lease_expires_at=now + timedelta(days=1),
                    worker_id="fixture",
                    generation=1,
                    attempt=1,
                )
            )
        await connection.execute(insert(TaskModel), rows)
    metrics_obj = ObservabilityMetrics("sesrag-api", "obs-test")
    poller = SnapshotPoller(settings, metrics_obj, lambda *args: None)
    try:
        started = time.monotonic()
        await poller.refresh("queue")
        duration = time.monotonic() - started
        assert metrics_obj.child("SNAPSHOT_VALID", "queue")._value.get() == 1, (
            "11000条队列夹具查询未成功"
        )
        assert duration < 1, "队列查询超过总预算"
        total = sum(
            metrics_obj.child("QUEUE_GROUPS", "index_document", g)._value.get()
            for g in ["queued_future", "retry_backoff", "leased", "running"]
        )
        assert total >= 1000
        return dict(historical_terminal=10000, mixed_nonterminal=1000, query_seconds=duration)
    finally:
        await poller.close()
        async with engine.begin() as connection:
            await connection.execute(delete(TaskModel).where(TaskModel.document_id == document))
            await connection.execute(
                delete(DocumentModel).where(DocumentModel.document_id == document)
            )
        await engine.dispose()


async def export_fault():
    config = load_config(
        "worker",
        {
            "OBS_METRICS_ENABLED": "false",
            "OBS_TRACES_ENABLED": "true",
            "OBS_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces",
            "OBS_OTLP_ALLOWED_HOSTS": "collector",
        },
    )
    runtime = ObservabilityRuntime(config, log_stream=io.StringIO())
    await runtime.start()
    initial_threads = threading.active_count()
    rss = []
    business_completed = 0

    async def business_during_fault():
        nonlocal business_completed
        async with httpx.AsyncClient(
            base_url="http://api:8000", trust_env=False, timeout=10
        ) as api:
            for _ in range(18):
                thread = (
                    await api.post("/api/v1/threads", json={"title": "接收端故障期间"})
                ).json()
                run = (
                    await api.post(
                        f"/api/v1/threads/{thread['thread_id']}/messages",
                        json={"content": "受控故障验证"},
                    )
                ).json()
                for _ in range(100):
                    row = (await api.get("/api/v1/runs/" + run["run_id"])).json()
                    if row["status"] in {"succeeded", "failed", "cancelled"}:
                        assert row["status"] == "succeeded"
                        business_completed += 1
                        break
                    await asyncio.sleep(0.1)
                await asyncio.sleep(5)

    with httpx.Client(trust_env=False) as c:
        c.post("http://collector:4318/mode", json={"mode": "slow"})
        business = asyncio.create_task(business_during_fault())
        try:
            started = time.monotonic()
            while time.monotonic() - started < 120:
                # 前60秒制造发送队列饱和；后60秒保留持续慢接收端故障。
                count = 400 if time.monotonic() - started < 60 else 1
                for _ in range(count):
                    runtime.tracing.start("controlled.export.load", root=True).end()
                rss.append(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
                await asyncio.sleep(0.05)
            assert threading.active_count() <= initial_threads + 1, "导出线程随请求数增长"
            assert max(rss) - min(rss) < 96 * 1024**2, "故障期间观测内存无界增长"
            assert runtime.metrics.child("TRACE_EXPORT", "failure")._value.get() > 0, (
                "未观测到实际导出失败"
            )
            await business
            assert business_completed == 18
        finally:
            # 验证关闭调用方有界，再恢复捕获器，不要求队列零丢失。
            closing = time.monotonic()
            await runtime.close()
            close_seconds = time.monotonic() - closing
            c.post("http://collector:4318/mode", json={"mode": "ok"})
    assert close_seconds <= 3.3, "观测关闭超过预算"
    with client() as c:
        thread = request(c, "POST", "/api/v1/threads", json={"title": "故障后的业务"})
        run = request(
            c,
            "POST",
            f"/api/v1/threads/{thread['thread_id']}/messages",
            json={"content": "恢复验证"},
        )
        wait(c, "/api/v1/runs/" + run["run_id"])
    return dict(
        fault_seconds=120,
        saturation_seconds=60,
        close_seconds=close_seconds,
        queue_drop_count=None,
        queue_drop_count_state="unknown",
        thread_count=threading.active_count(),
        business_completed=business_completed,
    )


def run():
    return dict(
        queue=asyncio.run(historical_queue()),
        scrapes=asyncio.run(frequent_scrapes()),
        exporter=asyncio.run(export_fault()),
    )
