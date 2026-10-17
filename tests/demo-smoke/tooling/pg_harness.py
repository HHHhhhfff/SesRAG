"""5a/5b/5c共享真实PG与有界屏障；仅测试目录可导入。"""

import asyncio
import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from backend.application.documents import create_document
from backend.application.threads import create_message_run, create_thread
from backend.config import Settings
from backend.db.models import DocumentModel, MessageModel, RunModel, TaskModel, ThreadModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.journal import list_events
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.infrastructure.queue import postgres_queue as queue
from backend.workers.runtime import WorkerRuntime


async def until(operation, timeout=8):
    async with asyncio.timeout(timeout):
        while True:
            result = await operation()
            if result:
                return result
            await asyncio.sleep(0.03)


class Gate:
    """屏障必须finally放行；到达和等待均有界。"""

    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.times = {}

    async def pause(self):
        self.times["entered"] = time.monotonic()
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), 25)
        self.times["released"] = time.monotonic()

    async def wait(self):
        await asyncio.wait_for(self.entered.wait(), 8)

    def open(self):
        self.release.set()


class Provider:
    """真实handler的Port替身；暂停/错误只作用本对象，不改业务状态。"""

    def __init__(self, *, stage=None, gate=None, failures=0, permanent=False):
        self.stage, self.gate = stage, gate
        self.failures, self.permanent = failures, permanent
        self.calls = {"embed": 0, "model": 0, "delta": 0}

    async def embed(self, value):
        self.calls["embed"] += 1
        if self.stage == "embed":
            await self.gate.pause()
        if self.calls["embed"] <= self.failures:
            from backend.application.errors import ApplicationError

            raise ApplicationError(
                "TEST_PROVIDER_FAILURE", "测试安全错误", retryable=not self.permanent
            )
        return MockEmbeddingProvider(384).embed(value)

    async def stream_answer(self, question, evidence):
        self.calls["model"] += 1
        if self.stage == "model":
            await self.gate.pause()
        for index, delta in enumerate(("第一片", "第二片", "第三片")):
            if index == 1 and self.stage == "delta":
                await self.gate.pause()
            self.calls["delta"] += 1
            yield delta


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.raw = []

    def emit(self, record):
        self.raw.append(record.getMessage())
        try:
            row = json.loads(record.getMessage())
            row["observed_at"] = time.monotonic()
            self.rows.append(row)
        except (ValueError, TypeError):
            pass


def event_fact(event, *, payload=None):
    """比较规范化payload hash，避免仅事件身份不变掩盖原事实被改写。"""
    body = event.payload_json if payload is None else payload
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return {
        "seq": event.seq,
        "type": event.type,
        "event_id": event.event_id,
        "run_id": event.run_id,
        "schema_version": event.schema_version,
        "created_at": event.created_at,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


class Harness:
    def __init__(self, url, **options):
        self.temp = tempfile.TemporaryDirectory(prefix="sesrag-5a-")
        url = (
            make_url(url)
            .update_query_dict({"application_name": "sesrag-5a-" + make_url(url).database})
            .render_as_string(hide_password=False)
        )
        defaults = dict(
            task_lease_ttl=4,
            task_heartbeat_interval=1,
            task_retry_base_delay=2,
            queue_poll_interval=0.05,
            sse_poll_interval=0.03,
            redis_enabled=False,
        )
        defaults.update(options)
        self.cfg = Settings(
            _env_file=None,
            database_url=url,
            upload_dir=self.temp.name,
            **defaults,
        )
        self.engine = create_engine(self.cfg)
        self.factory = create_session_factory(self.engine)
        self.children, self.pending, self.gates = [], [], []
        self.assertions, self.trace = [], {}
        self.trace["observations"] = []
        self.logs = LogCapture()
        self.logger = logging.getLogger("backend.workers.runtime")
        self.logger.disabled = False
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.logs)

    def check(self, condition, message):
        assert condition, message
        self.assertions.append(message)

    def gate(self):
        gate = Gate()
        self.gates.append(gate)
        return gate

    def launch(self, operation):
        work = asyncio.create_task(operation)
        self.pending.append(work)
        return work

    async def seed(self, kind="run", cfg=None, thread_id=None):
        cfg = cfg or self.cfg
        async with self.factory() as session:
            if kind == "index":
                document, task = await create_document(
                    session, cfg, "five-a.txt", "text/plain", b"alpha beta"
                )
                return {"document_id": document.document_id, "task_id": task.task_id}
            thread = await create_thread(session, cfg, "真实PG专项") if thread_id is None else None
            message, run, task, _ = await create_message_run(
                session, cfg, thread_id or thread.thread_id, "安全专项问题", str(uuid4())
            )
            return {
                "thread_id": run.thread_id,
                "run_id": run.run_id,
                "task_id": task.task_id,
                "message_id": message.message_id,
            }

    async def facts(self, ids):
        async with self.factory() as session:
            task = await session.get(TaskModel, ids["task_id"])
            result = {
                "task": {
                    key: getattr(task, key)
                    for key in (
                        "task_id",
                        "state",
                        "attempt",
                        "generation",
                        "worker_id",
                        "lease_expires_at",
                        "available_at",
                        "deadline_at",
                        "last_error_code",
                    )
                }
            }
            if "run_id" in ids:
                run = await session.get(RunModel, ids["run_id"])
                thread = await session.get(ThreadModel, ids["thread_id"])
                messages = list(
                    await session.scalars(
                        select(MessageModel)
                        .where(MessageModel.thread_id == ids["thread_id"])
                        .order_by(MessageModel.seq)
                    )
                )
                result.update(
                    run={
                        key: getattr(run, key)
                        for key in (
                            "status",
                            "assistant_message_id",
                            "next_event_seq",
                            "last_error_code",
                            "snapshot_json",
                            "cancel_requested_at",
                        )
                    },
                    messages=[
                        {
                            "message_id": m.message_id,
                            "seq": m.seq,
                            "role": m.role,
                            "run_id": m.run_id,
                            "content_sha256": hashlib.sha256(m.content.encode()).hexdigest(),
                            "citations": m.citations_json,
                            "status": m.status,
                            "source": m.source,
                            "created_at": m.created_at,
                        }
                        for m in messages
                    ],
                    cursor=thread.next_message_seq,
                    events=[event_fact(e) for e in await list_events(session, ids["run_id"])],
                )
            else:
                doc = await session.get(DocumentModel, ids["document_id"])
                result["document"] = {
                    "status": doc.status,
                    "active": doc.active_index_batch_id,
                    "error": doc.last_error_code,
                }
            self.trace["observations"].append(
                {"observed_at": time.monotonic(), "ids": ids, "facts": result}
            )
            return result

    async def claim(self, owner="worker-a"):
        async with self.factory() as session:
            return await queue.claim_next_task(session, owner, self.cfg)

    async def reclaim(self):
        async with self.factory() as session:
            return await queue.requeue_expired(session)

    async def cancel(self, ids):
        # 正式HTTP路由取消；真实网络SSE专项另外启动socket服务。
        import httpx

        from backend.app import create_app

        app = create_app(self.cfg)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/runs/" + ids["run_id"] + "/cancel")
                assert response.status_code == 200
                return response.json()
        finally:
            await app.state.engine.dispose()

    def worker(self, provider=None, **kwargs):
        worker = WorkerRuntime(self.cfg, self.factory, RedisNotifier(self.cfg), **kwargs)
        if provider:
            worker.embedding_provider = provider
            worker.model_provider = provider
        return worker

    async def locked(self, count=1):
        # pg_stat_activity提供实际锁等待证据，不以sleep猜测竞争成立。
        async def inspect():
            async with self.factory() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT pid, wait_event FROM pg_stat_activity "
                            "WHERE datname=current_database() AND wait_event_type='Lock'"
                        )
                    )
                ).all()
                return [dict(row._mapping) for row in rows] if len(rows) >= count else None

        observed = await until(inspect)
        self.trace.setdefault("lock_waits", []).append(observed)

    async def close(self):
        errors = []
        for gate in self.gates:
            gate.open()
        for child in self.children:
            try:
                await child.close()
            except Exception as error:
                errors.append(type(error).__name__)
        for work in self.pending:
            if not work.done():
                work.cancel()
        if self.pending:
            _, pending = await asyncio.wait(self.pending, timeout=3)
            if pending:
                errors.append("测试协程未在3秒内关闭")
            for work in self.pending:
                if work.done() and not work.cancelled():
                    work.exception()
        self.logger.removeHandler(self.logs)
        try:
            await self.engine.dispose()
        finally:
            self.temp.cleanup()
        if errors:
            raise RuntimeError("测试资源关闭失败：" + ",".join(errors))


class ChildWorker:
    """Linux真实生产main进程；文件仅控制测试Port，不控制生产loop/signals。"""

    def __init__(self, harness, stage="embed", bootstrap="worker-bootstrap.py"):
        self.harness = harness
        self.directory = Path(harness.temp.name) / str(uuid4())
        self.directory.mkdir()
        self.log_path = self.directory / "worker.log"
        self.log_file = self.log_path.open("w")
        environment = dict(os.environ)
        for key, value in harness.cfg.model_dump().items():
            if value is not None:
                environment[key.upper()] = (
                    str(value).lower() if isinstance(value, bool) else str(value)
                )
        environment.update(
            WORKER_CONTROL_DIR=str(self.directory),
            WORKER_CONTROL_STAGE=stage,
            WORKER_ID="linux-" + self.directory.name,
        )
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name(bootstrap))],
            env=environment,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        harness.children.append(self)

    async def reached(self):
        async def inspect():
            if self.process.poll() is not None:
                raise AssertionError("真实main在到达Port前退出")
            return (self.directory / "entered").exists()

        await until(inspect)

    def release(self):
        (self.directory / "release").touch()

    def signal(self, number=signal.SIGTERM):
        self.process.send_signal(number)

    async def wait_exit(self, timeout=8):
        async def inspect():
            code = self.process.poll()
            return {"code": code} if code is not None else None

        return (await until(inspect, timeout))["code"]

    def logs(self):
        self.log_file.flush()
        result = []
        for line in self.log_path.read_text().splitlines():
            try:
                result.append(json.loads(line))
            except ValueError:
                pass
        return result

    async def close(self):
        self.release()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                await self.wait_exit()
            except TimeoutError:
                self.process.kill()
                await self.wait_exit()
        self.log_file.close()
