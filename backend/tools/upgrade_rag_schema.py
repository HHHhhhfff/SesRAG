"""先catalog再显式初始化，最后升级剩余schema；不碰模型或MinerU。"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.rag_profiles import bootstrap_mock, import_profiles
from backend.config import Settings
from backend.db.rag_models import EmbeddingProfileModel, KnowledgeBaseModel
from backend.db.session import create_engine


async def upgrade(settings):
    engine = create_engine(settings)
    config = Config("alembic.ini")

    def migrate(connection, revision):
        config.attributes["connection"] = connection
        command.upgrade(config, revision)

    try:
        async with engine.begin() as conn:
            current = await conn.run_sync(
                lambda c: MigrationContext.configure(c).get_current_revision()
            )
            if current == "0010_rag_task_and_run_protocol":
                print("RAG数据库已在目标版本，未覆盖现有配置。")
                return
            if current not in {
                "0007_rag_catalog_and_profiles",
                "0008_rag_builds_and_vectors",
                "0009_rag_views_tools_evidence",
            }:
                await conn.run_sync(lambda c: migrate(c, "0007_rag_catalog_and_profiles"))
        async with engine.begin() as conn:
            owners = set(
                (await conn.execute(text("SELECT DISTINCT owner_id FROM documents"))).scalars()
            )
            owners.add(settings.owner_id)
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                if settings.rag_bootstrap_config:
                    payload = json.loads(
                        Path(settings.rag_bootstrap_config).read_text(encoding="utf-8")
                    )
                    await import_profiles(session, payload["profiles"])
                    selection = payload["default_embedding"]
                else:
                    old_count = await conn.scalar(text("SELECT count(*) FROM documents"))
                    if old_count:
                        raise RuntimeError("RAG_BOOTSTRAP_REQUIRED: 旧库需显式非Secret初始化文件")
                    await bootstrap_mock(session)
                    selection = {"profile_id": "mock-embedding", "version": 1}
                profile = await session.get(
                    EmbeddingProfileModel, (selection["profile_id"], selection["version"])
                )
                if profile is None:
                    raise RuntimeError("RAG_BOOTSTRAP_REQUIRED: 默认空间配置不存在")
                for owner in owners:
                    existing = await session.scalar(
                        select(KnowledgeBaseModel).where(
                            KnowledgeBaseModel.owner_id == owner,
                            KnowledgeBaseModel.is_default.is_(True),
                        )
                    )
                    if existing is None:
                        session.add(
                            KnowledgeBaseModel(
                                knowledge_base_id=str(uuid4()),
                                owner_id=owner,
                                name="默认知识库",
                                is_default=True,
                                embedding_space_id=profile.space_id,
                                embedding_profile_id=profile.profile_id,
                                embedding_profile_version=profile.version,
                            )
                        )
                await session.flush()
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: migrate(c, "head"))
        print("RAG分段迁移完成；旧向量仍须可信空间确认，未自动重索引或外发。")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(upgrade(Settings()))
