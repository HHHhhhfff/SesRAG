"""005隔离组件故障：每次真实Run仍成功；区分导出失败与业务事实。"""

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError
from helpers.verify import query
from live_validation import wait


def run_business(e):
    base = "http://127.0.0.1:18005"

    def api(path, data=None):
        r = urllib.request.Request(
            base + path,
            None if data is None else json.dumps(data).encode(),
            {"Content-Type": "application/json"},
        )
        return json.load(
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r, timeout=15)
        )

    t = api("/api/v1/threads", {"title": "005观测故障隔离"})
    r = api("/api/v1/threads/" + t["thread_id"] + "/messages", {"content": "005受控无外发验证"})
    result = wait(
        e,
        "观测失败时业务继续",
        lambda: (lambda x: x if x["status"] in ("succeeded", "failed", "cancelled") else None)(
            api("/api/v1/runs/" + r["run_id"])
        ),
        120,
    )
    if result["status"] != "succeeded":
        raise MonitoringError("OBS005_TELEMETRY_CHANGED_BUSINESS")
    return {"run_id": r["run_id"], "task_id": r["task_id"], "status": result["status"]}


def main():
    e = Environment("verify005")
    error = None
    try:
        with e.mutex():
            e.reconcile()
            e.check_drift()
            for service, metric in [
                ("loki", "loki_write_batch_retries_total"),
                ("tempo", "otelcol_exporter_send_failed_spans_total"),
                ("alloy", 'sesrag_trace_export_spans_total{result="failure"}'),
            ]:
                expression = "sum(" + metric + ")"
                baseline = sum(float(x["value"][1]) for x in query(e, expression))
                container = e.project + "-" + service + "-1"
                e.run(["docker", "stop", "--time", "5", container])
                started = time.monotonic()
                try:
                    business = run_business(e)

                    def failed(expression=expression, baseline=baseline):
                        values = query(e, expression)
                        return (
                            values if sum(float(x["value"][1]) for x in values) > baseline else None
                        )

                    samples = wait(e, service + "受限导出/重试错误可见", failed, 150)
                    e.report.setdefault("component_faults", []).append(
                        {
                            "component": service,
                            "business": business,
                            "error_metric": metric,
                            "before": baseline,
                            "after": samples,
                            "seconds": round(time.monotonic() - started, 2),
                        }
                    )
                finally:
                    e.run(["docker", "start", container])
                e.wait_ready()
                run_business(e)
                e.check(
                    service + "中断/恢复",
                    "passed",
                    "真实Run继续成功；有实际错误counter，恢复后新业务成功；不承诺零丢失",
                )
            e.report["resource_stats"] = e.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    *[x["id"] for x in e.inventory()["container"]],
                ]
            ).splitlines()
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
