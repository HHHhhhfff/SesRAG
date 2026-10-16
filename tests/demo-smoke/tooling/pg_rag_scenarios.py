"""索引提交、正式RAG配置、Port替换与搜索故障的独立真实PG场景。"""

import asyncio
import hashlib
import os
import sys
from dataclasses import asdict

from pg_document_scenarios import SENTINELS, document, read_index
from pg_harness import until
from provider_protocol import assert_safe_raw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.documents import create_index_task
from backend.application.errors import PermanentTaskError, TransientTaskError
from backend.config import Settings
from backend.db.models import MessageModel, RunEventModel, TaskModel
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider
from backend.infrastructure.queue import postgres_queue as queue
from backend.infrastructure.queue.adapter import PostgresQueue
from backend.infrastructure.rag.parsers import SubprocessParser
from backend.infrastructure.rag.pgvector_store import PgVectorStore
from backend.workers.runtime import WorkerRuntime


async def publication_commit(h):
    ids = await document(h)
    await h.worker().run_once()
    old = await read_index(h, ids)
    h.check(old["task"]["state"] == "succeeded", "提交故障前旧索引Task确已succeeded")
    h.check(old["document"]["status"] == "indexed", "提交故障前旧Document确已indexed")
    h.check(bool(old["document"]["active"]), "提交故障前旧active非空")
    h.check(bool(old["hits"]), "提交故障前旧search实际hits非空")
    async with h.factory() as session:
        task = await create_index_task(session, h.cfg, ids["document_id"])
        ids = {**ids, "task_id": task.task_id}
    gate = h.gate()
    hits = []

    class CommitBarrier(AsyncSession):
        async def commit(self):
            targets = [
                t
                for t in self.identity_map.values()
                if isinstance(t, TaskModel)
                and t.task_id == ids["task_id"]
                and t.state == "succeeded"
            ]
            if targets and not hits:
                hits.append("published-and-task-success-after-flush")
                await gate.pause()
                raise RuntimeError("本例最终commit故障")
            return await super().commit()

    factory = async_sessionmaker(h.engine, class_=CommitBarrier, expire_on_commit=False)
    worker = WorkerRuntime(h.cfg, factory, RedisNotifier(h.cfg))
    work = h.launch(worker.run_once())
    await gate.wait()
    before = await read_index(h, ids)
    h.check(
        before["task"]["state"] == "running" and before["document"]["status"] == "indexing",
        "最终flush后commit前外部仍为running/indexing",
    )
    h.check(
        before["chunks"] == old["chunks"]
        and before["hits"] == old["hits"]
        and before["document"]["active"] == old["document"]["active"],
        "最终commit前旧active/chunks可见，新候选及成功不可见",
    )
    gate.open()
    await work
    after = await read_index(h, ids)
    h.check(
        hits == ["published-and-task-success-after-flush"]
        and after["task"]["state"] == "retry_waiting",
        "精确最终commit故障命中后Runtime正式退避",
    )
    h.check(
        after["chunks"] == old["chunks"]
        and after["hits"] == old["hits"]
        and after["document"]["active"] == old["document"]["active"]
        and after["document"]["status"] != "indexed",
        "提交故障整组回滚，无indexed与非成功Task半发布",
    )
    h.trace["commit_fault_hits"] = hits


async def top_k(h, k):
    if k <= 0:
        try:
            Settings(_env_file=None, rag_top_k=k)
        except ValueError:
            h.check(True, f"正式Settings拒绝top_k={k}，非法配置不能创建Worker/Run")
            return
        raise AssertionError("非法top_k被接受")
    h.cfg.chunk_size, h.cfg.chunk_overlap = 8, 0
    ids = await document(h, b"alpha beta gamma delta epsilon zeta")
    await h.worker().run_once()
    indexed = await read_index(h, ids)
    n = len(indexed["chunks"])
    selected = 1 if k == 1 else n + 2
    cfg = Settings(_env_file=None, **{**h.cfg.model_dump(), "rag_top_k": selected})
    run = await h.seed(cfg=cfg)
    calls = []

    class ObservedStore(PgVectorStore):
        async def search(self, owner, vector, top_k):
            result = await super().search(owner, vector, top_k)
            calls.append(
                {"top_k": top_k, "count": len(result), "ids": [e.chunk_id for e in result]}
            )
            return result

    await h.worker(vector_store_factory=ObservedStore).run_once()
    facts = await h.facts(run)
    h.check(
        facts["run"]["status"] == "succeeded"
        and facts["run"]["snapshot_json"]["retrieval"]["top_k"] == selected,
        f"正式Run冻结并消费top_k={selected}配置",
    )
    h.check(
        len(calls) == 1 and calls[0]["top_k"] == selected and calls[0]["count"] == min(selected, n),
        f"正式Runtime配置K={selected}/N={n}实际search返回min(K,N)",
    )
    h.trace["top_k_calls"] = calls


async def search_failure(h, permanent):
    h.cfg.task_retry_base_delay = 1
    ids = await h.seed()
    calls = []

    class BrokenSearch(PgVectorStore):
        async def search(self, owner, vector, top_k):
            # 先执行真实PG检索，再模拟此适配器结果返回失败，不能假装空召回。
            await super().search(owner, vector, top_k)
            calls.append(top_k)
            error = PermanentTaskError if permanent else TransientTaskError
            raise error("TEST_SEARCH_UNAVAILABLE", "检索暂不可用")

    worker = h.worker(vector_store_factory=BrokenSearch)
    for attempt in range(1, 2 if permanent else 4):
        await worker.run_once()
        facts = await h.facts(ids)
        h.check(
            facts["task"]["attempt"] == attempt
            and facts["task"]["last_error_code"] == "TEST_SEARCH_UNAVAILABLE",
            f"search故障attempt{attempt}经正式Runtime结算",
        )
        if not permanent and attempt < 3:
            h.check(facts["task"]["state"] == "retry_waiting", "search临时错误真实持久退避")

            async def due(facts=facts):
                return queue.utc_now() >= facts["task"]["available_at"]

            await until(due, 6)
    h.check(
        facts["task"]["state"] == facts["run"]["status"] == "failed"
        and facts["run"]["last_error_code"] == "TEST_SEARCH_UNAVAILABLE",
        "search故障Task/Run同步失败",
    )
    h.check(
        facts["run"]["assistant_message_id"] is None
        and len(facts["messages"]) == 1
        and not any(
            e["type"] in ("retrieval.completed", "answer.delta", "run.succeeded")
            for e in facts["events"]
        ),
        "search故障不伪装空检索/无知识成功，无assistant/delta",
    )
    h.check(
        sum(e["type"] == "run.failed" for e in facts["events"]) == 1
        and len(calls) == (1 if permanent else 3),
        "search有限调用次数与唯一失败终态",
    )


async def port_replacement(h):
    calls = {
        "parse": 0,
        "replace": 0,
        "search": 0,
        "claim": 0,
        "embed": 0,
        "model": 0,
        "factory": 0,
    }
    evidence = []

    class Parser:
        async def parse(self, key, extension):
            calls["parse"] += 1
            return await SubprocessParser(h.cfg.upload_path).parse(key, extension)

    class Store:
        def __init__(self, session):
            self.actual = PgVectorStore(session)

        async def replace(self, document_id, batch_id, chunks):
            calls["replace"] += 1
            return await self.actual.replace(document_id, batch_id, chunks)

        async def search(self, owner, vector, top_k):
            calls["search"] += 1
            result = await self.actual.search(owner, vector, top_k)
            evidence.extend(asdict(item) for item in result)
            return result

    class Queue(PostgresQueue):
        async def claim(self, worker):
            calls["claim"] += 1
            return await super().claim(worker)

    class Embedding:
        async def embed(self, value):
            calls["embed"] += 1
            return MockEmbeddingProvider(384).embed(value)

    class Model:
        async def stream_answer(self, question, items):
            calls["model"] += 1
            async for value in MockModelProvider().stream_answer(question, items):
                yield value

    def provider_factory(snapshot):
        calls["factory"] += 1
        assert snapshot["mock_provider"] is True
        return Embedding(), Model()

    worker = h.worker(
        parser=Parser(),
        vector_store_factory=Store,
        queue_factory=lambda session: Queue(session, h.cfg),
        provider_factory=provider_factory,
    )
    worker.embedding_provider = Embedding()
    # 索引注入Embedding；Run通过构造参数factory消费冻结快照来取得两个Port。
    ids = await document(h, b"alpha\nbeta")
    await worker.run_once()
    worker.embedding_provider = None
    run = await h.seed()
    await worker.run_once()
    facts = await h.facts(run)
    h.check(
        facts["run"]["status"] == "succeeded" and all(calls[k] >= 1 for k in calls),
        "替换Parser/Vector/Queue/Embedding/Model后真实索引与Run全部成功",
    )
    async with h.factory() as session:
        message = await session.get(MessageModel, facts["run"]["assistant_message_id"])
        retrieval = await session.scalar(
            select(RunEventModel).where(
                RunEventModel.run_id == run["run_id"], RunEventModel.type == "retrieval.completed"
            )
        )
        h.check(
            len(evidence) == 1
            and evidence[0]["document_id"] == ids["document_id"]
            and evidence[0]["locations"][0]["number"] == 1,
            "替换Port保留实际Document/chunk/batch/原始行位置证据",
        )
        h.check(
            message.source == "assistant_generation"
            and [{k: v for k, v in c.items() if k != "filename"} for c in message.citations_json]
            == retrieval.payload_json["items"]
            and message.citations_json[0]["filename"] == "five-b.txt"
            and message.citations_json[0]["chunk_id"] == evidence[0]["chunk_id"],
            "替换Port后Message来源与本Run实际证据引用身份一致",
        )
    h.trace["port_calls"] = calls
    h.trace["citations"] = message.citations_json


async def startup_config(h, missing):
    environment = dict(os.environ)
    environment.update(
        {
            key.upper(): str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in h.cfg.model_dump().items()
            if value is not None
        }
    )
    config = {
        "MOCK_PROVIDER": "false",
        "MODEL_BASE_URL": "http://127.0.0.1:1/v1",
        "MODEL_API_KEY": "virtual-secret-5b",
        "MODEL_NAME": "fixture-model",
        "EMBEDDING_MODEL_NAME": "fixture-embedding",
        "REDIS_ENABLED": "false",
    }
    if missing == "mock":
        config["MOCK_PROVIDER"] = "true"
        for key in ("MODEL_BASE_URL", "MODEL_API_KEY", "MODEL_NAME", "EMBEDDING_MODEL_NAME"):
            config[key] = ""
    elif missing == "all":
        for key in ("MODEL_BASE_URL", "MODEL_API_KEY", "MODEL_NAME", "EMBEDDING_MODEL_NAME"):
            config[key] = ""
    else:
        config[missing] = ""
    environment.update(config)
    ids = await h.seed() if missing == "mock" else None
    # 当前源码容器内真实Worker main；本例独立库，父容器覆盖子进程登记。
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "backend.workers.main",
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        if missing == "mock":

            async def completed():
                if process.returncode is not None:
                    raise AssertionError("Mock main在真实执行前退出")
                return (await h.facts(ids))["run"]["status"] == "succeeded"

            await until(completed, 15)
            h.check(
                process.returncode is None,
                "当前源码容器Mock无需外部配置真实Worker main已完成本例Run",
            )
            process.terminate()
        stdout, stderr = await asyncio.wait_for(process.communicate(), 8)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    h.trace["startup"] = {
        "missing": missing,
        "exit_code": process.returncode,
        "pid": process.pid,
        "accepted": process.returncode == 0,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "validation_error": b"ValidationError" in stderr,
    }
    h.check(
        assert_safe_raw([stdout.decode(), stderr.decode()], SENTINELS),
        "Worker启动原始stdout/stderr在脱敏前无敏感哨兵",
    )
    h.trace["startup"]["stderr_scanned_raw"] = True
    if missing != "mock":
        h.check(
            process.returncode != 0 and b"ValidationError" in stderr,
            f"当前源码容器缺{missing}在Worker入口初始化时拒绝",
        )
        h.check(b"virtual-secret-5b" not in stderr, "启动拒绝原始stderr不回显虚拟Key")
    else:
        h.check(process.returncode == 0, "Mock生产main真实SIGTERM有界exit0")


rag_scenarios = {
    "index-publication-commit": publication_commit,
    "rag-search-permanent": lambda h: search_failure(h, True),
    "rag-search-transient": lambda h: search_failure(h, False),
    "rag-ports": port_replacement,
    **{
        f"rag-top-k-{name}": (lambda h, k=k: top_k(h, k))
        for name, k in (("one", 1), ("over-n", 2), ("zero", 0), ("negative", -1))
    },
    **{
        f"rag-config-{name}": (lambda h, missing=missing: startup_config(h, missing))
        for name, missing in (
            ("base", "MODEL_BASE_URL"),
            ("key", "MODEL_API_KEY"),
            ("model", "MODEL_NAME"),
            ("embedding", "EMBEDDING_MODEL_NAME"),
            ("all", "all"),
            ("mock", "mock"),
        )
    },
}
