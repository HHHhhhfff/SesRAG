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
