"""使用真实SDK exporter发送并解码protobuf，避免只测Session假入口。"""

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from backend.domain.observability import TraceOrigin
from backend.infrastructure.observability.config import load_config
from backend.infrastructure.observability.exporter import SafeExporter
from backend.infrastructure.observability.metrics import ObservabilityMetrics
from backend.infrastructure.observability.tracing import Tracing


def test_slow_drip_headers_cannot_extend_total_deadline():
    import pytest
    import requests

    from backend.infrastructure.observability.exporter import FixedEndpointSession

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def drip():
        connection, _ = listener.accept()
        try:
            connection.recv(8192)
            connection.sendall(b"HTTP/1.1 200 OK\r\n")
            for _ in range(12):
                time.sleep(0.1)
                connection.sendall(b"X-Slow: x\r\n")
            connection.sendall(b"Content-Length: 0\r\n\r\n")
        except OSError:
            pass
        finally:
            connection.close()

    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{listener.getsockname()[1]}/v1/traces"
    session = FixedEndpointSession(endpoint, {"127.0.0.1"})
    try:
        started = time.monotonic()
        with pytest.raises(requests.RequestException):
            session.request("POST", endpoint, data=b"x", timeout=0.35)
        assert time.monotonic() - started < 0.7
    finally:
        session.close()
        listener.close()
        thread.join(2)


def test_actual_sdk_transport_uses_fixed_request_and_protobuf():
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append(
                ExportTraceServiceRequest.FromString(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
            )
            assert not self.headers.get("traceparent")
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = load_config(
        "worker",
        {
            "OBS_TRACES_ENABLED": "true",
            "OBS_OTLP_TRACES_ENDPOINT": f"http://127.0.0.1:{server.server_port}/v1/traces",
            "OBS_OTLP_ALLOWED_HOSTS": "127.0.0.1",
        },
    )
    metrics = ObservabilityMetrics("sesrag-worker", "local")
    tracing = Tracing(config, SafeExporter(config, metrics, lambda *args: None))
    try:
        origin = TraceOrigin(1, "a" * 32, "b" * 16, True)
        span = tracing.start("task.attempt", origin=origin)
        assert span.origin() is not None
        span.end(result="yielded")
        assert tracing.provider.force_flush(2000)
        assert captured
        actual = captured[0].resource_spans[0].scope_spans[0].spans[0]
        assert actual.trace_id.hex() == "a" * 32 and actual.parent_span_id.hex() == "b" * 16
        assert metrics.child("TRACE_EXPORT", "success")._value.get() == 1
    finally:
        tracing.provider.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(1)
