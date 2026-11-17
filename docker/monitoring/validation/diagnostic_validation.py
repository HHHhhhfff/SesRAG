"""实际捕获特定诊断规则的NoData/Error及恢复，归档sink白名单证据。"""

import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import load
from helpers.render import write_json
from helpers.verify import request
from live_validation import wait


def main():
    e = Environment("verify005")
    error = None
    path = e.path / "generated/provisioning/alerting/rules.yaml"
    original = path.read_bytes()
    cleanup = path.with_name("diagnostic-delete.yaml")
    ids = []

    def reload():
        request(e, "http://grafana:3000/api/admin/provisioning/alerting/reload", True, {})

    try:
        with e.mutex():
            config = load(path)
            diagnostic = copy.deepcopy(config["groups"][0]["rules"][0])
            diagnostic["for"] = "0s"
            uid = "obs005-diagnostic-validation"
            ids = [uid]
            diagnostic.update(uid=uid, title="OBS005-DIAGNOSTIC-VALIDATION")
            group = {
                "orgId": 1,
                "name": "obs005-diagnostic",
                "folder": "sesrag-observe",
                "interval": "10s",
                "rules": [diagnostic],
            }
            config["groups"].append(group)

            def events(alertname, status, after):
                items = request(e, "http://webhook-sink:8080/events")["events"]
                return [
                    x
                    for x in items
                    if x["received_at"] >= after
                    and any(
                        a["status"] == status
                        and a["labels"].get("alertname") == alertname
                        and a["labels"].get("rulename") == "OBS005-DIAGNOSTIC-VALIDATION"
                        for a in x["alerts"]
                    )
                ]

            for name, expr in [
                ("DatasourceNoData", "obs005_intentionally_missing"),
                ("DatasourceError", "invalid_promql("),
            ]:
                floor = time.time()
                diagnostic["data"][0]["model"]["expr"] = expr
                write_json(path, config)
                reload()
                received = wait(
                    e,
                    name + "真实通知",
                    lambda name=name, floor=floor: events(name, "firing", floor),
                    180,
                )
                e.report.setdefault("diagnostics", []).append({"type": name, "firing": received})
                diagnostic["data"][0]["model"]["expr"] = "vector(0)"
                write_json(path, config)
                reload()
                resolved = wait(
                    e,
                    name + "真实恢复",
                    lambda name=name, floor=floor: events(name, "resolved", floor),
                    180,
                )
                e.report["diagnostics"][-1]["resolved"] = resolved
                e.check(
                    name + "独立路由/恢复",
                    "passed",
                    "按本轮时间边界及特定rulename核验，Firing/Resolved已归档",
                )
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        path.write_bytes(original)
        write_json(
            cleanup, {"apiVersion": 1, "deleteRules": [{"orgId": 1, "uid": uid} for uid in ids]}
        )
        try:
            reload()
        except BaseException as exc:
            error = exc
        cleanup.unlink(missing_ok=True)
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
