"""仅针对新建专属 PG 库的索引发布竞争与故障探针。"""

import asyncio
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sync_engine
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.documents import create_document, create_index_task
from backend.application.errors import PermanentTaskError
from backend.application.task_execution import ExecutionStopped
from backend.application.vector_validation import validate_vector
from backend.config import Settings
from backend.db.models import ChunkModel, DocumentModel, TaskModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.rag.parsers import SubprocessParser
from backend.infrastructure.rag.pgvector_store import PgVectorStore
from backend.workers.handlers.index_handler import process_index_task
from backend.workers.runtime import WorkerRuntime


async def main():
    url = os.environ["DATABASE_URL"]
    assert url.rsplit("/", 1)[-1].startswith("sesrag_rag_")
    sync = sync_engine(url)
    with sync.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with tempfile.TemporaryDirectory() as upload:
        settings = Settings(database_url=url, upload_dir=upload, redis_enabled=False)
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        worker = WorkerRuntime(settings, factory, RedisNotifier(settings))
        async with factory() as session:
            document, _ = await create_document(
                session, settings, "note.txt", "text/plain", b"alpha\nbeta"
            )
        assert await worker.run_once()
        async with factory() as session:
            old_batch = (
                await session.get(DocumentModel, document.document_id)
            ).active_index_batch_id
            assert old_batch
            old_chunks = list((await session.scalars(select(ChunkModel))).all())
            assert old_chunks[0].locations_json[1]["number"] == 2

        async def enqueue():
            async with factory() as session:
                return await create_index_task(session, settings, document.document_id)

        first, second = await asyncio.gather(enqueue(), enqueue())
        assert first.task_id == second.task_id
        print("PASS: PG concurrent Document index reuses one active Task/batch")

        entered, finish = asyncio.Event(), asyncio.Event()

        class SlowProvider:
            async def embed(self, value):
                entered.set()
                await finish.wait()
                raise PermanentTaskError("EMBEDDING_INVALID", "safe")

        worker.embedding_provider = SlowProvider()
        work = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(entered.wait(), 10)
        async with factory() as session:
            idle = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid() AND state='idle in transaction'"
                )
            )
            assert idle == 0
            await session.execute(
                select(TaskModel)
                .where(TaskModel.task_id == first.task_id)
                .with_for_update(nowait=True)
            )
            await session.execute(
                select(DocumentModel)
                .where(DocumentModel.document_id == document.document_id)
                .with_for_update(nowait=True)
            )
        print("PASS: PG slow embedding holds no transaction or Task/Document lock")
        finish.set()
        await work
        async with factory() as session:
            saved = await session.get(DocumentModel, document.document_id)
            assert saved.status == "failed" and saved.active_index_batch_id == old_batch
            assert (await session.get(TaskModel, first.task_id)).state == "failed"
            assert {
                c.index_batch_id for c in (await session.scalars(select(ChunkModel))).all()
            } == {old_batch}
        print(
            "PASS: PG candidate failure settled centrally, old active/chunks preserved, no garbage"
        )

        next_task = await enqueue()
        async with factory() as session:
            lease = await queue.claim_next_task(session, "publication", settings)
            assert lease.task_id == next_task.task_id
            await queue.mark_running(session, lease.task_id, "publication", lease.generation)

        published, release = asyncio.Event(), asyncio.Event()

        class CommitBarrier(AsyncSession):
            async def commit(self):
                # 正式flush后拦截提交；此时真实PG事务已写候选/active/success，但外界不可见。
                pending = [
                    item
                    for item in self.identity_map.values()
                    if isinstance(item, TaskModel) and item.state == "succeeded"
                ]
                if pending:
                    published.set()
                    await release.wait()
                    raise RuntimeError("private commit failure")
                await super().commit()

        barrier_factory = async_sessionmaker(engine, class_=CommitBarrier, expire_on_commit=False)
        work = asyncio.create_task(
            process_index_task(
                barrier_factory,
                settings,
                lease.task_id,
                "publication",
                lease.generation,
                MockEmbeddingProvider(),
                SubprocessParser(settings.upload_path),
                PgVectorStore,
            )
        )
        await asyncio.wait_for(published.wait(), 10)
        async with factory() as session:
            assert (
                await session.get(DocumentModel, document.document_id)
            ).active_index_batch_id == old_batch
            assert (await session.get(TaskModel, lease.task_id)).state == "running"
            assert {
                c.index_batch_id for c in (await session.scalars(select(ChunkModel))).all()
            } == {old_batch}
        release.set()
        try:
            await work
            raise AssertionError("commit fault not triggered")
        except RuntimeError as error:
            assert str(error) == "private commit failure"
        async with factory() as session:
            assert (
                await session.get(DocumentModel, document.document_id)
            ).active_index_batch_id == old_batch
            assert (await session.get(TaskModel, lease.task_id)).state == "running"
            assert {
                c.index_batch_id for c in (await session.scalars(select(ChunkModel))).all()
            } == {old_batch}
        print(
            "PASS: PG publication+Task success invisible before commit; "
            "commit failure rolls all back"
        )

        # 解析已完成才加 Document 锁；释放最后 embedding 后让最终发布事务等待。
        ready = asyncio.Event()
        embedded, release_embedding = asyncio.Event(), asyncio.Event()

        class FinalStageProvider:
            async def embed(self, value):
                vector = MockEmbeddingProvider().embed(value)
                embedded.set()
                await release_embedding.wait()
                return vector

        class LockedStore(PgVectorStore):
            async def replace(self, document_id, batch_id, chunks):
                await super().replace(document_id, batch_id, chunks)
                ready.set()

        work = asyncio.create_task(
            process_index_task(
                factory,
                settings,
                lease.task_id,
                "publication",
                lease.generation,
                FinalStageProvider(),
                SubprocessParser(settings.upload_path),
                LockedStore,
            )
        )
        await asyncio.wait_for(embedded.wait(), 10)
        async with factory() as blocker:
            await blocker.execute(
                select(DocumentModel)
                .where(DocumentModel.document_id == document.document_id)
                .with_for_update()
            )
            release_embedding.set()
            await asyncio.sleep(0.2)
            assert not work.done()
            async with factory() as observer:
                waiting = await observer.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND wait_event_type='Lock' AND query LIKE '%documents%FOR UPDATE%'"
                    )
                )
                assert waiting == 1
            now = queue.utc_now() + timedelta(seconds=40)
            with patch.object(queue, "utc_now", return_value=now):
                await blocker.rollback()
                try:
                    await work
                    raise AssertionError("expired lease published")
                except ExecutionStopped:
                    pass
        assert not ready.is_set()
        print(
            "PASS: PG FINAL publication Document lock wait after embedding crosses lease; rejected"
        )

        for phase in ("chunks", "terminal"):
            for seconds in (40, 700):
                clock_patch = None
                observed_flush = False

                class ExpiringFlush(AsyncSession):
                    async def flush(self, objects=None, *, phase=phase, seconds=seconds):
                        nonlocal clock_patch, observed_flush
                        target = (
                            any(isinstance(item, ChunkModel) for item in self.new)
                            if phase == "chunks"
                            else any(
                                isinstance(item, TaskModel) and item.state == "succeeded"
                                for item in self.identity_map.values()
                            )
                        )
                        await super().flush(objects)
                        if target and not observed_flush:
                            observed_flush = True
                            clock_patch = patch.object(
                                queue,
                                "utc_now",
                                return_value=queue.utc_now() + timedelta(seconds=seconds),
                            )
                            clock_patch.start()

                expire_factory = async_sessionmaker(
                    engine, class_=ExpiringFlush, expire_on_commit=False
                )
                try:
                    await process_index_task(
                        expire_factory,
                        settings,
                        lease.task_id,
                        "publication",
                        lease.generation,
                        MockEmbeddingProvider(),
                        SubprocessParser(settings.upload_path),
                        PgVectorStore,
                    )
                    raise AssertionError("flush crossed deadline/lease but published")
                except ExecutionStopped:
                    assert observed_flush
                finally:
                    if clock_patch is not None:
                        clock_patch.stop()
                async with factory() as session:
                    assert (
                        await session.get(DocumentModel, document.document_id)
                    ).active_index_batch_id == old_batch
                    assert (await session.get(TaskModel, lease.task_id)).state == "running"
                    assert {
                        c.index_batch_id for c in (await session.scalars(select(ChunkModel))).all()
                    } == {old_batch}
                print(
                    f"PASS: PG {phase} flush crosses "
                    f"{'deadline and lease' if seconds == 700 else 'lease'}; rolls back all writes"
                )

        async with factory() as session:
            values = await PgVectorStore(session).search(settings.owner_id, [1] * 384, 1)
            assert values and values[0].score <= 1.000001
            for invalid in ([1e308] * 384, [10**400] * 384):
                try:
                    await PgVectorStore(session).search(settings.owner_id, invalid, 1)
                    raise AssertionError("out-of-range vector accepted")
                except PermanentTaskError as error:
                    assert error.code == "EMBEDDING_INVALID"
            assert validate_vector([1] * 384) == [1.0] * 384
        print("PASS: PG finite search succeeds; huge float/int rejected before database vector use")

        await process_index_task(
            factory,
            settings,
            lease.task_id,
            "publication",
            lease.generation,
            MockEmbeddingProvider(),
            SubprocessParser(settings.upload_path),
            PgVectorStore,
        )
        async with factory() as session:
            saved = await session.get(DocumentModel, document.document_id)
            assert saved.status == "indexed" and saved.active_index_batch_id != old_batch
            assert (await session.get(TaskModel, lease.task_id)).state == "succeeded"
            chunks = list((await session.scalars(select(ChunkModel))).all())
            assert {c.index_batch_id for c in chunks} == {saved.active_index_batch_id}
            locations = chunks[0].locations_json
        print("PASS: PG successful publication switches active/chunks and Task atomically")
        short = settings.model_copy(update={"task_deadline": 20})
        async with factory() as session:
            task = await create_index_task(session, short, document.document_id)
            short_lease = await queue.claim_next_task(session, "deadline-only", short)
            assert short_lease.task_id == task.task_id
            await queue.mark_running(session, task.task_id, "deadline-only", short_lease.generation)
        clock_patch = None

        class DeadlineFlush(AsyncSession):
            async def flush(self, objects=None):
                nonlocal clock_patch
                terminal = any(
                    isinstance(item, TaskModel) and item.state == "succeeded"
                    for item in self.identity_map.values()
                )
                await super().flush(objects)
                if terminal:
                    clock = queue.utc_now() + timedelta(seconds=25)
                    # 正式队列将 lease 截断到 deadline；短任务两者同时到期。
                    assert short_lease.lease_expires_at == short_lease.deadline_at < clock
                    clock_patch = patch.object(queue, "utc_now", return_value=clock)
                    clock_patch.start()

        try:
            await process_index_task(
                async_sessionmaker(engine, class_=DeadlineFlush, expire_on_commit=False),
                short,
                task.task_id,
                "deadline-only",
                short_lease.generation,
                MockEmbeddingProvider(),
                SubprocessParser(settings.upload_path),
                PgVectorStore,
            )
            raise AssertionError("deadline expired during final flush")
        except ExecutionStopped:
            assert clock_patch is not None
        finally:
            if clock_patch is not None:
                clock_patch.stop()
        async with factory() as session:
            assert (await session.get(TaskModel, task.task_id)).state == "running"
            assert (
                await session.get(DocumentModel, document.document_id)
            ).active_index_batch_id == saved.active_index_batch_id
            assert (await session.scalar(select(ChunkModel))).locations_json == locations
        print("PASS: PG final flush crosses deadline-capped lease; whole publication rolls back")
        await engine.dispose()
        with sync.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_demo_integrity")
            assert (
                connection.execute(text("SELECT locations_json FROM chunks")).scalar_one()
                == locations
            )
            command.upgrade(config, "head")
            assert (
                connection.execute(text("SELECT locations_json FROM chunks")).scalar_one()
                == locations
            )
        print("PASS: PG downgrade/re-upgrade preserves existing location evidence")
    sync.dispose()


if __name__ == "__main__":
    asyncio.run(main())
