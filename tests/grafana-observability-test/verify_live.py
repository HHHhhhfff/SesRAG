"""在持久live实例验证真实业务与告警；不创建临时环境，不改告警阈值。"""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from deployment.stack import Stack
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError
from helpers.verify import request


def api(path, payload=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request("http://127.0.0.1:5173" + path, body, headers)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            req, timeout=20
        ) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # HTTP错误正文可含业务数据，不写公开报告。
        raise MonitoringError("LIVE_HTTP_" + str(exc.code)) from None


def wait(name, predicate, timeout=180, interval=5):
    deadline = time.monotonic() + timeout
    last = 0
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        if time.monotonic() - last > 25:
            print("正在验证：" + name, flush=True)
            last = time.monotonic()
        time.sleep(interval)
    raise MonitoringError("LIVE_WAIT_TIMEOUT", name)


def signals(env):
    models = api("/api/v2/models")
    default = models["default_profile"]
    selected = next(p for p in models["models"] if p["profile_id"] == default["profile_id"])
    if selected["provider_kind"] != "openai_compatible" or selected["status"] != "enabled":
        raise MonitoringError("LIVE_REAL_MODEL_REQUIRED")
    thread = api("/api/v2/threads", {"title": "持久部署监控验证 " + env.run_id})
    detail = api("/api/v3/threads/" + thread["thread_id"])
    sentinel = "LIVE_PRIVATE_" + uuid.uuid4().hex
    response = api(
        "/api/v3/threads/" + thread["thread_id"] + "/messages",
        {
            "branch_id": detail["branch"]["branch_id"],
            "expected_version": detail["branch"]["version"],
            "content": "请用一句中文确认服务联通。验证编号：" + sentinel,
            "model_profile_id": default["profile_id"],
            "model_profile_version": default["version"],
            "rag": {"enabled": False},
        },
        key=uuid.uuid4().hex,
    )
    run_id = response["run_id"]

    def terminal():
        value = api("/api/v3/runs/" + run_id)
        return value if value["status"] in ("failed", "cancelled", "succeeded") else None

    result = wait("真实模型Run完成", terminal, timeout=240)
    env.report["real_business"] = {
        "run_id": run_id,
        "task_id": response["task_id"],
        "thread_id": thread["thread_id"],
        "status": result["status"],
        "model": selected["model_name"],
        "error_code": result["last_error_code"],
    }
    if result["status"] != "succeeded":
        raise MonitoringError("LIVE_MODEL_RUN_FAILED", result["last_error_code"] or "unknown")
    detail = api("/api/v3/threads/" + thread["thread_id"])
    answer = next(
        m["content"]
        for m in detail["messages"]
        if m["role"] == "assistant" and m["run_id"] == run_id
    )
    if not answer.strip():
        raise MonitoringError("LIVE_EMPTY_ANSWER")
    env.report["real_business"].update(
        answer_characters=len(answer), answer_sha256=hashlib.sha256(answer.encode()).hexdigest()
    )
    env.check(
        "真实模型请求与回答",
        "passed",
        "前端同源API→持久Run/Task→Worker→真实生成Provider；回答仅存长度/hash",
    )

    def logs():
        params = urllib.parse.urlencode(
            {
                "query": '{environment="live",service="sesrag-worker"} | json | run_id="'
                + run_id
                + '"',
                "start": str(time.time_ns() - 900000000000),
                "end": str(time.time_ns()),
                "limit": 200,
            }
        )
        streams = request(env, "http://loki:3100/loki/api/v1/query_range?" + params)["data"][
            "result"
        ]
        return [json.loads(line) for stream in streams for _, line in stream["values"]]

    lines = wait(
        "真实Worker日志进入Loki",
        lambda: [x for x in logs() if x.get("action") == "attempt_succeeded"],
    )
    trace_id = next(x["trace_id"] for x in lines if x.get("trace_id"))

    def trace():
        data = request(env, "http://tempo:3200/api/traces/" + trace_id)
        batches = data.get("batches", data.get("resourceSpans", []))
        services = {
            a["value"].get("stringValue")
            for b in batches
            for a in b.get("resource", {}).get("attributes", [])
            if a["key"] == "service.name"
        }
        return data if {"sesrag-api", "sesrag-worker"}.issubset(services) else None

    data = wait("API/Worker同trace进入Tempo", trace)
    if sentinel in json.dumps(data) or sentinel in json.dumps(logs()):
        raise MonitoringError("LIVE_TELEMETRY_BODY_LEAK")
    spans = [
        s
        for b in data.get("batches", data.get("resourceSpans", []))
        for scope in b.get("scopeSpans", [])
        for s in scope.get("spans", [])
    ]
    env.report["real_business"].update(
        trace_id=trace_id,
        span_names=sorted({s["name"] for s in spans}),
        log_actions=sorted({x.get("action", "") for x in logs()}),
    )
    env.check("真实日志/追踪关联", "passed", "Loki/Tempo使用同一trace_id；正文哨兵未进入遥测")
    targets = request(env, "http://prometheus:9090/api/v1/targets")["data"]["activeTargets"]
    if not targets or any(x["health"] != "up" for x in targets):
        raise MonitoringError("LIVE_TARGET_DOWN")
    env.report["targets"] = [{"job": x["labels"]["job"], "health": x["health"]} for x in targets]
    env.check("真实指标抓取", "passed", str(len(targets)) + "个目标UP；未替换为合成指标")
    profiles = api("/api/v3/rag/profiles")["items"]
    env.report["rag_availability"] = [
        {k: p.get(k) for k in ("kind", "profile_id", "version", "available", "unavailable_reason")}
        for p in profiles
    ]
    limited = [p for p in profiles if p.get("unavailable_reason") == "INPUT_COUNTER_UNVERIFIED"]
    if limited:
        env.check(
            "真实Embedding/rerank启用边界",
            "blocked",
            "凭据已配置，既有INPUT_COUNTER_UNVERIFIED门槛未绕过；不计RAG完整验收",
        )


def alerts(env, stack):
    stack.check_state()
    started = time.time()

    def events(status):
        values = request(env, "http://webhook-sink:8080/events")["events"]
        return [
            x
            for x in values
            if x["received_at"] >= started
            and any(
                a.get("status") == status
                and "TARGET-DOWN" in a.get("labels", {}).get("alertname", "")
                for a in x["alerts"]
            )
        ]

    worker_stopped = False
    try:
        stack.compose("stop", "--timeout", "30", "worker", timeout=60)
        worker_stopped = True
        env.check(
            "实际Worker停机",
            "passed",
            "优雅停止持久实例Worker；默认TARGET-DOWN规则与等待窗口未改写",
        )
        firing = wait("TARGET-DOWN真实Firing通知", lambda: events("firing"), timeout=300)
        env.report["alert_firing"] = firing
        env.check("告警触发及本地通知", "passed", "真实目标失联→默认规则Firing→本地sink实际接收")
    finally:
        if worker_stopped:
            stack.compose("start", "worker", timeout=90)
            print("实际Worker已恢复启动。", flush=True)
    resolved = wait("TARGET-DOWN真实Resolved通知", lambda: events("resolved"), timeout=240)
    env.report["alert_resolved"] = resolved
    env.check("告警恢复通知", "passed", "Worker恢复→Prometheus重新UP→本地sink实际接收Resolved")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["signals", "alerts"])
    args = parser.parse_args()
    stack = Stack()
    env = Environment("live")
    error = None
    try:
        with stack.observer.mutex(), env.mutex():
            env.reconcile()
            env.check_drift()
            if args.scenario == "signals":
                signals(env)
            else:
                alerts(env, stack)
    except BaseException as exc:
        error = (
            exc if isinstance(exc, MonitoringError) else MonitoringError("LIVE_VALIDATION_FAILED")
        )
        print("验证未完成：" + error.code, flush=True)
    finally:
        env.finish(error)
        target = Path(__file__).parent / "artifacts" / env.run_id
        target.mkdir(parents=True, exist_ok=True)
        (target / (args.scenario + ".json")).write_bytes(
            (env.artifact / "report.json").read_bytes()
        )
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
