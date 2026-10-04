from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def test_thread_message_run_and_event_flow(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        upload_dir=str(tmp_path / "uploads"),
        auto_create_schema=True,
        redis_enabled=False,
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json() == {"status": "ok"}

        thread = client.post("/api/v1/threads", json={"title": "测试会话"})
        assert thread.status_code == 201
        thread_id = thread.json()["thread_id"]

        archived = client.post(f"/api/v1/threads/{thread_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["archived"] is True

        message = client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers={"Idempotency-Key": "message-1"},
            json={"content": "什么是持久化会话？"},
        )
        assert message.status_code == 201
        run_id = message.json()["run_id"]
        assert message.json()["status"] == "queued"

        duplicate = client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers={"Idempotency-Key": "message-1"},
            json={"content": "不同内容也不能重复创建"},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["run_id"] == run_id

        events = client.get(f"/api/v1/runs/{run_id}/events")
        assert events.status_code == 200
        assert [event["type"] for event in events.json()["events"]] == [
            "run.created",
            "task.queued",
        ]

        cancelled = client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


def test_document_upload_rejects_unsupported_extension(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        upload_dir=str(tmp_path / "uploads"),
        auto_create_schema=True,
        redis_enabled=False,
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("unsafe.exe", b"not text", "application/octet-stream")},
        )

        assert response.status_code == 415
        assert response.json()["code"] == "UNSUPPORTED_DOCUMENT_TYPE"
