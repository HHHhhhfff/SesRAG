"""指标必须区分未获得快照和已知零。"""

from prometheus_client import generate_latest

from backend.infrastructure.observability.metrics import ObservabilityMetrics


def test_unknown_queue_is_absent_until_first_success():
    metrics = ObservabilityMetrics("sesrag-api", "local")
    before = generate_latest(metrics.registry).decode()
    assert (
        'sesrag_snapshot_valid{environment="local",service="sesrag-api",source="queue"} 0.0'
        in before
    )
    assert "sesrag_queue_ready_tasks{" not in before
    metrics.queue_snapshot({"run": (0, 0)})
    after = generate_latest(metrics.registry).decode()
    assert (
        'sesrag_queue_ready_tasks{environment="local",service="sesrag-api",task_kind="run"} 0.0'
        in after
    )


def test_separate_registries_do_not_share_request_counters():
    first = ObservabilityMetrics("sesrag-api", "local")
    second = ObservabilityMetrics("sesrag-api", "local")
    first.http_request("GET", "/api/v1/threads", "2xx", "short")
    assert first.child("HTTP_REQUESTS", "GET", "/api/v1/threads", "2xx", "short")._value.get() == 1
    assert second.child("HTTP_REQUESTS", "GET", "/api/v1/threads", "2xx", "short")._value.get() == 0
