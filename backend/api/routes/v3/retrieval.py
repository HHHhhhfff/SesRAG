from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select

from backend.api.dependencies import get_session, get_settings
from backend.api.schemas.v3.retrieval import DiagnosticCreate, EvidenceBundle, RetrievalExecution
from backend.application.errors import ApplicationError
from backend.application.retrieval import (
    create_diagnostic,
    load_execution,
    project_execution,
    read_bundle,
)
from backend.db.models import TaskModel, utc_now

router = APIRouter(prefix="/api/v3", tags=["retrieval-v3"])


@router.post("/retrieval-executions", response_model=RetrievalExecution, status_code=202)
async def post_diagnostic(
    payload: DiagnosticCreate,
    response: Response,
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    row, duplicate = await create_diagnostic(session, settings, payload, idempotency_key)
    if duplicate:
        response.status_code = 200
    return await project_execution(session, row)


@router.get("/retrieval-executions/{identity}", response_model=RetrievalExecution)
async def get_execution(
    identity: str, session=Depends(get_session), settings=Depends(get_settings)
):
    return await project_execution(session, await load_execution(session, settings, identity))


@router.post(
    "/retrieval-executions/{identity}/cancel", response_model=RetrievalExecution, status_code=202
)
async def cancel_execution(
    identity: str, response: Response, session=Depends(get_session), settings=Depends(get_settings)
):
    row = await load_execution(session, settings, identity)
    if row.origin != "diagnostic":
        raise ApplicationError("RUN_CANCEL_REQUIRED", "Run内工具请取消整个Run", 409)
    task = await session.scalar(
        select(TaskModel).where(TaskModel.task_id == row.task_id).with_for_update()
    )
    if row.state not in {"succeeded", "failed", "cancelled"}:
        task.cancel_requested_at = row.cancel_requested_at = utc_now()
        if task.state in {"queued", "waiting_external", "retry_waiting"}:
            from backend.application.rag_task_execution import settle_rag_task

            await settle_rag_task(session, task, "TASK_CANCELLED", cancelled=True)
        await session.commit()
    if row.state in {"succeeded", "failed", "cancelled"}:
        response.status_code = 200
    return await project_execution(session, row)


@router.get("/evidence-bundles/{identity}", response_model=EvidenceBundle)
async def get_bundle(
    identity: str,
    offset: int = Query(0, ge=0, le=64000),
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    return await read_bundle(session, settings, identity, offset)
