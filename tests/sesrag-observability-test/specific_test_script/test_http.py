"""A01/A02/A03：实际API与独立运维端点不混用。"""

import time
from uuid import uuid4

import httpx
from evidence import client, metrics, request, wait


def run():
    with client() as c:
        for version in (1, 2):
            thread = request(c, "POST", f"/api/v{version}/threads", json={"title": "004验证"})
            identity = thread["thread_id"]
            payload = {"content": "OBS_PROMPT_SENTINEL"}
            if version == 2:
                payload.update(branch_id=thread["default_branch_id"], expected_version=0)
            created = request(
                c,
                "POST",
                f"/api/v{version}/threads/{identity}/messages",
                json=payload,
                headers={"Idempotency-Key": str(uuid4())},
            )
            wait(c, f"/api/v{version}/runs/{created['run_id']}")
            response = c.get(f"/api/v{version}/runs/{created['run_id']}/events/stream")
            assert response.status_code == 200 and "run.succeeded" in response.text
            assert "trace_origin" not in response.text
        assert c.get("/metrics").status_code == 404
        assert c.get("/health/live").status_code == 200
        for n in range(15):
            assert c.get(f"/unknown-{n}").status_code == 404
    time.sleep(1.2)
    api, worker = metrics("api"), metrics("worker")
    assert "sesrag_http_requests_total" in api and "sesrag_task_attempts_total" in worker
    assert "unknown-14" not in api and "OBS_PROMPT_SENTINEL" not in api
    with httpx.Client(trust_env=False) as c:
        assert c.post("http://api:9101/metrics").status_code == 405
        assert c.get("http://api:9101/other").status_code == 404
        assert c.head("http://worker:9102/metrics").status_code == 200
    return {"api_versions": [1, 2], "sse_terminal_replay": True, "metrics_internal": True}
