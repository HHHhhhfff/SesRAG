"""PRD-003：元数据身份与不可变配置约束。"""

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.base import Base
from backend.db.rag_models import EmbeddingSpaceModel, KnowledgeBaseModel


def test_revision_identifiers_fit_alembic_postgres_version_column():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    revisions = ScriptDirectory.from_config(Config("alembic.ini")).walk_revisions()
    assert all(len(revision.revision) <= 32 for revision in revisions)


@pytest.mark.asyncio
async def test_catalog_enforces_owner_name_and_space_reference():
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            EmbeddingSpaceModel.__table__.insert().values(
                space_id="s",
                descriptor_hash="h",
                descriptor_json={"dimension": 2},
                dimension=2,
            )
        )
        await connection.execute(
            KnowledgeBaseModel.__table__.insert().values(
                knowledge_base_id="k",
                owner_id="a",
                name="库",
                embedding_space_id="s",
            )
        )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                KnowledgeBaseModel.__table__.insert().values(
                    knowledge_base_id="k2",
                    owner_id="a",
                    name="库",
                    embedding_space_id="s",
                )
            )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                KnowledgeBaseModel.__table__.insert().values(
                    knowledge_base_id="k3",
                    owner_id="a",
                    name="另一个库",
                    embedding_space_id="absent",
                )
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_empty_database_runs_actual_four_migrations_and_repeated_upgrade(tmp_path):
    from sqlalchemy import text

    from backend.config import Settings
    from backend.tools.upgrade_rag_schema import upgrade

    url = f"sqlite+aiosqlite:///{tmp_path / 'upgrade.db'}"
    settings = Settings(database_url=url, _env_file=None)
    await upgrade(settings)
    await upgrade(settings)
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        assert (
            await connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0010_rag_task_and_run_protocol"
        )
        assert await connection.scalar(text("SELECT count(*) FROM knowledge_bases")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM parse_jobs")) == 0
        from sqlalchemy import inspect

        constraints = await connection.run_sync(
            lambda sync: {fk["name"] for fk in inspect(sync).get_foreign_keys("documents")}
        )
        assert {"fk_document_active_batch", "fk_document_latest_batch"} <= constraints
    await engine.dispose()
