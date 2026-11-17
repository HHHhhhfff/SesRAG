"""接入契约、受控环境、资源身份与归档安全门禁。"""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
PREFIX = "io.sesrag.observability."
VOLUMES = ("grafana_data", "prometheus_data", "loki_data", "tempo_data", "alloy_data")


class MonitoringError(Exception):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_image_lock(data):
    names = {"grafana", "prometheus", "loki", "tempo", "alloy", "python", "node_exporter", "tools"}
    if data.get("schema_version") != 1 or set(data.get("images", {})) != names:
        raise MonitoringError("OBS005_IMAGE_LOCK_SCHEMA", "固定镜像集合不完整")
    for key, item in data["images"].items():
        if key == "tools":
            continue
        ref = item.get("reference", "")
        if (
            not re.fullmatch(r"[a-z0-9/.-]+@sha256:[0-9a-f]{64}", ref)
            or ref.split("@")[-1] != item.get("digest")
            or item.get("platform") != "linux/amd64"
            or item.get("tag", "").endswith(":latest")
        ):
            raise MonitoringError("OBS005_IMAGE_DIGEST", key)
    return data["images"]


def source_fingerprint():
    # 与004导出的源码范围一致，不读Secret、运行目录或本模块生成文件。
    h = hashlib.sha256()
    files = [
        p
        for d in ("backend", "contracts/observability", "migrations/versions")
        for p in (ROOT / d).rglob("*")
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
    for p in sorted(files):
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def deployment_fingerprint():
    h = hashlib.sha256()
    files = [
        p
        for d in ("backend", "contracts/observability", "migrations/versions")
        for p in (ROOT / d).rglob("*")
        if p.suffix in {".py", ".json"}
    ]
    files += [ROOT / "pyproject.toml"]
    for p in sorted(files):
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def validate_contract(data, check_source=True):
    try:
        Draft202012Validator(
            load(MODULE / "integration/application-contract.schema.json")
        ).validate(data)
    except Exception as exc:
        # Schema错误不回显输入值，避免凭据误填后进入报告。
        raise MonitoringError(
            "OBS005_CONTRACT_SCHEMA", getattr(exc, "json_path", "invalid")
        ) from None
    catalog = load(ROOT / "contracts/observability/metrics_v1.json")
    if data["metrics"] != catalog:
        raise MonitoringError("OBS005_METRIC_CONTRACT_DRIFT", "指标字典必须与004完整真源一致")
    for role in ("api", "worker"):
        if data["services"][role]["service_name"] != "sesrag-" + role:
            raise MonitoringError("OBS005_SERVICE_IDENTITY", role)
    if len(data["services"]["api"]["targets"]) != 1:
        raise MonitoringError("OBS005_API_SNAPSHOT_SOURCE", "本轮全局快照只允许唯一API统计来源")
    hosts = [t["host"] for role in ("api", "worker") for t in data["services"][role]["targets"]]
    if len(hosts) != len(set(hosts)):
        raise MonitoringError("OBS005_TARGET_NOT_UNIQUE", "每个实例需要唯一网络别名")
    if check_source:
        ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if data["source_ref"] != ref or data["source_fingerprint"] != source_fingerprint():
            raise MonitoringError("OBS005_SOURCE_DRIFT", "重新从目标版本导出能力并核实部署")
        if data["contract_reference_hash"] != digest(ROOT / "docs/接口文档.md"):
            raise MonitoringError(
                "OBS005_INTERFACE_REFERENCE_DRIFT", "正式接口文档变化，重新核对导出"
            )
    return data


def safe_environment(values=None):
    values = os.environ if values is None else values
    conflicts = sorted(k for k in values if k.startswith(("OBS_", "GF_", "IMAGE_")))
    if conflicts:
        raise MonitoringError("OBS005_SHELL_OVERRIDE", ",".join(conflicts))
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "DOCKER_HOST",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "COMMONPROGRAMFILES",
        "COMMONPROGRAMFILES(X86)",
        "COMMONPROGRAMW6432",
        "ALLUSERSPROFILE",
        "SYSTEMDRIVE",
        "HOMEDRIVE",
        "HOMEPATH",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
        "DOCKER_CERT_PATH",
        "DOCKER_TLS_VERIFY",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
    }
    return {k: v for k, v in values.items() if k.upper() in allowed}


def safe_archive_members(members, budget):
    total = 0
    for member in members:
        name = member.name.replace("\\", "/")
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or ":" in name
            or member.issym()
            or member.islnk()
        ):
            raise MonitoringError("OBS005_UNSAFE_ARCHIVE", "归档路径或链接越界")
        if not (member.isfile() or member.isdir()):
            raise MonitoringError("OBS005_UNSAFE_ARCHIVE", "仅允许普通文件和目录")
        total += member.size
        if total > budget:
            raise MonitoringError("OBS005_ARCHIVE_BUDGET", "展开大小超过允许预算")
    return total


def docker_admission(run, contract, environment, inspect_targets=True):
    info = json.loads(run(["docker", "info", "--format", "{{json .}}"]))
    if info["OSType"] != "linux" or info["MemTotal"] < 8 * 1024**3:
        raise MonitoringError("OBS005_DOCKER_CAPACITY", "需要Linux容器及至少8GiB Docker内存")
    if int(info["ServerVersion"].split(".")[0]) < 26:
        raise MonitoringError("OBS005_DOCKER_VERSION", "需要Engine26+")
    if shutil.disk_usage(MODULE).free < 12 * 1024**3:
        raise MonitoringError(
            "OBS005_HOST_DISK_BUDGET", "模块所在文件系统不足12GiB，镜像/应用/Docker数据盘另计"
        )
    compose = run(["docker", "compose", "version", "--short"]).strip().lstrip("v").split(".")
    if tuple(map(int, compose[:2])) < (2, 27):
        raise MonitoringError("OBS005_COMPOSE_VERSION", "需要Compose2.27+")
    if contract["platform"] == "linux-host" and (
        "Desktop" in info["OperatingSystem"] or os.name == "nt"
    ):
        raise MonitoringError("OBS005_PLATFORM", "Desktop不能使用Linux物理主机profile")
    network = json.loads(run(["docker", "network", "inspect", contract["application_network"]]))[0]
    if (
        network.get("Labels", {}).get("com.docker.compose.project")
        != contract["application_project"]
    ):
        raise MonitoringError("OBS005_FOREIGN_NETWORK", "应用网络归属不匹配")
    if contract["application_network_id"] != network["Id"]:
        raise MonitoringError("OBS005_NETWORK_ID_DRIFT", "应用网络已被替换，必须重新核准")
    alias = f"sesrag-obs-{environment}-alloy"
    for container_id in network.get("Containers", {}):
        other = json.loads(run(["docker", "inspect", container_id]))[0]
        aliases = other["NetworkSettings"]["Networks"].get(network["Name"], {}).get("Aliases") or []
        if (
            alias in aliases
            and other["Config"].get("Labels", {}).get("com.docker.compose.project")
            != "sesrag-observe-" + environment
        ):
            raise MonitoringError("OBS005_ALIAS_COLLISION", "应用网络存在占用监控别名的容器")
    if not inspect_targets:
        return info["ID"]
    ids = run(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=" + contract["application_project"],
        ]
    ).split()
    containers = json.loads(run(["docker", "inspect", *ids])) if ids else []
    for role in ("api", "worker"):
        for target in contract["services"][role]["targets"]:
            matches = [
                c
                for c in containers
                if target["host"]
                in (c["NetworkSettings"]["Networks"].get(network["Name"], {}).get("Aliases") or [])
            ]
            if len(matches) != 1:
                raise MonitoringError("OBS005_TARGET_OWNERSHIP", f"{role}别名必须对应唯一运行实例")
            c = matches[0]
            labels = c["Config"].get("Labels") or {}
            env = dict(x.split("=", 1) for x in c["Config"]["Env"] if "=" in x)
            required = {
                "OBS_ENVIRONMENT": environment,
                "OBS_SERVICE_NAME": "sesrag-" + role,
                "OBS_METRICS_ENABLED": "true",
                "OBS_TRACES_ENABLED": "true",
                "OBS_OTLP_ALLOWED_HOSTS": alias,
                "OBS_OTLP_TRACES_ENDPOINT": f"http://{alias}:4318/v1/traces",
            }
            if any(env.get(k) != v for k, v in required.items()):
                raise MonitoringError(
                    "OBS005_APPLICATION_OVERRIDE", f"{role}尚未显式应用观测override"
                )
            if (
                labels.get(PREFIX + "collect") != "true"
                or labels.get(PREFIX + "environment") != environment
            ):
                raise MonitoringError("OBS005_LOG_OPT_IN", f"{role}未授权日志采集")
            if c["HostConfig"]["LogConfig"]["Type"] != "json-file":
                raise MonitoringError("OBS005_LOG_DRIVER", f"{role}必须为受控json-file日志驱动")
            code = (
                "import hashlib; from pathlib import Path; root=Path('/app'); h=hashlib.sha256(); "
                "files=[p for d in ('backend','contracts/observability','migrations/versions') "
                "for p in (root/d).rglob('*') if p.suffix in {'.py','.json'}]"
                "+[root/'pyproject.toml']; "
                "[(h.update(p.relative_to(root).as_posix().encode()),h.update(p.read_bytes())) "
                "for p in sorted(files)]; print(h.hexdigest())"
            )
            actual = run(["docker", "exec", c["Id"], "python", "-c", code]).strip()
            if actual != deployment_fingerprint():
                raise MonitoringError("OBS005_DEPLOYED_SOURCE_DRIFT", f"{role}容器源码与声明不一致")
            metrics = run(
                [
                    "docker",
                    "exec",
                    c["Id"],
                    "python",
                    "-c",
                    f"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:{target['port']}/metrics',timeout=5).read().decode())",
                ]
            )
            for item in contract["metrics"]:
                if role in item["roles"] and item["initialization"] == "required_always":
                    if (
                        "# TYPE " + item["name"].removesuffix("_total") not in metrics
                        and "# TYPE " + item["name"] not in metrics
                    ):
                        raise MonitoringError("OBS005_REQUIRED_METRIC", item["logical_id"])
            if (
                f'environment="{environment}"' not in metrics
                or f'service="sesrag-{role}"' not in metrics
            ):
                raise MonitoringError("OBS005_SOURCE_LABEL", role)
    return info["ID"]
