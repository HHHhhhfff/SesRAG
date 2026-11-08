"""冻结实际可检索批次；后续重建／标签修改不重新展开旧视图。"""

from uuid import uuid4

from sqlalchemy import cast, exists, func, select
from sqlalchemy.dialects.postgresql import JSONB

from backend.application.errors import ApplicationError
from backend.application.knowledge_bases import load_base
from backend.application.rag_profiles import profile_reason, resolve_profile
from backend.db.models import DocumentModel
from backend.db.rag_models import IndexBuildModel, RetrievalViewItemModel, RetrievalViewModel
from backend.domain.rag import FrozenScope, RetrievalPolicy, digest
from backend.domain.rag_profiles import RetrievalConfig


async def freeze_retrieval(session, settings, selection):
    base = await load_base(
        session, settings.owner_id, selection.knowledge_base_id, lock=True, new_operation=True
    )
    retrieval = await resolve_profile(
        session,
        "retrieval",
        selection.retrieval_profile_id or "default-retrieval",
        selection.retrieval_profile_version or 1,
    )
    config = RetrievalConfig.model_validate(retrieval.config_json)
    values = config.policy.model_dump()
    values.update(selection.overrides.model_dump(exclude_none=True))
    try:
        policy = RetrievalPolicy.model_validate(values)
    except ValueError:
        raise ApplicationError("INVALID_RAG_PARAMETER", "检索覆盖参数与策略冲突", 422) from None
    embedding = await resolve_profile(
        session, "embedding", base.embedding_profile_id, base.embedding_profile_version
    )
    reason = profile_reason("embedding", embedding.config_json)
    if reason:
        raise ApplicationError(reason, "向量服务不可用", 409)
    rerank = None
    if policy.rerank_enabled:
        row = await resolve_profile(
            session, "rerank", config.rerank_profile_id, config.rerank_profile_version
        )
        reason = profile_reason("rerank", row.config_json)
        if reason:
            raise ApplicationError(reason, "重排服务不可用", 409)
        rerank = {"profile_id": row.profile_id, "version": row.version, "config": row.config_json}
    filters = selection.filters
    if filters.document_ids:
        owned = set(
            (
                await session.scalars(
                    select(DocumentModel.document_id).where(
                        DocumentModel.owner_id == settings.owner_id,
                        DocumentModel.knowledge_base_id == base.knowledge_base_id,
                        DocumentModel.document_id.in_(filters.document_ids),
                    )
                )
            ).all()
        )
        if owned != set(filters.document_ids):
            raise ApplicationError("DOCUMENT_NOT_FOUND", "文档范围无效", 404)
    query = (
        select(IndexBuildModel.index_batch_id)
        .join(DocumentModel, DocumentModel.active_index_batch_id == IndexBuildModel.index_batch_id)
        .where(
            DocumentModel.owner_id == settings.owner_id,
            DocumentModel.knowledge_base_id == base.knowledge_base_id,
            IndexBuildModel.knowledge_base_id == base.knowledge_base_id,
            IndexBuildModel.space_id == base.embedding_space_id,
            IndexBuildModel.state == "succeeded",
        )
    )
    if filters.document_ids is not None:
        query = query.where(DocumentModel.document_id.in_(filters.document_ids))
    if filters.extensions is not None:
        query = query.where(DocumentModel.extension.in_(filters.extensions))
    if filters.tags_all:
        if session.bind.dialect.name == "postgresql":
            query = query.where(
                cast(DocumentModel.tags_json, JSONB).contains(list(filters.tags_all))
            )
        else:
            for tag in filters.tags_all:
                array = func.json_each(DocumentModel.tags_json).table_valued("value").alias()
                query = query.where(
                    exists(select(1).select_from(array).where(array.c.value == tag))
                )
    batches = tuple(
        sorted(
            (
                await session.scalars(query.order_by(IndexBuildModel.index_batch_id).limit(1001))
            ).all()
        )
    )
    if len(batches) > 1000:
        raise ApplicationError("RETRIEVAL_SCOPE_TOO_LARGE", "检索视图超过1000文档", 422)
    manifest = digest(
        {
            "owner": settings.owner_id,
            "kb": base.knowledge_base_id,
            "space": base.embedding_space_id,
            "batches": batches,
        }
    )
    view = RetrievalViewModel(
        view_id=str(uuid4()),
        owner_id=settings.owner_id,
        knowledge_base_id=base.knowledge_base_id,
        space_id=base.embedding_space_id,
        filters_json=filters.model_dump(mode="json"),
        manifest_hash=manifest,
        scope_revision=base.scope_revision,
    )
    session.add(view)
    await session.flush()
    for batch in batches:
        session.add(
            RetrievalViewItemModel(
                view_id=view.view_id,
                index_batch_id=batch,
                knowledge_base_id=base.knowledge_base_id,
                space_id=base.embedding_space_id,
            )
        )
    await session.flush()
    snapshot = {
        "policy": policy.model_dump(),
        "retrieval_profile": {
            "profile_id": retrieval.profile_id,
            "version": retrieval.version,
            "config_hash": retrieval.config_hash,
        },
        "embedding": {
            "profile_id": embedding.profile_id,
            "version": embedding.version,
            "config": embedding.config_json,
        },
        "rerank": rerank,
        "tool": {"name": "rag.search", "version": 1},
        "view_id": view.view_id,
    }
    return await load_scope(session, settings, view.view_id), snapshot


async def load_scope(session, settings, identity):
    row = await session.get(RetrievalViewModel, identity)
    if row is None or row.owner_id != settings.owner_id:
        raise ApplicationError("RETRIEVAL_VIEW_UNAVAILABLE", "检索视图不可用", 404)
    batches = tuple(
        sorted(
            (
                await session.scalars(
                    select(RetrievalViewItemModel.index_batch_id).where(
                        RetrievalViewItemModel.view_id == identity
                    )
                )
            ).all()
        )
    )
    if (
        digest(
            {
                "owner": row.owner_id,
                "kb": row.knowledge_base_id,
                "space": row.space_id,
                "batches": batches,
            }
        )
        != row.manifest_hash
    ):
        raise ApplicationError("RETRIEVAL_VIEW_UNAVAILABLE", "检索视图校验失败", 409)
    valid = tuple(
        sorted(
            (
                await session.scalars(
                    select(IndexBuildModel.index_batch_id)
                    .join(DocumentModel, DocumentModel.document_id == IndexBuildModel.document_id)
                    .where(
                        IndexBuildModel.index_batch_id.in_(batches),
                        IndexBuildModel.state == "succeeded",
                        IndexBuildModel.space_id == row.space_id,
                        IndexBuildModel.knowledge_base_id == row.knowledge_base_id,
                        DocumentModel.owner_id == settings.owner_id,
                        DocumentModel.knowledge_base_id == row.knowledge_base_id,
                    )
                )
            ).all()
        )
    )
    if valid != batches:
        raise ApplicationError("RETRIEVAL_VIEW_UNAVAILABLE", "视图依赖批次缺失或归属不符", 409)
    return FrozenScope(
        row.view_id, row.owner_id, row.knowledge_base_id, row.space_id, batches, row.manifest_hash
    )
