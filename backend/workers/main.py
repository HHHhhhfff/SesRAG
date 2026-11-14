import asyncio

from backend.application.observation import bind
from backend.config import Settings
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.events.redis_notifier import RedisNotifier
from backend.infrastructure.observability.config import from_settings
from backend.infrastructure.observability.runtime import ObservabilityRuntime
from backend.workers.runtime import WorkerRuntime, install_signal_handlers


async def main() -> None:
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    notifier = RedisNotifier(settings)
    await notifier.connect()
    observation = ObservabilityRuntime(from_settings("worker", settings))
    await observation.start(settings)
    runtime = WorkerRuntime(settings, factory, notifier, observation=observation)
    install_signal_handlers(runtime)
    try:
        with bind(observation):
            await runtime.run_forever()
    finally:
        await observation.close()
        await notifier.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
