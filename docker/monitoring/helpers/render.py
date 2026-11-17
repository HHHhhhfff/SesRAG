"""有限模板渲染；业务指标语义只引用004真源，拒绝外部PromQL输入。"""

import json
import os
from pathlib import Path

from .preflight import MODULE, digest, load


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def configuration(contract):
    env = contract["environment_id"]
    jobs = []
    for role in ("api", "worker"):
        for i, target in enumerate(contract["services"][role]["targets"]):
            jobs.append(
                {
                    "job_name": f"sesrag-{role}-{i}",
                    "honor_labels": True,
                    "metrics_path": target["path"],
                    "sample_limit": 20000,
                    "label_limit": 32,
                    "label_value_length_limit": 256,
                    "static_configs": [
                        {
                            "targets": [f"{target['host']}:{target['port']}"],
                            "labels": {"service": "sesrag-" + role, "environment": env},
                        }
                    ],
                }
            )
    for service, port in (
        ("prometheus", 9090),
        ("grafana", 3000),
        ("loki", 3100),
        ("tempo", 3200),
        ("alloy", 12345),
    ):
        jobs.append(
            {
                "job_name": service,
                "sample_limit": 20000,
                "label_limit": 32,
                "static_configs": [
                    {
                        "targets": [f"{service}:{port}"],
                        "labels": {"service": service, "environment": env},
                    }
                ],
            }
        )
    if contract["platform"] == "linux-host":
        jobs.append(
            {
                "job_name": "node-exporter",
                "static_configs": [
                    {
                        "targets": ["node-exporter:9100"],
                        "labels": {"service": "linux-host", "environment": env},
                    }
                ],
            }
        )
    return {
        "global": {"scrape_interval": "15s", "scrape_timeout": "5s", "evaluation_interval": "30s"},
        "scrape_configs": jobs,
    }


def expressions(contract):
    env = contract["environment_id"]
    s = f'environment="{env}"'
    api = s + ',service="sesrag-api"'
    worker = s + ',service="sesrag-worker"'

    def api_metric(name, extra=""):
        return f"{name}{{{api}{extra}}}"

    def guard(source):
        extra = ',source="' + source + '"'
        return (
            f"({api_metric('sesrag_snapshot_initialized', extra)} == bool 1) * "
            f"({api_metric('sesrag_snapshot_valid', extra)} == bool 1) * "
            f"((time()-{api_metric('sesrag_snapshot_last_success_timestamp_seconds', extra)})"
            " <= bool 30)"
        )

    # 每个预期目标显式生成absent检查，不依赖已消失的动态label集合。
    down = []
    for job in configuration(contract)["scrape_configs"]:
        labels = job["static_configs"][0]["labels"]
        selector = ",".join(f'{k}="{v}"' for k, v in {"job": job["job_name"], **labels}.items())
        down.append(f"(1-up{{{selector}}}) or absent(up{{{selector}}})")
    missing = []
    for role in ("api", "worker"):
        for i, _ in enumerate(contract["services"][role]["targets"]):
            selector = f'{s},service="sesrag-{role}",job="sesrag-{role}-{i}"'
            for item in contract["metrics"]:
                if role not in item["roles"]:
                    continue
                name = item["name"] + ("_count" if item["type"] == "histogram" else "")
                condition = f"(up{{{selector}}} == 1)"
                source = item.get("validity_source")
                if item["initialization"] != "required_always":
                    if isinstance(source, dict):
                        for dependency, dep_source in source.items():
                            condition_dep = (
                                condition
                                + " and on(job,instance) "
                                + f"(sesrag_snapshot_initialized{{{selector},"
                                + f'source="{dep_source}"}} == 1)'
                            )
                            missing.append(
                                f"({condition_dep} unless on(job,instance) "
                                f'{name}{{{selector},dependency="{dependency}"}})'
                            )
                        continue
                    condition += (
                        " and on(job,instance) "
                        f'(sesrag_snapshot_initialized{{{selector},source="{source}"}} == 1)'
                    )
                # 缺失返回1，存在返回0；独立于业务数值是否为0。
                missing.append(f"({condition} unless on(job,instance) {name}{{{selector}}})")
                if item["allowed_tuples"]:
                    count = len(item["allowed_tuples"])
                    missing.append(
                        f"({condition} and on(job,instance) "
                        f"(count by(job,instance)({name}{{{selector}}}) != {count}))"
                    )
    missing_expr = "(" + " or ".join(missing) + f') or (up{{{s},job=~"sesrag-.*"}}*0)'
    component_missing = []
    for job, names in load(MODULE / "integration/component-metrics.json")[
        "required_always"
    ].items():
        for name in names:
            component_missing.append(
                f'(up{{{s},job="{job}"}}==1) unless on(job,instance) {name}{{{s},job="{job}"}}'
            )
    missing_expr = (
        "("
        + missing_expr
        + ") or ("
        + " or ".join(component_missing)
        + f') or (up{{{s},job=~"alloy|loki|tempo"}}*0)'
    )
    down_api = f"(up{{{api}}} == 0)"
    down_worker = f"(up{{{worker}}} == 0)"
    invalid = (
        f"(max by(environment,service) ((1-({guard('queue')})) "
        f"or (1-({guard('worker_presence')}))) and on(environment,service) "
        f"(up{{{api}}}==1)) or on(environment,service) {down_api}"
    )
    ready = (
        f"((1-({api_metric('sesrag_worker_ready')} == bool 1)) * on(service,environment) "
        f"({guard('worker_presence')}) and on(service,environment) (up{{{api}}}==1)) "
        f"or on(service,environment) {down_api}"
    )
    queue = (
        f"({api_metric('sesrag_queue_ready_tasks')} > bool 0) * "
        f"({api_metric('sesrag_queue_oldest_wait_seconds')} > bool 120) * "
        f"on(service,environment) group_left() ({guard('queue')})) "
        f"and on(job,instance) (up{{{api}}}==1)"
    )
    queue = "(" + queue + f" or on(service,environment) {down_api}"
    total = (
        "sum by(service,environment)(increase(sesrag_http_requests_total"
        f'{{{api},request_kind="short"}}[5m]))'
    )
    errors = (
        "sum by(service,environment)(increase(sesrag_http_requests_total"
        f'{{{api},request_kind="short",status_class="5xx"}}[5m]))'
    )
    http = (
        f"((({total} >= bool 20) * (({errors} / clamp_min({total},1)) > bool 0.05)) "
        f"and on(service,environment) (up{{{api}}}==1)) or on(service,environment) {down_api}"
    )
    attempts = (
        "(sum by(service,environment)(increase(sesrag_task_attempts_total"
        f'{{{worker},result="failed"}}[10m]) and on(job,instance) '
        f"(up{{{worker}}}==1)) >= bool 3) or on(service,environment) "
        f"(max by(service,environment)({down_worker}))"
    )
    pipeline = (
        "max by(service,environment) "
        f"(increase(loki_write_batch_retries_total{{{s}}}[5m]) > bool 0 "
        f"or increase(otelcol_exporter_send_failed_spans_total{{{s}}}[5m]) > bool 0 "
        f"or increase(otelcol_receiver_refused_spans_total{{{s}}}[5m]) > bool 0 "
        f"or increase(loki_discarded_samples_total{{{s}}}[5m]) > bool 0 "
        f"or increase(tempo_live_store_local_failed_flushes_total{{{s}}}[5m]) > bool 0 "
        f'or increase(prometheus_tsdb_wal_writes_failed_total{{{s},job="loki"}}[5m]) > bool 0 '
        f"or increase(loki_write_dropped_entries_total{{{s}}}[5m]) > bool 0) "
        "or on(service,environment) "
        f'(max by(service,environment)(up{{{s},job=~"alloy|loki|tempo"}})*0)'
    )
    return {
        "target-down": (
            "max by(environment,service) (" + " or ".join(down) + ")",
            "2m",
            "critical",
        ),
        "metric-missing": ("max by(environment,service) (" + missing_expr + ")", "2m", "critical"),
        "observation-invalid": (invalid, "2m", "warning"),
        "worker-not-ready": (ready, "2m", "critical"),
        "queue-wait": (queue, "5m", "warning"),
        "api-error": (http, "2m", "warning"),
        "task-failures": (attempts, "2m", "warning"),
        "pipeline-error": (pipeline, "1m", "warning"),
    }


def alerts(contract):
    rules = []
    for key, (expression, duration, severity) in expressions(contract).items():
        rules.append(
            {
                "uid": "obs005-" + key,
                "title": key.upper(),
                "condition": "C",
                "for": duration,
                "noDataState": "NoData",
                "execErrState": "Error",
                "labels": {
                    "environment": contract["environment_id"],
                    "severity": severity,
                    "module": "obs005",
                },
                "annotations": {
                    "summary": "SesRAG本地诊断：" + key,
                    "description": "检查关联来源有效性与同环境日志/追踪，遥测异常不等于业务终态。",
                },
                "data": [
                    {
                        "refId": "A",
                        "datasourceUid": "sesrag-prometheus",
                        "relativeTimeRange": {"from": 600, "to": 0},
                        "model": {
                            "refId": "A",
                            "expr": expression,
                            "instant": True,
                            "range": False,
                            "intervalMs": 1000,
                            "maxDataPoints": 43200,
                        },
                    },
                    {
                        "refId": "C",
                        "datasourceUid": "__expr__",
                        "relativeTimeRange": {"from": 0, "to": 0},
                        "model": {
                            "refId": "C",
                            "type": "threshold",
                            "expression": "A",
                            "conditions": [
                                {
                                    "evaluator": {"params": [0], "type": "gt"},
                                    "operator": {"type": "and"},
                                    "query": {"params": ["A"]},
                                    "reducer": {"params": [], "type": "last"},
                                    "type": "query",
                                }
                            ],
                        },
                    },
                ],
            }
        )
    return {
        "apiVersion": 1,
        "groups": [
            {
                "orgId": 1,
                "name": "obs005-local",
                "folder": "sesrag-observe",
                "interval": "30s",
                "rules": rules,
            }
        ],
    }


def render(contract, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "prometheus.yml", configuration(contract))
    for folder in ("datasources", "dashboards", "alerting"):
        for source in (MODULE / "grafana/provisioning" / folder).glob("*.yaml"):
            write_json(directory / "provisioning" / folder / source.name, load(source))
    # Grafana13按标题创建告警folder，首启需等dashboard先建立固定UID后再加载规则。
    write_json(directory / "rules.pending.json", alerts(contract))
    (directory / "provisioning/plugins").mkdir(parents=True, exist_ok=True)
    dashboards = directory / "dashboards"
    dashboards.mkdir(exist_ok=True)
    for source in (MODULE / "grafana/dashboards").glob("*.json"):
        if source.stem == "linux-host" and contract["platform"] != "linux-host":
            continue
        (dashboards / source.name).write_bytes(source.read_bytes())
    alloy = (MODULE / "alloy/config.alloy.tmpl").read_text(encoding="utf-8")
    for key, value in {
        "APPLICATION_PROJECT": contract["application_project"],
        "ENVIRONMENT": contract["environment_id"],
    }.items():
        alloy = alloy.replace("@@" + key + "@@", value)
    (directory / "config.alloy").write_text(alloy, encoding="utf-8")
    return {
        p.relative_to(directory).as_posix(): digest(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }
