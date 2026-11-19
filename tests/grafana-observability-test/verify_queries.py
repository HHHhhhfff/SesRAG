"""实际Grafana面板查询与重启后历史trace验证，不制造业务故障。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from deployment.stack import Stack
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError
from helpers.verify import query, request


def main():
    stack = Stack()
    env = Environment("live")
    error = None
    try:
        with stack.observer.mutex(), env.mutex():
            stack.check_state()
            env.reconcile()
            env.check_drift()
            results = []
            for uid in ("obs005-overview", "obs005-application", "obs005-pipeline"):
                dashboard = request(env, "http://grafana:3000/api/dashboards/uid/" + uid, True)[
                    "dashboard"
                ]
                if not dashboard.get("panels"):
                    raise MonitoringError("LIVE_DASHBOARD_EMPTY")
                for panel in dashboard["panels"]:
                    if panel.get("datasource", {}).get("uid") != "sesrag-prometheus":
                        continue
                    for target in panel.get("targets", []):
                        expression = target["expr"].replace("$environment", "live")
                        values = query(env, expression)
                        # 低流量histogram可能NaN，记录真实结果，不能伪造0或虚构样本。
                        results.append(
                            {
                                "dashboard": uid,
                                "panel_id": panel["id"],
                                "title": panel["title"],
                                "series": len(values),
                                "values": [x.get("value", [None, None])[1] for x in values],
                            }
                        )
            if len(results) != 15:
                raise MonitoringError("LIVE_PANEL_QUERY_COUNT")
            env.report["panel_queries"] = results
            env.check(
                "Grafana面板实际查询",
                "passed",
                "15条真实PromQL均成功；记录原始series数和NaN，无假零值",
            )
            history = sorted(Path(__file__).parent.glob("artifacts/*/signals.json"))
            source = next(
                json.loads(p.read_text(encoding="utf-8"))
                for p in reversed(history)
                if json.loads(p.read_text(encoding="utf-8")).get("real_business", {}).get("status")
                == "succeeded"
            )
            trace = source["real_business"]["trace_id"]
            data = request(env, "http://tempo:3200/api/traces/" + trace)
            if not data.get("batches", data.get("resourceSpans")):
                raise MonitoringError("LIVE_HISTORY_TRACE_MISSING")
            env.report["history_trace"] = {"trace_id": trace, "source_run": source["run_id"]}
            env.check(
                "历史真实trace查询",
                "passed",
                "源signals报告的真实模型trace仍可查；生命周期保护另据lifecycle独立证据",
            )
            rules = request(env, "http://grafana:3000/api/prometheus/grafana/api/v1/rules", True)
            states = [
                {"name": r["name"], "state": r["state"]}
                for g in rules["data"]["groups"]
                for r in g["rules"]
            ]
            env.report["rules"] = states
            if len(states) != 8 or any(r["state"] != "inactive" for r in states):
                raise MonitoringError("LIVE_RULES_NOT_RECOVERED")
            env.check("八类规则恢复", "passed", "实际八类规则均inactive，默认规则未改阈值")
            env.report["notification_events"] = request(env, "http://webhook-sink:8080/events")
            # sink随容器重建清空属于设计；历史通知证据已单独归档。
            env.report["queried_at_epoch"] = time.time()
    except BaseException as exc:
        error = (
            exc if isinstance(exc, MonitoringError) else MonitoringError("LIVE_QUERY_CHECK_FAILED")
        )
        print("查询验证未完成：" + error.code, flush=True)
    finally:
        env.finish(error)
        target = Path(__file__).parent / "artifacts" / env.run_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "queries.json").write_bytes((env.artifact / "report.json").read_bytes())
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
