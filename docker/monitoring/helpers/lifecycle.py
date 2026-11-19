"""仅操作具有完整所有权标签的监控资源；有限等待、账本及一致性备份。"""

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

from .preflight import (
    MODULE,
    PREFIX,
    VOLUMES,
    MonitoringError,
    digest,
    docker_admission,
    load,
    safe_archive_members,
    safe_environment,
    validate_contract,
    validate_image_lock,
)
from .render import render, write_json


def owned(labels, environment, nonce):
    labels = labels or {}
    return all(
        labels.get(k) == v
        for k, v in {
            "com.docker.compose.project": "sesrag-observe-" + environment,
            PREFIX + "module": "obs005",
            PREFIX + "environment": environment,
            PREFIX + "owner": nonce,
        }.items()
    )


def checked_child(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if root == path or root not in path.parents:
        raise MonitoringError("OBS005_PATH_ESCAPE", "拒绝越界文件操作")
    return path


def check_prepare_directory(path, contract_path):
    path = Path(path)
    if not path.exists():
        return
    files = [p for p in path.rglob("*") if p.is_file() or p.is_symlink()]
    expected = path / "inputs/application-contract.json"
    if files and (
        len(files) != 1
        or files[0].resolve() != expected.resolve()
        or Path(contract_path).resolve() != expected.resolve()
        or files[0].is_symlink()
    ):
        raise MonitoringError(
            "OBS005_ORPHAN_RUNTIME", "没有完整账本的runtime含其它文件，拒绝覆盖Secret或接管孤立状态"
        )


def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import csv
        import io

        who = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        sid = next(csv.reader(io.StringIO(who)))[1]
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    else:
        path.chmod(0o700)


def source_snapshot():
    files = []
    for folder in (
        "alloy",
        "loki",
        "tempo",
        "grafana",
        "platform",
        "helpers",
        "integration",
        "tools",
    ):
        files.extend(
            p for p in (MODULE / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts
        )
    files.extend(MODULE / name for name in ("compose.yaml", "requirements-host.lock"))
    return {p.relative_to(MODULE).as_posix(): digest(p) for p in files}


def verify_manifest(path, images):
    path = Path(path)
    try:
        manifest = load(path / "manifest.json")
        if manifest.get("complete") is not True or manifest.get("images") != images:
            raise ValueError()
        expected = set(manifest["files"])
        if expected != {v + ".tar.gz" for v in VOLUMES} | {"runtime.tar.gz"}:
            raise ValueError()
        expanded = 0
        for name, sha in manifest["files"].items():
            target = checked_child(path, path / name)
            if digest(target) != sha:
                raise ValueError()
            with tarfile.open(target) as archive:
                expanded += safe_archive_members(archive.getmembers(), 12 * 1024**3 - expanded)
    except Exception:
        raise MonitoringError(
            "OBS005_BACKUP_INVALID", "备份不完整、版本/hash不一致或归档越界"
        ) from None
    return manifest


class Environment:
    def __init__(self, environment):
        self.environment = environment
        self.project = "sesrag-observe-" + environment
        self.path = MODULE / "runtime" / environment
        self.run_id = (
            dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        )
        self.artifact = MODULE / "artifacts" / self.run_id
        self.artifact.mkdir(parents=True, exist_ok=False)
        self.report = {
            "schema_version": 1,
            "run_id": self.run_id,
            "environment": environment,
            "checks": [],
            "status": "running",
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        self.state = (
            load(self.path / "ledger.json") if (self.path / "ledger.json").exists() else None
        )
        self.images = validate_image_lock(load(MODULE / "images.lock.json"))
        self.deadline = None

    def check(self, name, status, detail=""):
        self.report["checks"].append({"name": name, "status": status, "detail": detail})
        print(f"[{status}] {name}：{detail}", flush=True)
        write_json(self.artifact / "report.json", self.report)

    def run(self, args, timeout=60, allow_failure=False):
        if self.deadline is not None:
            timeout = min(timeout, self.deadline - time.monotonic())
            if timeout <= 0:
                raise MonitoringError("OBS005_ACTION_TIMEOUT", "动作整体预算耗尽")
        # 参数数组且清理继承环境，绝不使用shell或打印展开后的环境值。
        process = subprocess.Popen(
            [str(x) for x in args],
            cwd=MODULE,
            env=safe_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        started = time.monotonic()
        try:
            while True:
                try:
                    stdout, stderr = process.communicate(
                        timeout=min(30, max(0.1, timeout - (time.monotonic() - started)))
                    )
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= timeout:
                        raise MonitoringError(
                            "OBS005_COMMAND_TIMEOUT", "子进程超出动作预算"
                        ) from None
                    print("操作仍在进行，等待受限子进程返回……", flush=True)
        except BaseException:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=10,
                    env=safe_environment(),
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.stdout.close()
                process.stderr.close()
            raise
        if process.returncode and not allow_failure:
            # 原始stderr可能带路径/环境；只存受控错误类别。
            self.report.setdefault("command_failures", []).append(
                {"executable": Path(args[0]).name, "code": process.returncode}
            )
            raise MonitoringError(
                "OBS005_COMMAND_FAILED",
                f"子进程退出码{process.returncode}；原始输出可能含敏感值，公开报告不回显",
            )
        return stdout

    @contextlib.contextmanager
    def mutex(self):
        directory = MODULE / ".cache/locks"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / (self.environment + ".lock")).open("a+b") as f:
            f.seek(0)
            f.write(b"0")
            f.flush()
            f.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                raise MonitoringError("OBS005_ENVIRONMENT_BUSY", "同环境动作正在执行") from None
            try:
                self.state = (
                    load(self.path / "ledger.json")
                    if (self.path / "ledger.json").exists()
                    else None
                )
                yield
            finally:
                f.seek(0)
                if os.name == "nt":
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(f, fcntl.LOCK_UN)

    def save(self, status=None):
        if status:
            self.state["status"] = status
        write_json(self.path / "ledger.json", self.state)

    def inventory(self):
        result = {}
        for kind, command in [
            ("container", ["ps", "-aq"]),
            ("volume", ["volume", "ls", "-q"]),
            ("network", ["network", "ls", "-q"]),
        ]:
            ids = self.run(
                ["docker", *command, "--filter", "label=com.docker.compose.project=" + self.project]
            ).split()
            resources = (
                json.loads(
                    self.run(["docker", *([] if kind == "container" else [kind]), "inspect", *ids])
                )
                if ids
                else []
            )
            for item in resources:
                labels = (
                    item.get("Config", {}).get("Labels")
                    if kind == "container"
                    else item.get("Labels")
                )
                if not self.state or not owned(labels, self.environment, self.state["owner"]):
                    raise MonitoringError(
                        "OBS005_RESOURCE_OWNERSHIP", "同project资源不属于当前环境，拒绝接管或删除"
                    )
            result[kind] = [
                {
                    "id": x.get("Id", x.get("Name")),
                    "name": x.get("Name", ""),
                    "status": x.get("State", {}).get("Status", ""),
                    "oom": x.get("State", {}).get("OOMKilled", False),
                    "service": x.get("Config", {})
                    .get("Labels", {})
                    .get("com.docker.compose.service"),
                }
                for x in resources
            ]
        return result

    def reconcile(self, cleanup=False):
        if not self.state:
            raise MonitoringError("OBS005_NOT_PREPARED", "先执行Prepare")
        daemon = self.run(["docker", "info", "--format", "{{.ID}}"]).strip()
        if daemon != self.state["daemon_id"]:
            raise MonitoringError("OBS005_DAEMON_CHANGED", "Docker daemon身份已改变")
        inventory = self.inventory()
        old = self.state.get("resources", {})
        # 崩溃后新增自有资源可以补账，已有同名卷/容器被替换则拒绝。
        for kind in ("container", "network"):
            previous = {x["name"]: x["id"] for x in old.get(kind, [])}
            for item in inventory[kind]:
                if (
                    item["name"] in previous
                    and previous[item["name"]] != item["id"]
                    and self.state["status"] == "running"
                ):
                    if not cleanup:
                        raise MonitoringError(
                            "OBS005_RESOURCE_ID_DRIFT", "运行资源被外部替换，须先Stop核验"
                        )
                    self.check(
                        "资源ID重入",
                        "passed",
                        "已按完整project/environment/owner标签核验替换资源；清理不因ID漂移阻断",
                    )
        self.state["resources"] = inventory
        self.save()
        return inventory

    def compose(self, arguments, timeout=60):
        args = [
            "docker",
            "compose",
            "--env-file",
            self.path / "monitoring.env",
            "-p",
            self.project,
            "--project-directory",
            MODULE,
            "-f",
            MODULE / "compose.yaml",
        ]
        if self.state.get("platform") == "linux-host":
            args += ["-f", MODULE / "platform/compose.linux-host.yaml"]
        if self.state.get("host_otlp"):
            args += ["-f", self.path / "generated/host-otlp.json"]
        return self.run([*args, *arguments], timeout=timeout)

    def ensure_images(self):
        for key, item in self.images.items():
            if key == "node_exporter" and self.state.get("platform") != "linux-host":
                continue
            reference = self.state["tool_image"] if key == "tools" else item["reference"]
            data = json.loads(self.run(["docker", "image", "inspect", reference]))[0]
            if data["Architecture"] != "amd64" or data["Os"] != "linux":
                raise MonitoringError("OBS005_IMAGE_PLATFORM", key)
            if key == "tools" and data["Id"] != reference:
                raise MonitoringError("OBS005_TOOL_IMAGE_DRIFT", key)

    def check_drift(self):
        contract = validate_contract(
            load(self.path / "inputs/application-contract.json"), check_source=False
        )
        if (
            self.state["environment"] != self.environment
            or contract["environment_id"] != self.environment
            or not re.fullmatch("[a-f0-9]{32}", self.state["owner"])
            or type(self.state["port"]) is not int
            or not 1024 <= self.state["port"] <= 65535
            or type(self.state["host_otlp"]) is not bool
            or self.state["platform"] != contract["platform"]
            or not re.fullmatch("(sha256:[a-f0-9]{64})?", self.state["tool_image"])
        ):
            raise MonitoringError("OBS005_LEDGER_SCHEMA", "恢复账本身份或类型无效")
        if self.state.get("env_hash") != digest(self.path / "monitoring.env"):
            raise MonitoringError("OBS005_ENV_FILE_DRIFT", "环境文件已被手工改写")
        if (self.path / "monitoring.env").read_text(encoding="utf-8") != self.environment_text():
            raise MonitoringError(
                "OBS005_ENV_BINDING", "环境文件绑定与当前受控目录/镜像/契约不一致"
            )
        cache = MODULE / ".cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            expected = render(contract, temporary)
            if self.state["host_otlp"]:
                p = Path(temporary) / "host-otlp.json"
                write_json(p, {"services": {"alloy": {"ports": ["127.0.0.1:4318:4318"]}}})
                expected["host-otlp.json"] = digest(p)
            if (self.path / "generated/provisioning/alerting/rules.yaml").exists():
                expected["provisioning/alerting/rules.yaml"] = expected["rules.pending.json"]
            actual = {
                p.relative_to(self.path / "generated").as_posix(): digest(p)
                for p in (self.path / "generated").rglob("*")
                if p.is_file()
            }
            if expected != actual or expected != self.state["generated_hashes"]:
                raise MonitoringError(
                    "OBS005_GENERATED_BINDING", "生成配置必须等于受信模板和版本化契约的有限渲染"
                )
        for name, sha in self.state["generated_hashes"].items():
            if (
                not (self.path / "generated" / name).is_file()
                or digest(self.path / "generated" / name) != sha
            ):
                raise MonitoringError("OBS005_GENERATED_DRIFT", name)
        if self.state["image_lock_hash"] != digest(MODULE / "images.lock.json"):
            raise MonitoringError("OBS005_IMAGE_LOCK_DRIFT", "镜像锁已变更，先备份并显式升级")
        if self.state["source_hashes"] != source_snapshot():
            raise MonitoringError("OBS005_TEMPLATE_DRIFT", "只读模块文件集合或内容不一致")

    def prepare(self, contract_path, port=3000, host_otlp=False):
        contract = validate_contract(load(contract_path))
        if contract["environment_id"] != self.environment:
            raise MonitoringError("OBS005_ENVIRONMENT_MISMATCH")
        daemon_id = docker_admission(self.run, contract, self.environment)
        if self.state:
            self.reconcile()
        self.inventory()  # 新环境也必须拒绝已有同名外来资源。
        if self.state:
            self.check_drift()
            if self.state["contract_hash"] != digest(contract_path):
                raise MonitoringError("OBS005_CONTRACT_CHANGED", "已有环境拒绝隐式换绑")
            if self.state["port"] != port or self.state["host_otlp"] != host_otlp:
                raise MonitoringError(
                    "OBS005_INPUT_DRIFT", "现有端口或OTLP profile不同，需显式迁移"
                )
            self.check("Prepare", "passed", "已有配置/Secret保持不变")
            return
        check_prepare_directory(self.path, contract_path)
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise MonitoringError("OBS005_PORT_IN_USE", "Grafana回环端口已占用") from None
        if host_otlp:
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", 4318))
                except OSError:
                    raise MonitoringError("OBS005_OTLP_PORT_IN_USE", "OTLP回环端口已占用") from None
        private_directory(self.path)
        secret_dir = self.path / "secrets"
        private_directory(secret_dir)
        password = secret_dir / "grafana-password"
        password.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        if os.name != "nt":
            password.chmod(0o600)
        write_json(self.path / "inputs/application-contract.json", contract)
        nonce = uuid.uuid4().hex
        self.state = {
            "environment": self.environment,
            "owner": nonce,
            "daemon_id": daemon_id,
            "platform": contract["platform"],
            "port": port,
            "host_otlp": host_otlp,
            "contract_hash": digest(contract_path),
            "image_lock_hash": digest(MODULE / "images.lock.json"),
            "resources": {},
            "tool_image": "",
            "source_hashes": {},
        }
        self.state["generated_hashes"] = render(contract, self.path / "generated")
        if host_otlp:
            write_json(
                self.path / "generated/host-otlp.json",
                {"services": {"alloy": {"ports": ["127.0.0.1:4318:4318"]}}},
            )
            self.state["generated_hashes"]["host-otlp.json"] = digest(
                self.path / "generated/host-otlp.json"
            )
        self.state["source_hashes"] = source_snapshot()
        self.write_env()
        self.save("prepared")
        self.check(
            "Prepare", "passed", "G1～G5、网络/容器实际归属及指标能力通过；凭据仅保存在私有runtime"
        )

    def refresh_binding(self, contract_path):
        """显式更新同一部署的源码依据；不能改变网络/目标/信号语义。"""
        self.reconcile()
        self.check_drift()
        current = load(self.path / "inputs/application-contract.json")
        incoming = validate_contract(load(contract_path))
        provenance = {"source_ref", "source_fingerprint", "contract_reference_hash"}
        if {k: v for k, v in current.items() if k not in provenance} != {
            k: v for k, v in incoming.items() if k not in provenance
        }:
            raise MonitoringError(
                "OBS005_BINDING_IDENTITY", "仅允许同一网络/目标/语义的源码依据更新"
            )
        docker_admission(self.run, incoming, self.environment)
        if incoming == current:
            self.check("RefreshBinding", "passed", "绑定未变化，配置和Secret保持")
            return
        previous_hash = self.state["contract_hash"]
        write_json(self.path / "inputs/application-contract.json", incoming)
        self.state["contract_hash"] = digest(self.path / "inputs/application-contract.json")
        self.report["binding_refresh"] = {
            "previous_hash": previous_hash,
            "current_hash": self.state["contract_hash"],
        }
        self.save(self.state["status"])
        self.check("RefreshBinding", "passed", "来源更新；采集身份/地址、模板、镜像和Secret不变")

    def environment_text(self):
        c = load(self.path / "inputs/application-contract.json")
        values = {
            "OBS_ENVIRONMENT_ID": self.environment,
            "OBS_OWNER": self.state["owner"],
            "OBS_GRAFANA_PORT": str(self.state["port"]),
            "OBS_APPLICATION_NETWORK": c["application_network"],
            "OBS_GENERATED": (self.path / "generated").as_posix(),
            "OBS_SECRET": (self.path / "secrets/grafana-password").as_posix(),
        }
        for key, item in self.images.items():
            values["IMAGE_" + key.upper()] = (
                self.state["tool_image"] if key == "tools" else item["reference"]
            )
        return "".join(f"{k}={v}\n" for k, v in values.items())

    def write_env(self):
        (self.path / "monitoring.env").write_text(self.environment_text(), encoding="utf-8")
        self.state["env_hash"] = digest(self.path / "monitoring.env")

    def pull(self):
        self.reconcile()
        self.check_drift()
        for key, item in self.images.items():
            if key == "tools" or (
                key == "node_exporter" and self.state["platform"] != "linux-host"
            ):
                continue
            exists = self.run(["docker", "image", "ls", "-q", item["reference"]]).strip()
            if not exists:
                self.run(
                    ["docker", "pull", "--platform", "linux/amd64", item["reference"]], timeout=1200
                )
            self.check("镜像 " + key, "passed", item["reference"])
        tool_hash = hashlib.sha256(
            "".join(digest(p) for p in sorted((MODULE / "tools").glob("*")) if p.is_file()).encode()
        ).hexdigest()
        tag = "sesrag-obs005-tools:" + tool_hash[:12]
        self.run(
            [
                "docker",
                "build",
                "--pull=false",
                "--build-arg",
                "BASE_IMAGE=" + self.images["python"]["reference"],
                "-t",
                tag,
                MODULE / "tools",
            ],
            timeout=1200,
        )
        self.state["tool_image"] = self.run(
            ["docker", "image", "inspect", tag, "--format", "{{.Id}}"]
        ).strip()
        self.write_env()
        self.save()

    def tool(self, arguments, network=True, mounts=(), timeout=60, input_path=None):
        args = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--memory=384m",
            "--cpus=0.5",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--label",
            "com.docker.compose.project=" + self.project,
            "--label",
            PREFIX + "module=obs005",
            "--label",
            PREFIX + "environment=" + self.environment,
            "--label",
            PREFIX + "owner=" + self.state["owner"],
        ]
        if "/tools/volume_inspector.py" in arguments:
            args += [
                "--user",
                "0:0",
                "--cap-add=CHOWN",
                "--cap-add=DAC_OVERRIDE",
                "--cap-add=FOWNER",
            ]
        if network:
            args += ["--network", self.project + "_monitoring"]
        for source, target, ro in mounts:
            args += ["-v", f"{source}:{target}" + (":ro" if ro else "")]
        return self.ephemeral(args, [self.state["tool_image"], "python", *arguments], timeout)

    def ephemeral(self, prefix, command, timeout=60):
        cid = self.path / ("cid-" + uuid.uuid4().hex)
        labels = [
            "--label",
            "com.docker.compose.project=" + self.project,
            "--label",
            PREFIX + "module=obs005",
            "--label",
            PREFIX + "environment=" + self.environment,
            "--label",
            PREFIX + "owner=" + self.state["owner"],
        ]
        try:
            return self.run([*prefix, "--cidfile", cid, *labels, *command], timeout=timeout)
        finally:
            if cid.exists():
                container_id = cid.read_text().strip()
                deadline = self.deadline
                self.deadline = None
                try:
                    self.run(["docker", "rm", "-f", container_id], allow_failure=True)
                finally:
                    self.deadline = deadline
                cid.unlink(missing_ok=True)

    def validate(self):
        self.reconcile()
        self.check_drift()
        self.ensure_images()
        self.compose(["config", "--quiet"])
        checks = [
            (
                "prometheus",
                ["/bin/promtool", "check", "config", "/config/prometheus.yml"],
                self.path / "generated",
                "/config",
            ),
            (
                "loki",
                ["-config.file=/config/config.yaml", "-verify-config=true"],
                MODULE / "loki",
                "/config",
            ),
            ("alloy", ["validate", "/config/config.alloy"], self.path / "generated", "/config"),
        ]
        for key, args, source, target in checks:
            prefix = [
                "docker",
                "run",
                "--rm",
                "--pull=never",
                "--memory=384m",
                "--cpus=0.5",
                "-v",
                f"{source}:{target}:ro",
            ]
            if key == "prometheus":
                prefix += ["--entrypoint", args.pop(0)]
            self.ephemeral(prefix, [self.images[key]["reference"], *args])
            self.check("配置解析 " + key, "passed", "固定镜像原生检查器")
        self.check(
            "Tempo配置", "not_run", "该版本无纯解析入口，Start/Verify以真实ready和写入查询验证"
        )

    def start(self):
        self.deadline = time.monotonic() + 180
        self.reconcile()
        self.check_drift()
        self.ensure_images()
        contract = validate_contract(load(self.path / "inputs/application-contract.json"))
        docker_admission(self.run, contract, self.environment)
        previous = self.inventory()
        existing = {x["id"] for x in previous["container"]}
        self.save("starting")
        try:
            self.compose(["up", "-d", "--no-build", "--pull", "never"], timeout=180)
            self.state["resources"] = self.inventory()
            self.save()
            self.wait_ready()
            self.install_provisioning()
            self.save("running")
            self.check("Start", "passed", "五组件与本地sink就绪，应用未重建")
            self.deadline = None
        except BaseException:
            self.deadline = None
            now = self.inventory()
            for item in now["container"]:
                if item["id"] not in existing:
                    self.run(["docker", "rm", "-f", item["id"]])
            if not previous["network"]:
                for item in now["network"]:
                    self.run(["docker", "network", "rm", item["id"]])
            self.state["resources"] = self.inventory()
            self.save("failed")
            raise

    def wait_ready(self):
        self.tool(["/tools/telemetry_fixture.py", "ready"], timeout=180)

    def install_provisioning(self):
        from .verify import request

        folders = request(self, "http://grafana:3000/api/folders", True)
        matching = [x for x in folders if x["title"] == "sesrag-observe"]
        if len(matching) != 1 or matching[0]["uid"] != "sesrag-observe":
            raise MonitoringError("OBS005_FOLDER_UID", "仪表盘/告警folder必须共用固定UID")
        name = "provisioning/alerting/rules.yaml"
        target = self.path / "generated" / name
        if not target.exists():
            target.write_bytes((self.path / "generated/rules.pending.json").read_bytes())
            request(self, "http://grafana:3000/api/admin/provisioning/alerting/reload", True, {})
            self.state["generated_hashes"][name] = digest(target)
            self.save()

    def stop(self):
        # 清理不依赖接入契约、模板或应用网络仍存在，直接核完整所有权后操作。
        inventory = self.reconcile(cleanup=True)
        if inventory["container"]:
            self.run(
                ["docker", "stop", "--time", "30", *[x["id"] for x in inventory["container"]]],
                timeout=90,
            )
        for item in inventory["container"]:
            self.run(["docker", "rm", "-f", item["id"]])
        for item in inventory["network"]:
            self.run(["docker", "network", "rm", item["id"]])
        self.state["resources"] = self.inventory()
        self.save("stopped")
        self.check("Stop", "passed", "容器/监控网络已删除；五卷、Secret、配置保留")

    def destroy(self, erase):
        if not erase:
            raise MonitoringError("OBS005_EXPLICIT_ERASE_REQUIRED", "需要-EraseMonitoringData")
        if not self.state:
            self.inventory()
            if self.path.exists() and any(self.path.iterdir()):
                raise MonitoringError(
                    "OBS005_ORPHAN_RUNTIME", "账本缺失但runtime非空，拒绝假报无残留或删除未核准数据"
                )
            self.check("Destroy", "passed", "不存在监控资源")
            return
        self.stop()
        for item in self.inventory()["volume"]:
            self.run(["docker", "volume", "rm", item["id"]])
        remaining = self.inventory()
        if any(remaining.values()):
            raise MonitoringError("OBS005_CLEANUP_INCOMPLETE")
        shutil.rmtree(checked_child(MODULE / "runtime", self.path))
        self.check(
            "Destroy", "passed", "监控容器/卷/网络/runtime均为空；应用、镜像、缓存、报告、备份保留"
        )

    def volume_stats(self):
        volumes = self.inventory()["volume"]
        if not volumes:
            return []
        return json.loads(
            self.tool(
                ["/tools/volume_inspector.py", "stats"],
                network=False,
                mounts=[
                    (v["id"], "/volumes/" + v["name"].removeprefix(self.project + "_"), True)
                    for v in volumes
                ],
            )
        )

    def status(self):
        if not self.state:
            self.inventory()
            self.check("Status", "passed", "absent")
            return
        inventory = self.reconcile()
        self.report["resources"] = inventory
        try:
            self.check_drift()
            self.check("配置漂移", "passed")
        except MonitoringError as exc:
            self.check("配置漂移", "failed", exc.code)
        self.report["volumes"] = self.volume_stats() if self.state["tool_image"] else []
        if inventory["container"]:
            self.report["stats"] = self.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    *[x["id"] for x in inventory["container"]],
                ]
            ).splitlines()
            from .verify import request

            try:
                targets = request(self, "http://prometheus:9090/api/v1/targets")["data"][
                    "activeTargets"
                ]
                self.report["targets"] = [
                    {"job": t["labels"]["job"], "health": t["health"]} for t in targets
                ]
            except Exception:
                self.check("抓取状态", "blocked", "监控未就绪或Prometheus不可读")
        self.report["retention"] = {
            "prometheus": "7d/2GB blocks",
            "loki": "72h",
            "tempo": "24h",
            "total_volume_budget_gib": 10,
        }
        self.report["limits"] = {
            "core_memory_mib": 6144,
            "core_cpus": 3.75,
            "sink_memory_mib": 128,
            "single_tool_memory_mib": 384,
        }
        self.check("Status", "passed", self.state["status"])

    def backup(self):
        self.reconcile()
        self.check_drift()
        self.ensure_images()
        original_status = self.state["status"]
        running_services = [
            c["service"]
            for c in self.inventory()["container"]
            if c["status"] == "running" and c.get("service")
        ]
        running = bool(running_services)
        backup = MODULE / "backups" / self.environment / self.run_id
        private_directory(backup)
        if running:
            self.stop()
        try:
            volume_list = self.inventory()["volume"]
            if len(volume_list) != 5:
                raise MonitoringError("OBS005_BACKUP_VOLUME_SET", "备份要求五卷完整存在")
            for v in volume_list:
                logical = v["name"].removeprefix(self.project + "_")
                self.tool(
                    ["/tools/volume_inspector.py", "backup", "--name", logical],
                    network=False,
                    mounts=[(v["id"], "/source", True), (backup.as_posix(), "/backup", False)],
                    timeout=600,
                )
            with tarfile.open(backup / "runtime.tar.gz", "w:gz") as archive:
                for p in self.path.rglob("*"):
                    if p.is_file():
                        archive.add(p, arcname=p.relative_to(self.path).as_posix(), recursive=False)
            manifest = {
                "complete": True,
                "environment": self.environment,
                "images": self.images,
                "files": {p.name: digest(p) for p in backup.glob("*.tar.gz")},
                "created_at": self.report["started_at"],
            }
            write_json(backup / "manifest.json", manifest)
            verify_manifest(backup, self.images)
            self.report["backup_id"] = self.run_id
            self.check("Backup", "passed", "五卷及私有配置完整备份；公共报告只含ID/hash")
        finally:
            if running:
                # 恢复原运行状态不以应用在线为前提，不重新接管应用。
                self.compose(
                    ["up", "-d", "--no-build", "--pull", "never", *running_services], timeout=180
                )
                if len(running_services) == 6:
                    self.wait_ready()
                self.state["resources"] = self.inventory()
                self.save(original_status)

    def restore(self, backup_id):
        backup = checked_child(
            MODULE / "backups" / self.environment, MODULE / "backups" / self.environment / backup_id
        )
        verify_manifest(backup, self.images)
        if self.path.exists() and any(self.path.iterdir()):
            raise MonitoringError(
                "OBS005_RESTORE_NOT_EMPTY", "runtime非空或账本不完整，拒绝覆盖凭据"
            )
        if self.state:
            inv = self.reconcile()
            if any(inv.values()):
                raise MonitoringError("OBS005_RESTORE_NOT_EMPTY", "目标已有容器/卷/网络，禁止覆盖")
            # prepared的Secret同样不应被隐式替换。
            raise MonitoringError("OBS005_RESTORE_NOT_EMPTY", "目标runtime已存在，先明确Destroy")
        self.inventory()
        private_directory(self.path)
        with tarfile.open(backup / "runtime.tar.gz") as archive:
            member = archive.getmember("ledger.json")
            recovered = json.load(archive.extractfile(member))
            if recovered["environment"] != self.environment or recovered[
                "image_lock_hash"
            ] != digest(MODULE / "images.lock.json"):
                raise MonitoringError("OBS005_BACKUP_ENVIRONMENT", "备份身份或镜像锁不匹配")
            archive.extractall(self.path)
        self.state = load(self.path / "ledger.json")
        self.state["resources"] = {}
        if self.run(["docker", "info", "--format", "{{.ID}}"]).strip() != self.state["daemon_id"]:
            raise MonitoringError("OBS005_DAEMON_CHANGED", "同环境恢复需使用原Docker daemon")
        self.check_drift()
        self.save("stopped")
        self.ensure_images()
        for logical in VOLUMES:
            volume = self.project + "_" + logical
            self.run(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    "com.docker.compose.project=" + self.project,
                    "--label",
                    PREFIX + "module=obs005",
                    "--label",
                    PREFIX + "environment=" + self.environment,
                    "--label",
                    PREFIX + "owner=" + self.state["owner"],
                    volume,
                ]
            )
            self.tool(
                ["/tools/volume_inspector.py", "restore", "--name", logical],
                network=False,
                mounts=[(volume, "/target", False), (backup.as_posix(), "/backup", True)],
                timeout=600,
            )
        self.state["resources"] = self.inventory()
        self.save("stopped")
        self.check("Restore", "passed", "同版本五卷/配置已恢复到空环境；Start仍须核实际应用准入")

    def finish(self, error=None):
        statuses = [x["status"] for x in self.report["checks"]]
        self.report["status"] = (
            "failed"
            if error or "failed" in statuses
            else ("partial" if any(x in statuses for x in ("not_run", "blocked")) else "passed")
        )
        if error:
            self.report["error"] = {
                "code": getattr(error, "code", "OBS005_INTERNAL"),
                "detail": getattr(error, "detail", "内部错误，详查本模块验证"),
            }
        self.report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        if self.state:
            self.report["provenance"] = {
                k: self.state.get(k)
                for k in (
                    "daemon_id",
                    "contract_hash",
                    "image_lock_hash",
                    "tool_image",
                    "source_hashes",
                    "generated_hashes",
                )
            }
        write_json(self.artifact / "report.json", self.report)
        print("脱敏报告：docker/monitoring/artifacts/" + self.run_id + "/report.json", flush=True)
