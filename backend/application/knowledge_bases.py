"""最小知识范围；库空间绑定创建后不变，停用不撤回历史。"""

from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.application.rag_operations import record, replay, transaction_lock
from backend.application.rag_profiles import resolve_profile
from backend.db.models import utc_now
from backend.db.rag_models import KnowledgeBaseModel
from backend.domain.rag import digest


async def load_base(session, owner, identity, *, lock=False, new_operation=False):
    query = select(KnowledgeBaseModel).where(
        KnowledgeBaseModel.knowledge_base_id == identity, KnowledgeBaseModel.owner_id == owner
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None:
        raise ApplicationError("KNOWLEDGE_BASE_NOT_FOUND", "知识库不存在", 404)
    if new_operation and not row.enabled:
        raise ApplicationError("KNOWLEDGE_BASE_DISABLED", "知识库已停用", 409)
    return row


def project_base(row):
    return {
        key: getattr(row, key)
        for key in (
            "knowledge_base_id",
            "name",
            "enabled",
            "is_default",
            "embedding_space_id",
            "embedding_profile_id",
            "embedding_profile_version",
            "created_at",
            "updated_at",
        )
    }


async def create_base(session, settings, payload, key):
    await transaction_lock(session, f"rag-catalog:{settings.owner_id}")
    name = payload.name.strip()
    if not name:
        raise ApplicationError("INVALID_RAG_PARAMETER", "知识库名称不能为空", 422)
    hashed = digest({**payload.model_dump(), "name": name})
    result = await replay(session, settings.owner_id, "create_kb", key, hashed)
    if result:
        return await load_base(session, settings.owner_id, result["knowledge_base_id"]), True
    profile = await resolve_profile(
        session, "embedding", payload.embedding_profile_id, payload.embedding_profile_version
    )
    # 同 owner 的默认库锁作为创建串行点；唯一约束仍负责最终并发屏障。
    existing = await session.scalar(
        select(KnowledgeBaseModel)
        .where(KnowledgeBaseModel.owner_id == settings.owner_id, KnowledgeBaseModel.name == name)
        .with_for_update()
    )
    if existing:
        raise ApplicationError("KNOWLEDGE_BASE_NAME_CONFLICT", "同一账号下知识库名称已存在", 409)
    any_base = await session.scalar(
        select(KnowledgeBaseModel.knowledge_base_id)
        .where(KnowledgeBaseModel.owner_id == settings.owner_id)
        .limit(1)
    )
    row = KnowledgeBaseModel(
        knowledge_base_id=str(uuid4()),
        owner_id=settings.owner_id,
        name=name,
        is_default=any_base is None,
        embedding_space_id=profile.space_id,
        embedding_profile_id=profile.profile_id,
        embedding_profile_version=profile.version,
    )
    session.add(row)
    await session.flush()
    record(
        session,
        settings.owner_id,
        "create_kb",
        key,
        hashed,
        {"knowledge_base_id": row.knowledge_base_id},
    )
    await session.commit()
    return row, False


async def patch_base(session, settings, identity, payload):
    await transaction_lock(session, f"rag-catalog:{settings.owner_id}")
    row = await load_base(session, settings.owner_id, identity, lock=True)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise ApplicationError("INVALID_RAG_PARAMETER", "知识库名称不能为空", 422)
        conflict = await session.scalar(
            select(KnowledgeBaseModel.knowledge_base_id).where(
                KnowledgeBaseModel.owner_id == settings.owner_id,
                KnowledgeBaseModel.name == name,
                KnowledgeBaseModel.knowledge_base_id != identity,
            )
        )
        if conflict:
            raise ApplicationError("KNOWLEDGE_BASE_NAME_CONFLICT", "知识库名称已存在", 409)
        row.name = name
    if payload.enabled is not None:
        row.enabled = payload.enabled
    row.updated_at = utc_now()
    await session.commit()
    return row
