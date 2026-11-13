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
            == "0011_rag_source_integrity"
        )
        assert await connection.scalar(text("SELECT count(*) FROM knowledge_bases")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM parse_jobs")) == 0
        from sqlalchemy import inspect

        constraints = await connection.run_sync(
            lambda sync: {fk["name"] for fk in inspect(sync).get_foreign_keys("documents")}
        )
        assert {"fk_document_active_batch", "fk_document_latest_batch"} <= constraints
    await engine.dispose()


@pytest.mark.asyncio
async def test_legacy_confirmation_is_atomic_and_provenance_fk_is_deferred():
    import hashlib

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.application.legacy_rag import LEGACY_SPACE
    from backend.application.rag_profiles import bootstrap_mock
    from backend.config import Settings
    from backend.db.models import ChunkModel, DocumentModel
    from backend.db.rag_models import IndexBuildModel, ParseJobModel
    from backend.tools.confirm_legacy_rag_space import confirm

    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(owner_id="owner", _env_file=None)
    raw = "legacy text"
    source_hash = hashlib.sha256(raw.encode()).hexdigest()
    manifest = {
        "space_id": LEGACY_SPACE.space_id,
        "provenance_reference": "trusted-deployment",
        "batches": [{"document_id": "doc", "index_batch_id": "batch", "source_hash": source_hash}],
    }
    async with factory() as session:
        await bootstrap_mock(session)
        session.add(
            KnowledgeBaseModel(
                knowledge_base_id="base",
                owner_id="owner",
                name="base",
                embedding_space_id=LEGACY_SPACE.space_id,
            )
        )
        await session.flush()
        session.add(
            DocumentModel(
                document_id="doc",
                owner_id="owner",
                knowledge_base_id="base",
                filename="old.txt",
                extension=".txt",
                source="local_upload",
                content_hash=source_hash,
                size_bytes=len(raw),
                storage_key="doc.txt",
                status="indexed",
            )
        )
        await session.flush()
        session.add(
            IndexBuildModel(
                index_batch_id="batch",
                document_id="doc",
                knowledge_base_id="base",
                embedding_snapshot={},
                chunker_snapshot={},
                state="succeeded",
                stage="completed",
                provenance="legacy_unknown",
                chunk_count=1,
            )
        )
        await session.flush()
        session.add(
            ChunkModel(
                chunk_id="chunk",
                document_id="doc",
                index_batch_id="batch",
                seq=0,
                text=raw,
                start_offset=0,
                end_offset=len(raw),
                embedding=[1.0] + [0.0] * 383,
                dimension=384,
                legacy_unverified=True,
            )
        )
        await session.commit()
        assert (await confirm(session, settings, manifest))[0]["state"] == "would_confirm"
        assert await session.scalar(select(ParseJobModel)) is None
        chunk = await session.get(ChunkModel, "chunk")
        chunk.legacy_unverified = False
        await session.flush()  # 允许事务中间态，但不能提交伪造来源。
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        with pytest.raises(ValueError):
            await confirm(
                session,
                settings,
                {
                    **manifest,
                    "batches": [
                        *manifest["batches"],
                        {**manifest["batches"][0], "document_id": "missing"},
                    ],
                },
                apply=True,
            )
        assert await session.scalar(select(ParseJobModel)) is None
        chunk = await session.get(ChunkModel, "chunk")
        assert chunk.legacy_unverified is True and chunk.space_id is None
        assert (await confirm(session, settings, manifest, apply=True))[0]["state"] == "confirmed"
        assert (await confirm(session, settings, manifest, apply=True))[0][
            "state"
        ] == "already_confirmed"
        await session.refresh(chunk)
        assert chunk.legacy_unverified is False and chunk.space_id == LEGACY_SPACE.space_id
        assert list(chunk.embedding) == [1.0] + [0.0] * 383
        chunk.legacy_unverified = True
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_from_0010_preserves_verified_and_unknown_legacy_batches(tmp_path):
    import json

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.application.legacy_rag import LEGACY_SPACE
    from backend.application.rag_profiles import bootstrap_mock
    from backend.config import Settings
    from backend.db.models import DocumentModel, utc_now
    from backend.tools.upgrade_rag_schema import upgrade

    url = f"sqlite+aiosqlite:///{tmp_path / 'legacy0010.db'}"
    engine = create_async_engine(url)

    def migrate(connection, revision):
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, revision)

    async with engine.begin() as connection:
        await connection.run_sync(lambda c: migrate(c, "0007_rag_catalog_and_profiles"))
        async with AsyncSession(bind=connection) as session:
            await bootstrap_mock(session)
            session.add(
                KnowledgeBaseModel(
                    knowledge_base_id="base",
                    owner_id="owner",
                    name="base",
                    embedding_space_id=LEGACY_SPACE.space_id,
                )
            )
            await session.flush()
        await connection.run_sync(lambda c: migrate(c, "0010_rag_task_and_run_protocol"))
    async with engine.begin() as connection:
        async with AsyncSession(bind=connection) as session:
            for identity, provenance in (
                ("verified", "legacy_verified"),
                ("unknown", "legacy_unknown"),
            ):
                session.add(
                    DocumentModel(
                        document_id=identity,
                        owner_id="owner",
                        knowledge_base_id="base",
                        filename="old.txt",
                        extension=".txt",
                        source="local_upload",
                        content_hash="h" * 64,
                        size_bytes=3,
                        storage_key=identity + ".txt",
                        status="indexed",
                    )
                )
                await session.flush()
                await session.execute(
                    text("""INSERT INTO index_builds
                    (index_batch_id,document_id,knowledge_base_id,space_id,embedding_snapshot,
                     chunker_snapshot,state,stage,provenance,chunk_count,created_at)
                    VALUES (:id,:id,'base',:space,'{}','{}','succeeded','completed',:p,1,:at)"""),
                    {
                        "id": identity,
                        "space": LEGACY_SPACE.space_id if identity == "verified" else None,
                        "p": provenance,
                        "at": utc_now().isoformat(),
                    },
                )
                await session.execute(
                    text("""INSERT INTO chunks
                    (chunk_id,document_id,index_batch_id,seq,text,start_offset,end_offset,embedding,
                     locations_json,created_at,space_id,dimension,block_segments_json,legacy_unverified)
                    VALUES (:id,:id,:id,0,'old',0,3,:v,'[]',:at,:space,384,'[]',:flag)"""),
                    {
                        "id": identity,
                        "v": json.dumps([1.0] + [0.0] * 383),
                        "at": utc_now().isoformat(),
                        "space": LEGACY_SPACE.space_id if identity == "verified" else None,
                        "flag": identity == "unknown",
                    },
                )
    await upgrade(Settings(database_url=url, _env_file=None))
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT provenance,legacy_unverified FROM index_builds ORDER BY provenance")
            )
        ).all()
        assert rows == [("legacy_unknown", 1), ("legacy_verified", 0)]
        assert await connection.scalar(text("SELECT count(*) FROM chunks")) == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_confirmation_locks_all_bases_before_documents_and_builds_in_sorted_order():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from sqlalchemy.dialects import postgresql

    from backend.db.models import DocumentModel
    from backend.tools.confirm_legacy_rag_space import _lock_confirmation_scope

    docs = {key: SimpleNamespace(document_id=key, owner_id="owner") for key in ("doc-a", "doc-b")}
    builds = {
        key: SimpleNamespace(
            index_batch_id=key, document_id="doc-" + key[-1], knowledge_base_id="base-" + key[-1]
        )
        for key in ("batch-a", "batch-b")
    }

    async def get(model, identity):
        return (docs if model is DocumentModel else builds).get(identity)

    session = SimpleNamespace(
        get=get, scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    )
    result = await _lock_confirmation_scope(
        session,
        SimpleNamespace(owner_id="owner"),
        [
            {"document_id": "doc-b", "index_batch_id": "batch-b"},
            {"document_id": "doc-a", "index_batch_id": "batch-a"},
        ],
    )
    queries = [call.args[0] for call in session.scalars.call_args_list]
    assert [query.column_descriptions[0]["entity"].__tablename__ for query in queries] == [
        "knowledge_bases",
        "documents",
        "index_builds",
    ]
    for query in queries:
        compiled = query.compile(dialect=postgresql.dialect())
        assert "FOR UPDATE" in str(compiled) and "ORDER BY" in str(compiled)
        assert query.get_execution_options()["populate_existing"] is True
        assert next(iter(compiled.params.values())) == sorted(next(iter(compiled.params.values())))
    assert result[("doc-b", "batch-b")] == "base-b"
