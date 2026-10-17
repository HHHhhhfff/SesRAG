import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    state = request.app.state
    database_ready = False
    try:
        # 包含连接池等待、连接和查询，避免依赖故障无限占住健康请求。
        async with asyncio.timeout(state.settings.health_probe_timeout):
            async with state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        database_ready = True
    except Exception:
        pass
    redis_ready = await state.notifier.probe()
    worker_count = await state.notifier.ready_worker_count() if redis_ready else None
    if worker_count is None:
        redis_ready = False
    payload = {
        "status": "ok" if redis_ready else "degraded",
        "database": "ready" if database_ready else "unavailable",
        "redis": "ready" if redis_ready else "degraded",
        "worker": "ready" if worker_count else "unknown",
        "worker_count": worker_count or 0,
    }
    if not database_ready:
        payload.update(status="unavailable", code="DATABASE_UNAVAILABLE")
        return JSONResponse(status_code=503, content=payload)
    return payload
