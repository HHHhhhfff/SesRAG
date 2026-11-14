import httpx
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from backend.app import create_app
from backend.config import Settings
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


@pytest.mark.asyncio
async def test_http_is_templated_and_untrusted_trace_headers_are_ignored():
    exporter = InMemorySpanExporter()
    runtime = ObservabilityRuntime(
        load_config(
            "api",
            {
                "OBS_METRICS_ENABLED": "false",
                "OBS_TRACES_ENABLED": "true",
                "OBS_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces",
                "OBS_OTLP_ALLOWED_HOSTS": "collector",
            },
        ),
        exporter=exporter,
    )
    app = create_app(Settings(redis_enabled=False))
    app.state.observability = runtime
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/missing/PRIVATE_QUERY",
            headers={
                "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01",
                "baggage": "secret=PRIVATE_BAGGAGE",
            },
        )
    assert response.status_code == 404
    runtime.tracing.provider.force_flush(2000)
    spans = exporter.get_finished_spans()
    assert len(spans) == 1 and spans[0].parent is None
    assert f"{spans[0].context.trace_id:032x}" != "a" * 32
    assert spans[0].attributes["route"] == "__unmatched__"
    assert "PRIVATE" not in str(spans[0].attributes)
    assert (
        runtime.metrics.child("HTTP_REQUESTS", "GET", "__unmatched__", "4xx", "short")._value.get()
        == 1
    )
    await runtime.close()
