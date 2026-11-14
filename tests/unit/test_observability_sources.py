"""来源只在创建事务提交时确认；未采样保留可关联身份。"""

import io
import json
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.domain.observability import ExecutionIdentity, TraceOrigin
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize("ratio", ["0", "1"])
async def test_enqueue_commit_and_rollback_have_distinct_parent_preserving_spans(ratio):
    exporter = InMemorySpanExporter()
    config = load_config(
        "api",
        {
            "OBS_TRACES_ENABLED": "true",
            "OBS_TRACE_SAMPLE_RATIO": ratio,
            "OBS_OTLP_TRACES_ENDPOINT": "http://collector/v1/traces",
            "OBS_OTLP_ALLOWED_HOSTS": "collector",
        },
    )
    runtime = ObservabilityRuntime(config, exporter=exporter)
    engine = create_async_engine("sqlite+aiosqlite://")
    root = runtime.tracing.start("request", root=True)
    with root.activate():
        for result in ("committed", "rolled_back"):
            async with AsyncSession(engine) as session:
                await session.begin()
                task = SimpleNamespace(task_id=result, kind="run", trace_origin_json=None)
                runtime.enqueue(session, task)
                assert task.trace_origin_json["sampled"] == (ratio == "1")
                assert task.trace_origin_json["trace_id"] == root.origin().trace_id
                if result == "committed":
                    await session.commit()
                else:
                    await session.rollback()
    root.end()
    runtime.tracing.provider.force_flush(2000)
    data = exporter.get_finished_spans()
    if ratio == "1":
        assert {s.attributes["result"] for s in data if s.name == "task.enqueue"} == {
            "committed",
            "rolled_back",
        }
    else:
        assert not data
    assert not runtime._pending
    await runtime.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_partial_worker_sampling_preserves_both_persisted_source_decisions():
    """A11：部分采样不重写来源决定；未采样仍有真实身份、日志及尝试指标。"""
    exporter, output = InMemorySpanExporter(), io.StringIO()
    runtime = ObservabilityRuntime(
        load_config(
            "worker",
            {
                "OBS_METRICS_ENABLED": "false",
                "OBS_TRACES_ENABLED": "true",
                "OBS_TRACE_SAMPLE_RATIO": "0.25",
                "OBS_OTLP_TRACES_ENDPOINT": "http://collector/v1/traces",
                "OBS_OTLP_ALLOWED_HOSTS": "collector",
            },
        ),
        exporter=exporter,
        log_stream=output,
    )
    for sampled in (False, True):
        origin = TraceOrigin(1, "1" * 32, "2" * 16, sampled)
        with runtime.attempt(
            ExecutionIdentity(str(sampled), "run", "worker", 1, 1), origin
        ) as attempt:
            assert attempt.span.origin().sampled is sampled
            runtime.log("stage", stage="generation")
    runtime.tracing.provider.force_flush(2000)
    spans = exporter.get_finished_spans()
    assert len(spans) == 1 and spans[0].attributes["task_id"] == "True"
    assert runtime.metrics.child("TASK_ATTEMPTS", "run", "unknown")._value.get() == 2
    await runtime.close()
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert {r["trace_sampled"] for r in rows if r["action"] == "stage"} == {False, True}
    assert all(r["trace_id"] == "1" * 32 for r in rows if r["action"] == "stage")
