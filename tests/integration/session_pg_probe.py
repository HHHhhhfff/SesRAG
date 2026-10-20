"""仅在显式隔离 PostgreSQL 测试库验证 v2 多连接锁与发布竞态。"""

import asyncio
import json
import os
import sys
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sync_engine
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.api.schemas.v2.runs import RunOperationCreate
from backend.api.schemas.v2.threads import BranchCreate, MessageCreate
from backend.application.branches import create_branch
from backend.application.errors import ApplicationError
from backend.application.session_runs import (
    cancel_session_run,
    create_related_run,
    create_session_message,
)
from backend.application.task_execution import ExecutionStopped, complete_run
from backend.application.threads import create_thread
from backend.config import Settings
from backend.db.models import BranchModel, MessageModel, RunEventModel, RunModel, TaskModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.journal import list_events
from backend.infrastructure.queue import postgres_queue as queue


@contextmanager
def isolated_database():
    """只接受已由操作者创建且名字含专属前缀的空库，不读取 DATABASE_URL。"""
    raw = os.environ.get("SESSION_PG_PROBE_URL", "")
    if not raw:
        raise SystemExit(
            "Set SESSION_PG_PROBE_URL to a NEW isolated sesrag_session_probe_* database"
        )
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "sesrag_session_probe_"
    ):
        raise SystemExit("Refusing database outside sesrag_session_probe_* namespace")
    engine = sync_engine(url)
    try:
        with engine.begin() as connection:
            tables = connection.scalar(
                text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            )
            if tables:
                raise SystemExit(
                    "Refusing nonempty probe database; create a fresh isolated database"
                )
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield url.render_as_string(hide_password=False)
    finally:
        engine.dispose()


async def seeded(factory, settings):
    async with factory() as session:
        thread = await create_thread(session, settings, "PG v2 probe", conversation_version=2)
        branch = await session.scalar(
            select(BranchModel).where(BranchModel.thread_id == thread.thread_id)
        )
        result, _ = await create_session_message(
            session,
            settings,
            thread.thread_id,
            MessageCreate(branch_id=branch.branch_id, content="source", expected_version=0),
            str(uuid4()),
        )
    return thread.thread_id, branch.branch_id, result


async def claim_seeded_task(session, settings, result, worker_id, scenario):
    """确保全局队列领取的是当前场景创建的Task，避免前置场景污染断言对象。"""
    claimed = await queue.claim_next_task(session, worker_id, settings)
    if claimed is None or claimed.task_id != result["task_id"]:
        await session.rollback()
        target = await session.get(TaskModel, result["task_id"])
        queued = list(
            (
                await session.execute(
                    select(
                        TaskModel.task_id,
                        TaskModel.run_id,
                        TaskModel.state,
                        TaskModel.available_at,
                        TaskModel.deadline_at,
                        TaskModel.attempt,
                        TaskModel.max_attempts,
                    )
                    .where(TaskModel.state == "queued")
                    .order_by(TaskModel.available_at, TaskModel.created_at)
                )
            ).mappings()
        )
        raise AssertionError(
            f"{scenario}: seeded Task领取不匹配；"
            f"expected={result['task_id']} target_state={getattr(target, 'state', None)}; "
            f"claimed={getattr(claimed, 'task_id', None)}; queued={queued}"
        )
    return claimed


async def task_holder(factory, task_id):
    session = factory()
    await session.begin()
    await queue.lock_task(session, task_id)
    return session


async def waiting_connection(engine, blocked_pid, operation):
    """通过 PG 的真实 wait graph 同步，不以固定 sleep 猜测已经阻塞。"""
    async with engine.connect() as observer:
        async with asyncio.timeout(5):
            while True:
                blocked = await observer.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": blocked_pid}
                )
                if blocked:
                    assert not operation.done()
                    return
                if operation.done():
                    await operation
                    raise AssertionError("operation completed before lock contention")
                await asyncio.sleep(0.01)


async def cancel_success_probe(engine, factory, settings):
    for cancel_first in (True, False):
        _, _, result = await seeded(factory, settings)
        async with factory() as session:
            task = await claim_seeded_task(session, settings, result, "race", "cancel/success race")
            await queue.mark_running(session, task.task_id, "race", task.generation)
        blocker = await task_holder(factory, task.task_id)
        try:
            async with factory() as waiter:
                pid = await waiter.scalar(text("SELECT pg_backend_pid()"))
                operation = asyncio.create_task(
                    complete_run(waiter, task.task_id, "race", task.generation, "answer", [])
                    if cancel_first
                    else cancel_session_run(waiter, settings, result["run_id"])
                )
                await waiting_connection(engine, pid, operation)
                if cancel_first:
                    await cancel_session_run(blocker, settings, result["run_id"])
                    try:
                        await operation
                    except ExecutionStopped:
                        pass
                    else:
                        raise AssertionError("cancel-first accepted late success")
                    await waiter.rollback()
                    async with factory() as session:
                        assert await queue.acknowledge_cancellation(
                            session, task.task_id, "race", task.generation
                        )
                else:
                    await complete_run(blocker, task.task_id, "race", task.generation, "answer", [])
                    assert (await operation).status == "succeeded"
        finally:
            await blocker.close()
        async with factory() as session:
            events = await list_events(session, result["run_id"])
            terminal = [
                e.type for e in events if e.type in {"run.succeeded", "run.failed", "run.cancelled"}
            ]
            assert terminal == ["run.cancelled" if cancel_first else "run.succeeded"]
    print("PASS PG Task lock serializes cancel/success both commit orders; one terminal")


async def creation_probe(engine, factory, settings):
    tid, bid, result = await seeded(factory, settings)
    async with factory() as session:
        await cancel_session_run(session, settings, result["run_id"])
    start = asyncio.Barrier(3)

    async def create(key, version=1):
        async with factory() as session:
            await start.wait()
            try:
                return await create_session_message(
                    session,
                    settings,
                    tid,
                    MessageCreate(branch_id=bid, content="concurrent", expected_version=version),
                    key,
                )
            except ApplicationError as exc:
                return exc.code

    one = asyncio.create_task(create("same"))
    two = asyncio.create_task(create("same"))
    await start.wait()
    left, right = await asyncio.gather(one, two)
    assert left[0]["run_id"] == right[0]["run_id"] and sorted([left[1], right[1]]) == [False, True]
    async with factory() as session:
        await cancel_session_run(session, settings, left[0]["run_id"])
        child, _ = await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=bid, fork_message_id=result["message_id"]),
            "child",
        )
    # 来源终态显式新 Run 可在 Thread 锁后只读，既有 Task 锁不应形成反序等待。
    held = await task_holder(factory, result["task_id"])
    try:
        async with factory() as session:
            async with asyncio.timeout(3):
                retry, _ = await create_related_run(
                    session, settings, result["run_id"], RunOperationCreate(), "related", "retry"
                )
            assert retry["branch_id"] != bid
    finally:
        await held.close()
    async with factory() as session:
        await cancel_session_run(session, settings, retry["run_id"])
    # 不同 Branch 的活动 Run 可并发创建，Thread 只短暂串行分配 seq。
    gate = asyncio.Barrier(3)

    async def submit_branch(branch_id, version, key):
        async with factory() as session:
            await gate.wait()
            return await create_session_message(
                session,
                settings,
                tid,
                MessageCreate(branch_id=branch_id, content="independent", expected_version=version),
                key,
            )

    left = asyncio.create_task(submit_branch(bid, 2, "parallel-root"))
    right = asyncio.create_task(submit_branch(child.branch_id, 0, "parallel-child"))
    await gate.wait()
    parallel = await asyncio.gather(left, right)
    assert parallel[0][0]["branch_id"] != parallel[1][0]["branch_id"]
    async with factory() as session:
        for result, _ in parallel:
            await cancel_session_run(session, settings, result["run_id"])
    print("PASS PG idempotent creation, independent Branches, and no source Task reverse locking")


async def stale_and_publication_probe(engine, factory, settings):
    for stage in ("assistant", "terminal"):
        _, _, result = await seeded(factory, settings)
        async with factory() as session:
            task = await claim_seeded_task(
                session, settings, result, "publisher", f"stale publication {stage}"
            )
            await queue.mark_running(session, task.task_id, "publisher", task.generation)
        clock = queue.utc_now() + timedelta(seconds=settings.task_lease_ttl + 1)
        with patch.object(queue, "utc_now", return_value=clock):
            async with factory() as session:
                await queue.requeue_expired(session)
                replacement = await queue.claim_next_task(session, "replacement", settings)
                assert replacement.task_id == task.task_id and replacement.generation == 2
        async with factory() as session:
            try:
                await complete_run(session, task.task_id, "publisher", task.generation, "stale", [])
            except ExecutionStopped:
                pass
            else:
                raise AssertionError("stale generation published")
        async with factory() as session:
            before = (await session.get(RunModel, result["run_id"])).next_event_seq

        class FlushBarrier(AsyncSession):
            async def flush(self, *args, probe_stage=stage, probe_task=replacement, **kwargs):
                hit = any(
                    (isinstance(row, MessageModel) and row.role == "assistant")
                    if probe_stage == "assistant"
                    else (isinstance(row, RunEventModel) and row.type == "run.succeeded")
                    for row in self.new
                )
                await super().flush(*args, **kwargs)
                if hit:
                    future = probe_task.lease_expires_at + timedelta(seconds=1)
                    clock_mock.return_value = future

        guarded_factory = async_sessionmaker(
            engine, class_=FlushBarrier, expire_on_commit=False, autoflush=False
        )
        with patch.object(queue, "utc_now", return_value=queue.utc_now()) as clock_mock:
            async with guarded_factory() as session:
                try:
                    await complete_run(
                        session, replacement.task_id, "replacement", 2, "expired", []
                    )
                except ExecutionStopped:
                    pass
                else:
                    raise AssertionError("last-flush expired authorization published")
        async with factory() as session:
            run = await session.get(RunModel, result["run_id"])
            assert run.next_event_seq == before and run.assistant_message_id is None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(MessageModel)
                    .where(MessageModel.run_id == run.run_id, MessageModel.role == "assistant")
                )
                == 0
            )
            await cancel_session_run(session, settings, run.run_id)
            await queue.acknowledge_cancellation(session, replacement.task_id, "replacement", 2)
    print(
        "PASS PG old generation rejected and assistant/terminal flush expiry rolls back all facts"
    )


async def cancellation_reclaim_probe(factory, settings):
    _, _, result = await seeded(factory, settings)
    async with factory() as session:
        task = await claim_seeded_task(
            session, settings, result, "cancel-reclaim", "cancellation reclaim"
        )
    held = await task_holder(factory, task.task_id)
    future = task.deadline_at + timedelta(seconds=1)
    try:
        # Task 锁已经建立后，另一真实连接回收必须 SKIP LOCKED。
        with patch.object(queue, "utc_now", return_value=future):
            async with factory() as reclaimer:
                assert await queue.requeue_expired(reclaimer) == 0
        assert (await cancel_session_run(held, settings, result["run_id"])).status == "cancelling"
    finally:
        await held.close()
    with patch.object(queue, "utc_now", return_value=future):
        async with factory() as session:
            assert not await queue.acknowledge_cancellation(
                session, task.task_id, "cancel-reclaim", 1
            )
            assert await queue.requeue_expired(session) == 1
    async with factory() as session:
        run = await session.get(RunModel, result["run_id"])
        saved = await session.get(TaskModel, task.task_id)
        assert run.status == saved.state == "cancelled"
        assert [e.type for e in await list_events(session, run.run_id)][-1] == "run.cancelled"
    print("PASS PG reclaimer skips locked Task; cancellation beats expired deadline after release")


async def main(url):
    settings = Settings(
        database_url=url, redis_enabled=False, task_lease_ttl=10, task_heartbeat_interval=2
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        await cancel_success_probe(engine, factory, settings)
        await creation_probe(engine, factory, settings)
        await stale_and_publication_probe(engine, factory, settings)
        await cancellation_reclaim_probe(factory, settings)
    finally:
        await engine.dispose()
    print(
        json.dumps(
            {
                "result": "PASS",
                "database_namespace": "sesrag_session_probe_*",
                "real_postgresql": True,
            }
        )
    )


if __name__ == "__main__":
    # Windows Proactor 无法承载 psycopg async；本机探针显式选用 Selector loop。
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with isolated_database() as isolated_url:
        asyncio.run(main(isolated_url))
