"""schema3会话入口；元数据CRUD继续复用v2，不建立平行聊天业务。"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_notifier, get_session, get_settings
from backend.api.schemas.v2.context import ContextQuery
from backend.api.schemas.v2.runs import CancelResponse, EventListQuery, RunOperationCreate
from backend.api.schemas.v2.threads import MessageRunResponse, ThreadDetailQuery
from backend.api.schemas.v3.context import ContextResponse
from backend.api.schemas.v3.events import Event, EventList
from backend.api.schemas.v3.sessions import MessageCreate, RunDetail, ThreadDetail
from backend.application.rag_sessions import run_detail
from backend.application.session_runs import (
    cancel_session_run,
    context_detail,
    create_related_run,
    create_session_message,
    session_run_events,
)
from backend.application.session_threads import session_thread_detail

router = APIRouter(prefix="/api/v3", tags=["sessions-v3"])


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    query: Annotated[ThreadDetailQuery, Query()],
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    return await session_thread_detail(session, settings, thread_id, query, allow_v3=True)


@router.post("/threads/{thread_id}/messages", response_model=MessageRunResponse, status_code=201)
async def post_message(
    thread_id: str,
    payload: MessageCreate,
    response: Response,
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
    notifier=Depends(get_notifier),
):
    result, duplicate = await create_session_message(
        session, settings, thread_id, payload, idempotency_key, allow_v3=True
    )
    if duplicate:
        response.status_code = 200
    await notifier.publish_run(result["run_id"])
    return result


@router.get("/runs/{identity}", response_model=RunDetail)
async def get_run(identity: str, session=Depends(get_session), settings=Depends(get_settings)):
    return await run_detail(session, settings, identity)


@router.get("/runs/{identity}/context", response_model=ContextResponse)
async def get_context(
    identity: str,
    query: Annotated[ContextQuery, Query()],
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    result = await context_detail(session, settings, identity, query.generation, allow_v3=True)
    if result["plan"]:
        from backend.application.session_runs import load_session_run

        run, _ = await load_session_run(session, settings, identity, allow_v3=True)
        result["plan"]["schema_version"] = 3 if run.execution_schema_version == 3 else 2
    return result


@router.get("/runs/{identity}/events", response_model=EventList)
async def get_events(
    identity: str,
    query: Annotated[EventListQuery, Query()],
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    return await session_run_events(
        session, settings, identity, query.after_seq, query.limit, allow_v3=True
    )


@router.post("/runs/{identity}/cancel", response_model=CancelResponse)
async def cancel_run(
    identity: str,
    session=Depends(get_session),
    settings=Depends(get_settings),
    notifier=Depends(get_notifier),
):
    row = await cancel_session_run(session, settings, identity)
    await notifier.publish_run(row.run_id)
    return {"run_id": row.run_id, "status": row.status}


async def related(identity, payload, response, key, session, settings, notifier, kind):
    result, duplicate = await create_related_run(
        session, settings, identity, payload, key, kind, allow_v3=True
    )
    if duplicate:
        response.status_code = 200
    await notifier.publish_run(result["run_id"])
    return result


@router.post("/runs/{identity}/retry", response_model=MessageRunResponse, status_code=201)
async def retry(
    identity: str,
    response: Response,
    payload: RunOperationCreate = Body(default_factory=RunOperationCreate),
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
    notifier=Depends(get_notifier),
):
    return await related(
        identity, payload, response, idempotency_key, session, settings, notifier, "retry"
    )


@router.post("/runs/{identity}/regenerate", response_model=MessageRunResponse, status_code=201)
async def regenerate(
    identity: str,
    response: Response,
    payload: RunOperationCreate = Body(default_factory=RunOperationCreate),
    idempotency_key: str | None = Header(None),
    session=Depends(get_session),
    settings=Depends(get_settings),
    notifier=Depends(get_notifier),
):
    return await related(
        identity, payload, response, idempotency_key, session, settings, notifier, "regenerate"
    )


@router.get("/runs/{identity}/events/stream")
async def stream(
    identity: str,
    request: Request,
    after_seq: str = "0",
    session=Depends(get_session),
    settings=Depends(get_settings),
):
    try:
        cursor = max(0, int(request.headers.get("Last-Event-ID", after_seq)))
    except ValueError:
        cursor = 0
    await run_detail(session, settings, identity)
    await session.rollback()

    async def generator():
        nonlocal cursor
        while not await request.is_disconnected():
            async with request.app.state.session_factory() as current:
                detail = await run_detail(current, settings, identity)
                page = await session_run_events(current, settings, identity, cursor, allow_v3=True)
            for event in page["events"]:
                event = Event.model_validate(event).model_dump(mode="json")
                cursor = event["seq"]
                data = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {data}\n\n"
            if not page["has_more"] and detail["status"] in {"succeeded", "failed", "cancelled"}:
                return
            if not page["has_more"]:
                await asyncio.sleep(settings.sse_poll_interval)

    return StreamingResponse(generator(), media_type="text/event-stream")
