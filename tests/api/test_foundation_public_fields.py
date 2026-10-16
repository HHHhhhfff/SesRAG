from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def test_message_and_document_expose_logical_source_and_created_at(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'source.db'}",
            upload_dir=str(tmp_path / "uploads"),
            auto_create_schema=True,
            redis_enabled=False,
        )
    )
    with TestClient(app) as client:
        thread_id = client.post("/api/v1/threads", json={"title": "source"}).json()["thread_id"]
        response = client.post(
            f"/api/v1/threads/{thread_id}/messages", json={"content": "question"}
        )
        assert response.status_code == 201
        message = client.get(f"/api/v1/threads/{thread_id}").json()["messages"][0]
        assert message["source"] == "user_input"
        assert message["created_at"]
        document = client.post(
            "/api/v1/documents", files={"file": ("source.txt", b"text", "text/plain")}
        ).json()
        assert document["source"] == "local_upload"
        assert document["created_at"]
        assert "storage_key" not in document
