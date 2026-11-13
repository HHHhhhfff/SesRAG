"""操作者显式清理入口；不清理仍被引用的历史或原始上传。"""

import argparse
import asyncio
import json

from backend.application.rag_gc import collect
from backend.config import Settings
from backend.db.session import create_engine, create_session_factory


async def main(args):
    settings = Settings()
    engine = create_engine(settings)
    try:
        report = await collect(
            create_session_factory(engine),
            settings,
            apply=args.apply,
            retention_hours=args.retention_hours,
            limit=args.limit,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG GC默认只输出计划；--apply才执行")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--retention-hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=100)
    asyncio.run(main(parser.parse_args()))
