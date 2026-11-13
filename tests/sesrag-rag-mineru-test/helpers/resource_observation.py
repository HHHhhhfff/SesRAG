"""宿主侧有限资源采样；仅接收已验证归属的不可变容器ID，不向tools挂Docker socket。"""

import json
import math
import re
import subprocess
import threading
import time


def memory_bytes(value):
    match = re.fullmatch(r"([0-9.]+)\s*([KMGT]?i?B)", value.strip())
    if not match:
        raise ValueError("STATS_MEMORY_INVALID")
    units = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
    }
    return int(float(match[1]) * units[match[2]])


def resource_summary(samples, *, failures=0, missed=0):
    return {
        "samples": len(samples),
        "failures": failures,
        "missed_container_samples": missed,
        "sampled_peak_cpu_percent": max((s["cpu_percent"] for s in samples), default=None),
        "sampled_peak_memory_bytes": max((s["memory_bytes"] for s in samples), default=None),
        "continuous_peak_proven": False,
        "scope": "单容器离散样本最大值；非连续峰值、非全project同时内存总量",
    }


class ResourceSampler:
    def __init__(self, owned_ids, *, interval=2, max_samples=900, runner=subprocess.run):
        self.ids = tuple(dict.fromkeys(owned_ids))
        if (
            not self.ids
            or len(self.ids) > 64
            or any(not re.fullmatch(r"[a-f0-9]{64}", x) for x in self.ids)
        ):
            raise ValueError("STATS_OWNED_IDS_INVALID")
        if not 1 <= interval <= 60 or not 1 <= max_samples <= 1800:
            raise ValueError("STATS_BOUNDS_INVALID")
        self.interval, self.max_samples, self.runner = interval, max_samples, runner
        self.samples, self.failures, self.missed, self.rounds = [], 0, 0, 0
        self.stop_event = threading.Event()
        self.thread = None

    def sample(self):
        self.rounds += 1
        observed = set()
        try:
            result = self.runner(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}", *self.ids],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode:
                raise ValueError("STATS_COMMAND_FAILED")
            for line in result.stdout.splitlines()[: len(self.ids)]:
                row = json.loads(line)
                short = row.get("ID", row.get("Container", ""))
                matches = [x for x in self.ids if x.startswith(short) and len(short) >= 12]
                if len(matches) != 1:
                    raise ValueError("STATS_CONTAINER_NOT_OWNED")
                container = matches[0]
                cpu = float(row["CPUPerc"].rstrip("%"))
                memory = memory_bytes(row["MemUsage"].split("/")[0])
                if not math.isfinite(cpu) or cpu < 0 or memory < 0 or container in observed:
                    raise ValueError("STATS_VALUE_INVALID")
                observed.add(container)
                self.samples.append(
                    {
                        "elapsed_seconds": round(time.monotonic() - self.started, 3),
                        "container": container,
                        "cpu_percent": cpu,
                        "memory_bytes": memory,
                    }
                )
        except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
            self.failures += 1
        finally:
            self.missed += len(self.ids) - len(observed)

    def start(self):
        self.started = time.monotonic()

        def loop():
            for _ in range(self.max_samples):
                if self.stop_event.is_set():
                    break
                self.sample()
                if self.stop_event.wait(self.interval):
                    break

        self.thread = threading.Thread(target=loop, name="rag-owned-resource-sampler", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=7)
            if self.thread.is_alive():
                raise ValueError("STATS_THREAD_STOP_FAILED")
        return {
            **resource_summary(self.samples, failures=self.failures, missed=self.missed),
            "rounds": self.rounds,
            "interval_seconds": self.interval,
            "max_rounds": self.max_samples,
            "samples_raw": self.samples,
            "sampling_window_exhausted": self.rounds >= self.max_samples,
        }


def performance_summary(categories, observations):
    executed = [
        r for r in categories if r["category"] == "performance" and r["status"] != "not_run"
    ]
    return {
        "status": executed[-1]["status"]
        if executed
        else ("partial_observed" if observations else "not_run"),
        "local_database_and_controlled_timing": executed,
        "resource_evidence": observations,
        "real_parse_resource_sampling": "sampled_during_real_category"
        if any(r["lane"] == "real" and r["samples"] > 0 for r in observations)
        else "not_run",
        "four_capability_full_chain": "not_run",
        "scope": "资源采样存在不代表真实全链性能已执行；效果评测保持独立",
    }
