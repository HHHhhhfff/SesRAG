"""Run内固定只读rag.search调用及按代检索事实。"""

import hashlib
from dataclasses import dataclass
from functools import partial
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.application.retrieval import execute_retrieval, persist_bundles
from backend.application.retrieval_views import load_scope
from backend.application.task_execution import (
    append_execution_event,
    check_locked_times,
    guarded_call,
    lock_execution,
)
from backend.db.models import DocumentModel
from backend.db.rag_models import RetrievalExecutionModel, ToolCallModel
from backend.domain.rag import digest


async def settle_open_tools(session, task, run, code, *, cancelled=False):
    if run.execution_schema_version != 3:
        return
    from backend.infrastructure.events.journal import append_event

    calls = (
        await session.scalars(
            select(ToolCallModel).where(
                ToolCallModel.task_id == task.task_id,
                ToolCallModel.generation == task.generation,
                ToolCallModel.state == "running",
            )
        )
    ).all()
    for call in calls:
        execution = await session.get(RetrievalExecutionModel, call.execution_id)
        call.state = execution.state = (
            "cancelled"
            if cancelled
            else "interrupted"
            if code in {"LEASE_EXPIRED", "WORKER_STOPPED"}
            else "failed"
        )
        call.error_code = execution.error_code = code
        execution.stage = "stopped"
        await append_event(
            session,
            run.run_id,
            "tool.cancelled" if cancelled else "tool.failed",
            {
                "call_id": call.call_id,
                "execution_id": call.execution_id,
                "tool_version": call.tool_version,
                "stage": "stopped",
                "error_code": code,
            },
        )


@dataclass(frozen=True)
class BundleContext:
    """上下文算法适配值，bundle身份不伪装为持久Chunk身份。"""

    bundle_id: str
    document_id: str
    index_batch_id: str
    filename: str
    text: str
    start_offset: int
    end_offset: int
    score: float
    locations: tuple[dict, ...]
    rerank_score: float | None
    components: tuple[dict, ...]
    selection_priority: float = 0


def context_identity(evidence):
    return evidence.bundle_id if isinstance(evidence, BundleContext) else evidence.chunk_id


def bundle_metadata(evidence):
    return {
        "schema_version": 2,
        "bundle_id": evidence.bundle_id,
        "document_id": evidence.document_id,
        "index_batch_id": evidence.index_batch_id,
        "context_evidence_ids": [],
        "locations": list(evidence.locations)[:1000],
        "dense_score": evidence.score,
        "rerank_score": evidence.rerank_score,
    }


async def execute_run_retrieval(factory, settings, task_id, worker, generation, snapshot, query):
    rag = snapshot["rag"]
    if not rag["enabled"]:
        async with factory() as session:
            await append_execution_event(
                session,
                task_id,
                worker,
                generation,
                "retrieval.completed",
                {"count": 0, "execution_id": None, "mode": "off", "bundle_ids": []},
            )
            await session.commit()
        return []
    config = rag["config"]
    async with factory() as session:
        task, run = await lock_execution(session, task_id, worker, generation)
        scope = await load_scope(session, settings, rag["view_id"])
        execution = RetrievalExecutionModel(
            execution_id=str(uuid4()),
            view_id=scope.view_id,
            origin="run",
            run_id=run.run_id,
            task_id=task_id,
            generation=generation,
            snapshot_json=config,
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            state="running",
        )
        session.add(execution)
        await session.flush()
        call = ToolCallModel(
            call_id=str(uuid4()),
            run_id=run.run_id,
            task_id=task_id,
            generation=generation,
            tool_name="rag.search",
            tool_version=1,
            binding_hash=digest(config),
            execution_id=execution.execution_id,
            state="running",
        )
        session.add(call)
        await session.flush()
        payload = {
            "call_id": call.call_id,
            "execution_id": execution.execution_id,
            "tool_version": 1,
            "stage": "retrieving",
        }
        await append_execution_event(session, task_id, worker, generation, "tool.started", payload)
        lease, deadline = task.lease_expires_at, task.deadline_at
        await session.flush()
        check_locked_times(lease, deadline)
        await session.commit()
        execution_id, call_id = execution.execution_id, call.call_id
    guarded = partial(guarded_call, factory, task_id, worker, generation)

    async def progress(stage):
        async with factory() as session:
            task, _ = await lock_execution(session, task_id, worker, generation)
            execution = await session.get(RetrievalExecutionModel, execution_id)
            execution.stage = stage
            await append_execution_event(
                session, task_id, worker, generation, "tool.stage", {**payload, "stage": stage}
            )
            await session.flush()
            check_locked_times(task.lease_expires_at, task.deadline_at)
            await session.commit()

    try:
        result = await execute_retrieval(
            factory, settings, scope, config, query, guarded, progress=progress
        )
    except ApplicationError as exc:
        async with factory() as session:
            task, _ = await lock_execution(session, task_id, worker, generation)
            call = await session.get(ToolCallModel, call_id)
            execution = await session.get(RetrievalExecutionModel, execution_id)
            call.state = execution.state = "failed"
            call.error_code = execution.error_code = exc.code
            await append_execution_event(
                session,
                task_id,
                worker,
                generation,
                "tool.failed",
                {**payload, "error_code": exc.code},
            )
            lease, deadline = task.lease_expires_at, task.deadline_at
            await session.flush()
            check_locked_times(lease, deadline)
            await session.commit()
        raise
    async with factory() as session:
        task, _ = await lock_execution(session, task_id, worker, generation)
        execution = await session.get(RetrievalExecutionModel, execution_id)
        call = await session.get(ToolCallModel, call_id)
        await persist_bundles(session, execution, result)
        call.state = "succeeded"
        await append_execution_event(
            session,
            task_id,
            worker,
            generation,
            "tool.completed",
            {
                **payload,
                "stage": "completed",
                "mode": result.mode,
                "count": len(result.bundles),
                "error_code": result.error_code,
            },
        )
        await append_execution_event(
            session,
            task_id,
            worker,
            generation,
            "retrieval.completed",
            {
                "count": len(result.bundles),
                "execution_id": execution_id,
                "mode": result.mode,
                "bundle_ids": [b["bundle_id"] for b in result.bundles],
            },
        )
        evidence = []
        for rank, bundle in enumerate(result.bundles):
            doc = await session.get(DocumentModel, bundle["document_id"])
            evidence.append(
                BundleContext(
                    bundle["bundle_id"],
                    bundle["document_id"],
                    bundle["index_batch_id"],
                    doc.filename,
                    bundle["text"],
                    bundle["start_offset"],
                    bundle["end_offset"],
                    bundle["dense_score"],
                    tuple(bundle["locations"]),
                    bundle["rerank_score"],
                    tuple(bundle["components"]),
                    len(result.bundles) - rank,
                )
            )
        lease, deadline = task.lease_expires_at, task.deadline_at
        await session.flush()
        check_locked_times(lease, deadline)
        await session.commit()
        return evidence
