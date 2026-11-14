"""受控OTLP HTTP/protobuf接收器；只保存安全span投影，不落原始payload。"""

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

SPANS = deque(maxlen=12000)
LOCK = threading.Lock()
MODE = "ok"
COUNTS = {"batches": 0, "spans": 0, "unsafe": 0}
SENTINELS = ("OBS_SECRET_SENTINEL", "OBS_PROMPT_SENTINEL", "OBS_URL_SENTINEL")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def do_GET(self):
        with LOCK:
            self.reply(200, {"spans": list(SPANS), "counts": COUNTS, "mode": MODE})

    def do_POST(self):
        global MODE
        self.connection.settimeout(3)
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 <= length <= 1024**2:
            self.reply(413, {})
            return
        raw = self.rfile.read(length)
        if self.path == "/mode":
            mode = json.loads(raw)["mode"]
            if mode not in {"ok", "failure", "slow"}:
                self.reply(400, {})
                return
            MODE = mode
            self.reply(200, {})
            return
        if (
            self.path != "/v1/traces"
            or self.headers.get("Content-Type") != "application/x-protobuf"
        ):
            self.reply(400, {})
            return
        if MODE == "slow":
            time.sleep(3)
        if MODE != "ok":
            self.reply(503, {})
            return
        request = ExportTraceServiceRequest.FromString(raw)
        projected = []
        unsafe = any(s.encode() in raw for s in SENTINELS)
        for resource in request.resource_spans:
            service = next(
                (
                    p.value.string_value
                    for p in resource.resource.attributes
                    if p.key == "service.name"
                ),
                None,
            )
            for scope in resource.scope_spans:
                for span in scope.spans:
                    attrs = {
                        p.key: getattr(p.value, p.value.WhichOneof("value"))
                        for p in span.attributes
                    }
                    projected.append(
                        dict(
                            name=span.name,
                            trace_id=span.trace_id.hex(),
                            span_id=span.span_id.hex(),
                            parent_span_id=span.parent_span_id.hex(),
                            service=service,
                            attributes=attrs,
                            events=len(span.events),
                            duration_ms=(span.end_time_unix_nano - span.start_time_unix_nano) / 1e6,
                        )
                    )
        with LOCK:
            COUNTS["batches"] += 1
            COUNTS["spans"] += len(projected)
            COUNTS["unsafe"] += int(unsafe)
            if not unsafe:
                SPANS.extend(projected)
        self.reply(200, {})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 4318), Handler).serve_forever()
