from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as DatabaseTimeoutError

from backend.api.routes import documents, health, runs, threads
from backend.api.routes.v2 import models as models_v2
from backend.api.routes.v2 import runs as runs_v2
from backend.api.routes.v2 import threads as threads_v2
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
        try:
            yield
        finally:
            await notifier.close()
            await engine.dispose()

    app = FastAPI(title="SesRAG", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.notifier = notifier

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_request: Request, exc: RequestValidationError):
        safe_locations = {
            "body",
            "query",
            "path",
            "header",
            "cookie",
            "title",
            "content",
            "file",
            "after_seq",
            "thread_id",
            "run_id",
            "document_id",
            "idempotency-key",
        }
        safe_types = {
            "missing",
            "string_type",
            "string_too_short",
            "string_too_long",
            "int_parsing",
            "int_type",
            "greater_than_equal",
            "json_invalid",
            "model_attributes_type",
            "model_type",
            "value_error",
        }
        # 校验异常包含原始 input/ctx/msg；仅白名单字段投影，未知路径不得回显输入键。
        detail = [
            {
                "type": error["type"] if error.get("type") in safe_types else "request_validation",
                "loc": [
                    part
                    if type(part) is int or (isinstance(part, str) and part in safe_locations)
                    else "field"
                    for part in error.get("loc", ())
                ]
                or ["body"],
                "msg": "请求参数校验失败",
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    async def database_unavailable_handler(_request: Request, _exc: Exception):
        # 依赖异常可能携带 DSN、SQL 和参数；公开响应只返回稳定错误码。
        return JSONResponse(
            status_code=503,
            content={"code": "DATABASE_UNAVAILABLE", "message": "数据库暂不可用，请稍后重试"},
        )

    for error_type in (OperationalError, InterfaceError, DatabaseTimeoutError):
        app.add_exception_handler(error_type, database_unavailable_handler)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, exc: ApplicationError):
        return JSONResponse(
            status_code=exc.status_code, content={"code": exc.code, "message": exc.message}
        )

    app.include_router(health.router)
    app.include_router(threads.router)
    app.include_router(threads_v2.router)
    app.include_router(models_v2.router)
    app.include_router(runs_v2.router)
    app.include_router(runs.router)
    app.include_router(documents.router)
    return app


app = create_app()
