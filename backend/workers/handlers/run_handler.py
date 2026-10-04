import inspect
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.models import MessageModel, RunModel, TaskModel, ThreadModel
from backend.domain.enums import MessageRole, MessageStatus, RunState, TaskState
from backend.infrastructure.events.journal import append_event
from backend.infrastructure.queue.postgres_queue import schedule_retry
from backend.infrastructure.rag.pgvector_store import search_chunks


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def process_run_task(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    task_id: str,
    worker_id: str,
    generation: int,
    embedding_provider,
    model_provider,
) -> None:
    async with session_factory() as session:
        task = await session.get(TaskModel, task_id)
        if task is None or task.worker_id != worker_id or task.generation != generation:
            return
        run = await session.get(RunModel, task.run_id)
        if run is None:
            raise ApplicationError("RUN_NOT_FOUND", "Task 引用的 Run 不存在")
        message = await session.get(MessageModel, run.user_message_id)
        if message is None:
            raise ApplicationError("MESSAGE_NOT_FOUND", "Run 引用的用户消息不存在")
        if run.status == RunState.CANCELLED.value:
            return
        run.status = RunState.RUNNING.value
        task.state = TaskState.RUNNING.value
        await append_event(session, run.run_id, "run.started", {"task_id": task_id})
        await session.commit()

    try:
        query_embedding = await _maybe_await(embedding_provider.embed(message.content))
        async with session_factory() as session:
            evidence = await search_chunks(
                session, settings.owner_id, query_embedding, settings.rag_top_k
            )
            await append_event(
                session,
                run.run_id,
                "retrieval.completed",
                {
                    "count": len(evidence),
                    "items": [
                        {
                            "document_id": item.document_id,
                            "chunk_id": item.chunk_id,
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
        async for delta in model_provider.stream_answer(message.content, evidence_payload):
            answer_parts.append(delta)
            async with session_factory() as session:
                current = await session.get(RunModel, run.run_id)
                if current is None or current.status == RunState.CANCELLED.value:
                    return
                await append_event(session, run.run_id, "answer.delta", {"text": delta})
                await session.commit()

        answer = "".join(answer_parts).strip()
        citations = [
            {
                "document_id": item.document_id,
                "chunk_id": item.chunk_id,
                "filename": item.filename,
                "start_offset": item.start_offset,
                "end_offset": item.end_offset,
                "score": item.score,
            }
            for item in evidence
        ]
        async with session_factory() as session:
            current_task = await session.get(TaskModel, task_id)
            current_run = await session.get(RunModel, run.run_id)
            if (
                current_task is None
                or current_run is None
                or current_task.worker_id != worker_id
                or current_task.generation != generation
                or current_run.status == RunState.CANCELLED.value
            ):
                return
            thread = await session.get(ThreadModel, current_run.thread_id)
            if thread is None:
                raise ApplicationError("THREAD_NOT_FOUND", "Run 引用的 Thread 不存在")
            thread.next_message_seq += 1
            assistant = MessageModel(
                message_id=str(uuid4()),
                thread_id=thread.thread_id,
                seq=thread.next_message_seq,
                role=MessageRole.ASSISTANT.value,
                content=answer,
                status=MessageStatus.COMPLETED.value,
                run_id=current_run.run_id,
                citations_json=citations,
            )
            session.add(assistant)
            current_run.assistant_message_id = assistant.message_id
            current_run.status = RunState.SUCCEEDED.value
            current_task.state = TaskState.SUCCEEDED.value
            current_task.lease_expires_at = None
            await session.flush()
            await append_event(
                session,
                current_run.run_id,
                "message.completed",
                {"message_id": assistant.message_id, "citations": citations},
            )
            await append_event(
                session, current_run.run_id, "run.succeeded", {"message_id": assistant.message_id}
            )
            await session.commit()
    except ApplicationError:
        raise
    except Exception as exc:
        async with session_factory() as session:
            await schedule_retry(
                session, task_id, worker_id, generation, settings, "RUN_FAILED", str(exc)
            )
        raise
