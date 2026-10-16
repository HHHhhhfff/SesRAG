"""在显式 DATABASE_URL 的隔离 PG 库执行真实双连接竞争，禁止修改业务状态 SQL。"""

import asyncio
import json
import os
from datetime import timedelta
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sync_engine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.runs import cancel_run
from backend.application.task_execution import (
    ExecutionStopped,
    append_execution_event,
    complete_run,
)
from backend.application.threads import create_message_run, create_thread
from backend.config import Settings
from backend.db.models import MessageModel, RunEventModel, RunModel, TaskModel, ThreadModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.journal import append_event, list_events
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.queue import postgres_queue as queue
from backend.workers.runtime import WorkerRuntime


async def claim_lock_probe(factory, settings):
    for advance in (40, 700):
        async with factory() as session:
            thread = await create_thread(session, settings, f"claim-lock-{advance}")
            _, run, task, _ = await create_message_run(
                session, settings, thread.thread_id, "question", "claim"
            )
        async with factory() as blocker:
            await queue.lock_run(blocker, run.run_id)

            async def claim():
                async with factory() as session:
                    return await queue.claim_next_task(session, "claim-lock-worker", settings)

            pending = asyncio.create_task(claim())
            await asyncio.sleep(0.2)
            assert not pending.done()
            clock = queue.utc_now() + timedelta(seconds=advance)
            with patch.object(queue, "utc_now", return_value=clock):
                await blocker.rollback()
                claimed = await pending
                if advance == 40:
                    assert claimed is not None
                    assert claimed.lease_expires_at > clock, (
                        "claim committed expired lease after Run lock wait"
                    )
                else:
                    assert claimed is None, (
                        "claim consumed attempt after deadline passed while waiting for Run lock"
                    )
        async with factory() as session:
            saved = await session.get(TaskModel, task.task_id)
            if advance == 700:
                assert saved.attempt == 0 and saved.generation == 0
                assert not any(
                    event.type == "task.leased" for event in await list_events(session, run.run_id)
                )
            await cancel_run(session, settings, run.run_id)
    print(
        "PASS: PG claim waits for Run lock before allocating fresh lease; "
        "crossed deadline consumes no attempt/event"
    )


async def shutdown_lock_probe(factory, settings):
    settings.worker_shutdown_grace = 1
    settings.task_heartbeat_interval = 1
    for phase in ("claim", "release"):
        async with factory() as session:
            thread = await create_thread(session, settings, f"shutdown-{phase}")
            _, run, task, _ = await create_message_run(
                session, settings, thread.thread_id, "question", phase
            )
        worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
        started = asyncio.Event()

        async def slow(_task, started=started):
            started.set()
            await asyncio.sleep(30)

        worker._dispatch = slow
        async with factory() as blocker:
            if phase == "claim":
                await queue.lock_run(blocker, run.run_id)
            pending = asyncio.create_task(worker.run_once())
            if phase == "release":
                await started.wait()
                await queue.lock_run(blocker, run.run_id)
            else:
                await asyncio.sleep(0.2)
                assert not pending.done()
            stopped_at = asyncio.get_running_loop().time()
            worker.request_stop()
            done, _ = await asyncio.wait({pending}, timeout=4)
            try:
                assert done, f"worker shutdown blocked in PG {phase}"
                pending.result()
                elapsed = asyncio.get_running_loop().time() - stopped_at
                async with factory() as session:
                    # NOWAIT证明取消的事务确实已回滚并释放Task锁。
                    saved = (
                        await session.execute(
                            select(TaskModel)
                            .where(TaskModel.task_id == task.task_id)
                            .with_for_update(nowait=True)
                        )
                    ).scalar_one()
                    expiry = saved.lease_expires_at
                    if phase == "claim":
                        assert saved.state == "queued" and saved.attempt == 0
                    else:
                        assert saved.state == "running"
                await asyncio.sleep(1.1)
                async with factory() as session:
                    assert (await session.get(TaskModel, task.task_id)).lease_expires_at == expiry
                print(
                    f"PASS: PG shutdown blocked {phase} exited in {elapsed:.3f}s; "
                    "transaction rolled back; no later renewal"
                )
            finally:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                await blocker.rollback()
        async with factory() as session:
            await cancel_run(session, settings, run.run_id)


async def main():
    settings = Settings(
        _env_file=None, database_url=os.environ["DATABASE_URL"], redis_enabled=False
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    if os.environ.get("EXECUTION_PROBE_CASE") == "final-publication":
        try:
            await final_publication_probe(engine, factory, settings)
        finally:
            await engine.dispose()
        return
    if os.environ.get("EXECUTION_PROBE_CASE") in {"claim-lock", "shutdown-lock", "fix1"}:
        try:
            if os.environ["EXECUTION_PROBE_CASE"] != "shutdown-lock":
                await claim_lock_probe(factory, settings)
            if os.environ["EXECUTION_PROBE_CASE"] != "claim-lock":
                await shutdown_lock_probe(factory, settings)
        finally:
            await engine.dispose()
        return

    async def seed(title):
        async with factory() as session:
            thread = await create_thread(session, settings, title)
            _, run, task, _ = await create_message_run(
                session, settings, thread.thread_id, "question", title
            )
            return thread.thread_id, run.run_id, task.task_id

    async with factory() as session:
        thread = await create_thread(session, settings, "concurrent idempotency")

    async def post():
        async with factory() as session:
            return await create_message_run(session, settings, thread.thread_id, "question", "same")

    results = await asyncio.gather(post(), post())
    assert results[0][1].run_id == results[1][1].run_id
    assert sorted(item[3] for item in results) == [False, True]
    run_id, task_id = results[0][1].run_id, results[0][2].task_id
    print("PASS: PG concurrent idempotency returns one Message/Run/Task")

    async def claim(worker):
        async with factory() as session:
            return await queue.claim_next_task(session, worker, settings)

    claims = await asyncio.gather(claim("a"), claim("b"))
    first = next(item for item in claims if item is not None)
    assert sum(item is not None for item in claims) == 1
    print("PASS: PG two executors claim exactly once")
    clock = queue.utc_now() + timedelta(seconds=40)
    with patch.object(queue, "utc_now", return_value=clock):
        async with factory() as session:
            await queue.requeue_expired(session)
        second = await claim("new")
        assert second.generation == 2
        async with factory() as stale, factory() as writer:
            await stale.get(TaskModel, task_id)
            assert await queue.mark_running(writer, task_id, "new", 2)
            assert not await queue.renew_lease(stale, task_id, first.worker_id, 1, settings)
            assert not await queue.mark_succeeded(stale, task_id, first.worker_id, 1)
            assert not await queue.schedule_retry(
                stale, task_id, first.worker_id, 1, settings, "RUN_FAILED"
            )
            for operation in (
                lambda: append_execution_event(
                    stale, task_id, first.worker_id, 1, "answer.delta", {"text": "late"}
                ),
                lambda: complete_run(stale, task_id, first.worker_id, 1, "late", []),
            ):
                try:
                    await operation()
                except ExecutionStopped:
                    await stale.rollback()
                else:
                    raise AssertionError("stale generation accepted")
            assert await queue.schedule_retry(writer, task_id, "new", 2, settings, "RUN_FAILED")
    with patch.object(queue, "utc_now", return_value=clock + timedelta(seconds=10)):
        async with factory() as session:
            await queue.requeue_expired(session)
            assert (await session.get(TaskModel, task_id)).state == "queued"
            assert (await session.get(RunModel, run_id)).status == "retry_waiting"
            third = await queue.claim_next_task(session, "third", settings)
            assert third.generation == 3
            await queue.mark_running(session, task_id, "third", 3)
            await complete_run(session, task_id, "third", 3, "answer", [])
            assert (await cancel_run(session, settings, run_id)).status == "succeeded"
    print(
        "PASS: PG stale renew/event/completion/failure rejected; retry due; success precedes cancel"
    )

    _, run_id, task_id = await seed("cancel-first")
    task = await claim("cancel-worker")
    async with factory() as writer, factory() as other:
        await queue.mark_running(writer, task_id, "cancel-worker", task.generation)
        await cancel_run(other, settings, run_id)
        try:
            await complete_run(writer, task_id, "cancel-worker", task.generation, "late", [])
        except ExecutionStopped:
            await writer.rollback()
        else:
            raise AssertionError("cancelled run completed")
        assert not list(
            (
                await writer.execute(
                    select(MessageModel).where(
                        MessageModel.run_id == run_id, MessageModel.role == "assistant"
                    )
                )
            ).scalars()
        )
    print("PASS: PG cancel precedes success; no assistant created")

    thread_id, run_id, task_id = await seed("journal")

    async def journal(text):
        async with factory() as session:
            # 提前读取，刻意保留另一连接提交前的 identity map。
            stale = await session.get(RunModel, run_id)
            await asyncio.sleep(0)
            await append_event(session, stale.run_id, "answer.delta", {"text": text})
            await session.commit()

    await asyncio.gather(*(journal(str(i)) for i in range(8)))
    async with factory() as session:
        await append_event(session, run_id, "answer.delta", {"text": "rollback"})
        await session.rollback()
        await append_event(session, run_id, "answer.delta", {"text": "after rollback"})
        await session.commit()
        events = await list_events(session, run_id)
        assert [item.seq for item in events] == list(range(1, 12))
        assert all(item.payload_json.get("text") != "rollback" for item in events)
    print("PASS: PG concurrent journal seq monotonic, rollback gap-free")

    task = await claim("expiry-worker")
    async with factory() as session:
        await queue.mark_running(session, task_id, "expiry-worker", task.generation)
    # Thread 锁真实等待：完成者先取得 Task/Run，随后时钟越过租约再释放 Thread。
    async with factory() as blocker:
        await blocker.execute(
            select(ThreadModel).where(ThreadModel.thread_id == thread_id).with_for_update()
        )

        async def finish_waiter():
            async with factory() as session:
                try:
                    await complete_run(
                        session, task_id, "expiry-worker", task.generation, "expired", []
                    )
                    return "accepted"
                except ExecutionStopped:
                    return "rejected"

        pending = asyncio.create_task(finish_waiter())
        await asyncio.sleep(0.2)
        assert not pending.done()
        with patch.object(queue, "utc_now", return_value=queue.utc_now() + timedelta(seconds=40)):
            await blocker.rollback()
            assert await pending == "rejected"
    print("PASS: PG Thread lock wait crossing lease expiry rejects completion")

    # Task 锁等待也不能沿用查询发起前的时间。
    async with factory() as blocker:
        await queue.lock_task(blocker, task_id)

        async def renew_waiter():
            async with factory() as session:
                return await queue.renew_lease(
                    session, task_id, "expiry-worker", task.generation, settings
                )

        pending = asyncio.create_task(renew_waiter())
        await asyncio.sleep(0.2)
        assert not pending.done()
        with patch.object(queue, "utc_now", return_value=queue.utc_now() + timedelta(seconds=40)):
            await blocker.rollback()
            assert not await pending
    async with factory() as session:
        await cancel_run(session, settings, run_id)
    print("PASS: PG Task lock wait crossing lease expiry rejects renewal")

    for winner in ("cancel", "success"):
        _, run_id, task_id = await seed(f"race-{winner}")
        task = await claim("racer")
        async with factory() as session:
            await queue.mark_running(session, task_id, "racer", task.generation)
        async with factory() as first:
            await queue.lock_task(first, task_id)

            async def contender(winner=winner, run_id=run_id, task_id=task_id, task=task):
                async with factory() as session:
                    if winner == "success":
                        return (await cancel_run(session, settings, run_id)).status
                    try:
                        await complete_run(session, task_id, "racer", task.generation, "late", [])
                        return "succeeded"
                    except ExecutionStopped:
                        return "rejected"

            pending = asyncio.create_task(contender())
            await asyncio.sleep(0.2)
            assert not pending.done()
            if winner == "success":
                await complete_run(first, task_id, "racer", task.generation, "winner", [])
                assert await pending == "succeeded"
            else:
                await cancel_run(first, settings, run_id)
                assert await pending == "rejected"
    print("PASS: PG overlapping cancel/success transactions honor first lock-holder commit")
    await engine.dispose()


async def final_publication_probe(engine, factory, settings):
    failures = []
    for stage in ("assistant", "terminal"):
        for expiry in ("lease", "deadline"):
            cfg = settings.model_copy(
                update={
                    "task_lease_ttl": 2 if expiry == "lease" else 30,
                    "task_heartbeat_interval": 1,
                    "task_deadline": 600 if expiry == "lease" else 2,
                }
            )
            async with factory() as session:
                thread = await create_thread(session, cfg, f"final-{stage}-{expiry}")
                _, run, task, _ = await create_message_run(
                    session, cfg, thread.thread_id, "question", "publication"
                )
                task = await queue.claim_next_task(session, "publication-worker", cfg)
                await queue.mark_running(
                    session, task.task_id, "publication-worker", task.generation
                )

            async def facts(task=task, run=run, thread=thread):
                async with factory() as session:
                    result = {}
                    for model, condition in (
                        (TaskModel, TaskModel.task_id == task.task_id),
                        (RunModel, RunModel.run_id == run.run_id),
                        (ThreadModel, ThreadModel.thread_id == thread.thread_id),
                        (MessageModel, MessageModel.thread_id == thread.thread_id),
                        (RunEventModel, RunEventModel.run_id == run.run_id),
                    ):
                        rows = (await session.execute(select(model).where(condition))).scalars()
                        result[model.__tablename__] = sorted(
                            [
                                dict(
                                    (c.name, getattr(row, c.name)) for c in model.__table__.columns
                                )
                                for row in rows
                            ],
                            key=lambda row: str(row),
                        )
                    return result

            before = await facts()
            entered = False

            class FlushBarrier(AsyncSession):
                async def flush(self, *args, stage=stage, expiry=expiry, task=task, **kwargs):
                    nonlocal entered
                    hit = (
                        any(
                            isinstance(item, MessageModel) and item.role == "assistant"
                            for item in self.new
                        )
                        if stage == "assistant"
                        else any(
                            isinstance(item, RunEventModel) and item.type == "run.succeeded"
                            for item in self.new
                        )
                    )
                    result = await super().flush(*args, **kwargs)
                    if hit and not entered:
                        entered = True
                        boundary = task.lease_expires_at if expiry == "lease" else task.deadline_at
                        # 等待真实时间自然到期；没有回收者、时钟替换或业务状态SQL。
                        async with asyncio.timeout(5):
                            while queue.utc_now() <= boundary:
                                await asyncio.sleep(0.02)
                    return result

            guarded_factory = async_sessionmaker(
                engine, class_=FlushBarrier, expire_on_commit=False, autoflush=False
            )
            async with guarded_factory() as session:
                try:
                    await complete_run(
                        session,
                        task.task_id,
                        "publication-worker",
                        task.generation,
                        "expired answer",
                        [],
                    )
                    outcome = "accepted"
                except ExecutionStopped:
                    outcome = "rejected"
            after = await facts()
            passed = entered and outcome == "rejected" and before == after
            print(
                "FINAL_PUBLICATION:"
                + json.dumps(
                    {
                        "stage": stage,
                        "expiry": expiry,
                        "outcome": outcome,
                        "unchanged": before == after,
                        "before": before,
                        "after": after,
                    },
                    default=str,
                )
            )
            if not passed:
                failures.append(f"{stage}/{expiry}")
            async with factory() as session:
                await cancel_run(session, cfg, run.run_id)
    assert not failures, f"final publication crossed expiry: {failures}"
    print(
        "PASS: PG final assistant/terminal flush x lease/deadline "
        "all facts and both cursors rolled back"
    )


if __name__ == "__main__":
    migration_engine = sync_engine(os.environ["DATABASE_URL"])
    with migration_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    migration_engine.dispose()
    asyncio.run(main())
