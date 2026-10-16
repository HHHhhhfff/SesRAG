"""真实Linux main的测试Port注入；信号安装、loop和退出均消费生产实现。"""

import asyncio
import os
from pathlib import Path

from pg_harness import Provider

import backend.workers.main as production


class FileGate:
    async def pause(self):
        directory = Path(os.environ["WORKER_CONTROL_DIR"])
        (directory / "entered").touch()
        async with asyncio.timeout(45):
            while not (directory / "release").exists():
                await asyncio.sleep(0.03)


class InjectedWorker(production.WorkerRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if os.environ.get("WORKER_CONTROL_STAGE") == "production":
            return
        provider = Provider(stage=os.environ.get("WORKER_CONTROL_STAGE", "embed"), gate=FileGate())
        self.embedding_provider = provider
        self.model_provider = provider


production.WorkerRuntime = InjectedWorker
asyncio.run(production.main())
