"""显式导入非 Secret 配置；普通服务启动不扫描配置文档。"""

import argparse
import asyncio
import json
from pathlib import Path

from backend.application.rag_profiles import import_profiles
from backend.config import Settings
from backend.db.session import create_engine, create_session_factory


async def sync(path):
    content = Path(path).read_bytes()
    if len(content) > 1024 * 1024:
        raise ValueError("配置文件超过1MiB")
    entries = json.loads(content)
    engine = create_engine(Settings())
    try:
        async with create_session_factory(engine)() as session:
            await import_profiles(session, entries)
            await session.commit()
        print("RAG配置导入完成；配置内容和凭据不输出。")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    asyncio.run(sync(parser.parse_args().path))
