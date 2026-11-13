"""仅容器内的PRD-003探针；真实PG约束／SQL／API／Worker，不调用外部付费服务。"""

import asyncio
import json
import os
import time
from uuid import uuid4

import httpx
from sqlalchemy import event, select, text
from sqlalchemy.exc import DBAPIError

from backend.application.rag_gc import collect
from backend.application.rag_profiles import import_profiles
from backend.application.retrieval_views import load_scope
from backend.config import Settings
from backend.db.models import ChunkModel
from backend.db.rag_models import RetrievalExecutionModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.rag.pgvector_store import cosine_similarity
from backend.infrastructure.rag.vector_search import VectorSearch


def wait(client, path, field, terminal):
    for _ in range(180):
        response = client.get(path)
        assert response.status_code == 200, response.text
        row = response.json()
        if row[field] in terminal:
            assert row[field] == "succeeded", row
            return row
        time.sleep(0.5)
    raise AssertionError("本地任务超过90秒")


async def database_checks(execution_id):
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    sql = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        sql.append(statement)

    try:
        async with factory() as session:
            execution = await session.get(RetrievalExecutionModel, execution_id)
            scope = await load_scope(session, settings, execution.view_id)
            rows = (
                await session.scalars(
                    select(ChunkModel).where(ChunkModel.index_batch_id.in_(scope.batches))
                )
            ).all()
            vector = list(rows[0].embedding)
            expected = sorted(
                rows,
                key=lambda c: (
                    -cosine_similarity(vector, list(c.embedding)),
                    c.document_id,
                    c.index_batch_id,
                    c.seq,
                    c.chunk_id,
                ),
            )[:20]
            hits = await VectorSearch(session).search(scope, vector, 20)
            assert [h.chunk_id for h in hits] == [c.chunk_id for c in expected]
            assert any("<=>" in s and "LIMIT" in s and "ORDER BY" in s for s in sql)
            version = await session.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "0011_rag_source_integrity"
            dimensions = (
                (
                    await session.execute(
                        text(
                            "SELECT DISTINCT vector_dims(embedding) FROM chunks "
                            "WHERE embedding IS NOT NULL"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert set(dimensions) == {384, 1024}
        blocked = 0
        for statement in (
            "UPDATE embedding_spaces SET dimension=3",
            "UPDATE knowledge_bases SET embedding_space_id='forged'",
            "UPDATE runs SET snapshot_json='{}' WHERE execution_schema_version=3",
            "DELETE FROM run_events",
            "UPDATE chunks SET text='forged'",
            "UPDATE documents SET active_index_batch_id='not-a-batch' "
            "WHERE active_index_batch_id IS NOT NULL",
            "UPDATE documents SET latest_index_batch_id='not-a-batch' "
            "WHERE latest_index_batch_id IS NOT NULL",
        ):
            try:
                async with engine.begin() as connection:
                    await connection.execute(text(statement))
            except DBAPIError:
                blocked += 1
        assert blocked == 7, blocked
        gc = await collect(factory, settings)
        return {
            "pgvector_version": version,
            "migration": revision,
            "sql_topk_matches_independent_cosine": True,
            "immutability_guards": blocked,
            "gc_dry_run": gc["apply"] is False,
            "isolated_vector_dimensions": sorted(dimensions),
        }
    finally:
        await engine.dispose()


async def prepare_second_space():
    engine = create_engine(Settings())
    try:
        async with create_session_factory(engine)() as session:
            await import_profiles(
                session,
                [
                    {
                        "kind": "embedding",
                        "profile_id": "probe-1024",
                        "version": 1,
                        "config": {
                            "space": {
                                "provider": "mock",
                                "model": "probe-1024",
                                "revision": "isolated_fixture_v1",
                                "dimension": 1024,
                            }
                        },
                    }
                ],
            )
            await session.commit()
    finally:
        await engine.dispose()


def main():
    marker = os.getenv("RAG_ISOLATION_MARKER", "")
    if not marker.startswith("sesrag-rag-check-") or not os.path.exists("/.dockerenv"):
        raise SystemExit("拒绝：只允许专用Compose容器及隔离marker，不接受开发数据库")
    with httpx.Client(base_url="http://localhost:8000", timeout=15) as client:
        base = client.get("/api/v3/knowledge-bases").json()["items"][0]["knowledge_base_id"]
        uploads = []
        for suffix in ("txt", "md"):
            response = client.post(
                "/api/v3/documents",
                data={"knowledge_base_id": base},
                files={
                    "file": (
                        "probe." + suffix,
                        ("# Database\n\nSesRAG uses PostgreSQL and pgvector.\n\n" * 40).encode(),
                        "text/plain",
                    )
                },
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == 202, response.text
            doc = response.json()
            wait(
                client,
                "/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"],
                "state",
                {"succeeded", "failed", "cancelled"},
            )
            uploads.append(doc)
        office = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={"file": ("probe.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert office.status_code == 422 and office.json()["code"] == "CLOUD_CONSENT_REQUIRED"
        thread = client.post("/api/v2/threads", json={"title": "PRD-003隔离验证"}).json()
        response = client.post(
            f"/api/v3/threads/{thread['thread_id']}/messages",
            json={
                "content": "Which database is used?",
                "branch_id": thread["default_branch_id"],
                "expected_version": 0,
                "rag": {"enabled": True, "knowledge_base_id": base},
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
        run = wait(
            client,
            "/api/v3/runs/" + response.json()["run_id"],
            "status",
            {"succeeded", "failed", "cancelled"},
        )
        journal = client.get(f"/api/v3/runs/{run['run_id']}/events").json()["events"]
        assert [e["seq"] for e in journal] == list(range(1, len(journal) + 1))
        assert journal[-2]["type"] == "message.completed" and journal[-1]["type"] == "run.succeeded"
        assert journal[-2]["data"]["citations"][0]["context_evidence_ids"]
        stream = client.get(f"/api/v3/runs/{run['run_id']}/events/stream", params={"after_seq": 0})
        assert "event: message.completed" in stream.text
        assert client.get(f"/api/v2/runs/{run['run_id']}").status_code == 409
        result = client.post(
            "/api/v3/retrieval-executions",
            json={
                "query": "PostgreSQL",
                "knowledge_base_id": base,
                "overrides": {"rerank_enabled": True},
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert result.status_code == 202, result.text
        execution = wait(
            client,
            "/api/v3/retrieval-executions/" + result.json()["execution_id"],
            "state",
            {"succeeded", "failed", "cancelled"},
        )
        bundle_id = execution["bundle_ids"][0]
        old_evidence = client.get("/api/v3/evidence-bundles/" + bundle_id).json()
        rebuild = client.post(
            f"/api/v3/documents/{uploads[0]['document_id']}/index-builds",
            json={},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert rebuild.status_code == 202, rebuild.text
        wait(
            client,
            "/api/v3/index-builds/" + rebuild.json()["index_batch_id"],
            "state",
            {"succeeded", "failed", "cancelled"},
        )
        assert client.get("/api/v3/evidence-bundles/" + bundle_id).json() == old_evidence
        legacy = client.post(
            "/api/v1/documents",
            files={"file": ("legacy.txt", b"PostgreSQL compatibility source", "text/plain")},
        )
        assert legacy.status_code == 201, legacy.text
        for _ in range(180):
            legacy_doc = client.get("/api/v3/documents/" + legacy.json()["document_id"]).json()
            if legacy_doc["availability"] == "ready":
                break
            time.sleep(0.5)
        else:
            raise AssertionError("旧文本入口发布未完成")
        legacy_diagnostic = client.post(
            "/api/v3/retrieval-executions",
            json={
                "query": "PostgreSQL",
                "knowledge_base_id": base,
                "filters": {"document_ids": [legacy_doc["document_id"]]},
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert legacy_diagnostic.status_code == 202, legacy_diagnostic.text
        legacy_result = wait(
            client,
            "/api/v3/retrieval-executions/" + legacy_diagnostic.json()["execution_id"],
            "state",
            {"succeeded", "failed", "cancelled"},
        )
        legacy_bundle = client.get("/api/v3/evidence-bundles/" + legacy_result["bundle_ids"][0])
        assert legacy_bundle.json()["text"] == "PostgreSQL compatibility source"
        asyncio.run(prepare_second_space())
        other_base = client.post(
            "/api/v3/knowledge-bases",
            json={
                "name": "隔离1024维空间",
                "embedding_profile_id": "probe-1024",
                "embedding_profile_version": 1,
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert other_base.status_code == 201, other_base.text
        vector_input = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": other_base.json()["knowledge_base_id"]},
            files={"file": ("other.txt", b"isolated nonlegacy space", "text/plain")},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert vector_input.status_code == 202, vector_input.text
        wait(
            client,
            "/api/v3/index-builds/" + vector_input.json()["latest_build"]["index_batch_id"],
            "state",
            {"succeeded", "failed", "cancelled"},
        )
        # 模拟浏览器通过本机入口访问；不要用容器DNS名绕过Vite的Host防护。
        frontend = client.get("http://frontend:5173", headers={"Host": "localhost:5173"})
        assert frontend.status_code == 200 and 'id="app"' in frontend.text, frontend.text
        proxy = client.get(
            "http://frontend:5173/api/v3/rag/profiles", headers={"Host": "localhost:5173"}
        )
        assert proxy.status_code == 200 and proxy.json()["items"]
        report = {
            "local_formats": ["txt", "md"],
            "mineru_disabled": True,
            "run_context_citations_sse": "passed",
            "history_after_rebuild": "passed",
            "legacy_upload_v3_retrieval": "passed",
            "frontend_proxy_container": "passed",
            "database": asyncio.run(database_checks(execution["execution_id"])),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
