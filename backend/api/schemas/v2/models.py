from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from backend.api.schemas.v2 import StrictModel

ProfileId = Annotated[str, Field(min_length=1, max_length=100)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]
ProviderKind = Literal["mock", "openai_compatible"]
ModelReason = Literal[
    "MODEL_PROFILE_DISABLED", "MODEL_PROFILE_INVALID", "MODEL_CREDENTIAL_UNAVAILABLE"
]


class ProfileSelectionRequest(StrictModel):
    model_profile_id: ProfileId | None = None
    model_profile_version: PositiveInt | None = None

    @model_validator(mode="after")
    def profile_pair(self):
        # 未传与显式 null 不等价，幂等指纹必须保留原始选择意图。
        fields = self.model_fields_set & {"model_profile_id", "model_profile_version"}
        if fields and (
            len(fields) != 2 or self.model_profile_id is None or self.model_profile_version is None
        ):
            raise ValueError("模型配置 ID 和版本必须成对提供")
        return self


class ModelProfileKey(StrictModel):
    profile_id: ProfileId
    version: PositiveInt


class ModelSelection(ModelProfileKey):
    display_name: str = Field(min_length=1)
    provider_kind: ProviderKind
    model_name: str = Field(min_length=1)
    context_window_tokens: PositiveInt
    max_output_tokens: PositiveInt


class ModelProfile(ModelSelection):
    status: Literal["enabled", "disabled", "invalid"]
    reason: ModelReason | None
    is_default: bool

    @model_validator(mode="after")
    def availability(self):
        if self.status == "enabled":
            if self.reason is not None:
                raise ValueError("启用模型不应有不可用原因")
        elif self.reason is None or self.is_default:
            raise ValueError("不可用模型须有安全原因且不能作为默认")
        return self


class ModelListResponse(StrictModel):
    models: list[ModelProfile]
    default_profile: ModelProfileKey
