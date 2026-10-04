import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_notifier, get_session, get_settings
from backend.application.runs import (
    cancel_run,
    get_run_detail,
    get_run_events,
)
from backend.config import Settings

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await get_run_detail(session, settings, run_id)


@router.get("/{run_id}/events")
async def get_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return {"events": await get_run_events(session, settings, run_id, after_seq)}


@router.post("/{run_id}/cancel")
async def post_cancel(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    run = await cancel_run(session, settings, run_id)
    await notifier.publish_run(run.run_id)
    return {"run_id": run.run_id, "status": run.status}


@router.get("/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    request: Request,
    after_seq: int = 0,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    notifier=Depends(get_notifier),
):
    last_event_id = request.headers.get("Last-Event-ID", str(after_seq))
    try:
        after_seq = max(0, int(last_event_id))
    except ValueError:
        after_seq = 0

    async def generator():
        nonlocal after_seq
        while True:
            if await request.is_disconnected():
                return
            async with request.app.state.session_factory() as stream_session:
                events = await get_run_events(stream_session, settings, run_id, after_seq)
            for event in events:
                after_seq = event["seq"]
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {after_seq}\nevent: {event['type']}\ndata: {payload}\n\n"
                if event["type"] in {"run.succeeded", "run.failed", "run.cancelled"}:
                    return
            await asyncio.sleep(settings.sse_poll_interval)

    del notifier
    return StreamingResponse(generator(), media_type="text/event-stream")
