"""阶段日志必须可关联且观测失败不能改变执行结果。"""

import json
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from backend.config import Settings
from backend.domain.ports import TaskLease
from backend.workers.runtime import WorkerRuntime


def test_all_worker_records_have_safe_correlation_and_duration(caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    runtime = WorkerRuntime(Settings(), None, None)
    task = TaskLease("task", "index_build", None, None, "worker", 4, 2, "batch")
    with caplog.at_level("INFO", logger="backend.workers.runtime"):
        runtime.log("claim", task)
    record = json.loads(caplog.records[-1].message)
    assert {
        "document_id",
        "parse_job_id",
        "index_batch_id",
        "run_id",
        "retrieval_execution_id",
        "task_id",
        "worker_id",
        "generation",
        "attempt",
        "error_code",
        "stage",
        "duration_ms",
    } <= record.keys()
    assert record["index_batch_id"] == "batch"
    assert record["duration_ms"] == 0


@pytest.mark.asyncio
async def test_stage_elapsed_is_monotonic_and_failure_keeps_safe_code(monkeypatch, caplog):
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    import backend.workers.runtime as module
    from backend.application.errors import PermanentTaskError

    runtime = WorkerRuntime(Settings(), None, None)
    task = TaskLease("task", "index_document", None, "doc", "worker", 2, 3)
    times = iter([10.0, 10.125])
    monkeypatch.setattr(module, "monotonic", lambda: next(times))

    async def broken(task):
        raise PermanentTaskError("SAFE_ERROR", "private-path-secret")

    monkeypatch.setattr(runtime, "_dispatch", broken)
    with caplog.at_level("INFO", logger="backend.workers.runtime"):
        with pytest.raises(PermanentTaskError):
            await runtime._observed_dispatch(task)
    record = json.loads(caplog.records[-1].message)
    assert record["duration_ms"] == 125
    assert record["stage"] == "index_document"
    assert record["error_code"] == "SAFE_ERROR"
    assert "private-path-secret" not in caplog.text


@pytest.mark.asyncio
async def test_build_identity_is_loaded_without_mutating_lease():
    build = SimpleNamespace(document_id="doc", parse_job_id="parse", stage="embed")

    class Session:
        async def get(self, model, identity):
            return build

    @asynccontextmanager
    async def factory():
        yield Session()

    runtime = WorkerRuntime(Settings(), factory, None)
    task = TaskLease("task", "index_build", None, None, "worker", 4, 2, "batch")
    await runtime._load_log_context(task)
    assert runtime._log_context["document_id"] == "doc"
    assert runtime._log_context["parse_job_id"] == "parse"
    assert runtime._log_context["stage"] == "embed"
    assert task.document_id is None


@pytest.mark.asyncio
async def test_observer_failure_does_not_replace_success_or_business_error(monkeypatch):
    from backend.application.stage_observation import observe_stage, observer

    async def broken(*args):
        raise RuntimeError("logging unavailable")

    token = observer.set(broken)
    try:
        async with observe_stage("generation"):
            pass
        with pytest.raises(ValueError, match="business"):
            async with observe_stage("generation"):
                raise ValueError("business")
    finally:
        observer.reset(token)


@pytest.mark.asyncio
async def test_logger_failure_does_not_interrupt_worker(monkeypatch):
    import backend.workers.runtime as module

    def broken(*args, **kwargs):
        raise RuntimeError("logger unavailable")

    monkeypatch.setattr(module.logger, "info", broken)
    WorkerRuntime(Settings(), None, None).log("claim")
