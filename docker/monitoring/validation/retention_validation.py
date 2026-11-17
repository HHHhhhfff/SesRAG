"""005独立保留删除演练：保持72h/24h阈值，以受控旧时间数据验证物理删除。"""

import argparse
import json
import secrets
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.lifecycle import Environment, private_directory
from helpers.preflight import MODULE, PREFIX, MonitoringError, load
from helpers.render import write_json
from helpers.verify import request
from live_validation import wait


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tool-image", required=True)
    p.add_argument("--timeout", type=int, default=1200)
    a = p.parse_args()
    e = Environment("retention005")
    error = None
    try:
        with e.mutex():
            if e.state or any(e.inventory().values()):
                raise MonitoringError("OBS005_RETENTION_NOT_EMPTY")
            private_directory(e.path)
            owner = uuid.uuid4().hex
            e.state = {
                "owner": owner,
                "status": "starting",
                "tool_image": a.tool_image,
                "resources": {},
                "daemon_id": e.run(["docker", "info", "--format", "{{.ID}}"]).strip(),
            }
            e.save()
            labels = [
                "--label",
                "com.docker.compose.project=" + e.project,
                "--label",
                PREFIX + "module=obs005",
                "--label",
                PREFIX + "environment=" + e.environment,
                "--label",
                PREFIX + "owner=" + owner,
            ]
            e.run(["docker", "network", "create", *labels, e.project + "_monitoring"])
            loki = load(MODULE / "loki/config.yaml")
            loki["limits_config"]["reject_old_samples"] = False
            loki["ingester"].update(
                chunk_idle_period="5s", max_chunk_age="10s", chunk_retain_period="1s"
            )
            loki["compactor"].update(
                compaction_interval="5s",
                retention_delete_delay="5s",
                retention_delete_worker_count=1,
            )
            # 首次先禁止删除以观察旧数据确实被持久化，再启用同一72h策略。
            loki["compactor"]["retention_enabled"] = False
            loki["querier"] = {"query_ingesters_within": "0s"}
            tempo = load(MODULE / "tempo/config.yaml")
            tempo["storage"]["trace"].update(blocklist_poll="5s")
            tempo["storage"]["trace"]["wal"]["ingestion_time_range_slack"] = "26h"
            tempo["live_store"] = {
                "wal": {
                    "path": "/var/tempo/live-store/traces",
                    "ingestion_time_range_slack": "26h",
                },
                "max_block_duration": "10s",
                "max_trace_idle": "2s",
                "max_trace_live": "5s",
                "block_reclaim_grace": "5s",
            }
            tempo["backend_scheduler"] = {
                "maintenance_interval": "5s",
                "backend_flush_interval": "5s",
                "provider": {"retention": {"interval": "8760h"}},
            }
            tempo["backend_worker"] = {"compaction": {"compacted_block_retention": "5s"}}
            generated = e.path / "generated"
            write_json(generated / "loki.json", loki)
            write_json(generated / "tempo.json", tempo)
            for key, target in [("loki", "/loki"), ("tempo", "/var/tempo")]:
                volume = e.project + "_" + key + "_data"
                e.run(["docker", "volume", "create", *labels, volume])
                e.run(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--pull=never",
                        "--memory=1536m",
                        "--cpus=1",
                        "--cap-drop=ALL",
                        *labels,
                        "--name",
                        e.project + "-" + key,
                        "--network",
                        e.project + "_monitoring",
                        "--network-alias",
                        key,
                        "-v",
                        volume + ":" + target,
                        "-v",
                        str((generated / (key + ".json")).resolve()) + ":/config.json:ro",
                        e.images[key]["reference"],
                        "-config.file=/config.json",
                    ]
                )
            e.state["resources"] = e.inventory()
            e.save("running")
            wait(e, "隔离Loki ready", lambda: request(e, "http://loki:3100/ready"), 180)
            wait(e, "隔离Tempo ready", lambda: request(e, "http://tempo:3200/ready"), 180)
            now = time.time_ns()
            old_log = now - 73 * 3600 * 10**9
            old_span = now - 25 * 3600 * 10**9
            trace = secrets.token_hex(16)
            request(
                e,
                "http://loki:3100/loki/api/v1/push",
                data={
                    "streams": [
                        {
                            "stream": {
                                "environment": "retention005",
                                "service": "obs005-retention",
                            },
                            "values": [[str(old_log), '{"action":"retention_fixture"}']],
                        }
                    ]
                },
            )
            request(
                e,
                "http://tempo:4318/v1/traces",
                data={
                    "resourceSpans": [
                        {
                            "resource": {
                                "attributes": [
                                    {
                                        "key": "service.name",
                                        "value": {"stringValue": "obs005-retention"},
                                    }
                                ]
                            },
                            "scopeSpans": [
                                {
                                    "spans": [
                                        {
                                            "traceId": trace,
                                            "spanId": secrets.token_hex(8),
                                            "name": "retention.fixture",
                                            "startTimeUnixNano": str(old_span),
                                            "endTimeUnixNano": str(old_span + 1000000),
                                            "kind": 1,
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                },
            )

            def log_query():
                q = urllib.parse.urlencode(
                    {
                        "query": '{environment="retention005"}',
                        "start": str(old_log - 1000000000),
                        "end": str(old_log + 1000000000),
                        "limit": 10,
                    }
                )
                return request(e, "http://loki:3100/loki/api/v1/query_range?" + q)["data"]["result"]

            wait(e, "73h旧日志可查", log_query, 90)
            wait(
                e, "25h旧trace可查", lambda: request(e, "http://tempo:3200/api/traces/" + trace), 90
            )

            def files(key):
                volume = e.project + "_" + key + "_data"
                return json.loads(
                    e.tool(
                        ["/tools/volume_inspector.py", "files"],
                        network=False,
                        mounts=[(volume, "/source", True)],
                    )
                )

            before_loki = wait(
                e,
                "Loki旧chunk持久化",
                lambda: [x for x in files("loki") if x.startswith("chunks/fake/")],
                180,
            )
            before_tempo = wait(
                e,
                "Tempo旧block持久化",
                lambda: [
                    x for x in files("tempo") if x.startswith("blocks/") and x.endswith("meta.json")
                ],
                180,
            )
            e.report["before"] = {
                "log_timestamp_age_h": 73,
                "trace_timestamp_age_h": 25,
                "loki_chunks": before_loki,
                "tempo_meta": before_tempo,
            }
            e.check(
                "旧数据实际落盘/查询",
                "passed",
                "固定版本接受合法旧时间，阈值仍72h/24h，未伪造过期成功",
            )
            loki["compactor"]["retention_enabled"] = True
            tempo["backend_scheduler"]["provider"]["retention"]["interval"] = "5s"
            write_json(generated / "loki.json", loki)
            write_json(generated / "tempo.json", tempo)
            e.run(["docker", "restart", e.project + "-loki", e.project + "-tempo"], timeout=90)
            wait(
                e,
                "Loki旧chunk物理删除",
                lambda: not (set(before_loki) & set(files("loki"))),
                a.timeout,
            )
            wait(
                e,
                "Tempo旧block物理删除",
                lambda: not (set(before_tempo) & set(files("tempo"))),
                a.timeout,
            )
            e.report["after"] = {"loki_files": files("loki"), "tempo_files": files("tempo")}
            e.check(
                "保留期物理删除",
                "passed",
                "已观察固定旧chunk/block文件消失；加速维护周期，不降低72h/24h阈值",
            )
    except BaseException as exc:
        error = exc
        print(str(exc), flush=True)
    finally:
        try:
            if e.state:
                inv = e.inventory()
                for c in inv["container"]:
                    e.run(["docker", "rm", "-f", c["id"]])
                for n in e.inventory()["network"]:
                    e.run(["docker", "network", "rm", n["id"]])
                for v in e.inventory()["volume"]:
                    e.run(["docker", "volume", "rm", v["id"]])
                import shutil

                from helpers.lifecycle import checked_child

                shutil.rmtree(checked_child(MODULE / "runtime", e.path))
                e.check("保留演练清理", "passed", "仅本次retention005资源已删除")
        except BaseException as cleanup:
            error = cleanup
        e.finish(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
