"""显式创建独立Compose项目，任何失败仍收证并销毁；不使用开发.env／旧验收工程。"""

import json
import os
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    project = "sesrag-rag-check-" + secrets.token_hex(5)
    output = ROOT / "data" / "rag-implementation" / project
    output.mkdir(parents=True)
    env = {**os.environ, "RAG_CHECK_PASSWORD": secrets.token_hex(24), "RAG_CHECK_PROJECT": project}
    command = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--file",
        str(ROOT / "tests/integration/compose.rag-v3.yml"),
        "--env-file",
        os.devnull,
    ]

    def run(args, name, *, timeout=300, check=True):
        with (output / name).open("w", encoding="utf-8") as log:
            result = subprocess.run(
                [*command, *args],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        if check and result.returncode:
            raise RuntimeError(f"隔离检查失败：{name}（不输出配置或凭据）")
        return result.returncode

    success = False
    try:
        print(f"创建隔离项目 {project}；证据目录 {output.relative_to(ROOT)}", flush=True)
        run(["up", "-d", "--build", "--wait", "--wait-timeout", "180"], "startup.txt", timeout=900)
        run(
            [
                "exec",
                "-T",
                "api",
                "python",
                "-m",
                "backend.tools.sync_model_profiles",
                "/app/config/models.json",
            ],
            "model-import.txt",
        )
        run(["exec", "-T", "api", "python", "/app/checks/rag_v3_pg_probe.py"], "probe.json")
        success = True
    finally:
        run(["logs", "--no-color", "--tail", "500"], "containers.txt", check=False)
        cleanup = run(
            ["down", "--volumes", "--remove-orphans", "--rmi", "local", "--timeout", "30"],
            "cleanup.txt",
            check=False,
        )
        leftovers = {}
        for kind in ("container", "volume", "network"):
            result = subprocess.run(
                [
                    "docker",
                    kind,
                    "ls",
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                    "--format",
                    "{{.ID}}" if kind == "container" else "{{.Name}}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            leftovers[kind] = (
                result.stdout.splitlines() if result.returncode == 0 else ["check_failed"]
            )
        report = {
            "project": project,
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "probe_passed": success,
            "cleanup_exit": cleanup,
            "remaining": leftovers,
        }
        images = subprocess.run(
            [
                "docker",
                "image",
                "ls",
                "--filter",
                f"reference={project}-*",
                "--format",
                "{{.Repository}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        leftovers["images"] = (
            images.stdout.splitlines() if images.returncode == 0 else ["check_failed"]
        )
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if cleanup or any(leftovers.values()):
            raise RuntimeError("隔离资源清理未通过，见本次summary；未执行全局prune")
        print("隔离容器、卷、网络和本次应用镜像已销毁；共享基础镜像及构建缓存保留。", flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
