"""将004只读能力与实际Docker部署身份绑定；不启动/重建应用。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment
from helpers.preflight import (
    MODULE,
    ROOT,
    digest,
    docker_admission,
    load,
    source_fingerprint,
    validate_contract,
)
from helpers.render import write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--environment", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--network", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--platform", choices=["docker-desktop", "linux-host"], default="docker-desktop")
    p.add_argument("--api-host", default="api")
    p.add_argument("--worker-hosts", default="worker")
    a = p.parse_args()
    c = load(MODULE / "integration/application-contract.example.json")
    c.update(
        environment_id=a.environment,
        application_project=a.project,
        application_network=a.network,
        application_network_id=json.loads(
            subprocess.check_output(["docker", "network", "inspect", a.network])
        )[0]["Id"],
        source_ref=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        source_fingerprint=source_fingerprint(),
        contract_reference_hash=digest(ROOT / "docs/接口文档.md"),
        platform=a.platform,
    )
    c["services"]["api"]["targets"][0]["host"] = a.api_host
    c["services"]["worker"]["targets"] = [
        {"host": h, "port": 9102, "path": "/metrics"} for h in a.worker_hosts.split(",")
    ]
    validate_contract(c)
    e = Environment(a.environment)
    error = None
    try:
        docker_admission(e.run, c, a.environment)
        write_json(a.output, c)
        e.check("部署接入描述导出", "passed", "真实源码/指标/应用容器/网络归属匹配；不包含Secret")
    except BaseException as exc:
        error = exc
        raise
    finally:
        e.finish(error)


if __name__ == "__main__":
    main()
