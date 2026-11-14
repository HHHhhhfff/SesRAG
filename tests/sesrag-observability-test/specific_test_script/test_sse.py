"""A03/A14：真实十连接持续30秒，断连不取消Run，游标补放无重复。"""

import asyncio
import time
from contextlib import AsyncExitStack
from pathlib import Path

import httpx
from evidence import client, metrics, request, wait
from prometheus_client.parser import text_string_to_metric_families


def active_connections():
    return sum(
        sample.value
        for family in text_string_to_metric_families(metrics("api"))
        for sample in family.samples
        if sample.name == "sesrag_sse_active_connections"
    )


async def hold_connections(path):
    async with (
        httpx.AsyncClient(base_url="http://api:8000", trust_env=False, timeout=50) as c,
        AsyncExitStack() as stack,
    ):
        for _ in range(10):
            response = await stack.enter_async_context(c.stream("GET", path))
            assert response.status_code == 200
        await asyncio.sleep(1.2)
        assert await asyncio.to_thread(active_connections) >= 10
        await asyncio.sleep(30)
        assert await asyncio.to_thread(active_connections) >= 10


def run():
    # All/Recovery在此之前显式启用recovery_worker；普通Worker不读取这个夹具开关。
    flag = Path("/data/recovery-delay")
    flag.touch()
    try:
        with client() as c:
            thread = request(c, "POST", "/api/v1/threads", json={"title": "SSE持续连接"})
            run = request(
                c,
                "POST",
                f"/api/v1/threads/{thread['thread_id']}/messages",
                json={"content": "SSE受控长任务"},
            )
            path = f"/api/v1/runs/{run['run_id']}"
            for _ in range(100):
                if request(c, "GET", path)["status"] == "running":
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("SSE夹具未进入运行中")
            events = request(c, "GET", path + "/events")["events"]
            cursor = events[0]["seq"]
            asyncio.run(hold_connections(path + "/events/stream"))
            for _ in range(30):
                if active_connections() == 0:
                    break
                time.sleep(0.1)
            assert active_connections() == 0, "SSE断连后active未归零"
            wait(c, path)
            replay = c.get(path + "/events/stream", headers={"Last-Event-ID": str(cursor)})
            assert replay.status_code == 200 and "run.succeeded" in replay.text
            ids = [
                int(line[3:].strip()) for line in replay.text.splitlines() if line.startswith("id:")
            ]
            assert ids and ids == sorted(set(ids)) and min(ids) > cursor
        return dict(
            connections=10,
            held_seconds=30,
            active_after_disconnect=0,
            run_succeeded=True,
            cursor_replay_unique=True,
        )
    finally:
        flag.unlink(missing_ok=True)
