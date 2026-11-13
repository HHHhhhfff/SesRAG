"""ENV_001～010宿主工程验收：只引用本次真实演练证据，不计产品通过率。"""

from helpers.common import SUITE, digest, load, schema_check, write


def record(prefix, runs, frozen):
    specs = [
        r
        for r in load(SUITE / "fixtures/case-catalog.json")["cases"]
        if r["category"] == "environment"
    ]
    root = SUITE / "artifacts" / (prefix + "-environment-cases")
    root.mkdir(exist_ok=False)
    run1, run2 = runs[0], runs[1]
    first_root = SUITE / "artifacts" / run1["run_id"]
    project = next(first_root.glob("sesrag-*/environment.json")).parent
    environment = load(project / "environment.json")
    validation = load(project / "compose-validation.json")
    build = load(SUITE / ".cache/frozen-builds" / frozen / "build.json")
    f1 = load(first_root / "fingerprints.json")
    f2 = load(SUITE / "artifacts" / run2["run_id"] / "fingerprints.json")
    runner = (project / "runner-selftests.log").read_text(encoding="utf8")
    preparation = (project / "preparation-selftests.log").read_text(encoding="utf8")
    cleanup = [
        load(SUITE / "artifacts" / row["run_id"] / "cleanup.json")
        for row in runs
        if "run_id" in row
    ]
    log_ok = "\nOK" in runner and "\nOK" in preparation
    checks = {
        "ENV_001": (
            validation["status"] == "passed" and environment["sse_proxy"] == "observed_data_event",
            "真实独立Compose/同源代理/SSE安全结构校核",
        ),
        "ENV_002": (
            environment["schema_revision"] == "0011_rag_source_integrity"
            and environment["ready"]["worker"] == "ready"
            and bool(environment["pgvector"]),
            "实际迁移/Profile/PG扩展/Worker就绪事实",
        ),
        "ENV_003": (
            environment["lane"] == "local" and log_ok,
            "真实local装配自检/受控传输与安全守卫负例",
        ),
        "ENV_004": (
            log_ok and runs[-1].get("real") == "blocked",
            "real覆盖清除本地装配自测及无授权真实拒绝；没有供应商请求",
        ),
        "ENV_005": (
            log_ok and run1["product"] == "not_run",
            "错身份/漏case/证据hash/planned门禁实际工程负例",
        ),
        "ENV_006": (
            f1["source"] == f2["source"]
            and f1["build_source"] == f2["build_source"] == build["build_source"]
            and run2.get("frozen_build") == frozen,
            "第二轮实际从归档加载且源码/归档hash核验",
        ),
        "ENV_007": (
            log_ok and all(r.get("cleanup") == "passed" for r in runs if "exit_code" in r),
            "坏Schema/路径/hash/泄漏负例与真实采证完整性",
        ),
        "ENV_008": (
            bool(cleanup)
            and all(
                r["status"] == "passed"
                and not any(r["remaining"].values())
                and not any(r.get("unrelated_resources_missing", {}).values())
                for r in cleanup
            ),
            "正常结束独立资源复查：容器/卷/网络/tag/runtime/tmp为空，既有资源未丢失",
        ),
        "ENV_009": (
            all(r["exit_code"] == 2 and r["cleanup"] == "passed" for r in runs[2:5])
            and all(r["status"] == "passed" for r in runs[5:7]),
            "真实Docker启动失败/子进程失败/超时/主进程强停+重复Cleanup；未用模拟函数替代",
        ),
        "ENV_010": (
            all(not r["remaining"].get("runtime_tmp") for r in cleanup) and log_ok,
            "运行时源/凭据/scratch已释放；报告/工具/冻结缓存/原始runtime-inputs保留，软门限自测",
        ),
    }
    cases = []
    for spec in specs:
        identity = spec["case_id"]
        passed, detail = checks[identity]
        evidence = {
            "case_id": identity,
            "scope": "环境工程，产品not_run",
            "结论": detail,
            "passed": passed,
            "本次演练run_ids": [r.get("run_id") for r in runs],
            "frozen_build": frozen,
            "未执行": "真实键盘Ctrl+C未单独注入；主进程强停已实际执行"
            if identity == "ENV_009"
            else "",
            "保留占用_bytes": {
                area: sum(p.stat().st_size for p in (SUITE / area).rglob("*") if p.is_file())
                for area in ("artifacts", ".cache", "runtime-inputs")
                if (SUITE / area).exists()
            },
        }
        proof = root / (identity + ".json")
        write(proof, evidence)
        cases.append(
            {
                **{k: spec[k] for k in ("case_id", "title", "requirements", "test_points")},
                "status": "passed" if passed else "harness_error",
                "duration_ms": 0,
                "error_code": None if passed else "ENGINEERING_EVIDENCE_INCOMPLETE",
                "expected": spec["expected"],
                "actual": detail,
                "phases": ["准备", "执行", "观察", "结论"],
                "evidence": [{"path": proof.name, "sha256": digest(proof.read_bytes())}],
            }
        )
        print(f"[{identity}] {'通过' if passed else '未通过'}：{detail}", flush=True)
    result = {
        "schema_version": 1,
        "run_id": prefix + "-environment-cases",
        "category": "environment",
        "lane": "local",
        "cases": cases,
    }
    schema_check("result", result)
    write(root / "result.json", result)
    if any(r["status"] != "passed" for r in cases):
        raise ValueError("ENV_CASE_AUDIT_FAILED")
