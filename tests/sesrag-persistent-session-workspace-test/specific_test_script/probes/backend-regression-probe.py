"""执行显式逐例测试节点；文件级结果不得自动推导为细粒度用例通过。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/work")
PROBES = Path(__file__).parent
PREFIXES = {
    "session": "SES",
    "context": "CTX",
    "model": "MOD",
    "run": "RUN",
    "compatibility": "COMP",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=PREFIXES, required=True)
    parser.add_argument("--expected-server-id", required=True)
    parser.add_argument("--expected-namespace", required=True)
    args = parser.parse_args()
    output = Path("/outputs") / args.category
    output.mkdir(parents=True, exist_ok=True)
    selectors = json.loads((PROBES / "case-selectors.json").read_text(encoding="utf-8"))
    cases = {
        key: value
        for key, value in selectors.items()
        if key.startswith(PREFIXES[args.category] + "_")
    }
    targets = sorted(
        {target for values in cases.values() for target in values if not target.startswith("@pg::")}
    )
    junit = output / "pytest-regression.xml"
    # 开发级回归自行显式构造Settings，不得意外继承Compose的真实HTTP Provider开关。
    env = {
        **{
            name: value
            for name, value in os.environ.items()
            if not name.startswith(
                (
                    "DATABASE_",
                    "REDIS_",
                    "MODEL_",
                    "MOCK_",
                    "EMBEDDING_",
                    "OWNER_",
                    "TASK_",
                    "UPLOAD_",
                )
            )
        },
        "WORKSPACE_TEST_DATABASE_URL": os.environ["DATABASE_URL"],
        "WORKSPACE_EXPECTED_SERVER_ID": args.expected_server_id,
        "WORKSPACE_EXPECTED_NAMESPACE": args.expected_namespace,
        "PYTHONPATH": "/work:/suite:/suite/specific_test_script/probes",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "pytest_asyncio.plugin",
            *(["-p", "pg_migration_plugin"] if args.category == "compatibility" else []),
            "-q",
            *[
                str(PROBES / "test_case_supplements.py") + "::" + target[7:]
                if target.startswith("@case::")
                else str(PROBES / "test_migration_supplements.py") + "::" + target[12:]
                if target.startswith("@migration::")
                else "tests/" + target
                for target in targets
            ],
            f"--junitxml={junit}",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=900,
    )
    log = process.stdout + process.stderr
    # 不截断证据再继续判定；日志过大是测试工程失败。
    if len(log.encode()) > 8 * 1024 * 1024:
        raise RuntimeError("TEST_LOG_LIMIT_EXCEEDED")
    (output / "pytest-regression.log").write_text(log, encoding="utf-8")
    if not junit.is_file():
        raise RuntimeError("PYTEST_JUNIT_MISSING")
    nodes = []
    for node in ET.parse(junit).getroot().iter("testcase"):
        classname = node.attrib.get("classname", "")
        file = classname.replace(".", "/") + ".py"
        nodes.append(
            {
                "node": file + "::" + node.attrib.get("name", ""),
                "status": "failed"
                if node.find("failure") is not None or node.find("error") is not None
                else "blocked"
                if node.find("skipped") is not None
                else "passed",
                "duration_seconds": float(node.attrib.get("time", "0")),
            }
        )
    results = []
    for case_id, targets_for_case in cases.items():
        observations = []
        missing = []
        for target in targets_for_case:
            if target.startswith("@pg::"):
                missing.append(target)
                continue
            if target.startswith(("@case::", "@migration::")):
                function = target.split("::", 1)[1]
                matches = [
                    node
                    for node in nodes
                    if node["node"].split("::")[-1] == function
                    or node["node"].split("::")[-1].startswith(function + "[")
                ]
                observations.extend(matches)
                if not matches:
                    missing.append(target)
                continue
            target = "tests/" + target
            matches = [
                node
                for node in nodes
                if node["node"] == target
                or node["node"].startswith(target + "[")
                or node["node"].startswith(target + "::")
            ]
            observations.extend(matches)
            if not matches:
                missing.append(target)
        state = (
            "failed"
            if any(node["status"] == "failed" for node in observations)
            else "blocked"
            if missing
            or not observations
            or any(node["status"] == "blocked" for node in observations)
            else "passed"
        )
        results.append(
            {
                "case_id": case_id,
                "status": state,
                "test_nodes": targets_for_case,
                "test_count": len(observations),
                "observations": observations,
                "missing_targets": missing,
                "reason": "指定节点未全部执行或有跳过项" if state == "blocked" else None,
            }
        )
    (output / "backend-regression.json").write_text(
        json.dumps(
            {
                "category": args.category,
                "pytest_exit_code": process.returncode,
                "case_results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # 产品断言失败仍正常交付结果；只有探针协议/采证错误才让helper本身失败。
    print(
        json.dumps(
            {
                "status": "passed",
                "pytest_exit_code": process.returncode,
                "collected_nodes": len(nodes),
            }
        )
    )


if __name__ == "__main__":
    main()
