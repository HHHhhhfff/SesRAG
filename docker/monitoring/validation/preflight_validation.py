"""005实际准入拒绝验证；不更改应用或启动监控资源。"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError, docker_admission, load, validate_contract


def main():
    e = Environment("verify005")
    error = None
    try:
        with e.mutex():
            c = load(e.path / "inputs/application-contract.json")
            before = e.inventory()
            cases = [
                ("缺指标字典", lambda x: x["metrics"].pop(), False),
                ("错误源码", lambda x: x.update(source_ref="0" * 40), False),
                (
                    "公网指标host",
                    lambda x: x["services"]["api"]["targets"][0].update(host="example.com"),
                    False,
                ),
                (
                    "其它project网络",
                    lambda x: x.update(application_project="foreign-project"),
                    True,
                ),
                ("替换网络ID", lambda x: x.update(application_network_id="0" * 64), True),
                ("Desktop拒绝Linux主机profile", lambda x: x.update(platform="linux-host"), True),
            ]
            for name, change, docker in cases:
                bad = copy.deepcopy(c)
                change(bad)
                try:
                    validate_contract(bad)
                    if docker:
                        docker_admission(e.run, bad, e.environment)
                except MonitoringError as exc:
                    e.check(name, "passed", "实际拒绝：" + exc.code)
                else:
                    raise MonitoringError("OBS005_NEGATIVE_NOT_REJECTED", name)
            if before != e.inventory():
                raise MonitoringError("OBS005_PREFLIGHT_MUTATION")
            e.check("拒绝路径无资源变更", "passed", "已有监控/应用均未启动、重建或删除")
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
