"""005真实保留/恢复/销毁/所有权演练，只操作已存在的verify005隔离环境。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError
from helpers.verify import query, request


def protection(e):
    # 其它project的ID/卷清单与应用事实计数；不导出业务正文或凭据。
    data = e.run(["docker", "ps", "-aq"]).split()
    containers = json.loads(e.run(["docker", "inspect", *data])) if data else []
    protected = sorted(
        c["Id"]
        for c in containers
        if c["Config"].get("Labels", {}).get("com.docker.compose.project") != e.project
    )
    volumes = sorted(e.run(["docker", "volume", "ls", "-q"]).split())
    volumes = [v for v in volumes if not v.startswith(e.project + "_")]
    facts = e.run(
        [
            "docker",
            "exec",
            "sesrag-obs005-app-postgres-1",
            "psql",
            "-U",
            "sesrag",
            "-d",
            "sesrag",
            "-At",
            "-c",
            "SELECT 'threads='||count(*) FROM threads "
            "UNION ALL SELECT 'runs='||count(*) FROM runs "
            "UNION ALL SELECT 'tasks='||count(*) FROM tasks;",
        ]
    )
    return {"containers": protected, "volumes": volumes, "fact_counts": facts.splitlines()}


def main():
    e = Environment("verify005")
    error = None
    try:
        with e.mutex():
            e.reconcile()
            e.check_drift()
            before = protection(e)
            e.report["protection_before"] = before
            fixture = json.loads(
                e.tool(
                    ["/tools/telemetry_fixture.py", "signals", "--environment", e.environment],
                    timeout=90,
                )
            )
            trace = fixture["trace_id"]
            e.report["history_trace_id"] = trace
            e.stop()
            e.start()
            request(e, "http://tempo:3200/api/traces/" + trace)
            if not query(e, 'up{environment="verify005"}'):
                raise MonitoringError("OBS005_STOP_HISTORY")
            e.check("Stop/Start历史保留", "passed", "固定trace仍可查，五卷未重建")
            e.backup()
            backup_id = e.report["backup_id"]
            try:
                e.restore(backup_id)
            except MonitoringError as exc:
                if exc.code != "OBS005_RESTORE_NOT_EMPTY":
                    raise
                e.check("非空恢复拒绝", "passed")
            else:
                raise MonitoringError("OBS005_NONEMPTY_RESTORE_ACCEPTED")
            e.destroy(True)
            # 删除监控历史后不能借旧活容器返回成功；资源必须为空。
            e.state = None
            if any(e.inventory().values()):
                raise MonitoringError("OBS005_DESTROY_REMAINS")
            e.restore(backup_id)
            e.start()
            request(e, "http://tempo:3200/api/traces/" + trace)
            sources = request(e, "http://grafana:3000/api/datasources", True)
            if len(sources) != 3:
                raise MonitoringError("OBS005_RESTORE_DATASOURCES")
            e.check(
                "同版本五卷/Secret/配置恢复",
                "passed",
                "真实trace、数据源、API抓取均恢复；卷根权限验证通过",
            )
            after = protection(e)
            e.report["protection_after"] = after
            if before != after:
                raise MonitoringError("OBS005_PROTECTED_RESOURCE_CHANGED")
            e.check(
                "应用与其它project保护", "passed", "容器ID/业务卷/Thread Run Task事实计数前后一致"
            )
            # 最终保留运行环境给后续故障演练；最终交付再明确Destroy。
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
