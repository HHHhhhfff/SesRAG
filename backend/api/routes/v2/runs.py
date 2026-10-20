"""Run 控制和 Journal 只读投影，事务规则位于应用层。"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_notifier, get_session, get_settings
from backend.api.schemas.v2.context import ContextQuery, ContextResponse
from backend.api.schemas.v2.runs import (
    CancelResponse,
    EventListQuery,
    EventListResponse,
    RunOperationCreate,
    RunResponse,
)
from backend.api.schemas.v2.threads import MessageRunResponse
from backend.application.session_runs import (
    cancel_session_run,
    context_detail,
    create_related_run,
    session_run_detail,
    session_run_events,
)
from backend.config import Settings

router = APIRouter(prefix="/api/v2/runs", tags=["v2 runs"])


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await session_run_detail(session, settings, run_id)


@router.get("/{run_id}/context", response_model=ContextResponse)
async def get_context(
    run_id: str,
    query: Annotated[ContextQuery, Query()],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await context_detail(session, settings, run_id, query.generation)


@router.get("/{run_id}/events", response_model=EventListResponse)
async def get_events(
    run_id: str,
    query: Annotated[EventListQuery, Query()],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await session_run_events(session, settings, run_id, query.after_seq, query.limit)


@router.post("/{run_id}/cancel", response_model=CancelResponse)
async def post_cancel(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    run = await cancel_session_run(session, settings, run_id)
    await notifier.publish_run(run.run_id)
    return {"run_id": run.run_id, "status": run.status}


async def related(run_id, payload, key, response, session, settings, notifier, kind):
    result, duplicate = await create_related_run(session, settings, run_id, payload, key, kind)
    if duplicate:
        response.status_code = 200
    await notifier.publish_run(result["run_id"])
    return result


@router.post("/{run_id}/retry", response_model=MessageRunResponse, status_code=201)
async def post_retry(
    run_id: str,
    response: Response,
    payload: RunOperationCreate = Body(default_factory=RunOperationCreate),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    return await related(
        run_id, payload, idempotency_key, response, session, settings, notifier, "retry"
    )


@router.post("/{run_id}/regenerate", response_model=MessageRunResponse, status_code=201)
async def post_regenerate(
    run_id: str,
    response: Response,
    payload: RunOperationCreate = Body(default_factory=RunOperationCreate),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    return await related(
        run_id, payload, idempotency_key, response, session, settings, notifier, "regenerate"
    )


@router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    request: Request,
    after_seq: str = "0",
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    try:
        cursor = max(0, int(request.headers.get("Last-Event-ID", after_seq)))
    except ValueError:
        cursor = 0
    await session_run_detail(session, settings, run_id)
    await session.rollback()

    async def generator():
        nonlocal cursor
        while not await request.is_disconnected():
            async with request.app.state.session_factory() as stream_session:
                detail = await session_run_detail(stream_session, settings, run_id)
                page = await session_run_events(stream_session, settings, run_id, cursor)
            for event in page["events"]:
                cursor = event["seq"]
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {payload}\n\n"
            if not page["has_more"] and detail["status"] in {"succeeded", "failed", "cancelled"}:
                return
            if not page["has_more"]:
                await asyncio.sleep(settings.sse_poll_interval)

    return StreamingResponse(generator(), media_type="text/event-stream")
