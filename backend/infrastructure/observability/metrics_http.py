"""独立只读监听；抓取仅复制缓存，不进入业务循环或数据库。"""

import socketserver
import threading
import time

from prometheus_client import generate_latest


class MetricsServer:
    def __init__(self, host, port, registry, on_error=None, before_encode=None):
        self.registry = registry
        self.before_encode = before_encode
        self.on_error = on_error or (lambda reason: None)
        self._cache = b""
        self._stopped = threading.Event()
        self._slots = threading.BoundedSemaphore(4)
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                deadline = time.monotonic() + 1
                data = bytearray()
                try:
                    while b"\r\n\r\n" not in data:
                        self.request.settimeout(max(0.001, deadline - time.monotonic()))
                        chunk = self.request.recv(min(1024, 8193 - len(data)))
                        if not chunk:
                            return
                        data.extend(chunk)
                        if len(data) > 8192 or time.monotonic() >= deadline:
                            return
                    parts = bytes(data).split(b"\r\n", 1)[0].split(b" ")
                    if len(parts) != 3:
                        return
                    method, path, _ = parts
                    status, payload = b"200 OK", owner._cache
                    if path != b"/metrics":
                        status, payload = b"404 Not Found", b""
                    elif method not in (b"GET", b"HEAD"):
                        status, payload = b"405 Method Not Allowed", b""
                    self.request.settimeout(1)
                    self.request.sendall(
                        b"HTTP/1.1 " + status + b"\r\nConnection: close\r\n"
                        b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                        b"Content-Length: "
                        + str(len(payload)).encode()
                        + b"\r\n\r\n"
                        + (payload if method != b"HEAD" else b"")
                    )
                except (OSError, ValueError):
                    pass

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True
            block_on_close = False

            def process_request(self, request, client_address):
                if not owner._slots.acquire(blocking=False):
                    try:
                        request.settimeout(0.05)
                        request.sendall(
                            b"HTTP/1.1 503 Busy\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                        )
                    except OSError:
                        pass
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, client_address)
                except BaseException:
                    owner._slots.release()
                    raise

            def process_request_thread(self, request, client_address):
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    owner._slots.release()

            def handle_error(self, request, client_address):
                owner.on_error("handler_error")

        self._server = Server((host, port), Handler, bind_and_activate=False)
        self.port = port

    def _encode(self):
        try:
            if self.before_encode:
                self.before_encode()
            encoded = generate_latest(self.registry)
            if len(encoded) > 2 * 1024**2 or encoded.count(b"\n") > 24000:
                self.on_error("encode_limit")
                return
            self._cache = encoded
        except Exception:
            self.on_error("handler_error")

    def start(self):
        self._server.server_bind()
        self._server.server_activate()
        self.port = self._server.server_address[1]
        self._encode()

        def encode_loop():
            while not self._stopped.wait(1):
                self._encode()

        self._encoder = threading.Thread(target=encode_loop, daemon=True, name="obs-metrics-cache")
        self._listener = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.1),
            daemon=True,
            name="obs-metrics-http",
        )
        self._encoder.start()
        self._listener.start()

    def close(self):
        if self._stopped.is_set():
            return
        self._stopped.set()
        if hasattr(self, "_listener"):
            self._server.shutdown()
            self._listener.join(0.5)
            self._encoder.join(0.3)
        self._server.server_close()
