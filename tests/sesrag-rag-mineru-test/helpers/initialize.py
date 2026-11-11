"""配置初始化仅调用产品导入工具；不写入业务成功状态。"""

import asyncio
from pathlib import Path

from backend.tools.sync_model_profiles import sync as sync_models
from backend.tools.sync_rag_profiles import sync as sync_profiles


async def main():
    await sync_profiles("/config/profiles.json")
    await sync_models(Path("/config/models.json"))


if __name__ == "__main__":
    asyncio.run(main())
