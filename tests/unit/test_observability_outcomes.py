"""七种互斥结果和采样来源均在真实公共scope验证。"""

import io

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.domain.observability import CommitReceipt, ExecutionIdentity, TraceOrigin
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result", ["succeeded", "failed", "yielded", "cancelled", "released", "lease_lost", "unknown"]
)
async def test_result_count_is_once_and_does_not_follow_normal_return(result):
    runtime = ObservabilityRuntime(
        load_config("worker", {"OBS_METRICS_ENABLED": "false"}), log_stream=io.StringIO()
    )
    identity = ExecutionIdentity("task", "run", "worker", 2, 2)
    engine = create_async_engine("sqlite+aiosqlite://")
    with runtime.attempt(identity, None) as observed:
        if result == "lease_lost":
            observed.stopped("lease_lost")
        elif result != "unknown":
            async with AsyncSession(engine) as session:
                await session.begin()
                runtime.receipt(
                    session, CommitReceipt(identity, result, retry_scheduled=result == "failed")
                )
                await session.commit()
    observed.finish()
    assert runtime.metrics.child("TASK_ATTEMPTS", "run", result)._value.get() == 1
    assert (
        sum(
            runtime.metrics.child("TASK_ATTEMPTS", "run", r)._value.get()
            for r in [
                "succeeded",
                "failed",
                "yielded",
                "cancelled",
                "released",
                "lease_lost",
                "unknown",
            ]
        )
        == 1
    )
    assert runtime.metrics.child("ATTEMPT_ACTIVE", "run")._value.get() == 0
    await engine.dispose()
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("sampled", [True, False])
async def test_parent_sampling_survives_receiver_ratio_change(sampled):
    exporter = InMemorySpanExporter()
    runtime = ObservabilityRuntime(
        load_config(
            "worker",
            {
                "OBS_TRACES_ENABLED": "true",
                "OBS_TRACE_SAMPLE_RATIO": "0.5",
                "OBS_OTLP_TRACES_ENDPOINT": "http://collector/v1/traces",
                "OBS_OTLP_ALLOWED_HOSTS": "collector",
            },
        ),
        exporter=exporter,
        log_stream=io.StringIO(),
    )
    origin = TraceOrigin(1, "a" * 32, "b" * 16, sampled)
    with runtime.attempt(ExecutionIdentity("task", "run", "worker", 1, 1), origin) as attempt:
        assert attempt.span.origin().sampled == sampled
    runtime.tracing.provider.force_flush(2000)
    spans = exporter.get_finished_spans()
    assert bool(spans) == sampled
    assert runtime.metrics.child("TASK_ATTEMPTS", "run", "unknown")._value.get() == 1
    await runtime.close()
