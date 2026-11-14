"""阶段观测为旁路；记录失败不得改变业务返回或异常。"""

from contextlib import asynccontextmanager, nullcontext, suppress
from contextvars import ContextVar
from functools import wraps
from time import monotonic

from backend.application.observation import current_attempt, current_runtime, current_stage

observer = ContextVar("stage_observer", default=None)


@asynccontextmanager
async def observe_stage(stage, outcome=None):
    start = monotonic()
    code = None
    handle = StageOutcomeHandle(outcome or "ok")
    runtime = current_runtime.get()
    span = None
    with suppress(Exception):
        span = runtime.start_span("stage." + stage, stage=stage) if runtime else None
    token = current_stage.set(stage)
    try:
        with span.activate() if span else nullcontext():
            yield handle
    except BaseException as exc:
        fallback = "STAGE_FAILED" if isinstance(exc, Exception) else "EXECUTION_STOPPED"
        code = getattr(exc, "code", fallback)
        handle.set_outcome("error" if isinstance(exc, Exception) else "cancelled")
        if type(exc).__name__ == "ExecutionStopped":
            handle.set_outcome("stopped")
        raise
    finally:
        current_stage.reset(token)
        duration = max(0, (monotonic() - start) * 1000)
        with suppress(Exception):
            attempt = current_attempt.get()
            if runtime and attempt:
                runtime.metrics.observe(
                    "STAGE_DURATION",
                    attempt.identity.task_kind,
                    stage,
                    handle.outcome,
                    seconds=duration / 1000,
                )
                with span.activate() if span else nullcontext():
                    runtime.log("stage", stage=stage, duration_ms=duration, error_code=code)
            if span:
                span.end(outcome=handle.outcome)
        callback = observer.get()
        if callback is not None:
            with suppress(Exception):
                await callback(stage, duration, code)


class StageOutcomeHandle:
    def __init__(self, outcome="ok"):
        self.outcome = outcome

    def set_outcome(self, mode):
        if mode in {"ok", "error", "cancelled", "stopped", "empty", "degraded"}:
            self.outcome = mode


def observed_stage(name):
    def decorate(function):
        @wraps(function)
        async def invoke(*args, **kwargs):
            async with observe_stage(name) as stage:
                result = await function(*args, **kwargs)
                mode = getattr(result, "mode", None)
                if mode in {"empty", "degraded"}:
                    stage.set_outcome(mode)
                return result

        return invoke

    return decorate
