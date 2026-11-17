"""监控读取验证，实际业务/故障验证在005专用validation中显式运行。"""

import json
import urllib.parse

from .preflight import MonitoringError, docker_admission, load, validate_contract


def request(env, url, auth=False, data=None):
    args = ["/tools/telemetry_fixture.py", "http", "--url", url]
    mounts = []
    if auth:
        args += ["--auth"]
        mounts.append(((env.path / "secrets").as_posix(), "/auth", True))
    if data is not None:
        from .render import write_json

        path = env.path / "request.json"
        write_json(path, data)
        mounts.append((path.as_posix(), "/input.json", True))
        args += ["--data-file", "/input.json"]
    try:
        return json.loads(env.tool(args, mounts=mounts))
    finally:
        if data is not None:
            path.unlink(missing_ok=True)


def query(env, expression):
    result = request(
        env, "http://prometheus:9090/api/v1/query?" + urllib.parse.urlencode({"query": expression})
    )
    if result.get("status") != "success":
        raise MonitoringError("OBS005_PROMETHEUS_QUERY")
    return result["data"]["result"]


def verify(env):
    import time

    env.deadline = time.monotonic() + 300
    env.reconcile()
    env.check_drift()
    env.ensure_images()
    c = validate_contract(load(env.path / "inputs/application-contract.json"))
    docker_admission(env.run, c, env.environment)
    env.wait_ready()
    env.check("六组件ready", "passed")
    targets = request(env, "http://prometheus:9090/api/v1/targets")["data"]["activeTargets"]
    if not targets or any(t["health"] != "up" for t in targets):
        raise MonitoringError("OBS005_TARGET_DOWN")
    env.report["targets"] = [{"job": t["labels"]["job"], "health": t["health"]} for t in targets]
    env.check("Prometheus实际抓取", "passed", str(len(targets)) + "个目标")
    for role in ("api", "worker"):
        result = query(
            env,
            f'sesrag_trace_export_spans_total{{environment="{env.environment}",service="sesrag-{role}"}}',
        )
        if not result:
            raise MonitoringError("OBS005_APPLICATION_METRICS", role)
    env.check("真实应用指标", "passed", "API/Worker服务身份正确；未生成业务假值")
    sources = request(env, "http://grafana:3000/api/datasources", True)
    if {x["uid"] for x in sources} != {"sesrag-prometheus", "sesrag-loki", "sesrag-tempo"}:
        raise MonitoringError("OBS005_DATASOURCE_UID")
    for uid in ("sesrag-prometheus", "sesrag-loki", "sesrag-tempo"):
        request(env, "http://grafana:3000/api/datasources/uid/" + uid + "/health", True)
    env.check("三数据源UID/连接", "passed")
    by_uid = {x["uid"]: x for x in sources}
    if (
        by_uid["sesrag-loki"]["jsonData"]["derivedFields"][0]["url"] != "${__value.raw}"
        or "${__span.traceId}" not in by_uid["sesrag-tempo"]["jsonData"]["tracesToLogsV2"]["query"]
    ):
        raise MonitoringError(
            "OBS005_CORRELATION_VARIABLE", "Grafana provisioning必须转义$，不能被环境变量展开为空"
        )
    env.check("关联变量持久化", "passed", "实际Grafana配置保留traceId/标签模板，双向引用UID正确")
    dashboards = request(env, "http://grafana:3000/api/search?type=dash-db", True)
    expected = {"obs005-overview", "obs005-application", "obs005-pipeline"}
    if not expected.issubset({x["uid"] for x in dashboards}):
        raise MonitoringError("OBS005_DASHBOARD_UID")
    env.check("版本化仪表盘", "passed", "overview/application/pipeline")
    rules = request(env, "http://grafana:3000/api/v1/provisioning/alert-rules", True)
    if len(rules) != 8:
        raise MonitoringError("OBS005_ALERT_RULE_COUNT")
    env.check("八类告警配置", "passed", "实际状态/通知验证另列，不以配置代替闭环")
    fixture = json.loads(
        env.tool(
            ["/tools/telemetry_fixture.py", "signals", "--environment", env.environment], timeout=90
        )
    )
    env.report["synthetic_signals"] = fixture
    env.check("合成Loki/OTLP→Tempo", "passed", "fixture身份；不是实际应用链路")
    env.report["volumes"] = env.volume_stats()
    env.check("资源与卷预算", "passed", "逻辑空间与规划预算已归档；不是硬配额")
    env.check(
        "完整验收",
        "not_run",
        "当前Verify是基础探测；真实业务代际、故障、八类告警、保留删除及备份恢复须运行独立005验证并审阅证据",
    )
