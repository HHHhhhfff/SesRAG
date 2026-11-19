"""在同一持久实例试跑统一入口，验证业务事实/卷/网络与其它项目保护。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from deployment.stack import Stack
from helpers.lifecycle import Environment
from helpers.preflight import MonitoringError


def protected(env):
    ids = env.run(["docker", "ps", "-aq"]).split()
    containers = json.loads(env.run(["docker", "inspect", *ids])) if ids else []
    return sorted(
        c["Id"]
        for c in containers
        if c["Config"].get("Labels", {}).get("com.docker.compose.project")
        not in {"sesrag-live", "sesrag-observe-live"}
    )


def snapshot(env):
    stack = Stack()
    stack.check_state()
    inv = stack.inventory()
    # 只导出业务表的行数和内容摘要，既不读取明文回答也不改业务数据。
    sql = " UNION ALL ".join(
        f"SELECT '{table}|'||count(*)||'|'||coalesce(md5(string_agg("
        "md5(row_to_json(x)::text),'' ORDER BY md5(row_to_json(x)::text))),"
        f"'empty') FROM {table} x"
        for table in ("threads", "messages", "runs", "run_events", "documents", "chunks")
    )
    facts = stack.compose(
        "exec", "-T", "postgres", "psql", "-U", "sesrag", "-d", "sesrag", "-At", "-c", sql
    ).splitlines()
    net = next(n for n in inv["network"] if n["Name"] == "sesrag-live_default")
    # Docker named volume没有独立不可变ID，使用名称+CreatedAt+Mountpoint摘要由engine标识。
    volumes = [{"name": v["Name"], "created_at": v["CreatedAt"]} for v in inv["volume"]]
    return {
        "facts": facts,
        "network_id": net["Id"],
        "volumes": sorted(volumes, key=lambda v: v["name"]),
        "protected_containers": protected(env),
    }


def main():
    env = Environment("live-lifecycle")
    error = None
    expected = None
    try:
        with env.mutex():
            expected = snapshot(env)
            env.report["before"] = expected
            for action in ("Update", "Stop", "Destroy", "Update", "Start", "Verify"):
                print("试跑统一入口：" + action, flush=True)
                env.run(
                    [
                        "pwsh",
                        "-NoProfile",
                        "-File",
                        Path(__file__).resolve().parents[2] / "scripts/sesrag.ps1",
                        action,
                    ],
                    timeout=1800,
                )
                if action in ("Update", "Start"):
                    current = snapshot(env)
                    if current != expected:
                        raise MonitoringError("LIVE_LIFECYCLE_FACT_CHANGED", action)
                    env.report[action + "_snapshot"] = current
                if action == "Stop":
                    inv = Stack().inventory()
                    if any(c["State"]["Running"] for c in inv["container"]):
                        raise MonitoringError("LIVE_STOP_RUNNING")
                if action == "Destroy":
                    inv = Stack().inventory()
                    if inv["container"] or len(inv["volume"]) != 4 or len(inv["network"]) != 1:
                        raise MonitoringError("LIVE_DESTROY_BOUNDARY")
                    env.report["destroy_preserved"] = {
                        "application_volumes": len(inv["volume"]),
                        "application_network": inv["network"][0]["Id"],
                    }
                env.check(action + "入口真实试跑", "passed", "数据与其它project保护边界符合预期")
            env.report["after"] = snapshot(env)
            env.check(
                "生命周期闭环",
                "passed",
                "已更新/停止/销毁容器/重启；业务行数与摘要、卷创建身份、网络ID及原有容器ID一致，最终服务运行",
            )
    except BaseException as exc:
        error = (
            exc if isinstance(exc, MonitoringError) else MonitoringError("LIVE_LIFECYCLE_FAILED")
        )
        print("生命周期验证未完成：" + error.code, flush=True)
    finally:
        env.finish(error)
        target = Path(__file__).parent / "artifacts" / env.run_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "lifecycle.json").write_bytes((env.artifact / "report.json").read_bytes())
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
