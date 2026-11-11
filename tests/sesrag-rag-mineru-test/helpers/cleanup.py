"""按Engine、完整标签和资源ID回收；禁止全局prune或按名称前缀猜删。"""

import json
import os
import re
import shutil
import signal
import subprocess
import time

from helpers.common import (
    LABEL,
    SUITE_NAME,
    command,
    engine_identity,
    load,
    process_token,
    run_path,
    write,
)


def discover(kind, ledger):
    args = ["docker", kind, "ls"]
    if kind == "container":
        args.append("-a")
    for label, value in (
        (LABEL, SUITE_NAME),
        ("sesrag.test.run", ledger["run_id"]),
        ("sesrag.test.owner", ledger["owner"]),
    ):
        args.extend(["--filter", f"label={label}={value}"])
    args.extend(["--format", "{{.ID}}" if kind == "container" else "{{.Name}}"])
    return command(args)[1].splitlines()


def existing_resources():
    result = {}
    for kind in ("container", "network", "volume"):
        args = ["docker", kind, "ls"] + (["-a"] if kind == "container" else [])
        result[kind] = command(
            [*args, "--format", "{{.ID}}" if kind == "container" else "{{.Name}}"]
        )[1].splitlines()
    return result


def validate_resource(kind, identity, ledger):
    raw = command(["docker", kind, "inspect", identity])[1]
    rows = json.loads(raw)
    info = rows[0]
    labels = (
        info.get("Config", {}).get("Labels", {}) if kind == "container" else info.get("Labels", {})
    )
    projects = {p["name"] for p in ledger["projects"]}
    if (
        any(
            labels.get(k) != v
            for k, v in {
                LABEL: SUITE_NAME,
                "sesrag.test.run": ledger["run_id"],
                "sesrag.test.owner": ledger["owner"],
            }.items()
        )
        or labels.get("com.docker.compose.project") not in projects
    ):
        raise ValueError("RESOURCE_OWNERSHIP_MISMATCH")
    return info.get("Id", info.get("ID", info.get("Name")))


def erase_run_directory(area, run_id):
    target = run_path(area, run_id)
    if not target.exists():
        return
    if target.is_symlink() or any(p.is_symlink() for p in target.rglob("*")):
        raise ValueError("CLEANUP_SYMLINK_REJECTED")
    # run_path已将绝对路径限制在当前suite/area/run_id内；不接收任意宿主路径。
    shutil.rmtree(target)


def cleanup(ledger_path):
    ledger = load(ledger_path)
    run_id = ledger["run_id"]
    root = run_path("artifacts", run_id)
    report = {
        "status": "failed",
        "run_id": run_id,
        "removed": [],
        "remaining": {},
        "errors": [],
        "retained": ["脱敏报告", "明确依赖/浏览器构建缓存", "冻结镜像归档", "操作者runtime-inputs"],
        "remote_cleanup": "本机清理不保证远端停止或计费撤销",
    }
    deadline = time.monotonic() + 180
    try:
        original = ledger.get("orchestrator")
        if (
            original
            and original["pid"] != os.getpid()
            and process_token(original["pid"]) == original["created"]
        ):
            raise ValueError("ORIGINAL_RUN_STILL_ACTIVE")
        processes_path = root / "host-processes.json"
        for row in load(processes_path) if processes_path.exists() else []:
            if process_token(row["pid"]) == row["created"]:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(row["pid"]), "/T", "/F"],
                        capture_output=True,
                        timeout=15,
                        check=True,
                    )
                else:
                    os.killpg(row["pid"], signal.SIGKILL)
        write(processes_path, [])
        current_engine = engine_identity()
        if ledger["engine"] is None and not ledger["projects"] and not ledger["images"]:
            # 在任何Engine副作用意图前失败，可在Engine恢复后确认从未部署。
            ledger["engine"] = current_engine
            write(ledger_path, ledger)
        if current_engine != ledger["engine"]:
            raise ValueError("CLEANUP_ENGINE_MISMATCH")
        # 容器先于网络/卷删除；每一个候选先inspect核实完整标签。
        for kind in ("container", "network", "volume"):
            for identity in discover(kind, ledger):
                if time.monotonic() > deadline:
                    raise TimeoutError("CLEANUP_DEADLINE")
                actual = validate_resource(kind, identity, ledger)
                args = ["docker", kind, "rm"]
                if kind == "container":
                    args.extend(["--force", "--volumes"])
                args.append(identity)
                command(args, timeout=35)
                report["removed"].append({"kind": kind, "id": actual})
        # 镜像按账本的本轮专有tag删除，不按共享ID强制删除。
        imports = ledger.get("temporary_import_tags", [])
        for row in [*reversed(ledger["images"]), *imports]:
            tag = row["tag"]
            temporary = row in imports
            if temporary:
                valid = (
                    row.get("absent_before_load") is True
                    and row.get("id")
                    and re.fullmatch(
                        r"sesrag-rag-test:rag-[a-z0-9-]{8,80}-(app|frontend|tools)", tag
                    )
                )
            else:
                valid = tag.startswith(f"sesrag-rag-test:{run_id}-")
            if not valid:
                raise ValueError("IMAGE_TAG_OWNERSHIP_MISMATCH")
            code, raw = command(["docker", "image", "inspect", tag], check=False)
            if code:
                continue
            image_info = json.loads(raw)[0]
            actual = image_info["Id"]
            if row.get("id") and row["id"] != actual:
                raise ValueError("IMAGE_ID_CHANGED")
            if (
                not row.get("id")
                and image_info.get("Config", {}).get("Labels", {}).get("sesrag.test.owner")
                != ledger["owner"]
            ):
                raise ValueError("UNREGISTERED_IMAGE_OWNER")
            command(["docker", "image", "rm", tag], timeout=45)
        for kind in ("container", "network", "volume"):
            report["remaining"][kind] = discover(kind, ledger)
        report["remaining"]["image_tags"] = command(
            [
                "docker",
                "image",
                "ls",
                "--filter",
                f"reference=sesrag-rag-test:{run_id}-*",
                "--format",
                "{{.Repository}}:{{.Tag}}",
            ]
        )[1].splitlines()
        report["remaining"]["temporary_import_tags"] = [
            row["tag"]
            for row in imports
            if command(["docker", "image", "inspect", row["tag"]], check=False)[0] == 0
        ]
        if any(report["remaining"].values()):
            raise ValueError("CLEANUP_REMAINS")
        if ledger.get("existing_resources"):
            after = existing_resources()
            report["unrelated_resources_missing"] = {
                kind: sorted(set(values) - set(after[kind]))
                for kind, values in ledger["existing_resources"].items()
            }
            if any(report["unrelated_resources_missing"].values()):
                raise ValueError("EXISTING_RESOURCES_CHANGED_REQUIRES_REVIEW")
        erase_run_directory("tmp", run_id)
        erase_run_directory("runtime", run_id)
        report["remaining"]["runtime_tmp"] = [
            area for area in ("runtime", "tmp") if run_path(area, run_id).exists()
        ]
        if report["remaining"]["runtime_tmp"]:
            raise ValueError("PRIVATE_DIRECTORY_REMAINS")
        report["status"] = "passed"
    except Exception as exc:
        report["errors"].append(
            str(exc) if isinstance(exc, (ValueError, TimeoutError)) else type(exc).__name__
        )
    write(root / "cleanup.json", report)
    return report
