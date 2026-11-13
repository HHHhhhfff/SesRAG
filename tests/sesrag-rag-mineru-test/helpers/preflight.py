"""无付费预检；真实门禁不足时阻止任何部署后的业务外发。"""

import re
import shutil

from helpers.common import ROOT, SUITE, command, digest


def source_fingerprint():
    _, output = command(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        output_limit=10 * 1024**2,
    )
    files = {}
    build = {}
    for name in sorted(set(output.split("\0")) - {""}):
        path = ROOT / name
        if not path.is_file():
            files[name] = "deleted"
            continue
        value = digest(path.read_bytes())
        files[name] = value
        if path.suffix.lower() not in {".md", ".png", ".jpg", ".pdf"} and (
            name.startswith(
                (
                    "backend/",
                    "frontend/",
                    "contracts/",
                    "migrations/",
                    "docker/",
                    "tests/sesrag-rag-mineru-test/",
                )
            )
            or name in {"pyproject.toml", ".dockerignore", "alembic.ini"}
        ):
            build[name] = value
    return {
        "source": digest(files),
        "build_source": digest(build),
        "head": command(["git", "rev-parse", "HEAD"])[1].strip(),
        "dirty": bool(command(["git", "status", "--porcelain"])[1].strip()),
        "files": files,
    }


def check_tools():
    for executable in ("docker", "git"):
        if shutil.which(executable) is None:
            raise ValueError(f"TOOL_MISSING_{executable}")
    version = command(["docker", "compose", "version", "--short"])[1].strip().lstrip("v")
    numbers = tuple(int(n) for n in re.findall(r"\d+", version)[:3])
    if numbers < (2, 24, 4):
        raise ValueError("COMPOSE_2_24_4_REQUIRED")
    info = load_json_command(["docker", "info", "--format", "{{json .}}"])
    if info["OSType"] != "linux":
        raise ValueError("LINUX_CONTAINERS_REQUIRED")
    free = shutil.disk_usage(SUITE).free
    if free < 5 * 1024**3:
        raise ValueError("DISK_BELOW_5_GIB")
    return {
        "compose": version,
        "engine": info["ServerVersion"],
        "os_type": info["OSType"],
        "cpus": info["NCPU"],
        "memory_bytes": info["MemTotal"],
        "disk_free_bytes": free,
        "resource_recommendation": "建议4核/8GiB/20GiB；本检查不证明性能达标",
    }


def load_json_command(args):
    import json

    return json.loads(command(args)[1])


def real_gate(path, plan_name):
    # 保留原调用入口；能力门禁独立模块便于离线自测。
    from helpers.live_preflight import evaluate

    return evaluate(path, plan_name, SUITE)
