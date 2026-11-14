"""A14容器内负载：2req/s、并发≤4、四类任务与1秒资源采样。"""

import concurrent.futures
import importlib.util
import json
import math
import sys
import threading
import time
import traceback
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling"))
from evidence import client, request, wait  # noqa: E402


def percentile(values, p):
    return sorted(values)[min(len(values) - 1, math.ceil(len(values) * p) - 1)]


def workload(seconds=300, warmup=False):
    if not warmup:
        Path("/data/budget-attempts.jsonl").write_text("")
    latencies, failures, tasks = [], [], []
    scrape_counts = {"api": 0, "worker": 0}
    has_metrics = importlib.util.find_spec("backend.infrastructure.observability") is not None
    lock = threading.Lock()
    started = time.monotonic()

    def reads(index):
        before = time.monotonic()
        try:
            with client() as c:
                response = c.get(
                    ["/api/v1/threads", "/api/v2/threads", "/api/v3/knowledge-bases"][index % 3]
                )
                assert response.status_code == 200
            with lock:
                latencies.append(time.monotonic() - before)
            # A14：候选每5秒抓取两角色；实施前基线不存在观测端点。
            # 抓取耗时不混入普通HTTP耗时，但其资源开销纳入同一窗口。
            if has_metrics and index % 10 == 0:
                with client() as c:
                    for role, port in (("api", 9101), ("worker", 9102)):
                        response = c.get(f"http://{role}:{port}/metrics")
                        assert response.status_code == 200
                        with lock:
                            scrape_counts[role] += 1
        except Exception:
            failures.append("http")

    def business():
        try:
            with client() as c:
                base = request(
                    c,
                    "POST",
                    "/api/v3/knowledge-bases",
                    json={
                        "name": "budget-" + uuid4().hex[:12],
                        "embedding_profile_id": "mock-embedding",
                        "embedding_profile_version": 1,
                    },
                    headers={"Idempotency-Key": str(uuid4())},
                )["knowledge_base_id"]
                for i in range(25 if not warmup else 2):
                    # 两代/多代IndexBuild也单列attempt，至少25个每类任务。
                    doc = request(
                        c,
                        "POST",
                        "/api/v3/documents",
                        files={
                            "file": ("load.md", f"# load {i}\n\nload sample {uuid4()}".encode())
                        },
                        data={"knowledge_base_id": base},
                        headers={"Idempotency-Key": str(uuid4())},
                    )
                    wait(c, "/api/v3/documents/" + doc["document_id"])
                    old = request(
                        c,
                        "POST",
                        "/api/v1/documents",
                        files={"file": ("load.txt", f"legacy {i} {uuid4()}".encode())},
                    )
                    for _ in range(300):
                        rows = request(c, "GET", "/api/v1/documents")["documents"]
                        if (
                            next(r for r in rows if r["document_id"] == old["document_id"])[
                                "status"
                            ]
                            == "indexed"
                        ):
                            break
                        time.sleep(0.05)
                    else:
                        raise AssertionError()
                    diagnostic = request(
                        c,
                        "POST",
                        "/api/v3/retrieval-executions",
                        json={"query": "load", "knowledge_base_id": base},
                        headers={"Idempotency-Key": str(uuid4())},
                    )
                    wait(c, "/api/v3/retrieval-executions/" + diagnostic["execution_id"], "state")
                    for _ in range(5 if not warmup else 1):
                        thread = request(c, "POST", "/api/v1/threads", json={"title": "budget"})
                        run = request(
                            c,
                            "POST",
                            f"/api/v1/threads/{thread['thread_id']}/messages",
                            json={"content": "load"},
                            headers={"Idempotency-Key": str(uuid4())},
                        )
                        wait(c, "/api/v1/runs/" + run["run_id"])
                    tasks.extend(
                        [
                            "index_build",
                            "index_document",
                            "retrieval_diagnostic",
                            *(["run"] * (5 if not warmup else 1)),
                        ]
                    )
        except Exception as exc:
            frames = [
                {"file": Path(f.filename).name, "line": f.lineno}
                for f in traceback.extract_tb(exc.__traceback__)
            ]
            failures.append({"type": type(exc).__name__, "frames": frames})
            print(json.dumps({"load_failure": failures[-1]}), flush=True)

    load = threading.Thread(target=business, daemon=True)
    load.start()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for index in range(seconds * 2):
            target = started + index * 0.5
            time.sleep(max(0, target - time.monotonic()))
            futures.append(pool.submit(reads, index))
        for future in futures:
            future.result()
    load.join(max(0, seconds - (time.monotonic() - started)))
    assert not load.is_alive(), "业务负载未在测量窗口内完成"
    assert not failures, "负载出现错误"
    if not warmup:
        assert len(latencies) >= 600 and len(tasks) >= 200
        if has_metrics:
            assert scrape_counts == {"api": 60, "worker": 60}
        assert all(
            tasks.count(k) >= 25
            for k in ("run", "index_document", "index_build", "retrieval_diagnostic")
        )
    durations = [
        json.loads(line)["seconds"]
        for line in Path("/data/budget-attempts.jsonl").read_text().splitlines()
    ]
    return dict(
        http_p95_seconds=percentile(latencies, 0.95),
        http_samples=len(latencies),
        tasks=len(tasks),
        task_kind_counts={k: tasks.count(k) for k in set(tasks)},
        task_p95_seconds=percentile(durations, 0.95),
        elapsed=time.monotonic() - started,
        throughput=len(tasks) / seconds,
        error_rate=0,
        metric_scrapes=scrape_counts,
    )


def run():
    return workload()


if __name__ == "__main__":
    import sys

    result = workload(60, True) if "--warmup" in sys.argv else workload()
    Path("/data/budget-workload.json").write_text(json.dumps(result))
    print(json.dumps(result), flush=True)
