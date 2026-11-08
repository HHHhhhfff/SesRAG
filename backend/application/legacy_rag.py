"""仅给有可信Mock-384基线的旧入口保留本地文本；未知历史不猜空间。"""

from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.db.rag_models import EmbeddingProfileModel, KnowledgeBaseModel
from backend.domain.rag import EmbeddingSpace

LEGACY_SPACE = EmbeddingSpace(model="mock-384", revision="sha256_v1", dimension=384)


async def bootstrap_default(session, settings):
    base = await session.scalar(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.owner_id == settings.owner_id,
            KnowledgeBaseModel.is_default.is_(True),
        )
    )
    if base is None and await session.get(EmbeddingProfileModel, ("mock-embedding", 1)):
        base = KnowledgeBaseModel(
            knowledge_base_id=str(uuid4()),
            owner_id=settings.owner_id,
            name="默认知识库",
            is_default=True,
            embedding_space_id=LEGACY_SPACE.space_id,
        )
        session.add(base)
        await session.flush()
    return base


async def require_legacy_base(session, settings):
    base = await session.scalar(
        select(KnowledgeBaseModel)
        .where(
            KnowledgeBaseModel.owner_id == settings.owner_id,
            KnowledgeBaseModel.is_default.is_(True),
        )
        .with_for_update()
    )
    if base is None and settings.auto_create_schema:
        from backend.application.rag_profiles import bootstrap_mock

        await bootstrap_mock(session)
        base = await bootstrap_default(session, settings)
    if (
        base is None
        or not base.enabled
        or base.embedding_space_id != LEGACY_SPACE.space_id
        or not settings.mock_provider
    ):
        raise ApplicationError(
            "LEGACY_RAG_SPACE_UNAVAILABLE", "旧入口缺少可信的兼容空间，请使用v3知识库", 409
        )
    return base


async def protect_legacy_items(session, items, *, message_id=None, plan_id=None):
    """兼容入口新写入的旧版证据也建立FK，避免GC只保护升级前的历史。"""
    from backend.db.models import ChunkModel
    from backend.db.rag_models import LegacyEvidenceRefModel

    for item in items:
        identity = {key: item.get(key) for key in ("document_id", "index_batch_id", "chunk_id")}
        chunk = await session.scalar(
            select(ChunkModel.chunk_id).where(
                *[getattr(ChunkModel, key) == value for key, value in identity.items()]
            )
        )
        session.add(
            LegacyEvidenceRefModel(
                ref_id=str(uuid4()),
                source_message_id=message_id,
                source_plan_id=plan_id,
                resolved_chunk_id=chunk,
                identity_json=identity,
                availability="available" if chunk else "unavailable",
            )
        )


async def materialize_legacy_text(session, document, chunks):
    """旧入口新发布也物化精确正文；只拼接一致且连续的既有片段，不重新解析。"""
    import hashlib
    from dataclasses import asdict

    from backend.application.errors import PermanentTaskError
    from backend.db.rag_models import ParsedArtifactModel, ParsedBlockModel, ParseJobModel
    from backend.domain.rag import digest

    text = ""
    for chunk in sorted(chunks, key=lambda c: c.seq):
        if chunk.start_offset > len(text) or chunk.end_offset - chunk.start_offset != len(
            chunk.text
        ):
            raise PermanentTaskError("EVIDENCE_UNAVAILABLE", "旧文本片段范围不连续")
        overlap = min(len(text), chunk.end_offset) - chunk.start_offset
        if text[chunk.start_offset : chunk.start_offset + overlap] != chunk.text[:overlap]:
            raise PermanentTaskError("EVIDENCE_UNAVAILABLE", "旧文本重叠内容不一致")
        text += chunk.text[max(0, overlap) :]
    job_id, artifact_id = str(uuid4()), str(uuid4())
    snapshot = {"legacy_parser": "local_text_v1", "source_hash": document.content_hash}
    parser_hash = digest(snapshot)
    job = ParseJobModel(
        parse_job_id=job_id,
        document_id=document.document_id,
        source_hash=document.content_hash,
        parser_kind="local",
        routing_policy_version="legacy_route_v0",
        parser_snapshot=snapshot,
        parser_hash=parser_hash,
        state="succeeded",
        stage="completed",
    )
    session.add(job)
    await session.flush()
    session.add(
        ParsedArtifactModel(
            artifact_id=artifact_id,
            parse_job_id=job_id,
            source_hash=document.content_hash,
            parser_hash=parser_hash,
            protocol="legacy_text_reconstruction_v1",
            text=text,
            text_hash=hashlib.sha256(text.encode()).hexdigest(),
            manifest_hash=digest(snapshot),
        )
    )
    await session.flush()
    session.add(
        ParsedBlockModel(
            block_id=str(uuid4()),
            artifact_id=artifact_id,
            seq=0,
            kind="legacy_text",
            text=text,
            start_offset=0,
            end_offset=len(text),
            locations_json=[asdict(p) for c in chunks for p in c.locations],
        )
    )
    job.artifact_id = artifact_id
    return job_id, artifact_id
