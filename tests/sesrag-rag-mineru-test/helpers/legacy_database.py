"""CMP迁移专用旧库：真实Alembic和反射夹具；永不连接开发数据库。"""

import asyncio
import hashlib
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from helpers.fixture_admin import FixtureAdmin

from backend.config import Settings
from backend.db.models import utc_now


class LegacyDatabase:
    def __init__(self, case):
        self.case = case
        self.admin = FixtureAdmin()
        self.key = case.case_id + "_LEGACY_" + uuid4().hex[:12].upper()
        self.url = self.admin.create_database(self.key)
        self.engine = sa.create_engine(self.url)
        self.temp = tempfile.TemporaryDirectory(prefix=case.case_id + "-", dir="/data/scratch")
        self.root = Path(self.temp.name)
        self.settings = Settings(
            database_url=self.url.render_as_string(hide_password=False),
            owner_id="rag-test-owner-a",
            upload_dir=str(self.root / "uploads"),
            rag_artifact_dir=str(self.root / "artifacts"),
            rag_tmp_dir=str(self.root / "tmp"),
            redis_enabled=False,
            _env_file=None,
        )
        self.settings.upload_path.mkdir(parents=True)

    def __enter__(self):
        self.migrate("0006_v2_run_guards")
        self.case.note("准备", "本例独占PG；正式Alembic至0006；旧数据为显式迁移夹具")
        return self

    def __exit__(self, *_):
        self.engine.dispose()
        self.admin.drop_database(self.key)
        self.temp.cleanup()

    def migrate(self, revision="head", *, downgrade=False):
        config = Config("alembic.ini")
        with self.engine.begin() as conn:
            config.attributes["connection"] = conn
            (command.downgrade if downgrade else command.upgrade)(config, revision)

    def sql(self, sql, params=None):
        with self.engine.begin() as conn:
            result = conn.execute(sa.text(sql), params or {})
            return [dict(r) for r in result.mappings()] if result.returns_rows else []

    def insert(self, table_name, **values):
        with self.engine.begin() as conn:
            table = sa.Table(table_name, sa.MetaData(), autoload_with=conn)
            conn.execute(table.insert().values(**{k: v for k, v in values.items() if k in table.c}))

    def seed(self, extension=".txt", *, owner=None, lease=False, citations=False):
        now = utc_now()
        doc, batch, chunk, task = (str(uuid4()) for _ in range(4))
        raw = b"Legacy ALPHA 37"
        self.insert(
            "documents",
            document_id=doc,
            owner_id=owner or self.settings.owner_id,
            filename="legacy" + extension,
            extension=extension,
            source="local_upload",
            size_bytes=len(raw),
            content_hash=hashlib.sha256(raw).hexdigest(),
            storage_key=doc + extension,
            status="indexed",
            active_index_batch_id=batch,
            created_at=now,
            updated_at=now,
        )
        (self.settings.upload_path / (doc + extension)).write_bytes(raw)
        self.sql(
            (
                "INSERT INTO chunks (chunk_id,document_id,index_batch_id,seq,text,"
                "start_offset,end_offset,embedding,locations_json,created_at) VALU"
                "ES (:c,:d,:b,0,:t,0,:n,CAST(:v AS vector),'[]',:at)"
            ),
            {
                "c": chunk,
                "d": doc,
                "b": batch,
                "t": raw.decode(),
                "n": len(raw),
                "v": str([1.0] + [0.0] * 383),
                "at": now,
            },
        )
        self.insert(
            "tasks",
            task_id=task,
            kind="index_document",
            document_id=doc,
            state="running" if lease else "queued",
            attempt=1 if lease else 0,
            generation=1 if lease else 0,
            max_attempts=3,
            worker_id="old-worker" if lease else None,
            lease_expires_at=now + timedelta(minutes=2) if lease else None,
            available_at=now,
            deadline_at=now + timedelta(minutes=10),
            progress_json={"index_batch_id": batch},
            created_at=now,
            updated_at=now,
        )
        if citations:
            thread, branch, message = (str(uuid4()) for _ in range(3))
            self.insert(
                "threads",
                thread_id=thread,
                owner_id=self.settings.owner_id,
                title="旧引用",
                next_message_seq=1,
                conversation_version=1,
                created_at=now,
                updated_at=now,
            )
            self.insert(
                "branches",
                branch_id=branch,
                thread_id=thread,
                name="默认分支",
                is_default=True,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.insert(
                "messages",
                message_id=message,
                thread_id=thread,
                branch_id=branch,
                seq=1,
                role="assistant",
                source="assistant_generation",
                content="Legacy answer",
                status="completed",
                citations_json=[
                    {"document_id": doc, "index_batch_id": batch, "chunk_id": chunk},
                    {"document_id": doc, "index_batch_id": batch, "chunk_id": str(uuid4())},
                ],
                created_at=now,
            )
        self.identity = {
            "document_id": doc,
            "index_batch_id": batch,
            "chunk_id": chunk,
            "task_id": task,
            "source_hash": hashlib.sha256(raw).hexdigest(),
        }
        return self.identity

    def upgrade(self, *, bootstrap=True):
        from helpers.common import SUITE, load, write

        from backend.tools.upgrade_rag_schema import upgrade

        if bootstrap:
            path = self.root / "bootstrap.json"
            write(
                path,
                {
                    "profiles": load(SUITE / "fixtures/profiles.local.json"),
                    "default_embedding": {"profile_id": "mock-embedding", "version": 1},
                },
            )
            self.settings.rag_bootstrap_config = str(path)
        asyncio.run(upgrade(self.settings))

    def confirm(self, *, apply=False, **changes):
        from backend.application.legacy_rag import LEGACY_SPACE
        from backend.db.session import create_engine, create_session_factory
        from backend.tools.confirm_legacy_rag_space import confirm

        payload = {
            "space_id": LEGACY_SPACE.space_id,
            "provenance_reference": "本轮固定旧Mock384迁移夹具",
            "batches": [
                {k: self.identity[k] for k in ("document_id", "index_batch_id", "source_hash")}
            ],
        }
        payload.update(changes)

        async def execute():
            engine = create_engine(self.settings)
            try:
                async with create_session_factory(engine)() as session:
                    return await confirm(session, self.settings, payload, apply=apply)
            finally:
                await engine.dispose()

        return asyncio.run(execute())
