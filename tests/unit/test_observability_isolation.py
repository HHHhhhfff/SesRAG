"""记录器故障不能替换响应/业务异常，也不能遗留当前执行身份。"""

import io
import json

import httpx
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from backend.app import create_app
from backend.application.observation import current_attempt
from backend.config import Settings
from backend.domain.observability import ExecutionIdentity
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


def broken(*args, **kwargs):
    raise RuntimeError("OBS_SECRET_SENTINEL")


@pytest.mark.asyncio
async def test_http_metric_failure_keeps_original_response(monkeypatch):
    runtime = ObservabilityRuntime(load_config("api", {"OBS_METRICS_ENABLED": "false"}))
    monkeypatch.setattr(runtime.metrics, "http_request", broken)
    app = create_app(Settings(redis_enabled=False))
    app.state.observability = runtime
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        assert (await c.get("/health/live")).status_code == 200
    await runtime.close()


def test_worker_stop_still_marks_stop_when_metrics_fail(monkeypatch):
    from types import SimpleNamespace

    from backend.workers.runtime import WorkerRuntime

    worker = WorkerRuntime(
        Settings(), None, None, observation=SimpleNamespace(metrics=SimpleNamespace(set=broken))
    )
    worker.request_stop()
    assert worker.stop_event.is_set()


@pytest.mark.asyncio
async def test_attempt_final_log_carries_actual_span_and_failure_does_not_leak_context(monkeypatch):
    out = io.StringIO()
    exporter = InMemorySpanExporter()
    runtime = ObservabilityRuntime(
        load_config(
            "worker",
            {
                "OBS_TRACES_ENABLED": "true",
                "OBS_OTLP_TRACES_ENDPOINT": "http://collector/v1/traces",
                "OBS_OTLP_ALLOWED_HOSTS": "collector",
            },
        ),
        exporter=exporter,
        log_stream=out,
    )
    identity = ExecutionIdentity("task", "run", "worker", 1, 1)
    with runtime.attempt(identity, None) as attempt:
        expected = attempt.span.origin()
    monkeypatch.setattr(runtime.metrics, "inc", broken)
    with runtime.attempt(identity, None):
        assert current_attempt.get() is None
    assert current_attempt.get() is None
    await runtime.close()
    rows = [json.loads(line) for line in out.getvalue().splitlines()]
    end = next(r for r in rows if r["action"] == "attempt_unknown")
    assert end["trace_id"] == expected.trace_id and end["span_id"] == expected.span_id
