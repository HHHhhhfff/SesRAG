"""005专用应用的可复现准备/清理；不是监控主入口，不操作日常应用。"""

import argparse
import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment, private_directory
from helpers.preflight import MODULE, ROOT, MonitoringError

PROJECT = "sesrag-obs005-app"
MARKER = "io.sesrag.observability.validation"


def check_resources(e):
    for kind, command in [
        ("container", ["ps", "-aq"]),
        ("volume", ["volume", "ls", "-q"]),
        ("network", ["network", "ls", "-q"]),
    ]:
        ids = e.run(
            ["docker", *command, "--filter", "label=com.docker.compose.project=" + PROJECT]
        ).split()
        if not ids:
            continue
        data = json.loads(
            e.run(["docker", *([] if kind == "container" else [kind]), "inspect", *ids])
        )
        for item in data:
            labels = (
                item.get("Config", {}).get("Labels") if kind == "container" else item.get("Labels")
            )
            if not labels or labels.get(MARKER) != "obs005":
                raise MonitoringError(
                    "OBS005_APPLICATION_FIXTURE_OWNERSHIP", "同名应用资源缺本轮测试标记，拒绝接管"
                )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["Start", "Stop"])
    a = p.parse_args()
    e = Environment("fixture-preparation")
    error = None
    path = MODULE / ".cache/application"
    env = path / "application.env"
    command = [
        "docker",
        "compose",
        "--env-file",
        env,
        "-p",
        PROJECT,
        "--project-directory",
        ROOT,
        "-f",
        ROOT / "docker-compose.yml",
        "-f",
        MODULE / "validation/compose.application.yaml",
        "-f",
        MODULE / "application.override.yaml",
    ]
    try:
        check_resources(e)
        if a.action == "Start":
            private_directory(path)
            if not env.exists():
                password = secrets.token_hex(24)
                env.write_text(
                    "POSTGRES_PASSWORD="
                    + password
                    + "\nDATABASE_URL=postgresql+psycopg://sesrag:"
                    + password
                    + "@postgres:5432/sesrag\nOBS_ENVIRONMENT_ID=verify005\n"
                    "OBS_ENVIRONMENT=verify005\nMOCK_PROVIDER=true\nMINERU_ENABLED=false\n",
                    encoding="utf-8",
                )
            e.run(
                [
                    "docker",
                    "build",
                    "--pull=false",
                    "-t",
                    "sesrag-obs005-app:local",
                    "-f",
                    ROOT / "docker/api/Dockerfile",
                    ROOT,
                ],
                timeout=1200,
            )
            e.run([*command, "config", "--quiet"])
            e.run(
                [
                    *command,
                    "up",
                    "-d",
                    "--no-build",
                    "--pull",
                    "never",
                    "postgres",
                    "redis",
                    "migrate",
                    "api",
                    "worker",
                ],
                timeout=180,
            )
            deadline = time.monotonic() + 120
            while True:
                health = e.run(
                    [
                        "docker",
                        "inspect",
                        PROJECT + "-api-1",
                        "--format",
                        "{{.State.Health.Status}}",
                    ]
                ).strip()
                if health == "healthy":
                    break
                if time.monotonic() > deadline:
                    raise MonitoringError("OBS005_APPLICATION_FIXTURE_READY")
                time.sleep(2)
            e.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    MODULE / "integration/export_binding.py",
                    "--environment",
                    "verify005",
                    "--project",
                    PROJECT,
                    "--network",
                    PROJECT + "_default",
                    "--output",
                    path / "contract.json",
                ]
            )
            e.check(
                "005隔离应用准备",
                "passed",
                "专用项目/回环18005/Mock；凭据只在受限.cache，不调用付费服务",
            )
        else:
            if not env.exists():
                raise MonitoringError(
                    "OBS005_APPLICATION_ENV_REQUIRED", "缺原受限env文件，禁止猜测清理归属"
                )
            network = e.run(
                [
                    "docker",
                    "network",
                    "ls",
                    "-q",
                    "--filter",
                    "label=com.docker.compose.project=" + PROJECT,
                ]
            ).split()
            for nid in network:
                members = json.loads(e.run(["docker", "network", "inspect", nid]))[0].get(
                    "Containers", {}
                )
                for cid in members:
                    labels = json.loads(e.run(["docker", "inspect", cid]))[0]["Config"].get(
                        "Labels", {}
                    )
                    if labels.get("com.docker.compose.project") != PROJECT:
                        raise MonitoringError(
                            "OBS005_MONITORING_STILL_CONNECTED", "先Destroy监控环境再清理应用夹具"
                        )
            e.run([*command, "down", "--volumes", "--timeout", "30"], timeout=120)
            e.check(
                "005隔离应用清理", "passed", "仅清带obs005测试标记的应用资源；镜像/报告/备份保留"
            )
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
