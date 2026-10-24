"""ModelProfile 的只读/显式导入 SQL 适配器。"""

from sqlalchemy import select

from backend.db.models import ModelProfileModel
from backend.domain.ports.session import ModelProfileRecord


def _record(row: ModelProfileModel) -> ModelProfileRecord:
    return ModelProfileRecord(
        **{name: getattr(row, name) for name in ModelProfileRecord.__dataclass_fields__}
    )


class SQLModelProfileRepository:
    def __init__(self, session):
        self.session = session

    async def list_profiles(self) -> list[ModelProfileRecord]:
        rows = (
            await self.session.scalars(
                select(ModelProfileModel).order_by(
                    ModelProfileModel.profile_id, ModelProfileModel.version
                )
            )
        ).all()
        return [_record(row) for row in rows]

    async def get_profile(self, profile_id: str, version: int) -> ModelProfileRecord | None:
        row = await self.session.get(ModelProfileModel, (profile_id, version))
        return _record(row) if row is not None else None

    async def import_profiles(self, profiles: list[dict]) -> None:
        """插入新版本；相同版本只允许更新启用和默认策略。"""
        from backend.application.model_profiles import validate_profile_config

        for config in profiles:
            validate_profile_config(config)
        requested_defaults = [
            p for p in profiles if p.get("is_default") and p.get("status") == "enabled"
        ]
        if len(requested_defaults) != 1:
            raise ValueError("导入配置必须指定且只指定一个启用默认 Profile")
        existing = {}
        for config in profiles:
            key = (config["profile_id"], config["version"])
            row = await self.session.get(ModelProfileModel, key)
            existing[key] = row
            if row is None:
                continue
            immutable = (
                "display_name",
                "provider_kind",
                "model_name",
                "generation_params",
                "base_url",
                "context_window_tokens",
                "max_output_tokens",
                "tokenizer_kind",
                "tokenizer_version",
                "tokenizer_config",
                "config_ref",
            )
            if any(getattr(row, name) != config.get(name) for name in immutable):
                raise ValueError("MODEL_PROFILE_VERSION_CONFLICT")
        # 先清除当前默认再统一设置，避免导入过程中出现两个默认值。
        rows = (await self.session.scalars(select(ModelProfileModel).with_for_update())).all()
        for row in rows:
            row.is_default = False
        for config in profiles:
            key = (config["profile_id"], config["version"])
            row = existing[key]
            if row is None:
                row = ModelProfileModel(**config)
                self.session.add(row)
            row.status = config["status"]
            row.is_default = bool(config.get("is_default"))
        await self.session.commit()
