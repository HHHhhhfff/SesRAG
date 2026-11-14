"""唯一容器编排入口：资源账本先于启动，finally只清理本测试project。"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
ROOT = SUITE.parents[1]
sys.path.insert(0, str(ROOT))
from backend.tools.export_observability_contract import (  # noqa: E402
    capability,
    check,
    fingerprint,
    source_ref,
)


class Runner:
    def __init__(self, group, run_id=None, skip_build=False):
        self.group = group
        self.run_id = run_id or datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S"
        ) + "-" + secrets.token_hex(3)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", self.run_id):
            raise ValueError("run-id格式无效")
        self.project = "obs004-" + self.run_id.lower()
        self.runtime = SUITE / "runtime" / self.run_id
        self.artifacts = SUITE / "artifacts" / self.run_id
        self.runtime.mkdir(parents=True, exist_ok=False)
        from recovery import lock_file

        self.lease = lock_file(self.runtime / "run.lock")
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.env = os.environ.copy()
        self.env.update(
            OBS_TEST_PASSWORD=secrets.token_hex(24),
            OBS_TEST_ENCRYPTION_KEY=base64.b64encode(secrets.token_bytes(32)).decode(),
        )
        self.env_file = self.runtime / "test.env"
        self.env_file.write_text(
            "\n".join(
                k + "=" + self.env[k] for k in ("OBS_TEST_PASSWORD", "OBS_TEST_ENCRYPTION_KEY")
            )
            + "\n"
        )
        self.skip_build = skip_build
        self.compose_files = [SUITE / "compose/compose.yaml"]
        self.results = []
        self._safe_logs = []
        self.ledger = self.runtime / "ledger.json"
        self.ledger.write_text(json.dumps({"project": self.project, "suite": "observability-004"}))

    def compose(self, *args, check=True, timeout=300):
        command = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--env-file",
            str(self.env_file),
        ]
        for file in self.compose_files:
            command += ["-f", str(file)]
        command += list(args)
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if check and result.returncode:
            # Docker异常输出可能含环境或DSN，不写入用户日志/证据。
            raise RuntimeError("Docker步骤失败：" + args[0])
        return result

    def probe(self, group):
        result = self.compose(
            "exec",
            "-T",
            "probe",
            "python",
            "/tests/obs/tooling/probe.py",
            group,
            check=False,
            timeout=900,
        )
        parsed = []
        for line in result.stdout.splitlines():
            try:
                record = json.loads(line)
                if (
                    isinstance(record, dict)
                    and {"case", "status", "message", "evidence"} <= record.keys()
                ):
                    parsed.append(record)
            except (ValueError, TypeError):
                pass
        record = (
            parsed[-1]
            if parsed
            else dict(case=group, status="failed", message="探针未产生有效结果", evidence={})
        )
        print(f"[{group}] {record['status']}：{record['message']}", flush=True)
        if record["status"] != "passed":
            print(json.dumps(record["evidence"], ensure_ascii=False), flush=True)
        self.results.append(record)
        return record

    def wait_api(self):
        for _ in range(90):
            result = self.compose(
                "exec",
                "-T",
                "probe",
                "python",
                "-c",
                "import httpx; r=httpx.get('http://api:8000/health/live');"
                " assert r.status_code==200",
                check=False,
                timeout=15,
            )
            if result.returncode == 0:
                return
            time.sleep(1)
        raise RuntimeError("应用未在启动预算内就绪")

    def cleanup(self):
        result = self.compose("down", "--volumes", "--remove-orphans", check=False, timeout=90)
        residual = {}
        for kind, cmd in [
            ("containers", ["docker", "ps", "-aq"]),
            ("volumes", ["docker", "volume", "ls", "-q"]),
            ("networks", ["docker", "network", "ls", "-q"]),
        ]:
            found = subprocess.run(
                cmd + ["--filter", "label=com.docker.compose.project=" + self.project],
                capture_output=True,
                text=True,
                timeout=10,
            )
            residual[kind] = found.stdout.split()
        clean = result.returncode == 0 and not any(residual.values())
        if clean:
            self.lease.close()
            target = self.runtime.resolve()
            if target.parent != (SUITE / "runtime").resolve():
                raise ValueError("清理路径不属于本测试运行")
            shutil.rmtree(target)
        return {"passed": clean, "remaining": residual, "retained": ["脱敏报告", "构建镜像与缓存"]}

    def scan_logs(self, *, final=True):
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (ROOT / "contracts/observability/log_v1.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        # 直接读取已核验容器的stdout/stderr，避开Compose的状态/渲染输出。
        role_logs = []
        for role in ("api", "worker"):
            container = self.compose("ps", "-q", role).stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container):
                raise AssertionError("日志容器身份未能核验")
            result = subprocess.run(
                ["docker", "logs", container],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode:
                raise AssertionError("容器日志读取失败")
            role_logs.extend((result.stdout, result.stderr))
        logs = "\n".join(role_logs)
        sentinels = [
            "OBS_SECRET_SENTINEL",
            "OBS_PROMPT_SENTINEL",
            "OBS_URL_SENTINEL",
            self.env["OBS_TEST_PASSWORD"],
        ]
        assert not any(s in logs for s in sentinels), "日志含敏感哨兵"
        safe = []
        for line in logs.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                # 保存有限形态以定位采集/源端问题，禁止把未清洗原行落盘。
                raise AssertionError(
                    "源端日志非JSON：长度="
                    + str(len(line.encode()))
                    + "，起始类别="
                    + ("object" if line.startswith("{") else "other")
                ) from None
            validator.validate(record)
            assert len(line.encode()) <= 4096
            safe.append(record)
        assert safe, "未收集到JSON应用日志"
        safe = (self._safe_logs + safe)[-2000:]
        self._safe_logs = safe
        if final and any(r["case"] == "trace" and r["status"] == "passed" for r in self.results):
            # A08/OBS4-023：真实四类任务的阶段及结束日志保留适用业务身份。
            identities = {
                "run": lambda r: r["run_id"] and r["thread_id"],
                "index_document": lambda r: (
                    r["document_id"] and r["index_batch_id"] and not r["parse_job_id"]
                ),
                "index_build": lambda r: (
                    r["document_id"] and r["index_batch_id"] and r["parse_job_id"]
                ),
                "retrieval_diagnostic": lambda r: r["retrieval_execution_id"] and not r["run_id"],
            }
            for kind, matches in identities.items():
                for action in ("claim", "stage", "attempt_"):
                    if kind == "index_document" and action == "claim":
                        # 旧索引候选批次在handler中选定；领取时尚不适用。
                        assert any(r["action"] == "claim" and r["document_id"] for r in safe)
                        continue
                    assert any(r["action"].startswith(action) and matches(r) for r in safe), (
                        "任务安全关联字段缺失：" + kind + "/" + action
                    )
        (self.artifacts / "logs.json").write_text(
            json.dumps(safe[-500:], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not final:
            return
        self.results.append(
            dict(
                case="log-schema",
                status="passed",
                message="日志逐行Schema与敏感哨兵核验通过",
                evidence={"lines": len(safe)},
            )
        )

    def run(self):
        cleanup = {}
        try:
            check()
            self.compose("config", "--quiet")
            if not self.skip_build:
                print("[Environment] 构建应用候选镜像", flush=True)
                self.compose("build", "api", timeout=1800)
            self.compose("up", "-d", "--no-build", timeout=300)
            self.wait_api()
            worker = self.compose("ps", "--status", "running", "--services").stdout.splitlines()
            if "worker" not in worker:
                raise RuntimeError("测试Worker未运行")
            self.results.append(
                dict(
                    case="environment",
                    status="passed",
                    message="隔离应用/迁移/捕获器已启动",
                    evidence={},
                )
            )
            groups = (
                ["Http", "Trace", "Metrics", "Recovery", "Security", "Handoff"]
                if self.group == "All"
                else []
                if self.group in {"Environment", "Budget"}
                else [self.group]
            )
            if self.group == "Recovery":
                self.probe("Trace")
            for group in groups:
                self.probe(group)
            if self.group in {"All", "Recovery"}:
                from restart import run_restarts

                self.scan_logs(final=False)
                run_restarts(self)
                self.probe("Sse")
            if self.group != "Environment":
                self.scan_logs()
            if self.group in {"Budget", "All"}:
                self.probe("Quality")
                from budget import run_budget

                run_budget(self)
        except Exception as exc:
            self.results.append(
                dict(
                    case="runner",
                    status="failed",
                    message="编排失败："
                    + type(exc).__name__
                    + ("，" + str(exc)[:300] if type(exc) is AssertionError else ""),
                    evidence={
                        "frames": [
                            {"file": Path(frame.filename).name, "line": frame.lineno}
                            for frame in traceback.extract_tb(exc.__traceback__)
                        ]
                    },
                )
            )
            print("[Runner] 编排失败，正在清理本轮资源", flush=True)
        finally:
            cleanup = self.cleanup()
            self.results.append(
                dict(
                    case="cleanup",
                    status="passed" if cleanup["passed"] else "failed",
                    message="自有资源清理核验",
                    evidence=cleanup,
                )
            )
            report = dict(
                schema_version=1,
                run_id=self.run_id,
                source_ref=source_ref(),
                source_fingerprint=fingerprint(),
                config_hash=hashlib.sha256(
                    (SUITE / "compose/compose.yaml").read_bytes()
                ).hexdigest(),
                contract_hash=hashlib.sha256(
                    (ROOT / "contracts/observability/metrics_v1.json").read_bytes()
                ).hexdigest(),
                results=self.results,
                cleanup=cleanup,
            )
            (self.artifacts / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (self.artifacts / "application.json").write_text(
                json.dumps(capability(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("[Report] " + str(self.artifacts / "report.json"), flush=True)
        return 0 if all(r["status"] == "passed" for r in self.results) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group",
        choices=[
            "Environment",
            "Http",
            "Metrics",
            "Trace",
            "Recovery",
            "Security",
            "Budget",
            "Handoff",
            "All",
        ],
        default="All",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    from recovery import recover_stale

    recover_stale(SUITE)
    raise SystemExit(Runner(args.group, args.run_id, args.skip_build).run())


if __name__ == "__main__":
    main()
