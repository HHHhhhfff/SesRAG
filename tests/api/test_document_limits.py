from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from backend.app import create_app
from backend.config import Settings


def test_overlimit_upload_reads_bounded_and_creates_no_files_or_facts(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        upload_dir=str(tmp_path / "uploads"),
        redis_enabled=False,
        auto_create_schema=True,
    )
    original = UploadFile.read
    reads = []

    async def read(file, size=-1):
        reads.append(size)
        return await original(file, size)

    monkeypatch.setattr(UploadFile, "read", read)
    with TestClient(create_app(settings)) as client:
        result = client.post(
            "/api/v1/documents",
            files={"file": ("large.txt", b"a" * (10 * 1024 * 1024 + 2), "text/plain")},
        )
        assert result.status_code == 413 and result.json()["code"] == "DOCUMENT_TOO_LARGE"
        assert client.get("/api/v1/documents").json() == {"documents": []}
    assert reads == [10 * 1024 * 1024 + 1]
    assert not list(settings.upload_path.rglob("*"))
