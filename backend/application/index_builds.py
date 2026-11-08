"""登记／重建／取消的事务边界；外部解析与发布由 Worker 推进。"""

import hashlib
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from backend.application.errors import ApplicationError
from backend.application.knowledge_bases import load_base
from backend.application.rag_capacity import reserve_storage
from backend.application.rag_operations import record, replay
from backend.application.rag_profiles import profile_reason, resolve_profile, select_parser
from backend.db.models import DocumentModel, TaskModel, utc_now
from backend.db.rag_models import IndexBuildModel, ParseJobModel
from backend.domain.rag import ROUTING_VERSION, digest
from backend.infrastructure.rag.isolated_processing import isolated
from backend.infrastructure.storage.local_files import LocalFileStorage

ACTIVE_BUILDS = ("queued", "building", "waiting")


def validate_tags(tags):
    if (
        not isinstance(tags, list)
        or len(tags) > 20
        or any(not isinstance(t, str) or not t.strip() or len(t.strip()) > 40 for t in tags)
    ):
        raise ApplicationError("INVALID_RAG_PARAMETER", "标签最多20项，每项1～40字符", 422)
    return list(dict.fromkeys(t.strip() for t in tags))


async def load_document(session, settings, identity, *, lock=False):
    query = select(DocumentModel).where(
        DocumentModel.document_id == identity, DocumentModel.owner_id == settings.owner_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None:
        raise ApplicationError("DOCUMENT_NOT_FOUND", "文档不存在", 404)
    return row


async def load_build(session, settings, identity, *, lock=False):
    query = (
        select(IndexBuildModel)
        .join(DocumentModel, DocumentModel.document_id == IndexBuildModel.document_id)
        .where(
            IndexBuildModel.index_batch_id == identity, DocumentModel.owner_id == settings.owner_id
        )
    )
    if lock:
        query = query.with_for_update(of=IndexBuildModel).execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None:
        from backend.application.rag_retention import check_expired

        await check_expired(session, settings, identity)
        raise ApplicationError("INDEX_BUILD_NOT_FOUND", "构建不存在", 404)
    return row


async def start_build(session, settings, base, document, parse, chunker):
    route = parse.resolve(document.extension)
    if chunker.overlap >= chunker.size:
        raise ApplicationError("INVALID_RAG_PARAMETER", "overlap必须小于size", 422)
    profile = await select_parser(session, settings, parse, route, document.extension)
    config = profile.config_json
    if config["parser_kind"] != route or document.extension not in config["formats"]:
        raise ApplicationError("INVALID_PARSE_SELECTION", "格式与解析Profile不匹配", 422)
    reason = profile_reason("parser", config, settings, document.extension)
    if reason:
        raise ApplicationError(
            reason, "办公解析能力当前不可用，请检查服务端配置及逐格式协议验证", 409
        )
    unknown = await session.scalar(
        select(ParseJobModel.parse_job_id)
        .where(
            ParseJobModel.document_id == document.document_id,
            ParseJobModel.remote_outcome == "unknown_may_continue",
        )
        .limit(1)
    )
    if unknown and route == "mineru" and not parse.acknowledge_duplicate_cost:
        raise ApplicationError(
            "MINERU_SUBMISSION_UNKNOWN", "前次可能已受理，重新提交须确认潜在重复成本", 409
        )
    embedding = await resolve_profile(
        session, "embedding", base.embedding_profile_id, base.embedding_profile_version
    )
    if embedding.space_id != base.embedding_space_id:
        raise ApplicationError("EMBEDDING_SPACE_MISMATCH", "知识库与配置空间不匹配", 409)
    reason = profile_reason("embedding", embedding.config_json)
    if reason:
        raise ApplicationError(reason, "向量配置当前不可用", 409)
    parser_snapshot = {
        "profile_id": profile.profile_id,
        "version": profile.version,
        "config": config,
    }
    candidate = await session.scalar(
        select(IndexBuildModel)
        .where(
            IndexBuildModel.document_id == document.document_id,
            IndexBuildModel.state.in_(ACTIVE_BUILDS),
        )
        .with_for_update()
    )
    if candidate:
        current_job = await session.get(ParseJobModel, candidate.parse_job_id)
        if (
            current_job
            and current_job.parser_hash == digest(parser_snapshot)
            and candidate.chunker_snapshot == chunker.model_dump()
        ):
            return candidate
        raise ApplicationError("INDEX_BUILD_BUSY", "文档已有其他配置的活动构建", 409)
    await reserve_storage(session, settings, new_build=True)
    reusable = await session.scalar(
        select(ParseJobModel)
        .where(
            ParseJobModel.document_id == document.document_id,
            ParseJobModel.source_hash == document.content_hash,
            ParseJobModel.parser_hash == digest(parser_snapshot),
            ParseJobModel.state == "succeeded",
            ParseJobModel.artifact_id.is_not(None),
        )
        .order_by(ParseJobModel.created_at.desc())
        .limit(1)
    )
    job = reusable or ParseJobModel(
        parse_job_id=str(uuid4()),
        document_id=document.document_id,
        source_hash=document.content_hash,
        parser_kind=route,
        routing_policy_version=ROUTING_VERSION,
        parser_snapshot=parser_snapshot,
        parser_hash=digest(parser_snapshot),
    )
    session.add(job)
    await session.flush()
    build = IndexBuildModel(
        index_batch_id=str(uuid4()),
        document_id=document.document_id,
        knowledge_base_id=base.knowledge_base_id,
        space_id=base.embedding_space_id,
        parse_job_id=job.parse_job_id,
        embedding_snapshot={
            "profile_id": embedding.profile_id,
            "version": embedding.version,
            "config": embedding.config_json,
        },
        chunker_snapshot=chunker.model_dump(),
        artifact_id=job.artifact_id,
        stage="chunk" if reusable else "parse",
    )
    session.add(build)
    await session.flush()
    task = TaskModel(
        task_id=str(uuid4()),
        kind="index_build",
        index_batch_id=build.index_batch_id,
        state="queued",
        max_attempts=3,
        deadline_at=utc_now() + timedelta(seconds=1800),
    )
    session.add(task)
    await session.flush()
    build.task_id = task.task_id
    document.latest_index_batch_id = build.index_batch_id
    if not document.active_index_batch_id:
        document.status = "indexing"
    return build


async def upload_document(
    session, settings, base_id, filename, mime, content, tags, parse, chunker, key
):
    name, extension = await isolated("validate", content, "", filename=filename, mime=mime)
    parse.resolve(extension)
    tags = validate_tags(tags)
    source_hash = hashlib.sha256(content).hexdigest()
    hashed = digest(
        {
            "base": base_id,
            "filename": name,
            "hash": source_hash,
            "tags": tags,
            "parse": parse.model_dump(),
            "chunker": chunker.model_dump(),
        }
    )
    result = await replay(session, settings.owner_id, "upload", key, hashed)
    if result:
        return await load_document(session, settings, result["document_id"]), True
    base = await load_base(session, settings.owner_id, base_id, lock=True, new_operation=True)
    identity = str(uuid4())
    document = DocumentModel(
        document_id=identity,
        owner_id=settings.owner_id,
        knowledge_base_id=base_id,
        filename=name,
        source="local_upload",
        extension=extension,
        size_bytes=len(content),
        content_hash=source_hash,
        storage_key=f"documents/{identity}/source{extension}",
        status="uploaded",
        tags_json=tags,
    )
    session.add(document)
    storage = LocalFileStorage(settings.upload_path)
    saved = None
    try:
        await session.flush()
        build = await start_build(session, settings, base, document, parse, chunker)
        saved, _ = storage.save(identity, extension, content)
        record(
            session,
            settings.owner_id,
            "upload",
            key,
            hashed,
            {"document_id": identity, "index_batch_id": build.index_batch_id},
        )
        await session.commit()
        return document, False
    except Exception:
        await session.rollback()
        if saved:
            storage.remove(saved)
        raise


async def rebuild_document(session, settings, identity, payload, key):
    document = await load_document(session, settings, identity)
    base = await load_base(
        session, settings.owner_id, document.knowledge_base_id, lock=True, new_operation=True
    )
    document = await load_document(session, settings, identity, lock=True)
    hashed = digest({"document_id": identity, **payload.model_dump()})
    result = await replay(session, settings.owner_id, f"build:{identity}", key, hashed)
    if result:
        return await load_build(session, settings, result["index_batch_id"]), True
    build = await start_build(session, settings, base, document, payload.parse, payload.chunker)
    record(
        session,
        settings.owner_id,
        f"build:{identity}",
        key,
        hashed,
        {"index_batch_id": build.index_batch_id},
    )
    await session.commit()
    return build, False


async def project_build(session, row):
    job = await session.get(ParseJobModel, row.parse_job_id) if row.parse_job_id else None
    parse = (
        None
        if job is None
        else {
            "parser_profile_id": job.parser_snapshot.get("profile_id"),
            "parser_profile_version": job.parser_snapshot.get("version"),
            "parser_hash": job.parser_hash,
            "output_protocol": job.parser_snapshot.get("config", {}).get("output_protocol"),
            **{
                key: getattr(job, key)
                for key in (
                    "parse_job_id",
                    "parser_kind",
                    "routing_policy_version",
                    "state",
                    "stage",
                    "error_code",
                    "remote_outcome",
                    "artifact_id",
                    "poll_count",
                )
            },
        }
    )
    return {
        **{
            key: getattr(row, key)
            for key in (
                "index_batch_id",
                "document_id",
                "knowledge_base_id",
                "state",
                "stage",
                "task_id",
                "chunk_count",
                "error_code",
                "created_at",
            )
        },
        "parse": parse,
        "operation_status": "cancelling"
        if row.cancel_requested_at and row.state in ACTIVE_BUILDS
        else None,
    }


async def project_document(session, row):
    latest = (
        await session.get(IndexBuildModel, row.latest_index_batch_id)
        if row.latest_index_batch_id
        else None
    )
    active = (
        await session.get(IndexBuildModel, row.active_index_batch_id)
        if row.active_index_batch_id
        else None
    )
    return {
        "document_id": row.document_id,
        "knowledge_base_id": row.knowledge_base_id,
        "filename": row.filename,
        "extension": row.extension,
        "size_bytes": row.size_bytes,
        "content_hash": row.content_hash,
        "metadata_version": row.metadata_version,
        "tags": row.tags_json,
        "availability": "ready"
        if active and active.state == "succeeded" and active.space_id
        else "reindex_required"
        if row.active_index_batch_id
        else "none",
        "active_index_batch_id": row.active_index_batch_id,
        "latest_build": await project_build(session, latest) if latest else None,
        "created_at": row.created_at,
    }


async def cancel_build(session, settings, identity):
    row = await load_build(session, settings, identity)
    task = await session.scalar(
        select(TaskModel).where(TaskModel.task_id == row.task_id).with_for_update()
    )
    await load_base(session, settings.owner_id, row.knowledge_base_id, lock=True)
    await load_document(session, settings, row.document_id, lock=True)
    row = await load_build(session, settings, identity, lock=True)
    if row.state not in ACTIVE_BUILDS:
        return row
    row.cancel_requested_at = task.cancel_requested_at = utc_now()
    job = await session.get(ParseJobModel, row.parse_job_id)
    if job and job.state not in {"succeeded", "failed", "cancelled"}:
        job.cancel_requested_at = utc_now()
    if task.state in {"queued", "waiting_external", "retry_waiting"}:
        from backend.application.rag_task_execution import settle_rag_task

        await settle_rag_task(session, task, "INDEX_CANCELLED", cancelled=True)
    await session.commit()
    return row
