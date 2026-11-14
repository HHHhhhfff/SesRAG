"""版本化字典驱动的独立registry；所有标签元组均由真源约束。"""

import json
import time
from pathlib import Path

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

CATALOG_PATH = Path(__file__).resolve().parents[3] / "contracts/observability/metrics_v1.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


class ApplicationRegistry(CollectorRegistry):
    def collect(self):
        for family in super().collect():
            family.samples = [s for s in family.samples if not s.name.endswith("_created")]
            yield family


class ObservabilityMetrics:
    def __init__(self, service: str, environment: str):
        self.registry = ApplicationRegistry()
        self.identity = {"service": service, "environment": environment}
        self.role = service.removeprefix("sesrag-")
        self._metrics = {}
        self._allowed = {}
        self._success_at: dict[str, float] = {}
        self.catalog_names = []
        for item in CATALOG:
            if self.role not in item["roles"]:
                continue
            kind = {"counter": Counter, "gauge": Gauge, "histogram": Histogram}[item["type"]]
            kwargs = {"buckets": item["buckets"]} if item["type"] == "histogram" else {}
            metric = kind(
                item["name"], item["logical_id"], item["labels"], registry=self.registry, **kwargs
            )
            self._metrics[item["logical_id"]] = metric
            self._allowed[item["logical_id"]] = {tuple(t) for t in item["allowed_tuples"]}
            self.catalog_names.append(item["name"])
            if item["initialization"] == "required_always":
                for values in item["allowed_tuples"]:
                    metric.labels(service, environment, *values)
        # 序列预算包含bucket/count/sum，禁止靠流量动态增长。
        count = sum(len(f.samples) for f in self.registry.collect())
        if count > 12000:
            raise ValueError("observability series budget exceeded")

    def child(self, key, *values):
        if key not in self._metrics or tuple(values) not in self._allowed[key]:
            return None
        return self._metrics[key].labels(*self.identity.values(), *values)

    def inc(self, key, *values, amount=1):
        metric = self.child(key, *values)
        if metric is not None:
            metric.inc(amount)

    def set(self, key, *values, value):
        metric = self.child(key, *values)
        if metric is not None:
            metric.set(value)

    def observe(self, key, *values, seconds):
        metric = self.child(key, *values)
        if metric is not None:
            metric.observe(max(0, seconds))

    def http_request(self, method, route, status, kind):
        self.inc("HTTP_REQUESTS", method, route, status, kind)

    def queue_snapshot(self, values):
        for kind, (count, oldest) in values.items():
            self.set("QUEUE_LENGTH", kind, value=count)
            self.set("QUEUE_OLDEST_WAIT", kind, value=oldest)
        self.snapshot_success("queue")

    def snapshot_success(self, source):
        self.set("SNAPSHOT_INITIALIZED", source, value=1)
        self.set("SNAPSHOT_VALID", source, value=1)
        self.set("SNAPSHOT_LAST_SUCCESS", source, value=time.time())
        self._success_at[source] = time.monotonic()

    def snapshot_failure(self, source):
        self.set("SNAPSHOT_VALID", source, value=0)

    def expire_snapshots(self):
        for source, at in tuple(self._success_at.items()):
            if time.monotonic() - at > 30:
                self.snapshot_failure(source)
