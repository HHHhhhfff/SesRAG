"""应用观测迁移不得改写既有 Task 的来源。"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DatabaseError

from tests.unit.test_foundation_migrations import migrate, migration_engine


def test_existing_task_is_preserved_and_origin_is_immutable():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0011_rag_source_integrity")
        connection.execute(
            text("""
            INSERT INTO tasks (task_id,kind,document_id,state,attempt,max_attempts,
                               available_at,deadline_at,generation,progress_json,
                               failure_count,created_at,updated_at)
            VALUES ('old','index_document','doc','queued',0,3,
                    CURRENT_TIMESTAMP,'2099-01-01',0,'{}',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
        """)
        )
        migrate(connection, "upgrade", "head")
        assert "trace_origin_json" in {c["name"] for c in inspect(connection).get_columns("tasks")}
        assert (
            connection.scalar(text("SELECT trace_origin_json FROM tasks WHERE task_id='old'"))
            is None
        )
        with pytest.raises(DatabaseError):
            connection.execute(text("UPDATE tasks SET trace_origin_json='{}' WHERE task_id='old'"))


@pytest.mark.asyncio
async def test_upgrade_entry_advances_existing_0011_and_is_repeatable(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.config import Settings
    from backend.tools.upgrade_rag_schema import upgrade

    url = f"sqlite+aiosqlite:///{tmp_path / 'upgrade.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: migrate(sync, "upgrade", "0011_rag_source_integrity")
        )
    settings = Settings(database_url=url, _env_file=None)
    await upgrade(settings)
    await upgrade(settings)
    async with engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0012_task_trace_origin"
        )
    await engine.dispose()
