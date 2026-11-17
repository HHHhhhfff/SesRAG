"""005专用实际接入/合成故障验证；仅允许专用隔离环境，输出中文脱敏证据。"""

import argparse
import base64
import json
import secrets
import sys
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import ROOT, MonitoringError, load
from helpers.render import alerts, configuration, write_json
from helpers.verify import query, request


def wait(env, name, predicate, timeout=180, interval=5):
    deadline = time.monotonic() + timeout
    last = 0
    while True:
        try:
            result = predicate()
        except MonitoringError:
            result = None
        if result:
            return result
        if time.monotonic() > deadline:
            raise MonitoringError("OBS005_VALIDATION_TIMEOUT", name)
        if time.monotonic() - last >= 25:
            print("验证进行中：" + name, flush=True)
            last = time.monotonic()
        time.sleep(interval)


def business(env, base):
    if base != "http://127.0.0.1:18005":
        raise MonitoringError("OBS005_ISOLATED_APP_REQUIRED")

    def api(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        r = urllib.request.Request(base + path, body, {"Content-Type": "application/json"})
        return json.load(
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r, timeout=15)
        )

    t = api("/api/v1/threads", {"title": "005隔离追踪验证"})
    marker = "OBS005_PRIVATE_BODY_" + secrets.token_hex(8)
    r = api("/api/v1/threads/" + t["thread_id"] + "/messages", {"content": marker})
    result = wait(
        env,
        "真实Run等待完成",
        lambda: (lambda x: x if x["status"] in ("succeeded", "failed", "cancelled") else None)(
            api("/api/v1/runs/" + r["run_id"])
        ),
    )
    if result["status"] != "succeeded":
        raise MonitoringError("OBS005_BUSINESS_FAILED")

    def logs():
        q = urllib.parse.urlencode(
            {
                "query": '{environment="'
                + env.environment
                + '",service="sesrag-worker"} | json | run_id="'
                + r["run_id"]
                + '"',
                "start": str(time.time_ns() - 600000000000),
                "end": str(time.time_ns()),
                "limit": 200,
            }
        )
        streams = request(env, "http://loki:3100/loki/api/v1/query_range?" + q)["data"]["result"]
        return [json.loads(line) for stream in streams for _, line in stream["values"]]

    lines = wait(
        env,
        "Worker安全stdout到达Loki",
        lambda: [x for x in logs() if x.get("action") == "attempt_succeeded"],
    )
    lines = logs()
    trace = next(x["trace_id"] for x in lines if x.get("trace_id"))

    def get_trace():
        try:
            data = request(env, "http://tempo:3200/api/traces/" + trace)
            spans = [
                s
                for batch in data.get("batches", data.get("resourceSpans", []))
                for scope in batch.get("scopeSpans", batch.get("instrumentationLibrarySpans", []))
                for s in scope["spans"]
            ]
            services = {
                next(
                    (
                        a["value"].get("stringValue")
                        for a in b["resource"]["attributes"]
                        if a["key"] == "service.name"
                    ),
                    None,
                )
                for b in data.get("batches", data.get("resourceSpans", []))
            }
            if {"sesrag-api", "sesrag-worker"}.issubset(services) and len(spans) >= 4:
                return data, spans
        except Exception:
            return None

    data, spans = wait(env, "API→producer→Worker真实protobuf追踪", get_trace)
    serialized = json.dumps(data)
    if marker in serialized or marker in json.dumps(lines):
        raise MonitoringError("OBS005_SECRET_SENTINEL_LEAK")
    safe = [
        {
            k: x.get(k)
            for k in (
                "service",
                "action",
                "trace_id",
                "span_id",
                "generation",
                "attempt",
                "run_id",
                "task_id",
            )
        }
        for x in lines
    ]
    attempts = {x.get("generation") for x in lines if x.get("generation") is not None}
    env.report["real_business"] = {
        "run_id": r["run_id"],
        "task_id": r["task_id"],
        "status": result["status"],
        "trace_id": trace,
        "spans": spans,
        "safe_log_identities": safe,
        "generations": sorted(attempts),
    }
    if not {1, 2}.issubset(attempts):
        raise MonitoringError(
            "OBS005_RETRY_FIXTURE_REQUIRED",
            "先重建005专用fault worker再运行，首次故障仅影响一次受控调用",
        )
    consumers = [
        s
        for s in spans
        if any(a["key"] == "generation" for a in s.get("attributes", []))
        and s.get("kind") in (5, "SPAN_KIND_CONSUMER")
    ]
    if len(consumers) < 2 or len({s.get("parentSpanId") for s in consumers}) != 1:
        raise MonitoringError("OBS005_TRACE_TOPOLOGY", "attempt必须为同一producer下兄弟执行span")
    env.check(
        "真实API/Task/Worker及自动重试代际",
        "passed",
        "1→2代，同trace兄弟consumer；正文哨兵未进入日志/追踪",
    )
    return trace


def log_boundaries(env, trace):
    marker = "OBS005_NON_JSON_" + secrets.token_hex(6)
    env.run(
        [
            "docker",
            "exec",
            "sesrag-obs005-app-api-1",
            "python",
            "-c",
            'open("/proc/1/fd/1","w").write(' + repr(marker + " sk-ShouldNeverAppear12345\n") + ")",
        ]
    )
    unauthorized = "OBS005_UNAUTHORIZED_" + secrets.token_hex(6)
    for project, opt_in in [("obs005-negative", "true"), ("sesrag-obs005-app", "false")]:
        env.run(
            [
                "docker",
                "run",
                "--rm",
                "--pull=never",
                "--memory=384m",
                "--cpus=.5",
                "--cap-drop=ALL",
                "--label",
                "com.docker.compose.project=" + project,
                "--label",
                "com.docker.compose.service=api",
                "--label",
                "io.sesrag.observability.environment=" + env.environment,
                "--label",
                "io.sesrag.observability.collect=" + opt_in,
                env.state["tool_image"],
                "python",
                "-c",
                "import time;print(" + repr(unauthorized) + ",flush=True);time.sleep(8)",
            ]
        )

    def query_logs(selector):
        return request(
            env,
            "http://loki:3100/loki/api/v1/query_range?"
            + urllib.parse.urlencode(
                {
                    "query": selector,
                    "start": str(time.time_ns() - 300000000000),
                    "end": str(time.time_ns()),
                    "limit": 1000,
                }
            ),
        )["data"]["result"]

    wait(
        env,
        "安全非JSON诊断",
        lambda: query_logs(
            '{environment="' + env.environment + '",service="sesrag-api"} |= "non_json_redacted"'
        ),
    )
    if query_logs('{environment="' + env.environment + '"} |= "' + marker + '"') or query_logs(
        '{environment="' + env.environment + '"} |= "' + unauthorized + '"'
    ):
        raise MonitoringError("OBS005_LOG_FILTER_LEAK")
    if not query_logs(
        '{environment="'
        + env.environment
        + '",service="sesrag-api"} | json | trace_id="'
        + trace
        + '"'
    ):
        raise MonitoringError("OBS005_API_LOG_TRACE_CORRELATION")
    env.check(
        "日志授权/非JSON/trace字段关联",
        "passed",
        "其它project/未opt-in不入库；非JSON原文屏蔽并有固定诊断；API与Worker同trace可查",
    )


def alert_fixture(env, scenarios=None, extended=True):
    sink = env.project + "-webhook-sink-1"
    catalog = base64.b64encode(
        zlib.compress(json.dumps(load(ROOT / "contracts/observability/metrics_v1.json")).encode())
    ).decode()
    env.run(
        [
            "docker",
            "exec",
            "-d",
            sink,
            "python",
            "/tools/fixture_server.py",
            "--catalog-b64",
            catalog,
        ]
    )
    wait(env, "合成指标夹具", lambda: request(env, "http://webhook-sink:8081/health"))
    generated = env.path / "generated"
    paths = [
        generated / "prometheus.yml",
        generated / "provisioning/alerting/rules.yaml",
        generated / "provisioning/alerting/policies.yaml",
    ]
    original = {p: p.read_bytes() for p in paths}
    # 先持久化原文件，硬杀后可显式恢复；不凭内存finally假设配置已还原。
    recovery = env.path / "validation-recovery"
    recovery.mkdir(exist_ok=True)
    for index, p in enumerate(paths):
        (recovery / str(index)).write_bytes(original[p])
    contract = load(env.path / "inputs/application-contract.json")
    contract["environment_id"] = "fixture005"
    conf = configuration(contract)
    for job in conf["scrape_configs"]:
        if job["job_name"].startswith("sesrag-"):
            role = "api" if "-api-" in job["job_name"] else "worker"
            job["metrics_path"] = "/" + role + ".metrics"
            job["static_configs"][0]["targets"] = ["webhook-sink:8081"]
    # 组件故障仍使用真实自指标，但环境为fixture005，报告明确记录受控配置差异。
    rule_config = alerts(contract)
    for rule in rule_config["groups"][0]["rules"]:
        rule["for"] = "10s"
    rule_config["groups"][0]["interval"] = "10s"
    policy = load(paths[2])
    policy["policies"][0].update(group_wait="1s", group_interval="5s", repeat_interval="30s")
    write_json(
        env.artifact / "alert-fixture-config.json",
        {
            "fixture": True,
            "environment": "fixture005",
            "pending": "10s",
            "repeat": "30s",
            "production_pending_preserved": [
                r["for"]
                for r in alerts(load(env.path / "inputs/application-contract.json"))["groups"][0][
                    "rules"
                ]
            ],
        },
    )
    history = []
    event_floor = time.time()

    def reload():
        request(env, "http://prometheus:9090/-/reload", data={})
        request(env, "http://grafana:3000/api/admin/provisioning/alerting/reload", True, {})

    def state():
        groups = request(env, "http://grafana:3000/api/prometheus/grafana/api/v1/rules", True)[
            "data"
        ]["groups"]
        return [r for group in groups for r in group["rules"]]

    def events(name, status):
        data = request(env, "http://webhook-sink:8080/events")["events"]
        return [
            e
            for e in data
            if e["received_at"] >= event_floor
            and any(
                a["labels"].get("alertname") == name
                and a["status"] == status
                and a["labels"].get("environment") == "fixture005"
                for a in e["alerts"]
            )
        ]

    try:
        write_json(paths[0], conf)
        write_json(paths[1], rule_config)
        write_json(paths[2], policy)
        reload()
        time.sleep(20)
        wait(
            env,
            "idle正常数值",
            lambda: all(
                r.get("health") == "ok" and r["state"] == "inactive" and not r.get("lastError")
                for r in state()
            ),
            120,
        )
        for rule in state():
            values = query(env, rule["query"])
            if not values or any(float(v["value"][1]) != 0 for v in values):
                raise MonitoringError("OBS005_IDLE_NOT_ZERO", rule["name"])
        env.check("idle八类表达式", "passed", "实际结果非空且全0，规则inactive")
        if scenarios is None:
            scenarios = (
                "target-down",
                "metric-missing",
                "observation-invalid",
                "worker-not-ready",
                "queue-wait",
                "api-error",
                "task-failures",
            )
        for scenario in scenarios:
            event_floor = time.time()
            name = scenario.upper()
            request(env, "http://webhook-sink:8081/scenario/" + scenario, data={})
            observed = set()

            def firing(name=name, observed=observed):
                r = next(r for r in state() if r["name"] == name)
                observed.add(r["state"])
                return events(name, "firing")

            received = wait(env, name + " Firing通知", firing, 240)
            history.append(
                {
                    "rule": name,
                    "states": sorted(observed),
                    "firing_notifications": len(received),
                    "fixture": True,
                }
            )
            if scenario == "target-down":
                wait(
                    env,
                    "重复通知且同组去重",
                    lambda name=name, received=received: (
                        len(events(name, "firing")) >= len(received) + 2
                    ),
                    100,
                )
                env.check(
                    "通知分组/重复",
                    "passed",
                    "API/Worker分组；相同fingerprint按缩短repeat窗口重复，非每次评估发送",
                )
            request(env, "http://webhook-sink:8081/scenario/idle", data={})
            # 窗口counter测试通过重载固定夹具job名清除旧窗口会掩盖恢复，必须等待真实窗口。
            timeout = (
                720 if scenario == "task-failures" else 420 if scenario == "api-error" else 180
            )
            wait(env, name + " Resolved通知", lambda name=name: events(name, "resolved"), timeout)
            history[-1]["notifications"] = {
                "firing": events(name, "firing"),
                "resolved": events(name, "resolved"),
            }
            env.report["alert_scenarios"] = history
            env.check(
                "规则 " + name,
                "passed",
                "受控fixture005 Firing和Resolved实际到达sink"
                "（验收加速pending，默认阈值/统计窗口不变）",
            )
        env.report["alert_scenarios"] = history
        if not extended:
            return
        event_floor = time.time()
        # PIPELINE使用真实Loki断开和Alloy实际重试counter，不伪造组件自指标。
        loki = env.project + "-loki-1"
        env.run(["docker", "stop", "--time", "5", loki])
        try:
            for _ in range(8):
                env.run(
                    [
                        "docker",
                        "exec",
                        "sesrag-obs005-app-api-1",
                        "python",
                        "-c",
                        'open("/proc/1/fd/1","w").write("OBS005_CONTROLLED_PIPELINE_FAULT\\n")',
                    ]
                )
                time.sleep(1)
            wait(
                env, "PIPELINE-ERROR实际重试Firing", lambda: events("PIPELINE-ERROR", "firing"), 240
            )
        finally:
            env.run(["docker", "start", loki])
        wait(
            env, "PIPELINE-ERROR实际恢复Resolved", lambda: events("PIPELINE-ERROR", "resolved"), 480
        )
        env.check(
            "规则 PIPELINE-ERROR", "passed", "真实Loki中断→Alloy重试→恢复；Firing和Resolved到达sink"
        )
        # NoData和Error通过独立验证规则触发，不能修改生产规则的异常策略。
        diagnostic = dict(rule_config["groups"][0]["rules"][0])
        diagnostic = json.loads(json.dumps(diagnostic))
        diagnostic.update(uid="obs005-fixture-nodata", title="FIXTURE-NODATA", **{"for": "0s"})
        diagnostic["data"][0]["model"]["expr"] = (
            'obs005_intentionally_absent{environment="fixture005"}'
        )
        rule_config["groups"][0]["rules"].append(diagnostic)
        write_json(paths[1], rule_config)
        reload()
        event_floor = time.time()
        wait(
            env,
            "DatasourceNoData通知",
            lambda: [
                e
                for e in events("DatasourceNoData", "firing")
                if any(a["labels"].get("rulename") == "FIXTURE-NODATA" for a in e["alerts"])
            ],
            120,
        )
        diagnostic["data"][0]["model"]["expr"] = "invalid_promql("
        diagnostic["uid"] = "obs005-fixture-error"
        diagnostic["title"] = "FIXTURE-ERROR"
        rule_config["groups"][0]["rules"][-1] = diagnostic
        write_json(paths[1], rule_config)
        reload()
        event_floor = time.time()
        wait(
            env,
            "DatasourceError通知",
            lambda: [
                e
                for e in events("DatasourceError", "firing")
                if any(a["labels"].get("rulename") == "FIXTURE-ERROR" for a in e["alerts"])
            ],
            120,
        )
        env.check("NoData/Error通知路由", "passed", "独立负例实际到达本地sink")
        env.report["notifications"] = request(env, "http://webhook-sink:8080/events")
    finally:
        env.deadline = None
        for p, data in original.items():
            p.write_bytes(data)
        reload()
        # 文件移除规则还需显式deleteRules；不假设删YAML即删数据库对象。
        cleanup = generated / "provisioning/alerting/fixture-delete.yaml"
        write_json(
            cleanup,
            {
                "apiVersion": 1,
                "deleteRules": [
                    {"orgId": 1, "uid": "obs005-fixture-nodata"},
                    {"orgId": 1, "uid": "obs005-fixture-error"},
                ],
            },
        )
        request(env, "http://grafana:3000/api/admin/provisioning/alerting/reload", True, {})
        cleanup.unlink()
        for p in recovery.iterdir():
            p.unlink()
        recovery.rmdir()
        env.check(
            "恢复生产规则/通知配置", "passed", "默认pending、30s/1m/4h已恢复，fixture目标已移除"
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scope", choices=["business", "alerts", "alerts-extra"])
    p.add_argument("--environment", default="verify005")
    a = p.parse_args()
    if a.environment != "verify005":
        p.error("只允许005专用隔离环境verify005")
    env = Environment(a.environment)
    env.deadline = time.monotonic() + 3600
    error = None
    try:
        with env.mutex():
            env.reconcile()
            if a.scope == "business":
                trace = business(env, "http://127.0.0.1:18005")
                log_boundaries(env, trace)
            elif a.scope == "alerts":
                alert_fixture(env)
            elif a.scope == "alerts-extra":
                alert_fixture(env, scenarios=("target-down",))
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        env.deadline = None
        env.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
