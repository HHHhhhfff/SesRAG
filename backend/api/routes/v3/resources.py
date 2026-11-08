"""v3资源适配；解析／权限／事务规则位于应用服务。"""

import base64
import json

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select

from backend.api.dependencies import get_session, get_settings
from backend.api.schemas.v3.documents import (
    BuildCreate,
    ChunkList,
    ChunkPolicy,
    Document,
    DocumentList,
    DocumentPatch,
    IndexBuild,
)
from backend.api.schemas.v3.knowledge_bases import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseList,
    KnowledgeBasePatch,
)
from backend.api.schemas.v3.profiles import RagProfileList
from backend.application.errors import ApplicationError
from backend.application.index_builds import (
    cancel_build,
    load_build,
    load_document,
    project_build,
    project_document,
    rebuild_document,
    upload_document,
    validate_tags,
)
from backend.application.knowledge_bases import create_base, load_base, patch_base, project_base
from backend.application.rag_profiles import KINDS, profile_reason
from backend.application.source_locations import public_locations
from backend.db.models import ChunkModel, DocumentModel
from backend.db.rag_models import KnowledgeBaseModel
from backend.domain.rag import ParseRequest

router = APIRouter(prefix="/api/v3", tags=["rag-v3"])


def decode_cursor(cursor):
    if not cursor:
        return ""
    try:
        value = base64.urlsafe_b64decode(cursor.encode()).decode()
        if len(value) > 80 or not value:
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise ApplicationError("INVALID_CURSOR", "分页游标无效", 422) from None


def encode_cursor(value):
    return base64.urlsafe_b64encode(str(value).encode()).decode()


@router.post("/knowledge-bases", response_model=KnowledgeBase, status_code=201)
async def post_base(
    payload: KnowledgeBaseCreate,
    response: Response,
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    row, duplicate = await create_base(session, settings, payload, idempotency_key)
    if duplicate:
        response.status_code = 200
    return project_base(row)


@router.get("/knowledge-bases", response_model=KnowledgeBaseList)
async def get_bases(
    cursor: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    rows = (
        await session.scalars(
            select(KnowledgeBaseModel)
            .where(
                KnowledgeBaseModel.owner_id == settings.owner_id,
                KnowledgeBaseModel.knowledge_base_id > decode_cursor(cursor),
            )
            .order_by(KnowledgeBaseModel.knowledge_base_id)
            .limit(limit + 1)
        )
    ).all()
    return {
        "items": [project_base(row) for row in rows[:limit]],
        "next_cursor": encode_cursor(rows[limit - 1].knowledge_base_id)
        if len(rows) > limit
        else None,
    }


@router.get("/knowledge-bases/{identity}", response_model=KnowledgeBase)
async def get_base(identity: str, session=Depends(get_session), settings=Depends(get_settings)):
    return project_base(await load_base(session, settings.owner_id, identity))


@router.patch("/knowledge-bases/{identity}", response_model=KnowledgeBase)
async def update_base(
    identity: str,
    payload: KnowledgeBasePatch,
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    return project_base(await patch_base(session, settings, identity, payload))


@router.get("/rag/profiles", response_model=RagProfileList)
async def get_profiles(session=Depends(get_session), settings=Depends(get_settings)):
    items = []
    for kind, (model, _) in KINDS.items():
        for row in (
            await session.scalars(
                select(model).order_by(model.profile_id, model.version).limit(200)
            )
        ).all():
            config = row.config_json
            reason = (
                "PROFILE_UNAVAILABLE"
                if row.selection_status != "enabled" or row.security_status == "blocked"
                else profile_reason(kind, config, settings)
            )
            items.append(
                {
                    "kind": kind,
                    "profile_id": row.profile_id,
                    "version": row.version,
                    "available": reason is None,
                    "unavailable_reason": reason,
                    "formats": config.get("formats", []),
                    "verified_formats": config.get("verified_formats", []),
                    "space_id": getattr(row, "space_id", None),
                    "dimension": config.get("space", {}).get("dimension"),
                }
            )
    return {"items": items[:200]}


@router.post("/documents", response_model=Document, status_code=202)
async def post_document(
    response: Response,
    file: UploadFile = File(...),
    knowledge_base_id: str = Form(...),
    tags: str = Form("[]"),
    parse: str = Form("{}"),
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    if len(tags) > 4096 or len(parse) > 4096:
        raise ApplicationError("INVALID_RAG_PARAMETER", "上传参数过大", 422)
    try:
        tag_values = json.loads(tags)
        parsed = ParseRequest.model_validate_json(parse)
    except (ValueError, ValidationError):
        raise ApplicationError("INVALID_RAG_PARAMETER", "上传参数无效", 422) from None
    document, duplicate = await upload_document(
        session,
        settings,
        knowledge_base_id,
        file.filename or "",
        file.content_type,
        await file.read(10 * 1024**2 + 1),
        tag_values,
        parsed,
        ChunkPolicy(),
        idempotency_key,
    )
    if duplicate:
        response.status_code = 200
    return await project_document(session, document)


@router.get("/documents", response_model=DocumentList)
async def get_documents(
    knowledge_base_id: str,
    cursor: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    await load_base(session, settings.owner_id, knowledge_base_id)
    rows = (
        await session.scalars(
            select(DocumentModel)
            .where(
                DocumentModel.owner_id == settings.owner_id,
                DocumentModel.knowledge_base_id == knowledge_base_id,
                DocumentModel.document_id > decode_cursor(cursor),
            )
            .order_by(DocumentModel.document_id)
            .limit(limit + 1)
        )
    ).all()
    return {
        "items": [await project_document(session, row) for row in rows[:limit]],
        "next_cursor": encode_cursor(rows[limit - 1].document_id) if len(rows) > limit else None,
    }


@router.get("/documents/{identity}", response_model=Document)
async def get_document(identity: str, session=Depends(get_session), settings=Depends(get_settings)):
    return await project_document(session, await load_document(session, settings, identity))


@router.patch("/documents/{identity}", response_model=Document)
async def update_document(
    identity: str,
    payload: DocumentPatch,
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    row = await load_document(session, settings, identity)
    base = await load_base(session, settings.owner_id, row.knowledge_base_id, lock=True)
    row = await load_document(session, settings, identity, lock=True)
    row.tags_json = validate_tags(payload.tags)
    base.scope_revision += 1
    await session.commit()
    return await project_document(session, row)


@router.post("/documents/{identity}/index-builds", response_model=IndexBuild, status_code=202)
async def post_build(
    identity: str,
    payload: BuildCreate,
    response: Response,
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    row, duplicate = await rebuild_document(session, settings, identity, payload, idempotency_key)
    if duplicate:
        response.status_code = 200
    return await project_build(session, row)


@router.get("/index-builds/{identity}", response_model=IndexBuild)
async def get_build(identity: str, session=Depends(get_session), settings=Depends(get_settings)):
    return await project_build(session, await load_build(session, settings, identity))


@router.post("/index-builds/{identity}/cancel", response_model=IndexBuild, status_code=202)
async def post_cancel(
    identity: str, response: Response, session=Depends(get_session), settings=Depends(get_settings)
):
    row = await cancel_build(session, settings, identity)
    if row.state in {"succeeded", "failed", "cancelled"}:
        response.status_code = 200
    return await project_build(session, row)


@router.get("/documents/{identity}/chunks", response_model=ChunkList)
async def get_chunks(
    identity: str,
    index_batch_id: str,
    cursor: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=20),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    await load_document(session, settings, identity)
    build = await load_build(session, settings, index_batch_id)
    if build.document_id != identity or build.state != "succeeded":
        raise ApplicationError("EVIDENCE_UNAVAILABLE", "批次尚不可读取", 409)
    try:
        seq = int(decode_cursor(cursor)) if cursor else -1
    except ValueError:
        raise ApplicationError("INVALID_CURSOR", "分页游标无效", 422) from None
    rows = (
        await session.scalars(
            select(ChunkModel)
            .where(
                ChunkModel.document_id == identity,
                ChunkModel.index_batch_id == index_batch_id,
                ChunkModel.seq > seq,
            )
            .order_by(ChunkModel.seq)
            .limit(limit + 1)
        )
    ).all()
    items = []
    chars = 0
    for row in rows[:limit]:
        if chars + len(row.text) > 64000:
            break
        chars += len(row.text)
        items.append(
            {
                "chunk_id": row.chunk_id,
                "document_id": identity,
                "index_batch_id": index_batch_id,
                "seq": row.seq,
                "content_hash": row.content_hash,
                "space_id": row.space_id,
                "dimension": row.dimension,
                "block_segments": row.block_segments_json,
                "text": row.text,
                "start_offset": row.start_offset,
                "end_offset": row.end_offset,
                "locations": public_locations(
                    row.locations_json, row.chunk_id, row.start_offset, row.end_offset
                ),
            }
        )
    return {
        "items": items,
        "next_cursor": encode_cursor(items[-1]["seq"])
        if items and len(rows) > len(items)
        else None,
    }
