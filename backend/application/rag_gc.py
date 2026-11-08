"""显式、有界GC；先检查引用，再按固定锁序删除无引用对象。默认仅列计划。"""

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, or_, select

from backend.application.rag_capacity import storage_usage
from backend.application.rag_operations import transaction_lock
from backend.application.rag_retention import collect_diagnostics, tombstone
from backend.db.models import ChunkModel, DocumentModel, TaskModel, utc_now
from backend.db.rag_models import (
    EvidenceBundleModel,
    IndexBuildModel,
    KnowledgeBaseModel,
    LegacyEvidenceRefModel,
    ParsedArtifactModel,
    ParsedBlockModel,
    ParseJobModel,
    RetrievalExecutionModel,
    RetrievalViewItemModel,
)


async def protected(session, build):
    if await session.scalar(
        select(DocumentModel.document_id)
        .where(
            or_(
                DocumentModel.active_index_batch_id == build.index_batch_id,
                DocumentModel.latest_index_batch_id == build.index_batch_id,
            )
        )
        .limit(1)
    ):
        return True
    for model in (RetrievalViewItemModel, EvidenceBundleModel):
        if await session.scalar(
            select(model.index_batch_id)
            .where(model.index_batch_id == build.index_batch_id)
            .limit(1)
        ):
            return True
    if await session.scalar(
        select(LegacyEvidenceRefModel.ref_id)
        .join(ChunkModel, ChunkModel.chunk_id == LegacyEvidenceRefModel.resolved_chunk_id)
        .where(ChunkModel.index_batch_id == build.index_batch_id)
        .limit(1)
    ):
        return True
    return False


async def collect(factory, settings, *, apply=False, retention_hours=24, limit=100):
    if not 1 <= limit <= 1000 or retention_hours < 24:
        raise ValueError("GC至少保留24小时，每次至多1000批次")
    cutoff = utc_now() - timedelta(hours=retention_hours)
    results = await collect_diagnostics(factory, settings, apply=apply, limit=limit)
    async with factory() as session:
        ids = (
            await session.scalars(
                select(IndexBuildModel.index_batch_id)
                .where(
                    IndexBuildModel.created_at < cutoff,
                    IndexBuildModel.state.in_(("succeeded", "failed", "cancelled")),
                )
                .order_by(IndexBuildModel.created_at)
                .limit(limit)
            )
        ).all()
    for identity in ids:
        async with factory() as session:
            row = await session.get(IndexBuildModel, identity)
            if row is None:
                continue
            task = await session.scalar(
                select(TaskModel).where(TaskModel.index_batch_id == identity).with_for_update()
            )
            await session.scalar(
                select(KnowledgeBaseModel)
                .where(KnowledgeBaseModel.knowledge_base_id == row.knowledge_base_id)
                .with_for_update()
            )
            await session.scalar(
                select(DocumentModel)
                .where(DocumentModel.document_id == row.document_id)
                .with_for_update()
            )
            await session.refresh(row, with_for_update=True)
            if (
                row.state not in {"succeeded", "failed", "cancelled"}
                or (task and task.state not in {"succeeded", "failed", "cancelled"})
                or await protected(session, row)
            ):
                results.append({"index_batch_id": identity, "action": "protected"})
                continue
            results.append(
                {"index_batch_id": identity, "action": "delete" if apply else "would_delete"}
            )
            if not apply:
                continue
            await transaction_lock(session, "rag-storage-budget-v1")
            job_id = row.parse_job_id
            await session.execute(delete(ChunkModel).where(ChunkModel.index_batch_id == identity))
            if task:
                await session.delete(task)
                await session.flush()
            await session.delete(row)
            await session.flush()
            tombstone(session, settings.owner_id, identity)
            if job_id and not await session.scalar(
                select(func.count())
                .select_from(IndexBuildModel)
                .where(IndexBuildModel.parse_job_id == job_id)
            ):
                job = await session.get(ParseJobModel, job_id)
                if job:
                    job.artifact_id = None
                    await session.flush()
                    artifacts = (
                        await session.scalars(
                            select(ParsedArtifactModel).where(
                                ParsedArtifactModel.parse_job_id == job_id
                            )
                        )
                    ).all()
                    for artifact in artifacts:
                        await session.execute(
                            delete(ParsedBlockModel).where(
                                ParsedBlockModel.artifact_id == artifact.artifact_id
                            )
                        )
                        await session.delete(artifact)
                    await session.flush()
                    # 保留解析错误、未知提交及源/hash事实；清理不能抹掉重复成本确认依据。
                    # artifact_id已清空，后续新构建不会把已清理产物误当作可复用结果。
            await session.commit()
    async with factory() as session:
        state_keys = set(
            (
                await session.scalars(
                    select(ParseJobModel.private_state_key).where(
                        ParseJobModel.state.not_in(("failed", "cancelled", "succeeded"))
                    )
                )
            ).all()
        )
        state_keys |= set(
            (
                await session.scalars(
                    select(RetrievalExecutionModel.private_query_key).where(
                        RetrievalExecutionModel.state.not_in(("failed", "cancelled", "succeeded"))
                    )
                )
            ).all()
        )
    # 只删应用专用目录的一层普通文件，绝不递归、跟随链接或遍历上传/数据库卷。
    for directory in (settings.rag_artifact_dir, settings.rag_tmp_dir):
        root = Path(directory).resolve()
        if not root.exists():
            continue
        for index, path in enumerate(root.iterdir()):
            if index >= 100000:
                break
            if (
                path.name in state_keys
                or path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != root
            ):
                continue
            if path.stat().st_mtime >= cutoff.timestamp():
                continue
            size = path.stat().st_size
            if apply:
                path.unlink()
            results.append(
                {
                    "private_file": path.name,
                    "action": "delete" if apply else "would_delete",
                    "bytes": size,
                }
            )
    async with factory() as session:
        usage = await storage_usage(session, settings)
    return {
        "apply": apply,
        "retention_hours": retention_hours,
        "resources": results,
        "usage": usage,
    }
