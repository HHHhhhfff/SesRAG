"""真实PG末次flush后的时间屏障；不写入伪造的业务状态。"""

import time
from datetime import timedelta

from pg_harness import Provider
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from backend.application.task_execution import ExecutionStopped, append_execution_event
from backend.config import Settings
from backend.db.models import (
    DocumentModel,
    MessageModel,
    RunEventModel,
    RunModel,
    TaskModel,
    ThreadModel,
)
from backend.infrastructure.queue import postgres_queue as queue
from backend.workers.handlers.index_handler import process_index_task
from backend.workers.handlers.run_handler import process_run_task


async def full_facts(h, ids):
    """独立连接读取整行，包含错误、进度和两个游标，不只比较终态。"""
    scopes = [(TaskModel, TaskModel.task_id == ids["task_id"])]
    if "run_id" in ids:
        scopes += [
            (RunModel, RunModel.run_id == ids["run_id"]),
            (ThreadModel, ThreadModel.thread_id == ids["thread_id"]),
            (MessageModel, MessageModel.thread_id == ids["thread_id"]),
            (RunEventModel, RunEventModel.run_id == ids["run_id"]),
        ]
    else:
        scopes += [(DocumentModel, DocumentModel.document_id == ids["document_id"])]
    async with h.factory() as session:
        return {
            model.__tablename__: sorted(
                [
                    {c.name: getattr(row, c.name) for c in model.__table__.columns}
                    for row in await session.scalars(select(model).where(condition))
                ],
                key=str,
            )
            for model, condition in scopes
        }


async def flush_boundaries(h, group):
    actions = {
        "queue": ["claim", "renew", "running", "succeeded"],
        "failure": ["permanent", "retry", "release", "index-permanent", "index-retry"],
        "events": ["started", "retrieval", "delta", "indexing"],
    }[group]
    failures = []
    for action in actions:
        for expiry in ("lease", "deadline"):
            cfg = Settings(
                _env_file=None,
                **{
                    **h.cfg.model_dump(),
                    "task_lease_ttl": 2 if expiry == "lease" else 10,
                    "task_heartbeat_interval": 1,
                    "task_deadline": 60 if expiry == "lease" else 2,
                },
            )
            kind = (
                "index"
                if action in ("succeeded", "indexing", "index-permanent", "index-retry")
                else "run"
            )
            ids = await h.seed(kind, cfg)
            task = None
            if action != "claim":
                async with h.factory() as session:
                    task = await queue.claim_next_task(session, "flush-worker", cfg)
                    if action == "succeeded":
                        assert await queue.mark_running(
                            session, task.task_id, task.worker_id, task.generation
                        )
            before = await full_facts(h, ids)
            hits = []

            class FlushSession(Session):
                pass

            @event.listens_for(FlushSession, "after_flush_postexec")
            def after_flush(
                session, context, hits=hits, ids=ids, action=action, task=task, expiry=expiry
            ):
                if hits:
                    return
                current = next(
                    (
                        x
                        for x in session.identity_map.values()
                        if isinstance(x, TaskModel) and x.task_id == ids["task_id"]
                    ),
                    None,
                )
                if current is None:
                    return
                # 钩子位于真实数据库flush之后，也覆盖commit隐式flush；仅本测试Session。
                original = current if action == "claim" else task
                boundary = original.lease_expires_at if expiry == "lease" else original.deadline_at
                hits.append(
                    {
                        "action": action,
                        "expiry": expiry,
                        "boundary": boundary,
                        "flush_completed_at": queue.utc_now(),
                    }
                )
                limit = time.monotonic() + 4
                while queue.utc_now() <= boundary:
                    if time.monotonic() >= limit:
                        raise TimeoutError("末flush自然到期屏障超过4秒")
                    time.sleep(0.01)
                hits[-1]["released_at"] = queue.utc_now()

            factory = async_sessionmaker(
                h.engine, sync_session_class=FlushSession, expire_on_commit=False, autoflush=False
            )
            accepted = False
            try:
                async with factory() as session:
                    args = (session, ids["task_id"], "flush-worker", 1)
                    if action == "claim":
                        accepted = (
                            await queue.claim_next_task(session, "flush-worker", cfg) is not None
                        )
                    elif action == "renew":
                        accepted = await queue.renew_lease(*args, cfg)
                    elif action == "running":
                        accepted = await queue.mark_running(*args)
                    elif action == "succeeded":
                        accepted = await queue.mark_succeeded(*args)
                    elif action == "release":
                        accepted = await queue.release_task(*args, cfg)
                    elif action in ("permanent", "retry", "index-permanent", "index-retry"):
                        accepted = await queue.schedule_retry(
                            *args, cfg, "TEST_FLUSH", permanent="permanent" in action
                        )
                    elif action in ("retrieval", "delta"):
                        await append_execution_event(
                            *args,
                            "answer.delta" if action == "delta" else "retrieval.completed",
                            {"text": "late"} if action == "delta" else {"count": 0, "items": []},
                        )
                        await session.commit()
                        accepted = True
                if action in ("started", "indexing"):
                    worker = h.worker(Provider())
                    if action == "started":
                        await process_run_task(
                            factory,
                            cfg,
                            ids["task_id"],
                            "flush-worker",
                            1,
                            provider_factory=worker.provider_factory,
                            vector_store_factory=worker.vector_store_factory,
                        )
                    else:
                        await process_index_task(
                            factory,
                            cfg,
                            ids["task_id"],
                            "flush-worker",
                            1,
                            worker.embedding_provider,
                            worker.parser,
                            worker.vector_store_factory,
                        )
                    accepted = True
            except ExecutionStopped:
                pass
            finally:
                event.remove(FlushSession, "after_flush_postexec", after_flush)
            after = await full_facts(h, ids)
            passed = bool(hits) and not accepted and before == after
            h.trace.setdefault("flush_boundaries", []).append(
                {
                    "action": action,
                    "expiry": expiry,
                    "barrier": hits,
                    "accepted": accepted,
                    "unchanged": before == after,
                    "before": before,
                    "after": after,
                }
            )
            if passed:
                h.check(True, f"{action}/{expiry}末flush过期整体回滚，所有事实及双游标不变")
            else:
                failures.append(f"{action}/{expiry}")
            # 正式调度结算到期仍合法；不以SQL改state清理前一轮。
            from unittest.mock import patch

            boundary = before["tasks"][0]["deadline_at"] + timedelta(seconds=1)
            with patch.object(queue, "utc_now", return_value=boundary):
                async with h.factory() as session:
                    await queue.requeue_expired(session)
            final = await h.facts(ids)
            h.check(
                final["task"]["state"] in ("failed", "succeeded"),
                f"{action}/{expiry}scheduler在过期后仍可合法结算",
            )
    assert not failures, f"末flush未拒绝或回滚不完整: {failures}"
