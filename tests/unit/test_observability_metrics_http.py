"""指标端点只能读取本进程指标。"""

from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from backend.infrastructure.observability.metrics import ObservabilityMetrics
from backend.infrastructure.observability.metrics_http import MetricsServer


def test_metrics_server_only_exposes_metrics():
    metrics = ObservabilityMetrics("sesrag-api", "local")
    server = MetricsServer("127.0.0.1", 0, metrics.registry)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        with urlopen(base + "/metrics", timeout=2) as response:
            assert b"sesrag_snapshot_valid" in response.read()
        with pytest.raises(HTTPError) as exc:
            urlopen(base + "/other", timeout=2)
        assert exc.value.code == 404
    finally:
        server.close()
