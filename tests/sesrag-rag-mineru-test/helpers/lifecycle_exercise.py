"""真实Docker环境工程演练；只验证生命周期，不接入产品分类case。"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.common import ROOT, SUITE, child_env, load, terminate_tree, write


def invoke(identity, extra, expected, timeout=5400):
    args = [sys.executable, str(SUITE / "helpers/orchestrate.py"), "--run-id", identity, *extra]
    process = subprocess.Popen(args, cwd=ROOT, env=child_env(), start_new_session=os.name != "nt")
    try:
        code = process.wait(timeout=timeout)
    finally:
        if process.poll() is None:
            terminate_tree(process)
    if code != expected:
        raise ValueError(f"演练退出码不符：{identity} expected={expected} actual={code}")
    if "--mode" not in extra or extra[extra.index("--mode") + 1] != "Cleanup":
        summary = load(SUITE / "artifacts" / identity / "summary.json")
        if summary["cleanup"] != "passed":
            raise ValueError("演练清理失败")
        return summary
    return load(SUITE / "artifacts" / identity / "cleanup.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    prefix = args.prefix
    results = []
    first = invoke(prefix + "-env1", ["--mode", "Environment"], 0)
    frozen = first["frozen_build"]
    results.append(first)
    results.append(invoke(prefix + "-env2", ["--mode", "Environment", "--frozen-build", frozen], 0))
    for fault in ("startup", "child-failure", "child-timeout"):
        results.append(
            invoke(
                prefix + "-" + fault,
                [
                    "--mode",
                    "Environment",
                    "--frozen-build",
                    frozen,
                    "--engineering-fault",
                    fault,
                    "--startup-timeout-seconds",
                    "90",
                ],
                2,
            )
        )
    identity = prefix + "-hardkill"
    process = subprocess.Popen(
        [
            sys.executable,
            str(SUITE / "helpers/orchestrate.py"),
            "--run-id",
            identity,
            "--mode",
            "Environment",
            "--frozen-build",
            frozen,
            "--hold-seconds",
            "180",
        ],
        cwd=ROOT,
        env=child_env(),
        start_new_session=os.name != "nt",
    )
    try:
        deadline = time.monotonic() + 600
        while not list((SUITE / "artifacts" / identity).glob("*/addresses.json")):
            if process.poll() is not None or time.monotonic() > deadline:
                raise ValueError("强停演练未到达就绪等待点")
            time.sleep(1)
    finally:
        terminate_tree(process)
    results.append(invoke(identity, ["--mode", "Cleanup"], 0))
    results.append(invoke(identity, ["--mode", "Cleanup"], 0))
    results.append(invoke(prefix + "-planned", ["--mode", "All"], 3))
    results.append(invoke(prefix + "-real-gate", ["--mode", "Real"], 3))
    target = SUITE / "artifacts" / (prefix + "-engineering.json")
    write(
        target,
        {
            "status": "passed",
            "scope": "环境工程，产品not_run，无真实外发",
            "frozen_build": frozen,
            "runs": results,
        },
    )
    print(json.dumps({"engineering": "passed", "record": target.name}), flush=True)


if __name__ == "__main__":
    main()
