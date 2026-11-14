import io
import json
from types import SimpleNamespace

import pytest

from backend.application.observation import correlate
from backend.config import Settings
from backend.domain.observability import ExecutionIdentity
from backend.domain.ports import TaskLease
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.logging import SafeLogger
from backend.infrastructure.observability.runtime import ObservabilityRuntime
from backend.workers.runtime import WorkerRuntime


def test_logging_projects_before_queue_and_never_formats_exception():
    out = io.StringIO()
    log = SafeLogger("sesrag-api", "local", stream=out)
    log.emit("request", prompt="SENSITIVE_PROMPT", error_code="secret/path", url="SECRET_URL")
    log.close(1)
    record = json.loads(out.getvalue())
    assert record["message"] == "请求处理结束"
    assert record["error_code"] == "UNKNOWN_ERROR"
    assert "SENSITIVE" not in out.getvalue() and "SECRET" not in out.getvalue()
    assert len(out.getvalue().encode()) <= 4096


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["run", "index_document", "index_build", "retrieval_diagnostic"])
async def test_worker_business_identity_survives_stage_and_attempt_logs(kind):
    """OBS4-023：适用身份在claim、阶段和结束日志中一致，下一任务不串身份。"""
    out = io.StringIO()
    runtime = ObservabilityRuntime(
        load_config("worker", {"OBS_METRICS_ENABLED": "false"}), log_stream=out
    )
    worker = WorkerRuntime(Settings(), None, None, observation=runtime)
    task = TaskLease(
        "task",
        kind,
        "run" if kind == "run" else None,
        "doc" if kind == "index_document" else None,
        worker.worker_id,
        1,
        1,
        "batch" if kind == "index_build" else None,
        "diagnostic" if kind == "retrieval_diagnostic" else None,
    )

    class Session:
        async def get(self, model, key):
            if model.__name__ == "RunModel":
                return SimpleNamespace(thread_id="thread")
            return SimpleNamespace(document_id="doc", parse_job_id="parse", stage="parse")

        async def scalar(self, query):
            return "retrieval"

    async def database(operation):
        return await operation(Session())

    worker._database = database
    with runtime.attempt(ExecutionIdentity("task", kind, worker.worker_id, 1, 1), None):
        await worker._load_log_context(task)
        worker.log("claim", task)
        if kind == "index_document":
            # 真实旧Task批次列为NULL；处理器选定候选后才补充当前批次身份。
            correlate(index_batch_id="batch")
        runtime.log("stage", stage="retrieval" if kind == "run" else "parse")
        worker.log("renew", task)
    with runtime.attempt(ExecutionIdentity("next", "run", worker.worker_id, 1, 1), None):
        runtime.log("stage", stage="generation")
    await runtime.close()
    records = [json.loads(line) for line in out.getvalue().splitlines()]
    expected = {
        "run": {"run_id": "run", "thread_id": "thread", "retrieval_execution_id": "retrieval"},
        "index_document": {"document_id": "doc", "index_batch_id": "batch"},
        "index_build": {"document_id": "doc", "index_batch_id": "batch", "parse_job_id": "parse"},
        "retrieval_diagnostic": {"retrieval_execution_id": "diagnostic"},
    }[kind]
    related = [r for r in records if r["task_id"] == "task"]
    assert {r["action"] for r in related} == {"claim", "stage", "renew", "attempt_unknown"}
    assert all(
        all(
            r[k] == v
            for k, v in expected.items()
            if not (kind == "index_document" and r["action"] == "claim" and k == "index_batch_id")
        )
        for r in related
    )
    assert all(
        r["document_id"] is None and r["thread_id"] is None
        for r in records
        if r["task_id"] == "next"
    )
