"""005配置撤销实际入库验证，不把删除本地文件等同数据库对象删除。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError, load
from helpers.render import write_json
from helpers.verify import query, request


def main():
    e = Environment("verify005")
    error = None
    source = e.path / "generated/provisioning/datasources/datasources.yaml"
    original = source.read_bytes()
    try:
        with e.mutex():
            config = load(source)
            temporary = dict(config["datasources"][0])
            temporary.update(uid="obs005-retired-test", name="005撤销验证临时数据源")
            temporary["isDefault"] = False
            config["datasources"].append(temporary)
            write_json(source, config)
            request(e, "http://grafana:3000/api/admin/provisioning/datasources/reload", True, {})
            if not any(
                x["uid"] == "obs005-retired-test"
                for x in request(e, "http://grafana:3000/api/datasources", True)
            ):
                raise MonitoringError("OBS005_PROVISION_CREATE")
            source.write_bytes(original)
            request(e, "http://grafana:3000/api/admin/provisioning/datasources/reload", True, {})
            if any(
                x["uid"] == "obs005-retired-test"
                for x in request(e, "http://grafana:3000/api/datasources", True)
            ):
                raise MonitoringError("OBS005_PROVISION_PRUNE")
            e.check("数据源撤销prune", "passed", "临时UID实际创建后撤销；Grafana数据库查询确认消失")
            rules = request(e, "http://grafana:3000/api/v1/provisioning/alert-rules", True)
            if len(rules) != 8 or {x["folderUID"] for x in rules} != {"sesrag-observe"}:
                raise MonitoringError("OBS005_RULE_UID_CLEANUP")
            e.check(
                "规则撤销/固定目录",
                "passed",
                "数据库仅八类生产规则，诊断规则已删除；共享sesrag-observe UID",
            )
            groups = request(e, "http://grafana:3000/api/prometheus/grafana/api/v1/rules", True)[
                "data"
            ]["groups"]
            for group in groups:
                for rule in group["rules"]:
                    values = query(e, rule["query"])
                    if not values or any(float(x["value"][1]) != 0 for x in values):
                        raise MonitoringError("OBS005_NORMAL_IDLE_NONZERO", rule["name"])
                    if rule["state"] != "inactive":
                        raise MonitoringError("OBS005_NORMAL_IDLE_ALERT", rule["name"])
            e.check(
                "正式配置idle",
                "passed",
                "八类真实表达式均非空且为0，实际规则inactive，无流量不误报",
            )
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        source.write_bytes(original)
        try:
            request(e, "http://grafana:3000/api/admin/provisioning/datasources/reload", True, {})
        except Exception:
            pass
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
