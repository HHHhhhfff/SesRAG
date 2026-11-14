"""仅恢复分组使用的受控慢生成入口；默认provider夹具保持不变。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from provider import install  # noqa: E402

install()
from backend.infrastructure.providers.mock import MockModelProvider  # noqa: E402
from backend.workers.main import main  # noqa: E402

original = MockModelProvider.stream_answer


async def delayed(*args, **kwargs):
    flag = Path("/data/recovery-delay")
    if flag.exists():
        await asyncio.sleep(40)
    async for token in original(*args, **kwargs):
        yield token


MockModelProvider.stream_answer = delayed
if __name__ == "__main__":
    asyncio.run(main())
