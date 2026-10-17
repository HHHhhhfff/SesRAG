"""由根Compose的API/Worker环境启动，观察真实快照、切分与召回消费。"""

import asyncio
import json
import os

from alembic import command
from alembic.config import Config
from pg_document_scenarios import document, read_index
from pg_harness import Harness
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# 导入实际启动模块，非法环境必须在这里被Settings拒绝。
import backend.app  # noqa: F401
import backend.workers.main  # noqa: F401
from backend.config import Settings


async def main():
    settings = Settings()
    actual = {
        key: getattr(settings, key)
        for key in ("vector_dimension", "rag_top_k", "chunk_size", "chunk_overlap")
    }
    assert actual == dict(vector_dimension=384, rag_top_k=1, chunk_size=96, chunk_overlap=8), actual
    token = os.environ["PG_SCENARIO_TOKEN"]
    assert len(token) == 8 and all(c in "0123456789abcdef" for c in token)
    url = make_url(settings.database_url)
    database = "sesrag_config_" + token
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {database}"))
    finally:
        admin.dispose()
    url = url.set(database=database).render_as_string(hide_password=False)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            config = Config("alembic.ini")
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
    finally:
        engine.dispose()
    h = Harness(url, **actual)
    try:
        ids = await document(h, b"alpha " * 40)
        await h.worker().run_once()
        indexed = await read_index(h, ids)
        assert indexed["task"]["state"] == "succeeded"
        assert indexed["document"]["status"] == "indexed"
        assert len(indexed["chunks"]) == 3
        assert [c["start_offset"] for c in indexed["chunks"]] == [0, 88, 176]
        run_ids = await h.seed()
        await h.worker().run_once()
        facts = await h.facts(run_ids)
        assert facts["run"]["status"] == "succeeded"
        assert facts["run"]["snapshot_json"]["retrieval"]["top_k"] == 1
        assert facts["run"]["snapshot_json"]["vector_dimension"] == 384
        assistant = [m for m in facts["messages"] if m["role"] == "assistant"]
        assert len(assistant) == 1 and len(assistant[0]["citations"]) == 1
        print(
            "COMPOSE_RAG:"
            + json.dumps(
                {
                    "settings": actual,
                    "database": database,
                    "chunk_offsets": [c["start_offset"] for c in indexed["chunks"]],
                    "run_status": facts["run"]["status"],
                    "snapshot_top_k": 1,
                    "citations": 1,
                }
            )
        )
    finally:
        await h.close()


if __name__ == "__main__":
    asyncio.run(main())
