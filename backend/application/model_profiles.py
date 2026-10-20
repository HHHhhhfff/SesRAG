"""Profile 元数据校验、安全投影和运行时 Secret 解析。"""

import os
from urllib.parse import urlsplit

from backend.api.schemas.v2.models import ModelListResponse, ModelProfile, ModelProfileKey
from backend.application.errors import ApplicationError
from backend.domain.ports.session import ModelProfilePort, ModelProfileRecord

SAFE_CONFIG_REFS = {"env:MODEL_API_KEY": "MODEL_API_KEY"}
ALLOWED_GENERATION_PARAMS = {"temperature", "top_p", "frequency_penalty", "presence_penalty"}
MOCK_TOKENIZER_CONFIG_FIELDS = {"safety_margin_tokens", "summary_max_tokens"}
TIKTOKEN_CONFIG_FIELDS = MOCK_TOKENIZER_CONFIG_FIELDS | {
    "encoding_name",
    "message_overhead_tokens",
    "request_overhead_tokens",
    "calibration_version",
}


def validate_profile_config(config: dict) -> None:
    required = {
        "profile_id",
        "version",
        "display_name",
        "provider_kind",
        "model_name",
        "generation_params",
        "context_window_tokens",
        "max_output_tokens",
        "status",
        "is_default",
        "tokenizer_kind",
        "tokenizer_version",
        "tokenizer_config",
    }
    if required - config.keys():
        raise ValueError("ModelProfile 字段不完整")
    if (
        not config["profile_id"].strip()
        or type(config["version"]) is not int
        or config["version"] < 1
    ):
        raise ValueError("Profile 身份无效")
    if config["provider_kind"] not in {"mock", "openai_compatible"}:
        raise ValueError("Provider 类型不支持")
    if (
        type(config["context_window_tokens"]) is not int
        or type(config["max_output_tokens"]) is not int
    ):
        raise ValueError("预算必须为整数")
    tokenizer_config = config["tokenizer_config"]
    if not isinstance(tokenizer_config, dict):
        raise ValueError("tokenizer_config 必须为对象")
    if frozenset(tokenizer_config) not in {
        frozenset(MOCK_TOKENIZER_CONFIG_FIELDS),
        frozenset(TIKTOKEN_CONFIG_FIELDS),
    }:
        raise ValueError("tokenizer_config 字段不完整或包含不支持字段")
    safety_margin = tokenizer_config["safety_margin_tokens"]
    summary_max = tokenizer_config["summary_max_tokens"]
    if (
        type(safety_margin) is not int
        or safety_margin < 0
        or type(summary_max) is not int
        or not 0 <= summary_max <= 512
    ):
        raise ValueError("tokenizer_config 预算无效")
    if config["context_window_tokens"] <= config["max_output_tokens"] + safety_margin:
        raise ValueError("输出预留和安全余量必须小于窗口")
    params = config["generation_params"]
    if not isinstance(params, dict) or set(params) - ALLOWED_GENERATION_PARAMS:
        raise ValueError("生成参数包含不支持的字段")
    for key, value in params.items():
        if type(value) not in (int, float) or not 0 <= value <= 2:
            raise ValueError(f"生成参数 {key} 超出安全范围")
    if config["provider_kind"] == "mock":
        if config.get("base_url") or config.get("config_ref"):
            raise ValueError("Mock Profile 不接受外部 URL 或 Secret 引用")
    else:
        parsed = urlsplit(config.get("base_url") or "")
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url 必须是无凭据且不含 query/fragment 的 HTTP(S) URL")
        if config.get("config_ref") not in SAFE_CONFIG_REFS:
            raise ValueError("config_ref 不在受信环境变量白名单中")
    tokenizer = config["tokenizer_kind"]
    # 真实Provider必须使用明确encoding，不能用Mock词法计数绕过上下文预算。
    if config["provider_kind"] == "openai_compatible" and tokenizer != "tiktoken":
        raise ValueError("真实 Provider 必须使用显式 tiktoken 配置")
    if tokenizer == "tiktoken":
        if set(tokenizer_config) != TIKTOKEN_CONFIG_FIELDS:
            raise ValueError("tokenizer_config 缺少显式框架开销或校准版本")
        encoding = tokenizer_config.get("encoding_name")
        if not isinstance(encoding, str) or not encoding:
            raise ValueError("真实 tokenizer 必须显式指定 encoding_name")
        if (
            type(tokenizer_config["message_overhead_tokens"]) is not int
            or not 0 <= tokenizer_config["message_overhead_tokens"] <= 64
            or type(tokenizer_config["request_overhead_tokens"]) is not int
            or not 0 <= tokenizer_config["request_overhead_tokens"] <= 256
            or not isinstance(tokenizer_config["calibration_version"], str)
            or not tokenizer_config["calibration_version"].strip()
        ):
            raise ValueError("tokenizer_config 框架开销或校准版本无效")
        try:
            from backend.infrastructure.providers.context_counter import load_encoding_offline

            load_encoding_offline(encoding)
        except (ImportError, ValueError, KeyError):
            raise ValueError("tiktoken encoding 不可用") from None
    elif tokenizer == "mock":
        if set(tokenizer_config) != MOCK_TOKENIZER_CONFIG_FIELDS:
            raise ValueError("Mock tokenizer_config 包含不支持字段")
    else:
        raise ValueError("tokenizer 类型不支持")


def profile_reason(profile: ModelProfileRecord, env: dict[str, str] | None = None) -> str | None:
    environment = os.environ if env is None else env
    try:
        validate_profile_config(
            {name: getattr(profile, name) for name in ModelProfileRecord.__dataclass_fields__}
        )
    except (ValueError, TypeError):
        return "MODEL_PROFILE_INVALID"
    if profile.status != "enabled":
        return "MODEL_PROFILE_DISABLED"
    if profile.config_ref and not environment.get(SAFE_CONFIG_REFS.get(profile.config_ref, "")):
        return "MODEL_CREDENTIAL_UNAVAILABLE"
    return None


async def list_model_profiles(
    repository: ModelProfilePort, env: dict[str, str] | None = None
) -> ModelListResponse:
    records = await repository.list_profiles()
    default = next(
        (record for record in records if record.is_default and profile_reason(record, env) is None),
        None,
    )
    if default is None:
        raise ApplicationError("MODEL_PROFILE_UNAVAILABLE", "默认模型配置不可用", 503)
    projected = []
    for record in records:
        reason = profile_reason(record, env)
        projected.append(
            ModelProfile.model_validate(
                dict(
                    profile_id=record.profile_id,
                    version=record.version,
                    display_name=record.display_name,
                    provider_kind=record.provider_kind,
                    model_name=record.model_name,
                    context_window_tokens=record.context_window_tokens,
                    max_output_tokens=record.max_output_tokens,
                    status="enabled"
                    if reason is None
                    else "disabled"
                    if reason == "MODEL_PROFILE_DISABLED"
                    else "invalid",
                    reason=reason,
                    is_default=record.is_default and reason is None,
                )
            )
        )
    return ModelListResponse(
        models=projected,
        default_profile=ModelProfileKey(profile_id=default.profile_id, version=default.version),
    )


def resolve_secret(config_ref: str | None, env: dict[str, str] | None = None) -> str | None:
    if config_ref is None:
        return None
    variable = SAFE_CONFIG_REFS.get(config_ref)
    if variable is None:
        raise ApplicationError("INVALID_RUN_SNAPSHOT", "Run 快照中的凭据引用无效")
    secret = (os.environ if env is None else env).get(variable)
    if not secret:
        raise ApplicationError("MODEL_CREDENTIAL_UNAVAILABLE", "模型凭据不可用", 422)
    return secret
