"""005内网探测/合成三信号/本地告警接收；合成身份与真实业务明确分离。"""

import argparse
import base64
import collections
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def http(url, data=None, auth=False, timeout=8):
    headers = {}
    if auth:
        password = Path("/auth/grafana-password").read_text().strip()
        headers["Authorization"] = (
            "Basic " + base64.b64encode(("admin:" + password).encode()).decode()
        )
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)

    # 内网请求禁代理/重定向，不把宿主代理或凭据带入信号链。
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(
        request, timeout=timeout
    ) as r:
        raw = r.read(8 * 1024 * 1024)
        try:
            return json.loads(raw)
        except ValueError:
            return raw.decode()


def ready():
    urls = {
        "prometheus": "http://prometheus:9090/-/ready",
        "loki": "http://loki:3100/ready",
        "tempo": "http://tempo:3200/ready",
        "alloy": "http://alloy:12345/-/ready",
        "grafana": "http://grafana:3000/api/health",
        "sink": "http://webhook-sink:8080/health",
    }
    deadline = time.monotonic() + 165
    while urls:
        for key, url in list(urls.items()):
            try:
                http(url, timeout=3)
                del urls[key]
            except Exception:
                pass
        if not urls:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("not_ready:" + ",".join(urls))
        time.sleep(2)
    print(json.dumps({"status": "passed", "ready": 6}))


class NotificationRing:
    """数量与时间同时有界；可注入时钟验证24h边界，不需要等待一天。"""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.items = collections.deque(maxlen=100)
        self.lock = threading.Lock()

    def trim(self):
        while self.items and self.clock() - self.items[0]["received_at"] > 86400:
            self.items.popleft()

    def append(self, item):
        with self.lock:
            self.trim()
            self.items.append(item)

    def snapshot(self):
        with self.lock:
            self.trim()
            return list(self.items)


def sink():
    ring = NotificationRing()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, data, code=200):
            b = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/health":
                return self.send({"status": "ok"})
            if self.path != "/events":
                return self.send({"error": "not_found"}, 404)
            data = ring.snapshot()
            return self.send({"events": data, "limit": 100, "max_age_seconds": 86400})

        def do_POST(self):
            if self.path != "/alerts":
                return self.send({"error": "not_found"}, 404)
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send({"error": "bad_length"}, 400)
            if not 0 <= n <= 262144:
                return self.send({"error": "too_large"}, 413)
            try:
                data = json.loads(self.rfile.read(n))
            except ValueError:
                return self.send({"error": "bad_json"}, 400)
            allowed = {
                "alertname",
                "environment",
                "service",
                "severity",
                "rulename",
                "grafana_folder",
                "module",
            }
            alerts = [
                {
                    "status": a.get("status"),
                    "labels": {
                        k: str(v)[:128] for k, v in a.get("labels", {}).items() if k in allowed
                    },
                    "startsAt": a.get("startsAt"),
                    "endsAt": a.get("endsAt"),
                    "fingerprint": str(a.get("fingerprint", ""))[:128],
                }
                for a in data.get("alerts", [])[:100]
            ]
            item = {
                "received_at": time.time(),
                "status": str(data.get("status", ""))[:16],
                "groupKeyHash": __import__("hashlib")
                .sha256(str(data.get("groupKey", "")).encode())
                .hexdigest(),
                "alerts": alerts,
            }
            ring.append(item)
            self.send({"accepted": len(alerts)})

    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


def signals(environment):
    now = time.time_ns()
    trace = secrets.token_hex(16)
    span = secrets.token_hex(8)
    http(
        "http://loki:3100/loki/api/v1/push",
        {
            "streams": [
                {
                    "stream": {
                        "environment": environment,
                        "service": "obs005-fixture",
                        "level": "INFO",
                    },
                    "values": [
                        [
                            str(now),
                            json.dumps(
                                {
                                    "action": "obs005_fixture",
                                    "trace_id": trace,
                                    "message": "受控合成日志",
                                }
                            ),
                        ]
                    ],
                }
            ]
        },
    )
    # OTLP HTTP JSON仅用于协议夹具；真实应用验收必须另核SDK的protobuf出口。
    http(
        "http://alloy:4318/v1/traces",
        {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "obs005-fixture"}},
                            {
                                "key": "deployment.environment.name",
                                "value": {"stringValue": environment},
                            },
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "obs005-fixture"},
                            "spans": [
                                {
                                    "traceId": trace,
                                    "spanId": span,
                                    "name": "obs005.fixture",
                                    "kind": 1,
                                    "startTimeUnixNano": str(now),
                                    "endTimeUnixNano": str(now + 1000000),
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            t = http("http://tempo:3200/api/traces/" + trace)
            q = urllib.parse.urlencode(
                {
                    "query": '{environment="' + environment + '",service="obs005-fixture"}',
                    "start": str(now - 1000000000),
                    "end": str(time.time_ns()),
                    "limit": 100,
                }
            )
            logs = http("http://loki:3100/loki/api/v1/query_range?" + q)
            if t and logs.get("data", {}).get("result"):
                break
        except Exception:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("fixture_not_queryable")
        time.sleep(2)
    print(
        json.dumps(
            {
                "status": "passed",
                "fixture": True,
                "trace_id": trace,
                "loki_streams": len(logs["data"]["result"]),
            }
        )
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["sink", "ready", "signals", "http"])
    p.add_argument("--environment", default="local")
    p.add_argument("--url")
    p.add_argument("--auth", action="store_true")
    p.add_argument("--data-file")
    a = p.parse_args()
    if a.action == "sink":
        sink()
    elif a.action == "ready":
        ready()
    elif a.action == "signals":
        signals(a.environment)
    else:
        print(
            json.dumps(
                http(
                    a.url,
                    json.loads(Path(a.data_file).read_text()) if a.data_file else None,
                    a.auth,
                ),
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
