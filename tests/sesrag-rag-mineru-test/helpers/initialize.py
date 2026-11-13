"""配置初始化仅调用产品导入工具；不写入业务成功状态。"""

import asyncio
from pathlib import Path

from helpers.baseline import baseline

from backend.config import Settings
from backend.tools.sync_model_profiles import sync as sync_models
from backend.tools.sync_rag_profiles import sync as sync_profiles


async def main():
    fixture = baseline("/config/baseline.json")
    if Settings().owner_id != fixture["owner"]:
        raise ValueError("BASELINE_OWNER_CONFIG_MISMATCH")
    await sync_profiles("/config/profiles.json")
    await sync_models(Path("/config/models.json"))
    print("虚假身份基线已核对；迁移与正式Profile导入完成，无用户表seed SQL。", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
