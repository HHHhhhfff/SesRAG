"""OTLP固定内网端点；地址固定后连接，禁代理、重定向与环境凭据。"""

import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from backend.infrastructure.observability.config import internal_address


class DeadlineReader:
    """同时约束status/header/chunk/body；持续小字节不能重置总预算。"""

    def __init__(self, stream, sock, deadline):
        self.stream, self.sock, self.deadline = stream, sock, deadline
        self.line_bytes = 0

    def read1(self, size=-1):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.sock.settimeout(remaining)
        return self.stream.read1(size)

    def read(self, size=-1):
        if size < 0:
            raise ValueError("unbounded response read")
        result = bytearray()
        while len(result) < size:
            chunk = self.read1(size - len(result))
            if not chunk:
                break
            result.extend(chunk)
        return bytes(result)

    def readline(self, limit=-1):
        limit = min(limit if limit >= 0 else 8193, 8193)
        line = bytearray()
        while len(line) < limit:
            chunk = self.read1(1)
            if not chunk:
                break
            line.extend(chunk)
            self.line_bytes += 1
            if self.line_bytes > 8192:
                raise ValueError("response header limit")
            if chunk == b"\n":
                break
        return bytes(line)

    def __getattr__(self, name):
        return getattr(self.stream, name)


class FixedEndpointSession(requests.Session):
    def __init__(self, endpoint, allowed_hosts):
        super().__init__()
        self.trust_env = False
        self.endpoint = endpoint
        self.allowed_hosts = allowed_hosts

    def request(self, method, url, data=None, timeout=2, **kwargs):
        deadline = time.monotonic() + min(float(timeout), 2)
        if (
            method.upper() != "POST"
            or url != self.endpoint
            or not isinstance(data, bytes)
            or len(data) > 1024**2
        ):
            raise requests.RequestException("OBS_DESTINATION_REJECTED")
        parsed = urlsplit(url)
        host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        if host not in self.allowed_hosts:
            raise requests.RequestException("OBS_DESTINATION_REJECTED")
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = [ipaddress.ip_address(row[4][0]) for row in addresses]
            if not ips or any(not internal_address(ip) for ip in ips):
                raise ValueError()
            # 保存socket引用；即使HTTP/1.0关闭连接也能逐次设置剩余总预算。
            connection = http.client.HTTPConnection(
                str(ips[0]), port, timeout=max(0.001, deadline - time.monotonic())
            )
            raw_socket = socket.create_connection(
                (str(ips[0]), port), timeout=max(0.001, deadline - time.monotonic())
            )
            raw_socket.settimeout(max(0.001, deadline - time.monotonic()))
            connection.sock = (
                ssl.create_default_context().wrap_socket(raw_socket, server_hostname=host)
                if parsed.scheme == "https"
                else raw_socket
            )
            bounded_socket = connection.sock

            # HTTPResponse内部同样使用deadline reader，覆盖getresponse逐行读头阶段。
            class BoundedResponse(http.client.HTTPResponse):
                def __init__(self, sock, *args, **kwargs):
                    super().__init__(sock, *args, **kwargs)
                    self.fp = DeadlineReader(self.fp, bounded_socket, deadline)

            connection.response_class = BoundedResponse
            try:
                connection.putrequest(
                    "POST", "/v1/traces", skip_host=True, skip_accept_encoding=True
                )
                connection.putheader("Content-Type", "application/x-protobuf")
                connection.putheader("Host", parsed.netloc)
                connection.putheader("Content-Length", str(len(data)))
                bounded_socket.settimeout(max(0.001, deadline - time.monotonic()))
                connection.endheaders()
                bounded_socket.settimeout(max(0.001, deadline - time.monotonic()))
                connection.send(data)
                bounded_socket.settimeout(max(0.001, deadline - time.monotonic()))
                response = connection.getresponse()
                body = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError()
                    bounded_socket.settimeout(remaining)
                    part = response.read1(min(4096, 65537 - len(body)))
                    body.extend(part)
                    if len(body) > 65536:
                        raise ValueError()
                    if not part:
                        break
                if 300 <= response.status < 400:
                    raise ValueError()
                safe = requests.Response()
                # SDK无需错误正文；防止SDK诊断再包含任意接收端消息。
                safe.status_code, safe._content = response.status, b""
                safe.headers = {}
                safe.url = self.endpoint
                return safe
            finally:
                connection.close()
        except (OSError, ValueError, http.client.HTTPException):
            raise requests.RequestException("OBS_EXPORT_FAILED") from None

    def close(self):
        super().close()


class SafeExporter(SpanExporter):
    def __init__(self, config, metrics, event):
        self.metrics, self.event = metrics, event
        self.session = FixedEndpointSession(config.endpoint, config.allowed_hosts)
        self.delegate = OTLPSpanExporter(
            endpoint=config.endpoint,
            timeout=2,
            headers={},
            max_request_size=1024**2,
            session=self.session,
            meter_provider=NoOpMeterProvider(),
        )

    def export(self, spans):
        try:
            result = self.delegate.export(spans)
        except Exception:
            result = SpanExportResult.FAILURE
        self.metrics.inc(
            "TRACE_EXPORT",
            "success" if result == SpanExportResult.SUCCESS else "failure",
            amount=len(spans),
        )
        if result != SpanExportResult.SUCCESS:
            self.event("traces", "export_failure")
        return result

    def shutdown(self):
        self.delegate.shutdown()

    def force_flush(self, timeout_millis=2000):
        return self.delegate.force_flush(timeout_millis)
