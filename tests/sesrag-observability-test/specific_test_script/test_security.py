"""A12：真实适配器请求头、日志和指标出口敏感哨兵。"""

import asyncio

import httpx
from evidence import metrics, spans

from backend.application.observation import bind
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.exporter import FixedEndpointSession
from backend.infrastructure.observability.runtime import ObservabilityRuntime
from backend.infrastructure.providers.openai_compatible import OpenAICompatibleProvider


async def adapter():
    seen = []
    original = httpx.AsyncClient

    def response(request):
        seen.append(dict(request.headers))
        return httpx.Response(200, json={"data": [{"embedding": [1.0] + [0.0] * 383}]})

    def factory(*args, **kwargs):
        return original(*args, **kwargs, transport=httpx.MockTransport(response))

    httpx.AsyncClient = factory
    try:
        runtime = ObservabilityRuntime(load_config("worker", {"OBS_METRICS_ENABLED": "false"}))
        with bind(runtime):
            await OpenAICompatibleProvider(
                "https://model.test", "OBS_SECRET_SENTINEL", "model", "embed"
            ).embed("OBS_PROMPT_SENTINEL")
        await runtime.close()
    finally:
        httpx.AsyncClient = original
    assert seen and not any(key in seen[0] for key in ("traceparent", "tracestate", "baggage"))


def run():
    asyncio.run(adapter())
    assert spans()["counts"]["unsafe"] == 0
    for role in ("api", "worker"):
        output = metrics(role)
        assert not any(
            x in output for x in ("OBS_SECRET_SENTINEL", "OBS_PROMPT_SENTINEL", "OBS_URL_SENTINEL")
        )
    session = FixedEndpointSession("http://8.8.8.8/v1/traces", frozenset({"8.8.8.8"}))
    try:
        try:
            session.post("http://8.8.8.8/v1/traces", data=b"x")
        except Exception:
            pass
        else:
            raise AssertionError("公网OTLP接收地址未拒绝")
    finally:
        session.close()
    return {"outbound_w3c_headers": False, "public_otlp_rejected": True, "sensitive_scan": "clean"}
