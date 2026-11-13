"""唯一生命周期入口：预检→隔离部署→接入/采证→所有权清理→真实摘要。"""

import argparse
import importlib.util
import json
import os
import secrets
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import cleanup as cleanup_module
from helpers.builds import freeze, images
from helpers.common import (
    ROOT,
    SUITE,
    command,
    digest,
    engine_identity,
    load,
    process_token,
    run_path,
    schema_check,
    write,
)
from helpers.evidence import index, redact, save_log, scan
from helpers.preflight import check_tools, real_gate, source_fingerprint
from helpers.prepare_runtime import prepare
from helpers.protocol import LOCAL, REAL, manifest, validate_result
from helpers.resource_observation import ResourceSampler, performance_summary


def compose_args(project, directory, lane):
    result = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--project-directory",
        str(ROOT),
        "--env-file",
        str(directory / "compose.env"),
        "--file",
        str(SUITE / "compose/docker-compose.rag-test.yml"),
    ]
    if lane == "real":
        result.extend(["--file", str(SUITE / "compose/docker-compose.rag-real.yml")])
    else:
        result.extend(["--profile", "local"])
    return result


def inspect_config(config, lane, project):
    services = config["services"]
    for name, row in services.items():
        if row.get("container_name") or any(
            port.get("host_ip") != "127.0.0.1" for port in row.get("ports", [])
        ):
            raise ValueError("COMPOSE_ISOLATION_INVALID")
        if name != "frontend" and row.get("ports"):
            raise ValueError("UNEXPECTED_PUBLISHED_PORT")
        if row.get("labels", {}).get("sesrag.test.suite") != "rag-mineru-003":
            raise ValueError("COMPOSE_LABEL_MISSING")
        for mount in row.get("volumes", []):
            source = str(mount.get("source", ""))
            if "docker.sock" in source or "docs/secret" in source.replace("\\", "/"):
                raise ValueError("COMPOSE_PRIVATE_MOUNT")
    if lane == "real":
        for name, row in services.items():
            if name == "scenario-control":
                if row.get("profiles") != ["local"]:
                    raise ValueError("REAL_CONTROL_ACTIVE")
                continue
            serialized = json.dumps(row)
            if any(
                word in serialized
                for word in (
                    "/suite/harness",
                    "harness.local_entry",
                    "dummy-",
                    "TEST_CONTROL_TOKEN",
                    "scenario-control",
                )
            ):
                raise ValueError("REAL_LOCAL_BINDING_REMAINS")
        if services["api"]["command"][:2] != ["uvicorn", "backend.app:app"] or services["worker"][
            "command"
        ] != ["python", "-m", "backend.workers.main"]:
            raise ValueError("REAL_ENTRYPOINT_INVALID")
        for name in ("tools", "migrate", "profile-init"):
            if any(
                k.endswith("API_KEY") or k == "MINERU_STATE_ENCRYPTION_KEY"
                for k in services[name].get("environment", {})
            ):
                raise ValueError("REAL_SECRET_IN_UNNECESSARY_SERVICE")
    return {
        "status": "passed",
        "lane": lane,
        "project": project,
        "services": sorted(services),
        "private_config_saved": True,
        "local_transport": lane == "local",
    }


def capture_project(command_prefix, output, secrets_list):
    problems = []
    for service in (
        "postgres",
        "redis",
        "migrate",
        "profile-init",
        "api",
        "worker",
        "frontend",
        "tools",
        "scenario-control",
    ):
        code, raw = command(
            [*command_prefix, "logs", "--no-color", "--tail", "500", service],
            check=False,
            timeout=30,
        )
        save_log(output / f"logs-{service}.txt", raw, secrets_list)
        if code:
            problems.append(service)
    # 安全投影容器状态，不输出完整inspect环境。
    code, raw = command([*command_prefix, "ps", "--all", "--format", "json"], check=False)
    save_log(output / "compose-ps.jsonl", raw, secrets_list)
    return problems + (["compose-ps"] if code else [])


def technical_probe(prefix, output):
    code, raw = command(
        [*prefix, "exec", "-T", "tools", "python", "-m", "helpers.environment_probe"],
        check=False,
        timeout=180,
    )
    save_log(output / "environment-probe.log", raw)
    if code:
        raise ValueError("ENVIRONMENT_PROBE_FAILED")
    environment = load(output / "environment.json")
    if environment["status"] != "passed" or environment["product"] != "not_run":
        raise ValueError("ENVIRONMENT_RESULT_INVALID")
    return environment


def execute_category(prefix, output, row, context):
    write(output / "context.json", context)
    extension = row["entrypoint"].rsplit(".", 1)[-1]
    interpreter = "node" if extension == "mjs" else "python"
    args = [
        *prefix,
        "exec",
        "-T",
        "tools",
        interpreter,
        "/suite/" + row["entrypoint"],
        "--context",
        f"/reports/{row['category']}/context.json",
        "--result",
        f"/reports/{row['category']}/result.json",
    ]
    code, raw = command(args, check=False, timeout=row["timeout_seconds"])
    save_log(output / "category.log", raw)
    if not (output / "result.json").exists():
        raise ValueError("CATEGORY_EXIT_WITHOUT_REPORT")
    result = load(output / "result.json")
    statuses = validate_result(result, context, row, output)
    if code == 0 and any(state != "passed" for state in statuses):
        raise ValueError("CATEGORY_EXIT_RESULT_CONTRADICTION")
    if code and all(state == "passed" for state in statuses):
        raise ValueError("CATEGORY_FAILED_WITH_PASSED_REPORT")
    return {
        "category": row["category"],
        "status": "passed"
        if all(s == "passed" for s in statuses)
        else "harness_error"
        if "harness_error" in statuses
        else "failed"
        if "failed" in statuses
        else "blocked",
        "case_count": len(statuses),
    }


def summarize(root, report, secrets_list):
    scan(root, secrets_list)
    write(root / "summary.json", report)
    text = f"# TEST-003运行结果：{report['run_id']}\n\n"
    text += (
        f"模式：{report['mode']}；退出码：{report['exit_code']}。"
        f"环境：{report['environment']}；产品：{report['product']}；清理：{report['cleanup']}。\n\n"
    )
    text += "本结果只证明请求范围；Environment不计产品通过，Mock不证明真实效果。\n\n"
    if "real_capabilities" in report:
        text += "真实能力范围：" + ", ".join(report["real_capabilities"]) + "。"
        text += (
            "四能力范围。"
            if report["full_business_scope"]
            else "部分能力范围，不能认定完整真实业务闭环通过。"
        ) + "\n\n"
    for error in report["reasons"]:
        text += f"- {error}\n"
    text += "\n缓存/冻结镜像归档/脱敏报告有意保留；本机清理不保证云端撤回或停止计费。\n"
    (root / "summary.md").write_text(text, encoding="utf-8")
    index(root)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["Environment", "Selected", "All", "Real", "Cleanup"],
        default="Environment",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--categories", nargs="+", default=[])
    parser.add_argument("--hold-seconds", type=int, default=0)
    parser.add_argument("--startup-timeout-seconds", type=int, default=300)
    parser.add_argument("--frozen-build")
    parser.add_argument("--real-plan", choices=["Business", "Acceptance"], default="Business")
    parser.add_argument("--allow-real-requests", action="store_true")
    parser.add_argument("--live-plan")
    parser.add_argument(
        "--engineering-fault",
        choices=["startup", "child-failure", "child-timeout"],
        help="仅Environment工程演练，不是产品用例或正常运行选项",
    )
    args = parser.parse_args(argv)
    if args.engineering_fault and args.mode != "Environment":
        parser.error("工程故障注入仅供Environment")
    if not 0 <= args.hold_seconds <= 300 or not 1 <= args.startup_timeout_seconds <= 300:
        parser.error("时间参数超界")
    if (
        args.categories
        and args.mode not in {"Selected", "Real"}
        or args.mode == "Selected"
        and not args.categories
    ):
        parser.error("Categories仅供Selected/Real；Selected必须明确")
    if args.mode == "Real" and (set(args.categories) - set(REAL)):
        parser.error("Real仅接受真实分类")
    if args.mode != "Real" and (args.allow_real_requests or args.live_plan):
        parser.error("真实参数仅供Real")
    if args.mode == "Cleanup":
        if not args.run_id:
            parser.error("Cleanup必须指定RunId")
        path = run_path("artifacts", args.run_id) / "recovery-ledger.json"
        if not path.is_file():
            parser.error("缺少可信账本，禁止猜删")
        result = cleanup_module.cleanup(path)
        root = path.parent
        existing = root / "summary.json"
        report = (
            load(existing)
            if existing.exists()
            else {
                "schema_version": 1,
                "run_id": args.run_id,
                "mode": "Cleanup",
                "environment": "not_run",
                "product": "not_run",
                "real": "not_run",
                "effects": "not_run",
                "performance": "not_run",
                "categories": [],
                "reasons": ["原主进程中断，已按账本恢复；不补造产品或环境通过结论"],
            }
        )
        report["cleanup"] = result["status"]
        report["recovery_cleanup_exit"] = 0 if result["status"] == "passed" else 4
        report.setdefault("exit_code", 2)
        summarize(root, report, [])
        print(f"[{args.run_id}] 恢复清理：{result['status']}", flush=True)
        return 0 if result["status"] == "passed" else 4
    identity = args.run_id or "rag-" + datetime.now(timezone.utc).strftime(
        "%Y%m%d-%H%M%S-"
    ) + secrets.token_hex(4)
    used = sum(p.stat().st_size for p in (SUITE / "artifacts").rglob("*") if p.is_file())
    if used > 2 * 1024**3:
        parser.error("artifacts超过2GiB软门限，请按run_id明确归档后再运行")
    try:
        root = run_path("artifacts", identity)
    except ValueError:
        parser.error("RunId格式无效")
    if (
        root.exists()
        or run_path("runtime", identity).exists()
        or run_path("tmp", identity).exists()
    ):
        parser.error("RunId已存在，请为新运行使用新ID；恢复资源请选择Cleanup")
    root.mkdir(parents=True, exist_ok=False)
    runtime = run_path("runtime", identity)
    scratch = run_path("tmp", identity)
    runtime.mkdir(parents=True, exist_ok=False)
    scratch.mkdir(parents=True, exist_ok=False)
    from helpers import common

    common.COMMAND_SCRATCH = scratch
    common.PROCESS_LEDGER = root / "host-processes.json"
    owner = secrets.token_hex(16)
    ledger_path = root / "recovery-ledger.json"
    ledger = {
        "schema_version": 1,
        "run_id": identity,
        "owner": owner,
        "engine": None,
        "projects": [],
        "images": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "orchestrator": {"pid": os.getpid(), "created": process_token(os.getpid())},
    }
    write(ledger_path, ledger)
    report = {
        "schema_version": 1,
        "run_id": identity,
        "mode": args.mode,
        "environment": "not_run",
        "product": "not_run",
        "real": "not_run",
        "effects": "not_run",
        "performance": "not_run",
        "cleanup": "not_run",
        "exit_code": 0,
        "reasons": [],
        "categories": [],
        "requested_categories": [],
    }
    secrets_list = []
    codes = set()
    prefixes = []
    fingerprints = None
    print(f"[{identity}] 开始{args.mode}，报告：artifacts/{identity}", flush=True)
    try:
        preflight = check_tools()
        ledger["engine"] = engine_identity()
        ledger["existing_resources"] = cleanup_module.existing_resources()
        write(ledger_path, ledger)
        preflight["engine_identity"] = ledger["engine"]
        write(root / "preflight.json", preflight)
        entries = manifest()
        requested = (
            args.categories
            if args.mode in {"Selected", "Real"} and args.categories
            else LOCAL
            if args.mode == "All"
            else REAL
            if args.mode == "Real" and args.real_plan == "Acceptance"
            else ["real-business"]
            if args.mode == "Real"
            else ["environment"]
        )
        if len(requested) != len(set(requested)) or set(requested) - set(entries) - {"environment"}:
            raise ValueError("INVALID_CATEGORY_SELECTION")
        report["requested_categories"] = [c for c in requested if c != "environment"]
        # planned分类不能运行；先说明真实执行范围，避免无脚本时读取无必要Secret。
        planned = [
            category
            for category in requested
            if category != "environment" and entries[category]["status"] != "ready"
        ]
        if planned:
            codes.add(3)
            report["reasons"].append("分类尚未ready，不执行或冒报通过：" + ",".join(planned))
            report["categories"].extend(
                {"category": c, "status": "not_run", "reason": "planned"} for c in planned
            )
        runnable = [c for c in requested if c not in planned]
        if not runnable:
            return finish(report, codes, ledger, ledger_path, root, secrets_list, fingerprints)
        gate = None
        if args.mode == "Real":
            if not args.allow_real_requests or not args.live_plan:
                codes.add(3)
                report["reasons"].append(
                    "REAL_REQUESTS_NOT_AUTHORIZED：必须显式开关及私有LivePlan，本轮无外发"
                )
                report["real"] = "blocked"
                return finish(report, codes, ledger, ledger_path, root, secrets_list, fingerprints)
            gate = real_gate(args.live_plan, args.real_plan)
            report["real_capabilities"] = gate["capabilities"]
            report["full_business_scope"] = gate["full_business_scope"]
            write(
                root / "real-gate.json",
                {
                    k: v
                    for k, v in gate.items()
                    if k not in {"secrets", "config_paths", "approved_files"}
                },
            )
            if not gate["passed"]:
                codes.add(3)
                report["real"] = "blocked"
                report["reasons"].extend(gate["reasons"])
                return finish(report, codes, ledger, ledger_path, root, secrets_list, fingerprints)
        fingerprints = source_fingerprint()
        write(root / "fingerprints.json", fingerprints)
        # 固定输入校验和复制完成后才部署，危险数据仅local目录。
        spec = importlib.util.spec_from_file_location(
            "fixture_materialize", SUITE / "fixtures/materialize.py"
        )
        materializer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(materializer)
        materialized = materializer.materialize(ROOT, scratch / "inputs")
        write(
            root / "fixtures.json",
            {"count": len(materialized["source_files"]), "manifest_hash": digest(materialized)},
        )
        tags = images(ledger, ledger_path, fingerprints, args.frozen_build)
        if args.mode == "All":
            report["frozen_build"] = freeze(ledger, fingerprints, tags)
        lane = "real" if args.mode == "Real" else "local"
        shared_real = None
        for category in runnable:
            project = shared_real or "sesrag-" + identity + "-" + category[:16]
            if lane == "real":
                shared_real = project
            output = root / project
            output.mkdir(exist_ok=True)
            if not any(p["name"] == project for p in ledger["projects"]):
                # 意图写入先于任何Engine副作用，硬杀恢复可按完整标签发现ID。
                ledger["projects"].append(
                    {"name": project, "category": category, "lane": lane, "resources": []}
                )
                write(ledger_path, ledger)
                directory, values = prepare(identity, project, lane, tags, owner, gate)
                secrets_list.extend(
                    v
                    for k, v in values.items()
                    if k.endswith("KEY") or k in {"TEST_PASSWORD", "TEST_CONTROL_TOKEN"}
                )
                prefix = compose_args(project, directory, lane)
                if args.engineering_fault == "startup":
                    # 本轮私有覆盖让真实API容器退出，验证真实Docker启动失败后的回收。
                    override = directory / "startup-fault.yml"
                    override.write_text(
                        'services:\n  api:\n    command: [python, -c, "raise SystemExit(73)"]\n',
                        encoding="utf-8",
                    )
                    prefix.extend(["--file", str(override)])
                prefixes.append((prefix, output))
                private_config = command([*prefix, "config", "--format", "json"])[1]
                (directory / "effective-compose.json").write_text(private_config, encoding="utf-8")
                write(
                    output / "compose-validation.json",
                    inspect_config(json.loads(private_config), lane, project),
                )
                print(f"[{identity}] 启动隔离分类 {category}", flush=True)
                workers = 1 if category == "environment" else entries[category]["workers"]
                args_up = [
                    *prefix,
                    "up",
                    "-d",
                    "--wait",
                    "--wait-timeout",
                    str(args.startup_timeout_seconds),
                    "--scale",
                    f"worker={workers}",
                ]
                code, raw = command(args_up, check=False, timeout=args.startup_timeout_seconds + 45)
                save_log(output / "startup.log", raw, secrets_list)
                if code:
                    raise ValueError("COMPOSE_STARTUP_FAILED")
                # 保存真实资源ID的安全投影，不输出环境。
                for kind in ("container", "network", "volume"):
                    for resource in cleanup_module.discover(kind, ledger):
                        actual = cleanup_module.validate_resource(kind, resource, ledger)
                        ledger["projects"][-1]["resources"].append({"kind": kind, "id": actual})
                write(ledger_path, ledger)
                if lane == "local":
                    technical_probe(prefix, output)
                    code, raw = command(
                        [*prefix, "exec", "-T", "tools", "python", "-m", "helpers.selftest_runner"],
                        check=False,
                        timeout=120,
                    )
                    save_log(output / "runner-selftests.log", raw, secrets_list)
                    if code:
                        raise ValueError("RUNNER_SELFTEST_FAILED")
                    code, raw = command(
                        [
                            *prefix,
                            "exec",
                            "-T",
                            "tools",
                            "python",
                            "-m",
                            "helpers.selftest_preparation",
                        ],
                        check=False,
                        timeout=120,
                    )
                    save_log(output / "preparation-selftests.log", raw, secrets_list)
                    if code:
                        raise ValueError("PREPARATION_SELFTEST_FAILED")
                    code, raw = command(
                        [
                            *prefix,
                            "exec",
                            "-T",
                            "tools",
                            "python",
                            "-m",
                            "helpers.selftest_engineering",
                        ],
                        check=False,
                        timeout=120,
                    )
                    save_log(output / "engineering-selftests.log", raw, secrets_list)
                    if code:
                        raise ValueError("ENGINEERING_SELFTEST_FAILED")
                port = command([*prefix, "port", "frontend", "5173"])[1].strip()
                frontend_ip = command(
                    [
                        *prefix,
                        "exec",
                        "-T",
                        "tools",
                        "python",
                        "-c",
                        "import socket; print(socket.gethostbyname('frontend'))",
                    ]
                )[1].strip()
                internal_origin = "http://" + frontend_ip + ":5173"
                write(
                    output / "addresses.json",
                    {"frontend": "http://" + port, "internal_origin": internal_origin},
                )
                report["environment"] = "passed"
                if args.engineering_fault in {"child-failure", "child-timeout"}:
                    code, _ = command(
                        [
                            *prefix,
                            "exec",
                            "-T",
                            "tools",
                            "python",
                            "-c",
                            "raise SystemExit(73)"
                            if args.engineering_fault == "child-failure"
                            else "import time; time.sleep(30)",
                        ],
                        timeout=1 if args.engineering_fault == "child-timeout" else 30,
                        check=False,
                    )
                    if code:
                        raise ValueError("ENGINEERING_CHILD_FAILURE_OBSERVED")
            if category != "environment":
                category_output = output / category
                category_output.mkdir(exist_ok=True)
                context = {
                    "schema_version": 1,
                    "run_id": identity,
                    "category": category,
                    "lane": lane,
                    "fingerprints": {
                        k: fingerprints[k] for k in ("source", "build_source", "head")
                    },
                    "addresses": {
                        "api": internal_origin,
                        "control": "http://scenario-control:8081",
                    }
                    if lane == "local"
                    else {"api": internal_origin},
                    "resources": {
                        "project": project,
                        "private_tools": "/run/secrets/tools-private.json",
                    },
                    "report_dir": f"/reports/{category}",
                    "budget": gate["budget"]
                    if gate
                    else {"timeout_seconds": entries[category]["timeout_seconds"]},
                    "allowed_operations": ["api", "owned-fixtures", "owned-container-faults"],
                }
                if gate:
                    context["real_capabilities"] = gate["capabilities"]
                schema_check("context", context)
                owned = next(p for p in ledger["projects"] if p["name"] == project)
                owned_ids = [r["id"] for r in owned["resources"] if r["kind"] == "container"]
                sampler = ResourceSampler(owned_ids).start()
                try:
                    result = execute_category(prefix, category_output, entries[category], context)
                    report["categories"].append(result)
                finally:
                    observed = sampler.stop()
                    write(category_output / "resource-samples.json", observed)
                    report.setdefault("resource_observations", []).append(
                        {
                            "category": category,
                            "lane": lane,
                            "path": str(
                                (category_output / "resource-samples.json").relative_to(root)
                            ),
                            **{k: v for k, v in observed.items() if k != "samples_raw"},
                        }
                    )
                codes.update(
                    {"failed": {1}, "blocked": {3}, "harness_error": {2}}.get(
                        result["status"], set()
                    )
                )
            for _ in range(args.hold_seconds):
                time.sleep(1)
            missing = capture_project(prefix, output, secrets_list)
            if missing:
                raise ValueError("LOG_COLLECTION_INCOMPLETE")
            if lane == "local":
                code, raw = command(
                    [*prefix, "down", "--volumes", "--remove-orphans", "--timeout", "25"],
                    check=False,
                    timeout=100,
                )
                save_log(output / "down.log", raw, secrets_list)
                if code:
                    raise ValueError("CATEGORY_DOWN_FAILED")
        if args.mode in {"All", "Selected"} and not codes:
            report["product"] = "passed"
        elif args.mode == "Real" and not codes:
            report["real"] = "passed" if gate["full_business_scope"] else "partial_passed"
        if source_fingerprint()["source"] != fingerprints["source"]:
            raise ValueError("SOURCE_CHANGED_DURING_RUN")
        if args.mode == "Environment":
            report["frozen_build"] = freeze(ledger, fingerprints, tags)
    except KeyboardInterrupt:
        codes.add(2)
        report["reasons"].append("运行中断；已进入资源回收")
    except Exception as exc:
        codes.add(2)
        report["reasons"].append(redact(str(exc), secrets_list)[:300])
        if report["environment"] == "not_run":
            report["environment"] = "failed"
        for prefix, output in prefixes:
            try:
                capture_project(prefix, output, secrets_list)
            except Exception:
                report["reasons"].append("异常分支采证不完整")
    return finish(report, codes, ledger, ledger_path, root, secrets_list, fingerprints)


def finish(report, codes, ledger, ledger_path, root, secrets_list, fingerprints):
    report["performance"] = performance_summary(
        report["categories"], report.get("resource_observations", [])
    )
    recorded = {r["category"] for r in report["categories"]}
    report["categories"].extend(
        {"category": category, "status": "not_run", "reason": "前置/工程未完成"}
        for category in report.get("requested_categories", [])
        if category not in recorded
    )
    cleanup = cleanup_module.cleanup(ledger_path)
    report["cleanup"] = cleanup["status"]
    if cleanup["status"] != "passed":
        codes.add(4)
        report["reasons"].append("清理未通过或Engine无法核验，使用相同RunId执行Cleanup")
    report["exit_code"] = next((c for c in (4, 2, 1, 3) if c in codes), 0)
    if any(row["status"] == "failed" for row in report["categories"]):
        report["product"] = "failed"
        if report["mode"] == "Real":
            report["real"] = "failed"
    elif any(row["status"] in {"blocked", "not_run"} for row in report["categories"]):
        report["product"] = "not_run"
        if report["mode"] == "Real":
            report["real"] = "blocked"
    try:
        summarize(root, report, secrets_list)
    except Exception:
        report["exit_code"] = 4 if 4 in codes else 2
        report["reasons"].append("证据泄漏或索引检查未通过；禁止认定运行通过")
        write(root / "summary.json", report)
    print(
        f"[{report['run_id']}] 环境={report['environment']}，产品={report['product']}，"
        f"清理={report['cleanup']}，退出={report['exit_code']}",
        flush=True,
    )
    return report["exit_code"]


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
