import asyncio

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


def app_for(tmp_path, **values):
    return create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'health.db'}",
            upload_dir=str(tmp_path / "uploads"),
            redis_enabled=False,
            auto_create_schema=True,
            **values,
        )
    )


def test_ready_database_connection_failure_is_safe_503_and_live_survives(tmp_path):
    app = app_for(tmp_path)

    class UnavailableEngine:
        def connect(self):
            raise ConnectionError("database password and private host must stay private")

    with TestClient(app) as client:
        app.state.engine = UnavailableEngine()
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["database"] == "unavailable"
        assert response.json()["code"] == "DATABASE_UNAVAILABLE"
        assert "password" not in response.text
        assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_redis_failure_does_not_claim_ready_or_block_database(tmp_path):
    app = app_for(tmp_path)

    class FailingRedis:
        async def ping(self):
            raise ConnectionError("Redis unavailable")

        async def scan_iter(self, **_kwargs):
            raise ConnectionError("Redis unavailable")
            yield  # pragma: no cover

        async def aclose(self):
            pass

    with TestClient(app) as client:
        app.state.notifier.client = FailingRedis()
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "database": "ready",
            "redis": "degraded",
            "worker": "unknown",
            "worker_count": 0,
        }
        assert client.post("/api/v1/threads", json={"title": "Redis 不可用"}).status_code == 201


def test_ready_redis_probe_timeout_is_bounded(tmp_path):
    app = app_for(tmp_path, health_probe_timeout=0.02)

    class HangingRedis:
        async def ping(self):
            await asyncio.sleep(60)

        async def scan_iter(self, **_kwargs):
            await asyncio.sleep(60)
            yield "worker"  # pragma: no cover

        async def aclose(self):
            pass

    with TestClient(app) as client:
        app.state.notifier.client = HangingRedis()
        response = client.get("/health/ready")
        assert response.json()["redis"] == "degraded"


def test_database_business_connection_failure_is_safe_503(tmp_path):
    app = app_for(tmp_path)
    with TestClient(app) as client:
        from sqlalchemy.exc import OperationalError

        async def database_failure():
            raise OperationalError("query", {}, Exception("private password"))

        app.add_api_route("/failure", database_failure)
        response = client.get("/failure")
        assert response.status_code == 503
        assert response.json()["code"] == "DATABASE_UNAVAILABLE"
        assert "password" not in response.text
