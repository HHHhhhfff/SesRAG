"""用64KiB临时内存盘验证Loki满盘诊断，不填满宿主或应用磁盘。"""

import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment, checked_child, private_directory
from helpers.preflight import MODULE, PREFIX, MonitoringError, load
from helpers.render import write_json
from helpers.verify import request


def main():
    e = Environment("disk005")
    error = None
    try:
        with e.mutex():
            if e.state or any(e.inventory().values()):
                raise MonitoringError("OBS005_DISK_FIXTURE_NOT_EMPTY")
            private_directory(e.path)
            e.state = {
                "owner": uuid.uuid4().hex,
                "daemon_id": e.run(["docker", "info", "--format", "{{.ID}}"]).strip(),
                "status": "starting",
                "resources": {},
            }
            # 工具复用已Prepare/Pull过的005环境ImageID，绝不隐式下载。
            e.state["tool_image"] = load(MODULE / "runtime/verify005/ledger.json")["tool_image"]
            e.save()
            labels = [
                "--label",
                "com.docker.compose.project=" + e.project,
                "--label",
                PREFIX + "module=obs005",
                "--label",
                PREFIX + "environment=" + e.environment,
                "--label",
                PREFIX + "owner=" + e.state["owner"],
            ]
            e.run(["docker", "network", "create", *labels, e.project + "_monitoring"])
            config = load(MODULE / "loki/config.yaml")
            config["ingester"].update(chunk_idle_period="1s", max_chunk_age="2s")
            write_json(e.path / "loki.json", config)
            name = e.project + "-loki"
            e.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--pull=never",
                    "--memory=1536m",
                    "--cpus=1",
                    "--cap-drop=ALL",
                    *labels,
                    "--name",
                    name,
                    "--network",
                    e.project + "_monitoring",
                    "--network-alias",
                    "loki",
                    "--tmpfs",
                    "/loki:rw,size=64k,uid=10001,gid=10001,mode=0700",
                    "-v",
                    str((e.path / "loki.json").resolve()) + ":/config.json:ro",
                    e.images["loki"]["reference"],
                    "-config.file=/config.json",
                ]
            )
            deadline = time.monotonic() + 120
            found = False
            while time.monotonic() < deadline:
                raw = subprocess.run(
                    ["docker", "logs", name], capture_output=True, timeout=10
                ).stdout
                raw += subprocess.run(
                    ["docker", "logs", name], capture_output=True, timeout=10
                ).stderr
                if b"no space left on device" in raw:
                    found = True
                    break
                try:
                    request(
                        e,
                        "http://loki:3100/loki/api/v1/push",
                        data={
                            "streams": [
                                {
                                    "stream": {"service": "obs005-disk", "environment": "disk005"},
                                    "values": [
                                        [str(time.time_ns()), secrets.token_hex(4096)]
                                        for _ in range(32)
                                    ],
                                }
                            ]
                        },
                    )
                except MonitoringError:
                    pass
                time.sleep(2)
            if not found:
                raise MonitoringError("OBS005_DISK_FULL_NOT_OBSERVED")
            e.report["disk_fixture"] = {
                "tmpfs_bytes": 65536,
                "no_space_error_observed": True,
                "host_or_application_disk_filled": False,
            }
            e.check(
                "真实ENOSPC诊断",
                "passed",
                "64KiB隔离tmpfs已触发no-space错误；未打印日志正文/路径，未填宿主盘",
            )
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        try:
            if e.state:
                for c in e.inventory()["container"]:
                    e.run(["docker", "rm", "-f", c["id"]])
                for n in e.inventory()["network"]:
                    e.run(["docker", "network", "rm", n["id"]])
                import shutil

                shutil.rmtree(checked_child(MODULE / "runtime", e.path))
                e.check("满盘夹具清理", "passed", "内存盘/容器/网络/runtime均释放")
        except BaseException as cleanup:
            error = cleanup
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
