import asyncio
import logging

from backend.config import Settings
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.workers.runtime import WorkerRuntime, install_signal_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    notifier = RedisNotifier(settings)
    await notifier.connect()
    runtime = WorkerRuntime(settings, factory, notifier)
    install_signal_handlers(runtime)
    try:
        await runtime.run_forever()
    finally:
        await notifier.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
