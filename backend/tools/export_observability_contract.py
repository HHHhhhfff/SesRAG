"""只读能力导出与接口/指标漂移检测；不读取私密文档或调用Docker。"""

import argparse
import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

from backend.infrastructure.observability.metrics import CATALOG, CATALOG_PATH, ObservabilityMetrics

ROOT = Path(__file__).resolve().parents[2]


def fingerprint():
    digest = hashlib.sha256()
    files = [
        p
        for directory in ("backend", "contracts/observability", "migrations/versions")
        for p in (ROOT / directory).rglob("*")
        if p.suffix in {".py", ".json"}
    ]
    files += [
        ROOT / p
        for p in (
            "pyproject.toml",
            "docker/api/Dockerfile",
            "docker-compose.yml",
            "docker/observability-requirements.lock",
        )
    ]
    for path in sorted(files):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def source_ref():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def capability():
    data = json.loads(
        (CATALOG_PATH.parent / "application_v1.example.json").read_text(encoding="utf-8")
    )
    data.update(
        application_version=version("sesrag"),
        source_ref=source_ref(),
        source_fingerprint=fingerprint(),
        metrics=CATALOG,
    )
    return data


def check():
    from backend.app import create_app

    schema = json.loads((CATALOG_PATH.parent / "capabilities_v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(capability())
    declared = {
        (t[0], t[1])
        for i in CATALOG
        if i["logical_id"] == "HTTP_REQUESTS"
        for t in i["allowed_tuples"]
        if t[1].startswith(("/api/", "/health/"))
    }
    actual = {
        (method.upper(), path)
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    }
    if declared != actual:
        raise ValueError("OBS_ROUTE_CONTRACT_DRIFT")
    for role in ("api", "worker"):
        metrics = ObservabilityMetrics(f"sesrag-{role}", "local")
        if set(metrics.catalog_names) != {i["name"] for i in CATALOG if role in i["roles"]}:
            raise ValueError("OBS_METRIC_CONTRACT_DRIFT")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    check()
    if args.output:
        args.output.write_text(
            json.dumps(capability(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print("应用观测契约与实际指标/路由一致")


if __name__ == "__main__":
    main()
