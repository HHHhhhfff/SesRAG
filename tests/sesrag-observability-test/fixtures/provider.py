"""仅测试进程注入的真实适配器transport替身，生产SafeHTTP边界不放宽。"""

import asyncio
import base64
import io
import json
import time
from contextvars import ContextVar
from pathlib import Path
from zipfile import ZipFile

import httpx

STATE = Path("/data/provider")
STATE.mkdir(parents=True, exist_ok=True)


def handler(request):
    # 用真实请求对象验证第三方出口没有内部上下文；不保存正文或URL。
    assert not any(k.lower() in {"traceparent", "tracestate", "baggage"} for k in request.headers)
    time.sleep(0.05)
    if request.method == "POST":
        payload = json.loads(request.content)["files"][0]
        batch = base64.urlsafe_b64encode(
            json.dumps([payload["data_id"], payload["name"]]).encode()
        ).decode()
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "batch_id": batch,
                    "file_urls": ["https://fixture.test/upload?batch=" + batch],
                },
            },
        )
    if request.method == "PUT":
        (STATE / request.url.params["batch"]).touch()
        return httpx.Response(200)
    if request.url.host == "mineru.net":
        batch = request.url.path.rsplit("/", 1)[1]
        data_id, filename = json.loads(base64.urlsafe_b64decode(batch))
        done = (STATE / batch).exists()
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "extract_result": [
                        {
                            "data_id": data_id,
                            "file_name": filename,
                            "state": "done" if done else "waiting-file",
                            "full_zip_url": "https://fixture.test/result.zip?OBS_URL_SENTINEL=secret",
                        }
                    ]
                },
            },
        )
    out = io.BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr(
            "full.md", "# 观测测试\n\n可观测体系使用安全指标与关联追踪。 OBS_PROMPT_SENTINEL"
        )
    return httpx.Response(200, content=out.getvalue())


def install():
    from backend.infrastructure.providers.mock import MockModelProvider
    from backend.infrastructure.providers.rag_registry import MockEmbeddingV2, MockRerank
    from backend.infrastructure.queue.adapter import PostgresQueue
    from backend.infrastructure.rag.mineru_client import MinerUClient
    from backend.workers.runtime import WorkerRuntime

    current_attempt = ContextVar("fixture_attempt_timer", default=None)
    claim = PostgresQueue.claim
    run_once = WorkerRuntime.run_once

    async def timed_claim(*args, **kwargs):
        task = await claim(*args, **kwargs)
        current = current_attempt.get()
        if task and current is not None:
            current.update(started=time.monotonic(), kind=task.kind)
        return task

    async def timed_once(*args, **kwargs):
        current = {}
        token = current_attempt.set(current)
        try:
            return await run_once(*args, **kwargs)
        finally:
            if current:
                record = {"kind": current["kind"], "seconds": time.monotonic() - current["started"]}
                with Path("/data/budget-attempts.jsonl").open("a") as output:
                    output.write(json.dumps(record) + "\n")
            current_attempt.reset(token)

    PostgresQueue.claim = timed_claim
    WorkerRuntime.run_once = timed_once
    original = MinerUClient.__init__

    def initialize(self, settings, **kwargs):
        return original(self, settings, transport=httpx.MockTransport(handler))

    MinerUClient.__init__ = initialize
    # 固定延迟与基线镜像使用相同fixture；观测仍发生于原适配边界。
    for cls, method in [(MockEmbeddingV2, "embed"), (MockRerank, "rank")]:
        old = getattr(cls, method)

        def delayed(original_method):
            async def call(*args, **kwargs):
                await asyncio.sleep(0.05)
                return await original_method(*args, **kwargs)

            return call

        setattr(cls, method, delayed(old))
    stream = MockModelProvider.stream_answer

    async def delayed_stream(*args, **kwargs):
        await asyncio.sleep(0.05)
        async for token in stream(*args, **kwargs):
            yield token

    MockModelProvider.stream_answer = delayed_stream


if __name__ == "__main__":
    install()
    from backend.workers.main import main

    asyncio.run(main())
