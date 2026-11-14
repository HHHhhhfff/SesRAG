"""A14：只读Git归档基线，B/C相同依赖和资源，保留三对全部结果。"""

import io
import json
import shutil
import subprocess
import tarfile
import threading
import time

BASE_REF = "1779e968332285bd524275270838bdec2b845d66"


def build_baseline(runner):
    directory = runner.runtime / "baseline"
    directory.mkdir()
    archive = subprocess.run(
        ["git", "archive", BASE_REF, "backend", "migrations", "alembic.ini", "pyproject.toml"],
        cwd=runner.runtime.parents[3],
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(directory, filter="data")
    (directory / "Dockerfile").write_text("""FROM sesrag-obs-candidate:local
RUN rm -rf /app/backend /app/migrations
COPY backend /app/backend
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
""")
    result = subprocess.run(
        ["docker", "build", "-t", "sesrag-obs-baseline:local", str(directory)],
        capture_output=True,
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError("基线镜像构建失败")
    return directory


def read_stats(runner):
    values = {"observed_at": time.monotonic()}
    for role in ("api", "worker"):
        result = runner.compose(
            "exec",
            "-T",
            role,
            "python",
            "-c",
            "import json; print(json.dumps({'cpu':open('/sys/fs/cgroup/cpu.stat').read(),"
            "'memory':int(open('/sys/fs/cgroup/memory.current').read()),"
            "'rss':open('/proc/1/status').read()}))",
        )
        raw = json.loads(result.stdout)
        cpu = (
            int(
                next(
                    line.split()[1]
                    for line in raw["cpu"].splitlines()
                    if line.startswith("usage_usec")
                )
            )
            / 1e6
        )
        rss = (
            int(
                next(
                    line.split()[1] for line in raw["rss"].splitlines() if line.startswith("VmRSS:")
                )
            )
            * 1024
        )
        values[role] = dict(cpu_seconds=cpu, memory_bytes=raw["memory"], rss_bytes=rss)
    return values


def run_budget(parent):
    from runner import Runner

    baseline_dir = build_baseline(parent)
    pairs = []
    for pair_index in range(3):
        pair = {}
        order = ("B", "C") if pair_index % 2 == 0 else ("C", "B")
        for label in order:
            runner = Runner(
                "Environment", f"{parent.run_id}-p{pair_index + 1}-{label}", skip_build=True
            )
            runner.env["OBS_TEST_IMAGE"] = (
                "sesrag-obs-baseline:local" if label == "B" else "sesrag-obs-candidate:local"
            )
            print(f"[Budget] 第{pair_index + 1}/3对 {label}：暖机60秒、采样300秒", flush=True)
            samples = []
            try:
                runner.compose("up", "-d", "--no-build")
                runner.wait_api()
                runner.compose(
                    "exec",
                    "-T",
                    "probe",
                    "python",
                    "/tests/obs/specific_test_script/test_budget.py",
                    "--warmup",
                    timeout=90,
                )
                stop = threading.Event()

                def sample(stop=stop, samples=samples, runner=runner):
                    due = time.monotonic()
                    while not stop.is_set():
                        try:
                            samples.append(read_stats(runner))
                        except Exception:
                            pass
                        due += 1
                        stop.wait(max(0, due - time.monotonic()))

                thread = threading.Thread(target=sample, daemon=True)
                thread.start()
                result = runner.compose(
                    "exec",
                    "-T",
                    "probe",
                    "python",
                    "/tests/obs/specific_test_script/test_budget.py",
                    timeout=360,
                )
                stop.set()
                thread.join(10)
                load = json.loads(result.stdout.strip().splitlines()[-1])
                assert len(samples) >= 240, "资源采样不完整"
                resources = {
                    role: dict(
                        cpu_cores=(
                            samples[-1][role]["cpu_seconds"] - samples[0][role]["cpu_seconds"]
                        )
                        / (samples[-1]["observed_at"] - samples[0]["observed_at"]),
                        rss_bytes=max(s[role]["rss_bytes"] for s in samples),
                        cgroup_memory_bytes=max(s[role]["memory_bytes"] for s in samples),
                    )
                    for role in ("api", "worker")
                }
                pair[label] = dict(load=load, resources=resources, samples=samples)
            finally:
                if "stop" in locals():
                    stop.set()
                if "thread" in locals():
                    thread.join(10)
                cleanup = runner.cleanup()
                assert cleanup["passed"], "预算测试资源残留"
        b, c = pair["B"], pair["C"]
        checks = {
            "http_p95": c["load"]["http_p95_seconds"]
            <= b["load"]["http_p95_seconds"] + max(0.005, 0.1 * b["load"]["http_p95_seconds"]),
            "task_p95": c["load"]["task_p95_seconds"]
            <= b["load"]["task_p95_seconds"] + max(0.02, 0.1 * b["load"]["task_p95_seconds"]),
            "throughput": c["load"]["throughput"] >= 0.95 * b["load"]["throughput"],
        }
        for role, limit in [("api", 0.10), ("worker", 0.15)]:
            checks[role + "_rss"] = (
                c["resources"][role]["rss_bytes"] - b["resources"][role]["rss_bytes"]
                <= 96 * 1024**2
            )
            checks[role + "_cpu"] = (
                c["resources"][role]["cpu_cores"] - b["resources"][role]["cpu_cores"] <= limit
            )
        pair["checks"] = checks
        pairs.append(pair)
        (parent.artifacts / "budget.json").write_text(json.dumps(pairs, indent=2), encoding="utf-8")
        print(
            f"[Budget] 第{pair_index + 1}/3对：" + ("passed" if all(checks.values()) else "failed"),
            flush=True,
        )
    parent.results.append(
        dict(
            case="budget",
            status="passed" if all(all(p["checks"].values()) for p in pairs) else "failed",
            message="三对同条件开销门槛核验",
            evidence={"pairs": 3, "artifact": "budget.json"},
        )
    )
    # baseline归档属于本任务创建的已校验runtime子目录。
    shutil.rmtree(baseline_dir)
