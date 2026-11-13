"""本轮接口及本地入库闭环；不调用旧PRD正式验收套件。"""

from datetime import timedelta

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.application.rag_gc import collect
from backend.config import Settings
from backend.db.models import utc_now
from backend.db.rag_models import RetrievalExecutionModel
from backend.workers.runtime import WorkerRuntime


def test_local_upload_publish_rebuild_and_office_consent_boundary(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'rag.db'}",
        upload_dir=str(tmp_path / "uploads"),
        rag_artifact_dir=str(tmp_path / "artifacts"),
        rag_tmp_dir=str(tmp_path / "tmp"),
        auto_create_schema=True,
        redis_enabled=False,
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        payload = {
            "name": "知识库",
            "embedding_profile_id": "mock-embedding",
            "embedding_profile_version": 1,
        }
        first = client.post(
            "/api/v3/knowledge-bases", json=payload, headers={"Idempotency-Key": "kb"}
        )
        assert first.status_code == 201, first.text
        base = first.json()["knowledge_base_id"]
        repeated = client.post(
            "/api/v3/knowledge-bases", json=payload, headers={"Idempotency-Key": "kb"}
        )
        assert repeated.status_code == 200 and repeated.json()["knowledge_base_id"] == base
        result = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={
                "file": ("sample.md", "# 标题\n\n本机文本RAG测试资料。".encode(), "text/markdown")
            },
            headers={"Idempotency-Key": "upload"},
        )
        assert result.status_code == 202, result.text
        document = result.json()
        batch = document["latest_build"]["index_batch_id"]
        runtime = WorkerRuntime(settings, app.state.session_factory, app.state.notifier)
        for _ in range(8):
            client.portal.call(runtime.run_once)
            state = client.get(f"/api/v3/index-builds/{batch}").json()
            if state["state"] in {"succeeded", "failed"}:
                break
        assert state["state"] == "succeeded", state
        assert state["parse"]["parser_kind"] == "local"
        chunks = client.get(
            f"/api/v3/documents/{document['document_id']}/chunks", params={"index_batch_id": batch}
        )
        assert chunks.status_code == 200 and "本机文本" in chunks.json()["items"][0]["text"]
        diagnostic = client.post(
            "/api/v3/retrieval-executions",
            json={
                "query": "本机文本RAG",
                "knowledge_base_id": base,
            },
            headers={"Idempotency-Key": "diagnostic"},
        )
        assert diagnostic.status_code == 202, diagnostic.text
        execution = diagnostic.json()["execution_id"]
        client.portal.call(runtime.run_once)
        observed = client.get(f"/api/v3/retrieval-executions/{execution}")
        assert observed.status_code == 200, observed.text
        assert observed.json()["state"] == "succeeded", observed.text
        assert observed.json()["bundle_ids"]
        evidence = client.get("/api/v3/evidence-bundles/" + observed.json()["bundle_ids"][0])
        assert evidence.status_code == 200 and "本机文本" in evidence.json()["text"], evidence.text
        empty = client.post(
            "/api/v3/retrieval-executions",
            json={
                "query": "本机文本",
                "knowledge_base_id": base,
                "filters": {"document_ids": []},
            },
            headers={"Idempotency-Key": "empty"},
        )
        assert empty.status_code == 202, empty.text
        client.portal.call(runtime.run_once)
        assert (
            client.get("/api/v3/retrieval-executions/" + empty.json()["execution_id"]).json()[
                "mode"
            ]
            == "empty"
        )
        office = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={"file": ("sample.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
            headers={"Idempotency-Key": "office"},
        )
        assert office.status_code == 422 and office.json()["code"] == "CLOUD_CONSENT_REQUIRED"
        old = client.post(
            "/api/v1/documents", files={"file": ("old.docx", b"fake", "application/octet-stream")}
        )
        assert old.status_code == 409 and old.json()["code"] == "DOCUMENT_WRITE_UPGRADE_REQUIRED"

        async def age_diagnostic():
            async with app.state.session_factory() as session:
                row = await session.get(RetrievalExecutionModel, execution)
                row.created_at = utc_now() - timedelta(days=8)
                await session.commit()
            return await collect(app.state.session_factory, settings, apply=True)

        report = client.portal.call(age_diagnostic)
        assert any(
            r.get("execution_id") == execution and r["action"] == "delete"
            for r in report["resources"]
        )
        assert client.get(f"/api/v3/retrieval-executions/{execution}").status_code == 410
        assert (
            client.get("/api/v3/evidence-bundles/" + observed.json()["bundle_ids"][0]).status_code
            == 410
        )
        assert (
            client.get("/api/v3/documents/" + document["document_id"]).json()["availability"]
            == "ready"
        )


def test_http_chunk_policy_rejects_coercion_without_creating_candidate(tmp_path):
    from sqlalchemy import func, select

    from backend.db.rag_models import IndexBuildModel

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'strict.db'}",
        upload_dir=str(tmp_path / "uploads"),
        rag_artifact_dir=str(tmp_path / "artifacts"),
        rag_tmp_dir=str(tmp_path / "tmp"),
        auto_create_schema=True,
        redis_enabled=False,
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        base = client.post(
            "/api/v3/knowledge-bases",
            json={
                "name": "strict",
                "embedding_profile_id": "mock-embedding",
                "embedding_profile_version": 1,
            },
            headers={"Idempotency-Key": "strict-base"},
        ).json()["knowledge_base_id"]
        doc = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={"file": ("strict.txt", b"hello world", "text/plain")},
            headers={"Idempotency-Key": "strict-upload"},
        ).json()

        async def count():
            async with app.state.session_factory() as session:
                return await session.scalar(select(func.count()).select_from(IndexBuildModel))

        async def emulate_old_default_operation():
            import hashlib

            from backend.db.rag_models import RagOperationModel
            from backend.domain.rag import ParseRequest, digest

            old_chunker = {"mode": "structure_v1", "size": 800, "overlap": 120}
            async with app.state.session_factory() as session:
                operation = await session.scalar(
                    select(RagOperationModel).where(
                        RagOperationModel.idempotency_key == "strict-upload"
                    )
                )
                operation.request_hash = digest(
                    {
                        "base": base,
                        "filename": "strict.txt",
                        "hash": hashlib.sha256(b"hello world").hexdigest(),
                        "tags": [],
                        "parse": ParseRequest().model_dump(),
                        "chunker": old_chunker,
                    }
                )
                build = await session.get(IndexBuildModel, doc["latest_build"]["index_batch_id"])
                build.chunker_snapshot = old_chunker
                session.add(
                    RagOperationModel(
                        operation_id="old-operation",
                        owner_id=settings.owner_id,
                        scope="build:" + doc["document_id"],
                        idempotency_key="old-build",
                        request_hash=digest(
                            {
                                "document_id": doc["document_id"],
                                "parse": ParseRequest().model_dump(),
                                "chunker": old_chunker,
                            }
                        ),
                        result_json={"index_batch_id": build.index_batch_id},
                    )
                )
                await session.commit()

        client.portal.call(emulate_old_default_operation)
        replayed = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={"file": ("strict.txt", b"hello world", "text/plain")},
            headers={"Idempotency-Key": "strict-upload"},
        )
        assert replayed.status_code == 200, replayed.text
        for key in ("old-build", "new-default-build"):
            replayed = client.post(
                f"/api/v3/documents/{doc['document_id']}/index-builds",
                json={},
                headers={"Idempotency-Key": key},
            )
            assert replayed.status_code in (200, 202), replayed.text
            assert replayed.json()["index_batch_id"] == doc["latest_build"]["index_batch_id"]
        changed = client.post(
            f"/api/v3/documents/{doc['document_id']}/index-builds",
            json={"chunker": {"max_chunks": 128}},
            headers={"Idempotency-Key": "old-build"},
        )
        assert changed.status_code == 409 and changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
        before = client.portal.call(count)
        for field in ("size", "overlap", "max_chunks"):
            for value in (True, False, "1", 1.0):
                response = client.post(
                    f"/api/v3/documents/{doc['document_id']}/index-builds",
                    json={"chunker": {field: value}},
                    headers={"Idempotency-Key": f"{field}-{value}"},
                )
                assert response.status_code == 422, response.text
        assert client.portal.call(count) == before
        runtime = WorkerRuntime(settings, app.state.session_factory, app.state.notifier)
        for _ in range(8):
            client.portal.call(runtime.run_once)
            original = client.get(
                "/api/v3/index-builds/" + doc["latest_build"]["index_batch_id"]
            ).json()
            if original["state"] in {"succeeded", "failed"}:
                break
        assert original["state"] == "succeeded", original
        capped = client.post(
            f"/api/v3/documents/{doc['document_id']}/index-builds",
            json={"chunker": {"size": 1, "overlap": 0, "max_chunks": 1}},
            headers={"Idempotency-Key": "capped"},
        ).json()
        from unittest.mock import patch

        from backend.infrastructure.providers.rag_registry import MockEmbeddingV2

        with patch.object(
            MockEmbeddingV2, "embed", side_effect=AssertionError("unexpected embedding")
        ) as embed:
            for _ in range(8):
                client.portal.call(runtime.run_once)
                failed = client.get("/api/v3/index-builds/" + capped["index_batch_id"]).json()
                if failed["state"] in {"succeeded", "failed"}:
                    break
            embed.assert_not_called()
        assert failed["state"] == "failed" and failed["error_code"] == "CHUNK_COUNT_LIMIT", failed
        observed = client.get("/api/v3/documents/" + doc["document_id"]).json()
        assert observed["active_index_batch_id"] == original["index_batch_id"]

        async def candidate_count():
            from backend.db.models import ChunkModel

            async with app.state.session_factory() as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(ChunkModel)
                    .where(ChunkModel.index_batch_id == capped["index_batch_id"])
                )

        assert client.portal.call(candidate_count) == 0


def test_multipart_upload_enforces_frozen_chunk_budget_before_embedding(tmp_path):
    import json
    from unittest.mock import patch

    from sqlalchemy import func, select

    from backend.db.models import DocumentModel
    from backend.db.rag_models import IndexBuildModel
    from backend.infrastructure.providers.rag_registry import MockEmbeddingV2

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'uploadcap.db'}",
        upload_dir=str(tmp_path / "uploads"),
        rag_artifact_dir=str(tmp_path / "artifacts"),
        rag_tmp_dir=str(tmp_path / "tmp"),
        auto_create_schema=True,
        redis_enabled=False,
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        base = client.post(
            "/api/v3/knowledge-bases",
            json={
                "name": "uploadcap",
                "embedding_profile_id": "mock-embedding",
                "embedding_profile_version": 1,
            },
            headers={"Idempotency-Key": "base"},
        ).json()["knowledge_base_id"]

        async def counts():
            async with app.state.session_factory() as session:
                return tuple(
                    [
                        await session.scalar(select(func.count()).select_from(model))
                        for model in (DocumentModel, IndexBuildModel)
                    ]
                )

        before = client.portal.call(counts)
        invalid = ["{", "[]", "null", '{"unknown":1}', '{"size":1,"overlap":1}', " " * 4097] + [
            json.dumps({"max_chunks": value}) for value in (True, "1", 1.0, 0, 50001)
        ]

        for number, policy in enumerate(invalid):
            rejected = client.post(
                "/api/v3/documents",
                data={"knowledge_base_id": base, "chunker": policy},
                files={"file": ("cap.txt", b"abcdef", "text/plain")},
                headers={"Idempotency-Key": f"bad-{number}"},
            )
            assert rejected.status_code == 422, rejected.text
        assert client.portal.call(counts) == before
        uploaded = client.post(
            "/api/v3/documents",
            data={
                "knowledge_base_id": base,
                "chunker": json.dumps({"size": 1, "overlap": 0, "max_chunks": 2}),
            },
            files={"file": ("cap.txt", b"abcdef", "text/plain")},
            headers={"Idempotency-Key": "cap"},
        )
        assert uploaded.status_code == 202, uploaded.text
        batch = uploaded.json()["latest_build"]["index_batch_id"]

        async def snapshot():
            async with app.state.session_factory() as session:
                return (await session.get(IndexBuildModel, batch)).chunker_snapshot

        assert client.portal.call(snapshot)["max_chunks"] == 2
        runtime = WorkerRuntime(settings, app.state.session_factory, app.state.notifier)
        with patch.object(
            MockEmbeddingV2, "embed", side_effect=AssertionError("embedding forbidden")
        ) as embed:
            for _ in range(8):
                client.portal.call(runtime.run_once)
                state = client.get("/api/v3/index-builds/" + batch).json()
                if state["state"] in {"failed", "succeeded"}:
                    break
            embed.assert_not_called()
        assert state["state"] == "failed" and state["error_code"] == "CHUNK_COUNT_LIMIT", state
