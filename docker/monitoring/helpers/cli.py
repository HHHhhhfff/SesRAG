"""PowerShell与Linux共用唯一动作入口。"""

import argparse
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError


def main():
    p = argparse.ArgumentParser(description="SesRAG独立本地监控生命周期")
    p.add_argument(
        "action",
        choices=[
            "Prepare",
            "RefreshBinding",
            "Pull",
            "Validate",
            "Start",
            "Status",
            "Verify",
            "Stop",
            "Destroy",
            "Backup",
            "Restore",
        ],
    )
    p.add_argument("--environment", default="local")
    p.add_argument("--application-contract", type=Path)
    p.add_argument("--grafana-port", type=int, default=3000)
    p.add_argument("--host-otlp", action="store_true")
    p.add_argument("--erase-monitoring-data", action="store_true")
    p.add_argument("--backup-id")
    a = p.parse_args()
    if (
        not re.fullmatch("[a-z0-9][a-z0-9-]{0,31}", a.environment)
        or not 1024 <= a.grafana_port <= 65535
    ):
        p.error("环境身份或端口非法")
    try:
        env = Environment(a.environment)
    except MonitoringError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    error = None
    try:
        with env.mutex():
            if a.action == "Prepare":
                if not a.application_contract:
                    raise MonitoringError("OBS005_CONTRACT_REQUIRED", "需要显式部署契约文件")
                env.prepare(a.application_contract, a.grafana_port, a.host_otlp)
            elif a.action == "Destroy":
                env.destroy(a.erase_monitoring_data)
            elif a.action == "RefreshBinding":
                if not a.application_contract:
                    raise MonitoringError("OBS005_CONTRACT_REQUIRED")
                env.refresh_binding(a.application_contract)
            elif a.action == "Restore":
                if not a.backup_id:
                    raise MonitoringError("OBS005_BACKUP_ID_REQUIRED")
                env.restore(a.backup_id)
            elif a.action == "Verify":
                from helpers.verify import verify

                verify(env)
            else:
                getattr(env, a.action.lower())()
    except (Exception, KeyboardInterrupt) as exc:
        error = exc
        print(
            "操作失败：" + str(exc)
            if isinstance(exc, MonitoringError)
            else "操作失败：OBS005_INTERNAL（已保留脱敏报告）",
            file=sys.stderr,
        )
    finally:
        env.finish(error)
    return 1 if error or env.report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
