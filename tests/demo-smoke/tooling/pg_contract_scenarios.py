"""QLT006：真实Runtime创建失败/重试事件，再用正式ASGI原始投影供Schema校验。"""

import asyncio
from datetime import datetime, timezone

import httpx
from pg_harness import Provider

from backend.app import create_app


async def event_contracts(h):
    app = create_app(h.cfg)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for mode in ("retry", "failed"):
                ids = await h.seed()
                worker = h.worker(Provider(failures=1, permanent=mode == "failed"))
                await worker.run_once()
                response = await client.get(f"/api/v1/runs/{ids['run_id']}/events")
                h.check(response.status_code == 200, f"{mode}正式events响应成功")
                events = response.json()["events"]
                required = "task.retry_scheduled" if mode == "retry" else "run.failed"
                h.check(any(row["type"] == required for row in events), f"{required}真实持久")
                h.trace[mode] = events
                detail = await client.get(f"/api/v1/runs/{ids['run_id']}")
                h.trace[mode + "_detail"] = detail.json()
                if mode == "retry":
                    facts = await h.facts(ids)
                    delay = (
                        facts["task"]["available_at"] - datetime.now(timezone.utc)
                    ).total_seconds()
                    await asyncio.sleep(max(0, delay) + 0.05)
                    await worker.run_once()
    finally:
        await app.state.engine.dispose()
