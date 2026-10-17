from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def test_sse_rejects_unknown_run_before_handshake(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'stream.db'}",
        auto_create_schema=True,
        redis_enabled=False,
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/api/v1/runs/missing/events/stream")
        assert response.status_code == 404


def test_sse_invalid_cursor_replays_and_terminal_empty_suffix_closes(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'stream.db'}",
        auto_create_schema=True,
        redis_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        thread = client.post("/api/v1/threads", json={"title": "stream"}).json()
        run = client.post(
            f"/api/v1/threads/{thread['thread_id']}/messages", json={"content": "hello"}
        ).json()
        run_id = run["run_id"]
        client.post(f"/api/v1/runs/{run_id}/cancel")
        url = f"/api/v1/runs/{run_id}/events/stream"
        for cursor in ("bad", "-1", "1.2"):
            response = client.get(url + "?after_seq=999", headers={"Last-Event-ID": cursor})
            assert response.status_code == 200
            assert "id: 1\n" in response.text
        assert "id: 1\n" in client.get(url + "?after_seq=-1").text
        assert client.get(url + "?after_seq=999").text == ""
        response = client.get(url, headers={"Last-Event-ID": "1"})
        assert "id: 1\n" not in response.text
        assert "event: run.cancelled" in response.text
