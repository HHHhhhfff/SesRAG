"""监听冲突/重复关闭不能影响业务生命周期，配置错误只降级观测。"""

import io
import socket

import pytest

from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.runtime import ObservabilityRuntime


@pytest.mark.asyncio
async def test_bind_conflict_is_visible_and_does_not_escape_runtime_start():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        runtime = ObservabilityRuntime(
            load_config(
                "worker",
                {
                    "OBS_METRICS_HOST": "127.0.0.1",
                    "OBS_METRICS_PORT": str(occupied.getsockname()[1]),
                },
            ),
            log_stream=io.StringIO(),
        )
        await runtime.start()
        assert runtime.listener is None
        assert (
            runtime.metrics.child("OBSERVATION_EVENTS", "metrics", "bind_failed")._value.get() == 1
        )
        await runtime.close()
        await runtime.close()
