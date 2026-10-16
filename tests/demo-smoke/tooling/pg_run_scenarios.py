"""真实会话/取消/Journal事务场景。"""

import asyncio
import json

from pg_harness import Provider, event_fact, until
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.task_execution import (
    ExecutionStopped,
    complete_run,
)
from backend.application.threads import create_message_run, create_thread
from backend.db.models import MessageModel, RunModel, TaskModel, ThreadModel
from backend.infrastructure.events.journal import append_event, list_events
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.rag.pgvector_store import PgVectorStore
from backend.workers.handlers.run_handler import process_run_task


async def complete(h, task, answer="最终回答"):
    async with h.factory() as session:
        await queue.mark_running(session, task.task_id, task.worker_id, task.generation)
        await complete_run(session, task.task_id, task.worker_id, task.generation, answer, [])


async def dispatch(h, task, provider=None):
    provider = provider or Provider()
    await process_run_task(
        h.factory,
        h.cfg,
        task.task_id,
        task.worker_id,
        task.generation,
        provider,
        provider,
        provider_factory=lambda _: (provider, provider),
        vector_store_factory=PgVectorStore,
    )


async def idempotency(h):
    async with h.factory() as session:
        thread = await create_thread(session, h.cfg, "确定性幂等竞争")
    async with h.factory() as blocker:
        await blocker.execute(
            select(ThreadModel).where(ThreadModel.thread_id == thread.thread_id).with_for_update()
        )

        async def submit():
            async with h.factory() as session:
                return await create_message_run(
                    session, h.cfg, thread.thread_id, "同Key问题", "same-key"
                )

        first, second = h.launch(submit()), h.launch(submit())
        await h.locked(2)
        await blocker.rollback()
        a, b = await asyncio.gather(first, second)
    h.check(
        a[0].message_id == b[0].message_id
        and a[1].run_id == b[1].run_id
        and a[2].task_id == b[2].task_id,
        "真实双连接等待Thread锁后返回同一Message/Run/Task",
    )
    h.check(sorted([a[3], b[3]]) == [False, True], "锁内幂等复查区分首次与重放")
    facts = await h.facts(
        {"thread_id": thread.thread_id, "run_id": a[1].run_id, "task_id": a[2].task_id}
    )
    h.check(
        len(facts["messages"]) == 1 and len(facts["events"]) == 2 and facts["cursor"] == 1,
        "幂等竞争仅创建一组事实和两个初始Event",
    )
    h.trace["facts"] = facts


async def reentry(h):
    for terminal in ("succeeded", "failed"):
        ids = await h.seed()
        if terminal == "succeeded":
            task = await h.claim()
            await dispatch(h, task)
        else:
            await h.worker(Provider(failures=1, permanent=True)).run_once()
            async with h.factory() as session:
                task = await session.get(TaskModel, ids["task_id"])
        before = await h.facts(ids)
        h.check(
            before["run"]["status"] == before["task"]["state"] == terminal,
            f"{terminal}重入前Run/Task确为目标终态",
        )
        assistants = [m for m in before["messages"] if m["role"] == "assistant"]
        terminal_events = [
            e
            for e in before["events"]
            if e["type"] in {"run.succeeded", "run.failed", "run.cancelled"}
        ]
        h.check(
            len(terminal_events) == 1 and terminal_events[0]["type"] == "run." + terminal,
            f"{terminal}重入前恰有一个对应terminal事件",
        )
        if terminal == "succeeded":
            h.check(
                len(assistants) == 1
                and assistants[0]["message_id"] == before["run"]["assistant_message_id"],
                "succeeded重入前唯一assistant与Run指针一致",
            )
        else:
            h.check(
                not assistants
                and before["run"]["assistant_message_id"] is None
                and before["run"]["last_error_code"]
                == before["task"]["last_error_code"]
                == "TEST_PROVIDER_FAILURE",
                "failed重入前无assistant且注入的永久失败码一致",
            )
        async with h.factory() as session:
            event = (await list_events(session, ids["run_id"]))[-1]
            normal = event_fact(event)
            changed = event_fact(
                event, payload={**event.payload_json, "comparison_sentinel": "changed"}
            )
            h.check(
                normal != changed
                and {k: v for k, v in normal.items() if k != "payload_sha256"}
                == {k: v for k, v in changed.items() if k != "payload_sha256"},
                f"{terminal}仅内存payload改变的比较负哨兵被hash识别，未写业务SQL",
            )
        for operation in (lambda task=task: dispatch(h, task), lambda task=task: complete(h, task)):
            try:
                await operation()
            except ExecutionStopped:
                pass
            else:
                raise AssertionError("终态重入未拒绝")
        async with h.factory() as session:
            accepted = await queue.schedule_retry(
                session, task.task_id, task.worker_id, task.generation, h.cfg, "LATE_ERROR"
            )
        h.check(not accepted, f"{terminal}终态拒绝迟到失败重入")
        await h.cancel(ids)
        h.check(
            await h.facts(ids) == before,
            f"{terminal}重复handler/final/失败/cancel不改变消息、指针、状态、错误与Journal",
        )


async def message_sequence(h):
    for winner in ("user", "assistant"):
        ids = await h.seed()
        task = await h.claim()
        async with h.factory() as session:
            await queue.mark_running(session, task.task_id, task.worker_id, task.generation)
        async with h.factory() as first:
            await first.execute(
                select(ThreadModel)
                .where(ThreadModel.thread_id == ids["thread_id"])
                .with_for_update()
            )
            if winner == "user":
                pending = h.launch(complete(h, task))
            else:

                async def submit(ids=ids):
                    async with h.factory() as session:
                        return await create_message_run(
                            session, h.cfg, ids["thread_id"], "交错用户", "second"
                        )

                pending = h.launch(submit())
            await h.locked()
            if winner == "user":
                await create_message_run(first, h.cfg, ids["thread_id"], "交错用户", "second")
            else:
                await complete_run(
                    first, task.task_id, task.worker_id, task.generation, "assistant", []
                )
            await pending
        facts = await h.facts(ids)
        h.check(
            [m["seq"] for m in facts["messages"]] == [1, 2, 3] and facts["cursor"] == 3,
            f"{winner}先提交后共享seq无丢失且游标一致",
        )
        expected = (
            ["user", "user", "assistant"] if winner == "user" else ["user", "assistant", "user"]
        )
        h.check(
            [m["role"] for m in facts["messages"]] == expected,
            f"{winner}先提交的消息顺序反映真实锁顺序",
        )
        # 第二条用户Task经正式cancel收尾，避免下一迭代领取错身份。
        async with h.factory() as session:
            other = (
                await session.scalars(
                    select(RunModel).where(
                        RunModel.thread_id == ids["thread_id"], RunModel.run_id != ids["run_id"]
                    )
                )
            ).one()
            from backend.application.runs import cancel_run

            await cancel_run(session, h.cfg, other.run_id)


async def creation_rollback(h, phase):
    async with h.factory() as session:
        thread = await create_thread(session, h.cfg, "创建事务失败")
    fired = []

    class FaultSession(AsyncSession):
        async def flush(self, *args, **kwargs):
            if phase == "flush" and not fired and any(isinstance(x, RunModel) for x in self.new):
                fired.append("flush")
                raise RuntimeError("test-flush-fault")
            return await super().flush(*args, **kwargs)

        async def commit(self):
            if phase == "commit" and not fired:
                await self.flush()
                fired.append("commit")
                raise RuntimeError("test-commit-fault")
            return await super().commit()

    factory = async_sessionmaker(h.engine, class_=FaultSession, expire_on_commit=False)
    try:
        async with factory() as session:
            await create_message_run(session, h.cfg, thread.thread_id, "事务失败", "rollback")
    except RuntimeError:
        pass
    h.check(fired == [phase], "精确本例session故障已命中")
    async with h.factory() as session:
        counts = [
            (await session.execute(select(model).where(model.thread_id == thread.thread_id))).all()
            for model in (MessageModel, RunModel)
        ]
        tasks = list(await session.scalars(select(TaskModel)))
        events = (await session.execute(text("SELECT count(*) FROM run_events"))).scalar()
        cursor = (await session.get(ThreadModel, thread.thread_id)).next_message_seq
    h.check(
        counts == [[], []] and not tasks and events == 0 and cursor == 0,
        "独立PG连接确认Message/Run/Task/Event/Thread游标整组回滚",
    )
    ids = await h.seed(thread_id=thread.thread_id)
    h.check((await h.facts(ids))["cursor"] == 1, "故障解除后新提交从seq1正常创建")


async def final_rollback(h):
    ids = await h.seed()
    task = await h.claim()
    async with h.factory() as session:
        await queue.mark_running(session, task.task_id, task.worker_id, task.generation)
    before = await h.facts(ids)
    gate = h.gate()

    class FaultSession(AsyncSession):
        async def commit(self):
            if any(
                isinstance(x, RunModel) and x.status == "succeeded"
                for x in self.identity_map.values()
            ):
                await self.flush()
                await gate.pause()
                raise RuntimeError("final-commit-fault")
            return await super().commit()

    factory = async_sessionmaker(h.engine, class_=FaultSession, expire_on_commit=False)

    async def finish():
        async with factory() as session:
            try:
                await complete_run(
                    session, task.task_id, task.worker_id, task.generation, "answer", []
                )
            except RuntimeError:
                return "rolled-back"

    pending = h.launch(finish())
    await gate.wait()
    h.check(
        await h.facts(ids) == before, "final事务已flush但提交前外部连接不可见assistant/终态/游标"
    )
    gate.open()
    h.check(
        await pending == "rolled-back" and await h.facts(ids) == before,
        "final commit故障后所有最终事实原子回滚",
    )
    await complete(h, task)
    facts = await h.facts(ids)
    h.check(
        facts["run"]["status"] == facts["task"]["state"] == "succeeded"
        and len(facts["messages"]) == 2
        and [e["type"] for e in facts["events"][-2:]] == ["message.completed", "run.succeeded"],
        "恢复后assistant/Run/Task/两个终态事件同事务成功",
    )


async def journal(h):
    ids = await h.seed()
    async with h.factory() as first:
        await append_event(first, ids["run_id"], "answer.delta", {"text": "一"})

        async def append():
            async with h.factory() as second:
                await append_event(second, ids["run_id"], "answer.delta", {"text": "二"})
                await second.commit()

        pending = h.launch(append())
        await h.locked()
        await first.commit()
        await pending
    async with h.factory() as first:
        await append_event(first, ids["run_id"], "answer.delta", {"text": "回滚"})
        pending = h.launch(append())
        await h.locked()
        await first.rollback()
        await pending
    facts = await h.facts(ids)
    h.check(
        [e["seq"] for e in facts["events"]] == [1, 2, 3, 4, 5]
        and facts["run"]["next_event_seq"] == 5,
        "两连接竞争及回滚后append的Journal严格连续且游标等于最大seq",
    )
    async with h.factory() as session:
        h.check(
            all(
                e.payload_json.get("text") != "回滚"
                for e in await list_events(session, ids["run_id"])
            ),
            "回滚Event不可见且不永久占号",
        )
    h.trace["facts"] = facts


async def cancellation(h, stage):
    ids = await h.seed()
    gate = h.gate()
    provider = Provider(stage=stage, gate=gate)
    searches = []

    class Store(PgVectorStore):
        async def search(self, *args):
            result = await super().search(*args)
            searches.append(True)
            if stage == "search":
                await gate.pause()
            return result

    worker = h.worker(provider, vector_store_factory=Store)
    pending = h.launch(worker.run_once())
    await gate.wait()
    before = await h.facts(ids)
    h.check(before["run"]["status"] == "running", "取消屏障时Run真实running")
    if stage == "delta":
        h.check(
            sum(e["type"] == "answer.delta" for e in before["events"]) == 1,
            "取消前第一片已在PG独立可见",
        )
    await h.cancel(ids)
    gate.open()
    await pending
    facts = await h.facts(ids)
    h.check(
        facts["run"]["status"] == facts["task"]["state"] == "cancelled"
        and facts["run"]["assistant_message_id"] is None,
        "取消阻止最终assistant和成功结算",
    )
    h.check(
        sum(e["type"] == "run.cancelled" for e in facts["events"]) == 1
        and not any(e["type"] == "run.succeeded" for e in facts["events"]),
        "只有一个取消终态且无成功事件",
    )
    h.check(
        sum(e["type"] == "answer.delta" for e in facts["events"]) == (1 if stage == "delta" else 0),
        "取消后不追加迟到delta",
    )
    if stage == "embed":
        h.check(
            not searches and provider.calls["model"] == 0, "embed屏障取消后search及模型调用均为零"
        )
    if stage == "search":
        h.check(
            len(searches) == 1 and provider.calls["model"] == 0, "search完成屏障取消后模型调用为零"
        )
    h.trace.update(before=before, after=facts, calls=provider.calls)


async def cancel_retry(h):
    ids = await h.seed()
    provider = Provider(failures=1)
    worker = h.worker(provider)
    await worker.run_once()
    facts = await h.facts(ids)
    h.check(facts["run"]["status"] == "retry_waiting", "取消前真实临时失败持久retry_waiting")
    await h.cancel(ids)

    async def due():
        return queue.utc_now() > facts["task"]["available_at"]

    await until(due)
    await worker.run_once()
    after = await h.facts(ids)
    h.check(
        after["task"]["state"] == after["run"]["status"] == "cancelled"
        and provider.calls["embed"] == 1,
        "跨available_at回排不复活已取消Task且无重试调用",
    )


async def terminal_race(h, winner):
    ids = await h.seed()
    task = await h.claim()
    async with h.factory() as session:
        await queue.mark_running(session, task.task_id, task.worker_id, task.generation)
    async with h.factory() as first:
        await queue.lock_task(first, task.task_id)

        async def contend():
            if winner == "success":
                await h.cancel(ids)
            else:
                try:
                    await complete(h, task)
                except ExecutionStopped:
                    return
                raise AssertionError("取消已提交却接受成功")

        pending = h.launch(contend())
        await h.locked()
        if winner == "success":
            await complete_run(first, task.task_id, task.worker_id, task.generation, "answer", [])
        else:
            from backend.application.runs import cancel_run

            await cancel_run(first, h.cfg, ids["run_id"])
        await pending
    facts = await h.facts(ids)
    state = "succeeded" if winner == "success" else "cancelled"
    h.check(
        facts["run"]["status"] == facts["task"]["state"] == state, f"{winner}先提交决定唯一持久终态"
    )
    h.check(
        sum(e["type"] in ("run.succeeded", "run.cancelled", "run.failed") for e in facts["events"])
        == 1,
        "取消/成功真实重叠后恰有一个终态Event",
    )
    h.check(
        len(facts["messages"]) == (2 if winner == "success" else 1),
        "assistant仅在成功先提交时创建一次",
    )


async def state_projection(h, state):
    import httpx

    from backend.app import create_app

    ids = await h.seed()
    gate = h.gate()
    provider = (
        Provider(stage="embed", gate=gate)
        if state == "running"
        else Provider(failures=1, permanent=state == "failed")
    )
    worker = h.worker(provider)
    pending = h.launch(worker.run_once())
    if state == "running":
        await gate.wait()
    else:
        await pending
    app = create_app(h.cfg)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/runs/" + ids["run_id"])
        facts = await h.facts(ids)
        body = response.json()
        h.check(
            response.status_code == 200
            and body["status"] == facts["run"]["status"] == state
            and body["task"]["state"] == facts["task"]["state"] == state,
            f"{state}正式API响应与独立PG的Run/Task一致",
        )
        h.check(
            body["last_error_code"] == facts["run"]["last_error_code"], f"{state}错误码投影一致"
        )
    finally:
        gate.open()
        await pending
        await app.state.engine.dispose()


async def final_flush_expiry(h):
    ids = await h.seed()
    task = await h.claim()
    async with h.factory() as session:
        await queue.mark_running(session, task.task_id, task.worker_id, task.generation)
    gate = h.gate()

    class FlushBarrier(AsyncSession):
        async def flush(self, *args, **kwargs):
            if not gate.entered.is_set() and any(
                isinstance(item, MessageModel) and item.role == "assistant" for item in self.new
            ):
                await gate.pause()
            return await super().flush(*args, **kwargs)

    factory = async_sessionmaker(h.engine, class_=FlushBarrier, expire_on_commit=False)

    async def finish():
        async with factory() as session:
            try:
                await complete_run(
                    session, task.task_id, task.worker_id, task.generation, "过期回答", []
                )
                return "accepted"
            except ExecutionStopped:
                return "rejected"

    pending = h.launch(finish())
    await gate.wait()
    before = await h.facts(ids)

    async def expired():
        return queue.utc_now() > task.lease_expires_at

    await until(expired)
    gate.open()
    outcome = await pending
    after = await h.facts(ids)
    print(
        "FINAL_FLUSH_OBSERVED:"
        + json.dumps(
            {"before": before, "after": after, "outcome": outcome}, default=str, ensure_ascii=False
        )
    )
    h.check(
        outcome == "rejected" and after == before,
        "最终assistant flush跨真实lease到期必须回滚而非发布成功",
    )
