"""文档注册、真实索引与发布观察；仅本例session/Port注入故障。"""

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import httpx
from pg_harness import Provider, until
from pg_network_scenarios import serve
from provider_protocol import assert_safe_raw
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.api.dependencies import get_session
from backend.app import create_app
from backend.application.documents import create_document, create_index_task
from backend.config import Settings
from backend.db.models import ChunkModel, DocumentModel, TaskModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.providers.mock import MockEmbeddingProvider
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.rag.chunker import chunk_text
from backend.infrastructure.rag.pgvector_store import PgVectorStore

SENTINELS = ["virtual-secret-5b", "credential-5b", "host-private-5b", "upstream-body-5b"]
FAULT_TEXT = (
    "virtual-secret-5b https://user:credential-5b@invalid/ C:/host-private-5b upstream-body-5b"
)


async def document(h, content=b"alpha beta gamma delta", filename="five-b.txt"):
    async with h.factory() as session:
        doc, task = await create_document(session, h.cfg, filename, "text/plain", content)
        return {"document_id": doc.document_id, "task_id": task.task_id}


async def read_index(h, ids):
    facts = await h.facts(ids)
    async with h.factory() as session:
        chunks = list(
            await session.scalars(
                select(ChunkModel)
                .where(ChunkModel.document_id == ids["document_id"])
                .order_by(ChunkModel.seq)
            )
        )
        hits = await PgVectorStore(session).search(
            h.cfg.owner_id, MockEmbeddingProvider(384).embed("alpha"), 100
        )
        facts["chunks"] = [
            {
                "id": c.chunk_id,
                "batch": c.index_batch_id,
                "seq": c.seq,
                "text_sha256": hashlib.sha256(c.text.encode()).hexdigest(),
                "vector_sha256": hashlib.sha256(
                    json.dumps(list(map(float, c.embedding))).encode()
                ).hexdigest(),
                "locations": c.locations_json,
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
            }
            for c in chunks
        ]
        facts["hits"] = [
            {"id": c.chunk_id, "batch": c.index_batch_id}
            for c in hits
            if c.document_id == ids["document_id"]
        ]
    h.trace.setdefault("index_reads", []).append(facts)
    return facts


async def registration_failure(h, mode):
    calls = []

    class FailingSession(AsyncSession):
        async def commit(self):
            # 文件已完整保存且本session正在登记本例Document时才命中。
            if any(isinstance(x, DocumentModel) for x in self.new):
                files = list(Path(h.temp.name).rglob("source.txt"))
                assert len(files) == 1 and files[0].read_bytes() == b"safe upload"
                calls.append("saved-before-registration-commit")
                raise RuntimeError(FAULT_TEXT)
            return await super().commit()

    app = create_app(h.cfg)
    factory = async_sessionmaker(h.engine, class_=FailingSession, expire_on_commit=False)

    async def session_override():
        async with factory() as session:
            yield session

    original_write = Path.write_bytes

    def partial_write(path, content):
        if Path(h.temp.name) in path.parents and path.name == "source.txt.tmp":
            original_write(path, b"partial")
            calls.append("own-temporary-partial-write")
            raise OSError(FAULT_TEXT)
        return original_write(path, content)

    if mode == "commit":
        app.dependency_overrides[get_session] = session_override
    async with serve(app) as base, httpx.AsyncClient() as client:
        with patch.object(
            Path, "write_bytes", partial_write if mode == "write" else original_write
        ):
            response = await client.post(
                base + "/api/v1/documents",
                files={"file": ("safe.txt", b"safe upload", "text/plain")},
            )
        raw = response.text
        h.check(
            response.status_code == 503
            and response.json()["code"]
            == ("DOCUMENT_PERSIST_FAILED" if mode == "commit" else "DOCUMENT_STORAGE_FAILED"),
            f"{mode}正式HTTP安全503与稳定错误码",
        )
        async with h.factory() as session:
            counts = [
                await session.scalar(select(func.count()).select_from(model))
                for model in (DocumentModel, TaskModel)
            ]
        h.check(counts == [0, 0], f"{mode}Document/Task登记整体不存在")
        h.check(
            len(calls) == 1 and not list(Path(h.temp.name).rglob("source*")),
            f"{mode}精确故障命中且source/tmp均清理",
        )
        h.check(
            assert_safe_raw([raw, counts, h.logs.raw], SENTINELS),
            f"{mode}原始HTTP/事实/日志在Context脱敏前无敏感哨兵",
        )
        restored = (
            await client.post(
                base + "/api/v1/documents", files={"file": ("restored.txt", b"safe", "text/plain")}
            )
            if mode == "write"
            else None
        )
        if restored is not None:
            h.check(restored.status_code == 201, "写故障解除后同HTTP服务可正常登记")
    h.trace["fault_hits"] = calls


async def active_reuse(h, state):
    ids = await document(h)
    pending = None
    if state == "leased":
        await h.claim()
    elif state == "running":
        gate = h.gate()
        pending = h.launch(h.worker(Provider(stage="embed", gate=gate)).run_once())
        await gate.wait()
    else:
        await h.worker(Provider(failures=1)).run_once()
    before = await h.facts(ids)
    h.check(before["task"]["state"] == state, f"{state}真实领取/Runtime已达到目标阶段")
    async with h.factory() as session:
        original = await session.get(TaskModel, ids["task_id"])
        batch = original.progress_json["index_batch_id"]
    async with h.factory() as session:
        reused = await create_index_task(session, h.cfg, ids["document_id"])
        h.check(
            reused.task_id == ids["task_id"] and reused.progress_json["index_batch_id"] == batch,
            f"{state}重复索引复用同Task/batch",
        )
    h.check(await h.facts(ids) == before, f"{state}请求不改变已存在的执行事实")
    async with h.factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.document_id == ids["document_id"])
        )
    h.check(count == 1, f"{state}复用后仍恰好一个Task，无额外候选任务")
    if pending:
        gate.open()
        await pending


async def document_lock(h):
    ids = await document(h)
    await h.worker().run_once()

    async def reindex():
        async with h.factory() as session:
            task = await create_index_task(session, h.cfg, ids["document_id"])
            return task.task_id, task.progress_json["index_batch_id"]

    async with h.factory() as blocker:
        await blocker.execute(
            select(DocumentModel)
            .where(DocumentModel.document_id == ids["document_id"])
            .with_for_update()
        )
        first, second = h.launch(reindex()), h.launch(reindex())
        await h.locked(2)
        h.check(
            not first.done() and not second.done(), "两个真实连接同时等Document锁且不能越过锁查询"
        )
        await blocker.rollback()
    a, b = await asyncio.gather(first, second)
    h.check(a == b and a[0] != ids["task_id"], "锁后复查两个重建请求复用唯一新Task/batch")
    async with h.factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.document_id == ids["document_id"], TaskModel.state == "queued")
        )
    h.check(count == 1, "并发重建只有一个活动Task")


async def invalid_chunk_config(h):
    for size, overlap in ((0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)):
        for consumer in ("settings", "chunker"):
            try:
                if consumer == "settings":
                    Settings(_env_file=None, chunk_size=size, chunk_overlap=overlap)
                else:
                    chunk_text("有效文本", chunk_size=size, overlap=overlap)
            except ValueError:
                h.check(
                    True, f"{consumer}拒绝非法size={size}/overlap={overlap}，不能进入永久indexing"
                )
            else:
                raise AssertionError("非法切分配置未拒绝")


async def candidate(h, mode):
    h.cfg.chunk_size, h.cfg.chunk_overlap = 8, 0
    ids = await document(h, b"alpha beta gamma delta epsilon zeta eta theta")
    old = None
    if mode != "first":
        await h.worker().run_once()
        old = await read_index(h, ids)
        h.check(old["task"]["state"] == "succeeded", f"{mode}旧索引Task确已succeeded")
        h.check(old["document"]["status"] == "indexed", f"{mode}旧Document确已indexed")
        h.check(bool(old["document"]["active"]), f"{mode}旧active非空")
        h.check(bool(old["hits"]), f"{mode}旧search实际hits非空")
        async with h.factory() as session:
            task = await create_index_task(session, h.cfg, ids["document_id"])
            ids = {**ids, "task_id": task.task_id}
    gate = h.gate()

    class SlowNth(Provider):
        async def embed(self, value):
            self.calls["embed"] += 1
            if self.calls["embed"] == 2:
                await gate.pause()
                if mode == "failed":
                    from backend.application.errors import PermanentTaskError

                    raise PermanentTaskError("TEST_NTH_CHUNK", "第N块安全失败")
            return MockEmbeddingProvider(384).embed(value)

    provider = SlowNth()
    work = h.launch(h.worker(provider).run_once())
    await gate.wait()
    before = await read_index(h, ids)
    h.check(
        before["document"]["status"] == "indexing" and before["task"]["state"] == "running",
        f"{mode}第二块真实Embedding暂停时Document indexing/Task running",
    )
    h.check(
        before["hits"] == ([] if old is None else old["hits"]),
        f"{mode}构建中实际search只能召回旧active，首次候选不可召回",
    )
    samples = []
    observer_engine = create_engine(h.cfg)
    observer_factory = create_session_factory(observer_engine)
    try:
        for _ in range(3):
            async with observer_factory() as observer:
                rows = (
                    (
                        await observer.execute(
                            text(
                                "SELECT pid,state,application_name,xact_start,"
                                "clock_timestamp() AS observed_at,"
                                "EXTRACT(EPOCH FROM (clock_timestamp()-xact_start)) "
                                "AS transaction_age_seconds,"
                                "xact_start IS NOT NULL AS in_transaction "
                                "FROM pg_stat_activity WHERE datname=current_database() "
                                "AND pid<>pg_backend_pid()"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                samples.append([dict(x) for x in rows])
            await asyncio.sleep(0.75)
    finally:
        await observer_engine.dispose()
    h.trace["transaction_samples"] = samples
    h.check(
        all(not r["in_transaction"] for sample in samples for r in sample) and any(samples),
        f"{mode}慢Embedding三次真实pg_stat_activity无贯穿事务",
    )
    gate.open()
    await work
    after = await read_index(h, ids)
    if mode == "failed":
        h.check(
            after["task"]["state"] == after["document"]["status"] == "failed"
            and after["document"]["error"] == "TEST_NTH_CHUNK",
            "第N块永久错误Task/Document一致failed",
        )
        h.check(
            after["hits"] == old["hits"]
            and after["chunks"] == old["chunks"]
            and after["document"]["active"] == old["document"]["active"],
            "第N块失败保留旧active及原Chunk身份，没有候选污染",
        )
    else:
        h.check(bool(after["hits"]), f"{mode}成功切换后search实际hits非空")
        h.check(
            after["task"]["state"] == "succeeded"
            and after["document"]["status"] == "indexed"
            and len(after["chunks"]) >= 3,
            f"{mode}全部块成功后Task/Document原子发布",
        )
        h.check(
            all(x["batch"] == after["document"]["active"] for x in after["hits"])
            and (old is None or after["document"]["active"] != old["document"]["active"]),
            f"{mode}成功后search才切换新active",
        )
    h.trace["transaction_samples"] = samples


async def exhaustion(h, stage):
    h.cfg.task_retry_base_delay = 1
    ids = await document(h)

    class BrokenParser:
        def parse(self, storage_key, extension):
            raise RuntimeError(FAULT_TEXT)

    class BrokenEmbedding:
        async def embed(self, value):
            raise RuntimeError(FAULT_TEXT)

    worker = (
        h.worker(BrokenEmbedding()) if stage == "embedding" else h.worker(parser=BrokenParser())
    )
    for attempt in (1, 2, 3):
        await worker.run_once()
        facts = await h.facts(ids)
        h.check(
            facts["task"]["attempt"] == attempt
            and facts["task"]["last_error_code"] == "INDEX_FAILED",
            f"{stage}普通异常attempt{attempt}保留稳定安全错误",
        )
        if attempt < 3:
            h.check(
                facts["task"]["state"] == "retry_waiting", f"{stage}attempt{attempt}真实持久退避"
            )

            async def due(facts=facts):
                return queue.utc_now() >= facts["task"]["available_at"]

            await until(due, 6)
    after = await read_index(h, ids)
    h.check(
        after["task"]["state"] == after["document"]["status"] == "failed"
        and after["document"]["error"] == "INDEX_FAILED",
        f"{stage}普通错误耗尽Task/Document同步failed",
    )
    h.check(
        not after["chunks"] and after["document"]["active"] is None and not await worker.run_once(),
        f"{stage}耗尽无候选/active且不会第四次执行",
    )
    h.check(
        assert_safe_raw([after, h.logs.raw], SENTINELS),
        f"{stage}原始事实/Runtime日志在脱敏前无异常哨兵",
    )


document_scenarios = {
    "document-commit-failure": lambda h: registration_failure(h, "commit"),
    "document-write-failure": lambda h: registration_failure(h, "write"),
    "document-lock": document_lock,
    "chunk-invalid-config": invalid_chunk_config,
    **{
        f"document-reuse-{s.replace('_', '-')}": (lambda h, s=s: active_reuse(h, s))
        for s in ("leased", "running", "retry_waiting")
    },
    **{
        f"index-candidate-{m}": (lambda h, m=m: candidate(h, m))
        for m in ("first", "rebuild", "failed")
    },
    "index-ordinary-exhaustion": lambda h: exhaustion(h, "embedding"),
    "parser-ordinary-exhaustion": lambda h: exhaustion(h, "parser"),
}
