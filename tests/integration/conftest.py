"""文档边界测试共用隔离 SQLite 和上传目录。"""

import pytest

from backend.config import Settings
from backend.db.base import Base
from backend.db.session import create_engine, create_session_factory


@pytest.fixture
async def document_db(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'docs.db'}",
        upload_dir=str(tmp_path / "uploads"),
        redis_enabled=False,
    )
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield settings, create_session_factory(engine)
    await engine.dispose()
