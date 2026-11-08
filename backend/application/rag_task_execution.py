"""新任务有效代控制与结算；业务、队列及文档事实同事务更新。"""

from datetime import timedelta

from sqlalchemy import select

from backend.application.task_execution import ExecutionStopped, check_locked_times
from backend.db.models import DocumentModel, utc_now
from backend.db.rag_models import (
    IndexBuildModel,
    KnowledgeBaseModel,
    ParseJobModel,
    RetrievalExecutionModel,
)
from backend.infrastructure.queue.postgres_queue import lock_owned_task

RAG_KINDS = {"index_build", "retrieval_diagnostic"}


async def lock_rag_execution(session, task_id, worker, generation):
    task = await lock_owned_task(session, task_id, worker, generation)
    if task is None or task.cancel_requested_at:
        raise ExecutionStopped()
    return task


async def lock_build_execution(session, task_id, worker, generation):
    task = await lock_rag_execution(session, task_id, worker, generation)
    build = await session.get(IndexBuildModel, task.index_batch_id)
    if build is None:
        raise ExecutionStopped()
    base = await session.scalar(
        select(KnowledgeBaseModel)
        .where(KnowledgeBaseModel.knowledge_base_id == build.knowledge_base_id)
        .with_for_update()
    )
    document = await session.scalar(
        select(DocumentModel)
        .where(DocumentModel.document_id == build.document_id)
        .with_for_update()
    )
    build = await session.scalar(
        select(IndexBuildModel)
        .where(IndexBuildModel.index_batch_id == build.index_batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        base is None
        or document is None
        or document.knowledge_base_id != base.knowledge_base_id
        or build.state not in {"queued", "building", "waiting"}
        or build.cancel_requested_at
    ):
        raise ExecutionStopped()
    return task, base, document, build


async def yield_task(session, task, *, delay=0):
    lease, deadline = task.lease_expires_at, task.deadline_at
    task.state = "waiting_external"
    task.available_at = utc_now() + timedelta(seconds=delay)
    task.worker_id = None
    task.lease_expires_at = None
    await session.flush()
    check_locked_times(lease, deadline)
    await session.commit()


async def settle_rag_task(session, task, code, *, retry=False, cancelled=False):
    task.state = "retry_waiting" if retry else "cancelled" if cancelled else "failed"
    task.last_error_code = code
    task.last_error_message = "任务取消" if cancelled else "RAG任务失败，请按错误码检查"
    task.lease_expires_at = None
    if task.kind == "index_build":
        identity = await session.get(IndexBuildModel, task.index_batch_id)
        if identity is None:
            return
        # 与发布及取消统一 Task→KB→Document→Build，避免交叉死锁。
        await session.scalar(
            select(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.knowledge_base_id == identity.knowledge_base_id)
            .with_for_update()
        )
        doc = await session.scalar(
            select(DocumentModel)
            .where(DocumentModel.document_id == identity.document_id)
            .with_for_update()
        )
        build = await session.scalar(
            select(IndexBuildModel)
            .where(IndexBuildModel.index_batch_id == task.index_batch_id)
            .with_for_update()
        )
        if build and build.state not in {"succeeded", "failed", "cancelled"}:
            build.state = "waiting" if retry else task.state
            build.error_code = code
            job = await session.get(ParseJobModel, build.parse_job_id)
            if job and job.state not in {"succeeded", "failed", "cancelled"} and not retry:
                # 本机取消/超时无法撤销已提交的云端作业，不把本机终态当作远端终态。
                if job.parser_kind == "mineru":
                    if code == "MINERU_PARSE_FAILED":
                        job.remote_outcome = "failed"
                    elif job.stage == "downloading":
                        job.remote_outcome = "completed"
                    elif job.remote_batch_id or job.stage == "submitting":
                        job.remote_outcome = "unknown_may_continue"
                job.state = "cancelled" if cancelled else "failed"
                job.error_code = code
                job.stage = (
                    "submission_unknown" if code == "MINERU_SUBMISSION_UNKNOWN" else "stopped"
                )
                if code == "MINERU_SUBMISSION_UNKNOWN":
                    job.remote_outcome = "unknown_may_continue"
            if doc and doc.latest_index_batch_id == build.index_batch_id:
                doc.last_error_code = code
                doc.status = "indexed" if doc.active_index_batch_id else "failed"
    else:
        execution = await session.get(RetrievalExecutionModel, task.retrieval_execution_id)
        if execution and execution.state not in {"succeeded", "failed", "cancelled"}:
            execution.state = "queued" if retry else task.state
            execution.error_code = code
