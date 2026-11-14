"""SSE流后的异常不得重记HTTP5xx，连接关闭口径与Run终态分离。"""

import asyncio
import io
from types import SimpleNamespace

import pytest

from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.http import ObservabilityMiddleware
from backend.infrastructure.observability.runtime import ObservabilityRuntime

ROUTE = "/api/v2/runs/{run_id}/events/stream"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["completed", "disconnected", "error", "cancelled", "handshake"])
async def test_sse_counts_once_and_always_releases_active_connection(mode):
    runtime = ObservabilityRuntime(
        load_config("api", {"OBS_METRICS_ENABLED": "false"}), log_stream=io.StringIO()
    )
    sent = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v2/runs/id/events/stream",
        "app": SimpleNamespace(state=SimpleNamespace(observability=runtime)),
    }

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        if mode == "handshake":
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        if mode == "error":
            raise ValueError("OBS_SECRET_SENTINEL")
        if mode == "cancelled":
            raise asyncio.CancelledError()
        if mode == "disconnected":
            await receive()
        else:
            scope["sesrag_sse_close"] = "completed"
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    try:
        if mode == "error":
            with pytest.raises(ValueError):
                await ObservabilityMiddleware(app)(scope, receive, send)
        elif mode == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await ObservabilityMiddleware(app)(scope, receive, send)
        else:
            await ObservabilityMiddleware(app)(scope, receive, send)
        m = runtime.metrics
        status = "4xx" if mode == "handshake" else "2xx"
        assert m.child("HTTP_REQUESTS", "GET", ROUTE, status, "sse")._value.get() == 1
        assert m.child("HTTP_REQUESTS", "GET", ROUTE, "5xx", "sse")._value.get() == 0
        assert m.child("SSE_ACTIVE", ROUTE)._value.get() == 0
        if mode != "handshake":
            assert m.child("SSE_CLOSE", ROUTE, mode)._value.get() == 1
        else:
            assert m.child("SSE_OPEN", ROUTE)._value.get() == 0
    finally:
        await runtime.close()
