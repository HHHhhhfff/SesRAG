from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session, get_settings
from backend.api.schemas.threads import (
    MessageCreate,
    MessageRunResponse,
    ThreadCreate,
    ThreadDetail,
    ThreadSummary,
)
from backend.application.runs import get_thread_detail
from backend.application.threads import (
    archive_thread,
    create_message_run,
    create_thread,
    list_threads,
)
from backend.config import Settings

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


@router.post("", response_model=ThreadSummary, status_code=status.HTTP_201_CREATED)
async def post_thread(
    payload: ThreadCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await create_thread(session, settings, payload.title)


@router.get("", response_model=list[ThreadSummary])
async def get_threads(
    session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)
):
    return await list_threads(session, settings)


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await get_thread_detail(session, settings, thread_id)


@router.post("/{thread_id}/archive")
async def post_archive(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    await archive_thread(session, settings, thread_id)
    return {"thread_id": thread_id, "archived": True}


@router.post(
    "/{thread_id}/messages", response_model=MessageRunResponse, status_code=status.HTTP_201_CREATED
)
async def post_message(
    thread_id: str,
    payload: MessageCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    message, run, task, duplicate = await create_message_run(
        session, settings, thread_id, payload.content, idempotency_key
    )
    if duplicate:
        response.status_code = status.HTTP_200_OK
        return MessageRunResponse(
            message_id=message.message_id,
            run_id=run.run_id,
            task_id=task.task_id,
            status=run.status,
        )
    notifier = request.app.state.notifier
    await notifier.publish_run(run.run_id)
    return MessageRunResponse(
        message_id=message.message_id, run_id=run.run_id, task_id=task.task_id, status=run.status
    )
