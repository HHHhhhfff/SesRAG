"""跨API/Worker的保守软预算；事务锁串行化预留，不代替宿主/数据库硬配额。"""

import shutil
from pathlib import Path

from sqlalchemy import func, select

from backend.application.errors import ApplicationError
from backend.application.rag_operations import transaction_lock
from backend.db.models import ChunkModel, DocumentModel
from backend.db.rag_models import IndexBuildModel, ParsedArtifactModel

BUILD_RESERVE = 640 * 1024**2
TMP_RESERVE = 384 * 1024**2


async def storage_usage(session, settings):
    sources = await session.scalar(select(func.coalesce(func.sum(DocumentModel.size_bytes), 0)))
    artifacts = await session.scalar(
        select(func.coalesce(func.sum(func.length(ParsedArtifactModel.text) * 8), 0))
    )
    chunks = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.length(ChunkModel.text) * 8
                    + func.coalesce(ChunkModel.dimension, 384) * 8
                    + 4096
                ),
                0,
            )
        )
    )
    active = await session.scalar(
        select(func.count())
        .select_from(IndexBuildModel)
        .where(IndexBuildModel.state.in_(("queued", "building", "waiting")))
    )
    private = 0
    root = Path(settings.rag_artifact_dir)
    if root.exists():
        for index, item in enumerate(root.iterdir()):
            if index >= 100000 or item.is_symlink():
                raise ApplicationError("RAG_STORAGE_EXHAUSTED", "私有目录超出可管理边界", 507)
            if item.is_file():
                private += item.stat().st_size
    used = int(sources + artifacts + chunks + private)
    return {
        "estimated_persistent_bytes": used,
        "reserved_build_bytes": int(active) * BUILD_RESERVE,
        "active_builds": int(active),
        "budget_bytes": settings.rag_storage_budget_bytes,
        "temporary_budget_bytes": settings.rag_tmp_budget_bytes,
    }


async def reserve_storage(session, settings, *, new_build=False, source_bytes=0):
    await transaction_lock(session, "rag-storage-budget-v1")
    await session.flush()
    usage = await storage_usage(session, settings)
    reserve = source_bytes + (BUILD_RESERVE if new_build else 0)
    if (
        usage["estimated_persistent_bytes"] + usage["reserved_build_bytes"] + reserve
        > settings.rag_storage_budget_bytes
    ):
        raise ApplicationError(
            "RAG_STORAGE_EXHAUSTED", "RAG软预算不足，请先检查容量和可清理对象", 507
        )
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < source_bytes + 16 * 1024**2:
        raise ApplicationError("RAG_STORAGE_EXHAUSTED", "私有存储可用空间不足", 507)
    session.info["rag_reservation"] = {
        "persistent_bytes": reserve,
        "temporary_bytes": TMP_RESERVE if new_build else 0,
    }
    return usage
