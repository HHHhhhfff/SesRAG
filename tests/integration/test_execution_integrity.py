import asyncio
import json
import logging
from datetime import timedelta

import pytest
import pytest_asyncio

from backend.application.documents import create_document
from backend.application.runs import cancel_run
from backend.application.task_execution import ExecutionStopped, guarded_call
from backend.application.threads import create_message_run, create_thread
from backend.config import Settings
from backend.db.base import Base
from backend.db.models import RunModel, TaskModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.journal import append_event, list_events
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.queue import postgres_queue as queue
from backend.workers.runtime import WorkerRuntime


@pytest_asyncio.fixture
async def execution(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'execution.db'}", redis_enabled=False
    )
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        thread = await create_thread(session, settings, "执行约束")
        _, run, task, _ = await create_message_run(
            session, settings, thread.thread_id, "问题", "one"
        )
    yield settings, factory, run.run_id, task.task_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_claim_records_event_and_snapshot_freezes_config(execution):
    settings, factory, run_id, _ = execution
    async with factory() as session:
        run = await session.get(RunModel, run_id)
        assert run.snapshot_json["owner_id"] == settings.owner_id
        assert run.snapshot_json["mock_provider"] is True
        await queue.claim_next_task(session, "a", settings)
        assert (await list_events(session, run_id))[-1].type == "task.leased"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["run", "index"])
async def test_runtime_logs_exact_persisted_task_business_identity(
    execution, tmp_path, caplog, monkeypatch, kind
):
    settings, factory, run_id, task_id = execution
    settings.upload_dir = str(tmp_path / "log-uploads")
    async with factory() as session:
        if kind == "index":
            document, task = await create_document(
                session, settings, "log.txt", "text/plain", b"safe fixture"
            )
            document_id = document.document_id
            task_id = task.task_id
        else:
            document_id = None
        task = await session.get(TaskModel, task_id)
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    caplog.set_level("INFO", logger="backend.workers.runtime")
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    for action, error_code in (
        ("claim", None),
        ("renew", None),
        ("release", "WORKER_STOPPED"),
        ("retry", "TEST_PROVIDER_FAILURE"),
        ("success", None),
        ("failure", "TEST_PROVIDER_FAILURE"),
    ):
        caplog.clear()
        worker.log(action, task, error_code)
        rows = [
            json.loads(record.message)
            for record in caplog.records
            if record.name == "backend.workers.runtime"
        ]
        assert rows == [
            {
                "action": action,
                "message": "task claimed" if action == "claim" else f"task {action}",
                "task_id": task_id,
                "run_id": run_id if kind == "run" else None,
                "document_id": document_id,
                "worker_id": worker.worker_id,
                "generation": 0,
                "attempt": 0,
                "error_code": error_code,
            }
        ]


@pytest.mark.asyncio
async def test_retry_due_and_deadline_settle_run(execution, monkeypatch):
    settings, factory, run_id, task_id = execution
    now = queue.utc_now()
    async with factory() as session:
        task = await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task_id, "a", task.generation)
        await queue.schedule_retry(
            session, task_id, "a", 1, settings, "RUN_FAILED", "private secret"
        )
        run = await session.get(RunModel, run_id)
        assert run.status == "retry_waiting"
        assert "private" not in (await session.get(TaskModel, task_id)).last_error_message
    monkeypatch.setattr(queue, "utc_now", lambda: now + timedelta(seconds=5))
    async with factory() as session:
        await queue.requeue_expired(session)
        assert (await session.get(TaskModel, task_id)).state == "queued"
        assert (await session.get(RunModel, run_id)).status == "retry_waiting"
    monkeypatch.setattr(queue, "utc_now", lambda: now + timedelta(seconds=700))
    async with factory() as session:
        await queue.requeue_expired(session)
        assert (await session.get(RunModel, run_id)).status == "failed"
        assert (await list_events(session, run_id))[-1].type == "run.failed"


@pytest.mark.asyncio
async def test_expired_lease_cannot_complete(execution, monkeypatch):
    settings, factory, _, task_id = execution
    async with factory() as session:
        await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task_id, "a", 1)
        now = queue.utc_now()
        monkeypatch.setattr(queue, "utc_now", lambda: now + timedelta(seconds=40))
        assert not await queue.mark_succeeded(session, task_id, "a", 1)


@pytest.mark.asyncio
async def test_terminal_journal_rejects_late_delta(execution):
    settings, factory, run_id, _ = execution
    async with factory() as session:
        await cancel_run(session, settings, run_id)
        with pytest.raises(ValueError):
            await append_event(session, run_id, "answer.delta", {"text": "late"})


def test_worker_identity_unique():
    settings = Settings(redis_enabled=False)
    assert (
        WorkerRuntime(settings, None, RedisNotifier(settings)).worker_id
        != WorkerRuntime(settings, None, RedisNotifier(settings)).worker_id
    )


@pytest.mark.asyncio
async def test_stopped_worker_does_not_claim(execution):
    settings, factory, _, task_id = execution
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    worker.request_stop()
    assert not await worker.run_once()
    async with factory() as session:
        assert (await session.get(TaskModel, task_id)).state == "queued"


@pytest.mark.asyncio
async def test_cancel_during_provider_stops_call(execution):
    settings, factory, run_id, task_id = execution
    started, stopped = asyncio.Event(), asyncio.Event()

    async def provider():
        started.set()
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    async with factory() as session:
        await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task_id, "a", 1)
    pending = asyncio.create_task(guarded_call(factory, task_id, "a", 1, provider))
    await started.wait()
    async with factory() as session:
        await cancel_run(session, settings, run_id)
    with pytest.raises(ExecutionStopped):
        await asyncio.wait_for(pending, 2)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_shutdown_releases_after_grace_and_logs_safe_fields(execution, caplog, monkeypatch):
    settings, factory, run_id, task_id = execution
    settings.worker_shutdown_grace = 1
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    started, stopped = asyncio.Event(), asyncio.Event()

    async def slow(_task):
        started.set()
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    worker._dispatch = slow
    caplog.set_level("INFO", logger="backend.workers.runtime")
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    pending = asyncio.create_task(worker.run_once())
    await started.wait()
    worker.request_stop()
    assert await asyncio.wait_for(pending, 3)
    assert stopped.is_set()
    async with factory() as session:
        assert (await session.get(TaskModel, task_id)).state == "retry_waiting"
        assert (await session.get(RunModel, run_id)).status == "retry_waiting"
    logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "backend.workers.runtime"
    ]
    assert logs[-1]["action"] == "release"
    assert logs[-1]["task_id"] == task_id
    assert logs[-1]["run_id"] == run_id
    assert logs[-1]["generation"] == 1
    assert logs[-1]["attempt"] == 1


@pytest.mark.asyncio
async def test_worker_database_poll_recovers_and_redacts_exception(execution, caplog, monkeypatch):
    settings, factory, _, _ = execution
    settings.queue_poll_interval = 0.01
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    original = worker.run_once
    calls = 0

    async def intermittent():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private-secret-host-path")
        result = await original()
        worker.request_stop()
        return result

    worker.run_once = intermittent
    caplog.set_level("INFO", logger="backend.workers.runtime")
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    await asyncio.wait_for(worker.run_forever(), 3)
    assert calls == 2
    assert "private-secret-host-path" not in caplog.text
    assert "DATABASE_UNAVAILABLE" in caplog.text


@pytest.mark.asyncio
async def test_readiness_cold_start_reconnects_without_restart(execution):
    settings, factory, _, _ = execution

    class ReconnectingNotifier:
        client = None

        async def probe(self):
            self.client = self
            return True

        async def set(self, key, value, ex):
            self.marker = (key, value, ex)

    notifier = ReconnectingNotifier()
    worker = WorkerRuntime(settings, factory, notifier)
    await worker.heartbeat()
    assert notifier.marker[0] == f"sesrag:worker:ready:{worker.worker_id}"


@pytest.mark.asyncio
async def test_journal_does_not_flush_stale_run_over_terminal(execution):
    settings, factory, run_id, _ = execution
    async with factory() as stale, factory() as writer:
        run = await stale.get(RunModel, run_id)
        await cancel_run(writer, settings, run_id)
        run.status = "running"
        with pytest.raises(ValueError):
            await append_event(stale, run_id, "answer.delta", {"text": "late"})
        await stale.rollback()
    async with factory() as session:
        assert (await session.get(RunModel, run_id)).status == "cancelled"


@pytest.mark.asyncio
async def test_run_task_only_success_helper_cannot_bypass_final_message(execution):
    settings, factory, run_id, task_id = execution
    async with factory() as session:
        await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task_id, "a", 1)
        assert not await queue.mark_succeeded(session, task_id, "a", 1)
        assert (await session.get(RunModel, run_id)).assistant_message_id is None


@pytest.mark.asyncio
async def test_transient_failure_emits_retry_action_with_safe_error(execution, caplog, monkeypatch):
    settings, factory, _, task_id = execution
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))

    async def failing(_task):
        raise RuntimeError("private-host-path-and-secret")

    worker._dispatch = failing
    caplog.set_level("INFO", logger="backend.workers.runtime")
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    await worker.run_once()
    logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "backend.workers.runtime"
    ]
    assert logs[-1]["action"] == "retry"
    assert logs[-1]["error_code"] == "RUN_FAILED"
    assert "private-host" not in caplog.text
    async with factory() as session:
        assert (await session.get(TaskModel, task_id)).last_error_code == "RUN_FAILED"


@pytest.mark.asyncio
async def test_legacy_mock_snapshot_survives_settings_change(execution):
    settings, factory, run_id, _ = execution
    async with factory() as session:
        run = await session.get(RunModel, run_id)
        # 升级前真实协议只有三个字段；此处构造旧持久事实，不模拟执行结果。
        run.snapshot_json = {"model": "mock", "retrieval": {"top_k": 5}, "prompt_version": 1}
        await session.commit()
    settings.mock_provider = False
    settings.owner_id = "changed-owner"
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    await worker.run_once()
    async with factory() as session:
        assert (await session.get(RunModel, run_id)).status == "succeeded"


@pytest.mark.asyncio
async def test_unrecoverable_snapshot_fails_permanently_with_safe_code(execution):
    settings, factory, run_id, task_id = execution
    async with factory() as session:
        run = await session.get(RunModel, run_id)
        run.snapshot_json = {"model": "unknown-old-model"}
        await session.commit()
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    await worker.run_once()
    async with factory() as session:
        task = await session.get(TaskModel, task_id)
        assert task.state == "failed"
        assert task.last_error_code == "INVALID_RUN_SNAPSHOT"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["queued", "running", "retry_waiting"])
async def test_deadline_settles_all_nonterminal_task_states(execution, monkeypatch, state):
    settings, factory, run_id, task_id = execution
    now = queue.utc_now()
    async with factory() as session:
        if state != "queued":
            await queue.claim_next_task(session, "a", settings)
            await queue.mark_running(session, task_id, "a", 1)
        if state == "retry_waiting":
            await queue.schedule_retry(session, task_id, "a", 1, settings, "RUN_FAILED")
    monkeypatch.setattr(queue, "utc_now", lambda: now + timedelta(seconds=700))
    async with factory() as session:
        await queue.requeue_expired(session)
        await queue.requeue_expired(session)
        assert (await session.get(TaskModel, task_id)).state == "failed"
        assert (await session.get(RunModel, run_id)).last_error_code == "TASK_DEADLINE_EXCEEDED"
        assert (
            len(
                [
                    event
                    for event in await list_events(session, run_id)
                    if event.type == "run.failed"
                ]
            )
            == 1
        )


@pytest.mark.asyncio
async def test_attempt_exhaustion_settles_run_without_stuck_task(execution):
    settings, factory, run_id, task_id = execution
    async with factory() as session:
        await cancel_run(session, settings, run_id)
        settings.task_max_attempts = 1
        thread = await create_thread(session, settings, "single attempt")
        _, run, task, _ = await create_message_run(
            session, settings, thread.thread_id, "question", "single"
        )
        await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task.task_id, "a", 1)
        await queue.schedule_retry(session, task.task_id, "a", 1, settings, "RUN_FAILED")
        assert (await session.get(TaskModel, task.task_id)).state == "failed"
        assert (await session.get(RunModel, run.run_id)).status == "failed"


@pytest.mark.asyncio
async def test_guarded_provider_timeout_cancels_pending_work(execution):
    settings, factory, _, task_id = execution
    stopped = asyncio.Event()

    async def hanging():
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    async with factory() as session:
        await queue.claim_next_task(session, "a", settings)
        await queue.mark_running(session, task_id, "a", 1)
    with pytest.raises(TimeoutError):
        await guarded_call(factory, task_id, "a", 1, hanging, timeout=0.02)
    assert stopped.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["requeue_expired", "claim_next_task", "mark_running"])
async def test_stop_interrupts_blocked_claim(execution, monkeypatch, phase):
    settings, factory, _, task_id = execution
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    blocked = asyncio.Event()

    async def claim(*_args):
        blocked.set()
        await asyncio.sleep(30)

    monkeypatch.setattr(queue, phase, claim)
    pending = asyncio.create_task(worker.run_once())
    await blocked.wait()
    worker.request_stop()
    try:
        done, _ = await asyncio.wait({pending}, timeout=1)
        assert done, "stop did not interrupt blocked claim"
        assert pending.result() == (phase == "mark_running")
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
    async with factory() as session:
        task = await session.get(TaskModel, task_id)
        assert task.attempt == (1 if phase == "mark_running" else 0)
        assert task.state == ("retry_waiting" if phase == "mark_running" else "queued")


@pytest.mark.asyncio
async def test_shutdown_blocked_release_is_bounded_and_stops_renewal(
    execution, monkeypatch, caplog
):
    settings, factory, _, _ = execution
    settings.worker_shutdown_grace = 1
    settings.task_heartbeat_interval = 1
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    started, releasing = asyncio.Event(), asyncio.Event()

    async def slow(_task):
        started.set()
        await asyncio.sleep(30)

    async def release(*_args):
        releasing.set()
        await asyncio.sleep(30)

    worker._dispatch = slow
    monkeypatch.setattr(queue, "release_task", release)
    caplog.set_level("INFO", logger="backend.workers.runtime")
    monkeypatch.setattr(logging.getLogger("backend.workers.runtime"), "disabled", False)
    pending = asyncio.create_task(worker.run_once())
    await started.wait()
    worker.request_stop()
    try:
        await releasing.wait()
        done, _ = await asyncio.wait({pending}, timeout=2)
        assert done, "shutdown blocked indefinitely in release"
        assert pending.result()
        renewals = sum('"action": "renew"' in record.message for record in caplog.records)
        await asyncio.sleep(1.1)
        assert sum('"action": "renew"' in record.message for record in caplog.records) == renewals
        assert not any('"action": "release"' in record.message for record in caplog.records)
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_shutdown_does_not_gather_uncooperative_handler_forever(execution):
    settings, factory, _, _ = execution
    settings.worker_shutdown_grace = 1
    worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
    started, allow_cleanup, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow_cleanup(_task):
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            while not allow_cleanup.is_set():
                try:
                    await allow_cleanup.wait()
                except asyncio.CancelledError:
                    pass
            cleaned.set()

    worker._dispatch = slow_cleanup
    pending = asyncio.create_task(worker.run_once())
    await started.wait()
    worker.request_stop()
    try:
        done, _ = await asyncio.wait({pending}, timeout=3)
        assert done, "shutdown waited indefinitely for handler cleanup"
        assert pending.result()
    finally:
        allow_cleanup.set()
        await asyncio.wait_for(cleaned.wait(), 1)
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
