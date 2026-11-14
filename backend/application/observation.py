"""应用层旁路facade；无runtime或记录器失败均保持原业务语义。"""

import inspect
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from functools import wraps

from backend.domain.observability import CommitReceipt, ExecutionIdentity

current_runtime = ContextVar("observation_runtime", default=None)
current_attempt = ContextVar("observation_attempt", default=None)
settlement_reason = ContextVar("observation_settlement_reason", default=None)
pending_producers = ContextVar("observation_pending_producers", default=None)
current_stage = ContextVar("observation_current_stage", default=None)
active_operation = ContextVar("observation_active_operation", default=None)


@contextmanager
def bind(runtime):
    token = current_runtime.set(runtime)
    try:
        yield
    finally:
        current_runtime.reset(token)


def enqueue(session, task):
    runtime = current_runtime.get()
    if runtime is not None:
        with suppress(Exception):
            runtime.enqueue(session, task)


def receipt(session, task, result, *, retry_scheduled=False, error_code=None):
    runtime = current_runtime.get()
    observed = current_attempt.get()
    if runtime is None or observed is None:
        return
    with suppress(Exception):
        identity = ExecutionIdentity(
            task.task_id, task.kind, task.worker_id, task.generation, task.attempt
        )
        # yield会清除worker_id，必须在该改变之前登记。
        result = "released" if settlement_reason.get() == "shutdown" else result
        runtime.receipt(session, CommitReceipt(identity, result, retry_scheduled, error_code))


def log(action, **fields):
    runtime = current_runtime.get()
    if runtime is not None:
        with suppress(Exception):
            runtime.log(action, **fields)


def correlate(**fields):
    """只补充当前尝试可确定的安全业务身份，不更改授权/结算身份。"""
    observed = current_attempt.get()
    if observed is not None:
        with suppress(Exception):
            observed.correlation.update(
                (key, value)
                for key, value in fields.items()
                if key
                in {
                    "thread_id",
                    "run_id",
                    "document_id",
                    "index_batch_id",
                    "parse_job_id",
                    "retrieval_execution_id",
                }
            )


def observe_control(operation):
    def decorate(function):
        @wraps(function)
        async def invoke(*args, **kwargs):
            runtime = current_runtime.get()
            result = "error"
            try:
                value = await function(*args, **kwargs)
                result = (
                    "empty"
                    if operation in {"claim", "reclaim"} and not value
                    else "rejected"
                    if value is False
                    else "ok"
                )
                return value
            finally:
                if runtime:
                    with suppress(Exception):
                        runtime.metrics.inc("WORKER_CONTROL", operation, result)

        return invoke

    return decorate


def observed_call(operation, backend="remote"):
    """流式适配器只在每次anext的当前Task绑定context，不跨yield保存token。"""

    def decorate(function):
        def start(kwargs):
            runtime = current_runtime.get()
            name = operation
            if name == "embedding":
                default = (
                    "query"
                    if current_stage.get() in {"query_embedding", "retrieval"}
                    else "document"
                )
                purpose = kwargs.get("purpose", default)
                name = "embedding.query" if purpose == "query" else "embedding.document"
            if runtime and active_operation.get() != name:
                with suppress(Exception):
                    return runtime.downstream(name, backend)
            return None

        if inspect.isasyncgenfunction(function):

            @wraps(function)
            async def stream(*args, **kwargs):
                call = start(kwargs)
                generator = function(*args, **kwargs)
                error = None
                try:
                    while True:
                        try:
                            if call:
                                with call.activate():
                                    value = await anext(generator)
                            else:
                                value = await anext(generator)
                        except StopAsyncIteration:
                            break
                        yield value
                except BaseException as exc:
                    error = exc
                    raise
                finally:
                    try:
                        if call:
                            with call.activate():
                                await generator.aclose()
                        else:
                            await generator.aclose()
                    finally:
                        if call:
                            call.finish(error)

            return stream

        if not inspect.iscoroutinefunction(function):

            @wraps(function)
            def sync(*args, **kwargs):
                call = start(kwargs)
                error = None
                try:
                    if call:
                        with call.activate():
                            return function(*args, **kwargs)
                    return function(*args, **kwargs)
                except BaseException as exc:
                    error = exc
                    raise
                finally:
                    if call:
                        call.finish(error)

            return sync

        @wraps(function)
        async def invoke(*args, **kwargs):
            call = start(kwargs)
            error = None
            try:
                if call:
                    with call.activate():
                        return await function(*args, **kwargs)
                return await function(*args, **kwargs)
            except BaseException as exc:
                error = exc
                raise
            finally:
                if call:
                    call.finish(error)

        return invoke

    return decorate
