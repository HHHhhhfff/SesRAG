"""FE_006：真实生产main消费永久失败Port，敏感哨兵只存在异常内存。"""

import asyncio
import os

from pg_harness import Provider

import backend.workers.main as production
from backend.application.errors import ApplicationError


class FailureProvider(Provider):
    async def embed(self, value):
        raise ApplicationError(
            "TEST_PROVIDER_FAILURE",
            "fe-secret-sentinel https://fe-user:fe-password@invalid.example "
            "C:\\fe-private\\payload fe-raw-response",
            retryable=False,
        )


class InjectedWorker(production.WorkerRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert os.environ["WORKER_CONTROL_STAGE"] == "failure"
        self.embedding_provider = FailureProvider()


production.WorkerRuntime = InjectedWorker
asyncio.run(production.main())
