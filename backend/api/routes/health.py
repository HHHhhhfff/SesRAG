from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict:
    worker_count = await request.app.state.notifier.ready_worker_count()
    return {
        "status": "ok",
        "database": "ready",
        "redis": "ready" if request.app.state.notifier.client is not None else "degraded",
        "worker": "ready" if worker_count else "unknown",
        "worker_count": worker_count or 0,
    }
