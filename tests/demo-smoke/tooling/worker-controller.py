"""测试专用API+真实main控制服务；整容器由Node登记和回收，不注入生产路由。"""

import os
import signal
from contextlib import asynccontextmanager

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from pg_harness import ChildWorker, Harness
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.app import create_app


def create_database():
    token = os.environ["PG_SCENARIO_TOKEN"]
    assert len(token) == 8 and all(c in "0123456789abcdef" for c in token)
    url = make_url(os.environ["DATABASE_URL"])
    database = "sesrag_5a_" + token
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database}"))
    admin.dispose()
    url = url.set(database=database).render_as_string(hide_password=False)
    engine = create_engine(url)
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    engine.dispose()
    return url


def controller_app(url, *, harness_options=None, worker_factory=ChildWorker, stages=None):
    runtime_keys = (
        "TASK_DEADLINE",
        "TASK_LEASE_TTL",
        "TASK_HEARTBEAT_INTERVAL",
        "WORKER_SHUTDOWN_GRACE",
    )
    harness = Harness(
        url,
        **{key.lower(): os.environ[key] for key in runtime_keys if key in os.environ},
        **(harness_options or {}),
    )
    child = None

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await harness.close()
            await production.state.notifier.close()
            await production.state.engine.dispose()

    app = FastAPI(lifespan=lifespan)

    class Start(BaseModel):
        stage: str = "delta"

    def status():
        return {
            "controller_pid": os.getpid(),
            "worker_pid": child.process.pid if child else None,
            "exit_code": child.process.poll() if child else None,
            "running": child is not None and child.process.poll() is None,
            "reached": child is not None and (child.directory / "entered").exists(),
            "released": child is not None and (child.directory / "release").exists(),
        }

    @app.get("/__test/status")
    async def state():
        return status()

    @app.post("/__test/start")
    async def start(body: Start):
        nonlocal child
        if body.stage not in (stages or ("embed", "model", "delta", "production")) or (
            child and child.process.poll() is None
        ):
            raise HTTPException(409, "控制阶段非法或Worker仍运行")
        child = worker_factory(harness, body.stage)
        return status()

    @app.post("/__test/release")
    async def release():
        if child is None:
            raise HTTPException(409, "未启动Worker")
        child.release()
        return status()

    @app.post("/__test/stop")
    async def stop():
        if child and child.process.poll() is None:
            child.signal(signal.SIGTERM)
            await child.wait_exit(harness.cfg.worker_shutdown_grace + 4)
        return status()

    @app.get("/__test/facts/{run_id}")
    async def facts(run_id: str):
        from backend.db.models import RunModel

        async with harness.factory() as session:
            run = await session.get(RunModel, run_id)
            if run is None:
                raise HTTPException(404, "Run不存在")
            ids = {"run_id": run_id, "thread_id": run.thread_id, "task_id": run.primary_task_id}
        return await harness.facts(ids)

    production = create_app(harness.cfg)
    app.mount("/", production)
    return app


if __name__ == "__main__":
    uvicorn.run(
        controller_app(create_database()),
        host="0.0.0.0",
        port=8765,
        log_level="warning",
        access_log=False,
    )
