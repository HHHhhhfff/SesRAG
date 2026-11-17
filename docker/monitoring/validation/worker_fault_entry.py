"""仅005隔离应用夹具：首次模型调用失败一次，证明真实Task重试代际到达Tempo。"""

import runpy
import sys

sys.path.insert(0, "/app")
from backend.infrastructure.providers.mock import MockModelProvider

original = MockModelProvider.stream_answer
failed = False


async def fail_once(self, *args, **kwargs):
    global failed
    if not failed:
        failed = True
        raise ConnectionError("OBS005_CONTROLLED_TRANSIENT")
    async for part in original(self, *args, **kwargs):
        yield part


MockModelProvider.stream_answer = fail_once
runpy.run_module("backend.workers.main", run_name="__main__")
