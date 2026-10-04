from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    extension: str
    size_bytes: int
    content_hash: str
    status: str
    active_index_batch_id: str | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
