"""SQL编译门禁：同空间集合必须先物化再距离排序；不代替真实PG运行证据。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from backend.domain.rag import FrozenScope
from backend.infrastructure.rag.vector_search import VectorSearch


@pytest.mark.asyncio
async def test_postgres_scope_materializes_before_distance_and_limits_results():
    session = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        get=AsyncMock(return_value=SimpleNamespace(dimension=2)),
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )
    scope = FrozenScope("view", "owner", "base", "space", ("batch",), "hash")
    await VectorSearch(session).search(scope, [0.3, 0.4], 20)
    query = session.execute.call_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "AS MATERIALIZED" in sql and "scoped.embedding" in sql
    assert "<=>" in sql and "ORDER BY" in sql and "LIMIT" in sql
    assert "documents.owner_id" in sql and "chunks.dimension" in sql
    assert "index_builds.state" in sql and "chunks.space_id" in sql
