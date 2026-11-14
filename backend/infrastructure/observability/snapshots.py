"""API专用只读快照，不占业务池、不因抓取增加查询次数。"""

import asyncio
import time
from contextlib import suppress
from datetime import timezone

from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.models import DocumentModel as D
from backend.db.models import RunModel as R
from backend.db.models import TaskModel as T
from backend.db.rag_models import IndexBuildModel as B
from backend.db.rag_models import RetrievalExecutionModel as E
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.observability.metrics import CATALOG

KINDS = ("run", "index_document", "index_build", "retrieval_diagnostic")
GROUPS = tuple(
    dict.fromkeys(
        t[1]
        for item in CATALOG
        if item["logical_id"] == "QUEUE_GROUPS"
        for t in item["allowed_tuples"]
    )
)


async def read_queue(connection, observed_at=None):
    # PostgreSQL事务内共用一个DB侧now；测试可注入固定时间验证边界。
    now = observed_at if observed_at is not None else await connection.scalar(select(func.now()))
    new_kind = T.kind.in_(["index_build", "retrieval_diagnostic"])
    active = T.state.in_(["leased", "running"])
    cancelled = or_(
        T.cancel_requested_at.is_not(None),
        and_(T.kind == "run", R.cancel_requested_at.is_not(None)),
        and_(T.kind == "index_build", B.cancel_requested_at.is_not(None)),
        and_(T.kind == "retrieval_diagnostic", E.cancel_requested_at.is_not(None)),
    )
    target_valid = or_(
        and_(
            T.kind == "run",
            R.run_id.is_not(None),
            R.status.in_(["queued", "running", "retry_waiting", "cancelling"]),
        ),
        and_(
            T.kind == "index_document", D.document_id.is_not(None), D.extension.in_([".txt", ".md"])
        ),
        and_(
            T.kind == "index_build",
            B.index_batch_id.is_not(None),
            B.state.in_(["queued", "building", "waiting"]),
        ),
        and_(
            T.kind == "retrieval_diagnostic",
            E.execution_id.is_not(None),
            E.state.in_(["queued", "running"]),
        ),
    )
    budget_valid = or_(
        active,
        and_(new_kind, T.failure_count < T.max_attempts),
        and_(~new_kind, T.attempt < T.max_attempts),
    )
    group = case(
        (cancelled, "cancel_pending"),
        (
            or_(
                T.deadline_at <= now,
                and_(active, or_(T.lease_expires_at.is_(None), T.lease_expires_at <= now)),
            ),
            "expired",
        ),
        (
            or_(
                ~target_valid,
                ~budget_valid,
                ~T.state.in_(["queued", "retry_waiting", "waiting_external", "leased", "running"]),
            ),
            "invalid",
        ),
        (and_(T.state == "queued", T.available_at <= now), "queued_ready"),
        (T.state == "queued", "queued_future"),
        (and_(T.state == "retry_waiting", T.available_at <= now), "retry_due"),
        (T.state == "retry_waiting", "retry_backoff"),
        (and_(T.state == "waiting_external", T.available_at <= now), "external_due"),
        (T.state == "waiting_external", "external_wait"),
        (T.state == "leased", "leased"),
        (T.state == "running", "running"),
        else_="invalid",
    ).label("task_group")
    query = (
        select(T.kind, group, func.count(), func.min(T.available_at))
        .outerjoin(R, R.run_id == T.run_id)
        .outerjoin(D, D.document_id == T.document_id)
        .outerjoin(B, B.index_batch_id == T.index_batch_id)
        .outerjoin(E, E.execution_id == T.retrieval_execution_id)
        .where(~T.state.in_(["succeeded", "failed", "cancelled"]))
        .group_by(T.kind, group)
    )
    values = {k: (0, 0.0) for k in KINDS}
    groups = {(k, g): 0 for k in KINDS for g in GROUPS}
    for kind, category, count, available in (await connection.execute(query)).all():
        if kind not in KINDS or category not in GROUPS:
            continue
        groups[kind, category] = count
        if category == "queued_ready":
            age = (
                now.replace(tzinfo=timezone.utc) - available.replace(tzinfo=timezone.utc)
            ).total_seconds()
            values[kind] = count, max(0, age)
    return values, groups


class SnapshotPoller:
    def __init__(self, settings, metrics, event):
        kwargs = (
            dict(pool_size=1, max_overflow=0, pool_timeout=0.2)
            if not settings.database_url.startswith("sqlite")
            else {}
        )
        self.engine = create_async_engine(settings.database_url, **kwargs)
        self.notifier = RedisNotifier(settings.model_copy(update={"health_probe_timeout": 0.5}))
        self.metrics, self.event = metrics, event
        self.task = None
        self.refreshes = 0

    def start(self):
        self.task = asyncio.create_task(self._loop(), name="observation-snapshots")

    async def _database(self, queue):
        async with asyncio.timeout(1):
            async with self.engine.connect() as connection, connection.begin():
                if connection.dialect.name == "postgresql":
                    await connection.execute(text("SET TRANSACTION READ ONLY"))
                    await connection.execute(text("SET LOCAL statement_timeout='500ms'"))
                    await connection.execute(text("SET LOCAL lock_timeout='100ms'"))
                return (
                    await read_queue(connection)
                    if queue
                    else await connection.scalar(text("SELECT 1"))
                )

    async def refresh(self, source):
        started, result = time.monotonic(), "ok"
        try:
            if source == "queue":
                values, groups = await self._database(True)
                for (kind, group), value in groups.items():
                    self.metrics.set("QUEUE_GROUPS", kind, group, value=value)
                self.metrics.queue_snapshot(values)
            elif source == "postgres":
                await self._database(False)
                self.metrics.set("DEPENDENCY_READY", "postgres", value=1)
            elif source == "redis":
                if not await self.notifier.probe():
                    raise ConnectionError()
                self.metrics.set("DEPENDENCY_READY", "redis", value=1)
            else:
                count = await self.notifier.ready_worker_count()
                if count is None:
                    raise ConnectionError()
                self.metrics.set("READY_WORKERS", value=count)
                self.metrics.set("WORKER_READY", value=int(count > 0))
            self.metrics.snapshot_success(source)
        except Exception as exc:
            result = "timeout" if isinstance(exc, TimeoutError) else "error"
            self.metrics.snapshot_failure(source)
            self.event("snapshot", "source_error")
        finally:
            self.metrics.inc("SNAPSHOT_REFRESH", source, result)
            self.metrics.observe("SNAPSHOT_DURATION", source, seconds=time.monotonic() - started)

    async def _loop(self):
        while True:
            self.refreshes += 1
            started = time.monotonic()
            for source in ("queue", "postgres", "redis", "worker_presence"):
                await self.refresh(source)
            self.metrics.expire_snapshots()
            await asyncio.sleep(max(0, 5 - (time.monotonic() - started)))

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.notifier.close()
        await self.engine.dispose()
