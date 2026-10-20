"""schema 2 Run 的 Provider 重建；schema 1 保持旧 factory 解码。"""

from copy import deepcopy
from urllib.parse import urlsplit

from backend.application.errors import ApplicationError
from backend.application.model_profiles import resolve_secret, validate_profile_config
from backend.domain.ports import ModelProvider
from backend.infrastructure.providers.context_counter import token_counter_from_profile
from backend.infrastructure.providers.mock import MockEmbeddingProvider, MockModelProvider
from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider

PROFILE_SNAPSHOT_FIELDS = (
    "profile_id",
    "version",
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
CONTEXT_SNAPSHOT_FIELDS = {
    "trim_policy_version",
    "summary_max_tokens",
    "max_candidate_messages",
    "max_candidate_chars",
    "safety_margin_tokens",
    "counter_version",
}
EXECUTION_SNAPSHOT_LIMITS = {
    "max_attempts": 3,
    "deadline_seconds": 600,
    "step_timeout_seconds": 60,
    "stream_timeout_seconds": 120,
    "max_raw_deltas": 4096,
    "max_output_chars": 1_000_000,
    "delta_flush_ms": 100,
    "delta_buffer_bytes": 65_536,
    "max_regular_events": 15_000,
}


def validate_retrieval_snapshot(retrieval: dict) -> None:
    fields = {
        "enabled",
        "top_k",
        "embedding_dimensions",
        "embedding_model",
        "embedding_provider_kind",
        "embedding_base_url",
        "embedding_config_ref",
    }
    if (
        not isinstance(retrieval, dict)
        or set(retrieval) != fields
        or type(retrieval["enabled"]) is not bool
        or type(retrieval["top_k"]) is not int
        or retrieval["top_k"] < 1
        or retrieval["embedding_dimensions"] != 384
        or not isinstance(retrieval["embedding_model"], str)
        or not retrieval["embedding_model"]
    ):
        raise ValueError("检索快照字段无效")
    kind = retrieval["embedding_provider_kind"]
    if kind == "mock":
        if (
            retrieval["embedding_base_url"] is not None
            or retrieval["embedding_config_ref"] is not None
        ):
            raise ValueError("Mock检索快照不能含外部服务配置")
    elif kind == "openai_compatible":
        parsed = urlsplit(retrieval["embedding_base_url"] or "")
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or retrieval["embedding_config_ref"] != "env:MODEL_API_KEY"
        ):
            raise ValueError("Embedding服务快照无效")
    else:
        raise ValueError("Embedding Provider类型无效")


def embedding_from_snapshot2(snapshot: dict):
    """检索源参数来自冻结快照，凭据仅按受信alias运行时注入。"""
    retrieval = snapshot["retrieval"]
    validate_retrieval_snapshot(retrieval)
    if retrieval["embedding_provider_kind"] == "mock":
        return MockEmbeddingProvider()
    secret = resolve_secret(retrieval["embedding_config_ref"])
    if secret is None:
        raise ApplicationError("MODEL_CREDENTIAL_UNAVAILABLE", "Embedding凭据不可用", 422)
    return OpenAICompatibleProvider(
        retrieval["embedding_base_url"], secret, "", retrieval["embedding_model"]
    )


def profile_snapshot(profile) -> dict:
    """提取不可变、非 Secret Profile 字段，不冻结 enabled/default 策略。"""
    return deepcopy({name: getattr(profile, name) for name in PROFILE_SNAPSHOT_FIELDS})


def _validate_snapshot_policy(snapshot: dict) -> None:
    if set(snapshot["input_anchor"]) != {"message_id", "seq"}:
        raise ValueError()
    if (
        not isinstance(snapshot["input_anchor"]["message_id"], str)
        or not snapshot["input_anchor"]["message_id"]
        or type(snapshot["input_anchor"]["seq"]) is not int
        or snapshot["input_anchor"]["seq"] < 1
    ):
        raise ValueError()
    prompt = snapshot["prompt"]
    if (
        set(prompt) != {"version"}
        or not isinstance(prompt["version"], str)
        or not prompt["version"]
    ):
        raise ValueError()

    profile = snapshot["model_profile"]
    context = snapshot["context"]
    if not isinstance(context, dict) or set(context) != CONTEXT_SNAPSHOT_FIELDS:
        raise ValueError()
    if context["trim_policy_version"] not in {"trim_then_extract_v1", "trim_only_v1"}:
        raise ValueError()
    bounded_context_fields = {
        "summary_max_tokens": (0, 512),
        "max_candidate_messages": (1, 200),
        "max_candidate_chars": (1, 200_000),
        "safety_margin_tokens": (0, 4096),
    }
    for field, (minimum, maximum) in bounded_context_fields.items():
        value = context[field]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError()
    tokenizer_config = profile["tokenizer_config"]
    if (
        context["summary_max_tokens"] != tokenizer_config["summary_max_tokens"]
        or context["safety_margin_tokens"] != tokenizer_config["safety_margin_tokens"]
        or context["counter_version"] != token_counter_from_profile(profile).version
    ):
        raise ValueError()

    execution = snapshot["execution"]
    if not isinstance(execution, dict) or set(execution) != set(EXECUTION_SNAPSHOT_LIMITS):
        raise ValueError()
    for field, maximum in EXECUTION_SNAPSHOT_LIMITS.items():
        value = execution[field]
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError()


def provider_from_snapshot2(snapshot: dict) -> ModelProvider:
    required = {
        "schema_version",
        "owner_id",
        "thread_id",
        "branch_id",
        "input_anchor",
        "model_profile",
        "prompt",
        "context",
        "retrieval",
        "execution",
    }
    if (
        not isinstance(snapshot, dict)
        or set(snapshot) != required
        or snapshot.get("schema_version") != 2
    ):
        raise ApplicationError("INVALID_RUN_SNAPSHOT", "Run 快照格式无效", 422)
    profile = snapshot["model_profile"]
    try:
        if set(profile) != set(PROFILE_SNAPSHOT_FIELDS):
            raise ValueError()
        if not isinstance(profile, dict):
            raise ValueError()
        validate_profile_config({**profile, "status": "enabled", "is_default": False})
        _validate_snapshot_policy(snapshot)
        validate_retrieval_snapshot(snapshot["retrieval"])
    except (ValueError, TypeError, AttributeError, KeyError, ImportError):
        raise ApplicationError("INVALID_RUN_SNAPSHOT", "Run 快照配置无效", 422) from None
    if profile["provider_kind"] == "mock":
        return MockModelProvider()
    api_key = resolve_secret(profile.get("config_ref"))
    if api_key is None:
        raise ApplicationError("MODEL_CREDENTIAL_UNAVAILABLE", "模型凭据不可用", 422)
    return OpenAICompatibleProvider(
        profile["base_url"],
        api_key,
        profile["model_name"],
        snapshot["retrieval"]["embedding_model"],
    )


def build_snapshot2(
    *,
    owner_id: str,
    thread_id: str,
    branch_id: str,
    input_anchor: dict,
    profile: dict,
    prompt: dict,
    retrieval: dict,
    context: dict,
    execution: dict,
) -> dict:
    """生成 schema 2 冻结快照；调用方提交事务前再次校验路径/锚点。"""
    snapshot = {
        "schema_version": 2,
        "owner_id": owner_id,
        "thread_id": thread_id,
        "branch_id": branch_id,
        "input_anchor": deepcopy(input_anchor),
        "model_profile": deepcopy(profile),
        "prompt": deepcopy(prompt),
        "context": deepcopy(context),
        "retrieval": deepcopy(retrieval),
        "execution": deepcopy(execution),
    }
    provider_from_snapshot2(snapshot)
    return snapshot
