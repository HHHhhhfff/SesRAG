"""显式将非 Secret Profile JSON 导入 PostgreSQL 元数据表。"""

import argparse
import asyncio
import json
from pathlib import Path

from backend.config import Settings
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository


async def sync(path: Path, database_url: str | None = None) -> None:
    profiles = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profiles, list):
        raise ValueError("Profile JSON 顶层必须是数组")
    settings = Settings(database_url=database_url) if database_url else Settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            await SQLModelProfileRepository(session).import_profiles(profiles)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    asyncio.run(sync(args.path))


if __name__ == "__main__":
    main()
