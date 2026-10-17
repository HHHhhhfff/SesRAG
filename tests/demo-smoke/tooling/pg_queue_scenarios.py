"""真实PG队列、租约、重试和Worker进程场景。"""

import asyncio
from datetime import timedelta
from unittest.mock import patch

from pg_harness import ChildWorker, Provider, until
from pg_run_scenarios import complete
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.task_execution import (
    ExecutionStopped,
    append_execution_event,
)
from backend.db.models import TaskModel
from backend.infrastructure.queue import postgres_queue as queue


async def dual_worker(h):
    first_ids, second_ids = await h.seed(), await h.seed()
    async with h.factory() as blocker:
        await queue.lock_run(blocker, first_ids["run_id"])
        first = h.launch(h.claim("a"))
        await h.locked()
        second = await asyncio.wait_for(h.claim("b"), 2)
        h.check(
            second.task_id == second_ids["task_id"],
            "A持Task锁等Run时B通过SKIP LOCKED立即领取另一Task",
        )
        await blocker.rollback()
        a = await first
    h.check(
        a.task_id == first_ids["task_id"]
        and a.generation == second.generation == 1
        and a.attempt == second.attempt == 1,
        "两个Worker领取互异Task且attempt/generation只加一次",
    )
    await h.cancel(first_ids)
    await h.cancel(second_ids)
    ids = await h.seed()
    claims = await asyncio.gather(h.claim("c"), h.claim("d"))
    h.check(sum(x is not None for x in claims) == 1, "两真实Worker竞争唯一Task仅一次成功")
    h.check((await h.facts(ids))["task"]["attempt"] == 1, "单Task竞争无重复attempt")


async def lease_identity(h):
    ids = await h.seed()
    task = await h.claim()
    for task_id, owner, generation in [
        ("00000000-0000-0000-0000-000000000000", task.worker_id, 1),
        (task.task_id, "wrong-worker", 1),
        (task.task_id, task.worker_id, 2),
    ]:
        before = await h.facts(ids)
        async with h.factory() as session:
            result = await queue.renew_lease(session, task_id, owner, generation, h.cfg)
        h.check(
            not result and await h.facts(ids) == before,
            "错误task/worker/generation续租均拒绝且持久事实不变",
        )
    async with h.factory() as session:
        h.check(
            await queue.renew_lease(session, task.task_id, task.worker_id, 1, h.cfg),
            "有效三元身份能正常续租",
        )
    before = await h.facts(ids)
    with patch.object(queue, "utc_now", return_value=before["task"]["lease_expires_at"]):
        async with h.factory() as session:
            accepted = await queue.renew_lease(session, task.task_id, task.worker_id, 1, h.cfg)
    h.check(not accepted and await h.facts(ids) == before, "租约等号已过期，即便未回收也不能续租")
    with patch.object(
        queue, "utc_now", return_value=before["task"]["lease_expires_at"] + timedelta(seconds=1)
    ):
        async with h.factory() as session:
            accepted = await queue.renew_lease(session, task.task_id, task.worker_id, 1, h.cfg)
    h.check(not accepted and await h.facts(ids) == before, "租约小于now已过期续租拒绝且事实不变")
    await h.cancel(ids)
    for state in ("queued", "retry_waiting", "succeeded", "failed", "cancelled"):
        ids = await h.seed()
        if state == "queued":
            owner, generation = "unowned", 0
        else:
            task = await h.claim()
            owner, generation = task.worker_id, task.generation
            if state == "succeeded":
                await complete(h, task)
            elif state == "cancelled":
                await h.cancel(ids)
            else:
                async with h.factory() as session:
                    await queue.schedule_retry(
                        session,
                        task.task_id,
                        owner,
                        generation,
                        h.cfg,
                        "TEST",
                        permanent=state == "failed",
                    )
        before = await h.facts(ids)
        async with h.factory() as session:
            accepted = await queue.renew_lease(session, ids["task_id"], owner, generation, h.cfg)
        h.check(
            not accepted and await h.facts(ids) == before, f"非active {state}即便身份正确也拒绝续租"
        )
        await h.cancel(ids)


async def stale_generation(h):
    for kind in ("run", "index"):
        ids = await h.seed(kind)
        old = await h.claim("old")
        clock = old.lease_expires_at + timedelta(milliseconds=1)
        with patch.object(queue, "utc_now", return_value=clock):
            await h.reclaim()
            current = await h.claim("new")
            async with h.factory() as session:
                await queue.mark_running(session, current.task_id, "new", current.generation)
            before = await h.facts(ids)
            operations = [
                lambda s, old=old: queue.renew_lease(s, old.task_id, "old", 1, h.cfg),
                lambda s, old=old: queue.mark_running(s, old.task_id, "old", 1),
                lambda s, old=old: queue.mark_succeeded(s, old.task_id, "old", 1),
                lambda s, old=old: queue.schedule_retry(
                    s, old.task_id, "old", 1, h.cfg, "LATE_ERROR"
                ),
                lambda s, old=old: queue.release_task(s, old.task_id, "old", 1, h.cfg),
            ]
            for operation in operations:
                async with h.factory() as session:
                    h.check(
                        not await operation(session),
                        f"{kind}旧generation的renew/start/success/retry/release安全拒绝",
                    )
                h.check(await h.facts(ids) == before, f"{kind}旧写回不能覆盖新owner/期限/状态/错误")
            if kind == "run":
                for event in ("retrieval.completed", "answer.delta"):
                    async with h.factory() as session:
                        try:
                            await append_execution_event(
                                session, old.task_id, "old", 1, event, {"text": "late"}
                            )
                        except ExecutionStopped:
                            pass
                        else:
                            raise AssertionError("旧Event未拒绝")
                h.check(await h.facts(ids) == before, "迟到retrieval/delta不追加Event或消耗seq")
        if kind == "run":
            await h.cancel(ids)
        else:
            with patch.object(queue, "utc_now", return_value=clock):
                async with h.factory() as session:
                    await queue.schedule_retry(
                        session,
                        current.task_id,
                        "new",
                        current.generation,
                        h.cfg,
                        "CLEANUP",
                        permanent=True,
                    )


async def retry(h, mode):
    for kind in ("run", "index"):
        ids = await h.seed(kind)
        provider = Provider(failures=1 if mode == "success" else 10)
        worker = h.worker(provider)
        original = await h.facts(ids)
        for attempt in range(1, h.cfg.task_max_attempts + 1):
            before = queue.utc_now()
            await worker.run_once()
            after = queue.utc_now()
            facts = await h.facts(ids)
            if facts["task"]["state"] == "succeeded":
                break
            expected_delay = h.cfg.task_retry_base_delay * 2 ** (attempt - 1)
            h.check(
                before + timedelta(seconds=expected_delay)
                <= facts["task"]["available_at"]
                <= after + timedelta(seconds=expected_delay),
                f"{kind}attempt{attempt}持久退避时间位于真实故障前后UTC区间",
            )
            if facts["task"]["state"] == "failed":
                break
            h.check(
                facts["task"]["state"] == "retry_waiting"
                and ("run" not in facts or facts["run"]["status"] == "retry_waiting"),
                f"{kind}临时错误正式结算retry_waiting",
            )
            calls = provider.calls.copy()
            await worker.run_once()
            h.check(provider.calls == calls, f"{kind}available_at之前不执行外部调用")

            async def due(facts=facts):
                return queue.utc_now() >= facts["task"]["available_at"]

            await until(due, 10)
            await h.reclaim()
            queued = await h.facts(ids)
            h.check(
                queued["task"]["state"] == "queued"
                and ("run" not in queued or queued["run"]["status"] == "retry_waiting"),
                f"{kind}到期正式回排Task queued且Run仍retry_waiting",
            )
        expected = "succeeded" if mode == "success" else "failed"
        h.check(facts["task"]["state"] == expected, f"{kind}真实重试最终{expected}")
        h.check(
            facts["task"]["attempt"] == (2 if mode == "success" else 3), f"{kind}重试次数遵守上限"
        )
        h.check(
            facts["task"]["task_id"] == original["task"]["task_id"], f"{kind}重试复用原Task身份"
        )
        if kind == "run":
            h.check(
                facts["run"]["status"] == expected
                and len([m for m in facts["messages"] if m["role"] == "user"]) == 1,
                "Run与Task终态一致且用户Message不重复",
            )
        else:
            h.check(
                facts["document"]["status"] == ("indexed" if expected == "succeeded" else "failed"),
                "索引Task与Document结算一致",
            )
        calls = provider.calls.copy()
        await worker.run_once()
        h.check(
            await h.facts(ids) == facts and provider.calls == calls,
            f"{kind}终态后额外轮询不再领取或执行",
        )


async def expired_final(h):
    for kind in ("run", "index"):
        ids = await h.seed(kind)
        task = await h.claim()
        async with h.factory() as session:
            await queue.mark_running(session, task.task_id, task.worker_id, task.generation)

        async def expired(task=task):
            return queue.utc_now() >= task.lease_expires_at

        await until(expired)
        before = await h.facts(ids)
        if kind == "run":
            try:
                await complete(h, task)
            except ExecutionStopped:
                pass
            else:
                raise AssertionError("到期终写未拒绝")
        else:
            async with h.factory() as session:
                h.check(
                    not await queue.mark_succeeded(
                        session, task.task_id, task.worker_id, task.generation
                    ),
                    "索引同身份到期mark_succeeded被拒绝",
                )
        h.check(await h.facts(ids) == before, f"{kind}真实租约到期且无人回收仍拒绝终写、保留原事实")
        if kind == "run":
            await h.cancel(ids)
        else:
            # 到期Task由正式回收推进，再永久结算，避免污染下一场景。
            await h.reclaim()
            current = await h.claim()
            async with h.factory() as session:
                await queue.schedule_retry(
                    session,
                    current.task_id,
                    current.worker_id,
                    current.generation,
                    h.cfg,
                    "CLEANUP",
                    permanent=True,
                )


async def long_lease(h):
    ids = await h.seed()
    gate = h.gate()
    worker = h.worker(Provider(stage="embed", gate=gate))
    pending = h.launch(worker.run_once())
    await gate.wait()
    first = await h.facts(ids)
    samples = []
    for _ in range(9):
        await asyncio.sleep(1)
        await h.reclaim()
        h.check(await h.claim("competitor") is None, "跨两个TTL期间竞争Worker不能接管")
        sample = (await h.facts(ids))["task"]
        h.check(
            sample["worker_id"] == worker.worker_id
            and sample["generation"] == 1
            and sample["lease_expires_at"] > queue.utc_now(),
            "每秒独立PG采样的owner/generation不变且lease有效",
        )
        samples.append(sample)
    h.check(
        samples[-1]["lease_expires_at"] > first["task"]["lease_expires_at"],
        "长任务实际续租延长过初始lease",
    )
    gate.open()
    await pending
    h.check((await h.facts(ids))["run"]["status"] == "succeeded", "原Worker在有效lease内成功完成")
    h.trace["lease_samples"] = samples


async def signal_shutdown(h, mode):
    import signal
    import time

    h.cfg.worker_shutdown_grace = 8 if mode == "within" else 2
    ids = await h.seed()
    child = ChildWorker(h)
    await child.reached()
    queued = await h.seed()
    first = await h.facts(ids)
    stopped = time.monotonic()
    child.signal(signal.SIGTERM)
    if mode == "within":
        # 剩余工作时间跨初始TTL，但小于grace，证明停领不停止续租。
        await asyncio.sleep(4.3)
        current = await h.facts(ids)
        h.check(
            current["task"]["lease_expires_at"] > first["task"]["lease_expires_at"]
            and current["task"]["lease_expires_at"] > queue.utc_now(),
            "SIGTERM宽限内跨初始TTL仍继续真实续租",
        )
        h.check(
            (await h.facts(queued))["task"]["state"] == "queued",
            "SIGTERM之后B保持queued且未被旧Worker领取",
        )
        child.release()
    code = await child.wait_exit(8)
    elapsed = time.monotonic() - stopped
    h.check(
        code == 0 and elapsed < h.cfg.worker_shutdown_grace + 3,
        "生产main真实SIGTERM以exit0在grace加3秒预算内退出，未使用SIGKILL",
    )
    final = await h.facts(ids)
    h.check(
        (await h.facts(queued))["task"]["state"] == "queued", "生产main退出后B仍queued，未继续claim"
    )
    if mode == "within":
        h.check(
            final["run"]["status"] == final["task"]["state"] == "succeeded",
            "宽限内原Task/Run原子成功",
        )
    else:
        h.check(
            final["task"]["state"] in ("retry_waiting", "running"),
            "超宽限任务显式释放或保持可回收租约",
        )
        lease = final["task"]["lease_expires_at"]
        await asyncio.sleep(1.2)
        h.check((await h.facts(ids))["task"]["lease_expires_at"] == lease, "main退出后无迟到续租")
    h.trace.update(
        pid=child.process.pid,
        exit_code=code,
        elapsed_seconds=elapsed,
        final=final,
        main_logs=child.logs(),
    )
    worker = h.worker(Provider())
    await worker.run_once()
    if mode == "outside":

        async def due():
            return queue.utc_now() > final["task"]["available_at"]

        await until(due)
        await worker.run_once()
    h.check((await h.facts(queued))["run"]["status"] == "succeeded", "新Worker可继续原B任务")
    if mode == "outside":
        h.check(
            (await h.facts(ids))["run"]["status"] == "succeeded", "超宽限任务恢复后仍以原身份完成"
        )


async def crash_recovery(h, exhaust=False):
    import signal

    for kind in ("run", "index"):
        ids = await h.seed(kind)
        for attempt in range(1, 4 if exhaust else 2):
            child = ChildWorker(h)
            await child.reached()
            before = await h.facts(ids)
            h.check(
                before["task"]["state"] == "running" and before["task"]["attempt"] == attempt,
                f"{kind}第{attempt}次真实main已领取并到达处理屏障",
            )
            child.signal(signal.SIGKILL)
            h.check(await child.wait_exit() == -signal.SIGKILL, "实际SIGKILL崩溃而非优雅SIGTERM")
            await h.reclaim()
            h.check(await h.claim("early") is None, "崩溃后TTL内不得接管")

            async def expired(before=before):
                return queue.utc_now() >= before["task"]["lease_expires_at"]

            await until(expired)
            await h.reclaim()
            after = await h.facts(ids)
            if attempt == 3:
                h.check(
                    after["task"]["state"] == "failed"
                    and after["task"]["last_error_code"] == "TASK_ATTEMPTS_EXHAUSTED",
                    f"{kind}三次崩溃达到attempt上限明确失败",
                )
                h.check(
                    after.get("run", after.get("document"))["status"] == "failed",
                    f"{kind}关联Run/Document同步失败",
                )
                h.check(await h.claim("too-late") is None, "耗尽后不再领取")
            else:
                h.check(
                    after["task"]["state"] == "queued"
                    and after["task"]["worker_id"] is None
                    and after["task"]["lease_expires_at"] is None,
                    f"{kind}到期正式回收为queued并清owner/lease",
                )
        if not exhaust:
            await h.worker(Provider()).run_once()
            after = await h.facts(ids)
            h.check(
                after["task"]["state"] == "succeeded"
                and after["task"]["generation"] == 2
                and after["task"]["attempt"] == 2,
                f"{kind}新Worker以同Task第二代完成",
            )
            if kind == "run":
                h.check(len(after["messages"]) == 2, "崩溃恢复没有重复用户或assistant")


async def deadline(h, mode):
    for kind in ("run", "index"):
        h.cfg.task_deadline = 2
        h.cfg.task_retry_base_delay = 3
        ids = await h.seed(kind)
        gate = h.gate()
        provider = Provider(failures=1) if mode == "retry" else Provider(stage="embed", gate=gate)
        worker = h.worker(provider)
        pending = h.launch(worker.run_once())
        if mode == "running":
            await gate.wait()
        else:
            await pending
            f = await h.facts(ids)
            h.check(
                f["task"]["state"] == "retry_waiting"
                and f["task"]["available_at"] > f["task"]["deadline_at"],
                f"{kind}真实失败退避晚于总deadline",
            )
        original = await h.facts(ids)

        async def expired(original=original):
            return queue.utc_now() > original["task"]["deadline_at"]

        await until(expired)
        gate.open()
        await pending
        await h.reclaim()
        facts = await h.facts(ids)
        h.check(
            facts["task"]["state"] == "failed"
            and facts["task"]["last_error_code"] == "TASK_DEADLINE_EXCEEDED",
            f"{kind}跨deadline通过正式回收明确截止失败",
        )
        h.check(
            facts.get("run", facts.get("document"))["status"] == "failed",
            f"{kind}关联对象截止失败且不接受迟到成功",
        )
        h.check(
            provider.calls["model"] == 0
            and not any(e["type"] == "answer.delta" for e in facts.get("events", [])),
            "deadline后不继续昂贵模型或增量",
        )
        if mode == "retry":

            async def available(original=original):
                return queue.utc_now() > original["task"]["available_at"]

            await until(available)
            await worker.run_once()
            h.check(
                await h.facts(ids) == facts and provider.calls["embed"] == 1,
                "跨退避到期后也不会重试复活",
            )


async def queue_boundaries(h):
    ids = await h.seed()
    before = await h.facts(ids)
    with patch.object(
        queue, "utc_now", return_value=before["task"]["available_at"] - timedelta(microseconds=1)
    ):
        h.check(await h.claim() is None, "future available_at严格拒绝领取")
    with patch.object(queue, "utc_now", return_value=before["task"]["deadline_at"]):
        h.check(await h.claim() is None, "deadline=now严格拒绝领取")
    first = await h.claim()
    h.check(
        first.task_id == ids["task_id"] and first.attempt == first.generation == 1,
        "合法queued领取一次且身份代数正确",
    )
    h.check(await h.claim() is None, "leased不被重复领取")
    async with h.factory() as session:
        await queue.mark_running(session, first.task_id, first.worker_id, 1)
    h.check(await h.claim() is None, "running不被重复领取")
    async with h.factory() as session:
        await queue.schedule_retry(session, first.task_id, first.worker_id, 1, h.cfg, "TEMP")
    h.check(await h.claim() is None, "retry_waiting不能直接领取")
    await h.cancel(ids)
    h.check(await h.claim() is None, "cancelled不能领取")
    for state in ("succeeded", "failed"):
        ids = await h.seed()
        task = await h.claim()
        if state == "succeeded":
            await complete(h, task)
        else:
            async with h.factory() as session:
                await queue.schedule_retry(
                    session, task.task_id, task.worker_id, 1, h.cfg, "FAIL", permanent=True
                )
        h.check(await h.claim() is None, f"{state}终态不能领取")
    a, b = await h.seed(), await h.seed()
    claimed = await h.claim()
    h.check(claimed.task_id == a["task_id"], "不同创建时间按available_at/created_at先后领取")
    h.check((await h.claim()).task_id == b["task_id"], "首任务领取后下一任务有序领取")


async def lost_lease(h, late_error=False, stage="embed"):
    from backend.application.errors import PermanentTaskError
    from backend.infrastructure.queue.adapter import PostgresQueue

    for kind in ("run",) if stage == "delta" else ("run", "index"):
        ids = await h.seed(kind)
        gate = h.gate()

        class LateProvider(Provider):
            async def stream_answer(self, question, evidence, gate=gate):
                if stage != "delta":
                    async for part in super().stream_answer(question, evidence):
                        yield part
                    return
                self.calls["model"] += 1
                self.calls["delta"] += 1
                yield "第一片"
                try:
                    await gate.pause()
                except asyncio.CancelledError:
                    await asyncio.wait_for(gate.release.wait(), 8)
                self.calls["late_delta"] = 1
                yield "接管后迟到第二片"

            async def embed(self, value, gate=gate):
                self.calls["embed"] += 1
                if stage == "delta":
                    return [1.0] + [0.0] * 383
                try:
                    await gate.pause()
                except asyncio.CancelledError:
                    # 有界迟到异常覆盖：父例finally必放行，不创建无界吞取消协程。
                    await asyncio.wait_for(gate.release.wait(), 8)
                if late_error:
                    self.calls["late_error"] = self.calls.get("late_error", 0) + 1
                    raise PermanentTaskError("OLD_ERROR", "迟到安全异常")
                return [1.0] + [0.0] * 383

        class NoRenew(PostgresQueue):
            async def renew(self, task):
                # 仅抑制本次测试Worker续租；真实lease自然到期，不写数据库。
                return True

        provider = LateProvider(stage=stage, gate=gate)
        worker = h.worker(provider, queue_factory=lambda session: NoRenew(session, h.cfg))
        pending = h.launch(worker.run_once())
        await gate.wait()
        old = await h.facts(ids)

        async def expired(old=old):
            return queue.utc_now() > old["task"]["lease_expires_at"]

        await until(expired)
        await h.reclaim()
        fresh = await h.claim("new-owner")
        before = await h.facts(ids)
        gate.open()
        await pending
        h.check(
            fresh.generation == 2 and await h.facts(ids) == before,
            f"{kind}旧handler在新generation接管后迟到结果/异常不能改变新事实",
        )
        if late_error:
            h.check(provider.calls.get("late_error") == 1, f"{kind}旧Provider异常确实在接管后抛出")
        if stage == "delta":
            h.check(
                provider.calls.get("late_delta") == 1,
                "旧Provider第二片确实在接管后返回，未被提前取消替代",
            )
        h.check(
            provider.calls["embed"] == 1
            and provider.calls["model"] == (1 if stage == "delta" else 0),
            f"{kind}失租停止后续昂贵步骤",
        )
        rejected = [
            row
            for row in h.logs.rows
            if row.get("action") == "reject" and row.get("task_id") == ids["task_id"]
        ]
        h.check(
            bool(rejected)
            and all(
                row.get("worker_id") == worker.worker_id and row.get("generation") == 1
                for row in rejected
            ),
            f"{kind}失租有安全可关联拒绝日志",
        )
        with patch.object(queue, "utc_now", return_value=queue.utc_now()):
            async with h.factory() as session:
                await queue.schedule_retry(
                    session,
                    fresh.task_id,
                    fresh.worker_id,
                    fresh.generation,
                    h.cfg,
                    "CLEANUP",
                    permanent=True,
                )


async def heartbeat_rejection(h):
    from backend.infrastructure.queue.adapter import PostgresQueue

    for kind in ("run", "index"):
        ids = await h.seed(kind)
        gate = h.gate()
        calls = []

        class RejectRenew(PostgresQueue):
            async def renew(self, task, calls=calls):
                calls.append(task.task_id)
                return False

        provider = Provider(stage="embed", gate=gate)
        worker = h.worker(provider, queue_factory=lambda session: RejectRenew(session, h.cfg))
        pending = h.launch(worker.run_once())
        await gate.wait()
        await asyncio.wait_for(pending, 4)
        gate.open()
        facts = await h.facts(ids)
        h.check(
            calls == [ids["task_id"]]
            and provider.calls["model"] == 0
            and provider.calls["embed"] == 1,
            f"{kind}实际heartbeat续租false取消handler并停止后续昂贵步骤",
        )
        h.check(
            facts["task"]["state"] == "running"
            and facts.get("run", facts.get("document"))["status"] != "succeeded",
            f"{kind}失租heartbeat不提交成功事实",
        )
        h.check(
            any(
                row["action"] == "reject"
                and row["error_code"] == "LEASE_LOST"
                and row["task_id"] == ids["task_id"]
                for row in h.logs.rows
            ),
            f"{kind}续租拒绝有LEASE_LOST关联日志",
        )
        if kind == "run":
            await h.cancel(ids)
        else:
            async with h.factory() as session:
                await queue.schedule_retry(
                    session, ids["task_id"], worker.worker_id, 1, h.cfg, "CLEANUP", permanent=True
                )


async def commit_condition(h):
    for action in ("renew", "success", "retry"):
        ids = await h.seed()
        old = await h.claim("old")
        async with h.factory() as stale:
            # 旧连接先读取有效对象并保留identity map，然后新连接回收/接管。
            stale_object = await stale.get(TaskModel, old.task_id)
            h.check(
                stale_object.worker_id == "old" and stale_object.state == "leased",
                f"{action}旧连接已真实读到有效身份",
            )
            future = old.lease_expires_at + timedelta(milliseconds=1)
            with patch.object(queue, "utc_now", return_value=future):
                await h.reclaim()
                await h.claim("new")
                before = await h.facts(ids)
                if action == "renew":
                    accepted = await queue.renew_lease(stale, old.task_id, "old", 1, h.cfg)
                elif action == "retry":
                    accepted = await queue.schedule_retry(
                        stale, old.task_id, "old", 1, h.cfg, "OLD_ERROR"
                    )
                else:
                    accepted = await queue.mark_succeeded(stale, old.task_id, "old", 1)
                h.check(
                    not accepted and await h.facts(ids) == before,
                    f"{action}旧SELECT对象不能在新claim提交后覆盖新owner/generation/期限/错误",
                )
        await h.cancel(ids)


async def locked_write_boundaries(h):
    for action in ("renew", "success", "retry"):
        ids = await h.seed("index")
        old = await h.claim("old")
        async with h.factory() as session:
            await queue.mark_running(session, old.task_id, old.worker_id, old.generation)
        gate = h.gate()

        class SelectedSession(AsyncSession):
            async def execute(self, statement, *args, gate=gate, **kwargs):
                result = await super().execute(statement, *args, **kwargs)
                sql = str(statement)
                if not gate.entered.is_set() and "FROM tasks" in sql and "FOR UPDATE" in sql:
                    await gate.pause()
                return result

        factory = async_sessionmaker(h.engine, class_=SelectedSession, expire_on_commit=False)
        async with factory() as old_session:

            async def write(action=action, old=old, old_session=old_session):
                if action == "renew":
                    return await queue.renew_lease(old_session, old.task_id, "old", 1, h.cfg)
                if action == "success":
                    return await queue.mark_succeeded(old_session, old.task_id, "old", 1)
                return await queue.schedule_retry(old_session, old.task_id, "old", 1, h.cfg, "OLD")

            pending = h.launch(write())
            await gate.wait()

            async def expired(old=old):
                return queue.utc_now() > old.lease_expires_at

            await until(expired)
            h.check(
                await h.reclaim() == 0 and await h.claim("contender") is None,
                f"{action}旧条件SELECT持锁时真实回收/claim不能越锁接管",
            )
            gate.open()
            h.check(not await pending, f"{action}条件SELECT返回前跨lease后复查拒绝写回")
            await h.reclaim()
            current = await h.claim("new")
            before = await h.facts(ids)
            await old_session.commit()
            h.check(
                current.generation == 2 and await h.facts(ids) == before,
                f"{action}新claim已提交后旧commit不覆盖新代事实",
            )
        async with h.factory() as session:
            await queue.schedule_retry(
                session,
                current.task_id,
                "new",
                current.generation,
                h.cfg,
                "CLEANUP",
                permanent=True,
            )


async def action_logs(h):
    from backend.application.errors import ApplicationError

    sentinels = (
        "SYNTHETIC_SECRET_5A_79412",
        "SYNTHETIC_PROMPT_5A_92814",
        "/private/host/SYNTHETIC_PATH_5A",
    )

    class UnsafeMessageProvider(Provider):
        async def embed(self, value):
            self.calls["embed"] += 1
            raise ApplicationError(
                "TEST_PROVIDER_FAILURE", "|".join(sentinels), retryable=not self.permanent
            )

    for kind in ("run", "index"):
        # 不手工调用logger；每个动作由真实Runtime生命周期触发。
        ids = await h.seed(kind)
        gate = h.gate()
        worker = h.worker(Provider(stage="embed", gate=gate))
        pending = h.launch(worker.run_once())
        await gate.wait()
        await asyncio.sleep(1.2)
        gate.open()
        await pending
        failed = await h.seed(kind)
        await h.worker(UnsafeMessageProvider(failures=1, permanent=True)).run_once()
        retry_ids = await h.seed(kind)
        await h.worker(UnsafeMessageProvider(failures=1)).run_once()
        # 重试任务先永久结算，避免下一release场景领取它。
        facts = await h.facts(retry_ids)
        with patch.object(queue, "utc_now", return_value=facts["task"]["available_at"]):
            await h.reclaim()
            task = await h.claim()
            async with h.factory() as session:
                await queue.schedule_retry(
                    session,
                    task.task_id,
                    task.worker_id,
                    task.generation,
                    h.cfg,
                    "CLEANUP",
                    permanent=True,
                )
        released = await h.seed(kind)
        gate = h.gate()
        h.cfg.worker_shutdown_grace = 1
        worker = h.worker(Provider(stage="embed", gate=gate))
        pending = h.launch(worker.run_once())
        await gate.wait()
        worker.request_stop()
        await pending
        relevant = [
            row
            for row in h.logs.rows
            if row.get("task_id")
            in {ids["task_id"], failed["task_id"], retry_ids["task_id"], released["task_id"]}
        ]
        identities = {value["task_id"]: value for value in (ids, failed, retry_ids, released)}
        expected_errors = {
            "claim": None,
            "renew": None,
            "success": None,
            "release": "WORKER_STOPPED",
            "retry": "TEST_PROVIDER_FAILURE",
            "failure": "TEST_PROVIDER_FAILURE",
        }
        # Python原始logger文本断言先于Context.evidence脱敏，失败不输出secret本身。
        raw = "\n".join(h.logs.raw)
        h.check(
            all(sentinel not in raw for sentinel in sentinels),
            f"{kind}原始日志在Context脱敏前没有合成secret/prompt/宿主路径哨兵",
        )
        h.trace.setdefault("log_safety", []).append(
            {"kind": kind, "checked_before_redaction": True, "sentinels_absent": True}
        )
        for action in ("claim", "renew", "release", "retry", "success", "failure"):
            rows = [row for row in relevant if row["action"] == action]
            h.check(bool(rows), f"{kind}真实触发{action}动作日志")
            h.check(
                all(
                    row["task_id"]
                    and row["worker_id"]
                    and row["generation"] >= 1
                    and row["attempt"] >= 1
                    and row.get("run_id") == identities[row["task_id"]].get("run_id")
                    and (
                        kind != "index"
                        or row.get("document_id") == identities[row["task_id"]]["document_id"]
                    )
                    and row.get("error_code") == expected_errors[action]
                    for row in rows
                ),
                f"{kind}/{action}关联task/worker/generation/attempt及精确Run或Document身份和安全error_code一致",
            )
        if kind == "run":
            await h.cancel(released)
        else:
            facts = await h.facts(released)
            with patch.object(queue, "utc_now", return_value=facts["task"]["available_at"]):
                await h.reclaim()
                task = await h.claim()
                async with h.factory() as session:
                    await queue.schedule_retry(
                        session,
                        task.task_id,
                        task.worker_id,
                        task.generation,
                        h.cfg,
                        "CLEANUP",
                        permanent=True,
                    )


async def database_recovery(h):
    # 精确终止本测试session的PG backend，真实TCP断开命中reclaim查询；不停止共享PG。
    killed = []

    class FaultSession(AsyncSession):
        async def execute(self, statement, *args, **kwargs):
            if len(killed) < 3 and "tasks" in str(statement) and not self.info.get("terminated"):
                self.info["terminated"] = True
                connection = await self.connection()
                pid = (await connection.execute(text("SELECT pg_backend_pid()"))).scalar()
                async with h.factory() as killer:
                    accepted = await killer.scalar(
                        text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
                    )
                killed.append({"pid": pid, "terminated": accepted})
            return await super().execute(statement, *args, **kwargs)

    factory = async_sessionmaker(h.engine, class_=FaultSession, expire_on_commit=False)
    worker = h.worker(Provider())
    worker.session_factory = factory
    pending = h.launch(worker.run_forever())

    async def failed_three():
        rows = [r for r in h.logs.rows if r.get("error_code") == "DATABASE_UNAVAILABLE"]
        return rows if len(rows) >= 3 else None

    rows = await until(failed_three)
    h.check(
        len(killed) == 3 and all(r["terminated"] for r in killed),
        "三次精确PG连接故障真实命中且有安全DATABASE_UNAVAILABLE日志",
    )
    gaps = [rows[i + 1]["observed_at"] - rows[i]["observed_at"] for i in range(2)]
    h.check(gaps[0] >= 0.08 and gaps[1] >= 0.18, "故障日志间隔证明指数退避而非热循环")
    ids = await h.seed()

    async def succeeded():
        return (await h.facts(ids))["run"]["status"] == "succeeded"

    await until(succeeded)
    h.check(
        not pending.done() and worker.worker_id == (await h.facts(ids))["task"]["worker_id"],
        "故障恢复后同一Runtime同进程无需重启执行新Task",
    )
    worker.request_stop()
    await pending
    h.trace.update(killed_connections=killed, backoff_seconds=gaps, worker_id=worker.worker_id)


async def readiness(h):
    import httpx

    from backend.app import create_app

    h.cfg.redis_enabled = True
    h.cfg.redis_url = "redis://redis:6379/14"
    ids = await h.seed()
    gate = h.gate()
    worker = h.worker(Provider(stage="embed", gate=gate))
    await worker.notifier.connect()
    app = create_app(h.cfg)
    await app.state.notifier.connect()
    pending = h.launch(worker.run_forever())
    try:
        await gate.wait()
        samples = []
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(7):
                await asyncio.sleep(1)
                response = await client.get("/health/ready")
                body = response.json()
                ttl = await worker.notifier.client.ttl("sesrag:worker:ready:" + worker.worker_id)
                facts = await h.facts(ids)
                h.check(
                    body["worker_count"] == 1 and body["worker"] == "ready" and ttl > 0,
                    "跨readiness TTL真实Redis键和正式ready保持一个活跃Worker",
                )
                h.check(
                    facts["task"]["lease_expires_at"] > queue.utc_now(),
                    "readiness采样同时独立验证Task lease仍有效",
                )
                samples.append(
                    {
                        "ready": body,
                        "readiness_ttl": ttl,
                        "lease": facts["task"]["lease_expires_at"],
                    }
                )
        gate.open()

        async def done():
            return (await h.facts(ids))["run"]["status"] == "succeeded"

        await until(done)
        h.check(True, "超过readiness TTL的慢任务仍原身份完成")
        h.trace["samples"] = samples
    finally:
        gate.open()
        worker.request_stop()
        await pending
        await worker.notifier.client.delete("sesrag:worker:ready:" + worker.worker_id)
        await worker.notifier.close()
        await app.state.notifier.close()
        await app.state.engine.dispose()
