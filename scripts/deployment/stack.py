"""应用所有者的一键入口；保留数据，监控下层仍独立。"""

# ruff: noqa: E402

import argparse
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parents[2] / "docker/monitoring"),
]
from helpers.lifecycle import Environment, private_directory
from helpers.preflight import MonitoringError, digest, load

from deployment.configuration import ROOT, RUNTIME, parse_env, prepare_configuration, write_json

PROJECT = "sesrag-live"
MARKER = "io.sesrag.deployment.owner"


def assert_owned(labels, owner):
    if (
        not labels
        or labels.get("com.docker.compose.project") != PROJECT
        or labels.get(MARKER) != owner
    ):
        raise ValueError("DEPLOY_FOREIGN_RESOURCE: 拒绝接管或删除缺少部署身份的资源")


def binding_identity(contract):
    return {
        k: v
        for k, v in contract.items()
        if k not in {"source_ref", "source_fingerprint", "contract_reference_hash"}
    }


def has_database(inventory):
    return any(v["Name"] == PROJECT + "_postgres_data" for v in inventory["volume"])


def record_child_result(observer, action, run_id, status):
    observer.report.setdefault("monitoring_runs", []).append(
        {"action": action, "run_id": run_id, "status": status}
    )
    if status == "partial":
        observer.check(
            "监控" + action + "未运行/受限子项",
            "not_run",
            "子报告" + run_id + "保留partial；不计作完整验收通过",
        )


class Stack:
    def __init__(self):
        self.observer = Environment("live-deployment")
        self.state_file = RUNTIME / "deployment.json"
        self.state = load(self.state_file) if self.state_file.exists() else None

    def run(self, args, timeout=60):
        return self.observer.run(args, timeout=timeout)

    def inventory(self):
        result = {}
        for kind, cmd in (
            ("container", ["ps", "-aq"]),
            ("volume", ["volume", "ls", "-q"]),
            ("network", ["network", "ls", "-q"]),
        ):
            ids = self.run(
                ["docker", *cmd, "--filter", "label=com.docker.compose.project=" + PROJECT]
            ).split()
            data = (
                json.loads(
                    self.run(["docker", *([] if kind == "container" else [kind]), "inspect", *ids])
                )
                if ids
                else []
            )
            for item in data:
                labels = item["Config"].get("Labels") if kind == "container" else item.get("Labels")
                assert_owned(labels, self.state["owner"] if self.state else "")
            result[kind] = data
        return result

    def check_state(self):
        if self.state is None or self.state.get("project") != PROJECT:
            raise ValueError("DEPLOY_NOT_PREPARED: 请先Prepare或Start")
        if self.state["daemon_id"] != self.run(["docker", "info", "--format", "{{.ID}}"]).strip():
            raise ValueError("DEPLOY_DAEMON_CHANGED: 不同Docker daemon，禁止接管")
        self.inventory()

    def compose(self, *args, timeout=60):
        return self.run(
            [
                "docker",
                "compose",
                "--env-file",
                ROOT / ".env",
                "--project-directory",
                ROOT,
                "-p",
                PROJECT,
                "-f",
                ROOT / "docker-compose.yml",
                "-f",
                ROOT / "docker/monitoring/application.override.yaml",
                "-f",
                ROOT / "scripts/compose.runtime.yaml",
                *args,
            ],
            timeout,
        )

    def prepare(self):
        if self.state:
            self.check_state()
            values = parse_env(ROOT / ".env")
            if values.get("SESRAG_DEPLOYMENT_OWNER") != self.state["owner"]:
                raise ValueError("DEPLOY_ENV_OWNER: 运行配置身份与账本不一致")
        else:
            # 没账本不接管任何同名project，即便容器已停或只剩卷。
            self.inventory()
            owner = uuid.uuid4().hex
            prepare_configuration(owner)
            self.state = {
                "project": PROJECT,
                "environment": "live",
                "owner": owner,
                "daemon_id": self.run(["docker", "info", "--format", "{{.ID}}"]).strip(),
            }
            write_json(self.state_file, self.state)
        self.compose("config", "--quiet")
        self.observer.check(
            "真实运行配置", "passed", "根.env及私有Profile已准备；凭据未输出，已有配置不覆盖"
        )

    def monitoring(self, action, candidate=None):
        monitor = Environment("live")
        error = None
        try:
            with monitor.mutex():
                if action == "Prepare":
                    monitor.prepare(candidate)
                elif action == "RefreshBinding":
                    monitor.refresh_binding(candidate)
                elif action == "Verify":
                    from helpers.verify import verify

                    verify(monitor)
                else:
                    getattr(monitor, action.lower())()
        except BaseException as exc:
            error = exc
            raise
        finally:
            monitor.finish(error)
            record_child_result(self.observer, action, monitor.run_id, monitor.report["status"])

    def wait_application(self):
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            states = self.compose("ps", "--format", "json", "api", "worker", "frontend")
            rows = [json.loads(line) for line in states.splitlines() if line.strip()]
            if (
                len(rows) == 3
                and all(x["State"] == "running" for x in rows)
                and next(x for x in rows if x["Service"] == "api").get("Health") == "healthy"
            ):
                self.observer.check(
                    "应用就绪", "passed", "API健康，Worker/前端运行；仅本机回环端口"
                )
                return
            print("等待应用API/Worker/前端就绪……", flush=True)
            time.sleep(5)
        raise ValueError("DEPLOY_APPLICATION_TIMEOUT: 应用未就绪，保留容器供诊断")

    def start(self, update=False):
        self.prepare()
        if update:
            # 停止写入后备份，失败立即停止；保留旧镜像ID便于人工回退。
            inv = self.inventory()
            self.observer.report["previous_images"] = {
                x["Config"]["Labels"]["com.docker.compose.service"]: x["Image"]
                for x in inv["container"]
            }
            if has_database(inv):
                self.monitoring("Stop")
                self.compose("stop", "--timeout", "30", "frontend", "api", "worker", timeout=120)
                # Destroy保留了数据库卷；即使容器为空也先只恢复PG，不能先跑迁移。
                self.compose("up", "-d", "--no-build", "--pull", "never", "postgres", timeout=120)
                deadline = time.monotonic() + 90
                while True:
                    pg = self.compose("ps", "--format", "json", "postgres")
                    row = json.loads(pg.strip()) if pg.strip() else {}
                    if row.get("Health") == "healthy":
                        break
                    if time.monotonic() > deadline:
                        raise ValueError("DEPLOY_DATABASE_TIMEOUT")
                    time.sleep(3)
                self.database_backup()
        self.compose("build", "migrate", "api", "worker", "frontend", timeout=1800)
        self.compose(
            "up",
            "-d",
            "--no-build",
            "postgres",
            "redis",
            "migrate",
            "api",
            "worker",
            "frontend",
            timeout=240,
        )
        self.wait_application()
        self.compose(
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "backend.tools.sync_model_profiles",
            "/app/config/live-model-profiles.json",
        )
        self.compose(
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "backend.tools.sync_rag_profiles",
            "/app/config/live-rag-profiles.json",
        )
        candidate = RUNTIME / "application-contract.json"
        self.run(
            [
                sys.executable,
                "-X",
                "utf8",
                ROOT / "docker/monitoring/integration/export_binding.py",
                "--environment",
                "live",
                "--project",
                PROJECT,
                "--network",
                PROJECT + "_default",
                "--output",
                candidate,
            ],
            timeout=120,
        )
        if (ROOT / "docker/monitoring/runtime/live/ledger.json").exists():
            self.monitoring("RefreshBinding", candidate)
        self.monitoring("Prepare", candidate)
        self.monitoring("Pull")
        self.monitoring("Validate")
        self.monitoring("Start")
        self.observer.check("持久服务启动", "passed", "应用与监控已启动；旧业务卷和其它project不变")

    def database_backup(self):
        stamp = self.observer.run_id
        target = RUNTIME / "backups" / stamp
        private_directory(target)
        self.compose("start", "postgres")
        cid = self.compose("ps", "-q", "postgres").strip()
        if not cid:
            raise ValueError("DEPLOY_DATABASE_UNAVAILABLE")
        remote = "/tmp/sesrag-deploy-" + stamp + ".dump"
        try:
            self.compose(
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "sesrag",
                "-d",
                "sesrag",
                "--format=custom",
                "-f",
                remote,
                timeout=180,
            )
            self.compose("exec", "-T", "postgres", "pg_restore", "--list", remote)
            self.run(["docker", "cp", cid + ":" + remote, target / "database.dump"], timeout=180)
        finally:
            self.compose("exec", "-T", "postgres", "rm", "-f", remote)
        self.observer.report["database_backup"] = {
            "backup_id": stamp,
            "sha256": digest(target / "database.dump"),
            "bytes": (target / "database.dump").stat().st_size,
        }
        self.observer.check(
            "更新前数据库备份", "passed", "停写后pg_dump且pg_restore清单有效；不自动降级数据库"
        )

    def stop(self, destroy=False):
        self.check_state()
        if (ROOT / "docker/monitoring/runtime/live/ledger.json").exists():
            self.monitoring("Stop")
        self.compose("stop", "--timeout", "30", timeout=150)
        if destroy:
            # 仅销毁停止容器；不使用down -v，保留应用网络ID供监控恢复绑定。
            self.compose("rm", "-f", timeout=120)
            if self.inventory()["container"]:
                raise ValueError("DEPLOY_CONTAINER_REMAINS")
        self.observer.check(
            "销毁容器" if destroy else "停止服务",
            "passed",
            "业务卷、应用网络、监控历史/Secret保留；没有删除数据",
        )

    def status(self):
        self.check_state()
        inventory = self.inventory()
        self.observer.report["application"] = [
            {
                "service": c["Config"]["Labels"]["com.docker.compose.service"],
                "status": c["State"]["Status"],
                "image": c["Image"],
            }
            for c in inventory["container"]
        ]
        self.monitoring("Status")
        self.observer.check("Status", "passed", "实际容器状态已归档")

    def verify(self):
        self.check_state()
        self.wait_application()
        self.monitoring("Verify")
        self.observer.check(
            "基础接线验证",
            "passed",
            "完整真实业务及告警另见tests/grafana-observability-test验证报告",
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "action", choices=["Prepare", "Start", "Update", "Stop", "Destroy", "Status", "Verify"]
    )
    args = p.parse_args()
    stack = Stack()
    error = None
    try:
        with stack.observer.mutex():
            if args.action == "Update":
                stack.start(update=True)
            elif args.action == "Destroy":
                stack.stop(destroy=True)
            else:
                getattr(stack, args.action.lower())()
    except BaseException as exc:
        error = exc
        # 限制公开异常内容，原始外部响应、密码和堆栈不回显。
        code = (
            str(exc).split(":", 1)[0]
            if isinstance(exc, (MonitoringError, ValueError))
            else "DEPLOY_INTERNAL"
        )
        print("部署动作失败：" + code, flush=True)
    finally:
        stack.observer.finish(
            error
            if isinstance(error, MonitoringError)
            else (MonitoringError("DEPLOY_FAILED") if error else None)
        )
        artifacts = ROOT / "tests/grafana-observability-test/artifacts" / stack.observer.run_id
        artifacts.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stack.observer.artifact / "report.json", artifacts / "deployment.json")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
