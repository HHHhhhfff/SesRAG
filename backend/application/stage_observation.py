"""阶段观测为旁路；记录失败不得改变业务返回或异常。"""

from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from time import monotonic

observer = ContextVar("stage_observer", default=None)


@asynccontextmanager
async def observe_stage(stage):
    start = monotonic()
    code = None
    try:
        yield
    except BaseException as exc:
        fallback = "STAGE_FAILED" if isinstance(exc, Exception) else "EXECUTION_STOPPED"
        code = getattr(exc, "code", fallback)
        raise
    finally:
        callback = observer.get()
        if callback is not None:
            with suppress(Exception):
                await callback(stage, max(0, (monotonic() - start) * 1000), code)
