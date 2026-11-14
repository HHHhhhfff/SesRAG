"""独立解析观测配置，错误不会阻止业务 Settings 初始化。"""

import ipaddress
import math
import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    service: str
    environment: str
    metrics_enabled: bool
    metrics_host: str
    metrics_port: int
    traces_enabled: bool
    endpoint: str | None
    allowed_hosts: frozenset[str]
    sample_ratio: float
    diagnostics: tuple[str, ...]


def _boolean(value: str) -> bool:
    if value.casefold() in {"true", "1"}:
        return True
    if value.casefold() in {"false", "0"}:
        return False
    raise ValueError("invalid boolean")


def load_config(role: str, env: Mapping[str, str]) -> ObservabilityConfig:
    if role not in {"api", "worker"}:
        raise ValueError("unsupported service role")
    issues: list[str] = []
    service = f"sesrag-{role}"
    environment = env.get("OBS_ENVIRONMENT", "local")
    if not re.fullmatch(r"[a-z0-9-]{1,32}", environment):
        environment = "local"
        issues.append("invalid_environment")
    identity_valid = env.get("OBS_SERVICE_NAME", service) == service
    if not identity_valid:
        issues.append("invalid_service")
    metrics = False
    host = env.get("OBS_METRICS_HOST", "0.0.0.0")
    port = 9101 if role == "api" else 9102
    try:
        metrics = _boolean(env.get("OBS_METRICS_ENABLED", "true")) and identity_valid
        port = int(env.get("OBS_METRICS_PORT", str(port)))
        if not 1 <= port <= 65535 or host not in {"0.0.0.0", "127.0.0.1"}:
            raise ValueError("invalid listener")
    except ValueError:
        metrics = False
        issues.append("invalid_metrics")
    endpoint = env.get("OBS_OTLP_TRACES_ENDPOINT") or None
    allowed = frozenset(
        filter(None, (x.strip().lower() for x in env.get("OBS_OTLP_ALLOWED_HOSTS", "").split(",")))
    )
    traces = False
    ratio = 1.0
    try:
        traces = _boolean(env.get("OBS_TRACES_ENABLED", "false")) and identity_valid
        ratio = float(env.get("OBS_TRACE_SAMPLE_RATIO", "1.0"))
        if not math.isfinite(ratio) or not 0 <= ratio <= 1:
            raise ValueError("invalid ratio")
        if traces:
            parsed = urlsplit(endpoint or "")
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.hostname.lower() not in allowed
                or parsed.path != "/v1/traces"
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or any(not re.fullmatch(r"[a-z0-9.-]+", h) for h in allowed)
                or any(key.startswith("OTEL_") for key in env)
            ):
                raise ValueError("invalid destination")
            if parsed.port == 0:
                raise ValueError("invalid port")
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                address = None
            if address is not None and not internal_address(address):
                raise ValueError("public receiver")
    except ValueError:
        traces = False
        issues.append("invalid_tracing")
    return ObservabilityConfig(
        service, environment, metrics, host, port, traces, endpoint, allowed, ratio, tuple(issues)
    )


def from_settings(role, settings):
    env = {
        key.upper(): value
        for key, value in settings.model_dump().items()
        if key.startswith("obs_") and value is not None
    }
    env.update({key: value for key, value in os.environ.items() if key.startswith("OTEL_")})
    return load_config(role, env)


def internal_address(address):
    return address.is_loopback or any(
        address in subnet
        for subnet in (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("fc00::/7"),
        )
        if address.version == subnet.version
    )
