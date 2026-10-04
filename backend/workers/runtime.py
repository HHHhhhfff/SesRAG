import asyncio
import logging
import os
import signal
from contextlib import suppress
from typing import Any

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import RunModel, TaskModel
from backend.domain.enums import RunState, TaskKind, TaskState
from backend.infrastructure.events.journal import append_event
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider
from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from backend.infrastructure.queue.postgres_queue import (
    claim_next_task,
    mark_running,
    renew_lease,
    requeue_expired,
)
from backend.workers.handlers.index_handler import process_index_task
from backend.workers.handlers.run_handler import process_run_task

logger = logging.getLogger(__name__)


class WorkerRuntime:
    """负责领取 Task、维持进程生命周期并分发两类 Demo handler。"""

    def __init__(self, settings: Settings, session_factory, notifier: RedisNotifier) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.notifier = notifier
        self.worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}")
        self.stop_event = asyncio.Event()
        self.embedding_provider: Any
        self.model_provider: Any
        if settings.mock_provider:
            self.embedding_provider = MockEmbeddingProvider(settings.vector_dimension)
            self.model_provider = MockModelProvider()
        else:
            if not all(
                [
                    settings.model_base_url,
                    settings.model_api_key,
                    settings.model_name,
                    settings.embedding_model_name,
                ]
            ):
                raise ValueError(
                    "真实 Provider 需要配置 MODEL_BASE_URL、MODEL_API_KEY、"
                    "MODEL_NAME 和 EMBEDDING_MODEL_NAME"
                )
            base_url = settings.model_base_url
            api_key = settings.model_api_key
            model_name = settings.model_name
            embedding_model_name = settings.embedding_model_name
            assert base_url and api_key and model_name and embedding_model_name
            provider = OpenAICompatibleProvider(base_url, api_key, model_name, embedding_model_name)
            self.embedding_provider = provider
            self.model_provider = provider

    def request_stop(self) -> None:
        self.stop_event.set()

    async def heartbeat(self) -> None:
        if self.notifier.client is None:
            return
        try:
            await self.notifier.client.set(
                f"sesrag:worker:ready:{self.worker_id}",
                "1",
                ex=max(5, self.settings.task_lease_ttl),
            )
        except Exception:
            return

    async def run_once(self) -> bool:
        async with self.session_factory() as session:
            await requeue_expired(session)
            task = await claim_next_task(session, self.worker_id, self.settings)
        if task is None:
            return False
        async with self.session_factory() as session:
            if not await mark_running(session, task.task_id, self.worker_id, task.generation):
                return True
        logger.info(
            "task claimed",
            extra={
                "task_id": task.task_id,
                "worker_id": self.worker_id,
                "generation": task.generation,
            },
        )
        heartbeat_task = asyncio.create_task(self._lease_heartbeat(task.task_id, task.generation))
        try:
            if task.kind == TaskKind.RUN.value:
                await process_run_task(
                    self.session_factory,
                    self.settings,
                    task.task_id,
                    self.worker_id,
                    task.generation,
                    self.embedding_provider,
                    self.model_provider,
                )
            elif task.kind == TaskKind.INDEX_DOCUMENT.value:
                await process_index_task(
                    self.session_factory,
                    self.settings,
                    task.task_id,
                    self.worker_id,
                    task.generation,
                    self.embedding_provider.embed,
                )
            else:
                raise ApplicationError("UNKNOWN_TASK_KIND", f"不支持的 Task 类型: {task.kind}")
        except Exception as exc:
            await self._record_run_failure(task.task_id, task.kind, str(exc))
            logger.exception(
                "task failed",
                extra={
                    "task_id": task.task_id,
                    "worker_id": self.worker_id,
                    "generation": task.generation,
                },
            )
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        return True

    async def _lease_heartbeat(self, task_id: str, generation: int) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.sleep(self.settings.task_heartbeat_interval)
                async with self.session_factory() as session:
                    renewed = await renew_lease(
                        session,
                        task_id,
                        self.worker_id,
                        generation,
                        self.settings,
                    )
                if not renewed:
                    logger.warning(
                        "task lease lost",
                        extra={
                            "task_id": task_id,
                            "worker_id": self.worker_id,
                            "generation": generation,
                        },
                    )
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("task heartbeat failed", extra={"task_id": task_id})

    async def _record_run_failure(self, task_id: str, task_kind: str, error: str) -> None:
        if task_kind != TaskKind.RUN.value:
            return
        async with self.session_factory() as session:
            task = await session.get(TaskModel, task_id)
            if task is None or task.run_id is None:
                return
            run = await session.get(RunModel, task.run_id)
            if run is None or run.status in {RunState.SUCCEEDED.value, RunState.CANCELLED.value}:
                return
            if task.state == TaskState.RETRY_WAITING.value:
                run.status = RunState.RETRY_WAITING.value
                await append_event(
                    session,
                    run.run_id,
                    "task.retry_scheduled",
                    {"error": error[:300], "attempt": task.attempt},
                )
            else:
                run.status = RunState.FAILED.value
                run.last_error_code = task.last_error_code or "RUN_FAILED"
                await append_event(
                    session,
                    run.run_id,
                    "run.failed",
                    {"error_code": run.last_error_code, "message": error[:300]},
                )
            await session.commit()

    async def run_forever(self) -> None:
        while not self.stop_event.is_set():
            await self.heartbeat()
            did_work = await self.run_once()
            if not did_work:
                try:
                    await asyncio.wait_for(
                        self.stop_event.wait(), timeout=self.settings.queue_poll_interval
                    )
                except asyncio.TimeoutError:
                    continue
        logger.info("worker stop requested; no new task will be claimed")
        await asyncio.sleep(min(self.settings.worker_shutdown_grace, 1))


def install_signal_handlers(runtime: WorkerRuntime) -> None:
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, runtime.request_stop)
        except (NotImplementedError, RuntimeError):
            # Windows 终端不支持所有 asyncio signal handler，依靠进程退出回收 lease。
            continue
