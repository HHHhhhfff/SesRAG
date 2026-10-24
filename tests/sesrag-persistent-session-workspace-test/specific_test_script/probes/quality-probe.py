"""QLT_002/004：在本轮只读源码工具容器执行真实后端门禁及负样本。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


def invalid_contract_errors(directory):
    """QLT_002：所有$ref仅解析仓库契约，禁止退回网络获取。"""
    base = "https://sesrag.local/contracts/"
    resources = []
    for file in directory.glob("*.json"):
        schema = json.loads(file.read_text(encoding="utf-8"))
        schema["$id"] = urljoin(base, schema.get("$id", file.name))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    schema = registry.contents(base + "run_event_v2.json")
    invalid = {"schema_version": 2, "run_id": "not-a-uuid", "seq": -1, "type": "invented.tool"}
    return list(
        Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()).iter_errors(
            invalid
        )
    )


def main():
    output = Path("/outputs/quality")
    checks = []
    commands = [
        (
            "ruff",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "backend",
                "tests/unit",
                "tests/api",
                "tests/integration",
                "migrations",
            ],
        ),
        (
            "mypy",
            [sys.executable, "-m", "mypy", "backend", "--cache-dir=/outputs/quality/mypy-cache"],
        ),
        (
            "pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/unit",
                "tests/api",
                "tests/integration",
                "-o",
                "cache_dir=/outputs/quality/pytest-cache",
                "--junitxml=/outputs/quality/quality-pytest.xml",
            ],
        ),
        (
            "counter",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/unit/test_model_profiles.py",
                "tests/unit/test_context_planning.py",
                "--junitxml=/outputs/quality/counter-pytest.xml",
            ],
        ),
    ]
    for name, argv in commands:
        result = subprocess.run(
            argv,
            cwd="/work",
            text=True,
            capture_output=True,
            timeout=900,
            env={
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
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        log = result.stdout + result.stderr
        if len(log.encode()) > 8 * 1024 * 1024:
            raise RuntimeError("QUALITY_LOG_LIMIT_EXCEEDED")
        (output / f"{name}.log").write_text(log, encoding="utf-8")
        checks.append({"name": name, "exit_code": result.returncode, "command": argv[1:]})
    # 真正坏字面样本必须到达JSON Schema拒绝分支。
    errors = invalid_contract_errors(Path("/work/contracts"))
    checks.append(
        {
            "name": "bad-contract-rejected",
            "exit_code": 0 if errors else 1,
            "error_count": len(errors),
        }
    )
    (output / "quality-backend.json").write_text(
        json.dumps({"checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": "passed", "checks": len(checks)}))


if __name__ == "__main__":
    main()
