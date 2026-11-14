"""纯ASGI边界：忽略公网追踪头，不记录URL、请求体或异常原文。"""

import asyncio
import re
import time
from contextlib import suppress

from opentelemetry.trace import SpanKind

from backend.application.observation import bind, pending_producers
from backend.infrastructure.observability.metrics import CATALOG
from backend.infrastructure.observability.tracing import span_budget

REQUESTS = next(i for i in CATALOG if i["logical_id"] == "HTTP_REQUESTS")
ROUTES = sorted(
    {(t[0], t[1], t[3]) for t in REQUESTS["allowed_tuples"] if t[1] != "__unmatched__"},
    key=lambda t: (t[1].count("{"), -len(t[1])),
)
MATCHERS = [
    (method, route, kind, re.compile(re.sub(r"\{[^}]+\}", "[^/]+", route)))
    for method, route, kind in ROUTES
]


class ObservabilityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        runtime = (
            getattr(scope.get("app").state, "observability", None) if scope.get("app") else None
        )
        if scope["type"] != "http" or runtime is None:
            await self.app(scope, receive, send)
            return
        method = (
            scope["method"]
            if scope["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            else "OTHER"
        )
        route, kind = "__unmatched__", "short"
        for m, r, k, matcher in MATCHERS:
            if m == method and matcher.fullmatch(scope["path"]):
                route, kind = r, k
                break
        span = runtime.tracing.start(
            "http.request", root=True, kind=SpanKind.SERVER, method=method, route=route
        )
        started, status, sse, disconnected, cancelled, failed = (
            time.monotonic(),
            None,
            False,
            False,
            False,
            False,
        )
        pending = set()
        producers = pending_producers.set(pending)
        budget = span_budget.set([0])

        async def observe_receive():
            nonlocal disconnected
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected = True
            return message

        async def observe_send(message):
            nonlocal status, sse
            if message["type"] == "http.response.start":
                status = message["status"]
                sse = any(
                    k.lower() == b"content-type" and v.startswith(b"text/event-stream")
                    for k, v in message.get("headers", [])
                )
                with suppress(Exception):
                    runtime.metrics.http_request(method, route, f"{status // 100}xx", kind)
                    if sse:
                        runtime.metrics.inc("SSE_ACTIVE", route)
                        runtime.metrics.inc("SSE_OPEN", route)
            await send(message)

        try:
            with bind(runtime), span.activate():
                try:
                    await self.app(scope, observe_receive, observe_send)
                except asyncio.CancelledError:
                    cancelled = True
                    raise
                except BaseException:
                    failed = True
                    raise
                finally:
                    with suppress(Exception):
                        elapsed = max(0, time.monotonic() - started)
                        if status is None:
                            if cancelled or disconnected:
                                runtime.metrics.inc(
                                    "HTTP_ABORTED",
                                    method,
                                    route,
                                    "disconnected" if disconnected else "cancelled",
                                )
                            else:
                                runtime.metrics.http_request(method, route, "5xx", kind)
                        if kind == "short":
                            runtime.metrics.observe("HTTP_DURATION", method, route, seconds=elapsed)
                        if sse:
                            reason = (
                                "error"
                                if failed
                                else "disconnected"
                                if disconnected
                                else "cancelled"
                                if cancelled
                                else scope.get("sesrag_sse_close", "unknown")
                            )
                            runtime.metrics.inc("SSE_ACTIVE", route, amount=-1)
                            runtime.metrics.inc("SSE_CLOSE", route, reason)
                            runtime.metrics.observe("SSE_DURATION", route, reason, seconds=elapsed)
                        runtime.log("request", duration_ms=elapsed * 1000)
                        runtime.finish_pending(pending)
                        span.end(status_class=f"{status // 100}xx" if status else None)
        finally:
            span_budget.reset(budget)
            pending_producers.reset(producers)
