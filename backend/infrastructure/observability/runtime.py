"""应用观测唯一装配点，所有记录操作仅写有界内存旁路。"""

import asyncio
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import asdict

from opentelemetry.trace import SpanKind

from backend.application.observation import (
    active_operation,
    bind,
    current_attempt,
    pending_producers,
)
from backend.infrastructure.observability.exporter import SafeExporter
from backend.infrastructure.observability.logging import SafeLogger, suppress_library_logs
from backend.infrastructure.observability.metrics import ObservabilityMetrics
from backend.infrastructure.observability.metrics_http import MetricsServer
from backend.infrastructure.observability.tracing import Tracing, span_budget
from backend.infrastructure.observability.transactions import after_transaction


class AttemptObservation:
    def __init__(self, runtime, identity, origin, origin_state=None):
        self.runtime, self.identity = runtime, identity
        self.result = None
        self.correlation = {}
        self.retry_scheduled = False
        self.ended = False
        self.started = time.monotonic()
        self.origin_state = origin_state or ("present" if origin else "missing")
        if runtime.config.traces_enabled and self.origin_state in {"missing", "invalid"}:
            runtime.event("context", "origin_" + self.origin_state)
        self.span = runtime.tracing.start(
            "task.attempt",
            origin=origin,
            root=origin is None,
            kind=SpanKind.CONSUMER,
            origin_state=self.origin_state,
            **asdict(identity),
        )
        runtime.metrics.inc("ATTEMPT_ACTIVE", identity.task_kind)

    def confirm(self, receipt):
        if not self.ended and self.result is None and receipt.identity == self.identity:
            if receipt.result in {"succeeded", "failed", "yielded", "cancelled", "released"}:
                self.result, self.retry_scheduled = receipt.result, receipt.retry_scheduled

    def stopped(self, reason):
        if not self.ended and self.result is None and reason in {"unknown", "lease_lost"}:
            self.result = reason

    def finish(self):
        if self.ended:
            return self.result
        self.ended = True
        self.result = self.result or "unknown"
        duration = max(0, time.monotonic() - self.started)
        m, k = self.runtime.metrics, self.identity.task_kind
        m.inc("TASK_ATTEMPTS", k, self.result)
        m.inc("ATTEMPT_ACTIVE", k, amount=-1)
        m.observe("ATTEMPT_DURATION", k, self.result, seconds=duration)
        self.runtime.log(
            "attempt_" + self.result,
            **asdict(self.identity),
            origin_state=self.origin_state,
            duration_ms=duration * 1000,
        )
        self.span.end(result=self.result, retry_scheduled=self.retry_scheduled)
        return self.result


class DownstreamObservation:
    def __init__(self, runtime, operation, backend):
        self.runtime, self.operation = runtime, operation
        self.started, self.ended = time.monotonic(), False
        self.span = runtime.start_span(operation, operation=operation, backend=backend)

    @contextmanager
    def activate(self):
        token = active_operation.set(self.operation)
        try:
            with self.span.activate():
                yield
        finally:
            active_operation.reset(token)

    def finish(self, error=None):
        if self.ended:
            return
        self.ended = True
        code = getattr(error, "code", "")
        outcome = (
            "ok"
            if error is None
            else "cancelled"
            if isinstance(error, (asyncio.CancelledError, GeneratorExit))
            else "timeout"
            if isinstance(error, TimeoutError) or "TIMEOUT" in code
            else "error"
        )
        duration = time.monotonic() - self.started
        with suppress(Exception):
            self.runtime.metrics.inc("DOWNSTREAM_CALLS", self.operation, outcome)
            self.runtime.metrics.observe(
                "DOWNSTREAM_DURATION", self.operation, outcome, seconds=duration
            )
            self.span.end(outcome=outcome)


class ObservabilityRuntime:
    def __init__(self, config, *, exporter=None, log_stream=None):
        self.config = config
        self.metrics = ObservabilityMetrics(config.service, config.environment)
        self._diagnosed = {}
        self.logger = SafeLogger(
            config.service,
            config.environment,
            stream=log_stream,
            on_error=lambda reason: self.event("logs", reason, log=False),
        )
        self.tracing = Tracing(
            config,
            exporter
            if exporter is not None
            else SafeExporter(config, self.metrics, self.event)
            if config.traces_enabled
            else None,
        )
        self.listener = None
        self.snapshots = None
        self._closed = False
        self._pending = set()

    async def start(self, settings=None):
        suppress_library_logs()
        if self.config.metrics_enabled:
            try:
                self.listener = MetricsServer(
                    self.config.metrics_host,
                    self.config.metrics_port,
                    self.metrics.registry,
                    lambda reason: self.event("metrics", reason),
                    self.metrics.expire_snapshots,
                )
                self.listener.start()
            except Exception:
                self.event("metrics", "bind_failed")
                if self.listener:
                    self.listener.close()
                self.listener = None
            if self.config.service == "sesrag-api" and settings:
                from backend.infrastructure.observability.snapshots import SnapshotPoller

                self.snapshots = SnapshotPoller(settings, self.metrics, self.event)
                self.snapshots.start()
        for _ in self.config.diagnostics:
            self.event("config", "invalid_config")
        self.log("startup")

    def event(self, component, reason, *, log=True):
        with suppress(Exception):
            self.metrics.inc("OBSERVATION_EVENTS", component, reason)
            key, now = (component, reason), time.monotonic()
            if log and now - self._diagnosed.get(key, -60) >= 30:
                self._diagnosed[key] = now
                self.logger.emit("diagnostic")

    def log(self, action, **fields):
        with suppress(Exception):
            current = current_attempt.get()
            correlated = asdict(current.identity) if current else {}
            if current:
                correlated.update(current.correlation)
                correlated["origin_state"] = current.origin_state
            correlated.pop("task_kind", None)
            correlated.update(self.tracing.fields())
            if current is None:
                correlated["origin_state"] = "present" if self.tracing.tracer else "disabled"
            correlated.update(
                (key, value)
                for key, value in fields.items()
                if value is not None or key not in correlated
            )
            self.logger.emit(action, **correlated)

    def start_span(self, name, **attrs):
        from backend.infrastructure.observability.tracing import SpanHandle

        if self._closed:
            return SpanHandle()
        budget = span_budget.get()
        if budget is not None:
            if budget[0] >= 128:
                if budget[0] == 128:
                    self.event("traces", "span_limit")
                    budget[0] += 1
                return SpanHandle()
            budget[0] += 1
        return self.tracing.start(name, **attrs)

    def downstream(self, operation, backend):
        return DownstreamObservation(self, operation, backend)

    @contextmanager
    def attempt(self, identity, origin, origin_state=None):
        try:
            observed = AttemptObservation(self, identity, origin, origin_state)
        except Exception:
            self.event("context", "context_error")
            with bind(self):
                yield None
            return
        token = current_attempt.set(observed)
        budget = span_budget.set([0])
        try:
            with bind(self), observed.span.activate():
                yield observed
        finally:
            try:
                with suppress(Exception):
                    with observed.span.activate():
                        observed.finish()
            finally:
                span_budget.reset(budget)
                current_attempt.reset(token)

    def receipt(self, session, receipt):
        observed = current_attempt.get()
        if observed and observed.identity == receipt.identity:
            after_transaction(session, lambda: observed.confirm(receipt), lambda: None)

    def enqueue(self, session, task):
        if not self.tracing.tracer or self._closed:
            return
        span = self.tracing.start(
            "task.enqueue", kind=SpanKind.PRODUCER, task_id=task.task_id, task_kind=task.kind
        )
        origin = span.origin()
        task.trace_origin_json = origin.to_json() if origin else None
        self._pending.add(span)
        scope_pending = pending_producers.get()
        if scope_pending is not None:
            scope_pending.add(span)

        def done(result):
            self._pending.discard(span)
            span.end(result=result)
            with span.activate():
                self.log("enqueue", task_id=task.task_id)

        try:
            after_transaction(session, lambda: done("committed"), lambda: done("rolled_back"))
        except Exception:
            task.trace_origin_json = None
            done("commit_unknown")
            self.event("context", "context_error")

    def finish_pending(self, pending):
        for span in tuple(pending):
            if span in self._pending:
                span.end(result="commit_unknown")
                self._pending.discard(span)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        started = time.monotonic()
        self.finish_pending(tuple(self._pending))
        if self.snapshots:
            await self.snapshots.close()
        if self.listener:
            await asyncio.to_thread(self.listener.close)
        self.log("shutdown")
        completed = threading.Event()

        def shutdown():
            try:
                if self.tracing.provider:
                    self.tracing.provider.shutdown()
            finally:
                completed.set()

        threading.Thread(target=shutdown, daemon=True, name="obs-traces-close").start()
        remaining = max(0, 3 - (time.monotonic() - started))
        await asyncio.gather(
            asyncio.to_thread(completed.wait, remaining),
            asyncio.to_thread(self.logger.close, remaining),
        )
        if not completed.is_set():
            self.event("traces", "flush_timeout", log=False)
