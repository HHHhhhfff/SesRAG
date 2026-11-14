import asyncio

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from backend.application.observation import bind
from backend.domain.observability import ExecutionIdentity
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime
from backend.infrastructure.providers.mock import MockModelProvider


@pytest.mark.asyncio
async def test_stream_anext_in_different_tasks_has_one_safe_call_span():
    exporter = InMemorySpanExporter()
    runtime = ObservabilityRuntime(
        load_config(
            "worker",
            {
                "OBS_METRICS_ENABLED": "false",
                "OBS_TRACES_ENABLED": "true",
                "OBS_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces",
                "OBS_OTLP_ALLOWED_HOSTS": "collector",
            },
        ),
        exporter=exporter,
    )
    with bind(runtime), runtime.attempt(ExecutionIdentity("task", "run", "worker", 1, 1), None):
        generator = MockModelProvider().stream_answer(
            "SECRET_PROMPT", [{"text": "alpha beta gamma"}]
        )
        output = []
        for _ in range(4):
            try:
                output.append(await asyncio.create_task(anext(generator)))
            except StopAsyncIteration:
                break
        await asyncio.create_task(generator.aclose())
    runtime.tracing.provider.force_flush(2000)
    spans = exporter.get_finished_spans()
    assert len([s for s in spans if s.name == "model.generate"]) == 1
    assert "SECRET_PROMPT" not in str([s.attributes for s in spans])
    assert output == ["根据检索到的资料：alpha ", "beta ", "gamma "]
    await runtime.close()
