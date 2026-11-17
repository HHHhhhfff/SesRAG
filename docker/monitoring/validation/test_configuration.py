# 模块独立导入需先加入父目录。
# ruff: noqa: E402
"""005 配置与安全边界；不连接 Docker，不借用前轮验收工程。"""

import copy
import json
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))
from helpers.preflight import (
    MonitoringError,
    safe_archive_members,
    safe_environment,
    validate_contract,
    validate_image_lock,
)
from helpers.render import alerts, configuration


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(
            (MODULE / "integration/application-contract.example.json").read_text()
        )

    def test_reference_contract_and_actual_metric_catalog(self):
        validate_contract(self.contract, check_source=False)

    def test_sink_quantity_and_24h_retention_are_both_bounded(self):
        from tools.telemetry_fixture import NotificationRing

        now = [1000.0]
        ring = NotificationRing(clock=lambda: now[0])
        for i in range(105):
            ring.append({"received_at": now[0], "id": i})
        self.assertEqual(len(ring.snapshot()), 100)
        self.assertEqual(ring.snapshot()[0]["id"], 5)
        now[0] += 86401
        self.assertEqual(ring.snapshot(), [])

    def test_bad_digest_and_latest_rejected_before_docker(self):
        lock = json.loads((MODULE / "images.lock.json").read_text())
        validate_image_lock(lock)
        for key, value in [
            ("reference", "grafana/grafana:latest"),
            ("digest", "sha256:" + "0" * 64),
        ]:
            bad = copy.deepcopy(lock)
            bad["images"]["grafana"][key] = value
            with self.subTest(key=key), self.assertRaises(MonitoringError):
                validate_image_lock(bad)

    def test_invalid_identity_host_path_and_extra_secret_rejected(self):
        for path, value in [
            (("environment_id",), "../escape"),
            (("services", "api", "targets", 0, "host"), "example.com"),
            (("services", "api", "targets", 0, "path"), "/metrics?key=secret"),
            (("services", "api", "targets", 0, "port"), 0),
            (("secret",), "forbidden"),
        ]:
            data = copy.deepcopy(self.contract)
            parent = data
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(MonitoringError):
                validate_contract(data, check_source=False)

    def test_missing_or_changed_binding_rejected(self):
        for change in ("missing", "type", "label"):
            data = copy.deepcopy(self.contract)
            if change == "missing":
                data["metrics"].pop()
            elif change == "type":
                data["metrics"][0]["type"] = "gauge"
            else:
                data["metrics"][0]["labels"].append("run_id")
            with self.subTest(change=change), self.assertRaises(MonitoringError):
                validate_contract(data, check_source=False)

    def test_global_snapshot_has_one_api_source_but_worker_can_have_multiple(self):
        data = copy.deepcopy(self.contract)
        data["services"]["api"]["targets"].append(
            {"host": "api-two", "port": 9101, "path": "/metrics"}
        )
        with self.assertRaises(MonitoringError):
            validate_contract(data, check_source=False)
        data = copy.deepcopy(self.contract)
        data["services"]["worker"]["targets"].append(
            {"host": "worker-two", "port": 9102, "path": "/metrics"}
        )
        validate_contract(data, check_source=False)

    def test_shell_override_and_unrelated_credentials_removed(self):
        with self.assertRaises(MonitoringError):
            safe_environment({"OBS_GRAFANA_PORT": "9999"})
        result = safe_environment(
            {"PATH": "bin", "MODEL_API_KEY": "sentinel", "COMPOSE_FILE": "evil"}
        )
        self.assertNotIn("MODEL_API_KEY", result)
        self.assertNotIn("COMPOSE_FILE", result)

    def test_render_has_unique_targets_and_no_public_ports(self):
        data = configuration(self.contract)
        app = [x for x in data["scrape_configs"] if x["job_name"].startswith("sesrag-")]
        self.assertTrue(app)
        self.assertTrue(all(x["honor_labels"] for x in app))
        targets = [t for job in app for group in job["static_configs"] for t in group["targets"]]
        self.assertEqual(len(targets), len(set(targets)))

    def test_alerts_preserve_unknown_and_source_guards(self):
        rules = alerts(self.contract)["groups"][0]["rules"]
        self.assertEqual(len(rules), 8)
        for rule in rules:
            self.assertEqual(rule["noDataState"], "NoData")
            self.assertEqual(rule["execErrState"], "Error")
            self.assertNotIn("or vector(0)", json.dumps(rule))
        queue = next(x for x in rules if x["uid"] == "obs005-queue-wait")
        self.assertIn("sesrag_snapshot_valid", json.dumps(queue))
        self.assertIn("sesrag_snapshot_initialized", json.dumps(queue))
        for key in ("api-error", "task-failures"):
            rule = next(x for x in rules if x["uid"] == "obs005-" + key)
            self.assertIn("==1", json.dumps(rule))

    def test_archive_traversal_links_and_expansion_rejected(self):
        import tarfile

        for name in ("../escape", "/absolute", "C:/windows", "safe/../../escape"):
            with self.subTest(name=name), self.assertRaises(MonitoringError):
                safe_archive_members([tarfile.TarInfo(name)], 1024)
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        with self.assertRaises(MonitoringError):
            safe_archive_members([link], 1024)
        large = tarfile.TarInfo("large")
        large.size = 1025
        with self.assertRaises(MonitoringError):
            safe_archive_members([large], 1024)


if __name__ == "__main__":
    unittest.main()
