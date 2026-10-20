import pytest

from backend.application.model_profiles import (
    list_model_profiles,
    profile_reason,
    validate_profile_config,
)
from backend.config import Settings
from backend.db.base import Base
from backend.db.models import ModelProfileModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.providers.registry import build_snapshot2, profile_snapshot
from backend.infrastructure.session.model_profiles import SQLModelProfileRepository


def profile(**overrides):
    value = {
        "profile_id": "mock-default",
        "version": 1,
        "display_name": "Mock",
        "provider_kind": "mock",
        "model_name": "mock",
        "generation_params": {},
        "base_url": None,
        "context_window_tokens": 8192,
        "max_output_tokens": 1024,
        "status": "enabled",
        "is_default": True,
        "tokenizer_kind": "mock",
        "tokenizer_version": "1",
        "tokenizer_config": {"safety_margin_tokens": 128, "summary_max_tokens": 512},
        "config_ref": None,
    }
    value.update(overrides)
    return value


def real_profile(**overrides):
    value = profile(
        provider_kind="openai_compatible",
        base_url="https://model.example/v1",
        config_ref="env:MODEL_API_KEY",
        tokenizer_kind="tiktoken",
        tokenizer_config={
            "encoding_name": "cl100k_base",
            "message_overhead_tokens": 4,
            "request_overhead_tokens": 2,
            "calibration_version": "test-frame@1",
            "safety_margin_tokens": 128,
            "summary_max_tokens": 512,
        },
    )
    value.update(overrides)
    return value


def test_real_provider_cannot_use_mock_token_counter():
    # 真实模型不得把连续中文按一个Mock词计数，从而绕过mandatory预算预检。
    with pytest.raises(ValueError, match="tiktoken"):
        validate_profile_config(
            real_profile(
                tokenizer_kind="mock",
                tokenizer_config={"safety_margin_tokens": 128, "summary_max_tokens": 512},
            )
        )


@pytest.mark.parametrize("encoding", ["cl100k_base", "p50k_base"])
def test_missing_encoding_cache_never_attempts_runtime_network(tmp_path, monkeypatch, encoding):
    import tiktoken.load
    import tiktoken.registry

    calls = []

    def network_attempt(url):
        calls.append(url)
        raise ValueError("test blocked remote read")

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    # 清除进程内缓存，模拟新API/Worker首次加载该Profile。
    monkeypatch.setattr(tiktoken.registry, "ENCODINGS", {})
    monkeypatch.setattr(tiktoken.load, "read_file", network_attempt)
    config = real_profile()
    config["tokenizer_config"]["encoding_name"] = encoding
    with pytest.raises(ValueError):
        validate_profile_config(config)
    assert calls == [], "缺失缓存必须明确不可用，不得在请求或Worker中尝试联网"


def test_corrupt_encoding_cache_is_rejected_without_refetch(tmp_path, monkeypatch):
    import hashlib

    import tiktoken.load

    from backend.infrastructure.providers.context_counter import ENCODING_ASSETS

    url, _ = ENCODING_ASSETS["cl100k_base"]
    (tmp_path / hashlib.sha1(url.encode()).hexdigest()).write_bytes(b"corrupt asset")
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(tiktoken.load, "read_file", lambda url: calls.append(url))
    with pytest.raises(ValueError):
        validate_profile_config(real_profile())
    assert calls == []


def test_profile_rejects_url_credentials_and_unknown_generation_parameters():
    with pytest.raises(ValueError):
        validate_profile_config(
            profile(
                provider_kind="openai_compatible",
                base_url="https://user:secret@example.test/v1",
                config_ref="env:MODEL_API_KEY",
            )
        )
    with pytest.raises(ValueError):
        validate_profile_config(profile(generation_params={"arbitrary_sdk_option": True}))


def test_missing_runtime_credential_is_reported_without_disclosing_secret():
    config = real_profile()
    from backend.domain.ports.session import ModelProfileRecord

    record = ModelProfileRecord(**config)
    assert profile_reason(record, {}) == "MODEL_CREDENTIAL_UNAVAILABLE"


def test_snapshot_profile_freezes_nonsecret_version_and_registry_rebuilds_mock():
    from backend.infrastructure.providers.registry import provider_from_snapshot2

    record = profile()
    frozen = profile_snapshot(type("Profile", (), record)())
    snapshot = build_snapshot2(
        owner_id="owner",
        thread_id="thread",
        branch_id="branch",
        input_anchor={"message_id": "message", "seq": 4},
        profile=frozen,
        prompt={"version": "sesrag-system@1"},
        retrieval={
            "enabled": True,
            "top_k": 5,
            "embedding_dimensions": 384,
            "embedding_model": "embed",
            "embedding_provider_kind": "mock",
            "embedding_base_url": None,
            "embedding_config_ref": None,
        },
        context={
            "trim_policy_version": "trim_then_extract_v1",
            "summary_max_tokens": 512,
            "max_candidate_messages": 200,
            "max_candidate_chars": 200_000,
            "safety_margin_tokens": 128,
            "counter_version": "mock-tokenizer@1",
        },
        execution={
            "max_attempts": 3,
            "deadline_seconds": 600,
            "step_timeout_seconds": 60,
            "stream_timeout_seconds": 120,
            "max_raw_deltas": 4096,
            "max_output_chars": 1_000_000,
            "delta_flush_ms": 100,
            "delta_buffer_bytes": 65_536,
            "max_regular_events": 15_000,
        },
    )
    record["is_default"] = False
    assert "api_key" not in snapshot and "status" not in snapshot["model_profile"]
    assert provider_from_snapshot2(snapshot).__class__.__name__ == "MockModelProvider"


@pytest.mark.asyncio
async def test_same_version_profile_model_change_is_rejected(tmp_path):
    engine = create_engine(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with create_session_factory(engine)() as session:
            repo = SQLModelProfileRepository(session)
            session.add(ModelProfileModel(**profile()))
            await session.commit()
            changed = profile(model_name="changed")
            with pytest.raises(ValueError, match="MODEL_PROFILE_VERSION_CONFLICT"):
                await repo.import_profiles([changed])
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_explicit_import_can_change_default_without_changing_profile_version(tmp_path):
    engine = create_engine(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'defaults.db'}"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with create_session_factory(engine)() as session:
            repo = SQLModelProfileRepository(session)
            first = profile()
            second = profile(
                profile_id="mock-small",
                display_name="Small Mock",
                context_window_tokens=4096,
                is_default=False,
            )
            await repo.import_profiles([first, second])
            await repo.import_profiles(
                [
                    {**first, "is_default": False},
                    {**second, "is_default": True},
                ]
            )

            listed = await list_model_profiles(repo, env={})

        assert listed.default_profile.profile_id == "mock-small"
        assert [item.is_default for item in listed.models] == [False, True]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_model_list_exposes_no_secret_fields_and_marks_missing_credential(tmp_path):
    engine = create_engine(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'projection.db'}")
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with create_session_factory(engine)() as session:
            repo = SQLModelProfileRepository(session)
            mock = profile()
            external = real_profile(
                profile_id="external",
                display_name="External",
                provider_kind="openai_compatible",
                model_name="safe-model-name",
                base_url="https://model.example/v1",
                config_ref="env:MODEL_API_KEY",
                is_default=False,
            )
            await repo.import_profiles([mock, external])

            listed = await list_model_profiles(repo, env={})

        external_item = next(item for item in listed.models if item.profile_id == "external")
        assert external_item.status == "invalid"
        assert external_item.reason == "MODEL_CREDENTIAL_UNAVAILABLE"
        assert "config_ref" not in external_item.model_dump()
        assert "base_url" not in external_item.model_dump()
    finally:
        await engine.dispose()


def test_snapshot_rejects_incomplete_retrieval_config_as_safe_application_error():
    from backend.application.errors import ApplicationError
    from backend.infrastructure.providers.registry import provider_from_snapshot2

    frozen = profile_snapshot(type("Profile", (), profile())())
    snapshot = {
        "schema_version": 2,
        "owner_id": "owner",
        "thread_id": "thread",
        "branch_id": "branch",
        "input_anchor": {"message_id": "message", "seq": 4},
        "model_profile": frozen,
        "prompt": {"version": "sesrag-system@1"},
        "context": {"context_window_tokens": 8192},
        "retrieval": {"enabled": True, "top_k": 5, "embedding_dimensions": 384},
        "execution": {"max_attempts": 3},
    }

    with pytest.raises(ApplicationError) as error:
        provider_from_snapshot2(snapshot)

    assert error.value.code == "INVALID_RUN_SNAPSHOT"


@pytest.mark.parametrize(
    "field,value",
    [
        ("context", {"trim_policy_version": "trim_then_extract_v1"}),
        (
            "context",
            {
                "trim_policy_version": "unknown",
                "summary_max_tokens": 512,
                "max_candidate_messages": 200,
                "max_candidate_chars": 200_000,
                "safety_margin_tokens": 128,
                "counter_version": "mock-tokenizer@1",
            },
        ),
        (
            "context",
            {
                "trim_policy_version": "trim_then_extract_v1",
                "summary_max_tokens": 512,
                "max_candidate_messages": 200,
                "max_candidate_chars": 200_000,
                "safety_margin_tokens": 128,
                "counter_version": "stale-tokenizer-version",
            },
        ),
        ("execution", {"max_attempts": 3}),
        (
            "execution",
            {
                "max_attempts": 3,
                "deadline_seconds": 600,
                "step_timeout_seconds": 60,
                "stream_timeout_seconds": 120,
                "max_raw_deltas": 4096,
                "max_output_chars": 1_000_001,
                "delta_flush_ms": 100,
                "delta_buffer_bytes": 65_536,
                "max_regular_events": 15_000,
            },
        ),
    ],
)
def test_snapshot_rejects_incomplete_or_out_of_bounds_nested_policy(field, value):
    from backend.application.errors import ApplicationError
    from backend.infrastructure.providers.registry import provider_from_snapshot2

    snapshot = snapshot_fixture()
    snapshot[field] = value

    with pytest.raises(ApplicationError) as error:
        provider_from_snapshot2(snapshot)

    assert error.value.code == "INVALID_RUN_SNAPSHOT"


def build_snapshot_context_execution():
    return (
        {
            "trim_policy_version": "trim_then_extract_v1",
            "summary_max_tokens": 512,
            "max_candidate_messages": 200,
            "max_candidate_chars": 200_000,
            "safety_margin_tokens": 128,
            "counter_version": "mock-tokenizer@1",
        },
        {
            "max_attempts": 3,
            "deadline_seconds": 600,
            "step_timeout_seconds": 60,
            "stream_timeout_seconds": 120,
            "max_raw_deltas": 4096,
            "max_output_chars": 1_000_000,
            "delta_flush_ms": 100,
            "delta_buffer_bytes": 65_536,
            "max_regular_events": 15_000,
        },
    )


def snapshot_fixture(profile_config=None):
    from backend.infrastructure.providers.registry import profile_snapshot

    context, execution = build_snapshot_context_execution()
    profile_config = profile() if profile_config is None else profile_config
    return {
        "schema_version": 2,
        "owner_id": "owner",
        "thread_id": "thread",
        "branch_id": "branch",
        "input_anchor": {"message_id": "message", "seq": 4},
        "model_profile": profile_snapshot(type("Profile", (), profile_config)()),
        "prompt": {"version": "sesrag-system@1"},
        "context": context,
        "retrieval": {
            "enabled": True,
            "top_k": 5,
            "embedding_dimensions": 384,
            "embedding_model": "embed",
            "embedding_provider_kind": "mock",
            "embedding_base_url": None,
            "embedding_config_ref": None,
        },
        "execution": execution,
    }


def test_profile_requires_explicit_tiktoken_framing_and_calibration_settings():
    value = profile(
        provider_kind="openai_compatible",
        base_url="https://model.example/v1",
        config_ref="env:MODEL_API_KEY",
        tokenizer_kind="tiktoken",
        tokenizer_config={
            "safety_margin_tokens": 128,
            "summary_max_tokens": 512,
            "encoding_name": "cl100k_base",
        },
    )

    with pytest.raises(ValueError, match="tokenizer_config"):
        validate_profile_config(value)


def test_tiktoken_counter_uses_frozen_message_and_request_overhead():
    config = profile(
        profile_id="external",
        provider_kind="openai_compatible",
        base_url="https://model.example/v1",
        config_ref="env:MODEL_API_KEY",
        tokenizer_kind="tiktoken",
        tokenizer_config={
            "encoding_name": "cl100k_base",
            "message_overhead_tokens": 1,
            "request_overhead_tokens": 3,
            "calibration_version": "provider-frame@1",
            "safety_margin_tokens": 128,
            "summary_max_tokens": 512,
        },
    )
    counter_factory = getattr(
        __import__("backend.infrastructure.providers.context_counter", fromlist=["x"]),
        "token_counter_from_profile",
        None,
    )
    assert callable(counter_factory)

    counter = counter_factory(config)

    message = type("Message", (), {"role": "user", "content": "hello"})()
    assert counter.count_messages((message,)) == 5


def test_real_counter_identity_fits_context_plan_storage_and_is_stable():
    from backend.db.models import ContextPlanModel
    from backend.infrastructure.providers.context_counter import TikTokenCounter

    settings = {
        "encoding_name": "cl100k_base",
        "message_overhead_tokens": 1,
        "request_overhead_tokens": 3,
        "calibration_version": "provider-frame@1" * 100,
        "profile_tokenizer_version": "1" * 100,
    }

    counter = TikTokenCounter(**settings)

    assert 0 < len(counter.version) <= 40
    assert len(counter.version) <= ContextPlanModel.__table__.c.counter_version.type.length
    assert counter.version == TikTokenCounter(**dict(reversed(list(settings.items())))).version


@pytest.mark.parametrize(
    "field,value",
    [
        ("message_overhead_tokens", 2),
        ("request_overhead_tokens", 4),
        ("calibration_version", "provider-frame@2"),
        ("profile_tokenizer_version", "2"),
    ],
)
def test_real_counter_identity_changes_with_frozen_counting_settings(field, value):
    from backend.infrastructure.providers.context_counter import TikTokenCounter

    settings = {
        "encoding_name": "cl100k_base",
        "message_overhead_tokens": 1,
        "request_overhead_tokens": 3,
        "calibration_version": "provider-frame@1",
        "profile_tokenizer_version": "1",
    }

    assert (
        TikTokenCounter(**settings).version != TikTokenCounter(**{**settings, field: value}).version
    )


def test_snapshot_builder_deep_copies_nested_policy_and_tokenizer_config():
    from backend.infrastructure.providers.registry import build_snapshot2

    profile_value = profile()
    frozen_profile = profile_snapshot(type("Profile", (), profile_value)())
    context, execution = build_snapshot_context_execution()
    snapshot = build_snapshot2(
        owner_id="owner",
        thread_id="thread",
        branch_id="branch",
        input_anchor={"message_id": "message", "seq": 4},
        profile=frozen_profile,
        prompt={"version": "sesrag-system@1"},
        retrieval={
            "enabled": True,
            "top_k": 5,
            "embedding_dimensions": 384,
            "embedding_model": "embed",
            "embedding_provider_kind": "mock",
            "embedding_base_url": None,
            "embedding_config_ref": None,
        },
        context=context,
        execution=execution,
    )

    profile_value["tokenizer_config"]["safety_margin_tokens"] = 0
    context["max_candidate_messages"] = 1
    execution["max_attempts"] = 1

    assert snapshot["model_profile"]["tokenizer_config"]["safety_margin_tokens"] == 128
    assert snapshot["context"]["max_candidate_messages"] == 200
    assert snapshot["execution"]["max_attempts"] == 3
