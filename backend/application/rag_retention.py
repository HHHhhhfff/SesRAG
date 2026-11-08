"""独立诊断的七天保留及三十天安全墓碑；不删除Run视图或回答证据。"""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from backend.application.errors import ApplicationError
from backend.db.models import TaskModel, utc_now
from backend.db.rag_models import (
    ContextEvidenceModel,
    EvidenceBundleModel,
    EvidenceComponentModel,
    KnowledgeBaseModel,
    RagGCRecordModel,
    RetrievalExecutionModel,
    RetrievalViewItemModel,
    RetrievalViewModel,
)
from backend.domain.rag import digest


def tombstone(session, owner, identity):
    session.add(
        RagGCRecordModel(
            record_id=str(uuid4()), resource_id=f"{digest(owner)}:{identity}", result="deleted"
        )
    )


async def check_expired(session, settings, identity):
    found = await session.scalar(
        select(RagGCRecordModel.record_id)
        .where(
            RagGCRecordModel.resource_id == f"{digest(settings.owner_id)}:{identity}",
            RagGCRecordModel.result == "deleted",
            RagGCRecordModel.created_at >= utc_now() - timedelta(days=30),
        )
        .limit(1)
    )
    if found:
        raise ApplicationError("RAG_RESOURCE_EXPIRED", "该临时检索资源已按保留策略清理", 410)


async def collect_diagnostics(factory, settings, *, apply=False, limit=100):
    results = []
    async with factory() as session:
        ids = (
            await session.scalars(
                select(RetrievalExecutionModel.execution_id)
                .where(
                    RetrievalExecutionModel.origin == "diagnostic",
                    RetrievalExecutionModel.state.in_(("succeeded", "failed", "cancelled")),
                    RetrievalExecutionModel.created_at < utc_now() - timedelta(days=7),
                )
                .order_by(RetrievalExecutionModel.created_at)
                .limit(limit)
            )
        ).all()
    for identity in ids:
        async with factory() as session:
            row = await session.get(RetrievalExecutionModel, identity)
            if not row:
                continue
            task = await session.scalar(
                select(TaskModel).where(TaskModel.task_id == row.task_id).with_for_update()
            )
            view = await session.get(RetrievalViewModel, row.view_id)
            if not view:
                continue
            await session.scalar(
                select(KnowledgeBaseModel)
                .where(KnowledgeBaseModel.knowledge_base_id == view.knowledge_base_id)
                .with_for_update()
            )
            await session.refresh(row, with_for_update=True)
            if row.state not in {"succeeded", "failed", "cancelled"}:
                continue
            bundle_ids = list(
                (
                    await session.scalars(
                        select(EvidenceBundleModel.bundle_id).where(
                            EvidenceBundleModel.execution_id == identity
                        )
                    )
                ).all()
            )
            component_ids = select(EvidenceComponentModel.component_id).where(
                EvidenceComponentModel.bundle_id.in_(bundle_ids)
            )
            referenced = await session.scalar(
                select(ContextEvidenceModel.context_evidence_id)
                .where(ContextEvidenceModel.component_id.in_(component_ids))
                .limit(1)
            )
            if referenced:
                results.append({"execution_id": identity, "action": "protected"})
                continue
            results.append(
                {"execution_id": identity, "action": "delete" if apply else "would_delete"}
            )
            if not apply:
                continue
            for bundle_id in bundle_ids:
                tombstone(session, view.owner_id, bundle_id)
            tombstone(session, view.owner_id, identity)
            await session.execute(
                delete(EvidenceComponentModel).where(
                    EvidenceComponentModel.bundle_id.in_(bundle_ids)
                )
            )
            await session.execute(
                delete(EvidenceBundleModel).where(EvidenceBundleModel.bundle_id.in_(bundle_ids))
            )
            if task:
                await session.delete(task)
                await session.flush()
            await session.delete(row)
            await session.flush()
            # 诊断独占自己的视图；Run共享的历史视图绝不进入本分支。
            await session.execute(
                delete(RetrievalViewItemModel).where(RetrievalViewItemModel.view_id == view.view_id)
            )
            await session.delete(view)
            await session.commit()
    if apply:
        async with factory() as session:
            await session.execute(
                delete(RagGCRecordModel).where(
                    RagGCRecordModel.created_at < utc_now() - timedelta(days=30)
                )
            )
            await session.commit()
    return results
