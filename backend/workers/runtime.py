import asyncio
import json
import logging
import os
import signal
from contextlib import suppress
from functools import partial
from time import monotonic
from uuid import uuid4

from backend.application.errors import ApplicationError
from backend.application.task_execution import ExecutionStopped
from backend.config import Settings
from backend.domain.ports import (
    EmbeddingPort,
    ModelProvider,
    ParserPort,
    QueuePort,
    VectorStorePort,
)
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.factory import providers_for_snapshot
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from backend.infrastructure.queue.adapter import PostgresQueue
from backend.infrastructure.queue.postgres_queue import acknowledge_cancellation
from backend.infrastructure.rag.parsers import SubprocessParser
from backend.infrastructure.rag.pgvector_store import PgVectorStore
from backend.workers.handlers.index_build_handler import process_index_build_task
from backend.workers.handlers.index_handler import process_index_task
from backend.workers.handlers.retrieval_diagnostic_handler import process_diagnostic_task
from backend.workers.handlers.run_handler import process_run_task

logger = logging.getLogger(__name__)

# 独立于业务 deadline 的控制面预算，覆盖连接、锁等待和事务清理。
DB_PHASE_TIMEOUT = 5.0
CANCEL_DRAIN_TIMEOUT = 0.5
RELEASE_TIMEOUT = 1.0


class WorkerRuntime:
    """进程 readiness 与任务租约独立；关闭窗口内继续续租。"""

    def __init__(
        self,
        settings: Settings,
        session_factory,
        notifier: RedisNotifier,
        *,
        queue_factory=None,
        parser: ParserPort | None = None,
        vector_store_factory=None,
        provider_factory=None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.notifier = notifier
        self.worker_id = os.getenv("WORKER_ID") or f"worker-{uuid4()}"
        self.stop_event = asyncio.Event()
        self._log_context: dict[str, str | None] = {}
        self.embedding_provider: EmbeddingPort | None = None
        self.model_provider: ModelProvider | None = None
        self.queue_factory = queue_factory or (lambda session: PostgresQueue(session, settings))
        self.parser = parser or SubprocessParser(settings.upload_path)
        self.vector_store_factory = vector_store_factory or PgVectorStore
        self.provider_factory = provider_factory or partial(
            providers_for_snapshot, api_key=settings.model_api_key
        )

    def queue(self, session) -> QueuePort:
        return self.queue_factory(session)

    def vector_store(self, session) -> VectorStorePort:
        return self.vector_store_factory(session)

    def log(self, action, task=None, error_code=None, *, stage=None, duration_ms=0):
        context = self._log_context if task is not None else {}
        # 日志处理器异常不能中断领取、续租或事实提交。
        with suppress(Exception):
            self._write_log(action, task, error_code, context, stage, duration_ms)

    def _write_log(self, action, task, error_code, context, stage, duration_ms):
        logger.info(
            json.dumps(
                {
                    "action": action,
                    "message": "task claimed" if action == "claim" else f"task {action}",
                    "task_id": getattr(task, "task_id", None),
                    "run_id": getattr(task, "run_id", None),
                    "document_id": context.get("document_id", getattr(task, "document_id", None)),
                    "parse_job_id": context.get("parse_job_id"),
                    "index_batch_id": getattr(task, "index_batch_id", None),
                    "retrieval_execution_id": context.get(
                        "retrieval_execution_id", getattr(task, "retrieval_execution_id", None)
                    ),
                    "worker_id": self.worker_id,
                    "generation": getattr(task, "generation", None),
                    "attempt": getattr(task, "attempt", None),
                    "error_code": error_code,
                    "stage": stage or action,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=False,
            )
        )

    async def _load_log_context(self, task):
        self._log_context = {}

        async def load(session):
            from sqlalchemy import select

            from backend.db.rag_models import IndexBuildModel, RetrievalExecutionModel

            context = {}
            if task.kind == "index_build":
                build = await session.get(IndexBuildModel, task.index_batch_id)
                if build is not None:
                    context.update(
                        document_id=build.document_id,
                        parse_job_id=build.parse_job_id,
                        stage=build.stage,
                    )
            elif task.kind == "run":
                execution_id = await session.scalar(
                    select(RetrievalExecutionModel.execution_id).where(
                        RetrievalExecutionModel.task_id == task.task_id,
                        RetrievalExecutionModel.generation == task.generation,
                    )
                )
                context["retrieval_execution_id"] = execution_id
            return context

        try:
            self._log_context = await self._database(load)
        except Exception:
            # 旧任务与替代 Queue/Session 不必实现观测专用查询。
            pass

    async def _observed_dispatch(self, task):
        from backend.application.stage_observation import observer

        stage = self._log_context.get("stage", task.kind)

        async def record(stage, duration, code):
            current = asyncio.current_task()
            # 退出后的观测只用已有身份，避免取消清理再次派生数据库任务。
            if not self.stop_event.is_set() and not (current and current.cancelling()):
                await self._load_log_context(task)
            self.log("stage", task, code, stage=stage, duration_ms=duration)

        token = observer.set(record)
        started = monotonic()
        code = None
        try:
            await self._dispatch(task)
        except BaseException as exc:
            code = getattr(exc, "code", "STAGE_FAILED")
            raise
        finally:
            observer.reset(token)
            elapsed = max(0, (monotonic() - started) * 1000)
            with suppress(Exception):
                await record(stage, elapsed, code)

    def request_stop(self) -> None:
        self.stop_event.set()

    async def _cancel_tasks(self, *tasks):
        pending = {task for task in tasks if task is not None and not task.done()}
        for task in pending:
            task.cancel()
        if pending:
            _, pending = await asyncio.wait(pending, timeout=CANCEL_DRAIN_TIMEOUT)
        for task in tasks:
            if task is None:
                continue
            if task.done():
                if not task.cancelled():
                    task.exception()
            else:
                # 不让拒绝取消的适配器无限阻塞退出；停止续租后交给租约回收。
                task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        return not pending

    async def _bounded(self, operation, *, timeout=DB_PHASE_TIMEOUT, stop_sensitive=False):
        pending = asyncio.create_task(operation)
        stop = asyncio.create_task(self.stop_event.wait()) if stop_sensitive else None
        watchers = {pending, stop} if stop is not None else {pending}
        try:
            done, _ = await asyncio.wait(
                watchers, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if pending in done:
                return pending.result()
            if stop is not None and stop in done:
                raise ExecutionStopped()
            raise TimeoutError()
        finally:
            await self._cancel_tasks(pending, stop)

    async def _database(self, operation, *, timeout=DB_PHASE_TIMEOUT, stop_sensitive=False):
        if stop_sensitive and self.stop_event.is_set():
            raise ExecutionStopped()

        async def transaction():
            async with self.session_factory() as session:
                return await operation(session)

        return await self._bounded(transaction(), timeout=timeout, stop_sensitive=stop_sensitive)

    async def _release(self, task):
        try:
            released = await self._database(
                lambda session: self.queue(session).release(task),
                timeout=RELEASE_TIMEOUT,
            )
        except Exception:
            self.log("reject", task, "RELEASE_TIMEOUT_OR_UNAVAILABLE")
            return
        self.log(
            "release" if released else "reject",
            task,
            "WORKER_STOPPED" if released else "LEASE_LOST",
        )

    async def heartbeat(self) -> None:
        try:
            if not await self.notifier.probe():
                return
            async with asyncio.timeout(self.settings.health_probe_timeout):
                await self.notifier.client.set(
                    f"sesrag:worker:ready:{self.worker_id}",
                    "1",
                    ex=max(5, self.settings.task_lease_ttl),
                )
        except Exception:
            return

    async def _readiness_loop(self):
        while not self.stop_event.is_set():
            await self.heartbeat()
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), self.settings.task_heartbeat_interval
                )
            except TimeoutError:
                pass

    async def _dispatch(self, task):
        if task.kind == "run":
            await process_run_task(
                self.session_factory,
                self.settings,
                task.task_id,
                self.worker_id,
                task.generation,
                self.embedding_provider,
                self.model_provider,
                provider_factory=self.provider_factory,
                vector_store_factory=self.vector_store,
            )
        elif task.kind == "index_document":
            provider = self.embedding_provider
            if provider is None:
                if self.settings.mock_provider:
                    provider = MockEmbeddingProvider(self.settings.vector_dimension)
                else:
                    provider = OpenAICompatibleProvider(
                        self.settings.model_base_url or "",
                        self.settings.model_api_key or "",
                        self.settings.model_name or "",
                        self.settings.embedding_model_name or "",
                    )
            await process_index_task(
                self.session_factory,
                self.settings,
                task.task_id,
                self.worker_id,
                task.generation,
                provider,
                self.parser,
                self.vector_store,
            )
        elif task.kind == "index_build":
            await process_index_build_task(
                self.session_factory, self.settings, task.task_id, self.worker_id, task.generation
            )
        elif task.kind == "retrieval_diagnostic":
            await process_diagnostic_task(
                self.session_factory, self.settings, task.task_id, self.worker_id, task.generation
            )
        else:
            raise ApplicationError("UNKNOWN_TASK_KIND", "不支持的任务类型")

    async def run_once(self) -> bool:
        if self.stop_event.is_set():
            return False
        try:
            recovered = await self._database(
                lambda session: self.queue(session).reclaim(), stop_sensitive=True
            )
            if recovered:
                self.log("reclaim")
            if self.stop_event.is_set():
                return False
            task = await self._database(
                lambda session: self.queue(session).claim(self.worker_id),
                stop_sensitive=True,
            )
        except ExecutionStopped:
            return False
        if task is None:
            return False
        await self._load_log_context(task)
        self.log("claim", task)
        try:
            if self.stop_event.is_set():
                await self._release(task)
                return True
            running = await self._database(
                lambda session: self.queue(session).start(task),
                stop_sensitive=True,
            )
            if not running:
                await self._ack_cancel(task)
                self.log("reject", task, "LEASE_LOST")
                return True
        except ExecutionStopped:
            await self._release(task)
            return True
        execution = asyncio.create_task(self._observed_dispatch(task))
        lease = asyncio.create_task(self._lease_heartbeat(task, execution))
        stop = asyncio.create_task(self.stop_event.wait())
        try:
            done, _ = await asyncio.wait({execution, stop}, return_when=asyncio.FIRST_COMPLETED)
            if stop in done and not execution.done():
                done, _ = await asyncio.wait(
                    {execution}, timeout=self.settings.worker_shutdown_grace
                )
                if not done:
                    await self._cancel_tasks(lease, execution)
                    await self._release(task)
                    return True
            await execution
            self.log("success", task)
        except (ExecutionStopped, asyncio.CancelledError):
            await self._ack_cancel(task)
            self.log("reject", task, "EXECUTION_STOPPED")
        except Exception as exc:
            code = (
                exc.code
                if isinstance(exc, ApplicationError)
                else "RUN_FAILED"
                if task.kind == "run"
                else "INDEX_FAILED"
            )
            permanent = isinstance(exc, ApplicationError) and not exc.retryable

            async def record_failure(session):
                return await self.queue(session).fail(task, code, permanent=permanent)

            try:
                action = await self._database(record_failure, stop_sensitive=True)
                self.log(action, task, code)
            except ExecutionStopped:
                self.log("reject", task, "WORKER_STOPPED")
        finally:
            await self._cancel_tasks(lease, stop, execution)
        return True

    async def _ack_cancel(self, task):
        if task.kind in {"index_build", "retrieval_diagnostic"}:

            async def acknowledge_rag(session):
                from backend.application.rag_task_execution import settle_rag_task
                from backend.infrastructure.queue.postgres_queue import lock_owned_task

                current = await lock_owned_task(
                    session, task.task_id, task.worker_id, task.generation
                )
                if current is not None and current.cancel_requested_at:
                    lease, deadline = current.lease_expires_at, current.deadline_at
                    await settle_rag_task(session, current, "TASK_CANCELLED", cancelled=True)
                    from backend.infrastructure.queue.postgres_queue import commit_authorized

                    await commit_authorized(session, lease, deadline)

            await self._database(acknowledge_rag)
            return
        if task.kind != "run":
            return
        try:
            await self._database(
                lambda session: acknowledge_cancellation(
                    session, task.task_id, task.worker_id, task.generation
                )
            )
        except Exception:
            self.log("reject", task, "CANCEL_ACK_UNAVAILABLE")

    async def _lease_heartbeat(self, task, execution):
        while True:
            await asyncio.sleep(self.settings.task_heartbeat_interval)
            try:
                renewed = await self._database(lambda session: self.queue(session).renew(task))
                if renewed:
                    self.log("renew", task)
                    continue
                self.log("reject", task, "LEASE_LOST")
            except Exception:
                self.log("reject", task, "LEASE_CHECK_FAILED")
            execution.cancel()
            return

    async def run_forever(self) -> None:
        readiness = asyncio.create_task(self._readiness_loop())
        failures = 0
        try:
            while not self.stop_event.is_set():
                delay = self.settings.queue_poll_interval
                try:
                    did_work = await self.run_once()
                    failures = 0
                    if did_work:
                        continue
                except Exception:
                    failures += 1
                    delay = min(30, self.settings.queue_poll_interval * 2 ** min(failures, 5))
                    self.log("failure", error_code="DATABASE_UNAVAILABLE")
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.stop_event.wait(), delay)
        finally:
            await self._cancel_tasks(readiness)


def install_signal_handlers(runtime: WorkerRuntime) -> None:
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, runtime.request_stop)
        except (NotImplementedError, RuntimeError):
            # Windows 使用同步信号桥接到同一停止标记。
            with suppress(ValueError):
                signal.signal(
                    signal_name, lambda *_: loop.call_soon_threadsafe(runtime.request_stop)
                )
