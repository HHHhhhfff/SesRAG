from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session, get_settings
from backend.api.schemas.documents import DocumentListResponse, DocumentResponse
from backend.application.documents import create_document, create_index_task, list_documents
from backend.config import Settings

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def to_response(document) -> DocumentResponse:
    return DocumentResponse(
        document_id=document.document_id,
        filename=document.filename,
        extension=document.extension,
        size_bytes=document.size_bytes,
        content_hash=document.content_hash,
        status=document.status,
        active_index_batch_id=document.active_index_batch_id,
        last_error_code=document.last_error_code,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    document, _task = await create_document(
        session,
        settings,
        file.filename or "unnamed.txt",
        file.content_type,
        await file.read(),
    )
    return to_response(document)


@router.get("", response_model=DocumentListResponse)
async def get_documents(
    session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)
):
    return {"documents": [to_response(item) for item in await list_documents(session, settings)]}


@router.post("/{document_id}/index")
async def index_document(
    document_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    task = await create_index_task(session, settings, document_id)
    return {"task_id": task.task_id, "document_id": document_id, "state": task.state}
