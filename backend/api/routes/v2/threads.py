from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_notifier, get_session, get_settings
from backend.api.schemas.v2.threads import (
    Branch,
    BranchCreate,
    BranchListResponse,
    MessageCreate,
    MessageRunResponse,
    ThreadCreate,
    ThreadDetail,
    ThreadDetailQuery,
    ThreadList,
    ThreadListQuery,
    ThreadPatch,
    ThreadSummary,
)
from backend.application.branches import create_branch
from backend.application.session_runs import create_session_message
from backend.application.session_threads import (
    list_session_branches,
    list_session_threads,
    patch_session_thread,
    session_thread_detail,
    thread_summary,
    utc_projection,
)
from backend.application.threads import create_thread
from backend.config import Settings

router = APIRouter(prefix="/api/v2/threads", tags=["v2 threads"])


@router.post("/{thread_id}/messages", response_model=MessageRunResponse, status_code=201)
async def post_message(
    thread_id: str,
    payload: MessageCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    result, duplicate = await create_session_message(
        session, settings, thread_id, payload, idempotency_key
    )
    if duplicate:
        response.status_code = 200
    await notifier.publish_run(result["run_id"])
    return result


@router.post("", response_model=ThreadSummary, status_code=201)
async def post_thread(
    payload: ThreadCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await thread_summary(
        session, await create_thread(session, settings, payload.title, conversation_version=2)
    )


@router.get("", response_model=ThreadList)
async def get_threads(
    query: Annotated[ThreadListQuery, Query()],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await list_session_threads(session, settings, query)


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_detail(
    thread_id: str,
    query: Annotated[ThreadDetailQuery, Query()],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await session_thread_detail(session, settings, thread_id, query)


@router.patch("/{thread_id}", response_model=ThreadSummary)
async def patch_thread(
    thread_id: str,
    payload: ThreadPatch,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await patch_session_thread(session, settings, thread_id, payload)


@router.get("/{thread_id}/branches", response_model=BranchListResponse)
async def get_branches(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await list_session_branches(session, settings, thread_id)


@router.post("/{thread_id}/branches", response_model=Branch, status_code=201)
async def post_branch(
    thread_id: str,
    payload: BranchCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    branch, duplicate = await create_branch(session, settings, thread_id, payload, idempotency_key)
    if duplicate:
        response.status_code = 200
    return utc_projection({name: getattr(branch, name) for name in Branch.model_fields})
