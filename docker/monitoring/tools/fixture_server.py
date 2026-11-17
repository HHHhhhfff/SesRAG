"""告警表达式用独立fixture005身份；不混入真实应用通过率。"""

import argparse
import http.server
import json
import time


def metrics(catalog, role, scenario, start):
    lines = []
    for item in catalog:
        if role not in item["roles"]:
            continue
        if scenario == "metric-missing" and item["logical_id"] == "TRACE_EXPORT":
            continue
        tuples = item["allowed_tuples"] or [[]]
        for values in tuples:
            labels = dict(zip(item["labels"][2:], values, strict=True))
            labels.update(service="sesrag-" + role, environment="fixture005")
            value = 0
            lid = item["logical_id"]
            if lid in (
                "SNAPSHOT_INITIALIZED",
                "SNAPSHOT_VALID",
                "WORKER_READY",
                "DEPENDENCY_READY",
                "WORKER_ACCEPTING",
            ):
                value = 1
            if lid == "SNAPSHOT_LAST_SUCCESS":
                value = time.time()
            if scenario == "observation-invalid" and lid == "SNAPSHOT_VALID":
                value = 0
            if scenario == "worker-not-ready" and lid == "WORKER_READY":
                value = 0
            if scenario == "queue-wait":
                if lid == "QUEUE_LENGTH":
                    value = 2
                if lid == "QUEUE_OLDEST_WAIT":
                    value = 180
            elapsed = max(0, time.monotonic() - start)
            if (
                scenario == "api-error"
                and lid == "HTTP_REQUESTS"
                and labels.get("request_kind") == "short"
            ):
                value = int(elapsed * 2)
            if (
                scenario == "task-failures"
                and lid == "TASK_ATTEMPTS"
                and labels.get("result") == "failed"
            ):
                value = int(elapsed)
            suffix = "_count" if item["type"] == "histogram" else ""
            # 只需count用于完整性规则；仪表盘/真实histogram另由实际应用验证。
            text = ",".join(k + "=" + json.dumps(str(v)) for k, v in labels.items())
            lines.append(item["name"] + suffix + "{" + text + "} " + str(value))
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog-b64", required=True)
    a = p.parse_args()
    catalog = json.loads(
        __import__("zlib").decompress(__import__("base64").b64decode(a.catalog_b64))
    )
    state = {"scenario": "idle", "start": time.monotonic()}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if not self.path.startswith("/scenario/"):
                self.send_error(404)
                return
            state.update(scenario=self.path.split("/")[-1], start=time.monotonic())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def do_GET(self):
            if self.path == "/health":
                data = '{"status":"ok"}'
            elif self.path in ["/api.metrics", "/worker.metrics"]:
                if state["scenario"] == "target-down":
                    self.send_error(503)
                    return
                data = metrics(
                    catalog,
                    "api" if self.path == "/api.metrics" else "worker",
                    state["scenario"],
                    state["start"],
                )
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(data.encode())

    http.server.ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()


if __name__ == "__main__":
    main()
