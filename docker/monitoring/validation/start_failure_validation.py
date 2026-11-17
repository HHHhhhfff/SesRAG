"""005真实资源回滚：注入就绪探测失败，验证仅回收本轮创建资源。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError


def main():
    e = Environment("verify005")
    error = None
    real = e.wait_ready

    def fail_ready():
        raise MonitoringError("OBS005_INJECTED_READY_FAILURE", "005受控探测失败")

    try:
        with e.mutex():
            e.reconcile()
            e.check_drift()
            healthy = e.inventory()
            e.wait_ready = fail_ready
            try:
                e.start()
            except MonitoringError as exc:
                if exc.code != "OBS005_INJECTED_READY_FAILURE":
                    raise
            else:
                raise MonitoringError("OBS005_FAILURE_NOT_TRIGGERED")
            if {x["id"] for x in healthy["container"]} != {
                x["id"] for x in e.inventory()["container"]
            }:
                raise MonitoringError("OBS005_HEALTHY_ENVIRONMENT_DESTROYED")
            e.wait_ready = real
            real()
            e.save("running")
            e.check("既有健康环境失败保护", "passed", "探测失败不拆已有六容器；原ID不变且仍ready")
            e.stop()
            volumes = {x["id"] for x in e.inventory()["volume"]}
            e.wait_ready = fail_ready
            try:
                e.start()
            except MonitoringError as exc:
                if exc.code != "OBS005_INJECTED_READY_FAILURE":
                    raise
            else:
                raise MonitoringError("OBS005_FAILURE_NOT_TRIGGERED")
            now = e.inventory()
            if now["container"] or now["network"] or volumes != {x["id"] for x in now["volume"]}:
                raise MonitoringError("OBS005_START_ROLLBACK_INVALID")
            e.check("新建资源失败回收", "passed", "仅清本轮六容器/监控网络；原五卷ID保留")
            e.wait_ready = real
            e.start()
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.wait_ready = real
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
