"""观测配置错误只影响对应观测能力，不改变业务配置。"""

import pytest

from backend.infrastructure.observability.config import load_config


def test_default_never_enables_trace_export():
    config = load_config("api", {})
    assert config.metrics_enabled is True
    assert config.metrics_port == 9101
    assert config.traces_enabled is False
    assert config.endpoint is None


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/v1/traces?secret=x",
        "http://example.com/v1/traces",
        "http://collector:4318/other",
        "http://user:password@collector:4318/v1/traces",
    ],
)
def test_invalid_endpoint_disables_trace_without_disabling_metrics(endpoint):
    config = load_config(
        "worker",
        {
            "OBS_TRACES_ENABLED": "true",
            "OBS_OTLP_TRACES_ENDPOINT": endpoint,
            "OBS_OTLP_ALLOWED_HOSTS": "collector",
        },
    )
    assert config.traces_enabled is False
    assert config.metrics_enabled is True
    assert config.diagnostics


def test_explicit_internal_endpoint_and_sampling():
    config = load_config(
        "worker",
        {
            "OBS_TRACES_ENABLED": "true",
            "OBS_OTLP_TRACES_ENDPOINT": "http://collector:4318/v1/traces",
            "OBS_OTLP_ALLOWED_HOSTS": "collector",
            "OBS_TRACE_SAMPLE_RATIO": "0.25",
        },
    )
    assert config.traces_enabled is True
    assert config.sample_ratio == 0.25
    assert config.metrics_port == 9102
