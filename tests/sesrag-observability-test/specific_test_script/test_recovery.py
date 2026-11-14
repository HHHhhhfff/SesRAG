"""A06/A09/A10：真实PG迁移门禁、来源不可变和原事务yield结算。"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.observation import bind
from backend.application.rag_task_execution import yield_task
from backend.config import Settings
from backend.db.models import TaskModel
from backend.db.session import create_engine as async_engine
from backend.domain.observability import ExecutionIdentity
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


async def receipt_check():
    engine = async_engine(Settings())
    from uuid import uuid4

    identity = str(uuid4())
    now = datetime.now(timezone.utc)
    runtime = ObservabilityRuntime(load_config("worker", {"OBS_METRICS_ENABLED": "false"}))
    with (
        bind(runtime),
        runtime.attempt(
            ExecutionIdentity(identity, "index_build", "test-worker", 1, 1), None
        ) as observed,
    ):
        async with AsyncSession(engine) as session:
            # 用实际已成功Build作目标；仅创建本组独立Task，不改变原Build。
            build = await session.scalar(text("SELECT index_batch_id FROM index_builds LIMIT 1"))
            if build is None:
                raise AssertionError("Recovery需先准备本组索引夹具")
            task = TaskModel(
                task_id=identity,
                kind="index_build",
                index_batch_id=build,
                state="running",
                worker_id="test-worker",
                generation=1,
                attempt=1,
                deadline_at=now + timedelta(minutes=1),
                lease_expires_at=now + timedelta(seconds=30),
            )
            session.add(task)
            await session.flush()
            await yield_task(session, task, delay=60)
        assert observed.result == "yielded"
    assert runtime.metrics.child("TASK_ATTEMPTS", "index_build", "succeeded")._value.get() == 0
    async with AsyncSession(engine) as session:
        await session.execute(text("DELETE FROM tasks WHERE task_id=:id"), {"id": identity})
        await session.commit()
    await runtime.close()
    await engine.dispose()


def run():
    settings = Settings()
    admin = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute("CREATE DATABASE obs_migration")
    engine = create_engine(settings.database_url.rsplit("/", 1)[0] + "/obs_migration")
    cfg = Config("alembic.ini")
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "0011_rag_source_integrity")
        connection.execute(
            text("""INSERT INTO tasks(task_id,kind,document_id,state,attempt,max_attempts,
            available_at,deadline_at,generation,progress_json,failure_count,created_at,updated_at)
            VALUES ('old','index_document','old-doc','queued',0,3,now(),
                    now()+interval '1 hour',0,'{}',0,now(),now())""")
        )
        connection.commit()
        command.upgrade(cfg, "head")
        assert (
            connection.scalar(text("SELECT trace_origin_json FROM tasks WHERE task_id='old'"))
            is None
        )
        connection.commit()
        try:
            connection.execute(text("UPDATE tasks SET trace_origin_json='{}' WHERE task_id='old'"))
        except Exception:
            connection.rollback()
        else:
            raise AssertionError("PostgreSQL来源不可变触发器未生效")
        try:
            command.downgrade(cfg, "0011_rag_source_integrity")
        except RuntimeError as exc:
            assert str(exc) == "OBSERVABILITY_LOSS_CONFIRMATION_REQUIRED"
            connection.rollback()
        else:
            raise AssertionError("缺少显式授权仍然允许降级")
        cfg.cmd_opts = SimpleNamespace(x=["allow_observability_loss=true"])
        command.downgrade(cfg, "0011_rag_source_integrity")
        command.upgrade(cfg, "head")
    engine.dispose()
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute("DROP DATABASE obs_migration WITH (FORCE)")
    asyncio.run(receipt_check())
    return {
        "postgres_origin_immutable": True,
        "downgrade_requires_opt_in": True,
        "yield_receipt": "yielded",
    }
