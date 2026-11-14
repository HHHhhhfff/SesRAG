"""独立SDK provider、安全span和可跨流存活的显式handle。"""

from contextlib import nullcontext
from contextvars import ContextVar

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import NonRecordingSpan, SpanContext, SpanKind, TraceFlags

from backend.domain.observability import TraceOrigin

span_budget = ContextVar("observation_span_budget", default=None)
SAFE_ATTRIBUTES = {
    "task_id",
    "task_kind",
    "worker_id",
    "generation",
    "attempt",
    "run_id",
    "document_id",
    "index_batch_id",
    "retrieval_execution_id",
    "parse_job_id",
    "stage",
    "outcome",
    "origin_state",
    "operation",
    "backend",
    "route",
    "method",
    "status_class",
    "result",
    "retry_scheduled",
    "error_code",
    "reason",
}


class SpanHandle:
    def __init__(self, span=None):
        self.span = span
        self.ended = False

    def activate(self):
        return (
            trace.use_span(
                self.span, end_on_exit=False, record_exception=False, set_status_on_exception=False
            )
            if self.span
            else nullcontext()
        )

    def end(self, **attributes):
        if self.ended:
            return
        self.ended = True
        if self.span:
            self.span.set_attributes(
                {k: v for k, v in attributes.items() if k in SAFE_ATTRIBUTES and v is not None}
            )
            self.span.end()

    def origin(self):
        if self.span:
            sc = self.span.get_span_context()
            if sc.is_valid:
                return TraceOrigin(
                    1, f"{sc.trace_id:032x}", f"{sc.span_id:016x}", sc.trace_flags.sampled
                )
        return None


class Tracing:
    def __init__(self, config, exporter=None):
        self.provider = None
        self.tracer = None
        if not config.traces_enabled:
            return
        self.provider = TracerProvider(
            resource=Resource(
                {
                    "service.name": config.service,
                    "service.version": "0.3.0",
                    "deployment.environment.name": config.environment,
                }
            ),
            sampler=ParentBased(TraceIdRatioBased(config.sample_ratio)),
            span_limits=SpanLimits(
                max_attributes=24, max_events=0, max_links=0, max_attribute_length=256
            ),
            shutdown_on_exit=False,
        )
        if exporter is not None:
            self.provider.add_span_processor(
                BatchSpanProcessor(
                    exporter,
                    max_queue_size=1024,
                    max_export_batch_size=128,
                    schedule_delay_millis=500,
                    export_timeout_millis=2000,
                )
            )
        self.tracer = self.provider.get_tracer("sesrag.observation", "1")

    def start(self, name, *, origin=None, root=False, kind=SpanKind.INTERNAL, **attributes):
        try:
            return self._start(name, origin=origin, root=root, kind=kind, **attributes)
        except Exception:
            # SDK采样/上下文错误不得改变业务；外部通过缺失span与诊断发现缺口。
            return SpanHandle()

    def _start(self, name, *, origin=None, root=False, kind=SpanKind.INTERNAL, **attributes):
        if self.tracer is None:
            return SpanHandle()
        context = Context() if root else None
        if origin:
            sc = SpanContext(
                int(origin.trace_id, 16),
                int(origin.span_id, 16),
                True,
                TraceFlags(TraceFlags.SAMPLED if origin.sampled else TraceFlags.DEFAULT),
            )
            context = trace.set_span_in_context(NonRecordingSpan(sc), Context())
        attrs = {
            k: v[:256] if isinstance(v, str) else v
            for k, v in attributes.items()
            if k in SAFE_ATTRIBUTES and isinstance(v, (str, bool, int, float))
        }
        return SpanHandle(
            self.tracer.start_span(name, context=context, kind=kind, attributes=attrs)
        )

    def fields(self):
        if not self.tracer:
            return dict(trace_id=None, span_id=None, trace_sampled=None)
        sc = trace.get_current_span().get_span_context()
        return dict(
            trace_id=f"{sc.trace_id:032x}" if sc.is_valid else None,
            span_id=f"{sc.span_id:016x}" if sc.is_valid else None,
            trace_sampled=sc.trace_flags.sampled if sc.is_valid else None,
        )
