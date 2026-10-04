from typing import Any

from backend.config import Settings


class RedisNotifier:
    """Redis 只用于唤醒观察者，所有事实仍从 PostgreSQL 读取。"""

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.redis_enabled
        self.url = settings.redis_url
        self.client: Any = None

    async def connect(self) -> None:
        if not self.enabled:
            return
        from redis.asyncio import Redis

        self.client = Redis.from_url(self.url, decode_responses=True)
        try:
            await self.client.ping()
        except Exception:
            await self.close()

    async def publish_run(self, run_id: str) -> None:
        if self.client is None:
            return
        try:
            await self.client.publish(f"sesrag:run:{run_id}", run_id)
        except Exception:
            # Redis 只做通知，失败时 SSE/Worker 会退化为数据库轮询。
            return

    async def ready_worker_count(self) -> int | None:
        if self.client is None:
            return None
        try:
            count = 0
            async for _key in self.client.scan_iter(match="sesrag:worker:ready:*"):
                count += 1
            return count
        except Exception:
            return None

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None
