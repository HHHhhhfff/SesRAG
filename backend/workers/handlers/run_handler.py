import asyncio
from dataclasses import asdict
from functools import partial

from backend.application.errors import PermanentTaskError
from backend.application.task_execution import (
    append_execution_event,
    check_execution,
    check_locked_times,
    complete_run,
    guarded_call,
    lock_execution,
)
from backend.application.vector_validation import validate_vector
from backend.db.models import MessageModel, ThreadModel
from backend.domain.ports import EmbeddingPort, ModelProvider
from backend.infrastructure.events.journal import append_event


def decode_snapshot(snapshot, owner_id):
    """旧版仅支持 mock，恢复时按旧协议固定值解释，不读取当前可变 Settings。"""
    snapshot = dict(snapshot)
    if "mock_provider" not in snapshot and snapshot.get("model") == "mock":
        snapshot.update(mock_provider=True, vector_dimension=384, owner_id=owner_id)
    try:
        valid = (
            type(snapshot["mock_provider"]) is bool
            and snapshot["vector_dimension"] == 384
            and snapshot["owner_id"] == owner_id
            and type(snapshot["retrieval"]["top_k"]) is int
            and snapshot["retrieval"]["top_k"] > 0
            and snapshot["prompt_version"] == 1
            and (
                snapshot["mock_provider"]
                or all(snapshot.get(key) for key in ("base_url", "model", "embedding_model"))
            )
        )
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise PermanentTaskError("INVALID_RUN_SNAPSHOT", "Run 快照无法恢复执行")
    return snapshot


async def process_run_task(
    session_factory,
    settings,
    task_id,
    worker_id,
    generation,
    embedding_provider: EmbeddingPort | None = None,
    model_provider: ModelProvider | None = None,
    *,
    provider_factory,
    vector_store_factory,
):
    async with session_factory() as session:
        _, initial_run = await lock_execution(session, task_id, worker_id, generation)
        schema = initial_run.execution_schema_version
    if schema == 2:
        from backend.application.session_execution import process_session_run

        return await process_session_run(
            session_factory,
            settings,
            task_id,
            worker_id,
            generation,
            embedding_provider=embedding_provider,
            model_provider=model_provider,
            vector_store_factory=vector_store_factory,
        )
    async with session_factory() as session:
        task, run = await lock_execution(session, task_id, worker_id, generation)
        assert run is not None
        message = await session.get(MessageModel, run.user_message_id)
        assert message is not None
        question = message.content
        thread = await session.get(ThreadModel, run.thread_id)
        assert thread is not None
        snapshot = decode_snapshot(run.snapshot_json, thread.owner_id)
        lease_expires_at, deadline_at = task.lease_expires_at, task.deadline_at
        run.status = "running"
        task.state = "running"
        await append_event(session, run.run_id, "run.started", {"task_id": task_id})
        await session.flush()
        check_locked_times(lease_expires_at, deadline_at)
        await session.commit()

    # 测试可注入 Provider；正常执行只从冻结快照构造，Secret 运行时注入。
    if embedding_provider is None or model_provider is None:
        default_embedding, default_model = provider_factory(snapshot)
        embedding_provider = embedding_provider or default_embedding
        model_provider = model_provider or default_model

    guarded = partial(guarded_call, session_factory, task_id, worker_id, generation)
    query_embedding = validate_vector(await guarded(partial(embedding_provider.embed, question)))
    await check_execution(session_factory, task_id, worker_id, generation)
    async with session_factory() as session:
        evidence = await vector_store_factory(session).search(
            snapshot["owner_id"], query_embedding, snapshot["retrieval"]["top_k"]
        )
        await append_execution_event(
            session,
            task_id,
            worker_id,
            generation,
            "retrieval.completed",
            {
                "count": len(evidence),
                "items": [
                    {
                        "document_id": item.document_id,
                        "chunk_id": item.chunk_id,
                        "index_batch_id": item.index_batch_id,
                        "locations": [asdict(p) for p in item.locations],
                        "start_offset": item.start_offset,
                        "end_offset": item.end_offset,
                        "score": item.score,
                    }
                    for item in evidence
                ],
            },
        )
        await session.commit()

    evidence_payload = [{"text": item.text, "chunk_id": item.chunk_id} for item in evidence]
    answer_parts: list[str] = []
    stream = model_provider.stream_answer(question, evidence_payload)
    # 总流时间和 delta 数量双重有界，不因持续小块输出无限执行。
    try:
        async with asyncio.timeout(120):
            for _ in range(4096):
                try:
                    delta = await guarded(partial(anext, stream))
                except StopAsyncIteration:
                    break
                if sum(map(len, answer_parts)) + len(delta) > 1_000_000:
                    raise ValueError("ANSWER_LIMIT_EXCEEDED")
                answer_parts.append(delta)
                async with session_factory() as session:
                    await append_execution_event(
                        session, task_id, worker_id, generation, "answer.delta", {"text": delta}
                    )
                    await session.commit()
            else:
                raise ValueError("ANSWER_LIMIT_EXCEEDED")
    finally:
        await stream.aclose()
    citations = [
        {
            "document_id": item.document_id,
            "chunk_id": item.chunk_id,
            "index_batch_id": item.index_batch_id,
            "locations": [asdict(p) for p in item.locations],
            "filename": item.filename,
            "start_offset": item.start_offset,
            "end_offset": item.end_offset,
            "score": item.score,
        }
        for item in evidence
    ]
    async with session_factory() as session:
        await complete_run(
            session, task_id, worker_id, generation, "".join(answer_parts).strip(), citations
        )
