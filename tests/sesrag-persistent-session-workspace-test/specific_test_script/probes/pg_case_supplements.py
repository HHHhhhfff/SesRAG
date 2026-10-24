"""SES_016 / RUN_003/016/021：真实PG事务与迟到执行边界补充。"""

import asyncio
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.api.schemas.v2.threads import BranchCreate, MessageCreate
from backend.application.branches import create_branch
from backend.application.context import ContextInput, plan_context
from backend.application.errors import ApplicationError
from backend.application.session_execution import publish_plan
from backend.application.session_runs import cancel_session_run, create_session_message
from backend.application.task_execution import (
    ExecutionStopped,
    append_execution_event,
    complete_run,
    lock_execution,
)
from backend.db.models import BranchModel, RunModel
from backend.infrastructure.providers.context_counter import MockTokenCounter
from backend.infrastructure.queue import postgres_queue as queue
from tests.integration.session_pg_probe import claim_seeded_task, seeded, task_holder


async def fingerprint(factory):
    # 新连接观察所有关联事实；不使用同一ORM identity map证明事务原子性。
    async with factory() as session:
        result = {}
        for table in [
            "threads",
            "branches",
            "messages",
            "runs",
            "tasks",
            "run_events",
            "context_plans",
        ]:
            rows = await session.scalars(text(f"SELECT row_to_json(t)::text FROM {table} t"))
            result[table] = sorted(rows)
        return result


async def creation_edges(engine, factory, settings):
    """SES_016：不同键同版本竞争；消息与合法历史分叉两种启动次序。"""
    tid, bid, first = await seeded(factory, settings)
    async with factory() as session:
        await cancel_session_run(session, settings, first["run_id"])
    gate = asyncio.Barrier(3)

    async def submit(token):
        async with factory() as session:
            await gate.wait()
            try:
                return await create_session_message(
                    session,
                    settings,
                    tid,
                    MessageCreate(branch_id=bid, content=token, expected_version=1),
                    token,
                )
            except ApplicationError as error:
                return error.code

    pending = [asyncio.create_task(submit(token)) for token in ["different-a", "different-b"]]
    await gate.wait()
    observations = await asyncio.wait_for(asyncio.gather(*pending), 5)
    winners = [item for item in observations if isinstance(item, tuple)]
    assert len(winners) == 1, f"同版本不同键应仅一胜：{observations!r}"
    assert [item for item in observations if isinstance(item, str)][0] in {
        "BRANCH_BUSY",
        "BRANCH_HEAD_CHANGED",
    }, f"失败方必须为正式Branch冲突码：{observations!r}"
    async with factory() as session:
        await cancel_session_run(session, settings, winners[0][0]["run_id"])
    for message_first in [True, False]:
        tid, bid, source = await seeded(factory, settings)
        async with factory() as session:
            await cancel_session_run(session, settings, source["run_id"])
        gate = asyncio.Barrier(3)

        async def message(gate=gate, tid=tid, bid=bid):
            async with factory() as session:
                await gate.wait()
                return await create_session_message(
                    session,
                    settings,
                    tid,
                    MessageCreate(
                        branch_id=bid, content="concurrent new input", expected_version=1
                    ),
                    "new-input",
                )

        async def branch(gate=gate, tid=tid, bid=bid, source=source):
            async with factory() as session:
                await gate.wait()
                return await create_branch(
                    session,
                    settings,
                    tid,
                    BranchCreate(parent_branch_id=bid, fork_message_id=source["message_id"]),
                    "historical-fork",
                )

        operations = [message(), branch()] if message_first else [branch(), message()]
        tasks = [asyncio.create_task(operation) for operation in operations]
        await gate.wait()
        values = await asyncio.wait_for(asyncio.gather(*tasks), 5)
        created = values[0 if message_first else 1][0]
        child = values[1 if message_first else 0][0]
        assert child.parent_branch_id == bid and child.fork_message_id == source["message_id"]
        assert created["branch_id"] == bid
        async with factory() as session:
            await cancel_session_run(session, settings, created["run_id"])
    print("真实PG：不同键同Branch同版本仅一套新事实；消息/历史分叉两种启动次序无死锁且都合法")


async def stale_all_writes(engine, factory, settings):
    """RUN_016：B真实重领后，A计划/delta/进度/续租/失败/完成全部不能写回。"""
    tid, bid, source = await seeded(factory, settings)
    async with factory() as session:
        old = await claim_seeded_task(session, settings, source, "old-worker", "stale all")
        assert await queue.mark_running(session, old.task_id, "old-worker", old.generation)
    future = queue.utc_now() + timedelta(seconds=settings.task_lease_ttl + 1)
    with patch.object(queue, "utc_now", return_value=future):
        async with factory() as session:
            await queue.requeue_expired(session)
            new = await queue.claim_next_task(session, "new-worker", settings)
            assert new.task_id == old.task_id and new.generation == old.generation + 1
            assert await queue.mark_running(session, new.task_id, "new-worker", new.generation)
        context = ContextInput(
            tid, bid, source["message_id"], "source", "system", 8192, 1024, 128, (), ()
        )
        plan = plan_context(context, MockTokenCounter())
        await publish_plan(
            factory, new.task_id, "new-worker", new.generation, plan, context, {}, []
        )
        async with factory() as session:
            await append_execution_event(
                session,
                new.task_id,
                "new-worker",
                new.generation,
                "answer.delta",
                {"text": "B_ONLY"},
            )
            await session.commit()
        before = await fingerprint(factory)
        try:
            await publish_plan(
                factory, old.task_id, "old-worker", old.generation, plan, context, {}, []
            )
        except ExecutionStopped:
            pass
        else:
            raise AssertionError("旧generation计划被接收")
        for boundary in ["delta", "progress", "complete"]:
            async with factory() as session:
                try:
                    if boundary == "delta":
                        await append_execution_event(
                            session,
                            old.task_id,
                            "old-worker",
                            old.generation,
                            "answer.delta",
                            {"text": "A_FORBIDDEN"},
                        )
                    elif boundary == "progress":
                        task, _ = await lock_execution(
                            session, old.task_id, "old-worker", old.generation
                        )
                        task.progress_json = {"forbidden": "A"}
                        await session.commit()
                    else:
                        await complete_run(
                            session, old.task_id, "old-worker", old.generation, "A_FORBIDDEN", []
                        )
                except ExecutionStopped:
                    await session.rollback()
                else:
                    raise AssertionError(f"旧generation {boundary}被接收")
            assert await fingerprint(factory) == before
        async with factory() as session:
            assert not await queue.renew_lease(
                session, old.task_id, "old-worker", old.generation, settings
            )
            assert not await queue.schedule_retry(
                session, old.task_id, "old-worker", old.generation, settings, "OLD"
            )
        assert await fingerprint(factory) == before
        async with factory() as session:
            await complete_run(session, new.task_id, "new-worker", new.generation, "B_ONLY", [])
    print("真实PG：旧generation六种迟到写边界全部拒绝，B计划/Event/消息/Head逐表不变且B正常完成")


async def commit_failure(engine, factory, settings):
    """RUN_003：最终事实已flush时制造真实PG事务错误，再用新连接确认整组回滚。"""
    _, bid, source = await seeded(factory, settings)
    async with factory() as session:
        task = await claim_seeded_task(session, settings, source, "commit-probe", "commit rollback")
        await queue.mark_running(session, task.task_id, "commit-probe", task.generation)
    before = await fingerprint(factory)

    class RejectCommit(AsyncSession):
        async def commit(self):
            await self.execute(text("SELECT 1/0"))

    broken = async_sessionmaker(
        engine, class_=RejectCommit, expire_on_commit=False, autoflush=False
    )
    async with broken() as session:
        try:
            await complete_run(
                session, task.task_id, "commit-probe", task.generation, "NOT_COMMITTED", []
            )
        except DBAPIError:
            await session.rollback()
        else:
            raise AssertionError("数据库错误没有中止最终发布")
    assert await fingerprint(factory) == before
    async with factory() as session:
        assert (await session.get(BranchModel, bid)).head_message_id == source["message_id"]
        await complete_run(session, task.task_id, "commit-probe", task.generation, "COMMITTED", [])
    async with factory() as session:
        assert (await session.get(RunModel, source["run_id"])).assistant_message_id
    print("真实PG：最终flush后事务错误整组回滚；同一合法执行者随后原子成功")


async def cancellation_skip_locked(engine, factory, settings):
    """RUN_021：取消回收遇到被锁任务时仍处理另一个任务，迟到delta被拒绝。"""
    sources = [(await seeded(factory, settings))[2] for _ in range(2)]
    tasks = []
    for index, source in enumerate(sources):
        async with factory() as session:
            tasks.append(
                await claim_seeded_task(session, settings, source, f"worker-{index}", "skip locked")
            )
            await cancel_session_run(session, settings, source["run_id"])
    held = await task_holder(factory, tasks[0].task_id)
    try:
        with patch.object(queue, "utc_now", return_value=queue.utc_now() + timedelta(seconds=11)):
            async with factory() as session:
                assert await asyncio.wait_for(queue.requeue_expired(session), 3) >= 1
            async with factory() as session:
                assert (await session.get(RunModel, sources[1]["run_id"])).status == "cancelled"
    finally:
        await held.close()
    with patch.object(queue, "utc_now", return_value=queue.utc_now() + timedelta(seconds=11)):
        async with factory() as session:
            await queue.requeue_expired(session)
    before = await fingerprint(factory)
    async with factory() as session:
        try:
            await append_execution_event(
                session,
                tasks[0].task_id,
                "worker-0",
                tasks[0].generation,
                "answer.delta",
                {"text": "LATE"},
            )
        except ExecutionStopped:
            await session.rollback()
        else:
            raise AssertionError("取消终态后接收迟到delta")
    assert await fingerprint(factory) == before
    print("真实PG：回收skip locked不阻塞其他取消任务；最终取消不可被迟到增量翻转")
