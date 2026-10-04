from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.routes import documents, health, runs, threads
from backend.application.errors import ApplicationError
from backend.config import Settings
from backend.db.base import Base
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    engine = create_engine(app_settings)
    session_factory = create_session_factory(engine)
    notifier = RedisNotifier(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_settings.upload_path.mkdir(parents=True, exist_ok=True)
        if app_settings.auto_create_schema:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        await notifier.connect()
        yield
        await notifier.close()
        await engine.dispose()

    app = FastAPI(title="SesRAG", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.notifier = notifier

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, exc: ApplicationError):
        return JSONResponse(
            status_code=exc.status_code, content={"code": exc.code, "message": exc.message}
        )

    app.include_router(health.router)
    app.include_router(threads.router)
    app.include_router(runs.router)
    app.include_router(documents.router)
    return app


app = create_app()
