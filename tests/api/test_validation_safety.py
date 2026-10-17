import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings

SENTINEL = "synthetic_private_key_422"
PRIVATE_PATH = "D:\\private\\credentials.txt"


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("POST", "/api/v1/threads", {"json": {"title": SENTINEL * 20}}),
        ("POST", "/api/v1/threads", {"json": {"title": {SENTINEL: PRIVATE_PATH}}}),
        ("POST", "/api/v1/threads", {"json": [SENTINEL, PRIVATE_PATH]}),
        (
            "POST",
            "/api/v1/threads",
            {
                "content": '{"title":"' + SENTINEL + '","path":"' + PRIVATE_PATH + '",}',
                "headers": {"Content-Type": "application/json"},
            },
        ),
        ("POST", "/api/v1/threads/id/messages", {"json": {"content": SENTINEL * 1000}}),
        ("POST", "/api/v1/threads/id/messages", {"json": {"content": [PRIVATE_PATH, SENTINEL]}}),
        ("GET", "/api/v1/runs/id/events", {"params": {"after_seq": SENTINEL + PRIVATE_PATH}}),
        ("GET", "/api/v1/runs/id/events", {"params": {"after_seq": "-1"}}),
        ("POST", "/api/v1/documents", {"data": {"unexpected": SENTINEL + PRIVATE_PATH}}),
    ],
)
async def test_raw_validation_response_never_echoes_request_input(method, path, kwargs, tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'unused.db'}",
            redis_enabled=False,
            upload_dir=str(tmp_path),
        )
    )
    # 无 lifespan/数据库写入；真实ASGI响应未经runner脱敏，直接断言原始字节。
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.request(method, path, **kwargs)
    assert response.status_code == 422
    assert SENTINEL not in response.text
    assert "credentials.txt" not in response.text
    assert set(response.json()) == {"detail"}
    assert response.json()["detail"]
    for error in response.json()["detail"]:
        assert set(error) == {"type", "loc", "msg"}
        assert error["type"]
        assert error["msg"] == "请求参数校验失败"
        assert error["loc"]
        assert all(isinstance(part, (str, int)) for part in error["loc"])


def test_safe_validation_does_not_change_business_errors_or_normal_creation(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'business.db'}",
            redis_enabled=False,
            upload_dir=str(tmp_path),
            auto_create_schema=True,
        )
    )
    with TestClient(app) as client:
        thread = client.post("/api/v1/threads", json={"title": "正常请求"})
        assert thread.status_code == 201
        missing = client.get("/api/v1/threads/missing")
        assert missing.status_code == 404
        assert missing.json()["code"] == "THREAD_NOT_FOUND"
        invalid_filename = client.post(
            "/api/v1/documents", files={"file": ("invalid:name.txt", b"text", "text/plain")}
        )
        assert invalid_filename.status_code == 422
        assert invalid_filename.json()["code"] == "INVALID_DOCUMENT_FILENAME"
        assert "detail" not in invalid_filename.json()
