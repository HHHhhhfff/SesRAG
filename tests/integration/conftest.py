"""文档边界测试共用隔离 SQLite 和上传目录。"""

import pytest

from backend.application.legacy_rag import bootstrap_default
from backend.application.rag_profiles import bootstrap_mock
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
    factory = create_session_factory(engine)
    # 测试明确建立可信Mock基线，不让生产入口凭维度推断旧空间。
    async with factory() as session:
        await bootstrap_mock(session)
        await bootstrap_default(session, settings)
        await session.commit()
    yield settings, factory
    await engine.dispose()
