"""schema3事务、工具事实、实际引用与旧客户端边界。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository
from backend.workers.runtime import WorkerRuntime


def test_schema3_run_tool_context_and_explicit_regeneration(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'run.db'}",
        redis_enabled=False,
        auto_create_schema=True,
        upload_dir=str(tmp_path / "uploads"),
        rag_artifact_dir=str(tmp_path / "artifacts"),
        rag_tmp_dir=str(tmp_path / "tmp"),
        _env_file=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def seed_model():
            profiles = json.loads(
                Path("docker/model-profiles.example.json").read_text(encoding="utf-8")
            )
            async with app.state.session_factory() as session:
                await SQLModelProfileRepository(session).import_profiles(
                    [p for p in profiles if p["provider_kind"] == "mock"]
                )

        client.portal.call(seed_model)
        base = client.post(
            "/api/v3/knowledge-bases",
            headers={"Idempotency-Key": "kb"},
            json={
                "name": "测试库",
                "embedding_profile_id": "mock-embedding",
                "embedding_profile_version": 1,
            },
        ).json()["knowledge_base_id"]
        upload = client.post(
            "/api/v3/documents",
            data={"knowledge_base_id": base},
            files={
                "file": ("data.txt", "项目使用PostgreSQL和pgvector数据库。".encode(), "text/plain")
            },
            headers={"Idempotency-Key": "file"},
        ).json()
        runtime = WorkerRuntime(settings, app.state.session_factory, app.state.notifier)
        for _ in range(4):
            client.portal.call(runtime.run_once)
        assert (
            client.get("/api/v3/documents/" + upload["document_id"]).json()["availability"]
            == "ready"
        )
        thread = client.post("/api/v2/threads", json={"title": "schema3"}).json()
        identity, branch = thread["thread_id"], thread["default_branch_id"]
        sent = client.post(
            f"/api/v3/threads/{identity}/messages",
            headers={"Idempotency-Key": "msg"},
            json={
                "branch_id": branch,
                "expected_version": 0,
                "content": "项目用什么数据库？",
                "rag": {"enabled": True, "knowledge_base_id": base},
            },
        )
        assert sent.status_code == 201, sent.text
        run_id = sent.json()["run_id"]
        client.portal.call(runtime.run_once)
        detail = client.get("/api/v3/runs/" + run_id)
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "succeeded", detail.text
        assert detail.json()["execution_schema_version"] == 3
        assert detail.json()["rag_summary"]["execution_state"] == "completed"
        assert detail.json()["rag_summary"]["result_mode"] == "ok"
        events = client.get(f"/api/v3/runs/{run_id}/events")
        assert events.status_code == 200, events.text
        types = [e["type"] for e in events.json()["events"]]
        assert "tool.started" in types and "tool.completed" in types
        assert types[-2:] == ["message.completed", "run.succeeded"]
        context = client.get(f"/api/v3/runs/{run_id}/context")
        assert context.status_code == 200, context.text
        assert context.json()["plan"]["selected_evidence"][0]["context_evidence_ids"]
        recovered = client.get(f"/api/v3/threads/{identity}")
        assert recovered.status_code == 200, recovered.text
        assistant = next(m for m in recovered.json()["messages"] if m["role"] == "assistant")
        assert (
            assistant["citation_schema_version"] == 2
            and assistant["citations"][0]["context_evidence_ids"]
        )
        assert client.get(f"/api/v2/threads/{identity}").status_code == 409
        assert client.get(f"/api/v2/runs/{run_id}").status_code == 409
        related = client.post(
            f"/api/v3/runs/{run_id}/regenerate", json={}, headers={"Idempotency-Key": "regen"}
        )
        assert related.status_code == 201, related.text
        next_detail = client.get("/api/v3/runs/" + related.json()["run_id"]).json()
        assert next_detail["rag_summary"]["view_id"] == detail.json()["rag_summary"]["view_id"]
        old_thread = client.post("/api/v2/threads", json={"title": "old protocol"}).json()
        old_run = client.post(
            f"/api/v2/threads/{old_thread['thread_id']}/messages",
            headers={"Idempotency-Key": "old-message"},
            json={
                "branch_id": old_thread["default_branch_id"],
                "expected_version": 0,
                "content": "legacy question",
            },
        ).json()
        client.post(f"/api/v3/runs/{old_run['run_id']}/cancel")
        refused = client.post(
            f"/api/v3/runs/{old_run['run_id']}/retry",
            json={},
            headers={"Idempotency-Key": "refuse-unknown-view"},
        )
        assert refused.status_code == 409
        assert refused.json()["code"] == "LEGACY_RETRIEVAL_VIEW_UNAVAILABLE"
